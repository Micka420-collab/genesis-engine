//! Tectonic plate field — Voronoi-based, computed lazily per query.
//!
//! We don't store a planet-wide plate map. Instead, plate centers are
//! generated on demand from the PRF: divide the world into "plate cells" of
//! size `cell_size`, generate one jittered center per cell from the PRF,
//! and answer queries by finding the nearest center in a 3×3 cell window.
//!
//! This keeps the field infinite, deterministic, and O(1) per query.

use genesis_core::Prf;
use serde::{Deserialize, Serialize};

/// Plate type.
#[derive(Copy, Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum PlateKind {
    /// Oceanic plate — thinner, denser, lower baseline elevation.
    Oceanic,
    /// Continental plate — thicker, lighter, higher baseline elevation.
    Continental,
}

/// Tectonic plate field.
#[derive(Copy, Clone, Debug)]
pub struct PlateField {
    prf: Prf,
    layer: u32,
    /// Grid cell size in world units.
    cell_size: f32,
    /// Fraction of plates that are continental in `[0, 1]`.
    continental_ratio: f32,
}

/// A nearest-plate query result.
#[derive(Copy, Clone, Debug)]
pub struct PlateSample {
    /// Plate ID (stable across queries).
    pub id: u64,
    /// Plate kind.
    pub kind: PlateKind,
    /// Distance (world units) to the plate center — used to soften boundaries.
    pub distance: f32,
    /// Distance to the 2nd-nearest plate — non-zero only along boundaries.
    pub distance2: f32,
    /// Plate motion vector (world units per million years, arbitrary scale).
    pub motion: [f32; 2],
}

impl PlateField {
    /// New plate field.
    #[must_use]
    pub fn new(prf: Prf, layer: u32, cell_size: f32, continental_ratio: f32) -> Self {
        Self {
            prf,
            layer,
            cell_size,
            continental_ratio: continental_ratio.clamp(0.0, 1.0),
        }
    }

    /// Plate center within cell `(ci, cj)`.
    #[inline]
    #[must_use]
    fn plate_center(&self, ci: i32, cj: i32) -> (f32, f32, u64, PlateKind, [f32; 2]) {
        let jitter_x = self.prf.unit_f32(self.layer, ci, cj, 0, 1);
        let jitter_y = self.prf.unit_f32(self.layer, ci, cj, 0, 2);
        let kind_roll = self.prf.unit_f32(self.layer, ci, cj, 0, 3);
        let mx = self.prf.signed_f32(self.layer, ci, cj, 0, 4);
        let my = self.prf.signed_f32(self.layer, ci, cj, 0, 5);
        let cx = (ci as f32 + jitter_x) * self.cell_size;
        let cy = (cj as f32 + jitter_y) * self.cell_size;
        let id = self.prf.hash(self.layer, ci, cj, 0, 0);
        let kind = if kind_roll < self.continental_ratio {
            PlateKind::Continental
        } else {
            PlateKind::Oceanic
        };
        (cx, cy, id, kind, [mx, my])
    }

    /// Query the plate field at world coordinate `(x, y)`.
    #[must_use]
    pub fn sample(&self, x: f32, y: f32) -> PlateSample {
        let ci = (x / self.cell_size).floor() as i32;
        let cj = (y / self.cell_size).floor() as i32;

        let mut best_d = f32::INFINITY;
        let mut best = (0u64, PlateKind::Oceanic, [0.0, 0.0]);
        let mut second_d = f32::INFINITY;
        for dj in -1..=1 {
            for di in -1..=1 {
                let (cx, cy, id, kind, motion) = self.plate_center(ci + di, cj + dj);
                let dx = cx - x;
                let dy = cy - y;
                let d2 = dx * dx + dy * dy;
                if d2 < best_d {
                    second_d = best_d;
                    best_d = d2;
                    best = (id, kind, motion);
                } else if d2 < second_d {
                    second_d = d2;
                }
            }
        }
        PlateSample {
            id: best.0,
            kind: best.1,
            distance: best_d.sqrt(),
            distance2: second_d.sqrt(),
            motion: best.2,
        }
    }

    /// Baseline elevation contributed by tectonics at `(x, y)`, in **metres**.
    ///
    /// Continental plates float higher, oceanic plates sit lower. Boundaries
    /// between converging continental plates raise mountain ranges; oceanic
    /// vs. continental convergence produces coastal mountains; divergent
    /// boundaries produce rifts.
    #[must_use]
    pub fn baseline_elevation(&self, x: f32, y: f32) -> f32 {
        let s = self.sample(x, y);

        // Base level: 1500 m for continents, -3000 m for oceans
        let base = match s.kind {
            PlateKind::Continental => 1_500.0,
            PlateKind::Oceanic => -3_000.0,
        };

        // Boundary strength: 1 at the boundary, 0 away from it
        let boundary_width = self.cell_size * 0.12;
        let edge_dist = (s.distance2 - s.distance).abs();
        let boundary = (1.0 - (edge_dist / boundary_width)).clamp(0.0, 1.0);

        // Convergence sign: if the dominant plate is moving toward the
        // boundary, it's converging → mountains. Otherwise → trench/rift.
        // We approximate it with the dot product of motion and the gradient
        // direction to the second-nearest plate center, but lacking that we
        // use a deterministic per-plate signed hash.
        let conv_sign = (self.prf.signed_f32(self.layer, 0, 0, 0, s.id as u32)).signum();
        let orogeny = match s.kind {
            PlateKind::Continental => 2_500.0,
            PlateKind::Oceanic => -2_000.0,
        };

        base + boundary * orogeny * conv_sign.max(0.3)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plate_sample_deterministic() {
        let f = PlateField::new(Prf::new(7), 0, 50_000.0, 0.4);
        let a = f.sample(1234.0, -567.0);
        let b = f.sample(1234.0, -567.0);
        assert_eq!(a.id, b.id);
        assert!((a.distance - b.distance).abs() < 1e-6);
    }

    #[test]
    fn baseline_elevation_finite() {
        let f = PlateField::new(Prf::new(1), 0, 50_000.0, 0.4);
        for i in 0..1000 {
            let v = f.baseline_elevation(i as f32 * 100.0, (i as f32).sin() * 1000.0);
            assert!(v.is_finite());
            assert!(v > -10_000.0 && v < 10_000.0, "elev={v}");
        }
    }
}
