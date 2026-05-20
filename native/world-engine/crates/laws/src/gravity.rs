//! Newtonian gravity.

use genesis_physics::{Kilogram, Meter, Newton, G};

/// Newton's law of universal gravitation between point masses `m1` and `m2`
/// separated by distance `r`:
///
/// ```text
///   F = G · m1 · m2 / r²
/// ```
#[inline]
#[must_use]
pub fn newton_force(m1: Kilogram, m2: Kilogram, r: Meter) -> Newton {
    if r.value() <= 0.0 {
        return Newton(f64::INFINITY);
    }
    Newton(G * m1.value() * m2.value() / (r.value() * r.value()))
}

/// Gravitational acceleration at distance `r` from a body of mass `m`:
///
/// ```text
///   g = G · m / r²
/// ```
#[inline]
#[must_use]
pub fn gravity_field(m: Kilogram, r: Meter) -> genesis_physics::MeterPerSecondSquared {
    if r.value() <= 0.0 {
        return genesis_physics::MeterPerSecondSquared(f64::INFINITY);
    }
    genesis_physics::MeterPerSecondSquared(G * m.value() / (r.value() * r.value()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use genesis_physics::{EARTH_MASS, EARTH_RADIUS};

    #[test]
    fn earth_surface_gravity() {
        let g = gravity_field(EARTH_MASS, EARTH_RADIUS);
        assert!((g.value() - 9.81).abs() < 0.02);
    }
}
