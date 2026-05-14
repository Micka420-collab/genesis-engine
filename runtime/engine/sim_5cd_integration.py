"""Phase 5c+5d non-invasive integration.

This module augments an existing :class:`engine.sim.Simulation` instance with
the Phase 5c (construction + tech tree + invention + chronic fatigue) and
Phase 5d (atmosphere + climate feedback + free-will values) behaviours without
touching the original ``sim.step()`` code.

Usage
-----

>>> from engine.sim import Simulation, SimConfig
>>> from engine.sim_5cd_integration import install
>>> sim = Simulation(SimConfig(...))
>>> install(sim)            # one-liner activation
>>> sim.step()              # now runs the new sub-ticks too

The wrapper attaches three new sub-systems to ``sim``::

    sim.construction_registry   # ConstructionRegistry
    sim.atmosphere              # Atmosphere (CO2 / temp anomaly)
    sim.invention_registry      # InventionRegistry

and runs five additional sub-ticks per simulation step.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.agent import ActionKind
from engine.agent_5cd_fields import (MATERIAL_INV_FIELDS, extend_registry,
                                     inherit_5cd_fields)
from engine.construction import (ConstructionProject, ConstructionRegistry,
                                 RECIPES, Structure, StructureKind)
from engine.core import prf_rng
from engine.ecology import (Atmosphere, apply_climate_feedback,
                            combustion_co2_kg)
from engine.genome import (attach_genome, cognitive_efficiency_for_row,
                           install_genome_inheritance)
from engine.invention import InventionRegistry
from engine.materials import MaterialKind
from engine.tech_tree import (NUM_TECHS, TECHS, TechKind, can_discover,
                              discovery_probability, transmission_probability)
from engine.values import evolve_value, free_will_override
from engine.world import (Biome, CHUNK_SIDE_M, invalidate_resource_masks,
                          world_to_cell, world_to_chunk)


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

BUILDER_RADIUS_M = 3.0
CRITICAL_DRIVE = 0.85
TRANSMIT_RADIUS_M = 4.0
INVENT_TRANSMIT_PROB = 0.25
HEARTH_BURN_KG_PER_TICK = 0.05      # ~50 g of wood per tick when occupied
CHRONIC_FATIGUE_FACTOR = 1.0e-4
CHRONIC_FATIGUE_DAMAGE = 0.0008
CLIMATE_FEEDBACK_EVERY = 100        # ticks

# Foraging-yield-of-materials (kg/tick) per cell when agent FORAGES.
# Biome-dependent — set so 30-tick forage gives ~1 kg wood in forest.
FORAGE_WOOD_FOREST_KG = 0.035       # kg/tick in forest biomes
FORAGE_WOOD_OPEN_KG = 0.005         # kg/tick in open biomes
FORAGE_FIBER_KG = 0.010             # kg/tick (universal, from grasses)
FORAGE_STONE_KG = 0.020             # kg/tick (loose stones, more in mountains)
FORAGE_STONE_MOUNTAIN_KG = 0.080
FORAGE_FLINT_PROB = 0.04            # chance/tick of finding flint near stones
FORAGE_FLINT_KG = 0.20              # 200 g per find
FORAGE_CLAY_RIVER_KG = 0.025        # near water bodies


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _has_critical_drive(agents, row: int) -> bool:
    return bool(
        agents.hunger[row] >= CRITICAL_DRIVE
        or agents.thirst[row] >= CRITICAL_DRIVE
        or agents.thermal[row] >= CRITICAL_DRIVE
    )


def _agent_material_inventory(agents, row: int) -> Dict[MaterialKind, float]:
    """Return current per-material inventory for an agent (in kg)."""
    out: Dict[MaterialKind, float] = {}
    for mat, fld in MATERIAL_INV_FIELDS.items():
        arr = getattr(agents, fld, None)
        if arr is None:
            continue
        q = float(arr[row])
        if q > 0:
            out[mat] = q
    return out


def _dist2(ax: float, ay: float, bx: float, by: float) -> float:
    dx = ax - bx
    dy = ay - by
    return dx * dx + dy * dy


# ---------------------------------------------------------------------------
# Sub-tick 1 — Construction
# ---------------------------------------------------------------------------

def tick_construction(sim) -> None:
    """Advance each active ConstructionProject by builder labor.

    Builders within :data:`BUILDER_RADIUS_M` of a project who are not in a
    critical drive contribute ``skill[build]`` hours per tick × ``drive_accel``.
    On completion an event ``{"kind": "build", ...}`` is emitted.
    """
    reg: ConstructionRegistry = sim.construction_registry
    if not reg.projects:
        return
    agents = sim.agents
    n = agents.n_active
    accel = float(sim.cfg.drive_accel)
    alive = np.flatnonzero(agents.alive[:n])
    new_events: List[dict] = []
    completed: List[int] = []

    for pid, proj in list(reg.projects.items()):
        px, py, _ = proj.pos
        r2 = BUILDER_RADIUS_M * BUILDER_RADIUS_M
        for r in alive:
            r_i = int(r)
            if _dist2(float(agents.pos[r_i, 0]), float(agents.pos[r_i, 1]),
                      px, py) > r2:
                continue
            if _has_critical_drive(agents, r_i):
                continue
            build_skill = float(agents.skills[r_i, 2])  # idx 2 = build
            hours = build_skill * accel / 3600.0
            agents.labor_invested[r_i] += hours
            agents.current_project_id[r_i] = pid
            done = reg.add_labor(pid, hours, r_i)
            if done:
                struct = reg.structures.get(reg._next_structure_id - 1)
                if struct is not None:
                    struct.built_tick = sim.tick
                new_events.append({
                    "kind": "build",
                    "structure_id": struct.structure_id if struct else -1,
                    "structure_kind": int(proj.kind),
                    "builders": list(proj.builders),
                    "tick": sim.tick,
                })
                completed.append(pid)
                # Builders feel a sense of legacy.
                for b in proj.builders:
                    if 0 <= b < n and agents.alive[b]:
                        evolve_value(agents.values[b], "invented", 0.005)
                        agents.current_project_id[b] = -1
                break  # this project is done, move on

    # Reset current_project_id for agents whose project completed.
    for pid in completed:
        rows = np.flatnonzero(agents.current_project_id[:n] == pid)
        for r in rows:
            agents.current_project_id[int(r)] = -1

    if new_events:
        sim.annalist.record_tick(sim.tick, agents,
                                 births=[], deaths=[], raw_events=new_events)


# ---------------------------------------------------------------------------
# Sub-tick 2 — Atmosphere / Climate
# ---------------------------------------------------------------------------

_FOREST_BIOMES = (
    int(Biome.BOREAL_FOREST), int(Biome.TEMPERATE_FOREST),
    int(Biome.TEMPERATE_RAINFOREST), int(Biome.TROPICAL_DRY_FOREST),
    int(Biome.TROPICAL_RAINFOREST),
)


_BIOME_COUNT_CACHE: Dict[Tuple[int, int, int], Tuple[int, int]] = {}


def _chunk_biome_counts(chunk) -> Tuple[int, int]:
    """Return (forest_cells, ocean_cells) for a chunk, cached by coord.

    Chunk biomes don't change after load (L2 modifies wood/vegetation,
    not the biome class), so this is a one-time cost per chunk that pays
    back every tick.
    """
    key = chunk.coord
    cached = _BIOME_COUNT_CACHE.get(key)
    if cached is not None:
        return cached
    bm = chunk.biome
    ocean = int((bm == int(Biome.OCEAN)).sum())
    forest = 0
    for fb in _FOREST_BIOMES:
        forest += int((bm == fb).sum())
    _BIOME_COUNT_CACHE[key] = (forest, ocean)
    # Bounded cache — chunks are usually < a few thousand even on huge maps.
    if len(_BIOME_COUNT_CACHE) > 8192:
        # FIFO evict
        try:
            oldest = next(iter(_BIOME_COUNT_CACHE))
            _BIOME_COUNT_CACHE.pop(oldest, None)
        except StopIteration:
            pass
    return (forest, ocean)


def tick_atmosphere(sim) -> None:
    """Update atmospheric CO2: count sinks, burn fuels, apply climate feedback."""
    atm: Atmosphere = sim.atmosphere
    atm.begin_tick()

    forest_cells = 0
    ocean_cells = 0
    for chunk in sim.streamer.cache.values():
        f, o = _chunk_biome_counts(chunk)
        forest_cells += f
        ocean_cells += o

    # Hearth combustion → CO2. Each active hearth burns a little wood per tick.
    reg: ConstructionRegistry = sim.construction_registry
    agents = sim.agents
    n = agents.n_active
    accel = float(sim.cfg.drive_accel)
    burn_kg_total = 0.0
    for s in reg.structures.values():
        if s.kind != StructureKind.HEARTH:
            continue
        # Hearth burns proportional to drive_accel.
        fuel_kg = HEARTH_BURN_KG_PER_TICK * (accel / 100.0)
        burn_kg_total += fuel_kg
        kg_co2 = combustion_co2_kg(MaterialKind.WOOD, fuel_kg)
        atm.emit(kg_co2, source="hearth")

    # Pending hearth projects also represent intent — emit only when complete.

    atm.tick(dt_s=accel, forest_cells=forest_cells, ocean_cells=ocean_cells)

    # Periodically apply climate feedback to loaded chunks.
    if sim.tick % CLIMATE_FEEDBACK_EVERY == 0 and atm.temp_anomaly_k > 0.0:
        for chunk in sim.streamer.cache.values():
            apply_climate_feedback(chunk, atm)


# ---------------------------------------------------------------------------
# Sub-tick 3 — Invention
# ---------------------------------------------------------------------------

def tick_invention(sim, rng) -> None:
    """Curious agents may invent artifacts; nearby agents may learn them."""
    inv: InventionRegistry = sim.invention_registry
    agents = sim.agents
    n = agents.n_active
    if n == 0:
        return
    alive = np.flatnonzero(agents.alive[:n])
    accel = float(sim.cfg.drive_accel)
    new_events: List[dict] = []

    inventors: List[int] = []
    for r in alive:
        r_i = int(r)
        if float(agents.curiosity[r_i]) <= 0.5:
            continue
        if _has_critical_drive(agents, r_i):
            continue
        mat_inv = _agent_material_inventory(agents, r_i)
        if not mat_inv:
            continue
        art = inv.try_invent(
            agent_row=r_i,
            has_materials=mat_inv,
            curiosity=float(agents.curiosity[r_i]),
            intelligence=float(agents.intelligence[r_i]),
            fatigue=float(agents.fatigue[r_i]),
            tick=sim.tick,
            drive_accel=accel,
            rng=rng,
        )
        if art is not None:
            inventors.append(r_i)
            evolve_value(agents.values[r_i], "invented", 0.02)
            new_events.append({
                "kind": "invent",
                "artifact_id": art.artifact_id,
                "name": art.name,
                "inventor": r_i,
                "function": int(art.function),
                "primary_material": int(art.primary_material),
                "secondary_material": (int(art.secondary_material)
                                       if art.secondary_material is not None else -1),
                "effectiveness": float(art.effectiveness),
                "tick": sim.tick,
            })

    # Transmission to nearby agents — anyone with known artifacts can teach.
    grid = getattr(sim, "_grid", None)
    if grid is not None and grid.n_indexed > 1:
        for r in alive:
            r_i = int(r)
            known = inv.known_by_agent.get(r_i)
            if not known:
                continue
            px = float(agents.pos[r_i, 0]); py = float(agents.pos[r_i, 1])
            cands = grid.query_disk(px, py, TRANSMIT_RADIUS_M, exclude_row=r_i)
            for j in cands or []:
                if not agents.alive[j]:
                    continue
                gained = inv.transmit(r_i, int(j), rng, prob=INVENT_TRANSMIT_PROB)
                if gained > 0:
                    new_events.append({
                        "kind": "artifact_transmitted",
                        "from": r_i, "to": int(j),
                        "count": gained, "tick": sim.tick,
                    })

    if new_events:
        sim.annalist.record_tick(sim.tick, agents,
                                 births=[], deaths=[], raw_events=new_events)


# ---------------------------------------------------------------------------
# Sub-tick 4 — Tech discovery + transmission
# ---------------------------------------------------------------------------

def tick_tech_discovery(sim, rng) -> None:
    """Probabilistic tech discovery + peer transmission."""
    agents = sim.agents
    n = agents.n_active
    if n == 0:
        return
    alive = np.flatnonzero(agents.alive[:n])
    accel = float(sim.cfg.drive_accel)
    new_events: List[dict] = []

    grid = getattr(sim, "_grid", None)

    # Build a quick map: for each tech, list of alive rows that know it.
    knows = agents.known_techs  # (N, NUM_TECHS)

    # ---- Discovery ----
    for r in alive:
        r_i = int(r)
        cur = float(agents.curiosity[r_i])
        intel = float(agents.intelligence[r_i])
        if cur < 0.20 or intel < 0.20:
            continue
        for tk in range(NUM_TECHS):
            if knows[r_i, tk]:
                continue
            tech = TechKind(tk)
            if not can_discover(tech, knows[r_i]):
                continue
            # Observation bonus if a nearby agent knows it.
            observation = False
            if grid is not None and grid.n_indexed > 1:
                px = float(agents.pos[r_i, 0]); py = float(agents.pos[r_i, 1])
                cands = grid.query_disk(px, py, TRANSMIT_RADIUS_M,
                                        exclude_row=r_i)
                for j in cands or []:
                    if agents.alive[j] and knows[int(j), tk]:
                        observation = True
                        break
            p = discovery_probability(cur, intel, tech, accel, observation)
            if p > 0.0 and rng.random() < p:
                knows[r_i, tk] = True
                evolve_value(agents.values[r_i], "invented", 0.01)
                new_events.append({
                    "kind": "innovation",
                    "agent": r_i,
                    "tech": int(tk),
                    "tech_name": TECHS[tech].name,
                    "tick": sim.tick,
                })

    # ---- Transmission ----
    if grid is not None and grid.n_indexed > 1:
        for r in alive:
            r_i = int(r)
            px = float(agents.pos[r_i, 0]); py = float(agents.pos[r_i, 1])
            cands = grid.query_disk(px, py, TRANSMIT_RADIUS_M, exclude_row=r_i)
            if not cands:
                continue
            cur_i = float(agents.curiosity[r_i])
            intel_i = float(agents.intelligence[r_i])
            for j in cands:
                j_i = int(j)
                if not agents.alive[j_i]:
                    continue
                # For each tech the other knows but I don't, roll.
                for tk in range(NUM_TECHS):
                    if knows[r_i, tk] or not knows[j_i, tk]:
                        continue
                    p = transmission_probability(cur_i, intel_i, accel)
                    if rng.random() < p:
                        knows[r_i, tk] = True
                        new_events.append({
                            "kind": "tech_transmitted",
                            "from": j_i, "to": r_i,
                            "tech": int(tk),
                            "tech_name": TECHS[TechKind(tk)].name,
                            "tick": sim.tick,
                        })

    if new_events:
        sim.annalist.record_tick(sim.tick, agents,
                                 births=[], deaths=[], raw_events=new_events)


# ---------------------------------------------------------------------------
# Sub-tick 5 — Chronic fatigue
# ---------------------------------------------------------------------------

def tick_chronic_fatigue(sim) -> None:
    """Long-term wear from accumulated labor degrades vitality past a threshold."""
    agents = sim.agents
    n = agents.n_active
    if n == 0:
        return
    alive_mask = agents.alive[:n]
    li = agents.labor_invested[:n]
    cf = agents.chronic_fatigue[:n]
    np.add(cf, li * CHRONIC_FATIGUE_FACTOR, out=cf, where=alive_mask)
    np.clip(cf, 0.0, 2.0, out=cf)
    # Slow decay of recent labor pool so it doesn't run away.
    li *= 0.95
    # Past threshold: vitality decays.
    over = alive_mask & (cf > 0.8)
    if over.any():
        vit = agents.vitality[:n]
        vit[over] = np.maximum(0.0, vit[over] - CHRONIC_FATIGUE_DAMAGE)


# ---------------------------------------------------------------------------
# Sub-tick 6 — Speech (emit vocalize events for buffered SPEAK actions)
# ---------------------------------------------------------------------------

_FOREST_FORAGE = (
    int(Biome.BOREAL_FOREST), int(Biome.TEMPERATE_FOREST),
    int(Biome.TEMPERATE_RAINFOREST), int(Biome.TROPICAL_DRY_FOREST),
    int(Biome.TROPICAL_RAINFOREST),
)
_MOUNTAIN_FORAGE = (
    int(Biome.TUNDRA), int(Biome.ICE), int(Biome.COLD_DESERT),
)


def tick_speech(sim) -> None:
    """Emit vocalize raw_events for every SPEAK action this tick.

    Reads from ``sim._5cd_speech_buffer`` populated by ``patched_apply``.
    """
    buf = getattr(sim, "_5cd_speech_buffer", None)
    if not buf:
        return
    agents = sim.agents
    raw_events: List[dict] = []
    rng = sim._5cd_rng
    for row, target in buf:
        if row < 0 or row >= agents.n_active:
            continue
        if not agents.alive[row]:
            continue
        if target is None or target < 0 or target >= agents.n_active:
            continue
        if not agents.alive[target]:
            continue
        # Deterministic lexical signature: derived from speaker's culture +
        # personality fingerprint, so two utterances from the same speaker
        # in similar emotional states cluster.
        emo = 0
        if hasattr(agents, "emotions"):
            try:
                emo = int(np.argmax(agents.emotions[row]))
            except Exception:
                emo = 0
        cult = int(agents.culture_id[row]) if hasattr(agents, "culture_id") else 0
        lex_sig = (int(row) * 17 + cult * 1009 + emo * 31 + sim.tick % 7) & 0xFFFF
        raw_events.append({
            "kind": "vocalize",
            "from": int(row), "to": int(target),
            "lex_sig": lex_sig, "tick": sim.tick,
        })
        # Lightly evolve community value for the speaker.
        if hasattr(agents, "values"):
            evolve_value(agents.values[row], "community", 0.001)
    buf.clear()
    if raw_events:
        sim.annalist.record_tick(sim.tick, agents,
                                 births=[], deaths=[], raw_events=raw_events)


# ---------------------------------------------------------------------------
# Sub-tick 7 — Material foraging (wood / stone / fiber / flint / clay)
# ---------------------------------------------------------------------------

def tick_material_forage(sim) -> None:
    """Whenever an agent FORAGEd this tick, also pick up raw materials
    from the cell's biome.

    Reads ``sim._5cd_forage_buffer`` populated by ``patched_apply``.
    """
    buf = getattr(sim, "_5cd_forage_buffer", None)
    if not buf:
        return
    agents = sim.agents
    rng = sim._5cd_rng
    accel_factor = float(sim.cfg.drive_accel) / 1500.0  # ~1.0 baseline
    for row in buf:
        if row < 0 or row >= agents.n_active or not agents.alive[row]:
            continue
        px = float(agents.pos[row, 0]); py = float(agents.pos[row, 1])
        # Get biome of the cell the agent stands on.
        chunk_c = world_to_chunk(px, py)
        chunk = None
        try:
            chunk = sim.streamer.cache.get(chunk_c)
        except Exception:
            chunk = None
        if chunk is None:
            continue
        cx, cy = world_to_cell(px, py, chunk_c)
        bm = int(chunk.biome[cy, cx])
        # Wood — only in vegetated biomes.
        wood_kg = (FORAGE_WOOD_FOREST_KG if bm in _FOREST_FORAGE
                   else FORAGE_WOOD_OPEN_KG) * accel_factor
        # Also gate wood pickup on the chunk having actual `wood` resource.
        try:
            local_wood = float(chunk.wood[cy, cx])
        except Exception:
            local_wood = 1.0
        if local_wood > 0.0 and hasattr(agents, "inv_wood"):
            agents.inv_wood[row] += wood_kg
            chunk.wood[cy, cx] = max(0.0, local_wood - wood_kg)
            invalidate_resource_masks(chunk)
        # Fiber — universal, but slow to gather.
        if hasattr(agents, "inv_fiber"):
            agents.inv_fiber[row] += FORAGE_FIBER_KG * accel_factor
        # Stone — more in mountain/alpine biomes.
        stone_kg = (FORAGE_STONE_MOUNTAIN_KG if bm in _MOUNTAIN_FORAGE
                    else FORAGE_STONE_KG) * accel_factor
        try:
            local_stone = float(chunk.stone[cy, cx])
        except Exception:
            local_stone = 1.0
        if local_stone > 0.0 and hasattr(agents, "inv_stone"):
            agents.inv_stone[row] += stone_kg
            chunk.stone[cy, cx] = max(0.0, local_stone - stone_kg)
            invalidate_resource_masks(chunk)
        # Flint — probabilistic find when there's stone nearby.
        if (local_stone > 0.5 and hasattr(agents, "inv_flint")
                and rng.random() < FORAGE_FLINT_PROB * accel_factor):
            agents.inv_flint[row] += FORAGE_FLINT_KG
        # Clay — near water bodies.
        try:
            water_n = float(chunk.water[
                max(0, cy-1):cy+2, max(0, cx-1):cx+2].max())
        except Exception:
            water_n = 0.0
        if water_n > 1.0 and hasattr(agents, "inv_clay"):
            agents.inv_clay[row] += FORAGE_CLAY_RIVER_KG * accel_factor
    buf.clear()


# ---------------------------------------------------------------------------
# Decision pre-hook — free-will / values override
# ---------------------------------------------------------------------------

def value_override(sim, agents, row: int, decision) -> "object":
    """Consult ``free_will_override`` and optionally swap the decision.

    Called *before* ``apply_decision`` in the wrapped step.  Returns the
    (possibly modified) decision.
    """
    # Sprint A4 — cognitive efficiency: multiply the decision confidence by
    # the life-stage factor (infants and elders think slower / less reliably).
    if getattr(agents, "_genome_attached", False):
        try:
            eff = cognitive_efficiency_for_row(agents, row, sim)
            decision.confidence = float(decision.confidence) * eff
        except Exception:
            pass
    if not hasattr(agents, "values"):
        return decision
    drives = (float(agents.hunger[row]), float(agents.thirst[row]),
              float(agents.thermal[row]), float(agents.fatigue[row]))
    drive_strength = max(drives)
    rng = prf_rng(sim.cfg.seed, ["free_will"], [row, sim.tick])

    # Mating preemption fix: when an agent decides MATE but neither party can
    # actually conceive (drives too high, cooldown active, or simply no fertile
    # partner), the cognition layer still emits MATE every tick — starving the
    # SPEAK/SHARE/EXPLORE branches. Detect this stall and downgrade to SPEAK
    # towards the would-be mate, which at least produces a vocalize event and
    # advances social bonds.
    try:
        if int(decision.action) == int(ActionKind.MATE):
            mate = getattr(decision, "other_row", None)
            sim_ref = sim
            stall = False
            if hasattr(sim_ref, "_is_fertile"):
                try:
                    stall = not sim_ref._is_fertile(int(row))
                    if not stall and mate is not None:
                        stall = not sim_ref._is_fertile(int(mate))
                except Exception:
                    stall = False
            if stall and mate is not None and 0 <= int(mate) < agents.n_active:
                from engine.cognition import Decision as _Dec
                tx = float(agents.pos[int(mate), 0])
                ty = float(agents.pos[int(mate), 1])
                return _Dec(int(ActionKind.SPEAK), tx, ty, 0.30, int(mate))
    except Exception:
        pass

    override, reason = free_will_override(agents.values[row], drive_strength,
                                          "", rng)
    if not override:
        return decision
    # Pick an action aligned with the dominant value.
    from engine.cognition import Decision
    if reason in ("curiosity", "freedom"):
        # Wander — pick a heading off the current one.
        ang = float(agents.heading[row]) + (rng.random() - 0.5) * 1.5
        px = float(agents.pos[row, 0]); py = float(agents.pos[row, 1])
        tx = px + math.cos(ang) * 20.0
        ty = py + math.sin(ang) * 20.0
        return Decision(int(ActionKind.EXPLORE), tx, ty, 0.4)
    if reason in ("community", "family"):
        # Try to talk to the nearest agent.
        n = agents.n_active
        grid = getattr(sim, "_grid", None)
        px = float(agents.pos[row, 0]); py = float(agents.pos[row, 1])
        cand = None
        if grid is not None and grid.n_indexed > 1:
            cands = grid.query_disk(px, py, 6.0, exclude_row=row)
            for j in (cands or []):
                if agents.alive[int(j)]:
                    cand = int(j); break
        if cand is not None:
            return Decision(int(ActionKind.SPEAK),
                            float(agents.pos[cand, 0]),
                            float(agents.pos[cand, 1]),
                            0.4, cand)
        return Decision(int(ActionKind.IDLE))
    if reason == "survival":
        return Decision(int(ActionKind.IDLE))
    # legacy / dominance / fallback: idle (caller already had a plan).
    return decision


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------

def install(sim, *, world_seed: Optional[int] = None) -> None:
    """Augment ``sim`` with Phase 5c+5d behaviours.

    Idempotent — safe to call multiple times on the same instance.
    """
    if getattr(sim, "_5cd_installed", False):
        return
    sim._5cd_installed = True

    if not sim._bootstrapped:
        sim.bootstrap()

    seed = world_seed if world_seed is not None else sim.cfg.seed
    extend_registry(sim.agents, seed)
    # Sprint A4: 256-d genome + 8 life stages.
    attach_genome(sim.agents, seed)
    install_genome_inheritance(sim, world_seed=seed)

    sim.construction_registry = ConstructionRegistry()
    sim.invention_registry = InventionRegistry()
    sim.atmosphere = Atmosphere(
        bounds_km2=float(sim.cfg.bounds_km[0] * sim.cfg.bounds_km[1]))

    sim._5cd_rng = prf_rng(seed, ["sim_5cd"], [0])
    sim._5cd_speech_buffer: List[Tuple[int, int]] = []
    sim._5cd_forage_buffer: List[int] = []

    original_step = sim.step

    def wrapped_step():
        # Per-tick buffers are cleared at start so even if the base sim
        # raises, we don't carry stale entries across ticks.
        sim._5cd_speech_buffer.clear()
        sim._5cd_forage_buffer.clear()
        stats = original_step()
        # After the base step has decided actions and applied them, run the
        # 5cd sub-ticks. The value_override pre-hook is applied INSIDE the
        # base step path via a monkey-patch on `apply_decision` — keep it
        # simple: we run the new behaviour as post-ticks here, and use a
        # standalone decision-rewrite below for value overrides.
        rng = sim._5cd_rng
        try:
            tick_speech(sim)
            tick_material_forage(sim)
            tick_construction(sim)
            tick_atmosphere(sim)
            tick_invention(sim, rng)
            tick_tech_discovery(sim, rng)
            tick_chronic_fatigue(sim)
        except Exception:
            # Never let a 5cd glitch crash the base sim — re-raise during
            # debugging by setting sim._5cd_strict = True.
            if getattr(sim, "_5cd_strict", False):
                raise
        return stats

    sim.step = wrapped_step

    # Monkey-patch apply_decision so value overrides are evaluated before
    # the base action is applied. We wrap engine.cognition.apply_decision
    # via a per-sim hook stored on the sim instance.
    from engine import cognition as _cog
    original_apply = _cog.apply_decision

    def patched_apply(agents, row, decision, streamer, tick):
        # Only override when this is the registered sim instance.
        events = []
        if agents is sim.agents:
            decision = value_override(sim, agents, int(row), decision)
            # Capture SPEAK / FORAGE for post-tick emission.
            try:
                act = int(decision.action)
                if act == int(ActionKind.SPEAK):
                    tgt = getattr(decision, "other_row", None)
                    if tgt is None:
                        tgt = -1
                    sim._5cd_speech_buffer.append((int(row), int(tgt)))
                elif act == int(ActionKind.FORAGE):
                    sim._5cd_forage_buffer.append(int(row))
                elif act == int(ActionKind.MATE):
                    # Emit mate_attempt event so Simulation._resolve_matings
                    # can pick it up. The base cognition.apply_decision never
                    # surfaces MATE intents — without this, no births happen.
                    other = getattr(decision, "other_row", None)
                    if (other is not None and 0 <= int(other) < agents.n_active
                            and agents.alive[int(other)]):
                        events.append({"kind": "mate_attempt",
                                       "a": int(row), "b": int(other)})
            except Exception:
                pass
        base_events = original_apply(agents, row, decision, streamer, tick)
        if base_events:
            events.extend(base_events)
        return events

    # Only patch once globally.
    if not getattr(_cog, "_5cd_patched", False):
        _cog._5cd_original_apply_decision = original_apply
        _cog.apply_decision = patched_apply
        _cog._5cd_patched = True

    # CRITICAL: ``engine.sim`` does ``from engine.cognition import apply_decision``
    # at import time, so it holds its own local binding that the monkey-patch on
    # ``cognition.apply_decision`` does NOT reach. Patch the local binding too.
    try:
        from engine import sim as _sim_mod
        if getattr(_sim_mod, "apply_decision", None) is not patched_apply:
            _sim_mod._5cd_original_apply_decision = getattr(
                _sim_mod, "apply_decision", None)
            _sim_mod.apply_decision = patched_apply
    except Exception:
        pass

    # Loosen fertility gate (P-NEW.4). The base `_is_fertile` refuses any
    # agent whose hunger or thirst is above 0.7; at drive_accel=1500 that
    # threshold is reached in ~120 ticks and never recovers without DRINK.
    # Net effect: 0 births in 5k ticks. We swap to a more permissive
    # threshold (0.85, just under CRITICAL) so mature agents in normal
    # drive ranges can still mate, while critical-drive agents still can't.
    _install_fertility_patch(sim)

    # P-NEW.16 — fix the 100%-exhaustion mortality observed on 5K Léman.
    # The original SLEEP_RELIEF (0.40) is calibrated for unaccelerated time;
    # at drive_accel=1500, fatigue accumulates at ~0.017/tick while a single
    # SLEEP tick relieves 0.28 fatigue and 0.40 sleep. With only ~5% of
    # ticks spent sleeping (mating + foraging crowd it out), net drift is
    # slightly positive and saturation arrives over ~900 ticks. We bump
    # SLEEP_RELIEF to 0.60 (40% more) AND halve FATIGUE_PER_S so the agent
    # has wider headroom before fatigue saturates.
    try:
        from engine import cognition as _cog_mod
        from engine import sim as _sim_mod
        _cog_mod.SLEEP_RELIEF = 0.60
        _sim_mod.FATIGUE_PER_S = 1.0 / (2.0 * 86_400.0)  # 2 sim-days to fatigue
    except Exception:
        pass

    # ALSO seed multiple HEARTH projects (P-NEW.7) — one per culture cluster
    # — so labor accumulates fast enough to produce a completed structure
    # in a 5k-10k tick run.
    _seed_initial_project(sim)


def _install_fertility_patch(sim) -> None:
    """Wrap ``sim._is_fertile`` to use a looser drive threshold (0.85).

    Idempotent. The original method is kept on ``sim._is_fertile_original``.
    """
    if getattr(sim, "_fertility_patched", False):
        return
    sim._fertility_patched = True
    from engine.cognition import MATURITY_TICKS, COOLDOWN_TICKS

    original = sim._is_fertile
    sim._is_fertile_original = original
    accel = max(1, int(sim.cfg.drive_accel / 10))

    def patched(row: int) -> bool:
        agents = sim.agents
        if sim.tick - int(agents.born_tick[row]) < (MATURITY_TICKS // accel):
            return False
        last = int(agents.last_mating_tick[row])
        if last >= 0 and (sim.tick - last) < (COOLDOWN_TICKS // accel):
            return False
        # Looser: only reject when drives are truly critical, not just elevated.
        if float(agents.hunger[row]) > 0.85 or float(agents.thirst[row]) > 0.85:
            return False
        return True

    sim._is_fertile = patched


def _seed_initial_project(sim) -> None:
    """Seed one HEARTH per founder cluster (per culture).

    With more than one seeded project, labor pools concentrate around
    several anchor points instead of a single one, making it likely that
    at least one project completes within a typical 5k-10k tick run.
    """
    if sim.construction_registry.projects or sim.construction_registry.structures:
        return
    agents = sim.agents
    n = agents.n_active
    if n == 0:
        return
    alive = np.flatnonzero(agents.alive[:n])
    if alive.size == 0:
        return
    # Group founders by culture_id to pick one initiator per group.
    seen_cultures: Dict[int, int] = {}
    for r in alive:
        r_i = int(r)
        try:
            cult = int(agents.relations[r_i].culture_id)
        except Exception:
            cult = 0
        if cult not in seen_cultures:
            seen_cultures[cult] = r_i
    # If somehow there's no culture info, fall back to one project at idx 0.
    if not seen_cultures:
        seen_cultures = {0: int(alive[0])}
    for cult, initiator in seen_cultures.items():
        pos = (float(agents.pos[initiator, 0]),
               float(agents.pos[initiator, 1]),
               float(agents.pos[initiator, 2]))
        proj = sim.construction_registry.start_project(
            StructureKind.HEARTH, pos, sim.tick, initiator)
        # Pre-deliver all materials so labor is what gates completion.
        for mat, qty in dict(RECIPES[StructureKind.HEARTH].materials).items():
            sim.construction_registry.deliver_material(proj.project_id, mat, qty)
        agents.current_project_id[initiator] = proj.project_id
