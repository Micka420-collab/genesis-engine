"""Genesis Engine — Wave 29 road network emergence via Dijkstra.

Connects Wave 28 settlements with a minimum-spanning-tree of
Dijkstra-shortest paths on a per-cell cost field derived from
terrain difficulty.

Cost field per macro cell (additive, all ≥ 1) :

  base                : 1.0
  + slope             : clip(|∇elev|, 0, 50) * 0.4      # mountains expensive
  + ocean             : 200.0  (cells below sea level)  # roads avoid water
  + convergent border : +5.0   (Wave 17 hazard)
  + low-food bonus    : (1 - food_npp) * 0.3            # bare/desert costlier
  + river bonus       : +2.0   (need bridges)
  + cliff penalty     : if |∇elev| > 80 m/cell -> +20

The minimum spanning tree (MST) connects all N settlements with N-1
edges, each edge = shortest path between its endpoints via Dijkstra.
Kruskal's algorithm with union-find decides which edges enter the MST.

The result is a **road_mask** (R, R) bool array marking every cell the
road network touches, plus per-edge path metadata for diagnostics.

Determinism : Dijkstra and Kruskal are pure functions (no RNG). Two
runs with identical settlements list → identical road network bit-for-
bit.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.world_genesis import (GenesisWorld, BOUND_CONVERGENT)
from engine.settlement_emergence import (BIOME_FOOD_POTENTIAL,
                                           SettlementCandidate)


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# ---------------------------------------------------------------------------
# Configuration + result types
# ---------------------------------------------------------------------------

@dataclass
class RoadCostConfig:
    """Hyper-parameters of the cost field."""
    base: float = 1.0
    slope_weight: float = 0.4
    slope_clip: float = 50.0
    cliff_threshold: float = 80.0
    cliff_penalty: float = 20.0
    ocean_penalty: float = 200.0
    convergent_penalty: float = 5.0
    river_penalty: float = 2.0
    low_food_weight: float = 0.3


@dataclass
class RoadEdge:
    """One edge in the minimum-spanning-tree of settlements."""
    from_rank: int
    to_rank: int
    from_ij: Tuple[int, int]   # (iy, ix) in macro grid
    to_ij: Tuple[int, int]
    length_cells: int
    cost_total: float
    length_km: float
    path: List[Tuple[int, int]] = field(default_factory=list)  # (iy, ix) sequence


@dataclass
class RoadNetwork:
    """Output of :func:`build_road_network`."""
    cost_field: np.ndarray            # (R, R) float32
    road_mask: np.ndarray             # (R, R) bool, True on any path cell
    edges: List[RoadEdge] = field(default_factory=list)
    total_length_km: float = 0.0
    total_cost: float = 0.0
    n_settlements: int = 0


# ---------------------------------------------------------------------------
# Cost field
# ---------------------------------------------------------------------------

def compute_cost_field(world: GenesisWorld,
                         cfg: Optional[RoadCostConfig] = None
                         ) -> np.ndarray:
    """Per-cell road-building cost. Higher = harder to build/cross.

    Returns (R, R) float32. Always ≥ 1.0. Ocean ~200. Mountains 30+.
    Flat plain near food ~1.5.
    """
    cfg = cfg or RoadCostConfig()
    elev = world.elevation_m.astype(np.float32)

    gx = (np.roll(elev, -1, 1) - np.roll(elev, 1, 1)) * 0.5
    gy = (np.roll(elev, -1, 0) - np.roll(elev, 1, 0)) * 0.5
    slope = np.sqrt(gx * gx + gy * gy)

    cost = np.full_like(elev, cfg.base, dtype=np.float32)
    cost += np.clip(slope, 0.0, cfg.slope_clip) * cfg.slope_weight
    cost = np.where(slope > cfg.cliff_threshold,
                     cost + cfg.cliff_penalty, cost)
    cost = np.where(elev <= world.params.sea_level_m,
                     cost + cfg.ocean_penalty, cost)
    # Convergent neighbours (Wave 17 hazard).
    bk = world.boundary_kind
    conv = (bk == BOUND_CONVERGENT)
    if conv.any():
        # dilate convergent by 1 cell.
        near_conv = conv.copy()
        for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            near_conv |= np.roll(conv, (di, dj), axis=(0, 1))
        cost = np.where(near_conv, cost + cfg.convergent_penalty, cost)
    # River : a small penalty (bridges needed) but cells next to river
    # are also valuable as transport corridors -> net small penalty only
    # on the river cell itself.
    if hasattr(world, "river_mask"):
        riv = world.river_mask.astype(bool)
        if riv.any():
            cost = np.where(riv, cost + cfg.river_penalty, cost)
    # Low-food bonus : barren land is moderately costlier (no shelter, no
    # resupply for road crews).
    biome = world.biome
    food = np.zeros_like(elev, dtype=np.float32)
    for b_id, npp in BIOME_FOOD_POTENTIAL.items():
        m = (biome == b_id)
        if m.any():
            food[m] = float(npp)
    cost += (1.0 - food) * cfg.low_food_weight

    return cost.astype(np.float32)


# ---------------------------------------------------------------------------
# Dijkstra single-source shortest path
# ---------------------------------------------------------------------------

# 8-neighbour offsets : (di, dj, dist_factor)
_NEIGHBOURS_8 = [
    (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
    (-1, -1, np.sqrt(2.0)), (-1, 1, np.sqrt(2.0)),
    (1, -1, np.sqrt(2.0)), (1, 1, np.sqrt(2.0)),
]


def dijkstra_path(cost: np.ndarray,
                    start: Tuple[int, int],
                    goal: Tuple[int, int]
                    ) -> Tuple[List[Tuple[int, int]], float]:
    """Shortest weighted-cost path from ``start`` to ``goal`` in (iy, ix).

    Uses 8-connectivity with √2 diagonal distance multiplier. Stops as
    soon as ``goal`` is popped. Returns ``(path, total_cost)``. Path is
    a list of (iy, ix) cells including both endpoints. Empty list if
    no path found (should never happen on a finite cost field).
    """
    R = cost.shape[0]
    sy, sx = start
    gy, gx = goal
    if (sy, sx) == (gy, gx):
        return [(sy, sx)], 0.0

    # Distance matrix; predecessors for path reconstruction.
    INF = float("inf")
    dist = np.full((R, R), INF, dtype=np.float32)
    dist[sy, sx] = 0.0
    prev = np.full((R, R, 2), -1, dtype=np.int32)
    visited = np.zeros((R, R), dtype=bool)

    heap: List[Tuple[float, int, int]] = [(0.0, sy, sx)]
    while heap:
        d, y, x = heapq.heappop(heap)
        if visited[y, x]:
            continue
        visited[y, x] = True
        if (y, x) == (gy, gx):
            break
        for di, dj, df in _NEIGHBOURS_8:
            ny = y + di; nx = x + dj
            if 0 <= ny < R and 0 <= nx < R and not visited[ny, nx]:
                nd = d + float(cost[ny, nx]) * df
                if nd < dist[ny, nx]:
                    dist[ny, nx] = nd
                    prev[ny, nx, 0] = y
                    prev[ny, nx, 1] = x
                    heapq.heappush(heap, (nd, ny, nx))

    # Reconstruct path.
    if dist[gy, gx] == INF:
        return [], INF
    path: List[Tuple[int, int]] = []
    cy, cx = gy, gx
    while (cy, cx) != (sy, sx):
        path.append((cy, cx))
        py, px = int(prev[cy, cx, 0]), int(prev[cy, cx, 1])
        if py < 0:
            return [], INF
        cy, cx = py, px
    path.append((sy, sx))
    path.reverse()
    return path, float(dist[gy, gx])


# ---------------------------------------------------------------------------
# Kruskal MST over settlements
# ---------------------------------------------------------------------------

class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_road_network(world: GenesisWorld,
                         settlements: List[SettlementCandidate],
                         *,
                         cfg: Optional[RoadCostConfig] = None,
                         ) -> RoadNetwork:
    """Build a Kruskal-MST road network connecting all ``settlements``.

    1. Compute the per-cell cost field.
    2. Pre-compute Dijkstra shortest paths between every pair of
       settlements (O(N² × N²log N)).
    3. Sort pairs by cost ascending.
    4. Apply Kruskal : add edges in order that connect new components,
       until all settlements are in one component (N-1 edges).

    Returns a :class:`RoadNetwork` with the cost field, road_mask,
    edges + total length.

    Determinism : zero RNG, identical inputs → identical output.
    """
    cfg = cfg or RoadCostConfig()
    n = len(settlements)
    network = RoadNetwork(
        cost_field=compute_cost_field(world, cfg),
        road_mask=np.zeros((world.params.resolution,
                              world.params.resolution), dtype=bool),
        n_settlements=n,
    )
    if n < 2:
        return network

    R = world.params.resolution
    cell_km = world.params.map_size_km / R

    # Pre-compute all-pairs shortest paths (Dijkstra from each).
    pairs: List[Tuple[float, int, int, List[Tuple[int, int]]]] = []
    for i in range(n):
        for j in range(i + 1, n):
            si = (settlements[i].macro_iy, settlements[i].macro_ix)
            sj = (settlements[j].macro_iy, settlements[j].macro_ix)
            path, cost_ij = dijkstra_path(network.cost_field, si, sj)
            if not path:
                continue
            pairs.append((cost_ij, i, j, path))

    # Sort pairs ascending by cost.
    pairs.sort(key=lambda p: p[0])

    uf = _UnionFind(n)
    edges_added = 0
    target_edges = n - 1
    for cost_ij, i, j, path in pairs:
        if edges_added >= target_edges:
            break
        if not uf.union(i, j):
            continue
        # Add edge.
        path_cells = len(path)
        # Approximate path length in km.
        length_km = 0.0
        for k in range(1, len(path)):
            dy = path[k][0] - path[k - 1][0]
            dx = path[k][1] - path[k - 1][1]
            length_km += np.sqrt(dy * dy + dx * dx) * cell_km
        edge = RoadEdge(
            from_rank=settlements[i].rank,
            to_rank=settlements[j].rank,
            from_ij=(settlements[i].macro_iy, settlements[i].macro_ix),
            to_ij=(settlements[j].macro_iy, settlements[j].macro_ix),
            length_cells=path_cells,
            cost_total=float(cost_ij),
            length_km=float(length_km),
            path=path,
        )
        network.edges.append(edge)
        network.total_length_km += length_km
        network.total_cost += float(cost_ij)
        for (py, px) in path:
            network.road_mask[py, px] = True
        edges_added += 1

    return network


# ---------------------------------------------------------------------------
# Render overlay
# ---------------------------------------------------------------------------

def render_road_network(world: GenesisWorld,
                          network: RoadNetwork,
                          settlements: List[SettlementCandidate],
                          *,
                          path: Optional[str] = None,
                          road_rgb: Tuple[int, int, int] = (200, 50, 50),
                          settlement_rgb: Tuple[int, int, int] = (255, 80, 200),
                          settlement_radius_px: int = 1,
                          ) -> np.ndarray:
    """Render the macro world + road network + settlement dots.

    Returns (R, R, 3) uint8. Optionally writes PNG.
    """
    from engine.world_render import (render_macro_world, MacroRenderOptions,
                                       _save_png)

    rgb = render_macro_world(world, options=MacroRenderOptions(
        draw_rivers=True, draw_plate_boundaries=False))
    R = rgb.shape[0]
    rd = np.array(road_rgb, dtype=np.uint8)
    sd = np.array(settlement_rgb, dtype=np.uint8)

    # Roads (paint mask).
    rgb[network.road_mask] = rd
    # Settlements (over roads).
    r = max(0, int(settlement_radius_px))
    for cand in settlements:
        cy = cand.macro_iy
        cx = cand.macro_ix
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if di * di + dj * dj > r * r:
                    continue
                ni = cy + di
                nj = cx + dj
                if 0 <= ni < R and 0 <= nj < R:
                    rgb[ni, nj] = sd
    if path is not None:
        _save_png(rgb, path)
    return rgb


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def network_summary(network: RoadNetwork) -> Dict[str, object]:
    """One-line diagnostic dict."""
    return {
        "n_settlements": network.n_settlements,
        "n_edges": len(network.edges),
        "road_cells": int(network.road_mask.sum()),
        "total_length_km": round(network.total_length_km, 1),
        "total_cost": round(network.total_cost, 1),
        "mean_edge_length_km": (
            round(network.total_length_km / max(len(network.edges), 1), 1)),
    }
