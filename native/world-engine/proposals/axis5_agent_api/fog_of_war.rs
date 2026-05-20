//! Fog-of-war for agent observation.
//!
//! `WorldClient::observe_area` currently returns the full chunk. For
//! realistic AI training (POMDP) we want a *partial* observation: only
//! cells within a disc of `radius_m` around the agent are revealed; the
//! rest are masked as `Unknown`.
//!
//! This module wraps `Chunk`-like data and produces a `MaskedObservation`
//! that's safe to hand off to a Python agent without leaking information
//! the agent shouldn't have.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// One cell in a masked observation.
#[derive(Copy, Clone, Debug, PartialEq)]
pub struct MaskedCell {
    /// True if the agent can currently observe this cell.
    pub visible: bool,
    /// Elevation (m) — only valid when `visible`.
    pub elevation: f32,
    /// Biome code (`Biome as u8`) — only valid when `visible`.
    pub biome: u8,
    /// River mask flag — only valid when `visible`.
    pub river: bool,
}

/// A masked, agent-relative observation of an area.
#[derive(Clone, Debug)]
pub struct MaskedObservation {
    /// Width in cells (= CHUNK_SIZE_X usually).
    pub width: u32,
    /// Height in cells (= CHUNK_SIZE_Y usually).
    pub height: u32,
    /// World coord of the top-left cell.
    pub origin_x: i32,
    /// World coord of the top-left cell.
    pub origin_y: i32,
    /// Cells, row-major.
    pub cells: Vec<MaskedCell>,
}

/// Inputs to compute a masked observation.
#[derive(Clone, Debug)]
pub struct ChunkLite<'a> {
    /// Width in cells.
    pub width: u32,
    /// Height in cells.
    pub height: u32,
    /// World coord of the top-left cell.
    pub origin_x: i32,
    /// World coord of the top-left cell.
    pub origin_y: i32,
    /// Per-cell elevation.
    pub elevation: &'a [f32],
    /// Per-cell biome code.
    pub biome: &'a [u8],
    /// Per-cell river mask.
    pub river: &'a [bool],
}

/// Build a masked observation by masking out cells outside `radius_m` of
/// the agent at `(ax, ay)`.
#[must_use]
pub fn observe_masked(c: ChunkLite, agent_x: f32, agent_y: f32, radius_m: f32) -> MaskedObservation {
    assert_eq!(c.elevation.len() as u32, c.width * c.height);
    assert_eq!(c.biome.len() as u32, c.width * c.height);
    assert_eq!(c.river.len() as u32, c.width * c.height);

    let r2 = radius_m * radius_m;
    let mut cells = Vec::with_capacity((c.width * c.height) as usize);
    for j in 0..c.height {
        for i in 0..c.width {
            let wx = c.origin_x as f32 + i as f32;
            let wy = c.origin_y as f32 + j as f32;
            let dx = wx - agent_x;
            let dy = wy - agent_y;
            let visible = dx * dx + dy * dy <= r2;
            let idx = (j * c.width + i) as usize;
            cells.push(if visible {
                MaskedCell {
                    visible: true,
                    elevation: c.elevation[idx],
                    biome: c.biome[idx],
                    river: c.river[idx],
                }
            } else {
                MaskedCell {
                    visible: false,
                    elevation: 0.0,
                    biome: 0,
                    river: false,
                }
            });
        }
    }
    MaskedObservation {
        width: c.width,
        height: c.height,
        origin_x: c.origin_x,
        origin_y: c.origin_y,
        cells,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lite() -> (Vec<f32>, Vec<u8>, Vec<bool>) {
        let n = 8 * 8;
        let e: Vec<f32> = (0..n).map(|k| k as f32).collect();
        let b: Vec<u8> = (0..n).map(|k| (k % 16) as u8).collect();
        let r: Vec<bool> = (0..n).map(|k| k % 5 == 0).collect();
        (e, b, r)
    }

    #[test]
    fn cells_outside_radius_are_unknown() {
        let (e, b, r) = lite();
        let c = ChunkLite {
            width: 8,
            height: 8,
            origin_x: 0,
            origin_y: 0,
            elevation: &e,
            biome: &b,
            river: &r,
        };
        let obs = observe_masked(c, 0.0, 0.0, 3.5);
        // Cell at (7,7) is outside the radius.
        let far = obs.cells[7 * 8 + 7];
        assert!(!far.visible);
        assert_eq!(far.elevation, 0.0);
        // Cell at (1,1) is inside.
        let near = obs.cells[1 * 8 + 1];
        assert!(near.visible);
    }

    #[test]
    fn zero_radius_blanks_everything() {
        let (e, b, r) = lite();
        let c = ChunkLite {
            width: 8,
            height: 8,
            origin_x: 0,
            origin_y: 0,
            elevation: &e,
            biome: &b,
            river: &r,
        };
        let obs = observe_masked(c, 100.0, 100.0, 0.0);
        assert!(obs.cells.iter().all(|c| !c.visible));
    }

    #[test]
    fn large_radius_reveals_everything() {
        let (e, b, r) = lite();
        let c = ChunkLite {
            width: 8,
            height: 8,
            origin_x: 0,
            origin_y: 0,
            elevation: &e,
            biome: &b,
            river: &r,
        };
        let obs = observe_masked(c, 4.0, 4.0, 1e6);
        assert!(obs.cells.iter().all(|c| c.visible));
    }
}
