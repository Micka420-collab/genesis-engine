//! Espace d'actions de l'agent.
//!
//! Phase 1 : 8 actions discrètes. Chacune est exécutée par un *system* dans la
//! sim plane. Le système valide la pré-condition (cible accessible, ressource
//! présente, etc.) et applique l'effet.

use glam::Vec3;
use serde::{Deserialize, Serialize};

/// Identifiant numérique d'une action (utilisé sur la wire).
#[derive(Copy, Clone, Eq, PartialEq, Debug, Serialize, Deserialize)]
#[repr(u32)]
pub enum ActionId {
    /// Ne fait rien (idle).
    Idle = 0,
    /// Marche vers la cible.
    WalkTo = 1,
    /// Boit à la source d'eau la plus proche.
    Drink = 2,
    /// Mange la nourriture en inventaire (ou cueille si à proximité).
    Eat = 3,
    /// Dort sur place.
    Sleep = 4,
    /// Récolte une ressource (bois, pierre, baies).
    Forage = 5,
    /// Cherche un abri (place avec faible exposition thermique).
    SeekShelter = 6,
    /// Se reproduit (Phase 2) — no-op Phase 1.
    Mate = 7,
}

impl ActionId {
    /// Nom court pour les logs / dashboards.
    pub fn name(self) -> &'static str {
        match self {
            Self::Idle => "idle",
            Self::WalkTo => "walk_to",
            Self::Drink => "drink",
            Self::Eat => "eat",
            Self::Sleep => "sleep",
            Self::Forage => "forage",
            Self::SeekShelter => "seek_shelter",
            Self::Mate => "mate",
        }
    }
}

/// Argument d'action — paramétrage typé.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum ActionArgs {
    /// Aucun paramètre.
    None,
    /// Cible de déplacement (position monde).
    Target(Vec3),
}

/// Décision finale produite par la cognition pour un agent à un tick donné.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Decision {
    /// Action choisie.
    pub action: ActionId,
    /// Arguments typés.
    pub args: ActionArgs,
    /// Confiance de la policy (0..1) — pour analytics / RL ultérieur.
    pub confidence: f32,
}

impl Decision {
    /// Décision « ne rien faire ».
    pub fn idle() -> Self {
        Self { action: ActionId::Idle, args: ActionArgs::None, confidence: 0.0 }
    }
}
