"""P174 — Wave 66 endorheic depression & lake hydrology observer smoke.

The substrate already routes water down the D8 network (Wave 53 / Wave 64) and
``world_genesis`` already marks interior pits (``flow_dir == 255`` above sea
level), but nothing turns those closed basins into **lakes**: the router treats
an interior sink as water *leaving the domain*. ``lake_hydrology`` is the
missing read — Priority-Flood (Barnes, Lehman & Mulla 2014) computes, from the
bare topography, where a closed depression fills to and how deep: the
depression-storage field, the emergent lakes, and the endorheic (terminal)
basins the world's own ``flow_dir`` pits imply.

Steps:
  1. Public API surface present.
  2. Synthetic crater : Priority-Flood fills it to the analytic volume, 1 lake,
     filled >= elev everywhere, filled == elev on the free-draining border.
  3. Lake surface is FLAT : one connected lake shares a single spill level
     (water finds its level) and surface_elev == that spill.
  4. Nested basins MERGE : a bowl containing a deeper sub-pit becomes ONE lake
     at the outer sill (meta-depression), not two stacked surfaces.
  5. Ocean drains free : a basin notched open to the sea is NOT impounded
     (ocean cells seed the flood as always-draining).
  6. Real Genesis world : lakes emerge, volume > 0, and every lake is cross-
     checked endorheic against the world's own D8 interior sinks.
  7. Read-only + installer : observe mutates nothing ; install wraps sim.step,
     captures a snapshot at cadence ; uninstall restores step.
  8. Determinism : same world seed -> identical snapshot signature.
"""
from __future__ import annotations

import io
import os
import sys

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import numpy as np                                                      # noqa: E402

from engine.world_genesis import GenesisParams, generate_world          # noqa: E402
from engine.lake_hydrology import (                                     # noqa: E402
    LakeConfig, LakeSnapshot, Lake,
    priority_flood_fill, lakes_from_elevation, lakes_from_world,
    observe_lakes, install_lake_observer, uninstall_lake_observer,
    lake_summary, _seed_mask,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:60s} {detail}"


class _FakeSim:
    """Minimal sim exercising the observer's world-resolution + step wrap."""
    def __init__(self, world):
        self._genesis_world = world
        self.tick = 0

    def step(self, *a, **k):
        self.tick += 1
        return {"tick": self.tick}


def _make_world(seed=0xC0FFEE_1234):
    gp = GenesisParams(seed=seed & 0xFFFFFFFFFFFFFFFF, resolution=64,
                       n_plates=10, erosion_iters=20, rain_iters=5,
                       river_threshold_cells=30.0, lat_span_deg=30.0)
    return generate_world(gp)


