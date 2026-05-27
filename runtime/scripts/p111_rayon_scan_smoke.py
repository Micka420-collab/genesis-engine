#!/usr/bin/env python3
"""Smoke -- Wave 61 : Rayon parallel batch scan + timing fix.

Tests:
  1. py_batch_scan_resources works (rayon path at >=16 agents)
  2. sim.step() stable at 6 agents (sequential path)
  3. Perceive < 0.80ms at 6 agents (includes batch pre-computation)
  4. sim.step() stable at 50 agents (rayon path)
  5. Perceive < 3.0ms at 50 agents (rayon parallel)
  6. sim.step() stable at 100 agents + perceive < 5ms
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


# ---------------------------------------------------------------------------
# 1. Import and rayon path test: 20 agents forces rayon (>= 16 threshold)
# ---------------------------------------------------------------------------
try:
    from genesis_world import py_batch_scan_resources
    from engine.world import CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M
    N = 20
    pos = np.random.default_rng(42).uniform(0, 32, (N, 2)).astype(np.float32)
    alive = np.ones(N, dtype=np.uint8)
    water = np.full(CHUNK_SIZE * CHUNK_SIZE, 100.0, dtype=np.float32)
    food = np.full(CHUNK_SIZE * CHUNK_SIZE, 50.0, dtype=np.float32)
    wood = np.full(CHUNK_SIZE * CHUNK_SIZE, 80.0, dtype=np.float32)
    stone = np.zeros(CHUNK_SIZE * CHUNK_SIZE, dtype=np.float32)
    height = np.zeros(CHUNK_SIZE * CHUNK_SIZE, dtype=np.float32)
    result = py_batch_scan_resources(
        pos, alive, [0], [0],
        [water], [food], [wood], [stone], [height],
        60.0, float(VOXEL_SIZE_M), float(CHUNK_SIDE_M), int(CHUNK_SIZE))
    rayon_ok = len(result) == N and all(r[0] is not None for r in result)
except Exception as e:
    rayon_ok = False
check("Rayon path (N=20 >= 16) produces correct results", rayon_ok)

# ---------------------------------------------------------------------------
# 2. sim.step() stable at 6 agents
# ---------------------------------------------------------------------------
cfg6 = SimConfig(seed=42, founders=6, bounds_km=(0.5, 0.5),
                 emergence_subsystems=False, life_emergence=False,
                 knowledge_layers=False, wind_advect_agents=False)
sim6 = Simulation(cfg6)
try:
    for _ in range(20):
        sim6.step()
    step6_ok = True
    detail6 = "tick=%d alive=%d" % (sim6.tick, int(sim6.agents.alive[:sim6.agents.n_active].sum()))
except Exception as e:
    step6_ok = False
    detail6 = str(e)[:200]
check("sim.step() stable 6 agents 20 ticks", step6_ok, detail6)

# ---------------------------------------------------------------------------
# 3. Perceive < 0.80ms at 6 agents
# ---------------------------------------------------------------------------
perc_times6 = []
for _ in range(20):
    stats = sim6.step()
    perc_times6.append(stats.perceive_ms)
avg_perc6 = sum(perc_times6) / len(perc_times6)
check("Perceive < 0.80ms at 6 agents (avg=%.4fms)" % avg_perc6,
      avg_perc6 < 0.80,
      "min=%.4fms max=%.4fms" % (min(perc_times6), max(perc_times6)))

# ---------------------------------------------------------------------------
# 4. sim.step() stable at 50 agents (rayon path)
# ---------------------------------------------------------------------------
cfg50 = SimConfig(seed=42, founders=50, bounds_km=(0.5, 0.5),
                  emergence_subsystems=False, life_emergence=False,
                  knowledge_layers=False, wind_advect_agents=False)
sim50 = Simulation(cfg50)
try:
    for _ in range(20):
        sim50.step()
    step50_ok = True
    detail50 = "tick=%d alive=%d" % (sim50.tick, int(sim50.agents.alive[:sim50.agents.n_active].sum()))
except Exception as e:
    step50_ok = False
    detail50 = str(e)[:200]
check("sim.step() stable 50 agents 20 ticks", step50_ok, detail50)

# ---------------------------------------------------------------------------
# 5. Perceive < 3.0ms at 50 agents
# ---------------------------------------------------------------------------
perc_times50 = []
for _ in range(20):
    stats = sim50.step()
    perc_times50.append(stats.perceive_ms)
avg_perc50 = sum(perc_times50) / len(perc_times50)
check("Perceive < 3.0ms at 50 agents (avg=%.4fms)" % avg_perc50,
      avg_perc50 < 3.0,
      "min=%.4fms max=%.4fms" % (min(perc_times50), max(perc_times50)))

# ---------------------------------------------------------------------------
# 6. sim.step() stable at 100 agents + perceive < 5ms
# ---------------------------------------------------------------------------
cfg100 = SimConfig(seed=42, founders=100, bounds_km=(0.5, 0.5),
                   emergence_subsystems=False, life_emergence=False,
                   knowledge_layers=False, wind_advect_agents=False)
sim100 = Simulation(cfg100)
try:
    for _ in range(20):
        sim100.step()
    step100_ok = True
    detail100 = "tick=%d alive=%d" % (sim100.tick, int(sim100.agents.alive[:sim100.agents.n_active].sum()))
except Exception as e:
    step100_ok = False
    detail100 = str(e)[:200]

perc_times100 = []
if step100_ok:
    for _ in range(20):
        stats = sim100.step()
        perc_times100.append(stats.perceive_ms)
    avg_perc100 = sum(perc_times100) / len(perc_times100)
    perc100_ok = avg_perc100 < 5.0
    detail100 += " | perceive avg=%.3fms" % avg_perc100
else:
    perc100_ok = False

check("100 agents stable + perceive < 5ms",
      step100_ok and perc100_ok,
      detail100)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print("\nSmoke p111 -- Wave 61 Rayon Parallel Scan (%d/%d)\n" % (passed, total))
for r in results:
    print(r)
print()
if failed:
    print("ECHEC : %d check(s) rate(s)." % failed)
    sys.exit(1)
print("OK -- Wave 61 rayon parallel scan validation complet.")
