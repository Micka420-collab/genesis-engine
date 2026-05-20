"""Observer feed — vue du ciel : chantiers, ouvriers, structures, terraformation.

Agrège les données simulation pour le rendu Earth Console (god-view RTS).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from engine.agent import ActionKind
from engine.construction import RECIPES, StructureKind
from engine.world import CHUNK_SIDE_M

PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"

# ActionKind values exposed to the client
ACTION_BUILD = int(ActionKind.BUILD)
ACTION_SMELT = int(ActionKind.SMELT)
ACTION_PLANT = int(ActionKind.PLANT)


def _in_bbox(
    x: float, y: float,
    xmin: float, ymin: float, xmax: float, ymax: float,
    margin_m: float = 80.0,
) -> bool:
    return (
        xmin - margin_m <= x <= xmax + margin_m
        and ymin - margin_m <= y <= ymax + margin_m
    )


def _chunk_center_xy(cx: int, cy: int) -> Tuple[float, float]:
    h = CHUNK_SIDE_M * 0.5
    return cx * CHUNK_SIDE_M + h, cy * CHUNK_SIDE_M + h


def _structure_icon(kind: StructureKind) -> str:
    icons = {
        StructureKind.HEARTH: "fire",
        StructureKind.LEAN_TO: "shelter",
        StructureKind.HUT: "hut",
        StructureKind.WELL: "well",
        StructureKind.GRANARY: "granary",
        StructureKind.WORKSHOP: "workshop",
        StructureKind.KILN: "kiln",
        StructureKind.FURNACE: "forge",
        StructureKind.BLOOMERY: "forge",
        StructureKind.FARM_PLOT: "farm",
    }
    return icons.get(kind, "build")


def _collect_emergent_sites(sim, xmin, ymin, xmax, ymax) -> List[Dict[str, Any]]:
    st = getattr(sim, "_emergent_construction", None)
    if st is None:
        return []
    from engine.emergent_construction import CATALOG

    sites: List[Dict[str, Any]] = []
    for site in st.sites:
        x, y = float(site.pos[0]), float(site.pos[1])
        if not _in_bbox(x, y, xmin, ymin, xmax, ymax):
            continue
        spec = CATALOG.get(site.recipe_key)
        labor = max(spec.labor_ticks, 1) if spec else 1
        progress = 1.0 - max(0, site.ticks_remaining) / labor
        sites.append({
            "kind": "emergent_site",
            "x": round(x, 1),
            "y": round(y, 1),
            "recipe": site.recipe_key,
            "channel": spec.channel if spec else "unknown",
            "progress": round(min(1.0, progress), 3),
            "agent_row": int(site.agent_row),
            "radius_m": 6.0 + progress * 4.0,
        })
    return sites


def _collect_registry(sim, xmin, ymin, xmax, ymax) -> Tuple[List[Dict], List[Dict]]:
    reg = getattr(sim, "construction_registry", None)
    if reg is None:
        return [], []
    sites: List[Dict[str, Any]] = []
    structures: List[Dict[str, Any]] = []
    for proj in reg.projects.values():
        x, y = float(proj.pos[0]), float(proj.pos[1])
        if not _in_bbox(x, y, xmin, ymin, xmax, ymax):
            continue
        total_labor = max(proj.recipe.labor_hours, 0.01)
        progress = min(1.0, proj.labor_committed / total_labor)
        sites.append({
            "kind": "registry_project",
            "x": round(x, 1),
            "y": round(y, 1),
            "recipe": proj.recipe.name,
            "channel": "structure",
            "progress": round(progress, 3),
            "agent_row": int(proj.initiator),
            "radius_m": proj.recipe.radius_m,
        })
    for st in reg.structures.values():
        x, y = float(st.pos[0]), float(st.pos[1])
        if not _in_bbox(x, y, xmin, ymin, xmax, ymax):
            continue
        structures.append({
            "kind": "structure",
            "x": round(x, 1),
            "y": round(y, 1),
            "recipe": st.recipe.name,
            "icon": _structure_icon(st.kind),
            "durability": round(float(st.durability), 3),
            "radius_m": st.recipe.radius_m,
            "built_tick": int(st.built_tick),
        })
    return sites, structures


def _collect_real_structures(sim, xmin, ymin, xmax, ymax) -> List[Dict[str, Any]]:
    rstate = getattr(sim, "_real_construct_state", None)
    if rstate is None:
        return []
    out: List[Dict[str, Any]] = []
    for s in rstate.structures.values():
        x, y = float(s.pos_xy[0]), float(s.pos_xy[1])
        if not _in_bbox(x, y, xmin, ymin, xmax, ymax):
            continue
        out.append({
            "kind": "real_structure",
            "x": round(x, 1),
            "y": round(y, 1),
            "recipe": s.recipe_name,
            "icon": "monument" if "temple" in s.recipe_name else "hut",
            "integrity": round(float(s.last_integrity), 3),
            "radius_m": 8.0,
            "culture": int(s.owner_culture),
        })
    return out


def _collect_workers(sim, xmin, ymin, xmax, ymax) -> List[Dict[str, Any]]:
    a = sim.agents
    n = int(a.n_active)
    worker_actions = {
        ACTION_BUILD, ACTION_SMELT, ACTION_PLANT,
        int(ActionKind.MINE),
    }
    workers: List[Dict[str, Any]] = []
    for row in range(n):
        if not a.alive[row]:
            continue
        act = int(a.action[row]) if hasattr(a, "action") else 0
        if act not in worker_actions:
            continue
        x, y = float(a.pos[row, 0]), float(a.pos[row, 1])
        if not _in_bbox(x, y, xmin, ymin, xmax, ymax):
            continue
        vx, vy = float(a.vel[row, 0]), float(a.vel[row, 1])
        heading = math.atan2(vy, vx) if (vx * vx + vy * vy) > 0.01 else 0.0
        from engine.agent_presence import human_presence
        pres = human_presence(sim, row)
        workers.append({
            "row": int(row),
            "x": round(x, 1),
            "y": round(y, 1),
            "action": act,
            "heading": round(heading, 4),
            "speed": round(math.hypot(vx, vy), 3),
            "culture": int(a.relations[row].culture_id),
            "posture": pres["posture"],
            "activity": pres["activity"],
            "tool": pres["tool"],
            "skin": pres["skin"],
            "gait_phase": pres["gait_phase"],
        })
    return workers


def _collect_terraform(sim, xmin, ymin, xmax, ymax) -> List[Dict[str, Any]]:
    patches: List[Dict[str, Any]] = []
    ag = getattr(sim, "_ag_state", None)
    if ag is not None:
        for (cx, cy, cz), fields in ag.fields_per_chunk.items():
            wx, wy = _chunk_center_xy(cx, cy)
            if not _in_bbox(wx, wy, xmin, ymin, xmax, ymax):
                continue
            for f in fields:
                intensity = min(1.0, 0.35 + f.harvest_count * 0.08)
                patches.append({
                    "kind": "cultivation",
                    "x": round(wx, 1),
                    "y": round(wy, 1),
                    "radius_m": CHUNK_SIDE_M * 0.45,
                    "clade": f.clade,
                    "intensity": round(intensity, 3),
                    "culture": int(f.owner_culture),
                })

    return patches


def observer_feed_snapshot(
    sim,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
) -> Dict[str, Any]:
    """Payload for ``GET /api/observer_feed``."""
    sites = _collect_emergent_sites(sim, xmin, ymin, xmax, ymax)
    reg_sites, reg_structures = _collect_registry(sim, xmin, ymin, xmax, ymax)
    sites.extend(reg_sites)
    structures = reg_structures + _collect_real_structures(sim, xmin, ymin, xmax, ymax)
    workers = _collect_workers(sim, xmin, ymin, xmax, ymax)
    terraform = _collect_terraform(sim, xmin, ymin, xmax, ymax)

    em = getattr(sim, "_emergent_construction", None)
    return {
        "tick": int(sim.tick),
        "bbox": [round(xmin, 1), round(ymin, 1), round(xmax, 1), round(ymax, 1)],
        "sites": sites,
        "structures": structures,
        "workers": workers,
        "terraform": terraform,
        "counts": {
            "sites": len(sites),
            "structures": len(structures),
            "workers": len(workers),
            "terraform": len(terraform),
        },
        "construction": {
            "discovered": len(em.discovered) if em else 0,
            "completed": em.completed_total if em else 0,
            "imitations": em.imitations if em else 0,
        },
    }


__all__ = [
    "observer_feed_snapshot",
    "ACTION_BUILD",
    "ACTION_SMELT",
    "ACTION_PLANT",
]
