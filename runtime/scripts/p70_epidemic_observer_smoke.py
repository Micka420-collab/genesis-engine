"""P70 — Wave 39 epidemic observer smoke.

  1. Public API surface.
  2. Without physiology installed → no pathogen arrays, all zeros.
  3. With physiology + 0 infections → all susceptible (S = n_alive).
  4. Manual injection of cholera load on agent 0 → infectious count rises.
  5. SIR counts sum to n_alive (or close, accounting for thresholds).
  6. Multiple pathogens tracked simultaneously and independently.
  7. R0 estimate produces a non-negative finite number.
  8. Determinism : two installed observers same seed → identical history.
  9. Snapshot wrapper fires every snapshot_every ticks.
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
from engine.physiology import install_physiology                        # noqa: E402
from engine.epidemic_observer import (                                  # noqa: E402
    DEFAULT_PATHOGENS, EpidemicConfig, PathogenSnapshot,
    EpidemicSnapshot, EpidemicHistory,
    observe_pathogen, take_epidemic_snapshot,
    estimate_r0_for_pathogen,
    install_epidemic_observer, uninstall_epidemic_observer,
    epidemic_state_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xC0FFEE_70):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=8, max_agents=20,
        bounds_km=(0.5, 0.5), spawn_radius_m=80.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def main() -> int:
    print("=" * 78)
    print("P70 — Wave 39 epidemic observer smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API.
    ok = all(name in globals() for name in (
        "EpidemicConfig", "PathogenSnapshot", "EpidemicSnapshot",
        "EpidemicHistory", "observe_pathogen",
        "take_epidemic_snapshot", "estimate_r0_for_pathogen",
        "install_epidemic_observer", "uninstall_epidemic_observer",
        "epidemic_state_summary", "DEFAULT_PATHOGENS",
    )) and DEFAULT_PATHOGENS == ("cholera", "flu", "wound")
    print(_row("step 1 - API + DEFAULT_PATHOGENS", ok,
                f"pathogens={DEFAULT_PATHOGENS}"))
    if not ok:
        failures += 1

    # Step 2 — without physiology, all zeros.
    sim_no_phys = _build_sim("p70_no_phys")
    sim_no_phys.step()
    snap_empty = take_epidemic_snapshot(sim_no_phys)
    ok = (snap_empty.tick == sim_no_phys.tick
          and all(ps.n_infectious == 0 for ps in snap_empty.per_pathogen.values()))
    print(_row("step 2 - no physiology → no infections",
               ok, f"n_alive={snap_empty.n_alive} "
                   f"infectious={ {p: ps.n_infectious for p, ps in snap_empty.per_pathogen.items()} }"))
    if not ok:
        failures += 1

    # Step 3 — with physiology, 0 infections → all susceptible.
    sim = _build_sim("p70_clean", seed=0xC0FFEE_7011 & 0xFFFFFFFFFFFFFFFF)
    sim.step()
    phys = install_physiology(sim)
    snap_clean = take_epidemic_snapshot(sim)
    n_alive = snap_clean.n_alive
    susceptible_ok = True
    for p, ps in snap_clean.per_pathogen.items():
        if ps.n_infectious > 0 or (ps.n_susceptible + ps.n_recovered) != n_alive:
            susceptible_ok = False
    ok = susceptible_ok and n_alive >= 1
    print(_row("step 3 - physiology + 0 infections → all susceptible",
               ok, f"n_alive={n_alive} "
                   f"susceptible={ {p: ps.n_susceptible for p, ps in snap_clean.per_pathogen.items()} }"))
    if not ok:
        failures += 1

    # Step 4 — manual cholera injection → infectious rises.
    n = sim.agents.n_active
    phys.cholera_load[0] = 0.5
    phys.cholera_load[1] = 0.3
    snap_inj = take_epidemic_snapshot(sim)
    n_inf_chol = snap_inj.per_pathogen["cholera"].n_infectious
    ok = n_inf_chol >= 2
    print(_row("step 4 - manual cholera load → infectious counted",
               ok, f"n_infectious_cholera={n_inf_chol}"))
    if not ok:
        failures += 1

    # Step 5 — S + I + R = n_alive for each pathogen.
    sir_ok = True
    for p, ps in snap_inj.per_pathogen.items():
        if ps.n_susceptible + ps.n_infectious + ps.n_recovered != ps.n_alive:
            sir_ok = False
    ok = sir_ok
    print(_row("step 5 - S + I + R == n_alive per pathogen",
               ok, f"cholera S+I+R={snap_inj.per_pathogen['cholera'].n_susceptible}+"
                   f"{snap_inj.per_pathogen['cholera'].n_infectious}+"
                   f"{snap_inj.per_pathogen['cholera'].n_recovered}="
                   f"{snap_inj.per_pathogen['cholera'].n_susceptible + snap_inj.per_pathogen['cholera'].n_infectious + snap_inj.per_pathogen['cholera'].n_recovered}"))
    if not ok:
        failures += 1

    # Step 6 — multiple pathogens independent.
    phys.flu_load[2] = 0.4
    phys.wound_load[3] = 0.3
    snap_multi = take_epidemic_snapshot(sim)
    n_chol = snap_multi.per_pathogen["cholera"].n_infectious
    n_flu = snap_multi.per_pathogen["flu"].n_infectious
    n_wound = snap_multi.per_pathogen["wound"].n_infectious
    ok = (n_chol >= 1 and n_flu >= 1 and n_wound >= 1
          and n_chol != n_flu or n_chol != n_wound)
    print(_row("step 6 - 3 pathogens tracked independently",
               ok, f"cholera={n_chol} flu={n_flu} wound={n_wound}"))
    if not ok:
        failures += 1

    # Step 7 — R0 estimate non-negative finite.
    state = install_epidemic_observer(
        sim, EpidemicConfig(snapshot_every=1, r0_window_snapshots=3))
    # Run a few ticks with cholera growing manually.
    for tick_off in range(5):
        phys.cholera_load[tick_off % n] = 0.5
        sim.step()
    r0 = estimate_r0_for_pathogen(state.history, "cholera", window=3)
    ok = np.isfinite(r0) and r0 >= 0.0
    print(_row("step 7 - R0 estimate non-negative finite",
               ok, f"R0_cholera={r0:.3f}"))
    if not ok:
        failures += 1

    # Step 8 — determinism : two sims same seed give same history shape.
    def _run_observed(seed):
        sub = _build_sim(f"p70_det_{seed}",
                          seed=seed & 0xFFFFFFFFFFFFFFFF)
        sub.step()
        install_physiology(sub)
        install_epidemic_observer(
            sub, EpidemicConfig(snapshot_every=2))
        for _ in range(10):
            sub.step()
        return tuple(
            (s.tick,
             s.per_pathogen["cholera"].n_susceptible,
             s.per_pathogen["cholera"].n_infectious,
             s.per_pathogen["cholera"].n_recovered)
            for s in sub._epidemic_state.history.snapshots
        )
    seed_d = 0xC0FFEE_7012 & 0xFFFFFFFFFFFFFFFF
    h_a = _run_observed(seed_d)
    h_b = _run_observed(seed_d)
    ok = h_a == h_b and len(h_a) >= 2
    print(_row("step 8 - determinism inter-runs",
               ok, f"len={len(h_a)} match={h_a == h_b}"))
    if not ok:
        failures += 1

    # Step 9 — snapshot wrapper fires at the right cadence.
    sim_cad = _build_sim("p70_cad",
                          seed=0xC0FFEE_7013 & 0xFFFFFFFFFFFFFFFF)
    sim_cad.step()
    install_physiology(sim_cad)
    state_cad = install_epidemic_observer(
        sim_cad, EpidemicConfig(snapshot_every=5))
    for _ in range(20):
        sim_cad.step()
    # Snapshots taken at ticks where tick % 5 ≈ 0 from start.
    n_snapshots = len(state_cad.history.snapshots)
    # Expected ~ 4 snapshots (20 ticks / 5) since wrap captures after step.
    ok = 2 <= n_snapshots <= 6
    print(_row("step 9 - wrapper captures at expected cadence",
               ok, f"n_snapshots={n_snapshots} ticks_run={state_cad.history.n_ticks_run}"))
    if not ok:
        failures += 1

    # Diagnostic dump.
    summary = epidemic_state_summary(sim_cad)
    print(f"\nEpidemic summary on sim_cad: {summary}")

    total = 9
    passed = total - failures
    print("=" * 78)
    if failures == 0:
        print(f"RESULT: {total}/{total} PASS")
        return 0
    else:
        print(f"RESULT: {passed}/{total} PASS, {failures} FAIL")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
