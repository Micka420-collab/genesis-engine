"""Genesis Engine — Wave 11 elite cognitive metrics (Veille 2026-05-15).

Inspiration : arxiv "Do Agent Societies Develop Intellectual Elites?
The Hidden Power Laws of Collective Cognition in LLM Multi-Agent Systems"
(April 2026).

Hypothèse H0-derivative : si des civilisations émergent réellement
*sans script*, leurs distributions cognitives devraient suivre une
loi de puissance (Pareto) sur le skill agrégé. On mesure :

  • skill_proxy(i) = 0.5 * intelligence[i] + 0.5 * conscientiousness[i]
  • Par culture :
        n_alive, mean, std,
        gini      ∈ [0, 1] (égalité parfaite → 0)
        top10_pct ∈ ratio top10% / médiane
        alpha     = estimateur de Hill (queue) si n ≥ 8

Pas de mutation d'état sim, pas d'événement forcé. Pur observateur,
journalisé via `log_elite_metrics()` → JSONL append.

Déterminisme : aucun appel à un PRNG ; lecture seule des arrays
NumPy. Bit-identique sous SHA-256 sur seed identique.
"""
from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Optional

import numpy as np


_SKILL_W_INTELLIGENCE = 0.5
_SKILL_W_CONSCIENTIOUSNESS = 0.5


def _skill_proxy(agents, alive_idx: np.ndarray) -> np.ndarray:
    intel = agents.intelligence[alive_idx]
    cons = agents.conscientiousness[alive_idx]
    return (_SKILL_W_INTELLIGENCE * intel
            + _SKILL_W_CONSCIENTIOUSNESS * cons).astype(np.float64)


def _gini(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    x = np.sort(np.asarray(x, dtype=np.float64))
    if x[-1] <= 0.0:
        return 0.0
    n = x.size
    cum = np.cumsum(x)
    denom = float(cum[-1]) * n
    if denom <= 0.0:
        return 0.0
    g = (n + 1 - 2.0 * float((cum.sum())) / float(cum[-1])) / n
    return max(0.0, min(1.0, float(g)))


def _top10_ratio(x: np.ndarray) -> float:
    if x.size < 4:
        return float("nan")
    x_sorted = np.sort(np.asarray(x, dtype=np.float64))
    median = float(np.median(x_sorted))
    if median <= 0.0:
        return float("nan")
    cutoff = max(1, int(math.ceil(x_sorted.size * 0.10)))
    top = x_sorted[-cutoff:]
    return float(top.mean() / median)


def _hill_alpha(x: np.ndarray) -> float:
    """Hill tail-index estimator (lower tail truncated at median).

    α ≈ 1 + n / Σ log(x_i / x_min). Returns NaN if degenerate.
    """
    if x.size < 8:
        return float("nan")
    x = np.asarray(x, dtype=np.float64)
    x_min = float(np.median(x))
    tail = x[x > x_min]
    if tail.size < 4:
        return float("nan")
    ratios = tail / x_min
    if (ratios <= 0.0).any():
        return float("nan")
    s = float(np.log(ratios).sum())
    if s <= 0.0:
        return float("nan")
    return 1.0 + float(tail.size) / s


def compute_elite_metrics(sim) -> Dict[int, Dict]:
    """Return per-culture metric dict, keyed by culture_id (int).

    No mutation of sim state. Safe to call at any tick.
    """
    agents = sim.agents
    n = agents.n_active
    if n <= 0:
        return {}
    alive_mask = agents.alive[:n]
    alive_idx = np.flatnonzero(alive_mask)
    if alive_idx.size == 0:
        return {}

    skills = _skill_proxy(agents, alive_idx)
    cult_ids = np.array(
        [agents.relations[int(i)].culture_id for i in alive_idx],
        dtype=np.int32,
    )
    result: Dict[int, Dict] = {}
    for cid in np.unique(cult_ids):
        mask = cult_ids == cid
        s = skills[mask]
        if s.size == 0:
            continue
        result[int(cid)] = {
            "n_alive": int(s.size),
            "mean": float(s.mean()),
            "std": float(s.std()),
            "gini": _gini(s),
            "top10_median_ratio": _top10_ratio(s),
            "hill_alpha": _hill_alpha(s),
        }
    return result


def log_elite_metrics(sim, journal_path: str,
                      extra: Optional[Dict] = None) -> Dict:
    """Append a JSONL entry with current metrics. Returns the entry."""
    metrics = compute_elite_metrics(sim)
    entry = {
        "tick": int(sim.tick),
        "alive": int(sim.agents.alive[:sim.agents.n_active].sum()),
        "cultures": {str(k): v for k, v in metrics.items()},
    }
    if extra:
        entry["extra"] = extra
    os.makedirs(os.path.dirname(os.path.abspath(journal_path)), exist_ok=True)
    with open(journal_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True, ensure_ascii=False))
        fh.write("\n")
    return entry


