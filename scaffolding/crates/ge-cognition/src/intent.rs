//! Intent — but courant maintenu d'un tick à l'autre.
//!
//! Permet à l'agent de poursuivre une action longue (marcher vers une source)
//! sans replanifier intégralement à chaque tick.

use crate::action::{ActionArgs, ActionId};
use bevy_ecs::prelude::Component;
use serde::{Deserialize, Serialize};

/// Composant ECS — intent en cours.
#[derive(Component, Clone, Debug, Serialize, Deserialize)]
pub struct Intent {
    /// Action engagée.
    pub action: ActionId,
    /// Args.
    pub args: ActionArgs,
    /// Tick de départ.
    pub started_tick: u64,
    /// Tick d'échéance (replan si dépassé).
    pub expires_tick: u64,
}

impl Intent {
    /// Construit un intent simple.
    pub fn new(action: ActionId, args: ActionArgs, started: u64, expires: u64) -> Self {
        Self { action, args, started_tick: started, expires_tick: expires }
    }
}
