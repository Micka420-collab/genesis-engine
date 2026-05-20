"""Rust bridge passes GENM when Genesis is bootstrapped (mock or native)."""
from __future__ import annotations

from engine.genesis_bootstrap import bootstrap_genesis_sim
from engine.rust_bridge import create_py_world_from_sim, bridge_status
from engine.sim import Simulation, SimConfig
from engine.world_genesis import GenesisParams


def test_bridge_genesis_bootstrapped():
    sim = Simulation(SimConfig(seed=0xBEEF, founders=2, max_agents=8))
    bootstrap_genesis_sim(
        sim,
        genesis_params=GenesisParams(seed=0xBEEF, resolution=16),
    )
    st = bridge_status(sim)
    assert st["genesis_bootstrapped"] is True


def test_create_py_world_from_sim_uses_genesis_mock():
    sim = Simulation(SimConfig(seed=0xCAFE, founders=2, max_agents=8))
    bootstrap_genesis_sim(
        sim,
        genesis_params=GenesisParams(seed=0xCAFE, resolution=16),
    )
    w = create_py_world_from_sim(sim)
    obs = w.observe_chunk(0, 0)
    assert obs.get("genesis") is True or obs.get("mock") is False
    assert len(obs["elevation"]) == 64 * 64
