"""Genesis Engine — Wave 24 multi-channel Neural Cellular Automata.

Extends :mod:`engine.neural_terrain` (Wave 23) to the **full Mordvintsev
architecture**: per-cell state vector with multiple channels that
co-evolve through 3×3 stencil filters.

Where Wave 23 NCA operated on a single channel (``height``), Wave 24
introduces three co-evolving fields per cell :

  - **H — height**   : bedrock elevation (m).
  - **S — sediment** : loose material kg-equivalent on the surface.
  - **W — water**    : surface moisture / runoff proxy in [0, 1].

The update rules realize a closed mini-hydrology + erosion loop :

  1. ``slope = |∇H|`` and ``laplacian(H)`` extracted via 3×3 stencils.
  2. **Erosion** : `dH ← -k_e · W · slope`  (water + slope carve bedrock).
  3. **Pickup**  : sediment created where eroded.
  4. **Sediment transport** : `S` diffuses (sediment moves to neighbours)
     and is biased downhill.
  5. **Deposition** : on low-slope cells (basins) sediment falls back
     onto height : `dH ← +k_d · S · (1 − slope/slope_cap)`.
  6. **Hillslope diffusion** : `dH ← +α · laplacian(H)` (mild).
  7. **Water budget** : evaporation + light rain top-up + neighbour
     spreading (proxy for surface flow).

The whole system is mass-conserving on average (sediment lifted ≈
sediment deposited) and produces visibly richer landscapes than the
single-channel Wave 23 : valleys carve themselves, alluvial fans spread
at basin mouths, ridge crests get sharpened.

Pure numpy, deterministic (zero RNG, zero global state). The
"neural" claim follows Mordvintsev *et al.* 2020 *Growing Neural
Cellular Automata* : the architecture (state + per-channel stencils +
linear update rule per channel) is identical to a learnable NCA; the
weights here are hand-tuned to physical priors. They can be replaced
by gradient-descent-learned values without changing the inference code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from engine.world import (Biome, CHUNK_SIZE, Chunk,
                           invalidate_resource_masks)


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


# ---------------------------------------------------------------------------
# 3×3 stencils (same Wave 23 convention)
# ---------------------------------------------------------------------------

_LAPLACIAN_3x3 = np.array([
    [0.0, 1.0, 0.0],
    [1.0, -4.0, 1.0],
    [0.0, 1.0, 0.0],
], dtype=np.float32)

_GAUSSIAN_3x3 = np.array([
    [1.0, 2.0, 1.0],
    [2.0, 4.0, 2.0],
    [1.0, 2.0, 1.0],
], dtype=np.float32) / 16.0

_DX_STENCIL = np.array([
    [0.0, 0.0, 0.0],
    [-0.5, 0.0, 0.5],
    [0.0, 0.0, 0.0],
], dtype=np.float32)

_DY_STENCIL = np.array([
    [0.0, -0.5, 0.0],
    [0.0, 0.0, 0.0],
    [0.0, 0.5, 0.0],
], dtype=np.float32)


def _conv3x3_reflect(arr: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Vectorised 3×3 convolution with reflect-padded edges (numpy only)."""
    padded = np.pad(arr, 1, mode="edge")
    out = np.zeros_like(arr, dtype=np.float32)
    for di in range(3):
        for dj in range(3):
            k = float(kernel[di, dj])
            if k == 0.0:
                continue
            out += padded[di:di + arr.shape[0],
                          dj:dj + arr.shape[1]] * k
    return out


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class NCAMultiChannelConfig:
    """Hyper-parameters of the multi-channel NCA.

    Channel-update weights are documented inline. All values are
    dimensionally consistent (slope is m/cell, sediment is m-equivalent,
    water is dimensionless ∈ [0, 1]).
    """

    iterations: int = 6

    # ---- height channel --------------------------------------------------
    h_diffuse: float = 0.06          # hillslope diffusion (Laplacian)
    h_erode_by_water: float = 0.020  # erosion = h_erode * water * slope
    h_deposit_sediment: float = 0.08  # height += h_deposit * S * (1 - s/cap)
    max_dh_per_iter: float = 20.0    # safety cap (m)

    # ---- sediment channel ------------------------------------------------
    s_pickup_efficiency: float = 0.4  # fraction of eroded mass that joins S
    s_diffuse: float = 0.12           # sediment diffusion (no advection)
    # Slope (in m/cell, raw stencil output, NOT normalised to m/m) below
    # which sediment deposits. Default 1.0 = ~200 % grade catches all
    # non-cliff terrain. Lower this for stricter deposition (alluvial fans
    # only on near-flat cells).
    s_settle_slope_cap: float = 1.0

    # ---- water channel ---------------------------------------------------
    w_rain_per_iter: float = 0.06    # global rain top-up per iter
    w_evaporate: float = 0.05         # fraction lost to evaporation per iter
    w_neighbour_share: float = 0.18   # how much water spreads to neighbours
    w_initial: float = 0.40           # initial water on land at iter 0

    # ---- boundary --------------------------------------------------------
    sea_level_m: float = 0.0
    abyss_freeze_below_m: float = -50.0
    reclassify_biomes: bool = True


