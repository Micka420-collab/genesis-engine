//! Async chunk manager — generates, caches, evicts.
//!
//! Concurrency model:
//!  - `DashMap<ChunkCoord, Arc<Chunk>>` for hot cache (lock-free reads).
//!  - Generation happens on `tokio::spawn_blocking` so the async runtime
//!    stays responsive while CPU-bound work runs on the rayon pool.
//!  - A second map tracks in-flight generations to coalesce duplicate reqs.

use crate::chunk::{Chunk, ChunkMeta};
use dashmap::DashMap;
use genesis_biome::Biome;
use genesis_climate::{Climate, ClimateParams, ClimateSample};
use genesis_core::{
    ChunkCoord, Material, SeedTree, Voxel, WorldSeed, CHUNK_SIZE_X, CHUNK_SIZE_Y, CHUNK_SIZE_Z,
};
use genesis_ecosystem::{fauna_for_chunk, flora_for_chunk};
use genesis_hydrology::compute as compute_hydro;
use genesis_terrain::{generate as generate_heightmap, hydraulic_erode, thermal_erode, TerrainParams};
use smallvec::smallvec;
use std::sync::Arc;
use tokio::sync::oneshot;
use tracing::{debug, instrument};

/// Config for the chunk manager.
#[derive(Clone, Debug)]
pub struct ChunkManagerConfig {
    /// Sea level (m).
    pub sea_level: f32,
    /// River drainage threshold (m²).
    pub river_threshold_m2: f32,
    /// Erosion droplets per pass.
    pub erosion_droplets: u32,
    /// Erosion passes.
    pub erosion_passes: u32,
    /// Terrain params.
    pub terrain: TerrainParams,
    /// Climate params.
    pub climate: ClimateParams,
    /// Max chunks cached in memory (LRU-style eviction).
    pub cache_capacity: usize,
}

impl Default for ChunkManagerConfig {
    fn default() -> Self {
        Self {
            sea_level: 0.0,
            river_threshold_m2: 5_000.0,
            erosion_droplets: 200,
            erosion_passes: 4,
            terrain: TerrainParams::default(),
            climate: ClimateParams::default(),
            cache_capacity: 1024,
        }
    }
}

/// Async chunk manager.
#[derive(Clone)]
pub struct ChunkManager {
    seed: WorldSeed,
    config: Arc<ChunkManagerConfig>,
    cache: Arc<DashMap<ChunkCoord, Arc<Chunk>>>,
    inflight: Arc<DashMap<ChunkCoord, Vec<oneshot::Sender<Arc<Chunk>>>>>,
    seed_tree: SeedTree,
}

impl ChunkManager {
    /// New manager.
    #[must_use]
    pub fn new(seed: WorldSeed, config: ChunkManagerConfig) -> Self {
        Self {
            seed,
            config: Arc::new(config),
            cache: Arc::new(DashMap::with_capacity(1024)),
            inflight: Arc::new(DashMap::new()),
            seed_tree: SeedTree::new(seed),
        }
    }

    /// Number of cached chunks.
    pub fn cached_count(&self) -> usize {
        self.cache.len()
    }

    /// Drop chunks if we're over capacity.
    pub fn maybe_evict(&self) {
        let cap = self.config.cache_capacity;
        if self.cache.len() > cap {
            let excess = self.cache.len() - cap;
            // Crude: drop the first `excess` we iterate. A real LRU comes
            // later; for now this prevents unbounded growth.
            let mut to_drop = Vec::with_capacity(excess);
            for kv in self.cache.iter().take(excess) {
                to_drop.push(*kv.key());
            }
            for k in to_drop {
                self.cache.remove(&k);
            }
            debug!("evicted {} chunks", excess);
        }
    }

