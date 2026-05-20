"""Genesis Engine — Wave 27 world hillshade renderer.

Produces PNG visualisations of the world fields built by Waves 16-26.
After 13 waves of invisible improvements, this is the module that finally
lets you SEE the generated world.

Three rendering entry points :

  - :func:`render_macro_world`     — continental map (elevation hillshade +
    biome colours + rivers overlay + plate boundaries optional).
  - :func:`render_chunk`           — per-chunk hillshade + biome colour +
    vegetation tile overlay (uses Wave 26 WFC tiles when present).
  - :func:`render_pipeline_demo`   — 2×2 panel comparing :
        raw FBM | Wave 23 NCA mono | Wave 24 NCA multi | Wave 26 WFC veg.

Pure numpy for the maths (hillshade, blending, downsampling).
PIL (Pillow) for the PNG IO only — imported lazily so the module is
still useful for in-memory rendering on environments without PIL.

The hillshade follows the standard surface-normal vs sun-vector dot
product :

    illumination = max(0,
        cos(slope) · cos(sun_zenith)
      + sin(slope) · sin(sun_zenith) · cos(sun_azimuth − aspect)
    )

Outputs are deterministic given the input arrays — no RNG.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from engine.world import Biome


# ---------------------------------------------------------------------------
# Optional PIL handling
# ---------------------------------------------------------------------------

def _try_import_pil():
    try:
        from PIL import Image
        return Image
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Biome → RGB colour table
# ---------------------------------------------------------------------------

# Hand-picked palette inspired by classic atlas hypsometric maps.
BIOME_COLOURS: dict = {
    int(Biome.OCEAN):                np.array([ 20,  60, 120], dtype=np.uint8),
    int(Biome.ICE):                  np.array([240, 248, 255], dtype=np.uint8),
    int(Biome.TUNDRA):               np.array([180, 190, 175], dtype=np.uint8),
    int(Biome.BOREAL_FOREST):        np.array([ 40, 100,  60], dtype=np.uint8),
    int(Biome.TEMPERATE_FOREST):     np.array([ 60, 140,  70], dtype=np.uint8),
    int(Biome.TEMPERATE_RAINFOREST): np.array([ 25, 110,  60], dtype=np.uint8),
    int(Biome.GRASSLAND):            np.array([170, 200, 120], dtype=np.uint8),
    int(Biome.HOT_DESERT):           np.array([230, 200, 130], dtype=np.uint8),
    int(Biome.COLD_DESERT):          np.array([200, 195, 170], dtype=np.uint8),
    int(Biome.SAVANNA):              np.array([200, 180, 100], dtype=np.uint8),
    int(Biome.TROPICAL_DRY_FOREST):  np.array([110, 150,  70], dtype=np.uint8),
    int(Biome.TROPICAL_RAINFOREST):  np.array([ 30,  95,  50], dtype=np.uint8),
}


def biome_color_map(biome_arr: np.ndarray) -> np.ndarray:
    """Map a (H, W) ``uint8`` biome grid to a (H, W, 3) ``uint8`` RGB image."""
    h, w = biome_arr.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for b_id, color in BIOME_COLOURS.items():
        mask = (biome_arr == b_id)
        if mask.any():
            rgb[mask] = color
    return rgb


# ---------------------------------------------------------------------------
# Hillshade
# ---------------------------------------------------------------------------

def hillshade(elev_m: np.ndarray,
              *,
              sun_azimuth_deg: float = 315.0,
              sun_altitude_deg: float = 45.0,
              vert_exag: float = 1.0,
              cell_size_m: float = 30.0) -> np.ndarray:
    """Compute a (H, W) hillshade intensity in [0, 1].

    Implements the standard remote-sensing equation::

        illum = cos(slope) * cos(zenith)
              + sin(slope) * sin(zenith) * cos(azimuth - aspect)

    Returns a float32 array in [0, 1] where 1 is fully lit and 0 fully
    shadowed.

    Parameters
    ----------
    elev_m
        Elevation field (metres, may be negative for ocean).
    sun_azimuth_deg
        Sun position in degrees from north (0=N, 90=E, 180=S, 270=W).
        Default 315° = NW (atlas convention).
    sun_altitude_deg
        Sun height above horizon (0 = sunrise/set, 90 = noon zenith).
    vert_exag
        Vertical exaggeration multiplier on elevation gradient. >1 makes
        relief more dramatic.
    cell_size_m
        Horizontal sample spacing in metres. Used to compute slope in
        m/m.
    """
    elev = elev_m.astype(np.float32) * float(vert_exag)
    # Gradient via central differences.
    dzdy = (np.roll(elev, -1, 0) - np.roll(elev, 1, 0)) * 0.5 / cell_size_m
    dzdx = (np.roll(elev, -1, 1) - np.roll(elev, 1, 1)) * 0.5 / cell_size_m
    # Aspect (compass direction the slope faces).
    aspect = np.arctan2(dzdy, -dzdx)
    # Slope magnitude.
    slope = np.arctan(np.sqrt(dzdx * dzdx + dzdy * dzdy))
    az = np.deg2rad(360.0 - sun_azimuth_deg + 90.0)
    alt = np.deg2rad(sun_altitude_deg)
    zenith = np.pi * 0.5 - alt
    illum = (np.cos(slope) * np.cos(zenith) +
             np.sin(slope) * np.sin(zenith) *
             np.cos(az - aspect))
    return np.clip(illum, 0.0, 1.0).astype(np.float32)


def surface_normals(elev_m: np.ndarray,
                      *,
                      cell_size_m: float = 30.0,
                      vert_exag: float = 1.0) -> np.ndarray:
    """Unit surface normals (H, W, 3) from elevation — PBR-lite input."""
    elev = elev_m.astype(np.float32) * float(vert_exag)
    dzdy = (np.roll(elev, -1, 0) - np.roll(elev, 1, 0)) * 0.5 / cell_size_m
    dzdx = (np.roll(elev, -1, 1) - np.roll(elev, 1, 1)) * 0.5 / cell_size_m
    nx = -dzdx
    ny = -dzdy
    nz = np.ones_like(elev, dtype=np.float32)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    norm = np.maximum(norm, 1e-6)
    return np.stack([nx / norm, ny / norm, nz / norm], axis=-1).astype(np.float32)


def specular_sun(rgb: np.ndarray,
                   normals: np.ndarray,
                   *,
                   sun_azimuth_deg: float = 315.0,
                   sun_altitude_deg: float = 45.0,
                   specular_strength: float = 0.35,
                   shininess: float = 24.0) -> np.ndarray:
    """Blinn-Phong specular highlight toward sun (PBR-lite)."""
    az = np.deg2rad(360.0 - sun_azimuth_deg + 90.0)
    alt = np.deg2rad(sun_altitude_deg)
    lx = float(np.cos(alt) * np.sin(az))
    ly = float(np.cos(alt) * np.cos(az))
    lz = float(np.sin(alt))
    light = np.array([lx, ly, lz], dtype=np.float32)
    light /= max(np.linalg.norm(light), 1e-6)
    ndotl = np.clip(
        normals[..., 0] * light[0]
        + normals[..., 1] * light[1]
        + normals[..., 2] * light[2],
        0.0, 1.0)
    view = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    half = light + view
    half /= max(np.linalg.norm(half), 1e-6)
    ndoth = np.clip(
        normals[..., 0] * half[0]
        + normals[..., 1] * half[1]
        + normals[..., 2] * half[2],
        0.0, 1.0)
    spec = (ndoth ** shininess) * ndotl * float(specular_strength)
    out = rgb.astype(np.float32)
    spec_rgb = np.array([255.0, 248.0, 220.0], dtype=np.float32)
    out = out + spec[..., None] * spec_rgb[None, None, :]
    return np.clip(out, 0.0, 255.0).astype(np.uint8)


def render_macro_pbr_lite(world,
                            *,
                            path: Optional[str] = None,
                            options: Optional[MacroRenderOptions] = None,
                            specular_strength: float = 0.3,
                            ) -> np.ndarray:
    """Macro render with hillshade + specular sun (PBR-lite)."""
    opts = options or MacroRenderOptions()
    cell_km = world.params.map_size_km / world.params.resolution
    cell_m = cell_km * 1000.0
    base = _composite_hillshade_biome(
        world.elevation_m, world.biome,
        sun_azimuth_deg=opts.sun_azimuth_deg,
        sun_altitude_deg=opts.sun_altitude_deg,
        cell_size_m=cell_m,
        hillshade_strength=opts.hillshade_strength,
    )
    normals = surface_normals(
        world.elevation_m, cell_size_m=cell_m,
        vert_exag=1.2)
    rgb = specular_sun(
        base, normals,
        sun_azimuth_deg=opts.sun_azimuth_deg,
        sun_altitude_deg=opts.sun_altitude_deg,
        specular_strength=specular_strength,
    )
    if opts.draw_rivers and hasattr(world, "river_mask"):
        river_rgb = np.array(opts.river_rgb, dtype=np.uint8)
        rgb[world.river_mask.astype(bool)] = river_rgb
    if path is not None:
        _save_png(rgb, path)
    return rgb


def hypsometric_tint(elev_m: np.ndarray,
                      sea_level_m: float = 0.0) -> np.ndarray:
    """Classic hypsometric colour ramp : blue (ocean) → green (lowland) →
    yellow → brown → white (high mountain). Returns (H, W, 3) uint8.
    """
    # Stops (elevation, RGB)
    stops = [
        (-6000.0, np.array([  5,  30,  80], dtype=np.float32)),
        (-200.0,  np.array([ 25,  90, 150], dtype=np.float32)),
        (0.0,     np.array([110, 170, 230], dtype=np.float32)),
        (1.0,     np.array([180, 210, 150], dtype=np.float32)),
        (250.0,   np.array([100, 170,  80], dtype=np.float32)),
        (800.0,   np.array([200, 190, 110], dtype=np.float32)),
        (1800.0,  np.array([170, 130,  90], dtype=np.float32)),
        (3500.0,  np.array([110,  80,  60], dtype=np.float32)),
        (5500.0,  np.array([255, 255, 255], dtype=np.float32)),
    ]
    h, w = elev_m.shape
    out = np.zeros((h, w, 3), dtype=np.float32)
    elev_flat = elev_m.astype(np.float32)
    for i in range(len(stops) - 1):
        e0, c0 = stops[i]
        e1, c1 = stops[i + 1]
        mask = (elev_flat >= e0) & (elev_flat < e1)
        if mask.any():
            t = ((elev_flat[mask] - e0) / max(e1 - e0, 1e-6))[:, None]
            out[mask] = c0 + (c1 - c0) * t
    # Out-of-range fallbacks.
    out[elev_flat < stops[0][0]] = stops[0][1]
    out[elev_flat >= stops[-1][0]] = stops[-1][1]
    return np.clip(out, 0, 255).astype(np.uint8)


def _composite_hillshade_biome(elev_m: np.ndarray,
                                 biome_arr: np.ndarray,
                                 *,
                                 sun_azimuth_deg: float = 315.0,
                                 sun_altitude_deg: float = 45.0,
                                 cell_size_m: float = 30.0,
                                 hillshade_strength: float = 0.5,
                                 ) -> np.ndarray:
    """Combine biome colour + hillshade into a single uint8 RGB image.

    Output pixel = biome_rgb * (1 - s + s * illum) where s is the
    hillshade strength. s=0 → flat biome map ; s=1 → only hillshade.
    """
    biome_rgb = biome_color_map(biome_arr).astype(np.float32)
    illum = hillshade(
        elev_m, sun_azimuth_deg=sun_azimuth_deg,
        sun_altitude_deg=sun_altitude_deg, cell_size_m=cell_size_m,
    )
    s = float(np.clip(hillshade_strength, 0.0, 1.0))
    shade = (1.0 - s) + s * illum
    rgb = biome_rgb * shade[:, :, None]
    return np.clip(rgb, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Macro renderer
# ---------------------------------------------------------------------------

@dataclass
class MacroRenderOptions:
    sun_azimuth_deg: float = 315.0
    sun_altitude_deg: float = 45.0
    hillshade_strength: float = 0.55
    draw_rivers: bool = True
    draw_plate_boundaries: bool = False
    river_rgb: Tuple[int, int, int] = (40, 80, 180)
    boundary_rgb: Tuple[int, int, int] = (220, 60, 60)


def render_macro_world(world,
                        *,
                        path: Optional[str] = None,
                        options: Optional[MacroRenderOptions] = None,
                        ) -> np.ndarray:
    """Render a continental-scale view of a ``GenesisWorld``.

    Returns a (R, R, 3) uint8 ndarray. If ``path`` is given AND PIL is
    available, the image is also saved as PNG.

    Composition :

      biome colour     ← world.biome (12 Whittaker classes)
      × hillshade      ← world.elevation_m + sun azimuth/altitude
      + river overlay  ← world.river_mask in pure blue
      + plate boundary ← world.boundary_kind != 0, in red (optional)
    """
    opts = options or MacroRenderOptions()
    elev = world.elevation_m.astype(np.float32)
    cell_size_m = (world.params.map_size_km * 1000.0) / world.params.resolution
    rgb = _composite_hillshade_biome(
        elev, world.biome,
        sun_azimuth_deg=opts.sun_azimuth_deg,
        sun_altitude_deg=opts.sun_altitude_deg,
        cell_size_m=cell_size_m,
        hillshade_strength=opts.hillshade_strength,
    )
    if opts.draw_rivers and hasattr(world, "river_mask"):
        river = world.river_mask.astype(bool)
        if river.any():
            rgb[river] = np.array(opts.river_rgb, dtype=np.uint8)
    if opts.draw_plate_boundaries and hasattr(world, "boundary_kind"):
        bk = world.boundary_kind > 0
        if bk.any():
            rgb[bk] = np.array(opts.boundary_rgb, dtype=np.uint8)
    if path is not None:
        _save_png(rgb, path)
    return rgb


# ---------------------------------------------------------------------------
# Chunk renderer
# ---------------------------------------------------------------------------

@dataclass
class ChunkRenderOptions:
    sun_azimuth_deg: float = 315.0
    sun_altitude_deg: float = 45.0
    hillshade_strength: float = 0.65
    overlay_water: bool = True
    overlay_wood: bool = True
    upsample: int = 4
    river_rgb: Tuple[int, int, int] = (40, 80, 180)


def render_chunk(chunk,
                  *,
                  path: Optional[str] = None,
                  options: Optional[ChunkRenderOptions] = None,
                  ) -> np.ndarray:
    """Render a single chunk : hillshade + biome + water + wood overlay.

    Output is upsampled by ``options.upsample`` (default 4×, so 64×64 →
    256×256) to make the image readable. Returns (R*upsample, R*upsample, 3)
    uint8.
    """
    opts = options or ChunkRenderOptions()
    elev = chunk.height.astype(np.float32)
    # cell_size = 0.5 m per voxel by Genesis convention.
    rgb = _composite_hillshade_biome(
        elev, chunk.biome,
        sun_azimuth_deg=opts.sun_azimuth_deg,
        sun_altitude_deg=opts.sun_altitude_deg,
        cell_size_m=0.5,
        hillshade_strength=opts.hillshade_strength,
    )
    if opts.overlay_water and hasattr(chunk, "water"):
        water_mask = chunk.water > 100.0
        if water_mask.any():
            rgb[water_mask] = np.array(opts.river_rgb, dtype=np.uint8)
    if opts.overlay_wood and hasattr(chunk, "wood"):
        wood = chunk.wood.astype(np.float32)
        if wood.max() > 1.0:
            # Darken pixels where wood is high (forest canopy).
            wood_norm = np.clip(wood / 80.0, 0.0, 1.0)
            shade = 1.0 - 0.35 * wood_norm
            rgb = (rgb.astype(np.float32) * shade[:, :, None]).clip(0, 255)
            rgb = rgb.astype(np.uint8)
    if opts.upsample > 1:
        rgb = np.repeat(np.repeat(rgb, opts.upsample, axis=0),
                         opts.upsample, axis=1)
    if path is not None:
        _save_png(rgb, path)
    return rgb


# ---------------------------------------------------------------------------
# Pipeline demo (4-panel)
# ---------------------------------------------------------------------------

def render_pipeline_demo(world,
                          *,
                          chunk_coord=(100, 100, 0),
                          path: Optional[str] = None,
                          ) -> np.ndarray:
    """Render a 2×2 panel comparing the chunk through the pipeline stages :

      panel TL : raw FBM chunk (anchored only)
      panel TR : + Wave 23 single-channel NCA
      panel BL : + Wave 24 multi-channel NCA
      panel BR : + Wave 26 WFC vegetation

    Returns a (2*chunk_render_size, 2*chunk_render_size, 3) uint8.
    Provides a visual A/B for the AI passes.
    """
    from engine.world import generate_chunk, TerrainParams
    from engine.world_genesis import make_anchor
    from engine.neural_terrain import (refine_chunk_elevation,
                                         NeuralTerrainConfig)
    from engine.nca_multichannel import (refine_chunk_multichannel,
                                          NCAMultiChannelConfig)
    from engine.wfc_vegetation import (run_wfc_on_chunk,
                                         WFCVegetationConfig)

    anchor = make_anchor(world)
    params = TerrainParams()
    sim_seed = 0xC0FFEE_27 & 0xFFFFFFFFFFFFFFFF

    # Panel TL : anchored chunk only.
    ch_raw = generate_chunk(sim_seed, chunk_coord, params, genesis=anchor)
    img_tl = render_chunk(ch_raw)

    # Panel TR : + NCA mono-channel.
    ch_mono = generate_chunk(sim_seed, chunk_coord, params, genesis=anchor)
    refine_chunk_elevation(ch_mono, NeuralTerrainConfig(iterations=4))
    img_tr = render_chunk(ch_mono)

    # Panel BL : + NCA multi-channel.
    ch_multi = generate_chunk(sim_seed, chunk_coord, params, genesis=anchor)
    refine_chunk_multichannel(ch_multi, NCAMultiChannelConfig(iterations=6))
    img_bl = render_chunk(ch_multi)

    # Panel BR : + WFC vegetation on top of multi-channel.
    ch_wfc = generate_chunk(sim_seed, chunk_coord, params, genesis=anchor)
    refine_chunk_multichannel(ch_wfc, NCAMultiChannelConfig(iterations=6))
    run_wfc_on_chunk(ch_wfc, sim_seed, WFCVegetationConfig())
    img_br = render_chunk(ch_wfc)

    h, w = img_tl.shape[:2]
    grid = np.zeros((h * 2, w * 2, 3), dtype=np.uint8)
    grid[:h, :w] = img_tl
    grid[:h, w:] = img_tr
    grid[h:, :w] = img_bl
    grid[h:, w:] = img_br

    if path is not None:
        _save_png(grid, path)
    return grid


# ---------------------------------------------------------------------------
# PNG IO
# ---------------------------------------------------------------------------

def _save_png(rgb: np.ndarray, path: str) -> bool:
    """Write an (H, W, 3) uint8 array as PNG. No-op if PIL is unavailable."""
    Image = _try_import_pil()
    if Image is None:
        return False
    img = Image.fromarray(rgb, mode="RGB")
    img.save(path, format="PNG")
    return True


def signature(rgb: np.ndarray) -> str:
    """SHA-256 hex digest of an RGB image — for deterministic checks."""
    import hashlib
    return hashlib.sha256(rgb.tobytes()).hexdigest()
