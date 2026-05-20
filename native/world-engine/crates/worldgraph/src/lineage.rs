//! Lineage — traceable record of which passes contributed to which output.
//!
//! When debugging "why is this voxel water?", a lineage trace shows the
//! chain of passes and their cache keys. Two same lineages ⇒ same output
//! by definition (content addressing).

use genesis_cache::CacheKey;
use serde::{Deserialize, Serialize};
use smallvec::SmallVec;

/// One node in a lineage chain.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LineageNode {
    /// Pass id ("terrain.heightmap.v1").
    pub pass_id: String,
    /// Params hash.
    pub params_hash: u64,
    /// Cache key produced.
    pub cache_key_hex: String,
    /// Whether the value came from cache (vs. fresh `run`).
    pub from_cache: bool,
    /// Run time in microseconds (only meaningful when `from_cache = false`).
    pub run_time_us: u64,
}

/// Chain of passes that produced an output.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Lineage {
    /// Nodes in execution order.
    pub nodes: SmallVec<[LineageNode; 8]>,
}

impl Lineage {
    /// New empty lineage.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Push a node.
    pub fn push(&mut self, pass_id: &str, params_hash: u64, key: CacheKey, from_cache: bool, run_time_us: u64) {
        self.nodes.push(LineageNode {
            pass_id: pass_id.to_string(),
            params_hash,
            cache_key_hex: key.to_hex(),
            from_cache,
            run_time_us,
        });
    }

    /// Pretty-print the lineage as a multi-line string.
    #[must_use]
    pub fn explain(&self) -> String {
        let mut s = String::new();
        for (i, n) in self.nodes.iter().enumerate() {
            let tag = if n.from_cache { "cache" } else { "fresh" };
            s.push_str(&format!(
                "{:>2}. {:<32} [{}] params=0x{:016x} key=…{} {}us\n",
                i,
                n.pass_id,
                tag,
                n.params_hash,
                &n.cache_key_hex[..12],
                n.run_time_us,
            ));
        }
        s
    }
}
