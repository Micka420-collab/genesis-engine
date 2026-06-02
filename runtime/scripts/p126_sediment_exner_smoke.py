"""P126 — Wave 57 Exner mobile-bed / sediment-transport observer smoke.

 1. Public API exposed.
 2. Headwater identity : a single chain with constant capacity erodes only at
    the headwater, then passes through at capacity.
 3. Decreasing capacity downstream : every step deposits the surplus.
 4. Exact mass closure on a random chain : Σ erosion == Σ deposition + export.
 5. Confluence : downstream export == capacity (both tributaries deposit/erode
    so the closure still holds).
 6. observe_sediment returns a sane snapshot on a real Genesis world.
 7. Mass balance closes on the real world (residual < 1e-6).
 8. Snapshot is read-only : world arrays + sim tick unchanged.
 9. Cross-sim determinism : same world seed ⇒ same signature.
10. install / uninstall round-trip + idempotent + captures cadence.
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
from engine.sediment_observer import (                                  # noqa: E402
    SedimentConfig, SedimentSnapshot,
    downstream_slope, transport_capacity, route_sediment, bed_change_rate,
    observe_sediment, install_sediment_observer,
    uninstall_sediment_observer, sediment_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _booted_sim(name, seed=0xCAFE_0126, resolution=64,
                river_threshold_cells=8.0):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=20,
        bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
        drive_accel=1500.0, cultures=1,
    )
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8,
                       river_threshold_cells=river_threshold_cells)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


def _chain(length):
    R = max(length + 2, 6)
    fd = np.full((R, R), 255, dtype=np.uint8)
    y0 = R // 2
    for x in range(length - 1):
        fd[y0, x] = 0  # east
    fd[y0, length - 1] = 255
    return fd, y0, length


def main() -> int:
    print("=" * 78)
    print("P126 — Wave 57 Exner mobile-bed / sediment-transport observer")
    print("=" * 78)
    results = []

    # 1. API surface --------------------------------------------------------
    try:
        api_ok = all(callable(f) for f in (
            downstream_slope, transport_capacity, route_sediment,
            bed_change_rate, observe_sediment, install_sediment_observer,
            uninstall_sediment_observer, sediment_summary))
        results.append(_row("step 1 - public API exposed", api_ok))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 1 - public API exposed", False))

    # 2. Headwater identity (constant capacity) ----------------------------
    try:
        fd, y0, length = _chain(7)
        cap = np.zeros_like(fd, dtype=np.float64)
        for i in range(length):
            cap[y0, i] = 5.0
        q_out, ero, dep = route_sediment(fd, cap)
        head_only = (abs(ero[y0, 0] - 5.0) < 1e-12
                     and all(abs(ero[y0, i]) < 1e-12 for i in range(1, length))
                     and all(abs(dep[y0, i]) < 1e-12 for i in range(length)))
        passthrough = all(abs(q_out[y0, i] - 5.0) < 1e-12
                          for i in range(length))
        ok2 = head_only and passthrough
        results.append(_row("step 2 - headwater erodes, rest pass at cap",
                            ok2, f"E_head={ero[y0, 0]:.2f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 2 - headwater erodes, rest pass at cap",
                            False))

    # 3. Decreasing capacity ⇒ deposition every step -----------------------
    try:
        fd, y0, length = _chain(5)
        caps = [5.0, 4.0, 3.0, 2.0, 1.0]
        cap = np.zeros_like(fd, dtype=np.float64)
        for i in range(length):
            cap[y0, i] = caps[i]
        q_out, ero, dep = route_sediment(fd, cap)
        deposits = [dep[y0, i] for i in range(1, length)]
        ok3 = (abs(ero[y0, 0] - 5.0) < 1e-12
               and all(abs(d - 1.0) < 1e-12 for d in deposits)
               and abs(q_out[y0, length - 1] - 1.0) < 1e-12)
        results.append(_row("step 3 - decreasing cap deposits surplus", ok3,
                            f"deposits={[round(d, 1) for d in deposits]}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 3 - decreasing cap deposits surplus", False))

    # 4. Exact mass closure on random chain --------------------------------
    try:
        fd, y0, length = _chain(8)
        rng = np.random.default_rng(126)
        cap = rng.uniform(0.0, 5.0, size=fd.shape)
        q_out, ero, dep = route_sediment(fd, cap)
        is_sink = (fd == 255)
        export = float(q_out[is_sink].sum())
        lhs = float(ero.sum())
        rhs = float(dep.sum()) + export
        ok4 = abs(lhs - rhs) < 1e-9
        results.append(_row("step 4 - mass closure ΣE==ΣD+export", ok4,
                            f"ΣE={lhs:.4f} ΣD+exp={rhs:.4f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 4 - mass closure ΣE==ΣD+export", False))

    # 5. Confluence closure -------------------------------------------------
    try:
        Rc = 8
        fdc = np.full((Rc, Rc), 255, dtype=np.uint8)
        fdc[2, 1] = 1   # SE
        fdc[4, 1] = 7   # NE
        fdc[3, 2] = 0   # east
        fdc[3, 3] = 255
        capc = np.zeros((Rc, Rc), dtype=np.float64)
        capc[2, 1], capc[4, 1], capc[3, 2], capc[3, 3] = 2.0, 3.0, 4.0, 4.0
        qo, ec, dc = route_sediment(fdc, capc)
        # tributaries erode to their cap (2,3); confluence inflow=5, cap=4 ⇒
        # deposits 1, exports 4; sink keeps 4.
        ok5 = (abs(qo[3, 2] - 4.0) < 1e-12 and abs(dc[3, 2] - 1.0) < 1e-12
               and abs(qo[3, 3] - 4.0) < 1e-12)
        export = float(qo[fdc == 255].sum())
        ok5 = ok5 and abs(float(ec.sum()) - (float(dc.sum()) + export)) < 1e-9
        results.append(_row("step 5 - confluence + closure", ok5,
                            f"Q_conf={qo[3, 2]:.1f} dep={dc[3, 2]:.1f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 5 - confluence + closure", False))

    # 6-9 real world --------------------------------------------------------
    snap = None
    try:
        sim = _booted_sim("p126_real")
        snap = observe_sediment(sim)
        ok6 = (isinstance(snap, SedimentSnapshot)
               and snap.total_erosion_m3s >= 0.0
               and snap.n_basins_considered <= snap.n_basins_total)
        results.append(_row("step 6 - snapshot on real world", ok6))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 6 - snapshot on real world", False))

    try:
        ok7 = snap is not None and snap.mass_balance_residual < 1e-6
        results.append(_row("step 7 - mass balance closes (real)", ok7,
                            f"resid={snap.mass_balance_residual:.2e}"
                            if snap else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 7 - mass balance closes (real)", False))

    try:
        sim2 = _booted_sim("p126_ro")
        world = sim2._genesis_bootstrap_state.world
        b_fd = world.flow_dir.copy()
        b_el = world.elevation_m.copy()
        b_tick = int(sim2.tick)
        observe_sediment(sim2)
        ok8 = (np.array_equal(world.flow_dir, b_fd)
               and np.array_equal(world.elevation_m, b_el)
               and int(sim2.tick) == b_tick)
        results.append(_row("step 8 - observe is read-only", ok8))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 8 - observe is read-only", False))

    try:
        a = observe_sediment(_booted_sim("p126_d1", seed=0xBEEF_0126))
        b = observe_sediment(_booted_sim("p126_d2", seed=0xBEEF_0126))
        ok9 = a is not None and b is not None and a.signature == b.signature
        results.append(_row("step 9 - cross-sim determinism", ok9,
                            f"sig={a.signature[:12]}…" if a else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 9 - cross-sim determinism", False))

    # 10. install / uninstall + cadence ------------------------------------
    try:
        sim3 = _booted_sim("p126_io")
        orig = sim3.step
        st = install_sediment_observer(sim3, SedimentConfig(snapshot_every=2))
        again = install_sediment_observer(sim3)
        round_trip = (sim3.step is not orig and again is st
                      and uninstall_sediment_observer(sim3) is True
                      and sim3.step is orig
                      and uninstall_sediment_observer(sim3) is False)
        sim4 = _booted_sim("p126_cad")
        install_sediment_observer(sim4, SedimentConfig(snapshot_every=2))
        for _ in range(4):
            sim4.step()
        summ = sediment_summary(sim4)
        ok10 = (round_trip and summ["installed"] and summ["n_snapshots"] >= 1
                and summ["mass_balance_residual"] < 1e-6)
        results.append(_row("step 10 - install/uninstall + cadence", ok10,
                            f"n_snaps={summ['n_snapshots']}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 10 - install/uninstall + cadence", False))

    for line in results:
        print(line)

    if snap is not None:
        print("\nSnapshot dump (sim p126_real) :")
        print(f"  cell_km                : {snap.cell_km:.3f}")
        print(f"  total_erosion_m3s      : {snap.total_erosion_m3s:.4f}")
        print(f"  total_deposition_m3s   : {snap.total_deposition_m3s:.4f}")
        print(f"  total_export_m3s       : {snap.total_export_m3s:.4f}")
        print(f"  mass_balance_residual  : {snap.mass_balance_residual:.2e}")
        print(f"  mean_denudation_mm_yr  : {snap.mean_denudation_mm_yr:.4f}")
        print(f"  max_incision_mm_yr     : {snap.max_incision_mm_yr:.4f}"
              f"  @ {snap.max_incision_yx}")
        print(f"  max_aggradation_mm_yr  : {snap.max_aggradation_mm_yr:.4f}")
        print(f"  basins total/considered: {snap.n_basins_total}"
              f" / {snap.n_basins_considered}")
        for b in snap.basins_top:
            print(f"  basin#{b.basin_id:<5d} area={b.area_km2:.1f}km²"
                  f" yield={b.sediment_export_m3s:.3f}m³/s"
                  f" denud={b.denudation_mm_yr:.3f}mm/yr")
        print(f"  signature              : {snap.signature}")

    passed = sum("[OK" in r for r in results)
    total = len(results)
    print("=" * 78)
    print(f"RESULT: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
