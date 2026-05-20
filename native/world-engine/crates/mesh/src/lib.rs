//! genesis-mesh — voxel → triangle mesh extraction.
//!
//! Implements **Naive Surface Nets** (NSN), the algorithm originally
//! described by Mikola Lysenko. NSN is the modern replacement for
//! Marching Cubes: comparable surface quality, simpler topology (one
//! vertex per cell, never split), faster GPU-friendly meshing, and
//! straightforward LOD via cell skipping.
//!
//! Output: a [`MeshChunk`] containing positions, normals, indices, and a
//! per-vertex material id. Layout is `Vec<[f32; 3]>` rather than packed
//! bytes — the GPU upload step can repack with `bytemuck` as needed.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod nets;
pub mod simplify;

pub use nets::{extract_surface_nets, MeshChunk, MeshError, Vertex};
pub use simplify::collapse_short_edges;
