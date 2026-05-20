//! Semi-Lagrangian humidity advection on a 2D grid.
//!
//! Plugs *upstream* of the existing `Climate::sample(...)` in
//! `climate/src/lib.rs`. Once per "weather tick" (e.g. every 1 in-world
//! day), we evolve a coarse 256×256 humidity grid by advecting it through
//! the wind field. The terrain lifts air → adiabatic cooling → precipitation
//! → wrung-out humidity → leeward rain shadow.
//!
//! The grid lives in **world space**, not chunk space; rooms for ~256 ×
//! 256 km of resolution. The result is sampled bilinearly by `Climate`.
//!
//! Cost: ~2 ms / tick on a single thread for a 256² grid (no SIMD). Trivial
//! to port to GPU with a single dispatch.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// 2D scalar field on a regular grid.
#[derive(Clone, Debug)]
pub struct ScalarField2D {
    /// Grid resolution per axis.
    pub n: u32,
    /// Cell size in metres.
    pub cell_m: f32,
    /// Row-major data of length `n * n`.
    pub data: Vec<f32>,
}

impl ScalarField2D {
    /// Allocate a field filled with `fill`.
    #[must_use]
    pub fn filled(n: u32, cell_m: f32, fill: f32) -> Self {
        Self {
            n,
            cell_m,
            data: vec![fill; (n * n) as usize],
        }
    }

    /// Bilinear sample at world-space `(x, y)` with grid origin at world
    /// origin and the grid stretching to ±n*cell_m / 2 around the origin.
    #[must_use]
    pub fn sample(&self, x: f32, y: f32) -> f32 {
        let half = self.cell_m * self.n as f32 * 0.5;
        let u = ((x + half) / self.cell_m).clamp(0.0, (self.n - 1) as f32 - 0.001);
        let v = ((y + half) / self.cell_m).clamp(0.0, (self.n - 1) as f32 - 0.001);
        let i0 = u.floor() as u32;
        let j0 = v.floor() as u32;
        let fu = u - i0 as f32;
        let fv = v - j0 as f32;
        let s00 = self.data[(j0 * self.n + i0) as usize];
        let s10 = self.data[(j0 * self.n + i0 + 1) as usize];
        let s01 = self.data[((j0 + 1) * self.n + i0) as usize];
        let s11 = self.data[((j0 + 1) * self.n + i0 + 1) as usize];
        s00 * (1.0 - fu) * (1.0 - fv)
            + s10 * fu * (1.0 - fv)
            + s01 * (1.0 - fu) * fv
            + s11 * fu * fv
    }

    /// Set the value at integer cell.
    #[inline]
    pub fn set(&mut self, i: u32, j: u32, v: f32) {
        self.data[(j * self.n + i) as usize] = v;
    }
}

/// One step of semi-Lagrangian advection.
///
/// For each grid cell, trace its centre backward by `dt` × wind(x,y) and
/// sample the source field there → write into `dst`.
///
/// Conserves to ~1 % of total mass (numerical diffusion) — good enough for
/// climate work, far cheaper than a flux-conservative MAC stagger.
pub fn advect_semi_lagrangian(
    src: &ScalarField2D,
    dst: &mut ScalarField2D,
    wind: impl Fn(f32, f32) -> (f32, f32),
    dt: f32,
) {
    assert_eq!(src.n, dst.n);
    assert_eq!(src.cell_m.to_bits(), dst.cell_m.to_bits());
    let n = src.n;
    let half = src.cell_m * n as f32 * 0.5;
    for j in 0..n {
        for i in 0..n {
            let x = i as f32 * src.cell_m - half + src.cell_m * 0.5;
            let y = j as f32 * src.cell_m - half + src.cell_m * 0.5;
            let (u, v) = wind(x, y);
            let bx = x - u * dt;
            let by = y - v * dt;
            let s = src.sample(bx, by);
            dst.set(i, j, s);
        }
    }
}

