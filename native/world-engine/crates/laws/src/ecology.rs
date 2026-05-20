//! Population dynamics — Lotka-Volterra, logistic growth.

/// Logistic growth tendency `dN/dt = r N (1 - N/K)`.
#[inline]
#[must_use]
pub fn logistic_tendency(n: f64, r: f64, k: f64) -> f64 {
    if k <= 0.0 {
        return -r * n; // collapse if no carrying capacity
    }
    r * n * (1.0 - n / k)
}

/// Lotka-Volterra predator-prey tendency.
///
/// Inputs: prey count `x`, predator count `y`, and coefficients
/// `(alpha, beta, delta, gamma)` :
///   dx/dt = α x − β x y
///   dy/dt = δ x y − γ y
///
/// Returns `(dx/dt, dy/dt)`.
#[inline]
#[must_use]
pub fn lotka_volterra(x: f64, y: f64, alpha: f64, beta: f64, delta: f64, gamma: f64) -> (f64, f64) {
    let dx = alpha * x - beta * x * y;
    let dy = delta * x * y - gamma * y;
    (dx, dy)
}

/// Explicit Euler step for Lotka-Volterra.
#[inline]
#[must_use]
pub fn lv_step(x: f64, y: f64, dx: f64, dy: f64, dt: f64) -> (f64, f64) {
    (x + dx * dt, y + dy * dt)
}

/// Per-capita Malthusian growth rate from doubling time.
#[inline]
#[must_use]
pub fn growth_rate_from_doubling_time(t_double_seconds: f64) -> f64 {
    if t_double_seconds <= 0.0 {
        return 0.0;
    }
    std::f64::consts::LN_2 / t_double_seconds
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lotka_volterra_oscillates() {
        // Classic textbook params: α=1.1, β=0.4, δ=0.1, γ=0.4
        let mut x = 10.0;
        let mut y = 5.0;
        let dt = 0.01;
        let mut max_x = x;
        let mut min_x = x;
        for _ in 0..2000 {
            let (dx, dy) = lotka_volterra(x, y, 1.1, 0.4, 0.1, 0.4);
            let (nx, ny) = lv_step(x, y, dx, dy, dt);
            x = nx;
            y = ny;
            if x > max_x {
                max_x = x;
            }
            if x < min_x {
                min_x = x;
            }
        }
        // Should oscillate (not flatline)
        assert!(max_x > min_x * 1.2);
    }

    #[test]
    fn logistic_saturates_near_k() {
        let n = 99.0;
        let dn = logistic_tendency(n, 0.5, 100.0);
        // Very small tendency near carrying capacity
        assert!(dn.abs() < 1.0);
    }
}
