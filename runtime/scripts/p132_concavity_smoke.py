"""P132 - Wave 63 emergent channel-concavity / chi-steepness observer smoke.

 1. Public API exposed.
 2. Flint power-law recovery (pivot) : S = k_s*A^-theta -> theta, k_s, R^2=1.
 3. Concavity scale invariance : A->c*A, S->c*S leave theta unchanged.
 4. Chi transform : chi>=0, chi==0 at mouth, strictly increasing upstream.
 5. Chi-elevation linearity : z = a + b*chi recovered, R^2=1, slope=ksn.
 6. observe_concavity returns a sane snapshot on a real Genesis world.
 7. Invariants close on the real world (R^2 in [0,1], finite theta, fit set).
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
from engine.concavity_observer import (                                 # noqa: E402
    ConcavityConfig, ConcavitySnapshot,
    CONCAVITY_GRADED_LO, CONCAVITY_GRADED_HI,
    channel_slope_area, fit_flint_law, chi_transform,
    fit_chi_elevation, concavity_stage,
    observe_concavity, install_concavity_observer,
    uninstall_concavity_observer, concavity_summary,
)

_D8_SOUTH = 2   # flow_dir code for (dy=+1, dx=0) in the world_genesis D8 table
_D8_SINK = 255


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _booted_sim(name, seed=0x150A_0132, resolution=64):
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


def _linear_channel(n=24):
    """One vertical channel flowing south; mouth (bottom) is a sink.

    Column x=0 carries the channel; flow_acc grows downstream (y increasing).
    Returns ``(flow_dir, flow_acc, river_mask)`` of shape ``(n, 2)``.
    """
    flow_dir = np.full((n, 2), _D8_SINK, dtype=np.uint8)
    flow_acc = np.zeros((n, 2), dtype=np.float64)
    river_mask = np.zeros((n, 2), dtype=bool)
    for y in range(n):
        river_mask[y, 0] = True
        flow_acc[y, 0] = float(y + 1)            # acc increases downstream
        flow_dir[y, 0] = _D8_SOUTH if y < n - 1 else _D8_SINK
    return flow_dir, flow_acc, river_mask


def main() -> int:
    print("=" * 78)
    print("P132 - Wave 63 emergent channel-concavity / chi-steepness observer")
    print("=" * 78)
    results = []

    # 1. API surface --------------------------------------------------------
    try:
        api_ok = all(callable(f) for f in (
            channel_slope_area, fit_flint_law, chi_transform,
            fit_chi_elevation, concavity_stage,
            observe_concavity, install_concavity_observer,
            uninstall_concavity_observer, concavity_summary))
        results.append(_row("step 1 - public API exposed", api_ok))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 1 - public API exposed", False))

    # 2. Flint power-law recovery (pivot) -----------------------------------
    try:
        A = np.geomspace(1.0, 1.0e6, 200)
        theta_true, ks_true = 0.5, 2.0
        S = ks_true * A ** (-theta_true)
        theta, ks, r2, n = fit_flint_law(A, S)
        ok2 = (abs(theta - theta_true) < 1e-9
               and abs(ks - ks_true) < 1e-7
               and abs(r2 - 1.0) < 1e-12
               and n == 200)
        results.append(_row("step 2 - Flint power-law recovery", ok2,
                            f"theta={theta:.6f} ks={ks:.6f} R2={r2:.6f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 2 - Flint power-law recovery", False))

    # 3. Concavity scale invariance -----------------------------------------
    try:
        A = np.geomspace(1.0, 1.0e6, 200)
        S = 2.0 * A ** (-0.5)
        th0, ks0, _, _ = fit_flint_law(A, S)
        th_area, _, _, _ = fit_flint_law(1000.0 * A, S)   # A -> c*A
        th_slope, _, _, _ = fit_flint_law(A, 1000.0 * S)  # S -> c*S
        ok3 = (abs(th_area - th0) < 1e-9 and abs(th_slope - th0) < 1e-9)
        results.append(_row("step 3 - concavity scale invariance", ok3,
                            f"d_area={abs(th_area-th0):.2e} "
                            f"d_slope={abs(th_slope-th0):.2e}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 3 - concavity scale invariance", False))

    # 4. Chi transform : base level + monotone upstream ---------------------
    try:
        fd, acc, rm = _linear_channel(24)
        chi = chi_transform(fd, acc, rm, cell_m=100.0, theta_ref=0.45)
        col = chi[:, 0]
        ok4 = (bool(np.all(chi >= 0.0))
               and abs(col[-1]) < 1e-15                       # mouth chi == 0
               and bool(np.all(np.diff(col) < 0.0))           # decreasing d/s
               and bool(np.all(chi[:, 1] == 0.0)))            # non-channel = 0
        results.append(_row("step 4 - chi base level + monotone", ok4,
                            f"chi_head={col[0]:.3f} chi_mouth={col[-1]:.1e}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 4 - chi base level + monotone", False))

    # 5. Chi-elevation linearity --------------------------------------------
    try:
        fd, acc, rm = _linear_channel(24)
        chi = chi_transform(fd, acc, rm, cell_m=100.0, theta_ref=0.45)
        z = 100.0 + 3.5 * chi                                 # z = a + ksn*chi
        ksn, intercept, r2, n = fit_chi_elevation(chi, z, rm)
        ok5 = (abs(ksn - 3.5) < 1e-9
               and abs(intercept - 100.0) < 1e-6
               and abs(r2 - 1.0) < 1e-12
               and n == 24)
        results.append(_row("step 5 - chi-elevation linearity", ok5,
                            f"ksn={ksn:.6f} R2={r2:.6f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 5 - chi-elevation linearity", False))

    # 6-9 real world (res 192 -> a genuine emergent channel network) --------
    snap = None
    try:
        sim = _booted_sim("p132_real", resolution=192)
        snap = observe_concavity(sim)
        ok6 = (isinstance(snap, ConcavitySnapshot)
               and snap.n_cells > 0
               and snap.n_channel_cells > 0          # genuine network present
               and snap.n_fit_cells > 0              # fit actually ran
               and 0.0 <= snap.slope_area_r2 <= 1.0
               and 0.0 <= snap.chi_z_r2 <= 1.0
               and snap.chi_max >= 0.0
               and snap.stage in ("convex", "low-concavity", "graded",
                                  "high-concavity", "degenerate"))
        results.append(_row("step 6 - snapshot on real network", ok6,
                            f"n_chan={snap.n_channel_cells} "
                            f"n_fit={snap.n_fit_cells}" if snap else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 6 - snapshot on real network", False))

    try:
        # On a coarse tectonic/isostatic world (~20 km/cell) the emergent
        # terrain is NOT a graded fluvial landscape, so R^2 is honestly low.
        # The invariant is that the machinery runs and stays bounded/finite.
        ok7 = (snap is not None
               and np.isfinite(snap.concavity_theta)
               and np.isfinite(snap.ksn)
               and np.isfinite(snap.steepness_ks)
               and snap.n_fit_cells > 0
               and snap.mean_channel_slope >= 0.0
               and snap.chi_max > 0.0)
        results.append(_row("step 7 - invariants close (real)", ok7,
                            f"theta={snap.concavity_theta:.3f} "
                            f"sa_r2={snap.slope_area_r2:.3f}" if snap else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 7 - invariants close (real)", False))

    try:
        sim2 = _booted_sim("p132_ro", resolution=192)
        world = sim2._genesis_bootstrap_state.world
        b_el = world.elevation_m.copy()
        b_fd = world.flow_dir.copy()
        b_acc = world.flow_acc.copy()
        b_tick = int(sim2.tick)
        observe_concavity(sim2)
        ok8 = (np.array_equal(world.elevation_m, b_el)
               and np.array_equal(world.flow_dir, b_fd)
               and np.array_equal(world.flow_acc, b_acc)
               and int(sim2.tick) == b_tick)
        results.append(_row("step 8 - observe is read-only", ok8))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 8 - observe is read-only", False))

    try:
        a = observe_concavity(_booted_sim("p132_d1", seed=0xBEEF_0132,
                                          resolution=192))
        b = observe_concavity(_booted_sim("p132_d2", seed=0xBEEF_0132,
                                          resolution=192))
        ok9 = a is not None and b is not None and a.signature == b.signature
        results.append(_row("step 9 - cross-sim determinism", ok9,
                            f"sig={a.signature[:12]}..." if a else ""))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 9 - cross-sim determinism", False))

    # 10. install / uninstall + cadence ------------------------------------
    try:
        sim3 = _booted_sim("p132_io")
        orig = sim3.step
        st = install_concavity_observer(sim3, ConcavityConfig(snapshot_every=2))
        again = install_concavity_observer(sim3)
        round_trip = (sim3.step is not orig and again is st
                      and uninstall_concavity_observer(sim3) is True
                      and sim3.step is orig
                      and uninstall_concavity_observer(sim3) is False)
        sim4 = _booted_sim("p132_cad")
        install_concavity_observer(sim4, ConcavityConfig(snapshot_every=2))
        for _ in range(4):
            sim4.step()
        summ = concavity_summary(sim4)
        ok10 = (round_trip and summ["installed"] and summ["n_snapshots"] >= 1
                and 0.0 <= summ["slope_area_r2"] <= 1.0)
        results.append(_row("step 10 - install/uninstall + cadence", ok10,
                            f"n_snaps={summ['n_snapshots']}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 10 - install/uninstall + cadence", False))

    for line in results:
        print(line)

    if snap is not None:
        print("\nSnapshot dump (sim p132_real) :")
        print(f"  cell_km                  : {snap.cell_km:.3f}")
        print(f"  n_cells                  : {snap.n_cells}")
        print(f"  n_channel_cells          : {snap.n_channel_cells}")
        print(f"  n_fit_cells              : {snap.n_fit_cells}")
        print(f"  concavity_theta (m/n)    : {snap.concavity_theta:.6f}")
        print(f"  steepness_ks             : {snap.steepness_ks:.6g}")
        print(f"  slope_area_r2            : {snap.slope_area_r2:.6f}")
        print(f"  ref_concavity            : {snap.ref_concavity:.3f}")
        print(f"  ksn (chi-z slope)        : {snap.ksn:.6g}")
        print(f"  chi_z_r2                 : {snap.chi_z_r2:.6f}")
        print(f"  chi_max                  : {snap.chi_max:.3f}")
        print(f"  mean_channel_slope       : {snap.mean_channel_slope:.6f}")
        print(f"  stage                    : {snap.stage}")
        print(f"  graded band              : "
              f"[{CONCAVITY_GRADED_LO}, {CONCAVITY_GRADED_HI}]")
        print(f"  signature                : {snap.signature[:24]}...")

    passed = sum("[OK" in r for r in results)
    total = len(results)
    print("=" * 78)
    print(f"RESULT: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
