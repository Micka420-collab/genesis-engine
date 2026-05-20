//! Determinism integration tests — generate the same chunk many times,
//! across threads, and verify bit-for-bit identical output.

use genesis_core::{ChunkCoord, WorldSeed};
use genesis_streaming::manager::ChunkManagerConfig;
use genesis_streaming::ChunkManager;
use std::thread;

fn fast_cfg() -> ChunkManagerConfig {
    ChunkManagerConfig {
        erosion_droplets: 16,
        erosion_passes: 1,
        cache_capacity: 8,
        ..Default::default()
    }
}

fn hash_chunk(chunk: &genesis_streaming::Chunk) -> [u8; 32] {
    let mut h = blake3::Hasher::new();
    for v in &chunk.elevation {
        h.update(&v.to_le_bytes());
    }
    for b in &chunk.biome {
        h.update(&(*b as u8).to_le_bytes());
    }
    for v in &chunk.voxels {
        h.update(&v.to_le_bytes());
    }
    *h.finalize().as_bytes()
}

#[test]
fn same_seed_same_chunk_single_thread() {
    let mgr = ChunkManager::new(WorldSeed::from_u64(42), fast_cfg());
    let a = mgr.generate(ChunkCoord { cx: 3, cy: -7 });
    let b = mgr.generate(ChunkCoord { cx: 3, cy: -7 });
    assert_eq!(hash_chunk(&a), hash_chunk(&b));
}

#[test]
fn same_seed_same_chunk_across_threads() {
    let mgr_a = ChunkManager::new(WorldSeed::from_u64(42), fast_cfg());
    let mgr_b = ChunkManager::new(WorldSeed::from_u64(42), fast_cfg());

    let h_a = thread::spawn(move || {
        let c = mgr_a.generate(ChunkCoord { cx: 1, cy: 1 });
        hash_chunk(&c)
    });
    let h_b = thread::spawn(move || {
        let c = mgr_b.generate(ChunkCoord { cx: 1, cy: 1 });
        hash_chunk(&c)
    });

    let ha = h_a.join().unwrap();
    let hb = h_b.join().unwrap();
    assert_eq!(ha, hb, "thread-1 ≠ thread-2 for same (seed, coord)");
}

#[test]
fn different_seeds_differ() {
    let m1 = ChunkManager::new(WorldSeed::from_u64(1), fast_cfg());
    let m2 = ChunkManager::new(WorldSeed::from_u64(2), fast_cfg());
    let a = m1.generate(ChunkCoord { cx: 0, cy: 0 });
    let b = m2.generate(ChunkCoord { cx: 0, cy: 0 });
    assert_ne!(hash_chunk(&a), hash_chunk(&b));
}
