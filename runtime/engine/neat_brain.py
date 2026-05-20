"""Genome-encoded neural policy (NEAT-inspired, no external RL).

Weights and action affinities are derived from the 256-D genome cognition
slice (genes 64–127). No backpropagation — selection pressure only.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

from engine.agent import ActionKind, AgentRegistry
from engine.cognition import (
    CRITICAL_THRESHOLD,
    Decision,
    Observation,
    _act_on,
)
from engine.genome import GENE_GROUP_COGNITION, cognitive_efficiency_for_row

# Subset of actions the latent policy can emit (world resolves targets).
CORE_ACTIONS: Tuple[int, ...] = (
    int(ActionKind.IDLE),
    int(ActionKind.WALK_TO),
    int(ActionKind.DRINK),
    int(ActionKind.EAT),
    int(ActionKind.FORAGE),
    int(ActionKind.EXPLORE),
    int(ActionKind.SPEAK),
    int(ActionKind.MATE),
    int(ActionKind.SHARE),
    int(ActionKind.FIGHT),
    int(ActionKind.SEEK_SHELTER),
    int(ActionKind.HUNT),
)

N_INPUTS = 12  # 8 drives + 4 perception flags
N_HIDDEN = 12
N_ACTIONS = len(CORE_ACTIONS)


def _obs_features(obs: Observation) -> np.ndarray:
    d = obs.drives
    extra = np.array([
        1.0 if obs.nearest.get("water") else 0.0,
        1.0 if obs.nearest.get("food") or obs.nearest.get("game") else 0.0,
        1.0 if obs.nearest.get("shelter") else 0.0,
        1.0 if obs.near_agents else 0.0,
    ], dtype=np.float32)
    return np.concatenate([d[:N_INPUTS].astype(np.float32), extra])


def _tile_genes(g: np.ndarray, n: int) -> np.ndarray:
    """Expand 64 cognition genes to arbitrary tensor length (deterministic)."""
    if n <= 0:
        return np.zeros(0, dtype=np.float32)
    if g.size >= n:
        return g[:n]
    reps = int(np.ceil(n / max(g.size, 1)))
    return np.tile(g, reps)[:n].astype(np.float32)


def _genome_weights(genome_row: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Deterministic weight tensors from cognition genes (64-D slice, tiled)."""
    g = np.tanh(genome_row[GENE_GROUP_COGNITION].astype(np.float32) * 0.35)
    w1_flat = _tile_genes(g, N_HIDDEN * N_INPUTS)
    w1 = w1_flat.reshape(N_HIDDEN, N_INPUTS)
    b1 = _tile_genes(g, N_HIDDEN)
    w2 = _tile_genes(g, N_ACTIONS * N_HIDDEN).reshape(N_ACTIONS, N_HIDDEN)
    b2 = _tile_genes(g, N_ACTIONS)
    return w1, b1, w2, b2


def forward_policy(genome_row: np.ndarray, features: np.ndarray) -> np.ndarray:
    """Return action logits (length N_ACTIONS)."""
    w1, b1, w2, b2 = _genome_weights(genome_row)
    h = np.tanh(w1 @ features + b1)
    logits = w2 @ h + b2
    return logits.astype(np.float32)


def action_signatures(genome_row: np.ndarray) -> np.ndarray:
    """Per-agent action affinity matrix (N_ACTIONS x N_INPUTS) from genome."""
    g = np.tanh(genome_row[GENE_GROUP_COGNITION].astype(np.float32) * 0.35)
    sig = _tile_genes(g, N_ACTIONS * N_INPUTS)
    return sig.reshape(N_ACTIONS, N_INPUTS)


def genome_action_index(
    genome_row: np.ndarray,
    features: np.ndarray,
    *,
    prf_u: float = 0.5,
) -> Tuple[int, float]:
    """Latent policy + soft action choice (continuous genome → discrete ABI)."""
    from engine.latent_action import genome_latent, scores_to_action_index

    logits = forward_policy(genome_row, features)
    sig = action_signatures(genome_row)
    drive_part = features[:N_INPUTS]
    affinity = sig @ drive_part
    scores = logits + 0.45 * affinity
    latent = genome_latent(genome_row)
    return scores_to_action_index(scores, latent, prf_u=prf_u)


