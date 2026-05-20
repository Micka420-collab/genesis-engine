//! genesis-noise — coherent noise primitives.
//!
//! Pure functions: every value is `Prf::value(layer, x, y, z, salt)` keyed by
//! `(seed, layer, coord)`, so identical inputs ⇒ identical outputs across
//! threads, machines, and runs.
//!
//! For top-tier performance on production builds we would link against the
//! Rust port of FastNoise2 (AVX2/NEON). Here we ship a self-contained
//! OpenSimplex2-style implementation with no unsafe code so the workspace
//! compiles offline without proprietary deps. Bench data in the architecture
//! doc compares both.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod fbm;
pub mod ridged;
pub mod simplex;
pub mod warp;

pub use fbm::{fbm2, FbmParams};
pub use ridged::{ridged2, RidgedParams};
pub use simplex::{simplex2, simplex3};
pub use warp::{domain_warp2, WarpParams};
