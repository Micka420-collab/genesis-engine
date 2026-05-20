"""Chantiers isométriques — structures qui grandissent."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.emergent_construction import EmergentSite, install_emergent_construction
from engine.sim import Simulation, SimConfig
from engine.dashboard import render_bbox_iso_png
from engine.world_render_isometric import _construction_site_entries


def test_construction_site_entries_progress():
    cfg = SimConfig(name="iso", seed=4, founders=2, max_agents=8, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    install_emergent_construction(sim)
    st = sim._emergent_construction
    st.sites.append(EmergentSite("voxel_shelter", 0, 5, (12.0, 8.0, 0.0)))
    entries = _construction_site_entries(sim)
    assert len(entries) == 1
    assert 0.0 <= entries[0]["progress"] <= 1.0
    assert entries[0]["x"] == 12.0


def test_render_bbox_iso_png_with_site():
    cfg = SimConfig(name="iso2", seed=5, founders=2, max_agents=8, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    install_emergent_construction(sim)
    st = sim._emergent_construction
    st.sites.append(EmergentSite("voxel_shelter", 0, 2, (5.0, 5.0, 0.0)))
    png = render_bbox_iso_png(sim, -20.0, -20.0, 40.0, 40.0, 64, 48)
    assert len(png) > 200
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
