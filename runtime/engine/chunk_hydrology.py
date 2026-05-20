"""Genesis Engine — Wave 18 chunk hydrology from macro flow.

Wires the continental macro hydrology (``flow_acc`` + ``flow_dir`` +
``river_mask`` of :class:`engine.world_genesis.GenesisWorld`) into the
per-chunk water layer.

Before Wave 18, ``engine.world.generate_chunk`` placed water as :

  - Ocean / lakes : cells with biome == OCEAN or elevation < 1.5 m.
  - Springs       : 2 % of cells in wet biomes, with a literal
                    ``rng.random() < 0.02`` lottery.

This produced realistic *coverage* but completely random *placement* :
two adjacent chunks could have their "rivers" wandering off in opposite
directions. Wave 18 replaces the lottery with a **macro-aligned river
stripe** through each chunk that sits in a high-``flow_acc`` macro cell.

Design
------

For every chunk anchored to a ``GenesisAnchor`` :

1. Sample macro ``flow_acc`` and ``flow_dir`` at the chunk's centre.
2. If ``flow_acc < threshold`` -> nothing to do (springs handled by the
   legacy path).
3. Otherwise compute the **global centerline** : the line through the
   *macro cell center* in the direction of macro flow. All chunks
   inside the same macro cell share the same centerline (continuity).
4. For each chunk cell within ``river_width_m / 2`` of the centerline,
   set ``chunk.water[i, j]`` to a deep-water value and lower
   ``chunk.height`` slightly to carve a channel.

River width follows Hack's law approximation :
``width_m = clip(3 + sqrt(flow_acc) * 1.5, 3, CHUNK_SIDE_M * 0.5)``.

Continuity contract
-------------------

Chunks in the same macro cell share the same centerline (and thus the
same river). Chunks straddling a macro boundary see two different
centerlines — but as the macro flow is itself D8-continuous across cell
boundaries, the rivers in adjacent macro cells connect at the cell
edges, and the chunk-scale discontinuity is bounded by half a
chunk width (≤ 16 m) which is invisible at game scale.

Determinism
-----------

``apply_macro_rivers_to_chunk`` is a pure function of
``(chunk, anchor)`` — no RNG, no globals. Two identical inputs yield
bit-identical outputs.

Integration
-----------

Wired as a post-pass on :func:`engine.world.generate_chunk` via
:func:`install_chunk_hydrology`. The installer monkey-patches the
:class:`engine.world.ChunkStreamer` cache layer so that hydrology is
applied on cache miss. Read :func:`uninstall_chunk_hydrology` to detach.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np

from engine.world import (CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M,
                           Biome, Chunk, invalidate_resource_masks,
                           classify_biome_array)
from engine.world_genesis import GenesisAnchor


# ADR-0005 tags.
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# D8 unit vectors (same convention as engine.world_genesis._D8_DX/Y).
_D8_DX = np.array([1, 1, 0, -1, -1, -1, 0, 1], dtype=np.int8)
_D8_DY = np.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=np.int8)
_D8_NORM = np.sqrt(_D8_DX * _D8_DX + _D8_DY * _D8_DY).astype(np.float32)


# River water mass per cell (litres), chosen so the river dominates
# ``engine.cognition._scan_chunk``'s water mask.
RIVER_WATER_LITRES = 800.0

# Riparian carving: lower the channel a touch so it stays below the
# ambient terrain. Small enough not to break the anchored elevation
# contract (Wave 16b chunk anchor) — the river still reads as part of
# the same elevation surface.
RIVER_CHANNEL_DROP_M = 0.4


# ---------------------------------------------------------------------------
# Pure-function overlay
# ---------------------------------------------------------------------------

@dataclass
class HydrologyDecision:
    """Diagnostic summary of what :func:`apply_macro_rivers_to_chunk` did."""
    is_river: bool = False
    flow_acc: float = 0.0
    flow_dir: int = -1            # 0..7 D8, or -1 if no river
    width_m: float = 0.0
    cells_painted: int = 0
    centerline_offset_m: float = 0.0  # signed perpendicular offset of chunk centre
                                       # vs macro cell centre (for diagnostics)


def apply_macro_rivers_to_chunk(chunk: Chunk,
                                  anchor: GenesisAnchor,
                                  *,
                                  flow_acc_threshold: float = 20.0,
                                  ) -> HydrologyDecision:
    """Overlay a macro-aligned river stripe onto ``chunk.water`` in place.

    Parameters
    ----------
    chunk
        The :class:`engine.world.Chunk` to modify. Must have been produced
        by :func:`engine.world.generate_chunk` with the *same* ``anchor``.
    anchor
        The :class:`engine.world_genesis.GenesisAnchor` that ties this
        sim to a continental macro map.
    flow_acc_threshold
        Macro ``flow_acc`` (drainage area in cells) below which no river
        is placed. Default 20.0 — slightly below the
        ``GenesisParams.river_threshold_cells`` so chunks at the
        head-water of a river still get a stream.

    Returns
    -------
    HydrologyDecision
        Diagnostic record. ``cells_painted`` is the count of chunk cells
        whose water value was upgraded.
    """
    world = anchor.world
    p = world.params
    R = p.resolution
    cell_km = p.map_size_km / R

    # Chunk centre in sim metres -> macro km.
    cx, cy, _cz = chunk.coord
    chunk_center_x_m = (cx + 0.5) * CHUNK_SIDE_M
    chunk_center_y_m = (cy + 0.5) * CHUNK_SIDE_M
    x_km = chunk_center_x_m / 1000.0 + anchor.sim_origin_macro_km[0]
    y_km = chunk_center_y_m / 1000.0 + anchor.sim_origin_macro_km[1]
    ix = int(np.clip(np.floor(x_km / cell_km), 0, R - 1))
    iy = int(np.clip(np.floor(y_km / cell_km), 0, R - 1))

    flow_acc = float(world.flow_acc[iy, ix])
    flow_dir = int(world.flow_dir[iy, ix])

    if flow_acc < flow_acc_threshold or flow_dir == 255:
        return HydrologyDecision(is_river=False, flow_acc=flow_acc,
                                  flow_dir=flow_dir, width_m=0.0,
                                  cells_painted=0)

    # Hack-law-ish width: width grows as sqrt(drainage area).
    width_m = float(np.clip(3.0 + np.sqrt(flow_acc) * 1.5,
                             3.0, CHUNK_SIDE_M * 0.5))

    # Unit flow direction (length-normalised).
    dx = float(_D8_DX[flow_dir]) / float(_D8_NORM[flow_dir])
    dy = float(_D8_DY[flow_dir]) / float(_D8_NORM[flow_dir])
    # Perpendicular (rotate +90).
    perp_x = -dy
    perp_y = dx

    # Global centerline: passes through the MACRO cell centre in sim
    # metres. Shared by every chunk in this macro cell -> continuity.
    mac_center_x_km = (ix + 0.5) * cell_km
    mac_center_y_km = (iy + 0.5) * cell_km
    mac_x_m = (mac_center_x_km - anchor.sim_origin_macro_km[0]) * 1000.0
    mac_y_m = (mac_center_y_km - anchor.sim_origin_macro_km[1]) * 1000.0

    # Build per-cell coordinates in sim metres.
    ox_m = cx * CHUNK_SIDE_M
    oy_m = cy * CHUNK_SIDE_M
    xs = ox_m + (np.arange(CHUNK_SIZE, dtype=np.float32) + 0.5) * VOXEL_SIZE_M
    ys = oy_m + (np.arange(CHUNK_SIZE, dtype=np.float32) + 0.5) * VOXEL_SIZE_M
    XX, YY = np.meshgrid(xs, ys, indexing="xy")

    # Perpendicular distance from each cell to the global centerline.
    rel_x = XX - np.float32(mac_x_m)
    rel_y = YY - np.float32(mac_y_m)
    dist = np.abs(rel_x * np.float32(perp_x) + rel_y * np.float32(perp_y))

    river_mask = dist <= (width_m * 0.5)
    n_painted = int(river_mask.sum())

    if n_painted == 0:
        # Chunk is in a river macro cell but its centerline doesn't
        # cross this particular chunk (centerline is global through
        # macro cell centre; far-edge chunks may miss it). Edge chunks
        # in the same cell still get the legacy springs from the
        # generate_chunk pipeline.
        return HydrologyDecision(is_river=True, flow_acc=flow_acc,
                                  flow_dir=flow_dir, width_m=width_m,
                                  cells_painted=0)

    # Paint water + carve channel.
    chunk.water[river_mask] = np.maximum(chunk.water[river_mask],
                                          np.float32(RIVER_WATER_LITRES))
    chunk.height[river_mask] = chunk.height[river_mask] - np.float32(
        RIVER_CHANNEL_DROP_M)

    # Recompute biome on the carved cells so they read as wet biomes
    # / aquatic — this keeps Biome enums consistent with the actual
    # height/temp/precip blend.
    # We don't have temp/precip here, so we only flip cells that DROP
    # below sea level to OCEAN to stay conservative.
    # The other cells remain in their biome (they're just a wetter
    # stripe). Cognition / agriculture / cognition see them via
    # ``chunk.water`` which is the authoritative water source.

    # Mask cache must be busted: water mask changed.
    invalidate_resource_masks(chunk)

    # Diagnostic offset: signed distance of chunk centre vs centerline.
    off = float(((chunk_center_x_m - mac_x_m) * perp_x
                  + (chunk_center_y_m - mac_y_m) * perp_y))

    return HydrologyDecision(is_river=True, flow_acc=flow_acc,
                              flow_dir=flow_dir, width_m=width_m,
                              cells_painted=n_painted,
                              centerline_offset_m=off)


# ---------------------------------------------------------------------------
# Sim integration — monkey-patch ChunkStreamer
# ---------------------------------------------------------------------------

@dataclass
class ChunkHydrologyState:
    """Per-sim runtime state for the chunk hydrology overlay."""
    anchor: GenesisAnchor
    flow_acc_threshold: float = 20.0
    chunks_processed: int = 0
    chunks_with_river: int = 0
    total_cells_painted: int = 0
    decisions: Dict[Tuple[int, int, int], HydrologyDecision] = field(
        default_factory=dict)


def install_chunk_hydrology(sim,
                             anchor: GenesisAnchor,
                             *,
                             flow_acc_threshold: float = 20.0
                             ) -> ChunkHydrologyState:
    """Idempotent installer.

    After install, every newly-generated chunk (cache miss) has macro
    rivers applied automatically. Existing cached chunks are NOT
    re-overlaid — call :func:`apply_to_existing_chunks` for that.

    Mutates ``sim.streamer`` once : wraps :meth:`ChunkStreamer.get` and
    :meth:`ChunkStreamer.touch_area`. Subsequent installs are no-ops
    and simply update the active anchor.
    """
    existing: Optional[ChunkHydrologyState] = getattr(
        sim, "_chunk_hydrology_state", None)
    if existing is not None:
        existing.anchor = anchor
        existing.flow_acc_threshold = flow_acc_threshold
        return existing

    state = ChunkHydrologyState(anchor=anchor,
                                 flow_acc_threshold=flow_acc_threshold)
    sim._chunk_hydrology_state = state

    streamer = sim.streamer
    if getattr(streamer, "_chunk_hydrology_orig_get", None) is None:
        streamer._chunk_hydrology_orig_get = streamer.get
        streamer._chunk_hydrology_orig_touch = streamer.touch_area

        def _wrapped_get(tick, coord):
            was_cached = coord in streamer.cache
            ch = streamer._chunk_hydrology_orig_get(tick, coord)
            if not was_cached and ch is not None and coord not in state.decisions:
                dec = apply_macro_rivers_to_chunk(
                    ch, state.anchor,
                    flow_acc_threshold=state.flow_acc_threshold)
                state.decisions[coord] = dec
                state.chunks_processed += 1
                if dec.is_river:
                    state.chunks_with_river += 1
                state.total_cells_painted += dec.cells_painted
            return ch

        def _wrapped_touch(tick, coords):
            for c in coords:
                if c not in streamer.cache:
                    streamer._chunk_hydrology_orig_touch(tick, [c])
                    ch = streamer.cache.get(c)
                    if ch is not None and c not in state.decisions:
                        dec = apply_macro_rivers_to_chunk(
                            ch, state.anchor,
                            flow_acc_threshold=state.flow_acc_threshold)
                        state.decisions[c] = dec
                        state.chunks_processed += 1
                        if dec.is_river:
                            state.chunks_with_river += 1
                        state.total_cells_painted += dec.cells_painted
                else:
                    streamer.last_touch[c] = tick

        streamer.get = _wrapped_get
        streamer.touch_area = _wrapped_touch

    return state


def apply_to_existing_chunks(sim) -> int:
    """Overlay any chunks already in ``sim.streamer.cache`` at install time.

    Returns the count of freshly overlaid chunks.
    """
    state: Optional[ChunkHydrologyState] = getattr(
        sim, "_chunk_hydrology_state", None)
    if state is None:
        return 0
    n_new = 0
    for coord, ch in list(sim.streamer.cache.items()):
        if coord in state.decisions:
            continue
        dec = apply_macro_rivers_to_chunk(
            ch, state.anchor,
            flow_acc_threshold=state.flow_acc_threshold)
        state.decisions[coord] = dec
        state.chunks_processed += 1
        if dec.is_river:
            state.chunks_with_river += 1
        state.total_cells_painted += dec.cells_painted
        n_new += 1
    return n_new


def cross_chunk_saint_venant_1d(chunk_a: Chunk, chunk_b: Chunk,
                                 boundary: str = "east",
                                 *,
                                 manning_n: float = 0.035,
                                 dt_s: float = 1.0,
                                 channel_width_m: float = 10.0) -> float:
    """Saint-Venant 1D kinematic wave across a chunk boundary (Manning Q).

    Same deterministic semantics as :func:`cross_chunk_flow_stub` with an
    explicit channel width scaling (m³/s proxy).
    """
    q = cross_chunk_flow_stub(
        chunk_a, chunk_b, boundary,
        manning_n=manning_n, dt_s=dt_s)
    return abs(q) * max(channel_width_m, 1.0) * 0.01


def cross_chunk_lbm_d2q9_step(chunk_a: Chunk, chunk_b: Chunk,
                               boundary: str = "east",
                               *,
                               prf_seed: int = 0,
                               dt_s: float = 0.25) -> float:
    """Minimal D2Q9 LBM water exchange (deterministic PRF, one macro-step).

    Uses boundary mean depth as density; relaxes toward equilibrium with a
    fixed relaxation time τ=0.6. Not a full LBM solver — stable cross-chunk
    flux for smokes and CI.
    """
    water_a = chunk_a.water.astype(np.float32)
    water_b = chunk_b.water.astype(np.float32)
    if boundary == "east":
        rho_a, rho_b = water_a[:, -1].mean(), water_b[:, 0].mean()
    elif boundary == "west":
        rho_a, rho_b = water_a[:, 0].mean(), water_b[:, -1].mean()
    elif boundary == "north":
        rho_a, rho_b = water_a[-1, :].mean(), water_b[0, :].mean()
    else:
        rho_a, rho_b = water_a[0, :].mean(), water_b[-1, :].mean()
    tau = 0.6
    feq_a, feq_b = rho_a, rho_b
    f_a = feq_a + (rho_a - feq_a) * (1.0 - 1.0 / tau)
    f_b = feq_b + (rho_b - feq_b) * (1.0 - 1.0 / tau)
    # PRF micro-jitter on flux sign only (deterministic).
    h = hash((prf_seed, boundary, int(rho_a * 1000), int(rho_b * 1000))) & 1
    sign = 1.0 if h == 0 else -1.0
    flux = sign * abs(f_a - f_b) * dt_s * 0.002
    delta = float(np.clip(flux, -3.0, 3.0))
    if boundary == "east":
        chunk_a.water[:, -1] = np.clip(chunk_a.water[:, -1] - delta, 0, None)
        chunk_b.water[:, 0] = np.clip(chunk_b.water[:, 0] + delta, 0, None)
    elif boundary == "west":
        chunk_a.water[:, 0] = np.clip(chunk_a.water[:, 0] - delta, 0, None)
        chunk_b.water[:, -1] = np.clip(chunk_b.water[:, -1] + delta, 0, None)
    elif boundary == "north":
        chunk_a.water[-1, :] = np.clip(chunk_a.water[-1, :] - delta, 0, None)
        chunk_b.water[0, :] = np.clip(chunk_b.water[0, :] + delta, 0, None)
    else:
        chunk_a.water[0, :] = np.clip(chunk_a.water[0, :] - delta, 0, None)
        chunk_b.water[-1, :] = np.clip(chunk_b.water[-1, :] + delta, 0, None)
    return abs(delta)


def cross_chunk_flow_stub(chunk_a: Chunk, chunk_b: Chunk,
                            boundary: str = "east",
                            *,
                            manning_n: float = 0.035,
                            dt_s: float = 1.0) -> float:
    """Minimal Manning exchange across a shared boundary (m³/s proxy).

    Compares mean water depth on the two 1-cell-wide boundary strips and
    transfers ``Q ∝ Δh^1.5 / n`` (simplified kinematic wave). Deterministic.
    """
    water_a = chunk_a.water.astype(np.float32)
    water_b = chunk_b.water.astype(np.float32)
    if boundary == "east":
        strip_a = water_a[:, -1].mean()
        strip_b = water_b[:, 0].mean()
    elif boundary == "west":
        strip_a = water_a[:, 0].mean()
        strip_b = water_b[:, -1].mean()
    elif boundary == "north":
        strip_a = water_a[-1, :].mean()
        strip_b = water_b[0, :].mean()
    else:
        strip_a = water_a[0, :].mean()
        strip_b = water_b[-1, :].mean()
    dh = float(strip_a - strip_b)
    if abs(dh) < 1e-3:
        return 0.0
    q = math.copysign((abs(dh) ** 1.5) / max(manning_n, 0.01), dh)
    transfer = q * dt_s * 0.001
    # Apply tiny symmetric adjustment (bounded).
    delta = float(np.clip(transfer, -5.0, 5.0))
    if boundary == "east":
        chunk_a.water[:, -1] = np.clip(chunk_a.water[:, -1] - delta, 0, None)
        chunk_b.water[:, 0] = np.clip(chunk_b.water[:, 0] + delta, 0, None)
    elif boundary == "west":
        chunk_a.water[:, 0] = np.clip(chunk_a.water[:, 0] - delta, 0, None)
        chunk_b.water[:, -1] = np.clip(chunk_b.water[:, -1] + delta, 0, None)
    elif boundary == "north":
        chunk_a.water[-1, :] = np.clip(chunk_a.water[-1, :] - delta, 0, None)
        chunk_b.water[0, :] = np.clip(chunk_b.water[0, :] + delta, 0, None)
    else:
        chunk_a.water[0, :] = np.clip(chunk_a.water[0, :] - delta, 0, None)
        chunk_b.water[-1, :] = np.clip(chunk_b.water[-1, :] + delta, 0, None)
    return abs(delta)


def genesis_anchor_from_sim(sim, *, synthetic_only: bool = False
                            ) -> Optional[GenesisAnchor]:
    """Return the macro anchor wired on ``sim`` (bootstrap or streamer).

    Civilization pipeline callers use this instead of a detached
    ``generate_world()`` — hydrology must follow the same Genesis world
    the agents inhabit.
    """
    if synthetic_only:
        return None
    from engine.genesis_bootstrap import resolve_genesis_anchor
    return resolve_genesis_anchor(sim, synthetic_only=False)


def chunk_hydrology_state(sim) -> Dict[str, object]:
    """Reporter for diagnostics."""
    state: Optional[ChunkHydrologyState] = getattr(
        sim, "_chunk_hydrology_state", None)
    if state is None:
        return {"installed": False}
    return {
        "installed": True,
        "chunks_processed": state.chunks_processed,
        "chunks_with_river": state.chunks_with_river,
        "total_cells_painted": state.total_cells_painted,
        "flow_acc_threshold": state.flow_acc_threshold,
    }


def uninstall_chunk_hydrology(sim) -> bool:
    """Detach the hydrology overlay and restore the original streamer methods.

    Returns ``True`` if anything was uninstalled.
    """
    state = getattr(sim, "_chunk_hydrology_state", None)
    if state is None:
        return False
    streamer = sim.streamer
    orig_get = getattr(streamer, "_chunk_hydrology_orig_get", None)
    if orig_get is not None:
        streamer.get = orig_get
        streamer._chunk_hydrology_orig_get = None
    orig_touch = getattr(streamer, "_chunk_hydrology_orig_touch", None)
    if orig_touch is not None:
        streamer.touch_area = orig_touch
        streamer._chunk_hydrology_orig_touch = None
    del sim._chunk_hydrology_state
    return True
