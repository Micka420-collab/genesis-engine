//! genesis-terrain — heightmap, tectonics, erosion.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod erosion;
pub mod heightmap;
pub mod tectonics;

pub use erosion::{hydraulic_erode, thermal_erode};
pub use heightmap::{generate, Heightmap, TerrainParams};
pub use tectonics::{PlateField, PlateKind};
