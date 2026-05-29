"""Tests d'invariants — Wave 49 watershed / Strahler observer.

Couvre :
- Strahler order monotone le long d'une rivière unique.
- Promotion d'ordre sur Y-confluence.
- Réseau dendritique réel : déterminisme, read-only, signature sha256 stable.
- Horton ratios finis sur réseau bien formé.
- Install idempotent / uninstall restaure step.
- Snapshot capturé à la cadence configurée.
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
from engine.watershed_observer import (                                # noqa: E402
    WatershedConfig, WatershedSnapshot, WatershedHistory, WatershedState,
    BasinStats,
    compute_strahler_order, compute_horton_ratios,
    observe_watersheds, install_watershed_observer,
    uninstall_watershed_observer, watershed_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = 0xC0DE_4949, *,
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
    rm = np.zeros((R, R), dtype=bool)
    y0 = R // 2
    for x in range(length - 1):
        fd[y0, x] = 0  # east
        rm[y0, x] = True
    rm[y0, length - 1] = True
    fd[y0, length - 1] = 255
    return fd, rm


def _y_confluence():
    R = 10
    fd = np.full((R, R), 255, dtype=np.uint8)
    rm = np.zeros((R, R), dtype=bool)
    for (y, x) in [(1, 1), (2, 2)]:
        fd[y, x] = 1   # SE
        rm[y, x] = True
    for (y, x) in [(5, 1), (4, 2)]:
        fd[y, x] = 7   # NE
        rm[y, x] = True
    rm[3, 3] = True; fd[3, 3] = 0
    rm[3, 4] = True; fd[3, 4] = 0
    rm[3, 5] = True; fd[3, 5] = 255
    return fd, rm


# ---------------------------------------------------------------------------
# Pure-function tests
# ---------------------------------------------------------------------------

def test_strahler_chain_single_order():
    fd, rm = _chain(length=7)
    order = compute_strahler_order(fd, rm)
    assert int(order[rm].min()) == 1
    assert int(order[rm].max()) == 1
    # Non-river cells must remain at 0.
    assert int(order[~rm].sum()) == 0


def test_strahler_y_confluence_promotes_to_order_two():
    fd, rm = _y_confluence()
    order = compute_strahler_order(fd, rm)
    assert int(order[1, 1]) == 1 and int(order[5, 1]) == 1
    assert int(order[2, 2]) == 1 and int(order[4, 2]) == 1
    assert int(order[3, 3]) == 2  # junction promoted
    assert int(order[3, 5]) == 2  # outlet keeps order 2


def test_strahler_empty_river_mask_zero_orders():
    R = 5
    fd = np.full((R, R), 255, dtype=np.uint8)
    rm = np.zeros((R, R), dtype=bool)
    order = compute_strahler_order(fd, rm)
    assert int(order.sum()) == 0


def test_strahler_capped_by_max_order():
    fd, rm = _y_confluence()
    capped = compute_strahler_order(fd, rm, max_order=1)
    # The junction should be clamped at 1 because of max_order.
    assert int(capped[3, 3]) == 1


def test_horton_ratios_zero_when_single_order():
    fd, rm = _chain(length=5)
    order = compute_strahler_order(fd, rm)
    rb, rl, counts, lengths = compute_horton_ratios(order, fd, rm, cell_km=1.0)
    assert rb == 0.0 and rl == 0.0
    assert counts == {1: 5}
    assert lengths.get(1, 0.0) > 0.0


def test_horton_ratios_finite_on_two_orders():
    fd, rm = _y_confluence()
    order = compute_strahler_order(fd, rm)
    rb, rl, counts, lengths = compute_horton_ratios(order, fd, rm, cell_km=10.0)
    assert rb > 0.0 and rb < 10.0
    assert rl >= 0.0 and not np.isnan(rl)
    assert set(counts.keys()) == {1, 2}


# ---------------------------------------------------------------------------
# Real-world observer tests
# ---------------------------------------------------------------------------

def test_observe_returns_snapshot_on_real_world():
    sim = _booted_sim("ws_real_a", seed=0xC0DE_4949_001)
    snap = observe_watersheds(sim)
    assert isinstance(snap, WatershedSnapshot)
    assert snap.n_basins_total >= 1
    assert snap.map_area_km2 > 0.0
    assert snap.cell_km > 0.0
    assert len(snap.signature) == 64


def test_observe_is_read_only():
    sim = _booted_sim("ws_readonly", seed=0xC0DE_4949_002)
    world = sim._genesis_bootstrap_state.world
    fd_b = np.array(world.flow_dir, copy=True)
    rm_b = np.array(world.river_mask, copy=True)
    elev_b = np.array(world.elevation_m, copy=True)
    wid_b = np.array(world.watershed_id, copy=True)
    tick_b = int(sim.tick)
    _ = observe_watersheds(sim)
    assert int(sim.tick) == tick_b
    assert np.array_equal(world.flow_dir, fd_b)
    assert np.array_equal(world.river_mask, rm_b)
    assert np.array_equal(world.elevation_m, elev_b)
    assert np.array_equal(world.watershed_id, wid_b)


def test_cross_sim_determinism_same_seed_same_signature():
    seed = 0xC0DE_4949_003
    sim_a = _booted_sim("ws_det_a", seed=seed)
    sim_b = _booted_sim("ws_det_b", seed=seed)
    sig_a = observe_watersheds(sim_a).signature
    sig_b = observe_watersheds(sim_b).signature
    assert sig_a == sig_b


def test_observe_returns_none_when_no_world():
    cfg = SimConfig(name="ws_nowor", seed=1, founders=2, max_agents=4,
                    bounds_km=(0.1, 0.1))
    sim = Simulation(cfg)
    # No bootstrap_genesis_sim → no macro world available.
    assert observe_watersheds(sim) is None


def test_horton_ratios_finite_on_real_world():
    sim = _booted_sim("ws_horton", seed=0xC0DE_4949_004)
    snap = observe_watersheds(sim)
    assert snap is not None
    assert snap.bifurcation_ratio >= 0.0
    assert snap.length_ratio >= 0.0
    assert not np.isnan(snap.bifurcation_ratio)
    assert not np.isnan(snap.length_ratio)


def test_drainage_density_coherent_with_rivers():
    sim = _booted_sim("ws_dd", seed=0xC0DE_4949_005)
    snap = observe_watersheds(sim)
    assert snap is not None
    if snap.total_river_cells == 0:
        assert snap.global_drainage_density == 0.0
    else:
        # Must be non-negative; usually > 0 because river segments contribute.
        assert snap.global_drainage_density >= 0.0


def test_basin_stats_areas_sum_le_map_area():
    sim = _booted_sim("ws_basin", seed=0xC0DE_4949_006)
    snap = observe_watersheds(sim)
    assert snap is not None
    # Top basins should each be smaller than the whole map.
    for b in snap.basins_top:
        assert 0 < b.area_km2 <= snap.map_area_km2
        # Hypsometric integral bounded by [0, 1].
        assert 0.0 <= b.hypsometric_integral <= 1.0
        assert b.max_strahler >= 0


# ---------------------------------------------------------------------------
# Install / cadence tests
# ---------------------------------------------------------------------------

def test_install_uninstall_round_trip():
    sim = _booted_sim("ws_install", seed=0xC0DE_4949_007)
    step_before = sim.step
    install_watershed_observer(
        sim, WatershedConfig(snapshot_every=3))
    assert sim.step is not step_before
    assert getattr(sim, "_watershed_wrapped", False) is True
    restored = uninstall_watershed_observer(sim)
    assert restored is True
    assert sim.step is step_before
    assert watershed_summary(sim) == {"installed": False}


def test_double_install_idempotent_updates_config():
    sim = _booted_sim("ws_idem", seed=0xC0DE_4949_008)
    s1 = install_watershed_observer(
        sim, WatershedConfig(snapshot_every=4))
    step_after_first = sim.step
    s2 = install_watershed_observer(
        sim, WatershedConfig(snapshot_every=7))
    assert s2 is s1
    # No additional wrapping.
    assert sim.step is step_after_first
    assert s2.config.snapshot_every == 7
    uninstall_watershed_observer(sim)


def test_installed_observer_captures_at_cadence():
    sim = _booted_sim("ws_cadence", seed=0xC0DE_4949_009)
    install_watershed_observer(sim, WatershedConfig(snapshot_every=2))
    for _ in range(7):
        sim.step()
    summary = watershed_summary(sim)
    assert summary["installed"] is True
    assert int(summary["n_snapshots"]) >= 2
    assert summary["last_signature"] is not None
    uninstall_watershed_observer(sim)


def test_full_run_determinism_observed_stream():
    """Two installs on two fresh sims with identical seed produce the same
    stream of signatures."""
    def _run(seed):
        sim = _booted_sim(f"ws_full_{seed}", seed=seed)
        install_watershed_observer(sim, WatershedConfig(snapshot_every=2))
        for _ in range(7):
            sim.step()
        snaps = sim._watershed_state.history.snapshots
        return tuple(s.signature for s in snaps)

    seed = 0xC0DE_4949_010
    a = _run(seed)
    b = _run(seed)
    assert a == b
    assert len(a) >= 2
