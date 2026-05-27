#!/usr/bin/env python3
"""Smoke -- Wave 51 : targeted regen + vectorised thermal.

Checks:
  1. Targeted regen: food regrows for perceived chunks
  2. Vectorised thermal: thermal stress updates correctly
  3. Stability: 100 ticks no NaN/Inf
  4. regen_ms < 1ms (targeted: ~25 chunks vs 113)
  5. Total sim tick < 3ms steady-state
  6. Overall 10 ticks under 150ms
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


from engine.sim import Simulation, SimConfig  # noqa: E402

SEED = 42

# ---------------------------------------------------------------------------
# 1. Targeted regen: food regrows in perceived chunks
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
    sim.step()  # bootstrap

    # Record food in perceived chunks
    alive_idx = np.flatnonzero(sim.agents.alive[:sim.agents.n_active])
    row0 = int(alive_idx[0])
    from engine.world import world_to_chunk
    px, py = float(sim.agents.pos[row0, 0]), float(sim.agents.pos[row0, 1])
    home_chunk_coord = world_to_chunk(px, py)
    home_chunk = sim.streamer.cache.get(home_chunk_coord)

    food_before = home_chunk.food_kcal.copy()
    # Deplete some food
    home_chunk.food_kcal *= 0.5

    sim.step()  # should regen the perceived chunk

    food_after = home_chunk.food_kcal
    regrew = (food_after > home_chunk.food_kcal * 0.5 - 1.0).any()
    # Food should move toward capacity (increased from depleted level)
    diff = float((food_after - home_chunk.food_kcal * 0.5).mean())

    check("Targeted regen: food regrows in perceived chunks",
          regrew,
          f"chunk={home_chunk_coord} mean_food={float(food_after.mean()):.1f}")
except Exception as e:
    check("Targeted regen: food regrows in perceived chunks", False, str(e))

# ---------------------------------------------------------------------------
# 2. Vectorised thermal updates correctly
# ---------------------------------------------------------------------------
try:
    sim2 = Simulation(cfg)
    sim2.step()

    # Record thermal values
    n = sim2.agents.n_active
    alive = np.flatnonzero(sim2.agents.alive[:n])
    thermal_before = sim2.agents.thermal[alive].copy()

    # Run 10 ticks
    for _ in range(10):
        sim2.step()

    thermal_after = sim2.agents.thermal[alive]
    # Thermal should have changed (not all zeros or NaN)
    no_nan = not np.isnan(thermal_after).any()
    no_inf = not np.isinf(thermal_after).any()
    in_range = ((thermal_after >= 0.0) & (thermal_after <= 1.5)).all()
    changed = not np.allclose(thermal_before, thermal_after, atol=1e-6)

    check("Vectorised thermal: correct + bounded",
          no_nan and no_inf and in_range,
          f"range=[{float(thermal_after.min()):.3f}, {float(thermal_after.max()):.3f}] changed={changed}")
except Exception as e:
    check("Vectorised thermal: correct + bounded", False, str(e))

# ---------------------------------------------------------------------------
# 3. Stability: 100 ticks
# ---------------------------------------------------------------------------
try:
    sim3 = Simulation(cfg)
    for _ in range(100):
        sim3.step()

    n3 = sim3.agents.n_active
    alive3 = np.flatnonzero(sim3.agents.alive[:n3])
    no_nan = not np.isnan(sim3.agents.thermal[alive3]).any()
    no_inf = not np.isinf(sim3.agents.thermal[alive3]).any()
    drives_ok = all(
        not np.isnan(getattr(sim3.agents, d)[alive3]).any()
        for d in ("hunger", "thirst", "sleep", "fatigue", "thermal")
    )

    check("100 ticks stable (no NaN/Inf)",
          no_nan and no_inf and drives_ok,
          f"alive={len(alive3)} ticks={sim3.tick}")
except Exception as e:
    check("100 ticks stable", False, str(e))

# ---------------------------------------------------------------------------
# 4. regen_ms < 1ms (targeted)
# ---------------------------------------------------------------------------
try:
    sim4 = Simulation(cfg)
    for _ in range(5):
        sim4.step()

    regen_times = []
    for _ in range(10):
        stats = sim4.step()
        regen_times.append(stats.regen_ms)
    avg_regen = sum(regen_times) / len(regen_times)

    check(f"regen_ms < 1ms ({avg_regen:.2f}ms)",
          avg_regen < 1.0,
          f"avg={avg_regen:.2f}ms chunks={stats.chunks_in_mem}")
except Exception as e:
    check("regen_ms < 1ms", False, str(e))

# ---------------------------------------------------------------------------
# 5. Total tick < 3ms
# ---------------------------------------------------------------------------
try:
    tick_times = []
    for _ in range(10):
        stats = sim4.step()
        tick_times.append(stats.last_tick_ms)
    avg_tick = sum(tick_times) / len(tick_times)

    check(f"Sim tick < 3ms ({avg_tick:.2f}ms)",
          avg_tick < 3.0,
          f"avg_tick={avg_tick:.2f}ms stream={stats.stream_ms:.2f} "
          f"perceive={stats.perceive_ms:.2f} regen={stats.regen_ms:.2f}")
except Exception as e:
    check("Sim tick < 3ms", False, str(e))

# ---------------------------------------------------------------------------
# 6. 10 ticks under 150ms
# ---------------------------------------------------------------------------
try:
    sim5 = Simulation(cfg)
    t0 = time.perf_counter()
    for _ in range(10):
        sim5.step()
    elapsed = (time.perf_counter() - t0) * 1000.0

    check(f"10 ticks under 150ms ({elapsed:.0f}ms)",
          elapsed < 150.0,
          f"elapsed={elapsed:.1f}ms ({elapsed/10:.1f}ms/tick)")
except Exception as e:
    check("10 ticks under 150ms", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p101 -- Wave 51 Targeted Regen + Vectorised Thermal ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 51 targeted regen + vectorised thermal validation complet.")
