"""Agent data model (Phase 4 — lexicon vector added)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import derive_agent_id, prf_rng


class DeathCause(IntEnum):
    NONE = 0
    STARVATION = 1
    DEHYDRATION = 2
    COLD = 3
    HEAT = 4
    EXHAUSTION = 5
    OLD_AGE = 6
    VIOLENCE = 7
    DISEASE = 8
    CATASTROPHE = 9


class DriveKind(IntEnum):
    HUNGER = 0
    THIRST = 1
    SLEEP = 2
    FATIGUE = 3
    THERMAL = 4
    PAIN = 5
    STRESS = 6
    LONELINESS = 7


class ActionKind(IntEnum):
    IDLE = 0
    WALK_TO = 1
    DRINK = 2
    EAT = 3
    SLEEP = 4
    FORAGE = 5
    SEEK_SHELTER = 6
    MATE = 7
    SPEAK = 8
    SHARE = 9
    FIGHT = 10
    BUILD = 11
    FLEE = 12
    EXPLORE = 13
    HUNT = 14
    # Phase 4 — Émergence civilisationnelle.
    PLANT = 15       # sow a known seed clade onto the current chunk
    HARVEST = 16     # gather standing biomass from a cultivated chunk
    # Wave 10 — Mining.
    MINE = 17        # extract ore/rock from the chunk's strata column
    # Wave 10c — Metallurgy.
    SMELT = 18       # reduce ore with fuel in a furnace → pure metal
    # D12 wire (2026-06-24) — stone-age tool-stone foraging (consumes C2).
    KNAP = 19        # debit a knappable outcrop into raw stone + a cutting edge
    # D12 wire (2026-06-25) — frost-shattered surface clast gathering (consumes C14).
    GATHER = 20      # pick up a frost-detached surface clast (no percussion)
    # D12 wire (2026-06-27) — cold-grind the rusty iron-hat earth into pigment (consumes C18).
    GRIND = 21       # triturate weathered gossan oxide earth → ochre pigment powder
    # D12 wire (2026-06-28) — leave a pigment mark on a carbonate wall (consumes C20).
    MARK = 22        # paint held pigment onto a paintable rock wall — the world decides if it lasts
    # D12 wire (2026-06-28) — strike a fire at a firestone site (consumes C7, the VOÛTE).
    IGNITE = 23      # kindle a fire (pyrite percussion / dry-tinder friction) — the world decides if a spark takes
    # D12 wire (2026-06-29) — heat-treat a silica stone in the fire (consumes C8, fire's first use).
    TEMPER = 24      # roast a knappable silica nodule → a superior cutting edge — the world decides the gain
    # D12 wire (2026-06-29) — dig workable clay from a clay exposure (consumes C5, non-fire precursor).
    DIG = 25         # gather plastic clay from a surface bank — the world decides if it is workable / ceramic-grade
    # D12 wire (2026-06-29) — fire shaped clay in a fire into pottery (consumes C9 = C5 clay × C7 fire).
    FIRE_CLAY = 26   # bake carried clay in the fire → irreversible ceramic — the world decides if it fires sound
    # D12 wire (2026-06-29) — quarry carbonate building/lime stone (consumes C6, non-fire precursor to lime).
    QUARRY = 27      # hew a block of surface limestone — the world decides its purity (mortar-grade?) / soundness
    # D12 wire (2026-06-29) — burn carried limestone in a fire into quicklime (consumes C10 = C6 × C7).
    CALCINE = 28     # decarbonate limestone in the fire → caustic quicklime — the world decides if it burns well
    # D12 wire (2026-06-29) — rake solar salt from an arid brine pan (consumes C15, non-fire / non-thermal).
    RAKE = 29        # gather the dried salt crust from a solar pan — the world decides if it is harvestable
    # D12 wire (2026-06-29) — glean combustible fuel from a dark exposure (consumes C4, non-fire precursor).
    GLEAN = 30       # collect peat / coal / oil-shale from a fuel exposure — the world decides if it burns now


@dataclass
class EpisodicMemory:
    short_term: List[dict] = field(default_factory=list)
    long_term: List[dict] = field(default_factory=list)
    known_water_locations: List[Tuple[float, float]] = field(default_factory=list)
    known_food_locations: List[Tuple[float, float]] = field(default_factory=list)
    known_shelters: List[Tuple[float, float]] = field(default_factory=list)
    known_toolstone_locations: List[Tuple[float, float]] = field(default_factory=list)
    known_frost_clast_locations: List[Tuple[float, float]] = field(default_factory=list)
    known_ochre_locations: List[Tuple[float, float]] = field(default_factory=list)
    known_canvas_locations: List[Tuple[float, float]] = field(default_factory=list)
    known_firesite_locations: List[Tuple[float, float]] = field(default_factory=list)
    # Colour of the pigment last ground (C18) — the hue the agent now CARRIES, so a later
    # MARK (C20) knows what colour it is painting with (and whether it shows on the wall).
    last_pigment_hue: Optional[Tuple[int, int, int]] = None
    # Fire (C7): the keystone skill, learned by acting. ``has_made_fire`` is the
    # discovery flag (the agent now knows a spark can be struck here-and-such);
    # ``last_fire_method`` records HOW (PERCUSSION / FRICTION) — emergent, never told.
    has_made_fire: bool = False
    last_fire_method: Optional[str] = None
    # Heat treatment (C8): fire's first use ON a material. ``has_tempered_stone``
    # is the discovery flag (the agent has learned fire+silex → a keener edge);
    # ``last_temper_gain`` records the last knap-quality premium the heat yielded
    # — emergent, never told. ``known_temper_locations`` are remembered sites.
    known_temper_locations: List[Tuple[float, float]] = field(default_factory=list)
    has_tempered_stone: bool = False
    last_temper_gain: Optional[float] = None
    # Clay (C5): the matter of the future pot, learned by acting. ``known_clay_locations``
    # are remembered banks; ``last_clay_class`` records WHICH clay last dug (SHALE_CLAY /
    # PLASTIC_CLAY) — emergent, never told (the agent learns plastic→holds-shape by digging).
    known_clay_locations: List[Tuple[float, float]] = field(default_factory=list)
    last_clay_class: Optional[str] = None
    # Ceramic (C9): the founding neolithic transformation, learned by acting. ``has_fired_pottery``
    # is the discovery flag (the agent now knows soft clay + fire → an irreversible vessel);
    # ``last_ware_quality`` records the last fired vessel's grade; ``known_kiln_locations`` the sites.
    known_kiln_locations: List[Tuple[float, float]] = field(default_factory=list)
    has_fired_pottery: bool = False
    last_ware_quality: Optional[float] = None
    # Limestone (C6): the binder/builder stone, learned by acting. ``known_limestone_locations``
    # are remembered carbonate banks; ``last_lime_class`` records WHICH carbonate last quarried —
    # emergent (the agent learns white-stone→lime by burning it later, never told).
    known_limestone_locations: List[Tuple[float, float]] = field(default_factory=list)
    last_lime_class: Optional[str] = None
    # Quicklime (C10): the oldest chemical industry, learned by acting. ``has_burnt_lime`` is the
    # discovery flag (the agent now knows white-stone + big fire → a caustic binder); ``last_lime_yield``
    # records the last burn's grade — emergent, never told. ``known_limekiln_locations`` the sites.
    known_limekiln_locations: List[Tuple[float, float]] = field(default_factory=list)
    has_burnt_lime: bool = False
    last_lime_yield: Optional[float] = None
    # Salt (C15): « white gold », the preservative that structures neolithic trade — learned by
    # acting. ``known_saltpan_locations`` are remembered pans; ``last_salt_zone`` records the aridity
    # zone last raked (hyperarid / arid / semiarid) — emergent, never told.
    known_saltpan_locations: List[Tuple[float, float]] = field(default_factory=list)
    last_salt_zone: Optional[str] = None
    # Fuel (C4): durable combustible (peat / coal / oil-shale), learned by acting. ``known_fuel_locations``
    # are remembered exposures; ``last_fuel_class`` records WHICH fuel last gleaned (PEAT / OIL_SHALE /
    # COAL) — emergent (the agent learns dark-rock→long-fire by burning it, never told).
    known_fuel_locations: List[Tuple[float, float]] = field(default_factory=list)
    last_fuel_class: Optional[str] = None
    capacity_short: int = 32
    capacity_long: int = 256


@dataclass
class SocialRelations:
    affinity: Dict[int, float] = field(default_factory=dict)
    parents: List[int] = field(default_factory=list)
    children: List[int] = field(default_factory=list)
    group_id: Optional[int] = None
    culture_id: int = 0

    def update_affinity(self, other_row: int, delta: float) -> None:
        cur = self.affinity.get(other_row, 0.0)
        self.affinity[other_row] = max(-1.0, min(1.0, cur + delta))


@dataclass
class AgentRegistry:
    capacity: int

    uuid: List[uuid.UUID] = field(default_factory=list)
    generation: np.ndarray = field(default=None)
    born_tick: np.ndarray = field(default=None)
    parents: List[Tuple[Optional[int], Optional[int]]] = field(default_factory=list)

    pos: np.ndarray = field(default=None)
    vel: np.ndarray = field(default=None)
    heading: np.ndarray = field(default=None)
    mass_kg: np.ndarray = field(default=None)
    walk_max_ms: np.ndarray = field(default=None)
    run_max_ms: np.ndarray = field(default=None)
    lifespan_ticks: np.ndarray = field(default=None)

    hunger: np.ndarray = field(default=None)
    thirst: np.ndarray = field(default=None)
    sleep: np.ndarray = field(default=None)
    fatigue: np.ndarray = field(default=None)
    thermal: np.ndarray = field(default=None)
    pain: np.ndarray = field(default=None)
    stress: np.ndarray = field(default=None)
    loneliness: np.ndarray = field(default=None)

    vitality: np.ndarray = field(default=None)
    injuries: np.ndarray = field(default=None)
    pathogen_load: np.ndarray = field(default=None)

    openness: np.ndarray = field(default=None)
    conscientiousness: np.ndarray = field(default=None)
    extraversion: np.ndarray = field(default=None)
    agreeableness: np.ndarray = field(default=None)
    neuroticism: np.ndarray = field(default=None)
    ambition: np.ndarray = field(default=None)
    risk_tolerance: np.ndarray = field(default=None)
    aggression: np.ndarray = field(default=None)
    curiosity: np.ndarray = field(default=None)
    empathy: np.ndarray = field(default=None)
    intelligence: np.ndarray = field(default=None)

    last_mating_tick: np.ndarray = field(default=None)
    offspring_count: np.ndarray = field(default=None)

    inv_water: np.ndarray = field(default=None)
    inv_food: np.ndarray = field(default=None)
    inv_wood: np.ndarray = field(default=None)
    inv_stone: np.ndarray = field(default=None)
    inv_metal: np.ndarray = field(default=None)
    inv_tools: np.ndarray = field(default=None)
    inv_pigment: np.ndarray = field(default=None)
    inv_clay: np.ndarray = field(default=None)
    inv_ceramic: np.ndarray = field(default=None)
    inv_limestone: np.ndarray = field(default=None)
    inv_lime: np.ndarray = field(default=None)
    inv_salt: np.ndarray = field(default=None)
    inv_fuel: np.ndarray = field(default=None)
    inv_capacity_kg: np.ndarray = field(default=None)

    action: np.ndarray = field(default=None)
    target_x: np.ndarray = field(default=None)
    target_y: np.ndarray = field(default=None)
    intent_expires: np.ndarray = field(default=None)

    alive: np.ndarray = field(default=None)
    death_cause: np.ndarray = field(default=None)
    death_tick: np.ndarray = field(default=None)

    lexicon: np.ndarray = field(default=None)  # Phase 4

    memory: List[EpisodicMemory] = field(default_factory=list)
    relations: List[SocialRelations] = field(default_factory=list)

    n_active: int = 0

    def __post_init__(self):
        N = self.capacity
        self.generation = np.zeros(N, dtype=np.int32)
        self.born_tick = np.zeros(N, dtype=np.int64)
        self.parents = [(None, None)] * N
        self.uuid = [uuid.UUID(int=0)] * N
        self.pos = np.zeros((N, 3), dtype=np.float32)
        self.vel = np.zeros((N, 3), dtype=np.float32)
        self.heading = np.zeros(N, dtype=np.float32)
        self.mass_kg = np.full(N, 70.0, dtype=np.float32)
        self.walk_max_ms = np.full(N, 1.4, dtype=np.float32)
        self.run_max_ms = np.full(N, 6.5, dtype=np.float32)
        self.lifespan_ticks = np.full(N, 80 * 365 * 86400, dtype=np.int64)
        for name in ("hunger","thirst","sleep","fatigue","thermal","pain","stress","loneliness"):
            setattr(self, name, np.zeros(N, dtype=np.float32))
        self.vitality = np.ones(N, dtype=np.float32)
        self.injuries = np.zeros(N, dtype=np.float32)
        self.pathogen_load = np.zeros(N, dtype=np.float32)
        for name in ("openness","conscientiousness","extraversion","agreeableness",
                     "neuroticism","ambition","risk_tolerance","aggression",
                     "curiosity","empathy","intelligence"):
            setattr(self, name, np.full(N, 0.5, dtype=np.float32))
        self.last_mating_tick = np.full(N, -1, dtype=np.int64)
        self.offspring_count = np.zeros(N, dtype=np.int32)
        for name in ("inv_water","inv_food","inv_wood","inv_stone","inv_metal","inv_tools","inv_pigment","inv_clay","inv_ceramic","inv_limestone","inv_lime","inv_salt","inv_fuel"):
            setattr(self, name, np.zeros(N, dtype=np.float32))
        self.inv_capacity_kg = np.full(N, 20.0, dtype=np.float32)
        self.action = np.zeros(N, dtype=np.int32)
        self.target_x = np.zeros(N, dtype=np.float32)
        self.target_y = np.zeros(N, dtype=np.float32)
        self.intent_expires = np.zeros(N, dtype=np.int64)
        self.alive = np.zeros(N, dtype=bool)
        self.death_cause = np.zeros(N, dtype=np.int32)
        self.death_tick = np.full(N, -1, dtype=np.int64)
        self.lexicon = np.full((N, 16), 0.5, dtype=np.float32)
        self.memory = [EpisodicMemory() for _ in range(N)]
        self.relations = [SocialRelations() for _ in range(N)]

    def alive_indices(self):
        return np.flatnonzero(self.alive[:self.n_active])

    def spawn_founder(self, world_seed, founder_idx, pos_xyz, born_tick, culture_id=0):
        if self.n_active >= self.capacity:
            raise RuntimeError(f"AgentRegistry full (cap={self.capacity})")
        row = self.n_active
        self.n_active += 1
        self.uuid[row] = derive_agent_id(world_seed, ["agent","founder"], [founder_idx])
        self.generation[row] = 0
        self.born_tick[row] = born_tick
        self.parents[row] = (None, None)
        self.pos[row] = pos_xyz
        self.vel[row] = 0.0
        self.heading[row] = 0.0
        rng = prf_rng(world_seed, ["agent","personality"], [founder_idx])
        traits = rng.random(11, dtype=np.float32)
        (self.openness[row], self.conscientiousness[row], self.extraversion[row],
         self.agreeableness[row], self.neuroticism[row], self.ambition[row],
         self.risk_tolerance[row], self.aggression[row], self.curiosity[row],
         self.empathy[row], self.intelligence[row]) = traits.tolist()
        self.hunger[row] = 0.30
        self.thirst[row] = 0.30
        self.sleep[row] = 0.10
        self.fatigue[row] = 0.10
        self.vitality[row] = 1.0
        self.injuries[row] = 0.0
        self.alive[row] = True
        lex_rng = prf_rng(world_seed, ["agent","lexicon","founder"], [culture_id, founder_idx])
        culture_base = prf_rng(world_seed, ["agent","lexicon","culture"], [culture_id]).random(16, dtype=np.float32)
        self.lexicon[row] = np.clip(
            culture_base + lex_rng.normal(0.0, 0.04, size=16).astype(np.float32), 0.0, 1.0)
        self.memory[row] = EpisodicMemory()
        rel = SocialRelations()
        rel.culture_id = culture_id
        self.relations[row] = rel
        return row

    def spawn_offspring(self, world_seed, parent_a, parent_b, tick, child_idx, pos_xyz):
        if self.n_active >= self.capacity:
            return -1
        row = self.n_active
        self.n_active += 1
        pa, pb = ((parent_a, parent_b) if self.uuid[parent_a].int < self.uuid[parent_b].int
                  else (parent_b, parent_a))
        pa_high = int.from_bytes(self.uuid[pa].bytes[:8], "little")
        pb_high = int.from_bytes(self.uuid[pb].bytes[:8], "little")
        self.uuid[row] = derive_agent_id(world_seed, ["agent","birth"], [pa_high, pb_high, tick, child_idx])
        self.generation[row] = int(max(self.generation[pa], self.generation[pb])) + 1
        self.born_tick[row] = tick
        self.parents[row] = (pa, pb)
        self.pos[row] = pos_xyz
        self.vel[row] = 0.0
        rng = prf_rng(world_seed, ["agent","inherit"], [pa_high, pb_high, tick, child_idx])
        for trait in ("openness","conscientiousness","extraversion","agreeableness",
                      "neuroticism","ambition","risk_tolerance","aggression",
                      "curiosity","empathy","intelligence"):
            arr = getattr(self, trait)
            mid = (float(arr[pa]) + float(arr[pb])) * 0.5
            mutation = float(rng.normal(0.0, 0.05))
            arr[row] = float(np.clip(mid + mutation, 0.0, 1.0))
        self.hunger[row] = 0.30
        self.thirst[row] = 0.30
        self.alive[row] = True
        self.vitality[row] = 1.0
        lex_mid = (self.lexicon[pa] + self.lexicon[pb]) * 0.5
        lex_mut = rng.normal(0.0, 0.02, size=16).astype(np.float32)
        self.lexicon[row] = np.clip(lex_mid + lex_mut, 0.0, 1.0)
        self.memory[row] = EpisodicMemory()
        rel = SocialRelations()
        rel.parents = [pa, pb]
        rel.culture_id = self.relations[pa].culture_id
        self.relations[row] = rel
        self.relations[pa].children.append(row)
        self.relations[pb].children.append(row)
        self.offspring_count[pa] += 1
        self.offspring_count[pb] += 1
        return row

    def kill(self, row, cause, tick):
        if self.alive[row]:
            self.alive[row] = False
            self.death_cause[row] = int(cause)
            self.death_tick[row] = tick
            self.vel[row] = 0.0
