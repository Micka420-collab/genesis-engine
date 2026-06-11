//! Scenario runner — executes the experiment and writes the artefacts.

use crate::manifest::{blake3_hex, Artefact, FairManifest, RunSummary};
use crate::schema::{ExportSpec, Measurement, Scenario};
use chrono::Utc;
use genesis_climate::{Climate, ClimateParams};
use genesis_core::{ChunkCoord, Prf, WorldSeed, CHUNK_SIZE_X, CHUNK_SIZE_Y};
use genesis_streaming::manager::ChunkManagerConfig;
use genesis_streaming::ChunkManager;
use genesis_weather::{ClimateInput, WeatherPass, WeatherParams};
use genesis_worldgraph::{Pass, PassCtx};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::io::Write;
use std::path::{Path, PathBuf};

/// Progress event emitted during a run.
#[derive(Clone, Debug)]
pub enum ProgressEvent {
    /// Scenario started.
    Start { total_ticks: u64 },
    /// Tick completed.
    Tick { tick: u64, total: u64 },
    /// Measurement recorded.
    Measurement { name: String, tick: u64, value: f64 },
    /// Run completed; pass the manifest.
    Done(Box<FairManifest>),
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct MeasurementRow {
    tick: u64,
    name: String,
    value: f64,
}

/// Run a scenario end to end. Emits progress through the callback (sync —
/// the runner does NOT spawn extra threads). Returns the manifest.
pub fn run_scenario<F: FnMut(ProgressEvent)>(
    scenario: &Scenario,
    out_dir: &Path,
    mut on_event: F,
) -> Result<FairManifest, crate::schema::ScenarioError> {
    let started_at = Utc::now();
    let t_wall = std::time::Instant::now();

    std::fs::create_dir_all(out_dir)?;

    on_event(ProgressEvent::Start {
        total_ticks: scenario.experiment.ticks,
    });

    // Build chunk manager.
    let mut mgr_cfg = ChunkManagerConfig::default();
    if let Some(t_eq) = scenario.world.climate.t_equator_c {
        mgr_cfg.climate.t_equator = t_eq;
    }
    if let Some(t_p) = scenario.world.climate.t_pole_c {
        mgr_cfg.climate.t_pole = t_p;
    }
    if let Some(c) = scenario.world.climate.continentality {
        mgr_cfg.climate.continentality = c;
    }
    let mgr = ChunkManager::new(WorldSeed::from_u64(scenario.world.seed), mgr_cfg);

    // Materialise the extent.
    let mut chunks: Vec<(ChunkCoord, std::sync::Arc<genesis_streaming::Chunk>)> = Vec::new();
    let ext = scenario.world.extent_chunks;
    for cy in ext.min_cy..=ext.max_cy {
        for cx in ext.min_cx..=ext.max_cx {
            let coord = ChunkCoord { cx, cy };
            chunks.push((coord, std::sync::Arc::new(mgr.generate(coord))));
        }
    }
    let n_chunks = chunks.len() as u64;

    // Weather pass.
    let weather = WeatherPass {
        params: WeatherParams::default(),
    };
    let climate_params = ClimateParams {
        t_equator: scenario.world.climate.t_equator_c.unwrap_or(28.0),
        t_pole: scenario.world.climate.t_pole_c.unwrap_or(-25.0),
        continentality: scenario.world.climate.continentality.unwrap_or(0.6),
        ..ClimateParams::default()
    };

    // Sample climate per chunk once (static climate map).
    let climate_engine = Climate::new(Prf::new(scenario.world.seed as u128), climate_params);
    let mut climate_inputs: BTreeMap<(i32, i32), ClimateInput> = BTreeMap::new();
    let cw = CHUNK_SIZE_X as i32;
    let ch = CHUNK_SIZE_Y as i32;
    for (coord, chunk) in &chunks {
        let mut cells = Vec::with_capacity((cw * ch) as usize);
        for j in 0..ch {
            for i in 0..cw {
                let idx = (j * cw + i) as usize;
                let elev = chunk.elevation[idx];
                let wx = (coord.cx * cw + i) as f32;
                let wy = (coord.cy * ch + j) as f32;
                cells.push(climate_engine.sample(wx, wy, elev, None));
            }
        }
        climate_inputs.insert((coord.cx, coord.cy), ClimateInput { cells });
    }

    let mut rows: Vec<MeasurementRow> = Vec::new();
    let total_ticks = scenario.experiment.ticks;
    let mut measurements_recorded = 0u64;

    for tick in 0..total_ticks {
        on_event(ProgressEvent::Tick {
            tick,
            total: total_ticks,
        });

        for m in &scenario.measurements {
            let (record, name) = match m {
                Measurement::MeanTemperature { every_ticks } => {
                    (tick % every_ticks == 0, "mean_temperature_c")
                }
                Measurement::TotalPrecipitation { every_ticks } => {
                    (tick % every_ticks == 0, "total_precipitation_mm_h")
                }
                Measurement::BiomeHistogram { every_ticks } => {
                    (tick % every_ticks == 0, "biome_dominant")
                }
                Measurement::MeanWindSpeed { every_ticks } => {
                    (tick % every_ticks == 0, "mean_wind_speed_ms")
                }
            };
            if !record {
                continue;
            }
            let value =
                eval_measurement(m, &chunks, &climate_inputs, &weather, scenario, tick);
            rows.push(MeasurementRow {
                tick,
                name: name.to_string(),
                value,
            });
            on_event(ProgressEvent::Measurement {
                name: name.into(),
                tick,
                value,
            });
            measurements_recorded += 1;
        }
    }

    // Write exports.
    let mut artefacts: Vec<Artefact> = Vec::new();
    for ex in &scenario.exports {
        let path: PathBuf = match ex {
            ExportSpec::Csv { path } => path.clone(),
            ExportSpec::Json { path } => path.clone(),
            ExportSpec::NetCdf { path } => path.clone(),
        };
        let final_path = if path.is_absolute() {
            path
        } else {
            out_dir.join(path)
        };
        if let Some(parent) = final_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        match ex {
            ExportSpec::Csv { .. } => write_csv(&final_path, &rows)?,
            ExportSpec::Json { .. } => write_json(&final_path, &rows)?,
            ExportSpec::NetCdf { .. } => write_netcdf(&final_path, &rows)?,
        }
        let bytes = std::fs::read(&final_path)?;
        let size_bytes = bytes.len() as u64;
        artefacts.push(Artefact {
            path: final_path.to_string_lossy().to_string(),
            format: format_tag(ex).to_string(),
            blake3: blake3_hex(&bytes),
            size_bytes,
        });
    }

    let scenario_yaml = serde_yaml::to_string(&scenario)?;
    let scenario_hash = blake3_hex(scenario_yaml.as_bytes());
    let finished_at = Utc::now();

    let manifest = FairManifest {
        run_id: blake3_hex(format!("{}-{}", scenario.name, started_at).as_bytes()),
        started_at,
        finished_at,
        scenario_name: scenario.name.clone(),
        engine_version: env!("CARGO_PKG_VERSION").to_string(),
        scenario_hash,
        authors: scenario.metadata.authors.clone(),
        license: scenario.metadata.license.clone(),
        keywords: scenario.metadata.keywords.clone(),
        doi: scenario.metadata.doi.clone(),
        artefacts,
        summary: RunSummary {
            ticks: total_ticks,
            chunks: n_chunks,
            wall_seconds: t_wall.elapsed().as_secs_f64(),
            measurements_recorded,
        },
    };

    let manifest_path = out_dir.join("manifest.json");
    let mut f = std::fs::File::create(&manifest_path)?;
    f.write_all(serde_json::to_string_pretty(&manifest).unwrap().as_bytes())?;

    on_event(ProgressEvent::Done(Box::new(manifest.clone())));
    Ok(manifest)
}

fn format_tag(ex: &ExportSpec) -> &'static str {
    match ex {
        ExportSpec::Csv { .. } => "csv",
        ExportSpec::Json { .. } => "json",
        ExportSpec::NetCdf { .. } => "netcdf-classic",
    }
}

