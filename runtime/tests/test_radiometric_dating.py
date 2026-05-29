"""Tests d'invariants — Wave 51 radiometric (absolute) dating observer.

Couvre :
- Sélection du géochronomètre par bande d'âge émergente.
- Fermeture de la loi de décroissance : âge récupéré == âge émergent.
- Signaux de décroissance monotones (D/P ↑, fraction parent ↓).
- Bornes physiques : 0 < fraction parent ≤ 1, D/P ≥ 0, σ borné.
- Roll-up read-only sur monde Genesis réel + concordance superposition.
- Histogramme = somme des couches datables ⊆ total.
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
from engine.genesis_bootstrap import bootstrap_genesis_sim             # noqa: E402
from engine import geology as geo                                      # noqa: E402
from engine.radiometric_dating import (                                # noqa: E402
    ISOTOPES, SYSTEM_NAMES, RadiometricConfig, RadiometricSnapshot,
    select_isotopic_system, date_layer, date_column, column_concordant,
    observe_radiometric, install_radiometric_observer,
    uninstall_radiometric_observer, radiometric_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = 0xC0DE_5151, *, resolution: int = 64):
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
# Pure geochronology invariants
# ---------------------------------------------------------------------------

def test_system_selection_per_band():
    assert select_isotopic_system(0.01).name == "C-14"
    assert select_isotopic_system(0.2).name == "U-Th"
    assert select_isotopic_system(10.0).name == "K-Ar"
    assert select_isotopic_system(540.0).name == "U-Pb"
    # Non-positive / unassigned age is undatable, not fabricated.
    assert select_isotopic_system(0.0) is None
    assert select_isotopic_system(-3.0) is None
    # Older than every window clamps to the oldest system.
    assert select_isotopic_system(9_000.0).name == ISOTOPES[-1].name


@pytest.mark.parametrize("age", [0.005, 0.02, 0.2, 5.0, 60.0, 540.0,
                                 1100.0, 3000.0])
def test_decay_law_closure(age):
    """Inverting the decay law recovers the emergent age (geochronometer
    closure) to sub-ppm precision."""
    ld = date_layer(age)
    assert ld is not None
    assert ld.recovered_age_ma == pytest.approx(age, abs=1e-6, rel=1e-9)


def test_decay_signals_monotonic_and_bounded():
    d5, d60 = date_layer(5.0), date_layer(60.0)
    # Daughter accumulates, parent depletes with age (same K-Ar system).
    assert d60.daughter_parent_ratio > d5.daughter_parent_ratio > 0.0
    assert d5.parent_fraction > d60.parent_fraction
    # Physical bounds on every band.
    for age in (0.001, 0.3, 12.0, 800.0, 4000.0):
        ld = date_layer(age)
        assert 0.0 < ld.parent_fraction <= 1.0
        assert ld.daughter_parent_ratio >= 0.0
        assert 0.0 <= ld.sigma_rel <= 0.5


def test_isochron_equation_consistency():
    """parent_fraction and daughter/parent ratio are the same clock:
    f * (1 + D/P) == 1 for every system."""
    for age in (0.01, 0.25, 8.0, 300.0, 2000.0):
        ld = date_layer(age)
        assert ld.parent_fraction * (1.0 + ld.daughter_parent_ratio) == \
            pytest.approx(1.0, rel=1e-9)


# ---------------------------------------------------------------------------
# Roll-up on a real Genesis world
# ---------------------------------------------------------------------------

def test_snapshot_sane_and_concordant():
    sim = _booted_sim("rad_obs")
    gs = _populate_geology(sim)
    snap = observe_radiometric(gs, RadiometricConfig(), tick=0)
    assert isinstance(snap, RadiometricSnapshot)
    assert snap.total_layers > 0
    assert 0 < snap.datable_layers <= snap.total_layers
    assert 0.0 < snap.datable_fraction <= 1.0
    assert snap.oldest_age_ma > 0.0
    assert snap.oldest_system in SYSTEM_NAMES
    # Histogram partitions exactly the datable layers.
    assert sum(snap.system_histogram.values()) == snap.datable_layers
    # Absolute dating agrees with the law of superposition.
    assert snap.concordance_ok
    assert snap.max_closure_residual_ma < RadiometricConfig().closure_tol_ma


def test_observation_is_read_only():
    sim = _booted_sim("rad_ro")
    gs = _populate_geology(sim)
    coord0 = sorted(gs.chunks.keys())[0]
    before = [L.age_ma for L in gs.chunks[coord0].layers]
    tick_before = int(getattr(sim, "tick", 0))
    observe_radiometric(gs, RadiometricConfig(), tick=0)
    after = [L.age_ma for L in gs.chunks[coord0].layers]
    assert before == after
    assert int(getattr(sim, "tick", 0)) == tick_before


def test_column_concordance_helper():
    sim = _booted_sim("rad_col")
    gs = _populate_geology(sim)
    for coord in sorted(gs.chunks.keys()):
        dates = date_column(gs.chunks[coord])
        assert column_concordant(dates)


def test_install_uninstall_roundtrip():
    sim = _booted_sim("rad_inst")
    _populate_geology(sim)
    orig_step = sim.step
    st = install_radiometric_observer(sim, RadiometricConfig(snapshot_every=1))
    assert getattr(sim, "_radiometric_state", None) is st
    assert sim.step is not orig_step
    # Idempotent.
    assert install_radiometric_observer(sim) is st
    uninstall_radiometric_observer(sim)
    assert sim.step is orig_step
    assert getattr(sim, "_radiometric_state", None) is None


def test_cross_sim_determinism():
    sim_a = _booted_sim("rad_det")
    sim_b = _booted_sim("rad_det")          # same seed
    snap_a = observe_radiometric(_populate_geology(sim_a),
                                 RadiometricConfig(), tick=0)
    snap_b = observe_radiometric(_populate_geology(sim_b),
                                 RadiometricConfig(), tick=0)
    assert snap_a.signature == snap_b.signature
    assert snap_a.oldest_age_ma == snap_b.oldest_age_ma


def test_summary_dict_shape():
    sim = _booted_sim("rad_sum")
    _populate_geology(sim)
    summ = radiometric_summary(sim)
    for key in ("total_layers", "datable_layers", "oldest_age_ma",
                "oldest_system", "concordance_ok", "system_histogram",
                "signature"):
        assert key in summ
    assert summ["concordance_ok"] is True
