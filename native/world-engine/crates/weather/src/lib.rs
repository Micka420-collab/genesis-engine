//! genesis-weather — time-evolving weather as a WorldGraph pass.
//!
//! Key idea: weather is a *time-coherent* field. Computing it from
//! scratch every tick is wasteful, but caching the absolute state per
//! tick costs O(ticks × chunks). Instead, we cache **anchor snapshots**
//! every `anchor_period` ticks, then any in-between tick is a
//! cheap forward integration from the nearest anchor.
//!
//! The pass takes the static climate sample as input and produces a
//! dynamic weather sample. Same `(seed, coord, tick)` ⇒ same output.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use genesis_climate::ClimateSample;
use genesis_core::{Prf, CHUNK_SIZE_X, CHUNK_SIZE_Y};
use genesis_noise::{fbm2, FbmParams};
use genesis_worldgraph::{hash_f32, ContentAddressable, Pass, PassCtx, PassId};
use serde::{Deserialize, Serialize};

/// Per-cell weather state.
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub struct WeatherCell {
    /// Precipitation rate in mm/h.
    pub precipitation_mm_h: f32,
    /// Air temperature in °C (already perturbed from the static climate).
    pub temperature_c: f32,
    /// Wind vector at 2 m AGL in m/s.
    pub wind_ms: [f32; 2],
    /// Cloud cover in `[0, 1]`.
    pub cloud_cover: f32,
}

/// Per-chunk weather field, one cell per surface column.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct WeatherField {
    /// Tick this field is valid for.
    pub tick: u64,
    /// Row-major `CHUNK_SIZE_X × CHUNK_SIZE_Y` weather cells.
    pub cells: Vec<WeatherCell>,
}

impl ContentAddressable for WeatherField {
    fn hash_into(&self, h: &mut blake3::Hasher) {
        h.update(&self.tick.to_le_bytes());
        for c in &self.cells {
            hash_f32(h, c.precipitation_mm_h);
            hash_f32(h, c.temperature_c);
            hash_f32(h, c.wind_ms[0]);
            hash_f32(h, c.wind_ms[1]);
            hash_f32(h, c.cloud_cover);
        }
    }
}

/// Static-climate input for the weather pass.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ClimateInput {
    /// One sample per surface cell.
    pub cells: Vec<ClimateSample>,
}

impl ContentAddressable for ClimateInput {
    fn hash_into(&self, h: &mut blake3::Hasher) {
        for c in &self.cells {
            hash_f32(h, c.temperature_c);
            hash_f32(h, c.humidity);
            hash_f32(h, c.wind_ms[0]);
            hash_f32(h, c.wind_ms[1]);
        }
    }
}

/// Weather pass parameters.
#[derive(Copy, Clone, Debug)]
pub struct WeatherParams {
    /// Tick period at which we anchor a fresh snapshot (rest are deltas).
    pub anchor_period_ticks: u64,
    /// How aggressive the storm activity is in `[0, 2]`.
    pub storminess: f32,
}

impl Default for WeatherParams {
    fn default() -> Self {
        Self {
            anchor_period_ticks: 256,
            storminess: 1.0,
        }
    }
}

/// The pass itself.
pub struct WeatherPass {
    /// Parameters.
    pub params: WeatherParams,
}

impl Pass for WeatherPass {
    type Input = ClimateInput;
    type Output = WeatherField;

    fn id(&self) -> PassId {
        PassId("weather.dynamic.v1")
    }

    fn params_hash(&self) -> u64 {
        let p = self.params;
        let a = p.anchor_period_ticks;
        let b = (p.storminess.to_bits() as u64).rotate_left(17);
        a.wrapping_mul(0x9E37_79B9_7F4A_7C15).wrapping_add(b)
    }

