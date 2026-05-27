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


def classify_biome_array(temp_c: np.ndarray, precip_mm: np.ndarray,
                          elev_m: np.ndarray) -> np.ndarray:
    """Vectorised Whittaker classifier — same logic as ``classify_biome``.

    Replaces a Python loop that called ``classify_biome`` 4096 times per
    chunk during procedural generation. Returns a ``uint8`` array of Biome
    values with the same shape as the inputs.
    """
    biome = np.full(elev_m.shape, int(Biome.OCEAN), dtype=np.uint8)
    # Default by elevation (land vs ocean), then temperature, then precip.
    land = elev_m >= 0.0
    # Ice / tundra
    ice = land & (temp_c < -10.0)
    tundra = land & (temp_c >= -10.0) & (temp_c < 0.0)
    # Cold band [0, 10) — split by precip
    cold = land & (temp_c >= 0.0) & (temp_c < 10.0)
    cold_desert_cold = cold & (precip_mm < 300.0)
    boreal = cold & (precip_mm >= 300.0)
    # Temperate band [10, 20) — split by precip
    temperate = land & (temp_c >= 10.0) & (temp_c < 20.0)
    cold_desert_temp = temperate & (precip_mm < 250.0)
    grassland = temperate & (precip_mm >= 250.0) & (precip_mm < 750.0)
    temperate_forest = temperate & (precip_mm >= 750.0) & (precip_mm < 1500.0)
    temperate_rain = temperate & (precip_mm >= 1500.0)
    # Hot band [20, ∞)
    hot = land & (temp_c >= 20.0)
    hot_desert = hot & (precip_mm < 250.0)
    savanna = hot & (precip_mm >= 250.0) & (precip_mm < 750.0)
    tropical_dry = hot & (precip_mm >= 750.0) & (precip_mm < 1500.0)
    tropical_rain = hot & (precip_mm >= 1500.0)
    # Paint in priority order (later masks overwrite earlier).
    biome[ice] = int(Biome.ICE)
    biome[tundra] = int(Biome.TUNDRA)
    biome[cold_desert_cold] = int(Biome.COLD_DESERT)
    biome[boreal] = int(Biome.BOREAL_FOREST)
    biome[cold_desert_temp] = int(Biome.COLD_DESERT)
    biome[grassland] = int(Biome.GRASSLAND)
    biome[temperate_forest] = int(Biome.TEMPERATE_FOREST)
    biome[temperate_rain] = int(Biome.TEMPERATE_RAINFOREST)
    biome[hot_desert] = int(Biome.HOT_DESERT)
    biome[savanna] = int(Biome.SAVANNA)
    biome[tropical_dry] = int(Biome.TROPICAL_DRY_FOREST)
    biome[tropical_rain] = int(Biome.TROPICAL_RAINFOREST)
    return biome


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


