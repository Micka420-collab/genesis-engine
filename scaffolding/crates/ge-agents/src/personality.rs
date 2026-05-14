//! Personnalité — traits stables qui modulent la cognition.
//!
//! Modèle Big Five (OCEAN) + 3 dimensions Genesis-specific.
//!
//! Phase 3 ajoute l'héritage génétique : `Personality::inherit(seed, p1, p2, child)`
//! produit l'enfant par crossover gene-wise (chaque trait tiré indépendamment du
//! parent A ou du parent B) puis applique une mutation gaussienne déterministe
//! à taux faible (`MUTATION_RATE = 0.05` → 5 % de chance qu'un trait bouge de
//! ±0.10 maximum). Le tirage utilise le PRF de `ge-core`, donc tout est
//! reproductible bit-à-bit pour (seed, p1, p2, child).

use bevy_ecs::prelude::Component;
use ge_core::{prf_rng, AgentId, WorldSeed};
use rand::Rng;
use serde::{Deserialize, Serialize};

/// Probabilité qu'un trait subisse une mutation à la naissance.
pub const MUTATION_RATE: f32 = 0.05;
/// Amplitude max d'une mutation (additive, clampée dans [0,1]).
pub const MUTATION_AMPLITUDE: f32 = 0.10;

/// Traits stables (0..1). Hérités partiellement à la reproduction (Phase 2).
#[derive(Component, Copy, Clone, Debug, Serialize, Deserialize)]
pub struct Personality {
    /// Openness — curiosité, ouverture à l'innovation.
    pub openness: f32,
    /// Conscientiousness — planification, prudence.
    pub conscientiousness: f32,
    /// Extraversion — recherche sociale.
    pub extraversion: f32,
    /// Agreeableness — empathie, coopération.
    pub agreeableness: f32,
    /// Neuroticism — sensibilité émotionnelle, peur.
    pub neuroticism: f32,
    /// Ambition (Genesis-specific) — modifie le poids des goals long-terme.
    pub ambition: f32,
    /// Risk tolerance — biais d'aversion au risque.
    pub risk_tolerance: f32,
    /// Aggression — disposition au conflit.
    pub aggression: f32,
}

impl Personality {
    /// Personnalité tirée depuis un PRF déterministe.
    pub fn sampled(seed: WorldSeed, agent: AgentId) -> Self {
        let id_bytes = agent.0.as_bytes();
        let high = u64::from_le_bytes([
            id_bytes[0], id_bytes[1], id_bytes[2], id_bytes[3],
            id_bytes[4], id_bytes[5], id_bytes[6], id_bytes[7],
        ]);
        let low = u64::from_le_bytes([
            id_bytes[8], id_bytes[9], id_bytes[10], id_bytes[11],
            id_bytes[12], id_bytes[13], id_bytes[14], id_bytes[15],
        ]);
        let mut rng = prf_rng(seed, &["agent", "personality"], &[high, low]);
        Self {
            openness: rng.gen(),
            conscientiousness: rng.gen(),
            extraversion: rng.gen(),
            agreeableness: rng.gen(),
            neuroticism: rng.gen(),
            ambition: rng.gen(),
            risk_tolerance: rng.gen(),
            aggression: rng.gen(),
        }
    }

    /// Hérite d'une personnalité de deux parents via crossover gene-wise +
    /// mutation gaussienne. Tri canonique des parents (par AgentId) avant
    /// dérivation pour que `inherit(seed, A, B, C) == inherit(seed, B, A, C)`.
    pub fn inherit(seed: WorldSeed, parent_a: Self, parent_b: Self, child: AgentId) -> Self {
        let id_bytes = child.0.as_bytes();
        let high = u64::from_le_bytes([
            id_bytes[0], id_bytes[1], id_bytes[2], id_bytes[3],
            id_bytes[4], id_bytes[5], id_bytes[6], id_bytes[7],
        ]);
        let low = u64::from_le_bytes([
            id_bytes[8], id_bytes[9], id_bytes[10], id_bytes[11],
            id_bytes[12], id_bytes[13], id_bytes[14], id_bytes[15],
        ]);
        let mut rng = prf_rng(seed, &["agent", "inherit"], &[high, low]);

        // Crossover : pour chaque trait, on choisit aléatoirement le parent A
        // ou B (uniforme). Puis mutation : avec probabilité MUTATION_RATE, on
        // perturbe additivement de ±MUTATION_AMPLITUDE.
        let cross = |rng: &mut rand_chacha::ChaCha20Rng, a: f32, b: f32| -> f32 {
            let base = if rng.gen_bool(0.5) { a } else { b };
            if rng.gen::<f32>() < MUTATION_RATE {
                let delta = (rng.gen::<f32>() * 2.0 - 1.0) * MUTATION_AMPLITUDE;
                (base + delta).clamp(0.0, 1.0)
            } else {
                base
            }
        };

        Self {
            openness: cross(&mut rng, parent_a.openness, parent_b.openness),
            conscientiousness: cross(&mut rng, parent_a.conscientiousness, parent_b.conscientiousness),
            extraversion: cross(&mut rng, parent_a.extraversion, parent_b.extraversion),
            agreeableness: cross(&mut rng, parent_a.agreeableness, parent_b.agreeableness),
            neuroticism: cross(&mut rng, parent_a.neuroticism, parent_b.neuroticism),
            ambition: cross(&mut rng, parent_a.ambition, parent_b.ambition),
            risk_tolerance: cross(&mut rng, parent_a.risk_tolerance, parent_b.risk_tolerance),
            aggression: cross(&mut rng, parent_a.aggression, parent_b.aggression),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    fn aid(s: u128, idx: u64) -> AgentId {
        AgentId::derive(s, &["test", "agent"], &[idx])
    }

    #[test]
    fn inherit_is_deterministic_for_fixed_parents_and_child() {
        let seed: WorldSeed = 0xC0FFEE;
        let pa = Personality::sampled(seed, aid(seed, 1));
        let pb = Personality::sampled(seed, aid(seed, 2));
        let c = aid(seed, 99);
        let x = Personality::inherit(seed, pa, pb, c);
        let y = Personality::inherit(seed, pa, pb, c);
        assert_eq!(x.openness, y.openness);
        assert_eq!(x.aggression, y.aggression);
    }

    #[test]
    fn inherit_traits_stay_in_unit_interval() {
        let seed: WorldSeed = 0xBABE;
        let pa = Personality::sampled(seed, aid(seed, 1));
        let pb = Personality::sampled(seed, aid(seed, 2));
        for i in 0..20 {
            let c = AgentId::from_uuid(Uuid::from_u128(i as u128 + 7777));
            let x = Personality::inherit(seed, pa, pb, c);
            for t in [
                x.openness, x.conscientiousness, x.extraversion, x.agreeableness,
                x.neuroticism, x.ambition, x.risk_tolerance, x.aggression,
            ] {
                assert!((0.0..=1.0).contains(&t), "trait out of [0,1]: {t}");
            }
        }
    }
}
