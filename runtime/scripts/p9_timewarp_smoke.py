"""P9 smoke — engine.timewarp (Sprint A3).

Build a Lausanne world (1.5km bounds) and run three 200-tick segments at
realtime / x10 / x100. Measure wall-clock per segment. Pass criteria:

  * x10  wall-clock  ≥ 3×   faster than realtime
  * x100 wall-clock  ≥ 10×  faster than realtime
  * no exceptions
  * sim.tick advances by 200 every segment

UTF-8 stdout, errors collected, exit-code non-zero on failure.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.world_builder import WorldBuilder  # noqa: E402


SEGMENTS = (
    ("realtime", 200),
    ("x10",      200),
    ("x100",     200),
)


def _fresh_world():
    return (WorldBuilder("p9_timewarp")
            .anchor(lat=46.510, lon=6.633)
            .size_km(1.5)
            .founders(20)
            .cultures(2)
            .max_agents(200)
            .drive_accel(1500.0)
            .seed(0xA3_71_E_5A & 0xFFFFFFFF_FFFFFFFF)
            .with_l1_earth(True)
            .with_l2_lift(True)
            .with_realism(seasons={"year": 2026, "day_of_year": 120})
            .build())


def main() -> int:
    out_path = os.path.join(ROOT, "journals", "p9_timewarp_smoke.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    results = []
    errors = []

    # Each mode runs in its own fresh world so wall-clock comparisons are
    # population-independent (sim cost is dominated by per-agent loop, so
    # running x10/x100 *after* realtime would otherwise penalise them with
    # the population they grew during the realtime segment).
    for mode, n_ticks in SEGMENTS:
        try:
            world = _fresh_world()
        except Exception as exc:
            errors.append({"phase": "build", "mode": mode,
                           "exc": type(exc).__name__, "msg": str(exc)})
            break

        # Warm-up tick so streamer/realism lazy-init isn't counted.
        try:
            world.step()
        except Exception as exc:
            errors.append({"phase": "warmup", "mode": mode,
                           "exc": type(exc).__name__, "msg": str(exc)})
            break

        try:
            status = world.set_time_warp(mode)
        except Exception as exc:
            errors.append({"phase": "set_mode", "mode": mode,
                           "exc": type(exc).__name__, "msg": str(exc)})
            break
        tick_before = int(world.tick)
        t0 = time.perf_counter()
        for _ in range(n_ticks):
            try:
                world.step()
            except Exception as exc:
                errors.append({"phase": "step", "mode": mode,
                               "exc": type(exc).__name__,
                               "msg": str(exc),
                               "trace": traceback.format_exc().splitlines()[-6:]})
                break
        elapsed = time.perf_counter() - t0
        tick_after = int(world.tick)
        results.append({
            "mode":       mode,
            "n_ticks":    n_ticks,
            "wall_s":     round(elapsed, 4),
            "tick_delta": tick_after - tick_before,
            "n_alive":    int(world.n_alive),
            "status":     status,
        })
        if errors:
            break

    # ---- pass criteria --------------------------------------------------
    by_mode = {r["mode"]: r for r in results}
    base = by_mode.get("realtime", {}).get("wall_s")
    x10  = by_mode.get("x10",      {}).get("wall_s")
    x100 = by_mode.get("x100",     {}).get("wall_s")

    speedup_x10  = (base / x10)  if (base and x10  and x10  > 0) else 0.0
    speedup_x100 = (base / x100) if (base and x100 and x100 > 0) else 0.0

    summary = {
        "segments": results,
        "speedup_x10":  round(speedup_x10,  2),
        "speedup_x100": round(speedup_x100, 2),
        "errors": errors,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

    if errors:
        print("\n[X] P9 TIMEWARP SMOKE FAILED — exception during run")
        return 2

    failed = False
    if any(r["tick_delta"] != r["n_ticks"] for r in results):
        print("\n[X] P9 TIMEWARP SMOKE FAILED — tick_delta mismatch")
        failed = True
    if speedup_x10 < 3.0:
        print(f"\n[X] P9 TIMEWARP SMOKE FAILED — x10 only {speedup_x10:.2f}× "
              f"(need ≥3×)")
        failed = True
    if speedup_x100 < 10.0:
        print(f"\n[X] P9 TIMEWARP SMOKE FAILED — x100 only {speedup_x100:.2f}× "
              f"(need ≥10×)")
        failed = True
    if failed:
        return 3

    print(f"\n[OK] P9 TIMEWARP SMOKE PASSED  "
          f"(x10={speedup_x10:.2f}×, x100={speedup_x100:.2f}×)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
