//! Hydrology — Saint-Venant (river) + Darcy (groundwater) approximations.

use genesis_physics::{Meter, MeterPerSecond, Pascal, Second};

/// Manning's equation for flow velocity in an open channel:
///
/// ```text
///   v = (1/n) · R^{2/3} · S^{1/2}
/// ```
///
/// - `roughness_n` (Manning's n, ~0.03 for natural rivers)
/// - `hydraulic_radius`: cross-section area / wetted perimeter (m)
/// - `slope`: water surface slope (m/m, dimensionless)
#[inline]
#[must_use]
pub fn manning_velocity(roughness_n: f64, hydraulic_radius: Meter, slope: f64) -> MeterPerSecond {
    if roughness_n <= 0.0 || slope < 0.0 {
        return MeterPerSecond(0.0);
    }
    let v = (1.0 / roughness_n) * hydraulic_radius.value().powf(2.0 / 3.0) * slope.sqrt();
    MeterPerSecond(v)
}

/// Discharge `Q = v · A` for an open channel.
#[inline]
#[must_use]
pub fn discharge(velocity: MeterPerSecond, area: genesis_physics::SquareMeter) -> f64 {
    velocity.value() * area.value()
}

/// Darcy flux through a saturated porous medium:
///
/// ```text
///   q = -K · ∂h/∂x
/// ```
///
/// - `hydraulic_conductivity_K` in m/s (~10⁻⁵ for sand, 10⁻⁹ for clay)
/// - `head_gradient`: ∂h/∂x in m/m
#[inline]
#[must_use]
pub fn darcy_flux(hydraulic_conductivity_k: f64, head_gradient: f64) -> MeterPerSecond {
    MeterPerSecond(-hydraulic_conductivity_k * head_gradient)
}

/// Capillary pressure under simplified Young-Laplace for water in a tube.
#[inline]
#[must_use]
pub fn capillary_pressure(surface_tension_n_per_m: f64, contact_angle_rad: f64, radius: Meter) -> Pascal {
    if radius.value() <= 0.0 {
        return Pascal(0.0);
    }
    Pascal(2.0 * surface_tension_n_per_m * contact_angle_rad.cos() / radius.value())
}

/// Saint-Venant 1D shallow-water tendencies for a single channel cell.
///
/// Returns `(dh/dt, dv/dt)` for the water height and depth-averaged velocity.
/// Inputs are dimensional. This is the bare minimum to step a 1D river —
/// real solvers add a friction term and use a Riemann solver at cell faces.
#[inline]
#[must_use]
pub fn saint_venant_tendency(
    h: Meter,
    v: MeterPerSecond,
    dh_dx: f64,
    dv_dx: f64,
    bed_slope: f64,
    g: genesis_physics::MeterPerSecondSquared,
) -> (Meter, MeterPerSecond) {
    let dh_dt = Meter(-(v.value() * dh_dx + h.value() * dv_dx));
    let dv_dt = MeterPerSecond(-(v.value() * dv_dx + g.value() * (dh_dx - bed_slope)));
    (dh_dt, dv_dt)
}

/// Integrate one explicit Euler step of Saint-Venant.
#[inline]
#[must_use]
pub fn saint_venant_step(
    h: Meter,
    v: MeterPerSecond,
    dh_dt: Meter,
    dv_dt: MeterPerSecond,
    dt: Second,
) -> (Meter, MeterPerSecond) {
    (
        Meter(h.value() + dh_dt.value() * dt.value()),
        MeterPerSecond(v.value() + dv_dt.value() * dt.value()),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn manning_natural_river() {
        // n=0.035, R=1.5 m, S=0.001 → v ≈ 1.18 m/s (textbook-ish)
        let v = manning_velocity(0.035, Meter(1.5), 0.001);
        assert!(v.value() > 1.0 && v.value() < 1.5);
    }

    #[test]
    fn darcy_zero_gradient_no_flow() {
        let q = darcy_flux(1e-5, 0.0);
        assert!(q.value().abs() < 1e-20);
    }
}
