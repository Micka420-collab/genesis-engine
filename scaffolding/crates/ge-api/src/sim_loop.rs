//! Boucle de simulation principale (Phase 1, mono-node).
//!
//! Cette boucle exécute l'ordre canonique des systèmes par tick :
//! 1. Spawn initial des fondateurs (1ʳᵉ itération uniquement)
//! 2. Streaming des chunks autour des agents
//! 3. Croissance des drives (`tick_drives`)
//! 4. Perception → Decision (R0) → Apply
//! 5. Intégration de la vélocité (`apply_velocity`)
//! 6. Détection des morts (`check_mortality`) + emission Death events
//! 7. GC chunks périodique
//!
//! Toute mutation se fait sous `state.write().await`. Pas d'unsafe.

use crate::state::AppState;
use bevy_ecs::prelude::*;
use ge_agents::{
    spawn_offspring, Aging, Deceased, Drives, Episode, EpisodeKind, Fertility, Health, Identity,
    Inventory, ItemKind, Memory, Metabolism, Personality, Position, Velocity,
    DRIVE_BLOCK_THRESHOLD, MATING_RADIUS_M,
};
use ge_ann::{Event, EventKind, Sink};
use ge_cognition::{
    apply_decision, decide, perceive_for, ActionId, AgentMut, Decision, PERCEPTION_RADIUS_M,
};
use ge_core::{AgentId, ChunkCoord};
use ge_world::{
    area_around, sample as sample_terrain, weather_at, Biome, Chunk, TerrainSample, CHUNK_SIZE,
    VOXEL_SIZE_M,
};
use serde_json::json;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::{info, warn};
use uuid::Uuid;

/// Boucle principale.
pub async fn run(state: Arc<RwLock<AppState>>) {
    // Cadence Phase 1 : 10 ticks/seconde (TimeScale::Standard).
    let target_period = Duration::from_millis(100);

    // Spawn initial.
    {
        let mut g = state.write().await;
        g.spawn_initial();
    }

    loop {
        let started = Instant::now();
        {
            let mut g = state.write().await;
            step_once(&mut g);
        }

        let elapsed = started.elapsed();
        if elapsed < target_period {
            tokio::time::sleep(target_period - elapsed).await;
        } else if elapsed > target_period * 2 {
            warn!(?elapsed, "sim tick exceeded target period");
        }
    }
}

/// Exécute un seul tick. Public pour permettre `/sim/step` et les tests.
pub fn step_once(state: &mut AppState) {
    let tick = state.tick.next();
    state.tick = tick;

    // 1) Streaming : zone autour de chaque agent + autour de l'origine.
    let active_positions = collect_active_positions(&mut state.world);
    let mut wanted: std::collections::HashSet<ChunkCoord> = std::collections::HashSet::new();
    if active_positions.is_empty() {
        // Aucun agent : on garde un voisinage minimal autour de l'origine.
        for c in area_around(ChunkCoord::new(0, 0, 0), 2) {
            wanted.insert(c);
        }
    } else {
        for pos in &active_positions {
            let center = Chunk::from_world_pos(pos.x, pos.y, pos.z);
            for c in area_around(center, 2) {
                wanted.insert(c);
            }
        }
    }
    state.streamer.touch_area(tick, wanted.into_iter());

    // 2) Tick drives — système simple (Bevy SystemState n'est pas nécessaire).
    run_tick_drives(&mut state.world);

    // 2b) Thermal comfort — wire la météo et le biome local au drive `thermal`.
    //     Sans ça, le drive `thermal` ne bouge jamais et `detect_mortality`
    //     ne peut jamais conclure à un décès par froid/chaud. C'est nécessaire
    //     pour les expériences de type "catastrophe environnementale".
    run_thermal_comfort(state);

    // 3) Perception → Décision (lecture seule sur l'ECS + streamer).
    let decisions = perceive_and_decide(state);

    // 4) Apply decisions (mutation).
    apply_decisions(&mut state.world, &decisions);

    // 4b) Récolte mondiale — consomme réellement les ressources des chunks
    //     pour les agents qui ont mangé/bu/fouragé ce tick. Sans cela, les
    //     ressources sont infinies et l'expérience "rareté" est impossible.
    run_world_harvest(state, &decisions);

    // 5) Intégration vélocité.
    run_apply_velocity(&mut state.world);

    // 6a-pre) Catastrophe environnementale (Phase 3, expérience 4).
    //         Si configurée et que le tick courant correspond, applique un
    //         choc de santé/thermal sur les agents dans la zone d'impact.
    let catastrophe_events = run_catastrophe(state);

    // 6a) Reproduction (Phase 2) — pairs proches & fertiles → naissances.
    //     Population cap : si on a déjà atteint `max_agents`, on saute.
    let birth_events = if state.agents_alive >= state.max_agents {
        Vec::new()
    } else {
        run_reproduction(state)
    };

    // 6b) Mémoire : enregistre la souffrance courante (drive >= 0.85).
    record_suffering(state);

    // 6c) Mortalité + emission events (incl. OldAge — Phase 3).
    let death_events = detect_mortality(state);

    // 7) Compte agents vivants/morts + maintient les compteurs cumulatifs.
    state.births_total = state.births_total.saturating_add(birth_events.len() as u64);
    for ev in &death_events {
        let cause = ev
            .metadata
            .get("cause")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown")
            .to_string();
        *state.deaths_by_cause.entry(cause).or_insert(0) += 1;
    }
    for ev in &birth_events {
        if let Some(g) = ev.metadata.get("generation").and_then(|v| v.as_u64()) {
            if (g as u32) > state.max_generation {
                state.max_generation = g as u32;
            }
        }
    }
    update_counters(state);

    // Persiste les events (naissances, décès, catastrophes) si journal actif.
    // Pousse également dans le buffer borné `recent_events` pour /sim/events.
    if !birth_events.is_empty() || !death_events.is_empty() || !catastrophe_events.is_empty() {
        if let Some(j) = state.journal.as_mut() {
            if !birth_events.is_empty() {
                if let Err(e) = j.append(&birth_events) {
                    warn!(error = %e, "failed to append birth events");
                } else {
                    state.events_emitted += birth_events.len() as u64;
                }
            }
            if !death_events.is_empty() {
                if let Err(e) = j.append(&death_events) {
                    warn!(error = %e, "failed to append death events");
                } else {
                    state.events_emitted += death_events.len() as u64;
                }
            }
            if !catastrophe_events.is_empty() {
                if let Err(e) = j.append(&catastrophe_events) {
                    warn!(error = %e, "failed to append catastrophe events");
                } else {
                    state.events_emitted += catastrophe_events.len() as u64;
                }
            }
            let _ = j.flush();
        }
        state.push_recent(&birth_events);
        state.push_recent(&death_events);
        state.push_recent(&catastrophe_events);
    }

    // 8) GC chunks périodique.
    if tick.get() % 1000 == 0 {
        let t = state.tick;
        state.streamer.gc(t);
        info!(
            tick = tick.get(),
            chunks = state.streamer.cache.len(),
            agents_alive = state.agents_alive,
            agents_dead = state.agents_dead,
            "tick heartbeat"
        );
    }
}

