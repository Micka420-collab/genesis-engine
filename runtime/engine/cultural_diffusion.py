"""Genesis Engine — Wave 31 cultural diffusion via trade network.

Each settlement receives an initial **culture vector** (D-dimensional)
sampled deterministically from ``prf_rng``. The vector diffuses to
neighbours along the Wave 29 road network, **weighted by Wave 30 trade
flow volumes**. After K iterations, settlements connected by heavy
trade share similar cultures ; isolated villages diverge — emergent
cultural blocs.

This is the same diffusion equation as a graph Laplacian heat kernel :

    culture_i(t+1) = (1 − α) · culture_i(t)
                    + α · Σ_j (flow_ij / Σ_k flow_ik) · culture_j(t)
                    + ε · innovation_noise

Where :
  - α : ``diffusion_rate`` (typical 0.1-0.3)
  - ε : ``innovation_rate`` (small drift, keeps cultures from full collapse)

The model captures the classic anthropological observation : cultures
diffuse through trade contact. Greek koine spread along the Mediterranean
trade routes ; Latin loanwords entered Germanic via Hanseatic-style
networks ; cuisines fuse along caravanserai paths.

Visualisation
-------------

The 5-D culture vector projects onto RGB via its first 3 dimensions
(or any chosen triplet). Two settlements with similar cultures land on
similar colours ; blocs become visible as colour clusters on the map.

Determinism
-----------

Initial cultures via ``prf_rng((seed, "culture", "init"), [rank, d])``.
Diffusion math is deterministic (no RNG inside the iterations). Two
runs with identical inputs produce bit-identical final cultures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.settlement_emergence import SettlementCandidate
from engine.road_network import RoadNetwork
from engine.trade_flow import TradeNetwork


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


# ---------------------------------------------------------------------------
# Configuration + data
# ---------------------------------------------------------------------------

@dataclass
class CulturalConfig:
    """Hyper-parameters of the diffusion process."""
    n_dimensions: int = 5            # culture vector dimensionality
    n_iterations: int = 50           # diffusion steps
    diffusion_rate: float = 0.15     # α : strength of neighbour pull per step
    innovation_rate: float = 0.005   # ε : small random drift per step
    initial_seed: int = 0xCAFE_C0DE


@dataclass
class CulturalHistory:
    """Trajectory of the diffusion process — per-step snapshots optional."""
    n_settlements: int = 0
    n_dimensions: int = 0
    iterations_run: int = 0
    initial: np.ndarray = field(default_factory=lambda: np.empty(0))
    final: np.ndarray = field(default_factory=lambda: np.empty(0))
    convergence_metric: float = 0.0  # mean shift between init and final


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def initialize_cultures(settlements: List[SettlementCandidate],
                         cfg: Optional[CulturalConfig] = None
                         ) -> np.ndarray:
    """Seed each settlement with a fresh random culture vector.

    Each component ∈ [0, 1]. Deterministic via
    ``prf_rng((cfg.initial_seed, "culture_init"), [rank, dim])``.

    Returns (N, D) float32 array.
    """
    cfg = cfg or CulturalConfig()
    n = len(settlements)
    d = cfg.n_dimensions
    cultures = np.zeros((n, d), dtype=np.float32)
    for i, sett in enumerate(settlements):
        rng = prf_rng(cfg.initial_seed,
                      ["culture_init"], [int(sett.rank)])
        cultures[i] = rng.random(d, dtype=np.float32)
    return cultures


# ---------------------------------------------------------------------------
# Diffusion step
# ---------------------------------------------------------------------------

def _build_diffusion_matrix(settlements: List[SettlementCandidate],
                              trade: TradeNetwork) -> np.ndarray:
    """Row-stochastic matrix : row i sums to 1 over its weighted neighbours.

    P[i, j] = flow_ij / Σ_k flow_ik

    P[i, i] = 0 (no self-loop in the off-diagonal part — the diffusion
    rule itself blends current state via (1 − α)). Isolated nodes get
    P[i, i] = 1 (degenerate row → stays the same).
    """
    n = len(settlements)
    flows = trade.flows.copy()
    np.fill_diagonal(flows, 0.0)
    row_sum = flows.sum(axis=1)
    P = np.zeros_like(flows)
    nonzero = row_sum > 0
    P[nonzero] = flows[nonzero] / row_sum[nonzero, None]
    # Isolated rows : map to identity (no diffusion).
    isolated = ~nonzero
    if isolated.any():
        for i in np.where(isolated)[0]:
            P[i, i] = 1.0
    return P.astype(np.float32)


def step_cultural_diffusion(cultures: np.ndarray,
                              diffusion_matrix: np.ndarray,
                              cfg: CulturalConfig,
                              step_seed: int,
                              ) -> np.ndarray:
    """One diffusion step. Returns new (N, D) cultures.

    Update rule :
        culture_i(t+1) = (1 − α) · culture_i(t)
                        + α · Σ_j P[i, j] · culture_j(t)
                        + ε · noise   (rng-drawn, prf_rng-keyed by step)

    The noise is small (default ε=0.005). It prevents global collapse
    onto a single point — without innovation, the system would converge
    to the average and lose all distinction.
    """
    n, d = cultures.shape
    neighbour_blend = diffusion_matrix @ cultures
    blended = (1.0 - cfg.diffusion_rate) * cultures \
               + cfg.diffusion_rate * neighbour_blend
    if cfg.innovation_rate > 0:
        rng = prf_rng(cfg.initial_seed,
                      ["culture_step"], [int(step_seed)])
        noise = (rng.random((n, d), dtype=np.float32) - 0.5) * 2.0
        blended += noise * cfg.innovation_rate
    # Clip to [0, 1] for visualisation stability.
    return np.clip(blended, 0.0, 1.0).astype(np.float32)


def run_cultural_diffusion(settlements: List[SettlementCandidate],
                             trade: TradeNetwork,
                             cfg: Optional[CulturalConfig] = None,
                             ) -> CulturalHistory:
    """Full N-step diffusion. Returns :class:`CulturalHistory`.

    The history holds the initial and final culture matrices + a
    convergence metric (mean L2 shift). All deterministic.
    """
    cfg = cfg or CulturalConfig()
    initial = initialize_cultures(settlements, cfg)
    if len(settlements) == 0:
        return CulturalHistory(
            n_settlements=0, n_dimensions=cfg.n_dimensions,
            iterations_run=0,
            initial=initial.copy(), final=initial.copy(),
            convergence_metric=0.0,
        )
    P = _build_diffusion_matrix(settlements, trade)
    current = initial.copy()
    for step in range(cfg.n_iterations):
        current = step_cultural_diffusion(current, P, cfg, step_seed=step)
    diff = current - initial
    convergence = float(np.linalg.norm(diff, axis=1).mean())
    return CulturalHistory(
        n_settlements=len(settlements),
        n_dimensions=cfg.n_dimensions,
        iterations_run=cfg.n_iterations,
        initial=initial.copy(),
        final=current.copy(),
        convergence_metric=convergence,
    )


# ---------------------------------------------------------------------------
# Cluster detection
# ---------------------------------------------------------------------------

def detect_cultural_blocs(cultures: np.ndarray,
                            *,
                            similarity_threshold: float = 0.20
                            ) -> List[List[int]]:
    """Group settlements into blocs by pairwise distance.

    Two settlements belong to the same bloc iff ``L2(culture_a, culture_b)
    < similarity_threshold``. Greedy union-find.

    Returns list of clusters (each cluster = list of settlement indices).
    Singletons included.
    """
    n = cultures.shape[0]
    if n == 0:
        return []
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            d = float(np.linalg.norm(cultures[i] - cultures[j]))
            if d < similarity_threshold:
                union(i, j)
    # Group by root.
    groups: Dict[int, List[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------

def culture_to_rgb(culture_vec: np.ndarray) -> Tuple[int, int, int]:
    """Project a D-dim culture vector to RGB.

    Uses dims [0, 1, 2] if D >= 3, else maps the first dim to gray. Each
    coordinate in [0, 1] maps linearly to [0, 255].
    """
    v = np.clip(culture_vec, 0.0, 1.0)
    if v.shape[0] >= 3:
        r = int(round(v[0] * 255))
        g = int(round(v[1] * 255))
        b = int(round(v[2] * 255))
    else:
        gray = int(round(v[0] * 255))
        r = g = b = gray
    return (r, g, b)


def render_cultural_map(world,
                          network: RoadNetwork,
                          settlements: List[SettlementCandidate],
                          history: CulturalHistory,
                          *,
                          path: Optional[str] = None,
                          dot_radius_px: int = 3,
                          paint_roads_neutral: bool = True,
                          road_rgb: Tuple[int, int, int] = (140, 140, 140),
                          ) -> np.ndarray:
    """Overlay culture-coloured settlement dots on the macro map.

    Each dot's RGB is :func:`culture_to_rgb` of its final culture vector.
    Roads are painted neutral grey by default so the cultural colours
    pop visually.

    Returns (R, R, 3) uint8. Optionally writes PNG.
    """
    from engine.world_render import (render_macro_world, MacroRenderOptions,
                                       _save_png)

    rgb = render_macro_world(world, options=MacroRenderOptions(
        draw_rivers=True, draw_plate_boundaries=False))
    R = rgb.shape[0]
    if paint_roads_neutral and hasattr(network, "road_mask"):
        rgb[network.road_mask] = np.array(road_rgb, dtype=np.uint8)

    if history.final.shape[0] != len(settlements):
        return rgb

    for i, sett in enumerate(settlements):
        col = culture_to_rgb(history.final[i])
        col_arr = np.array(col, dtype=np.uint8)
        cy, cx = sett.macro_iy, sett.macro_ix
        r = max(0, int(dot_radius_px))
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if di * di + dj * dj > r * r:
                    continue
                ni = cy + di; nj = cx + dj
                if 0 <= ni < R and 0 <= nj < R:
                    rgb[ni, nj] = col_arr

    if path is not None:
        _save_png(rgb, path)
    return rgb


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def cultural_summary(settlements: List[SettlementCandidate],
                       history: CulturalHistory,
                       *,
                       similarity_threshold: float = 0.20
                       ) -> Dict[str, object]:
    """Diagnostic dict : bloc count, dominant bloc, convergence."""
    if history.n_settlements == 0:
        return {"n": 0}
    blocs = detect_cultural_blocs(history.final,
                                    similarity_threshold=similarity_threshold)
    bloc_sizes = sorted([len(b) for b in blocs], reverse=True)
    return {
        "n_settlements": history.n_settlements,
        "n_dimensions": history.n_dimensions,
        "iterations_run": history.iterations_run,
        "convergence_metric": round(history.convergence_metric, 4),
        "n_blocs": len(blocs),
        "bloc_sizes": bloc_sizes,
        "dominant_bloc_size": bloc_sizes[0] if bloc_sizes else 0,
        "singleton_count": sum(1 for s in bloc_sizes if s == 1),
    }
