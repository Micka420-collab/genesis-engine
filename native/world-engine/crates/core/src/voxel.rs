//! Voxel + material taxonomy.
//!
//! A voxel is a 16-bit palette index inside a chunk; the palette maps
//! `u16 -> Material`. This keeps chunks small while allowing unlimited
//! material variety globally.

use bytemuck::{Pod, Zeroable};
use serde::{Deserialize, Serialize};

/// Palette index inside a chunk. 0 = AIR by convention.
#[repr(transparent)]
#[derive(
    Copy, Clone, Debug, Default, PartialEq, Eq, Hash, Pod, Zeroable, Serialize, Deserialize,
)]
pub struct Voxel(pub u16);

impl Voxel {
    /// The "empty" voxel — must always be palette index 0.
    pub const AIR: Voxel = Voxel(0);

    /// `true` if the voxel is air.
    #[inline]
    #[must_use]
    pub const fn is_air(self) -> bool {
        self.0 == 0
    }
}

/// Material classes. The `Material` enum is the *global* taxonomy; chunks
/// hold a *local* palette of indices that map into this enum.
#[repr(u16)]
#[derive(Copy, Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Material {
    /// Empty space.
    Air = 0,
    /// Crustal rock (basalt/granite-class).
    Bedrock = 1,
    /// Dense subsurface stone.
    Stone = 2,
    /// Mineral soil layer.
    Dirt = 3,
    /// Vegetative topsoil.
    Grass = 4,
    /// Loose dry mineral grains.
    Sand = 5,
    /// Frozen H₂O.
    Ice = 6,
    /// Compacted frozen water vapor.
    Snow = 7,
    /// Liquid H₂O.
    Water = 8,
    /// Molten silicates (T > ~700 °C).
    Lava = 9,
    /// Plant biomass — trunk or wood.
    Wood = 10,
    /// Plant biomass — canopy.
    Leaves = 11,
    /// Reserved range for procedural/user-defined materials.
    UserDefined = 0xFF00,
}

impl Material {
    /// Whether this material blocks line-of-sight.
    #[must_use]
    pub const fn opaque(self) -> bool {
        !matches!(self, Material::Air | Material::Water | Material::Leaves)
    }

    /// Whether agents/fauna treat this as walkable surface.
    #[must_use]
    pub const fn walkable(self) -> bool {
        matches!(
            self,
            Material::Bedrock
                | Material::Stone
                | Material::Dirt
                | Material::Grass
                | Material::Sand
                | Material::Snow
                | Material::Ice
        )
    }
}
