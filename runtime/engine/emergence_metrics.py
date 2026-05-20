"""EMERGENCE SIM v2 — observables only (ZERO PRE-SCRIPT).

Computes civilization emergence KPIs from simulation state without
injecting goals or scripted outcomes. Used by Earth Console and artifacts.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, List, Optional

import numpy as np


def _gini(values: np.ndarray) -> float:
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return 0.0
    v = np.sort(v)
    if v[-1] <= 0:
        return 0.0
    n = v.size
    idx = np.arange(1, n + 1, dtype=np.float64)
    return float((2 * np.dot(idx, v) / (n * v.sum())) - (n + 1) / n)


def _shannon_entropy(counts: Dict[str, int]) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    ent = 0.0
    for c in counts.values():
        if c <= 0:
            continue
        p = c / total
        ent -= p * math.log2(p)
    return float(ent)


def genetic_complexity_mean(sim) -> float:
    """Mean L2 norm of alive agents' genomes (proxy for genetic diversity)."""
    agents = sim.agents
    genome = getattr(agents, "genome", None)
    if genome is None or not getattr(agents, "_genome_attached", False):
        return 0.0
    n = agents.n_active
    alive = np.flatnonzero(agents.alive[:n])
    if alive.size == 0:
        return 0.0
    norms = []
    G = genome.values
    for row in alive:
        norms.append(float(np.linalg.norm(G[int(row)])))
    return float(np.mean(norms)) if norms else 0.0


def communication_entropy(sim, *, journal_tail: Optional[List[dict]] = None) -> float:
    """Shannon entropy over Annalist event kinds (recent tail or cum counters)."""
    if journal_tail:
        kinds = Counter(str(e.get("kind", "?")) for e in journal_tail)
        return _shannon_entropy(dict(kinds))
    a = sim.annalist
    kinds = Counter()
    kinds["birth"] = int(a.cum_births)
    kinds["death"] = int(a.cum_deaths)
    kinds["fight"] = int(a.cum_fights)
    kinds["share"] = int(a.cum_shares)
    kinds["mating"] = int(a.cum_matings)
    kinds["trade"] = int(a.cum_trades)
    kinds["vocalization"] = int(a.cum_vocalizations)
    kinds["founding"] = int(a.cum_foundings)
    return _shannon_entropy({k: v for k, v in kinds.items() if v > 0})


def wealth_gini(sim) -> float:
    """Gini on combined inventory wealth (food+stone+water+wood) per alive agent."""
    agents = sim.agents
    n = agents.n_active
    alive = agents.alive[:n]
    if not alive.any():
        return 0.0
    wealth = (
        agents.inv_food[:n][alive]
        + agents.inv_stone[:n][alive]
        + agents.inv_water[:n][alive]
        + agents.inv_wood[:n][alive]
    )
    return _gini(wealth.astype(np.float64))


def technologies_discovered(sim) -> int:
    reg = getattr(sim, "invention_registry", None)
    if reg is None:
        return 0
    return int(len(getattr(reg, "artifacts", {}) or {}))


def structures_diversity(sim) -> int:
    """Distinct invented artifacts + active build projects."""
    n = technologies_discovered(sim)
    projects = getattr(sim, "_build_projects", None) or getattr(sim, "build_projects", None)
    if projects is not None:
        try:
            n += len(projects)
        except TypeError:
            pass
    return int(n)


def terraformed_ratio(sim) -> float:
    """Share of cultivated macro cells vs land (0..1), if agriculture wired."""
    try:
        from engine.agriculture import agriculture_state
        ag = agriculture_state(sim)
    except Exception:
        return 0.0
    if not ag:
        return 0.0
    n_chunks = float(ag.get("n_cultivated_chunks", 0) or 0)
    if n_chunks <= 0:
        return 0.0
    n_stream = max(1, len(getattr(sim.streamer, "cache", {}) or {}))
    return float(min(1.0, n_chunks / n_stream))


def population_alive(sim) -> int:
    return int(sim.agents.alive[: sim.agents.n_active].sum())


def compute_emergence_metrics(
    sim,
    *,
    journal_tail: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    """Full emergence KPI block for API / Earth Console (read-only observables)."""
    return {
        "tick": int(sim.tick),
        "population_alive": population_alive(sim),
        "genetic_complexity_mean": round(genetic_complexity_mean(sim), 4),
        "communication_entropy": round(communication_entropy(sim, journal_tail=journal_tail), 4),
        "structures_diversity": structures_diversity(sim),
        "terraformed_ratio": round(terraformed_ratio(sim), 4),
        "technologies_discovered": technologies_discovered(sim),
        "wealth_gini": round(wealth_gini(sim), 4),
        "philosophy": "ZERO_PRE_SCRIPT",
        "layers": ["L0_PHYSICS", "L1_WORLD", "L2_BIOLOGY", "L3_COGNITION", "L4_CIVILIZATION"],
    }


def tick_emergence_metrics(sim, st, *, journal_tail: Optional[List[dict]] = None) -> None:
    """Refresh cached metrics on emergence state (no side effects on agents)."""
    st.last_emergence_metrics = compute_emergence_metrics(sim, journal_tail=journal_tail)


__all__ = [
    "compute_emergence_metrics",
    "tick_emergence_metrics",
    "genetic_complexity_mean",
    "communication_entropy",
    "wealth_gini",
]
