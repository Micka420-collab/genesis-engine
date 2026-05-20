//! Monotonic simulation tick.

use bytemuck::{Pod, Zeroable};
use serde::{Deserialize, Serialize};

/// Monotonic simulation tick (u64). 1 tick = 1 sim step, NOT 1 wall-clock unit.
#[repr(transparent)]
#[derive(
    Copy,
    Clone,
    Debug,
    Default,
    PartialEq,
    Eq,
    PartialOrd,
    Ord,
    Hash,
    Pod,
    Zeroable,
    Serialize,
    Deserialize,
)]
pub struct Tick(pub u64);

impl Tick {
    /// Tick 0.
    pub const ZERO: Tick = Tick(0);

    /// Next tick.
    #[inline]
    #[must_use]
    pub const fn next(self) -> Tick {
        Tick(self.0.wrapping_add(1))
    }
}

impl core::ops::Add<u64> for Tick {
    type Output = Tick;
    #[inline]
    fn add(self, rhs: u64) -> Tick {
        Tick(self.0.wrapping_add(rhs))
    }
}

impl core::ops::Sub for Tick {
    type Output = u64;
    #[inline]
    fn sub(self, rhs: Tick) -> u64 {
        self.0.wrapping_sub(rhs.0)
    }
}
