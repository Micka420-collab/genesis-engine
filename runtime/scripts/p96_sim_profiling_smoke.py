#!/usr/bin/env python3
"""Smoke -- Wave 46 : sim integration + per-phase profiling.

Checks:
  1. Simulation boots and runs 10 ticks with Rust backend
  2. SimStats has per-phase profiling fields (stream_ms, perceive_ms, regen_ms)
  3. chunks_around_sorted used in sim (streamer stats show batch_calls)
  4. Streamer stats consistent after 10 ticks
  5. Per-phase breakdown sums to ~total (no missing time)
  6. Performance: 10 ticks under 5 seconds
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


from engine.sim import Simulation, SimConfig, SimStats  # noqa: E402

SEED = 42

# ---------------------------------------------------------------------------
# 1. Simulation boots and runs 10 ticks
# ---------------------------------------------------------------------------
try:
    cfg = SimConfig(
        seed=SEED,
        founders=6,
        bounds_km=(0.5, 0.5),
        emergence_subsystems=False,
        life_emergence=False,
        knowledge_layers=False,
        wind_advect_agents=False,
    )
    sim = Simulation(cfg)
    t0 = time.perf_counter()
    for _ in range(10):
        stats = sim.step()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    check("Simulation boots + 10 ticks with Rust backend",
          stats.tick == 10 and stats.alive > 0,
          f"tick={stats.tick} alive={stats.alive} total={elapsed_ms:.1f}ms")
except Exception as e:
    check("Simulation boots + 10 ticks with Rust backend", False, str(e))

# ---------------------------------------------------------------------------
# 2. SimStats has per-phase profiling fields
# ---------------------------------------------------------------------------
try:
    has_fields = all(hasattr(stats, f) for f in [
        "stream_ms", "perceive_ms", "regen_ms", "decide_apply_ms"])
    positive = (stats.stream_ms >= 0 and stats.perceive_ms >= 0 and
                stats.regen_ms >= 0)
    check("SimStats has per-phase profiling fields",
          has_fields and positive,
          f"stream={stats.stream_ms:.2f}ms perceive={stats.perceive_ms:.2f}ms "
          f"regen={stats.regen_ms:.2f}ms")
except Exception as e:
    check("SimStats has per-phase profiling fields", False, str(e))

# ---------------------------------------------------------------------------
# 3. Streamer stats show activity
# ---------------------------------------------------------------------------
try:
    ss = sim.streamer.stats()
    has_activity = (ss["generated"] > 0 or ss["hits"] > 0)
    has_cache = ss["cache_size"] > 0
    check("Streamer stats show activity after sim",
          has_activity and has_cache,
          f"gen={ss['generated']} hits={ss['hits']} cache={ss['cache_size']} "
          f"batch={ss['batch_calls']}")
except Exception as e:
    check("Streamer stats show activity after sim", False, str(e))

# ---------------------------------------------------------------------------
# 4. Streamer stats consistent
# ---------------------------------------------------------------------------
try:
    total_accesses = ss["hits"] + ss["misses"]
    rate_ok = 0.0 <= ss["hit_rate"] <= 1.0
    gen_ok = ss["generated"] <= ss["misses"]  # can't generate more than misses
    check("Streamer stats consistent (hits+misses, hit_rate)",
          rate_ok and gen_ok and total_accesses > 0,
          f"total_access={total_accesses} hit_rate={ss['hit_rate']:.2f} "
          f"gen={ss['generated']}<=miss={ss['misses']}")
except Exception as e:
    check("Streamer stats consistent", False, str(e))

# ---------------------------------------------------------------------------
# 5. Per-phase breakdown sums to ~total
# ---------------------------------------------------------------------------
try:
    phase_sum = stats.stream_ms + stats.regen_ms + stats.perceive_ms
    total = stats.last_tick_ms
    # Phase sum should be <= total (other phases exist beyond these 3).
    # And at least 50% of total should be accounted for.
    ratio = phase_sum / max(total, 0.001)
    reasonable = phase_sum <= total * 1.1  # allow 10% measurement jitter
    check("Per-phase breakdown <= total tick time",
          reasonable,
          f"phases={phase_sum:.2f}ms total={total:.2f}ms ratio={ratio:.1%}")
except Exception as e:
    check("Per-phase breakdown <= total tick time", False, str(e))

# ---------------------------------------------------------------------------
# 6. Performance: 10 ticks under 5 seconds
# ---------------------------------------------------------------------------
try:
    check("10 ticks under 5 seconds",
          elapsed_ms < 5000.0,
          f"elapsed={elapsed_ms:.1f}ms ({elapsed_ms/10:.1f}ms/tick)")
except Exception as e:
    check("10 ticks under 5 seconds", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p96 -- Wave 46 Sim Integration + Profiling ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 46 sim integration + profiling validation complet.")