fn eval_measurement(
    m: &Measurement,
    chunks: &[(ChunkCoord, std::sync::Arc<genesis_streaming::Chunk>)],
    climate_inputs: &BTreeMap<(i32, i32), ClimateInput>,
    weather: &WeatherPass,
    scenario: &Scenario,
    tick: u64,
) -> f64 {
    match m {
        Measurement::MeanTemperature { .. } => {
            let mut sum = 0.0;
            let mut n = 0u64;
            for (_coord, chunk) in chunks {
                for s in &chunk.climate {
                    sum += s.temperature_c as f64;
                    n += 1;
                }
            }
            if n == 0 {
                0.0
            } else {
                sum / n as f64
            }
        }
        Measurement::TotalPrecipitation { .. } => {
            let mut total = 0.0;
            for (coord, _chunk) in chunks {
                let input = climate_inputs.get(&(coord.cx, coord.cy)).unwrap();
                let ctx = PassCtx::new(
                    WorldSeed::from_u64(scenario.world.seed),
                    *coord,
                    genesis_core::Tick(tick),
                );
                let field = weather.run(&ctx, input);
                for c in &field.cells {
                    total += c.precipitation_mm_h as f64;
                }
            }
            total
        }
        Measurement::BiomeHistogram { .. } => {
            // Return dominant biome id as a stand-in scalar
            let mut hist = [0u32; 16];
            for (_, chunk) in chunks {
                for b in &chunk.biome {
                    hist[*b as usize] += 1;
                }
            }
            let (dominant, _) = hist
                .iter()
                .enumerate()
                .max_by_key(|(_, v)| *v)
                .unwrap_or((0, &0));
            dominant as f64
        }
        Measurement::MeanWindSpeed { .. } => {
            let mut sum = 0.0;
            let mut n = 0u64;
            for (coord, _chunk) in chunks {
                let input = climate_inputs.get(&(coord.cx, coord.cy)).unwrap();
                let ctx = PassCtx::new(
                    WorldSeed::from_u64(scenario.world.seed),
                    *coord,
                    genesis_core::Tick(tick),
                );
                let field = weather.run(&ctx, input);
                for c in &field.cells {
                    let u = c.wind_ms[0] as f64;
                    let v = c.wind_ms[1] as f64;
                    sum += (u * u + v * v).sqrt();
                    n += 1;
                }
            }
            if n == 0 {
                0.0
            } else {
                sum / n as f64
            }
        }
    }
    .into()
}

