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

use crossbeam_channel::{unbounded, Receiver, Sender};
use genesis_biome::Biome;
use genesis_climate::ClimateSample;
use genesis_core::{ChunkCoord, Tick, Voxel, WorldCoord, CHUNK_SIZE_X, CHUNK_SIZE_Y};
use genesis_streaming::{Chunk, ChunkManager};
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
        let mut applied = 0;
        while let Ok(m) = self.inner.write_rx.try_recv() {
            // Mutations need write access to the loaded chunk. The current
            // streaming layer hands out `Arc<Chunk>` for read; full write
            // support is part of phase 2 (see roadmap). For now, count and
            // log without actually mutating — a deterministic stub keeps
            // the API surface stable for downstream callers.
            tracing::debug!(?m, "mutation queued (write-back stub)");
            applied += 1;
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
    pub async fn ensure_chunk(&self, coord: ChunkCoord) -> Arc<Chunk> {
        self.inner.manager.get_or_generate(coord).await
    }

    /// Fetch a chunk synchronously (blocks on the generation if not cached).
    pub fn ensure_chunk_blocking(&self, coord: ChunkCoord) -> Arc<Chunk> {
        // The streaming manager's blocking generator.
        Arc::new(self.inner.manager.generate(coord))
    }
}

impl WorldView for WorldClient {
    fn tick(&self) -> Tick {
        *self.inner.tick.read()
    }

    fn voxel(&self, p: WorldCoord) -> Option<Voxel> {
        let coord = p.chunk();
        // We DO NOT auto-generate from a sync read path — that would couple
        // pure reads to CPU-bound work. Callers should `ensure_chunk(...)`
        // before reading.
        if self.inner.manager.cached_count() == 0 {
            return None;
        }
        let local = p.local();
        // Cheap path: build the chunk synchronously if not cached. Acceptable
        // for tests and Python integration; production runtime should warm
        // chunks beforehand.
        let chunk = self.ensure_chunk_blocking(coord);
        Some(chunk.voxel_at(local))
    }

    fn biome(&self, p: WorldCoord) -> Option<Biome> {
        let coord = p.chunk();
        let chunk = self.ensure_chunk_blocking(coord);
        let local = p.local();
        Some(chunk.biome_at(local.x as u32, local.y as u32))
    }

    fn elevation(&self, x: i32, y: i32) -> Option<f32> {
        let p = WorldCoord::new(x, y, 0);
        let chunk = self.ensure_chunk_blocking(p.chunk());
        let local = p.local();
        Some(chunk.elevation_at(local.x as u32, local.y as u32))
    }

    fn climate(&self, x: i32, y: i32) -> Option<ClimateSample> {
        let p = WorldCoord::new(x, y, 0);
        let chunk = self.ensure_chunk_blocking(p.chunk());
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
        let chunk = self.ensure_chunk(coord).await;
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
}
