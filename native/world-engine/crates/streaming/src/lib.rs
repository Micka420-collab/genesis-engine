//! genesis-streaming — chunk lifecycle + LOD.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod chunk;
pub mod lod;
pub mod manager;

pub use chunk::{Chunk, ChunkMeta, SharedChunk};
pub use lod::Lod;
pub use manager::ChunkManager;
