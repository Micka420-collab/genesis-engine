"""Wave 36 — Isometric 2.5D renderer (Age of Empires style).

Pure numpy + PIL renderer that projects ``Chunk`` voxel terrain into a
2:1 isometric view, painter-algorithm ordered, with hill-shaded biome
faces, agent overlays and (optionally) discovered-building overlays.

This module is a **read-only observation tool** : it never mutates the
sim. It mirrors the API surface of the existing top-down
``engine.world_render`` (Wave 27) but ships an independent biome
palette + hill-shade implementation so it stays self-contained.

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L1 Substrate"``
``WORLD_MODEL_CAPABILITY = "paper-L4 Observer"``

Public API
----------
* :class:`IsometricRenderOptions` — dataclass of every tunable knob.
* :func:`render_chunk_isometric` — render a single :class:`engine.world.Chunk`.
* :func:`render_sim_isometric`   — render a region of ``sim.streamer.cache``
  + agents (+ wounded overlay if anatomy installed) + buildings overlay.
* :func:`render_macro_isometric` — render a macro elevation grid (bonus).
* :func:`signature`              — SHA-256 hex of an RGB array (determinism).
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L1 Substrate"
WORLD_MODEL_CAPABILITY = "paper-L4 Observer"

import hashlib
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from engine.world import (CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M, Biome,
                          Chunk)


# ---------------------------------------------------------------------------
# Biome palette (self-contained; matches the Whittaker buckets in world.py)
# ---------------------------------------------------------------------------

BIOME_COLOURS: Dict[int, Tuple[int, int, int]] = {
    int(Biome.OCEAN):                ( 30,  70, 130),
    int(Biome.ICE):                  (230, 235, 245),
    int(Biome.TUNDRA):               (170, 180, 170),
    int(Biome.BOREAL_FOREST):        ( 50,  90,  60),
    int(Biome.TEMPERATE_FOREST):     ( 60, 130,  70),
    int(Biome.TEMPERATE_RAINFOREST): ( 40, 110,  60),
    int(Biome.GRASSLAND):            (140, 175,  85),
    int(Biome.HOT_DESERT):           (230, 200, 130),
    int(Biome.COLD_DESERT):          (190, 180, 150),
    int(Biome.SAVANNA):              (200, 180,  90),
    int(Biome.TROPICAL_DRY_FOREST):  (110, 140,  60),
    int(Biome.TROPICAL_RAINFOREST):  ( 30, 110,  50),
}

_DEFAULT_BIOME_COLOUR = (120, 120, 120)


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------

@dataclass
class IsometricRenderOptions:
    """Render-time knobs. All public fields are deterministic."""

    # Projection
    tile_w: int = 32                       # tile width in pixels (2:1 iso)
    tile_h: int = 16                       # tile height in pixels
    height_scale_px_per_m: float = 1.0     # 1 px per metre of voxel block
    canvas_padding_px: int = 64

    # Hillshade
    sun_azimuth_deg: float = 315.0
    sun_altitude_deg: float = 45.0
    hillshade_strength: float = 0.55

    # Water
    draw_water: bool = True

    # Agents
    draw_agents: bool = True
    agent_radius_px: int = 3
    agent_rgb: Tuple[int, int, int] = (255, 80, 80)
    wounded_agent_rgb: Tuple[int, int, int] = (180, 0, 0)
    wound_severity_threshold: float = 0.1

    # Buildings
    draw_buildings: bool = True
    building_rgb: Tuple[int, int, int] = (160, 100, 50)

    # Canvas
    background_rgb: Tuple[int, int, int] = (15, 18, 30)

    # Z compression — chunk.height can be -4000..+4000 m. To avoid a 4 km tall
    # canvas, multiply Z by this scalar before projection.
    z_compress: float = 0.05

    # Voxel block height (in metres) — each "block" stacked is this tall.
    voxel_block_m: float = 4.0

    # Macro defaults
    macro_step_m: float = 32.0


# ---------------------------------------------------------------------------
# PIL lazy import (mirrors engine.world_render Wave 27 pattern)
# ---------------------------------------------------------------------------

def _try_import_pil():
    """Return ``(Image, ImageDraw)`` if PIL is available, else ``(None, None)``."""
    try:
        from PIL import Image, ImageDraw  # type: ignore
        return Image, ImageDraw
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Hillshade
# ---------------------------------------------------------------------------

def _hillshade(height: np.ndarray,
               sun_azimuth_deg: float,
               sun_altitude_deg: float,
               strength: float) -> np.ndarray:
    """Return a per-cell hillshade scalar in ``[1-strength, 1+strength*0.5]``.

    Standard hillshade : slope/aspect from finite differences in the height
    grid, dotted with the sun vector. Output is scaled to a multiplicative
    tint factor (around 1.0) so we can simply multiply the RGB face.
    """
    if height.size == 0:
        return np.ones_like(height, dtype=np.float32)
    h = height.astype(np.float32)
    # Central differences (numpy gradient handles edges with first-order).
    dy, dx = np.gradient(h)
    slope = np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    az = math.radians(sun_azimuth_deg)
    alt = math.radians(sun_altitude_deg)
    sa, ca = math.sin(alt), math.cos(alt)
    cos_inc = (sa * np.cos(slope)
               + ca * np.sin(slope) * np.cos(az - aspect))
    cos_inc = np.clip(cos_inc, 0.0, 1.0)
    # Map [0,1] -> [1 - strength, 1 + 0.5*strength] so darkest = 1-s and
    # brightest is only mildly above 1 (avoids blown-out highlights).
    s = float(max(0.0, min(1.0, strength)))
    return (1.0 - s) + cos_inc * (1.5 * s)


def hillshade(height: np.ndarray,
              sun_azimuth_deg: float = 315.0,
              sun_altitude_deg: float = 45.0,
              strength: float = 0.55) -> np.ndarray:
    """Public alias for :func:`_hillshade` (kept stable for downstream callers)."""
    return _hillshade(height, sun_azimuth_deg, sun_altitude_deg, strength)


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def _project_iso(wx: float, wy: float, wz: float,
                 options: IsometricRenderOptions) -> Tuple[float, float]:
    """2:1 isometric projection (world m + voxel height -> screen px).

    ``screen_x = (wx - wy) * tile_w / 2``
    ``screen_y = (wx + wy) * tile_h / 2 - wz * height_scale_px_per_m``
    """
    sx = (wx - wy) * options.tile_w * 0.5
    sy = (wx + wy) * options.tile_h * 0.5 - wz * options.height_scale_px_per_m
    return float(sx), float(sy)


def project_iso(wx: float, wy: float, wz: float = 0.0,
                options: Optional[IsometricRenderOptions] = None
                ) -> Tuple[float, float]:
    """Public alias for :func:`_project_iso`."""
    if options is None:
        options = IsometricRenderOptions()
    return _project_iso(wx, wy, wz, options)


# ---------------------------------------------------------------------------
# Face tinting helpers
# ---------------------------------------------------------------------------

def _tint(rgb: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    """Multiply each channel by ``factor`` and clip to uint8."""
    r = max(0, min(255, int(round(rgb[0] * factor))))
    g = max(0, min(255, int(round(rgb[1] * factor))))
    b = max(0, min(255, int(round(rgb[2] * factor))))
    return (r, g, b)


def _diamond(cx: float, cy: float, tw: int, th: int
             ) -> List[Tuple[int, int]]:
    """Return the 4 vertices of the top diamond around centre (cx, cy)."""
    hw = tw * 0.5
    hh = th * 0.5
    return [
        (int(round(cx)),       int(round(cy - hh))),  # north
        (int(round(cx + hw)),  int(round(cy))),       # east
        (int(round(cx)),       int(round(cy + hh))),  # south
        (int(round(cx - hw)),  int(round(cy))),       # west
    ]


def _left_face(cx: float, cy: float, tw: int, th: int, depth_px: float
               ) -> List[Tuple[int, int]]:
    """Return parallelogram vertices for the left vertical face."""
    hw = tw * 0.5
    hh = th * 0.5
    return [
        (int(round(cx - hw)), int(round(cy))),           # top-west
        (int(round(cx)),      int(round(cy + hh))),      # top-south
        (int(round(cx)),      int(round(cy + hh + depth_px))),  # bot-south
        (int(round(cx - hw)), int(round(cy + depth_px))),       # bot-west
    ]


def _right_face(cx: float, cy: float, tw: int, th: int, depth_px: float
                ) -> List[Tuple[int, int]]:
    """Return parallelogram vertices for the right vertical face."""
    hw = tw * 0.5
    hh = th * 0.5
    return [
        (int(round(cx)),      int(round(cy + hh))),      # top-south
        (int(round(cx + hw)), int(round(cy))),           # top-east
        (int(round(cx + hw)), int(round(cy + depth_px))),       # bot-east
        (int(round(cx)),      int(round(cy + hh + depth_px))),  # bot-south
    ]


# ---------------------------------------------------------------------------
# Canvas math
# ---------------------------------------------------------------------------

def _compute_canvas_bounds(cells_xy_z: np.ndarray,
                           options: IsometricRenderOptions
                           ) -> Tuple[float, float, float, float]:
    """Given an (N, 3) array of (wx, wy, wz) cell anchors return the screen
    bounding box ``(min_sx, min_sy, max_sx, max_sy)`` after projection.

    Note: this is the bounding box of the *cell anchors only* — callers
    need to extend by ``tile_w/2`` and ``tile_h/2 + max_block_depth`` to
    include the diamond and its vertical faces.
    """
    if cells_xy_z.size == 0:
        return (0.0, 0.0, 1.0, 1.0)
    sx = (cells_xy_z[:, 0] - cells_xy_z[:, 1]) * options.tile_w * 0.5
    sy = (cells_xy_z[:, 0] + cells_xy_z[:, 1]) * options.tile_h * 0.5 \
         - cells_xy_z[:, 2] * options.height_scale_px_per_m
    return (float(sx.min()), float(sy.min()),
            float(sx.max()), float(sy.max()))


def _world_to_canvas_xform(min_sx: float, min_sy: float,
                           padding: int,
                           extra_top_px: float
                           ) -> Tuple[float, float]:
    """Return ``(tx, ty)`` such that ``canvas = screen + (tx, ty)``.

    Adds ``padding`` on every side; the vertical *top* gets a bit of extra
    headroom for tall voxel stacks (``extra_top_px``).
    """
    tx = -min_sx + padding
    ty = -min_sy + padding + extra_top_px
    return tx, ty


# ---------------------------------------------------------------------------
# Voxel render
# ---------------------------------------------------------------------------

def _voxel_block_depth_px(block_count: int,
                          options: IsometricRenderOptions
                          ) -> float:
    """Vertical extrusion (in pixels) for ``block_count`` 1-voxel-tall blocks."""
    return max(0.0, float(block_count)) * options.voxel_block_m \
        * options.height_scale_px_per_m


def _draw_voxel_cell(draw,
                     cx: float, cy: float,
                     base_rgb: Tuple[int, int, int],
                     shade: float,
                     options: IsometricRenderOptions,
                     stack_blocks: int = 1) -> None:
    """Draw one voxel column at canvas centre ``(cx, cy)``.

    The "top" of the column is at ``(cx, cy)`` (so callers can place the
    diamond at any z-elevated position). Left and right faces extrude
    downwards by ``depth_px``.
    """
    depth_px = _voxel_block_depth_px(stack_blocks, options)
    tw, th = options.tile_w, options.tile_h

    if depth_px > 0.0:
        # Left face (darker) — light comes from azimuth 315° so the left side
        # is slightly more illuminated than the right in our convention. We
        # still tint left a bit darker than the top to keep a 3D look.
        left_rgb = _tint(base_rgb, max(0.4, shade * 0.75))
        draw.polygon(_left_face(cx, cy, tw, th, depth_px), fill=left_rgb)
        # Right face (darker still — opposite to sun)
        right_rgb = _tint(base_rgb, max(0.3, shade * 0.6))
        draw.polygon(_right_face(cx, cy, tw, th, depth_px), fill=right_rgb)

    # Top diamond — full shade
    top_rgb = _tint(base_rgb, shade)
    draw.polygon(_diamond(cx, cy, tw, th), fill=top_rgb)


# ---------------------------------------------------------------------------
# Chunk rendering
# ---------------------------------------------------------------------------

def _iter_cell_world_anchors(chunk: Chunk, options: IsometricRenderOptions
                             ) -> Iterable[Tuple[int, int, float, float,
                                                  float, float, int, int]]:
    """Yield, in painter order (increasing ``j+i``), for each cell ``(i, j)``:

    ``(i, j, wx_m, wy_m, top_wz_m, blocks_px_depth, biome_id, stack_blocks)``

    Where:
    * ``wx_m, wy_m`` — the cell centre in world metres (cell-local; the
      chunk's world offset is added separately by the caller).
    * ``top_wz_m`` — the z value (in metres) of the *top* of the voxel
      stack (i.e. the diamond elevation), after ``z_compress``.
    * ``stack_blocks`` — how many ``voxel_block_m`` blocks are stacked.
    """
    H, W = chunk.height.shape
    heights = chunk.height.astype(np.float32) * options.z_compress
    biomes = chunk.biome
    # Painter algorithm: iterate so that cells with lower (i+j) draw first
    # (they are "behind" cells with higher (i+j) in iso). After horizontal
    # rotation in iso, (i+j) maps directly to screen_y. We iterate
    # j outer ascending and i outer ascending — equivalent to a sort by
    # (j+i, j) which is stable enough for adjacent cells.
    for j in range(H):
        for i in range(W):
            cx_m = (i + 0.5) * VOXEL_SIZE_M
            cy_m = (j + 0.5) * VOXEL_SIZE_M
            top_z = float(heights[j, i])
            # How many "voxel blocks" to stack from sea level (z=0) up to
            # the top of the cell. Negative => single thin diamond at ocean
            # floor (no stack rendered, just a flat diamond at z=0).
            if top_z <= 0.0:
                stack = 0
                top_z_render = 0.0
            else:
                # 1 px per metre after z_compress already applied. We render
                # the diamond at the top of the cell and extrude downwards.
                # Block height in pixels = voxel_block_m * scale.
                px_per_block = options.voxel_block_m * options.height_scale_px_per_m
                if px_per_block <= 1e-6:
                    stack = 0
                else:
                    stack = max(1, int(math.ceil(
                        top_z * options.height_scale_px_per_m
                        / px_per_block)))
                top_z_render = top_z
            yield (i, j, cx_m, cy_m, top_z_render, 0.0,
                   int(biomes[j, i]), int(stack))


def _render_chunk_into(draw,
                       chunk: Chunk,
                       *,
                       world_offset_m: Tuple[float, float] = (0.0, 0.0),
                       canvas_xform: Tuple[float, float] = (0.0, 0.0),
                       options: IsometricRenderOptions) -> None:
    """Paint a chunk's cells into an already-allocated draw context.

    ``canvas_xform`` shifts the projected screen coords so they end up
    inside the canvas. ``world_offset_m`` is the chunk's world origin in
    metres; the chunk's local cells are offset by this before projection.
    """
    shade = _hillshade(chunk.height,
                       options.sun_azimuth_deg,
                       options.sun_altitude_deg,
                       options.hillshade_strength)
    tx, ty = canvas_xform
    ox, oy = world_offset_m

    for (i, j, lx_m, ly_m, top_z, _unused, biome_id, stack
         ) in _iter_cell_world_anchors(chunk, options):
        wx = ox + lx_m
        wy = oy + ly_m
        sx, sy = _project_iso(wx, wy, top_z, options)
        cx = sx + tx
        cy = sy + ty
        # Water cells get a fixed flat blue tint (no extrusion).
        biome = biome_id
        base = BIOME_COLOURS.get(biome, _DEFAULT_BIOME_COLOUR)
        cell_shade = float(shade[j, i])
        if biome == int(Biome.OCEAN) and not options.draw_water:
            continue
        if biome == int(Biome.OCEAN):
            stack = 0  # flat ocean
        _draw_voxel_cell(draw, cx, cy, base, cell_shade, options,
                         stack_blocks=stack)


def _canvas_from_chunks(chunks: Sequence[Tuple[Tuple[int, int, int], Chunk]],
                        options: IsometricRenderOptions
                        ) -> Tuple[int, int, float, float]:
    """Compute ``(W, H, tx, ty)`` canvas size + xform for the given chunks.

    Each chunk contributes a 64x64 cell grid offset by its world origin.
    We project only the four corners of each chunk to get a fast bbox.
    """
    if not chunks:
        return (32, 32, 0.0, 0.0)
    corners_wx = []
    corners_wy = []
    corners_wz = []
    max_top_z = 0.0
    for (coord, chunk) in chunks:
        cx_chunk, cy_chunk, _ = coord
        ox = cx_chunk * CHUNK_SIDE_M
        oy = cy_chunk * CHUNK_SIDE_M
        # Four corner cells (after we include cell padding inside the chunk).
        # For a tight bbox we include the four extreme cell centres.
        for (lx, ly) in [(0, 0), (CHUNK_SIZE - 1, 0),
                         (0, CHUNK_SIZE - 1),
                         (CHUNK_SIZE - 1, CHUNK_SIZE - 1)]:
            corners_wx.append(ox + (lx + 0.5) * VOXEL_SIZE_M)
            corners_wy.append(oy + (ly + 0.5) * VOXEL_SIZE_M)
            corners_wz.append(0.0)
        # Track max-top-z (in compressed metres) for extra top padding.
        h = chunk.height.max(initial=0.0) * options.z_compress
        if h > max_top_z:
            max_top_z = float(h)

    arr = np.array(list(zip(corners_wx, corners_wy, corners_wz)),
                   dtype=np.float64)
    min_sx, min_sy, max_sx, max_sy = _compute_canvas_bounds(arr, options)
    # Vertical extra: full voxel stack from sea level to the highest peak.
    extra_top_px = max(0.0, max_top_z * options.height_scale_px_per_m
                       + options.voxel_block_m * options.height_scale_px_per_m)
    pad = options.canvas_padding_px
    tile_w_half = options.tile_w * 0.5
    tile_h_half = options.tile_h * 0.5
    W = int(math.ceil((max_sx - min_sx) + tile_w_half * 2.0 + pad * 2.0))
    H = int(math.ceil((max_sy - min_sy) + tile_h_half * 2.0
                       + extra_top_px + pad * 2.0))
    # Defensive minimum so very tiny chunks still produce a non-empty canvas.
    W = max(W, 32)
    H = max(H, 32)
    tx, ty = _world_to_canvas_xform(min_sx, min_sy, pad, extra_top_px)
    return W, H, tx, ty


def render_chunk_isometric(chunk: Chunk,
                            *,
                            path: Optional[str] = None,
                            options: Optional[IsometricRenderOptions] = None
                            ) -> np.ndarray:
    """Render a single chunk to RGB ``(H, W, 3) uint8``.

    The chunk's own origin (its ``coord``) is honoured so multi-chunk
    callers can use the same projection; for a *standalone* chunk
    render this just centres it on the canvas.

    If ``path`` is given and PIL is available, the canvas is saved as PNG.
    """
    if options is None:
        options = IsometricRenderOptions()
    Image, ImageDraw = _try_import_pil()
    if Image is None:
        # PIL missing — return a deterministic background-only buffer.
        return _fallback_canvas(options)

    chunks: List[Tuple[Tuple[int, int, int], Chunk]] = [(chunk.coord, chunk)]
    W, H, tx, ty = _canvas_from_chunks(chunks, options)
    img = Image.new("RGB", (W, H), options.background_rgb)
    draw = ImageDraw.Draw(img)

    cx_chunk, cy_chunk, _ = chunk.coord
    ox = cx_chunk * CHUNK_SIDE_M
    oy = cy_chunk * CHUNK_SIDE_M
    _render_chunk_into(draw, chunk,
                       world_offset_m=(ox, oy),
                       canvas_xform=(tx, ty),
                       options=options)

    rgb = np.asarray(img, dtype=np.uint8)
    if path:
        _save_png(img, path)
    return rgb


# ---------------------------------------------------------------------------
# Sim rendering
# ---------------------------------------------------------------------------

def _bbox_of_chunks(coords: Iterable[Tuple[int, int, int]]
                    ) -> Optional[Tuple[int, int, int, int]]:
    cx = []
    cy = []
    for c in coords:
        cx.append(c[0])
        cy.append(c[1])
    if not cx:
        return None
    return (min(cx), min(cy), max(cx), max(cy))


def _wound_severity_array(sim) -> Optional[np.ndarray]:
    """Defensive lookup for Wave-34 anatomy wound_severity, returns None
    when the module isn't installed."""
    anat = getattr(sim, "_anatomy_fields", None)
    if anat is None:
        return None
    ws = getattr(anat, "wound_severity", None)
    if ws is None:
        return None
    try:
        return np.asarray(ws)
    except Exception:
        return None


def _agents_xy_alive(sim) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = int(getattr(sim.agents, "n_active", 0))
    if n <= 0:
        empty = np.zeros((0, 2), dtype=np.float32)
        return empty, np.zeros((0,), dtype=bool), np.arange(0)
    pos = np.asarray(sim.agents.pos[:n, :2], dtype=np.float32)
    alive_raw = np.asarray(sim.agents.alive[:n], dtype=bool)
    rows = np.arange(n)
    return pos, alive_raw, rows


def _draw_agents(draw,
                 sim,
                 canvas_xform: Tuple[float, float],
                 options: IsometricRenderOptions,
                 elevation_at_xy=None) -> int:
    """Paint agents on the canvas. Returns the number drawn."""
    pos, alive, rows = _agents_xy_alive(sim)
    if pos.shape[0] == 0:
        return 0
    tx, ty = canvas_xform
    r = max(1, int(options.agent_radius_px))
    wound = _wound_severity_array(sim)
    drawn = 0
    for k in range(pos.shape[0]):
        if not bool(alive[k]):
            continue
        wx = float(pos[k, 0])
        wy = float(pos[k, 1])
        wz = 0.0
        if elevation_at_xy is not None:
            try:
                wz = float(elevation_at_xy(wx, wy)) * options.z_compress
            except Exception:
                wz = 0.0
        sx, sy = _project_iso(wx, wy, wz, options)
        cx = sx + tx
        cy = sy + ty - 2  # tiny floor lift so the marker sits on top
        is_wounded = False
        if wound is not None:
            try:
                if wound.ndim == 2:
                    sev = float(wound[k].sum())
                else:
                    sev = float(wound[k])
                if sev > options.wound_severity_threshold:
                    is_wounded = True
            except Exception:
                pass
        col = options.wounded_agent_rgb if is_wounded else options.agent_rgb
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=col)
        drawn += 1
    return drawn


