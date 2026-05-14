//! ge-core — types fondamentaux et briques de déterminisme.
//!
//! Tout RNG et tout hash dans Genesis Engine doit transiter par ce crate
//! pour garantir la reproductibilité bit-à-bit.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod tick;
pub mod prf;
pub mod ids;
pub mod hash;

pub use tick::*;
pub use prf::*;
pub use ids::*;
pub use hash::*;
