"""Tests d'invariants - Wave 63 concavite de chenal / chi-steepness observer.

Couvre :
- Loi de Flint pente-aire : recuperation exacte de S = k_s*A^-theta (pivot),
  R^2 = 1, et invariance d'echelle de theta (A->c*A, S->c*S).
- Transformee chi (Perron & Royden 2013) : chi >= 0, chi = 0 au niveau de base,
  strictement croissante en remontant le chenal ; cellules hors-chenal = 0.
- Linearite chi-elevation : z = a + ksn*chi recupere a la tolerance flottante.
- Bandes de concavite (graded 0.40-0.60, convex, low/high-concavity).
- Monde reel : determinisme, read-only, signature sha256 stable.
- Install idempotent / uninstall restaure step ; snapshot a la cadence.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.sim import Simulation, SimConfig                           # noqa: E402
from engine.world_genesis import GenesisParams                         # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim           # noqa: E402
from engine.concavity_observer import (                                # noqa: E402
    ConcavityConfig, ConcavitySnapshot, ConcavityState,
    CONCAVITY_GRADED_LO, CONCAVITY_GRADED_HI,
    channel_slope_area, fit_flint_law, chi_transform,
    fit_chi_elevation, concavity_stage,
    observe_concavity, install_concavity_observer,
    uninstall_concavity_observer, concavity_summary,
)

_D8_SOUTH = 2
_D8_SINK = 255


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = 0x150A_0063, *, resolution: int = 64):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=4, max_agents=20,
                    bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


def _linear_channel(n: int = 24):
    """One vertical channel flowing south; bottom cell is the (sink) mouth."""
    flow_dir = np.full((n, 2), _D8_SINK, dtype=np.uint8)
    flow_acc = np.zeros((n, 2), dtype=np.float64)
    river_mask = np.zeros((n, 2), dtype=bool)
    for y in range(n):
        river_mask[y, 0] = True
        flow_acc[y, 0] = float(y + 1)
        flow_dir[y, 0] = _D8_SOUTH if y < n - 1 else _D8_SINK
    return flow_dir, flow_acc, river_mask


# ---------------------------------------------------------------------------
# Flint slope-area law
# ---------------------------------------------------------------------------

def test_flint_power_law_recovery():
    A = np.geomspace(1.0, 1.0e6, 200)
    theta_true, ks_true = 0.5, 2.0
    S = ks_true * A ** (-theta_true)
    theta, ks, r2, n = fit_flint_law(A, S)
    assert abs(theta - theta_true) < 1e-9
    assert abs(ks - ks_true) < 1e-7
    assert abs(r2 - 1.0) < 1e-12
    assert n == 200


def test_flint_concavity_scale_invariance():
    A = np.geomspace(1.0, 1.0e6, 200)
    S = 2.0 * A ** (-0.5)
    th0, ks0, _, _ = fit_flint_law(A, S)
    th_area, ks_area, _, _ = fit_flint_law(1000.0 * A, S)
    th_slope, ks_slope, _, _ = fit_flint_law(A, 1000.0 * S)
    # theta is blind to the units of A and S.
    assert abs(th_area - th0) < 1e-9
    assert abs(th_slope - th0) < 1e-9
    # k_s shifts predictably: S->c*S scales k_s by c.
    assert abs(ks_slope - 1000.0 * ks0) < 1e-3 * (1000.0 * ks0)


def test_flint_degenerate_inputs():
    # Fewer than two valid (A>0, S>0) points -> degenerate, no crash.
    theta, ks, r2, n = fit_flint_law(np.array([10.0]), np.array([1.0]))
    assert (theta, ks, r2, n) == (0.0, 0.0, 0.0, 1)
    # Non-positive slopes are filtered out of the log fit.
    theta, ks, r2, n = fit_flint_law(np.array([10.0, 20.0]),
                                     np.array([-1.0, 0.0]))
    assert n == 0


def test_concavity_stage_bands():
    assert concavity_stage(-0.2) == "convex"
    assert concavity_stage(0.1) == "low-concavity"
    assert concavity_stage(0.45) == "graded"
    assert concavity_stage(CONCAVITY_GRADED_LO) == "graded"
    assert concavity_stage(CONCAVITY_GRADED_HI) == "graded"
    assert concavity_stage(0.9) == "high-concavity"
    assert concavity_stage(float("nan")) == "degenerate"


# ---------------------------------------------------------------------------
# Chi integral transform
# ---------------------------------------------------------------------------

def test_chi_base_level_and_monotone():
    fd, acc, rm = _linear_channel(24)
    chi = chi_transform(fd, acc, rm, cell_m=100.0, theta_ref=0.45)
    col = chi[:, 0]
    assert np.all(chi >= 0.0)
    assert abs(col[-1]) < 1e-15                # mouth (sink) chi == 0
    assert np.all(np.diff(col) < 0.0)          # strictly decreasing downstream
    assert np.all(chi[:, 1] == 0.0)            # non-channel cells stay 0


def test_chi_empty_network_is_zero():
    fd = np.full((8, 8), _D8_SINK, dtype=np.uint8)
    acc = np.zeros((8, 8), dtype=np.float64)
    rm = np.zeros((8, 8), dtype=bool)
    chi = chi_transform(fd, acc, rm, cell_m=100.0)
    assert np.all(chi == 0.0)


def test_chi_elevation_linearity():
    fd, acc, rm = _linear_channel(24)
    chi = chi_transform(fd, acc, rm, cell_m=100.0, theta_ref=0.45)
    z = 100.0 + 3.5 * chi
    ksn, intercept, r2, n = fit_chi_elevation(chi, z, rm)
    assert abs(ksn - 3.5) < 1e-9
    assert abs(intercept - 100.0) < 1e-6
    assert abs(r2 - 1.0) < 1e-12
    assert n == 24


def test_channel_slope_area_positive_downslope():
    # A two-cell channel descending south: slope must be positive, area > 0.
    fd, acc, rm = _linear_channel(4)
    z = np.zeros((4, 2), dtype=np.float64)
    z[:, 0] = np.array([300.0, 200.0, 100.0, 0.0])   # descends downstream
    area, slope = channel_slope_area(z, fd, acc, rm, cell_m=100.0)
    assert area.size == 3                              # bottom cell is a sink
    assert np.all(area > 0.0)
    assert np.all(slope > 0.0)


# ---------------------------------------------------------------------------
# Real-world observer tests
# ---------------------------------------------------------------------------

def test_observe_real_world_snapshot():
    # res 192 -> a genuine emergent channel network (res 64 is near-empty).
    sim = _booted_sim("conc_real", resolution=192)
    snap = observe_concavity(sim)
    assert isinstance(snap, ConcavitySnapshot)
    assert snap.n_cells > 0
    assert snap.n_channel_cells > 0          # genuine network present
    assert snap.n_fit_cells > 0              # Flint fit actually ran
    assert snap.chi_max > 0.0
    assert 0.0 <= snap.slope_area_r2 <= 1.0
    assert 0.0 <= snap.chi_z_r2 <= 1.0
    assert np.isfinite(snap.concavity_theta)
    assert np.isfinite(snap.ksn)
    assert np.isfinite(snap.steepness_ks)
    assert snap.stage in ("convex", "low-concavity", "graded",
                          "high-concavity", "degenerate")


def test_observe_is_read_only():
    sim = _booted_sim("conc_ro", resolution=192)
    world = sim._genesis_bootstrap_state.world
    b_el = world.elevation_m.copy()
    b_fd = world.flow_dir.copy()
    b_acc = world.flow_acc.copy()
    b_tick = int(sim.tick)
    observe_concavity(sim)
    assert np.array_equal(world.elevation_m, b_el)
    assert np.array_equal(world.flow_dir, b_fd)
    assert np.array_equal(world.flow_acc, b_acc)
    assert int(sim.tick) == b_tick


def test_cross_sim_determinism():
    a = observe_concavity(_booted_sim("conc_d1", seed=0xABCD_0063,
                                      resolution=192))
    b = observe_concavity(_booted_sim("conc_d2", seed=0xABCD_0063,
                                      resolution=192))
    assert a is not None and b is not None
    assert a.signature == b.signature


def test_install_uninstall_roundtrip_and_cadence():
    sim = _booted_sim("conc_io")
    orig = sim.step
    st = install_concavity_observer(sim, ConcavityConfig(snapshot_every=2))
    assert isinstance(st, ConcavityState)
    again = install_concavity_observer(sim)
    assert again is st
    assert sim.step is not orig
    for _ in range(4):
        sim.step()
    summ = concavity_summary(sim)
    assert summ["installed"] is True
    assert summ["n_snapshots"] >= 1
    assert 0.0 <= summ["slope_area_r2"] <= 1.0
    assert summ["stage"] in ("convex", "low-concavity", "graded",
                             "high-concavity", "degenerate")
    assert uninstall_concavity_observer(sim) is True
    assert sim.step is orig
    assert uninstall_concavity_observer(sim) is False


def test_summary_without_install():
    sim = _booted_sim("conc_nosum")
    assert concavity_summary(sim) == {"installed": False}
