"""Plaques tectoniques en mouvement — monde autonome (L1).

Les plaques dérivent (cm/an), les frontières et le soulèvement se
recalculent ; l'élévation macro et les chunks locaux évoluent lentement.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.world import CHUNK_SIDE_M, world_to_chunk
from engine.world_genesis import (
    BOUND_CONVERGENT,
    BOUND_DIVERGENT,
    BOUND_NONE,
    BOUND_TRANSFORM,
    CONTINENTAL,
    OCEANIC,
    GenesisAnchor,
    GenesisWorld,
)

PIPELINE_LAYER = "Genesis-L1 World"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# 1 tick géologique ≈ 100 000 ans simulés (échelle coupler Tectonics)
MYR_PER_TECTONIC_TICK = 0.1


@dataclass
class PlateTectonicsLiveState:
    ticks: int = 0
    myr_elapsed: float = 0.0
    mean_plate_speed_cm_yr: float = 0.0
    boundary_cells: int = 0
    convergent_cells: int = 0
    elevation_delta_m: float = 0.0
    last_events: List[dict] = field(default_factory=list)


def _voronoi_from_seeds(world: GenesisWorld) -> np.ndarray:
    p = world.params
    R = p.resolution
    cell_size = p.map_size_km / R
    seeds = world.plate_seeds
    xs = (np.arange(R, dtype=np.float32) + 0.5) * cell_size
    ys = (np.arange(R, dtype=np.float32) + 0.5) * cell_size
    XX, YY = np.meshgrid(xs, ys, indexing="xy")
    dx = XX[..., None] - seeds[:, 0][None, None, :]
    dy = YY[..., None] - seeds[:, 1][None, None, :]
    d2 = dx * dx + dy * dy
    return np.argmin(d2, axis=2).astype(np.uint8)


def _classify_boundaries_live(world: GenesisWorld, plate_id: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Simplified boundary + uplift from plate motion."""
    R = world.params.resolution
    kinds = world.plate_kind
    motion = world.plate_motion
    boundary = np.zeros((R, R), dtype=np.uint8)
    uplift = np.zeros((R, R), dtype=np.float32)
    for iy in range(R):
        for ix in range(R):
            pid = int(plate_id[iy, ix])
            best_b = BOUND_NONE
            best_u = 0.0
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = ix + dx, iy + dy
                if 0 <= nx < R and 0 <= ny < R:
                    npid = int(plate_id[ny, nx])
                    if npid != pid:
                        v = motion[pid] - motion[npid]
                        rel = float(v[0] * dx + v[1] * dy)
                        if rel > 0.5:
                            best_b = BOUND_CONVERGENT
                            kk = kinds[pid], kinds[npid]
                            if kk[0] == CONTINENTAL and kk[1] == CONTINENTAL:
                                best_u = max(best_u, 8.0)
                            elif CONTINENTAL in kk:
                                best_u = max(best_u, 4.0)
                            else:
                                best_u = max(best_u, 1.5)
                        elif rel < -0.5:
                            best_b = BOUND_DIVERGENT
                            best_u = max(best_u, 0.8)
                        else:
                            best_b = BOUND_TRANSFORM
                            best_u = max(best_u, 0.2)
            boundary[iy, ix] = best_b
            uplift[iy, ix] = best_u
    return boundary, uplift


def tick_plate_tectonics_live(sim) -> List[dict]:
    st: PlateTectonicsLiveState = getattr(sim, "_plate_tectonics_live", None)
    if st is None:
        return []
    anchor: Optional[GenesisAnchor] = getattr(sim.streamer, "genesis", None)
    if anchor is None:
        return []

    world = anchor.world
    st.ticks += 1
    st.myr_elapsed += MYR_PER_TECTONIC_TICK
    dt_myr = MYR_PER_TECTONIC_TICK

    # Déplacer les graines de plaques (cm/yr → km/Myr)
    motion_km_myr = world.plate_motion.astype(np.float64) * (dt_myr * 1e5)
    world.plate_seeds = np.clip(
        world.plate_seeds + motion_km_myr,
        0.0,
        float(world.params.map_size_km) - 1.0,
    ).astype(np.float32)

    plate_id = _voronoi_from_seeds(world)
    boundary, uplift = _classify_boundaries_live(world, plate_id)
    world.plate_id[:] = plate_id
    world.boundary_kind[:] = boundary
    world.uplift_rate[:] = uplift

    # Élévation macro : convergence soulève, divergence abaisse légèrement
    d_elev = np.zeros_like(world.elevation_m)
    conv = boundary == BOUND_CONVERGENT
    div = boundary == BOUND_DIVERGENT
    d_elev[conv] = uplift[conv] * dt_myr * 0.01
    d_elev[div] = -0.3 * dt_myr
    world.elevation_m = np.clip(world.elevation_m + d_elev, -8000.0, 9000.0).astype(np.float32)
    st.elevation_delta_m = float(np.mean(np.abs(d_elev)))

    st.boundary_cells = int(np.sum(boundary > BOUND_NONE))
    st.convergent_cells = int(np.sum(conv))
    st.mean_plate_speed_cm_yr = float(np.mean(np.linalg.norm(world.plate_motion, axis=1)))

    # Propager aux chunks streamés (échantillon centre chunk)
    for coord, chunk in list(sim.streamer.cache.items()):
        x_m = (coord[0] + 0.5) * CHUNK_SIDE_M
        y_m = (coord[1] + 0.5) * CHUNK_SIDE_M
        p = world.params
        R = p.resolution
        cell_km = p.map_size_km / R
        x_km = x_m / 1000.0 + anchor.sim_origin_macro_km[0]
        y_km = y_m / 1000.0 + anchor.sim_origin_macro_km[1]
        ix = int(np.clip(np.floor(x_km / cell_km), 0, R - 1))
        iy = int(np.clip(np.floor(y_km / cell_km), 0, R - 1))
        de = float(d_elev[iy, ix]) * 1e-6  # m par tick géo
        if abs(de) > 1e-9:
            chunk.height += np.float32(de)

    events: List[dict] = []
    if st.convergent_cells > 0 and st.ticks % 5 == 0:
        events.append({
            "kind": "tectonic_pulse",
            "myr": round(st.myr_elapsed, 3),
            "convergent_cells": st.convergent_cells,
        })
    st.last_events = events[-5:]
    return events


def install_plate_tectonics_live(sim) -> PlateTectonicsLiveState:
    existing = getattr(sim, "_plate_tectonics_live", None)
    if existing is not None:
        return existing
    st = PlateTectonicsLiveState()
    sim._plate_tectonics_live = st
    return st


def plate_tectonics_snapshot(sim) -> Dict[str, Any]:
    st: Optional[PlateTectonicsLiveState] = getattr(sim, "_plate_tectonics_live", None)
    if st is None:
        return {"installed": False}
    return {
        "installed": True,
        "ticks": st.ticks,
        "myr_elapsed": round(st.myr_elapsed, 4),
        "mean_speed_cm_yr": round(st.mean_plate_speed_cm_yr, 3),
        "boundary_cells": st.boundary_cells,
        "convergent_cells": st.convergent_cells,
        "elevation_delta_m": round(st.elevation_delta_m, 6),
        "myr_per_tick": MYR_PER_TECTONIC_TICK,
    }


__all__ = [
    "PlateTectonicsLiveState",
    "install_plate_tectonics_live",
    "tick_plate_tectonics_live",
    "plate_tectonics_snapshot",
]
