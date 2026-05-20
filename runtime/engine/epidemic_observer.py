"""Genesis Engine — Wave 39 epidemic observer (SIR + R0 émergent).

Observe en read-only la propagation des pathogènes simulés par
`engine.physiology` (Wave 3) :

  - **cholera**  : waterborne (DRINK sur water contaminée par excrétion)
  - **flu**      : airborne (near-agent dans envelope thermique)
  - **wound**    : bacterial via injuries non soignées × dirtiness

Calcule par tick des courbes type **SIR** (Susceptible / Infectious /
Recovered) et estime R0 émergent à partir du ratio de croissance des
infections.

Architecture
------------

Aucune modification de physiology. On lit ses arrays :
  ``sim._physio_fields.cholera_load``    (N,) float [0, 1]
  ``sim._physio_fields.flu_load``        (N,) float [0, 1]
  ``sim._physio_fields.wound_load``      (N,) float [0, 1]
  ``sim._physio_fields.immune_cholera``  (N,) float [0, 1]
  ``sim._physio_fields.immune_flu``      (N,) float [0, 1]
  ``sim._physio_fields.immune_wound``    (N,) float [0, 1]

Classification per-pathogen :
  - **Susceptible**  : pas infecté, pas immunisé (load < I_thresh ET immune < R_thresh)
  - **Infectious**   : actuellement malade (load ≥ I_thresh)
  - **Recovered**    : guéri avec immunité résiduelle (load < I_thresh ET immune ≥ R_thresh)

R0 estimation (basée sur la croissance) :

```
n_new_infectious(window) = max(0, n_infectious(t) - n_infectious(t-window))
R0_estimate = n_new_infectious / max(n_infectious_avg_window, 1)
              × generation_time_in_ticks
```

C'est une approximation simple. Pour des estimations précises il
faudrait des chaînes de transmission tracées individuellement — out
of scope ici, on reste sur du SIR populationnel.

Determinism
-----------

Read-only sur les arrays physiology. Aucun RNG. Snapshots
reproductibles à 100% sur la même seed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


PIPELINE_LAYER = "Genesis-L5 Observer"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# Pathogen names matching engine.physiology.PATHOGEN_NAMES.
DEFAULT_PATHOGENS: Tuple[str, ...] = ("cholera", "flu", "wound")


# ---------------------------------------------------------------------------
# Configuration + snapshots
# ---------------------------------------------------------------------------

@dataclass
class EpidemicConfig:
    """Hyper-parameters of the observer."""
    snapshot_every: int = 10               # ticks between snapshots
    track_pathogens: Tuple[str, ...] = DEFAULT_PATHOGENS
    infection_threshold: float = 0.10      # load ≥ this → infectious
    recovery_threshold: float = 0.20       # immune ≥ this → recovered
    r0_window_snapshots: int = 3           # rolling window for R0 estim


@dataclass
class PathogenSnapshot:
    """SIR counts + flow indicators for one pathogen at one tick."""
    pathogen: str
    n_susceptible: int = 0
    n_infectious: int = 0
    n_recovered: int = 0
    n_alive: int = 0
    new_infections_this_window: int = 0
    new_recoveries_this_window: int = 0
    mean_load: float = 0.0
    max_load: float = 0.0
    mean_immune: float = 0.0
    r0_estimate: float = 0.0


@dataclass
class EpidemicSnapshot:
    """Per-tick aggregate over all tracked pathogens."""
    tick: int
    n_alive: int
    per_pathogen: Dict[str, PathogenSnapshot] = field(default_factory=dict)


@dataclass
class EpidemicHistory:
    """Full trajectory."""
    config: EpidemicConfig
    snapshots: List[EpidemicSnapshot] = field(default_factory=list)
    n_ticks_run: int = 0


@dataclass
class ContactEdge:
    """Undirected transmission edge between two alive agents (deterministic id)."""
    agent_a: int
    agent_b: int
    pathogen: str
    distance_m: float


@dataclass
class ContactGraphSnapshot:
    """Contact graph at one tick — edges sorted for reproducibility."""
    tick: int
    contact_radius_m: float
    edges: List[ContactEdge] = field(default_factory=list)
    n_infectious_pairs: int = 0


@dataclass
class EpidemicObserverState:
    """Per-sim state attached when installer hooks sim.step."""
    config: EpidemicConfig
    history: EpidemicHistory
    last_snapshot_tick: int = -1
    # Per-pathogen rolling memory : last counts for diff computation.
    prev_infectious: Dict[str, int] = field(default_factory=dict)
    prev_recovered: Dict[str, int] = field(default_factory=dict)
    contact_graphs: List[ContactGraphSnapshot] = field(default_factory=list)
    track_contact_graph: bool = True
    contact_radius_m: float = 4.0


# ---------------------------------------------------------------------------
# Core observer functions
# ---------------------------------------------------------------------------

def _get_pathogen_arrays(sim, pathogen: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Return ``(load_arr, immune_arr)`` for the pathogen, or (None, None)
    if physiology isn't installed."""
    fields = getattr(sim, "_physio_fields", None)
    if fields is None:
        return None, None
    load_attr = f"{pathogen}_load"
    immune_attr = f"immune_{pathogen}"
    load = getattr(fields, load_attr, None)
    immune = getattr(fields, immune_attr, None)
    return load, immune


