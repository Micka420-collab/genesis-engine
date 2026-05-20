//! Domain warping — distort the input coordinate with noise before sampling.
//!
//! This is the trick that turns "looks like noise" into "looks like
//! continents". Two passes of warp at large scale produce realistic shores,
//! peninsulas, and archipelagos.

use crate::fbm::{fbm2, FbmParams};
use genesis_core::Prf;

/// Domain warp parameters.
#[derive(Copy, Clone, Debug)]
pub struct WarpParams {
    /// Inner FBM params used to compute the warp offset.
    pub fbm: FbmParams,
    /// Distortion magnitude (in same units as the input coordinate).
    pub amplitude: f32,
}

impl Default for WarpParams {
    fn default() -> Self {
        Self {
            fbm: FbmParams {
                octaves: 3,
                lacunarity: 2.0,
                gain: 0.5,
                frequency: 1.0 / 800.0,
            },
            amplitude: 120.0,
        }
    }
}

/// Apply domain warp to `(x, y)`. Returns the warped coordinate.
#[inline]
#[must_use]
pub fn domain_warp2(prf: Prf, layer: u32, x: f32, y: f32, p: WarpParams) -> (f32, f32) {
    let dx = fbm2(prf, layer, x, y, p.fbm) * p.amplitude;
    let dy = fbm2(prf, layer.wrapping_add(0xA5A5), x + 100.0, y - 100.0, p.fbm) * p.amplitude;
    (x + dx, y + dy)
}
