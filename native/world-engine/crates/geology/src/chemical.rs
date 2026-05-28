//! Chemical signals — olfactive discovery channel.
//!
//! **Wave 44 — Substrate physique : signaux chimiques + dispersion vent.**
//!
//! Geology emits chemical signals from specific deposit types. Sulfur
//! fumaroles, coal seeps and salt brines volatilise to the air; an agent
//! within range registers an *intensity* (0–1), never an identity. The
//! agent's nose says "stronger this way" and walks upwind until the source
//! is found — the textbook stone-age discovery loop.
//!
//! Physical model (intentionally minimal, scales to GPU later):
//!
//!   intensity(d, wind, source_strength) =
//!       source_strength · exp(-d / λ_chem) · upwind_factor(wind, direction)
//!
//! where `λ_chem` is a per-signal decay length (sulfur travels further than
//! salt brine) and the upwind factor is the cosine of the angle between
//! `(observer − source)` and the wind vector, clamped to `[0.1, 1.0]` so an
//! agent directly downwind gets the full plume and an agent upwind still
//! gets a residual whiff.
//!
//! All randomness goes through `genesis_core::Prf`. Same `(seed, source,
//! wind, observer)` ⇒ same intensity, forever.

use crate::mineral::Mineral;
use crate::visual::sample_surface;
use crate::rock::RockType;
use genesis_core::Prf;
use serde::{Deserialize, Serialize};

/// Chemical signal kinds an agent's chemo-receptor can register. Distinct
/// kinds map to distinct olfactive percepts; the agent stores the kind tag
/// as an opaque integer in its memory, not the mineral identity.
#[repr(u8)]
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum SignalKind {
    /// Sharp pungent odour — sulfur / H₂S / fumarolic vent.
    Pungent = 0,
    /// Acrid sooty smell — exposed coal seam.
    Acrid = 1,
    /// Mineral / saline taste-smell — salt brine surfacing.
    Saline = 2,
}

impl SignalKind {
    /// Source-side characteristic decay length in metres. Larger = travels
    /// further with the wind. Real-world calibration: H₂S detectable several
    /// hundred metres downwind of a fumarole; coal smoke similar; salt brine
    /// is far weaker.
    #[must_use]
    pub const fn decay_length_m(self) -> f32 {
        match self {
            SignalKind::Pungent => 240.0,
            SignalKind::Acrid => 180.0,
            SignalKind::Saline => 40.0,
        }
    }

    /// Baseline emission strength of an active source voxel (0–1).
    #[must_use]
    pub const fn base_strength(self) -> f32 {
        match self {
            SignalKind::Pungent => 0.95,
            SignalKind::Acrid => 0.70,
            SignalKind::Saline => 0.35,
        }
    }
}

/// One chemical emission at a source voxel.
#[derive(Copy, Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ChemicalEmission {
    /// Kind of signal (Pungent / Acrid / Saline).
    pub kind: SignalKind,
    /// Source strength at the voxel itself, in `[0, 1]`.
    pub source_strength: f32,
}

/// Map a mineral to the signal it emits, if any. Returns `None` for
/// odourless minerals.
#[must_use]
pub const fn emission_for_mineral(m: Mineral) -> Option<SignalKind> {
    match m {
        Mineral::Sulfur => Some(SignalKind::Pungent),
        Mineral::Coal => Some(SignalKind::Acrid),
        Mineral::Salt => Some(SignalKind::Saline),
        _ => None,
    }
}

/// Sample whether the surface voxel at `(world_x, world_y, world_z)` emits
/// a chemical signal. Calls [`sample_surface`] internally and projects
/// `MineralDeposit → ChemicalEmission`.
#[must_use]
pub fn emission_at(
    prf: Prf,
    world_x: i32,
    world_y: i32,
    world_z: i32,
    host: RockType,
) -> Option<ChemicalEmission> {
    let sample = sample_surface(prf, world_x, world_y, world_z, host);
    let dep = sample.deposit?;
    if !sample.color_hint.mineral_visible {
        // Below discovery threshold — too dilute to emit detectable plume.
        return None;
    }
    let kind = emission_for_mineral(dep.mineral)?;
    Some(ChemicalEmission {
        kind,
        source_strength: kind.base_strength() * dep.concentration,
    })
}

/// Intensity an observer at `(ox, oy, oz)` registers from a single emission
/// located at `(sx, sy, sz)` under wind vector `wind_xy` (m/s, world space).
///
/// Implementation : exponential decay with distance, modulated by upwind /
/// downwind angle. Cheap closed form — ~10 FLOPs.
#[must_use]
pub fn intensity_at(
    emission: ChemicalEmission,
    sx: i32,
    sy: i32,
    sz: i32,
    ox: i32,
    oy: i32,
    oz: i32,
    wind_xy: [f32; 2],
) -> f32 {
    let dx = (ox - sx) as f32;
    let dy = (oy - sy) as f32;
    let dz = (oz - sz) as f32;
    let dist = (dx * dx + dy * dy + dz * dz).sqrt();
    if dist < 0.5 {
        return emission.source_strength; // at-source
    }
    let lambda = emission.kind.decay_length_m();
    let decay = (-dist / lambda).exp();

    // Upwind factor: positive cos(angle) means observer is downwind of source.
    let wind_speed = (wind_xy[0] * wind_xy[0] + wind_xy[1] * wind_xy[1]).sqrt();
    let upwind = if wind_speed < 0.1 {
        0.5 // calm air — diffusive only, no directional preference
    } else {
        let inv_w = 1.0 / wind_speed;
        let inv_d = 1.0 / dist;
        // dot((observer-source).xy, wind) / (|observer-source| · |wind|)
        let cos_theta = (dx * wind_xy[0] + dy * wind_xy[1]) * inv_w * inv_d;
        // Map cos ∈ [-1, 1] → factor ∈ [0.1, 1.0]
        (0.55 + 0.45 * cos_theta).clamp(0.1, 1.0)
    };

    emission.source_strength * decay * upwind
}

