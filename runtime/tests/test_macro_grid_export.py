"""GENM export round-trip (Python side)."""
from __future__ import annotations

import struct
import tempfile
from pathlib import Path

import numpy as np
import pytest

from engine.macro_grid_export import (
    MAGIC,
    VERSION,
    export_macro_grid_binary,
    export_macro_grid_bytes,
    macro_grid_meta,
)
from engine.world_genesis import GenesisParams, generate_world


def test_genm_roundtrip_bytes():
    world = generate_world(GenesisParams(seed=0xABCD, resolution=16))
    raw = export_macro_grid_bytes(world)
    assert raw[:4] == MAGIC
    ver = struct.unpack_from("<I", raw, 4)[0]
    assert ver == VERSION
    w, h, cell_km, _ = macro_grid_meta(world)
    assert w == 16 and h == 16
    assert cell_km == pytest.approx(world.params.map_size_km / 16.0)


def test_genm_file_matches_bytes():
    world = generate_world(GenesisParams(seed=1, resolution=8))
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "macro.genm"
        export_macro_grid_binary(world, path)
        assert path.read_bytes() == export_macro_grid_bytes(world)


def test_genm_elevation_payload_size():
    world = generate_world(GenesisParams(seed=2, resolution=4))
    raw = export_macro_grid_bytes(world)
    header = 4 + 4 + 4 + 4 + 4 + 8  # magic ver w h cell origin
    n = 4 * 4
    # GENM v2 payload is `elev [f32;n] | temp [f32;n] | precip [f32;n] | biome [u8;n]`
    # (see engine.macro_grid_export module docstring).
    assert len(raw) == header + 3 * (n * 4) + n
