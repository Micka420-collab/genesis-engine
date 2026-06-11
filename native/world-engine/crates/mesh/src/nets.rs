//! Naive Surface Nets.
//!
//! The voxel grid is binary (`solid` / `empty`). For each cell whose 8
//! corners aren't all the same, we emit ONE vertex at the centroid of the
//! sign-change edges, then connect adjacent surface vertices into quads
//! (split into 2 triangles). This produces a watertight mesh with very
//! few topological artifacts.
//!
//! Output coordinates are in voxel space — the renderer applies any
//! world-space transform.

use bytemuck::{Pod, Zeroable};
use genesis_core::{CHUNK_SIZE_X, CHUNK_SIZE_Y, CHUNK_SIZE_Z};
use genesis_streaming::Chunk;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Mesh extraction errors.
#[derive(Error, Debug)]
pub enum MeshError {
    /// The chunk was empty / fully air; nothing to mesh.
    #[error("empty chunk — no surface")]
    EmptyChunk,
}

/// One mesh vertex.
#[repr(C)]
#[derive(Copy, Clone, Debug, Default, PartialEq, Pod, Zeroable, Serialize, Deserialize)]
pub struct Vertex {
    /// Position in chunk-local voxel space.
    pub pos: [f32; 3],
    /// Surface normal (unit vector).
    pub normal: [f32; 3],
    /// Material id at this surface (from the chunk's voxel palette).
    pub material: u32,
}

/// A meshed chunk.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct MeshChunk {
    /// Vertex buffer.
    pub vertices: Vec<Vertex>,
    /// Index buffer (triangle list, `vertices.len() ≤ u32::MAX`).
    pub indices: Vec<u32>,
}

impl MeshChunk {
    /// Number of triangles.
    #[must_use]
    pub fn tri_count(&self) -> usize {
        self.indices.len() / 3
    }
}

const SX: usize = CHUNK_SIZE_X as usize;
const SY: usize = CHUNK_SIZE_Y as usize;
const SZ: usize = CHUNK_SIZE_Z as usize;

#[inline]
fn voxel_index(i: usize, j: usize, k: usize) -> usize {
    i + j * SX + k * SX * SY
}