def sample_terrain_with_genesis(seed: int, params: TerrainParams,
                                  x_m: np.ndarray, y_m: np.ndarray,
                                  anchor) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample chunk terrain anchored to a continental :class:`GenesisAnchor`.

    The chunk's elevation = ``blend * macro_elev + (1-blend) * pure_FBM``
    plus a micro FBM residual ``micro_amp_m`` (so that even when the
    macro is the truth, the chunk gets unique 32 m-scale detail).

    Temperature is the macro value plus a small jitter, with the
    adiabatic lapse rate applied to the *micro* elevation residual only
    (the macro already encodes its own lapse). Precipitation is the
    macro value plus a small jitter (no negative).

    Imported lazily to avoid the world <-> world_genesis circular load:
    world.py is a strict prerequisite of world_genesis.py.
    """
    from engine.world_genesis import sample_macro_grid

    ox_km, oy_km = anchor.sim_origin_macro_km
    x_km = x_m.astype(np.float32) * 0.001 + np.float32(ox_km)
    y_km = y_m.astype(np.float32) * 0.001 + np.float32(oy_km)
    macro_elev, macro_temp, macro_precip = sample_macro_grid(
        anchor.world, x_km, y_km)

    # Micro residual via the existing FBM noise — same lattice as before
    # so determinism contract is preserved.
    x = x_m / params.scale_m
    y = y_m / params.scale_m
    micro_e = fbm_2d(seed, "genesis_micro_elev", x, y, params.elev_octaves)
    micro_t = fbm_2d(seed, "genesis_micro_t", x * 0.3, y * 0.3,
                     params.temp_octaves)
    micro_p = fbm_2d(seed, "genesis_micro_p", x * 0.5, y * 0.5,
                     params.precip_octaves)

    # Optional fallback to pure-FBM blend (useful for transitions or A/B).
    blend = float(np.clip(anchor.blend, 0.0, 1.0))
    if blend < 1.0:
        fbm_full_elev = params.sea_level_m + micro_e * params.max_elev_m
        macro_elev = (macro_elev * blend +
                      fbm_full_elev * (1.0 - blend)).astype(np.float32)

    micro_offset_m = (micro_e * anchor.micro_amp_m).astype(np.float32)
    elev = (macro_elev + micro_offset_m).astype(np.float32)
    # Marginal lapse from the elevation that the macro did NOT see.
    macro_land = np.maximum(macro_elev, 0.0)
    blended_land = np.maximum(elev, 0.0)
    micro_lapse = -(blended_land - macro_land) / 1000.0 * 6.5
    temp = (macro_temp + micro_lapse +
            micro_t * anchor.micro_amp_temp_c).astype(np.float32)
    precip = np.maximum(
        macro_precip + micro_p * anchor.micro_amp_precip_mm,
        0.0).astype(np.float32)
    return elev, temp, precip


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

    def __post_init__(self):
        # Per-chunk read caches consumed by engine.cognition._scan_chunk
        # (optim #3c, sprint 2026-05-14 session 12). Any code path that
        # mutates ``water``, ``food_kcal``, ``wood``, ``stone`` or
        # ``height`` MUST call ``invalidate_resource_masks(chunk)`` so
        # the cached bool masks stay consistent and determinism holds.
        self._mask_cache = None  # ``(water_mask, food_mask, shelter_mask)`` or None
        # Wave 47: cached scalar means for immutable arrays (height, food_capacity).
        # These never change after generation, so computing mean once saves
        # 2 × np.mean per chunk per tick in regenerate_chunk_resources.
        self._mean_height: float = float(np.mean(self.height))
        self._mean_food_cap: float = float(np.mean(self.food_capacity))


def invalidate_resource_masks(chunk: "Chunk") -> None:
    """Drop the chunk's cached resource bool masks.

    Call from any site that mutates the chunk's ``water``, ``food_kcal``,
    ``wood``, ``stone``, or ``height`` arrays. The cached masks are
    consumed by ``engine.cognition._scan_chunk`` and reused across all
    agents perceiving the same chunk within a tick; mid-tick writes must
    bust the cache to preserve bit-perfect determinism.
    """
    chunk._mask_cache = None


def _compute_resources_py(seed: int, cx: int, cy: int, cz: int,
                          elev, biome):
    """Compute resources in pure Python (prf_rng path).

    Returns (stone, wood, metal, water, food_kcal, food_capacity) arrays.
    This is the pre-Wave-43 logic, kept as fallback.
    """
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
    water = np.zeros_like(elev)
    water[(biome == Biome.OCEAN) | (elev < 1.5)] = 1000.0
    spring_prob = np.zeros_like(elev)
    for wet in (Biome.TEMPERATE_FOREST, Biome.TEMPERATE_RAINFOREST,
                Biome.TROPICAL_RAINFOREST, Biome.BOREAL_FOREST, Biome.GRASSLAND,
                Biome.SAVANNA, Biome.TROPICAL_DRY_FOREST, Biome.TUNDRA):
        spring_prob[biome == wet] = 0.02
    spring_mask = noise_a.reshape(elev.shape) < spring_prob
    water[spring_mask] = np.maximum(water[spring_mask], 200.0)
    npp = np.zeros_like(elev)
    for b_id in range(12):
        mask = (biome == b_id)
        if mask.any():
            npp[mask] = _BIOME_NPP[Biome(b_id)]
    food_capacity = npp * 500.0
    food_kcal = food_capacity.copy()
    return (stone.astype(np.float32), wood.astype(np.float32),
            metal.astype(np.float32), water.astype(np.float32),
            food_kcal.astype(np.float32), food_capacity.astype(np.float32))


def _chunk_from_rust_terrain(seed: int, coord: Tuple[int, int, int],
                             terrain_dict) -> Chunk:
    """Build a Chunk from pre-computed Rust terrain + resources (batch path).

    Wave 43: resources from Rust when available.
    Wave 44: biome + content_root from Rust — zero Python computation,
    only dataclass construction.
    """
    cx, cy, cz = coord
    d = terrain_dict
    elev = np.asarray(d["elev"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
    temp = np.asarray(d["temp"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
    precip = np.asarray(d["precip"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)

    # Wave 44: use Rust biome when available.
    if "biome" in d:
        biome = np.asarray(d["biome"], dtype=np.uint8).reshape(CHUNK_SIZE, CHUNK_SIZE)
    else:
        biome = classify_biome_array(temp, precip, elev)

    # Wave 43: use Rust-computed resources if available.
    if "stone" in d:
        stone = np.asarray(d["stone"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        wood = np.asarray(d["wood"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        metal = np.asarray(d["metal"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        water = np.asarray(d["water"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        food_kcal = np.asarray(d["food_kcal"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        food_capacity = np.asarray(d["food_capacity"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
    else:
        stone, wood, metal, water, food_kcal, food_capacity = _compute_resources_py(
            seed, cx, cy, cz, elev, biome)

    # Wave 44: use Rust content_root when available.
    # ⚠ Batch path computes content_root with cz=0 in Rust.
    # If the actual cz != 0, we must recompute in Python to stay correct.
    if "content_root" in d and cz == 0:
        content_root = bytes(d["content_root"])
    else:
        content_root = prf_bytes(seed, ["chunk_root", str(cx), str(cy), str(cz)], [], 32)

    return Chunk(coord=(cx, cy, cz),
                 height=elev, biome=biome,
                 stone=stone, wood=wood,
                 metal=metal, water=water,
                 food_kcal=food_kcal,
                 food_capacity=food_capacity,
                 content_root=content_root)


def generate_chunk(seed: int, coord: Tuple[int, int, int],
                    params: TerrainParams, *, genesis=None,
                    rust_world=None) -> Chunk:
    """Generate a single chunk.

    Priority order for heightmap/biome sampling:
    1. ``rust_world`` (Phase 2): native Rust backend via ``genesis_world.PyWorld``.
       Falls back silently to Python if the call fails.
    2. ``genesis`` anchor (Wave 16+): tectonics + erosion macro field.
    3. Pure-FBM Python (legacy, pre-Wave-16 compatible).

    Wave 43: resources (stone/wood/metal/water/food) from Rust when available.
    Wave 44: biome + content_root from Rust — full Chunk data from Rust,
    only dataclass construction remains in Python.
    """
    cx, cy, cz = coord
    ox = cx * CHUNK_SIDE_M
    oy = cy * CHUNK_SIDE_M

    _rust_ok = False
    _rust_dict = None  # Wave 43+: full Rust-computed dict
    # Phase 3e: Rust backend handles genesis-anchored terrain too when
    # macro grid bytes were loaded into PyWorld at construction time.
    # Check: rust_world present AND (no genesis OR Rust has macro grid).
    _try_rust = (rust_world is not None and
                 (genesis is None or getattr(rust_world, "has_genesis", lambda: False)()))
    if _try_rust:
        try:
            # Wave 44: pass cz so Rust can compute content_root.
            d = rust_world.sample_terrain_chunk(cx, cy, cz)
            # Phase 3b: Rust returns numpy arrays directly (zero-copy).
            # np.asarray avoids copy if already float32; .reshape is a view.
            elev = np.asarray(d["elev"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
            temp = np.asarray(d["temp"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
            precip = np.asarray(d["precip"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
            _rust_ok = True
            _rust_dict = d
        except Exception:
            # Log the first failure once, then stay quiet.
            if not getattr(generate_chunk, "_rust_warned", False):
                import warnings
                warnings.warn(
                    "Rust backend sample_terrain_chunk failed; falling back to Python. "
                    "This warning appears only once.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                generate_chunk._rust_warned = True

    if not _rust_ok:
        xs = (ox + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
        ys = (oy + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
        XX, YY = np.meshgrid(xs, ys, indexing="xy")
        if genesis is None:
            elev, temp, precip = sample_terrain(seed, params, XX, YY)
        else:
            elev, temp, precip = sample_terrain_with_genesis(
                seed, params, XX, YY, genesis)

    # Wave 44: use Rust biome when available; else classify in Python.
    if _rust_dict is not None and "biome" in _rust_dict:
        biome = np.asarray(_rust_dict["biome"], dtype=np.int32).reshape(CHUNK_SIZE, CHUNK_SIZE)
    else:
        biome = classify_biome_array(temp, precip, elev)

    # Wave 43: use Rust-computed resources when available.
    if _rust_dict is not None and "stone" in _rust_dict:
        stone = np.asarray(_rust_dict["stone"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        wood = np.asarray(_rust_dict["wood"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        metal = np.asarray(_rust_dict["metal"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        water = np.asarray(_rust_dict["water"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        food_kcal = np.asarray(_rust_dict["food_kcal"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        food_capacity = np.asarray(_rust_dict["food_capacity"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
    else:
        stone, wood, metal, water, food_kcal, food_capacity = _compute_resources_py(
            seed, cx, cy, cz, elev, biome)

    # Wave 44: use Rust content_root when available.
    if _rust_dict is not None and "content_root" in _rust_dict:
        content_root = bytes(_rust_dict["content_root"])
    else:
        content_root = prf_bytes(seed, ["chunk_root", str(cx), str(cy), str(cz)], [], 32)

    return Chunk(coord=(cx, cy, cz),
                 height=elev, biome=biome,
                 stone=stone, wood=wood,
                 metal=metal, water=water,
                 food_kcal=food_kcal,
                 food_capacity=food_capacity,
                 content_root=content_root)


# ---------------------------------------------------------------------------
# Chunk streamer (LRU GC, on-demand generation)
# ---------------------------------------------------------------------------

class ChunkStreamer:
    def __init__(self, seed: int, params: TerrainParams,
                 keep_alive_ticks: int = 10_000,
                 genesis=None,
                 use_rust_backend: bool = True):
        self.seed = seed
        self.params = params
        self.keep_alive_ticks = keep_alive_ticks
        self.cache: Dict[Tuple[int, int, int], Chunk] = {}
        self.last_touch: Dict[Tuple[int, int, int], int] = {}
        self.genesis = genesis
        # Wave 45: streaming statistics.
        self._stats_hits: int = 0
        self._stats_misses: int = 0
        self._stats_gen_ms: float = 0.0   # cumulative generation time
        self._stats_gen_count: int = 0     # chunks generated (not cached)
        self._stats_batch_calls: int = 0
        self._stats_gc_evicted: int = 0
        # Phase 2 — opt-in Rust backend for heightmap/biome sampling.
        # When True and genesis_world native wheel is installed, terrain
        # sampling is delegated to ge-py; resources remain Python-side.
        # When the wheel is absent, _rust_world stays None and we silently
        # fall back to the Python path (no MockPyWorld created).
        self.use_rust_backend = use_rust_backend
        self._rust_world = None
        if use_rust_backend:
            try:
                from engine.rust_bridge import create_py_world
                # Phase 3e: pass genesis info so Rust can do genesis-blend.
                genesis_world = getattr(genesis, "world", None) if genesis else None
                self._rust_world = create_py_world(
                    seed=seed,
                    genesis_world=genesis_world,
                    genesis_anchor=genesis,
                    synthetic_only=True,
                )
                # Verify we got a native PyWorld, not a MockPyWorld.
                if not hasattr(self._rust_world, "cached_chunk_count"):
                    self._rust_world = None
            except Exception:
                self._rust_world = None

    def set_genesis(self, genesis) -> None:
        """Attach (or clear) a :class:`GenesisAnchor` for chunk generation.

        Mutates the streamer in place. Existing cached chunks are *not*
        regenerated — call :meth:`clear_cache` if you want the new
        anchor to apply retroactively.

        Phase 3e: rebuilds the Rust world with the new macro grid so the
        Rust backend can handle genesis-anchored terrain.
        """
        self.genesis = genesis
        # Rebuild Rust world with new genesis info.
        if self.use_rust_backend:
            try:
                from engine.rust_bridge import create_py_world
                genesis_world = getattr(genesis, "world", None) if genesis else None
                self._rust_world = create_py_world(
                    seed=self.seed,
                    genesis_world=genesis_world,
                    genesis_anchor=genesis,
                    synthetic_only=True,
                )
                if not hasattr(self._rust_world, "cached_chunk_count"):
                    self._rust_world = None
            except Exception:
                self._rust_world = None

    def clear_cache(self) -> None:
        """Drop all cached chunks and their last-touch records."""
        self.cache.clear()
        self.last_touch.clear()

    def _rust_world_for_gen(self):
        """Return the Rust world handle when backend is active.

        Phase 3e: Rust now handles genesis-anchored terrain too when the
        macro grid was loaded at construction. Falls back to Python only
        when Rust has no macro grid but genesis is requested.
        """
        if not self.use_rust_backend or self._rust_world is None:
            return None
        # If genesis is set but Rust doesn't have the macro grid,
        # fall back to the Python genesis path.
        if self.genesis is not None:
            if not getattr(self._rust_world, "has_genesis", lambda: False)():
                return None
        return self._rust_world

    def touch_area(self, tick: int, coords: Iterable[Tuple[int, int, int]],
                   *, max_new: int = 0) -> int:
        """Load/touch chunks, generating any that are missing.

        Wave 45 adaptive streaming:
        - *max_new*: maximum number of NEW chunks to generate in this call.
          0 means unlimited (generate all missing chunks).  When a budget
          is set, already-cached chunks are always served; only new
          generation is capped.  Coords should be pre-sorted by priority
          (e.g. via ``chunks_around_sorted``) so the most important
          chunks are generated first.
        - Returns the number of chunks that were newly generated.

        Wave 51: fast path when all chunks are already cached (common
        steady-state case). Avoids list comprehension + batch overhead.
        """
        import time as _time

        coords_list = list(coords)

        # Wave 51: fast path — all cached (common after warmup).
        _cache = self.cache
        _lt = self.last_touch
        all_cached = True
        for c in coords_list:
            if c not in _cache:
                all_cached = False
                break
        if all_cached:
            self._stats_hits += len(coords_list)
            for c in coords_list:
                _lt[c] = tick
            return 0

        rw = self._rust_world_for_gen()

        # Separate cached from uncached.
        cached_coords = [c for c in coords_list if c in _cache]
        uncached = [c for c in coords_list if c not in _cache]

        # Wave 45: budget-limit new generation.
        if max_new > 0 and len(uncached) > max_new:
            # Only generate the first max_new (closest if pre-sorted).
            deferred = set(map(tuple, uncached[max_new:]))
            uncached = uncached[:max_new]
        else:
            deferred = set()

        # Stats: cache hits for already-cached coords.
        self._stats_hits += len(cached_coords)
        self._stats_misses += len(uncached)

        # Phase 3g: batch parallel via Rust when available.
        batch_terrain = {}
        t0 = _time.perf_counter()

        if uncached and rw is not None and hasattr(rw, "sample_terrain_batch"):
            try:
                batch_coords_2d = [(c[0], c[1]) for c in uncached]
                batch_results = rw.sample_terrain_batch(batch_coords_2d)
                for c, d in zip(uncached, batch_results):
                    batch_terrain[c] = d
                self._stats_batch_calls += 1
            except Exception:
                pass  # Fallback to sequential below

        generated = 0
        for c in coords_list:
            if c in deferred:
                continue  # Skip deferred chunks (over budget).
            self.last_touch[c] = tick
            if c not in self.cache:
                if c in batch_terrain:
                    self.cache[c] = _chunk_from_rust_terrain(
                        self.seed, c, batch_terrain[c])
                else:
                    self.cache[c] = generate_chunk(
                        self.seed, c, self.params,
                        genesis=self.genesis, rust_world=rw)
                generated += 1

        gen_ms = (_time.perf_counter() - t0) * 1000.0
        self._stats_gen_ms += gen_ms
        self._stats_gen_count += generated
        return generated

    def get(self, tick: int, coord: Tuple[int, int, int]) -> Chunk:
        if coord not in self.cache:
            rw = self._rust_world_for_gen()
            self.cache[coord] = generate_chunk(self.seed, coord, self.params,
                                                genesis=self.genesis,
                                                rust_world=rw)
            self._stats_misses += 1
            self._stats_gen_count += 1
        else:
            self._stats_hits += 1
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
            self._stats_gc_evicted += len(to_drop)
        return len(to_drop)

    def stats(self) -> Dict[str, object]:
        """Wave 45: streaming statistics for profiling / adaptive tuning.

        Returns a dict with cache_size, hits, misses, hit_rate,
        generated, avg_gen_ms, batch_calls, gc_evicted.
        """
        total = self._stats_hits + self._stats_misses
        hit_rate = self._stats_hits / total if total > 0 else 0.0
        avg_ms = (self._stats_gen_ms / self._stats_gen_count
                  if self._stats_gen_count > 0 else 0.0)
        return {
            "cache_size":   len(self.cache),
            "hits":         self._stats_hits,
            "misses":       self._stats_misses,
            "hit_rate":     round(hit_rate, 4),
            "generated":    self._stats_gen_count,
            "avg_gen_ms":   round(avg_ms, 3),
            "total_gen_ms": round(self._stats_gen_ms, 1),
            "batch_calls":  self._stats_batch_calls,
            "gc_evicted":   self._stats_gc_evicted,
        }

    def reset_stats(self) -> None:
        """Reset streaming statistics counters."""
        self._stats_hits = 0
        self._stats_misses = 0
        self._stats_gen_ms = 0.0
        self._stats_gen_count = 0
        self._stats_batch_calls = 0
        self._stats_gc_evicted = 0


def chunks_around(center: Tuple[int, int, int], radius: int) -> List[Tuple[int, int, int]]:
    cx, cy, cz = center
    return [(cx + dx, cy + dy, cz) for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1)]


_SORTED_OFFSETS_CACHE: Dict[int, List[Tuple[int, int]]] = {}


def _get_sorted_offsets(radius: int) -> List[Tuple[int, int]]:
    """Return pre-sorted (dx, dy) offsets for the given radius.

    Cached at module level to avoid per-call sort overhead.
    """
    cached = _SORTED_OFFSETS_CACHE.get(radius)
    if cached is not None:
        return cached
    offsets = [(dx, dy)
               for dy in range(-radius, radius + 1)
               for dx in range(-radius, radius + 1)]
    offsets.sort(key=lambda c: (max(abs(c[0]), abs(c[1])),
                                abs(c[0]) + abs(c[1])))
    _SORTED_OFFSETS_CACHE[radius] = offsets
    return offsets


def chunks_around_sorted(center: Tuple[int, int, int], radius: int) -> List[Tuple[int, int, int]]:
    """Return chunks within *radius* of *center*, sorted closest-first.

    Wave 45/51: adaptive streaming — agents perceive nearby chunks before
    far ones.  Sorting uses Chebyshev distance (max(|dx|, |dy|)) as
    primary key and Manhattan distance as tiebreaker, producing a
    roughly spiral outward expansion from the center.

    Wave 51: offsets are cached at module level to avoid per-call sort.
    """
    cx, cy, cz = center
    return [(cx + dx, cy + dy, cz) for dx, dy in _get_sorted_offsets(radius)]


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

    # Walrus-free fallback
    day_of_year = (secs // 86400) % 365
    hour = (secs % 86400) / 3600.0
    season_phase = (day_of_year / 365.0) * 2.0 * math.pi
    season = (-math.cos(season_phase)) if hemisphere_north else math.cos(season_phase)
    season_amp = 12.0
    diurnal_phase = ((hour - 14.0) / 24.0) * 2.0 * math.pi
    diurnal = -math.cos(diurnal_phase) * 6.0
    temp_c = base_temp_c + season * season_amp + diurnal
    rain_mm_h = max(0.0, base_precip_mm / 24.0)
    cloud = 0.5 + 0.5 * math.sin(season_phase * 2.0)
    is_day = (6.0 <= hour <= 20.0)
    return Weather(temp_c=float(temp_c),
                   rain_mm_h=float(rain_mm_h),
                   cloud=float(cloud),
                   is_day=bool(is_day))



# --- P0 fix: missing helper referenced by sim.py.
# Minimal regenerator: tops up `food_kcal` toward `food_capacity` and
# replenishes `water` slowly when there is rain. CO2-neutral.
def regenerate_chunk_resources(chunk, weather, dt_s: float = 1.0) -> None:
    """Tick-level regeneration of chunk resources.

    Args:
        chunk: a Chunk object holding ``food_kcal``, ``food_capacity``, ``water``.
        weather: a Weather record (provides ``rain_mm_h``).
        dt_s: simulated seconds elapsed since last call.

    Wave 47: optimised — in-place ``+=`` avoids temporaries, ``np.float32``
    scalars keep operations in float32 (no f64 promotion), ``np.maximum``
    with ``out=`` avoids allocation. ~2× faster than Wave 44 version.
    """
    try:
        # Food regrowth (in-place, no temporaries).
        factor = np.float32(dt_s / (3.0 * 86400.0))
        # food_kcal += (capacity - current) * factor
        chunk.food_kcal += (chunk.food_capacity - chunk.food_kcal) * factor
        np.maximum(chunk.food_kcal, 0.0, out=chunk.food_kcal)

        # Water recharge from rain (in-place, skip if no rain).
        recharge = max(0.0, float(weather.rain_mm_h)) * dt_s / 3600.0
        if recharge > 0.0:
            chunk.water += np.float32(recharge)
    except Exception:
        pass
    invalidate_resource_masks(chunk)


def regenerate_chunks_batch(chunks: list, dt_s: float,
                            rain_per_chunk: np.ndarray) -> None:
    """Wave 49: batch regeneration — all chunks in 3 numpy ops.

    Instead of calling ``regenerate_chunk_resources`` per chunk (5 numpy
    calls × N chunks = 545 calls for 109 chunks), this function stacks
    all arrays, does 3 vectorised ops on the ``(N, 64, 64)`` block, then
    writes back. Reduces numpy call overhead from ~3.9ms to ~1.5ms.

    Args:
        chunks: list of Chunk objects to regenerate.
        dt_s: simulated seconds elapsed.
        rain_per_chunk: 1-D float32 array of rain_mm_h per chunk (same order).
    """
    n = len(chunks)
    if n == 0:
        return

    shape = (n, CHUNK_SIZE, CHUNK_SIZE)
    factor = np.float32(dt_s / (3.0 * 86400.0))
    water_factor = np.float32(dt_s / 3600.0)

    # --- Gather ---
    food_stack = np.empty(shape, dtype=np.float32)
    cap_stack = np.empty(shape, dtype=np.float32)
    water_stack = np.empty(shape, dtype=np.float32)
    for i, c in enumerate(chunks):
        food_stack[i] = c.food_kcal
        cap_stack[i] = c.food_capacity
        water_stack[i] = c.water

    # --- Batch compute (3 numpy ops on full stack) ---
    food_stack += (cap_stack - food_stack) * factor
    np.maximum(food_stack, 0.0, out=food_stack)

    # Water recharge: per-chunk rain values broadcast over (64, 64).
    recharges = np.maximum(rain_per_chunk, 0.0) * water_factor  # (N,)
    # Only add where recharge > 0 (sparse broadcast).
    mask = recharges > 0.0
    if mask.any():
        water_stack[mask] += recharges[mask, None, None]

    # --- Scatter + invalidate ---
    for i, c in enumerate(chunks):
        c.food_kcal[:] = food_stack[i]
        c.water[:] = water_stack[i]
        invalidate_resource_masks(c)
