"""Procedural world: terrain, biomes, resources, weather, chunk streaming."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Iterable, List, Tuple

import numpy as np

from engine.core import prf_rng, prf_bytes


def _stable_layer_salt(seed: int, layer: str) -> int:
    """Process-stable 64-bit salt derived from (seed, layer).

    Python's built-in ``hash`` is randomised per process when PYTHONHASHSEED
    is not fixed, which silently breaks the determinism contract of the
    procedural world.  This BLAKE2b-based salt is identical across processes
    and platforms, so terrain generated with the same (seed, layer) is
    bit-for-bit reproducible.
    """
    h = hashlib.blake2b(digest_size=8)
    h.update(int(seed).to_bytes(16, "little", signed=False))
    h.update(b"|")
    h.update(layer.encode("utf-8"))
    return int.from_bytes(h.digest(), "little", signed=False)


def _stable_bytes_sig(buf: bytes) -> int:
    """Process-stable 32-bit signature for a byte buffer (used for lexicon hashes)."""
    h = hashlib.blake2b(buf, digest_size=4)
    return int.from_bytes(h.digest(), "little", signed=False)


# ---------------------------------------------------------------------------
# Biomes (Whittaker simplified)
# ---------------------------------------------------------------------------

class Biome(IntEnum):
    OCEAN = 0
    ICE = 1
    TUNDRA = 2
    BOREAL_FOREST = 3
    TEMPERATE_FOREST = 4
    TEMPERATE_RAINFOREST = 5
    GRASSLAND = 6
    HOT_DESERT = 7
    COLD_DESERT = 8
    SAVANNA = 9
    TROPICAL_DRY_FOREST = 10
    TROPICAL_RAINFOREST = 11


_BIOME_NPP = {
    Biome.OCEAN: 0.30, Biome.ICE: 0.05, Biome.TUNDRA: 0.15,
    Biome.BOREAL_FOREST: 0.55, Biome.TEMPERATE_FOREST: 0.80,
    Biome.TEMPERATE_RAINFOREST: 0.80, Biome.GRASSLAND: 0.45,
    Biome.HOT_DESERT: 0.05, Biome.COLD_DESERT: 0.05,
    Biome.SAVANNA: 0.45, Biome.TROPICAL_DRY_FOREST: 0.55,
    Biome.TROPICAL_RAINFOREST: 1.00,
}

_BIOME_HABITABILITY = {
    Biome.OCEAN: 0.0, Biome.ICE: 0.05, Biome.TUNDRA: 0.15,
    Biome.BOREAL_FOREST: 0.50, Biome.TEMPERATE_FOREST: 0.90,
    Biome.TEMPERATE_RAINFOREST: 0.90, Biome.GRASSLAND: 0.85,
    Biome.HOT_DESERT: 0.20, Biome.COLD_DESERT: 0.20,
    Biome.SAVANNA: 0.85, Biome.TROPICAL_DRY_FOREST: 0.85,
    Biome.TROPICAL_RAINFOREST: 0.70,
}


def biome_npp(b: Biome) -> float:
    return _BIOME_NPP[b]


def biome_habitability(b: Biome) -> float:
    return _BIOME_HABITABILITY[b]


def classify_biome(temp_c: float, precip_mm: float, elev_m: float) -> Biome:
    if elev_m < 0.0:
        return Biome.OCEAN
    if temp_c < -10.0:
        return Biome.ICE
    if temp_c < 0.0:
        return Biome.TUNDRA
    if temp_c < 10.0:
        return Biome.COLD_DESERT if precip_mm < 300.0 else Biome.BOREAL_FOREST
    if temp_c < 20.0:
        if precip_mm < 250.0: return Biome.COLD_DESERT
        if precip_mm < 750.0: return Biome.GRASSLAND
        if precip_mm < 1500.0: return Biome.TEMPERATE_FOREST
        return Biome.TEMPERATE_RAINFOREST
    if precip_mm < 250.0: return Biome.HOT_DESERT
    if precip_mm < 750.0: return Biome.SAVANNA
    if precip_mm < 1500.0: return Biome.TROPICAL_DRY_FOREST
    return Biome.TROPICAL_RAINFOREST


# ---------------------------------------------------------------------------
# Deterministic value-noise (numpy-vectorized, hashed)
# ---------------------------------------------------------------------------

def _cell_values(seed: int, layer: str, gx: np.ndarray, gy: np.ndarray) -> np.ndarray:
    """Hash (gx, gy) -> float in [-1, 1] (vectorized, deterministic, uint64 mix)."""
    a = (gx.astype(np.uint64) * np.uint64(73856093)) ^ (gy.astype(np.uint64) * np.uint64(19349663))
    salt = np.uint64(_stable_layer_salt(int(seed), layer) & 0xFFFFFFFFFFFFFFFF)
    a = a ^ salt
    # SplitMix64-style avalanche
    a = (a ^ (a >> np.uint64(33))) * np.uint64(0xff51afd7ed558ccd)
    a = (a ^ (a >> np.uint64(33))) * np.uint64(0xc4ceb9fe1a85ec53)
    a = a ^ (a >> np.uint64(33))
    # Map uint64 -> [-1, 1]
    return ((a.astype(np.float64) / float(np.iinfo(np.uint64).max)) * 2.0 - 1.0).astype(np.float32)


def _smooth_lerp(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
    f = (1.0 - np.cos(t * math.pi)) * 0.5
    return a + (b - a) * f


def value_noise_2d(seed: int, layer: str, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    gx = np.floor(x).astype(np.int64)
    gy = np.floor(y).astype(np.int64)
    fx = (x - gx).astype(np.float32)
    fy = (y - gy).astype(np.float32)
    v00 = _cell_values(seed, layer, gx, gy)
    v10 = _cell_values(seed, layer, gx + 1, gy)
    v01 = _cell_values(seed, layer, gx, gy + 1)
    v11 = _cell_values(seed, layer, gx + 1, gy + 1)
    i1 = _smooth_lerp(v00, v10, fx)
    i2 = _smooth_lerp(v01, v11, fx)
    return _smooth_lerp(i1, i2, fy)


def fbm_2d(seed: int, layer: str, x: np.ndarray, y: np.ndarray,
           octaves: int = 5, lacunarity: float = 2.0, gain: float = 0.5) -> np.ndarray:
    amp, freq, sum_, norm = 1.0, 1.0, np.zeros_like(x, dtype=np.float32), 0.0
    for _ in range(octaves):
        sum_ += value_noise_2d(seed, layer, x * freq, y * freq) * amp
        norm += amp
        amp *= gain
        freq *= lacunarity
    return sum_ / max(norm, 1e-6)


# ---------------------------------------------------------------------------
# Terrain sampling (numpy-vectorized)
# ---------------------------------------------------------------------------

@dataclass
class TerrainParams:
    scale_m: float = 2_000.0
    max_elev_m: float = 4_000.0
    sea_level_m: float = 0.0
    elev_octaves: int = 6
    temp_octaves: int = 3
    precip_octaves: int = 4


def sample_terrain(seed: int, params: TerrainParams,
                   x_m: np.ndarray, y_m: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized: returns (elev_m, temp_c, precip_mm) arrays."""
    x = x_m / params.scale_m
    y = y_m / params.scale_m
    e_raw = fbm_2d(seed, "elev", x, y, params.elev_octaves)
    elev_m = params.sea_level_m + e_raw * params.max_elev_m
    lat_factor = 1.0 - np.minimum(np.abs(y_m) / 10_000_000.0, 1.0)
    t_noise = fbm_2d(seed, "temp", x * 0.3, y * 0.3, params.temp_octaves)
    temp_at_sea = 30.0 * lat_factor - 5.0 + t_noise * 8.0
    elev_drop = np.maximum(elev_m, 0.0) / 1000.0 * 6.5
    temp_c = temp_at_sea - elev_drop
    p_raw = fbm_2d(seed, "precip", x * 0.5, y * 0.5, params.precip_octaves)
    precip_mm = np.maximum((p_raw + 1.0) * 0.5 * 4_000.0, 0.0)
    return elev_m.astype(np.float32), temp_c.astype(np.float32), precip_mm.astype(np.float32)


