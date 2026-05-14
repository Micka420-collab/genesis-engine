//! Perception — extrait un Observation Vector lisible par la policy.
//!
//! Phase 1 : entrée structurée explicite (pas d'embedding ML).
//! Phase 2+ : DINOv3 sur frame voxel rendu localement.

use ge_agents::{Drives, DriveKind, Health};
use glam::Vec3;
use serde::{Deserialize, Serialize};

/// Cible repérée par perception (eau, nourriture, abri, agent).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PerceivedTarget {
    /// Type de cible.
    pub kind: TargetKind,
    /// Position monde.
    pub pos: Vec3,
    /// Distance euclidienne (mètres).
    pub distance_m: f32,
    /// Quantité estimée (kcal / L / autre).
    pub qty: f32,
}

/// Type d'élément perçu.
#[derive(Copy, Clone, Eq, PartialEq, Debug, Serialize, Deserialize)]
pub enum TargetKind {
    /// Source d'eau.
    Water,
    /// Source de nourriture (baie, gibier, etc.).
    Food,
    /// Abri (grotte, sous-bois dense, structure).
    Shelter,
    /// Autre agent.
    Agent,
}

/// Vecteur d'observation à passer à la policy (Phase 1 explicite).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Observation {
    /// Drives courants.
    pub drives: Drives,
    /// Santé.
    pub health: Health,
    /// Drive dominant (cache).
    pub dominant_drive: DriveKind,
    /// Cibles dans le champ de perception, triées par distance.
    pub nearby: Vec<PerceivedTarget>,
}

impl Observation {
    /// Récupère la cible la plus proche d'un type donné, si présente.
    pub fn nearest(&self, kind: TargetKind) -> Option<&PerceivedTarget> {
        self.nearby
            .iter()
            .filter(|t| t.kind == kind)
            .min_by(|a, b| a.distance_m.partial_cmp(&b.distance_m).unwrap_or(std::cmp::Ordering::Equal))
    }
}
