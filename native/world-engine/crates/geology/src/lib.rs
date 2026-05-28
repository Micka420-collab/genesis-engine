//! genesis-geology — deterministic mineral distribution + surface visual cues.
//!
//! **Wave 43 — Substrate physique : indices visuels minéraux.**
//!
//! The agent must DISCOVER ore by observation, never by being told it exists.
//! This crate produces, for any deterministic `(WorldCoord, seed)`, a triple:
//!
//!   `(RockType, Option<MineralDeposit>, SurfaceColorHint)`
//!
//! The `SurfaceColorHint` is the RGB the agent's vision system samples when
//! looking at the surface voxel. A green patch on otherwise grey stone is
//! malachite — an indirect indicator of underlying copper. The agent never
//! reads `Mineral::Copper`; it sees a colour, remembers, returns, mines.
//!
//! Geological rules are scientifically grounded (Wave 43 sprint doc):
//!   - Flint nodules → in limestone, near coast
//!   - Copper porphyry → metamorphic + pluton contact, malachite cap rock
//!   - Tin → granitic pegmatite, shear zones
//!   - Iron → BIF in Precambrian-class strata
//!   - Gold → quartz vein + hydrothermal shear
//!   - Coal seams → compressed organic strata under sedimentary cover
//!   - Salt → palaeo-sea evaporite deposits in low basins
//!   - Sulfur → active volcanic / fumarolic field
//!   - Obsidian → rapid-cooled volcanic flow (coastal / lakeside)
//!   - Fine clay → ubiquitous surface, quality varies
//!   - Limestone (pure) → coastal sedimentary outcrops
//!
//! All randomness comes from `genesis_core::Prf`. No `rand::thread_rng`.
//! Same `(seed, x, y, z)` ⇒ same answer, forever.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod mineral;
pub mod rock;
pub mod visual;

pub use mineral::{Mineral, MineralDeposit, MINERAL_COUNT};
pub use rock::{RockType, ROCK_TYPE_COUNT};
pub use visual::{
    sample_surface, surface_color_hint, SurfaceColorHint, SurfaceSample,
};
