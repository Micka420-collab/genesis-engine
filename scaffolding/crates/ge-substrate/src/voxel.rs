//! Types voxel du substrat physique.
//!
//! Tous les types sont `#[repr(C)]` pour un upload GPU bit-exact
//! ultérieur (WGSL storage buffers). Les tailles sont audit-ées par
//! des tests de layout dans `tests` ci-dessous.

use serde::{Deserialize, Serialize};

/// Voxel d'eau libre (rivière, lac, mer, ruissellement).
///
/// Unités SI sauf indication contraire. Conventions :
/// - `volume` est la quantité d'eau dans la colonne 1m² du voxel
///   (équivaut à une hauteur en mètres pour une grille 1m×1m).
/// - `velocity.xy` = flux horizontal m/s ; `velocity.z` = vertical
///   (utile pour cascades, geysers, sources).
#[repr(C, align(16))]
#[derive(Copy, Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct WaterVoxel {
    /// m³ d'eau dans le voxel (≡ hauteur en m pour grille 1m²).
    pub volume: f32,
    /// Vélocité du flux (m/s) — composantes x, y, z.
    pub velocity: [f32; 3],
    /// Sédiments en suspension (kg).
    pub sediment: f32,
    /// Température (°C). Stocke l'inertie thermique des masses d'eau.
    pub temperature: f32,
    /// Salinité (ppt — mer ≈ 35, eau douce ≈ 0).
    pub salinity: f32,
    /// Turbidité (NTU — lisibilité de l'eau).
    pub turbidity: f32,
    /// Padding pour alignement 16 bytes — futur GPU.
    pub _pad: f32,
}

/// Propriétés hydrologiques du sol (porosité, perméabilité, eau retenue).
///
/// Issues d'un mélange physique entre la roche-mère et la matière
/// organique. Les valeurs servent à la loi d'infiltration de
/// Green-Ampt et au modèle de croissance végétale (Liebig).
#[repr(C, align(16))]
#[derive(Copy, Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct SoilHydro {
    /// θ — teneur volumique en eau, 0.0 à ~0.45.
    pub water_content: f32,
    /// φ — porosité (argile 0.45, sable 0.38, roche compacte 0.02).
    pub porosity: f32,
    /// K_sat — perméabilité saturée (cm/h ; argile 0.05, sable 25.0).
    pub permeability: f32,
    /// θ_fc — capacité au champ (rétention max sans drainage).
    pub field_capacity: f32,
    /// θ_wp — point de flétrissement (min accessible aux plantes).
    pub wilting_point: f32,
    /// Fraction de matière organique (0.0 à ~0.3). ↑ rétention eau.
    pub organic_matter: f32,
    /// Padding alignement 16 bytes.
    pub _pad0: f32,
    /// Padding alignement 16 bytes.
    pub _pad1: f32,
}

/// Type de roche — 12 catégories couvrant sédimentaires,
/// métamorphiques et plutoniques courantes.
#[repr(u8)]
#[derive(Copy, Clone, Debug, Default, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[allow(missing_docs)]
pub enum RockType {
    #[default]
    Air = 0,
    Regolith = 1,
    Clay = 2,
    Sand = 3,
    Sandstone = 4,
    Limestone = 5,
    Basalt = 6,
    Granite = 7,
    Schist = 8,
    Marble = 9,
    Quartzite = 10,
    CoalSeam = 11,
}

/// Minéral ou ressource exploitable. `None` = pas de gisement notable.
///
/// L'ordre encode (informellement) une progression technologique :
/// silex avant cuivre avant bronze (cuivre+étain) avant fer.
#[repr(u8)]
#[derive(Copy, Clone, Debug, Default, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[allow(missing_docs)]
pub enum Mineral {
    #[default]
    None = 0,
    Flint = 1,
    Copper = 2,
    Tin = 3,
    Iron = 4,
    Gold = 5,
    Silver = 6,
    Coal = 7,
    Salt = 8,
    Sulfur = 9,
    Obsidian = 10,
    FineClay = 11,
    Malachite = 12,
    Magnetite = 13,
    Quartz = 14,
    LimestonePure = 15,
}

/// Voxel géologique 3D.
///
/// Encode à la fois la **roche-mère** et un éventuel **gisement**
/// minéral. `color_hint` est la couleur visible en surface si le
/// voxel affleure — c'est l'indice qu'un agent peut détecter en
/// observant son environnement (vert = malachite → cuivre dessous).
#[repr(C, align(16))]
#[derive(Copy, Clone, Debug, Default, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct GeoVoxel {
    /// Type de roche.
    pub rock_type: RockType,
    /// Minéral/ressource présente (peut être `None`).
    pub mineral_id: Mineral,
    /// Teneur du minéral, 0–255 (≡ 0.0–100% par /2.55).
    pub mineral_pct: u8,
    /// Dureté Mohs × 25 (talc=25, diamant=250).
    pub hardness: u8,
    /// Porosité 0–255 (0=imperméable, 255=très poreuse).
    pub porosity: u8,
    /// Catégorie de perméabilité K_sat (0–8, log-discrète).
    pub permeability: u8,
    /// Padding alignement.
    pub _pad: [u8; 2],
    /// Température °C × 10 (gradient géothermique ~25°C/km).
    pub temperature: i16,
    /// Âge stratigraphique simulé (Ma).
    pub age_strat: u16,
    /// Couleur visible RGBA si voxel affleure (indice visuel agent).
    pub color_hint: u32,
}

impl GeoVoxel {
    /// Teneur du minéral en fraction 0.0–1.0.
    #[inline]
    pub fn mineral_fraction(&self) -> f32 {
        self.mineral_pct as f32 / 255.0
    }

    /// Température en °C.
    #[inline]
    pub fn temperature_c(&self) -> f32 {
        self.temperature as f32 / 10.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::mem::{align_of, size_of};

    #[test]
    fn water_voxel_layout_is_stable() {
        // 7 × f32 = 28, padded à 32 pour align 16.
        assert_eq!(size_of::<WaterVoxel>(), 32);
        assert_eq!(align_of::<WaterVoxel>(), 16);
    }

    #[test]
    fn soil_hydro_layout_is_stable() {
        // 8 × f32 = 32, align 16.
        assert_eq!(size_of::<SoilHydro>(), 32);
        assert_eq!(align_of::<SoilHydro>(), 16);
    }

    #[test]
    fn geo_voxel_layout_is_stable() {
        // 6 × u8 + 2 padding + i16 + u16 + u32 = 16 bytes.
        assert_eq!(size_of::<GeoVoxel>(), 16);
        assert_eq!(align_of::<GeoVoxel>(), 16);
    }

    #[test]
    fn mineral_fraction_roundtrips() {
        let v = GeoVoxel { mineral_pct: 128, ..Default::default() };
        let f = v.mineral_fraction();
        assert!((f - 0.5019608).abs() < 1e-6);
    }

    #[test]
    fn rock_type_default_is_air() {
        let v = GeoVoxel::default();
        assert_eq!(v.rock_type, RockType::Air);
        assert_eq!(v.mineral_id, Mineral::None);
    }
}
