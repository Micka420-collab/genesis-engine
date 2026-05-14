//! Corps physique d'un agent — position, vitesse, paramètres métaboliques.

use bevy_ecs::prelude::Component;
use glam::Vec3;
use serde::{Deserialize, Serialize};

/// Position monde (mètres). Float32 suffisant Phase 1 (mondes < 1 000 km).
/// Phase 3+ : on passera à i64 fixed-point pour les mondes planétaires.
#[derive(Component, Copy, Clone, Debug, Serialize, Deserialize)]
pub struct Position(pub Vec3);

/// Vitesse linéaire (m/s).
#[derive(Component, Copy, Clone, Debug, Serialize, Deserialize)]
pub struct Velocity(pub Vec3);

/// Cap (yaw) en radians, 0 = +X.
#[derive(Component, Copy, Clone, Debug, Serialize, Deserialize)]
pub struct Heading(pub f32);

/// Profil métabolique de l'agent.
#[derive(Component, Clone, Debug, Serialize, Deserialize)]
pub struct Metabolism {
    /// Masse corporelle (kg).
    pub mass_kg: f32,
    /// Coût énergétique de base (kcal/jour).
    pub bmr_kcal_day: f32,
    /// Efficience de digestion (0..1).
    pub digestion_eff: f32,
    /// Vitesse de marche max (m/s).
    pub walk_max_ms: f32,
    /// Vitesse de course max (m/s).
    pub run_max_ms: f32,
    /// Espérance de vie max (jours).
    pub lifespan_days_max: u32,
}

impl Metabolism {
    /// Profil humain adulte standard (~70 kg).
    pub fn human_adult() -> Self {
        Self {
            mass_kg: 70.0,
            bmr_kcal_day: 1_650.0,
            digestion_eff: 0.85,
            walk_max_ms: 1.4,
            run_max_ms: 6.5,
            lifespan_days_max: 80 * 365,
        }
    }
}
