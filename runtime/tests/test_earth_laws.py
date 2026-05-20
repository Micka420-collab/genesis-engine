"""Lois de la Terre (L0) — axiomes tickables + champ lite."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.earth_laws import (
    EARTH_AXIOMS,
    earth_laws_snapshot,
    install_earth_laws,
    sample_lite_field,
)
from engine.sim import Simulation, SimConfig


def test_earth_axioms_count():
    assert len(EARTH_AXIOMS) >= 5
    ids = {a["id"] for a in EARTH_AXIOMS}
    assert "E" in ids
    assert "gradT" in ids


def test_install_earth_laws_ticks():
    cfg = SimConfig(name="laws", seed=3, founders=6, max_agents=16, bounds_km=(0.3, 0.3))
    sim = Simulation(cfg)
    sim.bootstrap()
    install_earth_laws(sim)
    for _ in range(20):
        sim.step()
    snap = earth_laws_snapshot(sim)
    assert snap["layer"] == "L0_PHYSICS"
    assert "live" in snap
    assert snap["live"]["ticks"] >= 20
    assert 0.0 <= snap["live"]["entropy_proxy"] <= 1.0


def test_sample_lite_field_rgba():
    cfg = SimConfig(name="lite", seed=9, founders=4, max_agents=12, bounds_km=(0.25, 0.25))
    sim = Simulation(cfg)
    sim.bootstrap()
    install_earth_laws(sim)
    for _ in range(5):
        sim.step()
    field = sample_lite_field(sim, -200, -200, 200, 200, 32, 24)
    assert field["w"] == 32 and field["h"] == 24
    assert "rgba_b64" in field
    import base64
    raw = base64.b64decode(field["rgba_b64"])
    assert len(raw) == 32 * 24 * 4
