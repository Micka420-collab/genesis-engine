//! Minimal driver: generate a 4×4 chunk patch, print biome distribution
//! and per-chunk timing.

use genesis_core::{ChunkCoord, WorldSeed};
use genesis_streaming::manager::ChunkManagerConfig;
use genesis_streaming::ChunkManager;
use std::time::Instant;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let cfg = ChunkManagerConfig::default();
    let mgr = ChunkManager::new(WorldSeed::from_u64(0xC0FFEE), cfg);

    let mut total = std::time::Duration::ZERO;
    let mut biome_hist = [0u32; 16];

    for cy in 0..4 {
        for cx in 0..4 {
            let t0 = Instant::now();
            let chunk = mgr.get_or_generate(ChunkCoord { cx, cy }).await;
            let dt = t0.elapsed();
            total += dt;
            for b in &chunk.biome {
                biome_hist[*b as usize] += 1;
            }
            println!(
                "chunk ({cx:>3},{cy:>3}) generated in {:>5.1} ms — {} flora, {} fauna seeds",
                dt.as_secs_f32() * 1000.0,
                chunk.flora.len(),
                chunk.fauna.len()
            );
        }
    }

    println!("\nTotal: {:?} for 16 chunks ({:.1} ms/chunk avg)",
        total, total.as_secs_f32() * 1000.0 / 16.0);

    println!("\nBiome distribution:");
    let names = [
        "Ocean", "CoastalSea", "Ice", "Tundra", "BorealForest", "TemperateForest",
        "TemperateRainforest", "Grassland", "HotDesert", "ColdDesert", "Savanna",
        "TropicalDryForest", "TropicalRainforest", "Shrubland", "Wetland", "AlpineRock",
    ];
    for (i, c) in biome_hist.iter().enumerate() {
        if *c > 0 {
            println!("  {:>20}: {c}", names[i]);
        }
    }
}
