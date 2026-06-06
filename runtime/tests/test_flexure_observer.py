"""Tests d'invariants — Wave 61 flexure lithosphérique élastique observer.

Couvre :
- Rigidité flexurale D = E·Te³/(12(1−ν²)) et paramètre flexural
  α = (4D/((ρm−ρc)g))^(1/4) (formes closes).
- Filtre flexural Φ(k) : Φ(0)=1, Φ ∈ (0,1], strictement décroissant en k.
- Limite d'Airy : Te → 0 ⇒ déflexion == racine d'Airy (Wave 59) à la
  précision machine.
- Bilan de charge mode zéro : moyenne(w) == moyenne(r_airy) (Φ(0)=1).
- Lissage régional : std(w) ≤ std(r_airy) (Parseval, Φ ≤ 1).
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
from engine.isostasy_observer import IsostasyConfig, airy_root_m       # noqa: E402
from engine.flexure_observer import (                                  # noqa: E402
    FlexureConfig, FlexureSnapshot, FlexureState,
    flexural_rigidity_nm, flexural_parameter_m, flexural_response,
    topographic_load_pa, flexural_deflection_m,
    observe_flexure, install_flexure_observer,
    uninstall_flexure_observer, flexure_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = 0x150A_0061, *,
                resolution: int = 64):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=4, max_agents=20,
                    bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


def _synthetic_relief(n: int = 64, seed: int = 61) -> np.ndarray:
    """Deterministic periodic relief mixing long + short wavelengths."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n] / float(n)
    long_wave = 2500.0 * np.sin(2 * np.pi * x) * np.cos(2 * np.pi * y)
    short_wave = 600.0 * np.sin(2 * np.pi * 12 * x)
    noise = 200.0 * rng.standard_normal((n, n))
    return long_wave + short_wave + noise - 500.0  # some ocean too


# ---------------------------------------------------------------------------
# Pure-law tests
# ---------------------------------------------------------------------------

def test_flexural_rigidity_closed_form():
    cfg = FlexureConfig(elastic_thickness_km=25.0)
    te = 25_000.0
    expected = cfg.young_modulus * te ** 3 / (12 * (1 - cfg.poisson_ratio ** 2))
    assert abs(flexural_rigidity_nm(cfg) - expected) < 1e-3
    # Te = 0 -> no plate strength.
    assert flexural_rigidity_nm(FlexureConfig(elastic_thickness_km=0.0)) == 0.0


def test_flexural_parameter_closed_form():
    cfg = FlexureConfig(elastic_thickness_km=25.0)
    D = flexural_rigidity_nm(cfg)
    drho_g = (cfg.mantle_density - cfg.crust_density) * cfg.gravity
    expected = (4.0 * D / drho_g) ** 0.25
    assert abs(flexural_parameter_m(cfg) - expected) < 1e-9
    # Typical continental value: tens of km.
    assert 10_000.0 < flexural_parameter_m(cfg) < 200_000.0


def test_response_bounds_and_monotonicity():
    cfg = FlexureConfig(elastic_thickness_km=25.0)
    ks = np.linspace(0.0, 1e-3, 256)
    phi = flexural_response(ks, cfg)
    assert abs(phi[0] - 1.0) < 1e-15          # Phi(0) = 1
    assert np.all(phi > 0.0) and np.all(phi <= 1.0)
    assert np.all(np.diff(phi) < 0.0)          # strictly decreasing


def test_load_consistent_with_airy_root():
    """q / ((rho_m - rho_c) g) must equal the Wave 59 Airy root."""
    cfg = FlexureConfig()
    iso = IsostasyConfig()
    drho_g = (cfg.mantle_density - cfg.crust_density) * cfg.gravity
    h = np.array([-4000.0, -500.0, 0.0, 1200.0, 5000.0])
    np.testing.assert_allclose(topographic_load_pa(h, cfg) / drho_g,
                               airy_root_m(h, iso), rtol=0, atol=1e-9)


