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

impl<T: Serialize> ContentAddressable for SerdeWrapper<T> {
    fn hash_into(&self, hasher: &mut blake3::Hasher) {
        let bytes = bincode::serialize(&self.0).expect("serde encode failed");
        hasher.update(&(bytes.len() as u64).to_le_bytes());
        hasher.update(&bytes);
    }
}

/// Adapter — wrap any `Serialize` type to satisfy `ContentAddressable`.
pub struct SerdeWrapper<'a, T>(pub &'a T);

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
