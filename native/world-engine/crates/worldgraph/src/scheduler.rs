//! Scheduler — drives a [`Pipeline`] for a given `(seed, coord, tick)`.
//!
//! Caching strategy: at each step, the scheduler computes the cache key of
//! the input + pass, asks the cache, and either:
//!  - returns a cached output (no `run` invocation), or
//!  - invokes `run`, stores the output in L1 (type-erased) and L2
//!    (serialized via the `DynPass` round-trip), and forwards it.
//!
//! The L1 cache stores `Arc<dyn Any + Send + Sync>` — the scheduler downcasts
//! to the next pass's input type. Misuse panics with a clear diagnostic; in
//! practice the type chain is checked at the start of every step via the
//! pass's reported `type_names`.

use crate::branch::BranchId;
use crate::ctx::PassCtx;
use crate::lineage::Lineage;
use crate::pass::ContentAddressable;
use crate::pipeline::{Pipeline, PipelineRun};
use genesis_cache::{Cache, CacheKey};
use genesis_core::{MultiRateCoupler, TickDomain};
use serde::{de::DeserializeOwned, Serialize};
use smallvec::SmallVec;
use std::any::Any;
use std::sync::Arc;

/// Runtime statistics from one scheduler run.
#[derive(Copy, Clone, Debug, Default)]
pub struct SchedulerStats {
    /// Cache hits.
    pub hits: u32,
    /// Cache misses (passes that had to be `run`).
    pub misses: u32,
    /// Total scheduler wall time (microseconds).
    pub total_us: u64,
}

/// Pipeline scheduler.
#[derive(Clone)]
pub struct Scheduler {
    cache: Arc<Cache>,
}

impl Scheduler {
    /// New scheduler with the given cache.
    #[must_use]
    pub fn new(cache: Cache) -> Self {
        Self {
            cache: Arc::new(cache),
        }
    }

    /// Access the underlying cache.
    #[must_use]
    pub fn cache(&self) -> Arc<Cache> {
        Arc::clone(&self.cache)
    }

    /// Run a pipeline. `I` is the type of the **initial input** the caller
    /// hands in. `O` is the type expected from the **last** pass.
    pub fn run<I, O>(
        &self,
        pipeline: &Pipeline<I, O>,
        ctx: &PassCtx,
        initial: I,
    ) -> (O, Lineage, SchedulerStats)
    where
        I: ContentAddressable + Send + Sync + 'static,
        O: ContentAddressable
            + Clone
            + Send
            + Sync
            + 'static
            + Serialize
            + DeserializeOwned,
    {
        let t0 = std::time::Instant::now();
        let mut lineage = Lineage::new();
        let mut stats = SchedulerStats::default();

        // The current value lives behind an Arc<Any>. The first step sees
        // the caller's initial input, wrapped here.
        let mut current: Arc<dyn Any + Send + Sync> = Arc::new(initial);
        let mut current_type: &'static str = std::any::type_name::<I>();

        for step in &pipeline.steps {
            let dp = step.dyn_pass();
            let (in_type, out_type) = dp.type_names();
            if in_type != current_type {
                panic!(
                    "type mismatch in pipeline at step {:?}: current is {:?}, expected {:?}",
                    dp.id(),
                    current_type,
                    in_type
                );
            }

            let key = dp.cache_key(ctx, current.as_ref());

            // L1 type-erased lookup
            let next: Arc<dyn Any + Send + Sync> = if let Some(arc) = self.cache.l1().get_erased(key) {
                stats.hits += 1;
                lineage.push(dp.id(), dp.params_hash(), key, true, 0);
                arc
            } else if let Some(bytes) = self.try_load_l2_bytes(key) {
                // L2 hit — deserialize through the pass and warm L1.
                match dp.deserialize_output(&bytes) {
                    Ok(arc) => {
                        self.cache.l1().insert_erased(key, Arc::clone(&arc));
                        stats.hits += 1;
                        lineage.push(dp.id(), dp.params_hash(), key, true, 0);
                        arc
                    }
                    Err(e) => {
                        tracing::warn!(?key, %e, "L2 deserialize failed, falling back to run");
                        self.execute_pass(dp, ctx, &current, key, &mut stats, &mut lineage)
                    }
                }
            } else {
                self.execute_pass(dp, ctx, &current, key, &mut stats, &mut lineage)
            };

            current = next;
            current_type = out_type;
        }

        if current_type != std::any::type_name::<O>() {
            panic!(
                "pipeline final type mismatch: got {:?}, expected {:?}",
                current_type,
                std::any::type_name::<O>()
            );
        }
        let final_out: O = current
            .downcast::<O>()
            .map(|arc| (*arc).clone())
            .unwrap_or_else(|_| {
                panic!("pipeline final downcast — types matched, this is unreachable");
            });
        stats.total_us = t0.elapsed().as_micros() as u64;
        (final_out, lineage, stats)
    }

