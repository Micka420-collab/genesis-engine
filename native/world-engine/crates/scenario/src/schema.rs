//! Scenario YAML schema.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use thiserror::Error;

/// Errors loading or validating a scenario.
#[derive(Error, Debug)]
pub enum ScenarioError {
    /// YAML parse failure.
    #[error("yaml: {0}")]
    Yaml(#[from] serde_yaml::Error),
    /// Filesystem error.
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    /// Validation failure (semantically invalid scenario).
    #[error("invalid scenario: {0}")]
    Invalid(String),
}

/// Top-level scenario document.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Scenario {
    /// Human-friendly name.
    pub name: String,
    /// Short description (one paragraph).
    pub description: String,
    /// Schema version (currently always "1").
    #[serde(default = "default_version")]
    pub version: String,
    /// FAIR metadata.
    pub metadata: ScenarioMetadata,
    /// World description.
    pub world: WorldSpec,
    /// Experiment description.
    pub experiment: ExperimentSpec,
    /// Measurements to record.
    #[serde(default)]
    pub measurements: Vec<Measurement>,
    /// Exports to produce at the end.
    #[serde(default)]
    pub exports: Vec<ExportSpec>,
}

fn default_version() -> String {
    "1".into()
}

/// Authoring + licensing info.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ScenarioMetadata {
    /// Author(s).
    pub authors: Vec<String>,
    /// SPDX license expression (e.g. "Apache-2.0").
    pub license: String,
    /// Free-text keywords / tags.
    #[serde(default)]
    pub keywords: Vec<String>,
    /// Optional DOI / preprint URL.
    #[serde(default)]
    pub doi: Option<String>,
}

/// World specification.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct WorldSpec {
    /// World seed.
    pub seed: u64,
    /// Geographic extent (in chunks).
    pub extent_chunks: ExtentChunks,
    /// Optional climate overrides.
    #[serde(default)]
    pub climate: ClimateSpec,
    /// Optional biome overrides.
    #[serde(default)]
    pub biome: BiomeSpec,
}

/// Bounding box in chunk coordinates (inclusive on both ends).
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub struct ExtentChunks {
    /// Min cx (inclusive).
    pub min_cx: i32,
    /// Max cx (inclusive).
    pub max_cx: i32,
    /// Min cy (inclusive).
    pub min_cy: i32,
    /// Max cy (inclusive).
    pub max_cy: i32,
}

impl ExtentChunks {
    /// Number of chunks in this extent.
    #[must_use]
    pub fn count(&self) -> i64 {
        let w = (self.max_cx - self.min_cx + 1) as i64;
        let h = (self.max_cy - self.min_cy + 1) as i64;
        w * h
    }
}

/// Climate overrides — leave fields `None` to use the engine default.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct ClimateSpec {
    /// Equatorial temperature in °C.
    pub t_equator_c: Option<f32>,
    /// Polar temperature in °C.
    pub t_pole_c: Option<f32>,
    /// Continentality factor in `[0, 1]`.
    pub continentality: Option<f32>,
}

/// Biome overrides — placeholder for future custom rules.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct BiomeSpec {
    /// If set, only consider these biome IDs.
    #[serde(default)]
    pub allow: Vec<String>,
}

/// Experiment specification.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExperimentSpec {
    /// Number of simulation ticks to run.
    pub ticks: u64,
    /// Real-world seconds per tick (default 1 day).
    #[serde(default = "default_dt_seconds")]
    pub dt_seconds: f64,
    /// Run mode (currently only "batch").
    #[serde(default = "default_mode")]
    pub mode: String,
}

fn default_dt_seconds() -> f64 {
    86_400.0
}
fn default_mode() -> String {
    "batch".into()
}

/// A measurement to record per-tick or at fixed intervals.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "kind")]
pub enum Measurement {
    /// Mean surface temperature of the extent.
    MeanTemperature {
        /// Record every N ticks.
        every_ticks: u64,
    },
    /// Total precipitation (mm) over the extent.
    TotalPrecipitation {
        /// Record every N ticks.
        every_ticks: u64,
    },
    /// Biome distribution histogram.
    BiomeHistogram {
        /// Record every N ticks.
        every_ticks: u64,
    },
    /// Mean wind speed.
    MeanWindSpeed {
        /// Record every N ticks.
        every_ticks: u64,
    },
}

/// Where + how to export results.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "format")]
pub enum ExportSpec {
    /// Write a CSV of measurements.
    Csv {
        /// Output path (will be created).
        path: PathBuf,
    },
    /// Write a JSON dump of measurements + manifest.
    Json {
        /// Output path.
        path: PathBuf,
    },
    /// Write a NetCDF-3 file with measurement variables along the tick axis.
    /// Minimal classic-format writer included in this crate — does NOT
    /// require linking to libnetcdf.
    NetCdf {
        /// Output path.
        path: PathBuf,
    },
}

impl Scenario {
    /// Load and validate a scenario from a YAML file.
    pub fn load(path: impl AsRef<std::path::Path>) -> Result<Self, ScenarioError> {
        let text = std::fs::read_to_string(path)?;
        let s: Scenario = serde_yaml::from_str(&text)?;
        s.validate()?;
        Ok(s)
    }

    /// Validate without re-loading.
    pub fn validate(&self) -> Result<(), ScenarioError> {
        if self.experiment.ticks == 0 {
            return Err(ScenarioError::Invalid("ticks must be > 0".into()));
        }
        if self.experiment.dt_seconds <= 0.0 {
            return Err(ScenarioError::Invalid("dt_seconds must be > 0".into()));
        }
        if self.world.extent_chunks.min_cx > self.world.extent_chunks.max_cx
            || self.world.extent_chunks.min_cy > self.world.extent_chunks.max_cy
        {
            return Err(ScenarioError::Invalid("extent_chunks min > max".into()));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const EXAMPLE: &str = r#"
name: "Alpine valley centennial"
description: "Centennial drift of biomes in a 16x16 chunk valley."
version: "1"
metadata:
  authors: ["Genesis Test"]
  license: "Apache-2.0"
  keywords: ["climate", "biome", "centennial"]
world:
  seed: 42
  extent_chunks: { min_cx: 0, max_cx: 15, min_cy: 0, max_cy: 15 }
  climate:
    t_equator_c: 28.0
    t_pole_c: -25.0
experiment:
  ticks: 365
  dt_seconds: 86400.0
measurements:
  - kind: MeanTemperature
    every_ticks: 30
  - kind: BiomeHistogram
    every_ticks: 90
exports:
  - format: Csv
    path: ./out/alpine.csv
"#;

    #[test]
    fn parses_example() {
        let s: Scenario = serde_yaml::from_str(EXAMPLE).unwrap();
        s.validate().unwrap();
        assert_eq!(s.world.extent_chunks.count(), 256);
    }

    #[test]
    fn rejects_zero_ticks() {
        let mut s: Scenario = serde_yaml::from_str(EXAMPLE).unwrap();
        s.experiment.ticks = 0;
        assert!(s.validate().is_err());
    }
}
