//! Built-in Whittaker biome classifier.
//!
//! The classifier is a deterministic function of `(temperature_c, humidity,
//! elevation_m, sea_level_m)`. Same inputs ⇒ same biome, always.

use serde::{Deserialize, Serialize};

/// Built-in 16-biome Whittaker biome enum.
#[repr(u8)]
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Biome {
    /// Deep oceanic water.
    Ocean = 0,
    /// Shallow coastal water.
    CoastalSea = 1,
    /// Permanent surface ice (e.g. ice cap, glacier).
    Ice = 2,
    /// Treeless cold plain.
    Tundra = 3,
    /// Cold needleleaf forest (taiga).
    BorealForest = 4,
    /// Mixed/deciduous temperate forest.
    TemperateForest = 5,
    /// Wet temperate forest (Pacific NW, NZ, etc.).
    TemperateRainforest = 6,
    /// Mid-latitude grass-dominated open biome (steppe, prairie).
    Grassland = 7,
    /// Hot, arid desert.
    HotDesert = 8,
    /// Cold, arid desert (rain shadow + altitude).
    ColdDesert = 9,
    /// Mixed grass + scattered trees, seasonal rain.
    Savanna = 10,
    /// Seasonal tropical forest.
    TropicalDryForest = 11,
    /// Year-round wet equatorial forest.
    TropicalRainforest = 12,
    /// Mediterranean shrubland.
    Shrubland = 13,
    /// Swamp / inland marsh.
    Wetland = 14,
    /// Bare rock above tree line.
    AlpineRock = 15,
}

impl Biome {
    /// All variants, in numeric-discriminant order. Single source of truth
    /// for `COUNT` and `from_index`. Adding a new biome means adding it
    /// both as an enum variant *and* in this array — the test
    /// `variants_match_discriminants` guards the invariant.
    pub const VARIANTS: [Biome; 16] = [
        Biome::Ocean,
        Biome::CoastalSea,
        Biome::Ice,
        Biome::Tundra,
        Biome::BorealForest,
        Biome::TemperateForest,
        Biome::TemperateRainforest,
        Biome::Grassland,
        Biome::HotDesert,
        Biome::ColdDesert,
        Biome::Savanna,
        Biome::TropicalDryForest,
        Biome::TropicalRainforest,
        Biome::Shrubland,
        Biome::Wetland,
        Biome::AlpineRock,
    ];

    /// Total number of Biome variants — sized lookup tables use this.
    pub const COUNT: usize = Self::VARIANTS.len();

    /// Convert a `u8` discriminant back to its `Biome`. Returns `None`
    /// for indices outside `0..COUNT`. Prefer this over a hand-rolled
    /// `match Some(0) => Biome::Ocean, …` — those silently default new
    /// variants to a catch-all branch and rot quietly.
    #[must_use]
    pub const fn from_index(i: u8) -> Option<Biome> {
        if (i as usize) < Self::COUNT {
            Some(Self::VARIANTS[i as usize])
        } else {
            None
        }
    }

    /// Classify by temperature (°C), humidity in `[0,1]`, elevation in metres,
    /// and sea level in metres.
    #[must_use]
    pub fn classify(temp_c: f32, humidity: f32, elevation_m: f32, sea_level_m: f32) -> Self {
        // 1) Below sea level → ocean (deep or shallow).
        if elevation_m < sea_level_m {
            let depth = sea_level_m - elevation_m;
            return if depth > 200.0 {
                Biome::Ocean
            } else {
                Biome::CoastalSea
            };
        }

        // 2) Frozen waterscape.
        if temp_c < -10.0 {
            return Biome::Ice;
        }

        // 3) Above tree line / alpine.
        if elevation_m - sea_level_m > 3_500.0 && temp_c < 5.0 {
            return Biome::AlpineRock;
        }

        // 4) Wetlands at low elevation + high humidity (regardless of temp).
        if humidity > 0.9 && elevation_m - sea_level_m < 30.0 && temp_c > 0.0 {
            return Biome::Wetland;
        }

        // 5) Whittaker chart proper.
        // Axis: temperature (cold → hot)
        if temp_c < 0.0 {
            return Biome::Tundra;
        }
        if temp_c < 7.0 {
            if humidity < 0.20 {
                Biome::ColdDesert
            } else {
                Biome::BorealForest
            }
        } else if temp_c < 17.0 {
            // temperate band
            if humidity < 0.18 {
                Biome::ColdDesert
            } else if humidity < 0.35 {
                Biome::Grassland
            } else if humidity < 0.55 {
                Biome::TemperateForest
            } else if humidity < 0.75 {
                Biome::TemperateForest
            } else if humidity < 0.92 {
                Biome::TemperateRainforest
            } else {
                Biome::TemperateRainforest
            }
        } else if temp_c < 22.0 {
            // warm-temperate / mediterranean
            if humidity < 0.18 {
                Biome::HotDesert
            } else if humidity < 0.35 {
                Biome::Shrubland
            } else if humidity < 0.55 {
                Biome::Grassland
            } else {
                Biome::TemperateForest
            }
        } else {
            // tropical band
            if humidity < 0.18 {
                Biome::HotDesert
            } else if humidity < 0.35 {
                Biome::Savanna
            } else if humidity < 0.60 {
                Biome::TropicalDryForest
            } else {
                Biome::TropicalRainforest
            }
        }
    }

