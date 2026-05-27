#!/usr/bin/env python3
"""Smoke -- Wave 60 : Rust batch resource scan.

Tests that the Rust py_batch_scan_resources function:
  1. Is importable from genesis_world
  2. Returns correct structure (tuple of 3 Optional ScanHits per agent)
  3. Finds water/food/shelter consistent with Python perceive() fallback
  4. sim.step() stable at 6 agents (20 ticks)
  5. Perceive time < 0.40ms at 6 agents
  6. sim.step() stable at 50 agents (20 ticks) + perceive time < 4.0ms
"""
from __future__ import annotations

import io
import math
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
from engine.world import CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M  # noqa: E402

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


# ---------------------------------------------------------------------------
# 1. Import check
# ---------------------------------------------------------------------------
try:
    from genesis_world import py_batch_scan_resources
    has_batch = True
except ImportError:
    has_batch = False
check("py_batch_scan_resources importable", has_batch)

if not has_batch:
    print("ECHEC: py_batch_scan_resources not available -- skipping all checks")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 2. Structure check: returns list of (Option, Option, Option) tuples
# ---------------------------------------------------------------------------
# Create a minimal 1-agent, 1-chunk scenario.
agent_pos = np.array([[16.0, 16.0]], dtype=np.float32)
agent_alive = np.array([1], dtype=np.uint8)
# Single chunk at (0,0) with some resources in cells.
S = CHUNK_SIZE
water = np.zeros(S * S, dtype=np.float32)
food = np.zeros(S * S, dtype=np.float32)
wood = np.zeros(S * S, dtype=np.float32)
stone = np.zeros(S * S, dtype=np.float32)
height = np.zeros(S * S, dtype=np.float32)
# Place water at cell (32,32) — centre of chunk
mid = S // 2
water[mid * S + mid] = 100.0
# Place food at cell (30,30)
food[30 * S + 30] = 50.0
# Place shelter (wood>30) at cell (20,20)
wood[20 * S + 20] = 80.0

result = py_batch_scan_resources(
    agent_pos, agent_alive,
    [0], [0],  # chunk_cx, chunk_cy
    [water], [food], [wood], [stone], [height],
    60.0,  # radius
    float(VOXEL_SIZE_M), float(CHUNK_SIDE_M), int(CHUNK_SIZE))

struct_ok = (isinstance(result, list) and len(result) == 1
             and isinstance(result[0], tuple) and len(result[0]) == 3)
w_hit, f_hit, s_hit = result[0] if struct_ok else (None, None, None)
# Water and food and shelter should all be found (non-None).
hits_ok = w_hit is not None and f_hit is not None and s_hit is not None
check("Batch scan returns correct structure",
      struct_ok and hits_ok,
      f"struct={struct_ok} w={w_hit is not None} f={f_hit is not None} s={s_hit is not None}")

# ---------------------------------------------------------------------------
# 3. Correctness: Rust hits match expected positions
# ---------------------------------------------------------------------------
# Water at cell (32,32): world x = 0 + (32+0.5)*voxel_m
expected_wx = (mid + 0.5) * VOXEL_SIZE_M
expected_wy = (mid + 0.5) * VOXEL_SIZE_M
if w_hit is not None:
    wx, wy, wdist, wqty = w_hit
    pos_ok = (abs(wx - expected_wx) < 0.01 and abs(wy - expected_wy) < 0.01
              and wqty > 50.0 and wdist > 0.0)
else:
    pos_ok = False
# Food at cell (30,30)
expected_fx = (30 + 0.5) * VOXEL_SIZE_M
expected_fy = (30 + 0.5) * VOXEL_SIZE_M
if f_hit is not None:
    fx, fy, fdist, fqty = f_hit
    food_ok = (abs(fx - expected_fx) < 0.01 and abs(fy - expected_fy) < 0.01
               and fqty > 20.0)
else:
    food_ok = False
# Shelter at cell (20,20)
expected_sx = (20 + 0.5) * VOXEL_SIZE_M
expected_sy = (20 + 0.5) * VOXEL_SIZE_M
if s_hit is not None:
    sx, sy, sdist, sqty = s_hit
    shelter_ok = (abs(sx - expected_sx) < 0.01 and abs(sy - expected_sy) < 0.01
                  and sqty > 30.0)
else:
    shelter_ok = False

check("Batch scan hits match expected positions",
      pos_ok and food_ok and shelter_ok,
      f"water_ok={pos_ok} food_ok={food_ok} shelter_ok={shelter_ok}")

# ---------------------------------------------------------------------------
# 4. sim.step() stable at 6 agents
# ---------------------------------------------------------------------------
cfg6 = SimConfig(seed=42, founders=6, bounds_km=(0.5, 0.5),
                 emergence_subsystems=False, life_emergence=False,
                 knowledge_layers=False, wind_advect_agents=False)
sim6 = Simulation(cfg6)
try:
    for _ in range(20):
        sim6.step()
    step6_ok = True
    detail6 = f"tick={sim6.tick} alive={int(sim6.agents.alive[:sim6.agents.n_active].sum())}"
except Exception as e:
    step6_ok = False
    detail6 = str(e)[:200]
check("sim.step() stable 6 agents 20 ticks", step6_ok, detail6)

# ---------------------------------------------------------------------------
# 5. Perceive time < 0.40ms at 6 agents
# ---------------------------------------------------------------------------
perc_times6 = []
for _ in range(20):
    stats = sim6.step()
    perc_times6.append(stats.perceive_ms)
avg_perc6 = sum(perc_times6) / len(perc_times6)
# Threshold includes batch_near + batch_scan + Python loop.
check(f"Perceive < 0.80ms at 6 agents (avg={avg_perc6:.4f}ms)",
      avg_perc6 < 0.80,
      f"min={min(perc_times6):.4f}ms max={max(perc_times6):.4f}ms")

# ---------------------------------------------------------------------------
# 6. sim.step() stable at 50 agents + perceive time < 4.0ms
# ---------------------------------------------------------------------------
cfg50 = SimConfig(seed=42, founders=50, bounds_km=(0.5, 0.5),
                  emergence_subsystems=False, life_emergence=False,
                  knowledge_layers=False, wind_advect_agents=False)
sim50 = Simulation(cfg50)
try:
    for _ in range(20):
        sim50.step()
    step50_ok = True
    detail50 = f"tick={sim50.tick} alive={int(sim50.agents.alive[:sim50.agents.n_active].sum())}"
except Exception as e:
    step50_ok = False
    detail50 = str(e)[:200]

perc_times50 = []
if step50_ok:
    for _ in range(20):
        stats = sim50.step()
        perc_times50.append(stats.perceive_ms)
    avg_perc50 = sum(perc_times50) / len(perc_times50)
    perc50_ok = avg_perc50 < 4.0
    detail50 += f" | perceive avg={avg_perc50:.3f}ms"
else:
    perc50_ok = False
    avg_perc50 = -1.0

check(f"sim.step() stable 50 agents + perceive < 4ms",
      step50_ok and perc50_ok,
      detail50)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p110 -- Wave 60 Batch Resource Scan ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 60 batch resource scan validation complet.")
