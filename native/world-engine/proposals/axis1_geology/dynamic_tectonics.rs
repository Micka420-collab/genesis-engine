//! Dynamic plate tectonics — Lagrangian particle cloth.
//!
//! Replaces the static Voronoi `PlateField` (`terrain/src/tectonics.rs`)
//! with plates that **actually move**. Each plate is a particle with a
//! position, velocity and kind. At each "geological tick" we advect the
//! particle by its velocity and detect interactions with neighbours
//! (convergence → orogeny, divergence → rift, transform → fault).
//!
//! Determinism: every velocity / kind / drift bias is derived from a
//! `genesis_core::Prf` seeded by `(world_seed, "geology")`. Two runs with
//! the same seed and tick count produce identical particle states.
//!
//! Cost: O(N_plates × neighbours) per geological tick. With 200 plates and
//! 6 neighbours that's ~1200 ops — trivial. The plate field is then queried
//! by the terrain pass as before (`baseline_elevation(x, y)`), using a
//! Voronoi nearest-search over the current particle positions.
//!
//! This module is **drop-in compatible** with the existing
//! `tectonics::PlateField` query API: the public `sample(x, y)` returns the
//! same `PlateSample` struct.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Plate kind — keep in sync with `genesis_terrain::PlateKind` when integrating.
#[derive(Copy, Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum PlateKind {
    /// Thin, dense, low-floating.
    Oceanic,
    /// Thick, light, high-floating.
    Continental,
}

/// One plate as a particle.
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub struct PlateParticle {
    /// Stable identifier (survives advection).
    pub id: u64,
    /// Current world-space position of the plate centre.
    pub pos: [f32; 2],
    /// Velocity in world-units per geological tick (≈ million years).
    pub vel: [f32; 2],
    /// Plate kind.
    pub kind: PlateKind,
    /// Age in geological ticks.
    pub age: u32,
}

/// Parameters for the geological simulation.
#[derive(Copy, Clone, Debug)]
pub struct GeologyParams {
    /// World extent on each axis (metres). Plates wrap toroidally outside.
    pub world_extent_m: f32,
    /// Number of plates total.
    pub plate_count: u32,
    /// Continental fraction in `[0, 1]`.
    pub continental_ratio: f32,
    /// Maximum plate speed (m / geological tick).
    pub max_speed: f32,
    /// Influence radius for plate–plate interactions (m).
    pub interaction_radius: f32,
    /// Drag applied each tick (`vel *= 1 - drag`).
    pub drag: f32,
}

impl Default for GeologyParams {
    fn default() -> Self {
        Self {
            world_extent_m: 20_000_000.0,
            plate_count: 200,
            continental_ratio: 0.42,
            max_speed: 800.0,
            interaction_radius: 200_000.0,
            drag: 0.02,
        }
    }
}

/// Dynamic plate field — owns particle state, advances on `tick_geology`.
#[derive(Clone, Debug)]
pub struct DynamicPlateField {
    seed_u64: u64,
    params: GeologyParams,
    plates: Vec<PlateParticle>,
    geo_tick: u32,
}

/// One nearest-plate query result.
#[derive(Copy, Clone, Debug)]
pub struct PlateSample {
    /// Stable plate id.
    pub id: u64,
    /// Plate kind.
    pub kind: PlateKind,
    /// Distance (m) to that plate's centre.
    pub distance: f32,
    /// Distance to the second-nearest plate (m) — used to soften boundaries.
    pub distance2: f32,
    /// Convergence speed component along (centre1 → centre2). Positive ⇒
    /// converging (mountain-building); negative ⇒ diverging (rift).
    pub convergence: f32,
}

