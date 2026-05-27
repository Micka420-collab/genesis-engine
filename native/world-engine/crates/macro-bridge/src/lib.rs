//! Continental macro grid bridge — unify Python `GenesisWorld` with Rust chunks.
//!
//! Phase 0 of the God-Engine roadmap: Rust terrain generation can **sample**
//! a precomputed macro grid (elevation, biome) instead of running an
//! independent procedural pipeline. Same seed + same grid bytes ⇒ identical
//! mesoscale relief at chunk boundaries.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

mod align;
mod binary;

pub use align::align_heightmap;
pub use binary::{read_binary, write_binary, MAGIC, VERSION};

use genesis_biome::Biome;
use genesis_core::ChunkCoord;
use thiserror::Error;

/// Errors loading or sampling a macro grid.
#[derive(Error, Debug)]
pub enum MacroBridgeError {
    /// File magic is not `GENM`.
    #[error("invalid macro grid magic")]
    BadMagic,
    /// Unsupported file version.
    #[error("unsupported macro grid version")]
    UnsupportedVersion,
    /// Buffer length does not match width × height.
    #[error("grid size mismatch: expected {expected} cells, got {got}")]
    SizeMismatch {
        /// Expected cell count.
        expected: usize,
        /// Actual cell count.
        got: usize,
    },
    /// Coordinate outside the grid.
    #[error("sample out of macro bounds")]
    OutOfBounds,
    /// Underlying I/O error from a binary reader/writer. Required so the
    /// `?` operator in `binary::read_binary` / `write_binary` can convert
    /// `std::io::Error` to a `MacroBridgeError` automatically — without
    /// this `#[from]` variant the binary module fails to compile on CI.
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
}

/// Read-only continental macro field (Python Genesis export).
#[derive(Clone, Debug)]
pub struct MacroGrid {
    /// Grid width in cells.
    pub width: usize,
    /// Grid height in cells.
    pub height: usize,
    /// Cell size in km (square cells).
    pub cell_km: f32,
    /// World origin of cell (0,0) in macro km.
    pub origin_km: (f32, f32),
    /// Elevation in metres, row-major `iy * width + ix`.
    pub elevation_m: Vec<f32>,
    /// Biome id per cell (matches `genesis_biome::Biome` discriminant).
    pub biome: Vec<u8>,
}

impl MacroGrid {
    /// Build from flat buffers (Python `GenesisWorld` export).
    pub fn from_buffers(
        width: usize,
        height: usize,
        cell_km: f32,
        origin_km: (f32, f32),
        elevation_m: Vec<f32>,
        biome: Vec<u8>,
    ) -> Result<Self, MacroBridgeError> {
        let n = width.checked_mul(height).unwrap_or(0);
        if elevation_m.len() != n || biome.len() != n {
            return Err(MacroBridgeError::SizeMismatch {
                expected: n,
                got: elevation_m.len(),
            });
        }
        Ok(Self {
            width,
            height,
            cell_km,
            origin_km,
            elevation_m,
            biome,
        })
    }

    fn cell_indices(&self, x_km: f32, y_km: f32) -> Result<(usize, usize), MacroBridgeError> {
        let fx = (x_km - self.origin_km.0) / self.cell_km;
        let fy = (y_km - self.origin_km.1) / self.cell_km;
        if fx < 0.0 || fy < 0.0 {
            return Err(MacroBridgeError::OutOfBounds);
        }
        let ix = fx.floor() as usize;
        let iy = fy.floor() as usize;
        if ix >= self.width.saturating_sub(1) || iy >= self.height.saturating_sub(1) {
            return Err(MacroBridgeError::OutOfBounds);
        }
        Ok((ix, iy))
    }

