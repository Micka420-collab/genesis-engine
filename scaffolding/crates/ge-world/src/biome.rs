//! Classification des biomes selon le diagramme Whittaker
//! (température moyenne annuelle vs précipitations).

use serde::{Deserialize, Serialize};

/// Biome canonique. 12 classes, suffisant pour Phase 1.
#[derive(Copy, Clone, Eq, PartialEq, Debug, Hash, Serialize, Deserialize)]
pub enum Biome {
    /// Inlandsis / banquise.
    Ice,
    /// Toundra arctique.
    Tundra,
    /// Forêt boréale (taïga).
    BorealForest,
    /// Forêt tempérée caducifoliée.
    TemperateForest,
    /// Forêt tempérée humide (rainforest tempérée).
    TemperateRainforest,
    /// Prairies, steppes tempérées.
    Grassland,
    /// Désert chaud.
    HotDesert,
    /// Désert froid.
    ColdDesert,
    /// Savane.
    Savanna,
    /// Forêt tropicale sèche.
    TropicalDryForest,
    /// Forêt tropicale humide.
    TropicalRainforest,
    /// Océan / mer.
    Ocean,
}

/// Classification Whittaker simplifiée.
/// - `temp_c` : température moyenne annuelle (°C, env. -25 à 35)
/// - `precip_mm` : précipitations annuelles (0 à 4500)
/// - `elev_m` : altitude (m, négatif = sous l'eau)
pub fn classify(temp_c: f32, precip_mm: f32, elev_m: f32) -> Biome {
    if elev_m < 0.0 {
        return Biome::Ocean;
    }
    if temp_c < -10.0 {
        return Biome::Ice;
    }
    if temp_c < 0.0 {
        return Biome::Tundra;
    }
    // < 10 °C
    if temp_c < 10.0 {
        return if precip_mm < 300.0 {
            Biome::ColdDesert
        } else {
            Biome::BorealForest
        };
    }
    // < 20 °C
    if temp_c < 20.0 {
        return if precip_mm < 250.0 {
            Biome::ColdDesert
        } else if precip_mm < 750.0 {
            Biome::Grassland
        } else if precip_mm < 1500.0 {
            Biome::TemperateForest
        } else {
            Biome::TemperateRainforest
        };
    }
    // tropical (>= 20 °C)
    if precip_mm < 250.0 {
        Biome::HotDesert
    } else if precip_mm < 750.0 {
        Biome::Savanna
    } else if precip_mm < 1500.0 {
        Biome::TropicalDryForest
    } else {
        Biome::TropicalRainforest
    }
}

impl Biome {
    /// Productivité primaire nette relative (0..1) — utilisé par la chaîne trophique.
    pub fn npp(self) -> f32 {
        match self {
            Self::Ice | Self::HotDesert | Self::ColdDesert => 0.05,
            Self::Tundra => 0.15,
            Self::Grassland | Self::Savanna => 0.45,
            Self::BorealForest | Self::TropicalDryForest => 0.55,
            Self::TemperateForest | Self::TemperateRainforest => 0.80,
            Self::TropicalRainforest => 1.00,
            Self::Ocean => 0.30,
        }
    }

    /// Habitabilité humaine de base (0..1). Joue dans le coût énergétique.
    pub fn habitability(self) -> f32 {
        match self {
            Self::Ice => 0.05,
            Self::Tundra => 0.15,
            Self::HotDesert | Self::ColdDesert => 0.20,
            Self::BorealForest => 0.50,
            Self::Grassland | Self::Savanna | Self::TropicalDryForest => 0.85,
            Self::TemperateForest | Self::TemperateRainforest => 0.90,
            Self::TropicalRainforest => 0.70,
            Self::Ocean => 0.0,
        }
    }
}
