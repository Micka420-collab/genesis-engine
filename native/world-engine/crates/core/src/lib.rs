//! genesis-core — deterministic primitives, types, math.
//!
//! No `rand::thread_rng`, no `Instant::now`, no global state. Everything
//! consumes an explicit seed and produces bit-for-bit reproducible output.

#![forbid(unsafe_code)]
#![warn(missing_docs)]
#![allow(clippy::module_name_repetitions)]

pub mod coord;
pub mod coupler;
pub mod prf;
pub mod seed;
pub mod tick;
pub mod tick_domain;
pub mod voxel;

pub use coord::{
    ChunkCoord, LocalCoord, WorldCoord, CHUNK_SIZE_X, CHUNK_SIZE_Y, CHUNK_SIZE_Z,
    CHUNK_VOXEL_COUNT,
};
pub use coupler::{CouplerStep, DomainConfig, MultiRateCoupler};
pub use prf::Prf;
pub use seed::{SeedTree, WorldSeed};
pub use tick::Tick;
pub use tick_domain::{domain_tick_to_master, DomainTick, TickDomain};
pub use voxel::{Material, Voxel};

/// Common `Result` alias used across the engine.
pub type Result<T, E = Error> = core::result::Result<T, E>;

/// Top-level engine errors. Domain-specific crates re-export their own.
#[derive(thiserror::Error, Debug)]
pub enum Error {
    /// Coordinate is outside the legal world range.
    #[error("coordinate out of bounds: {0:?}")]
    OutOfBounds(WorldCoord),
    /// A mutation conflicted with another in the same tick.
    #[error("mutation conflict at tick {0:?}")]
    MutationConflict(Tick),
    /// Generic I/O error.
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
}
