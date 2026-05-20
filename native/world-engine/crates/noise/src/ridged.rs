//! Ridged multi-fractal noise — used for mountain ranges and canyons.

use crate::simplex::simplex2;
use genesis_core::Prf;

/// Parameters for ridged multi-fractal.
#[derive(Copy, Clone, Debug)]
pub struct RidgedParams {
    /// Number of octaves.
    pub octaves: u8,
    /// Frequency multiplier.
    pub lacunarity: f32,
    /// Amplitude decay.
    pub gain: f32,
    /// Base frequency.
    pub frequency: f32,
    /// Ridge sharpness — higher = sharper ridges (1.0 default).
    pub sharpness: f32,
}

impl Default for RidgedParams {
    fn default() -> Self {
        Self {
            octaves: 5,
            lacunarity: 2.0,
            gain: 0.5,
            frequency: 1.0 / 512.0,
            sharpness: 1.0,
        }
    }
}

/// 2D ridged. Output in `[0, 1]`.
#[must_use]
pub fn ridged2(prf: Prf, layer: u32, x: f32, y: f32, p: RidgedParams) -> f32 {
    let mut amp = 1.0;
    let mut freq = p.frequency;
    let mut sum = 0.0;
    let mut norm = 0.0;
    for o in 0..p.octaves as u32 {
        let n = simplex2(prf, layer.wrapping_add(o), x * freq, y * freq);
        // ridge transform
        let r = (1.0 - n.abs()).powf(p.sharpness * 2.0);
        sum += amp * r;
        norm += amp;
        amp *= p.gain;
        freq *= p.lacunarity;
    }
    if norm > 0.0 {
        (sum / norm).clamp(0.0, 1.0)
    } else {
        0.0
    }
}
