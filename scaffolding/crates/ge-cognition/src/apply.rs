//! Application d'une `Decision` sur les composants ECS de l'agent.
//!
//! Cette couche est volontairement déterministe et stateless : étant donnés
//! les composants courants et la décision, elle calcule le nouvel état.
//! Aucun appel à un RNG, aucun timer asynchrone — replay bit-à-bit garanti.
//!
//! Phase 1 implémente : Idle, WalkTo, Drink, Eat, Sleep, Forage, SeekShelter.
//! Mate est un no-op (réservé Phase 2 — reproduction).
//!
//! ## Note Phase 3 — récolte mondiale
//!
//! Les actions `Drink`, `Eat`, `Forage` ne créent pas de ressources ex nihilo :
//! elles posent une *intention de récolte* (vélocité à zéro, position figée),
//! et le système `run_world_harvest` de `ge-api` consomme effectivement les
//! ressources du chunk sous-jacent + applique le soulagement du drive en
//! fonction de la disponibilité réelle. Cela rend les scénarios de rareté
//! exploitables : si la cellule est vide ou non-comestible, l'agent ne tire
//! aucun bénéfice de l'action.

use crate::action::{ActionArgs, ActionId, Decision};
use ge_agents::{Drives, Inventory, ItemKind, Metabolism, Position, Velocity};
use glam::Vec3;

/// Effet de l'action appliqué par tick (en secondes simulées).
pub const TICK_DT_S: f32 = 1.0;

/// Distance en deçà de laquelle on considère la cible « atteinte ».
pub const ARRIVE_RADIUS_M: f32 = 1.5;

/// Effet de boire (drive thirst réduit / tick).
pub const DRINK_RELIEF: f32 = 0.05;
/// Effet de manger.
pub const EAT_RELIEF: f32 = 0.04;
/// Effet de dormir (sleep + fatigue récupèrent).
pub const SLEEP_RELIEF: f32 = 0.08;
/// Taux de récolte par tick (kcal / kg / unit).
pub const FORAGE_RATE_KCAL: f32 = 8.0;

/// État mutable transmis à `apply_decision`.
pub struct AgentMut<'a> {
    /// Position courante.
    pub position: &'a mut Position,
    /// Vitesse courante.
    pub velocity: &'a mut Velocity,
    /// Drives.
    pub drives: &'a mut Drives,
    /// Inventaire.
    pub inventory: &'a mut Inventory,
    /// Métabolisme (lecture seule).
    pub metabolism: &'a Metabolism,
}

/// Applique une décision sur un agent.
///
/// Retourne `true` si l'action a effectivement été *exécutée* (par opposition
/// à juste mise à jour de la trajectoire), ce qui permet à l'annaliste de
/// loguer un événement.
pub fn apply_decision(agent: &mut AgentMut<'_>, decision: &Decision) -> bool {
    match decision.action {
        ActionId::Idle => {
            agent.velocity.0 = Vec3::ZERO;
            false
        }
        ActionId::WalkTo => walk_to(agent, &decision.args),
        ActionId::Drink => drink(agent),
        ActionId::Eat => eat(agent),
        ActionId::Sleep => sleep(agent),
        ActionId::Forage => forage(agent),
        ActionId::SeekShelter => walk_to(agent, &decision.args),
        ActionId::Mate => {
            // Phase 2 — placeholder explicite, pas une erreur.
            agent.velocity.0 = Vec3::ZERO;
            false
        }
    }
}

fn walk_to(agent: &mut AgentMut<'_>, args: &ActionArgs) -> bool {
    let target = match args {
        ActionArgs::Target(t) => *t,
        _ => {
            agent.velocity.0 = Vec3::ZERO;
            return false;
        }
    };
    let here = agent.position.0;
    let delta = target - here;
    let dist = delta.length();
    if dist < ARRIVE_RADIUS_M {
        agent.velocity.0 = Vec3::ZERO;
        // Snap on target horizontalement.
        agent.position.0.x = target.x;
        agent.position.0.y = target.y;
        return true;
    }
    let direction = delta / dist.max(1e-6);
    // Run si un drive est critique, sinon walk.
    let speed = if agent.drives.any_critical() {
        agent.metabolism.run_max_ms
    } else {
        agent.metabolism.walk_max_ms
    };
    agent.velocity.0 = direction * speed;
    false
}

fn drink(agent: &mut AgentMut<'_>) -> bool {
    // Phase 3 : c'est `run_world_harvest` (côté ge-api) qui consomme l'eau
    // du chunk et applique le soulagement effectif du drive. Ici on se
    // contente de fixer la vélocité à zéro pour figer l'agent sur place
    // pendant qu'il boit.
    agent.velocity.0 = Vec3::ZERO;
    false
}

