//! ge-cognition — boucle perception → décision → action.
#![forbid(unsafe_code)]

pub mod action;
pub mod apply;
pub mod intent;
pub mod perceive;
pub mod perception;
pub mod policy_r0;

pub use action::*;
pub use apply::{apply_decision, AgentMut, TICK_DT_S as APPLY_TICK_DT_S};
pub use intent::*;
pub use perceive::{perceive_for, PERCEPTION_RADIUS_M};
pub use perception::*;
pub use policy_r0::decide;