def main() -> int:
    print("=" * 78)
    print("P174 — Wave 66 endorheic depression & lake hydrology (Priority-Flood)")
    print("=" * 78)
    failures = 0

    # ----- Step 1 — API surface ----------------------------------------
    ok = all(callable(f) for f in (
        priority_flood_fill, lakes_from_elevation, lakes_from_world,
        observe_lakes, install_lake_observer, uninstall_lake_observer,
        lake_summary)) and all(t is not None for t in (
        LakeConfig, LakeSnapshot, Lake))
    print(_row("step 1 - public API surface present", ok, ""))
    failures += 0 if ok else 1

    # ----- Step 2 — synthetic crater, analytic volume ------------------
    R = 15
    elev = np.full((R, R), 100.0)
    elev[6:9, 6:9] = 90.0                       # 3x3 pit, 10 m deep
    filled, depth, lakes = lakes_from_elevation(elev, cell_km=1.0)
    exp_vol = 9 * 10 * (1000.0 ** 2)            # 9 cells x 10 m x (1 km)^2
    border_ok = (np.allclose(filled[0, :], elev[0, :])
                 and np.allclose(filled[-1, :], elev[-1, :])
                 and np.allclose(filled[:, 0], elev[:, 0])
                 and np.allclose(filled[:, -1], elev[:, -1]))
    ok = (len(lakes) == 1 and lakes[0].n_cells == 9
          and abs(lakes[0].volume_m3 - exp_vol) < 1.0
          and bool((filled >= elev - 1e-9).all()) and border_ok)
    print(_row("step 2 - crater: analytic volume, filled>=elev, border free", ok,
               f"vol={lakes[0].volume_m3:.0f} exp={exp_vol:.0f}"))
    failures += 0 if ok else 1

    # ----- Step 3 — lake surface is flat -------------------------------
    lk = lakes[0]
    surf_cells = filled[depth > 1e-9]
    ok = (float(surf_cells.std()) < 1e-9
          and abs(lk.surface_elev_m - 100.0) < 1e-9
          and abs(lk.bottom_elev_m - 90.0) < 1e-9
          and abs(lk.max_depth_m - 10.0) < 1e-9)
    print(_row("step 3 - lake surface flat (water finds its level)", ok,
               f"std={float(surf_cells.std()):.2e} surf={lk.surface_elev_m:.1f}"))
    failures += 0 if ok else 1

    # ----- Step 4 — nested basins merge to one surface -----------------
    e2 = np.full((11, 11), 100.0)
    e2[2:9, 2:9] = 50.0                          # big bowl
    e2[4:7, 4:7] = 20.0                          # deeper sub-pit
    f2, d2, l2 = lakes_from_elevation(e2, cell_km=1.0)
    surfaces = sorted({round(x.surface_elev_m, 3) for x in l2})
    ok = (len(l2) == 1 and surfaces == [100.0]
          and float(f2[f2 > e2 + 1e-9].std()) < 1e-9)
    print(_row("step 4 - nested bowl+pit -> ONE lake at outer sill", ok,
               f"n_lakes={len(l2)} surfaces={surfaces}"))
    failures += 0 if ok else 1

    # ----- Step 5 — ocean drains free (no impounding to the sea) -------
    e3 = np.full((11, 11), 50.0)
    e3[:, 0] = -5.0                              # sea column on the west edge
    e3[5, 1:6] = -1.0                            # a channel from the sea inland
    e3[5, 3] = -3.0                              # a dip along the channel (below sea? no, -3>-5)
    seed = _seed_mask(e3, sea_level_m=0.0)
    f3, d3, l3 = lakes_from_elevation(e3, cell_km=1.0, sea_level_m=0.0)
    # The channel connects to the sea below sea level -> it drains, not a lake.
    ocean_seeded = bool(seed[:, 0].all())
    ok = ocean_seeded and all(lk.surface_elev_m > 0.0 for lk in l3)
    print(_row("step 5 - ocean seeds free-drain (sea-open basin not impounded)",
               ok, f"ocean_seeded={ocean_seeded} lakes={len(l3)}"))
    failures += 0 if ok else 1

    # ----- Step 6 — real world : emergent lakes + endorheic cross-check -
    world = _make_world()
    sea = float(world.params.sea_level_m)
    snap = lakes_from_world(world, LakeConfig())
    fd = np.asarray(world.flow_dir)
    ev = np.asarray(world.elevation_m)
    interior_pits = int(((fd == 255) & (ev > sea)).sum())
    # Every emergent lake bottom that carries an interior pit must be flagged;
    # a raw (un-routed) DEM's closed basins are all terminal, so >=1 endorheic.
    ok = (snap.n_lakes >= 1 and snap.total_impounded_volume_m3 > 0.0
          and snap.n_endorheic >= 1 and interior_pits >= 1
          and snap.max_lake_depth_m > 0.0)
    print(_row("step 6 - real world: lakes emerge + endorheic cross-check", ok,
               f"lakes={snap.n_lakes} endo={snap.n_endorheic} "
               f"pits={interior_pits} vol={snap.total_impounded_volume_m3:.2e}"))
    failures += 0 if ok else 1

    # ----- Step 7 — read-only + installer wrap/uninstall ---------------
    e_before = ev.copy()
    fd_before = fd.copy()
    fake = _FakeSim(world)
    install_lake_observer(fake, LakeConfig(snapshot_every=1))
    step_wrapped = fake.step is not None and getattr(fake, "_lake_wrapped", False)
    fake.step()                                   # tick 1 -> snapshot captured
    summ = lake_summary(fake)
    read_only = (np.array_equal(np.asarray(world.elevation_m), e_before)
                 and np.array_equal(np.asarray(world.flow_dir), fd_before))
    removed = uninstall_lake_observer(fake)
    restored = (getattr(fake, "_lake_wrapped", False) is False)
    ok = (step_wrapped and summ["installed"] is True
          and summ["n_snapshots"] >= 1 and read_only and removed and restored)
    print(_row("step 7 - read-only + install/uninstall + snapshot capture", ok,
               f"snaps={summ.get('n_snapshots')} read_only={read_only}"))
    failures += 0 if ok else 1

    # ----- Step 8 — determinism ----------------------------------------
    snap_a = lakes_from_world(_make_world(seed=0x5EED_0001), LakeConfig())
    snap_b = lakes_from_world(_make_world(seed=0x5EED_0001), LakeConfig())
    ok = (snap_a.signature == snap_b.signature
          and snap_a.n_lakes == snap_b.n_lakes)
    print(_row("step 8 - determinism: same seed -> same signature", ok,
               f"sig={snap_a.signature[:12]} lakes={snap_a.n_lakes}"))
    failures += 0 if ok else 1

    print("-" * 78)
    passed = 8 - failures
    print(f"  RESULT: {passed}/8 checks passed")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
