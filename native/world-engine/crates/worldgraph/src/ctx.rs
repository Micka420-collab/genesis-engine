//! Context passed to every pass.

use genesis_core::{ChunkCoord, SeedTree, Tick, TickDomain, WorldSeed};

/// Read-only context handed to each [`super::Pass::run`].
#[derive(Copy, Clone, Debug)]
pub struct PassCtx {
    /// World seed.
    pub seed: WorldSeed,
    /// Hierarchical seed tree — use `seed_tree.prf("layer.name")`.
    pub seed_tree: SeedTree,
    /// Chunk being generated.
    pub coord: ChunkCoord,
    /// Simulation tick (for time-dependent passes).
    pub tick: Tick,
    /// Optional domain tag — used by multi-rate coupler hooks.
    pub domain: Option<TickDomain>,
}

impl PassCtx {
    /// New context.
    #[must_use]
    pub fn new(seed: WorldSeed, coord: ChunkCoord, tick: Tick) -> Self {
        Self {
            seed,
            seed_tree: SeedTree::new(seed),
            coord,
            tick,
            domain: None,
        }
    }

    /// Context with explicit domain (for multi-rate scheduling).
    #[must_use]
    pub fn with_domain(mut self, domain: TickDomain) -> Self {
        self.domain = Some(domain);
        self
    }
}
