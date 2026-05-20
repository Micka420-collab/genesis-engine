"""EMERGENCE SIM v2 metrics (read-only observables)."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.emergence_metrics import compute_emergence_metrics, wealth_gini
from engine.sim import Simulation, SimConfig
from engine.sim_emergence import wire_civilization_emergence


def test_compute_emergence_metrics_after_ticks():
    cfg = SimConfig(
        name="em_metrics",
        seed=42,
        founders=12,
        max_agents=40,
        bounds_km=(0.4, 0.4),
        emergence_subsystems=True,
    )
    sim = Simulation(cfg)
    wire_civilization_emergence(sim, observable_every=5)
    sim.bootstrap()
    for _ in range(30):
        sim.step()
    m = compute_emergence_metrics(sim)
    assert m["tick"] == 30
    assert m["population_alive"] >= 1
    assert "genetic_complexity_mean" in m
    assert "communication_entropy" in m
    assert "wealth_gini" in m
    assert m["philosophy"] == "ZERO_PRE_SCRIPT"
    st = sim._emergence
    assert st.last_emergence_metrics is not None


def test_wealth_gini_bounds():
    cfg = SimConfig(name="gini", seed=1, founders=8, max_agents=20, bounds_km=(0.3, 0.3))
    sim = Simulation(cfg)
    sim.bootstrap()
    g = wealth_gini(sim)
    assert 0.0 <= g <= 1.0
