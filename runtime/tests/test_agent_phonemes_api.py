"""API agent — phonèmes du lexique émergent."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.dashboard import _Handler
from engine.sim import Simulation, SimConfig


def test_agent_detail_includes_phonemes():
    cfg = SimConfig(name="ph", seed=2, founders=4, max_agents=10, bounds_km=(0.15, 0.15))
    sim = Simulation(cfg)
    sim.bootstrap()
    handler = type("_H", (), {})()
    handler.sim_ref = sim
    detail = _Handler._agent_detail(handler, 0)
    assert detail.get("phonemes")
    assert len(detail["phonemes"]) >= 4
    assert "lexicon_preview" in detail
    assert detail.get("action_name")
