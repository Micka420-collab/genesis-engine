"""Genesis Engine - Wave 62 emergent hypsometry / landscape-maturity observer.

Read-only geomorphology layer that quantifies the *shape* of the emergent
relief the tick has already produced. Where Wave 49 measured the drainage
network (Strahler stream orders, Horton ratios, drainage density), this wave
measures its area-altitude complement: the **hypsometric curve** and
**hypsometric integral** of Strahler (1952), the canonical descriptor of the
geomorphic cycle of erosion (Davis 1899; Strahler 1952; Pike & Wilson 1971).

Nothing here is scripted. The observer reads the same emergent elevation
field ``world.elevation_m`` the tick produced (as Waves 53 / 57 / 59 / 61 do)
and overlays one definition - the dimensionless area-altitude distribution.

The hypsometric curve plots the fraction of map area lying above a relative
elevation. With relative height ``h* = (h - h_min) / (h_max - h_min)`` in
[0, 1], the curve is the *survival function* of the relative-elevation
distribution::

    a*(h*) = fraction of cells with relative elevation >= h*

a monotonically non-increasing function from a*(0) = 1 to a*(1) ~ 0. The area
under that curve is the **hypsometric integral**::

    HI = integral_0^1 a*(h*) dh*

A youthful, deeply uplifted landscape carries much mass at altitude (HI high,
convex curve); an old peneplain has eroded most of its mass away (HI low,
concave curve). Strahler's empirical stages:

    HI > 0.60          inequilibrium / "youthful" (uplift-dominated)
    0.35 <= HI <= 0.60 equilibrium / "mature"
    HI < 0.35          monadnock / "old" (erosion-dominated peneplain)

Falsifiable invariants (asserted by the smoke / tests)
------------------------------------------------------
1. Pike-Wilson identity. The area under the survival curve equals the
   *elevation-relief ratio* ``E = (mean(h) - h_min) / (h_max - h_min)`` to the
   discretisation tolerance: the integral of a non-negative bounded variable's
   survival function is its mean (Pike & Wilson 1971). Falsified if the sampled
   curve and the closed-form HI disagree.
2. Bounds. ``HI in [0, 1]`` and the curve is bounded in [0, 1].
3. Monotone survival. ``a*`` is non-increasing in ``h*`` with ``a*(0) = 1``
   exactly (every cell is at or above the minimum).
4. Affine invariance. HI is invariant under ``h -> a*h + b`` (a > 0): both the
   numerator and the relief scale by ``a`` and the shift cancels. A pure
   diagnostic of relief *shape*, blind to datum and vertical exaggeration.
5. Linear-ramp datum. A landscape whose elevations are uniformly distributed
   between two values has ``HI = 0.5`` exactly (symmetric area-altitude curve).

Observer contract (mirrors Waves 53 / 55 / 57 / 59 / 61)
--------------------------------------------------------
``HypsometryConfig`` / ``HypsometrySnapshot`` / ``HypsometryHistory`` /
``HypsometryState`` dataclasses; pure helpers ``relative_elevation`` /
``hypsometric_integral`` / ``hypsometric_curve`` / ``hypsometric_skewness`` /
``hypsometric_stage``; ``observe_hypsometry(sim, cfg)`` - read-only, ``None``
if no world wired; idempotent ``install_hypsometry_observer`` /
``uninstall_hypsometry_observer`` (returns ``bool``); ``hypsometry_summary``
diagnostic dict.

Determinism
-----------
No RNG. The signature is ``sha256`` of a canonical tuple of rounded aggregate
metrics, so two runs with the same world seed produce identical snapshot
streams.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Reuse the Wave 53 world access helpers verbatim (no duplication).
from engine.discharge_observer import _field, _resolve_world

_M_PER_KM = 1000.0

# Strahler (1952) empirical stage thresholds on the hypsometric integral.
STAGE_YOUTHFUL = 0.60   # HI strictly above -> inequilibrium / youthful
STAGE_MATURE = 0.35     # HI in [MATURE, YOUTHFUL] -> equilibrium / mature


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HypsometryConfig:
    """Read-only knobs for the hypsometry observer."""
    # Number of evenly-spaced relative-height levels used to sample the
    # survival curve on [0, 1]. The reported curve has ``n_bins + 1`` points.
    n_bins: int = 512
    snapshot_every: int = 64


@dataclass(frozen=True)
class HypsometrySnapshot:
    """Map-wide hypsometry roll-up at one tick (read-only)."""
    tick: int
    n_cells: int
    cell_km: float
    min_elev_m: float
    max_elev_m: float
    mean_elev_m: float
    relief_m: float
    land_fraction: float          # fraction of cells with elevation >= 0
    hypsometric_integral: float   # HI = elevation-relief ratio (closed form)
    curve_integral: float         # trapz of the sampled survival curve
    pike_wilson_residual: float   # |curve_integral - HI| -> ~0 (invariant 1)
    skewness: float               # standardised 3rd moment of relative elev
    stage: str                    # Strahler stage label (invariant -> bands)
    n_bins: int
    curve_deciles: Tuple[float, ...]  # a* at h* = 0.0, 0.1, ... , 1.0
    signature: str


@dataclass
class HypsometryHistory:
    snapshots: List[HypsometrySnapshot] = field(default_factory=list)


@dataclass
class HypsometryState:
    config: HypsometryConfig
    history: HypsometryHistory = field(default_factory=HypsometryHistory)
    wrapped: bool = False


# ---------------------------------------------------------------------------
# Hypsometry laws (pure, vectorised)
# ---------------------------------------------------------------------------

def relative_elevation(elevation) -> Tuple[np.ndarray, float, float, float]:
    """Map elevation to relative height ``h* = (h - h_min)/(h_max - h_min)``.

    Returns ``(h_star, relief, h_min, h_max)``. On flat relief (h_max == h_min)
    the relief is 0 and ``h_star`` is all zeros (degenerate landscape).
    """
    h = np.asarray(elevation, dtype=np.float64)
    h_min = float(h.min())
    h_max = float(h.max())
    relief = h_max - h_min
    if relief <= 0.0:
        return np.zeros_like(h), 0.0, h_min, h_max
    return (h - h_min) / relief, relief, h_min, h_max


def hypsometric_integral(elevation) -> float:
    """Closed-form hypsometric integral = elevation-relief ratio (Pike &
    Wilson 1971): ``HI = (mean(h) - h_min) / (h_max - h_min)`` in [0, 1].

    Equals the area under the survival curve exactly (the mean of a bounded
    non-negative variable is the integral of its survival function). Returns
    0.0 for flat relief.
    """
    h = np.asarray(elevation, dtype=np.float64)
    h_min = float(h.min())
    h_max = float(h.max())
    relief = h_max - h_min
    if relief <= 0.0:
        return 0.0
    return (float(h.mean()) - h_min) / relief


def hypsometric_curve(elevation, n_bins: int = 512
                      ) -> Tuple[np.ndarray, np.ndarray]:
    """Sample the hypsometric (survival) curve on ``n_bins + 1`` levels.

    Returns ``(levels, area_frac)`` where ``levels`` are ``n_bins + 1``
    evenly-spaced relative heights on [0, 1] and ``area_frac[i]`` is the
    fraction of cells whose relative elevation is ``>= levels[i]``. The curve
    is non-increasing, ``area_frac[0] == 1`` and ``area_frac[-1]`` is the
    fraction of cells exactly at the maximum.
    """
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")
    h_star, relief, _, _ = relative_elevation(elevation)
    levels = np.linspace(0.0, 1.0, n_bins + 1)
    flat = h_star.reshape(-1)
    n = flat.size
    if n == 0:
        return levels, np.zeros_like(levels)
    # area_frac[i] = mean(h_star >= levels[i]). Vectorised via a sorted search:
    # count of values >= L = n - searchsorted(sorted, L, side="left").
    order = np.sort(flat)
    counts_below = np.searchsorted(order, levels, side="left")
    area_frac = (n - counts_below) / float(n)
    return levels, area_frac


def hypsometric_skewness(elevation) -> float:
    """Standardised third moment of the relative-elevation distribution.

    Positive skew = area-altitude mass concentrated at low elevations (mature /
    old landscape); negative = concentrated at altitude (youthful). 0.0 on flat
    relief or zero variance.
    """
    h_star, relief, _, _ = relative_elevation(elevation)
    if relief <= 0.0:
        return 0.0
    flat = h_star.reshape(-1).astype(np.float64)
    mu = float(flat.mean())
    sigma = float(flat.std())
    if sigma <= 0.0:
        return 0.0
    return float(np.mean(((flat - mu) / sigma) ** 3))


def hypsometric_stage(hi: float, relief: float = 1.0) -> str:
    """Strahler (1952) landscape-stage label from the hypsometric integral."""
    if relief <= 0.0:
        return "degenerate"
    if hi > STAGE_YOUTHFUL:
        return "youthful"
    if hi >= STAGE_MATURE:
        return "mature"
    return "monadnock"


# ---------------------------------------------------------------------------
# Map-wide observation (read-only)
# ---------------------------------------------------------------------------

def observe_hypsometry(sim, config: Optional[HypsometryConfig] = None
                       ) -> Optional[HypsometrySnapshot]:
    """Pure read-only hypsometry snapshot. ``None`` if no world wired."""
    cfg = config if config is not None else HypsometryConfig()
    world = _resolve_world(sim)
    if world is None:
        return None

    flow_dir = np.asarray(world.flow_dir, dtype=np.uint8)
    shape = flow_dir.shape
    R = int(shape[0])
    if R == 0:
        return None
    cell_km = float(world.params.map_size_km) / float(R)

    elev = _field(world, "elevation_m", 0.0, shape)
    n_cells = int(elev.size)

    h_min = float(elev.min())
    h_max = float(elev.max())
    relief = h_max - h_min
    mean_elev = float(elev.mean())
    land_fraction = float(np.count_nonzero(elev >= 0.0)) / float(n_cells)

    hi = hypsometric_integral(elev)
    levels, area_frac = hypsometric_curve(elev, cfg.n_bins)
    curve_integral = float(np.trapezoid(area_frac, levels))
    pike_wilson_residual = abs(curve_integral - hi)
    skew = hypsometric_skewness(elev)
    stage = hypsometric_stage(hi, relief)

    # Survival fraction at h* = 0.0, 0.1, ... , 1.0 for compact dashboards.
    decile_levels = np.linspace(0.0, 1.0, 11)
    decile_idx = np.round(decile_levels * cfg.n_bins).astype(int)
    curve_deciles = tuple(round(float(area_frac[i]), 6) for i in decile_idx)

    snap_seed = (
        int(sim.tick), n_cells, round(cell_km, 6),
        round(h_min, 4), round(h_max, 4), round(mean_elev, 4),
        round(relief, 4), round(land_fraction, 9),
        round(hi, 9), round(curve_integral, 9),
        round(pike_wilson_residual, 12), round(skew, 9),
        stage, int(cfg.n_bins), curve_deciles,
    )
    signature = hashlib.sha256(repr(snap_seed).encode("utf-8")).hexdigest()

    return HypsometrySnapshot(
        tick=int(sim.tick),
        n_cells=n_cells,
        cell_km=cell_km,
        min_elev_m=h_min,
        max_elev_m=h_max,
        mean_elev_m=mean_elev,
        relief_m=relief,
        land_fraction=land_fraction,
        hypsometric_integral=float(hi),
        curve_integral=curve_integral,
        pike_wilson_residual=float(pike_wilson_residual),
        skewness=float(skew),
        stage=stage,
        n_bins=int(cfg.n_bins),
        curve_deciles=curve_deciles,
        signature=signature,
    )


# ---------------------------------------------------------------------------
# Sim integration (idempotent observer install)
# ---------------------------------------------------------------------------

def install_hypsometry_observer(sim, config: Optional[HypsometryConfig] = None
                                ) -> HypsometryState:
    """Idempotent installer. Wraps ``sim.step`` once to capture a snapshot
    every ``cfg.snapshot_every`` ticks. Read-only - never mutates the world."""
    cfg = config if config is not None else HypsometryConfig()
    existing: Optional[HypsometryState] = getattr(sim, "_hypsometry_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = HypsometryState(config=cfg)
    sim._hypsometry_state = state

    original_step = sim.step

    def _wrapped_step(*args, **kwargs):
        result = original_step(*args, **kwargs)
        try:
            tick = int(sim.tick)
        except Exception:
            tick = 0
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            snap = observe_hypsometry(sim, cfg)
            if snap is not None:
                state.history.snapshots.append(snap)
        return result

    sim._hypsometry_original_step = original_step
    sim.step = _wrapped_step
    state.wrapped = True
    sim._hypsometry_wrapped = True
    return state


def uninstall_hypsometry_observer(sim) -> bool:
    """Restore the original ``sim.step``. ``True`` if anything was removed."""
    state = getattr(sim, "_hypsometry_state", None)
    if state is None:
        return False
    original = getattr(sim, "_hypsometry_original_step", None)
    if original is not None:
        sim.step = original
        del sim._hypsometry_original_step
    sim._hypsometry_wrapped = False
    del sim._hypsometry_state
    return True


def hypsometry_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards (does not mutate sim)."""
    state: Optional[HypsometryState] = getattr(sim, "_hypsometry_state", None)
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
        "hypsometric_integral": (last.hypsometric_integral
                                 if last is not None else None),
        "pike_wilson_residual": (last.pike_wilson_residual
                                 if last is not None else None),
        "stage": (last.stage if last is not None else None),
        "skewness": (last.skewness if last is not None else None),
        "land_fraction": (last.land_fraction if last is not None else None),
    }


__all__ = [
    "STAGE_YOUTHFUL", "STAGE_MATURE",
    "HypsometryConfig", "HypsometrySnapshot", "HypsometryHistory",
    "HypsometryState",
    "relative_elevation", "hypsometric_integral", "hypsometric_curve",
    "hypsometric_skewness", "hypsometric_stage",
    "observe_hypsometry",
    "install_hypsometry_observer", "uninstall_hypsometry_observer",
    "hypsometry_summary",
]
