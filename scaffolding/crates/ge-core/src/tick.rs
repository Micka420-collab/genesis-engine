//! Représentation du temps simulé.

use serde::{Deserialize, Serialize};

/// Tick simulé. Unité atomique de temps.
/// 1 tick = (1 / tick_rate) seconde simulée.
#[derive(Copy, Clone, Eq, PartialEq, Ord, PartialOrd, Hash, Debug, Serialize, Deserialize)]
#[repr(transparent)]
pub struct Tick(pub u64);

impl Tick {
    pub const ZERO: Tick = Tick(0);

    #[inline]
    pub fn next(self) -> Tick { Tick(self.0 + 1) }

    #[inline]
    pub fn get(self) -> u64 { self.0 }
}

/// Échelle temporelle.
#[derive(Copy, Clone, Eq, PartialEq, Debug, Serialize, Deserialize)]
pub enum TimeScale {
    Realtime,    // x1
    Standard,    // x10
    Fast,        // x100
    Eon,         // x1000
    Geological,  // x10000
}

impl TimeScale {
    pub const fn factor(self) -> u32 {
        match self {
            Self::Realtime => 1,
            Self::Standard => 10,
            Self::Fast => 100,
            Self::Eon => 1_000,
            Self::Geological => 10_000,
        }
    }
}
