"""Wave 7 meteorology install and state snapshot."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.meteorology import install_meteorology, meteorology_state
from engine.sim import Simulation, SimConfig


def test_install_meteorology_idempotent():
    cfg = SimConfig(name="met", seed=30, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    s1 = install_meteorology(sim)
    s2 = install_meteorology(sim)
    assert s1 is s2
    for _ in range(5):
        sim.step()
    snap = meteorology_state(sim)
    assert snap.get("global_temp_c") is not None or snap.get("origin_lat") is not None
    assert "global_cloud_cover" in snap or "storms" in snap
