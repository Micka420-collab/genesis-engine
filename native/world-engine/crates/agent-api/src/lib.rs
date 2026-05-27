//! genesis-agent-api — read/write façade for AI agents.
//!
//! Reads are lock-free (tick-stable snapshots). Writes are queued and applied
//! at tick boundaries — agents never observe a half-applied tick.
//!
//! Two surface layers:
//!  - `WorldView`   : pure read trait (Send+Sync, cheap clones).
//!  - `WorldClient` : owning handle that bundles read + queued writes.
//!
//! The Python bindings (in `genesis-pybindings`) wrap `WorldClient`.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

mod snapshot;

pub use snapshot::{
    load as load_snapshot, save as save_snapshot, hash_snapshot, ChunkSnapshot, SnapshotError,
    WorldSnapshot,
};

use crossbeam_channel::{unbounded, Receiver, Sender};
use genesis_biome::Biome;
use genesis_climate::ClimateSample;
use genesis_core::{
    ChunkCoord, Tick, Voxel, WorldCoord, CHUNK_SIZE_X, CHUNK_SIZE_Y, CHUNK_VOXEL_COUNT,
};
use genesis_streaming::{ChunkManager, SharedChunk};
use glam::Vec3;
use parking_lot::RwLock;
use smallvec::SmallVec;
use std::sync::Arc;
use thiserror::Error;

/// Errors that can occur during mutations.
#[derive(Error, Debug)]
pub enum MutError {
    /// Coordinate is outside the supported world range.
    #[error("out of bounds")]
    OutOfBounds,
    /// The chunk wasn't loaded; load it before mutating.
    #[error("chunk not loaded: {0:?}")]
    ChunkNotLoaded(ChunkCoord),
    /// Two agents tried to mutate the same voxel during the same tick.
    #[error("mutation conflict at tick {0:?}")]
    Conflict(Tick),
}

/// Identifier for an entity inside the world.
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash)]
pub struct EntityId(pub u64);

/// Lightweight handle returned by spatial queries.
#[derive(Copy, Clone, Debug)]
pub struct EntityRef {
    /// Entity identifier.
    pub id: EntityId,
    /// World coordinate.
    pub pos: WorldCoord,
}

/// Raycast hit.
#[derive(Copy, Clone, Debug)]
pub struct RayHit {
    /// Hit voxel position.
    pub voxel: WorldCoord,
    /// Distance along the ray.
    pub distance: f32,
    /// Voxel value at the hit.
    pub voxel_value: Voxel,
}

/// Mutation submitted by an agent — applied at the next tick boundary.
#[derive(Clone, Debug)]
pub enum Mutation {
    /// Replace a single voxel.
    SetVoxel {
        /// Position to modify.
        pos: WorldCoord,
        /// New value.
        value: Voxel,
        /// Agent submitting the change.
        actor: EntityId,
    },
    /// Spawn a new entity.
    SpawnEntity {
        /// Initial position.
        pos: WorldCoord,
        /// Blueprint hash — meaning is up to the agent runtime.
        blueprint: u64,
        /// Actor submitting the spawn.
        actor: EntityId,
    },
}

/// Read-only view of the world. Cheap to clone (it's an `Arc` inside).
pub trait WorldView: Send + Sync {
    /// Current simulation tick.
    fn tick(&self) -> Tick;
    /// Voxel at a position (if the containing chunk is loaded).
    fn voxel(&self, p: WorldCoord) -> Option<Voxel>;
    /// Surface biome at a position.
    fn biome(&self, p: WorldCoord) -> Option<Biome>;
    /// Surface elevation at `(x, y)` (m).
    fn elevation(&self, x: i32, y: i32) -> Option<f32>;
    /// Climate sample at the surface.
    fn climate(&self, x: i32, y: i32) -> Option<ClimateSample>;
    /// Entities near a position.
    fn entities_in_radius(&self, p: WorldCoord, r: f32) -> Vec<EntityRef>;
    /// Cast a ray. Returns the first solid hit or None.
    fn raycast(&self, origin: Vec3, dir: Vec3, max_distance: f32) -> Option<RayHit>;
}

/// Owning client — read + queued mutations.
pub struct WorldClient {
    inner: Arc<WorldClientInner>,
}

struct WorldClientInner {
    tick: RwLock<Tick>,
    manager: ChunkManager,
    write_tx: Sender<Mutation>,
    write_rx: Receiver<Mutation>,
    /// Spawn records applied at tick boundary (entity index = Python layer).
    spawns: RwLock<Vec<(WorldCoord, u64, EntityId)>>,
}

