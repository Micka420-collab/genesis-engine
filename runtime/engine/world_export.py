"""Export Genesis worlds to standard interchange formats.

Supported targets:
  * **GeoTIFF** (height / biome / slope / wood / water) — opens in QGIS,
    ArcGIS, Blender GIS, Mapbox, any GDAL consumer.
  * **PNG cartographic** — quick visual map (biome palette + elevation
    shading + lake/ocean overlay + walkability mask).
  * **JSON snapshot** — full state dump, suitable as a checkpoint.
  * **OBJ heightfield mesh** — quick 3D import for Blender / Unity / Three.js.

All exports are **deterministic** for a given World state and write to
absolute paths supplied by the caller.
"""
from __future__ import annotations

import json
import math
import os
import struct
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from engine.world import (Biome, CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M,
                          world_to_chunk)

try:
    import rasterio
    from rasterio.transform import from_bounds as _rio_from_bounds
    _HAS_RASTERIO = True
except Exception:  # pragma: no cover
    rasterio = None
    _HAS_RASTERIO = False


# ---------------------------------------------------------------------------
# Layer extraction
# ---------------------------------------------------------------------------

_VALID_LAYERS = (
    "height", "biome", "water", "wood", "stone", "metal", "food_capacity",
    "slope_deg", "veg_state", "ravine_depth", "walkability", "is_lake",
)


def _gather_layer(world, layer: str, chunk_coords: Iterable[Tuple[int, int, int]]
                  ) -> Tuple[np.ndarray, Tuple[float, float, float, float]]:
    """Stitch a layer across the requested chunks into a single 2D numpy
    array, plus the metric bbox (xmin, ymin, xmax, ymax) the array covers.
    """
    coords = list(chunk_coords)
    if not coords:
        raise ValueError("no chunks to gather")
    cxs = [c[0] for c in coords]
    cys = [c[1] for c in coords]
    cx_min, cx_max = min(cxs), max(cxs)
    cy_min, cy_max = min(cys), max(cys)
    rows = (cy_max - cy_min + 1) * CHUNK_SIZE
    cols = (cx_max - cx_min + 1) * CHUNK_SIZE
    sim = world.sim

    # Decide dtype + source per layer
    use_lift = layer in ("slope_deg", "veg_state", "ravine_depth",
                         "walkability", "is_lake")
    if layer in ("biome", "veg_state"):
        out = np.zeros((rows, cols), dtype=np.uint8)
    elif layer == "is_lake":
        out = np.zeros((rows, cols), dtype=np.uint8)  # 0/1
    else:
        out = np.zeros((rows, cols), dtype=np.float32)

    lift_fields = getattr(sim, "_lift_fields", {}) or {}
    for c in coords:
        cx, cy, _ = c
        chunk = sim.streamer.cache.get(c)
        if chunk is None:
            continue
        # Row in stitched array (Y growing downward to match GIS convention).
        r0 = (cy_max - cy) * CHUNK_SIZE
        col0 = (cx - cx_min) * CHUNK_SIZE
        if use_lift:
            field = lift_fields.get(c)
            if field is None:
                continue
            arr = getattr(field, layer, None)
            if arr is None:
                continue
            out[r0:r0 + CHUNK_SIZE, col0:col0 + CHUNK_SIZE] = (
                arr.astype(out.dtype) if layer != "is_lake"
                else arr.astype(np.uint8))
        else:
            arr = getattr(chunk, layer, None)
            if arr is None:
                continue
            out[r0:r0 + CHUNK_SIZE, col0:col0 + CHUNK_SIZE] = arr.astype(out.dtype)

    xmin = cx_min * CHUNK_SIDE_M
    ymin = cy_min * CHUNK_SIDE_M
    xmax = (cx_max + 1) * CHUNK_SIDE_M
    ymax = (cy_max + 1) * CHUNK_SIDE_M
    return out, (xmin, ymin, xmax, ymax)


def _enumerate_chunks(world) -> List[Tuple[int, int, int]]:
    return list(world.sim.streamer.cache.keys())


# ---------------------------------------------------------------------------
# GeoTIFF export
# ---------------------------------------------------------------------------

