//! Mineral taxonomy and deposit rules.
//!
//! A `MineralDeposit` is a discovery-grade concentration of a `Mineral` at a
//! given voxel. Whether a deposit exists at `(x, y, z)` is a deterministic
//! function of `(seed, host_rock, depth, climate_band)` — see
//! [`crate::visual::sample_surface`].
//!
//! Distribution rules are scientifically grounded; reading
//! `docs/sprints/2026-05-28_Wave43_mineral_visual_cues.md` documents the
//! geological reasoning for each `MineralRule` below.

use crate::rock::RockType;
use serde::{Deserialize, Serialize};

/// 16 mineral classes the world can host.
///
/// Numeric discriminants are stable; they are used both as palette indices
/// and as `Prf` salts when computing deposit probability per voxel.
#[repr(u8)]
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Mineral {
    /// Knappable silica nodule. Pre-metal technology.
    Flint = 0,
    /// Native or sulfide copper. Chalcolithic.
    Copper = 1,
    /// Cassiterite-class tin. Bronze precursor with copper.
    Tin = 2,
    /// Iron ore (BIF / hematite / limonite).
    Iron = 3,
    /// Native gold — placer and lode.
    Gold = 4,
    /// Native silver / argentite.
    Silver = 5,
    /// Compressed organic carbon.
    Coal = 6,
    /// Evaporite halite. Conservation + trade.
    Salt = 7,
    /// Native or fumarolic sulfur.
    Sulfur = 8,
    /// Volcanic glass — sharper than flint.
    Obsidian = 9,
    /// Plastic clay suitable for pottery / brick.
    FineClay = 10,
    /// Surface-visible copper carbonate (green crust). The single most
    /// important "tell" for buried copper — the agent sees green, digs.
    Malachite = 11,
    /// Naturally magnetic iron oxide.
    Magnetite = 12,
    /// Quartz vein matrix — co-occurs with gold / silver.
    Quartz = 13,
    /// Quicklime precursor — pure carbonate beds.
    LimestonePure = 14,
    /// Sentinel for "no deposit at this voxel".
    None = 15,
}

/// Number of [`Mineral`] variants (including `None`).
pub const MINERAL_COUNT: usize = 16;

impl Mineral {
    /// All variants in discriminant order.
    pub const VARIANTS: [Mineral; MINERAL_COUNT] = [
        Mineral::Flint,
        Mineral::Copper,
        Mineral::Tin,
        Mineral::Iron,
        Mineral::Gold,
        Mineral::Silver,
        Mineral::Coal,
        Mineral::Salt,
        Mineral::Sulfur,
        Mineral::Obsidian,
        Mineral::FineClay,
        Mineral::Malachite,
        Mineral::Magnetite,
        Mineral::Quartz,
        Mineral::LimestonePure,
        Mineral::None,
    ];

    /// Convert a `u8` discriminant back to its variant. Returns `None` for
    /// values outside the valid range. (Note the unfortunate name collision:
    /// the function returns `Option<Mineral>`, and `Mineral::None` is also
    /// a real variant. `from_index(15)` returns `Some(Mineral::None)`.)
    #[must_use]
    pub const fn from_index(i: u8) -> Option<Mineral> {
        if (i as usize) < MINERAL_COUNT {
            Some(Self::VARIANTS[i as usize])
        } else {
            None
        }
    }

    /// Surface RGB visible to an agent looking at a voxel with a deposit of
    /// this mineral exposed. **Critical contract**: same surface colour ⇒
    /// agent's vision system maps to same percept ⇒ same memory key. The
    /// agent does not see "copper"; it sees `[80, 140, 70]` (malachite green)
    /// and remembers "green stuff near grey rock".
    ///
    /// `None` returns black; callers should fall back to the rock base colour.
    #[must_use]
    pub const fn surface_color(self) -> [u8; 3] {
        match self {
            Mineral::Flint => [40, 40, 35],            // dark glossy node
            Mineral::Copper => [180, 100, 60],         // native copper sheen
            Mineral::Tin => [200, 200, 200],           // cassiterite grey
            Mineral::Iron => [120, 60, 40],            // hematite reddish-brown
            Mineral::Gold => [240, 200, 60],           // unmistakable yellow
            Mineral::Silver => [220, 220, 230],        // bright pale
            Mineral::Coal => [20, 20, 20],             // matte black
            Mineral::Salt => [250, 248, 245],          // crusty white
            Mineral::Sulfur => [240, 220, 60],         // bright yellow
            Mineral::Obsidian => [15, 10, 20],         // glassy black
            Mineral::FineClay => [180, 140, 110],      // smooth ochre
            Mineral::Malachite => [80, 140, 70],       // VIVID GREEN — copper tell
            Mineral::Magnetite => [40, 40, 50],        // dark with metallic glint
            Mineral::Quartz => [235, 230, 220],        // milky white
            Mineral::LimestonePure => [245, 240, 225], // chalk white
            Mineral::None => [0, 0, 0],
        }
    }

