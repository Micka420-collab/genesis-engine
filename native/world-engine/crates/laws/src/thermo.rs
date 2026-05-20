//! Thermodynamics — Stefan-Boltzmann, blackbody, sensible heat.

use genesis_physics::{Kelvin, WattPerSquareMeter, STEFAN_BOLTZMANN};

/// Stefan-Boltzmann radiated power per unit area for a perfect blackbody at
/// temperature `T`:
///
/// ```text
///   j = σ · T⁴
/// ```
#[inline]
#[must_use]
pub fn blackbody_emittance(t: Kelvin) -> WattPerSquareMeter {
    let t4 = t.value().powi(4);
    WattPerSquareMeter(STEFAN_BOLTZMANN * t4)
}

/// Greybody emittance: `j = ε · σ · T⁴` with emissivity `ε ∈ [0, 1]`.
#[inline]
#[must_use]
pub fn greybody_emittance(t: Kelvin, emissivity: f64) -> WattPerSquareMeter {
    let e = emissivity.clamp(0.0, 1.0);
    blackbody_emittance(t) * e
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sun_emittance_close_to_known() {
        // T_sun ≈ 5778 K → j ≈ 6.32 × 10⁷ W/m²
        let j = blackbody_emittance(Kelvin(5778.0));
        let expected = 6.32e7;
        let rel = (j.value() - expected).abs() / expected;
        assert!(rel < 0.02, "got {} vs {}", j.value(), expected);
    }

    #[test]
    fn earth_emittance_close_to_known() {
        // T_eff_earth ≈ 255 K → j ≈ 239 W/m²
        let j = blackbody_emittance(Kelvin(255.0));
        assert!((j.value() - 239.0).abs() < 5.0);
    }
}
