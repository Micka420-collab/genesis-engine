"""Tokens visuels Terre réaliste — palette unifiée (atlas / satellite).

Utilisé par ``earth_laws.sample_lite_field``, macro PNG, Earth Console.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np

from engine.world import Biome
from engine.world_render import BIOME_COLOURS, hillshade

# Alias aligné sur world_render (qualité « Terre » cohérente partout).
EARTH_BIOME_RGB: dict[int, Tuple[int, int, int]] = {
    int(k): tuple(int(c) for c in v)
    for k, v in BIOME_COLOURS.items()
}

# Teinte hypsométrique (m) — océan profond → sommets enneigés.
HYPSO_STOPS_M = np.array(
    [-8000, -200, 0, 200, 800, 2000, 3500, 5500], dtype=np.float32,
)
HYPSO_RGB = np.array([
    [12, 35, 95],
    [25, 75, 145],
    [55, 130, 75],
    [120, 165, 85],
    [165, 145, 95],
    [140, 120, 90],
    [200, 195, 185],
    [248, 250, 255],
], dtype=np.float32)


def biome_palette_array(max_id: int = 12) -> np.ndarray:
    """(max_id, 3) float32 pour indexation vectorisée."""
    pal = np.zeros((max_id, 3), dtype=np.float32)
    for bid, rgb in EARTH_BIOME_RGB.items():
        if 0 <= bid < max_id:
            pal[bid] = rgb
    return pal


def hypsometric_blend(
    biome_rgb: np.ndarray,
    height_m: np.ndarray,
    *,
    strength: float = 0.22,
) -> np.ndarray:
    """Mélange biomes + teinte altitude (relief type carte IGN/NASA)."""
    h = height_m.astype(np.float32)
    out = biome_rgb.astype(np.float32).copy()
    for i in range(len(HYPSO_STOPS_M) - 1):
        lo, hi = HYPSO_STOPS_M[i], HYPSO_STOPS_M[i + 1]
        mask = (h >= lo) & (h < hi)
        if not np.any(mask):
            continue
        t = ((h[mask] - lo) / max(hi - lo, 1.0)).astype(np.float32)
        tint = (
            HYPSO_RGB[i][None, :] * (1.0 - t[:, None])
            + HYPSO_RGB[i + 1][None, :] * t[:, None]
        )
        out[mask] = out[mask] * (1.0 - strength) + tint * strength
    return out


def compose_terrain_rgba(
    biome: np.ndarray,
    height_m: np.ndarray,
    water_mm: np.ndarray,
    *,
    cell_size_m: float = 30.0,
    overlay: str = "",
    temp_c: np.ndarray | None = None,
) -> np.ndarray:
    """(H, W, 4) uint8 — terrain Terre réaliste + overlays."""
    h, w = biome.shape
    pal = biome_palette_array(12)
    bclip = np.clip(biome.astype(np.int32), 0, 11)
    cols = pal[bclip].copy()

    hs = hillshade(
        height_m,
        sun_azimuth_deg=315.0,
        sun_altitude_deg=48.0,
        cell_size_m=cell_size_m,
        vert_exag=1.35,
    )
    cols *= (0.48 + 0.52 * hs)[..., None]
    cols = hypsometric_blend(cols, height_m, strength=0.18)

    water_mask = water_mm > 5.0
    ocean_deep = height_m < -5.0
    cols[water_mask] = cols[water_mask] * 0.25 + np.array([18, 72, 165], np.float32) * 0.75
    cols[ocean_deep] = cols[ocean_deep] * 0.15 + np.array([8, 42, 110], np.float32) * 0.85

    if overlay == "temp" and temp_c is not None:
        t_norm = np.clip((temp_c - (-12.0)) / 48.0, 0.0, 1.0)[..., None]
        cold = np.array([70, 120, 210], np.float32)
        hot = np.array([235, 100, 45], np.float32)
        cols = cols * 0.4 + (cold * (1.0 - t_norm) + hot * t_norm) * 0.6
    elif overlay == "water":
        w_norm = np.clip(water_mm / 500.0, 0.0, 1.0)[..., None]
        cols = cols * (1.0 - w_norm * 0.55) + np.array([35, 150, 255], np.float32) * (w_norm * 0.55)
    elif overlay == "flow":
        gx = np.zeros_like(water_mm)
        gy = np.zeros_like(water_mm)
        gx[:, 1:-1] = water_mm[:, 2:] - water_mm[:, :-2]
        gy[1:-1, :] = water_mm[2:, :] - water_mm[:-2, :]
        grad = np.sqrt(gx * gx + gy * gy)
        g_norm = np.clip(grad / (np.percentile(grad, 90) + 1e-3), 0.0, 1.0)[..., None]
        cols = cols * (1.0 - g_norm * 0.7) + np.array([70, 210, 255], np.float32) * (g_norm * 0.7)
        cols[water_mm > 80.0] = cols[water_mm > 80.0] * 0.25 + np.array([30, 110, 220], np.float32) * 0.75

    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = np.clip(cols, 0, 255).astype(np.uint8)
    rgba[..., 3] = 255
    return rgba


__all__ = [
    "EARTH_BIOME_RGB",
    "biome_palette_array",
    "hypsometric_blend",
    "compose_terrain_rgba",
]
