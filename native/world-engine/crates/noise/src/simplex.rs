//! 2D / 3D simplex noise — OpenSimplex2-style, single skewed lattice.
//!
//! The function is keyed by a `Prf` for determinism. This is **not** the
//! fastest possible simplex impl — for hot paths use the FastNoise2 backend
//! (feature `fastnoise2`). It IS correct, allocation-free, and produces
//! values in roughly `[-1, 1]`.

use genesis_core::Prf;

const F2: f32 = 0.366_025_4; // (sqrt(3)-1)/2
const G2: f32 = 0.211_324_87; // (3-sqrt(3))/6
const F3: f32 = 1.0 / 3.0;
const G3: f32 = 1.0 / 6.0;

#[inline]
fn grad2(prf: Prf, layer: u32, i: i32, j: i32, x: f32, y: f32) -> f32 {
    // Deterministic gradient direction from the PRF, taken over 8 evenly
    // spaced unit vectors. Branchless lookup.
    let h = prf.hash(layer, i, j, 0, 0) & 7;
    let (gx, gy) = match h {
        0 => (1.0, 0.0),
        1 => (-1.0, 0.0),
        2 => (0.0, 1.0),
        3 => (0.0, -1.0),
        4 => (core::f32::consts::FRAC_1_SQRT_2, core::f32::consts::FRAC_1_SQRT_2),
        5 => (-core::f32::consts::FRAC_1_SQRT_2, core::f32::consts::FRAC_1_SQRT_2),
        6 => (core::f32::consts::FRAC_1_SQRT_2, -core::f32::consts::FRAC_1_SQRT_2),
        _ => (-core::f32::consts::FRAC_1_SQRT_2, -core::f32::consts::FRAC_1_SQRT_2),
    };
    gx * x + gy * y
}

#[inline]
fn grad3(prf: Prf, layer: u32, i: i32, j: i32, k: i32, x: f32, y: f32, z: f32) -> f32 {
    let h = prf.hash(layer, i, j, k, 0) & 15;
    let (gx, gy, gz) = match h {
        0 => (1.0, 1.0, 0.0),
        1 => (-1.0, 1.0, 0.0),
        2 => (1.0, -1.0, 0.0),
        3 => (-1.0, -1.0, 0.0),
        4 => (1.0, 0.0, 1.0),
        5 => (-1.0, 0.0, 1.0),
        6 => (1.0, 0.0, -1.0),
        7 => (-1.0, 0.0, -1.0),
        8 => (0.0, 1.0, 1.0),
        9 => (0.0, -1.0, 1.0),
        10 => (0.0, 1.0, -1.0),
        11 => (0.0, -1.0, -1.0),
        12 => (1.0, 1.0, 0.0),
        13 => (-1.0, 1.0, 0.0),
        14 => (0.0, -1.0, 1.0),
        _ => (0.0, -1.0, -1.0),
    };
    gx * x + gy * y + gz * z
}

/// 2D simplex noise. Output ≈ `[-1, 1]`.
#[must_use]
pub fn simplex2(prf: Prf, layer: u32, x: f32, y: f32) -> f32 {
    let s = (x + y) * F2;
    let i = (x + s).floor() as i32;
    let j = (y + s).floor() as i32;

    let t = (i + j) as f32 * G2;
    let x0 = x - (i as f32 - t);
    let y0 = y - (j as f32 - t);

    let (i1, j1) = if x0 > y0 { (1, 0) } else { (0, 1) };

    let x1 = x0 - i1 as f32 + G2;
    let y1 = y0 - j1 as f32 + G2;
    let x2 = x0 - 1.0 + 2.0 * G2;
    let y2 = y0 - 1.0 + 2.0 * G2;

    let mut n = 0.0;
    let mut t0 = 0.5 - x0 * x0 - y0 * y0;
    if t0 > 0.0 {
        t0 *= t0;
        n += t0 * t0 * grad2(prf, layer, i, j, x0, y0);
    }
    let mut t1 = 0.5 - x1 * x1 - y1 * y1;
    if t1 > 0.0 {
        t1 *= t1;
        n += t1 * t1 * grad2(prf, layer, i + i1, j + j1, x1, y1);
    }
    let mut t2 = 0.5 - x2 * x2 - y2 * y2;
    if t2 > 0.0 {
        t2 *= t2;
        n += t2 * t2 * grad2(prf, layer, i + 1, j + 1, x2, y2);
    }

    // 70 normalises peak to ~[-1, 1]
    70.0 * n
}

