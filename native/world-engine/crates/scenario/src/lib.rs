//! genesis-scenario — declarative scientific experiments.
//!
//! A `Scenario` is a YAML document describing:
//!   - the world (seed, terrain, climate, biome rules)
//!   - the experiment (duration, time-step, measurements)
//!   - the exports (NetCDF / CSV / JSON)
//!   - the FAIR metadata (DOI, license, authors)
//!
//! Loading a scenario gives you a runnable plan that the `genesis-studio`
//! binary executes.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod manifest;
pub mod schema;
pub mod runner;

pub use manifest::{FairManifest, RunSummary};
pub use schema::{Scenario, ScenarioError, WorldSpec, ExperimentSpec, Measurement, ExportSpec};
pub use runner::{run_scenario, ProgressEvent};
