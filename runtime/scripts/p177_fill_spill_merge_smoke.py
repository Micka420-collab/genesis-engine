"""P177 — Wave 67 Fill–Spill–Merge finite-volume lake filling smoke.

Wave 66 (Priority-Flood) gave the **containers** — where a closed depression
*could* hold a lake and how big at most. But Priority-Flood fills every cup to
the brim by construction: a desert playa and a full alpine tarn look identical
to it. Wave 67 pours the **actual routed runoff** (Wave 64 discharge, the
mass-conserving LTI routing of a climate-driven runoff balance down the D8 graph)
into those cups and lets each fill only as far as its inflow allows — the
finite-volume Fill–Spill–Merge balance (Barnes, Callaghan & Wickert, ESurf 2021).
The emergent spectrum Priority-Flood could not see: full lakes that spill,
partial lakes, playas (starved terminal basins whose salt concentrates), and
dry basins.

Steps:
  1. Public API surface present.
  2. Crater half-filled : inflow = ½ capacity -> water = ½ capacity, level
     exactly halfway, ONE partial lake, the partial surface is FLAT, and the
     standing water is mass-conserved (Sum depth*area == water volume).
  3. Playa : a starved terminal basin (inflow << capacity) becomes a playa, its
     water level near the bottom and its salinity concentration ~ 1/fill.
  4. Spill : inflow > capacity -> water is CAPPED at capacity (finite volume
     never overfills), fill_fraction == 1, the basin spills the exact excess.
  5. Monotone spectrum : a larger fill window only ever raises the overall fill
     fraction and the standing water, bounded above by the total capacity.
  6. Real Genesis world : basins == Wave 66 containers, standing water <= its
     container everywhere, and a starved (1 yr) world yields playas/dry while a
     long window yields full, spilling lakes.
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
from engine.lake_hydrology import lakes_from_world, LakeConfig          # noqa: E402
from engine.fill_spill_merge import (                                   # noqa: E402
    FSMConfig, FSMSnapshot, FilledLake,
    fill_depressions, fsm_from_world, observe_fsm,
    install_fsm_observer, uninstall_fsm_observer, fsm_summary,
)

_YEAR_S = 365.25 * 24.0 * 3600.0


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


def _crater(depth_m=10.0):
    """15x15 plateau at 100 m with a 3x3 pit; every cell an interior sink so
    a single sink cell carries the whole basin inflow (pure, analytic)."""
    R = 15
    elev = np.full((R, R), 100.0)
    elev[6:9, 6:9] = 100.0 - depth_m
    flow = np.full((R, R), 255, dtype=np.uint8)   # all sinks
    cell_area = (1.0 * 1000.0) ** 2
    capacity = 9.0 * depth_m * cell_area
    return elev, flow, cell_area, capacity


def _inflow_field(rate_cell, y=7, x=7, R=15):
    Q = np.zeros((R, R))
    Q[y, x] = rate_cell
    return Q


def main() -> int:
    print("=" * 78)
    print("P177 — Wave 67 Fill–Spill–Merge finite-volume lake filling")
    print("=" * 78)
    failures = 0

    # ----- Step 1 — API surface ----------------------------------------
    ok = all(callable(f) for f in (
        fill_depressions, fsm_from_world, observe_fsm,
        install_fsm_observer, uninstall_fsm_observer, fsm_summary)) and all(
        t is not None for t in (FSMConfig, FSMSnapshot, FilledLake))
    print(_row("step 1 - public API surface present", ok, ""))
    failures += 0 if ok else 1

    # ----- Step 2 — crater half-filled ---------------------------------
    elev, flow, A, cap = _crater(10.0)
    Q = _inflow_field(0.5 * cap / _YEAR_S)         # 1 yr delivers half capacity
    _f, _d, wd, lakes = fill_depressions(
        elev, Q, flow, cell_km=1.0, sea_level_m=0.0, window_s=_YEAR_S)
    lk = lakes[0]
    wet_surface = (elev + wd)[wd > 1e-9]
    mass_ok = abs(float(wd.sum()) * A - lk.water_volume_m3) < 1.0
    ok = (len(lakes) == 1
          and abs(lk.water_volume_m3 - 0.5 * cap) < 1.0
          and abs(lk.fill_fraction - 0.5) < 1e-6
          and abs(lk.water_level_m - 95.0) < 1e-6
          and abs(lk.water_max_depth_m - 5.0) < 1e-6
          and lk.state == "lake"
          and float(wet_surface.std()) < 1e-9
          and mass_ok)
    print(_row("step 2 - crater half fill: level 95m, flat, mass-conserved", ok,
               f"frac={lk.fill_fraction:.2f} level={lk.water_level_m:.1f} "
               f"state={lk.state}"))
    failures += 0 if ok else 1

    # ----- Step 3 — playa (starved terminal basin) ---------------------
    Qp = _inflow_field(0.05 * cap / _YEAR_S)
    _, _, _, lkp = fill_depressions(
        elev, Qp, flow, cell_km=1.0, sea_level_m=0.0, window_s=_YEAR_S)
    p = lkp[0]
    ok = (p.state == "playa" and p.is_terminal
          and abs(p.fill_fraction - 0.05) < 1e-6
          and abs(p.salinity_factor - 20.0) < 1e-6      # 1/0.05
          and p.water_level_m < 95.0)
    print(_row("step 3 - starved terminal basin -> playa, salt concentrates", ok,
               f"state={p.state} frac={p.fill_fraction:.2f} "
               f"sal={p.salinity_factor:.1f}"))
    failures += 0 if ok else 1

    # ----- Step 4 — spill (finite volume never overfills) --------------
    Qo = _inflow_field(3.0 * cap / _YEAR_S)
    _, _, _, lko = fill_depressions(
        elev, Qo, flow, cell_km=1.0, sea_level_m=0.0, window_s=_YEAR_S)
    o = lko[0]
    ok = (o.state == "full" and o.spills
          and abs(o.water_volume_m3 - cap) < 1.0        # capped at capacity
          and abs(o.fill_fraction - 1.0) < 1e-9
          and abs(o.overflow_m3 - 2.0 * cap) < 1.0      # exact excess
          and abs(o.water_level_m - o.sill_elev_m) < 1e-9)
    print(_row("step 4 - inflow>capacity -> capped + spills exact excess", ok,
               f"water={o.water_volume_m3:.0f} cap={cap:.0f} "
               f"overflow={o.overflow_m3:.0f}"))
    failures += 0 if ok else 1

    # ----- Step 5 — monotone fill spectrum -----------------------------
    world = _make_world()
    lk66 = lakes_from_world(world, LakeConfig())
    cap_total = lk66.total_impounded_volume_m3
    fracs, waters = [], []
    for yrs in (1, 30, 300, 3000):
        s = fsm_from_world(world, FSMConfig(fill_window_days=365.25 * yrs))
        fracs.append(s.overall_fill_fraction)
        waters.append(s.total_water_m3)
    mono = all(fracs[i] <= fracs[i + 1] + 1e-12 for i in range(len(fracs) - 1)) \
        and all(waters[i] <= waters[i + 1] + 1.0 for i in range(len(waters) - 1))
    bounded = all(w <= cap_total + 1.0 for w in waters) and fracs[-1] <= 1.0 + 1e-9
    ok = mono and bounded
    print(_row("step 5 - monotone spectrum, bounded by capacity", ok,
               f"fracs={[round(f,3) for f in fracs]}"))
    failures += 0 if ok else 1

    # ----- Step 6 — real world : starved vs long-run ------------------
    starved = fsm_from_world(world, FSMConfig(fill_window_days=365.25))
    longrun = fsm_from_world(world, FSMConfig(fill_window_days=365.25 * 3000))
    # basins are exactly the Wave 66 containers; standing water never exceeds it.
    water_bounded = all(lk.water_volume_m3 <= lk.capacity_m3 + 1.0
                        and lk.water_level_m <= lk.sill_elev_m + 1e-6
                        for lk in starved.lakes_top)
    ok = (starved.n_basins == lk66.n_lakes
          and (starved.n_playa + starved.n_dry) >= 1
          and longrun.n_full >= 1 and longrun.n_spilling >= 1
          and longrun.total_water_m3 >= starved.total_water_m3
          and water_bounded)
    print(_row("step 6 - real world: starved playas -> long-run full+spill", ok,
               f"basins={starved.n_basins} starved(playa+dry)="
               f"{starved.n_playa + starved.n_dry} long(full/spill)="
               f"{longrun.n_full}/{longrun.n_spilling}"))
    failures += 0 if ok else 1

    # ----- Step 7 — read-only + installer wrap/uninstall ---------------
    ev = np.asarray(world.elevation_m)
    fd = np.asarray(world.flow_dir)
    e_before, fd_before = ev.copy(), fd.copy()
    fake = _FakeSim(world)
    install_fsm_observer(fake, FSMConfig(snapshot_every=1))
    step_wrapped = fake.step is not None and getattr(fake, "_fsm_wrapped", False)
    fake.step()                                    # tick 1 -> snapshot captured
    summ = fsm_summary(fake)
    read_only = (np.array_equal(np.asarray(world.elevation_m), e_before)
                 and np.array_equal(np.asarray(world.flow_dir), fd_before))
    removed = uninstall_fsm_observer(fake)
    restored = (getattr(fake, "_fsm_wrapped", False) is False)
    ok = (step_wrapped and summ["installed"] is True
          and summ["n_snapshots"] >= 1 and read_only and removed and restored)
    print(_row("step 7 - read-only + install/uninstall + snapshot capture", ok,
               f"snaps={summ.get('n_snapshots')} read_only={read_only}"))
    failures += 0 if ok else 1

    # ----- Step 8 — determinism ----------------------------------------
    snap_a = fsm_from_world(_make_world(seed=0x5EED_0001), FSMConfig())
    snap_b = fsm_from_world(_make_world(seed=0x5EED_0001), FSMConfig())
    ok = (snap_a.signature == snap_b.signature
          and snap_a.n_basins == snap_b.n_basins)
    print(_row("step 8 - determinism: same seed -> same signature", ok,
               f"sig={snap_a.signature[:12]} basins={snap_a.n_basins}"))
    failures += 0 if ok else 1

    print("-" * 78)
    passed = 8 - failures
    print(f"  RESULT: {passed}/8 checks passed")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
