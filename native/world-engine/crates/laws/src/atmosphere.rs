//! Atmospheric physics — lapse rate, hydrostatic pressure, scale height.

use genesis_physics::{Celsius, Kelvin, Meter, Pascal, AIR_DENSITY, GAS_R, G_EARTH, STANDARD_PRESSURE};

/// Dry adiabatic lapse rate Γ_d ≈ 9.8 °C / km — temperature decrease per
/// metre of altitude for an unsaturated parcel.
pub const DRY_ADIABATIC_LAPSE_K_PER_M: f64 = 0.009_8;

/// Saturated adiabatic lapse rate Γ_s ≈ 6.5 °C / km — what's actually
/// observed in the troposphere because of latent heat release.
pub const STANDARD_LAPSE_K_PER_M: f64 = 0.006_5;

/// Apply the standard lapse rate to translate a sea-level temperature to
/// altitude `h`.
#[inline]
#[must_use]
pub fn temperature_at_altitude(t_sea: Celsius, altitude: Meter) -> Celsius {
    Celsius(t_sea.value() - STANDARD_LAPSE_K_PER_M * altitude.value())
}

/// Hydrostatic pressure of a dry, isothermal atmosphere:
///
/// ```text
///   P(h) = P₀ · exp(-h / H),  H = R T / (M g)
/// ```
///
/// where `M` is the molar mass of dry air (0.0289644 kg/mol) and `H` is
/// the scale height. We compute `H` from the supplied `t_ref`.
#[inline]
#[must_use]
pub fn pressure_at_altitude(altitude: Meter, t_ref: Kelvin) -> Pascal {
    const MOLAR_MASS_AIR: f64 = 0.028_964_4; // kg/mol
    let scale_h = GAS_R * t_ref.value() / (MOLAR_MASS_AIR * G_EARTH.value());
    Pascal(STANDARD_PRESSURE.value() * (-altitude.value() / scale_h).exp())
}

/// Cheap dry-air density at altitude (ignores humidity). Useful as input
/// to lift / drag computations.
#[inline]
#[must_use]
pub fn air_density_at_altitude(altitude: Meter, t_ref: Kelvin) -> f64 {
    // ρ(h) = ρ₀ · exp(-h / H), same scale height as pressure.
    const MOLAR_MASS_AIR: f64 = 0.028_964_4;
    let scale_h = GAS_R * t_ref.value() / (MOLAR_MASS_AIR * G_EARTH.value());
    AIR_DENSITY * (-altitude.value() / scale_h).exp()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lapse_rate_matches_textbook() {
        let t = temperature_at_altitude(Celsius(15.0), Meter(1000.0));
        // 15 - 6.5 = 8.5 °C
        assert!((t.value() - 8.5).abs() < 0.1);
    }

    #[test]
    fn pressure_drops_with_altitude() {
        let p_sea = pressure_at_altitude(Meter(0.0), Kelvin(288.15));
        let p_5km = pressure_at_altitude(Meter(5000.0), Kelvin(288.15));
        // At 5 km, pressure should be roughly half.
        assert!(p_5km.value() < p_sea.value() * 0.6);
        assert!(p_5km.value() > p_sea.value() * 0.4);
    }
}
