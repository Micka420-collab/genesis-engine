//! Pseudo-Random Function — deterministic, indexed, no internal state.
//!
//! Use `Prf::new(seed)` once, then call `prf.value(layer, x, y, z, salt)` from
//! anywhere. Same inputs ⇒ same output, regardless of thread or order.

use siphasher::sip::SipHasher13;
use std::hash::Hasher;

/// Domain-keyed deterministic hash function.
#[derive(Copy, Clone, Debug)]
pub struct Prf {
    seed_lo: u64,
    seed_hi: u64,
}

impl Prf {
    /// Build a PRF from a 128-bit world seed.
    #[inline]
    #[must_use]
    pub const fn new(seed: u128) -> Self {
        Self {
            seed_lo: seed as u64,
            seed_hi: (seed >> 64) as u64,
        }
    }

    /// Raw 64-bit hash.
    #[inline]
    #[must_use]
    pub fn hash(self, layer: u32, x: i32, y: i32, z: i32, salt: u32) -> u64 {
        let mut h = SipHasher13::new_with_keys(self.seed_lo, self.seed_hi);
        h.write_u32(layer);
        h.write_i32(x);
        h.write_i32(y);
        h.write_i32(z);
        h.write_u32(salt);
        h.finish()
    }

    /// Hash a (named) layer + coords + salt. The layer name is hashed once and
    /// folded in; passing the same str twice is cheap.
    #[inline]
    #[must_use]
    pub fn hash_named(self, layer: &str, x: i32, y: i32, z: i32, salt: u32) -> u64 {
        // Fold layer name into a stable 32-bit tag. SipHasher is overkill here
        // but keeps everything in a single deterministic family.
        let mut h = SipHasher13::new_with_keys(0, 0);
        h.write(layer.as_bytes());
        let layer_tag = h.finish() as u32;
        self.hash(layer_tag, x, y, z, salt)
    }

    /// Uniform `f32` in `[0, 1)`.
    #[inline]
    #[must_use]
    pub fn unit_f32(self, layer: u32, x: i32, y: i32, z: i32, salt: u32) -> f32 {
        let bits = self.hash(layer, x, y, z, salt);
        // 24 bits of mantissa precision is enough; divide by 2^24
        ((bits >> 40) as f32) * (1.0 / (1u64 << 24) as f32)
    }

    /// Signed uniform `f32` in `[-1, 1)`.
    #[inline]
    #[must_use]
    pub fn signed_f32(self, layer: u32, x: i32, y: i32, z: i32, salt: u32) -> f32 {
        self.unit_f32(layer, x, y, z, salt) * 2.0 - 1.0
    }

    /// Uniform integer in `[0, n)`.
    #[inline]
    #[must_use]
    pub fn range(self, layer: u32, x: i32, y: i32, z: i32, salt: u32, n: u32) -> u32 {
        // multiply-shift (Lemire) — unbiased for hash-quality input.
        let h = self.hash(layer, x, y, z, salt);
        let prod = (h as u128) * (n as u128);
        (prod >> 64) as u32
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn determinism() {
        let p = Prf::new(42);
        for _ in 0..100 {
            assert_eq!(p.hash(0, 1, 2, 3, 4), p.hash(0, 1, 2, 3, 4));
            assert_eq!(p.unit_f32(0, 1, 2, 3, 4), p.unit_f32(0, 1, 2, 3, 4));
        }
    }

    #[test]
    fn different_inputs_differ() {
        let p = Prf::new(42);
        assert_ne!(p.hash(0, 1, 2, 3, 4), p.hash(1, 1, 2, 3, 4));
        assert_ne!(p.hash(0, 1, 2, 3, 4), p.hash(0, 2, 2, 3, 4));
    }

    #[test]
    fn unit_in_range() {
        let p = Prf::new(0xDEAD_BEEF);
        for i in 0..10_000 {
            let v = p.unit_f32(0, i, 0, 0, 0);
            assert!((0.0..1.0).contains(&v));
        }
    }
}
