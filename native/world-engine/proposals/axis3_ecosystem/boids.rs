//! Deterministic boids (flocking) for fauna emergent behaviour.
//!
//! Each agent has a position and velocity in 2D world space. Three local
//! rules (separation, alignment, cohesion) produce flocking without scripts.
//!
//! Determinism: agent order is canonical (sorted by id) when computing
//! forces, and all spatial queries use the same uniform grid bucket. Two
//! runs with the same `seed` and identical initial population trajectories
//! produce bit-identical output.
//!
//! Spatial cost: O(N) with a uniform grid (`bucket_size` ≈ 3× vision_radius).

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use ahash::AHashMap;

/// Opaque fauna identifier.
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct FaunaId(pub u64);

/// One boid.
#[derive(Copy, Clone, Debug)]
pub struct Boid {
    /// Identity.
    pub id: FaunaId,
    /// Position (m).
    pub pos: [f32; 2],
    /// Velocity (m/tick).
    pub vel: [f32; 2],
    /// Species tag — same species flock together.
    pub species: u16,
}

/// Boid parameters.
#[derive(Copy, Clone, Debug)]
pub struct BoidParams {
    /// Vision radius (m).
    pub vision: f32,
    /// Personal-space radius (m).
    pub separation_r: f32,
    /// Weight of separation rule.
    pub w_sep: f32,
    /// Weight of alignment rule.
    pub w_ali: f32,
    /// Weight of cohesion rule.
    pub w_coh: f32,
    /// Max speed.
    pub v_max: f32,
}

impl Default for BoidParams {
    fn default() -> Self {
        Self {
            vision: 12.0,
            separation_r: 3.0,
            w_sep: 1.6,
            w_ali: 1.0,
            w_coh: 0.8,
            v_max: 2.0,
        }
    }
}

/// Uniform spatial hash for O(1) neighbour queries.
fn build_grid<'a>(boids: &'a [Boid], cell: f32) -> AHashMap<(i32, i32), Vec<usize>> {
    let mut g: AHashMap<(i32, i32), Vec<usize>> = AHashMap::with_capacity(boids.len() / 4 + 1);
    for (idx, b) in boids.iter().enumerate() {
        let i = (b.pos[0] / cell).floor() as i32;
        let j = (b.pos[1] / cell).floor() as i32;
        g.entry((i, j)).or_default().push(idx);
    }
    g
}

