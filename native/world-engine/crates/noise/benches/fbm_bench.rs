use criterion::{black_box, criterion_group, criterion_main, Criterion};
use genesis_core::Prf;
use genesis_noise::{fbm2, simplex2, FbmParams};

fn bench_simplex2(c: &mut Criterion) {
    let prf = Prf::new(42);
    c.bench_function("simplex2 256x256", |b| {
        b.iter(|| {
            let mut acc = 0.0f32;
            for j in 0..256 {
                for i in 0..256 {
                    acc += simplex2(
                        prf,
                        0,
                        black_box(i as f32 * 0.01),
                        black_box(j as f32 * 0.01),
                    );
                }
            }
            acc
        })
    });
}

fn bench_fbm2(c: &mut Criterion) {
    let prf = Prf::new(42);
    let params = FbmParams::default();
    c.bench_function("fbm2 256x256 5oct", |b| {
        b.iter(|| {
            let mut acc = 0.0f32;
            for j in 0..256 {
                for i in 0..256 {
                    acc += fbm2(
                        prf,
                        0,
                        black_box(i as f32),
                        black_box(j as f32),
                        params,
                    );
                }
            }
            acc
        })
    });
}

criterion_group!(benches, bench_simplex2, bench_fbm2);
criterion_main!(benches);
