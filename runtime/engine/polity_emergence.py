"""Genesis Engine — Wave 32 polity emergence + Voronoi territory.

Aggregates Wave 28 settlements into **polities** (nations / states /
tribes) by clustering Wave 31 culture vectors. For each polity :

  - Members = a maximal cluster of culturally-similar settlements
    (greedy union-find under ``similarity_threshold``).
  - Capital = the settlement with the highest weight (Wave 30).
  - Territory = the set of macro land cells closer (Euclidean) to ANY
    of the polity's settlements than to any other polity's. This is
    the **multiplicatively-weighted Voronoi diagram** when weights
    are uniform → ordinary Voronoi.
  - Population = sum of member weights.
  - Color = average of member culture-RGB.

The emergent map looks like a Risk / Civilization VI political layer :
contiguous coloured regions, each holding 1+ cities, separated by
borders that follow the local terrain.

Determinism : zero RNG (cultures already came from Wave 31's prf_rng).
Voronoi is computed via vectorised pairwise distance — deterministic
ties broken by lowest-index settlement.

Compatible avec
---------------

- Wave 28 ``SettlementCandidate`` (positions, biomes, score).
- Wave 29 ``RoadNetwork`` (roads stay visible on the map).
- Wave 30 ``TradeNetwork`` (weights drive population).
- Wave 31 ``CulturalHistory`` (cultures drive bloc detection).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.world_genesis import GenesisWorld
from engine.settlement_emergence import SettlementCandidate
from engine.road_network import RoadNetwork
from engine.trade_flow import TradeNetwork
from engine.cultural_diffusion import (CulturalHistory, culture_to_rgb,
                                          detect_cultural_blocs)


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# ---------------------------------------------------------------------------
# Configuration + result types
# ---------------------------------------------------------------------------

@dataclass
class PolityConfig:
    """Hyper-parameters for clustering + territory assignment."""
    similarity_threshold: float = 0.25     # culture L2 distance for bloc
    min_polity_size: int = 1               # min member count (1 = include singletons)
    voronoi_weight_exp: float = 1.0        # > 1 = larger cities steal territory
    border_thickness_px: int = 1
    border_rgb: Tuple[int, int, int] = (30, 30, 30)


@dataclass
class Polity:
    """One emergent polity."""
    polity_id: int
    capital_rank: int                            # rank of dominant settlement
    member_ranks: List[int] = field(default_factory=list)
    territory_mask: np.ndarray = field(default_factory=lambda: np.empty(0))
    population: float = 0.0
    avg_culture: np.ndarray = field(default_factory=lambda: np.empty(0))
    color_rgb: Tuple[int, int, int] = (128, 128, 128)
    territory_cells: int = 0
    biome_counts: Dict[int, int] = field(default_factory=dict)


@dataclass
class PolityMap:
    """Output of :func:`assign_polities`."""
    polities: List[Polity] = field(default_factory=list)
    polity_id_grid: np.ndarray = field(default_factory=lambda: np.empty(0))  # (R, R) int32, -1 = ocean
    n_polities: int = 0
    total_population: float = 0.0


# ---------------------------------------------------------------------------
# Clustering settlements into polities
# ---------------------------------------------------------------------------

def _cluster_settlements(settlements: List[SettlementCandidate],
                           cultures: np.ndarray,
                           weights: np.ndarray,
                           cfg: PolityConfig
                           ) -> List[List[int]]:
    """Return clusters as lists of settlement *indices* (positional).

    Uses :func:`engine.cultural_diffusion.detect_cultural_blocs`.
    Filters out clusters smaller than ``cfg.min_polity_size``.
    """
    blocs = detect_cultural_blocs(
        cultures, similarity_threshold=cfg.similarity_threshold)
    if cfg.min_polity_size <= 1:
        return blocs
    return [b for b in blocs if len(b) >= cfg.min_polity_size]


# ---------------------------------------------------------------------------
# Voronoi territory assignment
# ---------------------------------------------------------------------------

def _compute_voronoi(world: GenesisWorld,
                      settlements: List[SettlementCandidate],
                      polity_of_settlement: List[int],
                      weights: np.ndarray,
                      weight_exp: float,
                      ) -> np.ndarray:
    """Per macro land cell, find the nearest settlement (multiplicatively-
    weighted Voronoi) and return its polity_id. Ocean cells get -1.

    weighted distance(cell, settlement) = euclid(cell, settlement) / weight^exp
    """
    R = world.params.resolution
    if not settlements:
        return np.full((R, R), -1, dtype=np.int32)

    # Settlement coords in macro grid.
    sx = np.array([c.macro_ix for c in settlements], dtype=np.float32)
    sy = np.array([c.macro_iy for c in settlements], dtype=np.float32)
    polity_arr = np.array(polity_of_settlement, dtype=np.int32)
    w = np.power(np.maximum(weights, 1e-3), float(weight_exp)).astype(np.float32)

    yy, xx = np.indices((R, R))
    yy = yy.astype(np.float32); xx = xx.astype(np.float32)

    # Distance tensor (R, R, N) -- could be big at large R but fine at 128.
    dx = xx[..., None] - sx[None, None, :]
    dy = yy[..., None] - sy[None, None, :]
    d = np.sqrt(dx * dx + dy * dy) / w[None, None, :]

    nearest = np.argmin(d, axis=2).astype(np.int32)
    polity_id_grid = polity_arr[nearest]
    # Ocean → -1.
    polity_id_grid = np.where(
        world.elevation_m > world.params.sea_level_m, polity_id_grid, -1)
    return polity_id_grid.astype(np.int32)


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def assign_polities(world: GenesisWorld,
                      settlements: List[SettlementCandidate],
                      cultures: CulturalHistory,
                      trade: TradeNetwork,
                      cfg: Optional[PolityConfig] = None
                      ) -> PolityMap:
    """Aggregate settlements into polities + assign territory.

    Pipeline :
      1. Cluster settlements by culture similarity (union-find).
      2. For each cluster :
           capital = member with largest trade weight
           avg_culture = mean of member cultures
           color = culture_to_rgb(avg_culture)
      3. Voronoi assignment of macro land cells.

    Returns a :class:`PolityMap`.
    """
    cfg = cfg or PolityConfig()
    n = len(settlements)
    if n == 0:
        R = world.params.resolution
        return PolityMap(
            polities=[],
            polity_id_grid=np.full((R, R), -1, dtype=np.int32),
            n_polities=0, total_population=0.0,
        )

    weights = trade.weights
    clusters = _cluster_settlements(settlements, cultures.final,
                                       weights, cfg)
    # Build polity-of-settlement lookup (idx -> polity_id).
    polity_of_settlement = [-1] * n
    polities: List[Polity] = []
    for pid, member_idxs in enumerate(clusters):
        if not member_idxs:
            continue
        # Capital = member with highest weight.
        capital_idx = max(member_idxs, key=lambda i: float(weights[i]))
        member_ranks = [int(settlements[i].rank) for i in member_idxs]
        avg_culture = cultures.final[member_idxs].mean(axis=0)
        color = culture_to_rgb(avg_culture)
        population = float(sum(float(weights[i]) for i in member_idxs))
        polity = Polity(
            polity_id=pid,
            capital_rank=int(settlements[capital_idx].rank),
            member_ranks=member_ranks,
            population=population,
            avg_culture=avg_culture.copy(),
            color_rgb=color,
        )
        for i in member_idxs:
            polity_of_settlement[i] = pid
        polities.append(polity)

    # Settlements that fell through (size below min) get a sentinel id.
    # Shouldn't happen with min_polity_size=1 default, but handle.
    for i, pid in enumerate(polity_of_settlement):
        if pid < 0:
            polity_of_settlement[i] = 0  # default to first polity

    # Voronoi.
    grid = _compute_voronoi(world, settlements, polity_of_settlement,
                              weights, cfg.voronoi_weight_exp)

    # Compute territory masks + biome counts + cell counts.
    for polity in polities:
        mask = (grid == polity.polity_id)
        polity.territory_mask = mask
        polity.territory_cells = int(mask.sum())
        biomes_inside = world.biome[mask]
        if biomes_inside.size > 0:
            vals, counts = np.unique(biomes_inside, return_counts=True)
            polity.biome_counts = {int(b): int(c)
                                     for b, c in zip(vals, counts)}

    total_pop = sum(p.population for p in polities)
    return PolityMap(
        polities=polities,
        polity_id_grid=grid,
        n_polities=len(polities),
        total_population=float(total_pop),
    )


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------

def render_polities(world: GenesisWorld,
                      polity_map: PolityMap,
                      settlements: List[SettlementCandidate],
                      network: Optional[RoadNetwork] = None,
                      *,
                      path: Optional[str] = None,
                      territory_alpha: float = 0.55,
                      draw_borders: bool = True,
                      border_rgb: Tuple[int, int, int] = (30, 30, 30),
                      draw_roads: bool = True,
                      road_rgb: Tuple[int, int, int] = (180, 180, 180),
                      draw_capitals: bool = True,
                      capital_rgb: Tuple[int, int, int] = (255, 255, 255),
                      capital_radius_px: int = 2,
                      ) -> np.ndarray:
    """Render the macro world + polity territories + borders + roads + capitals.

    Each polity's territory is blended over the biome map with
    ``territory_alpha`` (0 = no tint, 1 = solid colour). Borders are
    drawn where two adjacent cells belong to different polities.
    """
    from engine.world_render import (render_macro_world, MacroRenderOptions,
                                       _save_png)

    rgb = render_macro_world(world, options=MacroRenderOptions(
        draw_rivers=True, draw_plate_boundaries=False)).astype(np.float32)
    R = rgb.shape[0]

    # Tint each polity's territory.
    for polity in polity_map.polities:
        if polity.territory_cells == 0:
            continue
        tint = np.array(polity.color_rgb, dtype=np.float32)
        mask = polity.territory_mask
        rgb[mask] = ((1.0 - territory_alpha) * rgb[mask]
                      + territory_alpha * tint)

    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    if draw_borders:
        grid = polity_map.polity_id_grid
        # Cell (i, j) is a border if any 4-neighbour has a different
        # polity_id (and both are not ocean).
        border = np.zeros_like(grid, dtype=bool)
        for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            shifted = np.roll(grid, (di, dj), axis=(0, 1))
            border |= (shifted != grid) & (grid >= 0) & (shifted >= 0)
        rgb[border] = np.array(border_rgb, dtype=np.uint8)

    if draw_roads and network is not None:
        rgb[network.road_mask] = np.array(road_rgb, dtype=np.uint8)

    if draw_capitals:
        capital_idx_by_rank = {c.rank: i for i, c in enumerate(settlements)}
        for polity in polity_map.polities:
            idx = capital_idx_by_rank.get(polity.capital_rank)
            if idx is None:
                continue
            sett = settlements[idx]
            cy = sett.macro_iy; cx = sett.macro_ix
            r = max(0, int(capital_radius_px))
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    if di * di + dj * dj > r * r:
                        continue
                    ni = cy + di; nj = cx + dj
                    if 0 <= ni < R and 0 <= nj < R:
                        rgb[ni, nj] = np.array(capital_rgb, dtype=np.uint8)

    if path is not None:
        _save_png(rgb, path)
    return rgb


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def polity_summary(polity_map: PolityMap) -> Dict[str, object]:
    """Diagnostic dict : per-polity stats + global aggregates."""
    if polity_map.n_polities == 0:
        return {"n_polities": 0}
    rows = []
    for p in polity_map.polities:
        rows.append({
            "polity_id": p.polity_id,
            "capital_rank": p.capital_rank,
            "n_members": len(p.member_ranks),
            "members": p.member_ranks,
            "population": round(float(p.population), 4),
            "territory_cells": p.territory_cells,
            "color_rgb": p.color_rgb,
            "dominant_biome": (max(p.biome_counts,
                                     key=lambda k: p.biome_counts[k])
                                if p.biome_counts else -1),
        })
    rows.sort(key=lambda r: -r["population"])
    return {
        "n_polities": polity_map.n_polities,
        "total_population": round(float(polity_map.total_population), 4),
        "polities": rows,
    }
