#!/usr/bin/env python3
"""Smoke -- Wave 62 : Agent scaling benchmark.

Tests sim tick performance at increasing agent counts.
  1. 6 agents stable, tick < 2ms
  2. 50 agents stable, tick < 5ms
  3. 100 agents stable, tick < 8ms
  4. 200 agents stable, tick < 20ms
  5. Scaling is sub-quadratic (200-agent tick < 4× 100-agent tick)
  6. Profile breakdown at peak count
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from engine.sim import Simulation, SimConfig  # noqa: E402

results: list[str] = []
passed = failed = 0


def _row(label: str, ok: bool, detail: str = "") -> str:
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    results.append(_row(label, ok, detail))
    if ok:
        passed += 1
    else:
        failed += 1


def profile_agents(n_agents, tick_limit_ms, warmup=10, measure=20):
    """Run sim at n_agents, return (ok, avg_tick_ms, detail, stats_dict)."""
    cfg = SimConfig(seed=42, founders=n_agents, bounds_km=(1.0, 1.0),
                    emergence_subsystems=False, life_emergence=False,
                    knowledge_layers=False, wind_advect_agents=False)
    sim = Simulation(cfg)
    try:
        for _ in range(warmup):
            sim.step()
    except Exception as e:
        return False, 0.0, str(e)[:200], {}

    tick_ms = []
    stats_dict = {}
    for _ in range(measure):
        st = sim.step()
        t = st.stream_ms + st.regen_ms + st.drives_ms + st.perceive_ms + st.thermal_ms + st.post_ms
        tick_ms.append(t)
        for k in ('stream_ms', 'regen_ms', 'drives_ms', 'perceive_ms', 'thermal_ms', 'post_ms'):
            stats_dict.setdefault(k, []).append(getattr(st, k))

    avg_tick = sum(tick_ms) / len(tick_ms)
    alive = int(sim.agents.alive[:sim.agents.n_active].sum())
    detail = "tick=%d alive=%d avg=%.2fms" % (sim.tick, alive, avg_tick)
    ok = avg_tick < tick_limit_ms
    avg_stats = {k: sum(v)/len(v) for k, v in stats_dict.items()}
    return ok, avg_tick, detail, avg_stats


# ---------------------------------------------------------------------------
# 1-4: Stability + tick budget at each scale
# ---------------------------------------------------------------------------
benchmarks = {}
for n, limit in [(6, 2.0), (50, 5.0), (100, 8.0), (200, 20.0)]:
    ok, avg, detail, stats = profile_agents(n, limit)
    benchmarks[n] = (avg, stats)
    check("%d agents stable, tick < %.0fms (avg=%.2fms)" % (n, limit, avg), ok, detail)

# ---------------------------------------------------------------------------
# 5: Sub-quadratic scaling check
# ---------------------------------------------------------------------------
if 100 in benchmarks and 200 in benchmarks:
    t100 = benchmarks[100][0]
    t200 = benchmarks[200][0]
    ratio = t200 / max(t100, 0.001)
    # Sub-quadratic: 200/100 = 2× agents, if O(N²) would be 4×.
    # We expect < 3.5× with rayon parallelism.
    sub_quad = ratio < 3.5
    check("Scaling sub-quadratic (200/100 ratio = %.2f < 3.5)" % ratio,
          sub_quad,
          "t100=%.2fms t200=%.2fms" % (t100, t200))
else:
    check("Scaling sub-quadratic", False, "missing benchmark data")

# ---------------------------------------------------------------------------
# 6: Profile breakdown at 200 agents
# ---------------------------------------------------------------------------
if 200 in benchmarks:
    _, stats200 = benchmarks[200]
    total = sum(stats200.values())
    parts = []
    for k in ('stream_ms', 'regen_ms', 'drives_ms', 'perceive_ms', 'thermal_ms', 'post_ms'):
        label = k.replace('_ms', '')
        v = stats200[k]
        parts.append("%s=%.2fms(%.0f%%)" % (label, v, 100*v/total if total > 0 else 0))
    profile_ok = total > 0
    check("Profile at 200 agents", profile_ok, " ".join(parts))
else:
    check("Profile at 200 agents", False, "missing data")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print("\nSmoke p112 -- Wave 62 Scaling Benchmark (%d/%d)\n" % (passed, total))
for r in results:
    print(r)
print()
if failed:
    print("ECHEC : %d check(s) rate(s)." % failed)
    sys.exit(1)
print("OK -- Wave 62 scaling benchmark complet.")