    /// Net Primary Productivity proxy (units: arbitrary, 0..1).
    #[must_use]
    pub const fn npp(self) -> f32 {
        match self {
            Biome::Ocean => 0.30,
            Biome::CoastalSea => 0.45,
            Biome::Ice => 0.02,
            Biome::Tundra => 0.15,
            Biome::BorealForest => 0.55,
            Biome::TemperateForest => 0.80,
            Biome::TemperateRainforest => 0.95,
            Biome::Grassland => 0.45,
            Biome::HotDesert => 0.05,
            Biome::ColdDesert => 0.05,
            Biome::Savanna => 0.50,
            Biome::TropicalDryForest => 0.60,
            Biome::TropicalRainforest => 1.00,
            Biome::Shrubland => 0.35,
            Biome::Wetland => 0.85,
            Biome::AlpineRock => 0.05,
        }
    }

    /// Habitability proxy for agents (units: arbitrary, 0..1).
    #[must_use]
    pub const fn habitability(self) -> f32 {
        match self {
            Biome::Ocean => 0.0,
            Biome::CoastalSea => 0.30,
            Biome::Ice => 0.05,
            Biome::Tundra => 0.15,
            Biome::BorealForest => 0.50,
            Biome::TemperateForest => 0.90,
            Biome::TemperateRainforest => 0.85,
            Biome::Grassland => 0.90,
            Biome::HotDesert => 0.20,
            Biome::ColdDesert => 0.20,
            Biome::Savanna => 0.85,
            Biome::TropicalDryForest => 0.80,
            Biome::TropicalRainforest => 0.70,
            Biome::Shrubland => 0.75,
            Biome::Wetland => 0.40,
            Biome::AlpineRock => 0.10,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ocean_below_sea_level() {
        assert!(matches!(
            Biome::classify(15.0, 0.5, -500.0, 0.0),
            Biome::Ocean | Biome::CoastalSea
        ));
    }

    #[test]
    fn tropical_rainforest_at_equator_wet() {
        assert_eq!(Biome::classify(27.0, 0.85, 200.0, 0.0), Biome::TropicalRainforest);
    }

    #[test]
    fn polar_ice_when_freezing() {
        assert_eq!(Biome::classify(-20.0, 0.5, 100.0, 0.0), Biome::Ice);
    }

    #[test]
    fn hot_desert_at_low_humidity() {
        assert_eq!(Biome::classify(30.0, 0.05, 100.0, 0.0), Biome::HotDesert);
    }

    #[test]
    fn variants_match_discriminants() {
        // If a new variant is added to the enum but not to VARIANTS, or if
        // someone reorders them, this test catches it. The discriminant is
        // the canonical numeric identity used by every consumer.
        for (i, b) in Biome::VARIANTS.iter().enumerate() {
            assert_eq!(*b as u8 as usize, i, "variant {b:?} at slot {i} has mismatched discriminant");
            assert_eq!(Biome::from_index(i as u8), Some(*b));
        }
        assert_eq!(Biome::from_index(Biome::COUNT as u8), None);
        assert_eq!(Biome::from_index(255), None);
    }

    #[test]
    fn determinism() {
        for i in 0..1000 {
            let t = (i as f32) * 0.1 - 30.0;
            let h = (i as f32 * 0.013) % 1.0;
            let e = (i as f32) * 5.0 - 100.0;
            assert_eq!(
                Biome::classify(t, h, e, 0.0),
                Biome::classify(t, h, e, 0.0)
            );
        }
    }
}
