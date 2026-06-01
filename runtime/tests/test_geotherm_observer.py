"""Tests d'invariants — Wave 56 geotherm & metamorphic-facies observer.

Couvre :
- Géotherme T(z) = Tsurf + Γ·z : ancrage en surface + croissance stricte.
- Classement du grade métamorphique (bandes Barroviennes) + branche haute-P
  (blueschist / éclogite).
- Intégration d'une colonne : température ↑, pression ↑, grade non décroissant
  avec la profondeur.
- Roll-up read-only sur monde Genesis réel + invariant géotherme.
- Couches profondes plus chaudes que la surface ; install/uninstall ;
  déterminisme de la signature.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.sim import Simulation, SimConfig                           # noqa: E402
from engine.world_genesis import GenesisParams                         # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim            # noqa: E402
from engine import geology as geo                                      # noqa: E402
from engine.geotherm_observer import (                                 # noqa: E402
    GeothermConfig, GeothermSnapshot,
    geotherm_temperature, metamorphic_grade, classify_facies,
    compute_column, column_geotherm_monotonic, observe_geotherm,
    install_geotherm_observer, uninstall_geotherm_observer,
    geotherm_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeLayer:
    def __init__(self, top, bottom, rock, density):
        self.depth_top_m = top
        self.depth_bottom_m = bottom
        self.rock_type = rock
        self.density_kg_m3 = density


class _FakeColumn:
    def __init__(self, layers):
        self.layers = layers


def _synthetic_column():
    return _FakeColumn([
        _FakeLayer(0.0, 1.0, "shale", 1500.0),
        _FakeLayer(1.0, 5.0, "sandstone", 1800.0),
        _FakeLayer(5.0, 200.0, "limestone", 2300.0),
        _FakeLayer(200.0, 6000.0, "granite", 2700.0),
        _FakeLayer(6000.0, 30000.0, "gneiss", 2850.0),
    ])


def _booted_sim(name: str, seed: int = 0xC0DE_5656, *, resolution: int = 64):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=4, max_agents=20,
                    bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


def _populate_geology(sim, grid: int = 5):
    geo.install_geology(sim)
    for cx in range(grid):
        for cy in range(grid):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
    return sim._geology_state


# ---------------------------------------------------------------------------
# Pure geotherm-law invariants
# ---------------------------------------------------------------------------

def test_geotherm_anchor_and_monotonic():
    cfg = GeothermConfig()
    assert geotherm_temperature(0.0, cfg) == pytest.approx(cfg.surface_temp_c)
    prev = geotherm_temperature(0.0, cfg)
    for z in (100.0, 1000.0, 5000.0, 30000.0):
        cur = geotherm_temperature(z, cfg)
        assert cur > prev
        prev = cur
    # Negative depth clamps to surface.
    assert geotherm_temperature(-50.0, cfg) == pytest.approx(cfg.surface_temp_c)


@pytest.mark.parametrize("grad", [15.0, 25.0, 40.0])
def test_geotherm_explicit_form(grad):
    cfg = GeothermConfig(gradient_c_per_km=grad)
    for z in (500.0, 3000.0, 12000.0):
        assert geotherm_temperature(z, cfg) == pytest.approx(
            cfg.surface_temp_c + grad * (z / 1000.0), rel=1e-12)


def test_metamorphic_grade_bands():
    cfg = GeothermConfig()
    assert metamorphic_grade(50.0, cfg) == 0
    assert metamorphic_grade(200.0, cfg) == 1
    assert metamorphic_grade(350.0, cfg) == 2
    assert metamorphic_grade(550.0, cfg) == 3
    assert metamorphic_grade(800.0, cfg) == 4
    # Monotone non-decreasing in temperature.
    grades = [metamorphic_grade(t, cfg) for t in range(0, 1000, 25)]
    assert all(b >= a for a, b in zip(grades, grades[1:]))


def test_facies_high_pressure_branch():
    cfg = GeothermConfig()
    # Standard prograde series at moderate pressure.
    assert classify_facies(50.0, 10.0, cfg) == "diagenetic"
    assert classify_facies(350.0, 50.0, cfg) == "greenschist"
    assert classify_facies(800.0, 50.0, cfg) == "granulite"
    # High-P / low-T window → blueschist; extreme P → eclogite.
    assert classify_facies(300.0, 900.0, cfg) == "blueschist"
    assert classify_facies(400.0, 1300.0, cfg) == "eclogite"
    # High-P qualifier never lowers the temperature-driven grade.
    assert metamorphic_grade(300.0, cfg) == 2


# ---------------------------------------------------------------------------
# Column integration invariants
# ---------------------------------------------------------------------------

def test_column_temperature_pressure_grade_monotonic():
    cfg = GeothermConfig()
    cols = compute_column(_synthetic_column(), cfg)
    assert len(cols) == 5
    temp = [c.temperature_c for c in cols]
    pres = [c.pressure_mpa for c in cols]
    grade = [c.metamorphic_grade for c in cols]
    assert all(b > a for a, b in zip(temp, temp[1:]))
    assert all(b > a for a, b in zip(pres, pres[1:]))
    assert all(b >= a for a, b in zip(grade, grade[1:]))
    assert column_geotherm_monotonic(cols)


def test_column_temperature_matches_geotherm():
    cfg = GeothermConfig()
    cols = compute_column(_synthetic_column(), cfg)
    for c in cols:
        assert c.temperature_c == pytest.approx(
            geotherm_temperature(c.z_mid_m, cfg), rel=1e-12)
        assert c.pressure_mpa >= 0.0


def test_empty_column_is_safe():
    assert compute_column(_FakeColumn([]), GeothermConfig()) == []
    assert column_geotherm_monotonic([]) is True


# ---------------------------------------------------------------------------
# Roll-up on a real Genesis world
# ---------------------------------------------------------------------------

def test_snapshot_sane_and_monotonic():
    sim = _booted_sim("geo_obs")
    gs = _populate_geology(sim)
    snap = observe_geotherm(gs, GeothermConfig(), tick=0)
    assert isinstance(snap, GeothermSnapshot)
    assert snap.total_layers > 0
    assert snap.n_chunks > 0
    assert snap.max_temperature_c >= snap.surface_temperature_c
    assert snap.max_pressure_mpa >= 0.0
    assert snap.geotherm_monotonic_ok


def test_observation_is_read_only():
    sim = _booted_sim("geo_ro")
    gs = _populate_geology(sim)
    coord0 = sorted(gs.chunks.keys())[0]
    before = [(L.depth_top_m, L.depth_bottom_m, L.density_kg_m3)
              for L in gs.chunks[coord0].layers]
    tick_before = int(getattr(sim, "tick", 0))
    observe_geotherm(gs, GeothermConfig(), tick=0)
    after = [(L.depth_top_m, L.depth_bottom_m, L.density_kg_m3)
             for L in gs.chunks[coord0].layers]
    assert before == after
    assert int(getattr(sim, "tick", 0)) == tick_before


def test_every_real_column_is_monotonic():
    sim = _booted_sim("geo_col")
    gs = _populate_geology(sim)
    for coord in sorted(gs.chunks.keys()):
        cols = compute_column(gs.chunks[coord], GeothermConfig())
        assert column_geotherm_monotonic(cols)


def test_install_uninstall_roundtrip():
    sim = _booted_sim("geo_inst")
    _populate_geology(sim)
    orig_step = sim.step
    st = install_geotherm_observer(sim, GeothermConfig(snapshot_every=1))
    assert getattr(sim, "_geotherm_state", None) is st
    assert sim.step is not orig_step
    # Idempotent.
    assert install_geotherm_observer(sim) is st
    uninstall_geotherm_observer(sim)
    assert sim.step is orig_step
    assert getattr(sim, "_geotherm_state", None) is None


def test_cross_sim_determinism():
    sim_a = _booted_sim("geo_det")
    sim_b = _booted_sim("geo_det")          # same seed
    snap_a = observe_geotherm(_populate_geology(sim_a),
                              GeothermConfig(), tick=0)
    snap_b = observe_geotherm(_populate_geology(sim_b),
                              GeothermConfig(), tick=0)
    assert snap_a.signature == snap_b.signature
    assert snap_a.mean_temperature_c == snap_b.mean_temperature_c


def test_summary_dict_shape():
    sim = _booted_sim("geo_sum")
    _populate_geology(sim)
    summ = geotherm_summary(sim)
    for key in ("total_layers", "n_chunks", "mean_temperature_c",
                "max_temperature_c", "max_pressure_mpa",
                "geotherm_monotonic_ok", "signature"):
        assert key in summ
    assert summ["geotherm_monotonic_ok"] is True