    /// Get a chunk, generating it asynchronously if needed.
    /// Multiple concurrent requests for the same chunk coalesce.
    #[instrument(skip(self), fields(cx = coord.cx, cy = coord.cy))]
    pub async fn get_or_generate(&self, coord: ChunkCoord) -> Arc<Chunk> {
        if let Some(c) = self.cache.get(&coord) {
            return Arc::clone(&c);
        }

        // Coalesce duplicate concurrent requests for the same chunk.
        // Only the first caller actually performs the generation; others
        // wait on a oneshot.
        let should_generate = {
            let mut entry = self.inflight.entry(coord).or_default();
            if entry.is_empty() {
                // We're the leader.
                true
            } else {
                let (tx, rx) = oneshot::channel();
                entry.push(tx);
                drop(entry);
                return rx.await.expect("inflight sender dropped");
            }
        };

        let _ = should_generate;
        let me = self.clone();
        let chunk = tokio::task::spawn_blocking(move || me.generate(coord))
            .await
            .expect("generate panicked");
        let arc = Arc::new(chunk);
        self.cache.insert(coord, Arc::clone(&arc));

        if let Some((_, waiters)) = self.inflight.remove(&coord) {
            for w in waiters {
                let _ = w.send(Arc::clone(&arc));
            }
        }
        self.maybe_evict();
        arc
    }

    /// Synchronous chunk generation (CPU-bound).
    pub fn generate(&self, coord: ChunkCoord) -> Chunk {
        let prf_terrain = self.seed_tree.prf("terrain");
        let prf_climate = self.seed_tree.prf("climate");
        let prf_ecology = self.seed_tree.prf("ecology");

        // 1. Heightmap
        let mut hm = generate_heightmap(prf_terrain, coord.cx, coord.cy, self.config.terrain);
        // 2. Erode
        let erode_seed = prf_terrain.hash(0xE00D_E000, coord.cx, coord.cy, 0, 0);
        hydraulic_erode(
            &mut hm,
            erode_seed,
            self.config.erosion_passes,
            self.config.erosion_droplets,
        );
        thermal_erode(&mut hm, 2, 0.7);

        // 3. Hydrology
        let hydro = compute_hydro(&hm, self.config.sea_level, self.config.river_threshold_m2);

        // 4. Climate + biome per column
        let climate = Climate::new(prf_climate, self.config.climate);
        let cw = CHUNK_SIZE_X as u32;
        let ch = CHUNK_SIZE_Y as u32;
        let n = (cw * ch) as usize;
        let mut elevation = vec![0.0f32; n];
        let mut biome_map = vec![Biome::Grassland; n];
        let mut climate_map = vec![
            ClimateSample {
                temperature_c: 0.0,
                humidity: 0.0,
                wind_ms: [0.0, 0.0],
            };
            n
        ];
        let mut river_mask = vec![false; n];
        let mut lake_mask = vec![false; n];

        for j in 0..ch {
            for i in 0..cw {
                let idx = (j * cw + i) as usize;
                let elev = hm.get(i, j);
                elevation[idx] = elev;
                let wx = (coord.cx * CHUNK_SIZE_X + i as i32) as f32;
                let wy = (coord.cy * CHUNK_SIZE_Y + j as i32) as f32;
                let cs = climate.sample(wx, wy, elev, None);
                climate_map[idx] = cs;
                biome_map[idx] = Biome::classify(
                    cs.temperature_c,
                    cs.humidity,
                    elev,
                    self.config.sea_level,
                );
                let hidx = ((j + 2) * hydro.width + (i + 2)) as usize;
                river_mask[idx] = hydro.river_mask[hidx];
                lake_mask[idx] = hydro.lake_mask[hidx];
            }
        }

        // 5. Voxel column fill
        let palette = smallvec![
            Material::Air as u16,
            Material::Bedrock as u16,
            Material::Stone as u16,
            Material::Dirt as u16,
            Material::Grass as u16,
            Material::Sand as u16,
            Material::Snow as u16,
            Material::Ice as u16,
            Material::Water as u16,
        ];
        let mut voxels =
            vec![Voxel::AIR.0; (CHUNK_SIZE_X * CHUNK_SIZE_Y * CHUNK_SIZE_Z) as usize];

        for j in 0..ch {
            for i in 0..cw {
                let idx = (j * cw + i) as usize;
                let surface_z = elevation[idx].round() as i32;
                let biome = biome_map[idx];
                let temp = climate_map[idx].temperature_c;
                for z in 0..CHUNK_SIZE_Z {
                    let world_z = z;
                    let v_idx = (i as usize)
                        + (j as usize) * CHUNK_SIZE_X as usize
                        + (z as usize) * (CHUNK_SIZE_X * CHUNK_SIZE_Y) as usize;
                    let mat = column_material(
                        world_z,
                        surface_z,
                        biome,
                        temp,
                        river_mask[idx],
                        lake_mask[idx],
                        self.config.sea_level,
                    );
                    voxels[v_idx] = mat as u16;
                }
            }
        }

        // 6. Flora + fauna
        let flora =
            flora_for_chunk(prf_ecology, coord.cx, coord.cy, &biome_map, &elevation, 1.0)
                .into_vec();
        let dominant = dominant_biome(&biome_map);
        let fauna = fauna_for_chunk(prf_ecology, coord.cx, coord.cy, dominant).into_vec();

        let meta = ChunkMeta {
            coord,
            generated_at_tick: 0,
            content_hash: [0; 32], // filled by persist if needed
        };

        Chunk {
            meta,
            palette,
            voxels,
            elevation,
            biome: biome_map,
            climate: climate_map,
            river_mask,
            lake_mask,
            flora,
            fauna,
        }
    }
}

