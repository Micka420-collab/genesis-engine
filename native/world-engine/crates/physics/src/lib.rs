//! genesis-physics — strong SI units and physical constants.
//!
//! Unlike `uom` (which is excellent but adds compile-time generics that slow
//! the build), this crate uses **newtype wrappers** over `f64`. Conversions
//! are explicit. Arithmetic is unit-checked at the type level — multiplying
//! a `Meter` by a `Meter` gives a `SquareMeter`, dividing by `Second` gives
//! a `MeterPerSecond`, etc. Mistakes that would otherwise produce silent
//! numerical garbage become compile errors.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod constants;
pub mod units;

pub use constants::*;
pub use units::*;
