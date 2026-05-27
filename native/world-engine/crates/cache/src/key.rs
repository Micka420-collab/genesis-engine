//! Cache keys — BLAKE3 32-byte digests built from typed components.
//!
//! Keys are *composable*: a downstream pass takes upstream key bytes,
//! appends its own params hash, and rolls it into a fresh BLAKE3. Same
//! lineage ⇒ same key ⇒ cache hit.

use std::fmt;

/// A 32-byte BLAKE3 hash that identifies a cache entry.
#[derive(Copy, Clone, PartialEq, Eq, Hash)]
pub struct CacheKey(pub [u8; 32]);

impl fmt::Debug for CacheKey {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "CacheKey({})", hex::encode(&self.0[..6]))
    }
}

impl CacheKey {
    /// Pretty hex (full).
    #[must_use]
    pub fn to_hex(&self) -> String {
        hex::encode(self.0)
    }

    /// First two hex chars — used by the on-disk sharding scheme.
    #[must_use]
    pub fn shard_prefix(&self) -> String {
        hex::encode(&self.0[..1])
    }
}

/// Builder for cache keys. Combine arbitrary `&[u8]` chunks deterministically.
pub struct KeyBuilder {
    hasher: blake3::Hasher,
}

impl KeyBuilder {
    /// New empty builder.
    #[must_use]
    pub fn new() -> Self {
        Self {
            hasher: blake3::Hasher::new(),
        }
    }

    /// Mix bytes (with a domain tag to avoid prefix collisions).
    #[must_use]
    pub fn mix(mut self, tag: &str, bytes: &[u8]) -> Self {
        self.hasher.update(tag.as_bytes());
        self.hasher.update(&(bytes.len() as u64).to_le_bytes());
        self.hasher.update(bytes);
        self
    }

    /// Mix a u64.
    #[must_use]
    pub fn mix_u64(self, tag: &str, v: u64) -> Self {
        self.mix(tag, &v.to_le_bytes())
    }

    /// Mix an i32 (commonly chunk coords).
    #[must_use]
    pub fn mix_i32(self, tag: &str, v: i32) -> Self {
        self.mix(tag, &v.to_le_bytes())
    }

    /// Finalise.
    #[must_use]
    pub fn build(self) -> CacheKey {
        CacheKey(*self.hasher.finalize().as_bytes())
    }
}

impl Default for KeyBuilder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stable_keys() {
        let k1 = KeyBuilder::new()
            .mix_u64("seed", 42)
            .mix_i32("cx", 3)
            .mix_i32("cy", -7)
            .build();
        let k2 = KeyBuilder::new()
            .mix_u64("seed", 42)
            .mix_i32("cx", 3)
            .mix_i32("cy", -7)
            .build();
        assert_eq!(k1, k2);
    }

    #[test]
    fn order_matters() {
        let k1 = KeyBuilder::new()
            .mix_i32("cx", 3)
            .mix_i32("cy", -7)
            .build();
        let k2 = KeyBuilder::new()
            .mix_i32("cy", -7)
            .mix_i32("cx", 3)
            .build();
        assert_ne!(k1, k2);
    }

    #[test]
    fn tag_separates_collisions() {
        let k1 = KeyBuilder::new().mix("a", &[1, 2]).mix("b", &[3]).build();
        let k2 = KeyBuilder::new().mix("ab", &[1, 2, 3]).build();
        assert_ne!(k1, k2);
    }
}
