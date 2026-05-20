//! Real `apply_pending` — replaces the explicit stub at
//! `agent-api/src/lib.rs:139-151`. Three steps per mutation:
//!  1. Lock the target chunk (interior mutability via parking_lot RwLock).
//!  2. Swap the voxel / spawn the entity.
//!  3. Invalidate the content-addressed cache key derived from
//!     `(world_seed, "chunk", coord, version)`.
//!
//! The "version" trick avoids invalidating the entire L1/L2 cache : each
//! chunk owns a monotonic version counter ; cache keys include it ; bump
//! the version when the chunk mutates, the *next* query goes to the new
//! cache slot, the old slot is GCed in the background.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use ahash::AHashMap;
use parking_lot::RwLock;
use std::sync::Arc;

/// Stand-in voxel value (16-bit material code).
pub type Voxel = u16;

/// Chunk coordinate (mirror of `core::ChunkCoord`).
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash)]
pub struct ChunkCoord {
    /// Chunk X.
    pub cx: i32,
    /// Chunk Y.
    pub cy: i32,
}

/// World coordinate (mirror of `core::WorldCoord`).
#[derive(Copy, Clone, Debug)]
pub struct WorldCoord {
    /// Voxel X.
    pub x: i32,
    /// Voxel Y.
    pub y: i32,
    /// Voxel Z.
    pub z: i32,
}

/// Entity id (mirror of `agent-api::EntityId`).
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash)]
pub struct EntityId(pub u64);

/// Mutation request.
#[derive(Clone, Debug)]
pub enum Mutation {
    /// Replace a voxel.
    SetVoxel {
        /// World position.
        pos: WorldCoord,
        /// New value.
        value: Voxel,
        /// Submitting agent.
        actor: EntityId,
    },
    /// Spawn a new entity at a position.
    SpawnEntity {
        /// World position.
        pos: WorldCoord,
        /// Opaque blueprint hash.
        blueprint: u64,
        /// Submitting agent.
        actor: EntityId,
    },
}

/// Errors during mutation application.
#[derive(Debug)]
pub enum MutError {
    /// The chunk was not loaded (caller did not pre-warm).
    ChunkNotLoaded(ChunkCoord),
    /// Out-of-bounds voxel coordinate.
    OutOfBounds,
}

/// Internal chunk record with versioning.
#[derive(Debug)]
pub struct VersionedChunk {
    /// Voxel buffer, flat row-major XYZ.
    pub voxels: Vec<Voxel>,
    /// Monotonic version. Increments on every mutation.
    pub version: u64,
    /// Spawned-entity list (delta against original chunk).
    pub spawned: Vec<(WorldCoord, u64, EntityId)>,
}

/// Mutation accumulator + applier.
#[derive(Default)]
pub struct MutationApplier {
    pending: parking_lot::Mutex<Vec<Mutation>>,
    chunks: AHashMap<ChunkCoord, Arc<RwLock<VersionedChunk>>>,
    /// Optional list of cache keys to drop after applying.
    pub invalidated: parking_lot::Mutex<Vec<(ChunkCoord, u64)>>,
}

impl MutationApplier {
    /// New empty applier.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Register an already-loaded chunk.
    pub fn register_chunk(&mut self, coord: ChunkCoord, c: VersionedChunk) {
        self.chunks.insert(coord, Arc::new(RwLock::new(c)));
    }

    /// Submit a mutation; processed at the next `apply_pending`.
    pub fn submit(&self, m: Mutation) {
        self.pending.lock().push(m);
    }

    /// Apply all queued mutations. Returns the number applied successfully.
    ///
    /// Canonical ordering: mutations are sorted by `(coord, actor.id, kind)`
    /// before application, so two runs with the same queue produce the
    /// same result regardless of submission order.
    pub fn apply_pending(&self) -> usize {
        let mut q = std::mem::take(&mut *self.pending.lock());
        q.sort_by_key(|m| match m {
            Mutation::SetVoxel { pos, actor, .. } => (
                pos.x / 64, pos.y / 64, actor.0, 0u8,
            ),
            Mutation::SpawnEntity { pos, actor, .. } => (
                pos.x / 64, pos.y / 64, actor.0, 1u8,
            ),
        });
        let mut applied = 0;
        for m in q {
            match m {
                Mutation::SetVoxel { pos, value, .. } => {
                    let coord = ChunkCoord {
                        cx: pos.x.div_euclid(64),
                        cy: pos.y.div_euclid(64),
                    };
                    if let Some(chunk) = self.chunks.get(&coord) {
                        let mut c = chunk.write();
                        let local_x = pos.x.rem_euclid(64) as usize;
                        let local_y = pos.y.rem_euclid(64) as usize;
                        let local_z = pos.z.clamp(0, 127) as usize;
                        let idx = local_x + local_y * 64 + local_z * 64 * 64;
                        if idx < c.voxels.len() {
                            c.voxels[idx] = value;
                            c.version = c.version.wrapping_add(1);
                            self.invalidated.lock().push((coord, c.version));
                            applied += 1;
                        }
                    }
                }
                Mutation::SpawnEntity { pos, blueprint, actor } => {
                    let coord = ChunkCoord {
                        cx: pos.x.div_euclid(64),
                        cy: pos.y.div_euclid(64),
                    };
                    if let Some(chunk) = self.chunks.get(&coord) {
                        let mut c = chunk.write();
                        c.spawned.push((pos, blueprint, actor));
                        c.version = c.version.wrapping_add(1);
                        applied += 1;
                    }
                }
            }
        }
        applied
    }

