//! Santé et intégrité corporelle.

use bevy_ecs::prelude::Component;
use serde::{Deserialize, Serialize};

/// État de santé. 0..1 (1 = parfaite santé).
#[derive(Component, Copy, Clone, Debug, Serialize, Deserialize)]
pub struct Health {
    /// Vitalité globale.
    pub vitality: f32,
    /// Blessures non soignées (somme normalisée).
    pub injuries: f32,
    /// Charge pathogène (Phase 3).
    pub pathogen_load: f32,
}

impl Health {
    /// Santé pleine.
    pub fn full() -> Self {
        Self { vitality: 1.0, injuries: 0.0, pathogen_load: 0.0 }
    }

    /// L'agent doit mourir ?
    pub fn fatal(&self) -> bool {
        self.vitality <= 0.0 || self.injuries >= 1.0
    }
}
