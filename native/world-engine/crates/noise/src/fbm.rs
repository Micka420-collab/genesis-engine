//! Fractal Brownian Motion — multi-octave simplex.

use crate::simplex::simplex2;
use genesis_core::Prf;

/// Parameters for FBM.
#[derive(Copy, Clone, Debug)]
pub struct FbmParams {
    /// Number of octaves.
    pub octaves: u8,
    /// Multiplier between octaves (>1; standard: 2.0).
    pub lacunarity: f32,
    /// Amplitude decay per octave in `(0, 1)`; standard: 0.5.
    pub gain: f32,
    /// Base frequency (cycles per world unit).
    pub frequency: f32,
}

impl Default for FbmParams {
    fn default() -> Self {
        Self {
            octaves: 5,
            lacunarity: 2.0,
            gain: 0.5,
            frequency: 1.0 / 256.0,
        }
    }
}

/// 2D FBM. Output normalised to ≈ `[-1, 1]`.
#[must_use]
pub fn fbm2(prf: Prf, layer: u32, x: f32, y: f32, p: FbmParams) -> f32 {
    let mut amp = 1.0;
    let mut freq = p.frequency;
    let mut sum = 0.0;
    let mut norm = 0.0;
    for o in 0..p.octaves as u32 {
        sum += amp * simplex2(prf, layer.wrapping_add(o), x * freq, y * freq);
        norm += amp;
        amp *= p.gain;
        freq *= p.lacunarity;
    }
    if norm > 0.0 {
        sum / norm
    } else {
        0.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fbm_deterministic() {
        let p = Prf::new(123);
        let params = FbmParams::default();
        let a = fbm2(p, 7, 100.0, 50.0, params);
        let b = fbm2(p, 7, 100.0, 50.0, params);
        assert_eq!(a, b);
    }

    #[test]
    fn fbm_in_range() {
        let p = Prf::new(1);
        let params = FbmParams::default();
        for i in 0..1000 {
            let v = fbm2(p, 0, i as f32, (i as f32).sin() * 50.0, params);
            assert!(v.abs() <= 1.5);
        }
    }
}
