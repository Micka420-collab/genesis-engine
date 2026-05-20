//! Discrete Lotka-Volterra food web (3 levels: producers / herbivores /
//! carnivores) per chunk. Sits on top of the existing `FaunaSeed` /
//! `FloraInstance` so it can update population *counts* without simulating
//! every individual. For flagship species the boid system carries the
//! visible representation; LV manages the bulk population dynamics.
//!
//! Determinism: all state lives in this struct; updates are pure functions
//! of the previous state + the world `(temperature, humidity, npp)` inputs.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Per-chunk population state.
#[derive(Copy, Clone, Debug, Default)]
pub struct Populations {
    /// Plant biomass (arbitrary units, kg of dry mass scaled).
    pub plant: f32,
    /// Herbivore population (count).
    pub herb: f32,
    /// Carnivore population (count).
    pub carn: f32,
}

/// LV parameters per biome class.
#[derive(Copy, Clone, Debug)]
pub struct LvParams {
    /// Plant intrinsic growth rate (per tick, before grazing).
    pub plant_growth: f32,
    /// Plant carrying capacity.
    pub plant_k: f32,
    /// Grazing rate constant (per herbivore per plant unit).
    pub grazing: f32,
    /// Herbivore reproductive efficiency from plants (0..1).
    pub herb_eff: f32,
    /// Herbivore natural mortality.
    pub herb_mort: f32,
    /// Predation rate constant.
    pub predation: f32,
    /// Carnivore reproductive efficiency from herbivores.
    pub carn_eff: f32,
    /// Carnivore natural mortality.
    pub carn_mort: f32,
}

impl Default for LvParams {
    fn default() -> Self {
        Self {
            plant_growth: 0.04,
            plant_k: 1_000.0,
            grazing: 0.0008,
            herb_eff: 0.35,
            herb_mort: 0.02,
            predation: 0.0009,
            carn_eff: 0.20,
            carn_mort: 0.015,
        }
    }
}

/// Climate factors that modulate growth/mortality.
#[derive(Copy, Clone, Debug)]
pub struct ClimateModifier {
    /// 0..1 — how productive the biome is (NPP-derived).
    pub npp_factor: f32,
    /// Temperature stress in `[0, 1]`. 0 = comfortable, 1 = lethal.
    pub thermal_stress: f32,
    /// Drought factor in `[0, 1]`. 0 = saturated, 1 = arid.
    pub drought: f32,
}

impl Default for ClimateModifier {
    fn default() -> Self {
        Self {
            npp_factor: 1.0,
            thermal_stress: 0.0,
            drought: 0.0,
        }
    }
}

/// One LV time step.
#[must_use]
pub fn step(pop: Populations, p: LvParams, m: ClimateModifier, dt: f32) -> Populations {
    let n = pop.plant.max(0.0);
    let h = pop.herb.max(0.0);
    let c = pop.carn.max(0.0);

    // Plant growth modulated by climate.
    let growth = p.plant_growth * m.npp_factor * (1.0 - m.drought.min(1.0));
    // Logistic growth.
    let dn = n * growth * (1.0 - n / p.plant_k.max(1.0)) - p.grazing * n * h;

    // Herbivores: gain from grazing - natural mortality - predation - thermal.
    let dh = p.herb_eff * p.grazing * n * h
        - p.herb_mort * h * (1.0 + m.thermal_stress)
        - p.predation * h * c;

    // Carnivores: gain from predation - natural mortality - thermal.
    let dc = p.carn_eff * p.predation * h * c - p.carn_mort * c * (1.0 + m.thermal_stress * 0.5);

    Populations {
        plant: (n + dn * dt).max(0.0),
        herb: (h + dh * dt).max(0.0),
        carn: (c + dc * dt).max(0.0),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deterministic_step() {
        let p = LvParams::default();
        let m = ClimateModifier::default();
        let s = Populations { plant: 500.0, herb: 30.0, carn: 5.0 };
        let a = step(s, p, m, 1.0);
        let b = step(s, p, m, 1.0);
        assert_eq!(a.plant.to_bits(), b.plant.to_bits());
        assert_eq!(a.herb.to_bits(), b.herb.to_bits());
        assert_eq!(a.carn.to_bits(), b.carn.to_bits());
    }

    #[test]
    fn lv_predator_decline_without_prey() {
        let p = LvParams::default();
        let m = ClimateModifier::default();
        let mut s = Populations { plant: 0.0, herb: 0.0, carn: 50.0 };
        for _ in 0..200 {
            s = step(s, p, m, 1.0);
        }
        assert!(s.carn < 1.0, "carnivores should die out without prey: {}", s.carn);
    }

    #[test]
    fn herbivores_grow_with_plants_present() {
        let p = LvParams::default();
        let m = ClimateModifier::default();
        let mut s = Populations { plant: 500.0, herb: 2.0, carn: 0.0 };
        let s0 = s;
        for _ in 0..100 {
            s = step(s, p, m, 1.0);
        }
        assert!(
            s.herb > s0.herb,
            "herbivores should grow with abundant plants: {} → {}",
            s0.herb,
            s.herb
        );
    }

    #[test]
    fn thermal_stress_kills() {
        let p = LvParams::default();
        let normal = step(
            Populations { plant: 100.0, herb: 30.0, carn: 5.0 },
            p,
            ClimateModifier::default(),
            1.0,
        );
        let hot = step(
            Populations { plant: 100.0, herb: 30.0, carn: 5.0 },
            p,
            ClimateModifier { thermal_stress: 0.5, ..Default::default() },
            1.0,
        );
        assert!(hot.herb < normal.herb);
    }
}
