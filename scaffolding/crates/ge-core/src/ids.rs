//! Identifiants déterministes (UUIDv8 dérivés du seed) + types de coordonnées
//! spatiales + identité de simulation.

use crate::prf::WorldSeed;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

fn seed_to_key(seed: WorldSeed) -> [u8; 32] {
    let mut out = [0u8; 32];
    out[..16].copy_from_slice(&seed.to_le_bytes());
    out[16..].copy_from_slice(&seed.to_be_bytes());
    out
}

fn shape_uuid_v8(mut bytes: [u8; 16]) -> Uuid {
    bytes[6] = (bytes[6] & 0x0F) | 0x80;
    bytes[8] = (bytes[8] & 0x3F) | 0x80;
    Uuid::from_bytes(bytes)
}

/// ID d'agent (UUIDv8 dérivé du seed).
#[derive(Copy, Clone, Eq, PartialEq, Ord, PartialOrd, Hash, Debug, Serialize, Deserialize)]
pub struct AgentId(pub Uuid);

impl AgentId {
    /// Dérive un AgentId déterministe depuis (seed, contexte, indices).
    pub fn derive(seed: WorldSeed, ctx: &[&str], indices: &[u64]) -> Self {
        let mut hasher = blake3::Hasher::new_keyed(&seed_to_key(seed));
        for c in ctx {
            hasher.update(b"|");
            hasher.update(c.as_bytes());
        }
        for i in indices {
            hasher.update(b"|");
            hasher.update(&i.to_le_bytes());
        }
        let full = hasher.finalize();
        let mut bytes = [0u8; 16];
        bytes.copy_from_slice(&full.as_bytes()[..16]);
        AgentId(shape_uuid_v8(bytes))
    }

    #[inline]
    pub const fn from_uuid(u: Uuid) -> Self { AgentId(u) }
}

impl std::fmt::Display for AgentId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

/// Coordonnée 3D d'un chunk.
#[derive(Copy, Clone, Eq, PartialEq, Ord, PartialOrd, Hash, Debug, Serialize, Deserialize)]
pub struct ChunkCoord { pub x: i32, pub y: i32, pub z: i32 }

impl ChunkCoord {
    #[inline]
    pub const fn new(x: i32, y: i32, z: i32) -> Self { Self { x, y, z } }
}

/// Identifiant de simulation.
#[derive(Copy, Clone, Eq, PartialEq, Ord, PartialOrd, Hash, Debug, Serialize, Deserialize)]
pub struct SimulationId(pub Uuid);

impl SimulationId {
    pub fn new_random() -> Self { SimulationId(Uuid::new_v4()) }
}

impl std::fmt::Display for SimulationId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn agent_id_deterministic() {
        let a = AgentId::derive(42, &["agent","founder"], &[7]);
        let b = AgentId::derive(42, &["agent","founder"], &[7]);
        assert_eq!(a, b);
    }

    #[test]
    fn agent_id_differs_with_index() {
        assert_ne!(
            AgentId::derive(42, &["x"], &[1]),
            AgentId::derive(42, &["x"], &[2])
        );
    }

    #[test]
    fn chunk_coord_eq() {
        assert_eq!(ChunkCoord::new(1,2,3), ChunkCoord::new(1,2,3));
    }
}
