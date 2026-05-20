//! Align procedural heightmaps to a continental :class:`MacroGrid`.

use crate::MacroGrid;
use genesis_core::{ChunkCoord, CHUNK_SIZE_X, CHUNK_SIZE_Y};
use genesis_terrain::Heightmap;

/// Blend procedural relief with macro continental elevation.
///
/// Border pixels (2 px) are pinned to macro samples for cross-chunk continuity.
/// Interior uses weight `interior_weight` toward macro (default 0.4).
pub fn align_heightmap(
    hm: &mut Heightmap,
    coord: ChunkCoord,
    grid: &MacroGrid,
    chunk_side_m: f32,
    interior_weight: f32,
) {
    let border = Heightmap::BORDER;
    let w = hm.width;
    let h = hm.height;
    let cell_m_x = chunk_side_m / CHUNK_SIZE_X as f32;
    let cell_m_y = chunk_side_m / CHUNK_SIZE_Y as f32;
    let iw = interior_weight.clamp(0.0, 1.0);

    for jj in 0..h {
        for ii in 0..w {
            let wx_m = coord.cx as f32 * chunk_side_m + (ii as f32 - border as f32) * cell_m_x;
            let wy_m = coord.cy as f32 * chunk_side_m + (jj as f32 - border as f32) * cell_m_y;
            let x_km = grid.origin_km.0 + wx_m / 1000.0;
            let y_km = grid.origin_km.1 + wy_m / 1000.0;
            let Ok(macro_e) = grid.sample_elevation_m(x_km, y_km) else {
                continue;
            };
            let proc = hm.get_raw(ii, jj);
            let is_border =
                ii < border || jj < border || ii >= w - border || jj >= h - border;
            let w_macro = if is_border { 1.0 } else { iw };
            let blended = proc * (1.0 - w_macro) + macro_e * w_macro;
            hm.set_raw(ii, jj, blended);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use genesis_core::Prf;
    use genesis_terrain::{generate as generate_heightmap, TerrainParams};

    #[test]
    fn border_pins_to_macro() {
        let grid = MacroGrid::from_buffers(
            8,
            8,
            10.0,
            (0.0, 0.0),
            vec![500.0; 64],
            vec![0; 64],
        )
        .unwrap();
        let prf = Prf::new(99);
        let mut hm = generate_heightmap(prf, 0, 0, TerrainParams::default());
        align_heightmap(&mut hm, ChunkCoord { cx: 0, cy: 0 }, &grid, 32.0, 0.0);
        // left border column should be ~500m
        assert!((hm.get_raw(0, Heightmap::BORDER) - 500.0).abs() < 1.0);
    }
}
