//! Counterfactual branches — tag alternate WorldGraph runs for A/B comparison.

use serde::{Deserialize, Serialize};

/// Identifier for a counterfactual branch (0 = baseline / control).
#[derive(Copy, Clone, Debug, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct BranchId(pub u32);

impl BranchId {
    /// Control run (no override).
    pub const BASELINE: BranchId = BranchId(0);

    /// Mix branch id into a pass params hash (deterministic).
    #[must_use]
    pub fn mix_params_hash(self, base: u64) -> u64 {
        if self.0 == 0 {
            return base;
        }
        base.wrapping_mul(0x9E37_79B9_7F4A_7C15).wrapping_add(self.0 as u64)
    }
}

/// Specification for a counterfactual experiment arm.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CounterfactualBranch {
    /// Branch id (non-zero for alternates).
    pub id: BranchId,
    /// Human label ("+2K warming", "no erosion", …).
    pub label: String,
    /// Optional scalar override applied by scenario tooling (meaning per pass).
    pub scalar_override: f64,
}

impl CounterfactualBranch {
    /// Baseline branch.
    #[must_use]
    pub fn baseline() -> Self {
        Self {
            id: BranchId::BASELINE,
            label: "baseline".to_string(),
            scalar_override: 0.0,
        }
    }

    /// Alternate branch with label and override.
    #[must_use]
    pub fn alternate(id: u32, label: impl Into<String>, scalar_override: f64) -> Self {
        Self {
            id: BranchId(id),
            label: label.into(),
            scalar_override,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn baseline_preserves_hash() {
        assert_eq!(BranchId::BASELINE.mix_params_hash(42), 42);
    }

    #[test]
    fn alternate_changes_hash() {
        let h0 = BranchId::BASELINE.mix_params_hash(42);
        let h1 = BranchId(1).mix_params_hash(42);
        assert_ne!(h0, h1);
    }
}
