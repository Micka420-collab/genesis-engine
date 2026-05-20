"""Novel world operators — not present elsewhere in Genesis Engine.

Each operator is a pure numpy transform on macro/chunk fields with a
parameter vector evolved by :mod:`algorithm_evolution`.

Operators (ZERO PRE-SCRIPT — substrate only):
  - mycorrhizal_mesh     fungal nutrient diffusion on land → food_capacity
  - aurora_ionosphere    polar thermodynamic coupling wind ↔ T
  - orographic_resonance standing wave precip reinforcement on ridges
  - plate_stress_cascade seismic energy release on plate boundaries
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

import numpy as np

from engine.world_genesis import GenesisWorld

PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"

OPERATOR_IDS = (
    "mycorrhizal_mesh",
    "aurora_ionosphere",
    "orographic_resonance",
    "plate_stress_cascade",
)

# param name → (min, max, default)
PARAM_SPECS: Dict[str, Dict[str, Tuple[float, float, float]]] = {
    "mycorrhizal_mesh": {
        "diffusion": (0.02, 0.35, 0.12),
        "decay": (0.001, 0.08, 0.02),
        "forest_inject": (0.05, 0.6, 0.25),
    },
    "aurora_ionosphere": {
        "lat_threshold": (50.0, 75.0, 62.0),
        "coupling": (0.01, 0.25, 0.08),
        "wind_power": (0.5, 2.5, 1.2),
    },
    "orographic_resonance": {
        "ridge_gain": (0.02, 0.4, 0.15),
        "wavelength_km": (80.0, 400.0, 200.0),
        "damping": (0.1, 0.9, 0.45),
    },
    "plate_stress_cascade": {
        "accum_rate": (0.001, 0.05, 0.012),
        "release_threshold": (0.3, 0.95, 0.72),
        "uplift_m": (1.0, 80.0, 18.0),
    },
}


@dataclass
class OperatorGenome:
    operator_id: str
    params: Dict[str, float]
    generation: int = 0
    fitness: float = 0.0
    genome_id: int = 0

    def clone(self) -> "OperatorGenome":
        return OperatorGenome(
            operator_id=self.operator_id,
            params=dict(self.params),
            generation=self.generation,
            fitness=self.fitness,
            genome_id=self.genome_id,
        )


def default_params(operator_id: str) -> Dict[str, float]:
    spec = PARAM_SPECS[operator_id]
    return {k: v[2] for k, v in spec.items()}


def clamp_params(operator_id: str, params: Dict[str, float]) -> Dict[str, float]:
    spec = PARAM_SPECS[operator_id]
    out: Dict[str, float] = {}
    for k, (lo, hi, _) in spec.items():
        out[k] = float(np.clip(params.get(k, lo), lo, hi))
    return out


def _neighbor_sum(arr: np.ndarray) -> np.ndarray:
    s = arr.copy()
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        sh = np.roll(arr, (dy, dx), axis=(0, 1))
        if dy == -1:
            sh[0, :] = arr[0, :]
        if dy == 1:
            sh[-1, :] = arr[-1, :]
        if dx == -1:
            sh[:, 0] = arr[:, 0]
        if dx == 1:
            sh[:, -1] = arr[:, -1]
        s += sh
    return s


def apply_mycorrhizal_mesh(world: GenesisWorld, p: Dict[str, float]) -> float:
    """Diffuse soil nutrient index; boost precip on connected forest biomes."""
    diff = p["diffusion"]
    decay = p["decay"]
    inj = p["forest_inject"]
    land = world.elevation_m > 0.0
    forest = (world.biome >= 3) & (world.biome <= 5) | (world.biome >= 10)
    N = np.where(forest & land, inj, 0.0).astype(np.float32)
    for _ in range(3):
        N = (1.0 - decay) * N + diff * (_neighbor_sum(N) / 5.0 - N)
    boost = np.clip(N * 0.15, 0.0, 0.12)
    world.precip_mm = np.clip(world.precip_mm * (1.0 + boost), 0.0, None)
    return float(np.mean(N[land])) if land.any() else 0.0


def apply_aurora_ionosphere(world: GenesisWorld, p: Dict[str, float]) -> float:
    """Polar cells: wind kinetic energy couples into surface temperature."""
    lat_th = p["lat_threshold"]
    coupling = p["coupling"]
    power = p["wind_power"]
    lat = np.abs(world.latitude_deg)
    mask = lat >= lat_th
    if not mask.any():
        return 0.0
    spd = np.sqrt(world.wind_u ** 2 + world.wind_v ** 2)
    dT = coupling * (spd ** power) * (lat - lat_th) / max(90.0 - lat_th, 1.0)
    world.temp_c = world.temp_c + np.where(mask, dT, 0.0).astype(np.float32)
    return float(np.mean(dT[mask]))


def apply_orographic_resonance(world: GenesisWorld, p: Dict[str, float]) -> float:
    """Standing lee-wave proxy: sin(elevation phase) modulates precip."""
    gain = p["ridge_gain"]
    wl = max(p["wavelength_km"], 20.0)
    damp = p["damping"]
    cell_km = world.params.map_size_km / world.params.resolution
    phase = (world.elevation_m / max(wl, 1.0)) * (2.0 * math.pi / cell_km)
    wave = np.sin(phase) * np.exp(-damp * np.maximum(world.elevation_m, 0.0) / 2000.0)
    land = world.elevation_m > 50.0
    mod = np.where(land, 1.0 + gain * wave, 1.0)
    world.precip_mm = np.clip(world.precip_mm * mod.astype(np.float32), 0.0, None)
    return float(np.std(wave[land])) if land.any() else 0.0


def apply_plate_stress_cascade(world: GenesisWorld, p: Dict[str, float]) -> float:
    """Accumulate stress on plate boundaries; release as elevation jitter."""
    accum = p["accum_rate"]
    thresh = p["release_threshold"]
    uplift = p["uplift_m"]
    boundary = world.boundary_kind > 0
    stress = np.zeros_like(world.elevation_m, dtype=np.float32)
    stress[boundary] = accum
    stress = _neighbor_sum(stress) / 5.0
    release = stress >= thresh
    if release.any():
        world.elevation_m = world.elevation_m + np.where(
            release, uplift * (stress - thresh), 0.0
        ).astype(np.float32)
    return float(release.mean())


_APPLY: Dict[str, Callable[[GenesisWorld, Dict[str, float]], float]] = {
    "mycorrhizal_mesh": apply_mycorrhizal_mesh,
    "aurora_ionosphere": apply_aurora_ionosphere,
    "orographic_resonance": apply_orographic_resonance,
    "plate_stress_cascade": apply_plate_stress_cascade,
}


def apply_operator(genome: OperatorGenome, world: GenesisWorld) -> float:
    """Apply one operator in-place; return internal activity metric."""
    fn = _APPLY.get(genome.operator_id)
    if fn is None:
        return 0.0
    p = clamp_params(genome.operator_id, genome.params)
    return float(fn(world, p))


def snapshot_world_arrays(world: GenesisWorld) -> Dict[str, np.ndarray]:
    return {
        "wind_u": world.wind_u.copy(),
        "wind_v": world.wind_v.copy(),
        "temp_c": world.temp_c.copy(),
        "precip_mm": world.precip_mm.copy(),
        "elevation_m": world.elevation_m.copy(),
    }


def restore_world_arrays(world: GenesisWorld, snap: Dict[str, np.ndarray]) -> None:
    world.wind_u[:] = snap["wind_u"]
    world.wind_v[:] = snap["wind_v"]
    world.temp_c[:] = snap["temp_c"]
    world.precip_mm[:] = snap["precip_mm"]
    world.elevation_m[:] = snap["elevation_m"]


__all__ = [
    "OPERATOR_IDS",
    "PARAM_SPECS",
    "OperatorGenome",
    "apply_operator",
    "default_params",
    "clamp_params",
    "snapshot_world_arrays",
    "restore_world_arrays",
]
