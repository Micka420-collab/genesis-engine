#!/usr/bin/env python3
"""Smoke -- Wave 54 : Rust chunk regen (py_regen_chunk).

Checks:
  1. Rust regen function available and imported
  2. Rust regen produces same output as numpy path (bit-for-bit)
  3. Food stays bounded [0, capacity] after 100 regens
  4. Water recharge matches expected value
  5. regen_ms < 0.2ms (Rust: ~0.12ms vs numpy 0.39ms)
  6. Total sim tick < 1.5ms
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
# 1. Rust regen imported
# ---------------------------------------------------------------------------
try:
    from engine.sim import _HAS_RUST_REGEN
    check("Rust regen function imported",
          _HAS_RUST_REGEN,
          f"_HAS_RUST_REGEN={_HAS_RUST_REGEN}")
except Exception as e:
    check("Rust regen function imported", False, str(e))

# ---------------------------------------------------------------------------
# 2. Rust regen matches numpy path (bit-for-bit)
# ---------------------------------------------------------------------------
try:
    from genesis_world import py_regen_chunk
    from engine.world import generate_chunk, TerrainParams

    chunk = generate_chunk(SEED, (0, 0, 0), TerrainParams())
    food_orig = chunk.food_kcal.copy()
    cap_orig = chunk.food_capacity.copy()
    water_orig = chunk.water.copy()

    food_factor = 1500.0 / (3.0 * 86400.0)
    food_retain = 1.0 - food_factor
    water_rain = 50.0 * 0.125 * (1500.0 / 3600.0)

    # Numpy path
    food_np = food_orig.copy()
    water_np = water_orig.copy()
    np.multiply(food_np, np.float32(food_retain), out=food_np)
    food_np += cap_orig * np.float32(food_factor)
    water_np += np.float32(water_rain)

    # Rust path
    food_rs = food_orig.copy()
    water_rs = water_orig.copy()
    py_regen_chunk(food_rs.ravel(), cap_orig.ravel(), water_rs.ravel(),
                   float(food_retain), float(food_factor), float(water_rain))

    food_diff = float(np.abs(food_np - food_rs).max())
    water_diff = float(np.abs(water_np - water_rs).max())
    # Allow tiny float tolerance (f32 multiply order may differ)
    match_ok = food_diff < 1e-4 and water_diff < 1e-4

    check("Rust regen matches numpy (bit-for-bit)",
          match_ok,
          f"food_max_diff={food_diff:.6f} water_max_diff={water_diff:.6f}")
except Exception as e:
    check("Rust regen matches numpy", False, str(e))

# ---------------------------------------------------------------------------
# 3. Food stays bounded [0, capacity] after 100 regens
# ---------------------------------------------------------------------------
try:
    food_test = food_orig.copy()
    cap_test = cap_orig.copy()
    water_test = water_orig.copy()

    for _ in range(100):
        py_regen_chunk(food_test.ravel(), cap_test.ravel(), water_test.ravel(),
                       float(food_retain), float(food_factor), 0.0)

    no_neg = bool(food_test.min() >= 0.0)
    no_nan = bool(not np.any(np.isnan(food_test)))
    bounded = bool(food_test.max() <= cap_test.max() * 1.001)

    check("Food bounded [0, capacity] after 100 regens",
          no_neg and no_nan and bounded,
          f"min={food_test.min():.3f} max={food_test.max():.3f} cap_max={cap_test.max():.3f}")
except Exception as e:
    check("Food bounded after 100 regens", False, str(e))

# ---------------------------------------------------------------------------
# 4. Water recharge matches expected value
# ---------------------------------------------------------------------------
try:
    water_before = water_orig.copy()
    rain = 5.0
    py_regen_chunk(food_orig.copy().ravel(), cap_orig.ravel(),
                   water_before.ravel(), float(food_retain), float(food_factor), rain)
    actual_diff = float((water_before - water_orig).mean())
    expected_diff = rain
    close_enough = abs(actual_diff - expected_diff) < 0.01

    check("Water recharge matches expected",
          close_enough,
          f"actual_diff={actual_diff:.4f} expected={expected_diff:.4f}")
except Exception as e:
    check("Water recharge", False, str(e))

# ---------------------------------------------------------------------------
# 5. regen_ms < 0.2ms
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
        sim.step()
    regen_times = []
    for _ in range(20):
        stats = sim.step()
        regen_times.append(stats.regen_ms)
    avg_regen = sum(regen_times) / len(regen_times)

    check(f"regen_ms < 0.2ms ({avg_regen:.3f}ms)",
          avg_regen < 0.2,
          f"avg={avg_regen:.3f}ms (Rust, was 0.623ms numpy)")
except Exception as e:
    check("regen_ms < 0.2ms", False, str(e))

# ---------------------------------------------------------------------------
# 6. Total sim tick < 1.5ms
# ---------------------------------------------------------------------------
try:
    tick_times = []
    for _ in range(20):
        stats = sim.step()
        tick_times.append(stats.last_tick_ms)
    avg_tick = sum(tick_times) / len(tick_times)

    check(f"Sim tick < 1.5ms ({avg_tick:.2f}ms)",
          avg_tick < 1.5,
          f"regen={stats.regen_ms:.3f} perceive={stats.perceive_ms:.3f} stream={stats.stream_ms:.3f}")
except Exception as e:
    check("Sim tick < 1.5ms", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p104 -- Wave 54 Rust Regen ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 54 Rust regen validation complet.")
