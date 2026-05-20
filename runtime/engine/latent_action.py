"""Latent action space — continuous genome vector → soft ActionKind mapping.

L'exécution reste l'ABI ``ActionKind`` ; le choix émerge d'un vecteur latent
dérivé des gènes cognition (pas d'enum fixe en tête de policy).
"""
from __future__ import annotations

import math
from typing import Tuple

import numpy as np

from engine.genome import GENE_GROUP_COGNITION
from engine.neat_brain import CORE_ACTIONS, N_ACTIONS, _tile_genes

LATENT_DIM = 4


def genome_latent(genome_row: np.ndarray) -> np.ndarray:
    """4-D latent in [-1, 1] from cognition genes (deterministic)."""
    g = np.tanh(genome_row[GENE_GROUP_COGNITION].astype(np.float32) * 0.35)
    v = _tile_genes(g, LATENT_DIM)
    return np.tanh(v).astype(np.float32)


def latent_temperature(latent: np.ndarray) -> float:
    """Softmax temperature from latent[3] — higher = more exploration."""
    return float(0.35 + 0.9 * (0.5 * (latent[3] + 1.0)))


def scores_to_action_index(
    scores: np.ndarray,
    latent: np.ndarray,
    *,
    prf_u: float,
) -> Tuple[int, float]:
    """Deterministic stochastic policy: softmax sample via PRF uniform."""
    temp = latent_temperature(latent)
    s = scores.astype(np.float64) / max(temp, 0.05)
    s -= s.max()
    exp_s = np.exp(s)
    probs = exp_s / exp_s.sum()
    u = float(prf_u) % 1.0
    cum = 0.0
    idx = int(N_ACTIONS - 1)
    for i, p in enumerate(probs):
        cum += float(p)
        if u <= cum:
            idx = i
            break
    conf = float(probs[idx])
    return idx, conf


def latent_walk_offset(latent: np.ndarray, base_heading: float, scale_m: float = 30.0) -> Tuple[float, float]:
    """Continuous locomotion bias (latent[0], latent[1]) in world metres."""
    ang = base_heading + float(latent[0]) * math.pi * 0.5
    dist = scale_m * (0.25 + 0.75 * abs(float(latent[1])))
    return math.cos(ang) * dist, math.sin(ang) * dist


__all__ = [
    "LATENT_DIM",
    "genome_latent",
    "latent_temperature",
    "scores_to_action_index",
    "latent_walk_offset",
]
