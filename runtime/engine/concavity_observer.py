"""Genesis Engine - Wave 63 emergent channel-concavity / chi-steepness observer.

Read-only fluvial-geomorphology layer that quantifies the *scaling* of the
emergent drainage network the tick has already built. Where Wave 49
(``watershed_observer``) measured the network *topology* (Strahler orders,
Horton ratios, drainage density) and Wave 62 (``hypsometry_observer``) measured
the *area-altitude* distribution, this wave measures the third canonical
fluvial descriptor: the **slope-area relationship** and its modern, low-noise
complement, the **chi (chi) integral transform**.

Nothing here is scripted. The observer reads the same emergent fields the tick
produced - ``world.elevation_m``, the D8 ``world.flow_dir`` and the drainage
area ``world.flow_acc`` (as Waves 49 / 53 / 57 do) - and overlays two classical
laws. The laws are *measured*, never imposed: the world makes the terrain, the
observer reports whether that terrain exhibits the law and with what exponents.

Slope-area / Flint's law
-------------------------
For detachment-limited fluvial incision the stream-power model
``E = K * A^m * S^n`` predicts, at topographic steady state under uniform
uplift, a power-law between local channel slope ``S`` and upstream drainage
area ``A`` (Flint 1974; Hack 1957)::

    S = k_s * A^(-theta)        theta = m / n  (concavity index)
    log S = log k_s - theta * log A

A least-squares fit of ``log S`` on ``log A`` over the channel cells recovers
the **concavity index** ``theta`` (the slope, negated) and the **steepness
coefficient** ``k_s`` (the intercept, exponentiated). Theory and worldwide
observation put graded channels in a narrow band ``0.4 < theta < 0.6`` (Wobus
et al. 2006; Kirby & Whipple 2012).

Chi (chi) integral transform - Perron & Royden (2013)
-----------------------------------------------------
The along-river slope is a noisy local derivative. The integral method
replaces it with a transformed horizontal coordinate integrated *upstream* from
base level::

    chi(x) = integral_{x_base}^{x} (A0 / A(x'))^theta_ref  dx'

With a reference concavity ``theta_ref`` and reference area ``A0 = 1 m^2``, a
steady-state channel is **linear in chi**: ``z = z_base + ksn * chi`` where the
slope ``ksn`` is the **normalised channel steepness** - a low-noise,
basin-comparable erosion-rate proxy (Mudd et al. 2014). The observer integrates
chi by a deterministic downstream->upstream sweep (decreasing ``flow_acc``) and
fits ``z`` against ``chi``.

Falsifiable invariants (asserted by the smoke / tests)
------------------------------------------------------
1. Power-law recovery (pivot). A synthetic ``(A, S)`` built as
   ``S = k_s * A^(-theta)`` exactly is recovered by ``fit_flint_law`` to the
   floating-point tolerance: ``theta`` and ``k_s`` to ~1e-9, ``R^2 == 1``.
   Falsified if the log-log regression does not invert the construction.
2. Concavity scale invariance. ``theta`` is invariant under ``A -> c*A`` and
   ``S -> c*S`` (only the intercept ``k_s`` shifts). A pure diagnostic of
   network *shape*, blind to area units and vertical exaggeration.
3. Chi base level + monotonicity. ``chi >= 0`` everywhere, ``chi == 0`` at the
   channel mouth (base level), and ``chi`` is strictly increasing upstream
   along any flow path (the integrand ``(A0/A)^theta_ref`` is strictly
   positive).
4. Chi-elevation linearity. A synthetic profile built as ``z = a + b*chi``
   is recovered by ``fit_chi_elevation`` with ``R^2 == 1`` and slope ``b``
   (= ksn) to the floating-point tolerance.
5. Bounds. ``R^2 in [0, 1]`` for both fits; a finite ``theta`` requires at
   least two channel cells with positive slope and distinct areas.

Observer contract (mirrors Waves 53 / 57 / 59 / 61 / 62)
--------------------------------------------------------
``ConcavityConfig`` / ``ConcavitySnapshot`` / ``ConcavityHistory`` /
``ConcavityState`` dataclasses; pure helpers ``channel_slope_area`` /
``fit_flint_law`` / ``chi_transform`` / ``fit_chi_elevation`` /
``concavity_stage``; ``observe_concavity(sim, cfg)`` - read-only, ``None`` if
no world wired; idempotent ``install_concavity_observer`` /
``uninstall_concavity_observer`` (returns ``bool``); ``concavity_summary``
diagnostic dict.

Determinism
-----------
No RNG. The chi sweep processes cells in decreasing ``flow_acc`` with a
row-major flat-index tie-break, and the signature is ``sha256`` of a canonical
tuple of rounded aggregate metrics, so two runs with the same world seed
produce identical snapshot streams.

Stone-age compliance
---------------------
The observer never declares channels, concavity or steepness - it reads the D8
graph and elevation field emergent from the world and reports the scaling law
they exhibit. No mutation of any world or sim array.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Reuse the Wave 53 world-access helpers verbatim (no duplication).
from engine.discharge_observer import _field, _resolve_world

# D8 convention matches engine.world_genesis / engine.watershed_observer.
_D8_DX = np.array([1, 1, 0, -1, -1, -1, 0, 1], dtype=np.int8)
_D8_DY = np.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=np.int8)
_D8_LEN = np.array([1.0, math.sqrt(2.0), 1.0, math.sqrt(2.0),
                    1.0, math.sqrt(2.0), 1.0, math.sqrt(2.0)], dtype=np.float64)
_D8_SINK = 255  # convention used by world_genesis flow_dir

_M_PER_KM = 1000.0

# Reference concavity for the chi transform (Perron & Royden 2013 convention).
# A fixed reference makes ksn comparable across landscapes ("normalised").
REF_CONCAVITY = 0.45
# Reference drainage area A0 (m^2). With A0 = 1, ksn is the raw chi-z slope.
REF_AREA_M2 = 1.0

# Stream-power graded-channel concavity band (Wobus 2006; Kirby & Whipple 2012).
CONCAVITY_GRADED_LO = 0.40
CONCAVITY_GRADED_HI = 0.60


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConcavityConfig:
    """Read-only knobs for the channel-concavity observer."""
    snapshot_every: int = 64
    # Minimum channel cells with positive slope required to attempt a fit.
    min_fit_cells: int = 8
    # Reference concavity used for the chi transform (normalised steepness).
    ref_concavity: float = REF_CONCAVITY
    ref_area_m2: float = REF_AREA_M2


@dataclass(frozen=True)
class ConcavitySnapshot:
    """Map-wide channel-concavity roll-up at one tick (read-only)."""
    tick: int
    n_cells: int
    cell_km: float
    n_channel_cells: int          # cells in river_mask with a downstream link
    n_fit_cells: int              # channel cells with positive slope (fit set)
    concavity_theta: float        # m/n from the slope-area log-log regression
    steepness_ks: float           # k_s coefficient (dimensional)
    slope_area_r2: float          # R^2 of the log S vs log A regression
    ref_concavity: float          # theta_ref used for the chi transform
    ksn: float                    # normalised steepness = chi-z OLS slope
    chi_z_r2: float               # R^2 of the z vs chi regression
    chi_max: float                # largest chi in the channel network (m)
    mean_channel_slope: float     # mean positive channel slope (dimensionless)
    stage: str                    # concavity band label (invariant -> bands)
    signature: str


@dataclass
class ConcavityHistory:
    snapshots: List[ConcavitySnapshot] = field(default_factory=list)


@dataclass
class ConcavityState:
    config: ConcavityConfig
    history: ConcavityHistory = field(default_factory=ConcavityHistory)
    wrapped: bool = False


# ---------------------------------------------------------------------------
# Slope-area / Flint's law (pure, vectorised)
# ---------------------------------------------------------------------------

def channel_slope_area(elevation: np.ndarray,
                       flow_dir: np.ndarray,
                       flow_acc: np.ndarray,
                       river_mask: np.ndarray,
                       cell_m: float,
                       ) -> Tuple[np.ndarray, np.ndarray]:
    """Per-channel-cell drainage area (m^2) and local downslope gradient.

    For every river cell with a valid in-bounds downstream neighbour, returns
    ``(area_m2, slope)`` where ``slope = (z - z_down) / segment_length``. Cells
    whose slope is non-positive (pits / flats from the raw DEM) are kept in the
    raw output with their (possibly negative) slope; the Flint fit filters them.

    Returns two 1-D arrays aligned cell-by-cell (area, slope).
    """
    R0, R1 = flow_dir.shape
    z = np.asarray(elevation, dtype=np.float64)
    acc = np.asarray(flow_acc, dtype=np.float64)
    cell_area = float(cell_m) * float(cell_m)

    areas: List[float] = []
    slopes: List[float] = []
    ys, xs = np.where(np.asarray(river_mask, dtype=bool))
    for y, x in zip(ys.tolist(), xs.tolist()):
        fd = int(flow_dir[y, x])
        if fd == _D8_SINK:
            continue
        ny = y + int(_D8_DY[fd])
        nx = x + int(_D8_DX[fd])
        if not (0 <= ny < R0 and 0 <= nx < R1):
            continue
        seg_len = float(_D8_LEN[fd]) * float(cell_m)
        if seg_len <= 0.0:
            continue
        slope = (float(z[y, x]) - float(z[ny, nx])) / seg_len
        # Drainage area in m^2 (flow_acc is the upstream cell count).
        area_m2 = max(float(acc[y, x]), 1.0) * cell_area
        areas.append(area_m2)
        slopes.append(slope)
    return np.asarray(areas, dtype=np.float64), np.asarray(slopes, dtype=np.float64)


def _ols(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    """Closed-form simple linear regression ``y = a + b*x``.

    Returns ``(slope_b, intercept_a, r2)``. ``r2`` is 0.0 when the predictor
    has zero variance (degenerate fit). Deterministic, no lstsq.
    """
    n = x.size
    if n < 2:
        return 0.0, (float(y[0]) if n == 1 else 0.0), 0.0
    xm = float(x.mean())
    ym = float(y.mean())
    dx = x - xm
    dy = y - ym
    sxx = float(np.dot(dx, dx))
    if sxx <= 0.0:
        return 0.0, ym, 0.0
    b = float(np.dot(dx, dy)) / sxx
    a = ym - b * xm
    ss_tot = float(np.dot(dy, dy))
    resid = y - (a + b * x)
    ss_res = float(np.dot(resid, resid))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 1.0
    # Clamp tiny negative round-off in R^2 to the valid [0, 1] band.
    r2 = max(0.0, min(1.0, r2))
    return b, a, r2


def fit_flint_law(area_m2: np.ndarray, slope: np.ndarray
                  ) -> Tuple[float, float, float, int]:
    """Fit ``S = k_s * A^(-theta)`` by OLS on ``log S`` vs ``log A``.

    Only cells with ``A > 0`` and ``S > 0`` enter the fit. Returns
    ``(theta, k_s, r2, n_points)``. With fewer than two valid points the fit
    is degenerate and returns ``(0.0, 0.0, 0.0, n_points)``.
    """
    a = np.asarray(area_m2, dtype=np.float64)
    s = np.asarray(slope, dtype=np.float64)
    good = (a > 0.0) & (s > 0.0) & np.isfinite(a) & np.isfinite(s)
    a = a[good]
    s = s[good]
    n = int(a.size)
    if n < 2:
        return 0.0, 0.0, 0.0, n
    log_a = np.log(a)
    log_s = np.log(s)
    b, intercept, r2 = _ols(log_a, log_s)
    theta = -b              # slope of log S vs log A is -theta
    k_s = float(math.exp(intercept))
    return float(theta), k_s, float(r2), n


# ---------------------------------------------------------------------------
# Chi (chi) integral transform - Perron & Royden (2013)
# ---------------------------------------------------------------------------

def chi_transform(flow_dir: np.ndarray,
                  flow_acc: np.ndarray,
                  river_mask: np.ndarray,
                  cell_m: float,
                  theta_ref: float = REF_CONCAVITY,
                  a0_m2: float = REF_AREA_M2,
                  ) -> np.ndarray:
    """Integrate ``chi = int (A0/A)^theta_ref dx`` upstream from base level.

    Returns a float64 ``chi`` field with ``chi == 0`` for non-channel cells and
    for channel mouths (channel cells whose downstream neighbour leaves the
    network or is a sink). Channel cells accumulate ``(A0/A)^theta_ref * dx``
    from their downstream neighbour, computed by a deterministic
    decreasing-``flow_acc`` sweep (downstream is always processed first because
    it carries strictly more accumulation than its upstream contributors).
    """
    R0, R1 = flow_dir.shape
    chi = np.zeros((R0, R1), dtype=np.float64)
    mask = np.asarray(river_mask, dtype=bool)
    if not bool(mask.any()):
        return chi
    acc = np.asarray(flow_acc, dtype=np.float64)
    cell_area = float(cell_m) * float(cell_m)

    # Channel cells ordered by decreasing accumulation (downstream first).
    ys, xs = np.where(mask)
    flat = ys.astype(np.int64) * R1 + xs.astype(np.int64)
    acc_vals = acc[ys, xs]
    # Sort by (-acc, flat_index) for a deterministic topological-by-area order.
    order = np.lexsort((flat, -acc_vals))
    ys = ys[order]
    xs = xs[order]

    for y, x in zip(ys.tolist(), xs.tolist()):
        fd = int(flow_dir[y, x])
        if fd == _D8_SINK:
            chi[y, x] = 0.0
            continue
        ny = y + int(_D8_DY[fd])
        nx = x + int(_D8_DX[fd])
        if not (0 <= ny < R0 and 0 <= nx < R1) or not bool(mask[ny, nx]):
            # Downstream leaves the channel network -> this cell is base level.
            chi[y, x] = 0.0
            continue
        seg_len = float(_D8_LEN[fd]) * float(cell_m)
        area_m2 = max(float(acc[y, x]), 1.0) * cell_area
        integrand = (float(a0_m2) / area_m2) ** float(theta_ref)
        chi[y, x] = chi[ny, nx] + integrand * seg_len
    return chi


def fit_chi_elevation(chi: np.ndarray,
                      elevation: np.ndarray,
                      river_mask: np.ndarray,
                      ) -> Tuple[float, float, float, int]:
    """Fit ``z = z_base + ksn * chi`` by OLS over channel cells.

    Returns ``(ksn, intercept, r2, n_points)``. At topographic steady state the
    chi-z relationship is linear with slope ``ksn`` (normalised steepness).
    """
    mask = np.asarray(river_mask, dtype=bool)
    c = np.asarray(chi, dtype=np.float64)[mask]
    z = np.asarray(elevation, dtype=np.float64)[mask]
    good = np.isfinite(c) & np.isfinite(z)
    c = c[good]
    z = z[good]
    n = int(c.size)
    if n < 2:
        return 0.0, (float(z[0]) if n == 1 else 0.0), 0.0, n
    ksn, intercept, r2 = _ols(c, z)
    return float(ksn), float(intercept), float(r2), n


def concavity_stage(theta: float, r2: float = 1.0) -> str:
    """Label the concavity band (stream-power graded channel = 0.40-0.60)."""
    if not math.isfinite(theta):
        return "degenerate"
    if theta < 0.0:
        return "convex"                      # convex-up profile (uplift front)
    if theta < CONCAVITY_GRADED_LO:
        return "low-concavity"               # transitional / debris-flow domain
    if theta <= CONCAVITY_GRADED_HI:
        return "graded"                      # steady-state fluvial band
    return "high-concavity"                  # strongly concave / transient


# ---------------------------------------------------------------------------
# Map-wide observation (read-only)
# ---------------------------------------------------------------------------

def observe_concavity(sim, config: Optional[ConcavityConfig] = None
                      ) -> Optional[ConcavitySnapshot]:
    """Pure read-only channel-concavity snapshot. ``None`` if no world wired."""
    cfg = config if config is not None else ConcavityConfig()
    world = _resolve_world(sim)
    if world is None:
        return None

    flow_dir = np.asarray(world.flow_dir, dtype=np.uint8)
    shape = flow_dir.shape
    R = int(shape[0])
    if R == 0:
        return None
    cell_km = float(world.params.map_size_km) / float(R)
    cell_m = cell_km * _M_PER_KM

    elev = _field(world, "elevation_m", 0.0, shape)
    flow_acc = np.asarray(getattr(world, "flow_acc", np.zeros(shape)),
                          dtype=np.float64)
    river_mask = np.asarray(getattr(world, "river_mask",
                                    np.zeros(shape, dtype=bool)), dtype=bool)
    n_cells = int(elev.size)
    n_channel = int(river_mask.sum())

    # Slope-area / Flint's law.
    area_m2, slope = channel_slope_area(
        elev, flow_dir, flow_acc, river_mask, cell_m)
    theta, k_s, sa_r2, n_fit = fit_flint_law(area_m2, slope)
    pos = slope[slope > 0.0]
    mean_channel_slope = float(pos.mean()) if pos.size else 0.0

    # Chi transform + chi-z steepness.
    chi = chi_transform(flow_dir, flow_acc, river_mask, cell_m,
                        theta_ref=cfg.ref_concavity, a0_m2=cfg.ref_area_m2)
    ksn, _chi_intercept, chi_r2, _n_chi = fit_chi_elevation(
        chi, elev, river_mask)
    chi_max = float(chi.max()) if chi.size else 0.0

    stage = (concavity_stage(theta, sa_r2)
             if n_fit >= cfg.min_fit_cells else "degenerate")

    snap_seed = (
        int(sim.tick), n_cells, round(cell_km, 6),
        n_channel, n_fit,
        round(theta, 9), round(k_s, 9), round(sa_r2, 9),
        round(cfg.ref_concavity, 6), round(ksn, 9), round(chi_r2, 9),
        round(chi_max, 6), round(mean_channel_slope, 9), stage,
    )
    signature = hashlib.sha256(repr(snap_seed).encode("utf-8")).hexdigest()

    return ConcavitySnapshot(
        tick=int(sim.tick),
        n_cells=n_cells,
        cell_km=cell_km,
        n_channel_cells=n_channel,
        n_fit_cells=int(n_fit),
        concavity_theta=float(theta),
        steepness_ks=float(k_s),
        slope_area_r2=float(sa_r2),
        ref_concavity=float(cfg.ref_concavity),
        ksn=float(ksn),
        chi_z_r2=float(chi_r2),
        chi_max=float(chi_max),
        mean_channel_slope=float(mean_channel_slope),
        stage=stage,
        signature=signature,
    )


# ---------------------------------------------------------------------------
# Sim integration (idempotent observer install)
# ---------------------------------------------------------------------------

def install_concavity_observer(sim, config: Optional[ConcavityConfig] = None
                               ) -> ConcavityState:
    """Idempotent installer. Wraps ``sim.step`` once to capture a snapshot
    every ``cfg.snapshot_every`` ticks. Read-only - never mutates the world."""
    cfg = config if config is not None else ConcavityConfig()
    existing: Optional[ConcavityState] = getattr(sim, "_concavity_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = ConcavityState(config=cfg)
    sim._concavity_state = state

    original_step = sim.step

    def _wrapped_step(*args, **kwargs):
        result = original_step(*args, **kwargs)
        try:
            tick = int(sim.tick)
        except Exception:
            tick = 0
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            snap = observe_concavity(sim, cfg)
            if snap is not None:
                state.history.snapshots.append(snap)
        return result

    sim._concavity_original_step = original_step
    sim.step = _wrapped_step
    state.wrapped = True
    sim._concavity_wrapped = True
    return state


def uninstall_concavity_observer(sim) -> bool:
    """Restore the original ``sim.step``. ``True`` if anything was removed."""
    state = getattr(sim, "_concavity_state", None)
    if state is None:
        return False
    original = getattr(sim, "_concavity_original_step", None)
    if original is not None:
        sim.step = original
        del sim._concavity_original_step
    sim._concavity_wrapped = False
    del sim._concavity_state
    return True


def concavity_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards (does not mutate sim)."""
    state: Optional[ConcavityState] = getattr(sim, "_concavity_state", None)
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
        "concavity_theta": (last.concavity_theta if last is not None else None),
        "steepness_ks": (last.steepness_ks if last is not None else None),
        "slope_area_r2": (last.slope_area_r2 if last is not None else None),
        "ksn": (last.ksn if last is not None else None),
        "chi_z_r2": (last.chi_z_r2 if last is not None else None),
        "stage": (last.stage if last is not None else None),
        "n_fit_cells": (last.n_fit_cells if last is not None else None),
    }


__all__ = [
    "REF_CONCAVITY", "REF_AREA_M2",
    "CONCAVITY_GRADED_LO", "CONCAVITY_GRADED_HI",
    "ConcavityConfig", "ConcavitySnapshot", "ConcavityHistory",
    "ConcavityState",
    "channel_slope_area", "fit_flint_law", "chi_transform",
    "fit_chi_elevation", "concavity_stage",
    "observe_concavity",
    "install_concavity_observer", "uninstall_concavity_observer",
    "concavity_summary",
]
