"""P127 - Wave 58 open-endedness / evolutionary-activity (Bedau-Packard) smoke.

 1. Public API exposed.
 2. Additive closure : A(T) == sum a_i(T) on an open-ended series.
 3. Diversity monotone and sum(n_new) == D_final.
 4. Frozen system (no novelty) classifies as "none".
 5. Saturating system (novelty rate -> 0) classifies as "bounded".
 6. Open-ended system (sustained novelty) classifies as "unbounded".
 7. observe_evolutionary_activity is read-only on a real Genesis world.
 8. Repeated observe is deterministic (same signature / both None).
 9. Cross-sim determinism : same world seed => same snapshot signature.
10. install / uninstall round-trip + idempotent + captures cadence.
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
from engine.evolutionary_activity import (                              # noqa: E402
    EvoActivityConfig, EvoActivitySnapshot,
    diversity_curve, new_component_curve, component_activity,
    total_activity_curve, classify_dynamics, evolutionary_activity_stats,
    component_usage, observe_evolutionary_activity,
    install_evolutionary_activity_observer,
    uninstall_evolutionary_activity_observer, evolutionary_activity_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _booted_sim(name, seed=0x0EE_0127, resolution=64,
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


def _series_none(T=200):
    return [{"a": 1.0, "b": 1.0, "c": 1.0} for _ in range(T)]


def _series_unbounded(T=200):
    return [{f"n{t}": 1.0, "a": 1.0} for t in range(T)]


def _series_bounded(T=200):
    out = []
    for t in range(T):
        step = {"a": 1.0}
        r = int(math.isqrt(t))
        if r * r == t:
            step[f"sq{t}"] = 1.0
        out.append(step)
    return out


def main() -> int:
    print("=" * 78)
    print("P127 - Wave 58 open-endedness / evolutionary-activity (Bedau-Packard)")
    print("=" * 78)
    results = []
    cfg = EvoActivityConfig()
    snap = None

    # 1. API surface --------------------------------------------------------
    try:
        api_ok = all(callable(f) for f in (
            diversity_curve, new_component_curve, component_activity,
            total_activity_curve, classify_dynamics,
            evolutionary_activity_stats, component_usage,
            observe_evolutionary_activity,
            install_evolutionary_activity_observer,
            uninstall_evolutionary_activity_observer,
            evolutionary_activity_summary))
        results.append(_row("step 1 - public API exposed", api_ok))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 1 - public API exposed", False))

    # 2. Additive closure A(T) == sum a_i(T) -------------------------------
    try:
        ser = _series_unbounded()
        A_T = float(total_activity_curve(ser)[-1])
        sum_ai = float(sum(component_activity(ser).values()))
        resid = abs(A_T - sum_ai)
        ok2 = resid < 1e-9
        results.append(_row("step 2 - A(T) == sum a_i(T)", ok2,
                            f"residual={resid:.2e}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 2 - A(T) == sum a_i(T)", False))

    # 3. Diversity monotone + sum(n_new) == D_final ------------------------
    try:
        ser = _series_bounded()
        D = diversity_curve(ser)
        nnew = new_component_curve(ser)
        ok3 = (bool(np.all(np.diff(D) >= 0))
               and int(nnew.sum()) == int(D[-1]))
        results.append(_row("step 3 - D monotone & sum(n_new)==D_final", ok3,
                            f"D_final={int(D[-1])}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 3 - D monotone & sum(n_new)==D_final", False))

    # 4. Frozen system -> none ---------------------------------------------
    try:
        cls = classify_dynamics(_series_none(), cfg)
        ok4 = cls == "none"
        results.append(_row("step 4 - frozen system => none", ok4,
                            f"class={cls}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 4 - frozen system => none", False))

    # 5. Saturating system -> bounded --------------------------------------
    try:
        st = evolutionary_activity_stats(_series_bounded(), cfg)
        ok5 = st.dynamics_class == "bounded"
        results.append(_row("step 5 - saturating system => bounded", ok5,
                            f"class={st.dynamics_class} "
                            f"rate={st.innovation_rate_tail:.3f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 5 - saturating system => bounded", False))

    # 6. Open-ended system -> unbounded ------------------------------------
    try:
        st = evolutionary_activity_stats(_series_unbounded(), cfg)
        ok6 = st.dynamics_class == "unbounded"
        results.append(_row("step 6 - open-ended system => unbounded", ok6,
                            f"class={st.dynamics_class} D={st.diversity_final}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 6 - open-ended system => unbounded", False))

    # 7. observe read-only on real Genesis world ---------------------------
    try:
        sim = _booted_sim("p127_real")
        tick0 = int(sim.tick)
        usage0 = component_usage(sim)
        snap = observe_evolutionary_activity(sim)
        ok7 = (int(sim.tick) == tick0
               and component_usage(sim) == usage0
               and (snap is None or isinstance(snap, EvoActivitySnapshot)))
        results.append(_row("step 7 - observe read-only on Genesis world", ok7,
                            f"n_components={len(usage0)}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 7 - observe read-only on Genesis world",
                            False))

    # 8. Repeated observe deterministic ------------------------------------
    try:
        sim = _booted_sim("p127_repeat")
        s1 = observe_evolutionary_activity(sim)
        s2 = observe_evolutionary_activity(sim)
        if s1 is None:
            ok8 = s2 is None
        else:
            ok8 = (s2 is not None and s1.signature == s2.signature)
        results.append(_row("step 8 - repeated observe deterministic", ok8))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 8 - repeated observe deterministic", False))

    # 9. Cross-sim determinism (install + step) ----------------------------
    try:
        sigs = []
        for _ in range(2):
            simd = _booted_sim("p127_det", seed=0x0EE_5151)
            install_evolutionary_activity_observer(
                simd, EvoActivityConfig(snapshot_every=1))
            for _ in range(3):
                simd.step()
            snaps = simd._evo_activity_state.history.snapshots
            sigs.append(snaps[-1].signature)
        ok9 = sigs[0] == sigs[1]
        results.append(_row("step 9 - cross-sim signature determinism", ok9,
                            f"sig={sigs[0][:12]}..."))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 9 - cross-sim signature determinism", False))

    # 10. install / uninstall round-trip + cadence -------------------------
    try:
        sim4 = _booted_sim("p127_install")
        original_step = sim4.step
        state = install_evolutionary_activity_observer(
            sim4, EvoActivityConfig(snapshot_every=1))
        idem = install_evolutionary_activity_observer(sim4) is state
        for _ in range(2):
            sim4.step()
        summ = evolutionary_activity_summary(sim4)
        round_trip = (uninstall_evolutionary_activity_observer(sim4)
                      and sim4.step is original_step)
        ok10 = (idem and summ["installed"] and summ["n_snapshots"] >= 1
                and round_trip)
        results.append(_row("step 10 - install/uninstall + cadence", ok10,
                            f"n_snaps={summ['n_snapshots']}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 10 - install/uninstall + cadence", False))

    for line in results:
        print(line)

    if snap is not None:
        s = snap.stats
        print("\nSnapshot dump (sim p127_real) :")
        print(f"  n_steps                : {s.n_steps}")
        print(f"  n_components           : {s.n_components}")
        print(f"  diversity_final        : {s.diversity_final}")
        print(f"  total_cum_activity     : {s.total_cumulative_activity:.2f}")
        print(f"  mean_cum_activity      : {s.mean_cumulative_activity:.4f}")
        print(f"  innovation_rate_tail   : {s.innovation_rate_tail:.4f}")
        print(f"  significance_threshold : {s.significance_threshold:.4f}")
        print(f"  n_significant          : {s.n_significant_components}")
        print(f"  dynamics_class         : {s.dynamics_class}")
        print(f"  signature              : {snap.signature}")

    passed = sum("[OK" in r for r in results)
    total = len(results)
    print("=" * 78)
    print(f"RESULT: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
