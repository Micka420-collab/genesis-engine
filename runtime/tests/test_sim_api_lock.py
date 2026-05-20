"""Thread-safety lock on Simulation.step and snapshot."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.dashboard import SimController, start_server
from engine.sim import Simulation, SimConfig


def test_sim_has_api_lock():
    sim = Simulation(SimConfig(name="lock", seed=1, founders=2, max_agents=8))
    assert hasattr(sim, "api_lock")


def test_start_server_shares_controller_lock():
    cfg = SimConfig(name="lock2", seed=2, founders=2, max_agents=8, bounds_km=(0.1, 0.1))
    sim = Simulation(cfg)
    sim.bootstrap()
    ctl = SimController()
    srv = start_server(sim, ctl, host="127.0.0.1", port=0)
    try:
        assert sim.api_lock is ctl.lock
    finally:
        srv.shutdown()


def test_concurrent_snapshot_during_step():
    cfg = SimConfig(name="lock3", seed=3, founders=4, max_agents=12, bounds_km=(0.15, 0.15))
    sim = Simulation(cfg)
    sim.bootstrap()
    errors: list = []

    def reader():
        try:
            for _ in range(20):
                with sim.api_lock:
                    snap = sim.snapshot()
                    assert "tick" in snap
        except Exception as exc:
            errors.append(exc)

    t = threading.Thread(target=reader)
    t.start()
    for _ in range(15):
        sim.step()
    t.join(timeout=5.0)
    assert not errors
