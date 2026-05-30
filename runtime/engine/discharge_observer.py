"""Genesis Engine — Wave 53 LTI river-discharge routing observer.

Read-only propagation of an emergent **runoff field** down the D8 drainage
network already built by :mod:`engine.world_genesis` (``flow_dir`` +
``precip_mm`` + ``temp_c`` + ``watershed_id``). No mutation, no RNG, no
ontology imposed: discharge is the steady-state response of a *linear,
time-invariant* (LTI) routing operator applied to whatever runoff the
climate fields already encode.

Why LTI routing
---------------

A linear time-invariant river-routing scheme is **mathematically a linear
operator** on the runoff field: with the D8 downstream adjacency matrix
``A`` (one out-edge per cell), steady-state discharge solves

    Q = r + Aᵀ Q   ⇔   Q = (I − Aᵀ)⁻¹ r

(Hascoet et al. 2025 — *Differentiable River Routing*, JGR-ML — show this
LTI operator is equivalent to a block-sparse convolution, which is what
makes the GPU / autodiff version possible). Because every cell has exactly
one downstream neighbour, ``(I − Aᵀ)⁻¹`` is evaluated **exactly and
deterministically** by a single upstream→downstream topological sweep
(Kahn) — no matrix inverse, no iteration, O(N). This module ships that
exact CPU sweep; the GPU/conv differentiable variant remains backlog
(veille 2026-05-30, DÉCOUVERTE_1) and is *not* on the deterministic core.

What it measures (all emergent, classical hydrology)
----------------------------------------------------

1. **Specific runoff** ``q = max(P − ETₐ, 0)`` per cell, where ``ETₐ`` is a
   temperature-limited actual-ET proxy. Mass is conserved: the routing
   never creates or destroys water.

2. **Discharge** ``Q`` (m³/s) at every cell — runoff routed downstream and
   accumulated. River discharge is ``Q`` restricted to ``river_mask``.

3. **Outlet discharge per basin** and the **specific discharge**
   ``Q_outlet / A_basin`` (mm/yr equivalent), plus the single largest
   river cell on the map (the emergent "main stem").

Observer contract (mirrors Waves 45 / 49 / 50 / 51)
---------------------------------------------------

- ``DischargeConfig`` / ``BasinDischarge`` / ``DischargeSnapshot`` /
  ``DischargeHistory`` / ``DischargeState`` dataclasses (frozen where data).
- ``observe_discharge(sim, cfg)`` — **read-only**, returns a snapshot.
- ``install_discharge_observer(sim, cfg)`` — idempotent, wraps ``sim.step``
  so a snapshot is captured every ``snapshot_every`` ticks.
- ``uninstall_discharge_observer(sim)`` — restores ``sim.step``.
- ``discharge_summary(sim)`` — diagnostic dict for dashboards.

Determinism
-----------

No RNG. The topological sweep is row-major on every queue iteration and the
signature is ``sha256`` of a canonical tuple, so two runs with the same
world seed produce identical snapshot streams.

Stone-age compliance
---------------------

The observer never declares rivers, basins or flow. It reads the D8 graph
and climate fields emergent from the world, routes a non-negative runoff
balance, and reports. No mutation of any world or sim array.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# D8 convention matches engine.world_genesis / engine.watershed_observer.
_D8_DX = np.array([1, 1, 0, -1, -1, -1, 0, 1], dtype=np.int8)
_D8_DY = np.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=np.int8)
_D8_SINK = 255  # convention used by world_genesis flow_dir

_SECONDS_PER_YEAR = 365.25 * 24.0 * 3600.0


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DischargeConfig:
    """Read-only knobs for the discharge routing observer.

    The runoff balance is intentionally simple and monotone so it adds no
    hidden parameters to the world: ``runoff = max(P − ET, 0)`` with a
    temperature-limited ET proxy ``ET = min(P, et_mm_per_degc · max(T, 0))``.
    """
    snapshot_every: int = 64
    min_basin_cells: int = 4
    top_basins: int = 5
    et_mm_per_degc: float = 45.0   # actual-ET sensitivity to temperature
    default_precip_mm: float = 800.0   # fallback when world has no precip
    default_temp_c: float = 12.0       # fallback when world has no temp


@dataclass(frozen=True)
class BasinDischarge:
    """Per-basin emergent discharge statistics (read-only)."""
    basin_id: int
    n_cells: int
    area_km2: float
    outlet_yx: Tuple[int, int]
    outlet_discharge_m3s: float
    runoff_volume_m3s: float            # total runoff generated in basin
    specific_discharge_mm_yr: float     # Q_outlet → depth over basin area
    max_cell_discharge_m3s: float


@dataclass(frozen=True)
class DischargeSnapshot:
    """Global + top-K basin discharge snapshot at a given sim tick."""
    tick: int
    cell_km: float
    map_area_km2: float
    total_runoff_m3s: float
    total_outflow_m3s: float            # Σ discharge at sinks (mass check)
    mass_balance_residual: float        # |runoff − outflow| / max(runoff, ε)
    mean_runoff_mm_yr: float
    max_discharge_m3s: float
    max_discharge_yx: Tuple[int, int]
    mean_river_discharge_m3s: float
    n_basins_total: int
    n_basins_considered: int
    basins_top: Tuple[BasinDischarge, ...]
    signature: str


@dataclass
class DischargeHistory:
    snapshots: List[DischargeSnapshot] = field(default_factory=list)


@dataclass
class DischargeState:
    config: DischargeConfig
    history: DischargeHistory = field(default_factory=DischargeHistory)
    wrapped: bool = False


# ---------------------------------------------------------------------------
# World access (read-only) — same resolution chain as watershed_observer
# ---------------------------------------------------------------------------

def _resolve_world(sim) -> Optional[Any]:
    """Return the :class:`GenesisWorld` attached to ``sim``, or ``None``."""
    ch = getattr(sim, "_chunk_hydrology_state", None)
    if ch is not None and getattr(ch, "anchor", None) is not None:
        w = getattr(ch.anchor, "world", None)
        if w is not None:
            return w
    boot = getattr(sim, "_genesis_bootstrap_state", None)
    if boot is not None:
        w = getattr(boot, "world", None)
        if w is not None:
            return w
        a = getattr(boot, "anchor", None)
        if a is not None and getattr(a, "world", None) is not None:
            return a.world
    streamer = getattr(sim, "streamer", None)
    if streamer is not None:
        genesis = getattr(streamer, "genesis", None)
        if genesis is not None and getattr(genesis, "world", None) is not None:
            return genesis.world
    anchor = getattr(sim, "_genesis_anchor", None)
    if anchor is not None and getattr(anchor, "world", None) is not None:
        return anchor.world
    return getattr(sim, "_genesis_world", None)


# ---------------------------------------------------------------------------
# Pure-function routing  (the LTI operator)
# ---------------------------------------------------------------------------

def route_runoff(flow_dir: np.ndarray, runoff: np.ndarray) -> np.ndarray:
    """Steady-state LTI routing of ``runoff`` down the D8 graph.

    Returns ``discharge`` (float64) of the same shape as ``runoff``: the
    exact solution of ``Q = r + Aᵀ Q`` where ``A`` is the D8 downstream
    adjacency (one out-edge per cell, ``255`` = sink draining out of the
    domain). Each cell's discharge is its own runoff plus the discharge of
    every cell upstream of it.

    Properties (used as invariants by the smoke / tests):

    * **Mass conservation** — ``Σ discharge[sinks] == Σ runoff`` (every cell
      ends at a sink, runoff is neither created nor destroyed).
    * **Monotonicity** — for ``runoff ≥ 0``, ``discharge[downstream] ≥
      discharge[upstream]`` (discharge grows downstream).
    * **Unit-runoff identity** — with ``runoff ≡ 1`` the discharge equals the
      number of cells draining through each cell (self included), i.e. the
      D8 contributing-area count.

    Bit-deterministic: Kahn topological order, row-major queue. Robust to
    (degenerate) cycles — any residual cell is resolved row-major so the
    routine always terminates.
    """
    if flow_dir.shape != runoff.shape:
        raise ValueError("flow_dir and runoff must share shape")
    R0, R1 = flow_dir.shape
    fd = np.asarray(flow_dir, dtype=np.uint8)
    discharge = np.array(runoff, dtype=np.float64, copy=True)

    # Precompute downstream target index (or -1 for sink/off-grid).
    down_y = np.full((R0, R1), -1, dtype=np.int64)
    down_x = np.full((R0, R1), -1, dtype=np.int64)
    in_deg = np.zeros((R0, R1), dtype=np.int64)
    for y in range(R0):
        for x in range(R1):
            d = int(fd[y, x])
            if d == _D8_SINK or d > 7:
                continue
            ny = y + int(_D8_DY[d])
            nx = x + int(_D8_DX[d])
            if 0 <= ny < R0 and 0 <= nx < R1:
                down_y[y, x] = ny
                down_x[y, x] = nx
                in_deg[ny, nx] += 1

    remaining = in_deg.copy()
    # Headwaters first (no upstream contribution), row-major.
    queue: List[Tuple[int, int]] = [
        (int(y), int(x))
        for y in range(R0) for x in range(R1)
        if remaining[y, x] == 0
    ]

    head = 0
    processed = np.zeros((R0, R1), dtype=bool)
    while head < len(queue):
        y, x = queue[head]
        head += 1
        if processed[y, x]:
            continue
        processed[y, x] = True
        dy = int(down_y[y, x])
        if dy < 0:
            continue  # sink: discharge leaves the domain
        dx = int(down_x[y, x])
        discharge[dy, dx] += discharge[y, x]
        remaining[dy, dx] -= 1
        if remaining[dy, dx] == 0:
            queue.append((dy, dx))

    # Degenerate guard: resolve any cycle residue row-major (real D8 from
    # elevation is acyclic, so this is a safety net, never hit in practice).
    if not bool(processed.all()):
        for y in range(R0):
            for x in range(R1):
                if processed[y, x]:
                    continue
                processed[y, x] = True
                dy = int(down_y[y, x])
                if dy < 0:
                    continue
                dx = int(down_x[y, x])
                if not processed[dy, dx]:
                    discharge[dy, dx] += discharge[y, x]

    return discharge


def runoff_field_m3s(precip_mm: np.ndarray,
                     temp_c: np.ndarray,
                     cell_km: float,
                     cfg: DischargeConfig) -> np.ndarray:
    """Per-cell runoff as a steady volumetric rate (m³/s).

    ``runoff_depth = max(P − ET, 0)`` (mm/yr), ``ET = min(P, k·max(T,0))``.
    Converted to volume over the cell area and divided by seconds/year.
    Always non-negative — the routing invariants rely on it.
    """
    P = np.asarray(precip_mm, dtype=np.float64)
    T = np.asarray(temp_c, dtype=np.float64)
    et = np.minimum(P, cfg.et_mm_per_degc * np.maximum(T, 0.0))
    runoff_mm_yr = np.maximum(P - et, 0.0)
    cell_area_m2 = (float(cell_km) * 1000.0) ** 2
    # mm/yr → m/yr (×1e-3) → m³/yr (×area) → m³/s (÷sec_per_year)
    return runoff_mm_yr * 1e-3 * cell_area_m2 / _SECONDS_PER_YEAR


# ---------------------------------------------------------------------------
# Snapshot / signature
# ---------------------------------------------------------------------------

def _snapshot_signature(snap_seed: Tuple[Any, ...]) -> str:
    """sha256 of a canonical, language-neutral tuple representation."""
    return hashlib.sha256(repr(snap_seed).encode("utf-8")).hexdigest()


def _basin_discharge(world,
                     discharge: np.ndarray,
                     runoff: np.ndarray,
                     cell_km: float,
                     basin_id: int) -> Optional[BasinDischarge]:
    mask = (world.watershed_id == basin_id)
    n_cells = int(mask.sum())
    if n_cells == 0:
        return None

    area_km2 = float(n_cells) * float(cell_km) * float(cell_km)
    runoff_vol = float(runoff[mask].sum())

    # Outlet = max-discharge cell within the basin (emergent main outlet).
    disc_in = np.where(mask, discharge, -1.0)
    flat = int(disc_in.argmax())
    oy, ox = divmod(flat, disc_in.shape[1])
    outlet_q = float(discharge[oy, ox])
    max_cell_q = float(discharge[mask].max())

    # Specific discharge as an equivalent depth (mm/yr) over the basin.
    area_m2 = area_km2 * 1e6
    if area_m2 > 0:
        spec_mm_yr = outlet_q * _SECONDS_PER_YEAR / area_m2 * 1e3
    else:
        spec_mm_yr = 0.0

    return BasinDischarge(
        basin_id=int(basin_id),
        n_cells=n_cells,
        area_km2=area_km2,
        outlet_yx=(int(oy), int(ox)),
        outlet_discharge_m3s=outlet_q,
        runoff_volume_m3s=runoff_vol,
        specific_discharge_mm_yr=float(spec_mm_yr),
        max_cell_discharge_m3s=max_cell_q,
    )


def _field(world, name: str, fallback: float, shape) -> np.ndarray:
    arr = getattr(world, name, None)
    if arr is None:
        return np.full(shape, float(fallback), dtype=np.float64)
    a = np.asarray(arr, dtype=np.float64)
    if a.shape != tuple(shape):
        return np.full(shape, float(fallback), dtype=np.float64)
    return a


def observe_discharge(sim, config: Optional[DischargeConfig] = None
                      ) -> Optional[DischargeSnapshot]:
    """Pure read-only discharge snapshot. ``None`` if no world is wired."""
    cfg = config if config is not None else DischargeConfig()
    world = _resolve_world(sim)
    if world is None:
        return None

    flow_dir = np.asarray(world.flow_dir, dtype=np.uint8)
    river_mask = np.asarray(world.river_mask, dtype=bool)
    watershed_id = np.asarray(world.watershed_id, dtype=np.int32)
    shape = flow_dir.shape

    R = int(shape[0])
    cell_km = float(world.params.map_size_km) / float(R)
    map_area_km2 = float(R * R) * cell_km * cell_km

    precip = _field(world, "precip_mm", cfg.default_precip_mm, shape)
    temp = _field(world, "temp_c", cfg.default_temp_c, shape)
    runoff = runoff_field_m3s(precip, temp, cell_km, cfg)

    discharge = route_runoff(flow_dir, runoff)

    total_runoff = float(runoff.sum())
    # Outflow = discharge at every sink (cells whose flow leaves the domain).
    is_sink = (flow_dir == _D8_SINK) | (flow_dir > 7)
    total_outflow = float(discharge[is_sink].sum())
    resid = (abs(total_runoff - total_outflow) / max(total_runoff, 1e-9))

    cell_area_m2 = (cell_km * 1000.0) ** 2
    mean_runoff_mm_yr = float(
        runoff.mean() * _SECONDS_PER_YEAR / cell_area_m2 * 1e3) if R > 0 else 0.0

    flat_max = int(discharge.argmax())
    my, mx = divmod(flat_max, R)
    max_q = float(discharge[my, mx])

    mean_river_q = (float(discharge[river_mask].mean())
                    if bool(river_mask.any()) else 0.0)

    unique_ids = np.unique(watershed_id)
    valid_ids = [int(i) for i in unique_ids.tolist() if i >= 0]
    n_basins_total = len(valid_ids)

    basins: List[BasinDischarge] = []
    for bid in valid_ids:
        bd = _basin_discharge(world, discharge, runoff, cell_km, bid)
        if bd is None or bd.n_cells < cfg.min_basin_cells:
            continue
        basins.append(bd)

    n_considered = len(basins)
    basins.sort(key=lambda b: (-b.outlet_discharge_m3s, b.basin_id))
    top = tuple(basins[:cfg.top_basins])

    canonical_basins = tuple(
        (b.basin_id, b.n_cells, round(b.area_km2, 4), b.outlet_yx,
         round(b.outlet_discharge_m3s, 4), round(b.runoff_volume_m3s, 4),
         round(b.specific_discharge_mm_yr, 4),
         round(b.max_cell_discharge_m3s, 4))
        for b in sorted(basins, key=lambda b: b.basin_id)
    )
    sig = _snapshot_signature((
        int(sim.tick), round(cell_km, 6), round(map_area_km2, 4),
        round(total_runoff, 4), round(total_outflow, 4),
        round(resid, 9), round(mean_runoff_mm_yr, 4),
        round(max_q, 4), (int(my), int(mx)), round(mean_river_q, 4),
        n_basins_total, n_considered, canonical_basins,
    ))

    return DischargeSnapshot(
        tick=int(sim.tick),
        cell_km=cell_km,
        map_area_km2=map_area_km2,
        total_runoff_m3s=total_runoff,
        total_outflow_m3s=total_outflow,
        mass_balance_residual=float(resid),
        mean_runoff_mm_yr=float(mean_runoff_mm_yr),
        max_discharge_m3s=max_q,
        max_discharge_yx=(int(my), int(mx)),
        mean_river_discharge_m3s=float(mean_river_q),
        n_basins_total=n_basins_total,
        n_basins_considered=n_considered,
        basins_top=top,
        signature=sig,
    )


# ---------------------------------------------------------------------------
# Install / uninstall (mirrors wave 45 / 49 / 50)
# ---------------------------------------------------------------------------

def install_discharge_observer(sim,
                               config: Optional[DischargeConfig] = None
                               ) -> DischargeState:
    """Idempotent installer. Wraps ``sim.step`` once to capture snapshots
    every ``cfg.snapshot_every`` ticks."""
    cfg = config if config is not None else DischargeConfig()
    existing: Optional[DischargeState] = getattr(
        sim, "_discharge_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = DischargeState(config=cfg)
    sim._discharge_state = state

    original_step = sim.step

    def _wrapped_step(*args, **kwargs):
        result = original_step(*args, **kwargs)
        try:
            tick = int(sim.tick)
        except Exception:
            tick = 0
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            snap = observe_discharge(sim, cfg)
            if snap is not None:
                state.history.snapshots.append(snap)
        return result

    sim._discharge_original_step = original_step
    sim.step = _wrapped_step
    state.wrapped = True
    sim._discharge_wrapped = True
    return state


def uninstall_discharge_observer(sim) -> bool:
    """Restore the original ``sim.step``. ``True`` if anything was removed."""
    state = getattr(sim, "_discharge_state", None)
    if state is None:
        return False
    original = getattr(sim, "_discharge_original_step", None)
    if original is not None:
        sim.step = original
        del sim._discharge_original_step
    sim._discharge_wrapped = False
    del sim._discharge_state
    return True


def discharge_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards (does not mutate sim)."""
    state: Optional[DischargeState] = getattr(sim, "_discharge_state", None)
    if state is None:
        return {"installed": False}
    snaps = state.history.snapshots
    last = snaps[-1] if snaps else None
    return {
        "installed": True,
        "n_snapshots": len(snaps),
        "snapshot_every": state.config.snapshot_every,
        "last_signature": (last.signature if last is not None else None),
        "last_tick": (last.tick if last is not None else None),
        "total_runoff_m3s": (last.total_runoff_m3s
                             if last is not None else None),
        "total_outflow_m3s": (last.total_outflow_m3s
                              if last is not None else None),
        "mass_balance_residual": (last.mass_balance_residual
                                  if last is not None else None),
        "max_discharge_m3s": (last.max_discharge_m3s
                              if last is not None else None),
        "mean_river_discharge_m3s": (last.mean_river_discharge_m3s
                                     if last is not None else None),
        "n_basins_considered": (last.n_basins_considered
                                if last is not None else None),
    }


__all__ = [
    "DischargeConfig",
    "BasinDischarge",
    "DischargeSnapshot",
    "DischargeHistory",
    "DischargeState",
    "route_runoff",
    "runoff_field_m3s",
    "observe_discharge",
    "install_discharge_observer",
    "uninstall_discharge_observer",
    "discharge_summary",
]
