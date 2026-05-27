#!/usr/bin/env python3
"""Micro-profiling script — uses actual sim.step() + internal probes.

Wave 53: fine-grained breakdown including drives, thermal, post phases.
"""
from __future__ import annotations
import sys, time, io, math
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import numpy as np
from engine.sim import Simulation, SimConfig

cfg = SimConfig(seed=42, founders=6, bounds_km=(0.5, 0.5),
                emergence_subsystems=False, life_emergence=False,
                knowledge_layers=False, wind_advect_agents=False)
sim = Simulation(cfg)
for _ in range(5):
    sim.step()

# Collect timing from SimStats — all phases now instrumented.
results = []
for _ in range(30):
    stats = sim.step()
    # "other" = total - (stream + regen + drives + perceive + thermal + post)
    known = (stats.stream_ms + stats.regen_ms + stats.drives_ms
             + stats.perceive_ms + stats.thermal_ms + stats.post_ms)
    other_ms = stats.last_tick_ms - known
    results.append({
        "stream": stats.stream_ms,
        "regen": stats.regen_ms,
        "drives": stats.drives_ms,
        "perceive+decide": stats.perceive_ms,
        "thermal": stats.thermal_ms,
        "post": stats.post_ms,
        "other": other_ms,
        "total": stats.last_tick_ms,
    })

phases = ["stream", "regen", "drives", "perceive+decide", "thermal", "post", "other", "total"]

print(f"\nMicro-profile (30 ticks avg via sim.step()):")
print(f"  {'Phase':<20s} {'Avg ms':>8s} {'Min ms':>8s} {'Max ms':>8s} {'% tick':>8s}")
print("  " + "-" * 58)
total_avg = sum(r["total"] for r in results) / len(results)
for k in phases:
    vals = [r[k] for r in results]
    avg = sum(vals) / len(vals)
    mn = min(vals)
    mx = max(vals)
    pct = avg / total_avg * 100 if k != "total" else 100.0
    print(f"  {k:<20s} {avg:>7.3f}ms {mn:>7.3f}ms {mx:>7.3f}ms {pct:>6.1f}%")

print(f"\n  chunks_in_mem={stats.chunks_in_mem}  alive={stats.alive}")
print(f"  Speedup from Wave 42 baseline (49.3ms -> {total_avg:.2f}ms/tick)")
print(f"  = {49.3/total_avg:.1f}x total speedup\n")

# Per-agent breakdown
n_alive = stats.alive
if n_alive > 0:
    pa = total_avg / n_alive
    print(f"  Per-agent: {pa:.3f}ms/agent ({n_alive} alive)")
    for k in phases[:-1]:  # skip total
        vals = [r[k] for r in results]
        avg = sum(vals) / len(vals)
        print(f"    {k:<20s} {avg/n_alive:.3f}ms/agent")
