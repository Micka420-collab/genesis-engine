"""Tests d'invariants — Wave 55 transient linear-reservoir hydrograph observer.

Couvre :
- Réservoir linéaire : fermeture de masse exacte (s0 + ΣI·dt − out_cum == S).
- Récession monotone : Q[n] == Q0·a**n, strictement décroissante.
- Convergence pas-à-pas : entrée constante depuis vide ⇒ Q → I (lien Wave 53).
- Temps de demi-récession ≈ k·ln2.
- Hydrogramme d'orage : montée, pic au creux de l'orage, récession.
- Validation des paramètres (k, dt, n_steps, forme inflow).
- Monde réel : snapshot, read-only, déterminisme sha256, lien Q_pic ≤ Q*.
- Install idempotent / uninstall restaure step ; capture à la cadence.
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
from engine.genesis_bootstrap import bootstrap_genesis_sim             # noqa: E402
from engine.hydrograph_observer import (                               # noqa: E402
    HydrographConfig, HydrographSnapshot, HydrographState,
    linear_reservoir_response, storm_hydrograph, half_recession_days,
    observe_hydrograph, install_hydrograph_observer,
    uninstall_hydrograph_observer, hydrograph_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = 0xD15C_5500, *,
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
# Pure-function reservoir tests (world-free)
# ---------------------------------------------------------------------------

def test_mass_closure_exact():
    inflow = np.array([2.0, 2.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)
    k, dt = 3.0, 0.5
    t, Q, S, out_cum = linear_reservoir_response(inflow, k, dt, inflow.size)
    cum_in = np.concatenate(([0.0], np.cumsum(inflow * dt)))
    # s0 (=0) + cumulative input − cumulative outflow == storage, exactly.
    assert np.allclose(0.0 + cum_in - out_cum, S, atol=1e-12, rtol=0.0)


def test_recession_is_geometric_and_monotone():
    k, dt, n = 4.0, 0.25, 40
    q0 = 7.0
    s0 = q0 * k
    t, Q, S, out_cum = linear_reservoir_response(0.0, k, dt, n, s0=s0)
    a = math.exp(-dt / k)
    assert Q[0] == pytest.approx(q0)
    # Strictly decreasing recession.
    assert all(b < a_ for a_, b in zip(Q[:-1], Q[1:]))
    # Exact geometric decay.
    for nn in range(n + 1):
        assert Q[nn] == pytest.approx(q0 * a ** nn, rel=1e-9)
    # All released water leaves: out_cum + storage == initial storage.
    assert out_cum[-1] + S[-1] == pytest.approx(s0, rel=1e-12)


def test_step_response_converges_to_inflow():
    # Constant input from empty rises monotonically toward I (= Wave 53 Q*).
    k, dt = 2.0, 0.5
    n = int(round(60.0 / dt))   # horizon >> k
    inflow = 5.0
    t, Q, S, out_cum = linear_reservoir_response(inflow, k, dt, n, s0=0.0)
    assert Q[0] == pytest.approx(0.0)
    assert all(b >= a_ for a_, b in zip(Q[:-1], Q[1:]))   # monotone rise
    assert Q[-1] == pytest.approx(inflow, rel=1e-6)


def test_half_recession_matches_k_ln2():
    cfg = HydrographConfig(storage_k_days=6.0, dt_days=0.25,
                           storm_days=2.0, horizon_days=80.0)
    t, Q, _out = storm_hydrograph(steady_discharge=10.0, cfg=cfg)
    half = half_recession_days(t, Q)
    assert half == pytest.approx(cfg.storage_k_days * math.log(2.0),
                                 abs=2 * cfg.dt_days)


def test_storm_hydrograph_shape():
    cfg = HydrographConfig(storage_k_days=5.0, dt_days=0.5,
                           storm_days=3.0, horizon_days=40.0)
    t, Q, out_cum = storm_hydrograph(steady_discharge=12.0, cfg=cfg)
    assert Q[0] == pytest.approx(0.0)            # starts empty
    peak_idx = int(np.argmax(Q))
    storm_steps = int(round(cfg.storm_days / cfg.dt_days))
    assert peak_idx == storm_steps               # peak at end of the storm
    assert Q[peak_idx] < 12.0                     # never exceeds equilibrium
    # Recession after the peak is strictly decreasing.
    rec = Q[peak_idx:]
    assert all(b < a_ for a_, b in zip(rec[:-1], rec[1:]))


def test_param_validation():
    with pytest.raises(ValueError):
        linear_reservoir_response(1.0, k=0.0, dt=0.5, n_steps=4)
    with pytest.raises(ValueError):
        linear_reservoir_response(1.0, k=1.0, dt=0.0, n_steps=4)
    with pytest.raises(ValueError):
        linear_reservoir_response(1.0, k=1.0, dt=0.5, n_steps=0)
    with pytest.raises(ValueError):
        linear_reservoir_response(np.ones(3), k=1.0, dt=0.5, n_steps=4)


# ---------------------------------------------------------------------------
# Observer-on-real-world tests
# ---------------------------------------------------------------------------

def test_observe_returns_snapshot():
    sim = _booted_sim("hyd_real")
    snap = observe_hydrograph(sim)
    assert isinstance(snap, HydrographSnapshot)
    assert snap.n_steps >= 1
    assert snap.n_basins_considered <= snap.n_basins_total
    # Mass closes for every basin reservoir.
    assert snap.max_volume_residual < 1e-6
    # Peak never exceeds the stationary discharge of any basin.
    for b in snap.basins_top:
        assert b.peak_discharge_m3s <= b.steady_discharge_m3s + 1e-9
        assert b.time_to_peak_days >= 0.0


def test_observe_read_only():
    sim = _booted_sim("hyd_ro")
    world = sim._genesis_bootstrap_state.world \
        if getattr(sim, "_genesis_bootstrap_state", None) is not None else None
    if world is None:
        pytest.skip("no world wired")
    before_fd = world.flow_dir.copy()
    before_precip = world.precip_mm.copy()
    before_tick = int(sim.tick)
    observe_hydrograph(sim)
    assert np.array_equal(world.flow_dir, before_fd)
    assert np.array_equal(world.precip_mm, before_precip)
    assert int(sim.tick) == before_tick


def test_determinism_cross_sim():
    a = observe_hydrograph(_booted_sim("hyd_d1", seed=0xBEEF_5500))
    b = observe_hydrograph(_booted_sim("hyd_d2", seed=0xBEEF_5500))
    assert a is not None and b is not None
    assert a.signature == b.signature


def test_install_uninstall_roundtrip():
    sim = _booted_sim("hyd_io")
    original = sim.step
    state = install_hydrograph_observer(sim, HydrographConfig(snapshot_every=2))
    assert isinstance(state, HydrographState)
    assert sim.step is not original
    again = install_hydrograph_observer(sim)
    assert again is state
    assert uninstall_hydrograph_observer(sim) is True
    assert sim.step is original
    assert uninstall_hydrograph_observer(sim) is False


def test_cadence_capture():
    sim = _booted_sim("hyd_cad")
    install_hydrograph_observer(sim, HydrographConfig(snapshot_every=2))
    for _ in range(4):
        sim.step()
    summ = hydrograph_summary(sim)
    assert summ["installed"] is True
    assert summ["n_snapshots"] >= 1
    assert summ["max_volume_residual"] < 1e-6
