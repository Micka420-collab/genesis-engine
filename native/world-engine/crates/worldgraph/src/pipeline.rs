//! Pipeline — a typed chain of passes.
//!
//! Pipelines are *type-eraced builder structures*: we can't enforce the
//! "output of pass N feeds input of pass N+1" rule at compile time without
//! exotic generic machinery. Instead, each [`Step`] hides one concrete
//! `Pass` impl behind a `dyn` trait object that the [`super::Scheduler`]
//! drives. The scheduler enforces the type contract dynamically; misuse
//! produces a clear runtime error rather than wrong silent output.
//!
//! For most engine pipelines, the type chain is fixed at startup, so this
//! is no worse than `Vec<Box<dyn Trait>>` and considerably simpler to
//! evolve.

use crate::ctx::PassCtx;
use crate::lineage::Lineage;
use crate::pass::{ContentAddressable, Pass};
use genesis_cache::CacheKey;
use std::any::Any;
use std::sync::Arc;
use thiserror::Error;

/// One step in a pipeline — type-erased wrapper around a `Pass`.
#[derive(Clone)]
pub struct Step {
    inner: Arc<dyn DynPass>,
}

/// Pipeline errors.
#[derive(Error, Debug)]
pub enum PipelineError {
    /// Type mismatch between two adjacent passes.
    #[error("type mismatch between step {prev_id:?} (out) and step {next_id:?} (in)")]
    TypeMismatch {
        /// Upstream step id.
        prev_id: &'static str,
        /// Downstream step id.
        next_id: &'static str,
    },
    /// No initial input was provided for a pipeline whose first pass expects
    /// a non-unit input.
    #[error("missing initial input")]
    MissingInput,
}

/// Internal trait — drives a pass without the caller knowing its concrete
/// `Input`/`Output` types. All `Any` references are `Any + Send + Sync` so
/// the trait objects are interchangeable without trait upcasting (which
/// only stabilised in Rust 1.86).
pub(crate) trait DynPass: Send + Sync {
    fn id(&self) -> &'static str;
    fn params_hash(&self) -> u64;
    /// Compute cache key given a type-erased input.
    fn cache_key(&self, ctx: &PassCtx, input: &(dyn Any + Send + Sync)) -> CacheKey;
    /// Run, taking erased input, returning a typed Arc wrapped in Any.
    fn run_erased(
        &self,
        ctx: &PassCtx,
        input: &(dyn Any + Send + Sync),
    ) -> Arc<dyn Any + Send + Sync>;
    /// Hint string for diagnostics.
    fn type_names(&self) -> (&'static str, &'static str);
    /// Serialize a type-erased output (assumed to be `Arc<Self::Output>`).
    fn serialize_output(
        &self,
        output: &(dyn Any + Send + Sync),
    ) -> Result<Vec<u8>, bincode::Error>;
    /// Deserialize bytes into an `Arc<Self::Output>` wrapped in Any.
    fn deserialize_output(
        &self,
        bytes: &[u8],
    ) -> Result<Arc<dyn Any + Send + Sync>, bincode::Error>;
}

struct DynPassImpl<P: Pass> {
    pass: P,
}

impl<P: Pass> DynPass for DynPassImpl<P> {
    fn id(&self) -> &'static str {
        self.pass.id().0
    }
    fn params_hash(&self) -> u64 {
        self.pass.params_hash()
    }
    fn cache_key(&self, ctx: &PassCtx, input: &(dyn Any + Send + Sync)) -> CacheKey {
        let typed: &P::Input = input
            .downcast_ref()
            .expect("scheduler dispatched mismatched input — pipeline bug");
        self.pass.cache_key(ctx, typed)
    }
    fn run_erased(
        &self,
        ctx: &PassCtx,
        input: &(dyn Any + Send + Sync),
    ) -> Arc<dyn Any + Send + Sync> {
        let typed: &P::Input = input
            .downcast_ref()
            .expect("scheduler dispatched mismatched input — pipeline bug");
        let out: P::Output = self.pass.run(ctx, typed);
        Arc::new(out)
    }
    fn type_names(&self) -> (&'static str, &'static str) {
        (
            std::any::type_name::<P::Input>(),
            std::any::type_name::<P::Output>(),
        )
    }
    fn serialize_output(
        &self,
        output: &(dyn Any + Send + Sync),
    ) -> Result<Vec<u8>, bincode::Error> {
        let typed: &P::Output = output
            .downcast_ref()
            .expect("serialize_output got the wrong type — scheduler bug");
        bincode::serialize(typed)
    }
    fn deserialize_output(
        &self,
        bytes: &[u8],
    ) -> Result<Arc<dyn Any + Send + Sync>, bincode::Error> {
        let typed: P::Output = bincode::deserialize(bytes)?;
        Ok(Arc::new(typed))
    }
}

impl Step {
    /// Wrap a `Pass` into a `Step`.
    #[must_use]
    pub fn from_pass<P: Pass>(pass: P) -> Self {
        Self {
            inner: Arc::new(DynPassImpl { pass }),
        }
    }

    /// Pass identifier.
    #[must_use]
    pub fn id(&self) -> &'static str {
        self.inner.id()
    }

    pub(crate) fn dyn_pass(&self) -> &dyn DynPass {
        &*self.inner
    }
}

/// A typed pipeline. The compile-time type parameters track the **caller's
/// expected** input and final output. Internal steps are dynamically typed.
pub struct Pipeline<I, O> {
    pub(crate) steps: Vec<Step>,
    _markers: std::marker::PhantomData<fn(I) -> O>,
}

impl<I, O> Default for Pipeline<I, O> {
    fn default() -> Self {
        Self {
            steps: Vec::new(),
            _markers: std::marker::PhantomData,
        }
    }
}

impl<I, O> Pipeline<I, O> {
    /// Builder: append a step.
    #[must_use]
    pub fn then<S: Pass>(mut self, pass: S) -> Self {
        self.steps.push(Step::from_pass(pass));
        self
    }

    /// New empty pipeline.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Number of steps.
    #[must_use]
    pub fn len(&self) -> usize {
        self.steps.len()
    }

    /// Whether the pipeline is empty.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.steps.is_empty()
    }
}

/// Output of one run of the pipeline.
pub struct PipelineRun<O> {
    /// Final output.
    pub output: O,
    /// Lineage trace.
    pub lineage: Lineage,
}

impl<O: 'static + ContentAddressable + Send + Sync + Clone> PipelineRun<O> {
    /// The final output, consumed.
    #[must_use]
    pub fn into_output(self) -> O {
        self.output
    }
}
