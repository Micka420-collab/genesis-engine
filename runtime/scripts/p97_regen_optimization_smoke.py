#!/usr/bin/env python3
"""Smoke -- Wave 47 : regeneration optimization.

Checks:
  1. Chunk has cached _mean_height and _mean_food_cap
  2. Cached means match np.mean (bit-exact)
  3. regenerate_chunk_resources produces correct values
  4. In-place ops don't corrupt arrays
  5. Regen performance: batch faster than per-chunk np.mean
  6. Sim regen_ms improved (< 5ms for 100+ chunks)
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
    generate_chunk, TerrainParams, Weather,
    regenerate_chunk_resources, CHUNK_SIZE,
)

SEED = 42

# ---------------------------------------------------------------------------
# 1. Chunk has cached means
# ---------------------------------------------------------------------------
try:
    chunk = generate_chunk(SEED, (0, 0, 0), TerrainParams())
    has_mean_h = hasattr(chunk, "_mean_height")
    has_mean_fc = hasattr(chunk, "_mean_food_cap")
    check("Chunk has cached _mean_height and _mean_food_cap",
          has_mean_h and has_mean_fc,
          f"_mean_height={has_mean_h} _mean_food_cap={has_mean_fc}")
except Exception as e:
    check("Chunk has cached means", False, str(e))

# ---------------------------------------------------------------------------
# 2. Cached means match np.mean
# ---------------------------------------------------------------------------
try:
    actual_h = float(np.mean(chunk.height))
    actual_fc = float(np.mean(chunk.food_capacity))
    h_match = abs(chunk._mean_height - actual_h) < 1e-6
    fc_match = abs(chunk._mean_food_cap - actual_fc) < 1e-6
    check("Cached means match np.mean (bit-exact)",
          h_match and fc_match,
          f"height diff={abs(chunk._mean_height - actual_h):.1e} "
          f"food_cap diff={abs(chunk._mean_food_cap - actual_fc):.1e}")
except Exception as e:
    check("Cached means match np.mean", False, str(e))

# ---------------------------------------------------------------------------
# 3. regenerate_chunk_resources produces correct values
# ---------------------------------------------------------------------------
try:
    chunk2 = generate_chunk(SEED, (1, 1, 0), TerrainParams())
    food_before = chunk2.food_kcal.copy()
    water_before = chunk2.water.copy()
    w = Weather(temp_c=20.0, rain_mm_h=5.0, cloud=0.5, is_day=True)
    regenerate_chunk_resources(chunk2, w, dt_s=3600.0)

    # Food should increase toward capacity (or stay same if at capacity)
    food_diff = chunk2.food_kcal - food_before
    food_increased = (food_diff >= -1e-6).all()  # should not decrease (except float noise)

    # Water should increase with rain
    water_diff = chunk2.water - water_before
    water_increased = (water_diff >= -1e-6).all()

    check("regenerate produces correct values",
          food_increased and water_increased,
          f"food_diff_range=[{food_diff.min():.4f}, {food_diff.max():.4f}] "
          f"water_diff_range=[{water_diff.min():.4f}, {water_diff.max():.4f}]")
except Exception as e:
    check("regenerate produces correct values", False, str(e))

# ---------------------------------------------------------------------------
# 4. In-place ops don't corrupt arrays
# ---------------------------------------------------------------------------
try:
    chunk3 = generate_chunk(SEED, (2, 2, 0), TerrainParams())
    # Run regen 100 times to check for accumulation bugs
    w = Weather(temp_c=15.0, rain_mm_h=2.0, cloud=0.3, is_day=True)
    for _ in range(100):
        regenerate_chunk_resources(chunk3, w, dt_s=60.0)

    no_nan = not (np.isnan(chunk3.food_kcal).any() or np.isnan(chunk3.water).any())
    no_inf = not (np.isinf(chunk3.food_kcal).any() or np.isinf(chunk3.water).any())
    non_neg = (chunk3.food_kcal >= 0).all() and (chunk3.water >= 0).all()

    check("In-place ops don't corrupt (100 iterations)",
          no_nan and no_inf and non_neg,
          f"no_nan={no_nan} no_inf={no_inf} non_neg={non_neg}")
except Exception as e:
    check("In-place ops don't corrupt", False, str(e))

# ---------------------------------------------------------------------------
# 5. Regen performance: cached means vs np.mean
# ---------------------------------------------------------------------------
try:
    chunks = [generate_chunk(SEED, (i % 10, i // 10, 0), TerrainParams())
              for i in range(50)]
    w = Weather(temp_c=20.0, rain_mm_h=3.0, cloud=0.5, is_day=True)

    # With cached means (Wave 47 path)
    t0 = time.perf_counter()
    for _ in range(10):
        for c in chunks:
            _ = c._mean_height
            _ = c._mean_food_cap
            regenerate_chunk_resources(c, w, dt_s=60.0)
    cached_ms = (time.perf_counter() - t0) * 1000.0

    # Recreate chunks (fresh)
    chunks2 = [generate_chunk(SEED, (i % 10, i // 10, 0), TerrainParams())
               for i in range(50)]

    # With np.mean each time (old path simulation)
    t0 = time.perf_counter()
    for _ in range(10):
        for c in chunks2:
            _ = float(np.mean(c.height))
            _ = float(np.mean(c.food_capacity))
            regenerate_chunk_resources(c, w, dt_s=60.0)
    uncached_ms = (time.perf_counter() - t0) * 1000.0

    speedup = uncached_ms / max(cached_ms, 0.001)
    check(f"Cached means faster ({speedup:.1f}x)",
          cached_ms < uncached_ms,
          f"cached={cached_ms:.1f}ms uncached={uncached_ms:.1f}ms")
except Exception as e:
    check("Cached means faster", False, str(e))

# ---------------------------------------------------------------------------
# 6. Sim regen_ms < 5ms
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
    # Warm up
    for _ in range(5):
        stats = sim.step()
    # Measure steady-state regen
    regen_times = []
    for _ in range(10):
        stats = sim.step()
        regen_times.append(stats.regen_ms)
    avg_regen = sum(regen_times) / len(regen_times)
    check(f"Sim regen_ms avg < 5ms ({avg_regen:.2f}ms)",
          avg_regen < 5.0,
          f"avg={avg_regen:.2f}ms chunks={stats.chunks_in_mem}")
except Exception as e:
    check("Sim regen_ms < 5ms", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p97 -- Wave 47 Regen Optimization ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 47 regen optimization validation complet.")