def _buildings_world_blocks(sim
                            ) -> List[Tuple[Tuple[int, int, int],
                                            Tuple[int, int, int]]]:
    """Return a list of ``(chunk_coord, voxel_position)`` for every block
    of every discovered building. Falls back to empty list when the
    building discovery state isn't installed.
    """
    out: List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = []
    state = getattr(sim, "_building_discovery_state", None)
    if state is None:
        return out
    buildings = getattr(state, "buildings", None)
    if not buildings:
        return out
    for bid, b in buildings.items():
        coord = getattr(b, "chunk_coord", None)
        if coord is None:
            continue
        # Each DiscoveredBuilding stores fingerprint + n_blocks; the
        # exact block positions live in pending_blocks BEFORE completion.
        # After completion the blocks are not retained, so we render a
        # *footprint extrusion* using the fingerprint footprint + height.
        fp = getattr(b, "fingerprint", None)
        if fp is None:
            continue
        fw = int(getattr(fp, "footprint_w", getattr(fp, "footprint_x", 2)))
        fh = int(getattr(fp, "footprint_h", getattr(fp, "footprint_y", 2)))
        height = int(getattr(fp, "height", 2))
        # Anchor the footprint at the chunk's origin cell (deterministic).
        # The exact in-chunk anchor isn't tracked post-discovery, so we
        # pick a stable corner via building_id.
        anchor_i = int(bid * 7) % max(1, CHUNK_SIZE - fw)
        anchor_j = int(bid * 13) % max(1, CHUNK_SIZE - fh)
        for di in range(fw):
            for dj in range(fh):
                for dk in range(height):
                    out.append((tuple(coord),
                                (anchor_i + di, anchor_j + dj, dk)))
    return out


