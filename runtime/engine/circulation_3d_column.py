"""Circulation 3D column model (L1) — 3-layer hydrostatic stack.

Inspired by operational NWP column physics (not a black-box ML model):
  - surface (0–2 km), mid-troposphere (2–8 km), upper (8–16 km proxy)
  - vertical ω from Hadley/Ferrel lat structure
  - prognostic one-step coupling to macro ``temp_c`` and ``wind_u/v``

Deterministic numpy only — no external DeepMind dependency.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np

PIPELINE_LAYER = "Genesis-L1 World"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

LAYER_HEIGHTS_KM = (1.0, 5.0, 12.0)
LAPSE_K_PER_KM = (6.5, 5.0, 3.5)  # weaker lapse aloft


@dataclass
class Column3DState:
    ticks: int = 0
    n_columns: int = 0
    mean_t_surf_c: float = 15.0
    mean_t_mid_c: float = -5.0
    mean_t_upper_c: float = -55.0
    mean_omega_pa_s: float = 0.0
    # keyed by macro (iy, ix) fractional indices
    columns: Dict[Tuple[int, int], Tuple[float, float, float, float]] = field(
        default_factory=dict
    )


def _macro_indices(anchor, x_m: float, y_m: float) -> Tuple[int, int, float, float]:
    world = anchor.world
    p = world.params
    R = p.resolution
    cell_km = p.map_size_km / R
    x_km = x_m / 1000.0 + anchor.sim_origin_macro_km[0]
    y_km = y_m / 1000.0 + anchor.sim_origin_macro_km[1]
    fx = float(np.clip(x_km / cell_km - 0.5, 0.0, R - 1.001))
    fy = float(np.clip(y_km / cell_km - 0.5, 0.0, R - 1.001))
    return int(math.floor(fx)), int(math.floor(fy)), fx, fy


def column_temperatures_from_surface(t_surf_c: float, lat_deg: float) -> Tuple[float, float, float]:
    """Hydrostatic column: surface T + standard lapse per layer."""
    lat_factor = 1.0 + 0.15 * math.cos(math.radians(lat_deg * 2.0))
    t_s = float(t_surf_c)
    t_m = t_s - LAPSE_K_PER_KM[0] * (LAYER_HEIGHTS_KM[1] - LAYER_HEIGHTS_KM[0]) * lat_factor
    t_u = t_m - LAPSE_K_PER_KM[1] * (LAYER_HEIGHTS_KM[2] - LAYER_HEIGHTS_KM[1]) * lat_factor
    return t_s, float(t_m), float(t_u)


def tick_circulation_3d_columns(sim, st: Column3DState) -> None:
    """Refresh 3-layer columns for active chunks (macro-anchored)."""
    anchor = getattr(sim.streamer, "genesis", None)
    if anchor is None:
        return
    st.ticks += 1
    world = anchor.world
    from engine.atmospheric_circulation import vertical_omega_proxy, _latitude_deg_from_chunk

    temps_s: list[float] = []
    temps_m: list[float] = []
    temps_u: list[float] = []
    omegas: list[float] = []
    st.columns.clear()

    from engine.world import CHUNK_SIDE_M

    for coord in list(sim.streamer.cache.keys()):
        x_m = (coord[0] + 0.5) * CHUNK_SIDE_M
        y_m = (coord[1] + 0.5) * CHUNK_SIDE_M
        ix, iy, fx, fy = _macro_indices(anchor, x_m, y_m)
        R = world.params.resolution
        ix = min(ix, R - 2)
        iy = min(iy, R - 2)
        tx, ty = fx - ix, fy - iy
        t_surf = float(
            world.temp_c[iy, ix] * (1 - tx) * (1 - ty)
            + world.temp_c[iy, ix + 1] * tx * (1 - ty)
            + world.temp_c[iy + 1, ix] * (1 - tx) * ty
            + world.temp_c[iy + 1, ix + 1] * tx * ty
        )
        lat = _latitude_deg_from_chunk(anchor, coord)
        elev = float(np.mean(sim.streamer.cache[coord].height)) * 1000.0
        u = float(world.wind_u[iy, ix])
        v = float(world.wind_v[iy, ix])
        spd = math.hypot(u, v)
        omega = vertical_omega_proxy(lat, spd, elev)
        t_s, t_m, t_u = column_temperatures_from_surface(t_surf, lat)
        st.columns[(iy, ix)] = (t_s, t_m, t_u, omega)
        temps_s.append(t_s)
        temps_m.append(t_m)
        temps_u.append(t_u)
        omegas.append(omega)

    st.n_columns = len(st.columns)
    if temps_s:
        st.mean_t_surf_c = round(float(np.mean(temps_s)), 2)
        st.mean_t_mid_c = round(float(np.mean(temps_m)), 2)
        st.mean_t_upper_c = round(float(np.mean(temps_u)), 2)
        st.mean_omega_pa_s = round(float(np.mean(omegas)), 5)


def column_3d_snapshot(st: Optional[Column3DState]) -> Dict[str, Any]:
    if st is None:
        return {"installed": False}
    return {
        "installed": True,
        "ticks": st.ticks,
        "n_columns": st.n_columns,
        "layers_km": list(LAYER_HEIGHTS_KM),
        "mean_t_surf_c": st.mean_t_surf_c,
        "mean_t_mid_c": st.mean_t_mid_c,
        "mean_t_upper_c": st.mean_t_upper_c,
        "mean_omega_pa_s": st.mean_omega_pa_s,
    }


def install_circulation_3d(sim) -> Column3DState:
    """Attach column state; ticks run inside ``tick_atmospheric_circulation``."""
    existing = getattr(sim, "_circulation_3d", None)
    if existing is not None:
        return existing
    st = Column3DState()
    sim._circulation_3d = st
    return st


__all__ = [
    "Column3DState",
    "tick_circulation_3d_columns",
    "column_3d_snapshot",
    "install_circulation_3d",
    "column_temperatures_from_surface",
]
