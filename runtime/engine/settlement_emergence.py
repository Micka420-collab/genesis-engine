"""Genesis Engine — Wave 28 settlement emergence via multi-criteria scoring.

Discovers candidate settlement sites on a :class:`GenesisWorld` by
combining **macro signals from Waves 16-22** into a single per-cell
viability score, then samples N sites via deterministic Poisson-disk
spacing.

The site-selection algorithm is **emergent** : nothing in
``settlement_emergence`` says "place a town at coord X". Each macro
cell receives a score derived from physical/geographical features ;
the top scorers (respecting a minimum spacing) become candidates.

Score components (weighted sum, all in [0, 1]) :

  - **Flatness**      : 1 − clip(|∇elev| / 50, 0, 1)
  - **Water access**  : near river_mask cells, decays with distance
  - **Food potential**: biome NPP (rainforest=1, desert=0.05, etc.)
  - **Tectonic safety**: 1 if no convergent neighbour, else 0.3
  - **Climate score** : Gaussian around 15 °C temp, 800 mm precip
  - **Coast bonus**   : 1 if 5 km < dist_to_coast_km < 80 km (river
                        delta / harbour zone), else attenuated

Final score is the **geometric mean** of components (all-zero in any
factor collapses the score to zero — settlements need all of them).

Poisson-disk sampling
---------------------

After scoring, candidate sites are picked greedily : highest-score
cell that's still > ``min_spacing_km`` from any already-picked site.
Repeat until ``n_candidates`` picked or no remaining candidate.

Determinism
-----------

Score function is pure (no RNG). Tie-breaking in Poisson sampling uses
``prf_rng((seed, "settlements"), [n_picked])`` for jitter when many
cells share the maximum score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.world import Biome
from engine.world_genesis import (GenesisWorld, BOUND_CONVERGENT,
                                    BOUND_DIVERGENT, BOUND_TRANSFORM,
                                    BOUND_NONE)


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# ---------------------------------------------------------------------------
# Biome NPP lookup (food potential)
# ---------------------------------------------------------------------------

# Net Primary Production proxy, normalised to [0, 1].
BIOME_FOOD_POTENTIAL: Dict[int, float] = {
    int(Biome.OCEAN):                0.10,
    int(Biome.ICE):                  0.02,
    int(Biome.TUNDRA):               0.15,
    int(Biome.BOREAL_FOREST):        0.55,
    int(Biome.TEMPERATE_FOREST):     0.80,
    int(Biome.TEMPERATE_RAINFOREST): 0.85,
    int(Biome.GRASSLAND):            0.70,
    int(Biome.HOT_DESERT):           0.05,
    int(Biome.COLD_DESERT):          0.05,
    int(Biome.SAVANNA):              0.60,
    int(Biome.TROPICAL_DRY_FOREST):  0.70,
    int(Biome.TROPICAL_RAINFOREST):  1.00,
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SettlementConfig:
    """Hyper-parameters for the scoring + sampling pipeline."""
    weight_flatness: float = 1.0
    weight_water: float = 1.0
    weight_food: float = 1.0
    weight_safety: float = 0.6
    weight_climate: float = 0.8
    weight_coast: float = 0.4
    target_temp_c: float = 15.0
    temp_sigma_c: float = 12.0
    target_precip_mm: float = 800.0
    precip_sigma_mm: float = 600.0
    coast_optimal_km: float = 25.0
    coast_sigma_km: float = 40.0
    convergent_penalty: float = 0.25     # multiplier when neighbour is CONV
    water_search_radius_cells: int = 3
    score_floor: float = 1e-3            # avoid log(0) in geometric mean


@dataclass
class SettlementCandidate:
    """One discovered candidate site."""
    rank: int
    macro_ix: int
    macro_iy: int
    macro_x_km: float
    macro_y_km: float
    score: float
    components: Dict[str, float] = field(default_factory=dict)
    biome: int = -1
    nearest_river_dist_cells: float = -1.0


# ---------------------------------------------------------------------------
# Score components
# ---------------------------------------------------------------------------

def _flatness_score(world: GenesisWorld) -> np.ndarray:
    """1 − clip(|∇elev|/50, 0, 1) on land, 0 on ocean."""
    elev = world.elevation_m.astype(np.float32)
    gx = (np.roll(elev, -1, 1) - np.roll(elev, 1, 1)) * 0.5
    gy = (np.roll(elev, -1, 0) - np.roll(elev, 1, 0)) * 0.5
    slope = np.sqrt(gx * gx + gy * gy)
    score = 1.0 - np.clip(slope / 50.0, 0.0, 1.0)
    score = np.where(elev > world.params.sea_level_m, score, 0.0)
    return score.astype(np.float32)


def _water_score(world: GenesisWorld,
                   search_radius_cells: int) -> np.ndarray:
    """Distance-decayed proximity to river_mask cells.

    Computed via a small dilation : for each cell, the min distance (in
    cells) to a river_mask cell within ``search_radius_cells``. Cells
    farther get score 0.
    """
    R = world.params.resolution
    riv = world.river_mask.astype(bool)
    dist = np.full((R, R), float(search_radius_cells + 1),
                    dtype=np.float32)
    if riv.any():
        for r in range(search_radius_cells + 1):
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    if abs(di) + abs(dj) != r:
                        continue
                    shifted = np.roll(riv, (di, dj), axis=(0, 1))
                    if di > 0:
                        shifted[:di, :] = False
                    elif di < 0:
                        shifted[di:, :] = False
                    if dj > 0:
                        shifted[:, :dj] = False
                    elif dj < 0:
                        shifted[:, dj:] = False
                    dist = np.where(shifted & (dist > r), r, dist)
    # Optimal : 1 cell away (water access without flooding).
    score = np.where(
        dist < 0.5, 0.5,                         # ON a river : OK but mid
        np.where(dist <= 3.5, 1.0 - (dist - 1.0) / 3.0, 0.0))
    return np.clip(score, 0.0, 1.0).astype(np.float32)


def _food_score(world: GenesisWorld) -> np.ndarray:
    biome = world.biome
    score = np.zeros_like(biome, dtype=np.float32)
    for b_id, npp in BIOME_FOOD_POTENTIAL.items():
        mask = (biome == b_id)
        if mask.any():
            score[mask] = npp
    return score


def _safety_score(world: GenesisWorld, conv_penalty: float) -> np.ndarray:
    """1 if no CONVERGENT boundary cell within 1 cell, else conv_penalty."""
    bk = world.boundary_kind
    conv = (bk == BOUND_CONVERGENT)
    if not conv.any():
        return np.ones_like(bk, dtype=np.float32)
    # Dilate convergent mask by 1 cell.
    near_conv = conv.copy()
    for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        shifted = np.roll(conv, (di, dj), axis=(0, 1))
        near_conv |= shifted
    return np.where(near_conv, conv_penalty, 1.0).astype(np.float32)


def _climate_score(world: GenesisWorld, target_t: float, sigma_t: float,
                    target_p: float, sigma_p: float) -> np.ndarray:
    t = world.temp_c.astype(np.float32)
    p = world.precip_mm.astype(np.float32)
    score_t = np.exp(-((t - target_t) ** 2) / (2.0 * sigma_t * sigma_t))
    score_p = np.exp(-((p - target_p) ** 2) / (2.0 * sigma_p * sigma_p))
    return (score_t * score_p).astype(np.float32)


def _coast_score(world: GenesisWorld, optimal_km: float,
                   sigma_km: float) -> np.ndarray:
    d = world.distance_to_coast_km.astype(np.float32)
    return np.exp(-((d - optimal_km) ** 2) /
                   (2.0 * sigma_km * sigma_km)).astype(np.float32)


# ---------------------------------------------------------------------------
# Combined score
# ---------------------------------------------------------------------------

def score_settlement_viability(world: GenesisWorld,
                                cfg: Optional[SettlementConfig] = None
                                ) -> Dict[str, np.ndarray]:
    """Compute per-cell settlement viability score from macro signals.

    Returns a dict ``{component_name: (R, R) float32 array}`` with the
    individual components AND a ``"score"`` key holding the geometric
    mean (raised to the power of summed weights). Geometric mean
    collapses to 0 if any component is zero — settlements need every
    factor present.
    """
    cfg = cfg or SettlementConfig()
    flat = _flatness_score(world)
    water = _water_score(world, cfg.water_search_radius_cells)
    food = _food_score(world)
    safe = _safety_score(world, cfg.convergent_penalty)
    clim = _climate_score(
        world, cfg.target_temp_c, cfg.temp_sigma_c,
        cfg.target_precip_mm, cfg.precip_sigma_mm)
    coast = _coast_score(world, cfg.coast_optimal_km, cfg.coast_sigma_km)

    # Geometric mean with weighted exponents.
    weights = {
        "flatness": cfg.weight_flatness,
        "water": cfg.weight_water,
        "food": cfg.weight_food,
        "safety": cfg.weight_safety,
        "climate": cfg.weight_climate,
        "coast": cfg.weight_coast,
    }
    components = {
        "flatness": flat,
        "water": water,
        "food": food,
        "safety": safe,
        "climate": clim,
        "coast": coast,
    }
    total_w = sum(weights.values())
    if total_w <= 0:
        score = np.zeros_like(flat)
    else:
        log_score = np.zeros_like(flat)
        for name, arr in components.items():
            w = weights[name] / total_w
            log_score += w * np.log(np.maximum(arr, cfg.score_floor))
        score = np.exp(log_score)
    # Land-only.
    score = np.where(world.elevation_m > world.params.sea_level_m,
                      score, 0.0)
    return {**components, "score": score.astype(np.float32)}


# ---------------------------------------------------------------------------
# Poisson-disk site sampling
# ---------------------------------------------------------------------------

def find_settlement_candidates(world: GenesisWorld,
                                 *,
                                 n_candidates: int = 20,
                                 min_spacing_km: float = 200.0,
                                 cfg: Optional[SettlementConfig] = None,
                                 seed: Optional[int] = None,
                                 ) -> List[SettlementCandidate]:
    """Greedy Poisson-disk pick of the top-scoring cells.

    Algorithm :
      1. Compute score field.
      2. Greedy pick : take argmax cell, mark all cells within
         ``min_spacing_km`` as unavailable, repeat.
      3. Ties broken with a deterministic prf_rng jitter.

    Returns up to ``n_candidates`` candidates ranked by score descending.
    """
    cfg = cfg or SettlementConfig()
    seed = int(seed if seed is not None else int(world.params.seed))

    components = score_settlement_viability(world, cfg)
    score = components["score"].copy()
    R = world.params.resolution
    cell_km = world.params.map_size_km / R
    spacing_cells = max(1, int(np.ceil(min_spacing_km / cell_km)))

    # Deterministic jitter to break score ties. Tiny — smaller than
    # any meaningful score difference.
    rng = prf_rng(seed, ["settlements", "jitter"], [int(R)])
    jitter = rng.random((R, R)).astype(np.float32) * 1e-6
    score = score + jitter

    available = score > cfg.score_floor
    candidates: List[SettlementCandidate] = []

    for rank in range(n_candidates):
        masked = np.where(available, score, -1.0)
        if masked.max() <= 0.0:
            break
        idx = int(np.argmax(masked.ravel()))
        ciy = idx // R
        cix = idx % R
        # Record.
        cand = SettlementCandidate(
            rank=rank,
            macro_ix=cix,
            macro_iy=ciy,
            macro_x_km=(cix + 0.5) * cell_km,
            macro_y_km=(ciy + 0.5) * cell_km,
            score=float(score[ciy, cix] - jitter[ciy, cix]),
            biome=int(world.biome[ciy, cix]),
            components={
                k: float(v[ciy, cix])
                for k, v in components.items() if k != "score"
            },
        )
        candidates.append(cand)
        # Mark spacing zone unavailable.
        for di in range(-spacing_cells, spacing_cells + 1):
            for dj in range(-spacing_cells, spacing_cells + 1):
                if di * di + dj * dj > spacing_cells * spacing_cells:
                    continue
                ni = ciy + di
                nj = cix + dj
                if 0 <= ni < R and 0 <= nj < R:
                    available[ni, nj] = False

    return candidates


# ---------------------------------------------------------------------------
# Render overlay (extends Wave 27)
# ---------------------------------------------------------------------------

def render_settlements_overlay(world: GenesisWorld,
                                 candidates: List[SettlementCandidate],
                                 *,
                                 path: Optional[str] = None,
                                 dot_rgb: Tuple[int, int, int] = (255, 80, 200),
                                 dot_radius_px: int = 1,
                                 ) -> np.ndarray:
    """Render the macro world (Wave 27) + overlay settlement dots.

    Returns (R, R, 3) uint8 array; optionally writes PNG to ``path``.
    """
    from engine.world_render import render_macro_world, MacroRenderOptions, _save_png

    rgb = render_macro_world(world, options=MacroRenderOptions(
        draw_rivers=True, draw_plate_boundaries=False))
    R = rgb.shape[0]
    dot = np.array(dot_rgb, dtype=np.uint8)
    r = max(0, int(dot_radius_px))
    for cand in candidates:
        cy = cand.macro_iy
        cx = cand.macro_ix
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if di * di + dj * dj > r * r:
                    continue
                ni = cy + di
                nj = cx + dj
                if 0 <= ni < R and 0 <= nj < R:
                    rgb[ni, nj] = dot
    if path is not None:
        _save_png(rgb, path)
    return rgb


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def candidates_summary(candidates: List[SettlementCandidate]) -> Dict[str, object]:
    """One-line summary for diagnostics."""
    if not candidates:
        return {"n": 0}
    scores = [c.score for c in candidates]
    biomes_seen = sorted({c.biome for c in candidates})
    return {
        "n": len(candidates),
        "score_min": float(min(scores)),
        "score_max": float(max(scores)),
        "score_mean": float(sum(scores) / len(scores)),
        "biomes_distinct": biomes_seen,
        "top_3_xy_km": [(c.macro_x_km, c.macro_y_km)
                         for c in candidates[:3]],
    }
