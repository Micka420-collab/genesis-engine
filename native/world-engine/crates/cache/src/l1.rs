//! L1 (in-memory) cache. Type-erased `dyn Any` values, downcast on `get`.

use crate::key::CacheKey;
use dashmap::DashMap;
use std::any::Any;
use std::sync::Arc;

/// Thread-safe type-erased in-memory cache.
#[derive(Clone)]
pub struct L1Cache {
    inner: Arc<DashMap<CacheKey, Arc<dyn Any + Send + Sync>>>,
    max_entries: usize,
}

impl L1Cache {
    /// New cache with `max_entries` soft cap.
    #[must_use]
    pub fn new(max_entries: usize) -> Self {
        Self {
            inner: Arc::new(DashMap::with_capacity(max_entries.max(16))),
            max_entries,
        }
    }

    /// Approximate size.
    #[must_use]
    pub fn len(&self) -> usize {
        self.inner.len()
    }

    /// Whether the cache is empty.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }

    /// Insert a typed value. Triggers eviction if over capacity.
    pub fn insert<T: Send + Sync + 'static>(&self, key: CacheKey, value: T) {
        if self.inner.len() >= self.max_entries {
            self.evict_one();
        }
        self.inner.insert(key, Arc::new(value));
    }

    /// Fetch a typed value, downcasting on the way out. Returns `None` if
    /// either the key is absent or the stored type doesn't match.
    pub fn get<T: Clone + Send + Sync + 'static>(&self, key: CacheKey) -> Option<T> {
        let any = self.inner.get(&key)?;
        let arc: &Arc<dyn Any + Send + Sync> = &any;
        let v: &T = arc.downcast_ref::<T>()?;
        Some(v.clone())
    }

    /// Type-erased insert. Used by the scheduler to cache intermediate
    /// pass outputs without knowing their concrete type at the call site.
    pub fn insert_erased(&self, key: CacheKey, value: Arc<dyn Any + Send + Sync>) {
        if self.inner.len() >= self.max_entries {
            self.evict_one();
        }
        self.inner.insert(key, value);
    }

    /// Type-erased get. Returns the stored `Arc<dyn Any>` if present.
    pub fn get_erased(&self, key: CacheKey) -> Option<Arc<dyn Any + Send + Sync>> {
        self.inner.get(&key).map(|v| Arc::clone(&v))
    }

    fn evict_one(&self) {
        if let Some(kv) = self.inner.iter().next() {
            let k = *kv.key();
            drop(kv);
            self.inner.remove(&k);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::key::KeyBuilder;

    #[test]
    fn roundtrip() {
        let c = L1Cache::new(8);
        let key = KeyBuilder::new().mix_u64("x", 1).build();
        c.insert(key, 42u32);
        assert_eq!(c.get::<u32>(key), Some(42));
    }

    #[test]
    fn type_mismatch_returns_none() {
        let c = L1Cache::new(8);
        let key = KeyBuilder::new().mix_u64("x", 1).build();
        c.insert(key, 42u32);
        assert_eq!(c.get::<f32>(key), None);
    }

    #[test]
    fn evicts_when_full() {
        let c = L1Cache::new(2);
        let k1 = KeyBuilder::new().mix_u64("x", 1).build();
        let k2 = KeyBuilder::new().mix_u64("x", 2).build();
        let k3 = KeyBuilder::new().mix_u64("x", 3).build();
        c.insert(k1, 1u32);
        c.insert(k2, 2u32);
        assert_eq!(c.len(), 2);
        c.insert(k3, 3u32);
        assert!(c.len() <= 2);
    }
}