    /// Hardness (Mohs × 10) of the mineral itself, NOT the host rock.
    /// Drives whether a stone-age tool can scratch / break it.
    #[must_use]
    pub const fn hardness_mohs_x10(self) -> u8 {
        match self {
            Mineral::Flint => 70,           // quartz family
            Mineral::Copper => 30,          // native, soft
            Mineral::Tin => 15,
            Mineral::Iron => 45,            // metallic; ore softer
            Mineral::Gold => 25,
            Mineral::Silver => 25,
            Mineral::Coal => 20,
            Mineral::Salt => 20,
            Mineral::Sulfur => 20,
            Mineral::Obsidian => 60,
            Mineral::FineClay => 10,
            Mineral::Malachite => 35,
            Mineral::Magnetite => 60,
            Mineral::Quartz => 70,
            Mineral::LimestonePure => 30,
            Mineral::None => 0,
        }
    }

    /// Whether the mineral's surface signature looks "metallic" — used by
    /// agent vision heuristics ("brillant" perception). Sparkle is the
    /// observable that lets stone-age agents distinguish gold/silver from
    /// dull yellow/grey rock.
    #[must_use]
    pub const fn is_lustrous(self) -> bool {
        matches!(
            self,
            Mineral::Copper | Mineral::Gold | Mineral::Silver | Mineral::Magnetite
        )
    }

    /// Whether the mineral has a perceptible smell — for the chemical-signal
    /// channel of the agent percept. Sulfur is the textbook case.
    #[must_use]
    pub const fn has_smell(self) -> bool {
        matches!(self, Mineral::Sulfur | Mineral::Coal)
    }
}

/// A single deposit of `mineral` in `host_rock` with a `concentration` in
/// `[0,1]` (interpretable as ore grade / surface area fraction).
#[derive(Copy, Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct MineralDeposit {
    /// The mineral present.
    pub mineral: Mineral,
    /// 0.0–1.0 normalized concentration.
    pub concentration: f32,
}

