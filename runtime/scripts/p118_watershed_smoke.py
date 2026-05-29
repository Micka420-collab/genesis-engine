"""P118 — Wave 49 watershed / Strahler observer smoke.

 1. Public API exposed.
 2. Strahler order on a hand-built chain : monotonic, single-stream order = 1.
 3. Strahler order on a Y-confluence : two order-1 → one order-2.
 4. observe_watersheds returns a sane snapshot on a real Genesis world.
 5. Snapshot is read-only : world arrays + sim tick unchanged.
 6. Cross-sim determinism : same world seed ⇒ same signature.
 7. Horton ratios : Rb ≥ 0, Rl ≥ 0, ratios finite on a real network.
 8. Drainage density positive when rivers exist.
 9. install / uninstall wrap restore : sim.step round-trip.
10. Installed observer captures snapshots at the right cadence.
"""
from __future__ import annotations

import io
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import numpy as np                                                      # noqa: E402

from engine.sim import Simulation, SimConfig                            # noqa: E402
from engine.world_genesis import GenesisParams                          # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim              # noqa: E402
from engine.watershed_observer import (                                 # noqa: E402
    WatershedConfig, WatershedSnapshot, WatershedHistory, WatershedState,
    BasinStats,
    compute_strahler_order, compute_horton_ratios,
    observe_watersheds, install_watershed_observer,
    uninstall_watershed_observer, watershed_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xCAFE_0118):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=20,
        bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def _booted_sim(name, seed=0xCAFE_0118, resolution=64,
                river_threshold_cells=8.0):
    """Build a Genesis-bootstrapped sim with enough rivers to exercise
    the Strahler / Horton paths (default threshold is 60 which yields
    near-zero river cells at smoke resolutions)."""
    sim = _build_sim(name, seed=seed)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8,
                       river_threshold_cells=river_threshold_cells)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


def _chain_inputs(length: int = 8):
    """Build a horizontal river chain flowing east (D8 code 0)."""
    R = max(length + 2, 6)
    flow_dir = np.full((R, R), 255, dtype=np.uint8)
    river_mask = np.zeros((R, R), dtype=bool)
    y0 = R // 2
    for x in range(length - 1):
        flow_dir[y0, x] = 0  # east
        river_mask[y0, x] = True
    # Last cell is the outlet — still a river cell, no downstream river.
    river_mask[y0, length - 1] = True
    flow_dir[y0, length - 1] = 255  # sink
    return flow_dir, river_mask, R


def _y_confluence_inputs():
    """Two NW and SW tributaries (length 3) meeting at one east outlet."""
    R = 10
    flow_dir = np.full((R, R), 255, dtype=np.uint8)
    river_mask = np.zeros((R, R), dtype=bool)

    # D8 indices recap: 0=E,1=SE,2=S,3=SW,4=W,5=NW,6=N,7=NE.
    # Top tributary: (1,1) -> (2,2) -> (3,3)  flowing SE (1).
    # Bottom tributary: (5,1) -> (4,2) -> (3,3)  flowing NE (7).
    # Combined stem: (3,3) -> (3,4) -> (3,5)    flowing E (0).
    top = [(1, 1), (2, 2)]
    bot = [(5, 1), (4, 2)]
    for (y, x) in top:
        flow_dir[y, x] = 1  # SE
        river_mask[y, x] = True
    for (y, x) in bot:
        flow_dir[y, x] = 7  # NE
        river_mask[y, x] = True
    # Junction + stem.
    river_mask[3, 3] = True; flow_dir[3, 3] = 0  # E
    river_mask[3, 4] = True; flow_dir[3, 4] = 0  # E
    river_mask[3, 5] = True; flow_dir[3, 5] = 255  # outlet
    return flow_dir, river_mask


