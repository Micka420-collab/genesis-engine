//! ge-agents — composants ECS pour les agents (Bevy ECS).
#![forbid(unsafe_code)]

pub mod aging;
pub mod body;
pub mod drives;
pub mod fertility;
pub mod health;
pub mod identity;
pub mod inventory;
pub mod memory;
pub mod personality;
pub mod spawn;
pub mod systems;

pub use aging::*;
pub use body::*;
pub use drives::*;
pub use fertility::*;
pub use health::*;
pub use identity::*;
pub use inventory::*;
pub use memory::*;
pub use personality::*;
pub use spawn::*;
pub use systems::*;