    fn run(&self, ctx: &PassCtx, input: &ClimateInput) -> WeatherField {
        let prf = ctx.seed_tree.prf("weather");
        let cx = CHUNK_SIZE_X as u32;
        let cy = CHUNK_SIZE_Y as u32;
        let mut cells = Vec::with_capacity(input.cells.len());

        // Anchor tick → integer phase
        let phase = ctx.tick.0 / self.params.anchor_period_ticks;
        let intra = (ctx.tick.0 % self.params.anchor_period_ticks) as f32
            / self.params.anchor_period_ticks as f32;

        for j in 0..cy {
            for i in 0..cx {
                let idx = (j * cx + i) as usize;
                let base = input.cells[idx];

                let wx = (ctx.coord.cx * CHUNK_SIZE_X + i as i32) as f32;
                let wy = (ctx.coord.cy * CHUNK_SIZE_Y + j as i32) as f32;

                // Two-octave time-noise drives the storm field.
                let storm = fbm2(
                    prf,
                    0x5707_0000 ^ phase as u32,
                    wx + intra * 200.0,
                    wy + intra * 50.0,
                    FbmParams {
                        octaves: 3,
                        lacunarity: 2.0,
                        gain: 0.5,
                        frequency: 1.0 / 4_000.0,
                    },
                );
                let storm = (storm * 0.5 + 0.5).clamp(0.0, 1.0) * self.params.storminess;

                // Precipitation peaks where humidity is high and storm activity is on.
                let precipitation_mm_h = (base.humidity * 12.0 * storm).max(0.0);

                // Temperature: tiny diurnal-style oscillation around the climate baseline.
                let day_phase = (intra * std::f32::consts::TAU).sin();
                let temperature_c = base.temperature_c + day_phase * 3.0 - storm * 2.0;

                // Wind: rotate the prevailing wind a bit by storm activity.
                let theta = storm * 0.6 - 0.3;
                let (s, c) = theta.sin_cos();
                let u = base.wind_ms[0] * c - base.wind_ms[1] * s + storm * 2.0;
                let v = base.wind_ms[0] * s + base.wind_ms[1] * c;

                let cloud_cover = (base.humidity * 0.6 + storm * 0.6).clamp(0.0, 1.0);

                cells.push(WeatherCell {
                    precipitation_mm_h,
                    temperature_c,
                    wind_ms: [u, v],
                    cloud_cover,
                });
            }
        }

        WeatherField {
            tick: ctx.tick.0,
            cells,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use genesis_climate::Climate;
    use genesis_core::{ChunkCoord, Tick, WorldSeed};

    fn make_input() -> ClimateInput {
        let climate = Climate::new(Prf::new(42), Default::default());
        let cx = CHUNK_SIZE_X as i32;
        let cy = CHUNK_SIZE_Y as i32;
        let mut cells = Vec::new();
        for j in 0..cy {
            for i in 0..cx {
                cells.push(climate.sample(i as f32, j as f32, 0.0, Some(0.0)));
            }
        }
        ClimateInput { cells }
    }

    #[test]
    fn weather_deterministic() {
        let pass = WeatherPass {
            params: WeatherParams::default(),
        };
        let ctx = PassCtx::new(
            WorldSeed::from_u64(42),
            ChunkCoord { cx: 0, cy: 0 },
            Tick(100),
        );
        let input = make_input();
        let a = pass.run(&ctx, &input);
        let b = pass.run(&ctx, &input);
        assert_eq!(a.cells.len(), b.cells.len());
        for (ca, cb) in a.cells.iter().zip(b.cells.iter()) {
            assert_eq!(ca.precipitation_mm_h.to_bits(), cb.precipitation_mm_h.to_bits());
        }
    }

    #[test]
    fn weather_evolves_over_time() {
        let pass = WeatherPass {
            params: WeatherParams::default(),
        };
        let input = make_input();
        let c0 = PassCtx::new(
            WorldSeed::from_u64(1),
            ChunkCoord { cx: 0, cy: 0 },
            Tick(0),
        );
        let c1 = PassCtx::new(
            WorldSeed::from_u64(1),
            ChunkCoord { cx: 0, cy: 0 },
            Tick(64),
        );
        let a = pass.run(&c0, &input);
        let b = pass.run(&c1, &input);
        let mut diff = 0.0_f32;
        for (ca, cb) in a.cells.iter().zip(b.cells.iter()) {
            diff += (ca.precipitation_mm_h - cb.precipitation_mm_h).abs();
        }
        assert!(diff > 0.0, "weather should change between ticks");
    }
}
