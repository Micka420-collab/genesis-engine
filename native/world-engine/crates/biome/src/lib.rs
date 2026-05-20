//! genesis-biome — Whittaker classifier + extensible registry.
//!
//! Two ways to use it:
//!  - `Biome::classify(temp_c, humidity, elevation, sea_level)` for the
//!    built-in 16-biome Whittaker table (zero allocations).
//!  - `BiomeRegistry` for plugging in your own biome rules without modifying
//!    this crate.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod koeppen;
pub mod registry;
pub mod whittaker;

pub use koeppen::{harness_pass_rate, KoeppenClass, ReferenceClimate, REFERENCE_CLIMATES};
pub use registry::{BiomeId, BiomeRule, BiomeRegistry, EnvSample};
pub use whittaker::Biome;
