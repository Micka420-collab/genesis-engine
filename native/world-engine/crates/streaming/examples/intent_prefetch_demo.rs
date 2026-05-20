//! Demonstrate intent-aware prefetching.
//!
//! An "agent" declares a walk path; a background prefetcher warms the
//! chunks the agent will reach. We measure the perceived latency
//! difference between cold reads and prefetched reads.

use genesis_core::{ChunkCoord, WorldCoord, WorldSeed, CHUNK_SIZE_X, CHUNK_SIZE_Y};
use genesis_intent::{spawn_prefetcher, AgentId, Intent, IntentBus, Plan};
use genesis_streaming::manager::ChunkManagerConfig;
use genesis_streaming::ChunkManager;
use std::time::{Duration, Instant};

#[tokio::main(flavor = "multi_thread", worker_threads = 4)]
async fn main() {
    tracing_subscriber::fmt::init();

    let cfg = ChunkManagerConfig {
        erosion_droplets: 64,
        erosion_passes: 2,
        cache_capacity: 512,
        ..Default::default()
    };
    let manager = ChunkManager::new(WorldSeed::from_u64(0xC0FFEE), cfg);
    let bus = IntentBus::new();

    // Spawn the prefetcher.
    let _handle = spawn_prefetcher(bus.clone(), manager.clone(), 20);

    // The agent declares it will walk a long diagonal path.
    let waypoints: Vec<WorldCoord> = (0..16)
        .map(|i| WorldCoord::new(i * CHUNK_SIZE_X, i * CHUNK_SIZE_Y, 0))
        .collect();
    bus.submit(Intent {
        agent: AgentId(1),
        plan: Plan::WalkAlong(waypoints.clone()),
        horizon_ticks: 500,
        priority: 200,
    });

    // Give the prefetcher time to do its thing.
    tokio::time::sleep(Duration::from_millis(600)).await;
    println!("Prefetched {} chunks in cache", manager.cached_count());

    // Walk the path "in real time" — touch each chunk and time the access.
    let mut total_warm_us = 0u64;
    for w in &waypoints {
        let coord = w.chunk();
        let t = Instant::now();
        let _ = manager.get_or_generate(coord).await;
        total_warm_us += t.elapsed().as_micros() as u64;
    }
    println!(
        "Sum of read latencies after prefetch: {} µs ({:.1} µs/chunk)",
        total_warm_us,
        total_warm_us as f32 / waypoints.len() as f32
    );

    // Compare: cold start on a different region the prefetcher hasn't seen.
    let mut cold_us = 0u64;
    for i in 0..waypoints.len() as i32 {
        let coord = ChunkCoord { cx: 1000 + i, cy: -1000 };
        let t = Instant::now();
        let _ = manager.get_or_generate(coord).await;
        cold_us += t.elapsed().as_micros() as u64;
    }
    println!(
        "Sum of cold-read latencies: {} µs ({:.1} µs/chunk)",
        cold_us,
        cold_us as f32 / waypoints.len() as f32
    );
}
