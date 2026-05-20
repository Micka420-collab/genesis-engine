"""Civilization emergence wired into the simulation tick loop.

Subsystems (Köppen, cross-chunk hydrology, epidemic observation, live
observable state, multi-rate coupler) attach to :class:`engine.sim.Simulation`
and update as *consequences* of ``sim.step()`` — not via external orchestrator
scripts or batch pipelines.

Smokes and ``run.py`` only *validate* behaviour; they do not drive it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np

from engine.world import invalidate_resource_masks, world_to_chunk


ObservationListener = Callable[["Simulation", Dict[str, Any]], None]


@dataclass
class EmergenceState:
    """Per-simulation emergence side-state (read by dashboard / artifacts)."""
    koeppen_refresh_every: int = 200
    observable_every: int = 25
    hydrology_cross_chunk: bool = True
    hydrology_mode: str = "stub"
    koeppen_manifest: Optional[Dict[str, Any]] = None
    epidemic_summary: Optional[Dict[str, Any]] = None
    live_observable: Optional[Dict[str, Any]] = None
    hydrology_ticks: int = 0
    hydrology_pairs_exchanged: int = 0
    observation_listeners: List[ObservationListener] = field(default_factory=list)
    _hydrology_pairs_seen: Set[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = field(
        default_factory=set, repr=False)


def wire_civilization_emergence(sim, *,
                                 koeppen_refresh_every: int = 200,
                                 observable_every: int = 25,
                                 hydrology_cross_chunk: bool = True,
                                 hydrology_mode: str = "stub",
                                 epidemic_snapshot_every: int = 10,
                                 install_coupler: bool = True,
                                 install_epidemic: bool = True,
                                 ) -> EmergenceState:
    """Idempotent hook-up of emergence subsystems on ``sim``."""
    existing: Optional[EmergenceState] = getattr(sim, "_emergence", None)
    if existing is not None:
        return existing

    mode = str(hydrology_mode or "stub").strip().lower()
    if mode not in ("stub", "sv1d", "lbm"):
        mode = "stub"
    st = EmergenceState(
        koeppen_refresh_every=max(0, int(koeppen_refresh_every)),
        observable_every=max(1, int(observable_every)),
        hydrology_cross_chunk=bool(hydrology_cross_chunk),
        hydrology_mode=mode,
    )
    sim._emergence = st

    if install_coupler:
        try:
            from engine.multi_rate_coupler import install_multi_rate_coupler
            install_multi_rate_coupler(sim, master_dt=int(sim.cfg.drive_accel))
        except Exception:
            pass

    if install_epidemic:
        _wire_epidemic(sim, snapshot_every=epidemic_snapshot_every)

    if st.koeppen_refresh_every > 0:
        _refresh_koeppen(sim, st)

    return st


def _wire_epidemic(sim, *, snapshot_every: int) -> None:
    """Epidemic observer + physiology when agents can carry pathogens."""
    try:
        from engine.physiology import install_physiology
        if getattr(sim, "_physio_fields", None) is None:
            install_physiology(sim)
    except Exception:
        pass
    try:
        from engine.epidemic_observer import install_epidemic_observer
        install_epidemic_observer(sim, snapshot_every=max(1, int(snapshot_every)))
    except Exception:
        pass


def _refresh_koeppen(sim, st: EmergenceState) -> None:
    try:
        from engine.koeppen_grid import koeppen_from_genesis_bootstrap, fair_koeppen_manifest
        manifest = koeppen_from_genesis_bootstrap(sim)
        if manifest is None:
            anchor = getattr(sim.streamer, "genesis", None)
            if anchor is not None and hasattr(anchor, "world"):
                manifest = fair_koeppen_manifest(anchor.world)
        st.koeppen_manifest = manifest
    except Exception:
        st.koeppen_manifest = None


def _agent_density_per_chunk(sim) -> Dict[Tuple[int, int, int], int]:
    n = sim.agents.n_active
    counts: Dict[Tuple[int, int, int], int] = {}
    live = np.flatnonzero(sim.agents.alive[:n])
    for row in live:
        row = int(row)
        c = world_to_chunk(
            float(sim.agents.pos[row, 0]),
            float(sim.agents.pos[row, 1]),
        )
        counts[c] = counts.get(c, 0) + 1
    return counts


def _tick_cross_chunk_hydrology(sim, st: EmergenceState,
                                 density: Dict[Tuple[int, int, int], int]) -> None:
    """Cross-chunk water exchange; model selected by ``st.hydrology_mode``."""
    if not st.hydrology_cross_chunk:
        return
    cache = sim.streamer.cache
    if len(cache) < 2:
        return

    mode = str(st.hydrology_mode or "stub").strip().lower()
    try:
        from engine.chunk_hydrology import cross_chunk_flow_stub
    except Exception:
        return

    use_lbm_kwargs = False
    if mode == "sv1d":
        try:
            from engine.chunk_hydrology import cross_chunk_saint_venant_1d
            cross_fn = cross_chunk_saint_venant_1d
        except Exception:
            cross_fn = cross_chunk_flow_stub
    elif mode == "lbm":
        try:
            from engine.chunk_hydrology import cross_chunk_lbm_d2q9_step
            cross_fn = cross_chunk_lbm_d2q9_step
            use_lbm_kwargs = True
        except Exception:
            cross_fn = cross_chunk_flow_stub
    else:
        cross_fn = cross_chunk_flow_stub

    coords = list(cache.keys())
    dt_s = float(sim.cfg.drive_accel) * 0.001
    pairs_this_tick = 0
    for coord in coords:
        cx, cy, cz = coord
        for dx, dy, boundary in (
            (1, 0, "east"),
            (0, 1, "north"),
        ):
            nb = (cx + dx, cy + dy, cz)
            ch_a = cache.get(coord)
            ch_b = cache.get(nb)
            if ch_a is None or ch_b is None:
                continue
            key = (coord, nb) if coord < nb else (nb, coord)
            if key in st._hydrology_pairs_seen and sim.tick % 5 != 0:
                continue
            st._hydrology_pairs_seen.add(key)
            n_a = density.get(coord, 0)
            n_b = density.get(nb, 0)
            activity = max(n_a, n_b)
            if activity < 1:
                continue
            boost = 1.0 + min(activity, 8) * 0.12
            if n_a >= 3 or n_b >= 3:
                irrigate = 0.985 ** min(n_a + n_b, 12)
                ch_a.water[:] *= irrigate
                ch_b.water[:] *= irrigate
                invalidate_resource_masks(ch_a)
                invalidate_resource_masks(ch_b)
            eff_dt = dt_s * boost
            if use_lbm_kwargs:
                prf = int(sim.cfg.seed) ^ (sim.tick * 0x9E3779B9)
                cross_fn(ch_a, ch_b, boundary, prf_seed=prf, dt_s=eff_dt)
            else:
                cross_fn(ch_a, ch_b, boundary, dt_s=eff_dt)
            pairs_this_tick += 1
    if pairs_this_tick:
        st.hydrology_ticks += 1
        st.hydrology_pairs_exchanged += pairs_this_tick


def _tick_live_observable(sim, st: EmergenceState) -> None:
    """In-memory observable snapshot for dashboard / SSE (no static JSON)."""
    try:
        from engine.agent_observation import observe_agent_row
    except Exception:
        return

    agents = sim.agents
    n = agents.n_active
    compact: List[Dict[str, Any]] = []
    for row in range(n):
        if not bool(agents.alive[row]):
            continue
        obs = observe_agent_row(sim, row)
        compact.append({
            "row": obs.row,
            "uuid": obs.uuid,
            "x": round(obs.x_m, 2),
            "y": round(obs.y_m, 2),
            "v": round(obs.vitality, 3),
            "c": obs.culture_id,
            "g": obs.group_id,
            "pathogen": round(obs.pathogen_load, 4),
        })
    bx_m = sim.cfg.bounds_km[0] * 500.0
    by_m = sim.cfg.bounds_km[1] * 500.0
    payload: Dict[str, Any] = {
        "tick": int(sim.tick),
        "sim_id": str(sim.sim_id),
        "n_alive": len(compact),
        "bounds_m": [float(bx_m), float(by_m)],
        "agents_compact": compact,
    }
    if st.koeppen_manifest:
        payload["koeppen_land_cells"] = st.koeppen_manifest.get("koeppen_land_cells")
    st.live_observable = payload
    for listener in st.observation_listeners:
        try:
            listener(sim, payload)
        except Exception:
            pass


def _refresh_epidemic_summary(sim, st: EmergenceState) -> None:
    if not getattr(sim, "_epidemic_state", None):
        return
    try:
        from engine.epidemic_observer import epidemic_state_summary
        st.epidemic_summary = epidemic_state_summary(sim)
    except Exception:
        st.epidemic_summary = None


def tick_emergence_world(sim) -> None:
    """Called from :meth:`Simulation.step` — one pass per tick."""
    st: Optional[EmergenceState] = getattr(sim, "_emergence", None)
    if st is None:
        return

    if st.koeppen_refresh_every > 0 and sim.tick % st.koeppen_refresh_every == 0:
        _refresh_koeppen(sim, st)

    density = _agent_density_per_chunk(sim)
    _tick_cross_chunk_hydrology(sim, st, density)

    if sim.tick % st.observable_every == 0:
        _tick_live_observable(sim, st)

    if getattr(sim, "_epidemic_state", None) is not None:
        _refresh_epidemic_summary(sim, st)

    if getattr(sim, "_rust_worldgraph", None) is not None:
        try:
            from engine.rust_worldgraph_tick import tick_rust_worldgraph
            tick_rust_worldgraph(sim)
        except Exception:
            pass

    if getattr(sim, "_commerce_emergence", None) is not None:
        try:
            from engine.commerce_emergence import tick_commerce_emergence
            tick_commerce_emergence(sim)
        except Exception:
            pass


def emergence_snapshot(sim) -> Dict[str, Any]:
    """Block for ``Simulation.snapshot()`` / artifacts."""
    st: Optional[EmergenceState] = getattr(sim, "_emergence", None)
    if st is None:
        return {}
    out: Dict[str, Any] = {
        "koeppen": st.koeppen_manifest,
        "observable_tick": (st.live_observable or {}).get("tick"),
        "hydrology": {
            "mode": st.hydrology_mode,
            "ticks_active": st.hydrology_ticks,
            "pairs_exchanged": st.hydrology_pairs_exchanged,
        },
    }
    if st.epidemic_summary:
        out["epidemic"] = st.epidemic_summary
    rw = getattr(sim, "_rust_worldgraph", None)
    if rw is not None:
        try:
            from engine.rust_worldgraph_tick import rust_worldgraph_snapshot
            out["rust_worldgraph"] = rust_worldgraph_snapshot(sim)
        except Exception:
            pass
    ce = getattr(sim, "_commerce_emergence", None)
    if ce is not None:
        try:
            from engine.commerce_emergence import commerce_emergence_snapshot
            out["commerce"] = commerce_emergence_snapshot(sim)
        except Exception:
            pass
    return {k: v for k, v in out.items() if v is not None}


def add_observation_listener(sim, listener: ObservationListener) -> None:
    st: Optional[EmergenceState] = getattr(sim, "_emergence", None)
    if st is not None:
        st.observation_listeners.append(listener)


__all__ = [
    "EmergenceState",
    "wire_civilization_emergence",
    "tick_emergence_world",
    "emergence_snapshot",
    "add_observation_listener",
]