# ---------------------------------------------------------------------------
# Chunks
# ---------------------------------------------------------------------------

CHUNK_SIZE = 64       # cells per chunk side
VOXEL_SIZE_M = 0.5    # metres per cell
CHUNK_SIDE_M = CHUNK_SIZE * VOXEL_SIZE_M   # 32 m


@dataclass
class Chunk:
    coord: Tuple[int, int, int]
    height: np.ndarray            # (CHUNK_SIZE, CHUNK_SIZE) float32
    biome: np.ndarray             # (CHUNK_SIZE, CHUNK_SIZE) uint8 of Biome
    stone: np.ndarray             # kg/m^2 per cell
    wood: np.ndarray
    metal: np.ndarray
    water: np.ndarray             # litres/cell (regenerative on rain)
    food_kcal: np.ndarray         # kcal/cell (regenerative via NPP)
    food_capacity: np.ndarray     # max kcal/cell (cached)
    content_root: bytes


def generate_chunk(seed: int, coord: Tuple[int, int, int], params: TerrainParams) -> Chunk:
    cx, cy, cz = coord
    ox = cx * CHUNK_SIDE_M
    oy = cy * CHUNK_SIDE_M
    xs = (ox + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
    ys = (oy + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
    XX, YY = np.meshgrid(xs, ys, indexing="xy")
    elev, temp, precip = sample_terrain(seed, params, XX, YY)
    biome = np.empty_like(elev, dtype=np.uint8)
    flat_elev, flat_temp, flat_precip = elev.ravel(), temp.ravel(), precip.ravel()
    flat_biome = biome.ravel()
    for i in range(flat_elev.size):
        flat_biome[i] = int(classify_biome(float(flat_temp[i]), float(flat_precip[i]), float(flat_elev[i])))

    # Resources (vectorized + small deterministic noise)
    rng = prf_rng(seed, ["world", "resources"], [cx, cy, cz])
    nz = elev.size
    noise_a = rng.random(nz, dtype=np.float32)
    noise_b = rng.random(nz, dtype=np.float32)
    noise_c = rng.random(nz, dtype=np.float32)
    noise_d = rng.random(nz, dtype=np.float32)
    base_stone = np.where(
        (biome == Biome.HOT_DESERT) | (biome == Biome.COLD_DESERT), 30.0,
        np.where((biome == Biome.ICE) | (biome == Biome.TUNDRA), 20.0, 10.0)
    )
    stone = np.maximum(base_stone + np.maximum(elev, 0.0) * 0.02 + noise_a.reshape(elev.shape) * 5.0, 0.0)
    wood = np.zeros_like(elev)
    wood[biome == Biome.TROPICAL_RAINFOREST] = 80.0
    wood[biome == Biome.TEMPERATE_RAINFOREST] = 50.0
    wood[biome == Biome.TEMPERATE_FOREST] = 50.0
    wood[biome == Biome.BOREAL_FOREST] = 30.0
    wood[biome == Biome.TROPICAL_DRY_FOREST] = 30.0
    wood[biome == Biome.SAVANNA] = 5.0
    wood = wood + (noise_b.reshape(elev.shape) * 15.0) * (wood > 0)
    metal_mask = noise_c.reshape(elev.shape) < (0.01 + np.minimum(np.maximum(elev, 0.0), 3000.0) / 60_000.0)
    metal = np.zeros_like(elev)
    metal[metal_mask] = noise_d.reshape(elev.shape)[metal_mask] * 50.0

    # Water sources: ocean + lakes (low elev) + scattered springs in wet biomes
    water = np.zeros_like(elev)
    water[(biome == Biome.OCEAN) | (elev < 1.5)] = 1000.0
    # Springs in wet biomes
    spring_prob = np.zeros_like(elev)
    for wet in (Biome.TEMPERATE_FOREST, Biome.TEMPERATE_RAINFOREST,
                Biome.TROPICAL_RAINFOREST, Biome.BOREAL_FOREST, Biome.GRASSLAND,
                Biome.SAVANNA, Biome.TROPICAL_DRY_FOREST, Biome.TUNDRA):
        spring_prob[biome == wet] = 0.02
    spring_mask = noise_a.reshape(elev.shape) < spring_prob
    water[spring_mask] = np.maximum(water[spring_mask], 200.0)

    # Food capacity from NPP (kcal/cell)
    npp = np.zeros_like(elev)
    for b_id in range(12):
        mask = (biome == b_id)
        if mask.any():
            npp[mask] = _BIOME_NPP[Biome(b_id)]
    food_capacity = npp * 500.0  # kcal/cell, scaled
    food_kcal = food_capacity.copy()

    content_root = prf_bytes(seed, ["chunk_root", str(cx), str(cy), str(cz)], [], 32)
    return Chunk(coord=(cx, cy, cz),
                 height=elev, biome=biome,
                 stone=stone.astype(np.float32), wood=wood.astype(np.float32),
                 metal=metal.astype(np.float32), water=water.astype(np.float32),
                 food_kcal=food_kcal.astype(np.float32),
                 food_capacity=food_capacity.astype(np.float32),
                 content_root=content_root)


# ---------------------------------------------------------------------------
# Chunk streamer (LRU GC, on-demand generation)
# ---------------------------------------------------------------------------

class ChunkStreamer:
    def __init__(self, seed: int, params: TerrainParams,
                 keep_alive_ticks: int = 10_000):
        self.seed = seed
        self.params = params
        self.keep_alive_ticks = keep_alive_ticks
        self.cache: Dict[Tuple[int, int, int], Chunk] = {}
        self.last_touch: Dict[Tuple[int, int, int], int] = {}

    def touch_area(self, tick: int, coords: Iterable[Tuple[int, int, int]]) -> None:
        for c in coords:
            self.last_touch[c] = tick
            if c not in self.cache:
                self.cache[c] = generate_chunk(self.seed, c, self.params)

    def get(self, tick: int, coord: Tuple[int, int, int]) -> Chunk:
        if coord not in self.cache:
            self.cache[coord] = generate_chunk(self.seed, coord, self.params)
        self.last_touch[coord] = tick
        return self.cache[coord]

    def gc(self, tick: int) -> int:
        cutoff = tick - self.keep_alive_ticks
        to_drop = [c for c, t in self.last_touch.items() if t < cutoff]
        for c in to_drop:
            self.cache.pop(c, None)
            self.last_touch.pop(c, None)
        if to_drop:
            try:
                # Defer-import to avoid circular module load.
                from engine.cognition import evict_cell_grid_cache
                evict_cell_grid_cache(to_drop)
            except Exception:
                pass
        return len(to_drop)


def chunks_around(center: Tuple[int, int, int], radius: int) -> List[Tuple[int, int, int]]:
    cx, cy, cz = center
    return [(cx + dx, cy + dy, cz) for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1)]


def world_to_chunk(x_m: float, y_m: float, z_m: float = 0.0) -> Tuple[int, int, int]:
    return (int(math.floor(x_m / CHUNK_SIDE_M)),
            int(math.floor(y_m / CHUNK_SIDE_M)),
            int(math.floor(z_m / CHUNK_SIDE_M)))


def world_to_cell(x_m: float, y_m: float, chunk_coord: Tuple[int, int, int]) -> Tuple[int, int]:
    cx, cy, _ = chunk_coord
    lx = x_m - cx * CHUNK_SIDE_M
    ly = y_m - cy * CHUNK_SIDE_M
    return (max(0, min(CHUNK_SIZE - 1, int(lx / VOXEL_SIZE_M))),
            max(0, min(CHUNK_SIZE - 1, int(ly / VOXEL_SIZE_M))))


# ---------------------------------------------------------------------------
# Weather / climate
# ---------------------------------------------------------------------------

@dataclass
class Weather:
    temp_c: float
    rain_mm_h: float
    cloud: float
    is_day: bool


def weather_at(tick: int, base_temp_c: float, base_precip_mm: float,
               hemisphere_north: bool = True) -> Weather:
    secs = tick
    day_of_year = (secs // 86400) % 365
    hour = (secs % 86400) / 3600.0
    season_phase = (day_of_year / 365.0) * 2.0 * math.pi
    season = (-math.cos(season_phase)) if hemisphere_north else math.cos(season_phase)
    season_amp = 12.0
    diurnal_phase = ((hour - 14.0) / 24.0) * 2.0 * math.pi
    diurnal = -math.cos(diurnal_phase) * 6.0
    temp_c = base_temp_c + season * season_amp + diurnal
    rain_mm_h = max(base_precip_mm / (365.0 * 24.0), 0.0)
    cloud = min(rain_mm_h * 4.0, 1.0)
    is_day = 6.0 <= hour < 20.0
    return Weather(temp_c=temp_c, rain_mm_h=rain_mm_h, cloud=cloud, is_day=is_day)


# ---------------------------------------------------------------------------
# Ecosystem regeneration: rainfall recharges water, NPP regrows food
# ---------------------------------------------------------------------------

def regenerate_chunk_resources(chunk: Chunk, weather: Weather, dt_s: float) -> None:
    """In-place regeneration. Cheap per-tick update of food and water."""
    daylight = 1.0 if weather.is_day else 0.2
    growth_rate = 0.00002 * daylight * dt_s   # kcal per cell per second
    chunk.food_kcal = np.minimum(chunk.food_kcal + chunk.food_capacity * growth_rate,
                                 chunk.food_capacity)
    if weather.rain_mm_h > 0:
        recharge = weather.rain_mm_h * (dt_s / 3600.0) * 5.0
        land = chunk.biome != Biome.OCEAN
        chunk.water[land] = np.minimum(chunk.water[land] + recharge, 50.0)
