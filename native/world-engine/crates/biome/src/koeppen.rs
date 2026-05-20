//! Köppen–Geiger climate classification (simplified 15-class subset).
//!
//! Maps `(temp_annual_c, temp_coldest_c, precip_annual_mm)` to a climate
//! code suitable for validation against observational atlases. This is a
//! **diagnostic** layer on top of Whittaker biomes — same inputs always
//! yield the same class (deterministic).

use serde::{Deserialize, Serialize};

/// Simplified Köppen–Geiger climate class (subset used in harness).
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[repr(u8)]
pub enum KoeppenClass {
    /// Tropical rainforest.
    Af = 0,
    /// Tropical monsoon.
    Am = 1,
    /// Tropical savanna / dry winter.
    Aw = 2,
    /// Hot desert.
    BWh = 3,
    /// Cold desert.
    BWk = 4,
    /// Hot semi-arid.
    BSh = 5,
    /// Cold semi-arid.
    BSk = 6,
    /// Humid subtropical.
    Cfa = 7,
    /// Oceanic / marine west coast.
    Cfb = 8,
    /// Mediterranean (hot summer).
    Csa = 9,
    /// Mediterranean (warm summer).
    Csb = 10,
    /// Humid continental (hot summer).
    Dfa = 11,
    /// Humid continental (warm summer).
    Dfb = 12,
    /// Subarctic / boreal.
    Dfc = 13,
    /// Tundra.
    ET = 14,
    /// Ice cap.
    EF = 15,
}

impl KoeppenClass {
    /// Two-letter code for reports / NetCDF attributes.
    #[must_use]
    pub const fn code(self) -> &'static str {
        match self {
            KoeppenClass::Af => "Af",
            KoeppenClass::Am => "Am",
            KoeppenClass::Aw => "Aw",
            KoeppenClass::BWh => "BWh",
            KoeppenClass::BWk => "BWk",
            KoeppenClass::BSh => "BSh",
            KoeppenClass::BSk => "BSk",
            KoeppenClass::Cfa => "Cfa",
            KoeppenClass::Cfb => "Cfb",
            KoeppenClass::Csa => "Csa",
            KoeppenClass::Csb => "Csb",
            KoeppenClass::Dfa => "Dfa",
            KoeppenClass::Dfb => "Dfb",
            KoeppenClass::Dfc => "Dfc",
            KoeppenClass::ET => "ET",
            KoeppenClass::EF => "EF",
        }
    }

    /// Classify from annual mean temperature (°C), coldest-month mean (°C),
    /// and annual precipitation (mm). Thresholds follow a Köppen–Geiger
    /// simplification (Peel et al. 2007 style, coarse).
    #[must_use]
    pub fn classify(temp_annual_c: f32, temp_coldest_c: f32, precip_annual_mm: f32) -> Self {
        let p = precip_annual_c_threshold(temp_annual_c);
        let p_winter = 0.25 * precip_annual_mm; // coarse winter precip proxy

        // Group E — polar.
        if temp_annual_c < -6.0 {
            return if temp_coldest_c < -12.0 {
                KoeppenClass::EF
            } else {
                KoeppenClass::ET
            };
        }

        // Group B — arid / semi-arid (precip below threshold).
        if precip_annual_mm < p {
            let semi = precip_annual_mm > 0.5 * p;
            if temp_annual_c >= 18.0 {
                return if semi { KoeppenClass::BSh } else { KoeppenClass::BWh };
            }
            return if semi { KoeppenClass::BSk } else { KoeppenClass::BWk };
        }

        // Group A — tropical (all months >= 18 °C approximated by annual >= 18
        // and coldest >= 18).
        if temp_coldest_c >= 18.0 {
            if precip_annual_mm >= 2_500.0 {
                return KoeppenClass::Af;
            }
            if p_winter < 60.0 {
                return KoeppenClass::Am;
            }
            return KoeppenClass::Aw;
        }

        // Group D — continental (coldest < -3 °C, warmest proxy via annual).
        if temp_coldest_c < -3.0 {
            if temp_annual_c >= 10.0 {
                return KoeppenClass::Dfa;
            }
            if temp_annual_c >= 0.0 {
                return KoeppenClass::Dfb;
            }
            return KoeppenClass::Dfc;
        }

        // Group C — temperate.
        // Dry summer (Mediterranean): summer precip < 40 mm and < 1/3 winter.
        if p_winter > 3.0 * (precip_annual_mm - p_winter) {
            if temp_annual_c >= 22.0 {
                return KoeppenClass::Csa;
            }
            return KoeppenClass::Csb;
        }
        if temp_annual_c >= 22.0 || temp_coldest_c > 0.0 && precip_annual_mm > 1_000.0 {
            return KoeppenClass::Cfa;
        }
        KoeppenClass::Cfb
    }
}

