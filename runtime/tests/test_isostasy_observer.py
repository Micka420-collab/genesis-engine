"""Tests d'invariants — Wave 59 isostasie d'Airy / racine crustale observer.

Couvre :
- Loi de racine d'Airy : r = rho_c/(rho_m−rho_c)·h sur les terres ;
  anti-racine = (rho_m−rho_w)/(rho_m−rho_c)·|h| en mer.
- Compensation équipression : la pression lithostatique à la profondeur de
  compensation D_c est identique pour toutes les colonnes (résidu ≈ 0).
- Racines de montagnes : l'épaisseur crustale croît avec l'altitude.
- Cas mer : croûte amincie + anti-racine (Moho remonte).
- Monde réel : déterminisme, read-only, signature sha256 stable.
- Install idempotent / uninstall restaure step ; snapshot à la cadence.
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
from engine.isostasy_observer import (                                 # noqa: E402
    IsostasyConfig, IsostasySnapshot, IsostasyState,
    airy_root_m, crustal_thickness_m, compensation_pressure_pa,
    observe_isostasy, install_isostasy_observer,
    uninstall_isostasy_observer, isostasy_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = 0x150A_0059, *,
                resolution: int = 64):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=4, max_agents=20,
                    bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


# ---------------------------------------------------------------------------
# Pure-law tests
# ---------------------------------------------------------------------------

def test_airy_root_land_closed_form():
    cfg = IsostasyConfig()
    h = 2000.0
    expected = cfg.crust_density / (cfg.mantle_density - cfg.crust_density) * h
    assert abs(airy_root_m(h, cfg) - expected) < 1e-9
    # Sea level ⇒ no root.
    assert abs(airy_root_m(0.0, cfg)) < 1e-12


def test_airy_antiroot_ocean_sign_and_magnitude():
    cfg = IsostasyConfig()
    d = 4000.0  # 4 km of water
    r = airy_root_m(-d, cfg)
    assert r < 0.0  # anti-root, mantle rises
    expected = (cfg.crust_density - cfg.water_density) / (
        cfg.mantle_density - cfg.crust_density) * d
    assert abs(-r - expected) < 1e-9


def test_root_is_monotonic_in_elevation():
    cfg = IsostasyConfig()
    hs = np.array([-3000.0, -500.0, 0.0, 500.0, 3000.0])
    roots = airy_root_m(hs, cfg)
    assert np.all(np.diff(roots) > 0.0)


def test_crust_thickens_with_elevation():
    cfg = IsostasyConfig()
    hs = np.array([-2000.0, 0.0, 1000.0, 4000.0])
    H = crustal_thickness_m(hs, cfg)
    assert np.all(np.diff(H) > 0.0)
    # Reference sea-level column is exactly T0.
    assert abs(crustal_thickness_m(0.0, cfg)
               - cfg.reference_crust_km * 1000.0) < 1e-6


def test_equal_pressure_compensation_uniform():
    """Airy compensation ⇒ pressure at D_c is identical for every column."""
    cfg = IsostasyConfig()
    h = np.array([-5000.0, -1000.0, 0.0, 800.0, 2500.0, 6000.0])
    root = airy_root_m(h, cfg)
    moho = cfg.reference_crust_km * 1000.0 + root
    Dc = float(moho.max()) + 10_000.0
    P = compensation_pressure_pa(h, Dc, cfg)
    residual = (P.max() - P.min()) / P.mean()
    assert residual < 1e-12


def test_compensation_margin_invariant_to_depth():
    """The equal-pressure property is independent of the chosen D_c margin."""
    cfg = IsostasyConfig()
    h = np.array([-2000.0, 0.0, 1500.0, 4000.0])
    root = airy_root_m(h, cfg)
    moho = cfg.reference_crust_km * 1000.0 + root
    base = float(moho.max())
    for margin in (1_000.0, 5_000.0, 50_000.0):
        P = compensation_pressure_pa(h, base + margin, cfg)
        assert (P.max() - P.min()) / P.mean() < 1e-12


# ---------------------------------------------------------------------------
# Real-world observer tests
# ---------------------------------------------------------------------------

def test_observe_real_world_snapshot():
    sim = _booted_sim("iso_real")
    snap = observe_isostasy(sim)
    assert isinstance(snap, IsostasySnapshot)
    assert snap.n_cells > 0
    assert snap.mean_crust_thickness_km > 0.0
    assert snap.max_crust_thickness_km >= snap.min_crust_thickness_km


def test_real_world_equal_pressure_invariant():
    sim = _booted_sim("iso_resid")
    snap = observe_isostasy(sim)
    assert snap is not None
    assert snap.isostatic_residual < 1e-6
    assert snap.roots_track_elevation is True


def test_observe_is_read_only():
    sim = _booted_sim("iso_ro")
    world = sim._genesis_bootstrap_state.world
    b_el = world.elevation_m.copy()
    b_fd = world.flow_dir.copy()
    b_tick = int(sim.tick)
    observe_isostasy(sim)
    assert np.array_equal(world.elevation_m, b_el)
    assert np.array_equal(world.flow_dir, b_fd)
    assert int(sim.tick) == b_tick


def test_cross_sim_determinism():
    a = observe_isostasy(_booted_sim("iso_d1", seed=0xABCD_0059))
    b = observe_isostasy(_booted_sim("iso_d2", seed=0xABCD_0059))
    assert a is not None and b is not None
    assert a.signature == b.signature


def test_install_uninstall_roundtrip_and_cadence():
    sim = _booted_sim("iso_io")
    orig = sim.step
    st = install_isostasy_observer(sim, IsostasyConfig(snapshot_every=2))
    assert isinstance(st, IsostasyState)
    again = install_isostasy_observer(sim)
    assert again is st
    assert sim.step is not orig
    for _ in range(4):
        sim.step()
    summ = isostasy_summary(sim)
    assert summ["installed"] is True
    assert summ["n_snapshots"] >= 1
    assert summ["isostatic_residual"] < 1e-6
    assert uninstall_isostasy_observer(sim) is True
    assert sim.step is orig
    assert uninstall_isostasy_observer(sim) is False


def test_summary_without_install():
    sim = _booted_sim("iso_nosum")
    assert isostasy_summary(sim) == {"installed": False}
