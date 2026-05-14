//! État global du serveur — sim + Bevy ECS + journal d'événements.

use anyhow::Result;
use bevy_ecs::world::World as BevyWorld;
use ge_agents::{spawn_founders, Aging, Deceased, Drives, Fertility, Health, Identity, Personality, Position};
use ge_ann::{Event, EventKind, JsonlSink, LineageMap, Sink};

/// Taille max du buffer d'événements récents exposé via /sim/events.
pub const RECENT_EVENTS_CAPACITY: usize = 1_024;
use ge_core::{AgentId, SimulationId, Tick, WorldSeed};
use ge_world::{ChunkStreamer, TerrainParams};
use glam::Vec3;
use serde::Serialize;
use serde_json::json;
use tracing::{info, warn};
use uuid::Uuid;

/// Vue exportée par l'API.
#[derive(Serialize, Clone, Debug)]
pub struct SimSnapshot {
    /// ID de la simulation.
    pub sim_id: String,
    /// Seed monde (hex).
    pub seed_hex: String,
    /// Tick courant.
    pub tick: u64,
    /// Nombre d'agents vivants.
    pub agents_alive: u32,
    /// Nombre d'agents morts cumulés.
    pub agents_dead: u32,
    /// Naissances cumulées depuis le démarrage (Phase 3).
    pub births_total: u64,
    /// Morts cumulées par cause (Phase 3).
    pub deaths_by_cause: serde_json::Value,
    /// Génération max observée (Phase 3 — observabilité de la lignée).
    pub max_generation: u32,
    /// Nombre d'événements émis depuis le démarrage.
    pub events_emitted: u64,
    /// Chunks en mémoire.
    pub chunks_in_memory: usize,
}

/// Vue résumée d'un agent — utilisé par `/sim/agents`.
#[derive(Serialize, Clone, Debug)]
pub struct AgentView {
    /// ID stable (UUIDv8 dérivé du seed).
    pub id: String,
    /// Génération.
    pub generation: u32,
    /// Tick de naissance.
    pub born_tick: u64,
    /// Espérance de vie en ticks (Phase 3).
    pub lifespan_ticks: u64,
    /// Position monde (m).
    pub pos: [f32; 3],
    /// Drives 0..1 (hunger, thirst, sleep, fatigue, thermal).
    pub drives: [f32; 5],
    /// Vitalité (0..1).
    pub vitality: f32,
    /// True si l'agent est mort (kept around 1 tick for event emission).
    pub deceased: bool,
    /// Compteur d'enfants (Phase 3).
    pub offspring_count: u32,
    /// True si l'agent est actuellement fertile (Phase 3).
    pub fertile: bool,
    /// Personnalité (OCEAN + 3 Genesis) — utile au dashboard.
    pub personality: [f32; 8],
}

/// État applicatif partagé entre les routes et le sim loop.
pub struct AppState {
    /// Identité de la sim.
    pub sim_id: SimulationId,
    /// Seed monde.
    pub seed: WorldSeed,
    /// Tick courant.
    pub tick: Tick,
    /// Cache de chunks (streamer).
    pub streamer: ChunkStreamer,
    /// World Bevy contenant tous les agents.
    pub world: BevyWorld,
    /// Lignée (parent → enfants).
    pub lineage: LineageMap,
    /// Stats agrégées — vivants.
    pub agents_alive: u32,
    /// Cumulatif décès (tous types).
    pub agents_dead: u32,
    /// Cumulatif naissances (fondateurs + offspring).
    pub births_total: u64,
    /// Compteur par cause de mort (key = `DeathCause` Display).
    pub deaths_by_cause: std::collections::BTreeMap<String, u64>,
    /// Génération max observée (incrémenté par le système reproduction).
    pub max_generation: u32,
    /// Buffer borné des derniers événements pour /sim/events (Phase 3).
    pub recent_events: std::collections::VecDeque<Event>,
    /// Cumulatif événements.
    pub events_emitted: u64,
    /// Sink de journal (None si désactivé).
    pub journal: Option<JsonlSink>,
    /// Prêt à servir (sim chargée et stable) ?
    pub ready: bool,
    /// Nombre de fondateurs configuré.
    pub founder_count: u32,
    /// Fondateurs déjà spawnés ?
    pub bootstrapped: bool,
}

