//! Bruit cohérent (value noise déterministe basé sur PRF).
//!
//! NB : pour la production on remplacera par OpenSimplex2 vectorisé,
//! mais on garde ici une implémentation simple, déterministe, sans crate
//! externe non auditée, pour bootstrapper la Phase 1.

use ge_core::{prf_rng, WorldSeed};
use rand::Rng;

/// Hash déterministe d'une cellule (gx, gy) -> f32 dans [-1, 1].
fn cell_value(seed: WorldSeed, layer: &str, gx: i64, gy: i64) -> f32 {
    let mut rng = prf_rng(seed, &["world", "noise", layer], &[gx as u64, gy as u64]);
    rng.gen::<f32>() * 2.0 - 1.0
}

/// Interpolation cosinus (continue C1) — moins cher que cubic, suffisant pour terrain Phase 1.
#[inline]
fn smooth_lerp(a: f32, b: f32, t: f32) -> f32 {
    let f = (1.0 - (t * std::f32::consts::PI).cos()) * 0.5;
    a + (b - a) * f
}

/// Value noise 2D, échelle = 1.0 cellule par unité (mettre `frequency` pour zoomer).
pub fn value_noise_2d(seed: WorldSeed, layer: &str, x: f32, y: f32) -> f32 {
    let gx = x.floor() as i64;
    let gy = y.floor() as i64;
    let fx = x - gx as f32;
    let fy = y - gy as f32;

    let v00 = cell_value(seed, layer, gx, gy);
    let v10 = cell_value(seed, layer, gx + 1, gy);
    let v01 = cell_value(seed, layer, gx, gy + 1);
    let v11 = cell_value(seed, layer, gx + 1, gy + 1);

    let i1 = smooth_lerp(v00, v10, fx);
    let i2 = smooth_lerp(v01, v11, fx);
    smooth_lerp(i1, i2, fy)
}

/// Bruit fractal (somme d'octaves) — Brownian motion fractionnaire.
pub fn fbm_2d(
    seed: WorldSeed,
    layer: &str,
    x: f32,
    y: f32,
    octaves: u32,
    lacunarity: f32,
    gain: f32,
) -> f32 {
    let mut amp = 1.0;
    let mut freq = 1.0;
    let mut sum = 0.0;
    let mut norm = 0.0;
    for _ in 0..octaves {
        sum += value_noise_2d(seed, layer, x * freq, y * freq) * amp;
        norm += amp;
        amp *= gain;
        freq *= lacunarity;
    }
    sum / norm.max(1e-6)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deterministic() {
        let s = 0xC0FFEE_u128;
        let a = fbm_2d(s, "elev", 12.3, 45.6, 4, 2.0, 0.5);
        let b = fbm_2d(s, "elev", 12.3, 45.6, 4, 2.0, 0.5);
        assert_eq!(a, b);
    }

    #[test]
    fn bounded() {
        let s = 0xABCD_u128;
        for i in 0..100 {
            let v = fbm_2d(s, "elev", i as f32 * 0.1, i as f32 * 0.13, 5, 2.0, 0.5);
            assert!(v >= -1.0 && v <= 1.0, "fbm out of bounds: {v}");
        }
    }
}