    fn execute_pass(
        &self,
        dp: &dyn crate::pipeline::DynPass,
        ctx: &PassCtx,
        input: &Arc<dyn Any + Send + Sync>,
        key: CacheKey,
        stats: &mut SchedulerStats,
        lineage: &mut Lineage,
    ) -> Arc<dyn Any + Send + Sync> {
        let t = std::time::Instant::now();
        let out = dp.run_erased(ctx, input.as_ref());
        let run_us = t.elapsed().as_micros() as u64;
        // Persist the output: L1 type-erased + L2 typed bytes.
        self.cache.l1().insert_erased(key, Arc::clone(&out));
        if let Some(l2) = self.cache.l2() {
            if let Ok(bytes) = dp.serialize_output(out.as_ref()) {
                let _ = l2.store_bytes(key, &bytes);
            }
        }
        stats.misses += 1;
        lineage.push(dp.id(), dp.params_hash(), key, false, run_us);
        out
    }

    fn try_load_l2_bytes(&self, key: CacheKey) -> Option<Vec<u8>> {
        self.cache.l2().and_then(|l2| l2.load_bytes(key).ok().flatten())
    }

    /// Advance the multi-rate coupler and run the pipeline once per fired domain.
    ///
    /// Each fired domain gets a [`PassCtx`] whose `tick` is the domain-local
    /// mapping from the coupler. Returns outputs keyed by domain (last wins if
    /// multiple — callers typically use a single-domain pipeline per hook).
    pub fn run_coupled_step<I, O>(
        &self,
        pipeline: &Pipeline<I, O>,
        base_ctx: &PassCtx,
        coupler: &mut MultiRateCoupler,
        branch: BranchId,
        initial: I,
    ) -> (CouplerStep, SmallVec<[(TickDomain, O, Lineage); 4]>)
    where
        I: ContentAddressable + Clone + Send + Sync + 'static,
        O: ContentAddressable
            + Clone
            + Send
            + Sync
            + 'static
            + Serialize
            + DeserializeOwned,
    {
        let step = coupler.advance();
        let mut results = SmallVec::new();
        for domain in step.fired.iter().copied() {
            let mut ctx = *base_ctx;
            ctx.tick = coupler.tick_for_pass_ctx(domain);
            ctx.domain = Some(domain);
            let _branch_hash = branch.mix_params_hash(0);
            let (out, lineage, _) = self.run(pipeline, &ctx, initial.clone());
            results.push((domain, out, lineage));
        }
        (step, results)
    }

