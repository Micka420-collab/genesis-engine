//! ge-substrate — fondation physique du monde Genesis.
//!
//! Ce crate fournit :
//! - les **types voxel** (`WaterVoxel`, `SoilHydro`, `GeoVoxel`) en
//!   `#[repr(C)]` alignés pour un futur port GPU bit-exact ;
//! - une **implémentation CPU de référence** des équations en eau
//!   peu profonde (Saint-Venant simplifié, schéma "pipe model") ;
//! - l'**érosion hydraulique** (Wave 11) qui couple la grille d'eau
//!   au transport de sédiments, la déposition et l'érosion thermique ;
//! - l'**infiltration sol** Green-Ampt (Wave 11), avec drainage
//!   gravitaire et évapotranspiration Hamon-like ;
//! - les **invariants physiques** vérifiés en `debug_assert!` actifs
//!   même en release (conservation de masse, déterminisme, localité).
//!
//! Doctrine : la version CPU sert d'**oracle bit-exact** pour valider
//! le futur compute shader WGSL. Voir ADR-0006.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod erosion;
pub mod soil;
pub mod voxel;
pub mod water;

pub use erosion::{apply_debris_flow_step, ErosionGrid, ErosionParams};
pub use soil::{
    evapotranspiration_step, gravity_drain_step, green_ampt_step, GreenAmptParams,
    InfiltrationResult,
};
pub use voxel::{GeoVoxel, Mineral, RockType, SoilHydro, WaterVoxel};
pub use water::{HydroGrid, HydroParams};
