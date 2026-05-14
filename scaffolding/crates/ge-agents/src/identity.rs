//! Identité et lignée d'un agent.

use bevy_ecs::prelude::Component;
use ge_core::AgentId;
use serde::{Deserialize, Serialize};

/// Composant d'identité.
#[derive(Component, Clone, Debug, Serialize, Deserialize)]
pub struct Identity {
    /// ID stable de l'agent.
    pub id: AgentId,
    /// Tick de naissance.
    pub born_tick: u64,
    /// Génération depuis les fondateurs (0 = fondateur).
    pub generation: u32,
    /// Parents (jusqu'à 2 — reproduction sexuée Phase 2).
    pub parents: [Option<AgentId>; 2],
}

/// Composant marqueur — l'agent est mort (kept around 1 tick for death event).
#[derive(Component, Copy, Clone, Debug)]
pub struct Deceased {
    /// Tick de décès.
    pub died_tick: u64,
    /// Cause.
    pub cause: DeathCause,
}

/// Causes de mort. Étendu en Phase 2 (violence, vieillesse, maladie).
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub enum DeathCause {
    /// Faim.
    Starvation,
    /// Soif.
    Dehydration,
    /// Hypothermie.
    Cold,
    /// Hyperthermie.
    Heat,
    /// Épuisement (drives multiples).
    Exhaustion,
    /// Vieillesse (Phase 2).
    OldAge,
    /// Violence (Phase 3).
    Violence,
    /// Maladie (Phase 3).
    Disease,
    /// Catastrophe.
    Catastrophe,
}
