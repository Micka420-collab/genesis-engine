"""Genesis Engine — Wave 55 transient linear-reservoir hydrograph observer.

Read-only **time-domain** companion to the Wave 53 LTI discharge observer
(:mod:`engine.discharge_observer`). Wave 53 routes the emergent runoff field
to a *stationary* discharge ``Q*`` at every basin outlet; it explicitly left
the **transient hydrograph** (the rise-and-recession of a storm) as backlog
(``NEXT-SPRINT.md`` Wave 53 — « pas d'hydrogramme transitif / réservoir
linéaire »). This module fills that gap with the textbook construction.

Why a linear reservoir
----------------------

A catchment outlet behaves, to first order, as a **single linear reservoir**
(Maillet 1905; Nash 1957 unit-hydrograph theory): storage ``S`` releases at a
rate proportional to itself, ``Q = S / k``, so

    dS/dt = I(t) − S/k .

For a piece-wise-constant input ``I`` over a uniform step ``Δt`` this ODE has
an **exact** closed-form update — no numerical integration, unconditionally
stable, bit-deterministic::

    a        = exp(−Δt / k)
    S_{n+1}  = S_n · a + I_n · k · (1 − a)
    Q_{n+1}  = S_{n+1} / k

The observer drives this with a finite **rainfall pulse** of duration
``storm_days`` whose equilibrium rate is the basin's *own* emergent stationary
discharge ``Q*`` (read from Wave 53). The result is a genuine storm
hydrograph: a rising limb during the storm, a peak at storm end, then an
exponential recession with characteristic time ``k``.

What it measures (all emergent, classical hydrology)
----------------------------------------------------

* **Steady discharge** ``Q*`` — the Wave 53 stationary outlet discharge, used
  as the pulse equilibrium rate (the two waves are tied: as the horizon grows
  under a permanent storm, ``Q → Q*``).
* **Peak discharge** and **time-to-peak** of the storm hydrograph.
* **Half-recession time** ``≈ k·ln 2`` — the falling-limb timescale.
* **Volume-balance residual** — exact mass closure of the reservoir.

Observer contract (mirrors Waves 45 / 49 / 50 / 51 / 53)
--------------------------------------------------------

``HydrographConfig`` / ``BasinHydrograph`` / ``HydrographSnapshot`` /
``HydrographHistory`` / ``HydrographState`` dataclasses; ``observe_hydrograph``
(read-only); idempotent ``install_hydrograph_observer`` /
``uninstall_hydrograph_observer`` wrapping ``sim.step``; ``hydrograph_summary``
diagnostic dict.

Determinism
-----------

No RNG. The reservoir recurrence is pure float64 arithmetic and the snapshot
signature is ``sha256`` of a canonical rounded tuple, so two runs with the
same world seed produce identical hydrograph streams.

Stone-age compliance
--------------------

The observer never declares a storm, a basin, or a flow direction. It reuses
the emergent D8 discharge of Wave 53 and applies a parameter-free-in-spirit
linear-reservoir transform. No mutation of any world or sim array.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.discharge_observer import DischargeConfig, observe_discharge


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HydrographConfig:
    """Read-only knobs for the transient hydrograph observer.

    Defaults describe a small flashy catchment: a 3-day storm draining through
    a 5-day linear reservoir, sampled every half day over 40 days.
    """
    storage_k_days: float = 5.0     # linear-reservoir constant k (days)
    dt_days: float = 0.5            # sampling step Δt (days)
    storm_days: float = 3.0         # rainfall-pulse duration
    horizon_days: float = 40.0      # total simulated span
    top_basins: int = 5
    min_basin_cells: int = 4
    snapshot_every: int = 64


@dataclass(frozen=True)
class BasinHydrograph:
    """Per-basin storm-hydrograph descriptors (read-only)."""
    basin_id: int
    area_km2: float
    steady_discharge_m3s: float     # Wave 53 stationary outlet discharge Q*
    peak_discharge_m3s: float
    time_to_peak_days: float
    half_recession_days: float
    volume_balance_residual: float  # |reservoir mass closure| (≈ 0)


@dataclass(frozen=True)
class HydrographSnapshot:
    """Global + top-K basin transient-hydrograph snapshot at a sim tick."""
    tick: int
    storage_k_days: float
    dt_days: float
    storm_days: float
    horizon_days: float
    n_steps: int
    n_basins_total: int
    n_basins_considered: int
    max_peak_discharge_m3s: float
    mean_time_to_peak_days: float
    mean_half_recession_days: float
    max_volume_residual: float
    basins_top: Tuple[BasinHydrograph, ...]
    signature: str


@dataclass
class HydrographHistory:
    snapshots: List[HydrographSnapshot] = field(default_factory=list)


@dataclass
class HydrographState:
    config: HydrographConfig
    history: HydrographHistory = field(default_factory=HydrographHistory)
    wrapped: bool = False


# ---------------------------------------------------------------------------
# Pure-function reservoir model  (world-free, fully unit-testable)
# ---------------------------------------------------------------------------

def linear_reservoir_response(inflow: Any,
                              k: float,
                              dt: float,
                              n_steps: int,
                              s0: float = 0.0
                              ) -> Tuple[np.ndarray, np.ndarray,
                                         np.ndarray, np.ndarray]:
    """Exact transient response of a single linear reservoir.

    Solves ``dS/dt = I − S/k`` with ``Q = S/k`` over ``n_steps`` uniform steps
    ``dt`` using the closed-form update (piece-wise-constant ``inflow``).

    ``inflow`` is a scalar (constant) or a length-``n_steps`` array. Returns
    ``(t, Q, S, outflow_cum)`` of length ``n_steps + 1`` each:

    * ``Q`` — outflow rate ``S/k`` sampled at step boundaries,
    * ``S`` — reservoir storage,
    * ``outflow_cum`` — **exact** cumulative outflow volume, integrated
      analytically over each step (``∫Q dt = I·dt − ΔS``).

    Invariants (used by the smoke / tests), all exact to machine precision:

    * **Mass closure** — ``s0 + Σ I·dt − outflow_cum[n] == S[n]`` for all ``n``.
    * **Monotone recession** — with ``inflow == 0`` and ``S0 > 0``, ``Q`` is
      strictly decreasing and ``Q[n] == Q[0]·a**n`` (``a = exp(−dt/k)``).
    * **Step convergence** — with constant ``inflow`` from empty, ``Q`` rises
      monotonically to ``inflow`` (ties to the Wave 53 stationary discharge).
    """
    if k <= 0.0:
        raise ValueError("k must be > 0")
    if dt <= 0.0:
        raise ValueError("dt must be > 0")
    if n_steps < 1:
        raise ValueError("n_steps must be >= 1")

    inflow_arr = np.asarray(inflow, dtype=np.float64)
    if inflow_arr.ndim == 0:
        inflow_arr = np.full(n_steps, float(inflow_arr), dtype=np.float64)
    elif inflow_arr.shape != (n_steps,):
        raise ValueError("inflow must be scalar or length n_steps")

    a = math.exp(-dt / k)
    S = np.empty(n_steps + 1, dtype=np.float64)
    Q = np.empty(n_steps + 1, dtype=np.float64)
    out_cum = np.empty(n_steps + 1, dtype=np.float64)
    S[0] = float(s0)
    Q[0] = S[0] / k
    out_cum[0] = 0.0
    for n in range(n_steps):
        i_n = float(inflow_arr[n])
        S[n + 1] = S[n] * a + i_n * k * (1.0 - a)
        Q[n + 1] = S[n + 1] / k
        # Exact outflow volume over the step: ∫Q dt = I·dt − (S_{n+1} − S_n).
        out_cum[n + 1] = out_cum[n] + i_n * dt - (S[n + 1] - S[n])

    t = np.arange(n_steps + 1, dtype=np.float64) * dt
    return t, Q, S, out_cum


def storm_hydrograph(steady_discharge: float,
                     cfg: HydrographConfig
                     ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Storm hydrograph for one outlet: a rainfall pulse through a reservoir.

    The pulse rate equals ``steady_discharge`` (the basin's emergent ``Q*``)
    for ``storm_days``, then zero. Starts from an empty reservoir. Returns
    ``(t, Q, outflow_cum)``.
    """
    n_steps = max(1, int(round(cfg.horizon_days / cfg.dt_days)))
    storm_steps = max(0, int(round(cfg.storm_days / cfg.dt_days)))
    storm_steps = min(storm_steps, n_steps)
    inflow = np.zeros(n_steps, dtype=np.float64)
    if storm_steps > 0:
        inflow[:storm_steps] = float(steady_discharge)
    t, Q, _S, out_cum = linear_reservoir_response(
        inflow, cfg.storage_k_days, cfg.dt_days, n_steps, s0=0.0)
    return t, Q, out_cum


