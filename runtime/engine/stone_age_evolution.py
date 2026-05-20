"""Genesis Engine — Wave 33 stone-age evolution observer.

Harness pour lancer la simulation depuis l'âge de pierre et **observer
read-only** ce qui émerge, **sans rien scripter**.

Règle invariante (rappelée par l'utilisateur 2026-05-18) : tout doit
émerger comme à l'apparition de la vie sur Terre. Les agents stone-age
décident eux-mêmes par leur cognition (engine.cognition PIANO). Aucun
solveur top-down ne prédit où seront les villes, les routes, les
trades, les cultures, les polities. Ces phénomènes émergent ; on ne
fait que les OBSERVER.

Architecture
------------

```
1. bootstrap_genesis_sim(sim)
       → world tectonique + chunk anchor + macro climat
       (Waves 16-19 fournissent le substrate, c'est de la géologie pure)

2. install_geology + install_meteorology + install_marine + install_wildfire
   + install_agriculture + install_writing + install_polity + install_invention
   + install_cognitive_plasticity + install_communication + ...
       → tout l'engine émergent agent-driven s'active

3. for year in range(n_years):
       for tick in range(ticks_per_year):
           sim.step()
       observe(sim) → snapshot
```

Les ``observe_*`` fonctions sont **read-only** : elles lisent l'état
des modules existants (positions agents, polity state, invention
registry, lexicon, …) et en font un résumé. Aucune mutation.

Détectables comme phénomènes émergents :

- **Settlements émergents** = clusters d'agents (DBSCAN-like sur
  positions). Pas pré-calculés, on les observe.
- **Trails émergents** = densité cumulative de passage agent par chunk.
- **Polities émergentes** = leaders élus par `engine.polity` Wave 9c
  via prestige/ambition. Existe déjà depuis Phase 4.
- **Inventions émergentes** = artifacts créés par `engine.invention`
  via curiosity × material.
- **Language émergent** = lexicons par culture, observe le drift.
- **Buildings émergents** = archetypes créés par `engine.building_discovery`.
- **Agriculture émergente** = seeds découvertes par forage
  (`engine.agriculture.maybe_record_forage_discovery`).
- **Metallurgy émergente** = smelting d'ore en éléments purs.

Pas de timeline scriptée. Si une civilisation n'atteint jamais l'âge
du bronze, c'est parce que ses agents n'ont pas découvert le smelt —
pas parce que le script l'a décidé. C'est ça l'expérience scientifique.

Déterminisme : entièrement piloté par `prf_rng((sim_seed, ...), [...])`.
Deux runs avec la même seed produisent les mêmes trajectoires.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


PIPELINE_LAYER = "Genesis-L5 Observer"
WORLD_MODEL_CAPABILITY = "paper-L3 Simulator"


# ---------------------------------------------------------------------------
# Configuration + snapshot types
# ---------------------------------------------------------------------------

@dataclass
class StoneAgeConfig:
    """Hyper-parameters of the evolution observer.

    ``n_years_sim`` is the number of *simulated* years (not real-time).
    With ``drive_accel = 1500`` (Genesis default), 1 sim-year ≈
    ~36 sim-seconds × 1500 / (86400 × 365) … actually the engine ticks
    in sim-seconds × drive_accel. See the engine internals for exact
    timing.
    """
    n_ticks: int = 200             # total ticks to run
    snapshot_every: int = 20       # ticks between snapshots
    cluster_radius_m: float = 80.0  # DBSCAN-style cluster radius
    cluster_min_pts: int = 2
    trail_grid_cell_m: float = 32.0  # observe trail density at chunk scale


@dataclass
class AgentSnapshot:
    """One per-tick observation of all agents."""
    tick: int
    n_alive: int
    positions: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))  # (N, 2)
    cultures: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.int32))  # (N,) culture id
    intelligence: np.ndarray = field(default_factory=lambda: np.empty(0))
    age: np.ndarray = field(default_factory=lambda: np.empty(0))


@dataclass
class ClusterObservation:
    """One emergent cluster (proto-settlement)."""
    cluster_id: int
    n_agents: int
    center_x_m: float
    center_y_m: float
    radius_m: float
    cultures: List[int] = field(default_factory=list)


@dataclass
class EvolutionSnapshot:
    """Full read-only snapshot at one tick."""
    tick: int
    agents: AgentSnapshot
    clusters: List[ClusterObservation] = field(default_factory=list)
    polities: Dict[str, Any] = field(default_factory=dict)
    inventions: Dict[str, Any] = field(default_factory=dict)
    buildings: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    languages: Dict[str, Any] = field(default_factory=dict)
    inscriptions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvolutionHistory:
    """Full trajectory of an evolution run."""
    config: StoneAgeConfig
    snapshots: List[EvolutionSnapshot] = field(default_factory=list)
    trail_density: Optional[np.ndarray] = None  # (RY, RX) cumulative
    seed: int = 0
    n_ticks_run: int = 0


# ---------------------------------------------------------------------------
# Read-only observation functions
# ---------------------------------------------------------------------------

def observe_agents(sim) -> AgentSnapshot:
    """Snapshot of all alive agents — pure read-only."""
    n = sim.agents.n_active
    alive_mask = sim.agents.alive[:n].astype(bool)
    pos = sim.agents.pos[:n, :2][alive_mask].copy().astype(np.float32)
    culture = sim.agents.culture_id[:n][alive_mask].copy().astype(np.int32) \
        if hasattr(sim.agents, "culture_id") else np.zeros(int(alive_mask.sum()),
                                                              dtype=np.int32)
    intel = sim.agents.intelligence[:n][alive_mask].copy().astype(np.float32) \
        if hasattr(sim.agents, "intelligence") else np.zeros(int(alive_mask.sum()),
                                                                 dtype=np.float32)
    age = sim.agents.age[:n][alive_mask].copy().astype(np.float32) \
        if hasattr(sim.agents, "age") else np.zeros(int(alive_mask.sum()),
                                                        dtype=np.float32)
    return AgentSnapshot(
        tick=int(sim.tick), n_alive=int(alive_mask.sum()),
        positions=pos, cultures=culture, intelligence=intel, age=age,
    )


def observe_clusters(agents: AgentSnapshot,
                       radius_m: float,
                       min_pts: int) -> List[ClusterObservation]:
    """DBSCAN-like single-pass clustering on agent positions.

    Pure read-only. Returns list of clusters (≥ min_pts agents within
    radius_m). Used to detect **emergent settlements** — clumps of
    agents that have stopped wandering and stayed near each other.
    Doesn't decide where they SHOULD settle ; just observes where they
    HAVE clumped.
    """
    n = agents.n_alive
    if n < min_pts:
        return []
    pos = agents.positions
    # Pairwise distance (N <= ~200 fine).
    dx = pos[:, 0][:, None] - pos[:, 0][None, :]
    dy = pos[:, 1][:, None] - pos[:, 1][None, :]
    dist = np.sqrt(dx * dx + dy * dy)
    neighbours = dist <= radius_m
    np.fill_diagonal(neighbours, False)
    # Union-find on neighbour pairs.
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if neighbours[i, j]:
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[rb] = ra
    # Group.
    groups: Dict[int, List[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    clusters: List[ClusterObservation] = []
    cid = 0
    for root, members in groups.items():
        if len(members) < min_pts:
            continue
        mp = pos[members]
        center = mp.mean(axis=0)
        radius = float(np.linalg.norm(mp - center, axis=1).max())
        cultures = sorted({int(agents.cultures[m]) for m in members})
        clusters.append(ClusterObservation(
            cluster_id=cid,
            n_agents=len(members),
            center_x_m=float(center[0]),
            center_y_m=float(center[1]),
            radius_m=radius,
            cultures=cultures,
        ))
        cid += 1
    return clusters


def observe_polities(sim) -> Dict[str, Any]:
    """Read engine.polity Wave 9c state — pure read-only."""
    state = getattr(sim, "_polity_state", None)
    if state is None:
        return {"installed": False}
    out = {
        "installed": True,
        "n_polities": len(getattr(state, "polities", [])),
        "polities": [],
    }
    for p in getattr(state, "polities", []):
        out["polities"].append({
            "polity_id": getattr(p, "polity_id", -1),
            "n_members": len(getattr(p, "members", [])),
            "leader_row": getattr(p, "leader_row", -1),
            "treasury_kcal": float(getattr(p, "treasury_kcal", 0.0)),
        })
    return out


def observe_inventions(sim) -> Dict[str, Any]:
    """Read engine.invention.InventionRegistry — pure read-only."""
    state = getattr(sim, "_invention_state", None) or getattr(sim, "invention", None)
    if state is None:
        return {"installed": False}
    registry = getattr(state, "registry", state)
    artifacts = getattr(registry, "artifacts", None) or {}
    return {
        "installed": True,
        "n_artifacts": len(artifacts),
        "by_function": dict(
            getattr(registry, "by_function_counts", {})
            if hasattr(registry, "by_function_counts") else {}
        ),
    }


def observe_buildings(sim) -> Dict[str, Any]:
    """Read engine.building_discovery state — pure read-only."""
    state = getattr(sim, "_building_discovery_state", None)
    if state is None:
        return {"installed": False}
    return {
        "installed": True,
        "n_structures": int(getattr(state, "n_structures_total", 0)),
        "n_archetypes": int(getattr(state, "n_archetypes", 0)),
    }


def observe_languages(sim) -> Dict[str, Any]:
    """Read lexicon drift per culture — pure read-only."""
    lex = getattr(sim, "_culture_lexicons", None) or {}
    if not lex:
        return {"installed": False, "n_cultures": 0}
    summary: Dict[str, Any] = {"installed": True, "n_cultures": len(lex)}
    sigs: List[str] = []
    for cid, lexicon in lex.items():
        try:
            arr = np.asarray(lexicon, dtype=np.float32)
            import hashlib
            sigs.append(hashlib.sha256(arr.tobytes()).hexdigest()[:12])
        except Exception:
            sigs.append("?")
    summary["lexicon_signatures"] = sigs
    return summary


def observe_inscriptions(sim) -> Dict[str, Any]:
    """Read engine.writing state — pure read-only."""
    state = getattr(sim, "_writing_state", None)
    if state is None:
        return {"installed": False}
    inscr = getattr(state, "inscriptions", []) or []
    return {
        "installed": True,
        "n_inscriptions": len(inscr),
        "n_legible": sum(1 for i in inscr
                          if getattr(i, "legible", True)),
    }


def observe_artifacts(sim) -> Dict[str, Any]:
    """Read engine.art_discovery state — pure read-only."""
    state = getattr(sim, "_art_discovery_state", None)
    if state is None:
        return {"installed": False}
    return {
        "installed": True,
        "n_drawings": int(getattr(state, "n_drawings_total", 0)),
        "n_fingerprints": int(getattr(state, "n_fingerprints", 0)),
    }


def take_snapshot(sim, cluster_radius_m: float,
                    cluster_min_pts: int) -> EvolutionSnapshot:
    """Take a full read-only snapshot at the current sim tick."""
    agents = observe_agents(sim)
    clusters = observe_clusters(agents, cluster_radius_m, cluster_min_pts)
    return EvolutionSnapshot(
        tick=int(sim.tick),
        agents=agents,
        clusters=clusters,
        polities=observe_polities(sim),
        inventions=observe_inventions(sim),
        buildings=observe_buildings(sim),
        artifacts=observe_artifacts(sim),
        languages=observe_languages(sim),
        inscriptions=observe_inscriptions(sim),
    )


# ---------------------------------------------------------------------------
# Trail density (passive observation of where agents have walked)
# ---------------------------------------------------------------------------

def accumulate_trail(trail: Dict[Tuple[int, int], int],
                       agents: AgentSnapshot,
                       cell_size_m: float) -> None:
    """Increment a (chunk_x, chunk_y) counter per agent position.

    Mutates ``trail`` dict in place. Read-only on ``agents``.
    """
    for i in range(agents.n_alive):
        cx = int(np.floor(agents.positions[i, 0] / cell_size_m))
        cy = int(np.floor(agents.positions[i, 1] / cell_size_m))
        trail[(cx, cy)] = trail.get((cx, cy), 0) + 1


# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

def run_stone_age_evolution(sim,
                              cfg: Optional[StoneAgeConfig] = None
                              ) -> EvolutionHistory:
    """Run the simulation for ``cfg.n_ticks`` and capture snapshots.

    Does NOT install any modules — the caller must have already done
    ``bootstrap_genesis_sim(sim)`` + any of the agent-driven modules
    they want active (polity, invention, agriculture, writing, ...).

    The harness only :
      1. Calls ``sim.step()`` repeatedly.
      2. Every ``snapshot_every`` ticks, takes a read-only snapshot.
      3. Accumulates a trail density grid.

    Returns :class:`EvolutionHistory`. Pure observation, zero mutation
    of agent state.
    """
    cfg = cfg or StoneAgeConfig()
    history = EvolutionHistory(
        config=cfg, seed=int(sim.cfg.seed), snapshots=[], n_ticks_run=0)
    trail_dict: Dict[Tuple[int, int], int] = {}

    # Ensure founders exist before the first snapshot. The Simulation
    # bootstraps on the first step() — calling it here guarantees the
    # initial snapshot captures stone-age agents already spawned.
    if not getattr(sim, "_bootstrapped", False):
        sim.bootstrap()

    # Initial snapshot — post-bootstrap, pre-evolution.
    snap0 = take_snapshot(sim, cfg.cluster_radius_m, cfg.cluster_min_pts)
    history.snapshots.append(snap0)
    accumulate_trail(trail_dict, snap0.agents, cfg.trail_grid_cell_m)

    for tick_idx in range(cfg.n_ticks):
        sim.step()
        history.n_ticks_run += 1
        # Accumulate trail every tick (for fine grain).
        snap_agents = observe_agents(sim)
        accumulate_trail(trail_dict, snap_agents, cfg.trail_grid_cell_m)
        if (tick_idx + 1) % cfg.snapshot_every == 0:
            snap = take_snapshot(sim, cfg.cluster_radius_m,
                                  cfg.cluster_min_pts)
            history.snapshots.append(snap)

    # Densify trail to a numpy array.
    if trail_dict:
        xs = [k[0] for k in trail_dict.keys()]
        ys = [k[1] for k in trail_dict.keys()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w = max_x - min_x + 1
        h = max_y - min_y + 1
        grid = np.zeros((h, w), dtype=np.int32)
        for (cx, cy), v in trail_dict.items():
            grid[cy - min_y, cx - min_x] = v
        history.trail_density = grid
    return history


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def evolution_summary(history: EvolutionHistory) -> Dict[str, Any]:
    """Diagnostic dict over the trajectory."""
    if not history.snapshots:
        return {"n_snapshots": 0}
    first = history.snapshots[0]
    last = history.snapshots[-1]
    cluster_counts = [len(s.clusters) for s in history.snapshots]
    n_alive_track = [s.agents.n_alive for s in history.snapshots]

    def safe_get(d, k, default=0):
        return d.get(k, default) if isinstance(d, dict) else default

    return {
        "n_snapshots": len(history.snapshots),
        "n_ticks_run": history.n_ticks_run,
        "n_alive_first": first.agents.n_alive,
        "n_alive_last": last.agents.n_alive,
        "n_alive_track": n_alive_track,
        "cluster_count_track": cluster_counts,
        "first_cluster_tick": next(
            (s.tick for s in history.snapshots if s.clusters), -1),
        "first_invention_tick": next(
            (s.tick for s in history.snapshots
             if safe_get(s.inventions, "n_artifacts", 0) > 0), -1),
        "first_building_tick": next(
            (s.tick for s in history.snapshots
             if safe_get(s.buildings, "n_structures", 0) > 0), -1),
        "first_polity_tick": next(
            (s.tick for s in history.snapshots
             if safe_get(s.polities, "n_polities", 0) > 0), -1),
        "first_inscription_tick": next(
            (s.tick for s in history.snapshots
             if safe_get(s.inscriptions, "n_inscriptions", 0) > 0), -1),
        "trail_grid_shape": (history.trail_density.shape
                               if history.trail_density is not None else None),
        "trail_max_visits": (int(history.trail_density.max())
                               if history.trail_density is not None
                               and history.trail_density.size > 0 else 0),
    }
