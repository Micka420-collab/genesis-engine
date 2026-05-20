//! Level-of-detail enum (5 levels, see specs/streaming-and-lod-spec.md).

use serde::{Deserialize, Serialize};

/// Discrete LOD levels.
#[repr(u8)]
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Lod {
    /// Full voxel + animations.
    L0Full = 0,
    /// Simplified mesh, rare anim.
    L1Mesh = 1,
    /// 2D impostor.
    L2Impostor = 2,
    /// Pre-rendered tile.
    L3Tile = 3,
    /// Solid colour macroblock.
    L4Macro = 4,
}

impl Lod {
    /// LOD for a chunk at distance `d` (metres) from the nearest observer.
    #[must_use]
    pub const fn for_distance(d: f32) -> Self {
        if d < 32.0 {
            Lod::L0Full
        } else if d < 128.0 {
            Lod::L1Mesh
        } else if d < 1024.0 {
            Lod::L2Impostor
        } else if d < 10_000.0 {
            Lod::L3Tile
        } else {
            Lod::L4Macro
        }
    }
}
