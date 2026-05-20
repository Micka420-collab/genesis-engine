"""Genesis Engine — Wave 30 trade flow gravity model.

Computes **emergent inter-settlement trade volumes** using the
gravity / Reilly / Wilson model from urban economics :

    flow_ij = K · (weight_i · weight_j) / (distance_ij ^ β)

This is the same equation Newton wrote for gravitation, repurposed by
Stewart (1948) and Wilson (1967) for spatial interaction modelling.
It captures the empirical fact that two large cities far apart trade
roughly as much as two small cities nearby.

Inputs (all from prior waves) :

  - Settlements : list of :class:`SettlementCandidate` from Wave 28.
  - Road network : MST of paths from Wave 29.
  - World macro : Wave 16 elevation + biome (for food capacity proxy).

The settlement **weight** (a population proxy) is :

    weight_i = settlement_score_i · (1 + bias · biome_NPP_at_site)

The **distance** is the road-network distance in km (Wave 29 edges),
*not* the Euclidean straight-line — because real-world trade follows
actual roads, not crow-flight.

Output is a (N, N) symmetric float32 flow matrix, normalised so that
``flows.max() == max_flow_volume``. Cells (i, j) where i and j are not
directly connected in the road MST stay zero.

Visualisation : :func:`render_trade_flows` colours each MST edge by
its flow magnitude (low-flow yellow → high-flow deep red), settlement
dots sized in proportion to their weight.

Determinism : pure-function. No RNG, no global state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.world_genesis import GenesisWorld
from engine.settlement_emergence import (BIOME_FOOD_POTENTIAL,
                                           SettlementCandidate)
from engine.road_network import RoadEdge, RoadNetwork


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# ---------------------------------------------------------------------------
# Configuration + data
# ---------------------------------------------------------------------------

@dataclass
class TradeConfig:
    """Hyper-parameters of the gravity flow model."""
    beta_distance: float = 1.6        # gravity exponent (1.5-2.0 typical)
    weight_floor: float = 0.01
    bias_food: float = 0.5            # food-rich sites get bonus weight
    max_flow_volume: float = 100.0    # output normalisation cap


@dataclass
class TradeNetwork:
    """Output of :func:`compute_trade_flows`."""
    weights: np.ndarray                  # (N,) float32 per-settlement
    flows: np.ndarray                    # (N, N) float32 symmetric, normalised
    edge_flow: Dict[Tuple[int, int], float] = field(default_factory=dict)
    n_settlements: int = 0
    total_volume: float = 0.0
    dominant_city_rank: int = -1


# ---------------------------------------------------------------------------
# Weight computation
# ---------------------------------------------------------------------------

def compute_settlement_weights(settlements: List[SettlementCandidate],
                                 world: GenesisWorld,
                                 cfg: Optional[TradeConfig] = None
                                 ) -> np.ndarray:
    """Per-settlement weight (population proxy).

    ``weight = max(score, floor) × (1 + bias · biome_NPP)``.
    Settlements with higher score AND food-rich biome get amplified
    weights. Returns (N,) float32.
    """
    cfg = cfg or TradeConfig()
    n = len(settlements)
    out = np.zeros(n, dtype=np.float32)
    for i, c in enumerate(settlements):
        npp = BIOME_FOOD_POTENTIAL.get(c.biome, 0.3)
        score = max(float(c.score), cfg.weight_floor)
        out[i] = score * (1.0 + cfg.bias_food * float(npp))
    return out


# ---------------------------------------------------------------------------
# Gravity flow computation
# ---------------------------------------------------------------------------

def compute_trade_flows(settlements: List[SettlementCandidate],
                          world: GenesisWorld,
                          network: RoadNetwork,
                          cfg: Optional[TradeConfig] = None
                          ) -> TradeNetwork:
    """Compute the (N, N) trade flow matrix using the gravity model.

    Only directly-connected pairs in the road network MST get nonzero
    flow. Edges not in the MST are NOT given indirect flow (this is a
    one-step model — for multi-hop redistribution, run a Markov chain
    on the matrix in a follow-up wave).

    Returns a :class:`TradeNetwork`. Flows are normalised so the max
    equals ``cfg.max_flow_volume``.
    """
    cfg = cfg or TradeConfig()
    n = len(settlements)
    weights = compute_settlement_weights(settlements, world, cfg)
    flows = np.zeros((n, n), dtype=np.float32)
    edge_flow: Dict[Tuple[int, int], float] = {}

    # Index settlements by rank for fast lookup.
    rank_to_idx = {c.rank: i for i, c in enumerate(settlements)}

    beta = float(cfg.beta_distance)
    for edge in network.edges:
        i = rank_to_idx.get(edge.from_rank)
        j = rank_to_idx.get(edge.to_rank)
        if i is None or j is None or i == j:
            continue
        dist = max(edge.length_km, 1.0)
        raw_flow = (float(weights[i]) * float(weights[j])) / (dist ** beta)
        flows[i, j] = raw_flow
        flows[j, i] = raw_flow

    # Normalise so the max equals max_flow_volume.
    if flows.max() > 0:
        flows = flows * (cfg.max_flow_volume / float(flows.max()))

    # Build per-edge flow lookup keyed by sorted (rank_a, rank_b).
    for edge in network.edges:
        i = rank_to_idx.get(edge.from_rank)
        j = rank_to_idx.get(edge.to_rank)
        if i is None or j is None or i == j:
            continue
        key = tuple(sorted((int(edge.from_rank), int(edge.to_rank))))
        edge_flow[key] = float(flows[i, j])

    total_volume = float(flows.sum() * 0.5)  # symmetric, count once
    dominant_idx = int(np.argmax(weights)) if n > 0 else -1
    dominant_rank = (settlements[dominant_idx].rank
                     if dominant_idx >= 0 else -1)

    return TradeNetwork(
        weights=weights,
        flows=flows,
        edge_flow=edge_flow,
        n_settlements=n,
        total_volume=total_volume,
        dominant_city_rank=int(dominant_rank),
    )


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------

def _flow_to_rgb(volume_frac: float) -> Tuple[int, int, int]:
    """Map normalised flow [0, 1] to RGB : pale yellow → deep red."""
    f = float(np.clip(volume_frac, 0.0, 1.0))
    # 0.0 = (255, 240, 100)  pale yellow
    # 0.5 = (255, 150,  60)  amber
    # 1.0 = (200,  40,  40)  deep red
    if f < 0.5:
        t = f / 0.5
        r = int(round(255 * (1 - t) + 255 * t))
        g = int(round(240 * (1 - t) + 150 * t))
        b = int(round(100 * (1 - t) + 60 * t))
    else:
        t = (f - 0.5) / 0.5
        r = int(round(255 * (1 - t) + 200 * t))
        g = int(round(150 * (1 - t) + 40 * t))
        b = int(round(60 * (1 - t) + 40 * t))
    return (r, g, b)


def render_trade_flows(world: GenesisWorld,
                         network: RoadNetwork,
                         settlements: List[SettlementCandidate],
                         trade: TradeNetwork,
                         *,
                         path: Optional[str] = None,
                         settlement_rgb_min: Tuple[int, int, int] = (240, 200, 240),
                         settlement_rgb_max: Tuple[int, int, int] = (255, 80, 200),
                         max_radius_px: int = 3,
                         ) -> np.ndarray:
    """Render the macro world + trade-coloured roads + weighted settlement dots.

    Each MST edge is painted in a colour proportional to its trade
    volume (low = pale yellow, high = deep red). Settlements are
    drawn as filled disks whose radius scales with their weight.

    Returns (R, R, 3) uint8. Optionally writes PNG.
    """
    from engine.world_render import (render_macro_world, MacroRenderOptions,
                                       _save_png)

    rgb = render_macro_world(world, options=MacroRenderOptions(
        draw_rivers=True, draw_plate_boundaries=False))
    R = rgb.shape[0]

    # Per-edge colour via edge_flow lookup.
    if trade.flows.max() > 0:
        flow_norm_factor = 1.0 / float(trade.flows.max())
    else:
        flow_norm_factor = 0.0
    rank_to_idx = {c.rank: i for i, c in enumerate(settlements)}

    for edge in network.edges:
        key = tuple(sorted((int(edge.from_rank), int(edge.to_rank))))
        vol = trade.edge_flow.get(key, 0.0)
        norm = vol * flow_norm_factor
        color = np.array(_flow_to_rgb(norm), dtype=np.uint8)
        for (py, px) in edge.path:
            if 0 <= py < R and 0 <= px < R:
                rgb[py, px] = color

    # Settlements : radius scaled by weight (1-max_radius_px).
    if len(settlements) > 0:
        max_w = float(trade.weights.max()) if trade.weights.size else 1.0
        max_w = max(max_w, 1e-6)
        min_rgb = np.array(settlement_rgb_min, dtype=np.float32)
        max_rgb = np.array(settlement_rgb_max, dtype=np.float32)
        for i, c in enumerate(settlements):
            w_norm = float(trade.weights[i]) / max_w
            radius = max(0, int(round(w_norm * max_radius_px)))
            color = (min_rgb * (1 - w_norm) + max_rgb * w_norm).astype(np.uint8)
            cy, cx = c.macro_iy, c.macro_ix
            for di in range(-radius, radius + 1):
                for dj in range(-radius, radius + 1):
                    if di * di + dj * dj > radius * radius:
                        continue
                    ni = cy + di; nj = cx + dj
                    if 0 <= ni < R and 0 <= nj < R:
                        rgb[ni, nj] = color

    if path is not None:
        _save_png(rgb, path)
    return rgb


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def trade_summary(settlements: List[SettlementCandidate],
                    trade: TradeNetwork) -> Dict[str, object]:
    """Diagnostic dict with top routes + dominant city info."""
    if trade.n_settlements == 0:
        return {"n": 0}
    rank_to_idx = {c.rank: i for i, c in enumerate(settlements)}
    # Top 5 edges by flow.
    edges_sorted = sorted(trade.edge_flow.items(),
                            key=lambda kv: kv[1], reverse=True)[:5]
    top_routes = []
    for (ra, rb), vol in edges_sorted:
        top_routes.append({
            "from_rank": int(ra), "to_rank": int(rb),
            "volume": round(float(vol), 2),
        })
    dom_idx = rank_to_idx.get(trade.dominant_city_rank, -1)
    dom_weight = (float(trade.weights[dom_idx])
                   if 0 <= dom_idx < len(trade.weights) else 0.0)
    return {
        "n_settlements": trade.n_settlements,
        "total_volume": round(float(trade.total_volume), 2),
        "weight_min": round(float(trade.weights.min()), 4),
        "weight_max": round(float(trade.weights.max()), 4),
        "dominant_city_rank": trade.dominant_city_rank,
        "dominant_city_weight": round(dom_weight, 4),
        "top_routes": top_routes,
    }
