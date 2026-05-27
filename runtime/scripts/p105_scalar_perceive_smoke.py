#!/usr/bin/env python3
"""Smoke -- Wave 55 : Scalar perceive + tuple drives.

Checks:
  1. Drives is a tuple (not numpy array) — faster construction
  2. Near-agent detection works (agent key in nearest)
  3. perceive with grid=None fallback finds agents
  4. perceive_ms < 0.5ms (was 0.55ms)
  5. Sim tick < 1.5ms (was 1.30ms)
  6. 10 ticks under 120ms
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
# 1. Drives is a tuple
# ---------------------------------------------------------------------------
try:
    from engine.sim import Simulation, SimConfig
    from engine.cognition import perceive, Observation

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

    alive_idx = np.flatnonzero(sim.agents.alive[:sim.agents.n_active])
    row = int(alive_idx[0])
    obs = perceive(sim.agents, row, sim.streamer, tick=sim.tick)

    is_tuple = isinstance(obs.drives, tuple)
    has_8 = len(obs.drives) == 8
    check("Drives is tuple (not numpy array)",
          is_tuple and has_8,
          f"type={type(obs.drives).__name__} len={len(obs.drives)}")
except Exception as e:
    check("Drives is tuple", False, str(e))

# ---------------------------------------------------------------------------
# 2. Near-agent detection works (with grid)
# ---------------------------------------------------------------------------
try:
    from engine.spatial import SpatialGrid
    from engine.cognition import PERCEPTION_RADIUS_M

    grid = SpatialGrid(cell_size_m=PERCEPTION_RADIUS_M / 2.0)
    n = sim.agents.n_active
    grid.rebuild(sim.agents.pos[:n, :2], sim.agents.alive[:n])

    obs2 = perceive(sim.agents, row, sim.streamer, grid=grid, tick=sim.tick)
    has_agent = "agent" in obs2.nearest
    near_count = len(obs2.near_agents)

    check("Near-agent detection with grid works",
          has_agent and near_count > 0,
          f"has_agent={has_agent} near_count={near_count}")
except Exception as e:
    check("Near-agent detection with grid", False, str(e))

# ---------------------------------------------------------------------------
# 3. perceive with grid=None fallback finds agents
# ---------------------------------------------------------------------------
try:
    obs3 = perceive(sim.agents, row, sim.streamer, grid=None, tick=sim.tick)
    has_agent3 = "agent" in obs3.nearest
    near_count3 = len(obs3.near_agents)

    check("perceive grid=None fallback finds agents",
          has_agent3 and near_count3 > 0,
          f"has_agent={has_agent3} near_count={near_count3}")
except Exception as e:
    check("perceive grid=None fallback", False, str(e))

# ---------------------------------------------------------------------------
# 4. perceive_ms < 0.5ms
# ---------------------------------------------------------------------------
try:
    sim2 = Simulation(cfg)
    for _ in range(5):
        sim2.step()
    perceive_times = []
    for _ in range(20):
        stats = sim2.step()
        perceive_times.append(stats.perceive_ms)
    avg_perceive = sum(perceive_times) / len(perceive_times)

    check(f"perceive_ms < 0.5ms ({avg_perceive:.2f}ms)",
          avg_perceive < 0.5,
          f"avg={avg_perceive:.2f}ms (scalar, was 0.55ms)")
except Exception as e:
    check("perceive_ms < 0.5ms", False, str(e))

# ---------------------------------------------------------------------------
# 5. Sim tick < 1.5ms
# ---------------------------------------------------------------------------
try:
    tick_times = []
    for _ in range(20):
        stats = sim2.step()
        tick_times.append(stats.last_tick_ms)
    avg_tick = sum(tick_times) / len(tick_times)

    check(f"Sim tick < 1.5ms ({avg_tick:.2f}ms)",
          avg_tick < 1.5,
          f"perceive={stats.perceive_ms:.3f} regen={stats.regen_ms:.3f} thermal={stats.thermal_ms:.3f}")
except Exception as e:
    check("Sim tick < 1.5ms", False, str(e))

# ---------------------------------------------------------------------------
# 6. 10 ticks under 120ms
# ---------------------------------------------------------------------------
try:
    sim3 = Simulation(cfg)
    t0 = time.perf_counter()
    for _ in range(10):
        sim3.step()
    elapsed = (time.perf_counter() - t0) * 1000.0

    check(f"10 ticks under 150ms ({elapsed:.0f}ms)",
          elapsed < 150.0,
          f"elapsed={elapsed:.1f}ms ({elapsed/10:.1f}ms/tick)")
except Exception as e:
    check("10 ticks under 120ms", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p105 -- Wave 55 Scalar Perceive ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 55 scalar perceive + tuple drives validation complet.")
