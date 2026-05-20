"""DeepMind-inspired world priors — deterministic CPU numpy (ZERO PRE-SCRIPT).

These are **algorithmic priors**, not calls to DeepMind APIs:

  - **GraphCast-lite** (Lam et al., 2023 style): message-passing on the macro
    lat-lon grid to smooth/prognose ``wind_u/v`` from ``temp_c`` gradients and
    Coriolis — makes Genesis continents share a coherent synoptic field.
  - **NCA terrain** (Mordvintsev 2020): already in ``nca_training`` / Wave 25 —
    this module only documents the bridge via ``apply_world_prior_stack``.

Nothing here scripts agent goals or civilisation outcomes; it refines the
*physical substrate* before ``Simulation.step()`` runs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from engine.world_genesis import GenesisAnchor, GenesisWorld

PIPELINE_LAYER = "Genesis-L2 Climate"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


@dataclass
class WorldPriorState:
    graphcast_passes: int = 0
    wind_delta_rms: float = 0.0
    applied: bool = False


def _neighbor_mean(arr: np.ndarray) -> np.ndarray:
    """4-neighbor average with edge clamp (GraphCast message-passing lite)."""
    R = arr.shape[0]
    out = arr.copy()
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        shifted = np.roll(arr, shift=(dy, dx), axis=(0, 1))
        if dy == -1:
            shifted[0, :] = arr[0, :]
        if dy == 1:
            shifted[-1, :] = arr[-1, :]
        if dx == -1:
            shifted[:, 0] = arr[:, 0]
        if dx == 1:
            shifted[:, -1] = arr[:, -1]
        out += shifted
    return out / 5.0


def graphcast_lite_prognostic(
    wind_u: np.ndarray,
    wind_v: np.ndarray,
    temp_c: np.ndarray,
    lat_deg: np.ndarray,
    *,
    n_message_passes: int = 2,
    dt_hours: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """One-step synoptic wind refinement via grid message passing.

    Geostrophic-ish correction from meridional temperature gradient plus
    Coriolis coupling — deterministic, no learned weights required.
    """
    u = wind_u.astype(np.float64, copy=True)
    v = wind_v.astype(np.float64, copy=True)
    t = temp_c.astype(np.float64)
    lat = lat_deg.astype(np.float64)
    R = t.shape[0]
    # Meridional gradient proxy (K per degree latitude)
    dt_dy = np.zeros_like(t)
    dt_dy[1:-1, :] = (t[2:, :] - t[:-2, :]) / 2.0
    dt_dy[0, :] = t[1, :] - t[0, :]
    dt_dy[-1, :] = t[-1, :] - t[-2, :]
    f_coriolis = 2.0 * 7.2921e-5 * np.sin(np.radians(lat))
    f_coriolis = np.where(np.abs(f_coriolis) < 1e-6, 1e-6, f_coriolis)
    scale = 0.08 * dt_hours
    for _ in range(max(1, n_message_passes)):
        u_msg = _neighbor_mean(u)
        v_msg = _neighbor_mean(v)
        # Thermal wind tendency: stronger east wind where T increases northward
        du_geo = -scale * dt_dy / (np.abs(f_coriolis) + 1e-4) * 0.15
        dv_geo = scale * np.gradient(t, axis=1)[0] / (np.abs(f_coriolis) + 1e-4) * 0.08
        u = 0.72 * u + 0.18 * u_msg + 0.10 * (u + du_geo)
        v = 0.72 * v + 0.18 * v_msg + 0.10 * (v + dv_geo)
        # ITCZ convergence belt: weaken polarward noise near equator
        eq_mask = np.exp(-(lat ** 2) / 400.0)
        u *= 1.0 - 0.05 * eq_mask
        v *= 1.0 - 0.05 * eq_mask
    delta = float(np.sqrt(np.mean((u - wind_u) ** 2 + (v - wind_v) ** 2)))
    return u.astype(np.float32), v.astype(np.float32), delta


def apply_graphcast_lite_to_world(
    world: GenesisWorld,
    *,
    n_message_passes: int = 2,
) -> WorldPriorState:
    """In-place refinement of macro wind fields on a GenesisWorld."""
    u, v, delta = graphcast_lite_prognostic(
        world.wind_u,
        world.wind_v,
        world.temp_c,
        world.latitude_deg,
        n_message_passes=n_message_passes,
    )
    world.wind_u[:] = u
    world.wind_v[:] = v
    return WorldPriorState(
        graphcast_passes=n_message_passes,
        wind_delta_rms=round(delta, 4),
        applied=True,
    )


def install_deepmind_world_prior(
    sim,
    anchor: Optional[GenesisAnchor] = None,
    *,
    graphcast_passes: int = 2,
    nca_learned: bool = False,
) -> Dict[str, Any]:
    """Apply priors after Genesis bootstrap (idempotent per sim)."""
    out: Dict[str, Any] = {
        "graphcast_lite": False,
        "nca_learned": False,
        "wind_delta_rms": 0.0,
    }
    if getattr(sim, "_world_prior_applied", False):
        return {**out, "skipped": True}
    anchor = anchor or getattr(sim.streamer, "genesis", None)
    if anchor is None:
        return out
    st = apply_graphcast_lite_to_world(
        anchor.world,
        n_message_passes=graphcast_passes,
    )
    sim._world_prior = st
    sim._world_prior_applied = True
    out["graphcast_lite"] = True
    out["wind_delta_rms"] = st.wind_delta_rms

    if nca_learned:
        try:
            from engine.nca_training import LEARNED_NCA_CONFIG
            from engine.nca_multichannel import install_nca_multichannel

            install_nca_multichannel(sim, LEARNED_NCA_CONFIG)
            out["nca_learned"] = True
        except Exception:
            pass
    return out


def world_prior_snapshot(sim) -> Dict[str, Any]:
    st: Optional[WorldPriorState] = getattr(sim, "_world_prior", None)
    if st is None:
        return {"applied": False, "model": "GraphCast-lite + NCA (optional)"}
    return {
        "applied": st.applied,
        "graphcast_passes": st.graphcast_passes,
        "wind_delta_rms": st.wind_delta_rms,
        "model": "GraphCast-lite message-passing (numpy)",
        "reference": "DeepMind GraphCast 2023 — CPU prior, not API",
    }


__all__ = [
    "graphcast_lite_prognostic",
    "apply_graphcast_lite_to_world",
    "install_deepmind_world_prior",
    "world_prior_snapshot",
    "WorldPriorState",
]