/// Affinity score of mineral × host rock × depth.
///
/// Returns the probability multiplier (>0) when the geological context is
/// consistent with this mineral being there. Returns 0.0 to forbid the pairing
/// outright (e.g. gold in clay).
///
/// **Distribution rules** (scientifically grounded):
///
/// | Mineral        | Allowed hosts                            | Depth preference           |
/// |----------------|------------------------------------------|----------------------------|
/// | Flint          | Limestone (nodules)                      | shallow                    |
/// | Copper         | Schist, Granite (contact aureole)        | moderate                   |
/// | Tin            | Granite (pegmatite)                      | moderate                   |
/// | Iron           | Sandstone, Schist (BIF analogue)         | deep                       |
/// | Gold           | Quartzite, Granite (quartz vein)         | moderate to deep           |
/// | Silver         | Quartzite, Granite                       | deep                       |
/// | Coal           | CoalSeam (definitional)                  | sedimentary cover          |
/// | Salt           | Clay (palaeo-evaporite basin)            | sub-surface                |
/// | Sulfur         | Basalt (volcanic / fumarolic)            | near-surface               |
/// | Obsidian       | Basalt (rapid-cooled flow)               | surface                    |
/// | FineClay       | Clay, Regolith (ubiquitous, grade vary)  | surface                    |
/// | Malachite      | follows Copper as oxidised cap rock      | surface, above Copper      |
/// | Magnetite      | Basalt, Schist                           | any                        |
/// | Quartz         | Quartzite, Granite                       | any                        |
/// | LimestonePure  | Limestone (high-purity beds)             | any                        |
#[must_use]
pub fn affinity(mineral: Mineral, host: RockType, depth_m: i32) -> f32 {
    use Mineral as M;
    use RockType as R;

    if matches!(mineral, M::None) || matches!(host, R::Air) {
        return 0.0;
    }

    // Returns (base_affinity, depth_optimum_m, depth_tolerance_m).
    // 0.0 means forbidden pairing.
    let (base, opt, tol): (f32, f32, f32) = match (mineral, host) {
        (M::Flint, R::Limestone) => (0.6, 8.0, 30.0),
        (M::Copper, R::Schist) => (0.45, 60.0, 100.0),
        (M::Copper, R::Granite) => (0.35, 80.0, 120.0),
        (M::Tin, R::Granite) => (0.30, 70.0, 90.0),
        (M::Iron, R::Sandstone) => (0.40, 200.0, 250.0),
        (M::Iron, R::Schist) => (0.30, 250.0, 300.0),
        (M::Gold, R::Quartzite) => (0.15, 150.0, 200.0),
        (M::Gold, R::Granite) => (0.08, 200.0, 250.0),
        (M::Silver, R::Quartzite) => (0.12, 180.0, 200.0),
        (M::Silver, R::Granite) => (0.07, 220.0, 250.0),
        (M::Coal, R::CoalSeam) => (0.95, 40.0, 80.0),
        (M::Salt, R::Clay) => (0.25, 20.0, 60.0),
        (M::Sulfur, R::Basalt) => (0.35, 5.0, 25.0),
        (M::Obsidian, R::Basalt) => (0.25, 0.0, 5.0),
        (M::FineClay, R::Clay) => (0.70, 2.0, 10.0),
        (M::FineClay, R::Regolith) => (0.40, 1.0, 5.0),
        (M::Malachite, R::Schist) => (0.30, 4.0, 8.0), // surface oxidation
        (M::Malachite, R::Granite) => (0.20, 4.0, 8.0),
        (M::Magnetite, R::Basalt) => (0.20, 30.0, 80.0),
        (M::Magnetite, R::Schist) => (0.15, 80.0, 150.0),
        (M::Quartz, R::Quartzite) => (0.55, 50.0, 200.0),
        (M::Quartz, R::Granite) => (0.30, 80.0, 200.0),
        (M::LimestonePure, R::Limestone) => (0.45, 10.0, 50.0),
        _ => return 0.0, // forbidden pairing
    };

    // Gaussian falloff around the optimum depth.
    let d = depth_m as f32;
    let z = (d - opt) / tol;
    let depth_factor = (-(z * z)).exp();
    base * depth_factor
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn variants_match_discriminants() {
        for (i, m) in Mineral::VARIANTS.iter().enumerate() {
            assert_eq!(*m as u8 as usize, i);
            assert_eq!(Mineral::from_index(i as u8), Some(*m));
        }
        assert_eq!(Mineral::from_index(MINERAL_COUNT as u8), None);
    }

    #[test]
    fn forbidden_pairings_are_zero() {
        // The skill is explicit: no gold in clay strata.
        assert_eq!(affinity(Mineral::Gold, RockType::Clay, 100), 0.0);
        // No coal outside coal seams.
        assert_eq!(affinity(Mineral::Coal, RockType::Granite, 50), 0.0);
        // No native copper in pure sand.
        assert_eq!(affinity(Mineral::Copper, RockType::Sand, 50), 0.0);
        // Air hosts nothing.
        assert_eq!(affinity(Mineral::Iron, RockType::Air, 100), 0.0);
        // `None` mineral has zero affinity everywhere.
        assert_eq!(affinity(Mineral::None, RockType::Schist, 50), 0.0);
    }

    #[test]
    fn malachite_is_surface_marker_for_copper() {
        // Malachite's affinity peaks shallow; copper's peaks deeper. So the
        // agent's eye sees the malachite first and would have to dig to
        // reach the copper. This is the entire point of the visual-cue
        // mechanic — emergence over scripting.
        let mal_shallow = affinity(Mineral::Malachite, RockType::Schist, 4);
        let cu_shallow = affinity(Mineral::Copper, RockType::Schist, 4);
        let cu_deep = affinity(Mineral::Copper, RockType::Schist, 60);
        assert!(mal_shallow > 0.0);
        assert!(cu_deep > cu_shallow);
    }

    #[test]
    fn gold_is_rare_compared_to_iron() {
        let au = affinity(Mineral::Gold, RockType::Quartzite, 150);
        let fe = affinity(Mineral::Iron, RockType::Sandstone, 200);
        assert!(au < fe, "gold {au} should be rarer than iron {fe}");
    }

    #[test]
    fn malachite_green_is_distinguishable_from_grass() {
        // Critical: malachite must look distinctly different from any
        // green that vegetation produces. Grass biome green is around
        // (110, 170, 60) in stock palettes; malachite is (80, 140, 70).
        // We don't compare against grass directly here, but we lock the
        // malachite RGB so visual regressions are caught.
        assert_eq!(Mineral::Malachite.surface_color(), [80, 140, 70]);
    }

    #[test]
    fn lustrous_set_matches_intuition() {
        assert!(Mineral::Gold.is_lustrous());
        assert!(Mineral::Silver.is_lustrous());
        assert!(!Mineral::Coal.is_lustrous());
        assert!(!Mineral::FineClay.is_lustrous());
    }

    #[test]
    fn sulfur_smells() {
        assert!(Mineral::Sulfur.has_smell());
        assert!(!Mineral::Gold.has_smell());
    }
}
