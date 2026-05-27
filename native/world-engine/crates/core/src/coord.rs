//! Coordinate types.
//!
//! `WorldCoord` is the absolute integer coordinate in voxel space.
//! `ChunkCoord` identifies a chunk (64×64×128 voxels).
//! `LocalCoord` is a coordinate inside a chunk.

use bytemuck::{Pod, Zeroable};
use serde::{Deserialize, Serialize};

/// Voxels along X inside a chunk.
pub const CHUNK_SIZE_X: i32 = 64;
/// Voxels along Y inside a chunk.
pub const CHUNK_SIZE_Y: i32 = 64;
/// Voxels along Z (vertical) inside a chunk.
pub const CHUNK_SIZE_Z: i32 = 128;

/// Number of voxels in one chunk.
pub const CHUNK_VOXEL_COUNT: usize =
    (CHUNK_SIZE_X * CHUNK_SIZE_Y * CHUNK_SIZE_Z) as usize;

/// Absolute integer voxel coordinate.
#[repr(C)]
#[derive(
    Copy, Clone, Debug, PartialEq, Eq, Hash, Pod, Zeroable, Serialize, Deserialize,
)]
pub struct WorldCoord {
    /// East-West axis.
    pub x: i32,
    /// North-South axis.
    pub y: i32,
    /// Vertical axis (positive = up).
    pub z: i32,
}

impl WorldCoord {
    /// Build a new world coordinate.
    #[inline]
    #[must_use]
    pub const fn new(x: i32, y: i32, z: i32) -> Self {
        Self { x, y, z }
    }

    /// Chunk containing this coordinate.
    #[inline]
    #[must_use]
    pub const fn chunk(self) -> ChunkCoord {
        ChunkCoord {
            cx: self.x.div_euclid(CHUNK_SIZE_X),
            cy: self.y.div_euclid(CHUNK_SIZE_Y),
        }
    }

    /// Position inside the containing chunk.
    #[inline]
    #[must_use]
    pub const fn local(self) -> LocalCoord {
        // `i32::clamp` is still unstable in `const fn` on stable Rust 1.85
        // (rust-lang/rust#115107), so we inline a manual clamp to keep
        // `local()` callable in const contexts.
        let z = if self.z < 0 {
            0
        } else if self.z >= CHUNK_SIZE_Z {
            CHUNK_SIZE_Z - 1
        } else {
            self.z
        };
        LocalCoord {
            x: self.x.rem_euclid(CHUNK_SIZE_X) as u8,
            y: self.y.rem_euclid(CHUNK_SIZE_Y) as u8,
            z: z as u8,
        }
    }
}

/// Chunk identifier in the world (32-bit each axis).
#[repr(C)]
#[derive(
    Copy, Clone, Debug, PartialEq, Eq, Hash, Pod, Zeroable, Serialize, Deserialize,
)]
pub struct ChunkCoord {
    /// Chunk index on the east-west axis.
    pub cx: i32,
    /// Chunk index on the north-south axis.
    pub cy: i32,
}

impl ChunkCoord {
    /// World coordinate of the chunk's south-west corner.
    #[inline]
    #[must_use]
    pub const fn origin(self) -> WorldCoord {
        WorldCoord::new(self.cx * CHUNK_SIZE_X, self.cy * CHUNK_SIZE_Y, 0)
    }

    /// Iterate over the 9 chunks centered on `self` (used for streaming).
    #[must_use]
    pub fn neighbors_3x3(self) -> [ChunkCoord; 9] {
        let mut out = [ChunkCoord { cx: 0, cy: 0 }; 9];
        let mut i = 0;
        for dy in -1..=1 {
            for dx in -1..=1 {
                out[i] = ChunkCoord {
                    cx: self.cx + dx,
                    cy: self.cy + dy,
                };
                i += 1;
            }
        }
        out
    }
}

/// Coordinate inside a chunk.
#[repr(C)]
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Pod, Zeroable)]
pub struct LocalCoord {
    /// Inside-chunk x in `[0, CHUNK_SIZE_X)`.
    pub x: u8,
    /// Inside-chunk y in `[0, CHUNK_SIZE_Y)`.
    pub y: u8,
    /// Inside-chunk z in `[0, CHUNK_SIZE_Z)`.
    pub z: u8,
}

impl LocalCoord {
    /// Flat index for a `[u16; CHUNK_VOXEL_COUNT]` palette buffer.
    #[inline]
    #[must_use]
    pub const fn index(self) -> usize {
        (self.x as usize)
            + (self.y as usize) * (CHUNK_SIZE_X as usize)
            + (self.z as usize) * (CHUNK_SIZE_X as usize) * (CHUNK_SIZE_Y as usize)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn world_coord_round_trip() {
        let c = WorldCoord::new(130, -7, 12);
        let chunk = c.chunk();
        let local = c.local();
        let back = WorldCoord::new(
            chunk.cx * CHUNK_SIZE_X + local.x as i32,
            chunk.cy * CHUNK_SIZE_Y + local.y as i32,
            local.z as i32,
        );
        assert_eq!(c, back);
    }

    #[test]
    fn neighbors_3x3_contains_self() {
        let c = ChunkCoord { cx: 5, cy: -3 };
        assert!(c.neighbors_3x3().contains(&c));
    }
}
