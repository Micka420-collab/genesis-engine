"""Construction émergente unifiée — tout émerge du monde + matériaux + agents.

Fusionne sans script civilisationnel :
  - ``material_transform`` (objets : céramique, outils, bronze)
  - ``realistic_construction`` (huttes, forges, temples minéraux nommés)
  - ``construction`` (foyers, puits, ateliers — StructureKind)
  - voxels / ``building_discovery`` (blocs physiques)

BUILD / SMELT (choisi par le cerveau, pas de script) → expérimentation ou
recettes **déjà découvertes** ; outils d'abord, puis constructions libres.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.agent import ActionKind
from engine.construction import RECIPES, ConstructionRegistry, StructureKind
from engine.core import prf_rng
from engine.material_transform import (
    TRANSFORM_RECIPES,
    can_transform,
    start_transform,
    tick_material_transform,
    _local_temp_k,
)
from engine.realistic_construction import REAL_RECIPES, build_real, can_build
from engine.tool_discovery import (
    agent_artifact_kinds,
    has_tool_prereqs,
    known_recipes_for_agent,
    pick_experiment_recipe,
    register_discovery,
)

PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"

IMITATION_RADIUS_M = 42.0
LABOR_HOURS_PER_BUILD_TICK = 0.35

# Process-wide stacked wrapper (comme physiology / knowledge).
_EMERGENT_DISPATCH: Dict[int, Any] = {}


@dataclass(frozen=True)
class EmergentRecipe:
    key: str
    channel: str  # transform | real | structure | voxel
    labor_ticks: int
    min_temp_k: float = 280.0
    structure_kind: Optional[StructureKind] = None


def _build_catalog() -> Dict[str, EmergentRecipe]:
    cat: Dict[str, EmergentRecipe] = {}
    for rid, tr in TRANSFORM_RECIPES.items():
        cat[rid] = EmergentRecipe(
            key=rid, channel="transform",
            labor_ticks=tr.labor_ticks, min_temp_k=tr.min_temp_k,
        )
    for rid, rr in REAL_RECIPES.items():
        cat[rid] = EmergentRecipe(
            key=rid, channel="real",
            labor_ticks=max(3, int(rr.labor_h / 4)),
            min_temp_k=290.0,
        )
    for sk, rec in RECIPES.items():
        cat[f"struct_{rec.name}"] = EmergentRecipe(
            key=f"struct_{rec.name}", channel="structure",
            labor_ticks=max(4, int(rec.labor_hours / 3)),
            min_temp_k=280.0,
            structure_kind=sk,
        )
    cat["voxel_shelter"] = EmergentRecipe(
        key="voxel_shelter", channel="voxel", labor_ticks=2, min_temp_k=270.0,
    )
    return cat


CATALOG = _build_catalog()


@dataclass
class EmergentSite:
    recipe_key: str
    agent_row: int
    ticks_remaining: int
    pos: Tuple[float, float, float]
    project_id: Optional[int] = None


@dataclass
class EmergentConstructionState:
    """Mémoire civilisationnelle — vide au départ (ZERO PRE-SCRIPT)."""
    discovered: List[str] = field(default_factory=list)
    per_agent_discovered: Dict[int, List[str]] = field(default_factory=dict)
    culture_discovered: Dict[int, List[str]] = field(default_factory=dict)
    sites: List[EmergentSite] = field(default_factory=list)
    completed_total: int = 0
    failed_total: int = 0
    structures_total: int = 0
    imitations: int = 0
    experiments_started: int = 0
    experiments_success: int = 0


def _ensure_subsystems(sim) -> ConstructionRegistry:
    if not hasattr(sim, "construction_registry"):
        sim.construction_registry = ConstructionRegistry()
    from engine.realistic_construction import install_realistic_construction
    install_realistic_construction(sim)
    from engine.material_transform import install_material_transform
    install_material_transform(sim)
    return sim.construction_registry


def _agent_materials(sim, row: int) -> Dict[str, float]:
    a = sim.agents
    out = {
        "wood": float(a.inv_wood[row]),
        "stone": float(a.inv_stone[row]),
        "water": float(a.inv_water[row]),
        "clay": float(a.inv_stone[row]) * 0.12,
        "fiber": float(a.inv_wood[row]) * 0.15,
        "flint": float(a.inv_stone[row]) * 0.08,
        "charcoal": float(a.inv_wood[row]) * 0.05,
    }
    metal = float(getattr(a, "inv_metal", np.zeros(1))[row])
    if metal > 0:
        out["copper"] = metal * 0.4
        out["tin"] = metal * 0.15
        out["Fe"] = metal * 0.2
    return out


def _can_emerge(sim, row: int, spec: EmergentRecipe) -> Tuple[bool, float]:
    T = _local_temp_k(sim, row)
    if T < spec.min_temp_k * 0.9:
        return False, 0.0
    if spec.channel == "transform":
        ok, _ = can_transform(sim, row, spec.key)
        return ok, 1.0 if ok else 0.0
    if spec.channel == "real":
        ok, deficits = can_build(sim, row, spec.key)
        score = 1.0 - min(1.0, sum(deficits.values()) / 100.0) if ok else 0.2
        return ok, score
    if spec.channel == "structure" and spec.structure_kind is not None:
        reg = _ensure_subsystems(sim)
        inv = {}
        from engine.materials import MaterialKind
        mats = _agent_materials(sim, row)
        inv[MaterialKind.WOOD] = mats.get("wood", 0)
        inv[MaterialKind.STONE] = mats.get("stone", 0)
        inv[MaterialKind.FIBER] = mats.get("fiber", 0)
        inv[MaterialKind.CLAY] = mats.get("clay", 0)
        ok = reg.can_satisfy_materials(spec.structure_kind, inv)
        return ok, 0.85 if ok else 0.1
    if spec.channel == "voxel":
        mats = _agent_materials(sim, row)
        ok = mats.get("stone", 0) >= 0.3 or mats.get("wood", 0) >= 0.3
        return ok, 0.5 if ok else 0.0
    return False, 0.0


def _score_candidates(sim, row: int, st: EmergentConstructionState) -> List[Tuple[float, str]]:
    """Uniquement recettes **déjà découvertes** et débloquées par les outils."""
    known = known_recipes_for_agent(st, sim, row)
    artifacts = agent_artifact_kinds(sim, row)
    scored: List[Tuple[float, str]] = []
    curiosity = float(sim.agents.curiosity[row])
    for key, spec in CATALOG.items():
        if key not in known:
            continue
        if not has_tool_prereqs(key, known, artifacts):
            continue
        ok, base = _can_emerge(sim, row, spec)
        if not ok and base < 0.15:
            continue
        scored.append((base + curiosity * 0.1, key))
    scored.sort(key=lambda x: -x[0])
    return scored


def _imitate_discoveries(sim, row: int, st: EmergentConstructionState) -> None:
    ax = float(sim.agents.pos[row, 0])
    ay = float(sim.agents.pos[row, 1])
    n = sim.agents.n_active
    for other in range(n):
        if other == row or not sim.agents.alive[other]:
            continue
        d2 = (ax - sim.agents.pos[other, 0]) ** 2 + (ay - sim.agents.pos[other, 1]) ** 2
        if d2 > IMITATION_RADIUS_M ** 2:
            continue
        ost = getattr(sim, "_emergent_construction", None)
        if ost is None:
            continue
        for key in ost.discovered:
            if key not in st.discovered:
                st.discovered.append(key)
                st.imitations += 1


def _complete_site(sim, site: EmergentSite, st: EmergentConstructionState) -> List[dict]:
    spec = CATALOG[site.recipe_key]
    row = site.agent_row
    events: List[dict] = []

    if spec.channel == "transform":
        ok, _ = can_transform(sim, row, spec.key)
        if ok and start_transform(sim, row, spec.key):
            st.experiments_success += 1
            events.append({"kind": "emergent_transform", "recipe": spec.key, "agent": row})
        elif not ok:
            st.failed_total += 1
            events.append({"kind": "emergent_experiment_fail", "recipe": spec.key, "agent": row})
    elif spec.channel == "real":
        ok, sid, reason = build_real(sim, row, spec.key)
        if ok:
            st.structures_total += 1
            events.append({"kind": "emergent_build_real", "recipe": spec.key,
                           "structure_id": sid, "agent": row})
        else:
            st.failed_total += 1
            events.append({"kind": "emergent_build_fail", "reason": reason})
    elif spec.channel == "structure" and spec.structure_kind is not None:
        reg = sim.construction_registry
        proj = reg.start_project(
            spec.structure_kind, site.pos, sim.tick, row,
        )
        site.project_id = proj.project_id
        from engine.materials import MaterialKind as MK
        avail = {
            MK.WOOD: _agent_materials(sim, row).get("wood", 0),
            MK.STONE: _agent_materials(sim, row).get("stone", 0),
            MK.FIBER: _agent_materials(sim, row).get("fiber", 0),
            MK.CLAY: _agent_materials(sim, row).get("clay", 0),
        }
        for mat, qty in list(proj.materials_needed.items()):
            reg.deliver_material(proj.project_id, mat, min(qty, avail.get(mat, 0)))
        hours = LABOR_HOURS_PER_BUILD_TICK * max(spec.labor_ticks, 1)
        done = reg.add_labor(proj.project_id, hours, row)
        if done:
            st.structures_total += 1
            events.append({"kind": "emergent_build_structure", "recipe": spec.key,
                           "agent": row})
    elif spec.channel == "voxel":
        from engine.knowledge_wiring import _maybe_build_voxel
        ev = _maybe_build_voxel(sim, sim.agents, row)
        if ev:
            events.append(ev)
            st.structures_total += 1

    register_discovery(st, sim, row, site.recipe_key)
    st.completed_total += 1
    _imitate_discoveries(sim, row, st)
    return events


def _nearby_site(st: EmergentConstructionState, sim, row: int) -> Optional[EmergentSite]:
    ax = float(sim.agents.pos[row, 0])
    ay = float(sim.agents.pos[row, 1])
    best: Optional[EmergentSite] = None
    best_d = 1e18
    for site in st.sites:
        d2 = (ax - site.pos[0]) ** 2 + (ay - site.pos[1]) ** 2
        if d2 < 28.0 ** 2 and d2 < best_d:
            best_d = d2
            best = site
    return best


def emergent_build_on_action(sim, row: int) -> List[dict]:
    """Point d'entrée BUILD / SMELT — chantier ou nouveau projet."""
    st: EmergentConstructionState = sim._emergent_construction
    _ensure_subsystems(sim)
    events: List[dict] = []

    site = _nearby_site(st, sim, row)
    if site is not None:
        site.ticks_remaining -= 1
        if site.ticks_remaining <= 0:
            events.extend(_complete_site(sim, site, st))
            st.sites.remove(site)
        else:
            events.append({
                "kind": "emergent_build_progress",
                "recipe": site.recipe_key,
                "progress": 1.0 - site.ticks_remaining / max(
                    CATALOG[site.recipe_key].labor_ticks, 1),
            })
        return events

    known = known_recipes_for_agent(st, sim, row)
    candidates = _score_candidates(sim, row, st)

    if not candidates:
        trial_key, trial_score = pick_experiment_recipe(sim, row, known)
        px = float(sim.agents.pos[row, 0])
        py = float(sim.agents.pos[row, 1])
        if trial_key is not None:
            spec = CATALOG[trial_key]
            extra = 2 if trial_score < 0.5 else 0
            site = EmergentSite(
                trial_key, row, spec.labor_ticks + extra, (px, py, 0.0),
            )
            st.sites.append(site)
            st.experiments_started += 1
            events.append({
                "kind": "emergent_experiment_start",
                "recipe": trial_key,
                "agent": row,
            })
            return events
        if float(sim.agents.inv_stone[row]) >= 0.5 or float(sim.agents.inv_wood[row]) >= 0.5:
            site = EmergentSite("voxel_shelter", row, 3, (px, py, 0.0))
            st.sites.append(site)
            st.experiments_started += 1
            events.append({"kind": "emergent_raw_stack_start", "recipe": "voxel_shelter"})
        return events

    rng = prf_rng(int(sim.cfg.seed), ["emerge", "build"], [row, sim.tick])
    pick = candidates[min(int(rng.integers(0, min(3, len(candidates)))), len(candidates) - 1)][1]
    spec = CATALOG[pick]
    px = float(sim.agents.pos[row, 0])
    py = float(sim.agents.pos[row, 1])
    site = EmergentSite(pick, row, spec.labor_ticks, (px, py, 0.0))
    st.sites.append(site)
    events.append({"kind": "emergent_site_start", "recipe": pick, "channel": spec.channel})
    return events


