"""Memetic diffusion — imitation culturelle locale (ZERO PRE-SCRIPT).

Quand un agent émet SPEAK, les voisins peuvent assimiler une fraction de son
lexique (16-D). Pas de symboles imposés : pression = proximité + empathie.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np

from engine.agent import ActionKind
from engine.core import prf_rng

IMITATION_RADIUS_M = 28.0
LEXICON_DIM = 16


@dataclass
class MemeticState:
    imitations_total: int = 0
    imitations_last_tick: int = 0
    speakers_last_tick: int = 0
    mean_lexicon_drift: float = 0.0


def _near_rows(sim, row: int) -> List[int]:
    agents = sim.agents
    px = float(agents.pos[row, 0])
    py = float(agents.pos[row, 1])
    grid = sim._grid
    out: List[int] = []
    for j in grid.query_disk(px, py, IMITATION_RADIUS_M, exclude_row=row):
        j = int(j)
        if j == row or not agents.alive[j]:
            continue
        out.append(j)
    return out


def tick_memetic(sim) -> None:
    """Post-action memetic blend (call once per tick after decisions applied)."""
    st: MemeticState = getattr(sim, "_memetic", None)
    if st is None:
        return
    st.imitations_last_tick = 0
    st.speakers_last_tick = 0
    agents = sim.agents
    n = int(agents.n_active)
    drifts: List[float] = []

    for row in range(n):
        if not agents.alive[row]:
            continue
        if int(agents.action[row]) != int(ActionKind.SPEAK):
            continue
        st.speakers_last_tick += 1
        src = agents.lexicon[row].astype(np.float32)
        for j in _near_rows(sim, row):
            rng = prf_rng(
                int(sim.cfg.seed),
                ["memetic", "imitate"],
                [int(sim.tick), row, j],
            )
            empathy = float(agents.empathy[j])
            base_rate = 0.018 + 0.04 * empathy
            rate = float(np.clip(base_rate * (0.85 + 0.3 * rng.random()), 0.005, 0.12))
            dst = agents.lexicon[j].astype(np.float32)
            before = dst.copy()
            agents.lexicon[j] = np.clip((1.0 - rate) * dst + rate * src, 0.0, 1.0)
            drifts.append(float(np.linalg.norm(agents.lexicon[j] - before)))
            st.imitations_last_tick += 1
            st.imitations_total += 1

    st.mean_lexicon_drift = float(np.mean(drifts)) if drifts else 0.0


def install_memetic_engine(sim) -> MemeticState:
    """Patch ``sim.step`` once to run memetic tick after the main step."""
    existing = getattr(sim, "_memetic", None)
    if existing is not None:
        return existing
    st = MemeticState()
    sim._memetic = st
    if getattr(sim, "_memetic_step_patched", False):
        return st
    sim._memetic_step_patched = True
    orig = sim.step

    def wrapped():
        stats = orig()
        tick_memetic(sim)
        return stats

    sim.step = wrapped
    return st


def memetic_snapshot(sim) -> Dict[str, Any]:
    st: MemeticState = getattr(sim, "_memetic", None)
    if st is None:
        return {}
    return {
        "imitations_total": int(st.imitations_total),
        "imitations_last_tick": int(st.imitations_last_tick),
        "speakers_last_tick": int(st.speakers_last_tick),
        "mean_lexicon_drift": round(st.mean_lexicon_drift, 5),
        "radius_m": IMITATION_RADIUS_M,
    }


__all__ = [
    "MemeticState",
    "install_memetic_engine",
    "tick_memetic",
    "memetic_snapshot",
]