def _draw_buildings(draw,
                    sim,
                    canvas_xform: Tuple[float, float],
                    options: IsometricRenderOptions) -> int:
    blocks = _buildings_world_blocks(sim)
    if not blocks:
        return 0
    tx, ty = canvas_xform
    # Sort painter-order: chunk anchor + voxel offset (smaller (wx+wy) first).
    enriched: List[Tuple[float, float, float, Tuple[int, int, int]]] = []
    for (coord, (vi, vj, vk)) in blocks:
        cx_chunk, cy_chunk, _ = coord
        wx = cx_chunk * CHUNK_SIDE_M + (vi + 0.5) * VOXEL_SIZE_M
        wy = cy_chunk * CHUNK_SIDE_M + (vj + 0.5) * VOXEL_SIZE_M
        # Building voxel size = 0.25 m (default of place_block) but we
        # snap to 1 m blocks for visibility.
        wz = (vk + 1) * 1.0 * options.z_compress
        enriched.append((wx + wy, wx, wy, (vi, vj, vk)))
    enriched.sort(key=lambda t: (t[0], t[1]))
    n = 0
    for (_key, wx, wy, (vi, vj, vk)) in enriched:
        wz = (vk + 1) * 1.0 * options.z_compress
        sx, sy = _project_iso(wx, wy, wz, options)
        cx = sx + tx
        cy = sy + ty
        _draw_voxel_cell(draw, cx, cy,
                         options.building_rgb,
                         shade=1.0,
                         options=options,
                         stack_blocks=1)
        n += 1
    return n


