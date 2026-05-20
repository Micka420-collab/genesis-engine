//! genesis-laws — real-world physical laws on top of `genesis-physics`.
//!
//! Every function takes strong SI units, applies an equation from real
//! physics with named constants and a documented source, and returns
//! strong SI units. The goal: an experimenter can read the source and
//! immediately compare to a textbook equation.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod atmosphere;
pub mod ecology;
pub mod gravity;
pub mod hydrology;
pub mod thermo;
