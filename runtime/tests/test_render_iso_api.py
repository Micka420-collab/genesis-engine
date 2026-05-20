"""Isometric bbox render helper smoke."""
from __future__ import annotations

import numpy as np

from engine.dashboard import render_bbox_iso_png, _encode_png
from engine.sim import Simulation, SimConfig


def test_render_bbox_iso_png_returns_png():
    sim = Simulation(SimConfig(seed=42, founders=4, max_agents=16, bounds_km=(0.2, 0.2)))
    sim.bootstrap()
    for _ in range(3):
        sim.step()
    png = render_bbox_iso_png(sim, -200.0, -200.0, 200.0, 200.0, 128, 96)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 500