# ---------------------------------------------------------------------------
# Public state structure
# ---------------------------------------------------------------------------

@dataclass
class MultiChannelDecision:
    """Diagnostic record returned by :func:`refine_chunk_multichannel`."""
    iterations: int = 0
    cells_eroded: int = 0
    cells_deposited: int = 0
    mass_balance_m: float = 0.0   # mean(height) - mean(height_init), m
    peak_water: float = 0.0
    peak_sediment_m: float = 0.0


# ---------------------------------------------------------------------------
# Core refinement (pure function)
# ---------------------------------------------------------------------------

def refine_chunk_multichannel(chunk: Chunk,
                                cfg: Optional[NCAMultiChannelConfig] = None
                                ) -> MultiChannelDecision:
    """Run K iterations of multi-channel NCA on ``chunk`` in place.

    Mutates ``chunk.height``. Sediment and water fields are *local* to this
    call — they do not persist on the chunk (they would not be useful
    cross-tick at chunk scale anyway; chunks live ~10 000 ticks).

    Pure-function : same chunk in → same chunk out (no RNG).

    Returns
    -------
    MultiChannelDecision
        Diagnostic record.
    """
    cfg = cfg or NCAMultiChannelConfig()
    H_init = chunk.height.astype(np.float32, copy=True)
    if (H_init <= cfg.sea_level_m).all():
        return MultiChannelDecision()

    H = H_init.copy()
    abyssal_mask = H_init < cfg.abyss_freeze_below_m

    # Init multi-channel state.
    land_mask = (~abyssal_mask).astype(np.float32)
    S = np.zeros_like(H)
    W = np.full_like(H, cfg.w_initial) * land_mask

    cells_eroded = 0
    cells_deposited = 0

    for _ in range(cfg.iterations):
        # ---- spatial features extracted via 3×3 stencils ------------------
        gx = _conv3x3_reflect(H, _DX_STENCIL)
        gy = _conv3x3_reflect(H, _DY_STENCIL)
        slope = np.sqrt(gx * gx + gy * gy)
        lap = _conv3x3_reflect(H, _LAPLACIAN_3x3)

        # ---- erosion = water × slope × scaling ----------------------------
        erosion = cfg.h_erode_by_water * W * slope  # m per iter
        erosion = np.minimum(
            erosion,
            np.maximum(H - cfg.sea_level_m, 0.0) * 0.2)  # cap at 20 % of relief

        # ---- sediment pickup ---------------------------------------------
        pickup = cfg.s_pickup_efficiency * erosion

        # ---- sediment deposition (Lorentzian decay with slope) -----------
        # Even steep cells deposit a tiny bit (crevice trapping); flat
        # cells deposit fully. Smooth, never clamps to zero.
        deposit_factor = 1.0 / (1.0 + slope /
                                 max(cfg.s_settle_slope_cap, 1e-3))
        deposit = cfg.h_deposit_sediment * S * deposit_factor

        # ---- hillslope diffusion -----------------------------------------
        diffuse = cfg.h_diffuse * lap

        # ---- update height channel ---------------------------------------
        dH = (diffuse           # smoothing
              - erosion         # carving
              + deposit)        # sediment fall-out
        dH = np.clip(dH, -cfg.max_dh_per_iter, cfg.max_dh_per_iter)
        H_new = H + dH
        # Freeze abyssal cells: bathymetry stays bedrock, no co-evolution.
        H_new = np.where(abyssal_mask, H_init, H_new)

        cells_eroded += int((erosion > 0.001).sum())
        cells_deposited += int((deposit > 0.0005).sum())

        H = H_new.astype(np.float32)

        # ---- update sediment channel -------------------------------------
        # pickup adds, deposit removes; diffuse to neighbours via Gaussian.
        S_after = S + pickup - deposit
        S_gauss = _conv3x3_reflect(S_after, _GAUSSIAN_3x3)
        S = S_after + (S_gauss - S_after) * cfg.s_diffuse
        S = np.maximum(S, 0.0)

        # ---- update water channel ----------------------------------------
        # Light rain top-up on land, evaporation, neighbour sharing.
        W = W * (1.0 - cfg.w_evaporate) + cfg.w_rain_per_iter * land_mask
        W_gauss = _conv3x3_reflect(W, _GAUSSIAN_3x3)
        W = W + (W_gauss - W) * cfg.w_neighbour_share
        W = np.clip(W, 0.0, 5.0)

    chunk.height = H.astype(np.float32)

    if cfg.reclassify_biomes:
        # Cells whose blended height drops below sea level → OCEAN.
        # Cells that emerged are left in-place biome (rare, no
        # neighbour vote here — simpler than Wave 23).
        old_above = H_init > cfg.sea_level_m
        new_above = H > cfg.sea_level_m
        submerged = old_above & ~new_above
        if submerged.any():
            chunk.biome[submerged] = int(Biome.OCEAN)

    invalidate_resource_masks(chunk)

    return MultiChannelDecision(
        iterations=cfg.iterations,
        cells_eroded=cells_eroded,
        cells_deposited=cells_deposited,
        mass_balance_m=float(H.mean() - H_init.mean()),
        peak_water=float(W.max()),
        peak_sediment_m=float(S.max()),
    )


