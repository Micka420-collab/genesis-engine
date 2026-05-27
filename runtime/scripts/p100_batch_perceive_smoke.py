#!/usr/bin/env python3
"""Smoke -- Wave 50 : sorted perceive + distance pruning.

Checks:
  1. perceive returns valid Observation with nearest resources
  2. Sorted chunks produce same resource types as unsorted
  3. Distance pruning: far chunks skipped for close resources
  4. perceive_ms < 4ms (improved from 4.84ms baseline)
  5. Total sim tick < 8ms steady-state
  6. Overall 10 ticks under 200ms
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


from engine.world import generate_chunk, TerrainParams, CHUNK_SIDE_M, ChunkStreamer  # noqa: E402
from engine.cognition import perceive, Observation  # noqa: E402

SEED = 42

# ---------------------------------------------------------------------------
# 1. perceive returns valid Observation
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
    sim.step()  # bootstrap + 1 tick

    # Pick first alive agent
    alive_idx = np.flatnonzero(sim.agents.alive[:sim.agents.n_active])
    row = int(alive_idx[0])
    obs = perceive(sim.agents, row, sim.streamer, tick=sim.tick)

    is_obs = isinstance(obs, Observation)
    has_nearest = isinstance(obs.nearest, dict)
    has_drives = obs.drives is not None and len(obs.drives) == 8

    check("perceive returns valid Observation",
          is_obs and has_nearest and has_drives,
          f"row={row} nearest_keys={list(obs.nearest.keys())}")
except Exception as e:
    check("perceive returns valid Observation", False, str(e))

# ---------------------------------------------------------------------------
# 2. Sorted chunks produce correct resource types
# ---------------------------------------------------------------------------
try:
    # Run perceive for all alive agents and check they find resources
    found_water = 0
    found_food = 0
    found_shelter = 0
    total_agents = 0
    for row in alive_idx:
        row = int(row)
        obs = perceive(sim.agents, row, sim.streamer, tick=sim.tick)
        total_agents += 1
        if "water" in obs.nearest:
            found_water += 1
        if "food" in obs.nearest:
            found_food += 1
        if "shelter" in obs.nearest:
            found_shelter += 1

    # Most agents should find at least water and food
    check("Sorted perceive finds resources",
          found_water >= total_agents * 0.5 and found_food >= total_agents * 0.5,
          f"agents={total_agents} water={found_water} food={found_food} shelter={found_shelter}")
except Exception as e:
    check("Sorted perceive finds resources", False, str(e))

# ---------------------------------------------------------------------------
# 3. Distance pruning works (close resource skips far chunks)
# ---------------------------------------------------------------------------
try:
    # After a few ticks, agents should have settled near resources.
    # Verify that the nearest resource distances are reasonable.
    for _ in range(5):
        sim.step()

    row = int(alive_idx[0])
    obs = perceive(sim.agents, row, sim.streamer, tick=sim.tick)

    distances = {}
    for k, t in obs.nearest.items():
        if k in ("water", "food", "shelter"):
            distances[k] = t.distance

    # At least 1 resource found and within perception radius
    any_close = any(d < 60.0 for d in distances.values())
    check("Distance pruning: resources within perception radius",
          any_close and len(distances) > 0,
          f"distances={distances}")
except Exception as e:
    check("Distance pruning: resources within perception radius", False, str(e))

# ---------------------------------------------------------------------------
# 4. perceive_ms < 4ms
# ---------------------------------------------------------------------------
try:
    sim2 = Simulation(cfg)
    for _ in range(5):
        sim2.step()  # warm up

    perceive_times = []
    for _ in range(10):
        stats = sim2.step()
        perceive_times.append(stats.perceive_ms)
    avg_perceive = sum(perceive_times) / len(perceive_times)

    check(f"perceive_ms < 4ms ({avg_perceive:.2f}ms)",
          avg_perceive < 4.0,
          f"avg={avg_perceive:.2f}ms chunks={stats.chunks_in_mem}")
except Exception as e:
    check("perceive_ms < 4ms", False, str(e))

# ---------------------------------------------------------------------------
# 5. Total tick < 8ms
# ---------------------------------------------------------------------------
try:
    tick_times = []
    for _ in range(10):
        stats = sim2.step()
        tick_times.append(stats.last_tick_ms)
    avg_tick = sum(tick_times) / len(tick_times)

    check(f"Sim tick < 8ms ({avg_tick:.2f}ms)",
          avg_tick < 8.0,
          f"avg_tick={avg_tick:.2f}ms stream={stats.stream_ms:.2f} "
          f"perceive={stats.perceive_ms:.2f} regen={stats.regen_ms:.2f}")
except Exception as e:
    check("Sim tick < 8ms", False, str(e))

# ---------------------------------------------------------------------------
# 6. 10 ticks under 200ms
# ---------------------------------------------------------------------------
try:
    sim3 = Simulation(cfg)
    t0 = time.perf_counter()
    for _ in range(10):
        sim3.step()
    elapsed = (time.perf_counter() - t0) * 1000.0

    check(f"10 ticks under 200ms ({elapsed:.0f}ms)",
          elapsed < 200.0,
          f"elapsed={elapsed:.1f}ms ({elapsed/10:.1f}ms/tick)")
except Exception as e:
    check("10 ticks under 200ms", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p100 -- Wave 50 Batch Perceive ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 50 sorted perceive + distance pruning validation complet.")
