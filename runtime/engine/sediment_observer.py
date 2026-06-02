"""Genesis Engine — Wave 57 Exner mobile-bed / sediment-transport observer.

Read-only morphodynamic layer that closes the **water → sediment → relief**
loop on top of the emergent D8 drainage network. It reuses the Wave 53
discharge field (:mod:`engine.discharge_observer`) without duplicating any
routing logic and adds the missing piece named by the roadmap as the next
geology / hydrology milestone (veille 2026-06-02, DÉCOUVERTE_1 — Shallow
Water–Exner morphodynamics): a deterministic CPU **Exner bed-evolution**
operator. No mutation, no RNG, no ontology imposed.

Physics (transport-limited Exner)
---------------------------------

The bed evolves by conservation of sediment mass — the **Exner equation**

    (1 − λ) ∂z_b/∂t = − ∇·q_s

where ``λ`` is the bed porosity and ``q_s`` the volumetric sediment flux.
On the D8 graph the divergence ``∇·q_s`` at a cell is simply ``q_out − q_in``
(one out-edge per cell), so the discrete bed-change rate is

    (1 − λ) · cell_area · ∂z/∂t = q_in − q_out   (>0 aggradation, <0 incision)

Each cell carries a **transport capacity** set by a stream-power law on the
*already emergent* discharge ``Q`` (Wave 53) and the local downstream slope
``S`` from the emergent elevation field:

    q_cap = k_transport · Q^m · S^n          (Engelund-Hansen / Bagnold family)

The flow is routed downstream once, in exact topological order (Kahn), and
at every cell:

* if ``q_in ≥ q_cap`` the surplus **deposits** → ``q_out = q_cap`` ;
* if ``q_in < q_cap`` the deficit is **eroded** from the bed (transport-
  limited, or optionally capped by a detachment limit) → ``q_out = q_in + e``.

What it measures (all emergent, classical geomorphology)
--------------------------------------------------------

1. **Erosion / deposition** volumetric rates (m³/s) per cell.
2. **Denudation / incision** as a bed-lowering / aggradation rate (mm/yr).
3. **Sediment export** ``Σ q_out`` at the basin outlets and domain sinks —
   the emergent sediment yield of the landscape.

Exact mass closure (used as the smoke / test invariant)
-------------------------------------------------------

Because routing telescopes along the one-out-edge graph,

    Σ erosion  ==  Σ deposition  +  Σ export(sinks)

holds to machine precision for *any* capacity field — every grain eroded is
either deposited downstream or leaves the domain at a sink.

Observer contract (mirrors Waves 49 / 51 / 53 / 55)
---------------------------------------------------

- ``SedimentConfig`` / ``BasinSediment`` / ``SedimentSnapshot`` /
  ``SedimentHistory`` / ``SedimentState`` dataclasses (frozen where data).
- ``observe_sediment(sim, cfg)`` — **read-only**, returns a snapshot.
- ``install_sediment_observer(sim, cfg)`` — idempotent, wraps ``sim.step``.
- ``uninstall_sediment_observer(sim)`` — restores ``sim.step``.
- ``sediment_summary(sim)`` — diagnostic dict for dashboards.

Determinism
-----------

No RNG. The topological sweep is row-major on every queue iteration and the
signature is ``sha256`` of a canonical tuple, so two runs with the same world
seed produce identical snapshot streams.

Stone-age compliance
--------------------

The observer never declares rivers, sediment or relief change as scripted
events. It reads the emergent D8 graph, discharge and elevation, applies a
mass-conserving Exner balance and reports. No mutation of any world or sim
array — the *bed itself is not modified*; the observer reports the rate at
which the closed physics *would* evolve it.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Reuse Wave 53 routing + world access verbatim (no duplication).
from engine.discharge_observer import (
    _D8_DX,
    _D8_DY,
    _D8_SINK,
    _SECONDS_PER_YEAR,
    _field,
    _resolve_world,
    route_runoff,
    runoff_field_m3s,
)

# D8 link length factor (1 for orthogonal, √2 for diagonal moves) — same
# convention/order as engine.world_genesis._D8_DIST.
_D8_DIST = np.array(
    [1.0, np.sqrt(2.0), 1.0, np.sqrt(2.0), 1.0, np.sqrt(2.0), 1.0, np.sqrt(2.0)],
    dtype=np.float64,
)


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SedimentConfig:
    """Read-only knobs for the Exner sediment-transport observer.

    The transport capacity ``q_cap = k_transport · Q^m_exp · S^n_exp`` is a
    classic stream-power form. ``detachment_limited`` optionally caps the
    erosion a single cell may supply per pass at
    ``k_erode · Q^m_exp · S^n_exp`` (alluvial → bedrock transition); when
    ``False`` the model is purely transport-limited (unlimited bed supply).
    Both regimes conserve mass exactly.
    """
    snapshot_every: int = 64
    min_basin_cells: int = 4
    top_basins: int = 5
    k_transport: float = 4.0e-4    # stream-power transport coefficient
    m_exp: float = 1.5             # discharge exponent
    n_exp: float = 1.0             # slope exponent
    porosity: float = 0.35         # bed porosity λ (Exner)
    detachment_limited: bool = False
    k_erode: float = 1.0e-4        # detachment coefficient (if limited)
    # Runoff balance knobs (forwarded to the Wave 53 discharge field).
    et_mm_per_degc: float = 45.0
    default_precip_mm: float = 800.0
    default_temp_c: float = 12.0


@dataclass(frozen=True)
class BasinSediment:
    """Per-basin emergent sediment budget (read-only)."""
    basin_id: int
    n_cells: int
    area_km2: float
    outlet_yx: Tuple[int, int]
    sediment_export_m3s: float       # q_out at the basin outlet
    erosion_m3s: float               # Σ erosion within basin
    deposition_m3s: float            # Σ deposition within basin
    denudation_mm_yr: float          # net (E − D) as basin-average lowering
    max_incision_mm_yr: float        # fastest bed lowering in basin


@dataclass(frozen=True)
class SedimentSnapshot:
    """Global + top-K basin Exner budget snapshot at a given sim tick."""
    tick: int
    cell_km: float
    map_area_km2: float
    total_erosion_m3s: float
    total_deposition_m3s: float
    total_export_m3s: float          # Σ q_out at domain sinks
    mass_balance_residual: float     # |ΣE − (ΣD + export)| / max(ΣE, ε)
    mean_denudation_mm_yr: float     # map-average bed-lowering rate
    max_incision_mm_yr: float
    max_incision_yx: Tuple[int, int]
    max_aggradation_mm_yr: float
    n_basins_total: int
    n_basins_considered: int
    basins_top: Tuple[BasinSediment, ...]
    signature: str


@dataclass
class SedimentHistory:
    snapshots: List[SedimentSnapshot] = field(default_factory=list)


@dataclass
class SedimentState:
    config: SedimentConfig
    history: SedimentHistory = field(default_factory=SedimentHistory)
    wrapped: bool = False


# ---------------------------------------------------------------------------
# Pure-function morphodynamics
# ---------------------------------------------------------------------------

def downstream_slope(elevation_m: np.ndarray,
                     flow_dir: np.ndarray,
                     cell_km: float) -> np.ndarray:
    """Non-negative slope (rise/run) from each cell to its D8 receiver.

    Mirrors :func:`engine.world_genesis._local_downslope`: the drop in metres
    over the link length in metres, clamped at ``0`` (flats / sinks → ``0``).
    """
    if elevation_m.shape != flow_dir.shape:
        raise ValueError("elevation and flow_dir must share shape")
    R0, R1 = flow_dir.shape
    yy, xx = np.indices((R0, R1))
    fd = np.asarray(flow_dir, dtype=np.uint8)
    valid = (fd != _D8_SINK) & (fd <= 7)
    idx = np.clip(fd, 0, 7)
    dx = np.where(valid, _D8_DX[idx], 0)
    dy = np.where(valid, _D8_DY[idx], 0)
    rx = np.clip(xx + dx, 0, R1 - 1)
    ry = np.clip(yy + dy, 0, R0 - 1)
    drop_m = np.asarray(elevation_m, dtype=np.float64) - \
        np.asarray(elevation_m, dtype=np.float64)[ry, rx]
    dist_m = np.where(valid, _D8_DIST[idx] * float(cell_km) * 1000.0, 1.0)
    return np.maximum(drop_m, 0.0) / np.maximum(dist_m, 1e-3)


def transport_capacity(discharge: np.ndarray,
                       slope: np.ndarray,
                       cfg: SedimentConfig) -> np.ndarray:
    """Stream-power transport capacity ``k · Q^m · S^n`` (m³/s, ≥ 0)."""
    Q = np.maximum(np.asarray(discharge, dtype=np.float64), 0.0)
    S = np.maximum(np.asarray(slope, dtype=np.float64), 0.0)
    return cfg.k_transport * np.power(Q, cfg.m_exp) * np.power(S, cfg.n_exp)


def route_sediment(flow_dir: np.ndarray,
                   capacity: np.ndarray,
                   erosion_limit: Optional[np.ndarray] = None
                   ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Capacity-limited Exner sediment routing down the D8 graph.

    Returns ``(q_out, erosion, deposition)`` float64 arrays of the input
    shape. ``q_out`` is the sediment flux leaving each cell; ``erosion`` and
    ``deposition`` are the non-negative bed exchange at each cell
    (``q_out − q_in`` split into its positive/negative parts).

    Invariants (used by the smoke / tests):

    * **Exact mass closure** — ``Σ erosion == Σ deposition + Σ q_out[sinks]``
      for any capacity field (telescoping along one-out-edge routing).
    * **Transport-limited cap** — ``q_out ≤ capacity`` everywhere; with
      ``erosion_limit=None`` a cell with spare capacity erodes up to it.
    * **Headwater identity** — a headwater (no inflow) erodes exactly its own
      capacity (or its detachment limit, if smaller).

    Bit-deterministic: Kahn topological order, row-major queue, with a
    row-major safety net for any (degenerate) cycle so the routine always
    terminates.
    """
    if flow_dir.shape != capacity.shape:
        raise ValueError("flow_dir and capacity must share shape")
    R0, R1 = flow_dir.shape
    fd = np.asarray(flow_dir, dtype=np.uint8)
    cap = np.maximum(np.asarray(capacity, dtype=np.float64), 0.0)
    if erosion_limit is not None:
        elim = np.maximum(np.asarray(erosion_limit, dtype=np.float64), 0.0)
    else:
        elim = None

    q_in = np.zeros((R0, R1), dtype=np.float64)
    q_out = np.zeros((R0, R1), dtype=np.float64)
    erosion = np.zeros((R0, R1), dtype=np.float64)
    deposition = np.zeros((R0, R1), dtype=np.float64)

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

    def _resolve(y: int, x: int) -> None:
        inflow = q_in[y, x]
        c = cap[y, x]
        if inflow >= c:
            out = c
        elif elim is None:
            out = c
        else:
            out = inflow + min(c - inflow, elim[y, x])
        q_out[y, x] = out
        if out >= inflow:
            erosion[y, x] = out - inflow
        else:
            deposition[y, x] = inflow - out

    remaining = in_deg.copy()
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
        _resolve(y, x)
        dy = int(down_y[y, x])
        if dy < 0:
            continue
        dx = int(down_x[y, x])
        q_in[dy, dx] += q_out[y, x]
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
                _resolve(y, x)
                dy = int(down_y[y, x])
                if dy < 0:
                    continue
                dx = int(down_x[y, x])
                if not processed[dy, dx]:
                    q_in[dy, dx] += q_out[y, x]

    return q_out, erosion, deposition


