//! [`Pass`] — the unit of work in a [`super::Pipeline`].
//!
//! Two principles:
//!
//! 1. **Pure** : `run` must be a deterministic function of `(input, ctx)`.
//!    No clocks, no globals, no `rand::thread_rng`. All randomness flows
//!    from `ctx.seed_tree`.
//! 2. **Content-addressable** : every input and output must implement
//!    [`ContentAddressable`] so the scheduler can build a stable BLAKE3
//!    key for the cache.

use crate::ctx::PassCtx;
use genesis_cache::{CacheKey, KeyBuilder};
use serde::Serialize;
use std::fmt;

/// Stable identifier for a pass — `"terrain.heightmap.v1"`-style.
///
/// **Bump the version suffix when the pass's algorithm changes** so cached
/// outputs from earlier versions are not reused.
#[derive(Copy, Clone, PartialEq, Eq, Hash)]
pub struct PassId(pub &'static str);

impl fmt::Debug for PassId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "PassId({:?})", self.0)
    }
}

/// Type whose bytes can be hashed deterministically.
///
/// Most engine types satisfy this via `serde::Serialize`. For very large
/// outputs you can implement it manually to stream-hash without
/// allocating a buffer.
///
/// **Floats:** when hashing `f32` or `f64` fields, use [`hash_f32`] / [`hash_f64`]
/// instead of `.to_le_bytes()`. They canonicalize NaN payloads so two
/// platforms producing semantically-equivalent-but-bitwise-different NaNs
/// hash identically. Raw `f32::to_le_bytes` on a NaN can yield any of
/// 2²³ bit-patterns and silently breaks the "same seed = same hash"
/// invariant.
pub trait ContentAddressable {
    /// Append the type's canonical bytes into the hasher.
    fn hash_into(&self, hasher: &mut blake3::Hasher);

    /// Convenience: full 32-byte digest.
    fn content_key(&self) -> CacheKey {
        let mut h = blake3::Hasher::new();
        self.hash_into(&mut h);
        CacheKey(*h.finalize().as_bytes())
    }
}

/// Quiet-NaN bit pattern for canonical f32 hashing (sign 0, exp all-1,
/// mantissa MSB set, rest zero — the IEEE 754 quiet NaN canonical form).
const F32_QUIET_NAN: u32 = 0x7FC0_0000;
/// Quiet-NaN bit pattern for canonical f64 hashing.
const F64_QUIET_NAN: u64 = 0x7FF8_0000_0000_0000;

/// Hash an `f32` into `hasher` with NaN canonicalization.
///
/// Use this in every `ContentAddressable::hash_into` impl that touches a
/// float field, instead of `hasher.update(&v.to_le_bytes())`. Two NaN
/// bit-patterns produced by different libm/CRT combinations (Linux glibc,
/// Windows MSVC, macOS) will hash to the same value.
///
/// Signed zero (`+0.0` vs `-0.0`) is **not** collapsed — they remain
/// distinguishable, since a sign flip is a real semantic change.
pub fn hash_f32(hasher: &mut blake3::Hasher, v: f32) {
    let bits = if v.is_nan() { F32_QUIET_NAN } else { v.to_bits() };
    hasher.update(&bits.to_le_bytes());
}

/// Same as [`hash_f32`] for `f64`.
pub fn hash_f64(hasher: &mut blake3::Hasher, v: f64) {
    let bits = if v.is_nan() { F64_QUIET_NAN } else { v.to_bits() };
    hasher.update(&bits.to_le_bytes());
}

/// Adapter — wrap any `Serialize` type to satisfy `ContentAddressable`.
pub struct SerdeWrapper<'a, T>(pub &'a T);

impl<'a, T: Serialize> ContentAddressable for SerdeWrapper<'a, T> {
    fn hash_into(&self, hasher: &mut blake3::Hasher) {
        let bytes = bincode::serialize(&self.0).expect("serde encode failed");
        hasher.update(&(bytes.len() as u64).to_le_bytes());
        hasher.update(&bytes);
    }
}

/// Implementation for common scalar types so they can be used as
/// `Pass::Input = ()` "no-input" markers.
impl ContentAddressable for () {
    fn hash_into(&self, hasher: &mut blake3::Hasher) {
        hasher.update(b"unit");
    }
}

impl ContentAddressable for [u8] {
    fn hash_into(&self, hasher: &mut blake3::Hasher) {
        hasher.update(&(self.len() as u64).to_le_bytes());
        hasher.update(self);
    }
}

