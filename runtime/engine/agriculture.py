"""Genesis Engine — Phase 4 / Wave 9 : agriculture.

Agents can **plant** seeds of any catalogued edible plant clade onto a
chunk and **harvest** the resulting biomass for food calories. This
turns the passive plant_evolution biomass into an active civilisation
resource.

Mechanics
---------
* Per-culture **seed library** : the set of plant clades a culture
  knows how to cultivate. Starts empty ; agents add clades when they
  discover them (any clade present in a chunk they FORAGE in).
* Per-chunk **cultivated field state** : which clades are being
  cultivated, sown_tick, harvest_count, owning_culture.
* ``ActionKind.PLANT`` boosts the chosen clade's biomass in the chunk
  by SEED_BIOMASS_KG, registers the chunk as cultivated by the agent's
  culture, and increases the long-term growth rate (selection pressure
  for high-yield variants).
* ``ActionKind.HARVEST`` reads the cultivated clade biomass × clade
  ``edible_kcal_per_kg``, fills the agent's ``inv_food`` (capped), and
  draws down 50 % of the standing biomass (sustainable harvest).
* Agents that successfully harvest broadcast the seed clade to
  fellow culture members via the existing knowledge sharing — handled
  implicitly through the culture-level seed library.

Compatibility & determinism
---------------------------
Pure additive: no modification of existing cognition, no breaking of
Wave 3/4 immune memory, no RNG outside ``prf_rng``. Bit-identical
across runs same seed.

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — civilisation choices
shape the biosphere.
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — composable
multi-step cultivation rollouts (sow → grow → harvest → seed share).
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from engine.core import TICK_DT_S, prf_rng
from engine.plant_catalog import CLADE_BY_NAME, PlantClade
from engine.world import CHUNK_SIDE_M, world_to_chunk


# ---------------------------------------------------------------------------
# Calibration constants
# ---------------------------------------------------------------------------

# Biomass injected per PLANT action (kg of the chosen clade).
SEED_BIOMASS_KG = 40.0

# Fraction of standing biomass actually picked per HARVEST.
HARVEST_FRACTION = 0.5

# Cap on inventory after a harvest (kg of food).
HARVEST_INVENTORY_CAP_KG = 10.0

# Bonus growth rate multiplier on cultivated clades (selection pressure).
CULTIVATED_GROWTH_BONUS = 1.5

# Minimum culture knowledge required to plant : 0 = anyone can sow if
# the clade is in the catalogue. Future hook for "learned recipes" gate.
MIN_KNOWLEDGE = 0


# ---------------------------------------------------------------------------
# State containers
# ---------------------------------------------------------------------------

@dataclass
class CultivatedField:
    """Per-(chunk, clade) record. One chunk may host several fields."""
    clade: str
    owner_culture: int
    sown_tick: int
    last_harvest_tick: int = -1
    harvest_count: int = 0
    total_kcal_harvested: float = 0.0


@dataclass
class AgricultureState:
    """Attached to ``sim._ag_state``."""
    # Per-chunk → list of CultivatedField (one per clade cultivated).
    fields_per_chunk: Dict[Tuple[int, int, int], List[CultivatedField]] = field(
        default_factory=dict)
    # Per-culture → set of clade names this culture knows how to plant.
    culture_seed_library: Dict[int, Set[str]] = field(default_factory=dict)
    # Cumulative stats.
    plant_events: int = 0
    harvest_events: int = 0
    total_kcal_harvested: float = 0.0
    discoveries: int = 0


# ---------------------------------------------------------------------------
# Public API used by cognition handlers
# ---------------------------------------------------------------------------

def discover_seed(state: AgricultureState, culture_id: int,
                  clade_name: str) -> bool:
    """Add a clade to a culture's seed library.

    Returns ``True`` if it was new to this culture (counts as discovery).
    """
    if clade_name not in CLADE_BY_NAME:
        return False
    lib = state.culture_seed_library.setdefault(culture_id, set())
    if clade_name in lib:
        return False
    lib.add(clade_name)
    state.discoveries += 1
    return True


def plant_seed(sim, state: AgricultureState, row: int,
               clade_name: str) -> Tuple[bool, str]:
    """Execute a PLANT action for agent ``row``.

    Returns (success, reason). Updates plant_evolution.ChunkVegetation
    directly so the next tick of photosynthesis sees the new biomass.
    """
    if clade_name not in CLADE_BY_NAME:
        return False, "unknown_clade"
    culture_id = _agent_culture(sim, row)
    lib = state.culture_seed_library.get(culture_id, set())
    if clade_name not in lib:
        return False, "culture_unknown_seed"
    px = float(sim.agents.pos[row, 0])
    py = float(sim.agents.pos[row, 1])
    chunk_c = world_to_chunk(px, py)
    chunk = sim.streamer.cache.get(chunk_c)
    if chunk is None:
        return False, "no_chunk"
    plant_state = getattr(sim, "_plant_state", None)
    if plant_state is None:
        return False, "no_plant_evolution"
    # Inject biomass into the chunk's vegetation record.
    from engine.plant_evolution import ChunkVegetation
    veg = plant_state.chunk_vegetation.setdefault(chunk_c, ChunkVegetation())
    cur = veg.biomass_kg.get(clade_name, 0.0)
    veg.biomass_kg[clade_name] = cur + SEED_BIOMASS_KG
    veg.present_since_tick[clade_name] = sim.tick
    plant_state.available_clades.add(clade_name)
    # Bookkeeping.
    fields = state.fields_per_chunk.setdefault(chunk_c, [])
    existing = next((f for f in fields if f.clade == clade_name), None)
    if existing is None:
        fields.append(CultivatedField(
            clade=clade_name, owner_culture=culture_id, sown_tick=sim.tick))
    else:
        existing.sown_tick = sim.tick
    state.plant_events += 1
    return True, ""


def harvest(sim, state: AgricultureState, row: int) -> Tuple[bool, float, str]:
    """Execute a HARVEST action for agent ``row``.

    Picks the highest-yield edible clade present at the chunk, draws
    down ``HARVEST_FRACTION`` of its standing biomass, and credits the
    agent's ``inv_food`` (capped at ``HARVEST_INVENTORY_CAP_KG``).
    Returns (success, kcal_harvested, reason).
    """
    px = float(sim.agents.pos[row, 0])
    py = float(sim.agents.pos[row, 1])
    chunk_c = world_to_chunk(px, py)
    plant_state = getattr(sim, "_plant_state", None)
    if plant_state is None:
        return False, 0.0, "no_plant_evolution"
    veg = plant_state.chunk_vegetation.get(chunk_c)
    if veg is None or not veg.biomass_kg:
        return False, 0.0, "no_biomass"
    # Find best edible clade in this chunk.
    best_name = ""
    best_kcal = 0.0
    best_mass = 0.0
    for name, mass in veg.biomass_kg.items():
        clade = CLADE_BY_NAME.get(name)
        if clade is None or clade.edible_kcal_per_kg <= 0:
            continue
        kcal = mass * clade.edible_kcal_per_kg * HARVEST_FRACTION
        if kcal > best_kcal:
            best_name = name
            best_kcal = kcal
            best_mass = mass
    if not best_name:
        return False, 0.0, "no_edible_biomass"
    # Apply harvest.
    removed = best_mass * HARVEST_FRACTION
    veg.biomass_kg[best_name] = best_mass - removed
    clade = CLADE_BY_NAME[best_name]
    # Convert kcal back into kg-of-food using a 2500 kcal/kg average
    # (rough Atwater food density for human food).
    kg_added = min(HARVEST_INVENTORY_CAP_KG,
                   best_kcal / 2500.0)
    try:
        cur = float(sim.agents.inv_food[row])
        sim.agents.inv_food[row] = min(
            float(sim.agents.inv_capacity_kg[row]), cur + kg_added)
    except Exception:
        pass
    # Mark field stats.
    fields = state.fields_per_chunk.get(chunk_c, [])
    f = next((f for f in fields if f.clade == best_name), None)
    if f is not None:
        f.last_harvest_tick = sim.tick
        f.harvest_count += 1
        f.total_kcal_harvested += best_kcal
    state.harvest_events += 1
    state.total_kcal_harvested += best_kcal
    # Discovery : agents who harvest something edible they didn't know
    # add it to their culture's seed library.
    culture_id = _agent_culture(sim, row)
    discover_seed(state, culture_id, best_name)
    return True, best_kcal, ""


def _agent_culture(sim, row: int) -> int:
    """Best-effort culture id resolution. Falls back to 0 if absent."""
    cultures = getattr(sim.agents, "culture", None)
    if cultures is not None:
        try:
            return int(cultures[row])
        except Exception:
            return 0
    return 0


# ---------------------------------------------------------------------------
# Forage-time discovery hook : every successful FORAGE in a chunk with
# measurable biomass of an edible clade adds that clade to the agent's
# culture seed library.
# ---------------------------------------------------------------------------

def maybe_record_forage_discovery(sim, state: AgricultureState,
                                  row: int) -> int:
    """Called from the action-wrapper after FORAGE succeeds.

    Inspects the chunk's plant_evolution biomass, adds every edible
    clade present (> 5 kg) to the agent's culture seed library.
    Returns the number of new clades discovered this call.
    """
    plant_state = getattr(sim, "_plant_state", None)
    if plant_state is None:
        return 0
    px = float(sim.agents.pos[row, 0])
    py = float(sim.agents.pos[row, 1])
    chunk_c = world_to_chunk(px, py)
    veg = plant_state.chunk_vegetation.get(chunk_c)
    if veg is None:
        return 0
    culture_id = _agent_culture(sim, row)
    n_new = 0
    for name, mass in veg.biomass_kg.items():
        if mass < 5.0:
            continue
        clade = CLADE_BY_NAME.get(name)
        if clade is None or clade.edible_kcal_per_kg <= 0:
            continue
        if discover_seed(state, culture_id, name):
            n_new += 1
    return n_new


# ---------------------------------------------------------------------------
# Per-tick boost : cultivated chunks grow faster (selection pressure).
# ---------------------------------------------------------------------------

def tick_agriculture(sim, state: AgricultureState) -> None:
    """Boost growth rate of cultivated clades by adding extra biomass
    each tick proportional to ``CULTIVATED_GROWTH_BONUS``.

    Cheap : O(n_cultivated_chunks × n_fields_per_chunk).
    """
    plant_state = getattr(sim, "_plant_state", None)
    if plant_state is None:
        return
    accel = float(sim.cfg.drive_accel)
    dt_days = TICK_DT_S * accel / 86400.0
    for chunk_c, fields in state.fields_per_chunk.items():
        veg = plant_state.chunk_vegetation.get(chunk_c)
        if veg is None:
            continue
        for f in fields:
            cur = veg.biomass_kg.get(f.clade, 0.0)
            clade = CLADE_BY_NAME.get(f.clade)
            if clade is None or cur <= 0:
                continue
            bonus = (CULTIVATED_GROWTH_BONUS - 1.0) \
                * clade.growth_kg_per_day_opt * dt_days * cur
            veg.biomass_kg[f.clade] = cur + max(0.0, bonus)


# ---------------------------------------------------------------------------
# Installer + reporter
# ---------------------------------------------------------------------------

# Module-level dispatch table : id(agents) -> (sim, state). The
# apply_decision wrapper is installed once per process and routes each
# call to the matching sim's AgricultureState — same pattern as
# engine.physiology._PHYSIO_DISPATCH. Allows multiple sims to coexist.
_AG_DISPATCH: Dict[int, Tuple[object, "AgricultureState"]] = {}


def _ag_global_wrapper(agents, row, decision, streamer, tick):
    """Stacked wrapper around the previous ``apply_decision``.

    Handles ActionKind.PLANT and ActionKind.HARVEST + side-effects
    on FORAGE (seed discovery). Falls through to ``inner`` for all
    other actions.
    """
    import engine.cognition as _cog
    from engine.agent import ActionKind

    inner = getattr(_cog, "_ag_inner_apply_decision", None)
    if inner is None:
        return None
    pair = _AG_DISPATCH.get(id(agents))
    if pair is None:
        return inner(agents, row, decision, streamer, tick)
    sim, state = pair
    act = int(decision.action)

    # PLANT — bridge to plant_seed. The agent needs a target clade ;
    # we encode it in decision.target_x as a hash of the clade name
    # (cognition.decide may stash it). Fallback : pick the highest-
    # yield seed in the agent's culture library.
    if act == int(ActionKind.PLANT):
        culture = _agent_culture(sim, row)
        lib = state.culture_seed_library.get(culture, set())
        clade = ""
        # Try the agent's intent first (target_x encodes the index).
        try:
            idx = int(decision.target_x)
            ordered = sorted(lib)
            if 0 <= idx < len(ordered):
                clade = ordered[idx]
        except Exception:
            pass
        if not clade and lib:
            # Pick the highest-edible-kcal clade we know.
            best = ("", 0.0)
            for c in lib:
                cl = CLADE_BY_NAME.get(c)
                if cl is None:
                    continue
                if cl.edible_kcal_per_kg > best[1]:
                    best = (c, cl.edible_kcal_per_kg)
            clade = best[0]
        if clade:
            plant_seed(sim, state, row, clade)
        # Velocity reset like other stationary actions.
        try:
            agents.vel[row, :2] = 0.0
        except Exception:
            pass
        return []

    # HARVEST — bridge to harvest() ; result already credited inv_food.
    if act == int(ActionKind.HARVEST):
        harvest(sim, state, row)
        try:
            agents.vel[row, :2] = 0.0
        except Exception:
            pass
        return []

    # All other actions : delegate, then hook FORAGE side-effect.
    events = inner(agents, row, decision, streamer, tick)
    if act == int(ActionKind.FORAGE):
        try:
            maybe_record_forage_discovery(sim, state, row)
        except Exception:
            pass
    return events


def _patch_actions(sim, state: AgricultureState) -> None:
    """Register sim in the dispatch table and install the global
    wrapper exactly once per process."""
    import engine.cognition as _cog
    import engine.sim as _sim_mod
    _AG_DISPATCH[id(sim.agents)] = (sim, state)
    if getattr(_cog, "_ag_inner_apply_decision", None) is None:
        # First install — capture current apply_decision as inner.
        _cog._ag_inner_apply_decision = _cog.apply_decision
        _cog.apply_decision = _ag_global_wrapper
        if hasattr(_sim_mod, "apply_decision"):
            _sim_mod.apply_decision = _ag_global_wrapper


def install_agriculture(sim) -> AgricultureState:
    """Idempotent installer. Wraps sim.step with the agriculture tick
    AND wraps cognition.apply_decision so agents can actually use
    PLANT / HARVEST and so FORAGE triggers seed discovery."""
    existing: Optional[AgricultureState] = getattr(sim, "_ag_state", None)
    if existing is not None:
        return existing
    state = AgricultureState()
    sim._ag_state = state
    _patch_actions(sim, state)
    orig_step = sim.step

    def wrapped_step():
        orig_step()
        tick_agriculture(sim, state)

    sim.step = wrapped_step
    return state


def agriculture_state(sim) -> Dict[str, object]:
    """Snapshot for ``/api/agriculture_state``."""
    state: Optional[AgricultureState] = getattr(sim, "_ag_state", None)
    if state is None:
        return {}
    cultures = sorted(state.culture_seed_library.keys())
    per_culture = {}
    for cid in cultures:
        per_culture[str(cid)] = sorted(state.culture_seed_library[cid])
    # Top cultivated clades by harvest count.
    clade_hist: Dict[str, int] = {}
    for fields in state.fields_per_chunk.values():
        for f in fields:
            clade_hist[f.clade] = clade_hist.get(f.clade, 0) + 1
    top_fields = sorted(clade_hist.items(), key=lambda kv: -kv[1])[:5]
    return {
        "plant_events": state.plant_events,
        "harvest_events": state.harvest_events,
        "total_kcal_harvested": round(state.total_kcal_harvested, 1),
        "discoveries": state.discoveries,
        "n_cultivated_chunks": len(state.fields_per_chunk),
        "culture_seed_libraries": per_culture,
        "top_cultivated_clades": [{"clade": c, "field_count": n}
                                   for c, n in top_fields],
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_agriculture_state(sim, target_dir: str) -> bool:
    state: Optional[AgricultureState] = getattr(sim, "_ag_state", None)
    if state is None:
        return False
    payload = {
        "plant_events": state.plant_events,
        "harvest_events": state.harvest_events,
        "total_kcal_harvested": state.total_kcal_harvested,
        "discoveries": state.discoveries,
        "culture_seed_library": {
            str(k): sorted(v) for k, v in state.culture_seed_library.items()
        },
        "fields_per_chunk": {
            f"{c[0]}_{c[1]}_{c[2]}": [
                {"clade": f.clade,
                 "owner_culture": f.owner_culture,
                 "sown_tick": f.sown_tick,
                 "last_harvest_tick": f.last_harvest_tick,
                 "harvest_count": f.harvest_count,
                 "total_kcal_harvested": f.total_kcal_harvested}
                for f in fields
            ]
            for c, fields in state.fields_per_chunk.items()
        },
    }
    with open(os.path.join(target_dir, "agriculture.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return True


def load_agriculture_state(sim, target_dir: str) -> bool:
    path = os.path.join(target_dir, "agriculture.json")
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state = install_agriculture(sim)
    state.plant_events = int(payload.get("plant_events", 0))
    state.harvest_events = int(payload.get("harvest_events", 0))
    state.total_kcal_harvested = float(payload.get("total_kcal_harvested", 0.0))
    state.discoveries = int(payload.get("discoveries", 0))
    state.culture_seed_library = {
        int(k): set(v) for k, v in payload.get("culture_seed_library", {}).items()
    }
    state.fields_per_chunk.clear()
    for key, fields in payload.get("fields_per_chunk", {}).items():
        parts = key.split("_")
        coord = tuple(int(p) for p in parts)
        state.fields_per_chunk[coord] = [
            CultivatedField(
                clade=d["clade"],
                owner_culture=int(d["owner_culture"]),
                sown_tick=int(d["sown_tick"]),
                last_harvest_tick=int(d.get("last_harvest_tick", -1)),
                harvest_count=int(d.get("harvest_count", 0)),
                total_kcal_harvested=float(d.get("total_kcal_harvested", 0.0)))
            for d in fields
        ]
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "CultivatedField", "AgricultureState",
    "install_agriculture", "tick_agriculture", "agriculture_state",
    "plant_seed", "harvest", "discover_seed",
    "maybe_record_forage_discovery",
    "save_agriculture_state", "load_agriculture_state",
]