/// Extract a surface mesh from a chunk using Naive Surface Nets.
///
/// `step` is a cell-skip factor (1 = full res; 2 = half-res LOD; etc.).
/// Larger `step` produces a coarser mesh in O(1/step³) time.
pub fn extract_surface_nets(chunk: &Chunk, step: u32) -> Result<MeshChunk, MeshError> {
    assert!(step >= 1, "step must be >= 1");
    let step = step as usize;

    // Cell coords range from 0..(SZ-step) etc. — each cell uses 8 corner voxels.
    // We store a `Option<u32>` per cell mapping → index of the surface
    // vertex in our output buffer, when present.
    let cx = (SX - step) / step;
    let cy = (SY - step) / step;
    let cz = (SZ - step) / step;
    if cx == 0 || cy == 0 || cz == 0 {
        return Err(MeshError::EmptyChunk);
    }
    let mut cell_to_vertex = vec![u32::MAX; cx * cy * cz];

    let mut vertices: Vec<Vertex> = Vec::with_capacity(4096);
    let mut indices: Vec<u32> = Vec::with_capacity(8192);

    let solid = |i: usize, j: usize, k: usize| -> bool {
        let idx = voxel_index(i.min(SX - 1), j.min(SY - 1), k.min(SZ - 1));
        chunk.voxels[idx] != 0 /* air = 0 */
    };

    let cell_idx = |ci: usize, cj: usize, ck: usize| ci + cj * cx + ck * cx * cy;

    // Pass 1: produce one vertex per surface cell.
    for ck in 0..cz {
        for cj in 0..cy {
            for ci in 0..cx {
                let i = ci * step;
                let j = cj * step;
                let k = ck * step;

                // Sample the 8 corners
                let s = [
                    solid(i,        j,        k),
                    solid(i + step, j,        k),
                    solid(i,        j + step, k),
                    solid(i + step, j + step, k),
                    solid(i,        j,        k + step),
                    solid(i + step, j,        k + step),
                    solid(i,        j + step, k + step),
                    solid(i + step, j + step, k + step),
                ];

                let mask = s.iter().enumerate().fold(0u8, |m, (n, b)| {
                    if *b {
                        m | (1 << n)
                    } else {
                        m
                    }
                });
                if mask == 0 || mask == 0xFF {
                    continue;
                }

                // Find centroid of edge crossings (12 edges of the cube)
                let edges: [(usize, usize); 12] = [
                    (0, 1), (2, 3), (4, 5), (6, 7),
                    (0, 2), (1, 3), (4, 6), (5, 7),
                    (0, 4), (1, 5), (2, 6), (3, 7),
                ];
                let edge_offsets: [(f32, f32, f32, f32, f32, f32); 12] = [
                    (0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
                    (0.0, 1.0, 0.0, 1.0, 1.0, 0.0),
                    (0.0, 0.0, 1.0, 1.0, 0.0, 1.0),
                    (0.0, 1.0, 1.0, 1.0, 1.0, 1.0),
                    (0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
                    (1.0, 0.0, 0.0, 1.0, 1.0, 0.0),
                    (0.0, 0.0, 1.0, 0.0, 1.0, 1.0),
                    (1.0, 0.0, 1.0, 1.0, 1.0, 1.0),
                    (0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
                    (1.0, 0.0, 0.0, 1.0, 0.0, 1.0),
                    (0.0, 1.0, 0.0, 0.0, 1.0, 1.0),
                    (1.0, 1.0, 0.0, 1.0, 1.0, 1.0),
                ];

                let mut sum = [0.0f32; 3];
                let mut count = 0.0f32;
                for (e, (a, b)) in edges.iter().enumerate() {
                    if s[*a] != s[*b] {
                        let (ax, ay, az, bx, by, bz) = edge_offsets[e];
                        sum[0] += 0.5 * (ax + bx);
                        sum[1] += 0.5 * (ay + by);
                        sum[2] += 0.5 * (az + bz);
                        count += 1.0;
                    }
                }
                if count == 0.0 {
                    continue;
                }
                let pos = [
                    i as f32 + sum[0] / count * step as f32,
                    j as f32 + sum[1] / count * step as f32,
                    k as f32 + sum[2] / count * step as f32,
                ];

                // Approximate normal: gradient of `solid` (signed).
                let normal = approx_normal(chunk, pos);

                // Pick material from the dominant solid corner
                let mat_corner = pick_material_corner(&s);
                let mat = if let Some(c) = mat_corner {
                    let (di, dj, dk) = corner_offset(c, step);
                    chunk.voxels[voxel_index(
                        (i + di).min(SX - 1),
                        (j + dj).min(SY - 1),
                        (k + dk).min(SZ - 1),
                    )] as u32
                } else {
                    0
                };

                cell_to_vertex[cell_idx(ci, cj, ck)] = vertices.len() as u32;
                vertices.push(Vertex {
                    pos,
                    normal,
                    material: mat,
                });
            }
        }
    }

    if vertices.is_empty() {
        return Err(MeshError::EmptyChunk);
    }

    // Pass 2: emit quads. For each cell that has a vertex, look at the
    // edges along +X, +Y, +Z that cross the surface, and connect with the
    // neighbouring cells' vertices.
    for ck in 0..cz {
        for cj in 0..cy {
            for ci in 0..cx {
                let v0 = cell_to_vertex[cell_idx(ci, cj, ck)];
                if v0 == u32::MAX {
                    continue;
                }
                let i = ci * step;
                let j = cj * step;
                let k = ck * step;

                // +X edge between (i+step,j,k) and (i+step,j+step,k+step) — i.e. we
                // need cells (ci, cj-1, ck-1), (ci, cj, ck-1), (ci, cj-1, ck), (ci, cj, ck).
                // Equivalent for +Y and +Z.
                if ci + 1 < cx {
                    try_emit_quad(
                        &mut indices,
                        &cell_to_vertex,
                        cx,
                        cy,
                        ci, cj, ck,
                        Axis::X,
                        chunk,
                        i + step, j, k, step,
                    );
                }
                if cj + 1 < cy {
                    try_emit_quad(
                        &mut indices,
                        &cell_to_vertex,
                        cx,
                        cy,
                        ci, cj, ck,
                        Axis::Y,
                        chunk,
                        i, j + step, k, step,
                    );
                }
                if ck + 1 < cz {
                    try_emit_quad(
                        &mut indices,
                        &cell_to_vertex,
                        cx,
                        cy,
                        ci, cj, ck,
                        Axis::Z,
                        chunk,
                        i, j, k + step, step,
                    );
                }
            }
        }
    }

    Ok(MeshChunk { vertices, indices })
}

#[derive(Copy, Clone)]
enum Axis {
    X,
    Y,
    Z,
}

#[allow(clippy::too_many_arguments)]
fn try_emit_quad(
    indices: &mut Vec<u32>,
    map: &[u32],
    cx: usize,
    cy: usize,
    ci: usize,
    cj: usize,
    ck: usize,
    axis: Axis,
    chunk: &Chunk,
    ax: usize,
    ay: usize,
    az: usize,
    step: usize,
) {
    // The shared edge between two voxel corners. If they differ in
    // solidity, we emit one quad spanning the 4 cells around the edge.
    let solid = |i: usize, j: usize, k: usize| -> bool {
        let i = i.min(SX - 1);
        let j = j.min(SY - 1);
        let k = k.min(SZ - 1);
        chunk.voxels[voxel_index(i, j, k)] != 0
    };

    let (a, b) = match axis {
        Axis::X => (solid(ax, ay, az), solid(ax, ay + step, az + step)),
        Axis::Y => (solid(ax, ay, az), solid(ax + step, ay, az + step)),
        Axis::Z => (solid(ax, ay, az), solid(ax + step, ay + step, az)),
    };
    if a == b {
        return; // no surface crossing this edge
    }

    let cell_idx = |ci: usize, cj: usize, ck: usize| ci + cj * cx + ck * cx * cy;

    let (v0, v1, v2, v3) = match axis {
        Axis::X => (
            cell_idx(ci, cj.saturating_sub(1), ck.saturating_sub(1)),
            cell_idx(ci, cj, ck.saturating_sub(1)),
            cell_idx(ci, cj, ck),
            cell_idx(ci, cj.saturating_sub(1), ck),
        ),
        Axis::Y => (
            cell_idx(ci.saturating_sub(1), cj, ck.saturating_sub(1)),
            cell_idx(ci, cj, ck.saturating_sub(1)),
            cell_idx(ci, cj, ck),
            cell_idx(ci.saturating_sub(1), cj, ck),
        ),
        Axis::Z => (
            cell_idx(ci.saturating_sub(1), cj.saturating_sub(1), ck),
            cell_idx(ci, cj.saturating_sub(1), ck),
            cell_idx(ci, cj, ck),
            cell_idx(ci.saturating_sub(1), cj, ck),
        ),
    };
    if v0 >= map.len() || v1 >= map.len() || v2 >= map.len() || v3 >= map.len() {
        return;
    }
    let i0 = map[v0];
    let i1 = map[v1];
    let i2 = map[v2];
    let i3 = map[v3];
    if i0 == u32::MAX || i1 == u32::MAX || i2 == u32::MAX || i3 == u32::MAX {
        return;
    }
    // Winding so the normal matches the sign change direction
    if a {
        indices.extend_from_slice(&[i0, i1, i2, i0, i2, i3]);
    } else {
        indices.extend_from_slice(&[i0, i2, i1, i0, i3, i2]);
    }
}

fn approx_normal(chunk: &Chunk, pos: [f32; 3]) -> [f32; 3] {
    let i = pos[0] as usize;
    let j = pos[1] as usize;
    let k = pos[2] as usize;
    let i = i.min(SX - 2).max(1);
    let j = j.min(SY - 2).max(1);
    let k = k.min(SZ - 2).max(1);

    let sample = |a: usize, b: usize, c: usize| -> f32 {
        let v = chunk.voxels[voxel_index(a, b, c)];
        if v == 0 {
            0.0
        } else {
            1.0
        }
    };
    let gx = sample(i + 1, j, k) - sample(i - 1, j, k);
    let gy = sample(i, j + 1, k) - sample(i, j - 1, k);
    let gz = sample(i, j, k + 1) - sample(i, j, k - 1);
    let len = (gx * gx + gy * gy + gz * gz).sqrt();
    if len < 1e-6 {
        [0.0, 0.0, 1.0]
    } else {
        // Surface normal points from solid → empty, i.e. the negative
        // gradient of `solid` (interior == 1).
        [-gx / len, -gy / len, -gz / len]
    }
}

fn pick_material_corner(s: &[bool; 8]) -> Option<usize> {
    s.iter().position(|b| *b)
}

fn corner_offset(c: usize, step: usize) -> (usize, usize, usize) {
    match c {
        0 => (0, 0, 0),
        1 => (step, 0, 0),
        2 => (0, step, 0),
        3 => (step, step, 0),
        4 => (0, 0, step),
        5 => (step, 0, step),
        6 => (0, step, step),
        _ => (step, step, step),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use genesis_core::WorldSeed;
    use genesis_streaming::manager::ChunkManagerConfig;
    use genesis_streaming::ChunkManager;

    fn fast_chunk() -> Chunk {
        let mgr = ChunkManager::new(
            WorldSeed::from_u64(7),
            ChunkManagerConfig {
                erosion_droplets: 8,
                erosion_passes: 1,
                cache_capacity: 4,
                ..Default::default()
            },
        );
        mgr.generate(genesis_core::ChunkCoord { cx: 0, cy: 0 })
    }

    #[test]
    fn extracts_non_empty_mesh() {
        let chunk = fast_chunk();
        let mesh = extract_surface_nets(&chunk, 1).expect("should produce mesh");
        assert!(mesh.vertices.len() > 0);
        assert!(mesh.tri_count() > 0);
    }

    #[test]
    fn lod_reduces_vertex_count() {
        let chunk = fast_chunk();
        let m1 = extract_surface_nets(&chunk, 1).unwrap();
        let m2 = extract_surface_nets(&chunk, 2).unwrap();
        let m4 = extract_surface_nets(&chunk, 4).unwrap();
        assert!(m2.vertices.len() < m1.vertices.len());
        assert!(m4.vertices.len() < m2.vertices.len());
    }
}