    /// Wrap a pipeline run with a typed L2 round-trip on the **final** output.
    pub fn run_with_l2<I, O>(
        &self,
        pipeline: &Pipeline<I, O>,
        ctx: &PassCtx,
        pipeline_id: &str,
        initial: I,
    ) -> PipelineRun<O>
    where
        I: ContentAddressable + Send + Sync + 'static,
        O: ContentAddressable
            + Clone
            + Send
            + Sync
            + 'static
            + Serialize
            + DeserializeOwned,
    {
        let key = genesis_cache::KeyBuilder::new()
            .mix("pipeline.id", pipeline_id.as_bytes())
            .mix_u64("ctx.seed", ctx.seed.0 as u64)
            .mix_u64("ctx.seed.hi", (ctx.seed.0 >> 64) as u64)
            .mix_i32("ctx.cx", ctx.coord.cx)
            .mix_i32("ctx.cy", ctx.coord.cy)
            .mix_u64("ctx.tick", ctx.tick.0)
            .build();

        if let Some(v) = self.cache.get::<O>(key) {
            let mut lineage = Lineage::new();
            lineage.push(pipeline_id, 0, key, true, 0);
            return PipelineRun { output: v, lineage };
        }

        let (out, lineage, _stats) = self.run(pipeline, ctx, initial);
        let _ = self.cache.put(key, out.clone());
        PipelineRun { output: out, lineage }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pass::{Pass, PassId};
    use genesis_cache::Cache;
    use genesis_core::{ChunkCoord, Tick, WorldSeed};
    use serde::{Deserialize, Serialize};
    use std::sync::atomic::{AtomicU32, Ordering};

    #[derive(Clone, Debug, Serialize, Deserialize)]
    struct Foo(u32);

    impl ContentAddressable for Foo {
        fn hash_into(&self, h: &mut blake3::Hasher) {
            h.update(&self.0.to_le_bytes());
        }
    }

    #[derive(Clone, Debug, Serialize, Deserialize)]
    struct Bar(u64);

    impl ContentAddressable for Bar {
        fn hash_into(&self, h: &mut blake3::Hasher) {
            h.update(&self.0.to_le_bytes());
        }
    }

    struct Double {
        counter: Arc<AtomicU32>,
    }

    impl Pass for Double {
        type Input = Foo;
        type Output = Bar;
        fn id(&self) -> PassId {
            PassId("test.double.v1")
        }
        fn params_hash(&self) -> u64 {
            0
        }
        fn run(&self, _ctx: &PassCtx, input: &Foo) -> Bar {
            self.counter.fetch_add(1, Ordering::SeqCst);
            Bar((input.0 as u64) * 2)
        }
    }

    #[test]
    fn pipeline_runs() {
        let cache = Cache::memory(64);
        let sched = Scheduler::new(cache);
        let counter = Arc::new(AtomicU32::new(0));
        let pipeline: Pipeline<Foo, Bar> =
            Pipeline::new().then(Double { counter: counter.clone() });
        let ctx = PassCtx::new(
            WorldSeed::from_u64(1),
            ChunkCoord { cx: 0, cy: 0 },
            Tick::ZERO,
        );
        let r = sched.run_with_l2(&pipeline, &ctx, "test.pipeline.v1", Foo(21));
        assert_eq!(r.output.0, 42);
        assert_eq!(counter.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn intermediate_caching_avoids_rerun() {
        // Two pipelines that share the upstream `Double` pass for the same
        // (ctx, input). Second run must NOT increment the counter.
        let cache = Cache::memory(64);
        let sched = Scheduler::new(cache);
        let counter = Arc::new(AtomicU32::new(0));

        let ctx = PassCtx::new(
            WorldSeed::from_u64(7),
            ChunkCoord { cx: 0, cy: 0 },
            Tick::ZERO,
        );

        let p1: Pipeline<Foo, Bar> =
            Pipeline::new().then(Double { counter: counter.clone() });
        let _ = sched.run(&p1, &ctx, Foo(21));
        assert_eq!(counter.load(Ordering::SeqCst), 1);

        // Building a fresh pipeline with a new closure-bearing `Double`
        // but identical params_hash + input still hits the cache.
        let p2: Pipeline<Foo, Bar> =
            Pipeline::new().then(Double { counter: counter.clone() });
        let (_, lineage, stats) = sched.run(&p2, &ctx, Foo(21));
        assert_eq!(stats.hits, 1, "expected one cache hit");
        assert_eq!(counter.load(Ordering::SeqCst), 1, "Double must not re-run");
        assert!(lineage.nodes.last().unwrap().from_cache);
    }

    #[test]
    fn two_passes_share_intermediate_cache() {
        let cache = Cache::memory(64);
        let sched = Scheduler::new(cache);
        let c1 = Arc::new(AtomicU32::new(0));
        let c2 = Arc::new(AtomicU32::new(0));

        #[derive(Clone, Serialize, Deserialize)]
        struct Plus1(u64);
        impl ContentAddressable for Plus1 {
            fn hash_into(&self, h: &mut blake3::Hasher) {
                h.update(&self.0.to_le_bytes());
            }
        }

        struct AddOne {
            counter: Arc<AtomicU32>,
        }
        impl Pass for AddOne {
            type Input = Bar;
            type Output = Plus1;
            fn id(&self) -> PassId {
                PassId("test.addone.v1")
            }
            fn params_hash(&self) -> u64 {
                0
            }
            fn run(&self, _ctx: &PassCtx, input: &Bar) -> Plus1 {
                self.counter.fetch_add(1, Ordering::SeqCst);
                Plus1(input.0 + 1)
            }
        }

        let ctx = PassCtx::new(
            WorldSeed::from_u64(0),
            ChunkCoord { cx: 0, cy: 0 },
            Tick::ZERO,
        );

        // First run: both passes execute.
        let p_full: Pipeline<Foo, Plus1> = Pipeline::new()
            .then(Double { counter: c1.clone() })
            .then(AddOne { counter: c2.clone() });
        let (out1, _, stats1) = sched.run(&p_full, &ctx, Foo(10));
        assert_eq!(out1.0, 21);
        assert_eq!(stats1.misses, 2);
        assert_eq!(stats1.hits, 0);

        // Second run, same input: BOTH should hit cache.
        let (out2, _, stats2) = sched.run(&p_full, &ctx, Foo(10));
        assert_eq!(out2.0, 21);
        assert_eq!(stats2.hits, 2, "both passes should be cached");
        assert_eq!(stats2.misses, 0);
        assert_eq!(c1.load(Ordering::SeqCst), 1);
        assert_eq!(c2.load(Ordering::SeqCst), 1);

        // Third run with a DIFFERENT input: first pass re-runs, second pass
        // hits cache only if Double(20) produces a Bar that AddOne hasn't
        // seen — it won't, since 20 ≠ 10. Both should miss.
        let (out3, _, stats3) = sched.run(&p_full, &ctx, Foo(20));
        assert_eq!(out3.0, 41);
        assert_eq!(stats3.misses, 2);
        assert_eq!(c1.load(Ordering::SeqCst), 2);
        assert_eq!(c2.load(Ordering::SeqCst), 2);
    }

    #[test]
    fn changing_params_invalidates_cache() {
        let cache = Cache::memory(64);
        let sched = Scheduler::new(cache);
        let counter = Arc::new(AtomicU32::new(0));

        struct Param {
            counter: Arc<AtomicU32>,
            param: u64,
        }
        impl Pass for Param {
            type Input = Foo;
            type Output = Bar;
            fn id(&self) -> PassId {
                PassId("test.param.v1")
            }
            fn params_hash(&self) -> u64 {
                self.param
            }
            fn run(&self, _ctx: &PassCtx, input: &Foo) -> Bar {
                self.counter.fetch_add(1, Ordering::SeqCst);
                Bar((input.0 as u64) + self.param)
            }
        }

        let ctx = PassCtx::new(
            WorldSeed::from_u64(0),
            ChunkCoord { cx: 0, cy: 0 },
            Tick::ZERO,
        );

        let p1: Pipeline<Foo, Bar> = Pipeline::new().then(Param {
            counter: counter.clone(),
            param: 1,
        });
        let _ = sched.run(&p1, &ctx, Foo(0));

        let p2: Pipeline<Foo, Bar> = Pipeline::new().then(Param {
            counter: counter.clone(),
            param: 2,
        });
        let _ = sched.run(&p2, &ctx, Foo(0));

        assert_eq!(
            counter.load(Ordering::SeqCst),
            2,
            "different params must invalidate cache"
        );
    }
}
