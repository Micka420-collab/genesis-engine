//! genesis-worldgraph — declarative DAG of procedural generation passes.
//!
//! Three primitives:
//!  - [`Pass`] : a pure, content-addressable transformation step.
//!  - [`Pipeline`] : an ordered list of passes typed by [`Step`].
//!  - [`Scheduler`] : runs a pipeline to produce an output for a `(seed, coord)`.
//!
//! Each pass output is cached by `BLAKE3(pass_id || params_hash || input_key || coord_key)`.
//! Same key ⇒ cached hit, with no need to re-run the pass — even across
//! completely different worlds.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod branch;
pub mod ctx;
pub mod lineage;
pub mod pass;
pub mod pipeline;
pub mod scheduler;

pub use branch::{BranchId, CounterfactualBranch};
pub use ctx::PassCtx;
pub use lineage::{Lineage, LineageNode};
pub use pass::{ContentAddressable, Pass, PassId};
pub use pipeline::{Pipeline, Step};
pub use scheduler::{Scheduler, SchedulerStats};
