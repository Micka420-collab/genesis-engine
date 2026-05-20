"""Rust WorldGraph bridge — observe chunks each tick from bootstrap context.

Uses :mod:`engine.rust_bridge` (native ``genesis_world`` or Genesis-aligned
mock). Wired after ``bootstrap_genesis_sim``; sampled from
:func:`engine.sim_emergence.tick_emergence_world`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from engine.rust_bridge import bridge_status, create_py_world_from_sim
from engine.world import world_to_chunk


PIPELINE_LAYER = "Genesis-L0 Core"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


@dataclass
class RustWorldgraphState:
    py_world: Any = None
    observe_every: int = 50
    prod_mode: bool = False
    last_native: bool = False
    ticks_observed: int = 0
    chunks_sampled: int = 0
    intents_submitted: int = 0
    cached_chunks: int = -1
    last_chunk: Optional[Tuple[int, int, int]] = None
    last_observation: Optional[Dict[str, Any]] = None
    _seen_coords: Set[Tuple[int, int, int]] = field(default_factory=set)


def install_rust_worldgraph(sim, *, observe_every: int = 50,
                            prod_mode: bool = False) -> RustWorldgraphState:
    """Attach PyWorld/mock handle; idempotent."""
    existing: Optional[RustWorldgraphState] = getattr(sim, "_rust_worldgraph", None)
    if existing is not None:
        return existing
    py_world = create_py_world_from_sim(sim)
    _, native = __import__(
        "engine.rust_bridge", fromlist=["try_import_genesis_world"]
    ).try_import_genesis_world()
    st = RustWorldgraphState(
        py_world=py_world,
        observe_every=max(1, int(observe_every)),
        prod_mode=bool(prod_mode),
        last_native=bool(native),
    )
    if native and hasattr(py_world, "cached_chunk_count"):
        try:
            st.cached_chunks = int(py_world.cached_chunk_count())
        except Exception:
            pass
    sim._rust_worldgraph = st
    return st


def _submit_native_prefetch(st: RustWorldgraphState, sim) -> None:
    """When native PyWorld exposes submit_intent, prefetch agent vicinities."""
    if not st.last_native or st.py_world is None:
        return
    submit = getattr(st.py_world, "submit_intent", None)
    if submit is None:
        return
    n = sim.agents.n_active
    for row in range(min(n, 32)):
        if not sim.agents.alive[row]:
            continue
        x = int(float(sim.agents.pos[row, 0]))
        y = int(float(sim.agents.pos[row, 1]))
        try:
            submit(row, "idle", [(x, y, 0)], priority=64, horizon_ticks=120,
                   radius_m=48.0)
            st.intents_submitted += 1
        except Exception:
            pass


def tick_rust_worldgraph(sim) -> None:
    """Sample ``observe_chunk`` for active agent chunk coords (sparse or prod)."""
    st: Optional[RustWorldgraphState] = getattr(sim, "_rust_worldgraph", None)
    if st is None or st.py_world is None:
        return
    interval = 1 if st.prod_mode else st.observe_every
    if sim.tick % interval != 0:
        return

    if st.prod_mode and sim.tick % 10 == 0:
        _submit_native_prefetch(st, sim)

    coords: Set[Tuple[int, int, int]] = set()
    n = sim.agents.n_active
    for row in range(n):
        if not sim.agents.alive[row]:
            continue
        coords.add(world_to_chunk(
            float(sim.agents.pos[row, 0]),
            float(sim.agents.pos[row, 1]),
        ))
    if not coords:
        coords.add((0, 0, 0))

    limit = 24 if st.prod_mode else 8
    for coord in sorted(coords)[:limit]:
        cx, cy, cz = coord
        obs = st.py_world.observe_chunk(cx, cy, cz)
        st.last_observation = obs
        st.last_chunk = coord
        st._seen_coords.add(coord)
        st.chunks_sampled += 1
    st.ticks_observed += 1

    if st.last_native and hasattr(st.py_world, "cached_chunk_count"):
        try:
            st.cached_chunks = int(st.py_world.cached_chunk_count())
        except Exception:
            pass


def rust_worldgraph_snapshot(sim) -> Dict[str, object]:
    st: Optional[RustWorldgraphState] = getattr(sim, "_rust_worldgraph", None)
    base = bridge_status(sim)
    if st is None:
        return {**base, "installed": False}
    return {
        **base,
        "installed": True,
        "prod_mode": st.prod_mode,
        "observe_every": st.observe_every,
        "ticks_observed": st.ticks_observed,
        "chunks_sampled": st.chunks_sampled,
        "intents_submitted": st.intents_submitted,
        "cached_chunks": st.cached_chunks,
        "unique_chunks": len(st._seen_coords),
        "last_chunk": list(st.last_chunk) if st.last_chunk else None,
        "last_mock": bool((st.last_observation or {}).get("mock", True)),
        "last_genesis": bool((st.last_observation or {}).get("genesis", False)),
    }


__all__ = [
    "RustWorldgraphState",
    "install_rust_worldgraph",
    "tick_rust_worldgraph",
    "rust_worldgraph_snapshot",
]