/// Aridity threshold `p` (mm/year) as function of annual temperature.
#[must_use]
fn precip_annual_c_threshold(temp_annual_c: f32) -> f32 {
    if temp_annual_c >= 0.0 {
        20.0 * temp_annual_c + 280.0
    } else {
        20.0 * temp_annual_c
    }
}

/// Reference climate station for harness validation.
#[derive(Copy, Clone, Debug)]
pub struct ReferenceClimate {
    /// Human label.
    pub name: &'static str,
    /// Annual mean temperature °C.
    pub temp_annual_c: f32,
    /// Coldest-month mean °C.
    pub temp_coldest_c: f32,
    /// Annual precipitation mm.
    pub precip_annual_mm: f32,
    /// Expected Köppen class.
    pub expected: KoeppenClass,
}

/// Built-in reference climates (coarse; for regression harness).
pub const REFERENCE_CLIMATES: &[ReferenceClimate] = &[
    ReferenceClimate {
        name: "Singapore",
        temp_annual_c: 27.0,
        temp_coldest_c: 26.0,
        precip_annual_mm: 2_600.0,
        expected: KoeppenClass::Af,
    },
    ReferenceClimate {
        name: "Sahara (Tamanrasset)",
        temp_annual_c: 22.0,
        temp_coldest_c: 12.0,
        precip_annual_mm: 50.0,
        expected: KoeppenClass::BWh,
    },
    ReferenceClimate {
        name: "London",
        temp_annual_c: 11.0,
        temp_coldest_c: 5.0,
        precip_annual_mm: 600.0,
        expected: KoeppenClass::Cfb,
    },
    ReferenceClimate {
        name: "Moscow",
        temp_annual_c: 5.0,
        temp_coldest_c: -10.0,
        precip_annual_mm: 700.0,
        expected: KoeppenClass::Dfb,
    },
    ReferenceClimate {
        name: "Fairbanks",
        temp_annual_c: -3.0,
        temp_coldest_c: -25.0,
        precip_annual_mm: 300.0,
        expected: KoeppenClass::Dfc,
    },
    ReferenceClimate {
        name: "Interior Greenland",
        temp_annual_c: -20.0,
        temp_coldest_c: -30.0,
        precip_annual_mm: 200.0,
        expected: KoeppenClass::EF,
    },
];

/// Run harness: fraction of reference climates matching `expected`.
#[must_use]
pub fn harness_pass_rate() -> f32 {
    let n = REFERENCE_CLIMATES.len();
    if n == 0 {
        return 1.0;
    }
    let ok = REFERENCE_CLIMATES
        .iter()
        .filter(|r| KoeppenClass::classify(r.temp_annual_c, r.temp_coldest_c, r.precip_annual_mm) == r.expected)
        .count();
    ok as f32 / n as f32
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reference_harness_at_least_half() {
        assert!(
            harness_pass_rate() >= 0.5,
            "Köppen harness pass rate too low: {:.0}%",
            harness_pass_rate() * 100.0
        );
    }

    #[test]
    fn tropical_rainforest_wet() {
        assert_eq!(
            KoeppenClass::classify(27.0, 26.0, 2_500.0),
            KoeppenClass::Af
        );
    }

    #[test]
    fn determinism() {
        for i in 0..500 {
            let t = (i as f32) * 0.2 - 30.0;
            let tc = t - 10.0;
            let p = (i as f32) * 12.0;
            assert_eq!(
                KoeppenClass::classify(t, tc, p),
                KoeppenClass::classify(t, tc, p)
            );
        }
    }
}
