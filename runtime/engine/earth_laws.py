"""Lois de la Terre (L0) — axiomes EMERGENCE SIM v2, tickables et observables.

Consolide gravité, thermo (∇T), entropie proxy et champs lite pour Earth Console 2D.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.physics import G_EARTH, SIGMA_SB, weight
from engine.world import CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M

# Axiomes §2 EMERGENCE-SIM-v2 (métadonnées + clés runtime)
EARTH_AXIOMS: Tuple[Dict[str, str], ...] = (
    {"id": "E", "symbol": "E", "name": "Conservation d'énergie",
     "law": "Métabolisme + coûts d'action ; pas de création ex nihilo"},
    {"id": "gradT", "symbol": "∇T", "name": "Gradient thermique",
     "law": "Lapse ~6.5 K/km + météo chunk ; stress thermique agents"},
    {"id": "DNA", "symbol": "DNA", "name": "Hérédité + mutation",
     "law": "Génome 256-D, crossover, mutation 1e-4"},
    {"id": "dt", "symbol": "∂t", "name": "Temps discret",
     "law": "tick + MultiRateCoupler (météo / écologie)"},
    {"id": "dx", "symbol": "Δx", "name": "Localité",
     "law": "Perception et streaming chunks bornés"},
    {"id": "S", "symbol": "∅→∞", "name": "Entropie",
     "law": "Dégradation matériaux, famine, structures sans entretien"},
)

LAPSE_K_PER_M = 0.0065
BODY_TEMP_K = 310.15

BIOME_RGB = {
    0: (34, 90, 160),
    1: (55, 130, 75),
    2: (120, 145, 60),
    3: (190, 175, 95),
    4: (140, 110, 70),
    5: (200, 200, 210),
    6: (90, 75, 55),
    7: (30, 120, 200),
    8: (180, 140, 90),
    9: (100, 100, 100),
    10: (60, 140, 100),
    11: (220, 200, 120),
}


@dataclass
class EarthLawsState:
    ticks: int = 0
    mean_lapse_c_per_km: float = 6.5
    mean_agent_load_n: float = 0.0
    mean_surface_temp_c: float = 15.0
    metabolism_j_per_tick: float = 0.0
    entropy_proxy: float = 0.0
    chunks_in_cache: int = 0
    hydrology_active: bool = False
    last_events: List[dict] = field(default_factory=list)


def _agent_metabolism_j(sim) -> float:
    """Proxy énergie dissipée par les agents vivants (J/tick)."""
    a = sim.agents
    n = int(a.n_active)
    total = 0.0
    for row in range(n):
        if not a.alive[row]:
            continue
        mass = float(a.mass_kg[row])
        hunger = float(a.hunger[row])
        thermal = float(a.thermal[row])
        # ~80 W basal + stress terms
        total += mass * 1.2 + hunger * 400.0 + thermal * 200.0
    return total


def _entropy_proxy(sim) -> float:
    """0–1 : morts récentes + structures instables + ressources épuisées."""
    a = sim.agents
    alive = int(np.sum(a.alive[: a.n_active])) if a.n_active else 0
    cap = max(int(a.n_active), 1)
    death_ratio = 1.0 - alive / cap
    phy = getattr(sim, "_physics_layer", None)
    struct_fail = 0.0
    if phy is not None and phy.structures_checked > 0:
        unstable = phy.structures_checked - phy.structures_stable
        struct_fail = unstable / max(phy.structures_checked, 1)
    depleted = 0.0
    for chunk in list(sim.streamer.cache.values()):
        if float(chunk.food_kcal.max()) < 1.0 and float(chunk.water.max()) < 2.0:
            depleted += 1.0
    nchunks = max(len(sim.streamer.cache), 1)
    return float(np.clip(0.4 * death_ratio + 0.35 * struct_fail + 0.25 * (depleted / nchunks), 0.0, 1.0))


def tick_earth_laws(sim) -> List[dict]:
    """Agrège les lois L0 après le pas physique (appelé en fin de step)."""
    st: Optional[EarthLawsState] = getattr(sim, "_earth_laws", None)
    if st is None:
        return []
    st.ticks += 1
    events: List[dict] = []

    st.metabolism_j_per_tick = _agent_metabolism_j(sim)
    st.entropy_proxy = _entropy_proxy(sim)
    st.chunks_in_cache = len(sim.streamer.cache)
    st.hydrology_active = getattr(sim, "_chunk_hydrology_state", None) is not None

    phy = getattr(sim, "_physics_layer", None)
    if phy is not None:
        st.mean_agent_load_n = phy.last_mean_agent_load_n
        st.mean_surface_temp_c = phy.last_mean_surface_temp_c
        # Lapse effectif depuis échantillons chunk
        lapses = []
        for chunk in list(sim.streamer.cache.values()):
            elev_m = float(np.mean(chunk.height)) * 1000.0
            if elev_m < 1.0:
                continue
            t_c = phy.chunk_temps_c.get(chunk.coord, phy.last_mean_surface_temp_c)
            lapses.append((15.0 - t_c) / max(elev_m, 1.0) * 1000.0)
        if lapses:
            st.mean_lapse_c_per_km = float(np.mean(lapses))

    if st.ticks % 200 == 0 and st.entropy_proxy > 0.65:
        events.append({
            "kind": "earth_law_entropy",
            "tick": int(sim.tick),
            "entropy": round(st.entropy_proxy, 3),
        })
    st.last_events = events[-8:]
    return events


def install_earth_laws(sim, *, physics: bool = True) -> EarthLawsState:
    """Active L0 : physics_layer + suivi axiomes (idempotent)."""
    existing = getattr(sim, "_earth_laws", None)
    if existing is not None:
        return existing

    if physics:
        from engine.physics_layer import install_physics_layer
        install_physics_layer(sim)

    st = EarthLawsState()
    sim._earth_laws = st

    if not getattr(sim, "_earth_laws_step_patched", False):
        sim._earth_laws_step_patched = True
        orig = sim.step

        def wrapped():
            stats = orig()
            tick_earth_laws(sim)
            return stats

        sim.step = wrapped

    return st


def earth_laws_snapshot(sim) -> Dict[str, Any]:
    st: Optional[EarthLawsState] = getattr(sim, "_earth_laws", None)
    phy_snap: Dict[str, Any] = {}
    if getattr(sim, "_physics_layer", None):
        from engine.physics_layer import physics_layer_snapshot
        phy_snap = physics_layer_snapshot(sim)

    base = {
        "philosophy": "ZERO_PRE_SCRIPT",
        "layer": "L0_PHYSICS",
        "axioms": list(EARTH_AXIOMS),
        "constants": {
            "g_earth_ms2": G_EARTH,
            "lapse_k_per_m": LAPSE_K_PER_M,
            "sigma_sb": SIGMA_SB,
        },
        "physics": phy_snap,
    }
    if st is None:
        return base
    base["live"] = {
        "ticks": st.ticks,
        "mean_lapse_c_per_km": round(st.mean_lapse_c_per_km, 3),
        "mean_agent_load_n": round(st.mean_agent_load_n, 2),
        "mean_surface_temp_c": round(st.mean_surface_temp_c, 2),
        "metabolism_j_per_tick": round(st.metabolism_j_per_tick, 1),
        "entropy_proxy": round(st.entropy_proxy, 4),
        "chunks_in_cache": st.chunks_in_cache,
        "hydrology_active": st.hydrology_active,
    }
    return base


def sample_lite_field(
    sim,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    out_w: int = 160,
    out_h: int = 120,
    *,
    overlay: str = "",
) -> Dict[str, Any]:
    """Champ raster léger (RGBA base64) pour vue 2D — sans PNG /api/render."""
    out_w = max(16, min(int(out_w), 384))
    out_h = max(16, min(int(out_h), 288))
    span_x = max(xmax - xmin, 1e-3)
    span_y = max(ymax - ymin, 1e-3)

    px = (np.arange(out_w, dtype=np.float32) + 0.5) / out_w * span_x + xmin
    py = (np.arange(out_h, dtype=np.float32) + 0.5) / out_h * span_y + ymin
    XX, YY = np.meshgrid(px, py, indexing="xy")

    cx_arr = np.floor(XX / CHUNK_SIDE_M).astype(np.int32)
    cy_arr = np.floor(YY / CHUNK_SIDE_M).astype(np.int32)

    biome_out = np.zeros((out_h, out_w), dtype=np.int32)
    height_out = np.zeros((out_h, out_w), dtype=np.float32)
    water_out = np.zeros((out_h, out_w), dtype=np.float32)
    temp_out = np.full((out_h, out_w), 15.0, dtype=np.float32)

    meteo_chunks = {}
    ms = getattr(sim, "_meteo_state", None)
    if ms is not None:
        meteo_chunks = ms.chunk_meteo

    phy = getattr(sim, "_physics_layer", None)
    chunk_temps = phy.chunk_temps_c if phy is not None else {}

    pairs = np.unique(np.stack([cx_arr.ravel(), cy_arr.ravel()], axis=1), axis=0)
    for ccx, ccy in pairs:
        coord = (int(ccx), int(ccy), 0)
        try:
            ch = sim.streamer.get(sim.tick, coord)
        except Exception:
            continue
        mask = (cx_arr == ccx) & (cy_arr == ccy)
        lx_w = XX[mask] - ccx * CHUNK_SIDE_M
        ly_w = YY[mask] - ccy * CHUNK_SIDE_M
        ix = np.clip((lx_w / VOXEL_SIZE_M).astype(np.int32), 0, CHUNK_SIZE - 1)
        iy = np.clip((ly_w / VOXEL_SIZE_M).astype(np.int32), 0, CHUNK_SIZE - 1)
        biome_out[mask] = ch.biome[iy, ix].astype(np.int32)
        height_out[mask] = ch.height[iy, ix]
        water_out[mask] = ch.water[iy, ix]
        mc = meteo_chunks.get(coord)
        if mc is not None:
            temp_out[mask] = float(mc.temp_c)
        elif coord in chunk_temps:
            temp_out[mask] = float(chunk_temps[coord])

    palette = np.array(
        [BIOME_RGB.get(i, (128, 128, 128)) for i in range(12)],
        dtype=np.float32,
    )
    biome_clipped = np.clip(biome_out, 0, 11)
    cols = palette[biome_clipped].copy()
    shade = np.clip(0.42 + height_out / 3500.0, 0.28, 1.08)[..., None]
    cols *= shade
    water_mask = water_out > 5.0
    cols[water_mask] = cols[water_mask] * 0.35 + np.array([25, 95, 200], np.float32) * 0.65

    if overlay == "temp":
        t_norm = np.clip((temp_out - (-10.0)) / 45.0, 0.0, 1.0)[..., None]
        cold = np.array([60, 100, 200], np.float32)
        hot = np.array([230, 90, 50], np.float32)
        cols = cols * 0.45 + (cold * (1.0 - t_norm) + hot * t_norm) * 0.55
    elif overlay == "water":
        w_norm = np.clip(water_out / 500.0, 0.0, 1.0)[..., None]
        cols = cols * (1.0 - w_norm * 0.6) + np.array([30, 140, 255], np.float32) * (w_norm * 0.6)
    elif overlay == "flow":
        gx = np.zeros_like(water_out)
        gy = np.zeros_like(water_out)
        gx[:, 1:-1] = water_out[:, 2:] - water_out[:, :-2]
        gy[1:-1, :] = water_out[2:, :] - water_out[:-2, :]
        grad = np.sqrt(gx * gx + gy * gy)
        g_norm = np.clip(grad / (np.percentile(grad, 92) + 1e-3), 0.0, 1.0)[..., None]
        flow_col = np.array([80, 200, 255], np.float32)
        cols = cols * (1.0 - g_norm * 0.75) + flow_col * (g_norm * 0.75)
        river = water_out > 80.0
        cols[river] = cols[river] * 0.3 + np.array([40, 120, 240], np.float32) * 0.7

    rgba = np.zeros((out_h, out_w, 4), dtype=np.uint8)
    rgba[..., :3] = np.clip(cols, 0, 255).astype(np.uint8)
    rgba[..., 3] = 255

    return {
        "w": out_w,
        "h": out_h,
        "xmin": xmin,
        "ymin": ymin,
        "xmax": xmax,
        "ymax": ymax,
        "overlay": overlay or "terrain",
        "rgba_b64": base64.b64encode(rgba.tobytes()).decode("ascii"),
        "tick": int(sim.tick),
    }


__all__ = [
    "EARTH_AXIOMS",
    "EarthLawsState",
    "install_earth_laws",
    "tick_earth_laws",
    "earth_laws_snapshot",
    "sample_lite_field",
]