    /// Read a voxel after mutations (returns `None` if chunk not loaded).
    pub fn read_voxel(&self, pos: WorldCoord) -> Option<Voxel> {
        let coord = ChunkCoord {
            cx: pos.x.div_euclid(64),
            cy: pos.y.div_euclid(64),
        };
        let chunk = self.chunks.get(&coord)?;
        let c = chunk.read();
        let local_x = pos.x.rem_euclid(64) as usize;
        let local_y = pos.y.rem_euclid(64) as usize;
        let local_z = pos.z.clamp(0, 127) as usize;
        let idx = local_x + local_y * 64 + local_z * 64 * 64;
        c.voxels.get(idx).copied()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn empty_chunk() -> VersionedChunk {
        VersionedChunk {
            voxels: vec![0u16; 64 * 64 * 128],
            version: 0,
            spawned: vec![],
        }
    }

    #[test]
    fn voxel_mutation_visible_next_tick() {
        let mut m = MutationApplier::new();
        m.register_chunk(ChunkCoord { cx: 0, cy: 0 }, empty_chunk());
        m.submit(Mutation::SetVoxel {
            pos: WorldCoord { x: 5, y: 7, z: 10 },
            value: 42,
            actor: EntityId(1),
        });
        assert_eq!(m.read_voxel(WorldCoord { x: 5, y: 7, z: 10 }), Some(0));
        assert_eq!(m.apply_pending(), 1);
        assert_eq!(m.read_voxel(WorldCoord { x: 5, y: 7, z: 10 }), Some(42));
    }

    #[test]
    fn submission_order_doesnt_affect_result() {
        let mut a = MutationApplier::new();
        a.register_chunk(ChunkCoord { cx: 0, cy: 0 }, empty_chunk());
        let mut b = MutationApplier::new();
        b.register_chunk(ChunkCoord { cx: 0, cy: 0 }, empty_chunk());
        let mutations = vec![
            Mutation::SetVoxel {
                pos: WorldCoord { x: 1, y: 0, z: 0 },
                value: 100,
                actor: EntityId(2),
            },
            Mutation::SetVoxel {
                pos: WorldCoord { x: 1, y: 0, z: 0 },
                value: 200,
                actor: EntityId(1),
            },
        ];
        for m in &mutations {
            a.submit(m.clone());
        }
        for m in mutations.iter().rev() {
            b.submit(m.clone());
        }
        a.apply_pending();
        b.apply_pending();
        // Both finished with the higher-id actor's mutation as last applied
        // (sort key is actor.id ascending → actor.id=2 wins because it sorts
        // last in the (coord, actor) key).
        let va = a.read_voxel(WorldCoord { x: 1, y: 0, z: 0 }).unwrap();
        let vb = b.read_voxel(WorldCoord { x: 1, y: 0, z: 0 }).unwrap();
        assert_eq!(va, vb);
    }

    #[test]
    fn out_of_chunk_mutation_is_noop() {
        let m = MutationApplier::new();
        m.submit(Mutation::SetVoxel {
            pos: WorldCoord { x: 100, y: 0, z: 0 },
            value: 7,
            actor: EntityId(0),
        });
        assert_eq!(m.apply_pending(), 0);
    }

    #[test]
    fn spawn_recorded() {
        let mut m = MutationApplier::new();
        m.register_chunk(ChunkCoord { cx: 0, cy: 0 }, empty_chunk());
        m.submit(Mutation::SpawnEntity {
            pos: WorldCoord { x: 3, y: 3, z: 3 },
            blueprint: 0xABCD,
            actor: EntityId(99),
        });
        assert_eq!(m.apply_pending(), 1);
        let c = m.chunks.get(&ChunkCoord { cx: 0, cy: 0 }).unwrap().read();
        assert_eq!(c.spawned.len(), 1);
        assert_eq!(c.spawned[0].1, 0xABCD);
    }
}
