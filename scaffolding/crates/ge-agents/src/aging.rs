//! Vieillissement — composant `Aging` + helpers de calcul d'âge.
//!
//! Phase 3 ajoute une cause de mort `OldAge` aux côtés des morts par drives.
//! L'âge est purement dérivé du tick courant et du `Identity::born_tick` — pas
//! de composant état mutable nécessaire à part le marqueur `Aging` qui porte
//! la durée de vie attendue (avec une légère variance déterministe pour éviter
//! que toute une cohorte ne meure exactement au même tick).
//!
//! Calibration Phase 3 (échelle pédagogique, **pas** biologique réaliste) :
//! - `LIFESPAN_BASE_TICKS = 60_000` ticks ≈ ~100 minutes wall-clock à 10 Hz.
//! - Variance déterministe ± `LIFESPAN_JITTER_TICKS = 6_000` (10 %) tirée du PRF.
//!
//! Le seuil exact d'un agent donné se calcule via `Aging::lifespan_ticks` et
//! sert au système `detect_old_age` dans la sim loop.

use crate::personality::Personality;
use bevy_ecs::prelude::Component;
use ge_core::{prf_rng, AgentId, WorldSeed};
use rand::Rng;
use serde::{Deserialize, Serialize};

/// Espérance de vie de base, en ticks.
pub const LIFESPAN_BASE_TICKS: u64 = 60_000;
/// Variance ±LIFESPAN_JITTER_TICKS (tirée du PRF) appliquée par agent.
pub const LIFESPAN_JITTER_TICKS: u64 = 6_000;
/// Bonus de longévité accordé pour 1.0 de conscientiousness (en ticks).
pub const CONSCIENTIOUS_BONUS_TICKS: u64 = 8_000;

/// Composant porteur de l'espérance de vie individuelle.
///
/// Calculé une fois à la naissance puis stable. La cause de mort `OldAge` se
/// déclenche dès que `current_tick - born_tick >= lifespan_ticks`.
#[derive(Component, Copy, Clone, Debug, Serialize, Deserialize)]
pub struct Aging {
    /// Durée de vie attendue de l'agent (ticks).
    pub lifespan_ticks: u64,
}

impl Aging {
    /// Échantillonne une durée de vie déterministe pour un agent donné.
    ///
    /// La consciencieusité agit comme un facteur de longévité — modélise
    /// (très grossièrement) qu'un agent prudent vit plus longtemps. Pas de
    /// magie : tout est dérivé du PRF du monde.
    pub fn sampled(seed: WorldSeed, agent: AgentId, personality: &Personality) -> Self {
        let id_bytes = agent.0.as_bytes();
        let high = u64::from_le_bytes([
            id_bytes[0], id_bytes[1], id_bytes[2], id_bytes[3],
            id_bytes[4], id_bytes[5], id_bytes[6], id_bytes[7],
        ]);
        let low = u64::from_le_bytes([
            id_bytes[8], id_bytes[9], id_bytes[10], id_bytes[11],
            id_bytes[12], id_bytes[13], id_bytes[14], id_bytes[15],
        ]);
        let mut rng = prf_rng(seed, &["agent", "aging"], &[high, low]);
        // Jitter ∈ [-LIFESPAN_JITTER_TICKS, +LIFESPAN_JITTER_TICKS].
        let r: f32 = rng.gen::<f32>() * 2.0 - 1.0;
        let jitter = (r * LIFESPAN_JITTER_TICKS as f32) as i64;
        let conscientious_bonus =
            (personality.conscientiousness.clamp(0.0, 1.0) * CONSCIENTIOUS_BONUS_TICKS as f32) as i64;
        let raw = LIFESPAN_BASE_TICKS as i64 + jitter + conscientious_bonus;
        Self {
            lifespan_ticks: raw.max(LIFESPAN_BASE_TICKS as i64 / 4) as u64,
        }
    }

    /// L'agent a-t-il dépassé son espérance de vie ?
    #[inline]
    pub fn died_of_age(&self, now: u64, born_tick: u64) -> bool {
        now.saturating_sub(born_tick) >= self.lifespan_ticks
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::personality::Personality;

    fn pers(c: f32) -> Personality {
        Personality {
            openness: 0.5, conscientiousness: c, extraversion: 0.5,
            agreeableness: 0.5, neuroticism: 0.5, ambition: 0.5,
            risk_tolerance: 0.5, aggression: 0.5,
        }
    }

    #[test]
    fn determinism() {
        let s: WorldSeed = 0xC0FFEE;
        let id = AgentId::derive(s, &["test"], &[1]);
        let p = pers(0.5);
        let a = Aging::sampled(s, id, &p);
        let b = Aging::sampled(s, id, &p);
        assert_eq!(a.lifespan_ticks, b.lifespan_ticks);
    }

    #[test]
    fn conscientious_lives_longer_on_average() {
        // Pour 50 agents tirés avec consc=0.0 vs consc=1.0, la moyenne des
        // durées de vie doit être strictement plus grande pour consc=1.
        let s: WorldSeed = 0xBABE;
        let (mut sum_lo, mut sum_hi) = (0u128, 0u128);
        for i in 0..50_u64 {
            let id = AgentId::derive(s, &["test"], &[i]);
            sum_lo += Aging::sampled(s, id, &pers(0.0)).lifespan_ticks as u128;
            sum_hi += Aging::sampled(s, id, &pers(1.0)).lifespan_ticks as u128;
        }
        assert!(sum_hi > sum_lo, "consc=1 cohort should outlive consc=0 cohort");
    }

    #[test]
    fn never_below_minimum_floor() {
        let s: WorldSeed = 0xDEAD;
        for i in 0..200_u64 {
            let id = AgentId::derive(s, &["test"], &[i]);
            let a = Aging::sampled(s, id, &pers(0.5));
            assert!(a.lifespan_ticks >= LIFESPAN_BASE_TICKS / 4);
        }
    }
}