def observe_pathogen(sim, pathogen: str,
                       cfg: Optional[EpidemicConfig] = None,
                       prev_infectious: int = 0
                       ) -> PathogenSnapshot:
    """Snapshot of one pathogen at the current tick.

    Pure read-only. Counts S/I/R based on load + immune thresholds.
    """
    cfg = cfg or EpidemicConfig()
    load, immune = _get_pathogen_arrays(sim, pathogen)
    if load is None or immune is None:
        return PathogenSnapshot(pathogen=pathogen)

    n = sim.agents.n_active
    alive = sim.agents.alive[:n].astype(bool)
    if not alive.any():
        return PathogenSnapshot(pathogen=pathogen)

    L = load[:n][alive]
    I = immune[:n][alive]
    I_th = float(cfg.infection_threshold)
    R_th = float(cfg.recovery_threshold)

    infectious = L >= I_th
    recovered = (L < I_th) & (I >= R_th)
    susceptible = (L < I_th) & (I < R_th)

    n_inf = int(infectious.sum())
    n_rec = int(recovered.sum())
    n_sus = int(susceptible.sum())
    n_alive = int(alive.sum())

    new_inf = max(0, n_inf - prev_infectious)

    return PathogenSnapshot(
        pathogen=pathogen,
        n_susceptible=n_sus,
        n_infectious=n_inf,
        n_recovered=n_rec,
        n_alive=n_alive,
        new_infections_this_window=new_inf,
        mean_load=float(L.mean()) if L.size > 0 else 0.0,
        max_load=float(L.max()) if L.size > 0 else 0.0,
        mean_immune=float(I.mean()) if I.size > 0 else 0.0,
        r0_estimate=0.0,  # filled by aggregator
    )


def build_contact_graph(sim,
                          *,
                          contact_radius_m: float = 4.0,
                          pathogen: str = "flu",
                          infection_threshold: float = 0.10,
                          ) -> ContactGraphSnapshot:
    """Deterministic contact graph: edges among pairs within ``contact_radius_m``
    where at least one agent is infectious for ``pathogen``."""
    n = sim.agents.n_active
    alive = sim.agents.alive[:n].astype(bool)
    rows = np.flatnonzero(alive)
    if rows.size < 2:
        return ContactGraphSnapshot(
            tick=int(sim.tick), contact_radius_m=contact_radius_m)

    load, _immune = _get_pathogen_arrays(sim, pathogen)
    if load is None:
        return ContactGraphSnapshot(
            tick=int(sim.tick), contact_radius_m=contact_radius_m)

    pos = sim.agents.pos[rows, :2].astype(np.float64)
    infectious = load[rows] >= infection_threshold
    edges: List[ContactEdge] = []
    r2 = float(contact_radius_m) ** 2
    for i in range(rows.size):
        if not infectious[i]:
            continue
        for j in range(i + 1, rows.size):
            dx = pos[i, 0] - pos[j, 0]
            dy = pos[i, 1] - pos[j, 1]
            d2 = dx * dx + dy * dy
            if d2 > r2 or d2 < 1e-6:
                continue
            a, b = int(rows[i]), int(rows[j])
            if a > b:
                a, b = b, a
            edges.append(ContactEdge(
                agent_a=a, agent_b=b, pathogen=pathogen,
                distance_m=float(np.sqrt(d2))))
    edges.sort(key=lambda e: (e.agent_a, e.agent_b, e.pathogen))
    return ContactGraphSnapshot(
        tick=int(sim.tick),
        contact_radius_m=contact_radius_m,
        edges=edges,
        n_infectious_pairs=len(edges),
    )


