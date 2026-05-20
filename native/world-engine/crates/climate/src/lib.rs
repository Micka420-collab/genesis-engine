//! genesis-climate — temperature, humidity, wind.
//!
//! Cheap, deterministic, gradient-friendly. Does NOT simulate fluid dynamics
//! — instead, gives plausible static maps that are stable over a year and
//! good enough to drive biome classification.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use genesis_core::Prf;
use genesis_noise::{fbm2, FbmParams};
use serde::{Deserialize, Serialize};

/// Climate model parameters.
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub struct ClimateParams {
    /// Equatorial mean temperature at sea level (°C).
    pub t_equator: f32,
    /// Polar mean temperature at sea level (°C).
    pub t_pole: f32,
    /// World latitude span — full world height in metres maps to ±90°.
    pub world_radius_m: f32,
    /// Lapse rate (°C per metre of altitude; typical wet adiabatic ≈ 0.0065).
    pub lapse_rate: f32,
    /// Mean ocean humidity output (0..1).
    pub ocean_humidity: f32,
    /// Continentality coefficient — higher → drier interiors.
    pub continentality: f32,
    /// Decay distance for ocean-borne humidity (m).
    pub humidity_decay_m: f32,
}

impl Default for ClimateParams {
    fn default() -> Self {
        Self {
            t_equator: 28.0,
            t_pole: -25.0,
            world_radius_m: 6_371_000.0,
            lapse_rate: 0.0065,
            ocean_humidity: 0.95,
            continentality: 0.6,
            humidity_decay_m: 250_000.0,
        }
    }
}

/// Climate sample at a point.
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub struct ClimateSample {
    /// Mean annual surface temperature in °C.
    pub temperature_c: f32,
    /// Relative humidity in `[0, 1]`.
    pub humidity: f32,
    /// Wind vector in m/s (geographic prevailing).
    pub wind_ms: [f32; 2],
}

/// Climate engine — takes a PRF + params, returns a sample at any coord.
#[derive(Copy, Clone, Debug)]
pub struct Climate {
    prf: Prf,
    params: ClimateParams,
}

impl Climate {
    /// New climate engine.
    #[must_use]
    pub const fn new(prf: Prf, params: ClimateParams) -> Self {
        Self { prf, params }
    }

    /// Sample climate at world-space `(x, y)` with elevation `z_m` (metres).
    ///
    /// `ocean_distance_m` is the geodesic distance to the nearest ocean
    /// pixel; if unknown, pass `None` → we approximate with a noise field.
    #[must_use]
    pub fn sample(&self, x: f32, y: f32, z_m: f32, ocean_distance_m: Option<f32>) -> ClimateSample {
        let p = &self.params;

        // Latitude proxy: |y| / world_radius maps to [0, 1] over a quarter
        // turn. We clamp so polar regions saturate.
        let lat_norm = ((y.abs()) / p.world_radius_m * 4.0).min(1.0);
        // Cosine falloff gives the classic mid-latitude curve
        let lat_factor = (1.0 - lat_norm).max(0.0);
        let sea_level_temp = p.t_pole + (p.t_equator - p.t_pole) * lat_factor;

        // Altitude correction
        let altitude_loss = (z_m.max(0.0)) * p.lapse_rate;
        let temperature_c = sea_level_temp - altitude_loss
            + 1.5 * fbm2(self.prf, 0xC11A_4A11, x, y, FbmParams {
                octaves: 3,
                lacunarity: 2.0,
                gain: 0.5,
                frequency: 1.0 / 400_000.0,
            });

        // Humidity: distance to ocean × continentality, plus noise
        let dist = ocean_distance_m.unwrap_or_else(|| {
            // Cheap approximation: use a different FBM channel as a stand-in
            (0.5
                + 0.5
                    * fbm2(self.prf, 0xC11A_AAAA, x, y, FbmParams {
                        octaves: 4,
                        lacunarity: 2.0,
                        gain: 0.5,
                        frequency: 1.0 / 600_000.0,
                    }))
                * p.humidity_decay_m
                * 1.5
        });
        let decay = (-dist / p.humidity_decay_m).exp();
        let base_hum = p.ocean_humidity * decay
            + 0.2 * (1.0 - p.continentality);
        let humidity_noise = 0.15
            * fbm2(self.prf, 0xC11A_BBBB, x, y, FbmParams {
                octaves: 3,
                lacunarity: 2.0,
                gain: 0.5,
                frequency: 1.0 / 200_000.0,
            });
        let humidity = (base_hum + humidity_noise).clamp(0.0, 1.0);

        // Prevailing wind — three-cell model approximation:
        //   - Trade winds: 0–30° → easterlies
        //   - Westerlies: 30–60°
        //   - Polar easterlies: 60–90°
        // Sign of y → hemisphere.
        let lat_deg = lat_norm * 90.0;
        let hemi = if y >= 0.0 { 1.0 } else { -1.0 };
        let (u, v) = if lat_deg < 30.0 {
            (-6.0, -1.5 * hemi)
        } else if lat_deg < 60.0 {
            (8.0, 1.0 * hemi)
        } else {
            (-3.0, -0.5 * hemi)
        };

        ClimateSample {
            temperature_c,
            humidity,
            wind_ms: [u, v],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn temperature_decreases_with_altitude() {
        let c = Climate::new(Prf::new(0), ClimateParams::default());
        let a = c.sample(0.0, 0.0, 0.0, Some(0.0)).temperature_c;
        let b = c.sample(0.0, 0.0, 3000.0, Some(0.0)).temperature_c;
        assert!(b < a);
    }

    #[test]
    fn temperature_decreases_toward_poles() {
        let c = Climate::new(Prf::new(0), ClimateParams::default());
        let eq = c.sample(0.0, 0.0, 0.0, Some(0.0)).temperature_c;
        let pole = c
            .sample(0.0, 5_000_000.0, 0.0, Some(0.0))
            .temperature_c;
        assert!(pole < eq);
    }

    #[test]
    fn humidity_drops_with_distance_from_ocean() {
        let c = Climate::new(Prf::new(0), ClimateParams::default());
        let coastal = c.sample(0.0, 0.0, 0.0, Some(0.0)).humidity;
        let inland = c.sample(0.0, 0.0, 0.0, Some(500_000.0)).humidity;
        assert!(inland < coastal);
    }

    #[test]
    fn climate_is_deterministic() {
        let c = Climate::new(Prf::new(123), ClimateParams::default());
        let a = c.sample(42.0, 17.0, 500.0, Some(10_000.0));
        let b = c.sample(42.0, 17.0, 500.0, Some(10_000.0));
        assert_eq!(a.temperature_c.to_bits(), b.temperature_c.to_bits());
        assert_eq!(a.humidity.to_bits(), b.humidity.to_bits());
    }
}
