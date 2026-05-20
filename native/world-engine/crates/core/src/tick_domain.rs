//! Multi-rate simulation domains — foundation for coupled sub-cycles.
//!
//! Each domain advances at its own `dt_sim_seconds`. The [`MultiRateCoupler`]
//! in [`super::coupler`] tracks per-domain ticks and reports which domains
//! should run when the master clock advances.

use crate::tick::Tick;
use serde::{Deserialize, Serialize};

/// Physical or logical sub-system with its own time step.
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[repr(u8)]
pub enum TickDomain {
    /// Agent cognition / physiology (base sim step, typically 1 s).
    Agent = 0,
    /// Mesoscale weather (default 300 s).
    Weather = 1,
    /// Daily ecology / hydrology (default 86_400 s).
    Ecology = 2,
    /// Geology / tectonics (default 1000 sim-years).
    Tectonics = 3,
}

impl TickDomain {
    /// Default `dt` in sim-seconds for this domain.
    #[must_use]
    pub const fn default_dt_sim_seconds(self) -> u64 {
        match self {
            TickDomain::Agent => 1,
            TickDomain::Weather => 300,
            TickDomain::Ecology => 86_400,
            TickDomain::Tectonics => 31_557_600_000, // ~1000 years @ 365.25 d
        }
    }

    /// All domains in coupling order (fast → slow).
    pub const ALL: [TickDomain; 4] = [
        TickDomain::Agent,
        TickDomain::Weather,
        TickDomain::Ecology,
        TickDomain::Tectonics,
    ];
}

/// Per-domain monotonic tick counter (domain-local step index).
#[derive(Copy, Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct DomainTick(pub u64);

impl DomainTick {
    /// Zero.
    pub const ZERO: DomainTick = DomainTick(0);

    /// Next step.
    #[must_use]
    pub const fn next(self) -> DomainTick {
        DomainTick(self.0.wrapping_add(1))
    }
}

/// Map a domain-local tick to a master [`Tick`] for cache keys / lineage.
#[must_use]
pub fn domain_tick_to_master(domain: TickDomain, domain_tick: DomainTick, dt: u64) -> Tick {
    Tick(domain_tick.0.saturating_mul(dt.max(1)))
}
