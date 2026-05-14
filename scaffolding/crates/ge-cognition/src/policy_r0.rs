//! Policy R0 — reflex utilitariste.
//!
//! Règle :
//! 1. Si un drive est critique (>= 0.85) → agir dessus immédiatement.
//! 2. Sinon, satisfaire le drive dominant si une cible existe.
//! 3. Sinon, idle (Phase 2 ajoutera exploration / social).
//!
//! Déterministe : pour les bris d'égalité on prend l'ordre Hunger > Thirst > ...

use crate::action::{ActionArgs, ActionId, Decision};
use crate::perception::{Observation, TargetKind};
use ge_agents::DriveKind;

const CRITICAL_THRESHOLD: f32 = 0.85;
const ACT_THRESHOLD: f32 = 0.40;

/// Décide quoi faire ce tick.
pub fn decide(obs: &Observation) -> Decision {
    // 1. Drive critique en priorité.
    if let Some(dec) = act_on_critical(obs) {
        return dec;
    }

    // 2. Drive dominant si au-dessus du seuil d'action.
    let dom = obs.dominant_drive;
    let dom_value = drive_value(obs, dom);
    if dom_value >= ACT_THRESHOLD {
        if let Some(dec) = act_on_drive(obs, dom) {
            return dec;
        }
    }

    // 3. Repli : idle.
    Decision::idle()
}

fn drive_value(obs: &Observation, k: DriveKind) -> f32 {
    match k {
        DriveKind::Hunger => obs.drives.hunger.0,
        DriveKind::Thirst => obs.drives.thirst.0,
        DriveKind::Sleep => obs.drives.sleep.0,
        DriveKind::Fatigue => obs.drives.fatigue.0,
        DriveKind::Thermal => obs.drives.thermal.0,
    }
}

fn act_on_critical(obs: &Observation) -> Option<Decision> {
    // Ordre canonique : Thirst > Hunger > Thermal > Sleep > Fatigue.
    for k in [
        DriveKind::Thirst,
        DriveKind::Hunger,
        DriveKind::Thermal,
        DriveKind::Sleep,
        DriveKind::Fatigue,
    ] {
        if drive_value(obs, k) >= CRITICAL_THRESHOLD {
            if let Some(d) = act_on_drive(obs, k) {
                return Some(d);
            }
        }
    }
    None
}

fn act_on_drive(obs: &Observation, k: DriveKind) -> Option<Decision> {
    match k {
        DriveKind::Thirst => {
            let w = obs.nearest(TargetKind::Water)?;
            Some(if w.distance_m < 1.5 {
                Decision { action: ActionId::Drink, args: ActionArgs::None, confidence: 0.9 }
            } else {
                Decision { action: ActionId::WalkTo, args: ActionArgs::Target(w.pos), confidence: 0.8 }
            })
        }
        DriveKind::Hunger => {
            let f = obs.nearest(TargetKind::Food)?;
            Some(if f.distance_m < 1.5 {
                Decision { action: ActionId::Eat, args: ActionArgs::None, confidence: 0.9 }
            } else {
                Decision { action: ActionId::WalkTo, args: ActionArgs::Target(f.pos), confidence: 0.7 }
            })
        }
        DriveKind::Thermal => {
            let s = obs.nearest(TargetKind::Shelter)?;
            Some(if s.distance_m < 1.5 {
                Decision { action: ActionId::SeekShelter, args: ActionArgs::None, confidence: 0.85 }
            } else {
                Decision { action: ActionId::WalkTo, args: ActionArgs::Target(s.pos), confidence: 0.7 }
            })
        }
        DriveKind::Sleep | DriveKind::Fatigue => {
            Some(Decision { action: ActionId::Sleep, args: ActionArgs::None, confidence: 0.8 })
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ge_agents::{Drive, Drives, Health};
    use crate::perception::{Observation, PerceivedTarget};
    use glam::Vec3;

    fn obs_with_drives(d: Drives, near: Vec<PerceivedTarget>) -> Observation {
        let dominant = d.dominant();
        Observation { drives: d, health: Health::full(), dominant_drive: dominant, nearby: near }
    }

    #[test]
    fn thirst_critical_with_water_nearby_drinks() {
        let mut d = Drives::newborn();
        d.thirst = Drive(0.95);
        let obs = obs_with_drives(d, vec![PerceivedTarget {
            kind: TargetKind::Water, pos: Vec3::ZERO, distance_m: 1.0, qty: 100.0,
        }]);
        let dec = decide(&obs);
        assert_eq!(dec.action, ActionId::Drink);
    }

    #[test]
    fn thirst_critical_no_water_idles() {
        let mut d = Drives::newborn();
        d.thirst = Drive(0.95);
        let obs = obs_with_drives(d, vec![]);
        let dec = decide(&obs);
        assert_eq!(dec.action, ActionId::Idle);
    }

    #[test]
    fn calm_agent_idles() {
        let obs = obs_with_drives(Drives::newborn(), vec![]);
        let dec = decide(&obs);
        assert_eq!(dec.action, ActionId::Idle);
    }
}