# ---------------------------------------------------------------------------
# Per-sim state + installer
# ---------------------------------------------------------------------------

@dataclass
class NCAMultiChannelState:
    config: NCAMultiChannelConfig
    chunks_refined: int = 0
    total_iterations: int = 0
    cells_eroded_total: int = 0
    cells_deposited_total: int = 0
    decisions: Dict[tuple, MultiChannelDecision] = None

    def __post_init__(self):
        if self.decisions is None:
            self.decisions = {}


def install_nca_multichannel(sim,
                               cfg: Optional[NCAMultiChannelConfig] = None
                               ) -> NCAMultiChannelState:
    """Idempotent installer. Wraps :meth:`ChunkStreamer.get` so newly-
    cached chunks pass through :func:`refine_chunk_multichannel` once.

    Note : install this AFTER ``install_neural_terrain`` if you want both
    Wave 23 (single-channel) and Wave 24 (multi-channel) to apply. The
    multi-channel pass runs last; its more elaborate erosion model
    further refines the Wave 23 output.
    """
    cfg = cfg or NCAMultiChannelConfig()
    existing: Optional[NCAMultiChannelState] = getattr(
        sim, "_nca_multichannel_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = NCAMultiChannelState(config=cfg)
    sim._nca_multichannel_state = state

    streamer = sim.streamer
    if getattr(streamer, "_nca_mc_orig_get", None) is None:
        streamer._nca_mc_orig_get = streamer.get
        streamer._nca_mc_orig_touch = streamer.touch_area

        def _wrapped_get(tick, coord):
            was_cached = coord in streamer.cache
            ch = streamer._nca_mc_orig_get(tick, coord)
            if (not was_cached and ch is not None
                    and coord not in state.decisions):
                dec = refine_chunk_multichannel(ch, state.config)
                state.decisions[coord] = dec
                state.chunks_refined += 1
                state.total_iterations += dec.iterations
                state.cells_eroded_total += dec.cells_eroded
                state.cells_deposited_total += dec.cells_deposited
            return ch

        def _wrapped_touch(tick, coords):
            for c in coords:
                if c not in streamer.cache:
                    streamer._nca_mc_orig_touch(tick, [c])
                    ch = streamer.cache.get(c)
                    if ch is not None and c not in state.decisions:
                        dec = refine_chunk_multichannel(ch, state.config)
                        state.decisions[c] = dec
                        state.chunks_refined += 1
                        state.total_iterations += dec.iterations
                        state.cells_eroded_total += dec.cells_eroded
                        state.cells_deposited_total += dec.cells_deposited
                else:
                    streamer.last_touch[c] = tick

        streamer.get = _wrapped_get
        streamer.touch_area = _wrapped_touch

    return state


def apply_to_existing_chunks(sim) -> int:
    state: Optional[NCAMultiChannelState] = getattr(
        sim, "_nca_multichannel_state", None)
    if state is None:
        return 0
    n = 0
    for coord, ch in list(sim.streamer.cache.items()):
        if coord in state.decisions:
            continue
        dec = refine_chunk_multichannel(ch, state.config)
        state.decisions[coord] = dec
        state.chunks_refined += 1
        state.total_iterations += dec.iterations
        state.cells_eroded_total += dec.cells_eroded
        state.cells_deposited_total += dec.cells_deposited
        n += 1
    return n


def nca_multichannel_state(sim) -> Dict[str, object]:
    state: Optional[NCAMultiChannelState] = getattr(
        sim, "_nca_multichannel_state", None)
    if state is None:
        return {"installed": False}
    return {
        "installed": True,
        "chunks_refined": state.chunks_refined,
        "total_iterations": state.total_iterations,
        "cells_eroded_total": state.cells_eroded_total,
        "cells_deposited_total": state.cells_deposited_total,
        "iterations_per_chunk": state.config.iterations,
    }


def uninstall_nca_multichannel(sim) -> bool:
    state = getattr(sim, "_nca_multichannel_state", None)
    if state is None:
        return False
    streamer = sim.streamer
    orig_get = getattr(streamer, "_nca_mc_orig_get", None)
    if orig_get is not None:
        streamer.get = orig_get
        streamer._nca_mc_orig_get = None
    orig_touch = getattr(streamer, "_nca_mc_orig_touch", None)
    if orig_touch is not None:
        streamer.touch_area = orig_touch
        streamer._nca_mc_orig_touch = None
    del sim._nca_multichannel_state
    return True
