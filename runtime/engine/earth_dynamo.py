"""Terre dynamo — noyau, rotation, géothermie, cycle jour/nuit (L0).

Le monde tourne sans script IA : Coriolis, flux géothermique du noyau,
insolation diurne sur les chunks streamés.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.physics import G_EARTH, SIGMA_SB
from engine.world import CHUNK_SIDE_M

PIPELINE_LAYER = "Genesis-L0 Physics"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

OMEGA_EARTH = 7.2921159e-5  # rad/s
EARTH_RADIUS_M = 6.371e6
CORE_RADIUS_M = 3.48e6
GEOTHERMAL_FLUX_W_M2 = 0.065  # moyenne continentale ~65 mW/m²
INSOLATION_BASE_W_M2 = 340.0


@dataclass
class EarthDynamoState:
    ticks: int = 0
    simulation_years: float = 0.0
    mean_core_temp_k: float = 6000.0
    mean_geothermal_w_m2: float = GEOTHERMAL_FLUX_W_M2
    mean_insolation_w_m2: float = INSOLATION_BASE_W_M2
    diurnal_phase_rad: float = 0.0
    coriolis_mean: float = 0.0
    chunks_heated: int = 0


def coriolis_parameter(lat_deg: float) -> float:
    return 2.0 * OMEGA_EARTH * math.sin(math.radians(lat_deg))


def core_geothermal_flux(elev_m: float, *, mantle_thickness_m: float = 30_000.0) -> float:
    """Flux W/m² depuis le noyau — plus fort en altitude basse (croûte fine)."""
    crust_thick = max(5000.0, mantle_thickness_m * (1.0 - min(elev_m, 4000.0) / 4000.0))
    return GEOTHERMAL_FLUX_W_M2 * (mantle_thickness_m / crust_thick)


def diurnal_insolation_factor(tick: int, *, ticks_per_day: int = 86400) -> float:
    """0..1 — jour/nuit sur la surface."""
    phase = (tick % ticks_per_day) / max(ticks_per_day, 1) * 2.0 * math.pi
    return float(0.5 + 0.5 * math.sin(phase - math.pi / 2.0))


def tick_earth_dynamo(sim) -> List[dict]:
    st: EarthDynamoState = getattr(sim, "_earth_dynamo", None)
    if st is None:
        return []
    st.ticks += 1
    dt_s = float(getattr(sim.cfg, "drive_accel", 1800.0))
    st.simulation_years += dt_s / (365.25 * 86400.0)
    st.diurnal_phase_rad = (sim.tick * dt_s * OMEGA_EARTH) % (2.0 * math.pi)
    insol_f = diurnal_insolation_factor(sim.tick)
    st.mean_insolation_w_m2 = INSOLATION_BASE_W_M2 * (0.25 + 0.75 * insol_f)

    anchor = getattr(sim.streamer, "genesis", None)
    coriolis_vals: List[float] = []
    heated = 0

    for coord, chunk in list(sim.streamer.cache.items()):
        elev = float(np.mean(chunk.height)) * 1000.0
        geo = core_geothermal_flux(elev)
        # Convertir flux en ΔT proxy par tick (très petit)
        dT = geo * dt_s / (2700.0 * 800.0 * 0.5)  # ρ·cp·épaisseur effective
        if float(chunk.height.mean()) > 0:
            chunk.height += np.float32(dT * 1e-6)  # relief micro-mètres géologiques
            heated += 1
        if anchor is not None:
            x_m = (coord[0] + 0.5) * CHUNK_SIDE_M
            y_m = (coord[1] + 0.5) * CHUNK_SIDE_M
            from engine.macro_climate import sample_macro_wind_at
            _, _ = sample_macro_wind_at(anchor, x_m, y_m)
            try:
                from engine.atmospheric_circulation import _latitude_deg_from_chunk
                lat = _latitude_deg_from_chunk(anchor, coord)
                coriolis_vals.append(abs(coriolis_parameter(lat)))
            except Exception:
                pass

    st.chunks_heated = heated
    st.coriolis_mean = float(np.mean(coriolis_vals)) if coriolis_vals else 0.0
    st.mean_core_temp_k = 6000.0 - 0.001 * st.simulation_years  # refroidissement négligeable

    if getattr(sim, "_autonomous_world", False) and sim.tick > 0 and sim.tick % 25 == 0:
        from engine.plate_tectonics_live import tick_plate_tectonics_live
        tick_plate_tectonics_live(sim)
    return []


def install_earth_dynamo(sim) -> EarthDynamoState:
    existing = getattr(sim, "_earth_dynamo", None)
    if existing is not None:
        return existing
    st = EarthDynamoState()
    sim._earth_dynamo = st
    if not getattr(sim, "_earth_dynamo_patched", False):
        sim._earth_dynamo_patched = True
        orig = sim.step

        def wrapped():
            stats = orig()
            tick_earth_dynamo(sim)
            return stats

        sim.step = wrapped
    return st


def dynamo_snapshot(sim) -> Dict[str, Any]:
    st: Optional[EarthDynamoState] = getattr(sim, "_earth_dynamo", None)
    if st is None:
        return {"installed": False}
    return {
        "installed": True,
        "ticks": st.ticks,
        "simulation_years": round(st.simulation_years, 4),
        "omega_rad_s": OMEGA_EARTH,
        "core_radius_m": CORE_RADIUS_M,
        "mean_core_temp_k": st.mean_core_temp_k,
        "geothermal_w_m2": round(st.mean_geothermal_w_m2, 4),
        "insolation_w_m2": round(st.mean_insolation_w_m2, 2),
        "diurnal_phase_rad": round(st.diurnal_phase_rad, 4),
        "coriolis_mean": round(st.coriolis_mean, 8),
        "chunks_heated": st.chunks_heated,
    }


__all__ = [
    "EarthDynamoState",
    "install_earth_dynamo",
    "tick_earth_dynamo",
    "dynamo_snapshot",
    "coriolis_parameter",
    "core_geothermal_flux",
]
