"""Tests d'invariants — Wave 57 Exner mobile-bed / sediment-transport observer.

Couvre :
- Fermeture de masse exacte : Σ erosion == Σ deposition + export aux puits.
- Identité tête de bassin : capacité constante ⇒ seule la tête érode.
- Capacité décroissante ⇒ dépôt du surplus à chaque maille.
- Confluence : export aval == capacité, fermeture conservée.
- Pente aval ≥ 0, capacité ∝ Q^m·S^n.
- Bilan de lit : signe (aggradation > 0, incision < 0) cohérent.
- Réseau réel : déterminisme, read-only, signature sha256 stable.
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
from engine.sediment_observer import (                                 # noqa: E402
    SedimentConfig, SedimentSnapshot, SedimentState,
    downstream_slope, transport_capacity, route_sediment, bed_change_rate,
    observe_sediment, install_sediment_observer,
    uninstall_sediment_observer, sediment_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = 0x5ED1_0057, *,
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


def _chain(length: int = 6):
    R = max(length + 2, 6)
    fd = np.full((R, R), 255, dtype=np.uint8)
    y0 = R // 2
    for x in range(length - 1):
        fd[y0, x] = 0  # east
    fd[y0, length - 1] = 255
    return fd, y0, length


# ---------------------------------------------------------------------------
# Pure-function routing tests
# ---------------------------------------------------------------------------

def test_headwater_identity_constant_capacity():
    fd, y0, length = _chain(7)
    cap = np.zeros_like(fd, dtype=np.float64)
    for i in range(length):
        cap[y0, i] = 5.0
    q_out, ero, dep = route_sediment(fd, cap)
    assert ero[y0, 0] == pytest.approx(5.0)
    for i in range(1, length):
        assert ero[y0, i] == pytest.approx(0.0)
        assert dep[y0, i] == pytest.approx(0.0)
        assert q_out[y0, i] == pytest.approx(5.0)


def test_decreasing_capacity_deposits_surplus():
    fd, y0, length = _chain(5)
    caps = [5.0, 4.0, 3.0, 2.0, 1.0]
    cap = np.zeros_like(fd, dtype=np.float64)
    for i in range(length):
        cap[y0, i] = caps[i]
    q_out, ero, dep = route_sediment(fd, cap)
    assert ero[y0, 0] == pytest.approx(5.0)
    for i in range(1, length):
        assert dep[y0, i] == pytest.approx(1.0)
    assert q_out[y0, length - 1] == pytest.approx(1.0)


def test_exact_mass_closure_random():
    fd, y0, length = _chain(8)
    rng = np.random.default_rng(57)
    cap = rng.uniform(0.0, 5.0, size=fd.shape)
    q_out, ero, dep = route_sediment(fd, cap)
    export = float(q_out[fd == 255].sum())
    assert float(ero.sum()) == pytest.approx(float(dep.sum()) + export)


def test_confluence_and_closure():
    R = 8
    fd = np.full((R, R), 255, dtype=np.uint8)
    fd[2, 1] = 1   # SE
    fd[4, 1] = 7   # NE
    fd[3, 2] = 0   # east
    fd[3, 3] = 255
    cap = np.zeros((R, R), dtype=np.float64)
    cap[2, 1], cap[4, 1], cap[3, 2], cap[3, 3] = 2.0, 3.0, 4.0, 4.0
    q_out, ero, dep = route_sediment(fd, cap)
    # tributaries erode to cap (2,3); confluence inflow 5, cap 4 ⇒ dep 1.
    assert q_out[3, 2] == pytest.approx(4.0)
    assert dep[3, 2] == pytest.approx(1.0)
    export = float(q_out[fd == 255].sum())
    assert float(ero.sum()) == pytest.approx(float(dep.sum()) + export)


def test_detachment_limit_caps_erosion():
    fd, y0, length = _chain(6)
    cap = np.full_like(fd, 10.0, dtype=np.float64)
    elim = np.full_like(fd, 1.0, dtype=np.float64)
    q_out, ero, dep = route_sediment(fd, cap, erosion_limit=elim)
    # Each cell can only supply 1.0 per pass, so q_out grows 1,2,3,...
    for i in range(length):
        assert ero[y0, i] == pytest.approx(1.0)
        assert q_out[y0, i] == pytest.approx(float(i + 1))


def test_route_shape_mismatch_raises():
    fd = np.full((4, 4), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        route_sediment(fd, np.ones((3, 3)))


def test_downstream_slope_non_negative_and_capacity_form():
    # 3-cell west→east step-down chain: elevations 30,20,10.
    R = 5
    fd = np.full((R, R), 255, dtype=np.uint8)
    fd[2, 0] = 0
    fd[2, 1] = 0
    fd[2, 2] = 255
    elev = np.zeros((R, R), dtype=np.float64)
    elev[2, 0], elev[2, 1], elev[2, 2] = 30.0, 20.0, 10.0
    cell_km = 1.0
    slope = downstream_slope(elev, fd, cell_km)
    assert np.all(slope >= 0.0)
    # 10 m drop over 1000 m run ⇒ slope 0.01.
    assert slope[2, 0] == pytest.approx(0.01)
    cfg = SedimentConfig(k_transport=1.0, m_exp=1.0, n_exp=1.0)
    disc = np.full((R, R), 100.0, dtype=np.float64)
    cap = transport_capacity(disc, slope, cfg)
    assert cap[2, 0] == pytest.approx(100.0 * 0.01)


def test_bed_change_sign():
    ero = np.array([[2.0, 0.0]], dtype=np.float64)
    dep = np.array([[0.0, 3.0]], dtype=np.float64)
    dz = bed_change_rate(ero, dep, cell_km=1.0, porosity=0.0)
    assert dz[0, 0] < 0.0   # erosion lowers the bed
    assert dz[0, 1] > 0.0   # deposition raises the bed


# ---------------------------------------------------------------------------
# Observer-on-real-world tests
# ---------------------------------------------------------------------------

def test_observe_returns_snapshot_and_mass_balance():
    sim = _booted_sim("sed_real")
    snap = observe_sediment(sim)
    assert isinstance(snap, SedimentSnapshot)
    assert snap.total_erosion_m3s >= 0.0
    assert snap.mass_balance_residual < 1e-6
    assert snap.n_basins_considered <= snap.n_basins_total
    # Closure echoed at the global level: ΣE ≈ ΣD + export.
    assert snap.total_erosion_m3s == pytest.approx(
        snap.total_deposition_m3s + snap.total_export_m3s, rel=1e-6, abs=1e-6)


def test_observe_read_only():
    sim = _booted_sim("sed_ro")
    world = sim._genesis_bootstrap_state.world \
        if getattr(sim, "_genesis_bootstrap_state", None) is not None else None
    if world is None:
        pytest.skip("no world wired")
    before_fd = world.flow_dir.copy()
    before_elev = world.elevation_m.copy()
    before_tick = int(sim.tick)
    observe_sediment(sim)
    assert np.array_equal(world.flow_dir, before_fd)
    assert np.array_equal(world.elevation_m, before_elev)
    assert int(sim.tick) == before_tick


def test_determinism_cross_sim():
    s1 = _booted_sim("sed_det1", seed=0xBEEF_5701)
    s2 = _booted_sim("sed_det2", seed=0xBEEF_5701)
    a = observe_sediment(s1)
    b = observe_sediment(s2)
    assert a is not None and b is not None
    assert a.signature == b.signature


def test_install_uninstall_roundtrip():
    sim = _booted_sim("sed_io")
    original = sim.step
    state = install_sediment_observer(sim, SedimentConfig(snapshot_every=2))
    assert isinstance(state, SedimentState)
    assert sim.step is not original
    again = install_sediment_observer(sim)
    assert again is state
    assert uninstall_sediment_observer(sim) is True
    assert sim.step is original
    assert uninstall_sediment_observer(sim) is False


def test_cadence_capture():
    sim = _booted_sim("sed_cad")
    install_sediment_observer(sim, SedimentConfig(snapshot_every=2))
    for _ in range(4):
        sim.step()
    summ = sediment_summary(sim)
    assert summ["installed"] is True
    assert summ["n_snapshots"] >= 1
    assert summ["mass_balance_residual"] < 1e-6
