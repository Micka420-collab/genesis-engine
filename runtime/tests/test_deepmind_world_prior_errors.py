"""World prior install — idempotence."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.deepmind_world_prior import install_deepmind_world_prior, world_prior_snapshot
from engine.genesis_bootstrap import bootstrap_genesis_sim
from engine.sim import Simulation, SimConfig
from engine.world_genesis import GenesisParams


def test_install_skipped_when_already_applied():
    cfg = SimConfig(name="prior2", seed=9, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=9, genesis_params=GenesisParams(seed=9, resolution=24))
    sim.bootstrap()
    a = install_deepmind_world_prior(sim)
    b = install_deepmind_world_prior(sim)
    assert a.get("graphcast_lite")
    assert b.get("skipped")
    snap = world_prior_snapshot(sim)
    assert snap.get("applied")
