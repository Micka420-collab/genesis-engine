//! Hierarchical world seed.
//!
//! `WorldSeed` is the root 128-bit value. `SeedTree` derives sub-seeds by
//! layer name, ensuring two systems that consume `tree.layer("terrain.relief")`
//! get the same value across runs.

use crate::prf::Prf;

/// 128-bit world seed.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct WorldSeed(pub u128);

impl WorldSeed {
    /// Build from a u64 (high bits zero-extended).
    #[inline]
    #[must_use]
    pub const fn from_u64(s: u64) -> Self {
        Self(s as u128)
    }

    /// Build from a u128.
    #[inline]
    #[must_use]
    pub const fn from_u128(s: u128) -> Self {
        Self(s)
    }
}

/// Cheap deterministic seed tree. Building one is free; cloning is free.
#[derive(Copy, Clone, Debug)]
pub struct SeedTree {
    root: WorldSeed,
}

impl SeedTree {
    /// New tree rooted at `seed`.
    #[inline]
    #[must_use]
    pub const fn new(seed: WorldSeed) -> Self {
        Self { root: seed }
    }

    /// Derive a sub-seed by layer name. Same name ⇒ same sub-seed, always.
    #[must_use]
    pub fn layer(self, name: &str) -> WorldSeed {
        // Fold the root seed and the layer name through SipHash twice to mix
        // the high and low halves independently.
        let p = Prf::new(self.root.0);
        let lo = p.hash_named(name, 0, 0, 0, 0);
        let hi = p.hash_named(name, 0, 0, 0, 1);
        WorldSeed((hi as u128) << 64 | (lo as u128))
    }

    /// PRF rooted at the layer-derived sub-seed.
    #[inline]
    #[must_use]
    pub fn prf(self, layer: &str) -> Prf {
        Prf::new(self.layer(layer).0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn layer_is_stable() {
        let t = SeedTree::new(WorldSeed::from_u64(42));
        let a = t.layer("terrain.tectonics");
        let b = t.layer("terrain.tectonics");
        assert_eq!(a, b);
    }

    #[test]
    fn distinct_layers_differ() {
        let t = SeedTree::new(WorldSeed::from_u64(42));
        let a = t.layer("terrain.relief");
        let b = t.layer("terrain.tectonics");
        assert_ne!(a, b);
    }

    #[test]
    fn distinct_roots_differ() {
        let t1 = SeedTree::new(WorldSeed::from_u64(1));
        let t2 = SeedTree::new(WorldSeed::from_u64(2));
        assert_ne!(t1.layer("x"), t2.layer("x"));
    }
}
