"""P131 — Wave 62 emergent hypsometry / landscape-maturity observer smoke.

 1. Public API exposed.
 2. Closed-form HI : elevation-relief ratio, affine invariance, linear ramp=0.5.
 3. Survival curve : a*(0)=1, bounded [0,1], monotone non-increasing.
 4. Pike-Wilson identity : trapz(curve) == HI (Pike & Wilson 1971).
 5. Strahler stages + skewness on synthetic youthful/mature/old reliefs.
 6. observe_hypsometry returns a sane snapshot on a real Genesis world.
 7. Invariants close on the real world (pike_wilson resid < 1e-3, HI in [0,1]).
 8. Snapshot is read-only : world arrays + sim tick unchanged.
 9. Cross-sim determinism : same world seed => same signature.
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
from engine.hypsometry_observer import (                                # noqa: E402
    HypsometryConfig, HypsometrySnapshot,
    STAGE_YOUTHFUL, STAGE_MATURE,
    relative_elevation, hypsometric_integral, hypsometric_curve,
    hypsometric_skewness, hypsometric_stage,
    observe_hypsometry, install_hypsometry_observer,
    uninstall_hypsometry_observer, hypsometry_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _booted_sim(name, seed=0x150A_0131, resolution=64):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=20,
        bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
        drive_accel=1500.0, cultures=1,
    )
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


def _synthetic_relief(n=64, seed=131):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n] / float(n)
    return (2500.0 * np.sin(2 * np.pi * x) * np.cos(2 * np.pi * y)
            + 600.0 * np.sin(2 * np.pi * 12 * x)
            + 200.0 * rng.standard_normal((n, n)) - 500.0)


def _power_field(power, n=64):
    """Relief whose relative elevations follow x**power: HI -> 1/(power+1)."""
    base = np.linspace(0.0, 1.0, n * n) ** power
    return (base * 4000.0 - 1000.0).reshape(n, n)


def main() -> int:
    print("=" * 78)
    print("P131 — Wave 62 emergent hypsometry / landscape-maturity observer")
    print("=" * 78)
    results = []

    # 1. API surface --------------------------------------------------------
    try:
        api_ok = all(callable(f) for f in (
            relative_elevation, hypsometric_integral, hypsometric_curve,
            hypsometric_skewness, hypsometric_stage,
            observe_hypsometry, install_hypsometry_observer,
            uninstall_hypsometry_observer, hypsometry_summary))
        results.append(_row("step 1 - public API exposed", api_ok))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 1 - public API exposed", False))

    # 2. Closed forms : HI, affine invariance, linear ramp ------------------
    try:
        h = _synthetic_relief()
        hi = hypsometric_integral(h)
        e = (float(h.mean()) - float(h.min())) / (float(h.max()) - float(h.min()))
        hi_affine = hypsometric_integral(3.0 * h + 1234.5)
        ramp = np.linspace(-1000.0, 5000.0, 4096).reshape(64, 64)
        ok2 = (abs(hi - e) < 1e-12
               and abs(hi_affine - hi) < 1e-9
               and abs(hypsometric_integral(ramp) - 0.5) < 1e-9
               and 0.0 <= hi <= 1.0)
        results.append(_row("step 2 - HI closed form + affine + ramp", ok2,
                            f"HI={hi:.4f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 2 - HI closed form + affine + ramp", False))

    # 3. Survival curve shape -----------------------------------------------
    try:
        h = _synthetic_relief()
        lv, af = hypsometric_curve(h, 512)
        ok3 = (len(lv) == 513 and len(af) == 513
               and abs(af[0] - 1.0) < 1e-15
               and bool(np.all(af >= 0.0)) and bool(np.all(af <= 1.0))
               and bool(np.all(np.diff(af) <= 1e-15))
               and abs(lv[0]) < 1e-15 and abs(lv[-1] - 1.0) < 1e-15)
        results.append(_row("step 3 - survival curve monotone + bounds", ok3,
                            f"a*(1)={af[-1]:.2e}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 3 - survival curve monotone + bounds", False))

    # 4. Pike-Wilson identity -----------------------------------------------
    try:
        h = _synthetic_relief()
        hi = hypsometric_integral(h)
        lv, af = hypsometric_curve(h, 512)
        ci = float(np.trapezoid(af, lv))
        resid = abs(ci - hi)
        ok4 = resid < 1e-3
        results.append(_row("step 4 - Pike-Wilson identity", ok4,
                            f"resid={resid:.2e}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 4 - Pike-Wilson identity", False))

    # 5. Strahler stages + skewness -----------------------------------------
    try:
        hi_young = hypsometric_integral(_power_field(0.25))   # ~0.80
        hi_mature = hypsometric_integral(_power_field(1.0))   # ~0.50
        hi_old = hypsometric_integral(_power_field(4.0))      # ~0.20
        stages_ok = (hypsometric_stage(hi_young) == "youthful"
                     and hypsometric_stage(hi_mature) == "mature"
                     and hypsometric_stage(hi_old) == "monadnock"
                     and hypsometric_stage(0.0, relief=0.0) == "degenerate")
        ordering_ok = hi_young > STAGE_YOUTHFUL > hi_mature > STAGE_MATURE > hi_old
        # Old landscape: mass at low elevations => positive skew; young => neg.
        skew_ok = (hypsometric_skewness(_power_field(4.0)) > 0.0
                   and hypsometric_skewness(_power_field(0.25)) < 0.0)
        ok5 = stages_ok and ordering_ok and skew_ok
        results.append(_row("step 5 - Strahler stages + skewness", ok5,
                            f"HI young/mat/old={hi_young:.2f}/"
                            f"{hi_mature:.2f}/{hi_old:.2f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 5 - Strahler stages + skewness", False))

    # 6-9 real world --------------------------------------------------------
    snap = None
    try:
        sim = _booted_sim("p131_real")
        snap = observe_hypsometry(sim)
        ok6 = (isinstance(snap, HypsometrySnapshot)
               and snap.n_cells > 0
               and 0.0 <= snap.hypsometric_integral <= 1.0
               and snap.relief_m > 0.0
               and len(snap.curve_deciles) == 11
               and snap.stage in ("youthful", "mature", "monadnock"))
        results.append(_row("step 6 - snapshot on real world", ok6))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 6 - snapshot on real world", False))

    try:
        ok7 = (snap is not None and snap.pike_wilson_residual < 1e-3
               and abs(snap.curve_deciles[0] - 1.0) < 1e-12
               and 0.0 <= snap.land_fraction <= 1.0)
        results.append(_row("step 7 - invariants close (real)", ok7,
                            f"resid={snap.pike_wilson_residual:.2e}"
                            if snap else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 7 - invariants close (real)", False))

    try:
        sim2 = _booted_sim("p131_ro")
        world = sim2._genesis_bootstrap_state.world
        b_el = world.elevation_m.copy()
        b_fd = world.flow_dir.copy()
        b_tick = int(sim2.tick)
        observe_hypsometry(sim2)
        ok8 = (np.array_equal(world.elevation_m, b_el)
               and np.array_equal(world.flow_dir, b_fd)
               and int(sim2.tick) == b_tick)
        results.append(_row("step 8 - observe is read-only", ok8))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 8 - observe is read-only", False))

    try:
        a = observe_hypsometry(_booted_sim("p131_d1", seed=0xBEEF_0131))
        b = observe_hypsometry(_booted_sim("p131_d2", seed=0xBEEF_0131))
        ok9 = a is not None and b is not None and a.signature == b.signature
        results.append(_row("step 9 - cross-sim determinism", ok9,
                            f"sig={a.signature[:12]}…" if a else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 9 - cross-sim determinism", False))

    # 10. install / uninstall + cadence ------------------------------------
    try:
        sim3 = _booted_sim("p131_io")
        orig = sim3.step
        st = install_hypsometry_observer(sim3, HypsometryConfig(snapshot_every=2))
        again = install_hypsometry_observer(sim3)
        round_trip = (sim3.step is not orig and again is st
                      and uninstall_hypsometry_observer(sim3) is True
                      and sim3.step is orig
                      and uninstall_hypsometry_observer(sim3) is False)
        sim4 = _booted_sim("p131_cad")
        install_hypsometry_observer(sim4, HypsometryConfig(snapshot_every=2))
        for _ in range(4):
            sim4.step()
        summ = hypsometry_summary(sim4)
        ok10 = (round_trip and summ["installed"] and summ["n_snapshots"] >= 1
                and summ["pike_wilson_residual"] < 1e-3)
        results.append(_row("step 10 - install/uninstall + cadence", ok10,
                            f"n_snaps={summ['n_snapshots']}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 10 - install/uninstall + cadence", False))

    for line in results:
        print(line)

    if snap is not None:
        print("\nSnapshot dump (sim p131_real) :")
        print(f"  cell_km                  : {snap.cell_km:.3f}")
        print(f"  n_cells                  : {snap.n_cells}")
        print(f"  min/max/mean elev_m      : {snap.min_elev_m:.1f} / "
              f"{snap.max_elev_m:.1f} / {snap.mean_elev_m:.1f}")
        print(f"  relief_m                 : {snap.relief_m:.1f}")
        print(f"  land_fraction            : {snap.land_fraction:.4f}")
        print(f"  hypsometric_integral     : {snap.hypsometric_integral:.6f}")
        print(f"  curve_integral           : {snap.curve_integral:.6f}")
        print(f"  pike_wilson_residual     : {snap.pike_wilson_residual:.2e}")
        print(f"  skewness                 : {snap.skewness:.4f}")
        print(f"  stage                    : {snap.stage}")
        print(f"  curve_deciles            : "
              f"{[round(d, 3) for d in snap.curve_deciles]}")
        print(f"  signature                : {snap.signature[:24]}…")

    passed = sum("[OK" in r for r in results)
    total = len(results)
    print("=" * 78)
    print(f"RESULT: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