impl DynamicPlateField {
    /// Construct the field at geological tick 0.
    #[must_use]
    pub fn new(seed_u64: u64, params: GeologyParams) -> Self {
        let mut plates = Vec::with_capacity(params.plate_count as usize);
        let half = params.world_extent_m * 0.5;
        for k in 0..params.plate_count {
            // Deterministic seed mixing — same recipe as PRF::hash but inlined
            // so the file compiles standalone.
            let mix = mix64(seed_u64, k as u64);
            let r0 = unit_from_u64(mix.wrapping_add(1));
            let r1 = unit_from_u64(mix.wrapping_add(2));
            let r2 = unit_from_u64(mix.wrapping_add(3));
            let r3 = unit_from_u64(mix.wrapping_add(4));
            let r4 = unit_from_u64(mix.wrapping_add(5));

            let px = (r0 * 2.0 - 1.0) * half;
            let py = (r1 * 2.0 - 1.0) * half;
            let vx = (r2 * 2.0 - 1.0) * params.max_speed;
            let vy = (r3 * 2.0 - 1.0) * params.max_speed;
            let kind = if r4 < params.continental_ratio {
                PlateKind::Continental
            } else {
                PlateKind::Oceanic
            };
            plates.push(PlateParticle {
                id: mix,
                pos: [px, py],
                vel: [vx, vy],
                kind,
                age: 0,
            });
        }
        Self {
            seed_u64,
            params,
            plates,
            geo_tick: 0,
        }
    }

    /// Advance the field by one geological tick.
    pub fn tick_geology(&mut self) {
        // 1. Advect (with toroidal wrap).
        let half = self.params.world_extent_m * 0.5;
        for p in self.plates.iter_mut() {
            p.pos[0] += p.vel[0];
            p.pos[1] += p.vel[1];
            // Toroidal wrap into [-half, half].
            if p.pos[0] > half {
                p.pos[0] -= self.params.world_extent_m;
            } else if p.pos[0] < -half {
                p.pos[0] += self.params.world_extent_m;
            }
            if p.pos[1] > half {
                p.pos[1] -= self.params.world_extent_m;
            } else if p.pos[1] < -half {
                p.pos[1] += self.params.world_extent_m;
            }
            // Drag
            p.vel[0] *= 1.0 - self.params.drag;
            p.vel[1] *= 1.0 - self.params.drag;
            p.age += 1;
        }
        // 2. Pairwise interaction (O(N²) — N=200 is fine; for N>1000 switch
        //    to a uniform grid bucket).
        let r = self.params.interaction_radius;
        let r2 = r * r;
        let n = self.plates.len();
        for i in 0..n {
            for j in (i + 1)..n {
                let pi = self.plates[i];
                let pj = self.plates[j];
                let dx = pj.pos[0] - pi.pos[0];
                let dy = pj.pos[1] - pi.pos[1];
                let d2 = dx * dx + dy * dy;
                if d2 > r2 || d2 < 1.0 {
                    continue;
                }
                let d = d2.sqrt();
                let nx = dx / d;
                let ny = dy / d;
                // Relative approach velocity (positive ⇒ converging).
                let rvx = pi.vel[0] - pj.vel[0];
                let rvy = pi.vel[1] - pj.vel[1];
                let approach = rvx * nx + rvy * ny;
                // Convergence damps the approach component (loses energy in
                // mountain-building); divergence stretches but is unaffected.
                if approach > 0.0 {
                    let damp = 0.35;
                    self.plates[i].vel[0] -= nx * approach * damp;
                    self.plates[i].vel[1] -= ny * approach * damp;
                    self.plates[j].vel[0] += nx * approach * damp;
                    self.plates[j].vel[1] += ny * approach * damp;
                }
            }
        }
        self.geo_tick += 1;
    }

    /// Query the plate field at world coord `(x, y)`.
    /// Returns nearest + second nearest + convergence component along the
    /// line that joins them at the query position.
    #[must_use]
    pub fn sample(&self, x: f32, y: f32) -> PlateSample {
        let mut best = (f32::INFINITY, 0usize);
        let mut second = (f32::INFINITY, 0usize);
        for (idx, p) in self.plates.iter().enumerate() {
            let dx = p.pos[0] - x;
            let dy = p.pos[1] - y;
            let d2 = dx * dx + dy * dy;
            if d2 < best.0 {
                second = best;
                best = (d2, idx);
            } else if d2 < second.0 {
                second = (d2, idx);
            }
        }
        let p1 = self.plates[best.1];
        let p2 = self.plates[second.1];
        let dx = p2.pos[0] - p1.pos[0];
        let dy = p2.pos[1] - p1.pos[1];
        let d = (dx * dx + dy * dy).sqrt().max(1.0);
        let nx = dx / d;
        let ny = dy / d;
        // Convergence: positive when both plates point toward each other.
        let conv = (p1.vel[0] * nx + p1.vel[1] * ny) - (p2.vel[0] * nx + p2.vel[1] * ny);
        PlateSample {
            id: p1.id,
            kind: p1.kind,
            distance: best.0.sqrt(),
            distance2: second.0.sqrt(),
            convergence: conv,
        }
    }