def export_geotiff(world, layer: str, out_path: str,
                   chunks: Optional[Iterable[Tuple[int, int, int]]] = None
                   ) -> str:
    """Write ``layer`` as a GeoTIFF in EPSG:4326 (degrees lat/lon).

    Requires rasterio + pyproj. Computes the lat/lon bbox from the world's
    EarthLoader if present; otherwise falls back to a flat-earth projection
    centred on the simulation origin. Returns ``out_path``.
    """
    if not _HAS_RASTERIO:
        raise RuntimeError("rasterio not available — install with `pip install rasterio`")
    if layer not in _VALID_LAYERS:
        raise ValueError(f"unknown layer {layer!r}; valid: {_VALID_LAYERS}")
    if chunks is None:
        chunks = _enumerate_chunks(world)
    arr, (xmin, ymin, xmax, ymax) = _gather_layer(world, layer, chunks)

    # Convert metric bbox to lat/lon via the loader.
    loader = getattr(world, "loader", None)
    if loader is not None and getattr(loader, "_transformer_xy_to_ll", None) is not None:
        lon_min, lat_min = loader._transformer_xy_to_ll.transform(xmin, ymin)
        lon_max, lat_max = loader._transformer_xy_to_ll.transform(xmax, ymax)
    else:
        # Flat-earth fallback (degrees per metre at the equator-ish).
        lat0 = getattr(loader, "origin_lat", 0.0) if loader is not None else 0.0
        lon0 = getattr(loader, "origin_lon", 0.0) if loader is not None else 0.0
        lat_min = lat0 + (ymin / 111_320.0)
        lat_max = lat0 + (ymax / 111_320.0)
        lon_scale = 111_320.0 * max(math.cos(math.radians(lat0)), 1e-6)
        lon_min = lon0 + (xmin / lon_scale)
        lon_max = lon0 + (xmax / lon_scale)

    transform = _rio_from_bounds(lon_min, lat_min, lon_max, lat_max,
                                 arr.shape[1], arr.shape[0])
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": arr.shape[0],
        "width": arr.shape[1],
        "count": 1,
        "dtype": arr.dtype.name,
        "crs": "EPSG:4326",
        "transform": transform,
        "compress": "deflate",
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(arr, 1)
        dst.update_tags(genesis_engine_layer=layer,
                        genesis_engine_world=getattr(world, "name", "world"),
                        genesis_engine_tick=str(getattr(world, "tick", 0)))
    return out_path


# ---------------------------------------------------------------------------
# PNG cartographic map
# ---------------------------------------------------------------------------

_BIOME_PALETTE = {
    0: (0, 80, 180),       # OCEAN deep
    1: (235, 250, 255),    # ICE
    2: (200, 215, 200),    # TUNDRA
    3: (60, 100, 70),      # BOREAL_FOREST
    4: (80, 145, 70),      # TEMPERATE_FOREST
    5: (50, 110, 60),      # TEMPERATE_RAINFOREST
    6: (200, 200, 100),    # GRASSLAND
    7: (240, 215, 145),    # HOT_DESERT
    8: (210, 200, 175),    # COLD_DESERT
    9: (220, 195, 110),    # SAVANNA
    10: (140, 175, 90),    # TROPICAL_DRY_FOREST
    11: (40, 140, 80),     # TROPICAL_RAINFOREST
}


def _encode_png(img: np.ndarray) -> bytes:
    """Minimal PNG encoder (RGBA, 8-bit per channel)."""
    import zlib as _zlib
    h, w = img.shape[:2]
    rows = np.zeros((h, w * 4 + 1), dtype=np.uint8)
    rows[:, 1:] = img.reshape(h, w * 4)
    raw = rows.tobytes()

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", _zlib.crc32(tag + data) & 0xFFFFFFFF))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (sig + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", _zlib.compress(raw, 6))
            + _chunk(b"IEND", b""))


