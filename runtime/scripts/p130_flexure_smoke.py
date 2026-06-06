"""P130 — Wave 61 elastic lithospheric flexure observer smoke.

 1. Public API exposed.
 2. Rigidity + flexural parameter closed forms (D, alpha).
 3. Flexural filter Phi(k) : Phi(0)=1, in (0,1], strictly decreasing.
 4. Airy limit : Te=0 ⇒ deflection == Wave 59 Airy root (machine precision).
 5. Zero-mode load balance + regional smoothing on a synthetic relief.
 6. observe_flexure returns a sane snapshot on a real Genesis world.
 7. Invariants close on the real world (zero-mode resid < 1e-9, smoother).
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
from engine.isostasy_observer import IsostasyConfig, airy_root_m        # noqa: E402
from engine.flexure_observer import (                                   # noqa: E402
    FlexureConfig, FlexureSnapshot,
    flexural_rigidity_nm, flexural_parameter_m, flexural_response,
    topographic_load_pa, flexural_deflection_m,
    observe_flexure, install_flexure_observer,
    uninstall_flexure_observer, flexure_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _booted_sim(name, seed=0x150A_0130, resolution=64):
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


def _synthetic_relief(n=64, seed=130):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:n, 0:n] / float(n)
    return (2500.0 * np.sin(2 * np.pi * x) * np.cos(2 * np.pi * y)
            + 600.0 * np.sin(2 * np.pi * 12 * x)
            + 200.0 * rng.standard_normal((n, n)) - 500.0)


def main() -> int:
    print("=" * 78)
    print("P130 — Wave 61 elastic lithospheric flexure observer")
    print("=" * 78)
    results = []
    cfg = FlexureConfig()

    # 1. API surface --------------------------------------------------------
    try:
        api_ok = all(callable(f) for f in (
            flexural_rigidity_nm, flexural_parameter_m, flexural_response,
            topographic_load_pa, flexural_deflection_m,
            observe_flexure, install_flexure_observer,
            uninstall_flexure_observer, flexure_summary))
        results.append(_row("step 1 - public API exposed", api_ok))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 1 - public API exposed", False))

    # 2. Closed forms D, alpha ----------------------------------------------
    try:
        te = cfg.elastic_thickness_km * 1000.0
        D_exp = cfg.young_modulus * te ** 3 / (12 * (1 - cfg.poisson_ratio ** 2))
        D = flexural_rigidity_nm(cfg)
        drho_g = (cfg.mantle_density - cfg.crust_density) * cfg.gravity
        a_exp = (4.0 * D / drho_g) ** 0.25
        ok2 = (abs(D - D_exp) < 1e-3
               and abs(flexural_parameter_m(cfg) - a_exp) < 1e-9
               and flexural_rigidity_nm(
                   FlexureConfig(elastic_thickness_km=0.0)) == 0.0)
        results.append(_row("step 2 - rigidity + flexural parameter", ok2,
                            f"alpha={a_exp / 1000:.1f}km"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 2 - rigidity + flexural parameter", False))

    # 3. Flexural filter ----------------------------------------------------
    try:
        ks = np.linspace(0.0, 1e-3, 256)
        phi = flexural_response(ks, cfg)
        ok3 = (abs(phi[0] - 1.0) < 1e-15
               and bool(np.all(phi > 0.0)) and bool(np.all(phi <= 1.0))
               and bool(np.all(np.diff(phi) < 0.0)))
        results.append(_row("step 3 - filter Phi(k) bounds + monotone", ok3,
                            f"Phi(kmax)={phi[-1]:.2e}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 3 - filter Phi(k) bounds + monotone", False))

    # 4. Airy limit (Te = 0) ------------------------------------------------
    try:
        h = _synthetic_relief()
        w0 = flexural_deflection_m(
            h, cell_m=1000.0, cfg=FlexureConfig(elastic_thickness_km=0.0))
        r = airy_root_m(h, IsostasyConfig())
        err = float(np.max(np.abs(w0 - r)))
        ok4 = err < 1e-6
        results.append(_row("step 4 - Airy limit Te=0", ok4,
                            f"max|w-r|={err:.2e}m"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 4 - Airy limit Te=0", False))

    # 5. Zero-mode balance + smoothing (synthetic) --------------------------
    try:
        h = _synthetic_relief()
        r = airy_root_m(h, IsostasyConfig())
        w = flexural_deflection_m(h, cell_m=1000.0, cfg=cfg)
        scale = float(np.abs(r).max())
        resid = abs(float(w.mean()) - float(r.mean())) / scale
        ok5 = resid < 1e-12 and float(w.std()) < float(r.std())
        results.append(_row("step 5 - zero-mode balance + smoothing", ok5,
                            f"resid={resid:.2e} "
                            f"std_ratio={w.std() / r.std():.3f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 5 - zero-mode balance + smoothing", False))

    # 6-9 real world --------------------------------------------------------
    snap = None
    try:
        sim = _booted_sim("p130_real")
        snap = observe_flexure(sim)
        ok6 = (isinstance(snap, FlexureSnapshot)
               and snap.n_cells > 0
               and snap.flexural_parameter_km > 0.0
               and 0.0 < snap.smoothing_ratio <= 1.0)
        results.append(_row("step 6 - snapshot on real world", ok6))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 6 - snapshot on real world", False))

    try:
        ok7 = (snap is not None and snap.zero_mode_residual < 1e-9
               and snap.smoother_than_airy)
        results.append(_row("step 7 - invariants close (real)", ok7,
                            f"resid={snap.zero_mode_residual:.2e}"
                            if snap else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 7 - invariants close (real)", False))

    try:
        sim2 = _booted_sim("p130_ro")
        world = sim2._genesis_bootstrap_state.world
        b_el = world.elevation_m.copy()
        b_fd = world.flow_dir.copy()
        b_tick = int(sim2.tick)
        observe_flexure(sim2)
        ok8 = (np.array_equal(world.elevation_m, b_el)
               and np.array_equal(world.flow_dir, b_fd)
               and int(sim2.tick) == b_tick)
        results.append(_row("step 8 - observe is read-only", ok8))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 8 - observe is read-only", False))

    try:
        a = observe_flexure(_booted_sim("p130_d1", seed=0xBEEF_0130))
        b = observe_flexure(_booted_sim("p130_d2", seed=0xBEEF_0130))
        ok9 = a is not None and b is not None and a.signature == b.signature
        results.append(_row("step 9 - cross-sim determinism", ok9,
                            f"sig={a.signature[:12]}…" if a else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 9 - cross-sim determinism", False))

    # 10. install / uninstall + cadence ------------------------------------
    try:
        sim3 = _booted_sim("p130_io")
        orig = sim3.step
        st = install_flexure_observer(sim3, FlexureConfig(snapshot_every=2))
        again = install_flexure_observer(sim3)
        round_trip = (sim3.step is not orig and again is st
                      and uninstall_flexure_observer(sim3) is True
                      and sim3.step is orig
                      and uninstall_flexure_observer(sim3) is False)
        sim4 = _booted_sim("p130_cad")
        install_flexure_observer(sim4, FlexureConfig(snapshot_every=2))
        for _ in range(4):
            sim4.step()
        summ = flexure_summary(sim4)
        ok10 = (round_trip and summ["installed"] and summ["n_snapshots"] >= 1
                and summ["zero_mode_residual"] < 1e-9)
        results.append(_row("step 10 - install/uninstall + cadence", ok10,
                            f"n_snaps={summ['n_snapshots']}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 10 - install/uninstall + cadence", False))

    for line in results:
        print(line)

    if snap is not None:
        print("\nSnapshot dump (sim p130_real) :")
        print(f"  cell_km                  : {snap.cell_km:.3f}")
        print(f"  n_cells                  : {snap.n_cells}")
        print(f"  te_km                    : {snap.te_km:.1f}")
        print(f"  rigidity_nm              : {snap.rigidity_nm:.3e}")
        print(f"  flexural_parameter_km    : {snap.flexural_parameter_km:.2f}")
        print(f"  mean_deflection_m        : {snap.mean_deflection_m:.2f}")
        print(f"  max_deflection_m         : {snap.max_deflection_m:.2f}")
        print(f"  min_deflection_m         : {snap.min_deflection_m:.2f}")
        print(f"  mean_moho_depth_km       : {snap.mean_moho_depth_km:.3f}")
        print(f"  zero_mode_residual       : {snap.zero_mode_residual:.2e}")
        print(f"  smoothing_ratio          : {snap.smoothing_ratio:.4f}")
        print(f"  response_at_nyquist      : {snap.response_at_nyquist:.2e}")
        print(f"  smoother_than_airy       : {snap.smoother_than_airy}")
        print(f"  signature                : {snap.signature[:24]}…")

    passed = sum("[OK" in r for r in results)
    total = len(results)
    print("=" * 78)
    print(f"RESULT: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
