"""api_lock helpers — safe_dict and wave payload errors."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.api_lock import safe_dict, safe_optional
from engine.dashboard import _Handler
from engine.sim import Simulation, SimConfig


def test_safe_dict_captures_exception():
    def boom():
        raise RuntimeError("wave offline")

    out = safe_dict("meteorology_state", boom)
    assert "error" in out
    assert "meteorology_state" in out["error"]


def test_safe_optional_returns_default():
    val, err = safe_optional("x", lambda: 1 / 0, default=None)
    assert val is None
    assert err and "ZeroDivisionError" in err


def test_wave_payload_on_handler():
    cfg = SimConfig(name="wave", seed=1, founders=2, max_agents=8, bounds_km=(0.1, 0.1))
    sim = Simulation(cfg)
    sim.bootstrap()
    h = object.__new__(_Handler)
    h.sim_ref = sim
    out = _Handler._wave_payload(h, lambda s: {"ok": True})
    assert out.get("ok") is True
