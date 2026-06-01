"""P124 — Wave 55 transient linear-reservoir hydrograph observer smoke.

 1. Public API exposed.
 2. Reservoir mass closure : s0 + ΣI·dt − out_cum == S (exact).
 3. Recession is geometric & monotone : Q[n] == Q0·a**n.
 4. Step response from empty converges to inflow (ties to Wave 53 Q*).
 5. Half-recession time ≈ k·ln2.
 6. Storm hydrograph shape : starts at 0, peaks at storm end, recedes.
 7. observe_hydrograph returns a sane snapshot on a real Genesis world.
 8. Snapshot is read-only : world arrays + sim tick unchanged.
 9. Cross-sim determinism : same world seed ⇒ same signature.
10. install / uninstall wrap restore + idempotent + cadence capture.
"""
from __future__ import annotations

import io
import math
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
from engine.hydrograph_observer import (                                # noqa: E402
    HydrographConfig, HydrographSnapshot,
    linear_reservoir_response, storm_hydrograph, half_recession_days,
    observe_hydrograph, install_hydrograph_observer,
    uninstall_hydrograph_observer, hydrograph_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _booted_sim(name, seed=0xCAFE_0124, resolution=64,
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
    print("P124 — Wave 55 transient linear-reservoir hydrograph observer")
    print("=" * 78)
    results = []

    # 1. API surface --------------------------------------------------------
    try:
        api_ok = all(callable(f) for f in (
            linear_reservoir_response, storm_hydrograph, half_recession_days,
            observe_hydrograph, install_hydrograph_observer,
            uninstall_hydrograph_observer, hydrograph_summary))
        results.append(_row("step 1 - public API exposed", api_ok))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 1 - public API exposed", False))

    # 2. Mass closure -------------------------------------------------------
    try:
        inflow = np.array([2.0, 2.0, 0.0, 0.0, 0.0, 0.0])
        k, dt = 3.0, 0.5
        t, Q, S, out_cum = linear_reservoir_response(inflow, k, dt, inflow.size)
        cum_in = np.concatenate(([0.0], np.cumsum(inflow * dt)))
        resid = float(np.max(np.abs((cum_in - out_cum) - S)))
        ok2 = resid < 1e-12
        results.append(_row("step 2 - reservoir mass closure (exact)", ok2,
                            f"max|resid|={resid:.2e}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 2 - reservoir mass closure (exact)", False))

    # 3. Geometric recession ------------------------------------------------
    try:
        k, dt, n, q0 = 4.0, 0.25, 40, 7.0
        t, Q, S, out_cum = linear_reservoir_response(0.0, k, dt, n, s0=q0 * k)
        a = math.exp(-dt / k)
        geo_ok = all(abs(Q[i] - q0 * a ** i) < 1e-9 for i in range(n + 1))
        mono_ok = all(Q[i + 1] < Q[i] for i in range(n))
        ok3 = geo_ok and mono_ok
        results.append(_row("step 3 - geometric monotone recession", ok3,
                            f"Q0={Q[0]:.3f} a={a:.4f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 3 - geometric monotone recession", False))

    # 4. Step response convergence -----------------------------------------
    try:
        k, dt = 2.0, 0.5
        n = int(round(60.0 / dt))
        t, Q, S, out_cum = linear_reservoir_response(5.0, k, dt, n, s0=0.0)
        ok4 = (abs(Q[0]) < 1e-12 and abs(Q[-1] - 5.0) < 1e-4
               and all(Q[i + 1] >= Q[i] for i in range(n)))
        results.append(_row("step 4 - step response → inflow (Wave53 tie)",
                            ok4, f"Q∞={Q[-1]:.4f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 4 - step response → inflow (Wave53 tie)",
                            False))

    # 5. Half-recession -----------------------------------------------------
    try:
        cfg = HydrographConfig(storage_k_days=6.0, dt_days=0.25,
                               storm_days=2.0, horizon_days=80.0)
        t, Q, _o = storm_hydrograph(10.0, cfg)
        half = half_recession_days(t, Q)
        expect = cfg.storage_k_days * math.log(2.0)
        ok5 = abs(half - expect) <= 2 * cfg.dt_days
        results.append(_row("step 5 - half-recession ≈ k·ln2", ok5,
                            f"t½={half:.3f}d expect={expect:.3f}d"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 5 - half-recession ≈ k·ln2", False))

    # 6. Storm hydrograph shape --------------------------------------------
    try:
        cfg = HydrographConfig(storage_k_days=5.0, dt_days=0.5,
                               storm_days=3.0, horizon_days=40.0)
        t, Q, _o = storm_hydrograph(12.0, cfg)
        peak_idx = int(np.argmax(Q))
        storm_steps = int(round(cfg.storm_days / cfg.dt_days))
        rec = Q[peak_idx:]
        ok6 = (abs(Q[0]) < 1e-12 and peak_idx == storm_steps
               and Q[peak_idx] < 12.0
               and all(rec[i + 1] < rec[i] for i in range(rec.size - 1)))
        results.append(_row("step 6 - storm hydrograph rise/peak/recede", ok6,
                            f"peak={Q[peak_idx]:.3f}@{t[peak_idx]:.1f}d"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 6 - storm hydrograph rise/peak/recede",
                            False))

    # 7. Real world ---------------------------------------------------------
    snap = None
    try:
        sim = _booted_sim("p124_real")
        snap = observe_hydrograph(sim)
        ok7 = (isinstance(snap, HydrographSnapshot)
               and snap.max_volume_residual < 1e-6
               and all(b.peak_discharge_m3s <= b.steady_discharge_m3s + 1e-9
                       for b in snap.basins_top))
        results.append(_row("step 7 - snapshot on real world", ok7))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 7 - snapshot on real world", False))

    # 8. read-only ----------------------------------------------------------
    try:
        sim2 = _booted_sim("p124_ro")
        world = sim2._genesis_bootstrap_state.world
        b_fd = world.flow_dir.copy()
        b_p = world.precip_mm.copy()
        b_tick = int(sim2.tick)
        observe_hydrograph(sim2)
        ok8 = (np.array_equal(world.flow_dir, b_fd)
               and np.array_equal(world.precip_mm, b_p)
               and int(sim2.tick) == b_tick)
        results.append(_row("step 8 - observe is read-only", ok8))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 8 - observe is read-only", False))

    # 9. determinism --------------------------------------------------------
    try:
        a = observe_hydrograph(_booted_sim("p124_d1", seed=0xBEEF_0124))
        b = observe_hydrograph(_booted_sim("p124_d2", seed=0xBEEF_0124))
        ok9 = a is not None and b is not None and a.signature == b.signature
        results.append(_row("step 9 - cross-sim determinism", ok9,
                            f"sig={a.signature[:12]}…" if a else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 9 - cross-sim determinism", False))

    # 10. install / uninstall / cadence ------------------------------------
    try:
        sim3 = _booted_sim("p124_io")
        orig = sim3.step
        st = install_hydrograph_observer(
            sim3, HydrographConfig(snapshot_every=2))
        again = install_hydrograph_observer(sim3)
        wrap_ok = (sim3.step is not orig and again is st)
        for _ in range(4):
            sim3.step()
        summ = hydrograph_summary(sim3)
        cad_ok = summ["installed"] and summ["n_snapshots"] >= 1
        uninstall_ok = (uninstall_hydrograph_observer(sim3) is True
                        and sim3.step is orig
                        and uninstall_hydrograph_observer(sim3) is False)
        ok10 = wrap_ok and cad_ok and uninstall_ok
        results.append(_row("step 10 - install/uninstall + cadence", ok10,
                            f"n_snaps={summ['n_snapshots']}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 10 - install/uninstall + cadence", False))

    for line in results:
        print(line)

    if snap is not None:
        print("\nSnapshot dump (sim p124_real) :")
        print(f"  storage_k_days         : {snap.storage_k_days:.2f}")
        print(f"  dt / storm / horizon   : {snap.dt_days:.2f}"
              f" / {snap.storm_days:.2f} / {snap.horizon_days:.2f} days")
        print(f"  n_steps                : {snap.n_steps}")
        print(f"  basins total/considered: {snap.n_basins_total}"
              f" / {snap.n_basins_considered}")
        print(f"  max_peak_discharge_m3s : {snap.max_peak_discharge_m3s:.3f}")
        print(f"  mean_time_to_peak_days : {snap.mean_time_to_peak_days:.3f}")
        print(f"  mean_half_recession    : {snap.mean_half_recession_days:.3f}")
        print(f"  max_volume_residual    : {snap.max_volume_residual:.2e}")
        for b in snap.basins_top:
            print(f"  basin#{b.basin_id:<5d} Q*={b.steady_discharge_m3s:.2f}"
                  f" peak={b.peak_discharge_m3s:.2f}m³/s"
                  f" t_peak={b.time_to_peak_days:.1f}d"
                  f" t½={b.half_recession_days:.1f}d")
        print(f"  signature              : {snap.signature}")

    passed = sum("[OK" in r for r in results)
    total = len(results)
    print("=" * 78)
    print(f"RESULT: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