#[cfg(test)]
mod tests {
    use super::*;

    fn prf() -> Prf {
        Prf::new(0x5_E_E_D_BABE_F00D_u128)
    }

    #[test]
    fn only_smelly_minerals_emit() {
        assert_eq!(emission_for_mineral(Mineral::Sulfur), Some(SignalKind::Pungent));
        assert_eq!(emission_for_mineral(Mineral::Coal), Some(SignalKind::Acrid));
        assert_eq!(emission_for_mineral(Mineral::Salt), Some(SignalKind::Saline));
        assert_eq!(emission_for_mineral(Mineral::Gold), None);
        assert_eq!(emission_for_mineral(Mineral::Iron), None);
        assert_eq!(emission_for_mineral(Mineral::Malachite), None);
    }

    #[test]
    fn intensity_decays_with_distance() {
        let e = ChemicalEmission {
            kind: SignalKind::Pungent,
            source_strength: 1.0,
        };
        let wind = [3.0, 0.0]; // wind blowing east
        let near = intensity_at(e, 0, 0, 0, 50, 0, 0, wind);
        let far = intensity_at(e, 0, 0, 0, 400, 0, 0, wind);
        assert!(near > far, "intensity must decay with distance");
        assert!(near < 1.0, "non-zero distance must lose some signal");
    }

    #[test]
    fn downwind_gets_more_than_upwind() {
        // Source at origin, wind blowing east (+x). Observer due east should
        // register a stronger plume than observer due west at same distance.
        let e = ChemicalEmission {
            kind: SignalKind::Pungent,
            source_strength: 1.0,
        };
        let wind = [3.0, 0.0];
        let downwind = intensity_at(e, 0, 0, 0, 100, 0, 0, wind);
        let upwind = intensity_at(e, 0, 0, 0, -100, 0, 0, wind);
        assert!(
            downwind > upwind,
            "downwind={downwind}, upwind={upwind} — wind asymmetry broken"
        );
        // Even upwind must register something (residual diffusion).
        assert!(upwind > 0.0);
    }

    #[test]
    fn calm_wind_is_isotropic() {
        // With near-zero wind, the upwind factor collapses to 0.5 regardless
        // of observer direction. Intensity becomes a pure function of dist.
        let e = ChemicalEmission {
            kind: SignalKind::Acrid,
            source_strength: 1.0,
        };
        let wind = [0.0, 0.0];
        let east = intensity_at(e, 0, 0, 0, 50, 0, 0, wind);
        let west = intensity_at(e, 0, 0, 0, -50, 0, 0, wind);
        let north = intensity_at(e, 0, 0, 0, 0, 50, 0, wind);
        let south = intensity_at(e, 0, 0, 0, 0, -50, 0, wind);
        let eps = 1e-5;
        assert!((east - west).abs() < eps);
        assert!((east - north).abs() < eps);
        assert!((east - south).abs() < eps);
    }

    #[test]
    fn at_source_returns_full_strength() {
        let e = ChemicalEmission {
            kind: SignalKind::Saline,
            source_strength: 0.42,
        };
        let i = intensity_at(e, 10, 20, 5, 10, 20, 5, [1.0, 1.0]);
        assert!((i - 0.42).abs() < 1e-6);
    }

    #[test]
    fn determinism_of_emission_sampling() {
        // Same seed + coord + host ⇒ same emission, every call.
        let p = prf();
        for x in -20..20 {
            for y in -20..20 {
                for z in [-2, -5, -8] {
                    let a = emission_at(p, x, y, z, RockType::Basalt);
                    let b = emission_at(p, x, y, z, RockType::Basalt);
                    assert_eq!(a, b, "non-deterministic at ({x},{y},{z})");
                }
            }
        }
    }

    #[test]
    fn coal_seam_emits_acrid_signal() {
        // In a coal seam, at least one voxel of a 32×32 patch should emit.
        let p = prf();
        let mut acrid_seen = 0;
        for x in -16..16 {
            for y in -16..16 {
                if let Some(em) = emission_at(p, x, y, -40, RockType::CoalSeam) {
                    if em.kind == SignalKind::Acrid {
                        acrid_seen += 1;
                    }
                }
            }
        }
        assert!(
            acrid_seen > 0,
            "agent walking over a coal seam should smell SOMETHING"
        );
    }

    #[test]
    fn decay_lengths_are_ordered() {
        // Sulfur travels further than coal smoke; coal smoke further than
        // salt brine. If anyone reorders without thinking, this catches it.
        assert!(SignalKind::Pungent.decay_length_m() > SignalKind::Acrid.decay_length_m());
        assert!(SignalKind::Acrid.decay_length_m() > SignalKind::Saline.decay_length_m());
    }
}