def bed_change_rate(erosion: np.ndarray,
                    deposition: np.ndarray,
                    cell_km: float,
                    porosity: float) -> np.ndarray:
    """Exner bed-elevation rate ``∂z/∂t`` (mm/yr).

    ``(1 − λ) · cell_area · ∂z/∂t = q_in − q_out = deposition − erosion``.
    Positive = aggradation, negative = incision.
    """
    cell_area_m2 = (float(cell_km) * 1000.0) ** 2
    one_minus_lambda = max(1.0 - float(porosity), 1e-6)
    dz_dt_m_s = (np.asarray(deposition, dtype=np.float64)
                 - np.asarray(erosion, dtype=np.float64)) \
        / (one_minus_lambda * cell_area_m2)
    return dz_dt_m_s * _SECONDS_PER_YEAR * 1000.0  # m/s → mm/yr


# ---------------------------------------------------------------------------
# Snapshot / signature
# ---------------------------------------------------------------------------

def _snapshot_signature(snap_seed: Tuple[Any, ...]) -> str:
    return hashlib.sha256(repr(snap_seed).encode("utf-8")).hexdigest()


def _basin_sediment(world,
                    q_out: np.ndarray,
                    erosion: np.ndarray,
                    deposition: np.ndarray,
                    dz_mm_yr: np.ndarray,
                    cell_km: float,
                    basin_id: int) -> Optional[BasinSediment]:
    mask = (world.watershed_id == basin_id)
    n_cells = int(mask.sum())
    if n_cells == 0:
        return None
    area_km2 = float(n_cells) * float(cell_km) * float(cell_km)

    ero = float(erosion[mask].sum())
    dep = float(deposition[mask].sum())

    # Outlet = max-export cell within the basin (emergent main outlet).
    qo_in = np.where(mask, q_out, -1.0)
    flat = int(qo_in.argmax())
    oy, ox = divmod(flat, qo_in.shape[1])

    # Net basin denudation as a basin-average lowering rate (mm/yr): convert
    # the net eroded volume (E − D) to a rock-equivalent depth over the basin
    # footprint. Positive = the basin is net-eroding (exporting sediment).
    area_m2 = area_km2 * 1e6
    net_vol_m3s = ero - dep
    if area_m2 > 0:
        denud_mm_yr = net_vol_m3s * _SECONDS_PER_YEAR / area_m2 * 1e3
    else:
        denud_mm_yr = 0.0

    incision = float(-dz_mm_yr[mask].min()) if n_cells else 0.0  # +ve lowering

    return BasinSediment(
        basin_id=int(basin_id),
        n_cells=n_cells,
        area_km2=area_km2,
        outlet_yx=(int(oy), int(ox)),
        sediment_export_m3s=float(q_out[oy, ox]),
        erosion_m3s=ero,
        deposition_m3s=dep,
        denudation_mm_yr=float(denud_mm_yr),
        max_incision_mm_yr=float(max(incision, 0.0)),
    )


