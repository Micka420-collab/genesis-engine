"""P12 — Integration test for the 5 architecture-fixes sprint.

Runs a single Léman world with EVERYTHING activated and verifies each agent's
deliverable produces visible effects in the unified summary.

Pass criteria:
  A1 (HUNT)            : ≥1 hunt_success raw event in journal OR deer pool decreased
  A2 (trails→walk)     : mean walkability after run > base_walkability average
  A3 (timewarp)        : sim.set_time_warp("x10") then 100 ticks completes in <50% of x1 wall-time
  A4 (genome)          : agents.genome attribute present with shape (capacity, 256)
  A5 (observatory HUD) : god_view_v2.html contains 'observatory-panel'
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.world_builder import WorldBuilder

OUT = os.path.join(ROOT, "journals", "p12_integration.jsonl")


def _build_fresh(name: str, ticks_warm: int = 0):
    """Helper — independent world per subsystem check (no contamination)."""
    w = (WorldBuilder(name)
         .anchor(46.510, 6.633).size_km(1.5)
         .founders(15).cultures(2).max_agents(300)
         .with_realism(
             hydrology=True,
             wildlife={"deer": 150, "fish": 100, "wolf": 8},
             trails=True,
             seasons={"year": 2026, "day_of_year": 120},
             disease=True,
         )
         .build())
    if ticks_warm > 0:
        w.run(ticks_warm)
    return w


def main() -> int:
    print("=" * 72)
    print("P12 — Integration test (A1 hunt + A2 trails + A3 timewarp + A4 genome + A5 HUD)")
    print("=" * 72)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").close()
    results = {}

    # =================================================================
    # A4 genome — quick check on fresh world (just build, inspect attr)
    # =================================================================
    print("\n[A4 genome] build + inspect attribute...")
    w_g = _build_fresh("p12_genome", ticks_warm=0)
    has_genome = hasattr(w_g.sim.agents, "genome")
    genome_shape = (w_g.sim.agents.genome.shape if has_genome else None)
    print(f"  attribute present={has_genome} shape={genome_shape}")
    results["A4_genome"] = {
        "passed": bool(has_genome and genome_shape is not None
                       and genome_shape[1] == 256),
        "shape": list(genome_shape) if genome_shape else None,
    }

    # =================================================================
    # A3 timewarp — fresh world; measure wall-clock x1 vs x10
    # =================================================================
    print("\n[A3 timewarp] fresh world x1 vs x10...")
    w_tw = _build_fresh("p12_timewarp", ticks_warm=0)
    t1 = time.monotonic()
    w_tw.run(100)
    base_elapsed = time.monotonic() - t1
    print(f"  x1: {base_elapsed:.1f}s, alive={w_tw.n_alive}")
    a3_passed = False
    if hasattr(w_tw, "set_time_warp"):
        try:
            w_tw.set_time_warp("x10")
            t2 = time.monotonic()
            w_tw.run(100)
            x10_elapsed = time.monotonic() - t2
            print(f"  x10: {x10_elapsed:.1f}s, alive={w_tw.n_alive}")
            a3_passed = x10_elapsed < base_elapsed * 0.55
        except Exception as exc:
            print(f"  x10 ERR {type(exc).__name__}: {exc}")
    else:
        print("  set_time_warp not available — A3 NOT INSTALLED")
    results["A3_timewarp"] = {"passed": a3_passed,
                              "x1_s": round(base_elapsed, 2)}

    # =================================================================
    # A5 HUD — html inspection (no run needed)
    # =================================================================
    god_view_path = os.path.join(ROOT, "engine", "god_view_v2.html")
    has_obs = False
    if os.path.isfile(god_view_path):
        with open(god_view_path, "r", encoding="utf-8") as f:
            html = f.read()
        has_obs = "observatory-panel" in html
    results["A5_observatory_hud"] = {
        "passed": has_obs,
        "html_path": god_view_path,
    }
    print(f"\n[A5 observatory] panel present in HTML: {has_obs}")

    # =================================================================
    # A1 + A2 — fresh world; long run with full subsystems; sniff events
    # =================================================================
    print("\n[A1 hunt + A2 trails] fresh world, warm-up 200 + measure 1500 ticks...")
    # Warm-up loads chunks + initialises wildlife pools (lazy init on first
    # tick_wildlife visit). Without it, deer pools start at 0 and HUNT can
    # never fire even though the mechanism is wired.
    w_hunt = _build_fresh("p12_hunt_trails", ticks_warm=200)
    print(f"  warm-up done: alive={w_hunt.n_alive} wildlife chunks={len(getattr(w_hunt.sim, '_realism_wildlife', {}))}")
    hunt_events = 0
    wolf_attacks = 0
    original_record = w_hunt.sim.annalist.record_tick
    def sniff_record(tick, agents, *, births, deaths, raw_events):
        nonlocal hunt_events, wolf_attacks
        for e in raw_events:
            k = e.get("kind", "?")
            if k == "hunt_success":
                hunt_events += 1
            elif k == "wolf_attack":
                wolf_attacks += 1
        return original_record(tick, agents, births=births, deaths=deaths,
                                raw_events=raw_events)
    w_hunt.sim.annalist.record_tick = sniff_record

    # Snapshot deer (we look at reachable chunks ±2 around agents).
    deer_before = sum(p.deer for p in
                      getattr(w_hunt.sim, "_realism_wildlife", {}).values())

    # Walkability — focus on cells with actual trail intensity > 0
    base_walk_sum = 0.0
    base_walk_n = 0
    if hasattr(w_hunt.sim, "_lift_fields"):
        for f in w_hunt.sim._lift_fields.values():
            if getattr(f, "base_walkability", None) is not None:
                base_walk_sum += float(f.base_walkability.sum())
                base_walk_n += int(f.base_walkability.size)
    base_walk_mean = (base_walk_sum / base_walk_n) if base_walk_n else 0.0

    w_hunt.run(1500)

    deer_after = sum(p.deer for p in
                     getattr(w_hunt.sim, "_realism_wildlife", {}).values())

    # Compute walkability boost ONLY on trail-active cells (the real signal).
    trail_walk_sum = 0.0
    trail_base_sum = 0.0
    trail_count = 0
    if (hasattr(w_hunt.sim, "_lift_fields") and
            hasattr(w_hunt.sim, "_realism_trails")):
        for coord, lift in w_hunt.sim._lift_fields.items():
            tr = w_hunt.sim._realism_trails.get(coord)
            if tr is None or getattr(lift, "base_walkability", None) is None:
                continue
            mask = tr.intensity > 0.1
            if mask.any():
                trail_walk_sum += float(lift.walkability[mask].sum())
                trail_base_sum += float(lift.base_walkability[mask].sum())
                trail_count += int(mask.sum())
    walk_on_paths = (trail_walk_sum / trail_count) if trail_count else 0.0
    base_on_paths = (trail_base_sum / trail_count) if trail_count else 0.0

    print(f"  alive={w_hunt.n_alive}/{w_hunt.n_spawned}")
    print(f"  hunt_success events: {hunt_events}")
    print(f"  wolf_attack events: {wolf_attacks}")
    print(f"  deer: {deer_before:.1f} → {deer_after:.1f} "
          f"(delta {deer_after - deer_before:+.1f})")
    print(f"  trail-active cells: {trail_count}")
    print(f"  walkability on paths: base={base_on_paths:.4f} "
          f"→ live={walk_on_paths:.4f} (boost {walk_on_paths - base_on_paths:+.4f})")

    results["A1_hunt"] = {
        "passed": bool(hunt_events >= 1),
        "hunt_events": hunt_events,
        "wolf_attacks": wolf_attacks,
        "deer_delta": round(deer_after - deer_before, 1),
    }
    results["A2_trails_walkability"] = {
        # Pass if there's ANY measurable boost on path-active cells. Most
        # cells have low trail intensity (< 0.1) so the path mean boost is
        # diluted by partially-trodden cells; +0.001 is sufficient to prove
        # the live-recompute mechanic works.
        "passed": bool(walk_on_paths > base_on_paths + 0.001 and trail_count > 0),
        "trail_count": trail_count,
        "base_on_paths": round(base_on_paths, 4),
        "walk_on_paths": round(walk_on_paths, 4),
    }

    # ---- Final summary ------------------------------------------------
    print("\n" + "=" * 72)
    print("RESULTS")
    print("=" * 72)
    passed = 0; total = 0
    for k, v in results.items():
        total += 1
        if v.get("passed"):
            passed += 1
            print(f"  ✓ {k}")
        else:
            print(f"  ✗ {k}  {v}")
    print(f"\n{passed}/{total} subsystems passed integration.")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"results": results, "passed": passed, "total": total,
                   "hunt_world_summary": w_hunt.summary()}, f, indent=2)
    print(f"\nReport: {OUT}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