def half_recession_days(t: np.ndarray, Q: np.ndarray) -> float:
    """Time from the hydrograph peak until discharge falls to half its peak.

    Linear interpolation on the recession limb; ``≈ k·ln 2`` for a single
    linear reservoir. Returns ``0.0`` if the limb never halves within horizon.
    """
    if Q.size == 0:
        return 0.0
    peak_idx = int(np.argmax(Q))
    peak = float(Q[peak_idx])
    if peak <= 0.0:
        return 0.0
    target = 0.5 * peak
    for n in range(peak_idx, Q.size):
        if Q[n] <= target:
            if n == peak_idx:
                return 0.0
            q0, q1 = float(Q[n - 1]), float(Q[n])
            t0, t1 = float(t[n - 1]), float(t[n])
            frac = 0.0 if q0 == q1 else (q0 - target) / (q0 - q1)
            return (t0 + frac * (t1 - t0)) - float(t[peak_idx])
    return 0.0


# ---------------------------------------------------------------------------
# Snapshot / signature
# ---------------------------------------------------------------------------

def _snapshot_signature(snap_seed: Tuple[Any, ...]) -> str:
    """sha256 of a canonical, language-neutral tuple representation."""
    return hashlib.sha256(repr(snap_seed).encode("utf-8")).hexdigest()


