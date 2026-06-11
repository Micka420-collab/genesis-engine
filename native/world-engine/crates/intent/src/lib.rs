//! genesis-intent — intent-aware chunk prefetcher.
//!
//! Agents declare their planned trajectory; this module converts that into
//! a list of chunks to warm up before the agent arrives. Useful in pure
//! AI-driven worlds where the consumer of the terrain is itself
//! introspectable.
//!
//! Compared to camera-frustum prefetch, this approach:
//!   - Looks beyond the visible range (a 1 km plan triggers 1 km prefetch).
//!   - Survives camera-cut transitions and teleports.
//!   - Lets the LRU evict chunks that the agent has *committed* to leaving.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use ahash::AHashSet;
use genesis_core::{ChunkCoord, WorldCoord, CHUNK_SIZE_X, CHUNK_SIZE_Y};
use genesis_streaming::ChunkManager;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use smallvec::SmallVec;
use std::sync::Arc;
use tracing::{debug, instrument};

/// Agent identifier (opaque from this crate's view).
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct AgentId(pub u64);

/// A movement intent.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum Plan {
    /// The agent is staying around `center` for the foreseeable future.
    Idle {
        /// Stationary position.
        center: WorldCoord,
        /// Radius the agent might wander within.
        radius_m: f32,
    },
    /// The agent is walking the given waypoints in order.
    WalkAlong(Vec<WorldCoord>),
    /// The agent will teleport to a single target and stay there.
    TeleportTo(WorldCoord),
}

/// A submitted intent.
#[derive(Clone, Debug)]
pub struct Intent {
    /// Whose intent it is.
    pub agent: AgentId,
    /// What they plan to do.
    pub plan: Plan,
    /// Horizon: how many ticks ahead this plan is considered valid.
    pub horizon_ticks: u32,
    /// Priority (1..255). Higher means warm earlier.
    pub priority: u8,
}

/// Computed prefetch list for one intent.
#[derive(Debug)]
pub struct PrefetchPlan {
    /// Chunks to warm, in priority order.
    pub chunks: SmallVec<[ChunkCoord; 32]>,
}

/// Intent registry. Holds the most recent intent per agent.
#[derive(Clone, Default)]
pub struct IntentBus {
    inner: Arc<RwLock<ahash::AHashMap<AgentId, Intent>>>,
}

impl IntentBus {
    /// New empty registry.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Replace any previous intent for the agent.
    pub fn submit(&self, intent: Intent) {
        self.inner.write().insert(intent.agent, intent);
    }

    /// Drop an agent's intent (e.g. when it dies or disconnects).
    pub fn clear(&self, agent: AgentId) {
        self.inner.write().remove(&agent);
    }

    /// Aggregate chunks across all live intents, deduplicated, ordered
    /// roughly by priority.
    #[must_use]
    pub fn collect_prefetch_chunks(&self) -> Vec<ChunkCoord> {
        let snapshot: Vec<Intent> = self.inner.read().values().cloned().collect();
        let mut bucket: Vec<(u8, ChunkCoord)> = Vec::new();
        let mut seen = AHashSet::with_capacity(64);
        for it in snapshot {
            let plan = plan_to_chunks(&it.plan);
            for c in plan.chunks {
                if seen.insert(c) {
                    bucket.push((it.priority, c));
                }
            }
        }
        bucket.sort_by(|a, b| b.0.cmp(&a.0));
        bucket.into_iter().map(|(_, c)| c).collect()
    }
}

