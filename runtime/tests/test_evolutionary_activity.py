"""Tests d'invariants - Wave 58 open-endedness / activite evolutive (Bedau-Packard).

Couvre :
- Fermeture additive : A(T) == somme a_i(T) (activite cumulee totale = somme par composant).
- Diversite D(t) monotone non decroissante ; n_new(t) = delta D(t) (somme n_new = D_final).
- Classification falsifiable : systeme fige => "none" ; nouveaute decroissante =>
  "bounded" ; nouveaute soutenue => "unbounded" ; serie trop courte => "insufficient".
- Seuil shadow neutre = facteur * activite moyenne ; n significatifs coherent.
- Lecture emergente read-only sur un monde Genesis : snapshot sain, sim inchangee,
  signature sha256 deterministe cross-sim, install idempotent / uninstall restaure step.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.sim import Simulation, SimConfig                           # noqa: E402
from engine.world_genesis import GenesisParams                         # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim            # noqa: E402
from engine.evolutionary_activity import (                             # noqa: E402
    EvoActivityConfig, EvoActivityStats, EvoActivitySnapshot, EvoActivityState,
    diversity_curve, new_component_curve, component_activity,
    total_activity_curve, mean_activity_curve, significance_threshold,
    n_significant_components, classify_dynamics, evolutionary_activity_stats,
    component_usage, observe_evolutionary_activity,
    install_evolutionary_activity_observer,
    uninstall_evolutionary_activity_observer, evolutionary_activity_summary,
)


# ---------------------------------------------------------------------------
# Synthetic usage series (world-free, deterministic)
# ---------------------------------------------------------------------------

def _series_none(T: int = 200):
    """Frozen system: the same 3 components are used every tick, no novelty."""
    return [{"a": 1.0, "b": 1.0, "c": 1.0} for _ in range(T)]


def _series_unbounded(T: int = 200):
    """Open-ended: a brand-new component is introduced at every tick."""
    return [{f"n{t}": 1.0, "a": 1.0} for t in range(T)]


def _series_bounded(T: int = 200):
    """Saturating: a new component appears only on perfect squares (rate->0)."""
    out = []
    for t in range(T):
        step = {"a": 1.0}
        r = int(math.isqrt(t))
        if r * r == t:
            step[f"sq{t}"] = 1.0
        out.append(step)
    return out


# ---------------------------------------------------------------------------
# Genesis world helper
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = 0x0EE0058, *,
                resolution: int = 64, river_threshold_cells: float = 8.0):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=4, max_agents=20,
                    bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8,
                       river_threshold_cells=river_threshold_cells)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


# ---------------------------------------------------------------------------
# Pure-statistic invariants
# ---------------------------------------------------------------------------

def test_total_activity_equals_sum_of_components():
    for ser in (_series_none(), _series_unbounded(), _series_bounded()):
        A = total_activity_curve(ser)
        assert abs(float(A[-1]) - sum(component_activity(ser).values())) < 1e-9


def test_diversity_is_monotone_and_new_is_its_increment():
    for ser in (_series_none(), _series_unbounded(), _series_bounded()):
        D = diversity_curve(ser)
        assert np.all(np.diff(D) >= 0)              # monotone non-decreasing
        nnew = new_component_curve(ser)
        assert int(nnew.sum()) == int(D[-1])        # sum n_new == D_final
        assert nnew[0] == D[0]
        assert np.array_equal(nnew[1:], np.diff(D))


def test_mean_activity_matches_total_over_diversity():
    ser = _series_bounded()
    A = total_activity_curve(ser)
    D = diversity_curve(ser).astype(np.float64)
    Abar = mean_activity_curve(ser)
    nz = D > 0
    assert np.allclose(Abar[nz], A[nz] / D[nz])


def test_classification_none_bounded_unbounded():
    cfg = EvoActivityConfig()
    assert classify_dynamics(_series_none(), cfg) == "none"
    assert classify_dynamics(_series_bounded(), cfg) == "bounded"
    assert classify_dynamics(_series_unbounded(), cfg) == "unbounded"


def test_classification_insufficient_below_min_steps():
    cfg = EvoActivityConfig(min_steps=8)
    assert classify_dynamics(_series_unbounded(3), cfg) == "insufficient"
    assert classify_dynamics([], cfg) == "insufficient"


def test_significance_threshold_and_count():
    ser = _series_none()                       # 3 comps, equal activity 200
    act = component_activity(ser)
    thr = significance_threshold(act, factor=1.0)
    assert thr == pytest.approx(200.0)
    assert n_significant_components(act, thr) == 0
    act2 = {"x": 100.0, "y": 1.0, "z": 1.0}
    thr2 = significance_threshold(act2, factor=1.0)
    assert n_significant_components(act2, thr2) == 1


def test_stats_bundle_is_deterministic_and_well_formed():
    cfg = EvoActivityConfig()
    s1 = evolutionary_activity_stats(_series_unbounded(), cfg)
    s2 = evolutionary_activity_stats(_series_unbounded(), cfg)
    assert s1 == s2
    assert isinstance(s1, EvoActivityStats)
    assert s1.dynamics_class == "unbounded"
    assert s1.diversity_final == s1.new_components_total
    assert 0.0 <= s1.innovation_rate_tail <= 1.0


# ---------------------------------------------------------------------------
# Observer on a real Genesis world (read-only, deterministic)
# ---------------------------------------------------------------------------

def test_component_usage_is_a_mapping_and_namespaced():
    sim = _booted_sim("evo_usage")
    usage = component_usage(sim)
    assert isinstance(usage, dict)
    for key, inc in usage.items():
        assert isinstance(key, str) and key.split(":", 1)[0] in {
            "inv", "rec", "lex"}
        assert inc == 1.0


def test_observe_is_read_only_and_stable():
    sim = _booted_sim("evo_ro")
    tick_before = int(sim.tick)
    usage_before = component_usage(sim)
    snap1 = observe_evolutionary_activity(sim)
    snap2 = observe_evolutionary_activity(sim)
    assert int(sim.tick) == tick_before
    assert component_usage(sim) == usage_before
    if snap1 is not None:
        assert isinstance(snap1, EvoActivitySnapshot)
        assert len(snap1.signature) == 64
        assert snap2 is not None and snap1.signature == snap2.signature
    else:
        assert snap2 is None


def test_install_uninstall_roundtrip_and_cadence():
    sim = _booted_sim("evo_install")
    original_step = sim.step
    state = install_evolutionary_activity_observer(
        sim, EvoActivityConfig(snapshot_every=1))
    assert isinstance(state, EvoActivityState)
    assert install_evolutionary_activity_observer(sim) is state
    for _ in range(3):
        sim.step()
    summ = evolutionary_activity_summary(sim)
    assert summ["installed"] is True
    assert summ["n_snapshots"] >= 1
    assert summ["n_usage_steps"] >= 1
    assert summ["dynamics_class"] in {
        "none", "bounded", "unbounded", "insufficient"}
    assert uninstall_evolutionary_activity_observer(sim) is True
    assert sim.step is original_step
    assert evolutionary_activity_summary(sim) == {"installed": False}


def test_signature_deterministic_cross_sim():
    sigs = []
    for _ in range(2):
        sim = _booted_sim("evo_det", seed=0x0EE5151)
        install_evolutionary_activity_observer(
            sim, EvoActivityConfig(snapshot_every=1))
        for _ in range(3):
            sim.step()
        snaps = sim._evo_activity_state.history.snapshots
        sigs.append(snaps[-1].signature)
    assert sigs[0] == sigs[1]