    /// Bilinear elevation sample at macro km coordinates.
    pub fn sample_elevation_m(&self, x_km: f32, y_km: f32) -> Result<f32, MacroBridgeError> {
        let fx = (x_km - self.origin_km.0) / self.cell_km;
        let fy = (y_km - self.origin_km.1) / self.cell_km;
        if fx < 0.0 || fy < 0.0 {
            return Err(MacroBridgeError::OutOfBounds);
        }
        let ix = fx.floor() as usize;
        let iy = fy.floor() as usize;
        if ix + 1 >= self.width || iy + 1 >= self.height {
            return Err(MacroBridgeError::OutOfBounds);
        }
        let tx = fx - ix as f32;
        let ty = fy - iy as f32;
        let i00 = iy * self.width + ix;
        let i10 = i00 + 1;
        let i01 = i00 + self.width;
        let i11 = i01 + 1;
        let e00 = self.elevation_m[i00];
        let e10 = self.elevation_m[i10];
        let e01 = self.elevation_m[i01];
        let e11 = self.elevation_m[i11];
        let ex0 = e00 * (1.0 - tx) + e10 * tx;
        let ex1 = e01 * (1.0 - tx) + e11 * tx;
        Ok(ex0 * (1.0 - ty) + ex1 * ty)
    }

    /// Nearest biome at macro km.
    pub fn sample_biome(&self, x_km: f32, y_km: f32) -> Result<Biome, MacroBridgeError> {
        let (ix, iy) = self.cell_indices(x_km, y_km)?;
        let idx = iy * self.width + ix;
        let id = self.biome[idx];
        Ok(biome_from_u8(id))
    }
}

fn biome_from_u8(id: u8) -> Biome {
    match id {
        0 => Biome::Ocean,
        1 => Biome::CoastalSea,
        2 => Biome::Ice,
        3 => Biome::Tundra,
        4 => Biome::BorealForest,
        5 => Biome::TemperateForest,
        6 => Biome::TemperateRainforest,
        7 => Biome::Grassland,
        8 => Biome::HotDesert,
        9 => Biome::ColdDesert,
        10 => Biome::Savanna,
        11 => Biome::TropicalDryForest,
        12 => Biome::TropicalRainforest,
        13 => Biome::Shrubland,
        14 => Biome::Wetland,
        15 => Biome::AlpineRock,
        _ => Biome::Ocean,
    }
}

/// Samples macro fields for chunk corner alignment (border consistency).
#[derive(Clone, Debug)]
pub struct ChunkMacroSampler<'a> {
    grid: &'a MacroGrid,
    /// Chunk side length in metres (must match streaming).
    pub chunk_side_m: f32,
}

impl<'a> ChunkMacroSampler<'a> {
    /// Create a sampler bound to a macro grid.
    #[must_use]
    pub fn new(grid: &'a MacroGrid, chunk_side_m: f32) -> Self {
        Self { grid, chunk_side_m }
    }

    /// Chunk centre macro km from chunk indices.
    #[must_use]
    pub fn chunk_center_km(&self, coord: ChunkCoord) -> (f32, f32) {
        let ox_m = coord.cx as f32 * self.chunk_side_m + self.chunk_side_m * 0.5;
        let oy_m = coord.cy as f32 * self.chunk_side_m + self.chunk_side_m * 0.5;
        (
            self.grid.origin_km.0 + ox_m / 1000.0,
            self.grid.origin_km.1 + oy_m / 1000.0,
        )
    }

    /// Mean elevation over the chunk footprint (for LOD-0 alignment).
    pub fn mean_elevation_m(&self, coord: ChunkCoord) -> Result<f32, MacroBridgeError> {
        let (cx, cy) = self.chunk_center_km(coord);
        self.grid.sample_elevation_m(cx, cy)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tiny_grid() -> MacroGrid {
        MacroGrid::from_buffers(
            4,
            4,
            10.0,
            (0.0, 0.0),
            vec![
                0.0, 100.0, 200.0, 300.0, 50.0, 150.0, 250.0, 350.0, 100.0, 200.0, 300.0,
                400.0, 150.0, 250.0, 350.0, 450.0,
            ],
            vec![0; 16],
        )
        .unwrap()
    }

    #[test]
    fn bilinear_is_deterministic() {
        let g = tiny_grid();
        let a = g.sample_elevation_m(15.0, 15.0).unwrap();
        let b = g.sample_elevation_m(15.0, 15.0).unwrap();
        assert_eq!(a, b);
        assert!(a > 100.0 && a < 300.0);
    }

    #[test]
    fn chunk_center_samples_in_bounds() {
        let g = tiny_grid();
        let s = ChunkMacroSampler::new(&g, 32.0);
        let e = s.mean_elevation_m(ChunkCoord { cx: 0, cy: 0 }).unwrap();
        assert!(e.is_finite());
    }
}
