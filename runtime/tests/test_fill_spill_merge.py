"""Tests d'invariants — Wave 67 Fill–Spill–Merge finite-volume lake filling.

Wave 66 (Priority-Flood) livre les **contenants** (jusqu'où une cuvette fermée
POURRAIT retenir un lac). Wave 67 y verse l'apport **réellement routé** (Wave 64)
et laisse chaque cuvette se remplir seulement autant que son inflow le permet —
le bilan volume-fini Fill–Spill–Merge (Barnes, Callaghan & Wickert, ESurf 2021).

Couvre :
- Remplissage hypsométrique exact : cratère à ½ capacité -> niveau à mi-hauteur,
  surface partielle PLANE (l'eau trouve son niveau), eau debout conservée
  (Sum depth*aire == volume d'eau).
- Playa : bassin terminal affamé (inflow << capacité) -> état playa + salinité
  concentrée ~ 1/remplissage.
- Débordement : inflow > capacité -> eau PLAFONNÉE à la capacité (le volume-fini
  ne déborde jamais) + spill du surplus exact.
- Spectre monotone : une fenêtre de remplissage plus longue ne fait qu'augmenter
  le remplissage global, borné par la capacité totale.
- Monde réel : bassins == contenants Wave 66, eau <= contenant partout,
  déterminisme (signature sha256 stable), read-only.
- Install idempotent / uninstall restaure sim.step ; snapshot à la cadence.
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

from engine.world_genesis import GenesisParams, generate_world          # noqa: E402
from engine.lake_hydrology import lakes_from_world, LakeConfig          # noqa: E402
from engine.fill_spill_merge import (                                   # noqa: E402
    FSMConfig, FSMSnapshot, _fill_level,
    fill_depressions, fsm_from_world, observe_fsm,
    install_fsm_observer, uninstall_fsm_observer, fsm_summary,
)

_YEAR_S = 365.25 * 24.0 * 3600.0


class _FakeSim:
    def __init__(self, world):
        self._genesis_world = world
        self.tick = 0

    def step(self, *a, **k):
        self.tick += 1
        return {"tick": self.tick}


def _world(seed=0xC0FFEE_1234):
    gp = GenesisParams(seed=seed & 0xFFFFFFFFFFFFFFFF, resolution=64,
                       n_plates=10, erosion_iters=20, rain_iters=5,
                       river_threshold_cells=30.0, lat_span_deg=30.0)
    return generate_world(gp)


def _crater(depth_m=10.0):
    R = 15
    elev = np.full((R, R), 100.0)
    elev[6:9, 6:9] = 100.0 - depth_m
    flow = np.full((R, R), 255, dtype=np.uint8)   # all cells interior sinks
    cell_area = (1.0 * 1000.0) ** 2
    capacity = 9.0 * depth_m * cell_area
    return elev, flow, cell_area, capacity


def _inflow(rate_cell, y=7, x=7, R=15):
    Q = np.zeros((R, R))
    Q[y, x] = rate_cell
    return Q


# --------------------------------------------------------------------------
# Hypsometric solver
# --------------------------------------------------------------------------

def test_fill_level_flat_bottom_is_linear():
    # Nine cells all at 0 m, sill 10 m, area 1 -> level == volume / n_cells.
    e = np.zeros(9)
    assert _fill_level(e, 1.0, 45.0, 10.0) == pytest.approx(5.0)
    assert _fill_level(e, 1.0, 0.0, 10.0) == pytest.approx(0.0)


def test_fill_level_capped_at_sill():
    e = np.zeros(9)
    # Target far beyond capacity -> clamped to the sill.
    assert _fill_level(e, 1.0, 1e9, 10.0) == pytest.approx(10.0)


def test_fill_level_stepped_hypsometry():
    # Bottom cell at 0, eight rim cells at 4 (sill 10). Filling to level 4 needs
    # only the bottom cell: volume = 4. Above 4 all nine rise together.
    e = np.array([0.0] + [4.0] * 8)
    assert _fill_level(e, 1.0, 4.0, 10.0) == pytest.approx(4.0)
    # +9 more volume raises all nine cells by 1 -> level 5.
    assert _fill_level(e, 1.0, 4.0 + 9.0, 10.0) == pytest.approx(5.0)


# --------------------------------------------------------------------------
# Finite-volume fill of a crater
# --------------------------------------------------------------------------

def test_crater_half_fill_level_and_mass():
    elev, flow, A, cap = _crater(10.0)
    Q = _inflow(0.5 * cap / _YEAR_S)
    _f, _d, wd, lakes = fill_depressions(
        elev, Q, flow, cell_km=1.0, sea_level_m=0.0, window_s=_YEAR_S)
    assert len(lakes) == 1
    lk = lakes[0]
    assert lk.water_volume_m3 == pytest.approx(0.5 * cap, rel=1e-9)
    assert lk.fill_fraction == pytest.approx(0.5)
    assert lk.water_level_m == pytest.approx(95.0)
    assert lk.water_max_depth_m == pytest.approx(5.0)
    assert lk.state == "lake"
    # Standing water is mass-conserved and its surface is flat.
    assert float(wd.sum()) * A == pytest.approx(lk.water_volume_m3, rel=1e-9)
    wet_surface = (elev + wd)[wd > 1e-9]
    assert float(wet_surface.std()) < 1e-9


def test_partial_water_never_exceeds_container_depth():
    elev, flow, A, cap = _crater(10.0)
    Q = _inflow(0.5 * cap / _YEAR_S)
    _f, depth, wd, _lk = fill_depressions(
        elev, Q, flow, cell_km=1.0, sea_level_m=0.0, window_s=_YEAR_S)
    # Standing water depth is bounded by the Priority-Flood container depth.
    assert bool((wd <= depth + 1e-9).all())


def test_starved_terminal_basin_is_playa_with_concentrated_salt():
    elev, flow, A, cap = _crater(10.0)
    Q = _inflow(0.05 * cap / _YEAR_S)
    _f, _d, _wd, lakes = fill_depressions(
        elev, Q, flow, cell_km=1.0, sea_level_m=0.0, window_s=_YEAR_S)
    lk = lakes[0]
    assert lk.is_terminal
    assert lk.state == "playa"
    assert lk.fill_fraction == pytest.approx(0.05)
    assert lk.salinity_factor == pytest.approx(20.0)      # 1 / 0.05
    assert lk.water_level_m < 95.0


def test_inflow_over_capacity_caps_and_spills():
    elev, flow, A, cap = _crater(10.0)
    Q = _inflow(3.0 * cap / _YEAR_S)
    _f, _d, _wd, lakes = fill_depressions(
        elev, Q, flow, cell_km=1.0, sea_level_m=0.0, window_s=_YEAR_S)
    lk = lakes[0]
    assert lk.state == "full"
    assert lk.spills
    assert lk.water_volume_m3 == pytest.approx(cap, rel=1e-9)   # capped
    assert lk.fill_fraction == pytest.approx(1.0)
    assert lk.overflow_m3 == pytest.approx(2.0 * cap, rel=1e-9)  # exact excess
    assert lk.water_level_m == pytest.approx(lk.sill_elev_m)


def test_zero_inflow_leaves_basin_dry():
    elev, flow, A, cap = _crater(10.0)
    _f, _d, wd, lakes = fill_depressions(
        elev, None, flow, cell_km=1.0, sea_level_m=0.0, window_s=_YEAR_S)
    lk = lakes[0]
    assert lk.state == "dry"
    assert lk.water_volume_m3 == pytest.approx(0.0)
    assert not lk.spills
    assert float(wd.sum()) == pytest.approx(0.0)


# --------------------------------------------------------------------------
# Real world
# --------------------------------------------------------------------------

def test_basins_are_the_wave66_containers():
    world = _world()
    lk66 = lakes_from_world(world, LakeConfig())
    snap = fsm_from_world(world, FSMConfig())
    assert snap.n_basins == lk66.n_lakes


def test_standing_water_bounded_by_capacity_real_world():
    world = _world()
    snap = fsm_from_world(world, FSMConfig(fill_window_days=365.25 * 200))
    assert snap.total_water_m3 <= snap.total_capacity_m3 + 1.0
    assert 0.0 <= snap.overall_fill_fraction <= 1.0 + 1e-9
    for lk in snap.lakes_top:
        assert lk.water_volume_m3 <= lk.capacity_m3 + 1.0
        assert lk.water_level_m <= lk.sill_elev_m + 1e-6


def test_longer_window_only_adds_water():
    world = _world()
    fracs, waters = [], []
    for yrs in (1, 30, 300, 3000):
        s = fsm_from_world(world, FSMConfig(fill_window_days=365.25 * yrs))
        fracs.append(s.overall_fill_fraction)
        waters.append(s.total_water_m3)
    assert all(fracs[i] <= fracs[i + 1] + 1e-12 for i in range(len(fracs) - 1))
    assert all(waters[i] <= waters[i + 1] + 1.0 for i in range(len(waters) - 1))


def test_starved_world_makes_playas_longrun_fills():
    world = _world()
    starved = fsm_from_world(world, FSMConfig(fill_window_days=365.25))
    longrun = fsm_from_world(world, FSMConfig(fill_window_days=365.25 * 3000))
    assert (starved.n_playa + starved.n_dry) >= 1
    assert longrun.n_full >= 1
    assert longrun.n_spilling >= 1
    assert longrun.total_water_m3 >= starved.total_water_m3


def test_determinism_signature_stable():
    a = fsm_from_world(_world(seed=0x5EED_0001), FSMConfig())
    b = fsm_from_world(_world(seed=0x5EED_0001), FSMConfig())
    assert a.signature == b.signature
    assert a.n_basins == b.n_basins


def test_read_only_on_world_arrays():
    world = _world()
    e0 = np.asarray(world.elevation_m).copy()
    fd0 = np.asarray(world.flow_dir).copy()
    _ = fsm_from_world(world, FSMConfig())
    assert np.array_equal(np.asarray(world.elevation_m), e0)
    assert np.array_equal(np.asarray(world.flow_dir), fd0)


# --------------------------------------------------------------------------
# Observer install / uninstall
# --------------------------------------------------------------------------

def test_observe_returns_snapshot():
    world = _world()
    sim = _FakeSim(world)
    snap = observe_fsm(sim, FSMConfig())
    assert isinstance(snap, FSMSnapshot)
    assert snap.n_basins >= 1


def test_install_wraps_step_and_captures_snapshot():
    world = _world()
    sim = _FakeSim(world)
    install_fsm_observer(sim, FSMConfig(snapshot_every=1))
    assert getattr(sim, "_fsm_wrapped", False)
    sim.step()
    summ = fsm_summary(sim)
    assert summ["installed"] is True
    assert summ["n_snapshots"] >= 1
    assert uninstall_fsm_observer(sim)
    assert getattr(sim, "_fsm_wrapped", False) is False


def test_install_is_idempotent():
    world = _world()
    sim = _FakeSim(world)
    s1 = install_fsm_observer(sim, FSMConfig())
    s2 = install_fsm_observer(sim, FSMConfig())
    assert s1 is s2
    assert uninstall_fsm_observer(sim)


def test_observe_none_without_world():
    class _Bare:
        tick = 0

        def step(self):
            pass
    assert observe_fsm(_Bare(), FSMConfig()) is None