def _basin_hydrograph(basin, cfg: HydrographConfig) -> BasinHydrograph:
    """Build the transient descriptors for one Wave 53 ``BasinDischarge``."""
    q_star = float(basin.outlet_discharge_m3s)
    t, Q, out_cum = storm_hydrograph(q_star, cfg)

    peak_idx = int(np.argmax(Q))
    peak = float(Q[peak_idx])
    t_peak = float(t[peak_idx])
    half = half_recession_days(t, Q)

    # Mass closure of the reservoir: total input volume == outflow + storage.
    n_steps = Q.size - 1
    storm_steps = min(max(0, int(round(cfg.storm_days / cfg.dt_days))), n_steps)
    total_input = q_star * storm_steps * cfg.dt_days
    final_storage = float(Q[-1]) * cfg.storage_k_days  # S = Q·k
    residual = abs(total_input - (float(out_cum[-1]) + final_storage))
    denom = max(total_input, 1e-9)

    return BasinHydrograph(
        basin_id=int(basin.basin_id),
        area_km2=float(basin.area_km2),
        steady_discharge_m3s=q_star,
        peak_discharge_m3s=peak,
        time_to_peak_days=t_peak,
        half_recession_days=float(half),
        volume_balance_residual=float(residual / denom),
    )


def observe_hydrograph(sim, config: Optional[HydrographConfig] = None
                       ) -> Optional[HydrographSnapshot]:
    """Pure read-only transient-hydrograph snapshot. ``None`` if no world."""
    cfg = config if config is not None else HydrographConfig()
    dcfg = DischargeConfig(top_basins=cfg.top_basins,
                           min_basin_cells=cfg.min_basin_cells)
    dsnap = observe_discharge(sim, dcfg)
    if dsnap is None:
        return None

    n_steps = max(1, int(round(cfg.horizon_days / cfg.dt_days)))
    basins = [_basin_hydrograph(b, cfg) for b in dsnap.basins_top]

    if basins:
        max_peak = max(b.peak_discharge_m3s for b in basins)
        mean_tpeak = sum(b.time_to_peak_days for b in basins) / len(basins)
        mean_half = sum(b.half_recession_days for b in basins) / len(basins)
        max_resid = max(b.volume_balance_residual for b in basins)
    else:
        max_peak = mean_tpeak = mean_half = max_resid = 0.0

    canonical = tuple(
        (b.basin_id, round(b.area_km2, 4), round(b.steady_discharge_m3s, 6),
         round(b.peak_discharge_m3s, 6), round(b.time_to_peak_days, 4),
         round(b.half_recession_days, 4), round(b.volume_balance_residual, 9))
        for b in sorted(basins, key=lambda b: b.basin_id)
    )
    sig = _snapshot_signature((
        int(sim.tick), round(cfg.storage_k_days, 6), round(cfg.dt_days, 6),
        round(cfg.storm_days, 6), round(cfg.horizon_days, 6), n_steps,
        dsnap.n_basins_total, len(basins), round(max_peak, 6),
        round(mean_tpeak, 4), round(mean_half, 4), round(max_resid, 9),
        canonical,
    ))

    return HydrographSnapshot(
        tick=int(sim.tick),
        storage_k_days=float(cfg.storage_k_days),
        dt_days=float(cfg.dt_days),
        storm_days=float(cfg.storm_days),
        horizon_days=float(cfg.horizon_days),
        n_steps=n_steps,
        n_basins_total=int(dsnap.n_basins_total),
        n_basins_considered=len(basins),
        max_peak_discharge_m3s=float(max_peak),
        mean_time_to_peak_days=float(mean_tpeak),
        mean_half_recession_days=float(mean_half),
        max_volume_residual=float(max_resid),
        basins_top=tuple(basins),
        signature=sig,
    )