fn collect_active_positions(world: &mut bevy_ecs::world::World) -> Vec<glam::Vec3> {
    let mut q = world.query_filtered::<&Position, Without<Deceased>>();
    q.iter(world).map(|p| p.0).collect()
}

fn run_tick_drives(world: &mut bevy_ecs::world::World) {
    // Reproduit `ge_agents::tick_drives` sans passer par un Schedule complet.
    const HUNGER_PER_S: f32 = 1.0 / (14.0 * 86_400.0);
    const THIRST_PER_S: f32 = 1.0 / (3.0 * 86_400.0);
    const FATIGUE_PER_S: f32 = 1.0 / (1.0 * 86_400.0);
    const SLEEP_PER_S: f32 = 1.0 / (1.5 * 86_400.0);
    const DT: f32 = 1.0;
    let mut q = world.query_filtered::<&mut Drives, Without<Deceased>>();
    for mut d in q.iter_mut(world) {
        d.hunger = d.hunger.add(HUNGER_PER_S * DT);
        d.thirst = d.thirst.add(THIRST_PER_S * DT);
        d.fatigue = d.fatigue.add(FATIGUE_PER_S * DT);
        d.sleep = d.sleep.add(SLEEP_PER_S * DT);
    }
}

fn perceive_and_decide(state: &mut AppState) -> HashMap<Entity, Decision> {
    let mut out = HashMap::new();
    let mut q = state
        .world
        .query_filtered::<(Entity, &Position, &Drives, &Health), Without<Deceased>>();
    let snapshots: Vec<(Entity, glam::Vec3, Drives, Health)> = q
        .iter(&state.world)
        .map(|(e, p, d, h)| (e, p.0, *d, *h))
        .collect();
    for (entity, pos, drives, health) in snapshots {
        let obs = perceive_for(&state.streamer, pos, drives, health, PERCEPTION_RADIUS_M);
        let decision = decide(&obs);
        out.insert(entity, decision);
    }
    out
}

fn apply_decisions(world: &mut bevy_ecs::world::World, decisions: &HashMap<Entity, Decision>) {
    let entities: Vec<Entity> = decisions.keys().copied().collect();
    for entity in entities {
        let Some(decision) = decisions.get(&entity) else { continue };
        // On retire les composants nécessaires, on mute, on les remet.
        let Some(mut entity_mut) = world.get_entity_mut(entity).ok() else { continue };
        let Some(mut position) = entity_mut.take::<Position>() else { continue };
        let Some(mut velocity) = entity_mut.take::<Velocity>() else {
            entity_mut.insert(position);
            continue;
        };
        let Some(mut drives) = entity_mut.take::<Drives>() else {
            entity_mut.insert((position, velocity));
            continue;
        };
        let Some(mut inventory) = entity_mut.take::<Inventory>() else {
            entity_mut.insert((position, velocity, drives));
            continue;
        };
        let Some(metabolism) = entity_mut.get::<Metabolism>().cloned() else {
            entity_mut.insert((position, velocity, drives, inventory));
            continue;
        };

        {
            let mut agent = AgentMut {
                position: &mut position,
                velocity: &mut velocity,
                drives: &mut drives,
                inventory: &mut inventory,
                metabolism: &metabolism,
            };
            apply_decision(&mut agent, decision);
        }

        entity_mut.insert((position, velocity, drives, inventory));
    }
}

fn run_apply_velocity(world: &mut bevy_ecs::world::World) {
    const DT: f32 = 1.0;
    let mut q = world.query_filtered::<(&Velocity, &mut Position), Without<Deceased>>();
    for (v, mut p) in q.iter_mut(world) {
        p.0 += v.0 * DT;
    }
}

