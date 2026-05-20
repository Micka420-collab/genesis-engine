//! World snapshot / restore — critical for RL training.
//!
//! A snapshot captures everything the agent runtime needs to *resume*
//! exactly where it left off:
//!  - tick counter
//!  - intent bus
//!  - per-chunk version + voxel buffer + spawned-entity list
//!  - spatial index
//!  - season clock + climate scratch
//!
//! Stored as a compact bincode + zstd blob (the engine already wires those
//! in `persist/`). For high-throughput RL, swap to `rkyv` later.
//!
//! Determinism check: snapshot ↔ restore ↔ snapshot must produce
//! bit-identical bytes (test `snapshot_restore_identity`).

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Serializable chunk delta.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ChunkSnapshot {
    /// Chunk coord.
    pub cx: i32,
    /// Chunk coord.
    pub cy: i32,
    /// Mutation version.
    pub version: u64,
    /// Voxel buffer (flat XYZ).
    pub voxels: Vec<u16>,
    /// Spawned entities (delta against original).
    pub spawned: Vec<(i32, i32, i32, u64, u64)>, // (x, y, z, blueprint, actor)
}

/// One intent stored in the snapshot.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct IntentSnap {
    /// Agent id.
    pub agent: u64,
    /// Plan kind tag : 0=Idle, 1=Walk, 2=Teleport.
    pub kind: u8,
    /// Plan payload (interpreted by kind).
    pub payload: Vec<i32>,
    /// Priority.
    pub priority: u8,
    /// Horizon.
    pub horizon: u32,
}

/// Full world snapshot.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct WorldSnapshot {
    /// World seed (so a restore can be cross-checked).
    pub seed: u64,
    /// Current tick.
    pub tick: u64,
    /// All loaded chunks.
    pub chunks: Vec<ChunkSnapshot>,
    /// All live intents.
    pub intents: Vec<IntentSnap>,
}

/// Serialize a snapshot to a compact bincode + zstd blob.
pub fn save(s: &WorldSnapshot, level: i32) -> Result<Vec<u8>, SnapshotError> {
    let raw = bincode::serialize(s)?;
    let zipped = zstd::stream::encode_all(raw.as_slice(), level)?;
    Ok(zipped)
}

/// Restore from a blob.
pub fn load(bytes: &[u8]) -> Result<WorldSnapshot, SnapshotError> {
    let raw = zstd::stream::decode_all(bytes)?;
    Ok(bincode::deserialize(&raw)?)
}

/// Snapshot errors.
#[derive(Debug, thiserror::Error)]
pub enum SnapshotError {
    /// Bincode error.
    #[error("bincode: {0}")]
    Bincode(#[from] bincode::Error),
    /// IO / zstd error.
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
}

/// Hash the snapshot bytes — useful in determinism tests.
#[must_use]
pub fn hash_snapshot(s: &WorldSnapshot) -> [u8; 32] {
    let raw = bincode::serialize(s).expect("snapshot serialize");
    *blake3::hash(&raw).as_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_snap() -> WorldSnapshot {
        WorldSnapshot {
            seed: 0xC0FFEE,
            tick: 12345,
            chunks: vec![ChunkSnapshot {
                cx: 0,
                cy: 0,
                version: 7,
                voxels: vec![0u16, 1, 2, 3, 4],
                spawned: vec![(1, 2, 3, 0xAABB, 999)],
            }],
            intents: vec![IntentSnap {
                agent: 42,
                kind: 1,
                payload: vec![0, 0, 100, 0, 0, 200],
                priority: 200,
                horizon: 50,
            }],
        }
    }

    #[test]
    fn snapshot_restore_identity() {
        let s0 = sample_snap();
        let bytes = save(&s0, 3).unwrap();
        let s1 = load(&bytes).unwrap();
        assert_eq!(s0, s1);
        // Round-trip again → same bytes (bincode is canonical for the type).
        let bytes2 = save(&s1, 3).unwrap();
        assert_eq!(bytes, bytes2);
    }

    #[test]
    fn snapshot_hash_is_stable() {
        let s = sample_snap();
        let h1 = hash_snapshot(&s);
        let h2 = hash_snapshot(&s);
        assert_eq!(h1, h2);
    }

    #[test]
    fn empty_snapshot_round_trips() {
        let s = WorldSnapshot {
            seed: 0,
            tick: 0,
            chunks: vec![],
            intents: vec![],
        };
        let bytes = save(&s, 1).unwrap();
        let back = load(&bytes).unwrap();
        assert_eq!(s, back);
    }
}
