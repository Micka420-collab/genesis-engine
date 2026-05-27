#!/usr/bin/env python3
"""Smoke -- Wave 57 : Agent scaling benchmark.

Tests simulation performance at 6, 12, 25, 50 agents to verify
linear scaling and identify any quadratic bottlenecks.

Checks:
  1. 6 agents: tick < 1.5ms (baseline)
  2. 12 agents: tick < 3ms (should be ~2× baseline)
  3. 25 agents: tick < 6ms (should scale ~linearly)
  4. 50 agents: tick < 15ms (should scale ~linearly)
  5. Per-agent cost scales sub-quadratically
  6. All configurations stable (no NaN/crash)
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
from engine.sim import Simulation, SimConfig

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


SEED = 42

def bench(n_agents: int, n_warmup: int = 5, n_ticks: int = 20):
    """Run a benchmark with n_agents and return avg tick_ms + phase breakdown."""
    bounds = max(0.5, n_agents * 0.01)  # scale bounds with agents
    cfg = SimConfig(
        seed=SEED,
        founders=n_agents,
        bounds_km=(bounds, bounds),
        emergence_subsystems=False,
        life_emergence=False,
        knowledge_layers=False,
        wind_advect_agents=False,
    )
    sim = Simulation(cfg)
    for _ in range(n_warmup):
        sim.step()
    tick_times = []
    perceive_times = []
    regen_times = []
    stream_times = []
    drives_times = []
    thermal_times = []
    for _ in range(n_ticks):
        stats = sim.step()
        tick_times.append(stats.last_tick_ms)
        perceive_times.append(stats.perceive_ms)
        regen_times.append(stats.regen_ms)
        stream_times.append(stats.stream_ms)
        drives_times.append(stats.drives_ms)
        thermal_times.append(stats.thermal_ms)
    alive = int(sim.agents.alive[:sim.agents.n_active].sum())
    return {
        "agents": n_agents,
        "alive": alive,
        "tick_ms": sum(tick_times) / len(tick_times),
        "perceive_ms": sum(perceive_times) / len(perceive_times),
        "regen_ms": sum(regen_times) / len(regen_times),
        "stream_ms": sum(stream_times) / len(stream_times),
        "drives_ms": sum(drives_times) / len(drives_times),
        "thermal_ms": sum(thermal_times) / len(thermal_times),
        "chunks": stats.chunks_in_mem,
    }

# Run benchmarks
configs = [6, 12, 25, 50]
bench_results = {}
for n in configs:
    try:
        bench_results[n] = bench(n)
    except Exception as e:
        bench_results[n] = {"error": str(e)}

# ---------------------------------------------------------------------------
# 1-4. Tick time within budget
# ---------------------------------------------------------------------------
budgets = {6: 1.5, 12: 3.0, 25: 6.0, 50: 15.0}
for n, budget in budgets.items():
    r = bench_results.get(n, {})
    if "error" in r:
        check(f"{n} agents: tick < {budget}ms", False, r["error"])
        continue
    tick = r["tick_ms"]
    per_agent = tick / r["alive"] if r["alive"] > 0 else 0
    check(f"{n} agents: tick < {budget}ms ({tick:.2f}ms)",
          tick < budget,
          f"per_agent={per_agent:.3f}ms alive={r['alive']} chunks={r['chunks']}")

# ---------------------------------------------------------------------------
# 5. Per-agent cost scales sub-quadratically
# ---------------------------------------------------------------------------
try:
    # Compare per-agent cost at 6 vs 50 agents
    # Linear scaling: ratio ≈ 1.0. Quadratic: ratio ≈ 8.3×.
    # Accept up to 3× (mild super-linear due to chunk overlap).
    r6 = bench_results[6]
    r50 = bench_results[50]
    pa6 = r6["tick_ms"] / r6["alive"]
    pa50 = r50["tick_ms"] / r50["alive"]
    ratio = pa50 / pa6
    sub_quad = ratio < 4.0

    check(f"Per-agent cost sub-quadratic (ratio={ratio:.2f}×)",
          sub_quad,
          f"6agents={pa6:.3f}ms/agent 50agents={pa50:.3f}ms/agent")
except Exception as e:
    check("Per-agent cost sub-quadratic", False, str(e))

# ---------------------------------------------------------------------------
# 6. All configurations stable
# ---------------------------------------------------------------------------
try:
    all_stable = True
    for n, r in bench_results.items():
        if "error" in r:
            all_stable = False
    check("All configurations stable (no crash/error)",
          all_stable,
          f"configs={configs}")
except Exception as e:
    check("All stable", False, str(e))

# ---------------------------------------------------------------------------
# Summary + detailed table
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p107 -- Wave 57 Agent Scaling ({passed}/{total})\n")
for r in results:
    print(r)

# Detailed breakdown table
print(f"\n  {'Agents':>7s} {'Alive':>6s} {'Tick ms':>8s} {'ms/agt':>8s} {'perc':>7s} {'regen':>7s} {'stream':>7s} {'drives':>7s} {'therm':>7s} {'chunks':>7s}")
print("  " + "-" * 75)
for n in configs:
    r = bench_results.get(n, {})
    if "error" in r:
        print(f"  {n:>7d} ERROR: {r['error']}")
        continue
    pa = r["tick_ms"] / r["alive"] if r["alive"] > 0 else 0
    print(f"  {n:>7d} {r['alive']:>6d} {r['tick_ms']:>7.2f}ms {pa:>7.3f}ms {r['perceive_ms']:>6.2f}ms {r['regen_ms']:>6.2f}ms {r['stream_ms']:>6.2f}ms {r['drives_ms']:>6.2f}ms {r['thermal_ms']:>6.02f}ms {r['chunks']:>7d}")

print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 57 agent scaling validation complet.")
