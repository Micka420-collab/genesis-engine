"""Bridge between :class:`engine.world.ChunkStreamer` and :class:`engine.earth_loader.EarthLoader`.

The default ``ChunkStreamer.get()`` always synthesises chunks from a seed via
``generate_chunk``. ``attach_earth_loader(streamer, loader)`` wraps the
streamer in-place so that ``get()`` first tries the EarthLoader; if the
loader returns a usable dict (i.e. real Earth data was reachable), we build
a Chunk from those arrays. Otherwise we fall through to the procedural path
unchanged.

This is non-invasive — no rewrite of ``world.py`` and no subclassing required.
The wrapper is idempotent. Call once per simulation, ideally right after
``Simulation`` is constructed and before ``install(sim)`` runs (so any
chunks pulled during ``bootstrap()`` come from real data when available).
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

import numpy as np

from engine.world import (CHUNK_SIZE, Biome, Chunk, ChunkStreamer,
                          generate_chunk, world_to_cell, world_to_chunk)
from engine.core import prf_bytes
try:
    from engine.earth_loader import EarthLoader
except Exception:  # pragma: no cover - earth_loader is always shipped
    EarthLoader = None  # type: ignore[assignment]


log = logging.getLogger(__name__)


def _chunk_from_earth(streamer: ChunkStreamer, coord: Tuple[int, int, int],
                      data: dict) -> Chunk:
    """Build a Chunk from the EarthLoader output dict.

    Falls back to procedural arrays for any field the loader did not supply.
    """
    height = np.asarray(data["height"], dtype=np.float32)
    biome = np.asarray(data["biome"], dtype=np.uint8)
    stone = np.asarray(data.get("stone"), dtype=np.float32)
    wood = np.asarray(data.get("wood"), dtype=np.float32)
    metal = np.asarray(data.get("metal"), dtype=np.float32)
    water = np.asarray(data.get("water"), dtype=np.float32)
    food_capacity = np.asarray(data.get("food_capacity"), dtype=np.float32)

    # Sanity: every field MUST be the right shape; if not, drop the chunk
    # entirely and let the caller fall back to procedural.
    target_shape = (CHUNK_SIZE, CHUNK_SIZE)
    for name, arr in (("height", height), ("biome", biome), ("stone", stone),
                      ("wood", wood), ("metal", metal), ("water", water),
                      ("food_capacity", food_capacity)):
        if arr.shape != target_shape:
            raise ValueError(
                f"Earth-backed chunk {coord}: field {name} has shape "
                f"{arr.shape}, expected {target_shape}")

    food_kcal = food_capacity.copy()
    cx, cy, cz = coord
    content_root = prf_bytes(streamer.seed,
                             ["earth_chunk_root", str(cx), str(cy), str(cz)],
                             [int(height.sum() * 100.0)], 32)
    return Chunk(coord=coord, height=height, biome=biome, stone=stone,
                 wood=wood, metal=metal, water=water, food_kcal=food_kcal,
                 food_capacity=food_capacity, content_root=content_root)


def attach_earth_loader(streamer: ChunkStreamer, loader,
                        *, strict: bool = False,
                        log_first_hit: bool = True) -> ChunkStreamer:
    """Wrap ``streamer.get`` and ``streamer.touch_area`` in place.

    Parameters
    ----------
    streamer : ChunkStreamer
        The streamer to augment. ``streamer._earth_loader`` is set.
    loader : EarthLoader
        The data source.
    strict : bool
        When True, exceptions inside the loader bubble up. Default False —
        any error is logged and the procedural fallback is used.
    log_first_hit : bool
        Log the first successful Earth-backed chunk fetch (informational).

    Returns
    -------
    The same streamer (for chaining).
    """
    if getattr(streamer, "_earth_loader", None) is loader:
        return streamer

    streamer._earth_loader = loader
    streamer._earth_strict = strict
    streamer._earth_logged_first = not log_first_hit
    streamer._earth_hits = 0
    streamer._earth_misses = 0

    original_get = streamer.get
    original_touch = streamer.touch_area

    def _try_earth(coord):
        try:
            data = loader.chunk_data(coord)
        except Exception as exc:  # pragma: no cover - defensive
            if strict:
                raise
            log.debug("earth_streamer: loader raised for %s: %s", coord, exc)
            streamer._earth_misses += 1
            return None
        if not data:
            streamer._earth_misses += 1
            return None
        try:
            chunk = _chunk_from_earth(streamer, coord, data)
        except Exception as exc:
            if strict:
                raise
            log.warning("earth_streamer: bad data shape for %s (%s); "
                        "falling back to procedural", coord, exc)
            streamer._earth_misses += 1
            return None
        streamer._earth_hits += 1
        if not streamer._earth_logged_first:
            log.info("earth_streamer: first Earth-backed chunk loaded at %s "
                     "(height %.1f-%.1f m)",
                     coord, float(chunk.height.min()), float(chunk.height.max()))
            streamer._earth_logged_first = True
        return chunk

    def wrapped_get(tick, coord):
        if coord in streamer.cache:
            streamer.last_touch[coord] = tick
            return streamer.cache[coord]
        chunk = _try_earth(coord)
        if chunk is None:
            return original_get(tick, coord)
        streamer.cache[coord] = chunk
        streamer.last_touch[coord] = tick
        return chunk

    def wrapped_touch(tick, coords):
        new_coords = []
        for c in coords:
            streamer.last_touch[c] = tick
            if c in streamer.cache:
                continue
            chunk = _try_earth(c)
            if chunk is not None:
                streamer.cache[c] = chunk
            else:
                new_coords.append(c)
        if new_coords:
            original_touch(tick, new_coords)

    streamer.get = wrapped_get
    streamer.touch_area = wrapped_touch
    return streamer


def attach_land_filter(sim) -> None:
    """Patch ``sim._pick_land_position`` to reject ocean / lake biome cells.

    The default filter in ``engine.sim.Simulation._pick_land_position`` only
    rejects cells with ``height <= 1.0`` — fine for procedural worlds where
    water is at sea level, but on Earth lakes sit at hundreds of metres
    elevation. The Léman surface (~372 m) passes the height check, so 20
    founders end up bobbing in the water with no wood and no food.

    This wrapper adds a biome check: cells whose ``chunk.biome`` is
    ``Biome.OCEAN`` are rejected even if their height clears the threshold.
    Idempotent.
    """
    if getattr(sim, "_land_filter_attached", False):
        return
    sim._land_filter_attached = True

    original = sim._pick_land_position

    def patched(rng, bounds_km, max_tries: int):
        bx_m = bounds_km[0] * 1000.0 * 0.5
        by_m = bounds_km[1] * 1000.0 * 0.5
        best = None
        best_score = -1.0
        ocean_id = int(Biome.OCEAN)
        for _ in range(max_tries):
            x = float(rng.uniform(-bx_m, bx_m))
            y = float(rng.uniform(-by_m, by_m))
            coord = world_to_chunk(x, y)
            chunk = sim.streamer.get(sim.tick, coord)
            cx, cy = world_to_cell(x, y, coord)
            if int(chunk.biome[cy, cx]) == ocean_id:
                continue
            if float(chunk.height[cy, cx]) <= 1.0:
                continue
            if float(chunk.food_capacity[cy, cx]) < 50.0:
                continue
            w_avail = float(chunk.water[
                max(0, cy - 3):cy + 4, max(0, cx - 3):cx + 4
            ].max(initial=0.0))
            f_avail = float(chunk.food_capacity[
                max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3
            ].mean())
            score = (w_avail / 100.0) + (f_avail / 100.0)
            if w_avail > 5.0 and score > best_score:
                best_score = score
                best = (x, y)
        if best is None:
            # Last-resort: fall back to the original filter (may still pick
            # water). Better than spawning at origin.
            return original(rng, bounds_km, max_tries)
        return best

    sim._pick_land_position = patched


__all__ = ["attach_earth_loader", "attach_land_filter"]
