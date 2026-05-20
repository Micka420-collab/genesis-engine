//! Hydraulic + thermal erosion on a heightmap.
//!
//! Both algorithms work on a single chunk's heightmap. They consume border
//! pixels for neighbour data, so don't trust the result inside the border
//! after the call.

use crate::heightmap::Heightmap;

/// Run hydraulic ("stream-power") erosion for `iterations` passes.
///
/// Each pass picks `n_droplets` deterministic positions, drops virtual water,
/// and lets it descend the steepest gradient, carrying sediment.
///
/// `prf_seed` is folded into the droplet placement so the result is
/// reproducible given the same heightmap and seed.
pub fn hydraulic_erode(hm: &mut Heightmap, prf_seed: u64, iterations: u32, n_droplets: u32) {
    let w = hm.width as i32;
    let h = hm.height as i32;
    let max_steps = 30u32;
    let inertia = 0.05f32;
    let sediment_capacity_factor = 4.0f32;
    let min_capacity = 0.01f32;
    let erode_speed = 0.3f32;
    let deposit_speed = 0.3f32;
    let evaporate_speed = 0.01f32;
    let gravity = 4.0f32;

    for it in 0..iterations {
        for d in 0..n_droplets {
            // deterministic drop position from the seed
            let h0 = prf_seed
                .wrapping_mul(0x9E37_79B9_7F4A_7C15)
                .wrapping_add((it as u64).wrapping_mul(0xBF58_476D_1CE4_E5B9))
                .wrapping_add((d as u64).wrapping_mul(0x94D0_49BB_1331_11EB));
            let h1 = h0 ^ (h0 >> 27);
            let rx = ((h0 >> 32) as u32) as f32 / u32::MAX as f32;
            let ry = ((h1 & 0xFFFF_FFFF) as u32) as f32 / u32::MAX as f32;
            let mut px = rx * (w - 1) as f32;
            let mut py = ry * (h - 1) as f32;

            let mut dir_x = 0.0f32;
            let mut dir_y = 0.0f32;
            let mut speed = 1.0f32;
            let mut water = 1.0f32;
            let mut sediment = 0.0f32;

            for _ in 0..max_steps {
                let nx = px.floor() as i32;
                let ny = py.floor() as i32;
                if nx < 1 || ny < 1 || nx >= w - 2 || ny >= h - 2 {
                    break;
                }
                let cell_off_x = px - nx as f32;
                let cell_off_y = py - ny as f32;

                let (g_x, g_y, current_h) = gradient_and_height(hm, nx, ny, cell_off_x, cell_off_y);

                dir_x = dir_x * inertia - g_x * (1.0 - inertia);
                dir_y = dir_y * inertia - g_y * (1.0 - inertia);
                let len = (dir_x * dir_x + dir_y * dir_y).sqrt();
                if len > 1e-6 {
                    dir_x /= len;
                    dir_y /= len;
                } else {
                    break;
                }

                let nx2 = px + dir_x;
                let ny2 = py + dir_y;
                if nx2 < 1.0 || ny2 < 1.0 || nx2 >= (w - 2) as f32 || ny2 >= (h - 2) as f32 {
                    break;
                }
                let (_, _, new_h) = gradient_and_height(
                    hm,
                    nx2.floor() as i32,
                    ny2.floor() as i32,
                    nx2 - nx2.floor(),
                    ny2 - ny2.floor(),
                );
                let delta_h = new_h - current_h;

                let capacity =
                    (-delta_h * speed * water * sediment_capacity_factor).max(min_capacity);

                if sediment > capacity || delta_h > 0.0 {
                    let deposit = if delta_h > 0.0 {
                        delta_h.min(sediment)
                    } else {
                        (sediment - capacity) * deposit_speed
                    };
                    sediment -= deposit;
                    deposit_at(hm, nx, ny, cell_off_x, cell_off_y, deposit);
                } else {
                    let erode = ((capacity - sediment) * erode_speed).min(-delta_h);
                    sediment += erode;
                    erode_at(hm, nx, ny, cell_off_x, cell_off_y, erode);
                }

                let speed2 = speed * speed + delta_h * gravity;
                speed = if speed2 > 0.0 { speed2.sqrt() } else { 0.0 };
                water *= 1.0 - evaporate_speed;
                px = nx2;
                py = ny2;
            }
        }
    }
}

#[inline]
fn gradient_and_height(hm: &Heightmap, nx: i32, ny: i32, off_x: f32, off_y: f32) -> (f32, f32, f32) {
    let h_nw = hm.get_raw(nx as u32, ny as u32);
    let h_ne = hm.get_raw((nx + 1) as u32, ny as u32);
    let h_sw = hm.get_raw(nx as u32, (ny + 1) as u32);
    let h_se = hm.get_raw((nx + 1) as u32, (ny + 1) as u32);

    let g_x = (h_ne - h_nw) * (1.0 - off_y) + (h_se - h_sw) * off_y;
    let g_y = (h_sw - h_nw) * (1.0 - off_x) + (h_se - h_ne) * off_x;
    let height = h_nw * (1.0 - off_x) * (1.0 - off_y)
        + h_ne * off_x * (1.0 - off_y)
        + h_sw * (1.0 - off_x) * off_y
        + h_se * off_x * off_y;
    (g_x, g_y, height)
}

