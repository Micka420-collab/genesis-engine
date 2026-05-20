"""Genome-encoded policy (NEAT-inspired, no external NEAT lib)."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

import numpy as np

from engine.emergent_action import install_emergent_cognition, restore_legacy_cognition
from engine.emergence_stack import wire_emergence_v2
from engine.genome import attach_genome
from engine.neat_brain import CORE_ACTIONS, forward_policy, genome_action_index, genome_decide
from engine.sim import Simulation, SimConfig
from engine.full_stack import wire_full_stack


def _sim_with_genome():
    cfg = SimConfig(
        name="neat",
        seed=7,
        founders=6,
        max_agents=20,
        bounds_km=(0.35, 0.35),
        emergence_subsystems=True,
        emergent_cognition=True,
    )
    sim = Simulation(cfg)
    sim.bootstrap()
    attach_genome(sim.agents, cfg.seed)
    wire_full_stack(sim, genesis=False, rust_worldgraph=False, five_cd=False, macro_commerce=False)
    return sim


def test_forward_policy_shape():
    sim = _sim_with_genome()
    g = sim.agents.genome[0]
    from engine.neat_brain import _obs_features
    from engine.cognition import perceive

    obs = perceive(sim.agents, 0, sim.streamer, grid=sim._grid, tick=sim.tick)
    logits = forward_policy(g, _obs_features(obs))
    assert logits.shape == (len(CORE_ACTIONS),)


def test_genome_action_index_in_range():
    sim = _sim_with_genome()
    g = sim.agents.genome[0]
    from engine.neat_brain import _obs_features
    from engine.cognition import perceive

    obs = perceive(sim.agents, 0, sim.streamer, grid=sim._grid, tick=sim.tick)
    idx, conf = genome_action_index(g, _obs_features(obs))
    assert 0 <= idx < len(CORE_ACTIONS)
    assert 0.0 < conf <= 1.0


def test_genome_decide_returns_decision():
    sim = _sim_with_genome()
    from engine.cognition import perceive

    obs = perceive(sim.agents, 0, sim.streamer, grid=sim._grid, tick=sim.tick)
    d = genome_decide(sim.agents, obs, sim)
    assert d.action in CORE_ACTIONS or int(d.action) >= 0


def test_wire_emergence_v2_idempotent():
    sim = _sim_with_genome()
    a = wire_emergence_v2(sim, genome_brain=True)
    b = wire_emergence_v2(sim, genome_brain=True)
    assert a["genome_brain"] and b["genome_brain"]
    install_emergent_cognition(sim, enable=True)
    for _ in range(15):
        sim.step()
    restore_legacy_cognition(sim)


def test_agents_lite_api_shape():
    from engine.agent_batch import snapshot_positions_lite

    sim = _sim_with_genome()
    for _ in range(5):
        sim.step()
    payload = snapshot_positions_lite(sim)
    assert "tick" in payload and "agents" in payload
    if payload["agents"]:
        a0 = payload["agents"][0]
        assert {"row", "x", "y", "c", "g"} <= set(a0.keys())