def render_sim_isometric(sim,
                          *,
                          chunks_range: Optional[Tuple[int, int, int, int]] = None,
                          path: Optional[str] = None,
                          options: Optional[IsometricRenderOptions] = None
                          ) -> np.ndarray:
    """Render a region of cached chunks for ``sim`` + agents + buildings.

    ``chunks_range = (cx_min, cy_min, cx_max, cy_max)`` selects chunks
    inclusive on all bounds. If ``None``, the bbox of every cached chunk
    is used.
    """
    if options is None:
        options = IsometricRenderOptions()
    cache = getattr(sim.streamer, "cache", {}) or {}
    if chunks_range is None:
        bbox = _bbox_of_chunks(cache.keys())
        if bbox is None:
            return _fallback_canvas(options)
        cx_min, cy_min, cx_max, cy_max = bbox
    else:
        cx_min, cy_min, cx_max, cy_max = chunks_range
    keep: List[Tuple[Tuple[int, int, int], Chunk]] = []
    for coord, chunk in cache.items():
        cx, cy, _cz = coord
        if cx_min <= cx <= cx_max and cy_min <= cy <= cy_max:
            keep.append((coord, chunk))
    keep.sort(key=lambda kv: (kv[0][1], kv[0][0]))
    if not keep:
        return _fallback_canvas(options)

    Image, ImageDraw = _try_import_pil()
    if Image is None:
        return _fallback_canvas(options)

    W, H, tx, ty = _canvas_from_chunks(keep, options)
    img = Image.new("RGB", (W, H), options.background_rgb)
    draw = ImageDraw.Draw(img)

    # Build a fast (x, y) -> elevation lookup so agents can stand on top.
    def elev_at(wx: float, wy: float) -> float:
        cx_chunk = int(math.floor(wx / CHUNK_SIDE_M))
        cy_chunk = int(math.floor(wy / CHUNK_SIDE_M))
        coord = (cx_chunk, cy_chunk, 0)
        chunk = cache.get(coord)
        if chunk is None:
            return 0.0
        lx = wx - cx_chunk * CHUNK_SIDE_M
        ly = wy - cy_chunk * CHUNK_SIDE_M
        ix = max(0, min(CHUNK_SIZE - 1, int(lx / VOXEL_SIZE_M)))
        iy = max(0, min(CHUNK_SIZE - 1, int(ly / VOXEL_SIZE_M)))
        return float(chunk.height[iy, ix])

    # Paint chunks in painter order (cy first, then cx).
    for (coord, chunk) in keep:
        cx_chunk, cy_chunk, _ = coord
        ox = cx_chunk * CHUNK_SIDE_M
        oy = cy_chunk * CHUNK_SIDE_M
        _render_chunk_into(draw, chunk,
                           world_offset_m=(ox, oy),
                           canvas_xform=(tx, ty),
                           options=options)

    if options.draw_buildings:
        _draw_buildings(draw, sim, (tx, ty), options)
    if options.draw_agents:
        _draw_agents(draw, sim, (tx, ty), options,
                     elevation_at_xy=elev_at)

    rgb = np.asarray(img, dtype=np.uint8)
    if path:
        _save_png(img, path)
    return rgb


