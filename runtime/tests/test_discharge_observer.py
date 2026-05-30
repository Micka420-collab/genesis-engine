"""Tests d'invariants — Wave 53 LTI river-discharge routing observer.

Couvre :
- Conservation de masse : Σ discharge[sinks] == Σ runoff.
- Monotonie aval : discharge croît le long d'une rivière unique.
- Identité runoff unitaire : discharge ≡ aire contributrice D8 (self inclus).
- Confluence : discharge aval == somme des branches + runoff local.
- Réseau réel : déterminisme, read-only, signature sha256 stable.
- runoff_field_m3s : non-négatif, ET bornée par P.
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
from engine.genesis_bootstrap import bootstrap_genesis_sim             # noqa: E402
from engine.discharge_observer import (                                # noqa: E402
    DischargeConfig, DischargeSnapshot, DischargeHistory, DischargeState,
    BasinDischarge,
    route_runoff, runoff_field_m3s,
    observe_discharge, install_discharge_observer,
    uninstall_discharge_observer, discharge_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = 0xD15C_4953, *,
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
    """A single west→east chain of cells, last one a sink."""
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

def test_unit_runoff_is_contributing_area():
    fd, y0, length = _chain(length=7)
    runoff = np.ones_like(fd, dtype=np.float64)
    q = route_runoff(fd, runoff)
    # Along the chain discharge should be 1,2,3,... up to the outlet, then the
    # outlet holds the whole chain length. Off-chain cells are isolated sinks
    # with discharge == their own runoff (1).
    for i in range(length):
        assert q[y0, i] == pytest.approx(float(i + 1))


def test_mass_conservation_chain():
    fd, y0, length = _chain(length=6)
    rng = np.random.default_rng(0)
    runoff = rng.uniform(0.0, 5.0, size=fd.shape)
    q = route_runoff(fd, runoff)
    is_sink = (fd == 255)
    assert float(q[is_sink].sum()) == pytest.approx(float(runoff.sum()))


def test_monotonic_downstream():
    fd, y0, length = _chain(length=8)
    runoff = np.ones_like(fd, dtype=np.float64)
    q = route_runoff(fd, runoff)
    chain_q = [q[y0, i] for i in range(length)]
    assert all(b >= a for a, b in zip(chain_q[:-1], chain_q[1:]))


def test_confluence_sum():
    # Two tributaries meeting at one cell that drains east to a sink.
    R = 8
    fd = np.full((R, R), 255, dtype=np.uint8)
    # tributary A: (2,1)->SE->(3,2); tributary B: (4,1)->NE->(3,2)
    fd[2, 1] = 1   # SE
    fd[4, 1] = 7   # NE
    fd[3, 2] = 0   # confluence flows east
    fd[3, 3] = 255  # sink
    runoff = np.zeros((R, R), dtype=np.float64)
    runoff[2, 1] = 2.0
    runoff[4, 1] = 3.0
    runoff[3, 2] = 1.0
    q = route_runoff(fd, runoff)
    # confluence discharge = its own runoff + both tributaries
    assert q[3, 2] == pytest.approx(6.0)
    assert q[3, 3] == pytest.approx(6.0)  # sink receives full chain


def test_route_shape_mismatch_raises():
    fd = np.full((4, 4), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        route_runoff(fd, np.ones((3, 3)))


def test_runoff_field_non_negative_and_et_bounded():
    cfg = DischargeConfig(et_mm_per_degc=45.0)
    precip = np.array([[0.0, 500.0], [1200.0, 800.0]])
    temp = np.array([[30.0, -5.0], [40.0, 10.0]])
    r = runoff_field_m3s(precip, temp, cell_km=10.0, cfg=cfg)
    assert np.all(r >= 0.0)
    # Cell with huge temp & modest precip → ET clamped to P → runoff 0.
    assert r[1, 0] == pytest.approx(0.0)
    # Cold cell keeps all its precip.
    assert r[0, 1] > 0.0


# ---------------------------------------------------------------------------
# Observer-on-real-world tests
# ---------------------------------------------------------------------------

def test_observe_returns_snapshot_and_mass_balance():
    sim = _booted_sim("disc_real")
    snap = observe_discharge(sim)
    assert isinstance(snap, DischargeSnapshot)
    assert snap.total_runoff_m3s >= 0.0
    # Mass closes to round-off: outflow at sinks == total runoff.
    assert snap.mass_balance_residual < 1e-6
    assert snap.max_discharge_m3s >= snap.mean_river_discharge_m3s
    assert snap.n_basins_considered <= snap.n_basins_total


def test_observe_read_only():
    sim = _booted_sim("disc_ro")
    world = sim._genesis_bootstrap_state.world \
        if getattr(sim, "_genesis_bootstrap_state", None) is not None else None
    if world is None:
        pytest.skip("no world wired")
    before_fd = world.flow_dir.copy()
    before_precip = world.precip_mm.copy()
    before_tick = int(sim.tick)
    observe_discharge(sim)
    assert np.array_equal(world.flow_dir, before_fd)
    assert np.array_equal(world.precip_mm, before_precip)
    assert int(sim.tick) == before_tick


def test_determinism_cross_sim():
    s1 = _booted_sim("disc_det1", seed=0xBEEF_5301)
    s2 = _booted_sim("disc_det2", seed=0xBEEF_5301)
    a = observe_discharge(s1)
    b = observe_discharge(s2)
    assert a is not None and b is not None
    assert a.signature == b.signature


def test_install_uninstall_roundtrip():
    sim = _booted_sim("disc_io")
    original = sim.step
    state = install_discharge_observer(sim, DischargeConfig(snapshot_every=2))
    assert isinstance(state, DischargeState)
    assert sim.step is not original
    # Idempotent: second install does not double-wrap.
    again = install_discharge_observer(sim)
    assert again is state
    assert uninstall_discharge_observer(sim) is True
    assert sim.step is original
    assert uninstall_discharge_observer(sim) is False


def test_cadence_capture():
    sim = _booted_sim("disc_cad")
    install_discharge_observer(sim, DischargeConfig(snapshot_every=2))
    for _ in range(4):
        sim.step()
    summ = discharge_summary(sim)
    assert summ["installed"] is True
    assert summ["n_snapshots"] >= 1
    assert summ["mass_balance_residual"] < 1e-6