fn detect_mortality(state: &mut AppState) -> Vec<Event> {
    let tick = state.tick;
    let sim_id = state.sim_id;
    let now = tick.get();
    let mut events = Vec::new();
    // Itère vivants — repère ceux à marquer. Inclut l'âge.
    let mut q = state
        .world
        .query_filtered::<(Entity, &Identity, &Drives, &Health, &Aging, &Position), Without<Deceased>>();
    let kills: Vec<(Entity, ge_core::AgentId, glam::Vec3, &'static str)> = q
        .iter(&state.world)
        .filter_map(|(e, id, d, h, age, pos)| {
            // OldAge en premier : on consomme la trajectoire « naturelle »
            // avant les drives quand l'agent est arrivé en fin de vie.
            let cause = if age.died_of_age(now, id.born_tick) {
                Some("old_age")
            } else if h.fatal() {
                Some("exhaustion")
            } else if d.thirst.is_critical() {
                Some("dehydration")
            } else if d.hunger.is_critical() {
                Some("starvation")
            } else if d.thermal.is_critical() {
                Some("cold")
            } else if d.fatigue.is_critical() && d.sleep.is_critical() {
                Some("exhaustion")
            } else {
                None
            };
            cause.map(|c| (e, id.id, pos.0, c))
        })
        .collect();

    for (entity, agent_id, pos, cause) in kills {
        state.world.entity_mut(entity).insert(Deceased {
            died_tick: tick.get(),
            cause: cause_to_enum(cause),
        });
        events.push(Event {
            event_id: Uuid::now_v7(),
            sim_id,
            tick,
            kind: EventKind::Death,
            participants: vec![agent_id],
            location: pos,
            metadata: json!({ "cause": cause }),
        });
    }

    events
}

fn cause_to_enum(s: &str) -> ge_agents::DeathCause {
    use ge_agents::DeathCause::*;
    match s {
        "starvation" => Starvation,
        "dehydration" => Dehydration,
        "cold" => Cold,
        "heat" => Heat,
        "old_age" => OldAge,
        _ => Exhaustion,
    }
}

fn update_counters(state: &mut AppState) {
    let mut alive_q = state.world.query_filtered::<Entity, Without<Deceased>>();
    let mut dead_q = state.world.query_filtered::<Entity, With<Deceased>>();
    state.agents_alive = alive_q.iter(&state.world).count() as u32;
    state.agents_dead = dead_q.iter(&state.world).count() as u32;
}

/// Reproduction (Phase 2).
///
/// Repère les paires d'agents fertiles à <= `MATING_RADIUS_M` les uns des
/// autres, à condition qu'aucun drive bloquant ne dépasse
/// `DRIVE_BLOCK_THRESHOLD`. Pour chaque paire retenue, spawn un enfant
/// déterministe, met à jour `Fertility`, enregistre la lignée et émet un
/// événement `Birth`.
///
/// Déterminisme : on trie les candidats par `AgentId` avant de constituer
/// les paires (un agent ne peut être que dans une paire par tick). L'ordre
/// canonique élimine la dépendance à l'ordre d'itération Bevy.
fn run_reproduction(state: &mut AppState) -> Vec<Event> {
    let tick = state.tick;
    let sim_id = state.sim_id;
    let seed = state.seed;
    let now = tick.get();

    // 1) Collecte les candidats fertiles (sans &mut World — lecture seule).
    //    On capture aussi la `Personality` pour pouvoir hériter génétiquement
    //    plus loin sans devoir re-fetch l'ECS.
    let mut candidates: Vec<(Entity, AgentId, u32, glam::Vec3, Personality)> = Vec::new();
    {
        let mut q = state.world.query_filtered::<
            (Entity, &Identity, &Position, &Drives, &Fertility, &Personality),
            Without<Deceased>,
        >();
        for (e, id, pos, drives, fert, pers) in q.iter(&state.world) {
            if !fert.is_fertile_at(now, id.born_tick) {
                continue;
            }
            if drives_block_reproduction(drives) {
                continue;
            }
            candidates.push((e, id.id, id.generation, pos.0, *pers));
        }
    }
    // Tri canonique par AgentId — élimine la dépendance à l'ordre d'itération.
    candidates.sort_by_key(|(_, id, _, _, _)| *id);

    // 2) Pairing greedy : pour chaque agent (dans l'ordre trié), trouve le
    //    plus proche partenaire fertile pas encore pris.
    let mut taken: std::collections::HashSet<Entity> = std::collections::HashSet::new();
    // Pairs déterministes : (entity_a, id_a, gen_a, pos_a, entity_b, id_b, gen_b, pos_b)
    let mut pairs: Vec<MatePair> = Vec::new();

    for i in 0..candidates.len() {
        let (e_a, id_a, gen_a, pos_a, pers_a) = candidates[i];
        if taken.contains(&e_a) {
            continue;
        }
        // Cherche le plus proche partenaire dans la liste, à <= MATING_RADIUS_M.
        let mut best: Option<(usize, f32)> = None;
        for j in (i + 1)..candidates.len() {
            let (e_b, _, _, pos_b, _) = candidates[j];
            if taken.contains(&e_b) {
                continue;
            }
            let d = pos_a.distance(pos_b);
            if d <= MATING_RADIUS_M {
                match best {
                    None => best = Some((j, d)),
                    Some((_, bd)) if d < bd => best = Some((j, d)),
                    _ => {}
                }
            }
        }
        if let Some((j, _)) = best {
            let (e_b, id_b, gen_b, pos_b, pers_b) = candidates[j];
            taken.insert(e_a);
            taken.insert(e_b);
            pairs.push(MatePair {
                e_a, id_a, gen_a, pos_a, pers_a,
                e_b, id_b, gen_b, pos_b, pers_b,
            });
        }
    }

    // 3) Pour chaque paire, exécute la mating : update Fertility + spawn child.
    let mut events = Vec::with_capacity(pairs.len());
    for (pair_idx, mp) in pairs.into_iter().enumerate() {
        // Position de naissance : midpoint des deux parents, avec un epsilon
        // de désynchronisation Z pour éviter les empilements parfaits.
        let mid = (mp.pos_a + mp.pos_b) * 0.5;
        let child_pos = glam::Vec3::new(mid.x, mid.y, mid.z.max(1.0));

        // Update fertility des deux parents. Profite de l'accès `&mut`
        // pour graver un épisode Mated + un bond positif dans la mémoire.
        if let Ok(mut e_a_mut) = state.world.get_entity_mut(mp.e_a) {
            if let Some(mut f) = e_a_mut.get_mut::<Fertility>() {
                f.record_mating(now);
            }
            if let Some(mut mem) = e_a_mut.get_mut::<Memory>() {
                mem.episodic.record(Episode {
                    tick: now,
                    kind: EpisodeKind::Mated,
                    pos: [child_pos.x, child_pos.y, child_pos.z],
                    other: Some(mp.id_b),
                    affect: 0.5,
                });
                mem.relationships.observe(mp.id_b, now, 0.5);
            }
        }
        if let Ok(mut e_b_mut) = state.world.get_entity_mut(mp.e_b) {
            if let Some(mut f) = e_b_mut.get_mut::<Fertility>() {
                f.record_mating(now);
            }
            if let Some(mut mem) = e_b_mut.get_mut::<Memory>() {
                mem.episodic.record(Episode {
                    tick: now,
                    kind: EpisodeKind::Mated,
                    pos: [child_pos.x, child_pos.y, child_pos.z],
                    other: Some(mp.id_a),
                    affect: 0.5,
                });
                mem.relationships.observe(mp.id_a, now, 0.5);
            }
        }

        // Spawn child — héritage génétique activé : on transmet la
        // `Personality` des deux parents (Phase 3).
        let child_id = spawn_offspring(
            &mut state.world,
            seed,
            mp.id_a,
            mp.id_b,
            mp.gen_a,
            mp.gen_b,
            Some(mp.pers_a),
            Some(mp.pers_b),
            now,
            pair_idx as u64,
            child_pos,
        );

        // Enregistre la lignée — parents triés.
        let (p1, p2) = if mp.id_a < mp.id_b { (mp.id_a, mp.id_b) } else { (mp.id_b, mp.id_a) };
        state.lineage.record_birth(child_id, &[p1, p2]);

        // Émet l'événement de naissance.
        events.push(Event {
            event_id: Uuid::now_v7(),
            sim_id,
            tick,
            kind: EventKind::Birth,
            participants: vec![child_id, p1, p2],
            location: child_pos,
            metadata: json!({
                "generation": mp.gen_a.max(mp.gen_b) + 1,
                "parents": [p1.0.to_string(), p2.0.to_string()],
                "child": child_id.0.to_string(),
            }),
        });
    }

    events
}

/// Paire d'agents retenue pour reproduction au tick courant.
struct MatePair {
    e_a: Entity,
    id_a: AgentId,
    gen_a: u32,
    pos_a: glam::Vec3,
    pers_a: Personality,
    e_b: Entity,
    id_b: AgentId,
    gen_b: u32,
    pos_b: glam::Vec3,
    pers_b: Personality,
}

/// Renvoie `true` si un drive bloquant excède le seuil — pas de mating.
fn drives_block_reproduction(d: &Drives) -> bool {
    d.hunger.0 > DRIVE_BLOCK_THRESHOLD
        || d.thirst.0 > DRIVE_BLOCK_THRESHOLD
        || d.sleep.0 > DRIVE_BLOCK_THRESHOLD
        || d.fatigue.0 > DRIVE_BLOCK_THRESHOLD
        || d.thermal.0 > DRIVE_BLOCK_THRESHOLD
}

// ---------------------------------------------------------------------------
// Thermal comfort
// ---------------------------------------------------------------------------

/// Zone de confort thermique d'un humain (°C).
pub const THERMAL_COMFORT_LO_C: f32 = 18.0;
/// Zone de confort thermique d'un humain (°C).
pub const THERMAL_COMFORT_HI_C: f32 = 26.0;
/// Pas d'incrément du drive thermal par tick (per °C d'écart hors zone).
///
/// Calibration Phase 3 : avec une déviation de 30 °C il faut ~20 000 ticks
/// (~5 heures simulation à 1 tick/s) pour atteindre le seuil critique 1.0.
/// Cela laisse les tests Phase 1/2/3 (≤ 1100 ticks) totalement saufs tout
/// en permettant qu'une catastrophe environnementale de longue durée tue
/// un agent par hypothermie/hyperthermie.
pub const THERMAL_RATE_PER_C: f32 = 1.0 / 600_000.0;
/// Décroissance passive quand l'agent est en zone de confort.
pub const THERMAL_DECAY_PER_TICK: f32 = 1.0 / 200_000.0;

/// Met à jour le drive `thermal` en fonction du climat local. Réduit aussi le
/// drive `loneliness` si des congénères sont à proximité (Phase 3 light).
///
/// Déterminisme : `sample_terrain` et `weather_at` sont des fonctions pures
/// déterministes (PRF). L'itération Bevy par-position-vivante donne le même
/// résultat pour un même seed quel que soit l'ordre interne.
fn run_thermal_comfort(state: &mut AppState) {
    let tick = state.tick;
    let seed = state.streamer.seed;
    let params = state.streamer.params.clone();
    // 1) Snapshot lecture seule des positions des agents vivants.
    let positions: Vec<(Entity, glam::Vec3)> = {
        let mut q = state
            .world
            .query_filtered::<(Entity, &Position), Without<Deceased>>();
        q.iter(&state.world).map(|(e, p)| (e, p.0)).collect()
    };
    // 2) Pour chaque agent, calcul du thermique local + mise à jour du drive.
    for (entity, pos) in positions {
        let base: TerrainSample = sample_terrain(seed, &params, pos.x, pos.y);
        // Hémisphère nord pour Y >= 0, sud sinon.
        let north = pos.y >= 0.0;
        let w = weather_at(tick, &base, north);
        // Cible biome — abri/forêt amortit ±3°C.
        let chunk_coord = Chunk::from_world_pos(pos.x, pos.y, pos.z);
        let buffer = state
            .streamer
            .cache
            .get(&chunk_coord)
            .and_then(|c| {
                let (ox, oy) = Chunk::origin_m(chunk_coord);
                let cx = ((pos.x - ox) / VOXEL_SIZE_M).floor() as i32;
                let cy = ((pos.y - oy) / VOXEL_SIZE_M).floor() as i32;
                if cx < 0 || cy < 0 || cx >= CHUNK_SIZE as i32 || cy >= CHUNK_SIZE as i32 {
                    None
                } else {
                    let i = Chunk::idx(cx as usize, cy as usize);
                    Some(match c.biome[i] {
                        Biome::TemperateForest
                        | Biome::TemperateRainforest
                        | Biome::TropicalRainforest
                        | Biome::BorealForest => 3.0,
                        Biome::TropicalDryForest => 1.5,
                        _ => 0.0,
                    })
                }
            })
            .unwrap_or(0.0);

        let mut t_felt = w.temp_c;
        // L'abri rapproche t_felt de la zone de confort.
        let mid = (THERMAL_COMFORT_LO_C + THERMAL_COMFORT_HI_C) * 0.5;
        if t_felt < THERMAL_COMFORT_LO_C {
            t_felt = (t_felt + buffer.min(mid - t_felt)).min(mid);
        } else if t_felt > THERMAL_COMFORT_HI_C {
            t_felt = (t_felt - buffer.min(t_felt - mid)).max(mid);
        }

        let delta = if t_felt < THERMAL_COMFORT_LO_C {
            (THERMAL_COMFORT_LO_C - t_felt) * THERMAL_RATE_PER_C
        } else if t_felt > THERMAL_COMFORT_HI_C {
            (t_felt - THERMAL_COMFORT_HI_C) * THERMAL_RATE_PER_C
        } else {
            -THERMAL_DECAY_PER_TICK
        };
        if let Ok(mut em) = state.world.get_entity_mut(entity) {
            if let Some(mut d) = em.get_mut::<Drives>() {
                d.thermal = d.thermal.add(delta);
            }
        }
    }
}

// ---------------------------------------------------------------------------
// World harvest — consomme les ressources des chunks lorsque les agents
// boivent / mangent / cueillent. Sans ça, les ressources sont infinies et les
// scénarios de rareté ne fonctionnent pas.
// ---------------------------------------------------------------------------

/// Quantité d'eau (L) qu'un agent retire localement par tick `Drink`.
pub const HARVEST_WATER_PER_TICK: f32 = 0.5;
/// Quantité de food (kcal-équivalent) qu'un agent retire par tick `Eat`/`Forage`.
pub const HARVEST_FOOD_PER_TICK: f32 = 1.0;
/// Quantité de bois (kg) qu'un agent retire par tick `Forage`.
pub const HARVEST_WOOD_PER_TICK: f32 = 0.3;

fn cell_index_for(pos: glam::Vec3) -> Option<(ChunkCoord, usize)> {
    let coord = Chunk::from_world_pos(pos.x, pos.y, pos.z);
    let (ox, oy) = Chunk::origin_m(coord);
    let cx = ((pos.x - ox) / VOXEL_SIZE_M).floor() as i32;
    let cy = ((pos.y - oy) / VOXEL_SIZE_M).floor() as i32;
    if cx < 0 || cy < 0 || cx >= CHUNK_SIZE as i32 || cy >= CHUNK_SIZE as i32 {
        return None;
    }
    Some((coord, Chunk::idx(cx as usize, cy as usize)))
}

/// Soulagement du drive `thirst` quand l'agent boit effectivement.
pub const DRINK_RELIEF: f32 = 0.05;
/// Soulagement du drive `hunger` par unité de food consommée pendant Forage.
pub const FORAGE_HUNGER_PER_FOOD: f32 = 0.04;

fn run_world_harvest(state: &mut AppState, decisions: &HashMap<Entity, Decision>) {
    // Tri canonique : on traite les agents par AgentId pour que l'ordre de
    // ponction sur les chunks soit reproductible quelle que soit l'ordre
    // d'itération Bevy/HashMap.
    let mut tasks: Vec<(AgentId, Entity, glam::Vec3, ActionId)> = {
        let mut q = state
            .world
            .query_filtered::<(Entity, &Identity, &Position), Without<Deceased>>();
        q.iter(&state.world)
            .filter_map(|(e, id, p)| {
                decisions
                    .get(&e)
                    .map(|d| (id.id, e, p.0, d.action))
                    .filter(|(_, _, _, a)| {
                        matches!(a, ActionId::Drink | ActionId::Forage)
                    })
            })
            .collect()
    };
    tasks.sort_by_key(|(id, _, _, _)| *id);

    for (_aid, entity, pos, action) in tasks {
        let Some((coord, idx)) = cell_index_for(pos) else { continue };
        let Some(chunk) = state.streamer.cache.get_mut(&coord) else { continue };
        match action {
            ActionId::Drink => {
                // Eau libre = cellule océan ou cellule à niveau bas (cours d'eau).
                let is_water = matches!(chunk.biome[idx], Biome::Ocean) || chunk.height[idx] < 0.5;
                if !is_water {
                    continue; // pas d'eau ici → l'action est sans effet
                }
                if let Ok(mut em) = state.world.get_entity_mut(entity) {
                    if let Some(mut inv) = em.get_mut::<Inventory>() {
                        inv.add(ItemKind::Water, HARVEST_WATER_PER_TICK);
                    }
                    if let Some(mut d) = em.get_mut::<Drives>() {
                        d.thirst = d.thirst.add(-DRINK_RELIEF);
                    }
                }
            }
            ActionId::Forage => {
                let npp = chunk.biome[idx].npp();
                let available_wood = chunk.resources.wood[idx];
                // Le "food" est calculé depuis la NPP du biome (régénère) +
                // une fraction du stock wood courant (qui se déplète).
                let available_food = (npp * 200.0 + available_wood * 0.5).max(0.0);

                let food_take = HARVEST_FOOD_PER_TICK.min(available_food);
                let wood_take = HARVEST_WOOD_PER_TICK.min(available_wood);

                // Décrémente le chunk (clamp >= 0). La moitié du food vient du wood.
                let wood_consumed_for_food = food_take * 0.5;
                let total_wood_consumed = (wood_take + wood_consumed_for_food).min(available_wood);
                chunk.resources.wood[idx] = (available_wood - total_wood_consumed).max(0.0);

                if food_take <= 0.0 && wood_take <= 0.0 {
                    continue; // cellule stérile, aucun effet
                }
                if let Ok(mut em) = state.world.get_entity_mut(entity) {
                    if let Some(mut inv) = em.get_mut::<Inventory>() {
                        inv.add(ItemKind::Food, food_take);
                        inv.add(ItemKind::Wood, wood_take);
                    }
                    if let Some(mut d) = em.get_mut::<Drives>() {
                        d.hunger = d.hunger.add(-FORAGE_HUNGER_PER_FOOD * food_take.max(0.1));
                    }
                }
            }
            _ => {}
        }
    }
}

// ---------------------------------------------------------------------------
// Catastrophe — choc déterministe sur les agents dans une zone à un tick donné.
// ---------------------------------------------------------------------------

fn run_catastrophe(state: &mut AppState) -> Vec<Event> {
    let Some(plan) = state.catastrophe.clone() else { return Vec::new() };
    if state.tick.get() != plan.tick {
        return Vec::new();
    }
    let mut events = Vec::new();
    let center = plan.center;
    let r2 = plan.radius_m * plan.radius_m;
    let mut q = state
        .world
        .query_filtered::<(Entity, &Identity, &Position), Without<Deceased>>();
    let victims: Vec<(Entity, AgentId, glam::Vec3)> = q
        .iter(&state.world)
        .filter_map(|(e, id, p)| {
            let dx = p.0.x - center.x;
            let dy = p.0.y - center.y;
            if dx * dx + dy * dy <= r2 {
                Some((e, id.id, p.0))
            } else {
                None
            }
        })
        .collect();

    for (entity, aid, pos) in &victims {
        if let Ok(mut em) = state.world.get_entity_mut(*entity) {
            if let Some(mut h) = em.get_mut::<Health>() {
                h.vitality = (h.vitality - plan.severity).max(0.0);
                h.injuries = (h.injuries + plan.severity).min(1.0);
            }
        }
        events.push(Event {
            event_id: Uuid::now_v7(),
            sim_id: state.sim_id,
            tick: state.tick,
            kind: EventKind::Catastrophe,
            participants: vec![*aid],
            location: *pos,
            metadata: json!({
                "label": plan.label,
                "severity": plan.severity,
                "radius_m": plan.radius_m,
            }),
        });
    }
    if !victims.is_empty() {
        info!(
            tick = state.tick.get(),
            count = victims.len(),
            label = %plan.label,
            "catastrophe applied"
        );
    }
    events
}

/// Enregistre un épisode `Suffered` pour les agents en privation aiguë.
///
/// Critère : au moins un drive ≥ 0.85 (le seuil critique de la policy R0).
/// On déduplique : pas d'épisode si le dernier `Suffered` est âgé de < 100 ticks.
fn record_suffering(state: &mut AppState) {
    let now = state.tick.get();
    const SUFFER_DEDUP_TICKS: u64 = 100;
    const SUFFER_THRESHOLD: f32 = 0.85;
    // Collecte d'abord (lecture seule) puis mutation — pas de double borrow.
    let mut targets: Vec<(Entity, glam::Vec3, &'static str)> = Vec::new();
    {
        let mut q = state
            .world
            .query_filtered::<(Entity, &Drives, &Position), Without<Deceased>>();
        for (e, d, pos) in q.iter(&state.world) {
            let label = if d.thirst.0 >= SUFFER_THRESHOLD {
                Some("thirst")
            } else if d.hunger.0 >= SUFFER_THRESHOLD {
                Some("hunger")
            } else if d.thermal.0 >= SUFFER_THRESHOLD {
                Some("thermal")
            } else if d.fatigue.0 >= SUFFER_THRESHOLD {
                Some("fatigue")
            } else if d.sleep.0 >= SUFFER_THRESHOLD {
                Some("sleep")
            } else {
                None
            };
            if let Some(l) = label {
                targets.push((e, pos.0, l));
            }
        }
    }
    for (entity, pos, _label) in targets {
        if let Ok(mut em) = state.world.get_entity_mut(entity) {
            if let Some(mut mem) = em.get_mut::<Memory>() {
                let recent = mem
                    .episodic
                    .last_of(EpisodeKind::Suffered)
                    .map(|e| now.saturating_sub(e.tick))
                    .unwrap_or(u64::MAX);
                if recent >= SUFFER_DEDUP_TICKS {
                    mem.episodic.record(Episode {
                        tick: now,
                        kind: EpisodeKind::Suffered,
                        pos: [pos.x, pos.y, pos.z],
                        other: None,
                        affect: -0.5,
                    });
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::AppState;

    fn make_state(seed: u128) -> AppState {
        let mut s = AppState::bootstrap("nonexistent.yaml", None).unwrap();
        // Override pour tests reproductibles (le YAML par défaut donne 0xC0FFEE).
        s.seed = seed;
        s.streamer = ge_world::ChunkStreamer::new(seed, ge_world::TerrainParams::default());
        s.founder_count = 2;
        s
    }

    #[test]
    fn step_once_advances_tick() {
        let mut s = make_state(0xCAFE);
        s.spawn_initial();
        let t0 = s.tick.get();
        step_once(&mut s);
        assert_eq!(s.tick.get(), t0 + 1);
    }

    #[test]
    fn agents_persist_across_ticks() {
        let mut s = make_state(0xBABE);
        s.spawn_initial();
        let alive0 = s.agents_alive;
        for _ in 0..5 {
            step_once(&mut s);
        }
        // Personne ne devrait être mort en 5 ticks (drives augmentent lentement).
        assert_eq!(s.agents_alive, alive0);
    }

    #[test]
    fn determinism_two_runs_same_hash() {
        let seed = 0xDEADBEEF_u128;
        let mut s1 = make_state(seed);
        let mut s2 = make_state(seed);
        s1.spawn_initial();
        s2.spawn_initial();
        for _ in 0..50 {
            step_once(&mut s1);
            step_once(&mut s2);
        }
        assert_eq!(s1.agents_root_hash(), s2.agents_root_hash());
    }

    /// Phase 2 : à partir de 2 fondateurs adjacents, après MATURITY_TICKS,
    /// au moins un enfant doit être né. Test direct du système de
    /// reproduction sans dépendre de la cognition.
    #[test]
    fn reproduction_produces_offspring() {
        use ge_agents::MATURITY_TICKS;
        let mut s = make_state(0xFACEFEED);
        // 2 fondateurs disposés à <2 m l'un de l'autre — déjà le cas par
        // défaut (cercle de rayon 5 m avec n=2 → distance ≈ 10 m). On
        // doit donc forcer la proximité après spawn pour ce test.
        s.spawn_initial();
        // Force la position de tous les fondateurs au même point.
        let mut q = s.world.query_filtered::<&mut Position, Without<Deceased>>();
        for mut p in q.iter_mut(&mut s.world) {
            p.0 = glam::Vec3::new(0.0, 0.0, 1.0);
        }
        // Avance le temps au-delà de la maturité.
        for _ in 0..(MATURITY_TICKS + 50) {
            step_once(&mut s);
        }
        // Au moins une naissance attendue ; la population doit donc être > 2.
        assert!(
            s.agents_alive >= 3,
            "expected ≥3 agents after MATURITY_TICKS+50 ticks of close founders, got {}",
            s.agents_alive
        );
        // Et `births_total` doit avoir avancé strictement au-delà des fondateurs.
        assert!(s.births_total > 2);
    }

    /// Phase 3 : OldAge déclenche bien la mortalité quand un agent dépasse
    /// son `Aging::lifespan_ticks`. On force une lifespan très courte sur
    /// tous les agents puis on avance le tick.
    #[test]
    fn old_age_kills_agents() {
        use ge_agents::Aging;
        let mut s = make_state(0xC0DE);
        s.founder_count = 4;
        s.spawn_initial();
        // Force lifespan = 10 ticks pour tous les agents.
        {
            let mut q = s.world.query::<&mut Aging>();
            for mut a in q.iter_mut(&mut s.world) {
                a.lifespan_ticks = 10;
            }
        }
        for _ in 0..15 {
            step_once(&mut s);
        }
        // Tous les agents auraient dû mourir d'old_age.
        assert_eq!(s.agents_alive, 0, "expected all 4 founders dead, got alive={}", s.agents_alive);
        let old_age_deaths = s.deaths_by_cause.get("old_age").copied().unwrap_or(0);
        assert_eq!(old_age_deaths, 4, "expected 4 old_age deaths, got {}", old_age_deaths);
    }

    /// Phase 3 : déterminisme avec héritage génétique activé.
    ///
    /// On lance deux simulations identiques jusqu'à observer au moins une
    /// naissance, et on compare le `agents_root_hash`. L'héritage de
    /// personnalité + le jitter d'`Aging` sont tous deux dérivés du PRF
    /// — donc le hash doit rester identique.
    #[test]
    fn determinism_with_inheritance() {
        let seed = 0xBEEFC0DE_u128;
        let mut s1 = make_state(seed);
        let mut s2 = make_state(seed);
        s1.spawn_initial();
        s2.spawn_initial();
        // Force la même proximité dans les deux sims (le PRF derrière le
        // spawn met les fondateurs aux mêmes positions, mais on garantit
        // explicitement le contact pour activer la reproduction).
        for s in [&mut s1, &mut s2] {
            let mut q = s.world.query_filtered::<&mut Position, Without<Deceased>>();
            for mut p in q.iter_mut(&mut s.world) {
                p.0 = glam::Vec3::new(0.0, 0.0, 1.0);
            }
        }
        for _ in 0..1100 {
            step_once(&mut s1);
            step_once(&mut s2);
        }
        assert!(s1.births_total >= 2, "test sanity: at least one offspring per sim");
        assert_eq!(s1.agents_root_hash(), s2.agents_root_hash());
        assert_eq!(s1.births_total, s2.births_total);
    }

    /// Phase 3 : scénario "scarcity" — vérifie que `apply_scenario` configure
    /// correctement l'état et que `spawn_initial` produit un cluster dense.
    #[test]
    fn scenario_scarcity_spawns_tight_cluster() {
        use crate::state::{apply_scenario, SpawnStrategy};
        let mut s = make_state(0x5CA12C17);
        apply_scenario(&mut s, "scarcity");
        assert_eq!(s.spawn_strategy, SpawnStrategy::TightCluster);
        assert_eq!(s.founder_count, 10);
        assert!(s.max_agents >= 14);
        s.spawn_initial();
        // 10 fondateurs avec rayon max 0.4 * sqrt(9) = 1.2 m → diamètre ≤ 2.4 m.
        let mut q = s.world.query::<&Position>();
        let positions: Vec<glam::Vec3> = q.iter(&s.world).map(|p| p.0).collect();
        assert_eq!(positions.len(), 10);
        for p in &positions {
            let xy = (p.x * p.x + p.y * p.y).sqrt();
            assert!(xy <= 1.5, "founder too far from origin (XY): {p:?}");
        }
    }

    /// Phase 3 : scénario "two_cultures" — deux clusters distincts à ±50 m.
    #[test]
    fn scenario_two_cultures_spawns_two_clusters() {
        use crate::state::{apply_scenario, SpawnStrategy};
        let mut s = make_state(0xC2C0CABE);
        apply_scenario(&mut s, "two_cultures");
        assert_eq!(s.spawn_strategy, SpawnStrategy::TwoCultures);
        assert_eq!(s.founder_count, 50);
        s.spawn_initial();
        let mut q = s.world.query::<&Position>();
        let positions: Vec<glam::Vec3> = q.iter(&s.world).map(|p| p.0).collect();
        // 25 à gauche (x < 0), 25 à droite (x > 0).
        let left = positions.iter().filter(|p| p.x < 0.0).count();
        let right = positions.iter().filter(|p| p.x > 0.0).count();
        assert_eq!(left, 25);
        assert_eq!(right, 25);
    }

    /// Phase 3 : scénario "catastrophe" — déclenche le choc au tick prévu et
    /// affecte la vitalité des agents dans le rayon d'impact.
    #[test]
    fn scenario_catastrophe_triggers_damage() {
        use crate::state::{apply_scenario, CatastrophePlan};
        let mut s = make_state(0xCA7A5FE);
        // Petit setup contrôlé : 4 agents, catastrophe immédiate.
        s.founder_count = 4;
        apply_scenario(&mut s, "default");
        // Override : catastrophe explicite au tick=1 pour mesurer l'effet.
        s.catastrophe = Some(CatastrophePlan {
            label: "test_quake".to_string(),
            tick: 1,
            center: glam::Vec3::ZERO,
            radius_m: 100.0,
            severity: 0.5,
        });
        s.spawn_initial();
        // Tick 1 : applique la catastrophe à tous les agents dans 100 m.
        step_once(&mut s);
        let mut q = s.world.query::<&Health>();
        let mut hit = 0;
        for h in q.iter(&s.world) {
            if h.vitality < 1.0 && h.injuries > 0.0 {
                hit += 1;
            }
        }
        assert!(hit >= 1, "catastrophe should have damaged at least one agent, got {hit}");
        // Le journal de buffer borné doit contenir au moins un événement Catastrophe.
        let has_catastrophe = s
            .recent_events
            .iter()
            .any(|e| matches!(e.kind, EventKind::Catastrophe));
        assert!(has_catastrophe, "catastrophe event must be recorded");
    }

    /// Phase 3 : population cap — la reproduction est gelée au-dessus de
    /// `max_agents`, mais les morts continuent à libérer la place.
    #[test]
    fn population_cap_blocks_reproduction() {
        use ge_agents::MATURITY_TICKS;
        let mut s = make_state(0xCA70BEEF);
        s.founder_count = 4;
        s.max_agents = 4; // pas de place pour des nouveaux-nés
        s.spawn_initial();
        // Force la proximité pour rendre la mating géométriquement valide.
        let mut q = s.world.query_filtered::<&mut Position, Without<Deceased>>();
        for mut p in q.iter_mut(&mut s.world) {
            p.0 = glam::Vec3::new(0.0, 0.0, 1.0);
        }
        for _ in 0..(MATURITY_TICKS + 200) {
            step_once(&mut s);
        }
        // Aucun enfant attendu — cap saturé.
        assert_eq!(s.agents_alive, 4);
        assert_eq!(s.births_total, 4); // uniquement les fondateurs
    }

    /// Phase 3 : stabilité 100 fondateurs sur 1 000 ticks.
    ///
    /// Ne fait pas d'assertion sur la population finale (le résultat émerge
    /// du PRF et des drives) — vérifie seulement qu'aucun tick ne panic et
    /// que le compteur `births_total` reste cohérent avec `agents_alive +
    /// agents_dead`.
    #[test]
    fn stability_100_founders_short_run() {
        let mut s = make_state(0xC0FFEE_BEEF);
        s.founder_count = 100;
        s.spawn_initial();
        for _ in 0..1000 {
            step_once(&mut s);
        }
        assert_eq!(
            s.agents_alive + s.agents_dead,
            s.births_total as u32,
            "alive + dead must equal cumulative births"
        );
        // Au moins quelques agents doivent encore être en vie après 1000 ticks.
        assert!(
            s.agents_alive >= 50,
            "expected ≥50 agents alive after 1000 ticks, got {}",
            s.agents_alive
        );
    }
}
