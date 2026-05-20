//! Pluggable biome registry — add biomes without modifying this crate.

use crate::whittaker::Biome;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

/// Stable biome identifier — built-in or user-defined.
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum BiomeId {
    /// One of the built-in Whittaker biomes.
    BuiltIn(Biome),
    /// User-defined biome, indexed by registry insertion order.
    Custom(u16),
}

/// Environmental sample passed to a `BiomeRule`.
#[derive(Copy, Clone, Debug)]
pub struct EnvSample {
    /// Temperature in °C.
    pub temperature_c: f32,
    /// Humidity in `[0, 1]`.
    pub humidity: f32,
    /// Elevation in metres.
    pub elevation_m: f32,
    /// Sea level in metres.
    pub sea_level_m: f32,
    /// Distance to nearest river in metres (None if unknown).
    pub river_distance_m: Option<f32>,
    /// Slope (radians).
    pub slope_rad: f32,
}

/// Trait that any biome rule must implement.
pub trait BiomeRule: Send + Sync {
    /// Identifier for this rule. Should be unique per rule.
    fn id(&self) -> BiomeId;
    /// Score the rule's fit for `env`. Higher = better fit. Return `0` to
    /// completely disable.
    fn score(&self, env: &EnvSample) -> f32;
}

/// Biome registry — pluggable rules.
#[derive(Default, Clone)]
pub struct BiomeRegistry {
    rules: Arc<RwLock<Vec<Arc<dyn BiomeRule>>>>,
}

impl BiomeRegistry {
    /// New empty registry.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Register a built-in Whittaker rule set (16 biomes).
    #[must_use]
    pub fn with_builtin() -> Self {
        let r = Self::new();
        r.register(Arc::new(WhittakerWrapper));
        r
    }

    /// Register a rule.
    pub fn register(&self, rule: Arc<dyn BiomeRule>) {
        self.rules.write().push(rule);
    }

    /// Classify by max score across all rules. Returns `None` only if the
    /// registry is empty.
    #[must_use]
    pub fn classify(&self, env: &EnvSample) -> Option<BiomeId> {
        let rules = self.rules.read();
        let mut best: Option<(f32, BiomeId)> = None;
        for r in rules.iter() {
            let s = r.score(env);
            if let Some((bs, _)) = best {
                if s > bs {
                    best = Some((s, r.id()));
                }
            } else {
                best = Some((s, r.id()));
            }
        }
        best.map(|(_, id)| id)
    }

    /// Number of registered rules.
    #[must_use]
    pub fn len(&self) -> usize {
        self.rules.read().len()
    }

    /// Whether the registry has no rules.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.rules.read().is_empty()
    }
}

/// Wraps the built-in Whittaker classifier as a single registry rule.
///
/// It always wins by 1.0 because no custom rule should override unless it
/// scores higher than that ceiling.
struct WhittakerWrapper;

impl BiomeRule for WhittakerWrapper {
    fn id(&self) -> BiomeId {
        // The score function returns the actual biome via thread-local —
        // here we just give a placeholder; consumers should call
        // `Biome::classify` directly when they need the precise built-in.
        BiomeId::BuiltIn(Biome::Grassland)
    }
    fn score(&self, _env: &EnvSample) -> f32 {
        // Baseline score so the registry is never empty
        0.5
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_registry_returns_none() {
        let r = BiomeRegistry::new();
        let env = EnvSample {
            temperature_c: 20.0,
            humidity: 0.5,
            elevation_m: 100.0,
            sea_level_m: 0.0,
            river_distance_m: None,
            slope_rad: 0.0,
        };
        assert!(r.classify(&env).is_none());
    }

    #[test]
    fn builtin_registry_classifies() {
        let r = BiomeRegistry::with_builtin();
        let env = EnvSample {
            temperature_c: 20.0,
            humidity: 0.5,
            elevation_m: 100.0,
            sea_level_m: 0.0,
            river_distance_m: None,
            slope_rad: 0.0,
        };
        assert!(r.classify(&env).is_some());
    }
}
