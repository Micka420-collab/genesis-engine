//! Drives biologiques — moteur de décision Phase 1.
//!
//! Tous les drives sont dans [0, 1]. 0 = comblé, 1 = critique (mort si > 1).

use bevy_ecs::prelude::Component;
use serde::{Deserialize, Serialize};

/// Drive value, clampé en [0, 1].
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub struct Drive(pub f32);

impl Drive {
    /// Constante : drive parfaitement comblé.
    pub const SATISFIED: Drive = Drive(0.0);
    /// Constante : drive critique.
    pub const CRITICAL: Drive = Drive(1.0);

    /// Clamp et retourne.
    #[inline]
    pub fn add(self, delta: f32) -> Drive {
        Drive((self.0 + delta).clamp(0.0, 1.5))
    }

    /// Niveau critique ?
    #[inline]
    pub fn is_critical(self) -> bool {
        self.0 >= 1.0
    }
}

/// Drives de l'agent. 8 axes (vecteur compatible Plutchik étendu).
#[derive(Component, Copy, Clone, Debug, Serialize, Deserialize)]
pub struct Drives {
    /// Faim. Augmente avec la dépense énergétique.
    pub hunger: Drive,
    /// Soif. Augmente avec température et activité.
    pub thirst: Drive,
    /// Sommeil. Augmente avec l'éveil.
    pub sleep: Drive,
    /// Énergie inversée (= fatigue). Phase 1 = corrélée à hunger+sleep.
    pub fatigue: Drive,
    /// Inconfort thermique.
    pub thermal: Drive,
    /// Douleur (Phase 2+).
    pub pain: Drive,
    /// Stress (Phase 2+).
    pub stress: Drive,
    /// Solitude (Phase 2+).
    pub loneliness: Drive,
}

impl Drives {
    /// Drives d'un agent nouvellement né — légèrement affamé/assoifé.
    pub fn newborn() -> Self {
        Self {
            hunger: Drive(0.3),
            thirst: Drive(0.3),
            sleep: Drive(0.1),
            fatigue: Drive(0.1),
            thermal: Drive(0.0),
            pain: Drive(0.0),
            stress: Drive(0.0),
            loneliness: Drive(0.0),
        }
    }

    /// Au moins un drive est critique ?
    pub fn any_critical(&self) -> bool {
        self.hunger.is_critical()
            || self.thirst.is_critical()
            || self.fatigue.is_critical()
            || self.thermal.is_critical()
    }

    /// Drive dominant — celui à maximiser la satisfaction (utility max).
    pub fn dominant(&self) -> DriveKind {
        let pairs = [
            (DriveKind::Thirst, self.thirst.0),
            (DriveKind::Hunger, self.hunger.0),
            (DriveKind::Thermal, self.thermal.0),
            (DriveKind::Sleep, self.sleep.0),
            (DriveKind::Fatigue, self.fatigue.0),
        ];
        let mut best = DriveKind::Hunger;
        let mut bv = -1.0;
        for (k, v) in pairs {
            if v > bv {
                bv = v;
                best = k;
            }
        }
        best
    }
}

/// Identifiant de drive (utilisé par la cognition).
#[derive(Copy, Clone, Eq, PartialEq, Debug, Serialize, Deserialize)]
pub enum DriveKind {
    /// Faim.
    Hunger,
    /// Soif.
    Thirst,
    /// Sommeil.
    Sleep,
    /// Fatigue.
    Fatigue,
    /// Thermorégulation.
    Thermal,
}
