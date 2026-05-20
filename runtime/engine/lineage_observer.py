"""Genesis Engine — Wave 40 lineage / genetics observer.

Observer **read-only** des lignées familiales émergentes. Aucune
modification de la sim : on lit ce que ``engine.agent`` produit déjà.

Pré-requis existant
-------------------

``AgentRegistry.spawn_offspring`` (Wave A4 / Sprint génétique) fait
déjà tout le travail :

- ``agents.parents[row] = (pa, pb)``     → arbre généalogique
- ``agents.generation[row]``             → max(parents.gen) + 1
- ``agents.offspring_count[pa] += 1``    → reproductive success
- Big-Five inherités : ``child = (pa + pb)/2 + N(0, σ=0.05)``
- Lexicon inheritance : idem
- ``relations[pa].children.append(row)`` → bidirectionnel

Wave 40 ne fait que **lire et résumer**.

API
---

- ``observe_lineage(sim)``       — snapshot complet (founders, families,
                                    generation distribution, ...)
- ``build_family_tree(sim, root_row)`` — ancêtres + descendants
- ``trait_drift_by_generation`` — variance Big-Five par génération
- ``inbreeding_coefficient(sim, row)`` — Wright's F approximation
- ``install_lineage_observer(sim)`` — wrap sim.step pour snapshots

Determinism
-----------

Read-only sur les arrays agents. Aucun RNG. Snapshots reproductibles à
100 % pour le même seed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np


PIPELINE_LAYER = "Genesis-L5 Observer"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# Big-Five + Genesis personality traits inherited at spawn_offspring.
TRAIT_NAMES: Tuple[str, ...] = (
    "openness", "conscientiousness", "extraversion", "agreeableness",
    "neuroticism", "ambition", "risk_tolerance", "aggression",
    "curiosity", "empathy", "intelligence",
)

# Founder sentinel : parents == (-1, -1) or unset.
FOUNDER_PARENT_SENTINEL = -1


# ---------------------------------------------------------------------------
# Configuration + data types
# ---------------------------------------------------------------------------

@dataclass
class LineageConfig:
    snapshot_every: int = 50
    track_traits: Tuple[str, ...] = TRAIT_NAMES


@dataclass
class FamilyEdge:
    parent: int
    child: int


@dataclass
class LineageSnapshot:
    tick: int
    n_alive: int = 0
    n_total_ever: int = 0
    n_founders: int = 0
    n_descendants: int = 0
    max_generation: int = 0
    generation_counts: Dict[int, int] = field(default_factory=dict)
    # Trait variance par génération : detect drift due to selection.
    trait_mean_by_gen: Dict[int, Dict[str, float]] = field(default_factory=dict)
    trait_std_by_gen: Dict[int, Dict[str, float]] = field(default_factory=dict)
    # Top reproducer (highest offspring_count).
    top_reproducer_row: int = -1
    top_reproducer_offspring: int = 0
    # Founder line tracking.
    founder_descendants_count: Dict[int, int] = field(default_factory=dict)


@dataclass
class LineageHistory:
    config: LineageConfig
    snapshots: List[LineageSnapshot] = field(default_factory=list)
    n_ticks_run: int = 0


@dataclass
class LineageObserverState:
    config: LineageConfig
    history: LineageHistory
    last_snapshot_tick: int = -1


# ---------------------------------------------------------------------------
# Pure-function observation
# ---------------------------------------------------------------------------

def _get_parents_array(sim) -> np.ndarray:
    """Lit ``sim.agents.parents`` — Python list de tuples
    ``[(None, None), (pa, pb), ...]`` — et le convertit en (N, 2)
    int32 avec ``FOUNDER_PARENT_SENTINEL=-1`` pour les founders.
    """
    parents_list = getattr(sim.agents, "parents", None)
    if parents_list is None:
        return np.full((0, 2), FOUNDER_PARENT_SENTINEL, dtype=np.int32)
    n = len(parents_list)
    arr = np.full((n, 2), FOUNDER_PARENT_SENTINEL, dtype=np.int32)
    for i, tup in enumerate(parents_list):
        if tup is None:
            continue
        try:
            a, b = tup
        except (TypeError, ValueError):
            continue
        if a is not None:
            arr[i, 0] = int(a)
        if b is not None:
            arr[i, 1] = int(b)
    return arr


def _get_generation_array(sim) -> np.ndarray:
    arr = getattr(sim.agents, "generation", None)
    if arr is None:
        return np.zeros(0, dtype=np.int32)
    return np.asarray(arr).astype(np.int32)


def _get_offspring_count_array(sim) -> np.ndarray:
    arr = getattr(sim.agents, "offspring_count", None)
    if arr is None:
        return np.zeros(0, dtype=np.int32)
    return np.asarray(arr).astype(np.int32)


def is_founder(sim, row: int) -> bool:
    """An agent is a founder iff its parents tuple is (-1, -1) or missing."""
    parents = _get_parents_array(sim)
    if row >= len(parents):
        return False
    pa, pb = int(parents[row][0]), int(parents[row][1])
    return pa == FOUNDER_PARENT_SENTINEL or pb == FOUNDER_PARENT_SENTINEL


def build_ancestors(sim, row: int, *, max_depth: int = 20) -> Set[int]:
    """Return all transitive ancestors of ``row``. Pure read-only walk."""
    parents = _get_parents_array(sim)
    if row >= len(parents):
        return set()
    ancestors: Set[int] = set()
    frontier: List[Tuple[int, int]] = [(row, 0)]
    while frontier:
        r, depth = frontier.pop()
        if depth >= max_depth:
            continue
        if r >= len(parents):
            continue
        pa, pb = int(parents[r][0]), int(parents[r][1])
        for p in (pa, pb):
            if p != FOUNDER_PARENT_SENTINEL and p not in ancestors and p >= 0:
                ancestors.add(p)
                frontier.append((p, depth + 1))
    return ancestors


def build_descendants(sim, row: int, *, max_depth: int = 20) -> Set[int]:
    """Return all transitive descendants of ``row``."""
    parents = _get_parents_array(sim)
    n = len(parents)
    if n == 0:
        return set()
    # Reverse adjacency : for each row, who claims it as parent.
    children_of: Dict[int, List[int]] = {}
    for i in range(n):
        for p in (int(parents[i][0]), int(parents[i][1])):
            if p != FOUNDER_PARENT_SENTINEL and p >= 0:
                children_of.setdefault(p, []).append(i)
    descendants: Set[int] = set()
    frontier: List[Tuple[int, int]] = [(row, 0)]
    while frontier:
        r, depth = frontier.pop()
        if depth >= max_depth:
            continue
        for c in children_of.get(r, []):
            if c not in descendants:
                descendants.add(c)
                frontier.append((c, depth + 1))
    return descendants


def inbreeding_coefficient(sim, row: int) -> float:
    """Wright's F approximation : 0 if no common ancestor between parents,
    closer to 0.25 for siblings, 0.0625 for first cousins, etc.

    Implémentation simple : si les deux parents partagent ≥1 ancêtre
    commun, F ≈ 1/2^(distance + 1). Sans timing exact, on retourne 0.0
    si pas commun, 0.25 si frère/sœur (parents directs partagés),
    0.0625 cousin-germain.
    """
    parents = _get_parents_array(sim)
    if row >= len(parents):
        return 0.0
    pa, pb = int(parents[row][0]), int(parents[row][1])
    if pa == FOUNDER_PARENT_SENTINEL or pb == FOUNDER_PARENT_SENTINEL:
        return 0.0
    anc_a = build_ancestors(sim, pa) | {pa}
    anc_b = build_ancestors(sim, pb) | {pb}
    common = anc_a & anc_b
    if not common:
        return 0.0
    # If parents themselves share a parent → child is product of siblings.
    parents_a_set = {int(parents[pa][0]), int(parents[pa][1])} if pa < len(parents) else set()
    parents_b_set = {int(parents[pb][0]), int(parents[pb][1])} if pb < len(parents) else set()
    if parents_a_set & parents_b_set & {x for x in parents_a_set if x != FOUNDER_PARENT_SENTINEL}:
        return 0.25  # full siblings → F=0.25 for the offspring
    # Otherwise some more distant overlap → first cousins F=0.0625
    return 0.0625


def observe_lineage(sim,
                      cfg: Optional[LineageConfig] = None
                      ) -> LineageSnapshot:
    """Pure read-only snapshot at the current sim tick."""
    cfg = cfg or LineageConfig()
    snap = LineageSnapshot(tick=int(sim.tick))
    n = sim.agents.n_active
    if n == 0:
        return snap
    alive = sim.agents.alive[:n].astype(bool)
    snap.n_alive = int(alive.sum())
    snap.n_total_ever = int(n)

    parents = _get_parents_array(sim)[:n]
    generation = _get_generation_array(sim)[:n]
    offspring_count = _get_offspring_count_array(sim)[:n]

    is_founder_mask = (parents[:, 0] == FOUNDER_PARENT_SENTINEL) | \
                        (parents[:, 1] == FOUNDER_PARENT_SENTINEL)
    snap.n_founders = int(is_founder_mask.sum())
    snap.n_descendants = int(n - snap.n_founders)
    snap.max_generation = int(generation.max()) if n > 0 else 0

    # Generation distribution.
    for g_val in range(int(generation.max()) + 1 if n > 0 else 0):
        count = int((generation == g_val).sum())
        if count > 0:
            snap.generation_counts[g_val] = count

    # Per-generation trait stats.
    for g_val in snap.generation_counts:
        mask = (generation == g_val)
        if not mask.any():
            continue
        mean_dict: Dict[str, float] = {}
        std_dict: Dict[str, float] = {}
        for trait in cfg.track_traits:
            arr = getattr(sim.agents, trait, None)
            if arr is None:
                continue
            vals = np.asarray(arr[:n])[mask]
            if vals.size == 0:
                continue
            mean_dict[trait] = float(vals.mean())
            std_dict[trait] = float(vals.std())
        snap.trait_mean_by_gen[g_val] = mean_dict
        snap.trait_std_by_gen[g_val] = std_dict

    # Top reproducer.
    if offspring_count.size > 0 and offspring_count.max() > 0:
        top_idx = int(np.argmax(offspring_count))
        snap.top_reproducer_row = top_idx
        snap.top_reproducer_offspring = int(offspring_count[top_idx])

    # Founder descendants count.
    if snap.n_founders > 0:
        founder_indices = np.where(is_founder_mask)[0]
        for fi in founder_indices:
            descs = build_descendants(sim, int(fi))
            snap.founder_descendants_count[int(fi)] = len(descs)

    return snap


# ---------------------------------------------------------------------------
# Sim integration (wraps sim.step like Wave 33 / 39)
# ---------------------------------------------------------------------------

def install_lineage_observer(sim,
                                cfg: Optional[LineageConfig] = None
                                ) -> LineageObserverState:
    """Idempotent installer. Wraps ``sim.step`` to capture snapshots."""
    cfg = cfg or LineageConfig()
    existing: Optional[LineageObserverState] = getattr(
        sim, "_lineage_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = LineageObserverState(
        config=cfg, history=LineageHistory(config=cfg))
    sim._lineage_state = state

    if getattr(sim, "_lineage_wrapped", False):
        return state
    sim._lineage_wrapped = True
    original_step = sim.step

    def wrapped_step():
        stats = original_step()
        st: LineageObserverState = sim._lineage_state
        cfg_now = st.config
        if (sim.tick - st.last_snapshot_tick) >= cfg_now.snapshot_every:
            snap = observe_lineage(sim, cfg_now)
            st.history.snapshots.append(snap)
            st.last_snapshot_tick = int(sim.tick)
            st.history.n_ticks_run = int(sim.tick)
        return stats

    sim.step = wrapped_step
    return state


def uninstall_lineage_observer(sim) -> bool:
    if hasattr(sim, "_lineage_state"):
        delattr(sim, "_lineage_state")
        return True
    return False


def lineage_state_summary(sim) -> Dict[str, object]:
    state: Optional[LineageObserverState] = getattr(
        sim, "_lineage_state", None)
    if state is None:
        snap = observe_lineage(sim)
        return {
            "installed": False,
            "snapshot_now": {
                "tick": snap.tick,
                "n_alive": snap.n_alive,
                "n_founders": snap.n_founders,
                "n_descendants": snap.n_descendants,
                "max_generation": snap.max_generation,
                "generation_counts": snap.generation_counts,
            },
        }
    last = state.history.snapshots[-1] if state.history.snapshots else None
    if last is None:
        return {"installed": True, "n_snapshots": 0}
    return {
        "installed": True,
        "n_snapshots": len(state.history.snapshots),
        "n_ticks_run": state.history.n_ticks_run,
        "last_tick": last.tick,
        "n_alive": last.n_alive,
        "n_founders": last.n_founders,
        "n_descendants": last.n_descendants,
        "max_generation": last.max_generation,
        "generation_counts": last.generation_counts,
        "top_reproducer_row": last.top_reproducer_row,
        "top_reproducer_offspring": last.top_reproducer_offspring,
        "founder_descendants_count": last.founder_descendants_count,
        "trait_mean_at_max_gen": last.trait_mean_by_gen.get(
            last.max_generation, {}),
    }


__all__ = [
    "TRAIT_NAMES", "FOUNDER_PARENT_SENTINEL",
    "LineageConfig", "LineageSnapshot", "LineageHistory",
    "LineageObserverState", "FamilyEdge",
    "is_founder", "build_ancestors", "build_descendants",
    "inbreeding_coefficient",
    "observe_lineage",
    "install_lineage_observer", "uninstall_lineage_observer",
    "lineage_state_summary",
]
