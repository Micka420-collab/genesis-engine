"""Genesis Engine — Wave 23 Neural Cellular Automata terrain refinement.

Implements an NCA-inspired post-pass on chunk elevation. The architecture
follows Mordvintsev et al. (2020) *Growing Neural Cellular Automata* and
Chan (2018) *Lenia* :

  - Per-cell state vector (4 channels : height, slope, curvature, flow_proxy)
  - 3x3 stencil filters to extract local features
  - Fixed per-channel weights combine features into a state delta
  - Iterate K times

The kernels are **hand-tuned to physical priors** rather than
gradient-descent-trained — this keeps the module CPU-friendly,
deterministic, and free of pretrained weight files. The architecture
remains genuinely NCA-shaped : you could swap the hand-tuned weights
for a learned set without changing the inference code.

Physical interpretation of the dynamics
---------------------------------------

The fixed kernel mix produces three competing dynamics each iteration :

  1. **Curvature-driven smoothing** (Laplacian × λ_curv)
     Concave cells (basins) accrete sediment, convex cells (peaks)
     lose mass. Equivalent to a linearised hillslope diffusion.

  2. **Slope-proportional fluvial carving** (|gradient| × λ_carve)
     Steeper cells erode more — encodes the m=0.5, n=1 stream-power
     idea at chunk scale (matches engine.world_genesis erosion).

  3. **Sediment redistribution** (3x3 Gaussian relaxation × λ_diff)
     Smooths checkerboard noise from FBM while preserving mid-scale
     features.

Determinism
-----------

Pure-function : zero RNG, zero global state, zero IO. Same chunk in,
same chunk out — bit-identical. ``install_neural_terrain`` monkey-patches
``ChunkStreamer.get`` so newly-generated chunks are auto-refined.

Read-only contract
------------------

Mutates ``chunk.height`` and ``chunk.biome`` (only when blended elevation
crosses the sea-level threshold) in place. Calls
``engine.world.invalidate_resource_masks`` so cognition caches stay
consistent. Does not modify any other module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np

from engine.world import (Biome, CHUNK_SIZE, Chunk, classify_biome_array,
                           invalidate_resource_masks)


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


# ---------------------------------------------------------------------------
# Hand-tuned NCA kernel weights
# ---------------------------------------------------------------------------

# 3x3 Laplacian (curvature). Concave -> +1, flat -> 0, convex -> -1.
_LAPLACIAN_3x3 = np.array([
    [0.0, 1.0, 0.0],
    [1.0, -4.0, 1.0],
    [0.0, 1.0, 0.0],
], dtype=np.float32)

# 3x3 separable Gaussian (sediment diffusion).
_GAUSSIAN_3x3 = np.array([
    [1.0, 2.0, 1.0],
    [2.0, 4.0, 2.0],
    [1.0, 2.0, 1.0],
], dtype=np.float32) / 16.0

# Central-difference gradient stencils.
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


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class NeuralTerrainConfig:
    """Hyper-parameters of the NCA refinement pass.

    Attributes
    ----------
    iterations
        Number of CA steps per chunk. Each step is O(CHUNK_SIZE^2).
    lambda_curvature
        Strength of curvature-driven smoothing (positive value =
        concavities accrete, convexities erode). Typical 0.05-0.20.
    lambda_carve
        Strength of slope-proportional fluvial carving. Typical
        0.005-0.05.
    lambda_diffuse
        Strength of Gaussian sediment redistribution. Typical 0.05-0.20.
    sea_level_m
        Below this, height is clamped (no NCA in the abyss).
    max_delta_m
        Hard cap on per-iteration height change to avoid runaway.
    """

    iterations: int = 4
    lambda_curvature: float = 0.12
    lambda_carve: float = 0.015
    lambda_diffuse: float = 0.10
    sea_level_m: float = 0.0
    max_delta_m: float = 25.0
    reclassify_biomes: bool = True


# ---------------------------------------------------------------------------
# Pure-function NCA refinement
# ---------------------------------------------------------------------------

def _conv3x3_reflect(arr: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Vectorised 3x3 convolution with reflect-padded boundaries.

    Pure-numpy so the module stays free of scipy. Used 4-5 times per
    iteration per chunk — fast enough for chunks up to 256x256.
    """
    padded = np.pad(arr, 1, mode="edge")
    out = np.zeros_like(arr, dtype=np.float32)
    for di in range(3):
        for dj in range(3):
            k = kernel[di, dj]
            if k == 0.0:
                continue
            out += padded[di:di + arr.shape[0],
                          dj:dj + arr.shape[1]] * k
    return out


