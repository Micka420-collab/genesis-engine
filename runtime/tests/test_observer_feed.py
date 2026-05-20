"""Observer feed API — god-view construction & terraformation."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.agent import ActionKind
from engine.autonomous_world import install_autonomous_world
from engine.emergent_construction import install_emergent_construction
from engine.genesis_bootstrap import bootstrap_genesis_sim
from engine.observer_feed import ACTION_BUILD, observer_feed_snapshot
from engine.sim import Simulation, SimConfig
from engine.world_genesis import GenesisParams


def test_observer_feed_empty_bbox():
    cfg = SimConfig(name="obs", seed=3, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    snap = observer_feed_snapshot(sim, -100, -100, 100, 100)
    assert snap["tick"] >= 0
    assert "sites" in snap
    assert "workers" in snap
    assert "terraform" in snap


def test_observer_feed_with_construction():
    cfg = SimConfig(
        name="obs2", seed=99, founders=8, max_agents=20,
        bounds_km=(0.4, 0.4), autonomous_world=True,
    )
    sim = Simulation(cfg)
    gp = GenesisParams(seed=99, resolution=32)
    bootstrap_genesis_sim(sim, seed=99, genesis_params=gp)
    sim.bootstrap()
    install_autonomous_world(sim)
    row = 0
    sim.agents.inv_wood[row] = 30.0
    sim.agents.inv_stone[row] = 30.0
    sim.agents.action[row] = int(ActionKind.BUILD)
    for _ in range(20):
        sim.step()
    snap = observer_feed_snapshot(sim, -5000, -5000, 5000, 5000)
    assert snap["counts"]["workers"] >= 0
    assert ACTION_BUILD == int(ActionKind.BUILD)


def test_observer_feed_emergent_site():
    cfg = SimConfig(name="obs3", seed=7, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    install_emergent_construction(sim)
    from engine.emergent_construction import EmergentSite, EmergentConstructionState
    st = sim._emergent_construction
    st.sites.append(EmergentSite("voxel_shelter", 0, 3, (10.0, 20.0, 0.0)))
    snap = observer_feed_snapshot(sim, 0, 0, 50, 50)
    assert snap["counts"]["sites"] >= 1