# ---------------------------------------------------------------------------
# Install / uninstall (mirrors waves 45 / 49 / 50 / 53)
# ---------------------------------------------------------------------------

def install_hydrograph_observer(sim,
                                config: Optional[HydrographConfig] = None
                                ) -> HydrographState:
    """Idempotent installer. Wraps ``sim.step`` once to capture snapshots
    every ``cfg.snapshot_every`` ticks."""
    cfg = config if config is not None else HydrographConfig()
    existing: Optional[HydrographState] = getattr(
        sim, "_hydrograph_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = HydrographState(config=cfg)
    sim._hydrograph_state = state

    original_step = sim.step

    def _wrapped_step(*args, **kwargs):
        result = original_step(*args, **kwargs)
        try:
            tick = int(sim.tick)
        except Exception:
            tick = 0
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            snap = observe_hydrograph(sim, cfg)
            if snap is not None:
                state.history.snapshots.append(snap)
        return result

    sim._hydrograph_original_step = original_step
    sim.step = _wrapped_step
    state.wrapped = True
    sim._hydrograph_wrapped = True
    return state


def uninstall_hydrograph_observer(sim) -> bool:
    """Restore the original ``sim.step``. ``True`` if anything was removed."""
    state = getattr(sim, "_hydrograph_state", None)
    if state is None:
        return False
    original = getattr(sim, "_hydrograph_original_step", None)
    if original is not None:
        sim.step = original
        del sim._hydrograph_original_step
    sim._hydrograph_wrapped = False
    del sim._hydrograph_state
    return True


def hydrograph_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards (does not mutate sim)."""
    state: Optional[HydrographState] = getattr(sim, "_hydrograph_state", None)
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
        "max_peak_discharge_m3s": (last.max_peak_discharge_m3s
                                   if last is not None else None),
        "mean_time_to_peak_days": (last.mean_time_to_peak_days
                                   if last is not None else None),
        "mean_half_recession_days": (last.mean_half_recession_days
                                     if last is not None else None),
        "max_volume_residual": (last.max_volume_residual
                                if last is not None else None),
        "n_basins_considered": (last.n_basins_considered
                                if last is not None else None),
    }


__all__ = [
    "HydrographConfig",
    "BasinHydrograph",
    "HydrographSnapshot",
    "HydrographHistory",
    "HydrographState",
    "linear_reservoir_response",
    "storm_hydrograph",
    "half_recession_days",
    "observe_hydrograph",
    "install_hydrograph_observer",
    "uninstall_hydrograph_observer",
    "hydrograph_summary",
]