impl ContentAddressable for Vec<u8> {
    fn hash_into(&self, hasher: &mut blake3::Hasher) {
        ContentAddressable::hash_into(self.as_slice(), hasher)
    }
}

impl<A: ContentAddressable, B: ContentAddressable> ContentAddressable for (A, B) {
    fn hash_into(&self, hasher: &mut blake3::Hasher) {
        hasher.update(b"tuple2");
        self.0.hash_into(hasher);
        self.1.hash_into(hasher);
    }
}

/// A single generation step.
///
/// Outputs must be `Serialize + DeserializeOwned` so the scheduler can store
/// intermediate values to the on-disk L2 cache and round-trip them across
/// processes.
pub trait Pass: Send + Sync + 'static {
    /// Input type — already produced by upstream passes.
    type Input: ContentAddressable + Send + Sync + 'static;
    /// Output type — fed to downstream passes (and possibly the caller).
    type Output: ContentAddressable
        + Clone
        + Send
        + Sync
        + 'static
        + serde::Serialize
        + serde::de::DeserializeOwned;

    /// Stable identifier (include a version suffix).
    fn id(&self) -> PassId;

    /// 64-bit hash of the pass parameters. Cheap to compute (just fold the
    /// few floats/ints that change behaviour). Same params ⇒ same hash.
    fn params_hash(&self) -> u64;

    /// Run the pass. Must be pure.
    fn run(&self, ctx: &PassCtx, input: &Self::Input) -> Self::Output;

    /// Compose a cache key from the pass, its params, input, and coord.
    fn cache_key(&self, ctx: &PassCtx, input: &Self::Input) -> CacheKey {
        let input_key = input.content_key();
        KeyBuilder::new()
            .mix("pass.id", self.id().0.as_bytes())
            .mix_u64("pass.params", self.params_hash())
            .mix("pass.input", &input_key.0)
            .mix_u64("ctx.seed", ctx.seed.0 as u64)
            .mix_u64("ctx.seed.hi", (ctx.seed.0 >> 64) as u64)
            .mix_i32("ctx.cx", ctx.coord.cx)
            .mix_i32("ctx.cy", ctx.coord.cy)
            .build()
    }
}

#[cfg(test)]
mod hash_helper_tests {
    use super::{hash_f32, hash_f64};

    fn digest_f32(v: f32) -> [u8; 32] {
        let mut h = blake3::Hasher::new();
        hash_f32(&mut h, v);
        *h.finalize().as_bytes()
    }

    fn digest_f64(v: f64) -> [u8; 32] {
        let mut h = blake3::Hasher::new();
        hash_f64(&mut h, v);
        *h.finalize().as_bytes()
    }

    #[test]
    fn all_f32_nan_payloads_hash_identically() {
        // Construct three different NaN bit-patterns. A naive
        // `f32::to_le_bytes` hash would produce three different digests.
        let nan_a = f32::from_bits(0x7FC0_0001);
        let nan_b = f32::from_bits(0x7FFF_FFFF);
        let nan_c = f32::from_bits(0xFFC0_0000); // negative-sign NaN
        assert!(nan_a.is_nan() && nan_b.is_nan() && nan_c.is_nan());
        let h_a = digest_f32(nan_a);
        let h_b = digest_f32(nan_b);
        let h_c = digest_f32(nan_c);
        assert_eq!(h_a, h_b);
        assert_eq!(h_a, h_c);
    }

    #[test]
    fn all_f64_nan_payloads_hash_identically() {
        let nan_a = f64::from_bits(0x7FF8_0000_0000_0001);
        let nan_b = f64::from_bits(0x7FFF_FFFF_FFFF_FFFF);
        let nan_c = f64::from_bits(0xFFF8_0000_0000_0000);
        assert!(nan_a.is_nan() && nan_b.is_nan() && nan_c.is_nan());
        assert_eq!(digest_f64(nan_a), digest_f64(nan_b));
        assert_eq!(digest_f64(nan_a), digest_f64(nan_c));
    }

    #[test]
    fn positive_and_negative_zero_remain_distinct() {
        // A sign flip is a real semantic change; we don't collapse it.
        assert_ne!(digest_f32(0.0f32), digest_f32(-0.0f32));
        assert_ne!(digest_f64(0.0f64), digest_f64(-0.0f64));
    }

    #[test]
    fn finite_values_round_trip_exactly() {
        // Sanity: non-NaN values still hash to distinct, stable digests.
        assert_ne!(digest_f32(1.0), digest_f32(2.0));
        assert_eq!(digest_f32(1.5_f32), digest_f32(1.5_f32));
    }
}
