"""Tests d'invariants — Wave 66 endorheic depression & lake observer.

Couvre :
- Priority-Flood : filled >= elev partout ; filled == elev sur tout drain libre
  (bord + océan) ; surface d'un lac PLANE (l'eau trouve son niveau).
- Cratère synthétique : volume analytique exact, 1 lac, profondeur/bottom exacts.
- Dépressions imbriquées : fusion en un seul plan d'eau au seuil externe.
- Océan draine libre : un bassin ouvert sur la mer n'est pas endigué.
- Monde réel : lacs émergents, cross-check endoréique vs pits D8, déterminisme,
  read-only, signature sha256 stable.
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
from engine.lake_hydrology import (                                     # noqa: E402
    LakeConfig, LakeSnapshot,
    priority_flood_fill, lakes_from_elevation, lakes_from_world,
    observe_lakes, install_lake_observer, uninstall_lake_observer,
    lake_summary, _seed_mask,
)


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


def _crater():
    elev = np.full((15, 15), 100.0)
    elev[6:9, 6:9] = 90.0
    return elev


# --------------------------------------------------------------------------
# Priority-Flood invariants
# --------------------------------------------------------------------------

def test_filled_never_below_elevation():
    elev = _crater()
    filled = priority_flood_fill(elev, sea_level_m=0.0)
    assert bool((filled >= elev - 1e-9).all())


def test_border_is_free_drain():
    elev = _crater()
    filled = priority_flood_fill(elev, sea_level_m=0.0)
    assert np.allclose(filled[0, :], elev[0, :])
    assert np.allclose(filled[-1, :], elev[-1, :])
    assert np.allclose(filled[:, 0], elev[:, 0])
    assert np.allclose(filled[:, -1], elev[:, -1])


def test_lake_surface_is_flat():
    """One connected lake shares a single spill level — water finds its level."""
    elev = _crater()
    filled, depth, lakes = lakes_from_elevation(elev, cell_km=1.0)
    submerged = filled[depth > 1e-9]
    assert float(submerged.std()) < 1e-9
    assert len(lakes) == 1
    assert abs(lakes[0].surface_elev_m - 100.0) < 1e-9


def test_crater_analytic_volume():
    elev = _crater()
    _f, _d, lakes = lakes_from_elevation(elev, cell_km=1.0)
    assert len(lakes) == 1
    lk = lakes[0]
    assert lk.n_cells == 9
    assert abs(lk.max_depth_m - 10.0) < 1e-9
    assert abs(lk.bottom_elev_m - 90.0) < 1e-9
    # 9 cells x 10 m x (1000 m)^2
    assert abs(lk.volume_m3 - 9 * 10 * (1000.0 ** 2)) < 1.0


def test_nested_basins_merge_to_single_surface():
    elev = np.full((11, 11), 100.0)
    elev[2:9, 2:9] = 50.0
    elev[4:7, 4:7] = 20.0
    filled, _d, lakes = lakes_from_elevation(elev, cell_km=1.0)
    assert len(lakes) == 1
    assert abs(lakes[0].surface_elev_m - 100.0) < 1e-9
    assert float(filled[filled > elev + 1e-9].std()) < 1e-9


def test_ocean_seeds_free_drain():
    elev = np.full((11, 11), 50.0)
    elev[:, 0] = -5.0          # a sea column below sea level
    seed = _seed_mask(elev, sea_level_m=0.0)
    assert bool(seed[:, 0].all())            # ocean cells seed the flood
    assert bool(seed[0, :].all())            # so does the border
    filled = priority_flood_fill(elev, sea_level_m=0.0)
    assert np.allclose(filled[:, 0], elev[:, 0])


def test_flat_terrain_has_no_lakes():
    elev = np.full((12, 12), 42.0)
    _f, _d, lakes = lakes_from_elevation(elev, cell_km=1.0)
    assert lakes == []


def test_min_lake_cells_filters_tiny_pits():
    elev = np.full((11, 11), 10.0)
    elev[5, 5] = 0.5                          # single-cell pit
    _f, _d, lakes = lakes_from_elevation(
        elev, cell_km=1.0, config=LakeConfig(min_lake_cells=2))
    assert lakes == []


# --------------------------------------------------------------------------
# Real world
# --------------------------------------------------------------------------

def test_real_world_lakes_emerge():
    snap = lakes_from_world(_world(), LakeConfig())
    assert isinstance(snap, LakeSnapshot)
    assert snap.n_lakes >= 1
    assert snap.total_impounded_volume_m3 > 0.0
    assert snap.max_lake_depth_m > 0.0
    assert 0.0 <= snap.lake_area_fraction_land <= 1.0


def test_endorheic_cross_check_against_d8_pits():
    world = _world()
    sea = float(world.params.sea_level_m)
    fd = np.asarray(world.flow_dir)
    ev = np.asarray(world.elevation_m)
    interior_pits = int(((fd == 255) & (ev > sea)).sum())
    snap = lakes_from_world(world, LakeConfig())
    # A raw (un-routed) DEM's closed basins are terminal: at least one lake
    # must be endorheic, and it can only be so if the world marks interior pits.
    assert interior_pits >= 1
    assert snap.n_endorheic >= 1
    assert snap.n_endorheic <= snap.n_lakes


def test_deterministic_signature():
    a = lakes_from_world(_world(seed=0x5EED_0001), LakeConfig())
    b = lakes_from_world(_world(seed=0x5EED_0001), LakeConfig())
    assert a.signature == b.signature
    assert a.n_lakes == b.n_lakes


def test_observe_is_read_only():
    world = _world()
    e0 = np.asarray(world.elevation_m).copy()
    fd0 = np.asarray(world.flow_dir).copy()
    lakes_from_world(world, LakeConfig())
    assert np.array_equal(np.asarray(world.elevation_m), e0)
    assert np.array_equal(np.asarray(world.flow_dir), fd0)


# --------------------------------------------------------------------------
# Observer install / uninstall
# --------------------------------------------------------------------------

def test_observe_lakes_resolves_world():
    sim = _FakeSim(_world())
    snap = observe_lakes(sim, LakeConfig())
    assert snap is not None
    assert snap.n_lakes >= 1


def test_observe_lakes_none_without_world():
    class _Bare:
        tick = 0
    assert observe_lakes(_Bare(), LakeConfig()) is None


def test_install_captures_snapshot_and_uninstall_restores():
    sim = _FakeSim(_world())
    original = sim.step
    state = install_lake_observer(sim, LakeConfig(snapshot_every=1))
    assert state.wrapped is True
    sim.step()                                    # tick 1 -> cadence hit
    summ = lake_summary(sim)
    assert summ["installed"] is True
    assert summ["n_snapshots"] >= 1
    assert uninstall_lake_observer(sim) is True
    assert sim.step == original                   # step behaviour restored
    assert getattr(sim, "_lake_wrapped", False) is False
    assert lake_summary(sim) == {"installed": False}


def test_install_is_idempotent():
    sim = _FakeSim(_world())
    s1 = install_lake_observer(sim, LakeConfig())
    s2 = install_lake_observer(sim, LakeConfig(snapshot_every=8))
    assert s1 is s2
    assert s1.config.snapshot_every == 8
    uninstall_lake_observer(sim)


def test_priority_flood_rejects_bad_shapes():
    with pytest.raises(ValueError):
        priority_flood_fill(np.zeros((4,)))       # not 2-D
    with pytest.raises(ValueError):
        priority_flood_fill(np.zeros((4, 4)), seed_mask=np.zeros((3, 3), bool))
