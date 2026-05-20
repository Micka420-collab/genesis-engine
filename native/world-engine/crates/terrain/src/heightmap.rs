//! Heightmap generation — combines tectonics + relief noise.
//!
//! Output: a dense `Heightmap` in metres above sea level, sized for one
//! chunk + a 2-pixel border (so erosion has neighbour information).

use crate::tectonics::PlateField;
use genesis_core::{Prf, CHUNK_SIZE_X, CHUNK_SIZE_Y};
use genesis_noise::{fbm2, ridged2, FbmParams, RidgedParams, domain_warp2, WarpParams};
use rayon::prelude::*;

/// Parameters controlling the terrain generator.
#[derive(Copy, Clone, Debug)]
pub struct TerrainParams {
    /// Sea level in metres (default 0).
    pub sea_level: f32,
    /// Tectonic plate cell size in metres.
    pub plate_cell_size: f32,
    /// Fraction of plates that are continental.
    pub continental_ratio: f32,
    /// Amplitude of detail relief noise (m).
    pub relief_amplitude: f32,
    /// Amplitude of mountain ridges (m).
    pub ridge_amplitude: f32,
    /// Whether to domain-warp the relief noise.
    pub use_domain_warp: bool,
}

impl Default for TerrainParams {
    fn default() -> Self {
        Self {
            sea_level: 0.0,
            plate_cell_size: 80_000.0,
            continental_ratio: 0.42,
            relief_amplitude: 400.0,
            ridge_amplitude: 600.0,
            use_domain_warp: true,
        }
    }
}

/// Dense heightmap with a 2-pixel border.
#[derive(Clone, Debug)]
pub struct Heightmap {
    /// Width including 2-pixel left + 2-pixel right border.
    pub width: u32,
    /// Height including border.
    pub height: u32,
    /// Elevation in metres, row-major.
    pub data: Vec<f32>,
}

impl Heightmap {
    /// Border width on each side.
    pub const BORDER: u32 = 2;

    /// Build an empty heightmap sized for one chunk + border.
    #[must_use]
    pub fn for_chunk() -> Self {
        let w = CHUNK_SIZE_X as u32 + 2 * Self::BORDER;
        let h = CHUNK_SIZE_Y as u32 + 2 * Self::BORDER;
        Self {
            width: w,
            height: h,
            data: vec![0.0; (w * h) as usize],
        }
    }

    /// Read an elevation at `(i, j)` in chunk-local coords (no border offset).
    #[inline]
    #[must_use]
    pub fn get(&self, i: u32, j: u32) -> f32 {
        let ii = i + Self::BORDER;
        let jj = j + Self::BORDER;
        self.data[(jj * self.width + ii) as usize]
    }

    /// Direct indexed get (with border included).
    #[inline]
    #[must_use]
    pub fn get_raw(&self, i: u32, j: u32) -> f32 {
        self.data[(j * self.width + i) as usize]
    }

    /// Direct indexed set (with border included).
    #[inline]
    pub fn set_raw(&mut self, i: u32, j: u32, v: f32) {
        self.data[(j * self.width + i) as usize] = v;
    }
}

/// Generate the raw heightmap for chunk `(cx, cy)`.
///
/// `prf` should be the tree-derived PRF for layer `"terrain"`.
#[must_use]
pub fn generate(prf: Prf, cx: i32, cy: i32, params: TerrainParams) -> Heightmap {
    let plates = PlateField::new(prf, 0, params.plate_cell_size, params.continental_ratio);

    let mut hm = Heightmap::for_chunk();
    let w = hm.width;
    let h = hm.height;

    // Sample every pixel in parallel rows
    let chunk_origin_x = cx * CHUNK_SIZE_X;
    let chunk_origin_y = cy * CHUNK_SIZE_Y;
    let border = Heightmap::BORDER as i32;

    let relief_params = FbmParams {
        octaves: 6,
        lacunarity: 2.0,
        gain: 0.5,
        frequency: 1.0 / 256.0,
    };
    let ridge_params = RidgedParams {
        octaves: 5,
        lacunarity: 2.0,
        gain: 0.5,
        frequency: 1.0 / 512.0,
        sharpness: 1.2,
    };
    let warp_params = WarpParams::default();

    let rows: Vec<Vec<f32>> = (0..h)
        .into_par_iter()
        .map(|jj| {
            let mut row = vec![0.0f32; w as usize];
            let py = chunk_origin_y as f32 + jj as f32 - border as f32;
            for ii in 0..w {
                let px = chunk_origin_x as f32 + ii as f32 - border as f32;

                let (wx, wy) = if params.use_domain_warp {
                    domain_warp2(prf, 0xC0DE_0001, px, py, warp_params)
                } else {
                    (px, py)
                };

                let tect = plates.baseline_elevation(wx, wy);
                let relief = fbm2(prf, 0xC0DE_0002, wx, wy, relief_params)
                    * params.relief_amplitude;
                let ridge = ridged2(prf, 0xC0DE_0003, wx * 0.5, wy * 0.5, ridge_params)
                    * params.ridge_amplitude;

                let mut elev = tect + relief;
                // Ridges only really show above-sea on continental crust
                if tect > 200.0 {
                    elev += ridge;
                }
                row[ii as usize] = elev;
            }
            row
        })
        .collect();

    for (jj, row) in rows.into_iter().enumerate() {
        let off = jj * w as usize;
        hm.data[off..off + w as usize].copy_from_slice(&row);
    }

    hm
}

#[cfg(test)]
mod tests {
    use super::*;
    use blake3::Hasher;

    fn hash_hm(hm: &Heightmap) -> [u8; 32] {
        let mut h = Hasher::new();
        for v in &hm.data {
            h.update(&v.to_le_bytes());
        }
        *h.finalize().as_bytes()
    }

    #[test]
    fn heightmap_is_deterministic() {
        let prf = Prf::new(42);
        let p = TerrainParams::default();
        let a = generate(prf, 3, -5, p);
        let b = generate(prf, 3, -5, p);
        assert_eq!(hash_hm(&a), hash_hm(&b));
    }

    #[test]
    fn heightmap_size() {
        let prf = Prf::new(1);
        let hm = generate(prf, 0, 0, TerrainParams::default());
        assert_eq!(hm.width, CHUNK_SIZE_X as u32 + 4);
        assert_eq!(hm.height, CHUNK_SIZE_Y as u32 + 4);
    }
}
