//! Minimal multi-rate coupler — advances domains on LCM boundaries.
//!
//! When the master tick advances by `master_dt`, each registered domain
//! whose accumulated sim-time crosses its `dt` fires once (or more if
//! `master_dt` exceeds several domain steps).

use crate::tick::Tick;
use crate::tick_domain::{DomainTick, TickDomain};
use serde::{Deserialize, Serialize};
use smallvec::SmallVec;

/// Configuration for one coupled domain.
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub struct DomainConfig {
    /// Which domain.
    pub domain: TickDomain,
    /// Sim-seconds per domain step.
    pub dt_sim_seconds: u64,
}

impl DomainConfig {
    /// Built-in default `dt` for `domain`.
    #[must_use]
    pub fn with_defaults(domain: TickDomain) -> Self {
        Self {
            domain,
            dt_sim_seconds: domain.default_dt_sim_seconds(),
        }
    }
}

/// Tracks per-domain clocks and reports which domains fire on `advance`.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MultiRateCoupler {
    master_tick: Tick,
    master_dt: u64,
    domains: SmallVec<[DomainState; 4]>,
}

#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
struct DomainState {
    domain: TickDomain,
    dt: u64,
    domain_tick: DomainTick,
    /// Accumulated sim-seconds since last domain step (for sub-stepping).
    remainder_s: u64,
}

/// Result of one `advance` call.
#[derive(Clone, Debug, Default)]
pub struct CouplerStep {
    /// New master tick after this advance.
    pub master_tick: Tick,
    /// Domains that should run their passes this step.
    pub fired: SmallVec<[TickDomain; 4]>,
}

impl MultiRateCoupler {
    /// New coupler with default four domains and `master_dt = 1` sim-second.
    #[must_use]
    pub fn new_default() -> Self {
        Self::new(
            1,
            [
                DomainConfig::with_defaults(TickDomain::Agent),
                DomainConfig::with_defaults(TickDomain::Weather),
                DomainConfig::with_defaults(TickDomain::Ecology),
                DomainConfig::with_defaults(TickDomain::Tectonics),
            ],
        )
    }

    /// Build a coupler from explicit domain configs.
    #[must_use]
    pub fn new(master_dt: u64, configs: impl IntoIterator<Item = DomainConfig>) -> Self {
        let domains = configs
            .into_iter()
            .map(|c| DomainState {
                domain: c.domain,
                dt: c.dt_sim_seconds.max(1),
                domain_tick: DomainTick::ZERO,
                remainder_s: 0,
            })
            .collect();
        Self {
            master_tick: Tick::ZERO,
            master_dt: master_dt.max(1),
            domains,
        }
    }

    /// Current master tick.
    #[must_use]
    pub fn master_tick(&self) -> Tick {
        self.master_tick
    }

    /// Domain-local tick for a domain (0 if unknown).
    #[must_use]
    pub fn domain_tick(&self, domain: TickDomain) -> DomainTick {
        self.domains
            .iter()
            .find(|d| d.domain == domain)
            .map(|d| d.domain_tick)
            .unwrap_or(DomainTick::ZERO)
    }

    /// Advance master clock by `master_dt` sim-seconds; returns fired domains.
    pub fn advance(&mut self) -> CouplerStep {
        self.master_tick = self.master_tick + self.master_dt;
        let mut fired = SmallVec::new();
        for state in &mut self.domains {
            state.remainder_s = state.remainder_s.saturating_add(self.master_dt);
            while state.remainder_s >= state.dt {
                state.remainder_s -= state.dt;
                state.domain_tick = state.domain_tick.next();
                fired.push(state.domain);
            }
        }
        CouplerStep {
            master_tick: self.master_tick,
            fired,
        }
    }

    /// Map domain tick to master tick for cache keys (used by WorldGraph).
    #[must_use]
    pub fn tick_for_pass_ctx(&self, domain: TickDomain) -> Tick {
        let state = self
            .domains
            .iter()
            .find(|d| d.domain == domain)
            .expect("domain not registered");
        Tick(state.domain_tick.0.saturating_mul(state.dt))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn agent_fires_every_master_step() {
        let mut c = MultiRateCoupler::new(
            1,
            [DomainConfig::with_defaults(TickDomain::Agent)],
        );
        let s = c.advance();
        assert_eq!(s.master_tick, Tick(1));
        assert!(s.fired.contains(&TickDomain::Agent));
    }

    #[test]
    fn weather_fires_every_300s() {
        let mut c = MultiRateCoupler::new(
            1,
            [
                DomainConfig::with_defaults(TickDomain::Agent),
                DomainConfig::with_defaults(TickDomain::Weather),
            ],
        );
        let mut weather_count = 0u32;
        for _ in 0..300 {
            let s = c.advance();
            if s.fired.contains(&TickDomain::Weather) {
                weather_count += 1;
            }
        }
        assert_eq!(weather_count, 1);
        assert_eq!(c.domain_tick(TickDomain::Weather), DomainTick(1));
    }

    #[test]
    fn determinism_same_sequence() {
        let mut a = MultiRateCoupler::new_default();
        let mut b = MultiRateCoupler::new_default();
        for _ in 0..10_000 {
            assert_eq!(a.advance().fired.as_slice(), b.advance().fired.as_slice());
        }
        assert_eq!(a.master_tick(), b.master_tick());
    }
}
