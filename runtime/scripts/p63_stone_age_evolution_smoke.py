"""P63 — Wave 33 stone-age evolution observer smoke.

Validates the read-only observer harness. The agents drive their own
evolution via engine.cognition + engine.polity + engine.invention etc.
This module ONLY observes — no script, no analytical solver.

  1. Public API surface.
  2. Initial snapshot at tick 0 captures alive founders, zero polities,
     zero inventions (stone-age starting state).
  3. After K ticks, snapshots are taken at expected intervals.
  4. Trail density grid is populated.
  5. Agent clusters observed (positions naturally clump).
  6. Determinism : two runs same seed → same trajectory signature.
  7. The observer never mutates sim state (read-only contract).
  8. evolution_summary returns plausible aggregates.
  9. Snapshots show monotone tick progression.
"""
from __future__ import annotations

import io
import os
import sys
import hashlib
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
from engine.stone_age_evolution import (                                # noqa: E402
    StoneAgeConfig, EvolutionSnapshot, EvolutionHistory,
    AgentSnapshot, ClusterObservation,
    observe_agents, observe_clusters, observe_polities,
    observe_inventions, observe_buildings, observe_languages,
    observe_inscriptions, observe_artifacts,
    take_snapshot, accumulate_trail,
    run_stone_age_evolution, evolution_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xC0FFEE_63):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=6, max_agents=20,
        bounds_km=(0.5, 0.5), spawn_radius_m=80.0,
        drive_accel=1500.0, cultures=2,
    )
    return Simulation(cfg)


def _snapshot_signature(snap: EvolutionSnapshot) -> str:
    h = hashlib.sha256()
    h.update(np.asarray(snap.agents.positions, dtype=np.float32).tobytes())
    h.update(np.asarray(snap.agents.cultures, dtype=np.int32).tobytes())
    h.update(int(snap.tick).to_bytes(8, "little"))
    return h.hexdigest()


