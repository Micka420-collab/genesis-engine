"""Batch agent positions for scale (Python fallback; Rust ECS target).

EMERGENCE SIM v2 §10 — hot path for thousands of agents should move to
``god-engine`` ECS + optional WebGPU instancing. See also ``agent_ecs_batch``.
"""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def snapshot_positions_lite(sim) -> Dict[str, Any]:
    """Minimal payload: row, x, y, culture, action, generation."""
    a = sim.agents
    n = int(a.n_active)
    if n == 0:
        return {"tick": int(sim.tick), "agents": []}
    alive = a.alive[:n]
    rows = np.nonzero(alive)[0]
    agents: List[Dict[str, Any]] = []
    for row in rows:
        agents.append({
            "row": int(row),
            "x": float(a.pos[row, 0]),
            "y": float(a.pos[row, 1]),
            "c": int(a.relations[row].culture_id),
            "a": int(a.action[row]) if hasattr(a, "action") else 0,
            "g": int(a.generation[row]),
        })
    return {"tick": int(sim.tick), "agents": agents}


def snapshot_positions_lite_with_vel(sim) -> Dict[str, Any]:
    """Lite JSON + vitesse + présence humaine (posture, peau, outil)."""
    from engine.agent_presence import enrich_lite_agent

    out = snapshot_positions_lite(sim)
    a = sim.agents
    n = int(a.n_active)
    if not out.get("agents"):
        return out
    rows = {ag["row"]: i for i, ag in enumerate(out["agents"])}
    for row, idx in rows.items():
        if row < n and a.alive[row]:
            ag = out["agents"][idx]
            ag["vx"] = round(float(a.vel[row, 0]), 3)
            ag["vy"] = round(float(a.vel[row, 1]), 3)
            enrich_lite_agent(sim, ag)
    return out


__all__ = ["snapshot_positions_lite", "snapshot_positions_lite_with_vel"]
