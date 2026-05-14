//! Génération d'un échantillon de terrain (height, temp, precip) à partir d'un seed.
//!
//! Toutes les sorties sont déterministes pour un (seed, x, y).

use crate::noise::fbm_2d;
use ge_core::WorldSeed;

/// Configuration globale du générateur de terrain.
#[derive(Clone, Debug)]
pub struct TerrainParams {
    /// Échelle horizontale (mètres par unité de bruit). Plus grand = relief plus large.
    pub scale_m: f32,
    /// Amplitude verticale max en mètres (sommets vs océan).
    pub max_elev_m: f32,
    /// Niveau de la mer (m, peut être négatif si planète sèche).
    pub sea_level_m: f32,
    /// Octaves pour l'élévation.
    pub elev_octaves: u32,
    /// Octaves pour la température.
    pub temp_octaves: u32,
    /// Octaves pour les précipitations.
    pub precip_octaves: u32,
}

impl Default for TerrainParams {
    fn default() -> Self {
        Self {
            scale_m: 2_000.0,
            max_elev_m: 4_000.0,
            sea_level_m: 0.0,
            elev_octaves: 6,
            temp_octaves: 3,
            precip_octaves: 4,
        }
    }
}

/// Échantillon climatique d'un point.
#[derive(Copy, Clone, Debug)]
pub struct TerrainSample {
    /// Altitude en mètres au-dessus du niveau de la mer.
    pub elev_m: f32,
    /// Température moyenne annuelle (°C).
    pub temp_c: f32,
    /// Précipitations annuelles (mm).
    pub precip_mm: f32,
}

/// Échantillonne le terrain au point (x_m, y_m) (en mètres absolus).
pub fn sample(seed: WorldSeed, params: &TerrainParams, x_m: f32, y_m: f32) -> TerrainSample {
    let x = x_m / params.scale_m;
    let y = y_m / params.scale_m;

    // Élévation: fbm 6 octaves, normalisé puis remappé.
    let e_raw = fbm_2d(seed, "elev", x, y, params.elev_octaves, 2.0, 0.5);
    let elev_m = params.sea_level_m + e_raw * params.max_elev_m;

    // Température : décroît avec la latitude (y) et l'altitude.
    let lat_factor = 1.0 - (y_m.abs() / 10_000_000.0).min(1.0); // crude
    let t_noise = fbm_2d(seed, "temp", x * 0.3, y * 0.3, params.temp_octaves, 2.0, 0.5);
    let temp_at_sea = 30.0 * lat_factor - 5.0 + t_noise * 8.0;
    let elev_drop = (elev_m.max(0.0) / 1000.0) * 6.5; // gradient adiabatique
    let temp_c = temp_at_sea - elev_drop;

    // Précipitations : 0–4000 mm, modulé par bruit haute fréquence.
    let p_raw = fbm_2d(seed, "precip", x * 0.5, y * 0.5, params.precip_octaves, 2.0, 0.55);
    let precip_mm = ((p_raw + 1.0) * 0.5 * 4_000.0).max(0.0);

    TerrainSample { elev_m, temp_c, precip_mm }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deterministic_samples() {
        let p = TerrainParams::default();
        let a = sample(0xDEAD, &p, 1234.5, 6789.0);
        let b = sample(0xDEAD, &p, 1234.5, 6789.0);
        assert_eq!(a.elev_m, b.elev_m);
        assert_eq!(a.temp_c, b.temp_c);
        assert_eq!(a.precip_mm, b.precip_mm);
    }
}