impl AppState {
    /// Bootstrap depuis le YAML de config.
    pub fn bootstrap(config_path: &str, journal_path: Option<&str>) -> Result<Self> {
        let yaml = std::fs::read_to_string(config_path).unwrap_or_default();
        let parsed: serde_yaml_ng_like::Doc = serde_yaml_ng_like::parse(&yaml);

        let seed: WorldSeed = parsed.get_hex_u128("simulation.seed").unwrap_or(0xC0FFEE);
        let founder_count = parsed.get_u32("founders.count").unwrap_or(2);
        let sim_id = SimulationId(Uuid::new_v4());

        let journal = match journal_path {
            Some(p) => match JsonlSink::open(p) {
                Ok(s) => {
                    info!(path = %p, "journal opened");
                    Some(s)
                }
                Err(e) => {
                    warn!(error = %e, path = %p, "failed to open journal — events will not be persisted");
                    None
                }
            },
            None => None,
        };

        Ok(Self {
            sim_id,
            seed,
            tick: Tick::ZERO,
            streamer: ChunkStreamer::new(seed, TerrainParams::default()),
            world: BevyWorld::new(),
            lineage: LineageMap::new(),
            agents_alive: 0,
            agents_dead: 0,
            births_total: 0,
            deaths_by_cause: std::collections::BTreeMap::new(),
            max_generation: 0,
            recent_events: std::collections::VecDeque::with_capacity(RECENT_EVENTS_CAPACITY),
            events_emitted: 0,
            journal,
            ready: false,
            founder_count,
            bootstrapped: false,
        })
    }

    /// Pousse un lot d'événements dans le buffer borné. Maintient la
    /// capacité maximale `RECENT_EVENTS_CAPACITY` en évinçant les plus anciens.
    pub fn push_recent(&mut self, events: &[Event]) {
        for ev in events {
            if self.recent_events.len() >= RECENT_EVENTS_CAPACITY {
                self.recent_events.pop_front();
            }
            self.recent_events.push_back(ev.clone());
        }
    }

    /// Spawn initial des fondateurs. Idempotent.
    ///
    /// Positions disposées en cercle de 5 m autour de l'origine. Z fixé à 1 m
    /// pour rester au-dessus du « niveau de la mer » par défaut.
    pub fn spawn_initial(&mut self) -> Vec<AgentId> {
        if self.bootstrapped {
            return Vec::new();
        }
        let n = self.founder_count as usize;
        let mut positions = Vec::with_capacity(n);
        // Disposition en spirale logarithmique compacte — couvre une zone
        // suffisamment dense pour que des paires soient à distance de
        // reproduction sans forcer la même position (cf. Phase 2).
        // Rayon ≈ 1.5 m × sqrt(i) — assure une densité raisonnable jusqu'à n=200.
        for i in 0..n {
            let phi = (i as f32) * 2.399_963_2; // angle d'or (rad) — distribution dense
            let r = 1.5 * (i as f32).sqrt();
            positions.push(Vec3::new(phi.cos() * r, phi.sin() * r, 1.0));
        }
        let tick = self.tick.get();
        let ids = spawn_founders(&mut self.world, self.seed, &positions, tick);
        self.agents_alive = ids.len() as u32;
        self.births_total = ids.len() as u64;
        self.bootstrapped = true;

        // Émet un Birth event par fondateur — déterministe. Pousse aussi
        // dans le buffer borné `recent_events` pour /sim/events.
        let founder_events: Vec<Event> = ids
            .iter()
            .zip(positions.iter())
            .map(|(id, pos)| Event {
                event_id: Uuid::now_v7(),
                sim_id: self.sim_id,
                tick: self.tick,
                kind: EventKind::Birth,
                participants: vec![*id],
                location: *pos,
                metadata: json!({"generation": 0u32, "founder": true}),
            })
            .collect();
        if let Some(j) = self.journal.as_mut() {
            if let Err(e) = j.append(&founder_events) {
                warn!(error = %e, "failed to append birth events");
            } else {
                self.events_emitted += founder_events.len() as u64;
            }
        }
        self.push_recent(&founder_events);

        self.ready = true;
        info!(count = ids.len(), "founders spawned");
        ids
    }

    /// Snapshot léger pour /sim/state.
    pub fn snapshot(&self) -> SimSnapshot {
        SimSnapshot {
            sim_id: format!("{}", self.sim_id.0),
            seed_hex: format!("{:#034x}", self.seed),
            tick: self.tick.get(),
            agents_alive: self.agents_alive,
            agents_dead: self.agents_dead,
            births_total: self.births_total,
            deaths_by_cause: serde_json::to_value(&self.deaths_by_cause)
                .unwrap_or(serde_json::Value::Null),
            max_generation: self.max_generation,
            events_emitted: self.events_emitted,
            chunks_in_memory: self.streamer.cache.len(),
        }
    }

    /// Liste les agents pour /sim/agents. Limité à `limit` lignes.
    pub fn list_agents(&mut self, limit: usize) -> Vec<AgentView> {
        let now = self.tick.get();
        let mut out = Vec::new();
        let mut q = self.world.query::<(
            &Identity,
            &Position,
            &Drives,
            &Health,
            &Aging,
            &Fertility,
            &Personality,
            Option<&Deceased>,
        )>();
        for (id, pos, drives, health, aging, fert, pers, dead) in q.iter(&self.world) {
            if out.len() >= limit {
                break;
            }
            let alive = dead.is_none();
            out.push(AgentView {
                id: id.id.0.to_string(),
                generation: id.generation,
                born_tick: id.born_tick,
                lifespan_ticks: aging.lifespan_ticks,
                pos: [pos.0.x, pos.0.y, pos.0.z],
                drives: [
                    drives.hunger.0,
                    drives.thirst.0,
                    drives.sleep.0,
                    drives.fatigue.0,
                    drives.thermal.0,
                ],
                vitality: health.vitality,
                deceased: !alive,
                offspring_count: fert.offspring_count,
                fertile: alive && fert.is_fertile_at(now, id.born_tick),
                personality: [
                    pers.openness,
                    pers.conscientiousness,
                    pers.extraversion,
                    pers.agreeableness,
                    pers.neuroticism,
                    pers.ambition,
                    pers.risk_tolerance,
                    pers.aggression,
                ],
            });
        }
        out
    }

