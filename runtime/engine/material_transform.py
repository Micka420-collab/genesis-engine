"""Transformation dynamique matériaux → objets (L2–L4).

Les agents (ou la chaleur ambiante) transforment des matériaux en objets
selon température, pression et recettes physiques — pas de craft scripté.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.agent import ActionKind
from engine.core import prf_rng
from engine.materials import MaterialKind, MATERIALS
from engine.world_physics_registry import material_props

PIPELINE_LAYER = "Genesis-L2 Simulator"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


@dataclass(frozen=True)
class TransformRecipe:
    name: str
    inputs: Dict[str, float]   # material name → kg
    outputs: Dict[str, float]    # product name → kg
    min_temp_k: float
    min_pressure_pa: float = 101325.0
    labor_ticks: int = 3
    object_kind: str = "artifact"


# Recettes naturelles (seuils physiques réels simplifiés)
TRANSFORM_RECIPES: Dict[str, TransformRecipe] = {
    "fire_clay_ceramic": TransformRecipe(
        name="fire_clay_ceramic",
        inputs={"clay": 2.0, "wood": 0.5},
        outputs={"ceramic": 1.8},
        min_temp_k=900.0 + 273.15,
        labor_ticks=5,
        object_kind="ceramic_vessel",
    ),
    "knapp_flint_tool": TransformRecipe(
        name="knapp_flint_tool",
        inputs={"flint": 0.8, "stone": 0.2},
        outputs={"flint_tool": 0.6},
        min_temp_k=280.0,
        labor_ticks=4,
        object_kind="stone_tool",
    ),
    "charcoal_fuel": TransformRecipe(
        name="charcoal_fuel",
        inputs={"wood": 3.0},
        outputs={"charcoal": 1.2},
        min_temp_k=400.0 + 273.15,
        labor_ticks=6,
        object_kind="fuel",
    ),
    "cordage_fiber": TransformRecipe(
        name="cordage_fiber",
        inputs={"fiber": 1.0},
        outputs={"cordage": 0.9},
        min_temp_k=280.0,
        labor_ticks=2,
        object_kind="cord",
    ),
    "bronze_ingot": TransformRecipe(
        name="bronze_ingot",
        inputs={"copper": 0.9, "tin": 0.1, "charcoal": 0.3},
        outputs={"bronze": 1.0},
        min_temp_k=1100.0 + 273.15,
        labor_ticks=8,
        object_kind="metal_ingot",
    ),
}


@dataclass
class TransformProject:
    recipe_id: str
    agent_row: int
    ticks_remaining: int
    progress: float = 0.0


@dataclass
class MaterialTransformState:
    projects: List[TransformProject] = field(default_factory=list)
    completed_total: int = 0
    failed_total: int = 0
    artifacts: Dict[int, List[Dict[str, Any]]] = field(default_factory=dict)
    discovered_recipes: List[str] = field(default_factory=list)


def _agent_inventory_map(agents, row: int) -> Dict[str, float]:
    inv = {
        "wood": float(agents.inv_wood[row]),
        "stone": float(agents.inv_stone[row]),
        "water": float(agents.inv_water[row]),
        "food": float(agents.inv_food[row]),
    }
    metal = float(getattr(agents, "inv_metal", np.zeros(1))[row])
    if metal > 0:
        inv["copper"] = metal * 0.5
        inv["tin"] = metal * 0.2
    # Proxy clay/fiber from wood/stone abundance
    inv["clay"] = inv["stone"] * 0.15
    inv["fiber"] = inv["wood"] * 0.2
    inv["flint"] = inv["stone"] * 0.1
    inv["charcoal"] = inv["wood"] * 0.05
    return inv


def _local_temp_k(sim, row: int) -> float:
    agents = sim.agents
    x = float(agents.pos[row, 0])
    y = float(agents.pos[row, 1])
    from engine.world import world_to_chunk
    cc = world_to_chunk(x, y)
    chunk = sim.streamer.cache.get(cc)
    if chunk is None:
        return 288.0
    base_c = float(np.mean(chunk.height)) * -6.5 + 15.0
    base_c = max(-30.0, min(50.0, base_c))
    dyn = getattr(sim, "_earth_dynamo", None)
    if dyn is not None:
        base_c += 5.0 * (dyn.mean_insolation_w_m2 / 340.0 - 0.5)
    return base_c + 273.15


def can_transform(sim, row: int, recipe_id: str) -> Tuple[bool, str]:
    rec = TRANSFORM_RECIPES.get(recipe_id)
    if rec is None:
        return False, "unknown_recipe"
    inv = _agent_inventory_map(sim.agents, row)
    for mat, need in rec.inputs.items():
        if inv.get(mat, 0.0) < need * 0.95:
            return False, f"missing_{mat}"
    T = _local_temp_k(sim, row)
    if T < rec.min_temp_k * 0.92:
        return False, f"too_cold:{T:.0f}K"
    return True, "ok"


def start_transform(sim, row: int, recipe_id: str) -> Optional[TransformProject]:
    ok, reason = can_transform(sim, row, recipe_id)
    if not ok:
        return None
    st: MaterialTransformState = sim._material_transform
    rec = TRANSFORM_RECIPES[recipe_id]
    proj = TransformProject(recipe_id=recipe_id, agent_row=row, ticks_remaining=rec.labor_ticks)
    st.projects.append(proj)
    if recipe_id not in st.discovered_recipes:
        st.discovered_recipes.append(recipe_id)
    return proj


def _consume_inputs(agents, row: int, rec: TransformRecipe) -> None:
    inv = _agent_inventory_map(agents, row)
    for mat, need in rec.inputs.items():
        if mat == "wood":
            agents.inv_wood[row] = max(0.0, agents.inv_wood[row] - need)
        elif mat == "stone":
            agents.inv_stone[row] = max(0.0, agents.inv_stone[row] - need)
        elif mat in ("copper", "tin") and hasattr(agents, "inv_metal"):
            agents.inv_metal[row] = max(0.0, agents.inv_metal[row] - need)


def _grant_outputs(agents, row: int, rec: TransformRecipe) -> Dict[str, Any]:
    artifact = {
        "kind": rec.object_kind,
        "recipe": rec.name,
        "outputs": dict(rec.outputs),
        "tick": int(getattr(agents, "_sim_tick", 0)),
    }
    for prod, kg in rec.outputs.items():
        if prod in ("ceramic", "flint_tool", "cordage", "charcoal"):
            agents.inv_stone[row] += kg * 0.3
        elif prod == "bronze":
            if hasattr(agents, "inv_metal"):
                agents.inv_metal[row] += kg
    return artifact


def tick_material_transform(sim) -> List[dict]:
    st: MaterialTransformState = getattr(sim, "_material_transform", None)
    if st is None:
        return []
    events: List[dict] = []
    still: List[TransformProject] = []
    for proj in st.projects:
        rec = TRANSFORM_RECIPES[proj.recipe_id]
        ok, _ = can_transform(sim, proj.agent_row, proj.recipe_id)
        if not ok:
            st.failed_total += 1
            continue
        proj.ticks_remaining -= 1
        proj.progress = 1.0 - proj.ticks_remaining / max(rec.labor_ticks, 1)
        if proj.ticks_remaining <= 0:
            _consume_inputs(sim.agents, proj.agent_row, rec)
            art = _grant_outputs(sim.agents, proj.agent_row, rec)
            st.artifacts.setdefault(proj.agent_row, []).append(art)
            st.completed_total += 1
            events.append({
                "kind": "material_transform",
                "agent": proj.agent_row,
                "recipe": proj.recipe_id,
                "object": rec.object_kind,
            })
        else:
            still.append(proj)
    st.projects = still
    return events


def suggest_recipe_for_agent(sim, row: int) -> Optional[str]:
    """Émergent : première recette réalisable (température + stock)."""
    T = _local_temp_k(sim, row)
    inv = _agent_inventory_map(sim.agents, row)
    candidates: List[str] = []
    for rid, rec in TRANSFORM_RECIPES.items():
        if T < rec.min_temp_k * 0.92:
            continue
        if all(inv.get(m, 0) >= need * 0.95 for m, need in rec.inputs.items()):
            candidates.append(rid)
    if not candidates:
        return None
    rng = prf_rng(int(sim.cfg.seed), ["transform", "suggest"], [row, sim.tick])
    return candidates[int(rng.integers(0, len(candidates)))]


def try_agent_build_transform(sim, row: int) -> List[dict]:
    """Appelé sur ActionKind.BUILD — démarre une transformation physique."""
    rid = suggest_recipe_for_agent(sim, row)
    if rid is None:
        return []
    proj = start_transform(sim, row, rid)
    if proj is None:
        return []
    return [{"kind": "transform_start", "agent": row, "recipe": rid}]


def install_material_transform(sim) -> MaterialTransformState:
    existing = getattr(sim, "_material_transform", None)
    if existing is not None:
        return existing
    st = MaterialTransformState()
    sim._material_transform = st

    if not getattr(sim, "_material_transform_patched", False):
        sim._material_transform_patched = True
        # BUILD/SMELT gérés par ``emergent_construction`` si présent.
        if not getattr(sim, "_emergent_construction_patched", False):
            import engine.cognition as cog
            if getattr(cog, "_transform_inner_apply", None) is None:
                cog._transform_inner_apply = cog.apply_decision

                def wrapped(agents, row, decision, streamer, tick):
                    events = cog._transform_inner_apply(agents, row, decision, streamer, tick)
                    if events is None:
                        events = []
                    if int(decision.action) == int(ActionKind.BUILD):
                        events.extend(try_agent_build_transform(sim, row))
                    if int(decision.action) == int(ActionKind.SMELT):
                        rid = "bronze_ingot"
                        if start_transform(sim, row, rid):
                            events.append({"kind": "transform_start", "agent": row, "recipe": rid})
                    return events

                cog.apply_decision = wrapped

            if not getattr(sim, "_emergent_construction_patched", False):
                orig = sim.step

                def step_wrapped():
                    stats = orig()
                    tick_material_transform(sim)
                    return stats

                sim.step = step_wrapped
    return st


def material_transform_snapshot(sim) -> Dict[str, Any]:
    st: Optional[MaterialTransformState] = getattr(sim, "_material_transform", None)
    if st is None:
        return {"installed": False}
    return {
        "installed": True,
        "active_projects": len(st.projects),
        "completed_total": st.completed_total,
        "failed_total": st.failed_total,
        "discovered_recipes": list(st.discovered_recipes),
        "recipe_catalog": list(TRANSFORM_RECIPES.keys()),
        "artifacts_count": sum(len(v) for v in st.artifacts.values()),
    }


__all__ = [
    "TRANSFORM_RECIPES",
    "TransformRecipe",
    "install_material_transform",
    "tick_material_transform",
    "material_transform_snapshot",
    "can_transform",
    "start_transform",
]