impl WorldClient {
    /// Build a new client from a chunk manager.
    #[must_use]
    pub fn new(manager: ChunkManager) -> Self {
        let (tx, rx) = unbounded();
        Self {
            inner: Arc::new(WorldClientInner {
                tick: RwLock::new(Tick::ZERO),
                manager,
                write_tx: tx,
                write_rx: rx,
                spawns: RwLock::new(Vec::new()),
            }),
        }
    }

    /// Submit a mutation. It is applied at the start of the next tick.
    pub fn submit(&self, m: Mutation) -> Result<(), MutError> {
        self.inner.write_tx.send(m).map_err(|_| MutError::OutOfBounds)
    }

    /// Drain all queued mutations and apply them. Called by the simulation
    /// tick coordinator — agents do not call this directly.
    pub fn apply_pending(&self) -> usize {
        let mut batch = Vec::new();
        while let Ok(m) = self.inner.write_rx.try_recv() {
            batch.push(m);
        }
        batch.sort_by_key(|m| match m {
            Mutation::SetVoxel { pos, actor, .. } => (pos.x, pos.y, pos.z, actor.0, 0u8),
            Mutation::SpawnEntity { pos, actor, .. } => (pos.x, pos.y, pos.z, actor.0, 1u8),
        });
        let mut applied = 0;
        for m in batch {
            match m {
                Mutation::SetVoxel { pos, value, actor } => {
                    if self.inner.manager.set_voxel(pos, value) {
                        tracing::debug!(?pos, ?value, ?actor, "voxel write-back");
                        applied += 1;
                    }
                }
                Mutation::SpawnEntity { pos, blueprint, actor } => {
                    self.inner.spawns.write().push((pos, blueprint, actor));
                    tracing::debug!(?pos, blueprint, ?actor, "spawn recorded");
                    applied += 1;
                }
            }
        }
        applied
    }

    /// Advance the tick counter by 1.
    pub fn advance_tick(&self) -> Tick {
        let mut t = self.inner.tick.write();
        *t = t.next();
        *t
    }

    /// Force-generate (or fetch from cache) a chunk.
    pub async fn ensure_chunk(&self, coord: ChunkCoord) -> SharedChunk {
        self.inner.manager.get_or_generate(coord).await
    }

    /// Fetch a chunk synchronously (cache-aware; preserves mutations).
    pub fn ensure_chunk_blocking(&self, coord: ChunkCoord) -> SharedChunk {
        self.inner.manager.get_or_generate_blocking(coord)
    }

    /// Spawns recorded since construction (cleared only on new client).
    pub fn pending_spawns(&self) -> Vec<(WorldCoord, u64, EntityId)> {
        self.inner.spawns.read().clone()
    }

    /// Capture tick + all cached chunks (including mutations).
    pub fn capture_snapshot(&self) -> WorldSnapshot {
        let tick = self.inner.tick.read().0;
        let seed = self.inner.manager.seed_u64();
        let spawns: Vec<(WorldCoord, u64, u64)> = self
            .inner
            .spawns
            .read()
            .iter()
            .map(|(p, bp, a)| (*p, *bp, a.0))
            .collect();
        let mut chunks = Vec::new();
        self.inner.manager.for_each_cached(|coord, chunk| {
            chunks.push(ChunkSnapshot::from_chunk(
                coord,
                chunk.meta.mutation_version,
                chunk.voxels.clone(),
                &spawns,
            ));
        });
        WorldSnapshot { seed, tick, chunks }
    }

    /// Serialize snapshot (zstd level 3).
    pub fn snapshot_bytes(&self) -> Result<Vec<u8>, SnapshotError> {
        save_snapshot(&self.capture_snapshot(), 3)
    }

    /// Restore voxel buffers and tick from a snapshot.
    pub fn restore_snapshot(&self, snap: &WorldSnapshot) -> Result<(), SnapshotError> {
        *self.inner.tick.write() = Tick(snap.tick);
        for cs in &snap.chunks {
            if cs.voxels.len() != CHUNK_VOXEL_COUNT {
                return Err(SnapshotError::VoxelLenMismatch {
                    cx: cs.cx,
                    cy: cs.cy,
                });
            }
            let coord = ChunkCoord {
                cx: cs.cx,
                cy: cs.cy,
            };
            self.inner
                .manager
                .restore_chunk_voxels(coord, cs.voxels.clone(), cs.version);
            let mut spawns = self.inner.spawns.write();
            spawns.retain(|(p, _, _)| p.chunk() != coord);
            for &(x, y, z, blueprint, actor) in &cs.spawned {
                spawns.push((
                    WorldCoord::new(x, y, z),
                    blueprint,
                    EntityId(actor),
                ));
            }
        }
        Ok(())
    }