    /// Calcule un hash BLAKE3 sur l'état des agents — utilisé pour le test
    /// de déterminisme. Stable tant que l'ordre d'itération des entities est
    /// déterministe pour un même chemin d'insertion (vrai en Bevy 0.15).
    ///
    /// Phase 3 : inclut `Aging.lifespan_ticks`, `Fertility.offspring_count` et
    /// la `Personality` complète — toute divergence génétique fait diverger
    /// le hash de manière détectable.
    pub fn agents_root_hash(&mut self) -> [u8; 32] {
        let mut hasher = blake3::Hasher::new();
        type Row = (uuid::Uuid, [f32; 3], [f32; 5], f32, u8, u64, u32, [f32; 8]);
        let mut snapshot: Vec<Row> = Vec::new();
        let mut q = self.world.query::<(
            &Identity, &Position, &Drives, &Health,
            &Aging, &Fertility, &Personality, Option<&Deceased>,
        )>();
        for (id, pos, drives, health, aging, fert, pers, dead) in q.iter(&self.world) {
            snapshot.push((
                id.id.0,
                [pos.0.x, pos.0.y, pos.0.z],
                [
                    drives.hunger.0,
                    drives.thirst.0,
                    drives.sleep.0,
                    drives.fatigue.0,
                    drives.thermal.0,
                ],
                health.vitality,
                if dead.is_some() { 1 } else { 0 },
                aging.lifespan_ticks,
                fert.offspring_count,
                [
                    pers.openness, pers.conscientiousness, pers.extraversion,
                    pers.agreeableness, pers.neuroticism, pers.ambition,
                    pers.risk_tolerance, pers.aggression,
                ],
            ));
        }
        snapshot.sort_by_key(|r| r.0);
        for (uuid, pos, drives, vit, dead, lifespan, offspring, pers) in snapshot {
            hasher.update(uuid.as_bytes());
            for v in pos.iter().chain(drives.iter()).chain(std::iter::once(&vit)) {
                hasher.update(&v.to_le_bytes());
            }
            hasher.update(&[dead]);
            hasher.update(&lifespan.to_le_bytes());
            hasher.update(&offspring.to_le_bytes());
            for t in pers.iter() {
                hasher.update(&t.to_le_bytes());
            }
        }
        // Inclut le tick pour distinguer 2 ticks identiques sur le même état.
        hasher.update(&self.tick.get().to_le_bytes());
        *hasher.finalize().as_bytes()
    }
}

/// Mini-parseur YAML sans dépendance externe (Phase 1).
mod serde_yaml_ng_like {
    /// Document parsé en map plate "a.b.c" -> string.
    pub struct Doc {
        flat: std::collections::HashMap<String, String>,
    }

    impl Doc {
        pub fn get_hex_u128(&self, k: &str) -> Option<u128> {
            let raw = self.flat.get(k)?.trim().to_string();
            let cleaned = raw.trim_start_matches("0x").replace('_', "");
            u128::from_str_radix(&cleaned, 16).ok()
        }

        pub fn get_u32(&self, k: &str) -> Option<u32> {
            let raw = self.flat.get(k)?.trim();
            raw.parse::<u32>().ok()
        }
    }

    pub fn parse(src: &str) -> Doc {
        let mut flat = std::collections::HashMap::new();
        let mut stack: Vec<(usize, String)> = Vec::new();

        for line in src.lines() {
            if line.trim().is_empty() || line.trim_start().starts_with('#') {
                continue;
            }
            let indent = line.chars().take_while(|c| *c == ' ').count();
            while stack.last().is_some_and(|(i, _)| *i >= indent) {
                stack.pop();
            }
            if let Some((k, v)) = line.trim().split_once(':') {
                let key = k.trim().to_string();
                let val = v.trim().to_string();
                let full_key = if stack.is_empty() {
                    key.clone()
                } else {
                    let prefix = stack.iter().map(|(_, s)| s.as_str()).collect::<Vec<_>>().join(".");
                    format!("{prefix}.{key}")
                };
                if val.is_empty() {
                    stack.push((indent, key));
                } else {
                    flat.insert(full_key, val);
                }
            }
        }

        Doc { flat }
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn parses_nested_keys() {
            let src = "simulation:\n  seed: 0xC0FFEE\nfounders:\n  count: 4\n";
            let doc = parse(src);
            assert_eq!(doc.get_hex_u128("simulation.seed"), Some(0xC0FFEE));
            assert_eq!(doc.get_u32("founders.count"), Some(4));
        }
    }
}