fn dominant_biome(biomes: &[Biome]) -> Biome {
    use std::collections::HashMap;
    let mut counts: HashMap<u8, u32> = HashMap::new();
    for b in biomes {
        *counts.entry(*b as u8).or_insert(0) += 1;
    }
    let best = counts.iter().max_by_key(|(_, v)| *v).map(|(k, _)| *k);
    match best {
        Some(0) => Biome::Ocean,
        Some(1) => Biome::CoastalSea,
        Some(2) => Biome::Ice,
        Some(3) => Biome::Tundra,
        Some(4) => Biome::BorealForest,
        Some(5) => Biome::TemperateForest,
        Some(6) => Biome::TemperateRainforest,
        Some(7) => Biome::Grassland,
        Some(8) => Biome::HotDesert,
        Some(9) => Biome::ColdDesert,
        Some(10) => Biome::Savanna,
        Some(11) => Biome::TropicalDryForest,
        Some(12) => Biome::TropicalRainforest,
        Some(13) => Biome::Shrubland,
        Some(14) => Biome::Wetland,
        Some(15) => Biome::AlpineRock,
        _ => Biome::Grassland,
    }
}

#[inline]
fn column_material(
    z: i32,
    surface_z: i32,
    biome: Biome,
    temp_c: f32,
    is_river: bool,
    is_lake: bool,
    sea_level: f32,
) -> Material {
    let sea_z = sea_level.round() as i32;
    if z > surface_z {
        // Above the surface. River/lake fill water up to surface_z+1.
        if (is_river || is_lake) && z == surface_z + 1 {
            return Material::Water;
        }
        // Ocean / coastal sea fills with water up to sea level.
        if surface_z < sea_z && z <= sea_z {
            return Material::Water;
        }
        return Material::Air;
    }
    if z == surface_z {
        // surface material
        return match biome {
            Biome::Ocean | Biome::CoastalSea => Material::Sand,
            Biome::HotDesert | Biome::ColdDesert => Material::Sand,
            Biome::Ice => Material::Ice,
            Biome::Tundra => {
                if temp_c < -2.0 {
                    Material::Snow
                } else {
                    Material::Dirt
                }
            }
            Biome::AlpineRock => Material::Stone,
            _ => {
                if temp_c < -2.0 {
                    Material::Snow
                } else {
                    Material::Grass
                }
            }
        };
    }
    if surface_z - z < 4 {
        Material::Dirt
    } else if surface_z - z < 32 {
        Material::Stone
    } else {
        Material::Bedrock
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn manager_generates_chunk_sync() {
        let mgr = ChunkManager::new(
            WorldSeed::from_u64(42),
            ChunkManagerConfig {
                erosion_droplets: 16, // keep test fast
                erosion_passes: 1,
                cache_capacity: 16,
                ..Default::default()
            },
        );
        let c = mgr.generate(ChunkCoord { cx: 0, cy: 0 });
        assert_eq!(c.elevation.len(), (CHUNK_SIZE_X * CHUNK_SIZE_Y) as usize);
        assert_eq!(
            c.voxels.len(),
            (CHUNK_SIZE_X * CHUNK_SIZE_Y * CHUNK_SIZE_Z) as usize
        );
    }
}
