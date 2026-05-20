//! Physical constants of the real universe — CODATA 2018 values.
//!
//! Naming follows the conventional physics symbols where it's unambiguous.

use crate::units::{
    JoulePerKilogramKelvin, Kelvin, Kilogram, Meter, MeterPerSecond, MeterPerSecondSquared, Pascal,
    Second, WattPerSquareMeter,
};

/// Gravitational constant `G = 6.674 30 × 10⁻¹¹ N·m²/kg²`.
pub const G: f64 = 6.674_30e-11;

/// Speed of light in vacuum.
pub const SPEED_OF_LIGHT: MeterPerSecond = MeterPerSecond(299_792_458.0);

/// Planck constant `h`.
pub const PLANCK: f64 = 6.626_070_15e-34;

/// Boltzmann constant `k_B` (J/K).
pub const BOLTZMANN: f64 = 1.380_649e-23;

/// Avogadro number `N_A` (1/mol).
pub const AVOGADRO: f64 = 6.022_140_76e23;

/// Universal gas constant `R = N_A · k_B` (J/(mol·K)).
pub const GAS_R: f64 = AVOGADRO * BOLTZMANN;

/// Stefan-Boltzmann constant σ (W/(m²·K⁴)).
pub const STEFAN_BOLTZMANN: f64 = 5.670_374_419e-8;

/// Standard gravity on Earth's surface.
pub const G_EARTH: MeterPerSecondSquared = MeterPerSecondSquared(9.806_65);

/// Mean Earth radius.
pub const EARTH_RADIUS: Meter = Meter(6_371_000.0);

/// Mean Earth mass (kg).
pub const EARTH_MASS: Kilogram = Kilogram(5.972_2e24);

/// Solar constant at top of atmosphere.
pub const SOLAR_CONSTANT: WattPerSquareMeter = WattPerSquareMeter(1_361.0);

/// Standard pressure at sea level.
pub const STANDARD_PRESSURE: Pascal = Pascal(101_325.0);

/// Triple point of water.
pub const WATER_TRIPLE: Kelvin = Kelvin(273.16);

/// Specific heat capacity of dry air at constant pressure.
pub const AIR_CP: JoulePerKilogramKelvin = JoulePerKilogramKelvin(1_005.0);

/// Specific heat capacity of liquid water.
pub const WATER_CP: JoulePerKilogramKelvin = JoulePerKilogramKelvin(4_184.0);

/// Latent heat of vaporisation of water at 100 °C (J/kg).
pub const WATER_LV: f64 = 2.257e6;

/// Latent heat of fusion of water at 0 °C (J/kg).
pub const WATER_LF: f64 = 3.34e5;

/// Sidereal day (s).
pub const SIDEREAL_DAY: Second = Second(86_164.1);

/// Tropical year (s).
pub const TROPICAL_YEAR: Second = Second(31_556_925.0);

/// Density of fresh water at 4 °C.
pub const WATER_DENSITY: f64 = 1_000.0;

/// Density of dry air at sea level, 15 °C.
pub const AIR_DENSITY: f64 = 1.225;
