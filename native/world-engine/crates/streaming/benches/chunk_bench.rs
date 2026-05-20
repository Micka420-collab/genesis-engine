use criterion::{black_box, criterion_group, criterion_main, Criterion};
use genesis_core::{ChunkCoord, WorldSeed};
use genesis_streaming::manager::ChunkManagerConfig;
use genesis_streaming::ChunkManager;

fn bench_generate(c: &mut Criterion) {
    let cfg = ChunkManagerConfig {
        erosion_droplets: 200,
        erosion_passes: 4,
        cache_capacity: 64,
        ..Default::default()
    };
    let mgr = ChunkManager::new(WorldSeed::from_u64(0xC0FFEE), cfg);

    c.bench_function("generate chunk (full)", |b| {
        let mut i = 0i32;
        b.iter(|| {
            // Walk the world so we don't hit cache
            i += 1;
            black_box(mgr.generate(ChunkCoord { cx: i, cy: 0 }))
        })
    });
}

criterion_group!(benches, bench_generate);
criterion_main!(benches);
