//! ge-world — moteur de monde procédural déterministe.
//!
//! Responsabilités :
//! - Génération de terrain par chunks (heightmap + biomes + ressources)
//! - Sharding spatial (1 chunk = 64×64 m²)
//! - Streaming (load/unload selon zones actives)
//! - Climat et météo
//!
//! Toute génération doit dériver d'un PRF (`ge_core::prf_rng`) pour rester
//! bit-à-bit reproductible entre runs et entre nœuds.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod biome;
pub mod chunk;
pub mod climate;
pub mod noise;
pub mod resource;
pub mod streaming;
pub mod terrain;

pub use biome::*;
pub use chunk::*;
pub use climate::*;
pub use resource::*;
pub use streaming::*;
pub use terrain::*;