# ---------------------------------------------------------------------------
# Macro (bonus)
# ---------------------------------------------------------------------------

def _macro_grid_from_world(world: Any) -> Optional[np.ndarray]:
    """Return a 2-D float elevation grid for any "world-like" object.

    Accepts (in order of preference):

    * A numpy array directly (shape (H, W)).
    * An object exposing ``.elevation`` / ``.heightmap`` / ``.elev_m``.
    * A :class:`GlobalWorld` — we build a synthetic grid by sampling each
      attached sim's anchor on a coarse latitude/longitude lattice.
    """
    if world is None:
        return None
    if isinstance(world, np.ndarray):
        if world.ndim == 2:
            return world.astype(np.float32)
        return None
    for attr in ("elevation", "heightmap", "elev_m", "macro_elevation"):
        v = getattr(world, attr, None)
        if isinstance(v, np.ndarray) and v.ndim == 2:
            return v.astype(np.float32)
    # GlobalWorld fallback — derive a synthetic 16x16 from attached sims.
    sims = getattr(world, "sims", None)
    if sims:
        n = max(8, min(64, 4 * int(len(sims) ** 0.5) + 8))
        g = np.zeros((n, n), dtype=np.float32)
        for k, rec in enumerate(sims):
            lat = float(getattr(rec, "anchor_lat", 0.0))
            lon = float(getattr(rec, "anchor_lon", 0.0))
            iy = max(0, min(n - 1, int((lat + 90.0) / 180.0 * (n - 1))))
            ix = max(0, min(n - 1, int((lon + 180.0) / 360.0 * (n - 1))))
            g[iy, ix] = 500.0 + (k % 7) * 100.0
        return g
    return None


