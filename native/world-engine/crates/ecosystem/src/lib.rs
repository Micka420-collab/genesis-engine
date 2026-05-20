//! genesis-ecosystem — flora and fauna spawn rules.
//!
//! Per chunk, this crate emits a list of seeds (flora) and population
//! seeds (fauna). Actual individual simulation lives in the agent runtime.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use genesis_biome::Biome;
use genesis_core::{Prf, WorldCoord, CHUNK_SIZE_X, CHUNK_SIZE_Y};
use serde::{Deserialize, Serialize};
use smallvec::SmallVec;

/// Plant species placeholder id — wired to the agent runtime catalog.
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct FloraId(pub u32);

/// Animal niche placeholder id.
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct FaunaNiche(pub u32);

/// One plant placed in the world.
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub struct FloraInstance {
    /// World coordinate (voxel).
    pub pos: WorldCoord,
    /// Species id.
    pub species: FloraId,
    /// Growth stage in `[0, 1]`.
    pub stage: f32,
}

/// One fauna population spawned in the chunk.
#[derive(Copy, Clone, Debug, Serialize, Deserialize)]
pub struct FaunaSeed {
    /// Centroid in voxel space.
    pub center: WorldCoord,
    /// Niche.
    pub niche: FaunaNiche,
    /// Initial population.
    pub count: u32,
}

/// Generate a flora list for a chunk.
///
/// Uses Poisson-disk style scattering with deterministic jitter from the PRF.
#[must_use]
pub fn flora_for_chunk(
    prf: Prf,
    cx: i32,
    cy: i32,
    biome_per_cell: &[Biome],
    elevation_per_cell: &[f32],
    density_factor: f32,
) -> SmallVec<[FloraInstance; 64]> {
    let mut out = SmallVec::<[FloraInstance; 64]>::new();

    let w = CHUNK_SIZE_X as usize;
    let h = CHUNK_SIZE_Y as usize;
    assert_eq!(biome_per_cell.len(), w * h);
    assert_eq!(elevation_per_cell.len(), w * h);

    // Grid sub-step (Poisson radius proxy). 4 voxel spacing default; biome
    // density modulates this.
    let step = 4i32;
    for j in (0..h as i32).step_by(step as usize) {
        for i in (0..w as i32).step_by(step as usize) {
            let idx = (j as usize) * w + (i as usize);
            let b = biome_per_cell[idx];
            let dens = biome_density(b) * density_factor;
            // Per-cell roll
            let r = prf.unit_f32(0xF10A_0001, cx * CHUNK_SIZE_X + i, cy * CHUNK_SIZE_Y + j, 0, 0);
            if r > dens {
                continue;
            }
            let ji = prf.signed_f32(
                0xF10A_0002,
                cx * CHUNK_SIZE_X + i,
                cy * CHUNK_SIZE_Y + j,
                0,
                0,
            ) * (step as f32 * 0.4);
            let jj = prf.signed_f32(
                0xF10A_0003,
                cx * CHUNK_SIZE_X + i,
                cy * CHUNK_SIZE_Y + j,
                0,
                0,
            ) * (step as f32 * 0.4);
            let xi = (i as f32 + ji).round() as i32;
            let yi = (j as f32 + jj).round() as i32;
            if xi < 0 || yi < 0 || xi >= w as i32 || yi >= h as i32 {
                continue;
            }
            let zi = elevation_per_cell[idx].round() as i32 + 1;
            let species_roll = prf.range(
                0xF10A_0004,
                cx * CHUNK_SIZE_X + xi,
                cy * CHUNK_SIZE_Y + yi,
                0,
                0,
                biome_species_count(b),
            );
            let stage = prf.unit_f32(
                0xF10A_0005,
                cx * CHUNK_SIZE_X + xi,
                cy * CHUNK_SIZE_Y + yi,
                0,
                0,
            );
            out.push(FloraInstance {
                pos: WorldCoord::new(
                    cx * CHUNK_SIZE_X + xi,
                    cy * CHUNK_SIZE_Y + yi,
                    zi,
                ),
                species: FloraId(biome_species_base(b) + species_roll),
                stage,
            });
        }
    }
    out
}

/// Generate fauna seeds for a chunk (one per niche per dominant biome).
#[must_use]
pub fn fauna_for_chunk(
    prf: Prf,
    cx: i32,
    cy: i32,
    dominant_biome: Biome,
) -> SmallVec<[FaunaSeed; 8]> {
    let mut out = SmallVec::<[FaunaSeed; 8]>::new();
    let niches: &[FaunaNiche] = match dominant_biome {
        Biome::Ocean | Biome::CoastalSea => &[FaunaNiche(0)],
        Biome::Ice | Biome::Tundra => &[FaunaNiche(10), FaunaNiche(20)],
        Biome::BorealForest => &[FaunaNiche(11), FaunaNiche(12), FaunaNiche(21)],
        Biome::TemperateForest | Biome::TemperateRainforest => {
            &[FaunaNiche(13), FaunaNiche(14), FaunaNiche(22)]
        }
        Biome::Grassland | Biome::Savanna => &[FaunaNiche(15), FaunaNiche(23)],
        Biome::HotDesert | Biome::ColdDesert => &[FaunaNiche(16)],
        Biome::TropicalDryForest | Biome::TropicalRainforest => {
            &[FaunaNiche(17), FaunaNiche(24)]
        }
        Biome::Shrubland => &[FaunaNiche(18)],
        Biome::Wetland => &[FaunaNiche(19)],
        Biome::AlpineRock => &[FaunaNiche(25)],
    };

    for (k, niche) in niches.iter().enumerate() {
        let cx_v = cx * CHUNK_SIZE_X + CHUNK_SIZE_X / 2;
        let cy_v = cy * CHUNK_SIZE_Y + CHUNK_SIZE_Y / 2;
        let count = prf
            .range(0xFA00_0000 | k as u32, cx, cy, 0, 0, 12)
            + 1;
        out.push(FaunaSeed {
            center: WorldCoord::new(cx_v, cy_v, 64),
            niche: *niche,
            count,
        });
    }
    out
}

#[inline]
const fn biome_density(b: Biome) -> f32 {
    match b {
        Biome::TropicalRainforest | Biome::TemperateRainforest => 0.85,
        Biome::TropicalDryForest | Biome::TemperateForest | Biome::BorealForest => 0.6,
        Biome::Savanna => 0.30,
        Biome::Grassland | Biome::Shrubland => 0.20,
        Biome::Wetland => 0.45,
        Biome::Tundra => 0.05,
        Biome::HotDesert | Biome::ColdDesert | Biome::Ice | Biome::AlpineRock => 0.01,
        Biome::Ocean | Biome::CoastalSea => 0.0,
    }
}

#[inline]
const fn biome_species_count(b: Biome) -> u32 {
    match b {
        Biome::TropicalRainforest => 24,
        Biome::TropicalDryForest => 14,
        Biome::TemperateRainforest => 16,
        Biome::TemperateForest => 18,
        Biome::BorealForest => 8,
        Biome::Savanna => 10,
        Biome::Grassland => 12,
        Biome::Shrubland => 8,
        Biome::Wetland => 14,
        Biome::Tundra => 4,
        Biome::HotDesert | Biome::ColdDesert => 3,
        Biome::Ice | Biome::AlpineRock => 1,
        Biome::Ocean | Biome::CoastalSea => 1,
    }
}

#[inline]
const fn biome_species_base(b: Biome) -> u32 {
    (b as u32) * 100
}
