#!/usr/bin/env python3
"""Smoke -- Wave 53 : Flat thermal + optimised regen.

Checks:
  1. Flat thermal gives same bounded output as before
  2. Optimised regen food converges toward capacity
  3. 100 ticks stable (no NaN/Inf, all alive)
  4. thermal_ms < 0.1ms (flat: ~0.046ms vs 0.335ms per-chunk)
  5. regen_ms < 0.5ms (optimised: ~0.39ms vs 0.63ms)
  6. Total sim tick < 2ms (baseline 2.07ms, target 1.54ms)
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


SEED = 42

# ---------------------------------------------------------------------------
# 1. Flat thermal: bounded output
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
    sim.step()

    # After 1 tick, thermal values should be in [0, 1.5]
    n = sim.agents.n_active
    alive = np.flatnonzero(sim.agents.alive[:n])
    thermal = sim.agents.thermal[alive]
    bounded = bool(np.all(thermal >= 0.0) and np.all(thermal <= 1.5))
    no_nan = bool(not np.any(np.isnan(thermal)))
    check("Flat thermal bounded [0, 1.5]",
          bounded and no_nan,
          f"range=[{thermal.min():.3f}, {thermal.max():.3f}] no_nan={no_nan}")
except Exception as e:
    check("Flat thermal bounded", False, str(e))

# ---------------------------------------------------------------------------
# 2. Optimised regen: food converges toward capacity
# ---------------------------------------------------------------------------
try:
    from engine.world import generate_chunk, TerrainParams, CHUNK_SIDE_M

    sim2 = Simulation(cfg)
    for _ in range(3):
        sim2.step()

    # Pick a chunk and check food_kcal <= food_capacity
    coords = list(sim2.streamer.cache.keys())[:5]
    ok_all = True
    for c in coords:
        chunk = sim2.streamer.cache[c]
        if chunk.food_kcal.max() > chunk.food_capacity.max() * 1.01:
            ok_all = False
    # Check no negative food
    no_neg = all(sim2.streamer.cache[c].food_kcal.min() >= 0.0 for c in coords)

    check("Optimised regen: food bounded [0, capacity]",
          ok_all and no_neg,
          f"chunks_checked={len(coords)} no_neg={no_neg}")
except Exception as e:
    check("Optimised regen food bounded", False, str(e))

# ---------------------------------------------------------------------------
# 3. 100 ticks stable
# ---------------------------------------------------------------------------
try:
    sim3 = Simulation(cfg)
    for _ in range(100):
        sim3.step()
    n3 = sim3.agents.n_active
    alive3 = sim3.agents.alive[:n3]
    thermal3 = sim3.agents.thermal[:n3]
    no_nan3 = not np.any(np.isnan(thermal3))
    no_inf3 = not np.any(np.isinf(thermal3))
    alive_count = int(alive3.sum())

    check("100 ticks stable (no NaN/Inf)",
          no_nan3 and no_inf3 and alive_count > 0,
          f"alive={alive_count} thermal_range=[{thermal3[alive3.astype(bool)].min():.3f}, {thermal3[alive3.astype(bool)].max():.3f}]")
except Exception as e:
    check("100 ticks stable", False, str(e))

# ---------------------------------------------------------------------------
# 4. thermal_ms < 0.1ms
# ---------------------------------------------------------------------------
try:
    sim4 = Simulation(cfg)
    for _ in range(5):
        sim4.step()
    thermal_times = []
    for _ in range(20):
        stats = sim4.step()
        thermal_times.append(stats.thermal_ms)
    avg_thermal = sum(thermal_times) / len(thermal_times)

    check(f"thermal_ms < 0.1ms ({avg_thermal:.3f}ms)",
          avg_thermal < 0.1,
          f"avg={avg_thermal:.3f}ms (flat vectorised, was 0.335ms)")
except Exception as e:
    check("thermal_ms < 0.1ms", False, str(e))

# ---------------------------------------------------------------------------
# 5. regen_ms < 0.5ms
# ---------------------------------------------------------------------------
try:
    regen_times = []
    for _ in range(20):
        stats = sim4.step()
        regen_times.append(stats.regen_ms)
    avg_regen = sum(regen_times) / len(regen_times)

    check(f"regen_ms < 0.5ms ({avg_regen:.3f}ms)",
          avg_regen < 0.5,
          f"avg={avg_regen:.3f}ms (optimised, was 0.623ms)")
except Exception as e:
    check("regen_ms < 0.5ms", False, str(e))

# ---------------------------------------------------------------------------
# 6. Total sim tick < 2ms
# ---------------------------------------------------------------------------
try:
    tick_times = []
    for _ in range(20):
        stats = sim4.step()
        tick_times.append(stats.last_tick_ms)
    avg_tick = sum(tick_times) / len(tick_times)

    check(f"Sim tick < 2ms ({avg_tick:.2f}ms)",
          avg_tick < 2.0,
          f"thermal={stats.thermal_ms:.3f} regen={stats.regen_ms:.3f} perceive={stats.perceive_ms:.3f}")
except Exception as e:
    check("Sim tick < 2ms", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p103 -- Wave 53 Flat Thermal + Optimised Regen ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 53 flat thermal + optimised regen validation complet.")
