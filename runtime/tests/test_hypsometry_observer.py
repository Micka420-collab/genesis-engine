"""Tests d'invariants — Wave 62 hypsométrie / maturité de paysage observer.

Couvre :
- Intégrale hypsométrique HI = ratio élévation-relief (forme close,
  Pike & Wilson 1971) ; HI ∈ [0, 1].
- Invariance affine de HI sous h -> a·h + b (a > 0).
- Rampe linéaire : distribution uniforme d'élévation ⇒ HI = 0.5 exact.
- Courbe de survie a*(h*) : a*(0)=1, bornée [0,1], non croissante.
- Identité Pike-Wilson : trapz(courbe) == HI à la tolérance de discrétisation.
- Étages de Strahler (youthful / mature / monadnock) + skewness signée.
- Monde réel : déterminisme, read-only, signature sha256 stable.
- Install idempotent / uninstall restaure step ; snapshot à la cadence.
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
from engine.genesis_bootstrap import bootstrap_genesis_sim            # noqa: E402
from engine.hypsometry_observer import (                               # noqa: E402
    HypsometryConfig, HypsometrySnapshot, HypsometryState,
    STAGE_YOUTHFUL, STAGE_MATURE,
    relative_elevation, hypsometric_integral, hypsometric_curve,
    hypsometric_skewness, hypsometric_stage,
    observe_hypsometry, install_hypsometry_observer,
    uninstall_hypsometry_observer, hypsometry_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = 0x150A_0062, *, resolution: int = 64):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=4, max_agents=20,
                    bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


def _synthetic_relief(n: int = 64, seed: int = 62) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n] / float(n)
    long_wave = 2500.0 * np.sin(2 * np.pi * x) * np.cos(2 * np.pi * y)
    short_wave = 600.0 * np.sin(2 * np.pi * 12 * x)
    noise = 200.0 * rng.standard_normal((n, n))
    return long_wave + short_wave + noise - 500.0


def _power_field(power: float, n: int = 64) -> np.ndarray:
    """Relief whose relative elevations follow x**power: HI -> 1/(power+1)."""
    base = np.linspace(0.0, 1.0, n * n) ** power
    return (base * 4000.0 - 1000.0).reshape(n, n)


# ---------------------------------------------------------------------------
# Pure-law tests
# ---------------------------------------------------------------------------

def test_hi_equals_elevation_relief_ratio():
    h = _synthetic_relief()
    e = (float(h.mean()) - float(h.min())) / (float(h.max()) - float(h.min()))
    assert abs(hypsometric_integral(h) - e) < 1e-12
    assert 0.0 <= hypsometric_integral(h) <= 1.0


def test_hi_affine_invariance():
    h = _synthetic_relief()
    hi = hypsometric_integral(h)
    assert abs(hypsometric_integral(3.0 * h + 1234.5) - hi) < 1e-9
    assert abs(hypsometric_integral(0.01 * h - 9.0) - hi) < 1e-9


def test_hi_linear_ramp_is_half():
    ramp = np.linspace(-1000.0, 5000.0, 4096).reshape(64, 64)
    assert abs(hypsometric_integral(ramp) - 0.5) < 1e-9


def test_hi_flat_relief_is_zero():
    flat = np.full((8, 8), 42.0)
    assert hypsometric_integral(flat) == 0.0
    _, relief, _, _ = relative_elevation(flat)
    assert relief == 0.0
    assert hypsometric_stage(0.0, relief=0.0) == "degenerate"
    assert hypsometric_skewness(flat) == 0.0


def test_survival_curve_shape():
    h = _synthetic_relief()
    levels, area = hypsometric_curve(h, 512)
    assert levels.shape == (513,) and area.shape == (513,)
    assert abs(levels[0]) < 1e-15 and abs(levels[-1] - 1.0) < 1e-15
    assert abs(area[0] - 1.0) < 1e-15           # all cells >= minimum
    assert np.all(area >= 0.0) and np.all(area <= 1.0)
    assert np.all(np.diff(area) <= 1e-15)        # non-increasing


def test_pike_wilson_identity():
    h = _synthetic_relief()
    hi = hypsometric_integral(h)
    levels, area = hypsometric_curve(h, 512)
    assert abs(float(np.trapezoid(area, levels)) - hi) < 1e-4


def test_curve_requires_positive_bins():
    import pytest
    with pytest.raises(ValueError):
        hypsometric_curve(_synthetic_relief(), 0)


def test_strahler_stage_bands():
    hi_young = hypsometric_integral(_power_field(0.25))
    hi_mature = hypsometric_integral(_power_field(1.0))
    hi_old = hypsometric_integral(_power_field(4.0))
    assert hi_young > STAGE_YOUTHFUL > hi_mature > STAGE_MATURE > hi_old
    assert hypsometric_stage(hi_young) == "youthful"
    assert hypsometric_stage(hi_mature) == "mature"
    assert hypsometric_stage(hi_old) == "monadnock"


def test_skewness_sign_tracks_maturity():
    # Old (eroded) landscape concentrates area at low elevation -> right-skewed.
    assert hypsometric_skewness(_power_field(4.0)) > 0.0
    # Youthful uplift concentrates area at altitude -> left-skewed.
    assert hypsometric_skewness(_power_field(0.25)) < 0.0


# ---------------------------------------------------------------------------
# Real-world observer tests
# ---------------------------------------------------------------------------

def test_observe_real_world_snapshot():
    sim = _booted_sim("hyp_real")
    snap = observe_hypsometry(sim)
    assert isinstance(snap, HypsometrySnapshot)
    assert snap.n_cells > 0
    assert snap.relief_m > 0.0
    assert 0.0 <= snap.hypsometric_integral <= 1.0
    assert 0.0 <= snap.land_fraction <= 1.0
    assert snap.stage in ("youthful", "mature", "monadnock")
    assert len(snap.curve_deciles) == 11


def test_real_world_pike_wilson_closes():
    sim = _booted_sim("hyp_inv")
    snap = observe_hypsometry(sim)
    assert snap is not None
    assert snap.pike_wilson_residual < 1e-3
    assert abs(snap.curve_deciles[0] - 1.0) < 1e-12


def test_observe_is_read_only():
    sim = _booted_sim("hyp_ro")
    world = sim._genesis_bootstrap_state.world
    b_el = world.elevation_m.copy()
    b_fd = world.flow_dir.copy()
    b_tick = int(sim.tick)
    observe_hypsometry(sim)
    assert np.array_equal(world.elevation_m, b_el)
    assert np.array_equal(world.flow_dir, b_fd)
    assert int(sim.tick) == b_tick


def test_cross_sim_determinism():
    a = observe_hypsometry(_booted_sim("hyp_d1", seed=0xABCD_0062))
    b = observe_hypsometry(_booted_sim("hyp_d2", seed=0xABCD_0062))
    assert a is not None and b is not None
    assert a.signature == b.signature


def test_install_uninstall_roundtrip_and_cadence():
    sim = _booted_sim("hyp_io")
    orig = sim.step
    st = install_hypsometry_observer(sim, HypsometryConfig(snapshot_every=2))
    assert isinstance(st, HypsometryState)
    again = install_hypsometry_observer(sim)
    assert again is st
    assert sim.step is not orig
    for _ in range(4):
        sim.step()
    summ = hypsometry_summary(sim)
    assert summ["installed"] is True
    assert summ["n_snapshots"] >= 1
    assert summ["pike_wilson_residual"] < 1e-3
    assert summ["stage"] in ("youthful", "mature", "monadnock")
    assert uninstall_hypsometry_observer(sim) is True
    assert sim.step is orig
    assert uninstall_hypsometry_observer(sim) is False


def test_summary_without_install():
    sim = _booted_sim("hyp_nosum")
    assert hypsometry_summary(sim) == {"installed": False}