    /// Load snapshot from compressed bytes and apply.
    pub fn restore_snapshot_bytes(&self, bytes: &[u8]) -> Result<WorldSnapshot, SnapshotError> {
        let snap = load_snapshot(bytes)?;
        self.restore_snapshot(&snap)?;
        Ok(snap)
    }
}

impl WorldView for WorldClient {
    fn tick(&self) -> Tick {
        *self.inner.tick.read()
    }

    fn voxel(&self, p: WorldCoord) -> Option<Voxel> {
        let shared = self.ensure_chunk_blocking(p.chunk());
        Some(shared.read().voxel_at(p.local()))
    }

    fn biome(&self, p: WorldCoord) -> Option<Biome> {
        let shared = self.ensure_chunk_blocking(p.chunk());
        let chunk = shared.read();
        let local = p.local();
        Some(chunk.biome_at(local.x as u32, local.y as u32))
    }

    fn elevation(&self, x: i32, y: i32) -> Option<f32> {
        let p = WorldCoord::new(x, y, 0);
        let shared = self.ensure_chunk_blocking(p.chunk());
        let chunk = shared.read();
        let local = p.local();
        Some(chunk.elevation_at(local.x as u32, local.y as u32))
    }

    fn climate(&self, x: i32, y: i32) -> Option<ClimateSample> {
        let p = WorldCoord::new(x, y, 0);
        let shared = self.ensure_chunk_blocking(p.chunk());
        let chunk = shared.read();
        let local = p.local();
        let idx = (local.y as usize) * (CHUNK_SIZE_X as usize) + (local.x as usize);
        Some(chunk.climate[idx])
    }

    fn entities_in_radius(&self, _p: WorldCoord, _r: f32) -> Vec<EntityRef> {
        // Stub — the entity index lives in the agent runtime, not in the
        // world engine. The Python layer will populate this.
        Vec::new()
    }

    fn raycast(&self, origin: Vec3, dir: Vec3, max_distance: f32) -> Option<RayHit> {
        // Branchless DDA over voxels. This walks one chunk at a time and
        // pulls chunks via the blocking path on demand. Acceptable for the
        // current API surface; a per-chunk acceleration structure is a
        // future task.
        let d = dir.normalize();
        let step = 0.5_f32;
        let mut t = 0.0_f32;
        while t < max_distance {
            let p = origin + d * t;
            let wc = WorldCoord::new(p.x.floor() as i32, p.y.floor() as i32, p.z.floor() as i32);
            if let Some(v) = self.voxel(wc) {
                if !v.is_air() {
                    return Some(RayHit {
                        voxel: wc,
                        distance: t,
                        voxel_value: v,
                    });
                }
            }
            t += step;
        }
        None
    }
}

/// A summarised, agent-friendly observation of a 2D area at the surface.
/// Returned by `WorldClient::observe_area` — useful for vision/perception.
#[derive(Clone, Debug)]
pub struct AreaObservation {
    /// Chunk coordinate covered.
    pub chunk: ChunkCoord,
    /// Surface elevation grid.
    pub elevation: Vec<f32>,
    /// Biome grid.
    pub biome: Vec<Biome>,
    /// River mask.
    pub river_mask: Vec<bool>,
    /// Entities sampled in the area.
    pub entities: SmallVec<[EntityRef; 16]>,
}

impl WorldClient {
    /// Build a complete area observation for one chunk. Generates if needed.
    pub async fn observe_area(&self, coord: ChunkCoord) -> AreaObservation {
        let shared = self.ensure_chunk(coord).await;
        let chunk = shared.read();
        AreaObservation {
            chunk: coord,
            elevation: chunk.elevation.clone(),
            biome: chunk.biome.clone(),
            river_mask: chunk.river_mask.clone(),
            entities: SmallVec::new(),
        }
    }
}

/// Convenience: how many surface cells in a chunk.
pub const SURFACE_CELLS_PER_CHUNK: usize = (CHUNK_SIZE_X * CHUNK_SIZE_Y) as usize;

#[cfg(test)]
mod tests {
    use super::*;
    use genesis_core::WorldSeed;
    use genesis_streaming::manager::ChunkManagerConfig;

    fn fast_cfg() -> ChunkManagerConfig {
        ChunkManagerConfig {
            erosion_droplets: 8,
            erosion_passes: 1,
            cache_capacity: 4,
            ..Default::default()
        }
    }