def main() -> int:
    print("=" * 78)
    print("P63 — Wave 33 stone-age evolution observer smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API.
    ok = all(name in globals() for name in (
        "StoneAgeConfig", "EvolutionSnapshot", "EvolutionHistory",
        "AgentSnapshot", "ClusterObservation",
        "observe_agents", "observe_clusters", "observe_polities",
        "observe_inventions", "observe_buildings", "observe_languages",
        "observe_inscriptions", "observe_artifacts",
        "take_snapshot", "accumulate_trail",
        "run_stone_age_evolution", "evolution_summary",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Step 2 — sim at stone-age starting state.
    sim = _build_sim("p63_stone")
    snap0 = take_snapshot(sim, cluster_radius_m=80.0, cluster_min_pts=2)
    # Pre-bootstrap : positions may be empty (Simulation lazy-inits).
    # Once bootstrap fires (in step()), founders appear.
    sim.step()
    snap1 = take_snapshot(sim, cluster_radius_m=80.0, cluster_min_pts=2)
    ok = (snap1.agents.n_alive >= 1
          and snap1.polities.get("n_polities", 0) == 0
          and snap1.inventions.get("n_artifacts", 0) == 0
          and snap1.buildings.get("n_structures", 0) == 0)
    print(_row("step 2 - stone-age starting state captured",
               ok, f"n_alive={snap1.agents.n_alive} "
                   f"polities={snap1.polities.get('n_polities', 0)} "
                   f"inventions={snap1.inventions.get('n_artifacts', 0)}"))
    if not ok:
        failures += 1

    # Step 3 — snapshots at expected intervals.
    sim2 = _build_sim("p63_run")
    cfg = StoneAgeConfig(n_ticks=30, snapshot_every=10,
                          cluster_radius_m=80.0, cluster_min_pts=2,
                          trail_grid_cell_m=32.0)
    history = run_stone_age_evolution(sim2, cfg)
    # Expected snapshots : initial + at ticks 10, 20, 30.
    expected_count = 1 + (cfg.n_ticks // cfg.snapshot_every)
    ok = len(history.snapshots) == expected_count
    print(_row("step 3 - snapshots at correct intervals",
               ok, f"snapshots={len(history.snapshots)} "
                   f"expected={expected_count}"))
    if not ok:
        failures += 1

    # Step 4 — trail density populated.
    ok = (history.trail_density is not None
          and history.trail_density.sum() > 0)
    print(_row("step 4 - trail density grid populated",
               ok, f"shape={history.trail_density.shape if history.trail_density is not None else None} "
                   f"sum={int(history.trail_density.sum()) if history.trail_density is not None else 0}"))
    if not ok:
        failures += 1

    # Step 5 — at least one snapshot observed clusters of >=2 agents.
    n_with_clusters = sum(1 for s in history.snapshots if s.clusters)
    ok = n_with_clusters >= 1
    print(_row("step 5 - at least one snapshot has clusters",
               ok, f"snapshots_with_clusters={n_with_clusters}/{len(history.snapshots)}"))
    if not ok:
        failures += 1

    # Step 6 — determinism : full re-run with same seed produces same
    # snapshot signatures.
    sim_a = _build_sim("p63_det_a")
    sim_b = _build_sim("p63_det_b")
    hist_a = run_stone_age_evolution(sim_a, cfg)
    hist_b = run_stone_age_evolution(sim_b, cfg)
    sigs_a = [_snapshot_signature(s) for s in hist_a.snapshots]
    sigs_b = [_snapshot_signature(s) for s in hist_b.snapshots]
    ok = (sigs_a == sigs_b and hist_a.n_ticks_run == hist_b.n_ticks_run)
    print(_row("step 6 - determinism inter-runs",
               ok, f"sigs_match={sigs_a == sigs_b} "
                   f"first_sig={sigs_a[0][:16] if sigs_a else 'none'}"))
    if not ok:
        failures += 1

    # Step 7 — observer is read-only : snapshot doesn't mutate sim.
    sim_ro = _build_sim("p63_ro")
    sim_ro.step()  # populate
    n_before = sim_ro.agents.n_active
    pos_before = sim_ro.agents.pos[:n_before, :2].copy()
    alive_before = sim_ro.agents.alive[:n_before].copy()
    # Take 5 snapshots without stepping.
    for _ in range(5):
        snap = take_snapshot(sim_ro, cfg.cluster_radius_m, cfg.cluster_min_pts)
    n_after = sim_ro.agents.n_active
    pos_after = sim_ro.agents.pos[:n_after, :2].copy()
    alive_after = sim_ro.agents.alive[:n_after].copy()
    ok = (n_before == n_after
          and np.array_equal(pos_before, pos_after)
          and np.array_equal(alive_before, alive_after))
    print(_row("step 7 - observer never mutates sim state",
               ok, f"n_active_unchanged={n_before == n_after} "
                   f"positions_unchanged={np.array_equal(pos_before, pos_after)}"))
    if not ok:
        failures += 1

    # Step 8 — summary.
    summary = evolution_summary(history)
    ok = (summary["n_snapshots"] == expected_count
          and summary["n_ticks_run"] == cfg.n_ticks
          and summary["n_alive_first"] >= 1
          and "cluster_count_track" in summary)
    print(_row("step 8 - evolution_summary plausible",
               ok, f"n_snap={summary['n_snapshots']} "
                   f"n_ticks={summary['n_ticks_run']} "
                   f"n_alive_track={summary['n_alive_track']}"))
    if not ok:
        failures += 1

    # Step 9 — snapshots monotone tick progression.
    ticks = [s.tick for s in history.snapshots]
    ok = all(ticks[i] <= ticks[i + 1] for i in range(len(ticks) - 1))
    print(_row("step 9 - snapshot ticks monotone increasing",
               ok, f"ticks={ticks}"))
    if not ok:
        failures += 1

    # Diagnostic dump.
    print(f"\nEvolution summary: {summary}")
    print(f"First snapshot:  tick={history.snapshots[0].tick} "
          f"n_alive={history.snapshots[0].agents.n_alive} "
          f"clusters={len(history.snapshots[0].clusters)}")
    print(f"Last snapshot:   tick={history.snapshots[-1].tick} "
          f"n_alive={history.snapshots[-1].agents.n_alive} "
          f"clusters={len(history.snapshots[-1].clusters)}")
    print(f"Trail density:   shape={history.trail_density.shape} "
          f"max_visits={int(history.trail_density.max())} "
          f"cells_visited={int((history.trail_density > 0).sum())}")

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
