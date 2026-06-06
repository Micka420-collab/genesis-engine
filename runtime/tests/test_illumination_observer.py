"""Tests d'invariants - Wave 60 illumination / Quality-Diversity observer.

Couvre :
- discretize : clamp + floor binning, hi -> dernier bin, erreur si bins<1.
- MAP-Elites : meilleur strict par niche (tie-break premier vu).
- coverage : grille pleine => 1.0 ; vide => 0.0 ; qd_score = somme des elites.
- niche_entropy : qualite uniforme => ~1.0 ; spike => bas ; <=1 niche => 0.
- behavioral_novelty : nuage etale plus novel qu'un cluster serre ; <2 => 0.
- Lecture emergente read-only sur monde Genesis : snapshot sain, sim inchangee,
  signature sha256 deterministe cross-sim, install idempotent / uninstall.
"""
from __future__ import annotations

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
from engine.illumination_observer import (                             # noqa: E402
    IlluminationConfig, IlluminationSnapshot, IlluminationState,
    discretize, build_archive, qd_score, niche_entropy,
    behavioral_novelty, illumination_stats, agent_behaviors,
    observe_illumination, install_illumination_observer,
    uninstall_illumination_observer, illumination_summary,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _booted_sim(name, seed=0x111_0129):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=20,
        bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
        drive_accel=1500.0, cultures=1,
    )
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=64, n_plates=8,
                       river_threshold_cells=8.0)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


def _full_grid(bins, quality=1.0):
    return [((i / bins + 1e-3, j / bins + 1e-3), quality)
            for i in range(bins) for j in range(bins)]


# ---------------------------------------------------------------------------
# Pure primitives
# ---------------------------------------------------------------------------

def test_discretize_clamp_and_floor():
    bins = 8
    assert discretize((-1.0, 0.0), bins) == (0, 0)
    assert discretize((1.0, 2.0), bins) == (bins - 1, bins - 1)
    assert discretize((0.5, 0.5), bins) == (4, 4)
    assert discretize((0.0, 0.999999), bins) == (0, bins - 1)


def test_discretize_invalid_bins():
    with pytest.raises(ValueError):
        discretize((0.5,), 0)


def test_archive_keeps_strict_best_per_niche():
    beh = [((0.10, 0.10), 0.2), ((0.12, 0.11), 0.9), ((0.11, 0.12), 0.5)]
    arch = build_archive(beh, bins=8)
    assert len(arch) == 1
    assert next(iter(arch.values())) == pytest.approx(0.9)


def test_archive_tie_break_first_seen():
    # Equal quality must NOT overwrite (strictly-greater overwrite only).
    beh = [((0.1, 0.1), 0.5), ((0.1, 0.1), 0.5)]
    arch = build_archive(beh, bins=8)
    assert len(arch) == 1
    assert next(iter(arch.values())) == pytest.approx(0.5)


def test_coverage_full_and_empty():
    bins = 4
    st_full = illumination_stats(_full_grid(bins), IlluminationConfig(bins=bins))
    assert st_full.coverage == pytest.approx(1.0)
    assert st_full.occupied_niches == bins * bins
    assert st_full.total_niches == bins * bins
    st_empty = illumination_stats([], IlluminationConfig(bins=bins))
    assert st_empty.coverage == 0.0
    assert st_empty.occupied_niches == 0


def test_qd_score_is_sum_of_elites():
    bins = 4
    grid = _full_grid(bins, quality=2.0)
    arch = build_archive(grid, bins)
    assert qd_score(arch) == pytest.approx(2.0 * bins * bins)


def test_niche_entropy_uniform_and_spike():
    bins = 4
    uni = build_archive(_full_grid(bins, 1.0), bins)
    assert niche_entropy(uni) == pytest.approx(1.0, abs=1e-9)
    spike = [((i / bins + 1e-3, j / bins + 1e-3),
              100.0 if (i == 0 and j == 0) else 0.01)
             for i in range(bins) for j in range(bins)]
    assert niche_entropy(build_archive(spike, bins)) < 0.5
    # 0 or 1 occupied niche => entropy 0.
    assert niche_entropy({}) == 0.0
    assert niche_entropy({(0, 0): 5.0}) == 0.0


def test_niche_entropy_all_zero_quality_uniform():
    # All-zero quality but multiple niches => treated uniform => entropy 1.0.
    arch = {(0, 0): 0.0, (1, 1): 0.0, (2, 2): 0.0, (3, 3): 0.0}
    assert niche_entropy(arch) == pytest.approx(1.0, abs=1e-9)


def test_behavioral_novelty_spread_gt_cluster():
    clustered = [(0.50, 0.50), (0.51, 0.50), (0.50, 0.51), (0.49, 0.50)]
    spread = [(0.05, 0.05), (0.95, 0.05), (0.05, 0.95), (0.95, 0.95)]
    assert behavioral_novelty(spread, k=2) > behavioral_novelty(clustered, k=2)
    # Degenerate sizes.
    assert behavioral_novelty([], k=3) == 0.0
    assert behavioral_novelty([(0.1, 0.2)], k=3) == 0.0


def test_behavioral_novelty_k_clamped():
    pts = [(0.0, 0.0), (1.0, 1.0)]
    # k larger than n-1 must clamp, not raise.
    val = behavioral_novelty(pts, k=10)
    assert val == pytest.approx(np.sqrt(2.0))


# ---------------------------------------------------------------------------
# Read-only emergent reads on a real Genesis world
# ---------------------------------------------------------------------------

def test_observe_read_only_on_genesis():
    sim = _booted_sim("test_illum_real")
    tick0 = int(sim.tick)
    beh0 = agent_behaviors(sim)
    snap = observe_illumination(sim)
    # Sim untouched by observation.
    assert int(sim.tick) == tick0
    assert agent_behaviors(sim) == beh0
    assert snap is None or isinstance(snap, IlluminationSnapshot)
    if snap is not None:
        s = snap.stats
        assert 0.0 <= s.coverage <= 1.0
        assert s.occupied_niches <= s.total_niches
        assert s.behavioral_novelty >= 0.0


def test_repeated_observe_deterministic():
    sim = _booted_sim("test_illum_repeat")
    s1 = observe_illumination(sim)
    s2 = observe_illumination(sim)
    if s1 is None:
        assert s2 is None
    else:
        assert s2 is not None and s1.signature == s2.signature


def test_cross_sim_signature_determinism():
    sigs = []
    for _ in range(2):
        sim = _booted_sim("test_illum_det", seed=0x111_5252)
        install_illumination_observer(sim, IlluminationConfig(snapshot_every=1))
        for _ in range(3):
            sim.step()
        snaps = sim._illumination_state.history.snapshots
        sigs.append(snaps[-1].signature if snaps else None)
    assert sigs[0] == sigs[1]


def test_install_idempotent_and_uninstall_restores():
    sim = _booted_sim("test_illum_install")
    original_step = sim.step
    state = install_illumination_observer(sim, IlluminationConfig(snapshot_every=1))
    assert isinstance(state, IlluminationState)
    assert install_illumination_observer(sim) is state          # idempotent
    for _ in range(2):
        sim.step()
    summ = illumination_summary(sim)
    assert summ["installed"] is True
    assert uninstall_illumination_observer(sim) is True
    assert sim.step is original_step
    assert illumination_summary(sim) == {"installed": False}


def test_agent_behaviors_degrades_without_agents():
    class _Bare:
        tick = 0
    assert agent_behaviors(_Bare()) == []
    assert observe_illumination(_Bare()) is None