def refine_chunk_elevation(chunk: Chunk,
                            cfg: Optional[NeuralTerrainConfig] = None,
                            *,
                            anchor=None,
                            ) -> int:
    """Run K iterations of NCA on ``chunk.height`` in place.

    Returns the number of iterations actually performed (always
    ``cfg.iterations`` unless the chunk is fully under sea level, in
    which case 0).

    The optional ``anchor`` argument is reserved for a future
    macro-coupled variant (Wave 24+) and is currently ignored.

    Algorithm per iteration::

        L  = laplacian(H)                  # curvature
        gx = central_diff_x(H)
        gy = central_diff_y(H)
        S  = sqrt(gx^2 + gy^2)             # slope magnitude
        G  = gaussian_blur(H)              # sediment field

        dH = (+ lambda_curv  * L
              - lambda_carve * S * sign(H - G)
              + lambda_diff  * (G - H))

        dH = clip(dH, -max_delta, +max_delta)
        H  = H + dH
        # land cells only — abyssal floor stays flat
        H  = where(H_initial < sea_level, H_initial, H)
    """
    cfg = cfg or NeuralTerrainConfig()
    H_init = chunk.height.astype(np.float32, copy=True)
    if (H_init <= cfg.sea_level_m).all():
        return 0
    H = H_init.copy()
    abyssal_mask = H_init < cfg.sea_level_m - 50.0

    for _ in range(cfg.iterations):
        lap = _conv3x3_reflect(H, _LAPLACIAN_3x3)
        gx = _conv3x3_reflect(H, _DX_STENCIL)
        gy = _conv3x3_reflect(H, _DY_STENCIL)
        slope = np.sqrt(gx * gx + gy * gy)
        gauss = _conv3x3_reflect(H, _GAUSSIAN_3x3)

        # NCA delta : three competing dynamics composed linearly.
        dH = (cfg.lambda_curvature * lap
              - cfg.lambda_carve * slope * np.sign(H - gauss)
              + cfg.lambda_diffuse * (gauss - H))
        dH = np.clip(dH, -cfg.max_delta_m, cfg.max_delta_m)
        H = H + dH
        # Freeze abyssal cells.
        H = np.where(abyssal_mask, H_init, H)

    chunk.height = H.astype(np.float32)

    # Optionally re-classify biomes for cells that crossed the sea level
    # boundary in either direction. Conservative : we don't have
    # access to temp_c/precip here, so we use the existing biome map
    # but flip submerged cells to OCEAN and re-emerged cells away from
    # OCEAN (by keeping their neighbour's mode biome).
    if cfg.reclassify_biomes:
        old_above = H_init > cfg.sea_level_m
        new_above = H > cfg.sea_level_m
        submerged = old_above & ~new_above
        emerged = ~old_above & new_above
        if submerged.any():
            chunk.biome[submerged] = int(Biome.OCEAN)
        if emerged.any():
            # Use nearest-neighbour vote among the 8 neighbours.
            from_n = []
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    if di == 0 and dj == 0:
                        continue
                    from_n.append(np.roll(chunk.biome, (di, dj), (0, 1)))
            stacked = np.stack(from_n, axis=0)
            # Mode along axis 0 — use bincount per cell.
            modes = np.zeros_like(chunk.biome)
            flat = stacked.reshape(stacked.shape[0], -1).T  # cells x 8
            for c_idx in np.where(emerged.ravel())[0]:
                counts = np.bincount(flat[c_idx], minlength=12)
                # Avoid OCEAN (0) for emerged cells.
                counts[0] = 0
                modes.flat[c_idx] = counts.argmax()
            chunk.biome[emerged] = modes[emerged]

    invalidate_resource_masks(chunk)
    return cfg.iterations


