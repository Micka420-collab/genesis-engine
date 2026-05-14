//! Spawning d'agents — création initiale (fondateurs) + bébés.
use crate::aging::Aging;
use crate::body::{Heading, Metabolism, Position, Velocity};
use crate::drives::Drives;
use crate::fertility::Fertility;
use crate::health::Health;
use crate::identity::Identity;
use crate::inventory::Inventory;
use crate::memory::Memory;
use crate::personality::Personality;
use bevy_ecs::prelude::{Bundle, World};
use ge_core::{AgentId, WorldSeed};
use glam::Vec3;

#[derive(Bundle)]
pub struct HumanAgentBundle {
    pub identity: Identity,
    pub position: Position,
    pub velocity: Velocity,
    pub heading: Heading,
    pub metabolism: Metabolism,
    pub drives: Drives,
    pub health: Health,
    pub inventory: Inventory,
    pub personality: Personality,
    pub fertility: Fertility,
    pub aging: Aging,
    pub memory: Memory,
}

impl HumanAgentBundle {
    pub fn founder(seed: WorldSeed, founder_index: u64, at: Vec3, born_tick: u64) -> Self {
        let id = AgentId::derive(seed, &["agent","founder"], &[founder_index]);
        let personality = Personality::sampled(seed, id);
        let aging = Aging::sampled(seed, id, &personality);
        Self {
            identity: Identity { id, born_tick, generation: 0, parents: [None, None] },
            position: Position(at),
            velocity: Velocity(Vec3::ZERO),
            heading: Heading(0.0),
            metabolism: Metabolism::human_adult(),
            drives: Drives::newborn(),
            health: Health::full(),
            inventory: Inventory::empty_human(),
            personality,
            fertility: Fertility::fresh(),
            aging,
            memory: Memory::fresh(),
        }
    }

    /// Construit un bundle enfant déterministe.
    ///
    /// Le `personality_*` doit être lu sur le World ECS par le caller (le
    /// système `run_reproduction` le fait avant d'appeler `spawn_offspring`).
    /// Si aucune personnalité n'est fournie (`None`), l'enfant est échantillonné
    /// frais sur son propre AgentId — utile uniquement pour les tests.
    pub fn offspring(
        seed: WorldSeed,
        parent_a: AgentId,
        parent_b: AgentId,
        parent_a_gen: u32,
        parent_b_gen: u32,
        personality_a: Option<Personality>,
        personality_b: Option<Personality>,
        tick: u64,
        child_index: u64,
        at: Vec3,
    ) -> Self {
        // Tri canonique des parents : `offspring(seed, A, B, ...) == offspring(seed, B, A, ...)`.
        let (p1, p2, g1, g2, pa, pb) = if parent_a < parent_b {
            (parent_a, parent_b, parent_a_gen, parent_b_gen, personality_a, personality_b)
        } else {
            (parent_b, parent_a, parent_b_gen, parent_a_gen, personality_b, personality_a)
        };
        let p1_high = u64::from_le_bytes(p1.0.as_bytes()[..8].try_into().unwrap());
        let p2_high = u64::from_le_bytes(p2.0.as_bytes()[..8].try_into().unwrap());
        let id = AgentId::derive(seed, &["agent","birth"], &[p1_high, p2_high, tick, child_index]);
        let generation = g1.max(g2).saturating_add(1);

        let personality = match (pa, pb) {
            (Some(a), Some(b)) => Personality::inherit(seed, a, b, id),
            // Fallback déterministe pour tests / chemins legacy.
            _ => Personality::sampled(seed, id),
        };
        let aging = Aging::sampled(seed, id, &personality);

        Self {
            identity: Identity { id, born_tick: tick, generation, parents: [Some(p1), Some(p2)] },
            position: Position(at),
            velocity: Velocity(Vec3::ZERO),
            heading: Heading(0.0),
            metabolism: Metabolism::human_adult(),
            drives: Drives::newborn(),
            health: Health::full(),
            inventory: Inventory::empty_human(),
            personality,
            fertility: Fertility::fresh(),
            aging,
            memory: Memory::fresh(),
        }
    }
}

pub fn spawn_founders(world: &mut World, seed: WorldSeed, positions: &[Vec3], tick: u64) -> Vec<AgentId> {
    let mut ids = Vec::with_capacity(positions.len());
    for (i, at) in positions.iter().enumerate() {
        let bundle = HumanAgentBundle::founder(seed, i as u64, *at, tick);
        ids.push(bundle.identity.id);
        world.spawn(bundle);
    }
    ids
}

/// Spawn un enfant. Si l'appelant a déjà lu les personnalités parentales, il
/// peut les fournir pour activer l'héritage génétique (`Personality::inherit`).
/// Sinon, l'enfant est échantillonné frais (back-compat, déterministe).
pub fn spawn_offspring(
    world: &mut World,
    seed: WorldSeed,
    parent_a: AgentId,
    parent_b: AgentId,
    parent_a_gen: u32,
    parent_b_gen: u32,
    personality_a: Option<Personality>,
    personality_b: Option<Personality>,
    tick: u64,
    child_index: u64,
    at: Vec3,
) -> AgentId {
    let bundle = HumanAgentBundle::offspring(
        seed,
        parent_a,
        parent_b,
        parent_a_gen,
        parent_b_gen,
        personality_a,
        personality_b,
        tick,
        child_index,
        at,
    );
    let id = bundle.identity.id;
    world.spawn(bundle);
    id
}
