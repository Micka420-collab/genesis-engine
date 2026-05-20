//! genesis-persist — chunk serialization.
//!
//! Wraps `serde + bincode + zstd`. The architecture mentions rkyv for true
//! zero-copy snapshots; we keep that as a follow-up. For now this gives us a
//! single round-trip that's fast enough (< 10 ms per chunk at L3 typically)
//! and that doesn't pull in rkyv's heavier dependency set.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{de::DeserializeOwned, Serialize};
use thiserror::Error;

/// Serialization errors.
#[derive(Error, Debug)]
pub enum PersistError {
    /// Underlying bincode error.
    #[error("bincode: {0}")]
    Bincode(#[from] bincode::Error),
    /// Underlying I/O / zstd error.
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
}

/// Serialize `value` → bincode → zstd at level `level` (1..22; 3 is the sweet
/// spot for chunks).
pub fn save<T: Serialize>(value: &T, level: i32) -> Result<Vec<u8>, PersistError> {
    let raw = bincode::serialize(value)?;
    let compressed = zstd::stream::encode_all(raw.as_slice(), level)?;
    Ok(compressed)
}

/// Deserialize `bytes` ← zstd ← bincode.
pub fn load<T: DeserializeOwned>(bytes: &[u8]) -> Result<T, PersistError> {
    let raw = zstd::stream::decode_all(bytes)?;
    Ok(bincode::deserialize(&raw)?)
}

/// 32-byte BLAKE3 hash of a value as serialized (useful for determinism
/// tests).
pub fn hash<T: Serialize>(value: &T) -> Result<[u8; 32], PersistError> {
    let raw = bincode::serialize(value)?;
    Ok(*blake3::hash(&raw).as_bytes())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::Deserialize;

    #[derive(Serialize, Deserialize, PartialEq, Debug)]
    struct Toy {
        a: u32,
        b: String,
        c: Vec<f32>,
    }

    #[test]
    fn roundtrip() {
        let t = Toy {
            a: 42,
            b: "hello".into(),
            c: vec![1.0, 2.0, 3.0],
        };
        let bytes = save(&t, 3).unwrap();
        let back: Toy = load(&bytes).unwrap();
        assert_eq!(t, back);
    }

    #[test]
    fn hash_stable() {
        let t = Toy { a: 1, b: "x".into(), c: vec![1.0] };
        let h1 = hash(&t).unwrap();
        let h2 = hash(&t).unwrap();
        assert_eq!(h1, h2);
    }
}
