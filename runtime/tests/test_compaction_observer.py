"""Tests d'invariants — Wave 54 diagenetic compaction & lithostatic observer.

Couvre :
- Loi de compaction φ(σ') = φ₀·exp(−b·σ') : ancrage en surface + décroissance.
- Intégration d'une colonne : contrainte effective ↑, porosité ↓ avec la profondeur.
- Bornes physiques : densité bulk ∈ [eau, grain] ; 0 < φ ≤ φ₀.
- Roll-up read-only sur monde Genesis réel + invariant de compaction.
- Contrainte effective positive ; porosité de surface > porosité profonde.
- Install idempotent / uninstall restaure step ; déterminisme signature.
"""
from __future__ import annotations

import math
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
from engine.compaction_observer import (                               # noqa: E402
    CompactionConfig, CompactionSnapshot,
    porosity_from_stress, compute_column, column_compaction_monotonic,
    observe_compaction, install_compaction_observer,
    uninstall_compaction_observer, compaction_summary,
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
        _FakeLayer(200.0, 1000.0, "granite", 2700.0),
        _FakeLayer(1000.0, 3000.0, "gneiss", 2850.0),
    ])


def _booted_sim(name: str, seed: int = 0xC0DE_5454, *, resolution: int = 64):
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
# Pure compaction-law invariants
# ---------------------------------------------------------------------------

def test_porosity_law_anchor_and_monotonic():
    cfg = CompactionConfig()
    assert porosity_from_stress(0.0, cfg) == pytest.approx(cfg.surface_porosity)
    # Strictly decreasing in effective stress.
    prev = porosity_from_stress(0.0, cfg)
    for s in (1.0, 5.0, 20.0, 100.0):
        cur = porosity_from_stress(s, cfg)
        assert cur < prev
        prev = cur
    # Negative stress clamps to the surface value (no tensile compaction).
    assert porosity_from_stress(-10.0, cfg) == pytest.approx(cfg.surface_porosity)


@pytest.mark.parametrize("b", [0.02, 0.045, 0.08])
def test_porosity_law_explicit_form(b):
    cfg = CompactionConfig(compaction_coeff_per_mpa=b)
    for s in (0.5, 3.0, 25.0):
        assert porosity_from_stress(s, cfg) == pytest.approx(
            cfg.surface_porosity * math.exp(-b * s), rel=1e-12)


# ---------------------------------------------------------------------------
# Column integration invariants
# ---------------------------------------------------------------------------

def test_column_stress_and_porosity_monotonic():
    cfg = CompactionConfig()
    cols = compute_column(_synthetic_column(), cfg)
    assert len(cols) == 5
    eff = [c.effective_stress_mpa for c in cols]
    por = [c.porosity for c in cols]
    # Effective stress strictly increases, porosity strictly decreases.
    assert all(b > a for a, b in zip(eff, eff[1:]))
    assert all(b < a for a, b in zip(por, por[1:]))
    assert column_compaction_monotonic(cols)


def test_column_pressure_and_density_bounds():
    cfg = CompactionConfig()
    cols = compute_column(_synthetic_column(), cfg)
    grains = (1500.0, 1800.0, 2300.0, 2700.0, 2850.0)
    for c, grain in zip(cols, grains):
        # Overburden exceeds pore pressure (grain denser than water).
        assert c.overburden_mpa > c.pore_pressure_mpa > 0.0
        assert c.effective_stress_mpa == pytest.approx(
            c.overburden_mpa - c.pore_pressure_mpa, rel=1e-9)
        # Porosity within (0, surface].
        assert 0.0 < c.porosity <= cfg.surface_porosity
        # Bulk density bracketed by water and grain density.
        assert cfg.water_density <= c.bulk_density_kg_m3 <= grain + 1e-6


def test_empty_column_is_safe():
    assert compute_column(_FakeColumn([]), CompactionConfig()) == []
    assert column_compaction_monotonic([]) is True


# ---------------------------------------------------------------------------
# Roll-up on a real Genesis world
# ---------------------------------------------------------------------------

def test_snapshot_sane_and_monotonic():
    sim = _booted_sim("comp_obs")
    gs = _populate_geology(sim)
    snap = observe_compaction(gs, CompactionConfig(), tick=0)
    assert isinstance(snap, CompactionSnapshot)
    assert snap.total_layers > 0
    assert snap.n_chunks > 0
    assert 0.0 < snap.mean_porosity <= CompactionConfig().surface_porosity + 1e-9
    assert snap.max_effective_stress_mpa > 0.0
    assert snap.max_overburden_mpa > 0.0
    # Compaction invariant holds map-wide.
    assert snap.compaction_monotonic_ok
    # Burial reduces porosity.
    assert snap.shallow_porosity > snap.deep_porosity


def test_observation_is_read_only():
    sim = _booted_sim("comp_ro")
    gs = _populate_geology(sim)
    coord0 = sorted(gs.chunks.keys())[0]
    before = [(L.depth_top_m, L.depth_bottom_m, L.density_kg_m3)
              for L in gs.chunks[coord0].layers]
    tick_before = int(getattr(sim, "tick", 0))
    observe_compaction(gs, CompactionConfig(), tick=0)
    after = [(L.depth_top_m, L.depth_bottom_m, L.density_kg_m3)
             for L in gs.chunks[coord0].layers]
    assert before == after
    assert int(getattr(sim, "tick", 0)) == tick_before


def test_every_real_column_is_monotonic():
    sim = _booted_sim("comp_col")
    gs = _populate_geology(sim)
    for coord in sorted(gs.chunks.keys()):
        cols = compute_column(gs.chunks[coord], CompactionConfig())
        assert column_compaction_monotonic(cols)


def test_install_uninstall_roundtrip():
    sim = _booted_sim("comp_inst")
    _populate_geology(sim)
    orig_step = sim.step
    st = install_compaction_observer(sim, CompactionConfig(snapshot_every=1))
    assert getattr(sim, "_compaction_state", None) is st
    assert sim.step is not orig_step
    # Idempotent.
    assert install_compaction_observer(sim) is st
    uninstall_compaction_observer(sim)
    assert sim.step is orig_step
    assert getattr(sim, "_compaction_state", None) is None


def test_cross_sim_determinism():
    sim_a = _booted_sim("comp_det")
    sim_b = _booted_sim("comp_det")          # same seed
    snap_a = observe_compaction(_populate_geology(sim_a),
                                CompactionConfig(), tick=0)
    snap_b = observe_compaction(_populate_geology(sim_b),
                                CompactionConfig(), tick=0)
    assert snap_a.signature == snap_b.signature
    assert snap_a.mean_porosity == snap_b.mean_porosity


def test_summary_dict_shape():
    sim = _booted_sim("comp_sum")
    _populate_geology(sim)
    summ = compaction_summary(sim)
    for key in ("total_layers", "n_chunks", "mean_porosity",
                "max_effective_stress_mpa", "compaction_monotonic_ok",
                "signature"):
        assert key in summ
    assert summ["compaction_monotonic_ok"] is True