def take_epidemic_snapshot(sim,
                              cfg: Optional[EpidemicConfig] = None,
                              prev_infectious: Optional[Dict[str, int]] = None,
                              ) -> EpidemicSnapshot:
    """Take a full snapshot across all tracked pathogens."""
    cfg = cfg or EpidemicConfig()
    prev = prev_infectious or {}
    n = sim.agents.n_active
    alive = int(sim.agents.alive[:n].sum()) if n > 0 else 0
    snap = EpidemicSnapshot(tick=int(sim.tick), n_alive=alive)
    for p in cfg.track_pathogens:
        snap.per_pathogen[p] = observe_pathogen(
            sim, p, cfg, prev_infectious=prev.get(p, 0))
    return snap


def estimate_r0_for_pathogen(history: EpidemicHistory,
                                pathogen: str,
                                window: int = 3) -> float:
    """Estimation R0 grossière sur les ``window`` derniers snapshots.

    R0 ≈ (Σ new_infections) / max(mean(n_infectious), 1)
    """
    if len(history.snapshots) < 2:
        return 0.0
    recent = history.snapshots[-window:]
    if not recent:
        return 0.0
    new_total = sum(
        s.per_pathogen.get(pathogen, PathogenSnapshot(pathogen=pathogen)
                              ).new_infections_this_window
        for s in recent
    )
    mean_infectious = float(np.mean([
        s.per_pathogen.get(pathogen, PathogenSnapshot(pathogen=pathogen)
                              ).n_infectious
        for s in recent
    ]))
    return float(new_total) / max(mean_infectious, 1.0)


# ---------------------------------------------------------------------------
# Sim integration (wraps sim.step like physiology / anatomy)
# ---------------------------------------------------------------------------

def install_epidemic_observer(sim,
                                 cfg: Optional[EpidemicConfig] = None
                                 ) -> EpidemicObserverState:
    """Idempotent installer. Wraps ``sim.step`` to capture snapshots
    every ``cfg.snapshot_every`` ticks.

    Read-only on physiology — does NOT install physiology itself. Caller
    must have installed physiology before for the observer to see
    anything.
    """
    cfg = cfg or EpidemicConfig()
    existing: Optional[EpidemicObserverState] = getattr(
        sim, "_epidemic_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = EpidemicObserverState(
        config=cfg, history=EpidemicHistory(config=cfg))
    sim._epidemic_state = state

    if getattr(sim, "_epidemic_wrapped", False):
        return state
    sim._epidemic_wrapped = True
    original_step = sim.step

    def wrapped_step():
        stats = original_step()
        st: EpidemicObserverState = sim._epidemic_state
        cfg_now = st.config
        if (sim.tick - st.last_snapshot_tick) >= cfg_now.snapshot_every:
            snap = take_epidemic_snapshot(
                sim, cfg_now, prev_infectious=st.prev_infectious)
            # Update prev for next window.
            for p, ps in snap.per_pathogen.items():
                st.prev_infectious[p] = ps.n_infectious
                st.prev_recovered[p] = ps.n_recovered
            # Fill R0 estimates with the rolling window.
            st.history.snapshots.append(snap)
            for p in cfg_now.track_pathogens:
                r0 = estimate_r0_for_pathogen(
                    st.history, p, window=cfg_now.r0_window_snapshots)
                if p in snap.per_pathogen:
                    snap.per_pathogen[p].r0_estimate = r0
            st.last_snapshot_tick = int(sim.tick)
            st.history.n_ticks_run = int(sim.tick)
            if st.track_contact_graph:
                cg = build_contact_graph(
                    sim,
                    contact_radius_m=st.contact_radius_m,
                    pathogen="flu",
                    infection_threshold=cfg_now.infection_threshold,
                )
                st.contact_graphs.append(cg)
        return stats

    sim.step = wrapped_step
    return state


