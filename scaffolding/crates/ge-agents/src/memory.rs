//! Mémoire d'agent — court terme (épisodes récents) + long terme (relations).
//!
//! Phase 3 : structures de données simples et bornées. Pas de base externe.
//!
//! - Court terme : ring buffer borné `MAX_EPISODES = 32` qui retient les
//!   N derniers événements saillants vécus par l'agent (action exécutée,
//!   cible perçue, agent croisé). La cognition peut interroger la mémoire
//!   pour préférer une eau déjà vue à un déplacement aveugle.
//!
//! - Long terme : `Relationships` — pour chaque autre agent croisé, on garde
//!   un compteur d'interactions et un affect ([-1.0, 1.0]). Le poids du lien
//!   décroît avec le temps. Phase 4 ajoutera un graph social complet.
//!
//! Les structures sont sérialisables — la sim peut snapshotter la mémoire
//! complète d'un agent.

use bevy_ecs::prelude::Component;
use ge_core::AgentId;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Nombre max d'épisodes retenus en mémoire courte.
pub const MAX_EPISODES: usize = 32;
/// Nombre max de relations long-terme conservées (les plus anciennes sont oubliées).
pub const MAX_RELATIONS: usize = 64;

/// Type d'épisode mémorisé.
#[derive(Copy, Clone, Eq, PartialEq, Debug, Serialize, Deserialize)]
pub enum EpisodeKind {
    /// L'agent a perçu une ressource (eau, nourriture, abri).
    SawResource,
    /// L'agent a exécuté une action.
    DidAction,
    /// L'agent a croisé un autre agent (proximité).
    MetAgent,
    /// L'agent a vécu une privation aiguë (drive >= seuil critique).
    Suffered,
    /// L'agent a réussi à se reproduire.
    Mated,
}

/// Un épisode atomique.
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub struct Episode {
    /// Tick auquel l'épisode est survenu.
    pub tick: u64,
    /// Type.
    pub kind: EpisodeKind,
    /// Position monde (m) — ou (0,0,0) si non-spatial.
    pub pos: [f32; 3],
    /// Référence éventuelle à un autre agent.
    pub other: Option<AgentId>,
    /// Affect ressenti (-1 = très négatif, 0 = neutre, +1 = très positif).
    pub affect: f32,
}

/// Mémoire épisodique courte (ring buffer).
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct EpisodicMemory {
    /// Capacité fixe `MAX_EPISODES`. Slots vides en fin.
    pub episodes: Vec<Episode>,
}

impl EpisodicMemory {
    /// Nouvelle mémoire vide.
    pub fn new() -> Self {
        Self { episodes: Vec::with_capacity(MAX_EPISODES) }
    }

    /// Enregistre un épisode. Si pleine, écrase le plus ancien.
    pub fn record(&mut self, ep: Episode) {
        if self.episodes.len() < MAX_EPISODES {
            self.episodes.push(ep);
        } else {
            // Ring : on retire le premier et on append.
            self.episodes.remove(0);
            self.episodes.push(ep);
        }
    }

    /// Cherche le dernier épisode d'un type donné.
    pub fn last_of(&self, kind: EpisodeKind) -> Option<&Episode> {
        self.episodes.iter().rev().find(|e| e.kind == kind)
    }
}

/// État relationnel envers un autre agent.
#[derive(Copy, Clone, Debug, Default, Serialize, Deserialize)]
pub struct Bond {
    /// Nombre d'interactions cumulées.
    pub interactions: u32,
    /// Affect courant (-1..1).
    pub affect: f32,
    /// Dernier tick de mise à jour.
    pub last_seen_tick: u64,
}

/// Mémoire relationnelle long-terme.
#[derive(Component, Clone, Debug, Default, Serialize, Deserialize)]
pub struct Relationships {
    /// Carte AgentId → Bond.
    pub bonds: HashMap<AgentId, Bond>,
}

impl Relationships {
    /// Constructeur.
    pub fn new() -> Self {
        Self::default()
    }