def observe_sediment(sim, config: Optional[SedimentConfig] = None
                     ) -> Optional[SedimentSnapshot]:
    """Pure read-only Exner sediment snapshot. ``None`` if no world wired."""
    cfg = config if config is not None else SedimentConfig()
    world = _resolve_world(sim)
    if world is None:
        return None

    flow_dir = np.asarray(world.flow_dir, dtype=np.uint8)
    watershed_id = np.asarray(world.watershed_id, dtype=np.int32)
    shape = flow_dir.shape
    R = int(shape[0])
    cell_km = float(world.params.map_size_km) / float(R)
    map_area_km2 = float(R * R) * cell_km * cell_km

    elevation = _field(world, "elevation_m", 0.0, shape)
    precip = _field(world, "precip_mm", cfg.default_precip_mm, shape)
    temp = _field(world, "temp_c", cfg.default_temp_c, shape)

    # Discharge from the Wave 53 LTI operator (no duplication).
    from engine.discharge_observer import DischargeConfig
    dcfg = DischargeConfig(
        et_mm_per_degc=cfg.et_mm_per_degc,
        default_precip_mm=cfg.default_precip_mm,
        default_temp_c=cfg.default_temp_c,
    )
    runoff = runoff_field_m3s(precip, temp, cell_km, dcfg)
    discharge = route_runoff(flow_dir, runoff)

    slope = downstream_slope(elevation, flow_dir, cell_km)
    capacity = transport_capacity(discharge, slope, cfg)
    if cfg.detachment_limited:
        elim = cfg.k_erode * np.power(np.maximum(discharge, 0.0), cfg.m_exp) \
            * np.power(np.maximum(slope, 0.0), cfg.n_exp)
    else:
        elim = None
    q_out, erosion, deposition = route_sediment(flow_dir, capacity, elim)

    dz_mm_yr = bed_change_rate(erosion, deposition, cell_km, cfg.porosity)

    total_ero = float(erosion.sum())
    total_dep = float(deposition.sum())
    is_sink = (flow_dir == _D8_SINK) | (flow_dir > 7)
    total_export = float(q_out[is_sink].sum())
    resid = abs(total_ero - (total_dep + total_export)) / max(total_ero, 1e-9)

    net_vol = total_ero - total_dep  # = export (closure)
    mean_denud_mm_yr = (net_vol * _SECONDS_PER_YEAR
                        / (map_area_km2 * 1e6) * 1e3) if map_area_km2 > 0 \
        else 0.0

    flat_min = int(dz_mm_yr.argmin())
    iy, ix = divmod(flat_min, R)
    max_incision = float(-dz_mm_yr[iy, ix])      # fastest lowering (+ve)
    max_aggradation = float(dz_mm_yr.max())      # fastest raising (+ve)

    unique_ids = np.unique(watershed_id)
    valid_ids = [int(i) for i in unique_ids.tolist() if i >= 0]
    n_basins_total = len(valid_ids)

    basins: List[BasinSediment] = []
    for bid in valid_ids:
        bs = _basin_sediment(world, q_out, erosion, deposition,
                             dz_mm_yr, cell_km, bid)
        if bs is None or bs.n_cells < cfg.min_basin_cells:
            continue
        basins.append(bs)

    n_considered = len(basins)
    basins.sort(key=lambda b: (-b.sediment_export_m3s, b.basin_id))
    top = tuple(basins[:cfg.top_basins])

    canonical_basins = tuple(
        (b.basin_id, b.n_cells, round(b.area_km2, 4), b.outlet_yx,
         round(b.sediment_export_m3s, 6), round(b.erosion_m3s, 6),
         round(b.deposition_m3s, 6), round(b.denudation_mm_yr, 6),
         round(b.max_incision_mm_yr, 6))
        for b in sorted(basins, key=lambda b: b.basin_id)
    )
    sig = _snapshot_signature((
        int(sim.tick), round(cell_km, 6), round(map_area_km2, 4),
        round(total_ero, 6), round(total_dep, 6), round(total_export, 6),
        round(resid, 9), round(mean_denud_mm_yr, 6),
        round(max_incision, 6), (int(iy), int(ix)),
        round(max_aggradation, 6),
        n_basins_total, n_considered, canonical_basins,
    ))

    return SedimentSnapshot(
        tick=int(sim.tick),
        cell_km=cell_km,
        map_area_km2=map_area_km2,
        total_erosion_m3s=total_ero,
        total_deposition_m3s=total_dep,
        total_export_m3s=total_export,
        mass_balance_residual=float(resid),
        mean_denudation_mm_yr=float(mean_denud_mm_yr),
        max_incision_mm_yr=float(max(max_incision, 0.0)),
        max_incision_yx=(int(iy), int(ix)),
        max_aggradation_mm_yr=float(max(max_aggradation, 0.0)),
        n_basins_total=n_basins_total,
        n_basins_considered=n_considered,
        basins_top=top,
        signature=sig,
    )


