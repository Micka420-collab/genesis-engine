"""Terre réaliste — tokens visuels."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.earth_visual_tokens import compose_terrain_rgba, EARTH_BIOME_RGB
from engine.world import Biome


def test_earth_biome_palette_matches_world_render():
    assert int(Biome.OCEAN) in EARTH_BIOME_RGB
    assert EARTH_BIOME_RGB[int(Biome.OCEAN)][2] > 80


def test_compose_terrain_rgba_shape():
    biome = np.zeros((8, 8), dtype=np.int32)
    height = np.linspace(-100, 500, 64).reshape(8, 8).astype(np.float32)
    water = np.zeros((8, 8), dtype=np.float32)
    rgba = compose_terrain_rgba(biome, height, water)
    assert rgba.shape == (8, 8, 4)
    assert rgba[..., 3].min() == 255
