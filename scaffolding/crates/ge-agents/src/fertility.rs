//! Fertilité — gouverne la reproduction (Phase 2).
//!
//! Deux contraintes Phase 2 :
//!
//! 1. **Maturité** : un agent doit avoir vécu au moins `MATURITY_TICKS`
//!    depuis sa naissance avant de pouvoir se reproduire.
//! 2. **Cooldown** : après un accouplement réussi, un agent est sur cooldown
//!    pour `COOLDOWN_TICKS` ticks (modélise la gestation + tabou social).
//!
//! Pas de notion de sexe biologique en Phase 2 — l'inter-fécondabilité est
//! universelle. Phase 3 introduira `Sex` (M/F/hermaphrodite) et les
//! contraintes XY/ZW correspondantes.
//!
//! Tous les paramètres sont **constantes** Phase 2 — pas de tirage aléatoire,
//! ce qui préserve le déterminisme bit-à-bit. Phase 3 introduira de la
//! variation génétique sur ces seuils.

use bevy_ecs::prelude::Component;
use serde::{Deserialize, Serialize};

/// Nombre de ticks à attendre depuis la naissance pour être fertile.
/// À 10 Hz, 10 ans simulés = ~315 M ticks. Phase 2 utilise un raccourci
/// pédagogique : 1000 ticks = ~100 secondes wall-clock = adulte.
pub const MATURITY_TICKS: u64 = 1_000;

/// Cooldown entre deux accouplements pour un même agent.
/// 9 mois simulés ≈ 6912 ticks à l'accéléré de référence. On garde un nombre
/// rond et observable : 5000 ticks.
pub const COOLDOWN_TICKS: u64 = 5_000;

/// Distance maximale (m) entre deux agents pour qu'ils puissent s'accoupler.
pub const MATING_RADIUS_M: f32 = 2.0;

/// Seuil au-dessous duquel un drive bloque la reproduction.
/// Si hunger / thirst / sleep / fatigue / thermal > 0.7, on ne mate pas.
pub const DRIVE_BLOCK_THRESHOLD: f32 = 0.7;

/// État de fertilité d'un agent.
#[derive(Component, Copy, Clone, Debug, Serialize, Deserialize)]
pub struct Fertility {
    /// Tick du dernier accouplement réussi (None tant qu'aucun).
    pub last_mating_tick: Option<u64>,
    /// Compteur d'enfants engendrés.
    pub offspring_count: u32,
}

impl Fertility {
    /// État initial — jamais mating réussi.
    pub const fn fresh() -> Self {
        Self { last_mating_tick: None, offspring_count: 0 }
    }

    /// L'agent est-il actuellement fertile au tick `now`, étant donné sa
    /// naissance au tick `born` ?
    #[inline]
    pub fn is_fertile_at(&self, now: u64, born_tick: u64) -> bool {
        // Maturité.
        if now.saturating_sub(born_tick) < MATURITY_TICKS {
            return false;
        }
        // Cooldown.
        match self.last_mating_tick {
            Some(t) if now.saturating_sub(t) < COOLDOWN_TICKS => false,
            _ => true,
        }
    }

    /// Met à jour l'état après un accouplement.
    #[inline]
    pub fn record_mating(&mut self, now: u64) {
        self.last_mating_tick = Some(now);
        self.offspring_count = self.offspring_count.saturating_add(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn newborn_is_not_fertile() {
        let f = Fertility::fresh();
        assert!(!f.is_fertile_at(500, 0));
    }

    #[test]
    fn mature_with_no_history_is_fertile() {
        let f = Fertility::fresh();
        assert!(f.is_fertile_at(MATURITY_TICKS + 1, 0));
    }

    #[test]
    fn cooldown_blocks_fertility() {
        let mut f = Fertility::fresh();
        f.record_mating(MATURITY_TICKS + 10);
        assert!(!f.is_fertile_at(MATURITY_TICKS + 100, 0));
        assert!(f.is_fertile_at(MATURITY_TICKS + 10 + COOLDOWN_TICKS + 1, 0));
    }

    #[test]
    fn offspring_count_increments() {
        let mut f = Fertility::fresh();
        assert_eq!(f.offspring_count, 0);
        f.record_mating(MATURITY_TICKS + 10);
        f.record_mating(MATURITY_TICKS + 10 + COOLDOWN_TICKS + 1);
        assert_eq!(f.offspring_count, 2);
    }
}
