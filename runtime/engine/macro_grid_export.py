"""Export Python :class:`GenesisWorld` macro fields to GENM v2 binary for Rust.

GENM v1 layout (deprecated):
    GENM | ver=1 u32 | W u32 | H u32 | cell_km f32 | ox f32 | oy f32
    | elev [f32;W*H] | biome [u8;W*H]

GENM v2 layout (Phase 3e):
    GENM | ver=2 u32 | W u32 | H u32 | cell_km f32 | ox f32 | oy f32
    | elev [f32;W*H] | temp [f32;W*H] | precip [f32;W*H] | biome [u8;W*H]

v2 adds temperature and precipitation arrays needed for genesis-anchor
blending in the Rust backend.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Tuple, Union

import numpy as np

MAGIC = b"GENM"
VERSION = 2


def macro_grid_meta(world: Any) -> Tuple[int, int, float, Tuple[float, float]]:
    """Return (width, height, cell_km, origin_km) for a Genesis world."""
    p = world.params
    R = int(p.resolution)
    cell_km = float(p.map_size_km) / float(R)
    return R, R, cell_km, (0.0, 0.0)


def _write_genm(
    world: Any,
    sink,
    *,
    origin_km: Tuple[float, float] = (0.0, 0.0),
) -> Tuple[int, int, float]:
    w, h, cell_km, _ = macro_grid_meta(world)
    elev = np.asarray(world.elevation_m, dtype=np.float32).reshape(h, w).ravel()
    temp = np.asarray(world.temp_c, dtype=np.float32).reshape(h, w).ravel()
    precip = np.asarray(world.precip_mm, dtype=np.float32).reshape(h, w).ravel()
    biome = np.asarray(world.biome, dtype=np.uint8).reshape(h, w).ravel()
    n = w * h
    if elev.size != n or temp.size != n or precip.size != n or biome.size != n:
        raise ValueError(f"macro grid size mismatch: {w}x{h} vs buffers")
    sink.write(MAGIC)
    sink.write(struct.pack("<I", VERSION))
    sink.write(struct.pack("<II", w, h))
    sink.write(struct.pack("<f", cell_km))
    sink.write(struct.pack("<ff", float(origin_km[0]), float(origin_km[1])))
    sink.write(elev.astype("<f4", copy=False).tobytes())
    sink.write(temp.astype("<f4", copy=False).tobytes())
    sink.write(precip.astype("<f4", copy=False).tobytes())
    sink.write(biome.tobytes())
    return w, h, cell_km


def export_macro_grid_binary(
    world: Any,
    path: Union[str, Path],
    *,
    origin_km: Tuple[float, float] = (0.0, 0.0),
) -> Path:
    """Write GENM v1 (little-endian) from ``world.elevation_m`` and ``world.biome``."""
    out = Path(path)
    with out.open("wb") as f:
        _write_genm(world, f, origin_km=origin_km)
    return out


def export_macro_grid_bytes(
    world: Any,
    *,
    origin_km: Tuple[float, float] = (0.0, 0.0),
) -> bytes:
    """In-memory GENM payload (for passing to native without a temp file)."""
    import io

    buf = io.BytesIO()
    _write_genm(world, buf, origin_km=origin_km)
    return buf.getvalue()


__all__ = [
    "MAGIC",
    "VERSION",
    "macro_grid_meta",
    "export_macro_grid_binary",
    "export_macro_grid_bytes",
]
