"""P128 — Wave 59 Airy isostasy / crustal-root observer smoke.

 1. Public API exposed.
 2. Land root closed form : r = rho_c/(rho_m−rho_c)·h ; 0 at sea level.
 3. Ocean anti-root : negative sign, magnitude (rho_m−rho_w)/(rho_m−rho_c)·|h|.
 4. Crust thickens with elevation (mountain roots) ; T0 at sea level.
 5. Equal-pressure compensation : P at D_c uniform across a synthetic relief.
 6. observe_isostasy returns a sane snapshot on a real Genesis world.
 7. Isostatic residual closes on the real world (residual < 1e-6).
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
from engine.isostasy_observer import (                                  # noqa: E402
    IsostasyConfig, IsostasySnapshot,
    airy_root_m, crustal_thickness_m, compensation_pressure_pa,
    observe_isostasy, install_isostasy_observer,
    uninstall_isostasy_observer, isostasy_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _booted_sim(name, seed=0x150A_0128, resolution=64):
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


def main() -> int:
    print("=" * 78)
    print("P128 — Wave 59 Airy isostasy / crustal-root observer")
    print("=" * 78)
    results = []
    cfg = IsostasyConfig()

    # 1. API surface --------------------------------------------------------
    try:
        api_ok = all(callable(f) for f in (
            airy_root_m, crustal_thickness_m, compensation_pressure_pa,
            observe_isostasy, install_isostasy_observer,
            uninstall_isostasy_observer, isostasy_summary))
        results.append(_row("step 1 - public API exposed", api_ok))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 1 - public API exposed", False))

    # 2. Land root closed form ---------------------------------------------
    try:
        h = 2000.0
        exp = cfg.crust_density / (cfg.mantle_density - cfg.crust_density) * h
        ok2 = (abs(airy_root_m(h, cfg) - exp) < 1e-9
               and abs(airy_root_m(0.0, cfg)) < 1e-12)
        results.append(_row("step 2 - land root closed form", ok2,
                            f"r({h:.0f}m)={airy_root_m(h, cfg):.1f}m"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 2 - land root closed form", False))

    # 3. Ocean anti-root ----------------------------------------------------
    try:
        d = 4000.0
        r = airy_root_m(-d, cfg)
        exp = (cfg.crust_density - cfg.water_density) / (
            cfg.mantle_density - cfg.crust_density) * d
        ok3 = r < 0.0 and abs(-r - exp) < 1e-9
        results.append(_row("step 3 - ocean anti-root sign/magnitude", ok3,
                            f"a({d:.0f}m)={-r:.1f}m"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 3 - ocean anti-root sign/magnitude", False))

    # 4. Crust thickens with elevation -------------------------------------
    try:
        hs = np.array([-2000.0, 0.0, 1000.0, 4000.0])
        H = crustal_thickness_m(hs, cfg)
        ok4 = (bool(np.all(np.diff(H) > 0.0))
               and abs(crustal_thickness_m(0.0, cfg)
                       - cfg.reference_crust_km * 1000.0) < 1e-6)
        results.append(_row("step 4 - crust thickens with elevation", ok4,
                            f"H={[round(x / 1000, 1) for x in H]}km"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 4 - crust thickens with elevation", False))

    # 5. Equal-pressure compensation (synthetic) ---------------------------
    try:
        h = np.array([-5000.0, -1000.0, 0.0, 800.0, 2500.0, 6000.0])
        root = airy_root_m(h, cfg)
        moho = cfg.reference_crust_km * 1000.0 + root
        Dc = float(moho.max()) + 10_000.0
        P = compensation_pressure_pa(h, Dc, cfg)
        resid = (P.max() - P.min()) / P.mean()
        ok5 = resid < 1e-12
        results.append(_row("step 5 - equal-pressure compensation", ok5,
                            f"resid={resid:.2e}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 5 - equal-pressure compensation", False))

    # 6-9 real world --------------------------------------------------------
    snap = None
    try:
        sim = _booted_sim("p128_real")
        snap = observe_isostasy(sim)
        ok6 = (isinstance(snap, IsostasySnapshot)
               and snap.n_cells > 0
               and snap.mean_crust_thickness_km > 0.0
               and snap.max_crust_thickness_km >= snap.min_crust_thickness_km)
        results.append(_row("step 6 - snapshot on real world", ok6))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 6 - snapshot on real world", False))

    try:
        ok7 = (snap is not None and snap.isostatic_residual < 1e-6
               and snap.roots_track_elevation)
        results.append(_row("step 7 - equal-pressure invariant (real)", ok7,
                            f"resid={snap.isostatic_residual:.2e}"
                            if snap else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 7 - equal-pressure invariant (real)", False))

    try:
        sim2 = _booted_sim("p128_ro")
        world = sim2._genesis_bootstrap_state.world
        b_el = world.elevation_m.copy()
        b_fd = world.flow_dir.copy()
        b_tick = int(sim2.tick)
        observe_isostasy(sim2)
        ok8 = (np.array_equal(world.elevation_m, b_el)
               and np.array_equal(world.flow_dir, b_fd)
               and int(sim2.tick) == b_tick)
        results.append(_row("step 8 - observe is read-only", ok8))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 8 - observe is read-only", False))

    try:
        a = observe_isostasy(_booted_sim("p128_d1", seed=0xBEEF_0128))
        b = observe_isostasy(_booted_sim("p128_d2", seed=0xBEEF_0128))
        ok9 = a is not None and b is not None and a.signature == b.signature
        results.append(_row("step 9 - cross-sim determinism", ok9,
                            f"sig={a.signature[:12]}…" if a else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 9 - cross-sim determinism", False))

    # 10. install / uninstall + cadence ------------------------------------
    try:
        sim3 = _booted_sim("p128_io")
        orig = sim3.step
        st = install_isostasy_observer(sim3, IsostasyConfig(snapshot_every=2))
        again = install_isostasy_observer(sim3)
        round_trip = (sim3.step is not orig and again is st
                      and uninstall_isostasy_observer(sim3) is True
                      and sim3.step is orig
                      and uninstall_isostasy_observer(sim3) is False)
        sim4 = _booted_sim("p128_cad")
        install_isostasy_observer(sim4, IsostasyConfig(snapshot_every=2))
        for _ in range(4):
            sim4.step()
        summ = isostasy_summary(sim4)
        ok10 = (round_trip and summ["installed"] and summ["n_snapshots"] >= 1
                and summ["isostatic_residual"] < 1e-6)
        results.append(_row("step 10 - install/uninstall + cadence", ok10,
                            f"n_snaps={summ['n_snapshots']}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 10 - install/uninstall + cadence", False))

    for line in results:
        print(line)

    if snap is not None:
        print("\nSnapshot dump (sim p128_real) :")
        print(f"  cell_km                  : {snap.cell_km:.3f}")
        print(f"  n_cells                  : {snap.n_cells}")
        print(f"  mean_elevation_m         : {snap.mean_elevation_m:.2f}")
        print(f"  mean_crust_thickness_km  : {snap.mean_crust_thickness_km:.3f}")
        print(f"  max_crust_thickness_km   : {snap.max_crust_thickness_km:.3f}")
        print(f"  min_crust_thickness_km   : {snap.min_crust_thickness_km:.3f}")
        print(f"  mean_moho_depth_km       : {snap.mean_moho_depth_km:.3f}")
        print(f"  max_root_m               : {snap.max_root_m:.1f}")
        print(f"  max_antiroot_m           : {snap.max_antiroot_m:.1f}")
        print(f"  compensation_depth_km    : {snap.compensation_depth_km:.3f}")
        print(f"  isostatic_residual       : {snap.isostatic_residual:.2e}")
        print(f"  roots_track_elevation    : {snap.roots_track_elevation}")
        print(f"  signature                : {snap.signature[:24]}…")

    passed = sum("[OK" in r for r in results)
    total = len(results)
    print("=" * 78)
    print(f"RESULT: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
 