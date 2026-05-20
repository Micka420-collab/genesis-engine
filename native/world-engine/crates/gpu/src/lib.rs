//! genesis-gpu — GPU compute passes for Genesis World Engine.
//!
//! Gated behind the `gpu` feature so CPU-only builds don't pull in wgpu.
//!
//! When the feature is off, the crate exposes the same API but every entry
//! point returns [`GpuError::Disabled`]. Callers branch on this and rely
//! on the CPU equivalents.

#![cfg_attr(not(feature = "gpu"), allow(dead_code, unused_imports))]
#![warn(missing_docs)]

use thiserror::Error;

/// GPU subsystem errors.
#[derive(Error, Debug)]
pub enum GpuError {
    /// GPU support not compiled in.
    #[error("genesis-gpu was built without the 'gpu' feature")]
    Disabled,
    /// No adapter found.
    #[error("no GPU adapter available")]
    NoAdapter,
    /// Device request failed.
    #[error("device: {0}")]
    Device(String),
}

#[cfg(feature = "gpu")]
pub mod erosion;

#[cfg(feature = "gpu")]
pub use erosion::HydraulicErosionGpu;

#[cfg(not(feature = "gpu"))]
/// Stub re-export when the feature is off.
pub struct HydraulicErosionGpu;

#[cfg(not(feature = "gpu"))]
impl HydraulicErosionGpu {
    /// Always fails when the feature is off.
    pub fn try_new() -> Result<Self, GpuError> {
        Err(GpuError::Disabled)
    }
}
