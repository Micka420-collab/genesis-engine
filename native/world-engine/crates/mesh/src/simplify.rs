//! Mesh post-processing: edge-collapse simplification.
//!
//! Strategy: greedy collapse of edges shorter than `min_edge_len`. Vertices
//! at collapsed edges are merged to their midpoint, and degenerate
//! triangles are removed. Cheap, deterministic, suitable for LOD baking.

use crate::nets::MeshChunk;
use ahash::AHashMap;

/// Collapse edges shorter than `min_edge_len` (in voxel units).
///
/// Mutates the mesh in place. Returns the number of vertices removed.
pub fn collapse_short_edges(mesh: &mut MeshChunk, min_edge_len: f32) -> usize {
    if mesh.indices.is_empty() {
        return 0;
    }

    let min_sq = min_edge_len * min_edge_len;
    let n = mesh.vertices.len();
    let mut remap: Vec<u32> = (0..n as u32).collect();

    let find_root = |remap: &Vec<u32>, mut x: u32| -> u32 {
        while remap[x as usize] != x {
            x = remap[x as usize];
        }
        x
    };

    // Pass 1: union short edges.
    for tri in mesh.indices.chunks(3) {
        let v = [tri[0], tri[1], tri[2]];
        for k in 0..3 {
            let a = v[k];
            let b = v[(k + 1) % 3];
            let ra = find_root(&remap, a) as usize;
            let rb = find_root(&remap, b) as usize;
            if ra == rb {
                continue;
            }
            let pa = mesh.vertices[ra].pos;
            let pb = mesh.vertices[rb].pos;
            let dx = pa[0] - pb[0];
            let dy = pa[1] - pb[1];
            let dz = pa[2] - pb[2];
            if dx * dx + dy * dy + dz * dz < min_sq {
                // Merge rb into ra
                remap[rb] = ra as u32;
                // Midpoint
                mesh.vertices[ra].pos = [
                    0.5 * (pa[0] + pb[0]),
                    0.5 * (pa[1] + pb[1]),
                    0.5 * (pa[2] + pb[2]),
                ];
            }
        }
    }

    // Compact vertices into a new buffer
    let mut new_index = AHashMap::with_capacity(n);
    let mut new_vertices = Vec::with_capacity(n);
    for (i, _) in mesh.vertices.iter().enumerate() {
        let r = find_root(&remap, i as u32);
        if new_index.contains_key(&r) {
            continue;
        }
        let ni = new_vertices.len() as u32;
        new_vertices.push(mesh.vertices[r as usize]);
        new_index.insert(r, ni);
    }

    let mut new_indices = Vec::with_capacity(mesh.indices.len());
    for tri in mesh.indices.chunks(3) {
        let r0 = find_root(&remap, tri[0]);
        let r1 = find_root(&remap, tri[1]);
        let r2 = find_root(&remap, tri[2]);
        if r0 == r1 || r1 == r2 || r0 == r2 {
            continue; // degenerate
        }
        new_indices.push(new_index[&r0]);
        new_indices.push(new_index[&r1]);
        new_indices.push(new_index[&r2]);
    }

    let removed = mesh.vertices.len().saturating_sub(new_vertices.len());
    mesh.vertices = new_vertices;
    mesh.indices = new_indices;
    removed
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::nets::{MeshChunk, Vertex};

    #[test]
    fn collapses_close_vertices() {
        let mut mesh = MeshChunk {
            vertices: vec![
                Vertex { pos: [0.0, 0.0, 0.0], normal: [0.0, 0.0, 1.0], material: 1 },
                Vertex { pos: [0.05, 0.0, 0.0], normal: [0.0, 0.0, 1.0], material: 1 },
                Vertex { pos: [5.0, 0.0, 0.0], normal: [0.0, 0.0, 1.0], material: 1 },
            ],
            indices: vec![0, 1, 2],
        };
        let removed = collapse_short_edges(&mut mesh, 0.5);
        assert_eq!(removed, 1);
        assert_eq!(mesh.vertices.len(), 2);
        // Triangle became degenerate, removed
        assert!(mesh.indices.is_empty());
    }

    #[test]
    fn keeps_distant_vertices() {
        let mut mesh = MeshChunk {
            vertices: vec![
                Vertex { pos: [0.0, 0.0, 0.0], normal: [0.0, 0.0, 1.0], material: 1 },
                Vertex { pos: [10.0, 0.0, 0.0], normal: [0.0, 0.0, 1.0], material: 1 },
                Vertex { pos: [0.0, 10.0, 0.0], normal: [0.0, 0.0, 1.0], material: 1 },
            ],
            indices: vec![0, 1, 2],
        };
        let removed = collapse_short_edges(&mut mesh, 0.5);
        assert_eq!(removed, 0);
        assert_eq!(mesh.vertices.len(), 3);
    }
}