    /// Enregistre / met à jour un bond.
    pub fn observe(&mut self, other: AgentId, tick: u64, affect_delta: f32) {
        let b = self.bonds.entry(other).or_default();
        b.interactions = b.interactions.saturating_add(1);
        b.affect = (b.affect + affect_delta).clamp(-1.0, 1.0);
        b.last_seen_tick = tick;

        // Cap : si plus de MAX_RELATIONS, on oublie la relation la plus
        // ancienne (least-recently-seen). Bornage déterministe par AgentId.
        if self.bonds.len() > MAX_RELATIONS {
            let oldest = self
                .bonds
                .iter()
                .min_by(|(id_a, a), (id_b, b)| {
                    a.last_seen_tick
                        .cmp(&b.last_seen_tick)
                        .then_with(|| id_a.cmp(id_b))
                })
                .map(|(id, _)| *id);
            if let Some(id) = oldest {
                self.bonds.remove(&id);
            }
        }
    }

    /// Affect global envers `other` (0 si inconnu).
    pub fn affect_toward(&self, other: AgentId) -> f32 {
        self.bonds.get(&other).map(|b| b.affect).unwrap_or(0.0)
    }
}

/// Composant ECS regroupant les deux types de mémoire — un seul Component pour
/// simplifier la composition Bevy.
#[derive(Component, Clone, Debug, Default, Serialize, Deserialize)]
pub struct Memory {
    /// Mémoire épisodique court terme.
    pub episodic: EpisodicMemory,
    /// Mémoire relationnelle long terme.
    pub relationships: Relationships,
}

impl Memory {
    /// Constructeur vide.
    pub fn fresh() -> Self {
        Self {
            episodic: EpisodicMemory::new(),
            relationships: Relationships::new(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    fn aid(n: u128) -> AgentId {
        AgentId::from_uuid(Uuid::from_u128(n))
    }

    #[test]
    fn ring_buffer_caps_at_max() {
        let mut m = EpisodicMemory::new();
        for t in 0..(MAX_EPISODES as u64 * 2) {
            m.record(Episode {
                tick: t, kind: EpisodeKind::DidAction,
                pos: [0.0, 0.0, 0.0], other: None, affect: 0.0,
            });
        }
        assert_eq!(m.episodes.len(), MAX_EPISODES);
        // Le plus ancien restant doit être le tick MAX_EPISODES (le buffer
        // a viré les MAX_EPISODES premiers).
        assert_eq!(m.episodes.first().unwrap().tick, MAX_EPISODES as u64);
    }

    #[test]
    fn relationships_track_and_clamp() {
        let mut r = Relationships::new();
        let a = aid(1);
        r.observe(a, 10, 0.5);
        r.observe(a, 20, 0.6);
        let bond = r.bonds.get(&a).unwrap();
        assert_eq!(bond.interactions, 2);
        // 0.5 + 0.6 = 1.1 → clampé à 1.0
        assert!((bond.affect - 1.0).abs() < 1e-6);
        assert_eq!(bond.last_seen_tick, 20);
    }

    #[test]
    fn relationships_forget_oldest_when_capped() {
        let mut r = Relationships::new();
        for i in 0..(MAX_RELATIONS as u128 + 5) {
            r.observe(aid(i + 1), i as u64, 0.1);
        }
        assert_eq!(r.bonds.len(), MAX_RELATIONS);
        // Les 5 plus anciens (id 1..=5) doivent avoir été oubliés.
        for i in 1..=5_u128 {
            assert!(!r.bonds.contains_key(&aid(i)));
        }
    }

    #[test]
    fn last_of_finds_last_matching() {
        let mut m = EpisodicMemory::new();
        m.record(Episode { tick: 1, kind: EpisodeKind::SawResource, pos: [1.0,0.0,0.0], other: None, affect: 0.5 });
        m.record(Episode { tick: 2, kind: EpisodeKind::DidAction,   pos: [0.0,0.0,0.0], other: None, affect: 0.0 });
        m.record(Episode { tick: 3, kind: EpisodeKind::SawResource, pos: [5.0,0.0,0.0], other: None, affect: 0.7 });
        let last = m.last_of(EpisodeKind::SawResource).unwrap();
        assert_eq!(last.tick, 3);
    }
}
