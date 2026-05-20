//! Seasonal cycle + diurnal cycle for `Climate::sample`.
//!
//! Adds two cosine terms to the existing mean-annual temperature
//! computation. Plug by extending `ClimateSample` with a season factor
//! consumed by `Climate::sample(x, y, z, ocean_distance, tick)`.
//!
//! Conventions:
//!  - 1 "tick" = the simulation tick used elsewhere (10 Hz in scaffolding,
//!    arbitrary here).
//!  - `TICKS_PER_DAY` and `TICKS_PER_YEAR` configurable; defaults pick
//!    integers so that determinism is preserved across resamples.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use core::f32::consts::TAU;

/// Configurable durations (ticks).
#[derive(Copy, Clone, Debug)]
pub struct SeasonClock {
    /// Ticks per simulated day.
    pub ticks_per_day: u32,
    /// Days per simulated year.
    pub days_per_year: u32,
    /// Axial tilt amplitude (°C peak-to-peak at the highest latitude).
    pub axial_amplitude_c: f32,
    /// Diurnal amplitude (°C peak-to-peak).
    pub diurnal_amplitude_c: f32,
}

impl Default for SeasonClock {
    fn default() -> Self {
        Self {
            ticks_per_day: 600,            // e.g. 10 Hz × 60 s/min × 60 s/min …
            days_per_year: 365,
            axial_amplitude_c: 25.0,
            diurnal_amplitude_c: 12.0,
        }
    }
}

/// Time-of-day / time-of-year sample.
#[derive(Copy, Clone, Debug)]
pub struct TimePhase {
    /// 0..1 phase along the year (0.0 = January 1).
    pub year_phase: f32,
    /// 0..1 phase along the day (0.0 = midnight).
    pub day_phase: f32,
}

impl SeasonClock {
    /// Compute the phase of the world at tick `tick`.
    #[must_use]
    pub fn phase(self, tick: u64) -> TimePhase {
        let day = (tick % self.ticks_per_day as u64) as f32 / self.ticks_per_day as f32;
        let total_days = tick / self.ticks_per_day as u64;
        let year = (total_days % self.days_per_year as u64) as f32 / self.days_per_year as f32;
        TimePhase {
            year_phase: year,
            day_phase: day,
        }
    }

    /// Seasonal temperature offset (°C) at world coord `(_x, y)` and tick.
    ///
    /// `y` is the latitudinal world coordinate. `world_radius_m` is the
    /// same constant used in `ClimateParams`.
    #[must_use]
    pub fn temperature_offset_c(self, y: f32, world_radius_m: f32, tick: u64) -> f32 {
        let phase = self.phase(tick);
        // Latitude in [0, 1].
        let lat_norm = ((y.abs()) / world_radius_m * 4.0).min(1.0);
        // Northern summer ↔ Southern winter.
        let hemi = if y >= 0.0 { 1.0 } else { -1.0 };
        // year_phase = 0 corresponds to January (Northern winter ⇒ negative offset).
        let season = -hemi * lat_norm * self.axial_amplitude_c * (TAU * phase.year_phase).cos();
        // Diurnal: warmest in mid-afternoon (day_phase ≈ 0.6).
        let diurnal = self.diurnal_amplitude_c * (TAU * (phase.day_phase - 0.6)).cos();
        season + diurnal
    }

    /// Day-light fraction in `[0, 1]` (1 = full sun at zenith).
    #[must_use]
    pub fn daylight_fraction(self, tick: u64) -> f32 {
        let phase = self.phase(tick);
        // Sinusoidal: 1 at noon, 0 at midnight, clamped to non-negative.
        ((TAU * (phase.day_phase - 0.25)).cos()).max(0.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn summer_warmer_than_winter_in_north_hemisphere() {
        let clk = SeasonClock::default();
        let tick_winter = 0u64; // jan
        let tick_summer = (clk.ticks_per_day as u64) * (clk.days_per_year as u64 / 2);
        let north_y = 4_000_000.0;
        let world_r = 6_371_000.0;
        let win = clk.temperature_offset_c(north_y, world_r, tick_winter);
        let sum = clk.temperature_offset_c(north_y, world_r, tick_summer);
        assert!(sum > win, "expected summer warmer: win={win}  sum={sum}");
    }

    #[test]
    fn hemispheres_oppose() {
        let clk = SeasonClock::default();
        let mid_year = (clk.ticks_per_day as u64) * (clk.days_per_year as u64 / 4);
        let w = 6_371_000.0;
        let n = clk.temperature_offset_c(3_000_000.0, w, mid_year);
        let s = clk.temperature_offset_c(-3_000_000.0, w, mid_year);
        assert!(n * s < 0.0, "hemispheres should have opposite signs");
    }

    #[test]
    fn daylight_peaks_around_noon() {
        let clk = SeasonClock::default();
        let noon = (clk.ticks_per_day / 2) as u64;
        let midnight = 0u64;
        let dn = clk.daylight_fraction(noon);
        let dm = clk.daylight_fraction(midnight);
        assert!(dn > dm, "noon brighter than midnight");
    }

    #[test]
    fn season_is_deterministic() {
        let clk = SeasonClock::default();
        let a = clk.temperature_offset_c(1.0e6, 6_371_000.0, 12_345);
        let b = clk.temperature_offset_c(1.0e6, 6_371_000.0, 12_345);
        assert_eq!(a.to_bits(), b.to_bits());
    }
}