#[inline]
fn deposit_at(hm: &mut Heightmap, nx: i32, ny: i32, off_x: f32, off_y: f32, amount: f32) {
    bilinear_add(hm, nx, ny, off_x, off_y, amount);
}

#[inline]
fn erode_at(hm: &mut Heightmap, nx: i32, ny: i32, off_x: f32, off_y: f32, amount: f32) {
    bilinear_add(hm, nx, ny, off_x, off_y, -amount);
}

#[inline]
fn bilinear_add(hm: &mut Heightmap, nx: i32, ny: i32, off_x: f32, off_y: f32, amount: f32) {
    let w00 = (1.0 - off_x) * (1.0 - off_y);
    let w10 = off_x * (1.0 - off_y);
    let w01 = (1.0 - off_x) * off_y;
    let w11 = off_x * off_y;
    let i = nx as u32;
    let j = ny as u32;
    let s0 = hm.get_raw(i, j) + amount * w00;
    let s1 = hm.get_raw(i + 1, j) + amount * w10;
    let s2 = hm.get_raw(i, j + 1) + amount * w01;
    let s3 = hm.get_raw(i + 1, j + 1) + amount * w11;
    hm.set_raw(i, j, s0);
    hm.set_raw(i + 1, j, s1);
    hm.set_raw(i, j + 1, s2);
    hm.set_raw(i + 1, j + 1, s3);
}

/// Thermal erosion — smooths slopes steeper than `talus_angle` (radians).
pub fn thermal_erode(hm: &mut Heightmap, iterations: u32, talus_angle: f32) {
    let w = hm.width;
    let h = hm.height;
    let cell_size = 1.0_f32;
    let max_dh = talus_angle.tan() * cell_size;
    let factor = 0.5;

    for _ in 0..iterations {
        // Pass 1: compute deltas (no aliasing on the buffer we'll modify).
        let mut delta = vec![0.0f32; (w * h) as usize];
        for j in 1..(h - 1) {
            for i in 1..(w - 1) {
                let c = hm.get_raw(i, j);
                let mut total_excess = 0.0;
                let mut neighbours = [(0u32, 0u32, 0.0f32); 4];
                let mut n_count = 0;
                for (di, dj) in [(1i32, 0i32), (-1, 0), (0, 1), (0, -1)] {
                    let ni = (i as i32 + di) as u32;
                    let nj = (j as i32 + dj) as u32;
                    let v = hm.get_raw(ni, nj);
                    let diff = c - v;
                    if diff > max_dh {
                        let excess = diff - max_dh;
                        neighbours[n_count] = (ni, nj, excess);
                        total_excess += excess;
                        n_count += 1;
                    }
                }
                if total_excess > 0.0 {
                    for k in 0..n_count {
                        let (ni, nj, excess) = neighbours[k];
                        let move_amount = excess * factor;
                        let idx = (nj * w + ni) as usize;
                        delta[idx] += move_amount;
                        let center_idx = (j * w + i) as usize;
                        delta[center_idx] -= move_amount;
                    }
                }
            }
        }
        // Pass 2: apply
        for k in 0..(w * h) as usize {
            hm.data[k] += delta[k];
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::heightmap::{generate, TerrainParams};
    use blake3::Hasher;
    use genesis_core::Prf;

    fn hash_hm(hm: &Heightmap) -> [u8; 32] {
        let mut h = Hasher::new();
        for v in &hm.data {
            h.update(&v.to_le_bytes());
        }
        *h.finalize().as_bytes()
    }

    #[test]
    fn erosion_is_deterministic() {
        let prf = Prf::new(42);
        let p = TerrainParams::default();
        let mut a = generate(prf, 0, 0, p);
        let mut b = generate(prf, 0, 0, p);
        hydraulic_erode(&mut a, 12345, 4, 200);
        hydraulic_erode(&mut b, 12345, 4, 200);
        assert_eq!(hash_hm(&a), hash_hm(&b));
    }

    #[test]
    fn thermal_smooths() {
        let prf = Prf::new(1);
        let p = TerrainParams::default();
        let mut hm = generate(prf, 0, 0, p);
        let before_variance = variance(&hm.data);
        thermal_erode(&mut hm, 4, 0.7);
        let after_variance = variance(&hm.data);
        assert!(after_variance <= before_variance);
    }

    fn variance(d: &[f32]) -> f32 {
        let n = d.len() as f32;
        let mean = d.iter().sum::<f32>() / n;
        d.iter().map(|v| (v - mean).powi(2)).sum::<f32>() / n
    }
}