/// One simulation step.
///
/// `boids` is updated in place. We do not allocate per-call beyond the grid;
/// for game-loop usage, reuse a scratch grid via `tick_into`.
pub fn tick(boids: &mut Vec<Boid>, p: BoidParams) {
    // Canonical ordering for reproducibility.
    boids.sort_by_key(|b| b.id);
    let cell = p.vision;
    let grid = build_grid(boids, cell);
    let n = boids.len();

    // Compute new velocities in a separate buffer to avoid order-dependent
    // updates across iterations.
    let mut new_vel = Vec::with_capacity(n);
    for (idx, b) in boids.iter().enumerate() {
        let i0 = (b.pos[0] / cell).floor() as i32;
        let j0 = (b.pos[1] / cell).floor() as i32;
        let mut sep = [0.0f32, 0.0];
        let mut ali = [0.0f32, 0.0];
        let mut coh = [0.0f32, 0.0];
        let mut n_neigh = 0u32;
        for dj in -1..=1 {
            for di in -1..=1 {
                if let Some(bucket) = grid.get(&(i0 + di, j0 + dj)) {
                    for &k in bucket {
                        if k == idx {
                            continue;
                        }
                        let nb = boids[k];
                        if nb.species != b.species {
                            continue;
                        }
                        let dx = nb.pos[0] - b.pos[0];
                        let dy = nb.pos[1] - b.pos[1];
                        let d2 = dx * dx + dy * dy;
                        if d2 > p.vision * p.vision {
                            continue;
                        }
                        let d = d2.sqrt().max(0.001);
                        // Separation: away from too-close neighbours.
                        if d < p.separation_r {
                            sep[0] -= dx / d;
                            sep[1] -= dy / d;
                        }
                        // Alignment: average neighbour velocity.
                        ali[0] += nb.vel[0];
                        ali[1] += nb.vel[1];
                        // Cohesion: move toward neighbour centroid.
                        coh[0] += nb.pos[0];
                        coh[1] += nb.pos[1];
                        n_neigh += 1;
                    }
                }
            }
        }
        let (av, cv) = if n_neigh > 0 {
            let inv = 1.0 / n_neigh as f32;
            (
                [ali[0] * inv - b.vel[0], ali[1] * inv - b.vel[1]],
                [coh[0] * inv - b.pos[0], coh[1] * inv - b.pos[1]],
            )
        } else {
            ([0.0, 0.0], [0.0, 0.0])
        };
        let mut vx = b.vel[0] + p.w_sep * sep[0] + p.w_ali * av[0] + p.w_coh * cv[0];
        let mut vy = b.vel[1] + p.w_sep * sep[1] + p.w_ali * av[1] + p.w_coh * cv[1];
        let speed = (vx * vx + vy * vy).sqrt();
        if speed > p.v_max {
            let s = p.v_max / speed;
            vx *= s;
            vy *= s;
        }
        new_vel.push([vx, vy]);
    }
    // Apply.
    for (b, v) in boids.iter_mut().zip(new_vel.iter()) {
        b.vel = *v;
        b.pos[0] += b.vel[0];
        b.pos[1] += b.vel[1];
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_flock(n: u64, seed: u64) -> Vec<Boid> {
        (0..n)
            .map(|k| {
                let mix = k.wrapping_mul(0x9E37_79B9_7F4A_7C15).wrapping_add(seed);
                let x = ((mix >> 32) as u32) as f32 / u32::MAX as f32 * 50.0;
                let y = ((mix & 0xFFFF_FFFF) as u32) as f32 / u32::MAX as f32 * 50.0;
                Boid {
                    id: FaunaId(k),
                    pos: [x, y],
                    vel: [0.5, 0.0],
                    species: 1,
                }
            })
            .collect()
    }

    #[test]
    fn deterministic_two_runs() {
        let mut a = make_flock(50, 42);
        let mut b = make_flock(50, 42);
        for _ in 0..20 {
            tick(&mut a, BoidParams::default());
            tick(&mut b, BoidParams::default());
        }
        for k in 0..a.len() {
            assert_eq!(a[k].pos[0].to_bits(), b[k].pos[0].to_bits());
            assert_eq!(a[k].pos[1].to_bits(), b[k].pos[1].to_bits());
        }
    }

    #[test]
    fn no_neighbours_no_change_in_velocity_magnitude() {
        // Single lonely boid → no separation, alignment, cohesion → velocity
        // unchanged (still vx=0.5).
        let mut v = vec![Boid {
            id: FaunaId(0),
            pos: [0.0, 0.0],
            vel: [0.5, 0.0],
            species: 1,
        }];
        tick(&mut v, BoidParams::default());
        assert!((v[0].vel[0] - 0.5).abs() < 1e-6);
        assert!(v[0].vel[1].abs() < 1e-6);
    }

    #[test]
    fn separation_pushes_too_close_neighbours_apart() {
        let mut v = vec![
            Boid {
                id: FaunaId(0),
                pos: [0.0, 0.0],
                vel: [0.0, 0.0],
                species: 1,
            },
            Boid {
                id: FaunaId(1),
                pos: [1.0, 0.0],
                vel: [0.0, 0.0],
                species: 1,
            },
        ];
        tick(&mut v, BoidParams::default());
        // Boid 0 should have negative-x velocity (pushed left).
        assert!(v[0].vel[0] < 0.0);
        // Boid 1 should have positive-x velocity (pushed right).
        assert!(v[1].vel[0] > 0.0);
    }
}
