//! World snapshot / restore — RL checkpoints and deterministic replay.

use genesis_core::{ChunkCoord, CHUNK_VOXEL_COUNT, WorldCoord};
use serde::{Deserialize, Serialize};

/// Serializable chunk delta (mutated voxels only when version > 0).
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ChunkSnapshot {
    /// Chunk X index.
    pub cx: i32,
    /// Chunk Y index.
    pub cy: i32,
    /// Mutation version at capture time.
    pub version: u64,
    /// Full voxel buffer (flat XYZ).
    pub voxels: Vec<u16>,
    /// Spawned entities: `(x, y, z, blueprint, actor_id)`.
    pub spawned: Vec<(i32, i32, i32, u64, u64)>,
}

/// Full world snapshot for agent runtime resume.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct WorldSnapshot {
    /// World seed (cross-check on restore).
    pub seed: u64,
    /// Simulation tick.
    pub tick: u64,
    /// All cached / mutated chunks.
    pub chunks: Vec<ChunkSnapshot>,
}

/// Snapshot errors.
#[derive(Debug, thiserror::Error)]
pub enum SnapshotError {
    /// Bincode serialization failed.
    #[error("bincode: {0}")]
    Bincode(#[from] bincode::Error),
    /// Compression / IO failed.
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    /// Voxel buffer length mismatch on restore.
    #[error("chunk voxel length mismatch at ({cx}, {cy})")]
    VoxelLenMismatch {
        /// Chunk X.
        cx: i32,
        /// Chunk Y.
        cy: i32,
    },
}

/// Serialize to zstd-compressed bincode.
pub fn save(s: &WorldSnapshot, level: i32) -> Result<Vec<u8>, SnapshotError> {
    let raw = bincode::serialize(s)?;
    let zipped = zstd::stream::encode_all(raw.as_slice(), level)?;
    Ok(zipped)
}

/// Restore from compressed bytes.
pub fn load(bytes: &[u8]) -> Result<WorldSnapshot, SnapshotError> {
    let raw = zstd::stream::decode_all(bytes)?;
    Ok(bincode::deserialize(&raw)?)
}

/// BLAKE3 hash of canonical bincode (determinism tests).
#[must_use]
pub fn hash_snapshot(s: &WorldSnapshot) -> [u8; 32] {
    let raw = bincode::serialize(s).expect("snapshot serialize");
    *blake3::hash(&raw).as_bytes()
}

impl ChunkSnapshot {
    /// Build from a live chunk coordinate and buffers.
    pub fn from_chunk(
        coord: ChunkCoord,
        version: u64,
        voxels: Vec<u16>,
        spawns: &[(WorldCoord, u64, u64)],
    ) -> Self {
        let spawned = spawns
            .iter()
            .filter(|(p, _, _)| p.chunk() == coord)
            .map(|(p, bp, actor)| (p.x, p.y, p.z, *bp, *actor))
            .collect();
        Self {
            cx: coord.cx,
            cy: coord.cy,
            version,
            voxels,
            spawned,
        }
    }

    /// Expected voxel buffer length.
    #[must_use]
    pub const fn voxel_len() -> usize {
        CHUNK_VOXEL_COUNT
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> WorldSnapshot {
        WorldSnapshot {
            seed: 0xC0FFEE,
            tick: 12345,
            chunks: vec![ChunkSnapshot {
                cx: 0,
                cy: 0,
                version: 7,
                voxels: vec![0u16; CHUNK_VOXEL_COUNT],
                spawned: vec![(1, 2, 3, 0xAABB, 999)],
            }],
        }
    }

    #[test]
    fn snapshot_restore_identity() {
        let s0 = sample();
        let bytes = save(&s0, 3).unwrap();
        let s1 = load(&bytes).unwrap();
        assert_eq!(s0, s1);
        let bytes2 = save(&s1, 3).unwrap();
        assert_eq!(bytes, bytes2);
    }

    #[test]
    fn snapshot_hash_is_stable() {
        let s = sample();
        assert_eq!(hash_snapshot(&s), hash_snapshot(&s));
    }
}
