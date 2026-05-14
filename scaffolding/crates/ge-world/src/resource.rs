//! Distribution des ressources extractibles.

use crate::biome::Biome;
use ge_core::{prf_rng, ChunkCoord, WorldSeed};
use rand::Rng;
use serde::{Deserialize, Serialize};

use crate::chunk::{CHUNK_SIZE};

/// Carte de ressources d'un chunk. Densités en kg/m².
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ResourceMap {
    /// Densité de pierre exploitable.
    pub stone: Vec<f32>,
    /// Densité de bois (arbres) — fonction du biome.
    pub wood: Vec<f32>,
    /// Densité de minerai métallique (Fe/Cu).
    pub metal: Vec<f32>,
}

/// Génère la carte ressources d'un chunk de manière déterministe.
pub fn generate_resources(
    seed: WorldSeed,
    coord: ChunkCoord,
    biome: &[Biome],
    height: &[f32],
) -> ResourceMap {
    let n = CHUNK_SIZE * CHUNK_SIZE;
    let mut stone = vec![0.0; n];
    let mut wood = vec![0.0; n];
    let mut metal = vec![0.0; n];

    let mut rng = prf_rng(
        seed,
        &["world", "resources"],
        &[coord.x as u64, coord.y as u64, coord.z as u64],
    );

    for i in 0..n {
        let b = biome[i];
        let elev = height[i];

        // Pierre : croît avec l'élévation et la sécheresse.
        let base_stone = match b {
            Biome::HotDesert | Biome::ColdDesert => 30.0,
            Biome::Tundra | Biome::Ice => 20.0,
            _ => 10.0,
        };
        stone[i] = (base_stone + elev.max(0.0) * 0.02 + rng.gen::<f32>() * 5.0).max(0.0);

        // Bois : surtout les forêts.
        wood[i] = match b {
            Biome::TropicalRainforest => 80.0 + rng.gen::<f32>() * 20.0,
            Biome::TemperateRainforest | Biome::TemperateForest => 50.0 + rng.gen::<f32>() * 15.0,
            Biome::BorealForest | Biome::TropicalDryForest => 30.0 + rng.gen::<f32>() * 10.0,
            Biome::Savanna => 5.0 + rng.gen::<f32>() * 3.0,
            _ => 0.0,
        };

        // Métal : poches rares, indépendant du biome, plutôt en altitude.
        if rng.gen::<f32>() < 0.01 + elev.max(0.0).min(3000.0) / 60_000.0 {
            metal[i] = rng.gen::<f32>() * 50.0;
        }
    }

    ResourceMap { stone, wood, metal }
}
