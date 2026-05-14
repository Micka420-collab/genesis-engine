//! Chunks voxel + génération à la demande.

use crate::biome::{classify, Biome};
use crate::resource::{ResourceMap, generate_resources};
use crate::terrain::{sample, TerrainParams, TerrainSample};
use ge_core::{ChunkCoord, WorldSeed};
use serde::{Deserialize, Serialize};

pub const CHUNK_SIZE: usize = 64;
pub const CHUNK_HEIGHT: usize = 128;
pub const VOXEL_SIZE_M: f32 = 0.5;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Chunk {
    pub coord: ChunkCoord,
    pub height: Vec<f32>,
    pub biome: Vec<Biome>,
    pub resources: ResourceMap,
    pub content_root: [u8; 32],
}

impl Chunk {
    #[inline]
    pub fn idx(x: usize, y: usize) -> usize {
        debug_assert!(x < CHUNK_SIZE && y < CHUNK_SIZE);
        y * CHUNK_SIZE + x
    }

    pub fn origin_m(coord: ChunkCoord) -> (f32, f32) {
        let s = CHUNK_SIZE as f32 * VOXEL_SIZE_M;
        (coord.x as f32 * s, coord.y as f32 * s)
    }

    pub fn from_world_pos(x_m: f32, y_m: f32, z_m: f32) -> ChunkCoord {
        let s = CHUNK_SIZE as f32 * VOXEL_SIZE_M;
        ChunkCoord::new(
            (x_m / s).floor() as i32,
            (y_m / s).floor() as i32,
            (z_m / s).floor() as i32,
        )
    }

    pub fn cell_pos_m(coord: ChunkCoord, cx: usize, cy: usize) -> (f32, f32) {
        let (ox, oy) = Self::origin_m(coord);
        (ox + (cx as f32 + 0.5) * VOXEL_SIZE_M, oy + (cy as f32 + 0.5) * VOXEL_SIZE_M)
    }
}

pub fn generate_chunk(seed: WorldSeed, coord: ChunkCoord, params: &TerrainParams) -> Chunk {
    let (ox, oy) = Chunk::origin_m(coord);
    let mut height = vec![0.0f32; CHUNK_SIZE * CHUNK_SIZE];
    let mut biome = vec![Biome::Ocean; CHUNK_SIZE * CHUNK_SIZE];
    for y in 0..CHUNK_SIZE {
        for x in 0..CHUNK_SIZE {
            let wx = ox + (x as f32 + 0.5) * VOXEL_SIZE_M;
            let wy = oy + (y as f32 + 0.5) * VOXEL_SIZE_M;
            let TerrainSample { elev_m, temp_c, precip_mm } = sample(seed, params, wx, wy);
            let i = Chunk::idx(x, y);
            height[i] = elev_m;
            biome[i] = classify(temp_c, precip_mm, elev_m);
        }
    }
    let resources = generate_resources(seed, coord, &biome, &height);
    let content_root = compute_root(&height, &biome, &resources);
    Chunk { coord, height, biome, resources, content_root }
}

fn compute_root(height: &[f32], biome: &[Biome], res: &ResourceMap) -> [u8; 32] {
    use blake3::Hasher;
    let mut h = Hasher::new();
    for v in height { h.update(&v.to_le_bytes()); }
    for b in biome { h.update(&[*b as u8]); }
    for v in &res.stone { h.update(&v.to_le_bytes()); }
    for v in &res.wood { h.update(&v.to_le_bytes()); }
    for v in &res.metal { h.update(&v.to_le_bytes()); }
    *h.finalize().as_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn chunk_determinism() {
        let p = TerrainParams::default();
        let c1 = generate_chunk(0xCAFE, ChunkCoord::new(3,7,0), &p);
        let c2 = generate_chunk(0xCAFE, ChunkCoord::new(3,7,0), &p);
        assert_eq!(c1.content_root, c2.content_root);
    }
}
