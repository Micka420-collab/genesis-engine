"""P8 smoke — trails affect walkability live (Sprint A2).

Build a Lausanne world with realism, run 500 ticks. Verify that the mean
walkability AFTER trail accumulation is greater than the BASE walkability
(trails added bonus to frequented paths, §16 emergent urbanism precursor).
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

import numpy as np

from engine.world_builder import WorldBuilder


def _mean_walk_stats(sim):
    lf_dict = getattr(sim, "_lift_fields", {}) or {}
    if not lf_dict:
        return 0.0, 0.0, 0
    walk_sum = 0.0
    base_sum = 0.0
    cells = 0
    for lf in lf_dict.values():
        if lf.walkability is None:
            continue
        walk_sum += float(lf.walkability.sum())
        if lf.base_walkability is not None:
            base_sum += float(lf.base_walkability.sum())
        else:
            base_sum += float(lf.walkability.sum())
        cells += int(lf.walkability.size)
    if cells == 0:
        return 0.0, 0.0, 0
    return walk_sum / cells, base_sum / cells, cells


def main() -> int:
    out_path = os.path.join(ROOT, "journals", "p8_trails_smoke.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    world = (WorldBuilder("lausanne_p8")
             .anchor(46.510, 6.633)
             .size_km(2.0)
             .founders(20)
             .with_realism())
    w = world.build()
    sim = w.sim

    # Capture baseline AFTER first step (lift fields are lazy-init).
    sim.step()
    initial_mean, initial_base, cells_before = _mean_walk_stats(sim)

    t0 = time.monotonic()
    errors = []
    for t in range(499):
        try:
            sim.step()
        except Exception as exc:
            errors.append({
                "tick": sim.tick, "exc": type(exc).__name__, "msg": str(exc),
                "trace": traceback.format_exc().splitlines()[-6:],
            })
            break
    elapsed = time.monotonic() - t0

    final_mean, final_base, cells_after = _mean_walk_stats(sim)

    # Trail stats
    trails = getattr(sim, "_realism_trails", {}) or {}
    max_intensity = 0.0
    active_cells = 0
    for f in trails.values():
        max_intensity = max(max_intensity, float(f.intensity.max(initial=0.0)))
        active_cells += int((f.intensity > 0.1).sum())

    delta = final_mean - final_base
    summary = {
        "ticks": sim.tick,
        "elapsed_s": round(elapsed, 3),
        "agents_alive": int(sim.agents.alive[:sim.agents.n_active].sum()),
        "chunks_lift": len(sim._lift_fields),
        "chunks_trails": len(trails),
        "initial_mean_walkability": round(initial_mean, 6),
        "initial_base_walkability": round(initial_base, 6),
        "final_mean_walkability": round(final_mean, 6),
        "final_base_walkability": round(final_base, 6),
        "walk_minus_base": round(delta, 6),
        "max_trail_intensity": round(max_intensity, 4),
        "well_trodden_cells": active_cells,
        "errors": errors,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

    if errors:
        print("\n[X] P8 TRAILS SMOKE FAILED — exceptions")
        return 2
    if cells_after < 1:
        print("\n[X] P8 TRAILS SMOKE FAILED — no lift fields")
        return 3
    if final_mean <= initial_mean and delta <= 1e-6:
        print("\n[X] P8 TRAILS SMOKE FAILED — walkability did not grow"
              f" (initial={initial_mean:.6f}, final={final_mean:.6f},"
              f" delta_vs_base={delta:.6f})")
        return 4
    print("\n[OK] P8 TRAILS SMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