# ---------------------------------------------------------------------------
# Install / uninstall (mirrors Waves 49 / 53 / 55)
# ---------------------------------------------------------------------------

def install_sediment_observer(sim,
                              config: Optional[SedimentConfig] = None
                              ) -> SedimentState:
    """Idempotent installer. Wraps ``sim.step`` once to capture snapshots
    every ``cfg.snapshot_every`` ticks."""
    cfg = config if config is not None else SedimentConfig()
    existing: Optional[SedimentState] = getattr(sim, "_sediment_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = SedimentState(config=cfg)
    sim._sediment_state = state

    original_step = sim.step

    def _wrapped_step(*args, **kwargs):
        result = original_step(*args, **kwargs)
        try:
            tick = int(sim.tick)
        except Exception:
            tick = 0
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            snap = observe_sediment(sim, cfg)
            if snap is not None:
                state.history.snapshots.append(snap)
        return result

    sim._sediment_original_step = original_step
    sim.step = _wrapped_step
    state.wrapped = True
    sim._sediment_wrapped = True
    return state


def uninstall_sediment_observer(sim) -> bool:
    """Restore the original ``sim.step``. ``True`` if anything was removed."""
    state = getattr(sim, "_sediment_state", None)
    if state is None:
        return False
    original = getattr(sim, "_sediment_original_step", None)
    if original is not None:
        sim.step = original
        del sim._sediment_original_step
    sim._sediment_wrapped = False
    del sim._sediment_state
    return True


def sediment_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards (does not mutate sim)."""
    state: Optional[SedimentState] = getattr(sim, "_sediment_state", None)
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
        "total_erosion_m3s": (last.total_erosion_m3s
                              if last is not None else None),
        "total_deposition_m3s": (last.total_deposition_m3s
                                 if last is not None else None),
        "total_export_m3s": (last.total_export_m3s
                             if last is not None else None),
        "mass_balance_residual": (last.mass_balance_residual
                                  if last is not None else None),
        "mean_denudation_mm_yr": (last.mean_denudation_mm_yr
                                  if last is not None else None),
        "max_incision_mm_yr": (last.max_incision_mm_yr
                               if last is not None else None),
        "n_basins_considered": (last.n_basins_considered
                                if last is not None else None),
    }


__all__ = [
    "SedimentConfig",
    "BasinSediment",
    "SedimentSnapshot",
    "SedimentHistory",
    "SedimentState",
    "downstream_slope",
    "transport_capacity",
    "route_sediment",
    "bed_change_rate",
    "observe_sediment",
    "install_sediment_observer",
    "uninstall_sediment_observer",
    "sediment_summary",
]