def uninstall_epidemic_observer(sim) -> bool:
    """Detach state (best-effort — sim.step wrap remains a no-op once
    state is gone)."""
    if hasattr(sim, "_epidemic_state"):
        delattr(sim, "_epidemic_state")
        return True
    return False


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def estimate_r0_network_from_contact(graph: ContactGraphSnapshot,
                                       pathogen: str = "flu") -> float:
    """Degree-based R0 proxy from the last contact graph snapshot."""
    if not graph.edges:
        return 0.0
    degree: Dict[int, int] = {}
    for e in graph.edges:
        if e.pathogen != pathogen:
            continue
        degree[e.agent_a] = degree.get(e.agent_a, 0) + 1
        degree[e.agent_b] = degree.get(e.agent_b, 0) + 1
    if not degree:
        return 0.0
    return float(np.mean(list(degree.values())))


def epidemic_export_for_artifacts(sim) -> Dict[str, object]:
    """Dashboard / artifact block: SIR R0 vs contact-network R0 per pathogen."""
    summary = epidemic_state_summary(sim)
    state: Optional[EpidemicObserverState] = getattr(
        sim, "_epidemic_state", None)
    comparison: Dict[str, Dict[str, float]] = {}
    if state and state.history.snapshots:
        for p in state.config.track_pathogens:
            r0_sir = estimate_r0_for_pathogen(state.history, p)
            r0_net = 0.0
            if state.contact_graphs:
                cg = state.contact_graphs[-1]
                r0_net = estimate_r0_network_from_contact(cg, pathogen=p)
            comparison[p] = {
                "r0_sir_estimate": round(r0_sir, 3),
                "r0_network_estimate": round(r0_net, 3),
            }
    summary["r0_comparison"] = comparison
    return summary


def epidemic_state_summary(sim) -> Dict[str, object]:
    """Diagnostic dict over the trajectory."""
    state: Optional[EpidemicObserverState] = getattr(
        sim, "_epidemic_state", None)
    if state is None:
        return {"installed": False}
    history = state.history
    if not history.snapshots:
        return {"installed": True, "n_snapshots": 0}
    last = history.snapshots[-1]
    summary: Dict[str, object] = {
        "installed": True,
        "n_snapshots": len(history.snapshots),
        "n_ticks_run": history.n_ticks_run,
        "last_tick": last.tick,
        "n_alive_last": last.n_alive,
        "per_pathogen": {},
    }
    for p, ps in last.per_pathogen.items():
        summary["per_pathogen"][p] = {
            "n_susceptible": ps.n_susceptible,
            "n_infectious": ps.n_infectious,
            "n_recovered": ps.n_recovered,
            "mean_load": round(ps.mean_load, 4),
            "max_load": round(ps.max_load, 4),
            "mean_immune": round(ps.mean_immune, 4),
            "r0_estimate": round(ps.r0_estimate, 3),
        }
    cg = state.contact_graphs[-1] if state.contact_graphs else None
    summary["contact_graph"] = {
        "n_snapshots": len(state.contact_graphs),
        "last_edges": len(cg.edges) if cg else 0,
        "contact_radius_m": state.contact_radius_m,
    }
    return summary


__all__ = [
    "DEFAULT_PATHOGENS",
    "EpidemicConfig", "PathogenSnapshot", "EpidemicSnapshot",
    "EpidemicHistory", "EpidemicObserverState",
    "ContactEdge", "ContactGraphSnapshot",
    "observe_pathogen", "take_epidemic_snapshot",
    "build_contact_graph",
    "estimate_r0_for_pathogen",
    "install_epidemic_observer", "uninstall_epidemic_observer",
    "epidemic_state_summary", "epidemic_export_for_artifacts",
    "estimate_r0_network_from_contact",
]