fn eat(agent: &mut AgentMut<'_>) -> bool {
    agent.velocity.0 = Vec3::ZERO;
    // Si l'agent a déjà de la food en inventaire (récoltée précédemment),
    // il peut la consommer immédiatement — pas besoin de chunk. Sinon le
    // système de récolte traitera l'intention au même tick.
    let food = agent.inventory.take(ItemKind::Food, 0.5);
    if food <= 0.0 {
        return false;
    }
    let before = agent.drives.hunger.0;
    agent.drives.hunger = agent.drives.hunger.add(-EAT_RELIEF * food.max(0.1));
    before > agent.drives.hunger.0
}

fn sleep(agent: &mut AgentMut<'_>) -> bool {
    agent.velocity.0 = Vec3::ZERO;
    let before = agent.drives.sleep.0 + agent.drives.fatigue.0;
    agent.drives.sleep = agent.drives.sleep.add(-SLEEP_RELIEF);
    agent.drives.fatigue = agent.drives.fatigue.add(-SLEEP_RELIEF * 0.5);
    let after = agent.drives.sleep.0 + agent.drives.fatigue.0;
    before > after
}

fn forage(agent: &mut AgentMut<'_>) -> bool {
    // Phase 3 : le système `run_world_harvest` côté ge-api consulte le chunk
    // sous l'agent et crédite l'inventaire en fonction de la NPP et du wood
    // disponible. Ici on se contente d'immobiliser l'agent.
    agent.velocity.0 = Vec3::ZERO;
    false
}

#[cfg(test)]
mod tests {
    use super::*;
    use ge_agents::{Drive, Drives, Inventory, Metabolism, Position, Velocity};

    fn fresh_agent() -> (Position, Velocity, Drives, Inventory, Metabolism) {
        (
            Position(Vec3::ZERO),
            Velocity(Vec3::ZERO),
            Drives::newborn(),
            Inventory::empty_human(),
            Metabolism::human_adult(),
        )
    }

    #[test]
    fn drink_is_velocity_zero_intent_only() {
        // Phase 3 : `Drink` est désormais une *intention* — l'effet hydrique
        // est appliqué par `run_world_harvest` côté ge-api en fonction du
        // chunk sous l'agent. La cognition se contente d'immobiliser.
        let (mut p, mut v, mut d, mut inv, m) = fresh_agent();
        v.0 = Vec3::new(2.0, 0.0, 0.0);
        d.thirst = Drive(0.5);
        let mut a = AgentMut { position: &mut p, velocity: &mut v, drives: &mut d, inventory: &mut inv, metabolism: &m };
        let _ = apply_decision(&mut a, &Decision { action: ActionId::Drink, args: ActionArgs::None, confidence: 1.0 });
        assert_eq!(v.0, Vec3::ZERO);
        // Le drive n'a pas changé à ce niveau.
        assert!((d.thirst.0 - 0.5).abs() < 1e-6);
    }

    #[test]
    fn walk_to_sets_velocity_toward_target() {
        let (mut p, mut v, mut d, mut inv, m) = fresh_agent();
        let mut a = AgentMut { position: &mut p, velocity: &mut v, drives: &mut d, inventory: &mut inv, metabolism: &m };
        apply_decision(&mut a, &Decision {
            action: ActionId::WalkTo,
            args: ActionArgs::Target(Vec3::new(10.0, 0.0, 0.0)),
            confidence: 0.8,
        });
        assert!(v.0.x > 0.0);
    }

    #[test]
    fn walk_to_arrive_zeros_velocity() {
        let (mut p, mut v, mut d, mut inv, m) = fresh_agent();
        p.0 = Vec3::new(0.0, 0.0, 0.0);
        let mut a = AgentMut { position: &mut p, velocity: &mut v, drives: &mut d, inventory: &mut inv, metabolism: &m };
        let arrived = apply_decision(&mut a, &Decision {
            action: ActionId::WalkTo,
            args: ActionArgs::Target(Vec3::new(0.5, 0.0, 0.0)),
            confidence: 0.8,
        });
        assert!(arrived);
        assert_eq!(v.0, Vec3::ZERO);
    }

    #[test]
    fn idle_zeros_velocity() {
        let (mut p, mut v, mut d, mut inv, m) = fresh_agent();
        v.0 = Vec3::new(1.0, 0.0, 0.0);
        let mut a = AgentMut { position: &mut p, velocity: &mut v, drives: &mut d, inventory: &mut inv, metabolism: &m };
        apply_decision(&mut a, &Decision::idle());
        assert_eq!(v.0, Vec3::ZERO);
    }
}
