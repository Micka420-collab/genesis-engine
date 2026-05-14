//! Détecteurs d'événements.
//!
//! Phase 1 : Birth + Death (depuis les tick deltas).
//! Phase 2 : Innovation (premier outil), Founding (cluster spatial stable).
//! Phase 3 : Conflict (violences groupées), Trade (transfert d'item récurrent).

use crate::event::{Event, EventKind};
use ge_core::{AgentId, SimulationId, Tick};
use glam::Vec3;
use serde_json::json;
use uuid::Uuid;

/// Trait commun à tous les détecteurs.
pub trait Detector: Send {
    /// Inspecte un delta de tick et émet 0..N événements.
    fn inspect(&mut self, ctx: &TickContext) -> Vec<Event>;
}

/// Contexte fourni à chaque détecteur pour un tick.
pub struct TickContext<'a> {
    /// Sim ID.
    pub sim_id: SimulationId,
    /// Tick courant.
    pub tick: Tick,
    /// Agents nés ce tick.
    pub births: &'a [(AgentId, Vec3)],
    /// Agents morts ce tick.
    pub deaths: &'a [(AgentId, Vec3, &'a str)],
}

/// Détecteur trivial — birth / death.
pub struct VitalDetector;

impl Detector for VitalDetector {
    fn inspect(&mut self, ctx: &TickContext) -> Vec<Event> {
        let mut out = Vec::with_capacity(ctx.births.len() + ctx.deaths.len());
        for (id, pos) in ctx.births {
            out.push(Event {
                event_id: Uuid::now_v7(),
                sim_id: ctx.sim_id,
                tick: ctx.tick,
                kind: EventKind::Birth,
                participants: vec![*id],
                location: *pos,
                metadata: json!({}),
            });
        }
        for (id, pos, cause) in ctx.deaths {
            out.push(Event {
                event_id: Uuid::now_v7(),
                sim_id: ctx.sim_id,
                tick: ctx.tick,
                kind: EventKind::Death,
                participants: vec![*id],
                location: *pos,
                metadata: json!({ "cause": cause }),
            });
        }
        out
    }
}