def export_png_map(world, out_path: str,
                   include_walkability_overlay: bool = True,
                   include_lake_overlay: bool = True) -> str:
    """Render a cartographic PNG using biome palette + elevation shading.

    Optionally overlays walkability dimming and lake-vs-ocean colour shift.
    """
    chunks = _enumerate_chunks(world)
    biome, _ = _gather_layer(world, "biome", chunks)
    height, _ = _gather_layer(world, "height", chunks)

    h, w = biome.shape
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 3] = 255

    palette = np.array([_BIOME_PALETTE.get(i, (128, 128, 128)) for i in range(12)],
                       dtype=np.float32)
    biome_clipped = np.clip(biome.astype(np.int32), 0, 11)
    cols = palette[biome_clipped]
    shade = np.clip(0.45 + height / 4000.0, 0.30, 1.05)[..., None]
    cols = cols * shade

    if include_lake_overlay:
        try:
            lake, _ = _gather_layer(world, "is_lake", chunks)
            lake_mask = lake.astype(bool)
            if lake_mask.any():
                cols[lake_mask] = cols[lake_mask] * 0.6 + np.array(
                    [70, 130, 200], np.float32) * 0.4
        except Exception:
            pass

    if include_walkability_overlay:
        try:
            walk, _ = _gather_layer(world, "walkability", chunks)
            impassable = walk < 0.3
            if impassable.any():
                cols[impassable] = cols[impassable] * 0.4 + np.array(
                    [70, 30, 30], np.float32) * 0.6
        except Exception:
            pass

    img[..., 0] = np.clip(cols[..., 0], 0, 255).astype(np.uint8)
    img[..., 1] = np.clip(cols[..., 1], 0, 255).astype(np.uint8)
    img[..., 2] = np.clip(cols[..., 2], 0, 255).astype(np.uint8)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(_encode_png(img))
    return out_path


# ---------------------------------------------------------------------------
# JSON snapshot — compact state
# ---------------------------------------------------------------------------

def export_json_snapshot(world, out_path: str,
                         include_agents: bool = True,
                         include_chunks: bool = False) -> str:
    """Write a compact JSON snapshot of the world.

    By default includes agents + summary. Pass ``include_chunks=True`` to
    also embed all cached chunk fields as nested arrays — much bigger but
    self-contained.
    """
    sim = world.sim
    data = {
        "summary": world.summary(),
        "tick": int(sim.tick),
    }
    if include_agents:
        try:
            data["agents"] = sim.snapshot_agents()
        except Exception:
            data["agents"] = []
    if include_chunks:
        chunks_dump = {}
        for coord, ch in sim.streamer.cache.items():
            chunks_dump[f"{coord[0]},{coord[1]},{coord[2]}"] = {
                "height": ch.height.tolist(),
                "biome": ch.biome.tolist(),
                "water": ch.water.tolist(),
                "wood": ch.wood.tolist(),
                "stone": ch.stone.tolist(),
            }
        data["chunks"] = chunks_dump
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    return out_path


# ---------------------------------------------------------------------------
# OBJ heightfield (Blender / Unity / Three.js)
# ---------------------------------------------------------------------------

def export_obj_heightfield(world, out_path: str,
                           z_scale: float = 1.0,
                           xy_step: int = 4) -> str:
    """Emit a Wavefront OBJ heightfield mesh stitching every cached chunk.

    ``xy_step`` decimates the grid (1 = full resolution, 4 = 1/16 vertices).
    ``z_scale`` multiplies elevation. The mesh is in metric world coordinates.
    """
    chunks = _enumerate_chunks(world)
    height, (xmin, ymin, xmax, ymax) = _gather_layer(world, "height", chunks)
    h, w = height.shape
    step = max(1, int(xy_step))
    rows = list(range(0, h, step))
    cols = list(range(0, w, step))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Genesis Engine heightfield — world={getattr(world, 'name', '?')} "
                f"tick={getattr(world, 'tick', 0)}\n")
        # Vertices
        for r in rows:
            for c in cols:
                x = xmin + c * VOXEL_SIZE_M
                y = ymin + r * VOXEL_SIZE_M
                z = float(height[r, c]) * z_scale
                f.write(f"v {x:.3f} {y:.3f} {z:.3f}\n")
        # Faces — emit a quad per (r, r+1) × (c, c+1) cell.
        n_cols = len(cols)
        for ri in range(len(rows) - 1):
            for ci in range(n_cols - 1):
                v00 = ri * n_cols + ci + 1
                v10 = (ri + 1) * n_cols + ci + 1
                v01 = ri * n_cols + ci + 2
                v11 = (ri + 1) * n_cols + ci + 2
                f.write(f"f {v00} {v10} {v11} {v01}\n")
    return out_path


__all__ = [
    "export_geotiff", "export_png_map", "export_json_snapshot",
    "export_obj_heightfield", "_VALID_LAYERS",
]
