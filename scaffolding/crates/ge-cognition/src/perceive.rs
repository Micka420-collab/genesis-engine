//! Construction d'une `Observation` depuis le monde streamé.
//!
//! Phase 1 : on scanne les chunks chargés autour de l'agent à un pas grossier
//! (1 sample tous les `STRIDE` voxels) pour repérer eau/nourriture/abri.
//! Pas d'embedding visuel ni de raycasting — c'est de la perception logique
//! (« je sais qu'il y a de l'eau à 8 m vers l'est »).
//!
//! Phase 2+ : passage à un encoder DINOv3 sur une vue voxel.

use crate::perception::{Observation, PerceivedTarget, TargetKind};
use ge_agents::{Drives, Health};
use ge_core::ChunkCoord;
use ge_world::{Biome, Chunk, ChunkStreamer, CHUNK_SIZE, VOXEL_SIZE_M};
use glam::Vec3;

/// Rayon de perception par défaut (m). Phase 1 = 50 m (~1.5 chunks).
pub const PERCEPTION_RADIUS_M: f32 = 50.0;

/// Pas d'échantillonnage des cellules de chunk. 8 = 8×8 = 64 samples/chunk.
const STRIDE: usize = 8;

/// Nombre max de cibles conservées dans l'Observation.
const MAX_TARGETS: usize = 32;

/// Construit l'Observation pour un agent à `pos`.
///
/// Cette fonction est *lecture seule* sur le streamer — elle suppose que les
/// chunks pertinents sont déjà chargés (le sim_loop appelle `touch_area` avant).
pub fn perceive_for(
    streamer: &ChunkStreamer,
    pos: Vec3,
    drives: Drives,
    health: Health,
    radius_m: f32,
) -> Observation {
    let dominant = drives.dominant();
    let mut nearby = Vec::with_capacity(MAX_TARGETS * 2);

    let center = Chunk::from_world_pos(pos.x, pos.y, pos.z);
    // Tchebychev radius en chunks (chunk side = 32 m, donc rayon arrondi sup).
    let chunk_side_m = (CHUNK_SIZE as f32) * VOXEL_SIZE_M;
    let r_chunks = (radius_m / chunk_side_m).ceil() as i32 + 1;

    for dy in -r_chunks..=r_chunks {
        for dx in -r_chunks..=r_chunks {
            let coord = ChunkCoord::new(center.x + dx, center.y + dy, center.z);
            if let Some(chunk) = streamer.cache.get(&coord) {
                scan_chunk(chunk, pos, radius_m, &mut nearby);
            }
        }
    }

    // Tri par distance croissante + cap.
    nearby.sort_by(|a, b| a.distance_m.partial_cmp(&b.distance_m).unwrap_or(std::cmp::Ordering::Equal));
    nearby.truncate(MAX_TARGETS);

    Observation {
        drives,
        health,
        dominant_drive: dominant,
        nearby,
    }
}

fn scan_chunk(chunk: &Chunk, agent_pos: Vec3, radius_m: f32, out: &mut Vec<PerceivedTarget>) {
    let r2 = radius_m * radius_m;
    for cy in (0..CHUNK_SIZE).step_by(STRIDE) {
        for cx in (0..CHUNK_SIZE).step_by(STRIDE) {
            let i = Chunk::idx(cx, cy);
            let biome = chunk.biome[i];
            let height = chunk.height[i];
            let (wx, wy) = Chunk::cell_pos_m(chunk.coord, cx, cy);
            let cell = Vec3::new(wx, wy, height.max(0.0));
            let d2 = cell.distance_squared(agent_pos);
            if d2 > r2 {
                continue;
            }
            let dist = d2.sqrt();

            // Eau : océan ou cellule au niveau de la mer.
            if matches!(biome, Biome::Ocean) || height < 0.5 {
                out.push(PerceivedTarget {
                    kind: TargetKind::Water,
                    pos: cell,
                    distance_m: dist,
                    qty: 100.0,
                });
            }

            // Nourriture : NPP élevé (forêts, prairies, savane).
            let npp = biome.npp();
            if npp >= 0.45 && !matches!(biome, Biome::Ocean) {
                let wood = chunk.resources.wood[i];
                let kcal = (npp * 200.0 + wood * 0.5).max(0.0);
                out.push(PerceivedTarget {
                    kind: TargetKind::Food,
                    pos: cell,
                    distance_m: dist,
                    qty: kcal,
                });
            }

            // Abri : canopée forestière (wood > 30) ou rocaille en altitude.
            let wood = chunk.resources.wood[i];
            let stone = chunk.resources.stone[i];
            let is_shelter = wood > 30.0 || (stone > 25.0 && height > 800.0);
            if is_shelter {
                out.push(PerceivedTarget {
                    kind: TargetKind::Shelter,
                    pos: cell,
                    distance_m: dist,
                    qty: (wood + stone),
                });
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ge_agents::{Drive, Drives, Health};
    use ge_core::Tick;
    use ge_world::TerrainParams;

    #[test]
    fn perceive_returns_observation_with_dominant_drive() {
        let mut streamer = ChunkStreamer::new(0xC0FFEE, TerrainParams::default());
        streamer.touch_area(
            Tick::ZERO,
            std::iter::once(ChunkCoord::new(0, 0, 0)),
        );
        let mut d = Drives::newborn();
        d.thirst = Drive(0.9);
        let pos = Vec3::new(16.0, 16.0, 0.0);
        let obs = perceive_for(&streamer, pos, d, Health::full(), 50.0);
        // Dominant should be thirst given drives.
        // (test does not assert specific targets — biome depends on seed)
        assert_eq!(obs.dominant_drive, d.dominant());
    }
}
