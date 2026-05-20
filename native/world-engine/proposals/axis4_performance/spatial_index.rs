//! Spatial index for entity queries — replaces the
//! `entities_in_radius -> Vec::new()` stub in `agent-api/src/lib.rs`.
//!
//! Two-level approach :
//!  - Outer: chunk-coord bucket map (so we only inspect entities in chunks
//!    overlapping the query).
//!  - Inner: a per-chunk uniform grid (cell ≈ 4 m) for O(1) radius lookup.
//!
//! Determinism: insertion order is irrelevant — the query result is sorted
//! by `(chunk, local index, id)` before return so callers see canonical
//! output across runs.
//!
//! No external deps; pure ahash. The audit recommends `rstar` for the
//! eventual production version when entity churn dominates.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use ahash::AHashMap;

/// Stable entity id (mirror of `EntityId` in `agent-api`).
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct EntityId(pub u64);

/// Reference returned by queries (mirror of `EntityRef`).
#[derive(Copy, Clone, Debug, PartialEq)]
pub struct EntityRef {
    /// Identity.
    pub id: EntityId,
    /// Position (m).
    pub pos: [f32; 2],
}

/// Spatial index parameters.
#[derive(Copy, Clone, Debug)]
pub struct SpatialParams {
    /// Cell size in metres. Pick ≈ vision_radius for balanced query cost.
    pub cell_m: f32,
}

impl Default for SpatialParams {
    fn default() -> Self {
        Self { cell_m: 4.0 }
    }
}

/// Spatial hash index.
#[derive(Debug, Default)]
pub struct SpatialIndex {
    cell_m: f32,
    grid: AHashMap<(i32, i32), Vec<EntityRef>>,
    by_id: AHashMap<EntityId, EntityRef>,
}

impl SpatialIndex {
    /// New index.
    #[must_use]
    pub fn new(p: SpatialParams) -> Self {
        Self {
            cell_m: p.cell_m,
            grid: AHashMap::new(),
            by_id: AHashMap::new(),
        }
    }

    #[inline]
    fn cell(&self, pos: [f32; 2]) -> (i32, i32) {
        let ix = (pos[0] / self.cell_m).floor() as i32;
        let iy = (pos[1] / self.cell_m).floor() as i32;
        (ix, iy)
    }

    /// Insert or move an entity.
    pub fn upsert(&mut self, e: EntityRef) {
        if let Some(prev) = self.by_id.get(&e.id).copied() {
            let prev_cell = self.cell(prev.pos);
            if let Some(bucket) = self.grid.get_mut(&prev_cell) {
                bucket.retain(|x| x.id != e.id);
            }
        }
        let cell = self.cell(e.pos);
        self.grid.entry(cell).or_default().push(e);
        self.by_id.insert(e.id, e);
    }

    /// Remove an entity.
    pub fn remove(&mut self, id: EntityId) -> bool {
        if let Some(e) = self.by_id.remove(&id) {
            let cell = self.cell(e.pos);
            if let Some(bucket) = self.grid.get_mut(&cell) {
                bucket.retain(|x| x.id != id);
            }
            return true;
        }
        false
    }

    /// All entities within `r` of `p`.
    /// Canonical ordering by id.
    #[must_use]
    pub fn radius(&self, p: [f32; 2], r: f32) -> Vec<EntityRef> {
        let r2 = r * r;
        let span = (r / self.cell_m).ceil() as i32;
        let (cx, cy) = self.cell(p);
        let mut out = Vec::with_capacity(16);
        for dy in -span..=span {
            for dx in -span..=span {
                if let Some(bucket) = self.grid.get(&(cx + dx, cy + dy)) {
                    for e in bucket {
                        let dx = e.pos[0] - p[0];
                        let dy = e.pos[1] - p[1];
                        if dx * dx + dy * dy <= r2 {
                            out.push(*e);
                        }
                    }
                }
            }
        }
        out.sort_by_key(|e| e.id);
        out
    }

    /// Number of indexed entities.
    #[must_use]
    pub fn len(&self) -> usize {
        self.by_id.len()
    }

    /// True iff empty.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.by_id.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make(n: u64) -> SpatialIndex {
        let mut idx = SpatialIndex::new(SpatialParams::default());
        for k in 0..n {
            let theta = k as f32 * 0.1;
            let r = (k as f32).sqrt();
            idx.upsert(EntityRef {
                id: EntityId(k),
                pos: [r * theta.cos(), r * theta.sin()],
            });
        }
        idx
    }

    #[test]
    fn radius_query_recall_100pct() {
        let idx = make(500);
        // Brute force reference.
        let mut brute = Vec::new();
        for k in 0..500 {
            let theta = k as f32 * 0.1;
            let r = (k as f32).sqrt();
            let x = r * theta.cos();
            let y = r * theta.sin();
            if x * x + y * y <= 25.0 {
                brute.push(EntityId(k));
            }
        }
        brute.sort();
        let got: Vec<EntityId> = idx.radius([0.0, 0.0], 5.0).into_iter().map(|e| e.id).collect();
        assert_eq!(got, brute);
    }

    #[test]
    fn upsert_moves_entity() {
        let mut idx = SpatialIndex::new(SpatialParams::default());
        idx.upsert(EntityRef { id: EntityId(1), pos: [0.0, 0.0] });
        idx.upsert(EntityRef { id: EntityId(1), pos: [100.0, 100.0] });
        assert!(idx.radius([0.0, 0.0], 5.0).is_empty());
        assert_eq!(idx.radius([100.0, 100.0], 5.0).len(), 1);
    }

    #[test]
    fn remove_works() {
        let mut idx = SpatialIndex::new(SpatialParams::default());
        idx.upsert(EntityRef { id: EntityId(1), pos: [0.0, 0.0] });
        assert!(idx.remove(EntityId(1)));
        assert!(idx.is_empty());
    }

    #[test]
    fn order_canonical_across_runs() {
        let mut a = SpatialIndex::new(SpatialParams::default());
        let mut b = SpatialIndex::new(SpatialParams::default());
        // Insert in different order — query result must match.
        for k in [3u64, 1, 4, 1, 5, 9, 2, 6].iter() {
            a.upsert(EntityRef { id: EntityId(*k), pos: [*k as f32, 0.0] });
        }
        for k in [9u64, 6, 5, 4, 3, 2, 1].iter() {
            b.upsert(EntityRef { id: EntityId(*k), pos: [*k as f32, 0.0] });
        }
        let qa: Vec<u64> = a.radius([0.0, 0.0], 20.0).iter().map(|e| e.id.0).collect();
        let qb: Vec<u64> = b.radius([0.0, 0.0], 20.0).iter().map(|e| e.id.0).collect();
        assert_eq!(qa, qb);
    }
}