def test_airy_limit_te_zero():
    """Te -> 0 recovers the Airy root field to machine precision."""
    cfg = FlexureConfig(elastic_thickness_km=0.0)
    h = _synthetic_relief()
    w = flexural_deflection_m(h, cell_m=1000.0, cfg=cfg)
    r = airy_root_m(h, IsostasyConfig())
    assert float(np.max(np.abs(w - r))) < 1e-6


def test_zero_mode_load_balance():
    """Phi(0)=1 => mean deflection == mean Airy root (total support kept)."""
    cfg = FlexureConfig(elastic_thickness_km=25.0)
    h = _synthetic_relief()
    w = flexural_deflection_m(h, cell_m=1000.0, cfg=cfg)
    r = airy_root_m(h, IsostasyConfig())
    scale = float(np.abs(r).max())
    assert abs(float(w.mean()) - float(r.mean())) / scale < 1e-12


def test_regional_smoothing_parseval():
    """Phi <= 1 => deflection never rougher than the Airy root field."""
    cfg = FlexureConfig(elastic_thickness_km=25.0)
    h = _synthetic_relief()
    w = flexural_deflection_m(h, cell_m=1000.0, cfg=cfg)
    r = airy_root_m(h, IsostasyConfig())
    assert float(w.std()) < float(r.std())  # strict: relief has short waves


def test_stiffer_plate_smooths_more():
    """Larger Te => stronger filtering => smaller deflection variance."""
    h = _synthetic_relief()
    stds = []
    for te in (0.0, 10.0, 25.0, 50.0):
        w = flexural_deflection_m(
            h, cell_m=1000.0, cfg=FlexureConfig(elastic_thickness_km=te))
        stds.append(float(w.std()))
    assert all(b < a for a, b in zip(stds, stds[1:]))


def test_deflection_requires_2d():
    import pytest
    with pytest.raises(ValueError):
        flexural_deflection_m(np.array([1.0, 2.0, 3.0]), cell_m=1000.0)


# ---------------------------------------------------------------------------
# Real-world observer tests
# ---------------------------------------------------------------------------

def test_observe_real_world_snapshot():
    sim = _booted_sim("flex_real")
    snap = observe_flexure(sim)
    assert isinstance(snap, FlexureSnapshot)
    assert snap.n_cells > 0
    assert snap.flexural_parameter_km > 0.0
    assert 0.0 < snap.smoothing_ratio <= 1.0
    assert 0.0 < snap.response_at_nyquist < 1.0


def test_real_world_invariants():
    sim = _booted_sim("flex_inv")
    snap = observe_flexure(sim)
    assert snap is not None
    assert snap.zero_mode_residual < 1e-9
    assert snap.smoother_than_airy is True


def test_observe_is_read_only():
    sim = _booted_sim("flex_ro")
    world = sim._genesis_bootstrap_state.world
    b_el = world.elevation_m.copy()
    b_fd = world.flow_dir.copy()
    b_tick = int(sim.tick)
    observe_flexure(sim)
    assert np.array_equal(world.elevation_m, b_el)
    assert np.array_equal(world.flow_dir, b_fd)
    assert int(sim.tick) == b_tick


def test_cross_sim_determinism():
    a = observe_flexure(_booted_sim("flex_d1", seed=0xABCD_0061))
    b = observe_flexure(_booted_sim("flex_d2", seed=0xABCD_0061))
    assert a is not None and b is not None
    assert a.signature == b.signature


def test_install_uninstall_roundtrip_and_cadence():
    sim = _booted_sim("flex_io")
    orig = sim.step
    st = install_flexure_observer(sim, FlexureConfig(snapshot_every=2))
    assert isinstance(st, FlexureState)
    again = install_flexure_observer(sim)
    assert again is st
    assert sim.step is not orig
    for _ in range(4):
        sim.step()
    summ = flexure_summary(sim)
    assert summ["installed"] is True
    assert summ["n_snapshots"] >= 1
    assert summ["zero_mode_residual"] < 1e-9
    assert summ["smoother_than_airy"] is True
    assert uninstall_flexure_observer(sim) is True
    assert sim.step is orig
    assert uninstall_flexure_observer(sim) is False


def test_summary_without_install():
    sim = _booted_sim("flex_nosum")
    assert flexure_summary(sim) == {"installed": False}
