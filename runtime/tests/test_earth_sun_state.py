"""État solaire — ombres portées pour Earth Console."""
from __future__ import annotations

import math
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.earth_sun_state import sun_state_snapshot
from engine.sim import Simulation, SimConfig


def test_sun_state_snapshot_keys():
    cfg = SimConfig(name="sun", seed=1, founders=2, max_agents=6, bounds_km=(0.1, 0.1))
    sim = Simulation(cfg)
    sim.bootstrap()
    snap = sun_state_snapshot(sim)
    assert snap["tick"] >= 0
    assert "shadow_offset_px" in snap
    assert len(snap["shadow_offset_px"]) == 2
    assert "day_factor" in snap
    assert 0.0 <= snap["day_factor"] <= 1.5
    assert "light_xy" in snap
    assert isinstance(snap["is_day"], bool)


def test_sun_state_with_dynamo():
    cfg = SimConfig(name="sun2", seed=2, founders=2, max_agents=6, bounds_km=(0.1, 0.1))
    sim = Simulation(cfg)
    sim.bootstrap()
    from engine.earth_dynamo import install_earth_dynamo
    install_earth_dynamo(sim)
    for _ in range(5):
        sim.step()
    snap = sun_state_snapshot(sim)
    assert math.isfinite(snap["phase_rad"])
    assert snap["insolation_w_m2"] > 0
