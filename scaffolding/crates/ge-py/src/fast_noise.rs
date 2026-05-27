//! Fast deterministic noise for terrain — SplitMix64-based.
//!
//! Phase 3b : remplace l'appel coûteux BLAKE3+ChaCha20 (ge_core::prf_rng)
//! par un hash SplitMix64 direct, ~100× plus rapide par lookup.
//!
//! Phase 3c : salt dérivé via **BLAKE2b** (identique à Python
//! `hashlib.blake2b(digest_size=8)`) pour **bit-for-bit determinism**
//! entre les backends Rust et Python.
//!
//! Le pattern est identique au Python `world.py::_cell_values` :
//! 1. Un salt BLAKE2b(seed_16LE | "|" | layer_utf8) → u64 LE.
//! 2. Un mix coords×salt via SplitMix64 avalanche (par point, ~3 ns).

use std::f32::consts::PI;

/// Salt stable dérivé de (seed, layer) via BLAKE2b — 8 bytes = u64.
///
/// Identique au Python :
/// ```python
/// h = hashlib.blake2b(digest_size=8)
/// h.update(seed.to_bytes(16, "little", signed=False))
/// h.update(b"|")
/// h.update(layer.encode("utf-8"))
/// return int.from_bytes(h.digest(), "little", signed=False)
/// ```
///
/// Appelé une seule fois par couche FBM (pas par point).
#[inline]
pub fn layer_salt(seed: u128, layer: &str) -> u64 {
    let mut params = blake2b_simd::Params::new();
    params.hash_length(8);
    let mut state = params.to_state();
    state.update(&seed.to_le_bytes()); // 16 bytes, little-endian
    state.update(b"|");
    state.update(layer.as_bytes());
    let hash = state.finalize();
    let bytes = hash.as_bytes();
    u64::from_le_bytes([
        bytes[0], bytes[1], bytes[2], bytes[3],
        bytes[4], bytes[5], bytes[6], bytes[7],
    ])
}

/// SplitMix64 avalanche — identique au Python `_cell_values`.
///
/// Maps (gx, gy, salt) → f32 in [-1, 1].
///
/// Matches Python exactly:
/// ```python
/// a = (uint64(gx) * uint64(73856093)) ^ (uint64(gy) * uint64(19349663))
/// a ^= salt
/// a = (a ^ (a >> 33)) * 0xff51afd7ed558ccd
/// a = (a ^ (a >> 33)) * 0xc4ceb9fe1a85ec53
/// a ^= a >> 33
/// return (float64(a) / MAX_UINT64) * 2.0 - 1.0
/// ```
#[inline]
pub fn cell_value(gx: i64, gy: i64, salt: u64) -> f32 {
    let mut a = (gx as u64).wrapping_mul(73856093)
        ^ (gy as u64).wrapping_mul(19349663);
    a ^= salt;
    // SplitMix64 finalizer (Stafford variant 13)
    a = (a ^ (a >> 33)).wrapping_mul(0xff51afd7ed558ccd);
    a = (a ^ (a >> 33)).wrapping_mul(0xc4ceb9fe1a85ec53);
    a ^= a >> 33;
    // Map to [-1, 1] — matches Python's float64 division then cast to float32
    (a as f64 / u64::MAX as f64) as f32 * 2.0 - 1.0
}

/// Cosine interpolation (C1 continuous) — matches Python `_smooth_lerp`.
#[inline]
fn smooth_lerp(a: f32, b: f32, t: f32) -> f32 {
    let f = (1.0 - (t * PI).cos()) * 0.5;
    a + (b - a) * f
}

/// 2D value noise at (x, y) with pre-computed layer salt.
///
/// Matches Python `value_noise_2d` exactly (same grid, same interpolation).
#[inline]
pub fn value_noise_2d(x: f32, y: f32, salt: u64) -> f32 {
    let gx = x.floor() as i64;
    let gy = y.floor() as i64;
    let fx = x - gx as f32;
    let fy = y - gy as f32;

    let v00 = cell_value(gx,     gy,     salt);
    let v10 = cell_value(gx + 1, gy,     salt);
    let v01 = cell_value(gx,     gy + 1, salt);
    let v11 = cell_value(gx + 1, gy + 1, salt);

    let i1 = smooth_lerp(v00, v10, fx);
    let i2 = smooth_lerp(v01, v11, fx);
    smooth_lerp(i1, i2, fy)
}