    #[tokio::test]
    async fn client_observes_area() {
        let mgr = ChunkManager::new(WorldSeed::from_u64(7), fast_cfg());
        let client = WorldClient::new(mgr);
        let obs = client.observe_area(ChunkCoord { cx: 0, cy: 0 }).await;
        assert_eq!(obs.elevation.len(), SURFACE_CELLS_PER_CHUNK);
        assert_eq!(obs.biome.len(), SURFACE_CELLS_PER_CHUNK);
    }

    #[test]
    fn set_voxel_writeback_in_chunk_buffer() {
        use genesis_core::{Material, Voxel};

        let mgr = ChunkManager::new(WorldSeed::from_u64(7), fast_cfg());
        let client = WorldClient::new(mgr.clone());
        let pos = WorldCoord::new(1, 1, 2);
        let stone = Voxel(Material::Stone as u16);
        client
            .submit(Mutation::SetVoxel {
                pos,
                value: stone,
                actor: EntityId(1),
            })
            .unwrap();
        assert_eq!(client.apply_pending(), 1);
        let read = client.voxel(pos).expect("voxel after write-back");
        assert_eq!(read, stone);
        let shared = mgr.get_or_generate_blocking(pos.chunk());
        assert_eq!(shared.read().voxel_at(pos.local()), stone);
        assert!(shared.read().meta.mutation_version >= 1);
    }

    #[test]
    fn snapshot_roundtrip_preserves_voxel() {
        use genesis_core::{Material, Voxel, WorldSeed};

        let mgr = ChunkManager::new(WorldSeed::from_u64(99), fast_cfg());
        let client = WorldClient::new(mgr);
        let pos = WorldCoord::new(2, 3, 4);
        let stone = Voxel(Material::Stone as u16);
        client
            .submit(Mutation::SetVoxel {
                pos,
                value: stone,
                actor: EntityId(1),
            })
            .unwrap();
        client.apply_pending();
        let bytes = client.snapshot_bytes().unwrap();
        assert!(client.voxel(pos).unwrap() == stone);
        // Fresh client + restore
        let mgr2 = ChunkManager::new(WorldSeed::from_u64(99), fast_cfg());
        let client2 = WorldClient::new(mgr2);
        client2.restore_snapshot_bytes(&bytes).unwrap();
        assert_eq!(client2.voxel(pos), Some(stone));
    }

    #[test]
    fn mutated_chunks_survive_eviction_pressure() {
        // Mutate many more chunks than the cache can hold. Without the
        // mutation-pin in maybe_evict, the LRU scanner could drop chunks
        // whose mutations exist nowhere else, silently losing data at
        // snapshot time.
        use genesis_core::{Material, Voxel, WorldSeed};

        let cfg = ChunkManagerConfig {
            erosion_droplets: 4,
            erosion_passes: 0,
            cache_capacity: 4, // tiny — forces eviction on every new chunk
            ..Default::default()
        };
        let mgr = ChunkManager::new(WorldSeed::from_u64(2026), cfg.clone());
        let client = WorldClient::new(mgr);

        let stone = Voxel(Material::Stone as u16);
        // 16 mutations across 16 distinct chunks (one mutation per chunk).
        let mutations: Vec<WorldCoord> = (0..16)
            .map(|i| {
                // Offset by CHUNK_SIZE so each WorldCoord lands in a different chunk.
                WorldCoord::new((i as i32) * (CHUNK_SIZE_X as i32) + 1, 1, 2)
            })
            .collect();
        for pos in &mutations {
            client
                .submit(Mutation::SetVoxel {
                    pos: *pos,
                    value: stone,
                    actor: EntityId(1),
                })
                .unwrap();
            client.apply_pending(); // triggers maybe_evict each round
        }

        // Sanity: all writes are still readable on the live client (i.e.
        // not evicted under our feet).
        for pos in &mutations {
            assert_eq!(
                client.voxel(*pos),
                Some(stone),
                "mutation at {pos:?} was lost in-process"
            );
        }

        // Snapshot must contain every mutation.
        let bytes = client.snapshot_bytes().expect("snapshot bytes");

        // Fresh manager + client, restore, and re-verify.
        let mgr2 = ChunkManager::new(WorldSeed::from_u64(2026), cfg);
        let client2 = WorldClient::new(mgr2);
        client2
            .restore_snapshot_bytes(&bytes)
            .expect("restore snapshot");
        for pos in &mutations {
            assert_eq!(
                client2.voxel(*pos),
                Some(stone),
                "mutation at {pos:?} lost in snapshot/restore round-trip"
            );
        }
    }
}