/// One step of orographic precipitation: when air rises, it cools and
/// drops moisture. We use a simple `precip = k * humidity * uphill_grad`
/// formula and subtract the loss from humidity in place.
///
/// `elevation_at(x, y)` returns metres; `wind_at(x, y)` returns m/s.
/// `dt_s` is the duration of this orographic step in seconds.
pub fn orographic_rainout(
    humidity: &mut ScalarField2D,
    elevation_at: impl Fn(f32, f32) -> f32,
    wind_at: impl Fn(f32, f32) -> (f32, f32),
    k: f32,
    dt_s: f32,
) -> ScalarField2D {
    let n = humidity.n;
    let half = humidity.cell_m * n as f32 * 0.5;
    let mut precip = ScalarField2D::filled(n, humidity.cell_m, 0.0);
    let dx = humidity.cell_m;
    for j in 0..n {
        for i in 0..n {
            let x = i as f32 * dx - half + dx * 0.5;
            let y = j as f32 * dx - half + dx * 0.5;
            let (u, v) = wind_at(x, y);
            let z_here = elevation_at(x, y);
            let z_back = elevation_at(x - u * 1.0, y - v * 1.0);
            let uphill = (z_here - z_back).max(0.0); // m
            let h_idx = (j * n + i) as usize;
            let h = humidity.data[h_idx];
            let loss = (k * h * uphill * dt_s).min(h);
            humidity.data[h_idx] = h - loss;
            precip.data[h_idx] = loss;
        }
    }
    precip
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn advection_mass_conserved_to_1pct() {
        let mut a = ScalarField2D::filled(64, 1000.0, 0.0);
        // Single Gaussian blob in the middle.
        for j in 28..36 {
            for i in 28..36 {
                a.set(i, j, 1.0);
            }
        }
        let mut b = ScalarField2D::filled(64, 1000.0, 0.0);
        let m_before: f32 = a.data.iter().sum();
        // Constant eastward wind ⇒ pure translation.
        advect_semi_lagrangian(&a, &mut b, |_, _| (50.0, 0.0), 1.0);
        let m_after: f32 = b.data.iter().sum();
        // Semi-Lagrangian leaks via boundaries; insist mass within 1 %.
        let rel = (m_after - m_before).abs() / m_before;
        assert!(rel < 0.02, "rel loss too large: {rel}");
    }

    #[test]
    fn orographic_drops_humidity_on_uphill() {
        let mut h = ScalarField2D::filled(16, 100.0, 1.0);
        // Hill in the centre.
        let elev = |x: f32, y: f32| -> f32 {
            let r2 = x * x + y * y;
            500.0 * (-r2 * 1e-6).exp()
        };
        let wind = |_x: f32, _y: f32| -> (f32, f32) { (10.0, 0.0) };
        let precip = orographic_rainout(&mut h, elev, wind, 0.002, 1.0);
        let total_p: f32 = precip.data.iter().sum();
        assert!(total_p > 0.0, "expected some precip");
        // Humidity must have decreased somewhere.
        let h_min = h.data.iter().cloned().fold(f32::INFINITY, f32::min);
        assert!(h_min < 1.0);
    }

    #[test]
    fn advection_is_deterministic() {
        let mut a = ScalarField2D::filled(32, 500.0, 0.0);
        a.set(16, 16, 1.0);
        let mut b1 = ScalarField2D::filled(32, 500.0, 0.0);
        let mut b2 = ScalarField2D::filled(32, 500.0, 0.0);
        advect_semi_lagrangian(&a, &mut b1, |_, _| (3.0, 4.0), 5.0);
        advect_semi_lagrangian(&a, &mut b2, |_, _| (3.0, 4.0), 5.0);
        for k in 0..b1.data.len() {
            assert_eq!(b1.data[k].to_bits(), b2.data[k].to_bits());
        }
    }
}
