//! Climat dynamique (saison, météo simple).
//!
//! Phase 1 : modèle pauvre — saison sinusoïdale + bruit léger.
//! Phase 3+ : modèle eulérien sur grille basse résolution.

use crate::terrain::TerrainSample;
use ge_core::Tick;
use serde::{Deserialize, Serialize};

/// Nombre de ticks par jour simulé (Phase 1 : 1 tick = 1 s, 1 jour = 86 400 s).
pub const TICKS_PER_DAY: u64 = 86_400;
/// Nombre de jours dans une année.
pub const DAYS_PER_YEAR: u64 = 365;

/// État météorologique courant d'une cellule.
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub struct Weather {
    /// Température actuelle (°C).
    pub temp_c: f32,
    /// Précipitations courantes (mm/h).
    pub rain_mm_h: f32,
    /// Couverture nuageuse (0..1).
    pub cloud: f32,
}

/// Calcule la météo à un tick donné à partir du climat moyen.
pub fn weather_at(tick: Tick, base: &TerrainSample, hemisphere_north: bool) -> Weather {
    let secs = tick.get();
    let day = (secs / TICKS_PER_DAY) % DAYS_PER_YEAR;
    let hour = (secs % TICKS_PER_DAY) as f32 / 3_600.0;

    // Saison (sinusoidal, max en juillet pour hémisphère nord).
    let season_phase = (day as f32) / DAYS_PER_YEAR as f32 * std::f32::consts::TAU;
    let season = if hemisphere_north {
        -(season_phase.cos())
    } else {
        season_phase.cos()
    };
    let season_amp = 12.0; // °C amplitude annuelle

    // Cycle jour/nuit (sinusoidal, max à 14h).
    let diurnal_phase = ((hour - 14.0) / 24.0) * std::f32::consts::TAU;
    let diurnal = -diurnal_phase.cos() * 6.0;

    let temp_c = base.temp_c + season * season_amp + diurnal;
    let rain_mm_h = (base.precip_mm / (DAYS_PER_YEAR as f32 * 24.0)).max(0.0);
    let cloud = (rain_mm_h * 4.0).min(1.0);

    Weather { temp_c, rain_mm_h, cloud }
}
