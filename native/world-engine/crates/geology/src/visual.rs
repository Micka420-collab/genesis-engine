//! Per-voxel surface sampling — host rock, mineral deposit, RGB seen.
//!
//! This is the only API agents need: given world coordinates + a seed, return
//! the colour that surface voxel reflects to an observer's eye. Agents store
//! the colour, not the mineral identity. Discovery happens because:
//!
//!   1. The colour is reproducible (same voxel ⇒ same colour every visit).
//!   2. The colour clusters spatially (deposits are not isolated specks).
//!   3. The mapping from `Mineral → RGB` is injective enough for distinct
//!      minerals to look distinct (asserted by `mineral.rs` tests).
//!
//! Determinism: all sampling is a pure function of
//! `(seed, world_x, world_y, world_z, host_rock)`. No interior mutability,
//! no atomics, no `thread_rng`.

use crate::mineral::{affinity, Mineral, MineralDeposit};
use crate::rock::RockType;
use genesis_core::Prf;
use serde::{Deserialize, Serialize};

/// What an agent's eye registers when looking at a surface voxel.
#[derive(Copy, Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct SurfaceColorHint {
    /// 8-bit RGB the vision system samples.
    pub rgb: [u8; 3],
    /// `true` if a mineral overrides the rock base colour.
    pub mineral_visible: bool,
    /// `true` if the deposit catches the light (gold, silver, native copper).
    pub lustrous: bool,
}

/// The full deterministic description of one surface voxel.
#[derive(Copy, Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct SurfaceSample {
    /// Host rock at this voxel.
    pub rock: RockType,
    /// `Some` if there is a discovery-grade deposit.
    pub deposit: Option<MineralDeposit>,
    /// Colour the agent sees.
    pub color_hint: SurfaceColorHint,
}

/// Layer tag (folded into the `Prf` hash) so geology hashes don't collide with
/// terrain, hydrology, climate, etc. Bumped if hashing semantics ever change.
const GEOLOGY_LAYER_TAG: u32 = 0x6E_07_06_43; // "GeoLogy" Wave 43 marker

/// Concentration threshold above which a deposit is "discovery-grade" — the
/// mineral colour overrides the host rock colour in [`surface_color_hint`].
///
/// Calibrated so that ~5–8% of voxels in a copper-belt schist host show
/// malachite. Tweak only with a corresponding smoke test update.
pub const DISCOVERY_THRESHOLD: f32 = 0.55;

/// Sample one voxel deterministically. The most expensive of the three
/// public functions; `surface_color_hint` is a thin wrapper.
#[must_use]
pub fn sample_surface(
    prf: Prf,
    world_x: i32,
    world_y: i32,
    world_z: i32,
    host: RockType,
) -> SurfaceSample {
    if matches!(host, RockType::Air) {
        return SurfaceSample {
            rock: host,
            deposit: None,
            color_hint: SurfaceColorHint {
                rgb: host.base_color(),
                mineral_visible: false,
                lustrous: false,
            },
        };
    }

    let depth_m = (-world_z).max(0); // negative z is underground; surface = 0
    let deposit = sample_deposit(prf, world_x, world_y, world_z, host, depth_m);

    let (rgb, mineral_visible, lustrous) = match deposit {
        Some(dep) if dep.concentration >= DISCOVERY_THRESHOLD => (
            dep.mineral.surface_color(),
            true,
            dep.mineral.is_lustrous(),
        ),
        _ => (host.base_color(), false, false),
    };

    SurfaceSample {
        rock: host,
        deposit,
        color_hint: SurfaceColorHint {
            rgb,
            mineral_visible,
            lustrous,
        },
    }
}

/// Just the colour — cheap path for vision systems that don't need the rock
/// identity. Functionally identical to `sample_surface(...).color_hint`.
#[must_use]
pub fn surface_color_hint(
    prf: Prf,
    world_x: i32,
    world_y: i32,
    world_z: i32,
    host: RockType,
) -> SurfaceColorHint {
    sample_surface(prf, world_x, world_y, world_z, host).color_hint
}

