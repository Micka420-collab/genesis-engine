"""Genesis Engine — Wave 26 Wave Function Collapse vegetation distribution.

Implements the Maxim Gumin (2016) **Wave Function Collapse** procedural
content generation algorithm to replace ``chunk.wood``'s uniform-per-
biome blob with an **emergent textured vegetation field** featuring
forest patches, clearings, edge zones, and riparian strips.

WFC is a constraint-satisfaction PCG algorithm inspired by quantum
mechanics : every cell starts in "superposition" over the full tile
set, and the lowest-entropy cell is iteratively collapsed via a
weighted-random choice. Each collapse propagates constraints to its
neighbours via an **adjacency table**, eliminating incompatible tile
options. Repeat until all cells collapsed → a globally-consistent
tile layout.

Distinct from Waves 23-25 NCA :
  - NCA = differential evolution of a continuous state vector.
  - WFC = discrete constraint propagation over a tileset.

Both are genuine AI/PCG techniques. They complement each other : NCA
shapes the terrain heightfield, WFC populates the surface with
vegetation tiles.

Tileset (8 tiles)
-----------------

| ID | Tile name      | Wood kg/m² | Allowed neighbours (4-conn)        |
|----|----------------|-----------:|------------------------------------|
| 0  | ocean          |      0     | shore, water_edge, ocean           |
| 1  | shore          |      0     | ocean, bare, grass, shore          |
| 2  | bare           |      0     | shore, grass, shrub, bare          |
| 3  | grass          |      3     | shore, bare, shrub, edge, water_e  |
| 4  | shrub          |     10     | bare, grass, edge, water_e, shrub  |
| 5  | forest_edge    |     40     | grass, shrub, forest, edge, water_e|
| 6  | forest         |     80     | edge, water_e, forest              |
| 7  | water_edge     |     25     | ocean, grass, shrub, edge, forest  |

The adjacency table enforces **no forest directly bordering bare**
(must transit through edge) and **no ocean directly bordering grass**
(must transit through shore or water_edge).

Biome-driven priors
-------------------

Per biome, a probability vector over the 8 tiles seeds the initial
distribution. Defined in :data:`BIOME_TILE_PRIORS`. Example :

  - TEMPERATE_FOREST → mostly forest (55%) + edge (25%) + shrub (15%)
  - HOT_DESERT       → mostly bare (80%) + grass (15%) + shrub (5%)

Determinism
-----------

All randomness via ``engine.core.prf_rng`` keyed by
``(seed, chunk_coord, wfc_step_counter)``. Two runs of
``run_wfc_on_chunk`` with identical inputs produce bit-identical tile
grids and ``chunk.wood`` fields.

Resolution
----------

WFC operates at a coarser grid than the chunk : default WFC grid is
16×16 cells, each mapping to a 4×4 pixel block of ``chunk.wood``. This
keeps WFC compute bounded (~256 cells × ~8 ops/cell = ~2 k ops per
chunk) and makes the resulting forest patches visible at chunk scale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.world import (Biome, CHUNK_SIZE, Chunk,
                           invalidate_resource_masks)


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# ---------------------------------------------------------------------------
# Tileset
# ---------------------------------------------------------------------------

T_OCEAN = 0
T_SHORE = 1
T_BARE = 2
T_GRASS = 3
T_SHRUB = 4
T_EDGE = 5
T_FOREST = 6
T_WATER_EDGE = 7

N_TILES = 8

TILE_NAMES = (
    "ocean", "shore", "bare", "grass", "shrub",
    "forest_edge", "forest", "water_edge",
)

WOOD_PER_TILE = np.array(
    [0.0, 0.0, 0.0, 3.0, 10.0, 40.0, 80.0, 25.0],
    dtype=np.float32,
)


def _build_adjacency() -> np.ndarray:
    """``ADJ[a, b] = True`` iff tile ``a`` may abut tile ``b`` (4-connected).

    Symmetric. Self-loops always true (clustering).
    """
    adj = np.zeros((N_TILES, N_TILES), dtype=bool)
    for t in range(N_TILES):
        adj[t, t] = True

    def link(a: int, b: int) -> None:
        adj[a, b] = True
        adj[b, a] = True

    # Coastal transitions
    link(T_OCEAN, T_SHORE)
    link(T_OCEAN, T_WATER_EDGE)
    link(T_SHORE, T_BARE)
    link(T_SHORE, T_GRASS)

    # Inland succession
    link(T_BARE, T_GRASS)
    link(T_BARE, T_SHRUB)
    link(T_GRASS, T_SHRUB)
    link(T_GRASS, T_EDGE)
    link(T_SHRUB, T_EDGE)
    link(T_EDGE, T_FOREST)

    # Riparian zones
    link(T_GRASS, T_WATER_EDGE)
    link(T_SHRUB, T_WATER_EDGE)
    link(T_EDGE, T_WATER_EDGE)
    link(T_WATER_EDGE, T_FOREST)

    return adj


ADJ = _build_adjacency()
"""8×8 boolean compatibility matrix between tiles. Use ``ADJ[a]`` as a
mask of tiles compatible with ``a``."""


# Per-biome prior over tiles (rows sum to 1).
BIOME_TILE_PRIORS: Dict[int, np.ndarray] = {
    int(Biome.OCEAN):               np.array([1.0,   0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],  dtype=np.float32),
    int(Biome.ICE):                 np.array([0.0,   0.0,  0.85, 0.13, 0.02, 0.0,  0.0,  0.0],  dtype=np.float32),
    int(Biome.TUNDRA):              np.array([0.0,   0.0,  0.35, 0.45, 0.18, 0.02, 0.0,  0.0],  dtype=np.float32),
    int(Biome.BOREAL_FOREST):       np.array([0.0,   0.0,  0.02, 0.10, 0.20, 0.30, 0.34, 0.04], dtype=np.float32),
    int(Biome.TEMPERATE_FOREST):    np.array([0.0,   0.0,  0.0,  0.05, 0.12, 0.22, 0.56, 0.05], dtype=np.float32),
    int(Biome.TEMPERATE_RAINFOREST):np.array([0.0,   0.0,  0.0,  0.02, 0.08, 0.18, 0.66, 0.06], dtype=np.float32),
    int(Biome.GRASSLAND):           np.array([0.0,   0.0,  0.05, 0.62, 0.18, 0.10, 0.02, 0.03], dtype=np.float32),
    int(Biome.HOT_DESERT):          np.array([0.0,   0.0,  0.80, 0.15, 0.05, 0.0,  0.0,  0.0],  dtype=np.float32),
    int(Biome.COLD_DESERT):         np.array([0.0,   0.0,  0.70, 0.22, 0.07, 0.01, 0.0,  0.0],  dtype=np.float32),
    int(Biome.SAVANNA):             np.array([0.0,   0.0,  0.08, 0.50, 0.28, 0.10, 0.02, 0.02], dtype=np.float32),
    int(Biome.TROPICAL_DRY_FOREST): np.array([0.0,   0.0,  0.02, 0.12, 0.28, 0.30, 0.26, 0.02], dtype=np.float32),
    int(Biome.TROPICAL_RAINFOREST): np.array([0.0,   0.0,  0.0,  0.02, 0.06, 0.16, 0.70, 0.06], dtype=np.float32),
}


# ---------------------------------------------------------------------------
# Configuration + result types
# ---------------------------------------------------------------------------

@dataclass
class WFCVegetationConfig:
    wfc_grid_size: int = 16              # cells per chunk side (must divide CHUNK_SIZE)
    max_resets_per_run: int = 64         # bail-out on too many contradictions
    mute_chunk_wood: bool = True         # write back to chunk.wood
    water_threshold_litres: float = 100.0  # cells with water >= are forced water_edge / ocean
    smooth_block_fill: bool = True       # bilinear-smooth wood at block boundaries


@dataclass
class WFCDecision:
    tiles_grid: Optional[np.ndarray] = None      # shape (R, R) uint8, R=wfc_grid_size
    tile_counts: Dict[int, int] = field(default_factory=dict)
    n_collapsed: int = 0
    n_resets: int = 0
    dominant_biome: int = -1
    dominant_tile: int = -1


# ---------------------------------------------------------------------------
# WFC core
# ---------------------------------------------------------------------------

def _dominant_biome_of(chunk: Chunk) -> int:
    biomes, counts = np.unique(chunk.biome, return_counts=True)
    return int(biomes[np.argmax(counts)])


def _downsample_biome(chunk: Chunk, R: int) -> np.ndarray:
    """Mode-pool the biome map from CHUNK_SIZE x CHUNK_SIZE down to R x R."""
    block = CHUNK_SIZE // R
    out = np.zeros((R, R), dtype=np.uint8)
    for i in range(R):
        for j in range(R):
            patch = chunk.biome[i * block:(i + 1) * block,
                                  j * block:(j + 1) * block]
            vals, cnts = np.unique(patch, return_counts=True)
            out[i, j] = vals[np.argmax(cnts)]
    return out


def _downsample_water(chunk: Chunk, R: int) -> np.ndarray:
    block = CHUNK_SIZE // R
    out = np.zeros((R, R), dtype=np.float32)
    for i in range(R):
        for j in range(R):
            out[i, j] = chunk.water[i * block:(i + 1) * block,
                                     j * block:(j + 1) * block].mean()
    return out


def _weighted_choice(rng: np.random.Generator, weights: np.ndarray) -> int:
    """Sample an index from a weight array, fallback to first nonzero."""
    total = float(weights.sum())
    if total <= 0.0:
        # All zero — uniform fallback.
        return int(rng.integers(0, len(weights)))
    r = float(rng.random()) * total
    acc = 0.0
    for i, w in enumerate(weights):
        acc += float(w)
        if acc >= r:
            return i
    return int(np.argmax(weights))


def run_wfc_on_chunk(chunk: Chunk,
                      sim_seed: int,
                      cfg: Optional[WFCVegetationConfig] = None
                      ) -> WFCDecision:
    """Wave-Function-Collapse vegetation tiles on ``chunk`` in place.

    Mutates ``chunk.wood`` (if ``cfg.mute_chunk_wood``) and calls
    :func:`invalidate_resource_masks`. Returns a :class:`WFCDecision`
    diagnostic record.

    Pure-function of ``(chunk_state, sim_seed)``. Determinism is
    guaranteed by ``prf_rng`` keyed by ``(sim_seed, chunk.coord, step)``.
    """
    cfg = cfg or WFCVegetationConfig()
    R = cfg.wfc_grid_size
    if CHUNK_SIZE % R != 0:
        raise ValueError(f"wfc_grid_size ({R}) must divide CHUNK_SIZE ({CHUNK_SIZE})")

    # Downsample per-chunk biome + water to the WFC grid.
    biome_grid = _downsample_biome(chunk, R)
    water_grid = _downsample_water(chunk, R)

    dominant_biome = _dominant_biome_of(chunk)
    dom_prior = BIOME_TILE_PRIORS.get(
        dominant_biome, np.ones(N_TILES, dtype=np.float32) / N_TILES)

    # Possibility tensor : (R, R, N_TILES) bool. True = tile still allowed.
    poss = np.ones((R, R, N_TILES), dtype=bool)

    # Per-cell prior matrix from the per-cell biome.
    prior = np.zeros((R, R, N_TILES), dtype=np.float32)
    for i in range(R):
        for j in range(R):
            b = int(biome_grid[i, j])
            p = BIOME_TILE_PRIORS.get(b, dom_prior)
            prior[i, j] = p
            # Zero out tiles with prior 0 (biome doesn't allow them).
            poss[i, j] = p > 0.0

    # Force water tiles where water content is high.
    high_water = water_grid >= cfg.water_threshold_litres
    if high_water.any():
        # Allow ocean + water_edge on high-water cells, prefer water_edge.
        for ix, iy in np.argwhere(high_water):
            ix = int(ix); iy = int(iy)
            poss[ix, iy] = False
            # Allow water_edge always; ocean if biome was OCEAN.
            poss[ix, iy, T_WATER_EDGE] = True
            if int(biome_grid[ix, iy]) == int(Biome.OCEAN):
                poss[ix, iy, T_OCEAN] = True
            # Reset prior to favour water tiles.
            new_p = np.zeros(N_TILES, dtype=np.float32)
            new_p[T_WATER_EDGE] = 0.7
            new_p[T_OCEAN] = 0.3
            prior[ix, iy] = new_p

    collapsed = np.zeros((R, R), dtype=bool)
    tiles = np.zeros((R, R), dtype=np.uint8)

    n_resets = 0
    # WFC loop : pick lowest-entropy cell, collapse, propagate.
    step = 0
    while not collapsed.all():
        # Entropy = number of remaining possibilities (cheap proxy).
        n_possible = poss.sum(axis=2)
        n_possible_for_pick = np.where(collapsed, 99, n_possible)

        # Find cells with the minimum (>0) entropy.
        mask_zero = (n_possible == 0) & ~collapsed
        if mask_zero.any():
            # Contradiction — reset these cells to biome prior.
            n_resets += 1
            if n_resets > cfg.max_resets_per_run:
                # Bail : force remaining cells to dominant tile.
                fallback_tile = int(np.argmax(dom_prior))
                tiles[~collapsed] = fallback_tile
                collapsed[~collapsed] = True
                break
            for ix, iy in np.argwhere(mask_zero):
                ix = int(ix); iy = int(iy)
                poss[ix, iy] = (prior[ix, iy] > 0.0)
                if not poss[ix, iy].any():
                    poss[ix, iy, np.argmax(dom_prior)] = True
            continue

        # Lowest entropy among un-collapsed cells (ties → first via argmin).
        idx_flat = int(np.argmin(n_possible_for_pick))
        ci = idx_flat // R
        cj = idx_flat % R

        # Collapse via weighted random choice of remaining tiles.
        rng = prf_rng(sim_seed,
                      ["wfc_veg", str(chunk.coord)],
                      [int(ci), int(cj), step])
        weights = poss[ci, cj].astype(np.float32) * prior[ci, cj]
        chosen = _weighted_choice(rng, weights)
        if not poss[ci, cj, chosen]:
            # Should not happen but safe fallback.
            chosen = int(np.argmax(poss[ci, cj].astype(np.float32)))

        poss[ci, cj, :] = False
        poss[ci, cj, chosen] = True
        tiles[ci, cj] = chosen
        collapsed[ci, cj] = True
        step += 1

        # Propagate constraints to 4-connected neighbours.
        adj_mask = ADJ[chosen]
        for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ni = ci + di
            nj = cj + dj
            if 0 <= ni < R and 0 <= nj < R and not collapsed[ni, nj]:
                poss[ni, nj] &= adj_mask

    # ---- Map tile grid → chunk.wood (block fill) ------------------------
    block = CHUNK_SIZE // R
    if cfg.mute_chunk_wood:
        wood_new = np.zeros_like(chunk.wood, dtype=np.float32)
        for i in range(R):
            for j in range(R):
                t = int(tiles[i, j])
                w = float(WOOD_PER_TILE[t])
                wood_new[i * block:(i + 1) * block,
                         j * block:(j + 1) * block] = w
        if cfg.smooth_block_fill:
            # 3x3 gaussian-ish smoothing across block boundaries.
            padded = np.pad(wood_new, 1, mode="edge")
            smoothed = np.zeros_like(wood_new)
            for di in range(3):
                for dj in range(3):
                    smoothed += padded[di:di + wood_new.shape[0],
                                       dj:dj + wood_new.shape[1]]
            wood_new = (smoothed / 9.0).astype(np.float32)
        chunk.wood = wood_new
        invalidate_resource_masks(chunk)

    counts: Dict[int, int] = {}
    for t in range(N_TILES):
        counts[t] = int((tiles == t).sum())
    dominant_tile = int(max(counts, key=lambda k: counts[k]))

    return WFCDecision(
        tiles_grid=tiles.copy(),
        tile_counts=counts,
        n_collapsed=int(collapsed.sum()),
        n_resets=n_resets,
        dominant_biome=dominant_biome,
        dominant_tile=dominant_tile,
    )


# ---------------------------------------------------------------------------
# Sim integration
# ---------------------------------------------------------------------------

@dataclass
class WFCVegetationState:
    config: WFCVegetationConfig
    chunks_processed: int = 0
    total_resets: int = 0
    tile_counts_total: Dict[int, int] = field(default_factory=lambda: {t: 0 for t in range(N_TILES)})
    decisions: Dict[tuple, WFCDecision] = field(default_factory=dict)


def install_wfc_vegetation(sim,
                             cfg: Optional[WFCVegetationConfig] = None
                             ) -> WFCVegetationState:
    """Idempotent installer. Wraps :meth:`ChunkStreamer.get` to apply WFC
    vegetation to newly-cached chunks."""
    cfg = cfg or WFCVegetationConfig()
    existing: Optional[WFCVegetationState] = getattr(
        sim, "_wfc_vegetation_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = WFCVegetationState(config=cfg)
    sim._wfc_vegetation_state = state

    streamer = sim.streamer
    if getattr(streamer, "_wfc_veg_orig_get", None) is None:
        streamer._wfc_veg_orig_get = streamer.get
        streamer._wfc_veg_orig_touch = streamer.touch_area

        def _wrapped_get(tick, coord):
            was_cached = coord in streamer.cache
            ch = streamer._wfc_veg_orig_get(tick, coord)
            if not was_cached and ch is not None and coord not in state.decisions:
                dec = run_wfc_on_chunk(ch, int(sim.cfg.seed), state.config)
                state.decisions[coord] = dec
                state.chunks_processed += 1
                state.total_resets += dec.n_resets
                for t, c in dec.tile_counts.items():
                    state.tile_counts_total[t] = state.tile_counts_total.get(t, 0) + c
            return ch

        def _wrapped_touch(tick, coords):
            for c in coords:
                if c not in streamer.cache:
                    streamer._wfc_veg_orig_touch(tick, [c])
                    ch = streamer.cache.get(c)
                    if ch is not None and c not in state.decisions:
                        dec = run_wfc_on_chunk(ch, int(sim.cfg.seed),
                                                state.config)
                        state.decisions[c] = dec
                        state.chunks_processed += 1
                        state.total_resets += dec.n_resets
                        for t, cnt in dec.tile_counts.items():
                            state.tile_counts_total[t] = state.tile_counts_total.get(t, 0) + cnt
                else:
                    streamer.last_touch[c] = tick

        streamer.get = _wrapped_get
        streamer.touch_area = _wrapped_touch

    return state


def apply_to_existing_chunks(sim) -> int:
    state: Optional[WFCVegetationState] = getattr(
        sim, "_wfc_vegetation_state", None)
    if state is None:
        return 0
    n = 0
    for coord, ch in list(sim.streamer.cache.items()):
        if coord in state.decisions:
            continue
        dec = run_wfc_on_chunk(ch, int(sim.cfg.seed), state.config)
        state.decisions[coord] = dec
        state.chunks_processed += 1
        state.total_resets += dec.n_resets
        for t, c in dec.tile_counts.items():
            state.tile_counts_total[t] = state.tile_counts_total.get(t, 0) + c
        n += 1
    return n


def wfc_vegetation_state(sim) -> Dict[str, object]:
    state: Optional[WFCVegetationState] = getattr(
        sim, "_wfc_vegetation_state", None)
    if state is None:
        return {"installed": False}
    return {
        "installed": True,
        "chunks_processed": state.chunks_processed,
        "total_resets": state.total_resets,
        "tile_counts": {TILE_NAMES[t]: c for t, c in state.tile_counts_total.items() if c > 0},
    }


def uninstall_wfc_vegetation(sim) -> bool:
    state = getattr(sim, "_wfc_vegetation_state", None)
    if state is None:
        return False
    streamer = sim.streamer
    orig_get = getattr(streamer, "_wfc_veg_orig_get", None)
    if orig_get is not None:
        streamer.get = orig_get
        streamer._wfc_veg_orig_get = None
    orig_touch = getattr(streamer, "_wfc_veg_orig_touch", None)
    if orig_touch is not None:
        streamer.touch_area = orig_touch
        streamer._wfc_veg_orig_touch = None
    del sim._wfc_vegetation_state
    return True


# ---------------------------------------------------------------------------
# Diagnostic : adjacency check on a tile grid
# ---------------------------------------------------------------------------

def count_adjacency_violations(tiles: np.ndarray) -> int:
    """Count pairs of 4-connected neighbours that violate :data:`ADJ`.

    Used by the smoke to verify constraint propagation produced a valid
    layout.
    """
    R = tiles.shape[0]
    violations = 0
    for i in range(R):
        for j in range(R):
            t = int(tiles[i, j])
            for di, dj in ((1, 0), (0, 1)):
                ni = i + di; nj = j + dj
                if 0 <= ni < R and 0 <= nj < R:
                    if not ADJ[t, int(tiles[ni, nj])]:
                        violations += 1
    return violations
