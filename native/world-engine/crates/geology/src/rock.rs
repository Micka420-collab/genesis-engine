//! Host rock taxonomy.
//!
//! Rocks are the geological host for mineral deposits. The mineral distribution
//! rules in [`crate::mineral`] are keyed on this enum: e.g. copper porphyry
//! only spawns where `host_rock = Schist | Granite`, never in `Clay`.

use serde::{Deserialize, Serialize};

/// 12 host-rock classes. The numeric discriminant is stable; it is used as a
/// palette index and as a `Prf` salt.
#[repr(u8)]
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum RockType {
    /// Empty / not rock (water column, atmosphere).
    Air = 0,
    /// Loose surface material — weathered top horizon.
    Regolith = 1,
    /// Sedimentary clay (fine, plastic, low permeability).
    Clay = 2,
    /// Loose mineral grains; high permeability.
    Sand = 3,
    /// Lithified sand; common sedimentary host.
    Sandstone = 4,
    /// Sedimentary carbonate — flint host, karst potential.
    Limestone = 5,
    /// Extrusive volcanic basalt — sulfur / obsidian context.
    Basalt = 6,
    /// Intrusive felsic pluton — tin pegmatite, hydrothermal source.
    Granite = 7,
    /// Metamorphic schist — copper porphyry candidate.
    Schist = 8,
    /// Metamorphosed limestone.
    Marble = 9,
    /// Metamorphosed sandstone — gold-bearing quartz veins.
    Quartzite = 10,
    /// Organic carbon-rich seam (coal).
    CoalSeam = 11,
}

/// Number of [`RockType`] variants. Sized lookup tables use this.
pub const ROCK_TYPE_COUNT: usize = 12;

impl RockType {
    /// All variants in discriminant order.
    pub const VARIANTS: [RockType; ROCK_TYPE_COUNT] = [
        RockType::Air,
        RockType::Regolith,
        RockType::Clay,
        RockType::Sand,
        RockType::Sandstone,
        RockType::Limestone,
        RockType::Basalt,
        RockType::Granite,
        RockType::Schist,
        RockType::Marble,
        RockType::Quartzite,
        RockType::CoalSeam,
    ];

    /// Convert a `u8` discriminant back to its variant. Returns `None` for
    /// values outside `0..ROCK_TYPE_COUNT`.
    #[must_use]
    pub const fn from_index(i: u8) -> Option<RockType> {
        if (i as usize) < ROCK_TYPE_COUNT {
            Some(Self::VARIANTS[i as usize])
        } else {
            None
        }
    }

    /// Mohs hardness × 10 (encoded so all variants are `const`-comparable).
    /// Real values: regolith ~1, clay 1–2, limestone 3, granite 6.5,
    /// quartzite 7, basalt 6. Used by the agent's tactile percept to
    /// distinguish "soft" vs "hard" without naming the rock.
    #[must_use]
    pub const fn hardness_mohs_x10(self) -> u8 {
        match self {
            RockType::Air => 0,
            RockType::Regolith => 10,
            RockType::Clay => 15,
            RockType::Sand => 25,
            RockType::Sandstone => 45,
            RockType::Limestone => 30,
            RockType::Basalt => 60,
            RockType::Granite => 65,
            RockType::Schist => 40,
            RockType::Marble => 35,
            RockType::Quartzite => 70,
            RockType::CoalSeam => 25,
        }
    }

    /// Baseline RGB the surface shows if NO mineral deposit overlays it.
    /// These are the "honest" colours of the bare rock as the agent perceives
    /// it under daylight. Mineral colour overrides this when present.
    #[must_use]
    pub const fn base_color(self) -> [u8; 3] {
        match self {
            RockType::Air => [0, 0, 0],
            RockType::Regolith => [140, 120, 100],
            RockType::Clay => [160, 130, 100],
            RockType::Sand => [220, 200, 150],
            RockType::Sandstone => [200, 170, 130],
            RockType::Limestone => [220, 215, 200],
            RockType::Basalt => [55, 55, 60],
            RockType::Granite => [180, 170, 165],
            RockType::Schist => [100, 95, 90],
            RockType::Marble => [240, 235, 230],
            RockType::Quartzite => [230, 220, 215],
            RockType::CoalSeam => [25, 25, 25],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn variants_match_discriminants() {
        for (i, r) in RockType::VARIANTS.iter().enumerate() {
            assert_eq!(*r as u8 as usize, i);
            assert_eq!(RockType::from_index(i as u8), Some(*r));
        }
        assert_eq!(RockType::from_index(ROCK_TYPE_COUNT as u8), None);
        assert_eq!(RockType::from_index(255), None);
    }

    #[test]
    fn hardness_monotonic_against_intuition() {
        // Sand is soft, granite is hard. If anyone re-orders the enum and
        // forgets to update hardness, this catches the obvious case.
        assert!(RockType::Sand.hardness_mohs_x10() < RockType::Granite.hardness_mohs_x10());
        assert!(RockType::Clay.hardness_mohs_x10() < RockType::Basalt.hardness_mohs_x10());
        assert!(RockType::Quartzite.hardness_mohs_x10() > RockType::Limestone.hardness_mohs_x10());
    }

    #[test]
    fn base_colors_are_visually_distinguishable() {
        // Coal is dark, marble is light. If they collapse to similar RGB,
        // agents could not differentiate them visually.
        let coal = RockType::CoalSeam.base_color();
        let marble = RockType::Marble.base_color();
        let dist = ((coal[0] as i32 - marble[0] as i32).pow(2)
            + (coal[1] as i32 - marble[1] as i32).pow(2)
            + (coal[2] as i32 - marble[2] as i32).pow(2)) as f32;
        assert!(dist.sqrt() > 200.0, "coal vs marble too similar: dist={}", dist.sqrt());
    }
}
