"""Genesis Engine — observable agent snapshots (humans + IA).

Exporte un instantané JSON structuré : positions, culture, santé,
rayon de perception, voisins proches. Read-only sur la simulation.

Usage::

    from engine.agent_observation import export_observable_snapshot
    export_observable_snapshot(sim, "artifacts/observable.json")
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from engine.cognition import PERCEPTION_RADIUS_M


PIPELINE_LAYER = "Genesis-L5 Observer"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

DEFAULT_PERCEPTION_RADIUS_M = PERCEPTION_RADIUS_M


def genesis_observable_meta(sim) -> Dict[str, Any]:
    """Genesis / bootstrap context for observable exports (no synthetic grid)."""
    state = getattr(sim, "_genesis_bootstrap_state", None)
    if state is None:
        anchor = getattr(getattr(sim, "streamer", None), "genesis", None)
        if anchor is None:
            return {"emergence": "agents_only", "genesis": False}
        return {"emergence": "streamer_anchor", "genesis": True}
    from engine.world_genesis import world_signature

    return {
        "emergence": "genesis_bootstrap",
        "genesis": True,
        "genesis_seed": int(state.world.params.seed),
        "world_signature": world_signature(state.world),
        "modules_installed": sorted(state.modules_installed),
    }


@dataclass
class AgentObservable:
    """One alive agent — fields for dashboard + LLM observers."""
    row: int
    uuid: str
    generation: int
    x_m: float
    y_m: float
    culture_id: int
    group_id: int
    vitality: float
    hunger: float
    thirst: float
    injuries: float
    pathogen_load: float
    perception_radius_m: float
    nearby_agents: int
    action: int
    intelligence: float = 0.0


@dataclass
class VisionCone:
    """Visible neighbours for one agent (deterministic, sorted by uuid)."""
    row: int
    center_x_m: float
    center_y_m: float
    radius_m: float
    visible_agent_rows: List[int] = field(default_factory=list)
    visible_uuids: List[str] = field(default_factory=list)


@dataclass
class ObservableSnapshot:
    """Full world observation at one tick."""
    tick: int
    sim_id: str
    bounds_m: List[float]
    n_alive: int
    perception_radius_m: float
    agents: List[AgentObservable] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    vision_cones: List[VisionCone] = field(default_factory=list)


def _pathogen_load(sim, row: int) -> float:
    """Worst active pathogen load if physiology is wired."""
    try:
        pf = sim._physio_fields
    except AttributeError:
        return 0.0
    loads = []
    for name in ("cholera_load", "flu_load", "wound_load"):
        arr = getattr(pf, name, None)
        if arr is not None:
            loads.append(float(arr[row]))
    return max(loads) if loads else 0.0


def observe_agent_row(sim, row: int, *,
                      perception_radius_m: float = DEFAULT_PERCEPTION_RADIUS_M,
                      nearby: Optional[int] = None) -> AgentObservable:
    """Build one observable record (agent must be alive)."""
    agents = sim.agents
    rel = agents.relations[row]
    culture = int(getattr(rel, "culture_id", 0))
    gid = rel.group_id
    group_id = int(gid) if gid is not None else -1
    intel = float(agents.intelligence[row]) if hasattr(agents, "intelligence") else 0.0
    nearby_n = int(nearby) if nearby is not None else 0
    pl = _pathogen_load(sim, row)
    return AgentObservable(
        row=int(row),
        uuid=str(agents.uuid[row]),
        generation=int(agents.generation[row]),
        x_m=float(agents.pos[row, 0]),
        y_m=float(agents.pos[row, 1]),
        culture_id=culture,
        group_id=group_id,
        vitality=float(agents.vitality[row]),
        hunger=float(agents.hunger[row]),
        thirst=float(agents.thirst[row]),
        injuries=float(agents.injuries[row]) if hasattr(agents, "injuries") else 0.0,
        pathogen_load=pl,
        perception_radius_m=float(perception_radius_m),
        nearby_agents=nearby_n,
        action=int(agents.action[row]),
        intelligence=intel,
    )


def export_vision_cone(sim, row: int, *,
                       perception_radius_m: float = DEFAULT_PERCEPTION_RADIUS_M
                       ) -> VisionCone:
    """Agents visible within perception radius (O(n), deterministic order)."""
    agents = sim.agents
    if not bool(agents.alive[row]):
        return VisionCone(row=row, center_x_m=0.0, center_y_m=0.0,
                          radius_m=perception_radius_m)
    ax = float(agents.pos[row, 0])
    ay = float(agents.pos[row, 1])
    n = agents.n_active
    visible_rows: List[int] = []
    visible_uuids: List[str] = []
    r2 = perception_radius_m ** 2
    for other in range(n):
        if other == row or not bool(agents.alive[other]):
            continue
        dx = float(agents.pos[other, 0]) - ax
        dy = float(agents.pos[other, 1]) - ay
        if dx * dx + dy * dy <= r2:
            visible_rows.append(int(other))
            visible_uuids.append(str(agents.uuid[other]))
    order = np.argsort(visible_uuids)
    visible_rows = [visible_rows[i] for i in order]
    visible_uuids = [visible_uuids[i] for i in order]
    return VisionCone(
        row=int(row), center_x_m=ax, center_y_m=ay,
        radius_m=float(perception_radius_m),
        visible_agent_rows=visible_rows,
        visible_uuids=visible_uuids,
    )


def export_all_vision_cones(sim, *,
                            perception_radius_m: float = DEFAULT_PERCEPTION_RADIUS_M,
                            max_agents: int = 200,
                            ) -> List[VisionCone]:
    """Vision cones for alive agents (capped for JSON size)."""
    agents = sim.agents
    n = agents.n_active
    rows = [r for r in range(n) if bool(agents.alive[r])]
    rows = rows[:max_agents]
    return [export_vision_cone(sim, r, perception_radius_m=perception_radius_m)
            for r in rows]


def _neighbor_counts(pos: np.ndarray, radius_m: float) -> np.ndarray:
    """Per-agent count of others within ``radius_m`` (O(n²), fine for n<500)."""
    n = pos.shape[0]
    if n == 0:
        return np.zeros(0, dtype=np.int32)
    dx = pos[:, 0][:, None] - pos[:, 0][None, :]
    dy = pos[:, 1][:, None] - pos[:, 1][None, :]
    dist = np.sqrt(dx * dx + dy * dy)
    within = (dist <= radius_m) & (dist > 1e-3)
    return within.sum(axis=1).astype(np.int32) - 1  # exclude self


def export_observable_snapshot(sim, out_path: str, *,
                               perception_radius_m: float = DEFAULT_PERCEPTION_RADIUS_M,
                               extra_meta: Optional[Dict[str, Any]] = None,
                               include_vision_cones: bool = True,
                               ) -> ObservableSnapshot:
    """Write JSON snapshot and return the in-memory struct."""
    agents = sim.agents
    n = agents.n_active
    alive_rows = [r for r in range(n) if bool(agents.alive[r])]
    pos = agents.pos[:n, :2][agents.alive[:n]].astype(np.float32) if alive_rows else np.zeros((0, 2))
    neighbors = _neighbor_counts(pos, perception_radius_m) if len(alive_rows) else np.zeros(0, dtype=np.int32)
    obs_agents: List[AgentObservable] = []
    for i, row in enumerate(alive_rows):
        obs_agents.append(
            observe_agent_row(
                sim, row,
                perception_radius_m=perception_radius_m,
                nearby=int(neighbors[i]) if len(neighbors) else None,
            )
        )

    bx_m = sim.cfg.bounds_km[0] * 500.0
    by_m = sim.cfg.bounds_km[1] * 500.0
    vision = (export_all_vision_cones(sim, perception_radius_m=perception_radius_m)
              if include_vision_cones else [])
    meta = dict(genesis_observable_meta(sim))
    if extra_meta:
        meta.update(extra_meta)
    snap = ObservableSnapshot(
        tick=int(sim.tick),
        sim_id=str(sim.sim_id),
        bounds_m=[float(bx_m), float(by_m)],
        n_alive=len(obs_agents),
        perception_radius_m=float(perception_radius_m),
        agents=obs_agents,
        meta=meta,
        vision_cones=vision,
    )
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    payload = asdict(snap)
    # Compact agent list for dashboard compatibility.
    payload["agents_compact"] = [
        {
            "row": a.row, "uuid": a.uuid, "gen": a.generation,
            "x": a.x_m, "y": a.y_m,
            "h": a.hunger, "t": a.thirst, "v": a.vitality,
            "c": a.culture_id, "g": a.group_id, "a": a.action,
            "vision_m": a.perception_radius_m,
            "nearby": a.nearby_agents,
            "pathogen": round(a.pathogen_load, 4),
        }
        for a in obs_agents
    ]
    if vision:
        payload["vision_cones"] = [
            {
                "row": vc.row, "x": vc.center_x_m, "y": vc.center_y_m,
                "r": vc.radius_m,
                "see": vc.visible_agent_rows,
                "uuids": vc.visible_uuids,
            }
            for vc in vision
        ]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return snap


def append_observable_jsonl(sim, out_path: str, *,
                            perception_radius_m: float = DEFAULT_PERCEPTION_RADIUS_M,
                            include_vision_cones: bool = False,
                            ) -> Dict[str, Any]:
    """Append one compact JSON line per call (streaming observers)."""
    agents = sim.agents
    n = agents.n_active
    compact = []
    for row in range(n):
        if not bool(agents.alive[row]):
            continue
        compact.append({
            "row": int(row),
            "x": round(float(agents.pos[row, 0]), 2),
            "y": round(float(agents.pos[row, 1]), 2),
            "v": round(float(agents.vitality[row]), 3),
        })
    line: Dict[str, Any] = {
        "tick": int(sim.tick),
        "sim_id": str(sim.sim_id),
        "n_alive": len(compact),
        "agents_compact": compact,
    }
    if include_vision_cones:
        cones = export_all_vision_cones(sim, perception_radius_m=perception_radius_m)
        line["vision_cones"] = [
            {"row": vc.row, "see": vc.visible_agent_rows}
            for vc in cones
        ]
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, separators=(",", ":")) + "\n")
    return line


def observable_summary(snap: ObservableSnapshot) -> Dict[str, Any]:
    """Aggregate stats for smokes / logging."""
    if not snap.agents:
        return {"n_alive": 0}
    vit = [a.vitality for a in snap.agents]
    near = [a.nearby_agents for a in snap.agents]
    return {
        "tick": snap.tick,
        "n_alive": snap.n_alive,
        "mean_vitality": round(float(np.mean(vit)), 4),
        "max_nearby": int(max(near)),
        "mean_nearby": round(float(np.mean(near)), 2),
        "cultures": len({a.culture_id for a in snap.agents}),
    }


__all__ = [
    "AgentObservable",
    "VisionCone",
    "ObservableSnapshot",
    "observe_agent_row",
    "export_vision_cone",
    "export_all_vision_cones",
    "export_observable_snapshot",
    "append_observable_jsonl",
    "observable_summary",
    "genesis_observable_meta",
    "DEFAULT_PERCEPTION_RADIUS_M",
]
