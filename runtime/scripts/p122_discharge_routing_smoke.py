"""P122 — Wave 53 LTI river-discharge routing observer smoke.

 1. Public API exposed.
 2. Unit-runoff routing on a chain : discharge == contributing-area count.
 3. Mass conservation on a random chain : Σ discharge[sinks] == Σ runoff.
 4. Confluence : downstream discharge == Σ tributaries + local runoff.
 5. observe_discharge returns a sane snapshot on a real Genesis world.
 6. Mass balance closes on the real world (residual < 1e-6).
 7. Snapshot is read-only : world arrays + sim tick unchanged.
 8. Cross-sim determinism : same world seed ⇒ same signature.
 9. install / uninstall wrap restore : sim.step round-trip + idempotent.
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
from engine.discharge_observer import (                                 # noqa: E402
    DischargeConfig, DischargeSnapshot, DischargeHistory, DischargeState,
    BasinDischarge,
    route_runoff, runoff_field_m3s,
    observe_discharge, install_discharge_observer,
    uninstall_discharge_observer, discharge_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _booted_sim(name, seed=0xCAFE_0122, resolution=64,
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


def main() -> int:
    print("=" * 78)
    print("P122 — Wave 53 LTI river-discharge routing observer")
    print("=" * 78)
    results = []

    # 1. API surface --------------------------------------------------------
    try:
        api_ok = all(callable(f) for f in (
            route_runoff, runoff_field_m3s, observe_discharge,
            install_discharge_observer, uninstall_discharge_observer,
            discharge_summary))
        results.append(_row("step 1 - public API exposed", api_ok))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 1 - public API exposed", False))

    # 2. Unit runoff == contributing area on a chain -----------------------
    try:
        R = 9
        fd = np.full((R, R), 255, dtype=np.uint8)
        y0, length = 4, 7
        for x in range(length - 1):
            fd[y0, x] = 0  # east
        fd[y0, length - 1] = 255
        q = route_runoff(fd, np.ones((R, R), dtype=np.float64))
        chain = [q[y0, i] for i in range(length)]
        ok2 = chain == [float(i + 1) for i in range(length)]
        results.append(_row("step 2 - unit runoff == contributing area",
                            ok2, f"chain={chain}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 2 - unit runoff == contributing area",
                            False))

    # 3. Mass conservation on a random chain -------------------------------
    try:
        rng = np.random.default_rng(7)
        runoff = rng.uniform(0.0, 5.0, size=(R, R))
        q = route_runoff(fd, runoff)
        out = float(q[fd == 255].sum())
        tot = float(runoff.sum())
        ok3 = abs(out - tot) < 1e-9
        results.append(_row("step 3 - mass conservation (chain)", ok3,
                            f"Σout={out:.4f} Σrunoff={tot:.4f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 3 - mass conservation (chain)", False))

    # 4. Confluence ---------------------------------------------------------
    try:
        Rc = 8
        fdc = np.full((Rc, Rc), 255, dtype=np.uint8)
        fdc[2, 1] = 1   # SE
        fdc[4, 1] = 7   # NE
        fdc[3, 2] = 0   # east
        fdc[3, 3] = 255
        rc = np.zeros((Rc, Rc), dtype=np.float64)
        rc[2, 1], rc[4, 1], rc[3, 2] = 2.0, 3.0, 1.0
        qc = route_runoff(fdc, rc)
        ok4 = (abs(qc[3, 2] - 6.0) < 1e-9) and (abs(qc[3, 3] - 6.0) < 1e-9)
        results.append(_row("step 4 - confluence sums tributaries", ok4,
                            f"Q_conf={qc[3, 2]:.1f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 4 - confluence sums tributaries", False))

    # 5-8 real world --------------------------------------------------------
    snap = None
    try:
        sim = _booted_sim("p122_real")
        snap = observe_discharge(sim)
        ok5 = isinstance(snap, DischargeSnapshot) and snap.total_runoff_m3s >= 0
        results.append(_row("step 5 - snapshot on real world", ok5))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 5 - snapshot on real world", False))

    try:
        ok6 = snap is not None and snap.mass_balance_residual < 1e-6
        results.append(_row("step 6 - mass balance closes (real)", ok6,
                            f"resid={snap.mass_balance_residual:.2e}"
                            if snap else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 6 - mass balance closes (real)", False))

    try:
        sim2 = _booted_sim("p122_ro")
        world = sim2._genesis_bootstrap_state.world
        b_fd = world.flow_dir.copy()
        b_p = world.precip_mm.copy()
        b_tick = int(sim2.tick)
        observe_discharge(sim2)
        ok7 = (np.array_equal(world.flow_dir, b_fd)
               and np.array_equal(world.precip_mm, b_p)
               and int(sim2.tick) == b_tick)
        results.append(_row("step 7 - observe is read-only", ok7))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 7 - observe is read-only", False))

    try:
        a = observe_discharge(_booted_sim("p122_d1", seed=0xBEEF_0122))
        b = observe_discharge(_booted_sim("p122_d2", seed=0xBEEF_0122))
        ok8 = a is not None and b is not None and a.signature == b.signature
        results.append(_row("step 8 - cross-sim determinism", ok8,
                            f"sig={a.signature[:12]}…" if a else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 8 - cross-sim determinism", False))

    # 9. install / uninstall ------------------------------------------------
    try:
        sim3 = _booted_sim("p122_io")
        orig = sim3.step
        st = install_discharge_observer(sim3, DischargeConfig(snapshot_every=2))
        again = install_discharge_observer(sim3)
        ok9 = (sim3.step is not orig and again is st
               and uninstall_discharge_observer(sim3) is True
               and sim3.step is orig
               and uninstall_discharge_observer(sim3) is False)
        results.append(_row("step 9 - install/uninstall round-trip", ok9))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 9 - install/uninstall round-trip", False))

    # 10. cadence -----------------------------------------------------------
    try:
        sim4 = _booted_sim("p122_cad")
        install_discharge_observer(sim4, DischargeConfig(snapshot_every=2))
        for _ in range(4):
            sim4.step()
        summ = discharge_summary(sim4)
        ok10 = (summ["installed"] and summ["n_snapshots"] >= 1
                and summ["mass_balance_residual"] < 1e-6)
        results.append(_row("step 10 - installed observer captures cadence",
                            ok10, f"n_snaps={summ['n_snapshots']}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 10 - installed observer captures cadence",
                            False))

    for line in results:
        print(line)

    if snap is not None:
        print("\nSnapshot dump (sim p122_real) :")
        print(f"  cell_km                : {snap.cell_km:.3f}")
        print(f"  total_runoff_m3s       : {snap.total_runoff_m3s:.3f}")
        print(f"  total_outflow_m3s      : {snap.total_outflow_m3s:.3f}")
        print(f"  mass_balance_residual  : {snap.mass_balance_residual:.2e}")
        print(f"  mean_runoff_mm_yr      : {snap.mean_runoff_mm_yr:.2f}")
        print(f"  max_discharge_m3s      : {snap.max_discharge_m3s:.3f}"
              f"  @ {snap.max_discharge_yx}")
        print(f"  mean_river_discharge   : {snap.mean_river_discharge_m3s:.3f}")
        print(f"  basins total/considered: {snap.n_basins_total}"
              f" / {snap.n_basins_considered}")
        for b in snap.basins_top:
            print(f"  basin#{b.basin_id:<5d} area={b.area_km2:.1f}km²"
                  f" Q_out={b.outlet_discharge_m3s:.2f}m³/s"
                  f" q={b.specific_discharge_mm_yr:.1f}mm/yr")
        print(f"  signature              : {snap.signature}")

    passed = sum("[OK" in r for r in results)
    total = len(results)
    print("=" * 78)
    print(f"RESULT: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
