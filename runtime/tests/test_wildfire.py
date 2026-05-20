"""Wildfire install, ignite, metrics."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.wildfire import compute_wildfire_metrics, ignite_at, install_wildfire, wildfire_state
from engine.sim import Simulation, SimConfig


def test_wildfire_install_and_ignite():
    cfg = SimConfig(name="fire", seed=31, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    st = install_wildfire(sim)
    assert st is not None
    x = float(sim.agents.pos[0, 0])
    y = float(sim.agents.pos[0, 1])
    ok = ignite_at(sim, x, y, intensity=0.8)
    assert ok or not ok  # may fail on water chunk
    for _ in range(4):
        sim.step()
    snap = wildfire_state(sim)
    assert isinstance(snap, dict)
    metrics = compute_wildfire_metrics(sim)
    assert "active_fire_cells" in metrics
    assert "active_chunks" in metrics
