"""Physics layer — gravité, statique (délégation), thermodynamique locale.

Branche ``engine.physics`` et ``engine.statics`` sur le tick de simulation :
poids des agents, contraintes thermiques sur les chunks, validation statique
des structures voxel (via :mod:`architecture_layer`).

ADR-0005: Genesis-L2 Simulator (paper-L2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple  # noqa: F401 used in state

import numpy as np

from engine.physics import (
    G_EARTH,
    heat_transfer_conduction,
    heat_transfer_radiation,
    thermal_conductivity_table,
    weight,
)
from engine.statics import analyze, is_structurally_stable
from engine.statics_load import (
    compute_stability_score,
    is_structurally_stable_spread,
)
from engine.world import world_to_cell, world_to_chunk


PIPELINE_LAYER = "Genesis-L2 Simulator"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"

VOXEL_SIZE_M = 0.5


@dataclass
class PhysicsLayerState:
    last_mean_agent_load_n: float = 0.0
    last_mean_chunk_cond_w_mk: float = 0.0
    last_mean_surface_temp_c: float = 15.0
    structures_checked: int = 0
    structures_stable: int = 0
    last_stability_score: float = 1.0
    chunk_temps_c: Dict[Tuple[int, int, int], float] = field(default_factory=dict)
    pending_voxel_structures: List[Any] = field(default_factory=list)


def tick_physics_layer(sim) -> List[dict]:
    """Per-tick physics: agent loads + chunk thermo conductivity sample."""
    st: PhysicsLayerState = getattr(sim, "_physics_layer", None)
    if st is None:
        return []
    events: List[dict] = []

    # Agent weight under gravity (inventory + body mass).
    loads = []
    n = sim.agents.n_active
    for row in range(n):
        if not sim.agents.alive[row]:
            continue
        mass = float(sim.agents.mass_kg[row])
        for fld in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal"):
            arr = getattr(sim.agents, fld, None)
            if arr is not None:
                mass += float(arr[row])
        loads.append(weight(mass))
    st.last_mean_agent_load_n = float(np.mean(loads)) if loads else 0.0

    # Chunk-scale effective conductivity (proxy from dominant surface material).
    conds = []
    for chunk in list(sim.streamer.cache.values()):
        mat = "stone"
        if float(chunk.water.max()) > 80.0:
            mat = "water"
        elif float(np.mean(chunk.wood)) > 1.0:
            mat = "wood"
        k = float(thermal_conductivity_table.get(mat, 1.0))
        conds.append(k)
    st.last_mean_chunk_cond_w_mk = float(np.mean(conds)) if conds else 0.0

    # Surface temperature proxy per chunk (lapse rate + diurnal weather).
    from engine.world import weather_at

    temps = []
    lapse_k_per_m = 0.0065
    for chunk in list(sim.streamer.cache.values()):
        elev_m = float(np.mean(chunk.height))
        base_t = 15.0 - lapse_k_per_m * elev_m * 1000.0
        w = weather_at(int(sim.tick), base_t, 600.0)
        st.chunk_temps_c[chunk.coord] = float(w.temp_c)
        temps.append(float(w.temp_c))
    st.last_mean_surface_temp_c = float(np.mean(temps)) if temps else 15.0

    # Agent thermal stress from local chunk temperature (1-node balance).
    n = sim.agents.n_active
    for row in range(n):
        if not sim.agents.alive[row]:
            continue
        px = float(sim.agents.pos[row, 0])
        py = float(sim.agents.pos[row, 1])
        cc = world_to_chunk(px, py)
        t_amb = st.chunk_temps_c.get(cc, st.last_mean_surface_temp_c)
        delta = agent_thermal_delta(sim, row, t_amb)
        sim.agents.thermal[row] = float(
            np.clip(float(sim.agents.thermal[row]) + delta * 0.02, 0.0, 1.5))

    return events


def check_voxel_structure_stable(
    blocks: List[Tuple[int, int, int, str]],
    *,
    voxel_size_m: float = 0.25,
) -> Tuple[bool, str]:
    """Validate voxel grid coords (ix, iy, iz, material) with statics + gravity."""
    from engine.statics import Structure

    vblocks = [
        __import__("engine.statics", fromlist=["VoxelBlock"]).VoxelBlock.from_material(
            (b[0], b[1], b[2]), b[3], voxel_size_m)
        for b in blocks
    ]
    struct = Structure(structure_id=0, blocks=vblocks, voxel_size_m=voxel_size_m)
    ok, reason = is_structurally_stable_spread(struct)
    if not ok:
        return False, reason
    report = analyze(struct)
    if not report.get("is_stable", False):
        return False, str(report.get("reason", "analyze_failed"))
    return True, "ok"


def structure_stability_score(
    blocks: List[Tuple[int, int, int, str]],
    *,
    voxel_size_m: float = 0.25,
) -> float:
    """Return [0,1] stability margin for a voxel list."""
    from engine.statics import Structure

    vblocks = [
        __import__("engine.statics", fromlist=["VoxelBlock"]).VoxelBlock.from_material(
            (b[0], b[1], b[2]), b[3], voxel_size_m)
        for b in blocks
    ]
    struct = Structure(structure_id=0, blocks=vblocks, voxel_size_m=voxel_size_m)
    return compute_stability_score(struct)


def agent_thermal_delta(sim, row: int, temp_ambient_c: float) -> float:
    """Radiative + conductive delta for one agent (simplified 1-node model)."""
    body_t_k = 37.0 + 273.15
    amb_k = float(temp_ambient_c) + 273.15
    area = 1.8
    emissivity = 0.9
    q_rad = heat_transfer_radiation(
        emissivity, area, body_t_k, amb_k)
    q_cond = heat_transfer_conduction(
        0.5, area, abs(body_t_k - amb_k), 0.02)
    # Positive delta = more thermal stress when ambient is cold.
    return float(max(0.0, (amb_k - body_t_k) * -1e-5 + q_cond * 1e-6))


def install_physics_layer(sim) -> PhysicsLayerState:
    existing = getattr(sim, "_physics_layer", None)
    if existing is not None:
        return existing
    st = PhysicsLayerState()
    sim._physics_layer = st
    if not getattr(sim, "_physics_layer_step_patched", False):
        sim._physics_layer_step_patched = True
        orig = sim.step

        def wrapped():
            stats = orig()
            tick_physics_layer(sim)
            return stats

        sim.step = wrapped
    return st


def physics_layer_snapshot(sim) -> Dict[str, object]:
    st: Optional[PhysicsLayerState] = getattr(sim, "_physics_layer", None)
    if st is None:
        return {}
    return {
        "g_earth": G_EARTH,
        "mean_agent_load_n": round(st.last_mean_agent_load_n, 2),
        "mean_chunk_conductivity_w_mk": round(st.last_mean_chunk_cond_w_mk, 4),
        "structures_checked": st.structures_checked,
        "structures_stable": st.structures_stable,
        "last_stability_score": st.last_stability_score,
        "mean_surface_temp_c": round(st.last_mean_surface_temp_c, 2),
        "chunks_thermo_tracked": len(st.chunk_temps_c),
    }


__all__ = [
    "PhysicsLayerState",
    "install_physics_layer",
    "tick_physics_layer",
    "check_voxel_structure_stable",
    "agent_thermal_delta",
    "physics_layer_snapshot",
]