def render_macro_isometric(world: Any,
                            *,
                            path: Optional[str] = None,
                            options: Optional[IsometricRenderOptions] = None
                            ) -> np.ndarray:
    """Render a macro elevation grid as an isometric block plain.

    Accepts a numpy array, a :class:`GlobalWorld`, or any object with an
    ``elevation`` attribute. Always returns a non-empty RGB ``(H, W, 3)``.
    """
    if options is None:
        options = IsometricRenderOptions()
    grid = _macro_grid_from_world(world)
    Image, ImageDraw = _try_import_pil()
    if Image is None or grid is None:
        return _fallback_canvas(options)

    H, W = grid.shape
    # Build a virtual "macro chunk" that we render with the same routines.
    macro_h = grid.astype(np.float32)
    # Pick biome based on macro elevation (very coarse: ocean / grass / hill).
    biome = np.full(macro_h.shape, int(Biome.GRASSLAND), dtype=np.uint8)
    biome[macro_h <= 0.0] = int(Biome.OCEAN)
    biome[macro_h >= 1500.0] = int(Biome.TUNDRA)

    fake = Chunk(coord=(0, 0, 0),
                 height=macro_h,
                 biome=biome,
                 stone=np.zeros_like(macro_h),
                 wood=np.zeros_like(macro_h),
                 metal=np.zeros_like(macro_h),
                 water=np.zeros_like(macro_h),
                 food_kcal=np.zeros_like(macro_h),
                 food_capacity=np.zeros_like(macro_h),
                 content_root=b"macro" * 6)

    # Override the iteration step so the renderer doesn't try to use 0.5 m
    # voxels for a continent-scale grid: we rescale via tile_w/tile_h
    # already given by the caller. We just project (i, j) directly.
    bounds = _compute_macro_canvas(W, H, macro_h, options)
    Wc, Hc, tx, ty = bounds
    img = Image.new("RGB", (Wc, Hc), options.background_rgb)
    draw = ImageDraw.Draw(img)

    shade = _hillshade(macro_h,
                       options.sun_azimuth_deg,
                       options.sun_altitude_deg,
                       options.hillshade_strength)
    z_scale = options.z_compress
    for j in range(H):
        for i in range(W):
            wx = float(i)
            wy = float(j)
            top_z = max(0.0, float(macro_h[j, i])) * z_scale
            sx, sy = _project_iso(wx, wy, top_z, options)
            cx = sx + tx
            cy = sy + ty
            b_id = int(biome[j, i])
            base = BIOME_COLOURS.get(b_id, _DEFAULT_BIOME_COLOUR)
            stack_blocks = 0
            if macro_h[j, i] > 0.0:
                # Macro blocks are larger than chunk blocks: scale stack
                # so peaks remain visible without dominating the canvas.
                stack_blocks = max(1, int(round(
                    macro_h[j, i] * z_scale
                    / max(1e-3, options.voxel_block_m
                          * options.height_scale_px_per_m))))
            _draw_voxel_cell(draw, cx, cy, base,
                              float(shade[j, i]),
                              options,
                              stack_blocks=stack_blocks)

    rgb = np.asarray(img, dtype=np.uint8)
    if path:
        _save_png(img, path)
    return rgb