def tick_emergent_construction(sim) -> List[dict]:
    st: Optional[EmergentConstructionState] = getattr(sim, "_emergent_construction", None)
    if st is None:
        return []
    events: List[dict] = []
    mt_events = tick_material_transform(sim)
    events.extend(mt_events)
    for ev in mt_events:
        if ev.get("kind") == "material_transform":
            register_discovery(st, sim, int(ev["agent"]), str(ev["recipe"]))
    if hasattr(sim, "construction_registry"):
        from engine.sim_5cd_integration import tick_construction
        tick_construction(sim)
    # Auto-progress sites when agent idle nearby
    for site in list(st.sites):
        row = site.agent_row
        if not sim.agents.alive[row]:
            continue
        if int(sim.agents.action[row]) in (int(ActionKind.BUILD), int(ActionKind.IDLE)):
            site.ticks_remaining -= 1
            if site.ticks_remaining <= 0:
                events.extend(_complete_site(sim, site, st))
                st.sites.remove(site)
    return events


def _emergent_global_wrapper(agents, row, decision, streamer, tick, *args, **kwargs):
    """Wrapper empilé — délègue puis BUILD/SMELT émergents."""
    import engine.cognition as cog

    inner = getattr(cog, "_emergent_inner_apply_decision", None)
    if inner is None:
        return None
    events = inner(agents, row, decision, streamer, tick, *args, **kwargs)
    if events is None:
        events = []
    sim = _EMERGENT_DISPATCH.get(id(agents))
    if sim is None or not getattr(sim, "_emergent_construction", None):
        return events
    act = int(decision.action)
    if act in (int(ActionKind.BUILD), int(ActionKind.SMELT)):
        events.extend(emergent_build_on_action(sim, row))
    return events


