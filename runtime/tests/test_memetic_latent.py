"""Memetic engine + latent action policy."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

import numpy as np

from engine.emergence_stack import wire_emergence_v2
from engine.genome import attach_genome
from engine.latent_action import genome_latent, scores_to_action_index
from engine.memetic_engine import install_memetic_engine, memetic_snapshot
from engine.sim import Simulation, SimConfig


def test_genome_latent_bounded():
    cfg = SimConfig(name="lat", seed=1, founders=4, max_agents=10, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    attach_genome(sim.agents, cfg.seed)
    v = genome_latent(sim.agents.genome[0])
    assert v.shape == (4,)
    assert np.all(v >= -1.0) and np.all(v <= 1.0)


def test_scores_to_action_index_deterministic():
    scores = np.array([1.0, 0.2, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    latent = np.array([0.0, 0.0, 0.0, 0.5], dtype=np.float32)
    a, _ = scores_to_action_index(scores, latent, prf_u=0.25)
    b, _ = scores_to_action_index(scores, latent, prf_u=0.25)
    assert a == b
    assert 0 <= a < len(scores)


def test_memetic_install_and_metrics():
    cfg = SimConfig(
        name="mem",
        seed=99,
        founders=8,
        max_agents=24,
        bounds_km=(0.35, 0.35),
        emergence_subsystems=True,
        hydrology_mode="stub",
    )
    sim = Simulation(cfg)
    sim.bootstrap()
    attach_genome(sim.agents, cfg.seed)
    wire_emergence_v2(sim, hydrology_mode="stub", memetic=True)
    for _ in range(40):
        sim.step()
    snap = memetic_snapshot(sim)
    assert "imitations_total" in snap
    from engine.emergence_metrics import compute_emergence_metrics
    m = compute_emergence_metrics(sim)
    assert "memetic_imitations" in m
    assert "hydrology" in m
