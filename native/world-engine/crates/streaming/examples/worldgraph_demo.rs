//! Show off the WorldGraph DSL:
//!
//!   1. Build a small declarative pipeline (heightmap → climate → biome).
//!   2. Run it through a content-addressed cache.
//!   3. Print lineage + stats.
//!
//! Run with:
//!
//!     cargo run --release -p genesis-streaming --example worldgraph_demo

use genesis_cache::Cache;
use genesis_core::{ChunkCoord, Prf, Tick, WorldSeed};
use genesis_terrain::TerrainParams;
use genesis_worldgraph::{hash_f32, ContentAddressable, Pass, PassCtx, PassId, Pipeline, Scheduler};
use serde::{Deserialize, Serialize};

/// Initial input: just the chunk coord packed.
#[derive(Clone, Debug, Serialize, Deserialize)]
struct InitInput;

impl ContentAddressable for InitInput {
    fn hash_into(&self, h: &mut blake3::Hasher) {
        h.update(b"init");
    }
}

/// Heightmap pass output.
#[derive(Clone, Debug, Serialize, Deserialize)]
struct HeightOut {
    width: u32,
    height: u32,
    data: Vec<f32>,
}

impl ContentAddressable for HeightOut {
    fn hash_into(&self, h: &mut blake3::Hasher) {
        h.update(&self.width.to_le_bytes());
        h.update(&self.height.to_le_bytes());
        for v in &self.data {
            hash_f32(h, *v);
        }
    }
}

struct HeightPass {
    params: TerrainParams,
}

impl Pass for HeightPass {
    type Input = InitInput;
    type Output = HeightOut;

    fn id(&self) -> PassId {
        PassId("demo.heightmap.v1")
    }

    fn params_hash(&self) -> u64 {
        // Fold a few floats into a stable hash
        let p = self.params;
        let v = [
            p.sea_level.to_bits() as u64,
            p.plate_cell_size.to_bits() as u64,
            (p.continental_ratio.to_bits() as u64) << 16,
            p.relief_amplitude.to_bits() as u64,
            p.ridge_amplitude.to_bits() as u64,
            p.use_domain_warp as u64,
        ];
        v.iter().fold(0xC0FFEE_u64, |a, b| a.rotate_left(11) ^ *b)
    }

    fn run(&self, ctx: &PassCtx, _input: &InitInput) -> HeightOut {
        let prf = Prf::new(ctx.seed.0);
        let hm = genesis_terrain::generate(prf, ctx.coord.cx, ctx.coord.cy, self.params);
        HeightOut {
            width: hm.width,
            height: hm.height,
            data: hm.data,
        }
    }
}

/// Summary metric for the demo's final output.
#[derive(Clone, Debug, Serialize, Deserialize)]
struct Summary {
    min: f32,
    max: f32,
    mean: f32,
}

impl ContentAddressable for Summary {
    fn hash_into(&self, h: &mut blake3::Hasher) {
        hash_f32(h, self.min);
        hash_f32(h, self.max);
        hash_f32(h, self.mean);
    }
}

struct SummaryPass;

impl Pass for SummaryPass {
    type Input = HeightOut;
    type Output = Summary;

    fn id(&self) -> PassId {
        PassId("demo.summary.v1")
    }
    fn params_hash(&self) -> u64 {
        0
    }
    fn run(&self, _ctx: &PassCtx, input: &HeightOut) -> Summary {
        let mut min = f32::MAX;
        let mut max = f32::MIN;
        let mut sum = 0.0;
        for v in &input.data {
            if *v < min {
                min = *v;
            }
            if *v > max {
                max = *v;
            }
            sum += *v;
        }
        Summary {
            min,
            max,
            mean: sum / input.data.len() as f32,
        }
    }
}

fn main() {
    let cache = Cache::memory(64);
    let sched = Scheduler::new(cache);

    let pipeline: Pipeline<InitInput, Summary> = Pipeline::new()
        .then(HeightPass {
            params: TerrainParams::default(),
        })
        .then(SummaryPass);

    println!("Pipeline has {} steps", pipeline.len());

    for cy in 0..2 {
        for cx in 0..2 {
            let ctx = PassCtx::new(
                WorldSeed::from_u64(0xBEEF),
                ChunkCoord { cx, cy },
                Tick::ZERO,
            );
            let t0 = std::time::Instant::now();
            let run = sched.run_with_l2(&pipeline, &ctx, "demo.pipeline.v1", InitInput);
            let dt = t0.elapsed();
            println!(
                "chunk ({:>2},{:>2}) min={:>7.1}m  max={:>7.1}m  mean={:>7.1}m  ({:>5.1} ms)",
                cx, cy, run.output.min, run.output.max, run.output.mean,
                dt.as_secs_f32() * 1000.0
            );
            println!("Lineage:\n{}", run.lineage.explain());
        }
    }

    // Demonstrate the cache: same coord twice — second run is a hit.
    let ctx = PassCtx::new(
        WorldSeed::from_u64(0xBEEF),
        ChunkCoord { cx: 0, cy: 0 },
        Tick::ZERO,
    );
    let t0 = std::time::Instant::now();
    let _ = sched.run_with_l2(&pipeline, &ctx, "demo.pipeline.v1", InitInput);
    println!(
        "re-run (0,0) via top-level cache: {:>5.3} ms",
        t0.elapsed().as_secs_f32() * 1000.0
    );
}