def _compute_macro_canvas(W: int, H: int,
                          height: np.ndarray,
                          options: IsometricRenderOptions
                          ) -> Tuple[int, int, float, float]:
    # Project the four corners and the highest peak.
    corners = np.array([
        [0.0, 0.0, 0.0],
        [W - 1.0, 0.0, 0.0],
        [0.0, H - 1.0, 0.0],
        [W - 1.0, H - 1.0, 0.0],
    ], dtype=np.float64)
    max_top = float(max(0.0, height.max(initial=0.0))) * options.z_compress
    min_sx, min_sy, max_sx, max_sy = _compute_canvas_bounds(corners, options)
    pad = options.canvas_padding_px
    tile_w_half = options.tile_w * 0.5
    tile_h_half = options.tile_h * 0.5
    extra_top_px = max_top * options.height_scale_px_per_m \
        + options.voxel_block_m * options.height_scale_px_per_m
    Wc = max(64, int(math.ceil(
        (max_sx - min_sx) + tile_w_half * 2.0 + pad * 2.0)))
    Hc = max(64, int(math.ceil(
        (max_sy - min_sy) + tile_h_half * 2.0 + extra_top_px + pad * 2.0)))
    tx, ty = _world_to_canvas_xform(min_sx, min_sy, pad, extra_top_px)
    return Wc, Hc, tx, ty


# ---------------------------------------------------------------------------
# Fallback canvas (PIL not available or no chunks)
# ---------------------------------------------------------------------------

def _fallback_canvas(options: IsometricRenderOptions) -> np.ndarray:
    """When PIL is missing, return a deterministic 64x64 background image."""
    W = H = 64
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    canvas[:, :, 0] = options.background_rgb[0]
    canvas[:, :, 1] = options.background_rgb[1]
    canvas[:, :, 2] = options.background_rgb[2]
    return canvas


def _save_png(img, path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    img.save(path, format="PNG", optimize=True)


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------

def signature(rgb: np.ndarray) -> str:
    """SHA-256 hex digest of an RGB array. Used for determinism tests."""
    if not isinstance(rgb, np.ndarray):
        raise TypeError("signature expects a numpy array")
    buf = np.ascontiguousarray(rgb, dtype=np.uint8).tobytes()
    return hashlib.sha256(buf).hexdigest()


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "BIOME_COLOURS",
    "IsometricRenderOptions",
    "hillshade",
    "project_iso",
    "render_chunk_isometric",
    "render_sim_isometric",
    "render_macro_isometric",
    "signature",
]
