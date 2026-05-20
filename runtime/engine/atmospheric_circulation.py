"""Circulation atmosphérique L1 — Hadley/Ferrel unifié + LOD vertical.

Complète ``macro_climate`` (vents macro Genesis) et ``meteorology`` (cellules
locales) : champ de vent cohérent, proxy ω vertical, advection physique légère
des agents par le vent (pas un comportement scripté).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.world import CHUNK_SIDE_M, world_to_chunk

PIPELINE_LAYER = "Genesis-L1 World"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

EARTH_ROT_RATE = 7.2921159e-5
ADVECT_STRENGTH = 0.015  # fraction of wind speed applied to agent drift per tick


@dataclass
class CirculationState:
    ticks: int = 0
    mean_wind_speed_ms: float = 0.0
    mean_vertical_omega: float = 0.0
    jet_streak_chunks: int = 0
    chunk_omega: Dict[Tuple[int, int, int], float] = field(default_factory=dict)
    chunk_wind: Dict[Tuple[int, int, int], Tuple[float, float]] = field(default_factory=dict)


def _latitude_deg_from_chunk(anchor, coord: Tuple[int, int, int]) -> float:
    """Approx latitude from macro anchor (degrees)."""
    try:
        from engine.macro_climate import sample_macro_wind_at
        x_m = (coord[0] + 0.5) * CHUNK_SIDE_M
        y_m = (coord[1] + 0.5) * CHUNK_SIDE_M
        world = anchor.world
        p = world.params
        R = p.resolution
        cell_km = p.map_size_km / R
        x_km = x_m / 1000.0 + anchor.sim_origin_macro_km[0]
        y_km = y_m / 1000.0 + anchor.sim_origin_macro_km[1]
        fy = float(np.clip(y_km / cell_km - 0.5, 0.0, R - 1.001))
        # macro row 0 = north in genesis convention
        lat = 90.0 - (fy / max(R - 1, 1)) * 180.0
        return float(np.clip(lat, -85.0, 85.0))
    except Exception:
        return 45.0


def vertical_omega_proxy(lat_deg: float, wind_speed: float, elev_m: float) -> float:
    """Simplified ω (Pa/s scale proxy): Hadley ascent at ITCZ, descent subtropics."""
    lat = abs(lat_deg)
    hadley = math.exp(-((lat - 5.0) ** 2) / 120.0) * 0.08
    ferrel = math.exp(-((lat - 45.0) ** 2) / 200.0) * 0.04 * (1.0 if lat_deg < 0 else -1.0)
    orographic = min(0.06, elev_m * 1e-5) * (1.0 if wind_speed > 4.0 else 0.3)
    return float(hadley + ferrel + orographic)


def tick_atmospheric_circulation(sim) -> None:
    """Refresh per-chunk wind/ω and optional agent wind advection."""
    st: Optional[CirculationState] = getattr(sim, "_circulation", None)
    if st is None:
        return
    st.ticks += 1
    anchor = getattr(sim.streamer, "genesis", None)
    if anchor is None:
        return

    from engine.macro_climate import sample_macro_wind_at

    speeds: List[float] = []
    omegas: List[float] = []
    jets = 0
    dt_s = float(getattr(sim.cfg, "drive_accel", 1800.0))

    for coord, chunk in list(sim.streamer.cache.items()):
        x_m = (coord[0] + 0.5) * CHUNK_SIDE_M
        y_m = (coord[1] + 0.5) * CHUNK_SIDE_M
        u, v = sample_macro_wind_at(anchor, x_m, y_m)
        # Blend with meteorology cell if present
        met = getattr(sim, "_meteo_state", None)
        if met is not None:
            cell = met.chunk_meteo.get(coord)
            if cell is not None:
                u = 0.55 * u + 0.45 * float(cell.wind_u_ms)
                v = 0.55 * v + 0.45 * float(cell.wind_v_ms)
        st.chunk_wind[coord] = (float(u), float(v))
        spd = math.hypot(u, v)
        speeds.append(spd)
        lat = _latitude_deg_from_chunk(anchor, coord)
        elev = float(np.mean(chunk.height)) * 1000.0
        omega = vertical_omega_proxy(lat, spd, elev)
        st.chunk_omega[coord] = omega
        omegas.append(omega)
        if spd > 12.0:
            jets += 1

    st.mean_wind_speed_ms = float(np.mean(speeds)) if speeds else 0.0
    st.mean_vertical_omega = float(np.mean(omegas)) if omegas else 0.0
    st.jet_streak_chunks = jets

    if getattr(sim.cfg, "wind_advect_agents", True):
        _wind_advect_agents(sim, anchor, st, dt_s)

    col3d = getattr(sim, "_circulation_3d", None)
    if col3d is not None:
        from engine.circulation_3d_column import tick_circulation_3d_columns
        tick_circulation_3d_columns(sim, col3d)


def _wind_advect_agents(sim, anchor, st: CirculationState, dt_s: float) -> None:
    from engine.macro_climate import sample_macro_wind_at

    agents = sim.agents
    n = int(agents.n_active)
    for row in range(n):
        if not agents.alive[row]:
            continue
        px = float(agents.pos[row, 0])
        py = float(agents.pos[row, 1])
        cc = world_to_chunk(px, py)
        uv = st.chunk_wind.get(cc)
        if uv is None:
            u, v = sample_macro_wind_at(anchor, px, py)
        else:
            u, v = uv
        scale = ADVECT_STRENGTH * dt_s
        agents.pos[row, 0] += float(u) * scale
        agents.pos[row, 1] += float(v) * scale


def install_atmospheric_circulation(sim) -> CirculationState:
    existing = getattr(sim, "_circulation", None)
    if existing is not None:
        return existing
    st = CirculationState()
    sim._circulation = st
    from engine.circulation_3d_column import install_circulation_3d
    install_circulation_3d(sim)
    if not getattr(sim, "_circulation_step_patched", False):
        sim._circulation_step_patched = True
        orig = sim.step

        def wrapped():
            stats = orig()
            tick_atmospheric_circulation(sim)
            return stats

        sim.step = wrapped
    return st


def circulation_snapshot(sim) -> Dict[str, Any]:
    st: Optional[CirculationState] = getattr(sim, "_circulation", None)
    macro = {}
    try:
        from engine.macro_climate import macro_climate_state
        macro = macro_climate_state(sim)
    except Exception:
        pass
    base: Dict[str, Any] = {
        "tick": int(sim.tick),
        "macro_climate": macro,
        "model": "Hadley-Ferrel-macro+meteo-blend",
    }
    if st is None:
        return base
    col3d = getattr(sim, "_circulation_3d", None)
    if col3d is not None:
        from engine.circulation_3d_column import column_3d_snapshot
        base["column_3d"] = column_3d_snapshot(col3d)
    base["live"] = {
        "ticks": st.ticks,
        "mean_wind_speed_ms": round(st.mean_wind_speed_ms, 3),
        "mean_vertical_omega": round(st.mean_vertical_omega, 5),
        "jet_streak_chunks": st.jet_streak_chunks,
        "chunks_tracked": len(st.chunk_wind),
    }
    return base


def sample_wind_lite_field(
    sim,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    out_w: int,
    out_h: int,
) -> Dict[str, Any]:
    """RGBA arrows encoded as colour (u,v) for 2D overlay — no PNG."""
    import base64

    out_w = max(16, min(int(out_w), 256))
    out_h = max(16, min(int(out_h), 192))
    span_x = max(xmax - xmin, 1e-3)
    span_y = max(ymax - ymin, 1e-3)
    px = (np.arange(out_w, dtype=np.float32) + 0.5) / out_w * span_x + xmin
    py = (np.arange(out_h, dtype=np.float32) + 0.5) / out_h * span_y + ymin
    XX, YY = np.meshgrid(px, py, indexing="xy")
    u_out = np.zeros((out_h, out_w), dtype=np.float32)
    v_out = np.zeros((out_h, out_w), dtype=np.float32)
    st: Optional[CirculationState] = getattr(sim, "_circulation", None)
    anchor = getattr(sim.streamer, "genesis", None)
    if anchor is not None:
        from engine.macro_climate import sample_macro_wind_at
        for j in range(out_h):
            for i in range(out_w):
                u, v = sample_macro_wind_at(anchor, float(XX[j, i]), float(YY[j, i]))
                if st is not None:
                    cc = world_to_chunk(float(XX[j, i]), float(YY[j, i]))
                    uv = st.chunk_wind.get(cc)
                    if uv is not None:
                        u, v = uv
                u_out[j, i] = u
                v_out[j, i] = v
    max_s = float(np.percentile(np.hypot(u_out, v_out), 95) + 1e-3)
    u_n = np.clip(u_out / max_s, -1.0, 1.0)
    v_n = np.clip(v_out / max_s, -1.0, 1.0)
    rgba = np.zeros((out_h, out_w, 4), dtype=np.uint8)
    rgba[..., 0] = ((u_n + 1.0) * 127.5).astype(np.uint8)
    rgba[..., 1] = ((v_n + 1.0) * 127.5).astype(np.uint8)
    rgba[..., 2] = (np.hypot(u_n, v_n) * 200).astype(np.uint8)
    rgba[..., 3] = 180
    return {
        "w": out_w,
        "h": out_h,
        "xmin": xmin,
        "ymin": ymin,
        "xmax": xmax,
        "ymax": ymax,
        "max_speed_ms": round(max_s, 3),
        "rgba_b64": base64.b64encode(rgba.tobytes()).decode("ascii"),
    }


__all__ = [
    "CirculationState",
    "install_atmospheric_circulation",
    "tick_atmospheric_circulation",
    "circulation_snapshot",
    "sample_wind_lite_field",
]