def _targets_for_action(agents, row: int, obs: Observation, action: int) -> Decision:
    """Attach world targets for locomotion / interaction actions."""
    from engine.agent import DriveKind

    nearest = obs.nearest
    if action == int(ActionKind.IDLE):
        return Decision.idle()
    if action == int(ActionKind.EAT):
        return Decision(int(ActionKind.EAT), 0.0, 0.0, 0.85)
    if action == int(ActionKind.DRINK):
        t = nearest.get("water")
        if t and t.distance < 2.0:
            return Decision(int(ActionKind.DRINK), t.x, t.y, 0.9)
        if t:
            return Decision(int(ActionKind.WALK_TO), t.x, t.y, 0.75)
    if action in (int(ActionKind.FORAGE), int(ActionKind.HUNT)):
        t = nearest.get("food") or nearest.get("game")
        if t:
            ak = int(ActionKind.HUNT) if nearest.get("game") else int(ActionKind.FORAGE)
            return Decision(ak, t.x, t.y, 0.7)
    if action == int(ActionKind.SEEK_SHELTER):
        t = nearest.get("shelter")
        if t:
            return Decision(int(ActionKind.SEEK_SHELTER), t.x, t.y, 0.7)
    if action == int(ActionKind.SPEAK) and obs.near_agents:
        j = obs.near_agents[0]
        return Decision(int(ActionKind.SPEAK), float(agents.pos[j, 0]), float(agents.pos[j, 1]), 0.4, j)
    if action == int(ActionKind.MATE) and obs.near_agents:
        j = obs.near_agents[0]
        return Decision(int(ActionKind.MATE), float(agents.pos[j, 0]), float(agents.pos[j, 1]), 0.55, j)
    if action == int(ActionKind.SHARE) and obs.near_agents:
        j = obs.near_agents[0]
        return Decision(int(ActionKind.SHARE), float(agents.pos[j, 0]), float(agents.pos[j, 1]), 0.5, j)
    if action == int(ActionKind.FIGHT) and obs.near_agents:
        j = obs.near_agents[0]
        return Decision(int(ActionKind.FIGHT), float(agents.pos[j, 0]), float(agents.pos[j, 1]), 0.55, j)
    if action == int(ActionKind.EXPLORE):
        from engine.latent_action import genome_latent, latent_walk_offset
        g = agents.genome[row] if getattr(agents, "_genome_attached", False) else None
        if g is not None:
            lat = genome_latent(g)
            ox, oy = latent_walk_offset(lat, float(agents.heading[row]))
            return Decision(int(ActionKind.EXPLORE),
                            obs.pos[0] + ox, obs.pos[1] + oy, 0.35)
        ang = float(agents.heading[row]) + 0.5
        return Decision(int(ActionKind.EXPLORE),
                        obs.pos[0] + math.cos(ang) * 25.0,
                        obs.pos[1] + math.sin(ang) * 25.0, 0.35)
    if action == int(ActionKind.WALK_TO):
        for key in ("water", "food", "shelter", "game"):
            t = nearest.get(key)
            if t:
                return Decision(int(ActionKind.WALK_TO), t.x, t.y, 0.5)
        if obs.near_agents:
            j = obs.near_agents[0]
            return Decision(int(ActionKind.WALK_TO),
                            float(agents.pos[j, 0]), float(agents.pos[j, 1]), 0.4, j)
    return Decision.idle()


def genome_decide(agents: AgentRegistry, obs: Observation, sim) -> Decision:
    """Policy from DNA; critical physiology still overrides."""
    from engine.agent import DriveKind

    row = obs.row
    if not getattr(agents, "_genome_attached", False):
        return Decision.idle()

    for k in (DriveKind.THIRST, DriveKind.HUNGER, DriveKind.THERMAL,
              DriveKind.SLEEP, DriveKind.FATIGUE):
        if float(obs.drives[int(k)]) >= CRITICAL_THRESHOLD:
            d = _act_on(agents, row, obs, int(k))
            if d is not None:
                return d

    g = agents.genome[row]
    feats = _obs_features(obs)
    from engine.core import prf_rng
    prf_u = float(prf_rng(int(sim.cfg.seed), ["brain", "act"], [int(sim.tick), row]).random())
    idx, conf = genome_action_index(g, feats, prf_u=prf_u)
    eff = cognitive_efficiency_for_row(agents, row, sim)
    conf *= max(0.15, min(1.0, eff))
    action = CORE_ACTIONS[idx]
    d = _targets_for_action(agents, row, obs, action)
    d.confidence = float(min(1.0, conf))
    return d


__all__ = [
    "CORE_ACTIONS",
    "forward_policy",
    "genome_action_index",
    "genome_decide",
    "action_signatures",
]
