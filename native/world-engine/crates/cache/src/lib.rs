//! genesis-cache — content-addressed cache, two-tier (L1 mem + L2 disk).
//!
//! The cache key is a [`CacheKey`] (32 bytes, BLAKE3). Two callers that
//! independently arrive at the same `CacheKey` share the same value, even
//! across different worlds, different processes, or different machines
//! (assuming a shared disk).
//!
//! ## Layered behaviour
//!
//! - L1 `Arc<DashMap<CacheKey, Arc<dyn Any>>>` — type-erased in-memory
//!   cache. Eviction: bounded by `max_entries`, simple FIFO drop. We don't
//!   pretend to be a perfect LRU; for procgen workloads the pareto
//!   distribution of accesses makes this OK.
//!
//! - L2 directory of files at `$root/aa/bbbbbbbb…cas`. Files are
//!   bincode-serialized + zstd-compressed values. Reads go through `mmap`
//!   for free zero-copy slices, decompressed on demand.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod key;
pub mod l1;
pub mod l2;

pub use key::{CacheKey, KeyBuilder};
pub use l1::L1Cache;
pub use l2::{L2Cache, L2Config};

use serde::{de::DeserializeOwned, Serialize};
use std::sync::Arc;
use thiserror::Error;

/// Cache errors.
#[derive(Error, Debug)]
pub enum CacheError {
    /// Disk I/O failure.
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    /// Encoding failure.
    #[error("bincode: {0}")]
    Bincode(#[from] bincode::Error),
}

/// A two-tier cache combining L1 (memory) and L2 (disk).
#[derive(Clone)]
pub struct Cache {
    l1: L1Cache,
    l2: Option<Arc<L2Cache>>,
}

impl Cache {
    /// Memory-only cache.
    #[must_use]
    pub fn memory(max_l1_entries: usize) -> Self {
        Self {
            l1: L1Cache::new(max_l1_entries),
            l2: None,
        }
    }

    /// Two-tier cache (memory + disk).
    pub fn with_disk(
        max_l1_entries: usize,
        l2_config: L2Config,
    ) -> Result<Self, CacheError> {
        Ok(Self {
            l1: L1Cache::new(max_l1_entries),
            l2: Some(Arc::new(L2Cache::open(l2_config)?)),
        })
    }

    /// Fetch a typed value if present in either tier.
    ///
    /// `T` must be the same concrete type for a given key — we type-erase
    /// in L1 but verify at downcast.
    pub fn get<T: Clone + Send + Sync + 'static + DeserializeOwned>(
        &self,
        key: CacheKey,
    ) -> Option<T> {
        if let Some(v) = self.l1.get::<T>(key) {
            tracing::trace!(?key, "L1 hit");
            return Some(v);
        }
        if let Some(l2) = &self.l2 {
            if let Some(value) = l2.load::<T>(key).ok().flatten() {
                tracing::trace!(?key, "L2 hit");
                self.l1.insert(key, value.clone());
                return Some(value);
            }
        }
        None
    }

    /// Insert a value into both tiers (best-effort for L2).
    pub fn put<T: Clone + Send + Sync + 'static + Serialize>(
        &self,
        key: CacheKey,
        value: T,
    ) -> Result<(), CacheError> {
        self.l1.insert(key, value.clone());
        if let Some(l2) = &self.l2 {
            l2.store(key, &value)?;
        }
        Ok(())
    }

    /// Compute or fetch — the typical caller entry point. The closure is
    /// only invoked on a full miss.
    pub fn get_or_compute<T, F>(&self, key: CacheKey, compute: F) -> Result<T, CacheError>
    where
        T: Clone + Send + Sync + 'static + Serialize + DeserializeOwned,
        F: FnOnce() -> T,
    {
        if let Some(v) = self.get::<T>(key) {
            return Ok(v);
        }
        let v = compute();
        self.put(key, v.clone())?;
        Ok(v)
    }

    /// Approximate L1 size.
    #[must_use]
    pub fn l1_size(&self) -> usize {
        self.l1.len()
    }

    /// Expose L1 for the worldgraph scheduler — it manages its own
    /// type-erased intermediate caching.
    #[must_use]
    pub fn l1(&self) -> &L1Cache {
        &self.l1
    }

    /// Expose L2 (if any) for typed disk round-trips.
    #[must_use]
    pub fn l2(&self) -> Option<&L2Cache> {
        self.l2.as_deref()
    }
}