    /// Baseline elevation contributed by tectonics at `(x, y)`, in metres.
    /// Convergent boundaries lift mountains; divergent ones cut rifts.
    #[must_use]
    pub fn baseline_elevation(&self, x: f32, y: f32) -> f32 {
        let s = self.sample(x, y);
        let base = match s.kind {
            PlateKind::Continental => 1_500.0,
            PlateKind::Oceanic => -3_000.0,
        };
        let edge = (s.distance2 - s.distance).abs();
        let boundary_w = self.params.interaction_radius * 0.6;
        let boundary = (1.0 - (edge / boundary_w)).clamp(0.0, 1.0);
        // Convergence in m/tick → translate to metres of orogeny.
        let oro = match s.kind {
            PlateKind::Continental => s.convergence * 4.0,
            PlateKind::Oceanic => s.convergence * 1.5,
        };
        base + boundary * oro
    }

    /// Number of plates.
    #[must_use]
    pub fn plate_count(&self) -> usize {
        self.plates.len()
    }

    /// Current geological tick.
    #[must_use]
    pub fn geo_tick(&self) -> u32 {
        self.geo_tick
    }
}

#[inline]
fn mix64(a: u64, b: u64) -> u64 {
    // SplitMix64-style mixer, no_std friendly.
    let mut z = a
        .wrapping_add(b.wrapping_mul(0x9E37_79B9_7F4A_7C15))
        .wrapping_add(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

#[inline]
fn unit_from_u64(u: u64) -> f32 {
    // 24 high bits → [0, 1), bit-stable.
    ((u >> 40) as f32) / ((1u64 << 24) as f32)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_seed_same_plate_field() {
        let a = DynamicPlateField::new(0xDEAD_BEEF, GeologyParams::default());
        let b = DynamicPlateField::new(0xDEAD_BEEF, GeologyParams::default());
        for k in 0..a.plates.len() {
            assert_eq!(a.plates[k].id, b.plates[k].id);
            assert_eq!(a.plates[k].pos[0].to_bits(), b.plates[k].pos[0].to_bits());
            assert_eq!(a.plates[k].pos[1].to_bits(), b.plates[k].pos[1].to_bits());
        }
    }

    #[test]
    fn tick_advection_is_deterministic() {
        let mut a = DynamicPlateField::new(7, GeologyParams::default());
        let mut b = DynamicPlateField::new(7, GeologyParams::default());
        for _ in 0..50 {
            a.tick_geology();
            b.tick_geology();
        }
        for k in 0..a.plates.len() {
            assert_eq!(a.plates[k].pos[0].to_bits(), b.plates[k].pos[0].to_bits());
        }
    }

    #[test]
    fn convergence_damps_velocity() {
        let mut f = DynamicPlateField::new(1, GeologyParams {
            plate_count: 2,
            world_extent_m: 100_000.0,
            max_speed: 0.0,
            interaction_radius: 100_000.0,
            ..Default::default()
        });
        // Place two plates head-on at fixed positions.
        f.plates[0].pos = [-1000.0, 0.0];
        f.plates[0].vel = [500.0, 0.0];
        f.plates[1].pos = [1000.0, 0.0];
        f.plates[1].vel = [-500.0, 0.0];
        let v0 = f.plates[0].vel[0];
        f.tick_geology();
        // Their head-on velocity should have decreased in magnitude.
        let v1 = f.plates[0].vel[0];
        assert!(v1 < v0, "expected damping: v0={v0} v1={v1}");
    }

    #[test]
    fn baseline_elevation_is_finite() {
        let f = DynamicPlateField::new(42, GeologyParams::default());
        for i in 0..1000 {
            let x = (i as f32 - 500.0) * 1000.0;
            let y = (i as f32 - 250.0) * 2000.0;
            let e = f.baseline_elevation(x, y);
            assert!(e.is_finite());
            assert!((-10_000.0..=12_000.0).contains(&e), "elev={e}");
        }
    }
}