/// Convert one plan into the chunks it touches.
#[must_use]
pub fn plan_to_chunks(plan: &Plan) -> PrefetchPlan {
    let mut chunks = SmallVec::<[ChunkCoord; 32]>::new();
    let mut seen = AHashSet::with_capacity(32);
    match plan {
        Plan::Idle { center, radius_m } => {
            let r_chunks = ((radius_m / CHUNK_SIZE_X as f32).ceil() as i32).max(1);
            let centre_chunk = center.chunk();
            for dy in -r_chunks..=r_chunks {
                for dx in -r_chunks..=r_chunks {
                    let c = ChunkCoord {
                        cx: centre_chunk.cx + dx,
                        cy: centre_chunk.cy + dy,
                    };
                    if seen.insert(c) {
                        chunks.push(c);
                    }
                }
            }
        }
        Plan::WalkAlong(waypoints) => {
            for w in waypoints {
                let cc = w.chunk();
                // Plus a small neighborhood
                for dj in -1..=1 {
                    for di in -1..=1 {
                        let c = ChunkCoord {
                            cx: cc.cx + di,
                            cy: cc.cy + dj,
                        };
                        if seen.insert(c) {
                            chunks.push(c);
                        }
                    }
                }
            }
        }
        Plan::TeleportTo(target) => {
            let cc = target.chunk();
            for dj in -2..=2 {
                for di in -2..=2 {
                    let c = ChunkCoord {
                        cx: cc.cx + di,
                        cy: cc.cy + dj,
                    };
                    if seen.insert(c) {
                        chunks.push(c);
                    }
                }
            }
        }
    }
    PrefetchPlan { chunks }
}

/// Spawn a background task that drains the bus and warms chunks via the
/// given `ChunkManager`. Returns a handle the caller can drop to stop.
#[must_use]
pub fn spawn_prefetcher(
    bus: IntentBus,
    manager: ChunkManager,
    poll_period_ms: u64,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(prefetch_loop(bus, manager, poll_period_ms))
}

#[instrument(skip(bus, manager))]
async fn prefetch_loop(bus: IntentBus, manager: ChunkManager, poll_period_ms: u64) {
    let mut tick_period = tokio::time::interval(std::time::Duration::from_millis(poll_period_ms));
    let mut max_inflight = 8usize;
    loop {
        tick_period.tick().await;
        let chunks = bus.collect_prefetch_chunks();
        if chunks.is_empty() {
            continue;
        }
        let mut handles = Vec::with_capacity(chunks.len().min(max_inflight));
        for c in chunks.into_iter().take(max_inflight) {
            let mgr = manager.clone();
            handles.push(tokio::spawn(async move { mgr.get_or_generate(c).await }));
        }
        for h in handles {
            let _ = h.await;
        }
        // Slow-start: if we kept up, warm more next round.
        if max_inflight < 64 {
            max_inflight += 1;
        }
        debug!("prefetch round done");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn idle_plan_covers_radius() {
        let p = Plan::Idle {
            center: WorldCoord::new(0, 0, 0),
            radius_m: (CHUNK_SIZE_X as f32) * 2.5,
        };
        let pp = plan_to_chunks(&p);
        // 3 chunks each way → 7x7 = 49
        assert!(pp.chunks.len() >= 49);
    }

    #[test]
    fn walk_along_covers_neighbourhood() {
        let p = Plan::WalkAlong(vec![
            WorldCoord::new(0, 0, 0),
            WorldCoord::new(CHUNK_SIZE_X * 4, CHUNK_SIZE_Y, 0),
        ]);
        let pp = plan_to_chunks(&p);
        assert!(pp.chunks.len() >= 9);
    }

    #[test]
    fn intent_bus_collects_unique() {
        let bus = IntentBus::new();
        bus.submit(Intent {
            agent: AgentId(1),
            plan: Plan::Idle {
                center: WorldCoord::new(0, 0, 0),
                radius_m: (CHUNK_SIZE_X as f32) * 1.5,
            },
            horizon_ticks: 100,
            priority: 200,
        });
        bus.submit(Intent {
            agent: AgentId(2),
            plan: Plan::Idle {
                center: WorldCoord::new(0, 0, 0),
                radius_m: (CHUNK_SIZE_X as f32) * 1.5,
            },
            horizon_ticks: 100,
            priority: 100,
        });
        let chunks = bus.collect_prefetch_chunks();
        let unique: AHashSet<_> = chunks.iter().copied().collect();
        assert_eq!(unique.len(), chunks.len());
    }
}