def main() -> int:
    print("=" * 78)
    print("P118 — Wave 49 watershed observer smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API surface.
    ok = all(name in globals() for name in (
        "WatershedConfig", "WatershedSnapshot", "WatershedHistory",
        "WatershedState", "BasinStats",
        "compute_strahler_order", "compute_horton_ratios",
        "observe_watersheds", "install_watershed_observer",
        "uninstall_watershed_observer", "watershed_summary",
    ))
    print(_row("step 1 - public API exposed", ok))
    if not ok:
        failures += 1

    # Step 2 — straight chain : every cell has order 1 (no confluence).
    fd, rm, _R = _chain_inputs(length=8)
    order = compute_strahler_order(fd, rm)
    river_orders = order[rm]
    ok = (river_orders.size == 8
          and int(river_orders.min()) == 1
          and int(river_orders.max()) == 1)
    print(_row("step 2 - straight river chain → order 1 everywhere",
               ok, f"min={int(river_orders.min())} max={int(river_orders.max())} "
                   f"n={int(river_orders.size)}"))
    if not ok:
        failures += 1

    # Step 3 — Y confluence : downstream stem promoted to order 2.
    fd2, rm2 = _y_confluence_inputs()
    order2 = compute_strahler_order(fd2, rm2)
    headwater_max = int(max(order2[1, 1], order2[5, 1]))
    junction = int(order2[3, 3])
    outlet = int(order2[3, 5])
    ok = (headwater_max == 1 and junction == 2 and outlet == 2)
    print(_row("step 3 - Y-confluence : two order-1 → order-2 stem",
               ok, f"head={headwater_max} junction={junction} outlet={outlet}"))
    if not ok:
        failures += 1

    # Step 4 — observe on real Genesis world.
    sim = _booted_sim("p118_real", seed=0xCAFE_01184)
    snap = observe_watersheds(sim)
    ok = (isinstance(snap, WatershedSnapshot)
          and snap.n_basins_total >= 1
          and snap.map_area_km2 > 0.0
          and snap.cell_km > 0.0
          and len(snap.signature) == 64)
    print(_row("step 4 - real-world snapshot well-formed", ok,
               f"basins={snap.n_basins_total} rivers={snap.total_river_cells} "
               f"sig={snap.signature[:10]}…"))
    if not ok:
        failures += 1

    # Step 5 — observe is read-only.
    sim5 = _booted_sim("p118_ro", seed=0xCAFE_01185)
    world5 = sim5._genesis_bootstrap_state.world
    fd_before = np.array(world5.flow_dir, copy=True)
    rm_before = np.array(world5.river_mask, copy=True)
    wid_before = np.array(world5.watershed_id, copy=True)
    elev_before = np.array(world5.elevation_m, copy=True)
    tick_before = int(sim5.tick)
    _ = observe_watersheds(sim5)
    ok = (int(sim5.tick) == tick_before
          and np.array_equal(world5.flow_dir, fd_before)
          and np.array_equal(world5.river_mask, rm_before)
          and np.array_equal(world5.watershed_id, wid_before)
          and np.array_equal(world5.elevation_m, elev_before))
    print(_row("step 5 - observe is read-only (world + tick frozen)", ok,
               f"tick={tick_before}->{int(sim5.tick)}"))
    if not ok:
        failures += 1

    # Step 6 — cross-sim determinism.
    seed_d = 0xCAFE_01186
    sim_a = _booted_sim("p118_det_a", seed=seed_d)
    sim_b = _booted_sim("p118_det_b", seed=seed_d)
    sig_a = observe_watersheds(sim_a).signature
    sig_b = observe_watersheds(sim_b).signature
    ok = (sig_a == sig_b)
    print(_row("step 6 - cross-sim determinism (same seed → same sig)",
               ok, f"match={sig_a == sig_b}"))
    if not ok:
        failures += 1

    # Step 7 — Horton ratios sanity on a real network.
    ok = (snap.bifurcation_ratio >= 0.0
          and snap.length_ratio >= 0.0
          and not np.isnan(snap.bifurcation_ratio)
          and not np.isnan(snap.length_ratio))
    print(_row("step 7 - Horton Rb/Rl ≥ 0 and finite", ok,
               f"Rb={snap.bifurcation_ratio:.3f} Rl={snap.length_ratio:.3f}"))
    if not ok:
        failures += 1

    # Step 8 — drainage density coherent with river presence.
    has_rivers = snap.total_river_cells > 0
    ok = ((not has_rivers and snap.global_drainage_density == 0.0)
          or (has_rivers and snap.global_drainage_density > 0.0))
    print(_row("step 8 - global drainage density coherent", ok,
               f"rivers={snap.total_river_cells} "
               f"Dd={snap.global_drainage_density:.4f}"))
    if not ok:
        failures += 1

    # Step 9 — install / uninstall round-trip.
    sim9 = _booted_sim("p118_install", seed=0xCAFE_01189)
    step_before = sim9.step
    state = install_watershed_observer(
        sim9, WatershedConfig(snapshot_every=2))
    wrapped = (sim9.step is not step_before
               and getattr(sim9, "_watershed_wrapped", False) is True)
    # Re-install should NOT wrap twice.
    state2 = install_watershed_observer(
        sim9, WatershedConfig(snapshot_every=3))
    ok_idem = (state2 is state)
    restored = uninstall_watershed_observer(sim9)
    ok_after = (sim9.step is step_before and restored is True
                and watershed_summary(sim9).get("installed") is False)
    ok = wrapped and ok_idem and ok_after
    print(_row("step 9 - install wraps step (idempotent) / uninstall restores",
               ok, f"wrap={wrapped} idem={ok_idem} restored={restored}"))
    if not ok:
        failures += 1

    # Step 10 — installed observer captures at cadence.
    sim10 = _booted_sim("p118_cadence", seed=0xCAFE_011810)
    install_watershed_observer(sim10, WatershedConfig(snapshot_every=2))
    for _ in range(7):
        sim10.step()
    summary = watershed_summary(sim10)
    n_snaps = int(summary.get("n_snapshots") or 0)
    # Snapshots captured when tick % 2 == 0 inside the wrapped step :
    # we expect at least 2 over 7 steps.
    ok = (summary.get("installed") is True
          and n_snaps >= 2
          and summary.get("last_signature") is not None)
    print(_row("step 10 - installed observer captures at cadence", ok,
               f"n_snaps={n_snaps} last_tick={summary.get('last_tick')}"))
    if not ok:
        failures += 1

    # Diagnostic dump.
    print()
    print("Snapshot dump (sim p118_real) :")
    print(f"  basins_total           : {snap.n_basins_total}")
    print(f"  basins_considered      : {snap.n_basins_considered}")
    print(f"  river_cells            : {snap.total_river_cells}")
    print(f"  river_length_km        : {snap.total_river_length_km:.2f}")
    print(f"  map_area_km2           : {snap.map_area_km2:.1f}")
    print(f"  global_drainage_dens   : {snap.global_drainage_density:.4f}")
    print(f"  bifurcation_ratio Rb   : {snap.bifurcation_ratio:.3f}")
    print(f"  length_ratio       Rl  : {snap.length_ratio:.3f}")
    print(f"  stream_order_counts    : {snap.stream_order_counts}")
    for b in snap.basins_top:
        print(f"  basin#{b.basin_id:>3} area={b.area_km2:>8.1f} "
              f"river={b.river_length_km:>7.1f}km "
              f"Dd={b.drainage_density:.4f} maxStrahler={b.max_strahler} "
              f"hypso={b.hypsometric_integral:.3f}")
    print(f"  signature              : {snap.signature}")

    total = 10
    passed = total - failures
    print("=" * 78)
    if failures == 0:
        print(f"RESULT: {total}/{total} PASS")
        return 0
    print(f"RESULT: {passed}/{total} PASS, {failures} FAIL")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