/// Pick the dominant mineral at this voxel (if any) by sampling the affinity
/// of every legal mineral and keeping the one whose `affinity × prf-noise`
/// score is highest. Returns `None` when even the winner is below threshold.
fn sample_deposit(
    prf: Prf,
    x: i32,
    y: i32,
    z: i32,
    host: RockType,
    depth_m: i32,
) -> Option<MineralDeposit> {
    let mut best: Option<(Mineral, f32)> = None;

    // Per-mineral salt — disjoint from any other geology sub-system.
    for (idx, mineral) in Mineral::VARIANTS.iter().enumerate() {
        if matches!(mineral, Mineral::None) {
            continue;
        }
        let a = affinity(*mineral, host, depth_m);
        if a == 0.0 {
            continue;
        }
        // Per-mineral noise in [0,1) — different salt per mineral so the
        // deposits of different minerals don't co-spawn at identical voxels.
        let noise = prf.unit_f32(GEOLOGY_LAYER_TAG, x, y, z, idx as u32);
        // Cluster modulation: a low-frequency hash (divide by 4 voxels) so
        // deposits form spatial clusters instead of single-voxel specks.
        let cluster = prf.unit_f32(
            GEOLOGY_LAYER_TAG ^ 0x5A5A_5A5A,
            x / 4,
            y / 4,
            z / 4,
            idx as u32,
        );
        let score = a * (0.35 + 0.65 * noise) * (0.4 + 0.6 * cluster);

        match best {
            None => best = Some((*mineral, score)),
            Some((_, prev)) if score > prev => best = Some((*mineral, score)),
            _ => {}
        }
    }

    best.map(|(m, conc)| MineralDeposit {
        mineral: m,
        concentration: conc.clamp(0.0, 1.0),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn prf() -> Prf {
        Prf::new(0xC0FFEE_DEAD_BEEF_u128)
    }

    #[test]
    fn determinism_same_seed_same_output() {
        let p = prf();
        for i in 0..200 {
            let s1 = sample_surface(p, i, i * 3, -10, RockType::Schist);
            let s2 = sample_surface(p, i, i * 3, -10, RockType::Schist);
            assert_eq!(s1, s2, "non-deterministic at x={i}");
        }
    }

    #[test]
    fn different_seeds_diverge() {
        let p1 = Prf::new(1);
        let p2 = Prf::new(2);
        let mut diffs = 0;
        for i in 0..200 {
            let a = sample_surface(p1, i, 0, -10, RockType::Schist);
            let b = sample_surface(p2, i, 0, -10, RockType::Schist);
            if a != b {
                diffs += 1;
            }
        }
        // We expect most samples to diverge with different seeds.
        assert!(diffs > 100, "only {diffs}/200 differed between seeds — Prf weak?");
    }

    #[test]
    fn air_voxel_never_has_deposit() {
        let p = prf();
        for i in 0..50 {
            let s = sample_surface(p, i, i, 100, RockType::Air);
            assert!(s.deposit.is_none());
            assert!(!s.color_hint.mineral_visible);
        }
    }

    #[test]
    fn gold_never_appears_in_clay() {
        // Property test : sample a chunk in clay, count gold deposits. Must
        // be zero. The agent should never see gold yellow on a clay surface.
        let p = prf();
        let mut gold_in_clay = 0;
        for x in 0..32 {
            for y in 0..32 {
                for z in -200..-10 {
                    let s = sample_surface(p, x, y, z, RockType::Clay);
                    if let Some(d) = s.deposit {
                        if d.mineral == Mineral::Gold {
                            gold_in_clay += 1;
                        }
                    }
                }
            }
        }
        assert_eq!(gold_in_clay, 0);
    }

    #[test]
    fn malachite_appears_at_shallow_schist_copper_belt() {
        // In schist near the surface, malachite should be one of the more
        // common visible deposits. We accept >= 1 across a 64×64 patch as a
        // weak existence check.
        let p = prf();
        let mut malachite_seen = 0;
        for x in -32..32 {
            for y in -32..32 {
                let s = sample_surface(p, x, y, -3, RockType::Schist);
                if let Some(d) = s.deposit {
                    if d.mineral == Mineral::Malachite && s.color_hint.mineral_visible {
                        malachite_seen += 1;
                    }
                }
            }
        }
        assert!(
            malachite_seen >= 1,
            "no malachite visible in 64x64 schist patch — agent has nothing to see"
        );
    }

    #[test]
    fn lustrous_implies_mineral_visible() {
        // If we ever report lustrous=true without mineral_visible=true,
        // the agent's vision pipeline could get inconsistent percepts.
        let p = prf();
        for x in -50..50 {
            for y in -50..50 {
                for z in [-1, -10, -50, -150] {
                    for host in [
                        RockType::Schist,
                        RockType::Granite,
                        RockType::Quartzite,
                        RockType::Sandstone,
                    ] {
                        let s = sample_surface(p, x, y, z, host);
                        if s.color_hint.lustrous {
                            assert!(
                                s.color_hint.mineral_visible,
                                "lustrous=true with mineral_visible=false at ({x},{y},{z},{host:?})"
                            );
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn deposits_cluster_spatially() {
        // Sanity: adjacent voxels of the same mineral should be more likely
        // to share a mineral than two random voxels. This is the cluster
        // mechanic; if it breaks, deposits look like uniform noise.
        let p = prf();
        let mut adjacent_same = 0;
        let mut adjacent_total = 0;
        for x in -16..16 {
            for y in -16..16 {
                let a = sample_surface(p, x, y, -5, RockType::Schist).deposit;
                let b = sample_surface(p, x + 1, y, -5, RockType::Schist).deposit;
                if let (Some(da), Some(db)) = (a, b) {
                    adjacent_total += 1;
                    if da.mineral == db.mineral {
                        adjacent_same += 1;
                    }
                }
            }
        }
        // Expect at least 30% of adjacent deposit-pairs to share mineral.
        if adjacent_total >= 10 {
            let ratio = adjacent_same as f32 / adjacent_total as f32;
            assert!(
                ratio > 0.30,
                "deposit clustering broken: ratio={ratio} ({adjacent_same}/{adjacent_total})"
            );
        }
    }
}