def install_emergent_construction(sim) -> EmergentConstructionState:
    existing = getattr(sim, "_emergent_construction", None)
    if existing is not None:
        _EMERGENT_DISPATCH[id(sim.agents)] = sim
        return existing
    # Réserver avant sous-systèmes : évite double patch material_transform.
    sim._emergent_construction_patched = True
    _ensure_subsystems(sim)
    st = EmergentConstructionState()
    sim._emergent_construction = st
    _EMERGENT_DISPATCH[id(sim.agents)] = sim

    import engine.cognition as cog
    import engine.sim as sim_mod

    if getattr(cog, "_emergent_inner_apply_decision", None) is None:
        cog._emergent_inner_apply_decision = cog.apply_decision
        cog.apply_decision = _emergent_global_wrapper
        if hasattr(sim_mod, "apply_decision"):
            sim_mod.apply_decision = _emergent_global_wrapper

    if not getattr(sim, "_emergent_construction_step_hooked", False):
        sim._emergent_construction_step_hooked = True
        orig_step = sim.step

        def wrapped_step():
            stats = orig_step()
            tick_emergent_construction(sim)
            return stats

        sim.step = wrapped_step

    return st


def emergent_construction_snapshot(sim) -> Dict[str, Any]:
    st: Optional[EmergentConstructionState] = getattr(sim, "_emergent_construction", None)
    if st is None:
        return {"installed": False}
    reg = getattr(sim, "construction_registry", None)
    return {
        "installed": True,
        "discovered": list(st.discovered),
        "n_cultures_with_tech": len(st.culture_discovered),
        "experiments_started": st.experiments_started,
        "experiments_success": st.experiments_success,
        "active_sites": len(st.sites),
        "completed_total": st.completed_total,
        "structures_total": st.structures_total,
        "imitations": st.imitations,
        "catalog_size": len(CATALOG),
        "registry_projects": len(reg.projects) if reg else 0,
        "registry_structures": len(reg.structures) if reg else 0,
        "channels": ["transform", "real", "structure", "voxel"],
    }


__all__ = [
    "CATALOG",
    "EmergentConstructionState",
    "install_emergent_construction",
    "emergent_build_on_action",
    "tick_emergent_construction",
    "emergent_construction_snapshot",
]
