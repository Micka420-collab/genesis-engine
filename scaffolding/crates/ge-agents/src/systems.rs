//! Systèmes Bevy ECS — boucle de tick côté agents.
//!
//! Phase 1 : 3 systèmes :
//! - `tick_drives` : faim/soif/sommeil croissent linéairement
//! - `apply_velocity` : mise à jour de la position
//! - `check_mortality` : repère les agents à tuer pour le tick suivant
//!
//! L'ordre canonique des systèmes est défini dans `ge-api`.

use crate::body::{Position, Velocity, Metabolism};
use crate::drives::{Drive, Drives};
use crate::health::Health;
use crate::identity::{Deceased, DeathCause, Identity};
use bevy_ecs::prelude::*;

/// Durée d'un tick simulé en secondes (Phase 1 = 1 s).
pub const TICK_DT_S: f32 = 1.0;

/// Système : croissance des drives biologiques.
///
/// Mod simple Phase 1, calibré pour qu'un agent meure de soif en ~3 jours
/// et de faim en ~14 jours s'il ne fait rien.
pub fn tick_drives(mut q: Query<(&mut Drives, &Metabolism)>) {
    // 86 400 s / 3 jours ≈ 259 200 → +1.0 / 259 200 s ≈ 3.86e-6 / s
    const HUNGER_PER_S: f32 = 1.0 / (14.0 * 86_400.0);
    const THIRST_PER_S: f32 = 1.0 / (3.0 * 86_400.0);
    const FATIGUE_PER_S: f32 = 1.0 / (1.0 * 86_400.0);
    const SLEEP_PER_S: f32 = 1.0 / (1.5 * 86_400.0);
    for (mut d, _m) in q.iter_mut() {
        d.hunger = d.hunger.add(HUNGER_PER_S * TICK_DT_S);
        d.thirst = d.thirst.add(THIRST_PER_S * TICK_DT_S);
        d.fatigue = d.fatigue.add(FATIGUE_PER_S * TICK_DT_S);
        d.sleep = d.sleep.add(SLEEP_PER_S * TICK_DT_S);
    }
}

/// Système : intégration de la vitesse dans la position.
pub fn apply_velocity(mut q: Query<(&Velocity, &mut Position)>) {
    for (v, mut p) in q.iter_mut() {
        p.0 += v.0 * TICK_DT_S;
    }
}

/// Système : marquage des agents à tuer cette frame.
///
/// Critères : drive critique (>= 1.0) sur soif/faim/fatigue OU santé fatale.
pub fn check_mortality(
    mut cmd: Commands,
    q: Query<(Entity, &Identity, &Drives, &Health), Without<Deceased>>,
    tick: Res<CurrentTick>,
) {
    for (e, id, d, h) in q.iter() {
        let cause = if h.fatal() {
            Some(DeathCause::Exhaustion)
        } else if d.thirst.is_critical() {
            Some(DeathCause::Dehydration)
        } else if d.hunger.is_critical() {
            Some(DeathCause::Starvation)
        } else if d.thermal.is_critical() {
            // distinction chaud/froid: à raffiner via le delta de température
            Some(DeathCause::Cold)
        } else if d.fatigue.is_critical() && d.sleep.is_critical() {
            Some(DeathCause::Exhaustion)
        } else {
            None
        };
        if let Some(cause) = cause {
            tracing::info!(agent = ?id.id, ?cause, "agent died");
            cmd.entity(e).insert(Deceased { died_tick: tick.0, cause });
        }
    }
}

/// Ressource Bevy — tick courant exposé aux systèmes.
#[derive(Resource, Copy, Clone, Debug)]
pub struct CurrentTick(pub u64);