/// FBM (fractional Brownian motion) with N octaves.
///
/// Salt is computed once from (seed, layer) — all octaves share it.
#[inline]
pub fn fbm_2d(
    seed: u128,
    layer: &str,
    x: f32,
    y: f32,
    octaves: u32,
    lacunarity: f32,
    gain: f32,
) -> f32 {
    let salt = layer_salt(seed, layer);
    fbm_2d_with_salt(x, y, octaves, lacunarity, gain, salt)
}

/// FBM with pre-computed layer salt — avoids re-hashing per call.
#[inline]
pub fn fbm_2d_with_salt(
    x: f32,
    y: f32,
    octaves: u32,
    lacunarity: f32,
    gain: f32,
    salt: u64,
) -> f32 {
    let mut amp = 1.0_f32;
    let mut freq = 1.0_f32;
    let mut sum = 0.0_f32;
    let mut norm = 0.0_f32;
    for _ in 0..octaves {
        sum += value_noise_2d(x * freq, y * freq, salt) * amp;
        norm += amp;
        amp *= gain;
        freq *= lacunarity;
    }
    sum / norm.max(1e-6)
}

#[cfg(test)]
mod tests {
    use super::*;

    // Test vectors from Python hashlib.blake2b(digest_size=8):
    // seed=0x2a layer='elev'   salt=0x2065ada467d908b5
    // seed=0x2a layer='temp'   salt=0xda6bfa1e6f752847
    // seed=0x2a layer='precip' salt=0xb6121c545423b9b1
    // seed=0xdead layer='elev' salt=0xa49f7ce4a7468fb5

    #[test]
    fn blake2b_salt_matches_python() {
        assert_eq!(layer_salt(0x2a, "elev"),   0x2065ada467d908b5);
        assert_eq!(layer_salt(0x2a, "temp"),   0xda6bfa1e6f752847);
        assert_eq!(layer_salt(0x2a, "precip"), 0xb6121c545423b9b1);
        assert_eq!(layer_salt(0xDEAD, "elev"), 0xa49f7ce4a7468fb5);
    }

    // Python cell_value test vectors (seed=42, layer="elev"):
    // gx=0 gy=0 → +0.064764169295077
    // gx=1 gy=0 → +0.683228792417397
    // gx=0 gy=1 → -0.050133474871146
    // gx=5 gy=7 → -0.730366020191259

    #[test]
    fn cell_value_matches_python() {
        let salt = layer_salt(0x2a, "elev");
        let eps = 1e-6;
        let v00 = cell_value(0, 0, salt);
        assert!((v00 as f64 - 0.064764169295077).abs() < eps,
                "v(0,0) = {v00}, expected ~0.0648");
        let v10 = cell_value(1, 0, salt);
        assert!((v10 as f64 - 0.683228792417397).abs() < eps,
                "v(1,0) = {v10}, expected ~0.6832");
        let v01 = cell_value(0, 1, salt);
        assert!((v01 as f64 - (-0.050133474871146)).abs() < eps,
                "v(0,1) = {v01}, expected ~-0.0501");
        let v57 = cell_value(5, 7, salt);
        assert!((v57 as f64 - (-0.730366020191259)).abs() < eps,
                "v(5,7) = {v57}, expected ~-0.7304");
    }

    #[test]
    fn deterministic() {
        let a = fbm_2d(0xC0FFEE, "elev", 12.3, 45.6, 4, 2.0, 0.5);
        let b = fbm_2d(0xC0FFEE, "elev", 12.3, 45.6, 4, 2.0, 0.5);
        assert_eq!(a, b);
    }

    #[test]
    fn bounded() {
        for i in 0..100 {
            let v = fbm_2d(0xABCD, "elev", i as f32 * 0.1, i as f32 * 0.13, 5, 2.0, 0.5);
            assert!(v >= -1.0 && v <= 1.0, "fbm out of bounds: {v}");
        }
    }

    #[test]
    fn different_layers_differ() {
        let a = fbm_2d(42, "elev", 1.0, 2.0, 3, 2.0, 0.5);
        let b = fbm_2d(42, "temp", 1.0, 2.0, 3, 2.0, 0.5);
        assert_ne!(a, b);
    }

    #[test]
    fn different_seeds_differ() {
        let a = fbm_2d(42, "elev", 1.0, 2.0, 3, 2.0, 0.5);
        let b = fbm_2d(99, "elev", 1.0, 2.0, 3, 2.0, 0.5);
        assert_ne!(a, b);
    }
}
