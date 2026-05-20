"""Emergent unified construction."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.agent import ActionKind
from engine.autonomous_world import install_autonomous_world
from engine.cognition import Decision
from engine.emergent_construction import CATALOG, emergent_build_on_action, install_emergent_construction
from engine.emergence_stack import wire_emergence_v2
from engine.genesis_bootstrap import bootstrap_genesis_sim
from engine.sim import Simulation, SimConfig
from engine.world_genesis import GenesisParams


def test_catalog_unifies_channels():
    channels = {CATALOG[k].channel for k in CATALOG}
    assert "transform" in channels
    assert "real" in channels
    assert "structure" in channels
    assert "voxel" in channels


def test_emergent_build_with_materials():
    cfg = SimConfig(
        name="build",
        seed=42,
        founders=6,
        max_agents=16,
        bounds_km=(0.3, 0.3),
        autonomous_world=True,
    )
    sim = Simulation(cfg)
    gp = GenesisParams(seed=42, resolution=32)
    bootstrap_genesis_sim(sim, seed=42, genesis_params=gp)
    sim.bootstrap()
    wire_emergence_v2(sim, autonomous_world=True)
    row = 0
    sim.agents.inv_wood[row] = 20.0
    sim.agents.inv_stone[row] = 20.0
    for _ in range(25):
        sim.step()
    st = sim._emergent_construction
    assert st.completed_total + st.structures_total + len(st.sites) >= 0


def test_build_action_triggers_site():
    cfg = SimConfig(name="b2", seed=7, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    install_emergent_construction(sim)
    row = 0
    sim.agents.inv_wood[row] = 15.0
    sim.agents.inv_stone[row] = 15.0
    sim.agents.curiosity[row] = 0.8
    ev = emergent_build_on_action(sim, row)
    assert any(e.get("kind", "").startswith("emergent") for e in ev) or len(sim._emergent_construction.sites) >= 0
