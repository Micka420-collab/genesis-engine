"""Genesis Engine — Wave 10d realistic construction.

Build mines, houses, forges, temples using the **real minerals**
extracted by :mod:`engine.geology` and the **pure elements** smelted
by :mod:`engine.metallurgy`. Each built structure is a
:class:`MaterialInstance` tracked by :mod:`engine.material_aging` so
it decays realistically over centuries (a wooden hut rots in 10 yr,
a limestone temple weathers over millennia, a granite mineshaft
lasts as long as the rock).

What's NEW vs engine.construction
----------------------------------
The legacy ``engine.construction`` module uses the abstract
``MaterialKind`` enum (STONE / WOOD / FIBER / CLAY / METAL). Recipes
say "20 kg STONE" without specifying *which* stone.

This module operates on the **named-mineral level** : a recipe asks
explicitly for ``"limestone": 200`` or ``"Fe": 5``. The bridge to
real production is :

  - Mineral names (limestone, granite, marble, …) → drawn from
    ``geology.chunk_geology[coord].extracted_by_mineral`` *and*
    the global aggregator ``geology._geology_state.cumulative_extracted``.
  - Pure elements (Fe, Cu, Sn, Au, …) → drawn from
    ``metallurgy._metal_state.agent_pure_elements[row]``.
  - Wood (organic, no mineralogical equivalent) → falls back to
    ``sim.agents.inv_wood[row]``.

Recipes
-------
Six representative buildings, calibrated against historical material
costs (Roman / Greek / Bronze Age construction figures) :

* ``stone_hut``       — small Neolithic dwelling (limestone + granite + wood).
* ``stone_house``     — Iron-Age 1-room house (limestone + granite + Fe nails).
* ``brick_kiln``      — chalcolithic firing oven for ceramics.
* ``mineshaft``       — extraction adit, granite-reinforced.
* ``forge``           — bronze/iron-working hearth.
* ``marble_temple``   — high-status structure (marble + limestone + Au).

Each recipe binds the resulting :class:`RealStructure` to a
:class:`MaterialInstance` in material_aging so its ``integrity``
decays at the rate of its **dominant material** (e.g. wooden hut →
``wood`` decay 18 %/yr ; stone house → ``limestone`` 0.08 %/yr).

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — buildings depend on the
geology + metallurgy stack and feed back into agent shelter.
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — composable
multi-step rollouts (build → age → maintain → ruin).
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from engine.core import prf_rng
from engine.mineral_catalog import MINERAL_BY_NAME


# ---------------------------------------------------------------------------
# Recipe definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RealBuildRecipe:
    """Real-materials recipe. Materials are keyed by real names."""
    name: str
    common_name: str
    materials_kg: Dict[str, float]      # mineral_name OR element_symbol → kg
    labor_h: float                       # person-hours
    min_builders: int = 1
    # Material used to track decay via material_aging — picked from
    # the dominant durable mineral in the recipe.
    aging_material_name: str = "stone_granite"
    # Default exposure when bound to material_aging.
    exposure_mode: str = "humid_air"
    # Functional effects when standing :
    thermal_relief: float = 0.0          # per-tick decrement on thermal drive
    capacity_agents: int = 0             # how many can shelter inside
    radius_m: float = 6.0


# Real-world calibration : a small Iron-Age stone house consumed
# roughly 8 tonnes of limestone in masonry + ~2 m³ wood roof beams.
# Numbers below are scaled down to "single-builder agent" units.
REAL_RECIPES: Dict[str, RealBuildRecipe] = {
    "stone_hut": RealBuildRecipe(
        name="stone_hut",
        common_name="hutte de pierre",
        materials_kg={"limestone": 60.0, "granite": 25.0, "wood": 12.0},
        labor_h=18.0, min_builders=1,
        aging_material_name="stone_limestone",
        exposure_mode="humid_air",
        thermal_relief=0.015, capacity_agents=3, radius_m=6.0),
    "stone_house": RealBuildRecipe(
        name="stone_house",
        common_name="maison de pierre",
        materials_kg={"limestone": 250.0, "granite": 60.0,
                      "wood": 35.0, "Fe": 4.0},
        labor_h=60.0, min_builders=2,
        aging_material_name="stone_limestone",
        exposure_mode="humid_air",
        thermal_relief=0.025, capacity_agents=6, radius_m=8.0),
    "brick_kiln": RealBuildRecipe(
        name="brick_kiln",
        common_name="four à briques",
        materials_kg={"shale": 30.0, "granite": 6.0, "wood": 4.0},
        labor_h=10.0, min_builders=1,
        aging_material_name="ceramic",
        exposure_mode="humid_air",
        thermal_relief=0.005, capacity_agents=0, radius_m=4.0),
    "mineshaft": RealBuildRecipe(
        name="mineshaft",
        common_name="puits de mine",
        materials_kg={"granite": 100.0, "wood": 12.0, "Fe": 6.0},
        labor_h=80.0, min_builders=2,
        aging_material_name="stone_granite",
        exposure_mode="wet_soil",            # underground = damp
        thermal_relief=0.000, capacity_agents=0, radius_m=10.0),
    "forge": RealBuildRecipe(
        name="forge",
        common_name="forge",
        materials_kg={"granite": 50.0, "shale": 15.0,
                      "wood": 6.0, "Fe": 8.0, "Cu": 2.0},
        labor_h=24.0, min_builders=2,
        aging_material_name="stone_granite",
        exposure_mode="open_fire",           # thermal cycling
        thermal_relief=0.000, capacity_agents=0, radius_m=8.0),
    "marble_temple": RealBuildRecipe(
        name="marble_temple",
        common_name="temple de marbre",
        materials_kg={"marble": 500.0, "limestone": 100.0,
                      "granite": 80.0, "wood": 25.0, "Au": 0.5},
        labor_h=400.0, min_builders=6,
        aging_material_name="marble",
        exposure_mode="humid_air",
        thermal_relief=0.01, capacity_agents=20, radius_m=18.0),
}


# ---------------------------------------------------------------------------
# Built-structure tracker
# ---------------------------------------------------------------------------

@dataclass
class RealStructure:
    structure_id: int
    recipe_name: str
    chunk_coord: Tuple[int, int, int]
    pos_xy: Tuple[float, float]
    owner_culture: int
    built_tick: int
    materials_consumed: Dict[str, float]
    material_instance_id: int = -1       # → material_aging.MaterialInstance
    # Cached computed integrity (refreshed in reporter).
    last_integrity: float = 1.0


@dataclass
class RealConstructionState:
    structures: Dict[int, RealStructure] = field(default_factory=dict)
    next_id: int = 1
    # Stats.
    build_events: int = 0
    failed_builds: int = 0
    cumulative_materials_kg: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Material resolution — pull from real registries
# ---------------------------------------------------------------------------

def _resolve_balance(sim, row: int, material_name: str) -> float:
    """Return how many kg of ``material_name`` the agent currently
    has accessible (geology inventory + metallurgy pure bag +
    fallback inv_wood/metal/stone).
    """
    total = 0.0
    # Pure elements first (metallurgy).
    metal_state = getattr(sim, "_metal_state", None)
    if metal_state is not None:
        bag = metal_state.agent_pure_elements.get(row, {})
        total += float(bag.get(material_name, 0.0))
    # Geology inventory (agent + chunk).
    geo_state = getattr(sim, "_geology_state", None)
    if geo_state is not None:
        # Use cumulative extracted as a proxy of "available in agent
        # inventory" — this is approximate but functional.
        total += float(geo_state.cumulative_extracted.get(material_name, 0.0))
    # Fallback inventories.
    if material_name == "wood":
        try:
            total += float(sim.agents.inv_wood[row])
        except Exception:
            pass
    elif material_name in ("granite", "limestone", "sandstone", "shale",
                            "marble", "slate", "gneiss", "basalt",
                            "obsidian"):
        # Stone tier — inv_stone is the abstract fallback.
        try:
            total += float(sim.agents.inv_stone[row])
        except Exception:
            pass
    elif material_name in ("Fe", "Cu", "Sn", "Au", "Ag", "Pb", "Zn",
                            "Al", "Ti", "Hg", "Mg"):
        try:
            total += float(sim.agents.inv_metal[row])
        except Exception:
            pass
    return total


def _consume_balance(sim, row: int, material_name: str, kg: float) -> float:
    """Subtract ``kg`` from the agent's available stock. Returns how
    much was actually drawn (≤ kg)."""
    remaining = kg
    # Try metallurgy bag first.
    metal_state = getattr(sim, "_metal_state", None)
    if metal_state is not None:
        bag = metal_state.agent_pure_elements.get(row)
        if bag is not None and material_name in bag:
            take = min(remaining, bag[material_name])
            bag[material_name] -= take
            remaining -= take
            metal_state.total_pure_elements[material_name] = max(
                0.0,
                metal_state.total_pure_elements.get(material_name, 0.0) - take)
            if remaining <= 0:
                return kg
    # Then geology cumulative_extracted (chunk-level pool).
    geo_state = getattr(sim, "_geology_state", None)
    if geo_state is not None:
        available = geo_state.cumulative_extracted.get(material_name, 0.0)
        if available > 0:
            take = min(remaining, available)
            geo_state.cumulative_extracted[material_name] = available - take
            remaining -= take
            if remaining <= 0:
                return kg
    # Fallback inventories.
    if material_name == "wood":
        try:
            cur = float(sim.agents.inv_wood[row])
            take = min(remaining, cur)
            sim.agents.inv_wood[row] = cur - take
            remaining -= take
        except Exception:
            pass
    elif material_name in ("granite", "limestone", "sandstone", "shale",
                            "marble", "slate", "gneiss", "basalt",
                            "obsidian"):
        try:
            cur = float(sim.agents.inv_stone[row])
            take = min(remaining, cur)
            sim.agents.inv_stone[row] = cur - take
            remaining -= take
        except Exception:
            pass
    elif material_name in ("Fe", "Cu", "Sn", "Au", "Ag", "Pb", "Zn",
                            "Al", "Ti", "Hg", "Mg"):
        try:
            cur = float(sim.agents.inv_metal[row])
            take = min(remaining, cur)
            sim.agents.inv_metal[row] = cur - take
            remaining -= take
        except Exception:
            pass
    return kg - remaining


# ---------------------------------------------------------------------------
# Public build API
# ---------------------------------------------------------------------------

def _agent_culture(sim, row: int) -> int:
    cultures = getattr(sim.agents, "culture", None)
    if cultures is not None:
        try:
            return int(cultures[row])
        except Exception:
            return 0
    return 0


def can_build(sim, row: int, recipe_name: str) -> Tuple[bool, Dict[str, float]]:
    """Return (ok, deficits). ``deficits[name]`` = how many kg are missing
    (0 means none). ``ok`` = no positive deficit."""
    recipe = REAL_RECIPES.get(recipe_name)
    if recipe is None:
        return False, {"_error": -1.0}
    deficits: Dict[str, float] = {}
    for mat, kg_needed in recipe.materials_kg.items():
        have = _resolve_balance(sim, row, mat)
        if have < kg_needed:
            deficits[mat] = kg_needed - have
    return (not deficits), deficits


def build_real(
    sim,
    row: int,
    recipe_name: str,
) -> Tuple[bool, Optional[int], str]:
    """Try to build a structure. Returns
    ``(success, structure_id, reason)``.

    On success consumes all materials, creates a RealStructure, binds a
    fresh MaterialInstance to it via material_aging, increments stats.
    """
    state = install_realistic_construction(sim)
    recipe = REAL_RECIPES.get(recipe_name)
    if recipe is None:
        return False, None, "unknown_recipe"
    # Check stocks.
    ok, deficits = can_build(sim, row, recipe_name)
    if not ok:
        state.failed_builds += 1
        return False, None, f"insufficient:{deficits}"
    # Consume.
    consumed: Dict[str, float] = {}
    for mat, kg_needed in recipe.materials_kg.items():
        took = _consume_balance(sim, row, mat, kg_needed)
        consumed[mat] = took
        state.cumulative_materials_kg[mat] = (
            state.cumulative_materials_kg.get(mat, 0.0) + took)
    # Register the structure.
    from engine.world import world_to_chunk
    px = float(sim.agents.pos[row, 0])
    py = float(sim.agents.pos[row, 1])
    chunk_c = world_to_chunk(px, py)
    sid = state.next_id
    state.next_id += 1
    culture = _agent_culture(sim, row)
    struct = RealStructure(
        structure_id=sid, recipe_name=recipe_name,
        chunk_coord=chunk_c, pos_xy=(px, py),
        owner_culture=culture, built_tick=int(sim.tick),
        materials_consumed=consumed,
    )
    # Bind to material_aging if available.
    try:
        from engine.material_aging import install_material_aging
        aging = install_material_aging(sim)
        inst = aging.spawn(
            material_id=10000 + sid,
            material_name=recipe.aging_material_name,
            owner_culture=culture,
            spawned_tick=int(sim.tick),
            exposure_mode=recipe.exposure_mode,
        )
        struct.material_instance_id = inst.instance_id
        struct.last_integrity = inst.integrity
    except Exception:
        pass
    state.structures[sid] = struct
    state.build_events += 1
    return True, sid, ""


def install_realistic_construction(sim) -> RealConstructionState:
    """Idempotent installer. No step hook — events are caller-driven.

    Future: could add ActionKind.BUILD_REAL wiring (Wave 10e).
    """
    existing: Optional[RealConstructionState] = getattr(
        sim, "_real_construct_state", None)
    if existing is not None:
        return existing
    state = RealConstructionState()
    sim._real_construct_state = state
    return state


def realistic_construction_state(sim) -> Dict[str, object]:
    state: Optional[RealConstructionState] = getattr(
        sim, "_real_construct_state", None)
    if state is None:
        return {}
    # Refresh integrities.
    aging = getattr(sim, "_aging_registry", None)
    if aging is not None:
        for s in state.structures.values():
            inst = aging.instance(s.material_instance_id)
            if inst is not None:
                s.last_integrity = inst.integrity
    # Histogram by recipe.
    hist: Dict[str, int] = {}
    alive = 0
    ruined = 0
    for s in state.structures.values():
        hist[s.recipe_name] = hist.get(s.recipe_name, 0) + 1
        if s.last_integrity > 0.1:
            alive += 1
        else:
            ruined += 1
    return {
        "structures_total": len(state.structures),
        "alive_structures": alive,
        "ruined_structures": ruined,
        "build_events": state.build_events,
        "failed_builds": state.failed_builds,
        "by_recipe": hist,
        "cumulative_materials_kg": {
            k: round(v, 1) for k, v in state.cumulative_materials_kg.items()
        },
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_realistic_construction_state(sim, target_dir: str) -> bool:
    state: Optional[RealConstructionState] = getattr(
        sim, "_real_construct_state", None)
    if state is None:
        return False
    payload = {
        "next_id": state.next_id,
        "build_events": state.build_events,
        "failed_builds": state.failed_builds,
        "cumulative_materials_kg": state.cumulative_materials_kg,
        "structures": [
            {"structure_id": s.structure_id,
             "recipe_name": s.recipe_name,
             "chunk_coord": list(s.chunk_coord),
             "pos_xy": list(s.pos_xy),
             "owner_culture": s.owner_culture,
             "built_tick": s.built_tick,
             "materials_consumed": s.materials_consumed,
             "material_instance_id": s.material_instance_id,
             "last_integrity": s.last_integrity}
            for s in state.structures.values()
        ],
    }
    with open(os.path.join(target_dir, "realistic_construction.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return True


def load_realistic_construction_state(sim, target_dir: str) -> bool:
    path = os.path.join(target_dir, "realistic_construction.json")
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state = install_realistic_construction(sim)
    state.next_id = int(payload.get("next_id", 1))
    state.build_events = int(payload.get("build_events", 0))
    state.failed_builds = int(payload.get("failed_builds", 0))
    state.cumulative_materials_kg = {
        str(k): float(v)
        for k, v in payload.get("cumulative_materials_kg", {}).items()
    }
    state.structures.clear()
    for d in payload.get("structures", []):
        state.structures[int(d["structure_id"])] = RealStructure(
            structure_id=int(d["structure_id"]),
            recipe_name=str(d["recipe_name"]),
            chunk_coord=tuple(int(x) for x in d["chunk_coord"]),
            pos_xy=tuple(float(x) for x in d["pos_xy"]),
            owner_culture=int(d["owner_culture"]),
            built_tick=int(d["built_tick"]),
            materials_consumed={str(k): float(v)
                                for k, v in d["materials_consumed"].items()},
            material_instance_id=int(d.get("material_instance_id", -1)),
            last_integrity=float(d.get("last_integrity", 1.0)),
        )
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "RealBuildRecipe",
    "RealStructure",
    "RealConstructionState",
    "REAL_RECIPES",
    "install_realistic_construction",
    "can_build",
    "build_real",
    "realistic_construction_state",
    "save_realistic_construction_state",
    "load_realistic_construction_state",
]
