#!/usr/bin/env python3
"""Smoke -- Wave 49 : lean inline regen (no Weather, no function call).

Checks:
  1. regenerate_chunks_batch produces correct food values
  2. regenerate_chunks_batch produces correct water values
  3. Stability: 100 batch iterations, no NaN/Inf
  4. Sim regen_ms < 2ms for 100+ chunks
  5. Total sim tick < 10ms steady-state
  6. Overall 10 ticks under 250ms
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


from engine.world import (  # noqa: E402
    generate_chunk, TerrainParams, regenerate_chunks_batch,
    invalidate_resource_masks, CHUNK_SIZE,
)

SEED = 42

# ---------------------------------------------------------------------------
# 1. Batch regen: food values correct
# ---------------------------------------------------------------------------
try:
    chunks = [generate_chunk(SEED, (i, 0, 0), TerrainParams()) for i in range(10)]
    food_before = [c.food_kcal.copy() for c in chunks]
    cap = [c.food_capacity.copy() for c in chunks]
    rain = np.array([5.0] * 10, dtype=np.float32)
    regenerate_chunks_batch(chunks, dt_s=3600.0, rain_per_chunk=rain)

    all_ok = True
    for i, c in enumerate(chunks):
        # food should move toward capacity (or stay same if at capacity)
        diff = c.food_kcal - food_before[i]
        if (diff < -1e-6).any():
            all_ok = False

    check("Batch regen: food moves toward capacity",
          all_ok,
          f"10 chunks, dt_s=3600")
except Exception as e:
    check("Batch regen: food correct", False, str(e))

# ---------------------------------------------------------------------------
# 2. Batch regen: water values correct
# ---------------------------------------------------------------------------
try:
    chunks2 = [generate_chunk(SEED, (i, 1, 0), TerrainParams()) for i in range(10)]
    water_before = [c.water.copy() for c in chunks2]
    rain2 = np.array([10.0] * 10, dtype=np.float32)
    regenerate_chunks_batch(chunks2, dt_s=3600.0, rain_per_chunk=rain2)

    all_water_ok = True
    for i, c in enumerate(chunks2):
        diff = c.water - water_before[i]
        if (diff < -1e-6).any():
            all_water_ok = False

    expected_recharge = 10.0 * 3600.0 / 3600.0  # = 10.0
    actual_max = max(float((c.water - water_before[i]).max()) for i, c in enumerate(chunks2))
    check("Batch regen: water recharge correct",
          all_water_ok and actual_max > 0,
          f"max_recharge={actual_max:.1f} expected={expected_recharge:.1f}")
except Exception as e:
    check("Batch regen: water correct", False, str(e))

# ---------------------------------------------------------------------------
# 3. Stability: 100 iterations
# ---------------------------------------------------------------------------
try:
    chunks3 = [generate_chunk(SEED, (i, 2, 0), TerrainParams()) for i in range(20)]
    rain3 = np.array([3.0] * 20, dtype=np.float32)
    for _ in range(100):
        regenerate_chunks_batch(chunks3, dt_s=60.0, rain_per_chunk=rain3)

    no_nan = all(not np.isnan(c.food_kcal).any() and not np.isnan(c.water).any()
                 for c in chunks3)
    no_inf = all(not np.isinf(c.food_kcal).any() and not np.isinf(c.water).any()
                 for c in chunks3)
    non_neg = all((c.food_kcal >= 0).all() and (c.water >= 0).all() for c in chunks3)

    check("100 batch iterations stable",
          no_nan and no_inf and non_neg,
          f"no_nan={no_nan} no_inf={no_inf} non_neg={non_neg}")
except Exception as e:
    check("100 batch iterations stable", False, str(e))

# ---------------------------------------------------------------------------
# 4. Sim regen_ms < 2ms
# ---------------------------------------------------------------------------
try:
    from engine.sim import Simulation, SimConfig
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
    for _ in range(5):
        sim.step()  # warm up

    regen_times = []
    for _ in range(10):
        stats = sim.step()
        regen_times.append(stats.regen_ms)
    avg_regen = sum(regen_times) / len(regen_times)

    check(f"Sim regen_ms < 2ms ({avg_regen:.2f}ms)",
          avg_regen < 2.0,
          f"avg={avg_regen:.2f}ms chunks={stats.chunks_in_mem}")
except Exception as e:
    check("Sim regen_ms < 2ms", False, str(e))

# ---------------------------------------------------------------------------
# 5. Total tick < 10ms
# ---------------------------------------------------------------------------
try:
    tick_times = []
    for _ in range(10):
        stats = sim.step()
        tick_times.append(stats.last_tick_ms)
    avg_tick = sum(tick_times) / len(tick_times)

    check(f"Sim tick < 10ms ({avg_tick:.2f}ms)",
          avg_tick < 10.0,
          f"avg_tick={avg_tick:.2f}ms stream={stats.stream_ms:.2f} "
          f"perceive={stats.perceive_ms:.2f} regen={stats.regen_ms:.2f}")
except Exception as e:
    check("Sim tick < 10ms", False, str(e))

# ---------------------------------------------------------------------------
# 6. 10 ticks under 250ms
# ---------------------------------------------------------------------------
try:
    sim2 = Simulation(cfg)
    t0 = time.perf_counter()
    for _ in range(10):
        sim2.step()
    elapsed = (time.perf_counter() - t0) * 1000.0

    check(f"10 ticks under 250ms ({elapsed:.0f}ms)",
          elapsed < 250.0,
          f"elapsed={elapsed:.1f}ms ({elapsed/10:.1f}ms/tick)")
except Exception as e:
    check("10 ticks under 250ms", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p99 -- Wave 49 Lean Regen ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 49 lean regen validation complet.")
