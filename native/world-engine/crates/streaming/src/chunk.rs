//! Chunk type — what one generated 64×64×128 patch contains.

use genesis_biome::Biome;
use genesis_climate::ClimateSample;
use genesis_core::{ChunkCoord, LocalCoord, Voxel, CHUNK_SIZE_X, CHUNK_SIZE_Y};
use genesis_ecosystem::{FaunaSeed, FloraInstance};
use serde::{Deserialize, Serialize};
use smallvec::SmallVec;

/// Per-chunk metadata.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ChunkMeta {
    /// Chunk identity.
    pub coord: ChunkCoord,
    /// Tick when generated.
    pub generated_at_tick: u64,
    /// 32-byte content hash (BLAKE3 over the serialized data).
    pub content_hash: [u8; 32],
}

/// A generated chunk.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Chunk {
    /// Metadata.
    pub meta: ChunkMeta,
    /// Palette: index → material id (16-bit material codes from `core::Material`).
    pub palette: SmallVec<[u16; 16]>,
    /// Voxel buffer of palette indices, len = CHUNK_SIZE_X*Y*Z.
    pub voxels: Vec<u16>,
    /// Surface elevation grid (m), CHUNK_SIZE_X × CHUNK_SIZE_Y.
    pub elevation: Vec<f32>,
    /// Biome per surface column.
    pub biome: Vec<Biome>,
    /// Climate per surface column.
    pub climate: Vec<ClimateSample>,
    /// River mask per surface column.
    pub river_mask: Vec<bool>,
    /// Lake mask per surface column.
    pub lake_mask: Vec<bool>,
    /// Flora placed in this chunk.
    pub flora: Vec<FloraInstance>,
    /// Fauna seeds for this chunk.
    pub fauna: Vec<FaunaSeed>,
}

impl Chunk {
    /// Voxel at a local coordinate.
    #[must_use]
    pub fn voxel_at(&self, local: LocalCoord) -> Voxel {
        Voxel(self.voxels[local.index()])
    }

    /// Surface elevation at column `(i, j)` in chunk-local coords.
    #[must_use]
    pub fn elevation_at(&self, i: u32, j: u32) -> f32 {
        debug_assert!(i < CHUNK_SIZE_X as u32 && j < CHUNK_SIZE_Y as u32);
        self.elevation[(j * CHUNK_SIZE_X as u32 + i) as usize]
    }

    /// Biome at column `(i, j)`.
    #[must_use]
    pub fn biome_at(&self, i: u32, j: u32) -> Biome {
        debug_assert!(i < CHUNK_SIZE_X as u32 && j < CHUNK_SIZE_Y as u32);
        self.biome[(j * CHUNK_SIZE_X as u32 + i) as usize]
    }
}