def detect_power_law(metrics_by_culture: Dict[int, Dict],
                     alpha_min: float = 1.2,
                     alpha_max: float = 4.0) -> Dict[int, bool]:
    """Heuristic : a culture exhibits power-law tail if α ∈ [alpha_min,
    alpha_max] and gini > 0.05 (some inequality)."""
    out: Dict[int, bool] = {}
    for cid, m in metrics_by_culture.items():
        a = m.get("hill_alpha", float("nan"))
        g = m.get("gini", 0.0)
        plausible = (
            isinstance(a, float)
            and not math.isnan(a)
            and alpha_min <= a <= alpha_max
            and g > 0.05
        )
        out[int(cid)] = bool(plausible)
    return out


__all__ = [
    "compute_elite_metrics",
    "log_elite_metrics",
    "detect_power_law",
    "compute_elite_metrics_effective",
]


# ---------------------------------------------------------------------------
# Wave 12 — effective skill (intelligence_base + learned_skill).
# Pure additive helper : the original `compute_elite_metrics` keeps its
# bit-identical signature & semantics. This new function reads the
# plasticity buffer if installed, else falls back to the base proxy.
# ---------------------------------------------------------------------------

def _skill_proxy_effective(agents, alive_idx: np.ndarray, sim) -> np.ndarray:
    intel_base = agents.intelligence[alive_idx].astype(np.float64)
    state = getattr(sim, "plasticity", None)
    if state is None:
        bonus = np.zeros_like(intel_base)
    else:
        # learned_skill is per-capacity ; index by alive_idx directly.
        bonus = state.learned_skill[alive_idx].astype(np.float64)
    intel_eff = np.clip(intel_base + bonus, 0.0, 1.0)
    cons = agents.conscientiousness[alive_idx].astype(np.float64)
    return _SKILL_W_INTELLIGENCE * intel_eff + _SKILL_W_CONSCIENTIOUSNESS * cons


def compute_elite_metrics_effective(sim) -> Dict[int, Dict]:
    """Same shape as :func:`compute_elite_metrics`, but uses
    :func:`engine.cognitive_plasticity.intelligence_effective` per agent.

    Drop-in replacement for dashboards / sprint reports that want to
    track elite emergence *post-learning* rather than purely genetic.
    """
    agents = sim.agents
    n = agents.n_active
    if n <= 0:
        return {}
    alive_mask = agents.alive[:n]
    alive_idx = np.flatnonzero(alive_mask)
    if alive_idx.size == 0:
        return {}

    skills = _skill_proxy_effective(agents, alive_idx, sim)
    cult_ids = np.array(
        [agents.relations[int(i)].culture_id for i in alive_idx],
        dtype=np.int32,
    )
    result: Dict[int, Dict] = {}
    for cid in np.unique(cult_ids):
        mask = cult_ids == cid
        s = skills[mask]
        if s.size == 0:
            continue
        result[int(cid)] = {
            "n_alive": int(s.size),
            "mean": float(s.mean()),
            "std": float(s.std()),
            "gini": _gini(s),
            "top10_median_ratio": _top10_ratio(s),
            "hill_alpha": _hill_alpha(s),
        }
    return result