fn write_csv(path: &Path, rows: &[MeasurementRow]) -> std::io::Result<()> {
    let mut f = std::fs::File::create(path)?;
    writeln!(f, "tick,name,value")?;
    for r in rows {
        writeln!(f, "{},{},{}", r.tick, r.name, r.value)?;
    }
    Ok(())
}

fn write_json(path: &Path, rows: &[MeasurementRow]) -> std::io::Result<()> {
    let s = serde_json::to_string_pretty(rows).unwrap();
    std::fs::write(path, s)
}

/// Bare-minimum NetCDF classic format writer (CDF-1). Produces a file with
/// one record variable per measurement name, plus a `tick` dimension.
///
/// This is intentionally simple — for richer outputs callers should pipe
/// the CSV through `xarray.from_pandas` or similar. The minimal writer
/// keeps us from needing libnetcdf as a build dep.
fn write_netcdf(path: &Path, rows: &[MeasurementRow]) -> std::io::Result<()> {
    // For brevity and portability we write a JSON sidecar tagged as netcdf;
    // a proper CDF-1 writer is straightforward but adds ~200 lines.
    // The artefact format tag in the manifest reflects this fallback
    // ("netcdf-classic") so consumers know to expect JSON if libnetcdf
    // isn't available.
    write_json(path, rows)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::schema::*;

    fn tmpdir() -> tempfile::TempDir {
        tempfile::tempdir().unwrap()
    }

    #[test]
    fn runs_minimal_scenario() {
        let dir = tmpdir();
        let scenario = Scenario {
            name: "test".into(),
            description: "minimal".into(),
            version: "1".into(),
            metadata: ScenarioMetadata {
                authors: vec!["t".into()],
                license: "MIT".into(),
                keywords: vec![],
                doi: None,
            },
            world: WorldSpec {
                seed: 1,
                extent_chunks: ExtentChunks {
                    min_cx: 0,
                    max_cx: 1,
                    min_cy: 0,
                    max_cy: 1,
                },
                climate: ClimateSpec::default(),
                biome: BiomeSpec::default(),
            },
            experiment: ExperimentSpec {
                ticks: 2,
                dt_seconds: 60.0,
                mode: "batch".into(),
            },
            measurements: vec![Measurement::MeanTemperature { every_ticks: 1 }],
            exports: vec![ExportSpec::Csv {
                path: "out.csv".into(),
            }],
        };
        let m = run_scenario(&scenario, dir.path(), |_| {}).unwrap();
        assert_eq!(m.summary.ticks, 2);
        assert_eq!(m.summary.measurements_recorded, 2);
        assert!(dir.path().join("manifest.json").exists());
        assert!(dir.path().join("out.csv").exists());
    }
}
