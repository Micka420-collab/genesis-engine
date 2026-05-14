//! Schéma d'événement.

use ge_core::{AgentId, SimulationId, Tick};
use glam::Vec3;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Évènement détecté par l'Annaliste.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Event {
    /// ID unique (UUIDv7 pour ordre temporel).
    pub event_id: Uuid,
    /// Simulation source.
    pub sim_id: SimulationId,
    /// Tick auquel l'événement est survenu.
    pub tick: Tick,
    /// Type d'événement.
    pub kind: EventKind,
    /// Agents impliqués.
    pub participants: Vec<AgentId>,
    /// Lieu (centroid si multi-agent).
    pub location: Vec3,
    /// Payload spécifique.
    pub metadata: serde_json::Value,
}

/// Taxonomie d'événements.
#[derive(Copy, Clone, Eq, PartialEq, Debug, Serialize, Deserialize)]
pub enum EventKind {
    /// Naissance d'un agent.
    Birth,
    /// Décès d'un agent.
    Death,
    /// Première occurrence d'un comportement / techno (innovation).
    Innovation,
    /// Conflit organisé entre plusieurs agents.
    Conflict,
    /// Fondation d'un groupe / village.
    Founding,
    /// Catastrophe naturelle.
    Catastrophe,
    /// Échange économique.
    Trade,
    /// Vocalisation (proto-langage).
    Vocalization,
    /// Construction d'une structure.
    Build,
}
