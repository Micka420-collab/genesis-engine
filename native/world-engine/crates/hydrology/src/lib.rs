//! genesis-hydrology — rivers, lakes, drainage basins.
//!
//! Strategy: per chunk, compute flow direction (D8 steepest descent) and a
//! cumulative drainage area. Pixels above a threshold are flagged as rivers.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use genesis_terrain::Heightmap;
use serde::{Deserialize, Serialize};

/// Per-chunk hydrology data.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Hydrology {
    /// Width (matches the heightmap).
    pub width: u32,
    /// Height (matches the heightmap).
    pub height: u32,
    /// Drainage area per pixel (square-metres).
    pub drainage: Vec<f32>,
    /// Boolean river mask (river = `true`).
    pub river_mask: Vec<bool>,
    /// Boolean lake mask.
    pub lake_mask: Vec<bool>,
    /// Sea level used.
    pub sea_level: f32,
}

/// Compute hydrology from a heightmap.
///
/// `river_threshold_m2` is the drainage area above which a pixel becomes a
/// river. Realistic values: 1–5 km² for visible rivers.
#[must_use]
pub fn compute(hm: &Heightmap, sea_level: f32, river_threshold_m2: f32) -> Hydrology {
    let w = hm.width;
    let h = hm.height;
    let total = (w * h) as usize;

    let mut drainage = vec![1.0f32; total]; // each cell starts as 1 m² of contribution
    let mut order: Vec<u32> = (0..total as u32).collect();
    // Sort by elevation descending so highest cells route water first.
    order.sort_by(|a, b| {
        let ha = hm.data[*a as usize];
        let hb = hm.data[*b as usize];
        hb.partial_cmp(&ha).unwrap_or(core::cmp::Ordering::Equal)
    });

    for idx in &order {
        let i = (*idx % w) as i32;
        let j = (*idx / w) as i32;
        let here = hm.data[*idx as usize];
        if here <= sea_level {
            continue; // ocean cells drain trivially
        }
        let mut best = (i, j, here);
        // D8 neighbours
        for dj in -1..=1 {
            for di in -1..=1 {
                if di == 0 && dj == 0 {
                    continue;
                }
                let ni = i + di;
                let nj = j + dj;
                if ni < 0 || nj < 0 || ni >= w as i32 || nj >= h as i32 {
                    continue;
                }
                let v = hm.data[(nj as u32 * w + ni as u32) as usize];
                if v < best.2 {
                    best = (ni, nj, v);
                }
            }
        }
        if best.0 != i || best.1 != j {
            let from = *idx as usize;
            let to = (best.1 as u32 * w + best.0 as u32) as usize;
            drainage[to] += drainage[from];
        }
    }

    let river_mask: Vec<bool> = drainage.iter().map(|d| *d > river_threshold_m2).collect();

    // Lake: cell that has 0 downslope neighbour AND is above sea level.
    // Cheap approximation — proper basin-filling is for a later pass.
    let mut lake_mask = vec![false; total];
    for j in 1..(h - 1) as i32 {
        for i in 1..(w - 1) as i32 {
            let idx = (j as u32 * w + i as u32) as usize;
            let here = hm.data[idx];
            if here <= sea_level {
                continue;
            }
            let mut is_local_min = true;
            'outer: for dj in -1..=1 {
                for di in -1..=1 {
                    if di == 0 && dj == 0 {
                        continue;
                    }
                    let v = hm.data[((j + dj) as u32 * w + (i + di) as u32) as usize];
                    if v < here {
                        is_local_min = false;
                        break 'outer;
                    }
                }
            }
            if is_local_min && drainage[idx] > river_threshold_m2 * 4.0 {
                lake_mask[idx] = true;
            }
        }
    }

    Hydrology {
        width: w,
        height: h,
        drainage,
        river_mask,
        lake_mask,
        sea_level,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use genesis_core::Prf;
    use genesis_terrain::{generate, TerrainParams};

    #[test]
    fn hydrology_runs() {
        let prf = Prf::new(7);
        let hm = generate(prf, 0, 0, TerrainParams::default());
        let hy = compute(&hm, 0.0, 5_000.0);
        assert_eq!(hy.river_mask.len(), hy.drainage.len());
    }
}
