//! True LRU cache for `ChunkManager`. Replaces the FIFO eviction in
//! `streaming/src/manager.rs::maybe_evict`.
//!
//! Implementation: an `IndexMap`-like structure built from `AHashMap` +
//! `VecDeque`-of-keys (move-to-back on access). For 10k-entry caches the
//! linear scan during eviction stays well under 100 µs.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use ahash::AHashMap;
use std::collections::VecDeque;
use std::hash::Hash;

/// Generic LRU.
#[derive(Debug)]
pub struct Lru<K: Eq + Hash + Clone, V> {
    cap: usize,
    map: AHashMap<K, V>,
    order: VecDeque<K>,
}

impl<K: Eq + Hash + Clone, V> Lru<K, V> {
    /// Build an empty LRU with the given capacity.
    #[must_use]
    pub fn new(cap: usize) -> Self {
        Self {
            cap: cap.max(1),
            map: AHashMap::with_capacity(cap.max(1)),
            order: VecDeque::with_capacity(cap.max(1)),
        }
    }

    /// Return a reference to the value AND mark the key as MRU.
    pub fn get(&mut self, k: &K) -> Option<&V> {
        if !self.map.contains_key(k) {
            return None;
        }
        // Move-to-back.
        if let Some(pos) = self.order.iter().position(|x| x == k) {
            self.order.remove(pos);
            self.order.push_back(k.clone());
        }
        self.map.get(k)
    }

    /// Insert. Evicts LRU if over capacity. Returns evicted entry if any.
    pub fn insert(&mut self, k: K, v: V) -> Option<(K, V)> {
        if self.map.contains_key(&k) {
            self.map.insert(k.clone(), v);
            // Refresh order.
            if let Some(pos) = self.order.iter().position(|x| x == &k) {
                self.order.remove(pos);
            }
            self.order.push_back(k);
            return None;
        }
        let evicted = if self.map.len() >= self.cap {
            let old = self.order.pop_front()?;
            let v = self.map.remove(&old)?;
            Some((old, v))
        } else {
            None
        };
        self.map.insert(k.clone(), v);
        self.order.push_back(k);
        evicted
    }

    /// Current size.
    #[must_use]
    pub fn len(&self) -> usize {
        self.map.len()
    }

    /// True iff empty.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.map.is_empty()
    }

    /// Remove a specific entry.
    pub fn remove(&mut self, k: &K) -> Option<V> {
        let v = self.map.remove(k)?;
        if let Some(pos) = self.order.iter().position(|x| x == k) {
            self.order.remove(pos);
        }
        Some(v)
    }

    /// Iterate over keys in LRU order (least → most recently used).
    pub fn keys_lru(&self) -> impl Iterator<Item = &K> {
        self.order.iter()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lru_evicts_oldest() {
        let mut lru = Lru::<u32, &'static str>::new(2);
        assert_eq!(lru.insert(1, "a"), None);
        assert_eq!(lru.insert(2, "b"), None);
        // Touch 1 → 1 is MRU, 2 is LRU.
        let _ = lru.get(&1);
        let evicted = lru.insert(3, "c").unwrap();
        assert_eq!(evicted.0, 2, "expected key 2 (LRU) to be evicted");
    }

    #[test]
    fn touch_promotes() {
        let mut lru = Lru::<u32, u32>::new(3);
        lru.insert(1, 10);
        lru.insert(2, 20);
        lru.insert(3, 30);
        let _ = lru.get(&1);
        let evicted = lru.insert(4, 40).unwrap();
        assert_eq!(evicted.0, 2);
    }

    #[test]
    fn no_eviction_under_cap() {
        let mut lru = Lru::<u32, u32>::new(10);
        for k in 0..5 {
            assert!(lru.insert(k, k * 10).is_none());
        }
        assert_eq!(lru.len(), 5);
    }

    #[test]
    fn remove_works() {
        let mut lru = Lru::<u32, u32>::new(4);
        lru.insert(1, 10);
        lru.insert(2, 20);
        assert_eq!(lru.remove(&1), Some(10));
        assert!(lru.get(&1).is_none());
        assert_eq!(lru.len(), 1);
    }
}