# ---------------------------------------------------------------------------
# Per-sim state
# ---------------------------------------------------------------------------

@dataclass
class NeuralTerrainState:
    config: NeuralTerrainConfig
    chunks_refined: int = 0
    total_iterations: int = 0
    decisions: Dict[tuple, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Sim integration
# ---------------------------------------------------------------------------

def install_neural_terrain(sim,
                            cfg: Optional[NeuralTerrainConfig] = None
                            ) -> NeuralTerrainState:
    """Idempotent installer. Wraps ``ChunkStreamer.get`` so newly-cached
    chunks pass through :func:`refine_chunk_elevation` once.

    Already-cached chunks are NOT retroactively refined — call
    :func:`apply_to_existing_chunks` for that.
    """
    cfg = cfg or NeuralTerrainConfig()
    existing: Optional[NeuralTerrainState] = getattr(
        sim, "_neural_terrain_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = NeuralTerrainState(config=cfg)
    sim._neural_terrain_state = state

    streamer = sim.streamer
    if getattr(streamer, "_neural_terrain_orig_get", None) is None:
        streamer._neural_terrain_orig_get = streamer.get
        streamer._neural_terrain_orig_touch = streamer.touch_area

        def _wrapped_get(tick, coord):
            was_cached = coord in streamer.cache
            ch = streamer._neural_terrain_orig_get(tick, coord)
            if not was_cached and ch is not None and coord not in state.decisions:
                iters = refine_chunk_elevation(ch, state.config)
                state.decisions[coord] = iters
                state.chunks_refined += 1
                state.total_iterations += iters
            return ch

        def _wrapped_touch(tick, coords):
            for c in coords:
                if c not in streamer.cache:
                    streamer._neural_terrain_orig_touch(tick, [c])
                    ch = streamer.cache.get(c)
                    if ch is not None and c not in state.decisions:
                        iters = refine_chunk_elevation(ch, state.config)
                        state.decisions[c] = iters
                        state.chunks_refined += 1
                        state.total_iterations += iters
                else:
                    streamer.last_touch[c] = tick

        streamer.get = _wrapped_get
        streamer.touch_area = _wrapped_touch

    return state


def apply_to_existing_chunks(sim) -> int:
    state: Optional[NeuralTerrainState] = getattr(
        sim, "_neural_terrain_state", None)
    if state is None:
        return 0
    n = 0
    for coord, ch in list(sim.streamer.cache.items()):
        if coord in state.decisions:
            continue
        iters = refine_chunk_elevation(ch, state.config)
        state.decisions[coord] = iters
        state.chunks_refined += 1
        state.total_iterations += iters
        n += 1
    return n


def neural_terrain_state(sim) -> Dict[str, object]:
    state: Optional[NeuralTerrainState] = getattr(
        sim, "_neural_terrain_state", None)
    if state is None:
        return {"installed": False}
    return {
        "installed": True,
        "chunks_refined": state.chunks_refined,
        "total_iterations": state.total_iterations,
        "iterations_per_chunk": state.config.iterations,
    }


def uninstall_neural_terrain(sim) -> bool:
    state = getattr(sim, "_neural_terrain_state", None)
    if state is None:
        return False
    streamer = sim.streamer
    orig_get = getattr(streamer, "_neural_terrain_orig_get", None)
    if orig_get is not None:
        streamer.get = orig_get
        streamer._neural_terrain_orig_get = None
    orig_touch = getattr(streamer, "_neural_terrain_orig_touch", None)
    if orig_touch is not None:
        streamer.touch_area = orig_touch
        streamer._neural_terrain_orig_touch = None
    del sim._neural_terrain_state
    return True