/// 3D simplex noise. Output ≈ `[-1, 1]`.
#[must_use]
pub fn simplex3(prf: Prf, layer: u32, x: f32, y: f32, z: f32) -> f32 {
    let s = (x + y + z) * F3;
    let i = (x + s).floor() as i32;
    let j = (y + s).floor() as i32;
    let k = (z + s).floor() as i32;

    let t = (i + j + k) as f32 * G3;
    let x0 = x - (i as f32 - t);
    let y0 = y - (j as f32 - t);
    let z0 = z - (k as f32 - t);

    // Determine simplex corner order
    let (i1, j1, k1, i2, j2, k2);
    if x0 >= y0 {
        if y0 >= z0 {
            i1 = 1; j1 = 0; k1 = 0; i2 = 1; j2 = 1; k2 = 0;
        } else if x0 >= z0 {
            i1 = 1; j1 = 0; k1 = 0; i2 = 1; j2 = 0; k2 = 1;
        } else {
            i1 = 0; j1 = 0; k1 = 1; i2 = 1; j2 = 0; k2 = 1;
        }
    } else if y0 < z0 {
        i1 = 0; j1 = 0; k1 = 1; i2 = 0; j2 = 1; k2 = 1;
    } else if x0 < z0 {
        i1 = 0; j1 = 1; k1 = 0; i2 = 0; j2 = 1; k2 = 1;
    } else {
        i1 = 0; j1 = 1; k1 = 0; i2 = 1; j2 = 1; k2 = 0;
    }

    let x1 = x0 - i1 as f32 + G3;
    let y1 = y0 - j1 as f32 + G3;
    let z1 = z0 - k1 as f32 + G3;
    let x2 = x0 - i2 as f32 + 2.0 * G3;
    let y2 = y0 - j2 as f32 + 2.0 * G3;
    let z2 = z0 - k2 as f32 + 2.0 * G3;
    let x3 = x0 - 1.0 + 3.0 * G3;
    let y3 = y0 - 1.0 + 3.0 * G3;
    let z3 = z0 - 1.0 + 3.0 * G3;

    let mut n = 0.0;

    let mut t0 = 0.6 - x0 * x0 - y0 * y0 - z0 * z0;
    if t0 > 0.0 {
        t0 *= t0;
        n += t0 * t0 * grad3(prf, layer, i, j, k, x0, y0, z0);
    }
    let mut t1 = 0.6 - x1 * x1 - y1 * y1 - z1 * z1;
    if t1 > 0.0 {
        t1 *= t1;
        n += t1 * t1 * grad3(prf, layer, i + i1, j + j1, k + k1, x1, y1, z1);
    }
    let mut t2 = 0.6 - x2 * x2 - y2 * y2 - z2 * z2;
    if t2 > 0.0 {
        t2 *= t2;
        n += t2 * t2 * grad3(prf, layer, i + i2, j + j2, k + k2, x2, y2, z2);
    }
    let mut t3 = 0.6 - x3 * x3 - y3 * y3 - z3 * z3;
    if t3 > 0.0 {
        t3 *= t3;
        n += t3 * t3 * grad3(prf, layer, i + 1, j + 1, k + 1, x3, y3, z3);
    }

    32.0 * n
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn simplex2_in_range() {
        let p = Prf::new(0xDEAD);
        for i in 0..1000 {
            let v = simplex2(p, 0, i as f32 * 0.1, (i as f32 * 0.07).sin());
            assert!(v >= -1.5 && v <= 1.5, "v = {v}");
        }
    }

    #[test]
    fn simplex3_in_range() {
        let p = Prf::new(0xBEEF);
        for i in 0..1000 {
            let v = simplex3(p, 0, i as f32 * 0.1, i as f32 * 0.05, i as f32 * 0.03);
            assert!(v >= -1.5 && v <= 1.5, "v = {v}");
        }
    }

    #[test]
    fn simplex2_deterministic() {
        let p = Prf::new(7);
        let a = simplex2(p, 0, 12.3, 4.5);
        let b = simplex2(p, 0, 12.3, 4.5);
        assert_eq!(a, b);
    }
}
