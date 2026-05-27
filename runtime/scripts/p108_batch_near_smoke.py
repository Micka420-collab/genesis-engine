#!/usr/bin/env python3
"""Smoke -- Wave 58 : Batch Rust near-agent scan.

Tests that the Rust py_batch_near_agents function:
  1. Is importable from genesis_world
  2. Returns correct results (same as Python scalar path)
  3. Deterministic across repeated calls
  4. Perceive with near_cache matches perceive without
  5. sim.step() still passes at 6 agents
  6. Performance: 50-agent perceive improved (< 6ms avg)
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
from engine.sim import Simulation, SimConfig
from engine.cognition import perceive, PERCEPTION_RADIUS_M
from engine.spatial import SpatialGrid

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
    from genesis_world import py_batch_near_agents
    has_batch = True
except ImportError:
    has_batch = False
check("py_batch_near_agents importable", has_batch)

if not has_batch:
    print("ECHEC: py_batch_near_agents not available — skipping all checks")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 2. Correctness vs Python scalar path
# ---------------------------------------------------------------------------
cfg = SimConfig(seed=42, founders=12, bounds_km=(0.5, 0.5),
                emergence_subsystems=False, life_emergence=False,
                knowledge_layers=False, wind_advect_agents=False)
sim = Simulation(cfg)
for _ in range(10):
    sim.step()

n = sim.agents.n_active
alive_idx = np.flatnonzero(sim.agents.alive[:n])
grid = SpatialGrid(cell_size_m=PERCEPTION_RADIUS_M / 2.0)
grid.rebuild(sim.agents.pos[:n, :2], sim.agents.alive[:n])

# Rust batch
batch_result = py_batch_near_agents(
    sim.agents.pos[:n, :2],
    sim.agents.alive[:n].view(np.uint8),
    float(PERCEPTION_RADIUS_M))

# Compare each agent
all_match = True
mismatch_detail = ""
for row in alive_idx:
    row = int(row)
    rust_near = batch_result[row]
    # Python scalar path
    px = float(sim.agents.pos[row, 0])
    py_ = float(sim.agents.pos[row, 1])
    candidates = grid.query_disk(px, py_, PERCEPTION_RADIUS_M, exclude_row=row)
    py_hits = []
    for j in candidates:
        if not sim.agents.alive[j]:
            continue
        dx = float(sim.agents.pos[j, 0]) - px
        dy = float(sim.agents.pos[j, 1]) - py_
        d2 = dx * dx + dy * dy
        if d2 < PERCEPTION_RADIUS_M * PERCEPTION_RADIUS_M:
            py_hits.append((d2, j))
    py_hits.sort()
    py_hits = py_hits[:16]

    rust_indices = [int(t[0]) for t in rust_near]
    py_indices = [j for _, j in py_hits]
    if rust_indices != py_indices:
        all_match = False
        mismatch_detail = f"row={row} rust={rust_indices} py={py_indices}"
        break
    # Check distances match within tolerance
    for (d2_py, _), (_, d_rust) in zip(py_hits, rust_near):
        d_py = math.sqrt(d2_py)
        if abs(d_py - d_rust) > 1e-6:
            all_match = False
            mismatch_detail = f"row={row} d_py={d_py} d_rust={d_rust}"
            break
    if not all_match:
        break

check("Batch near-agents matches Python scalar path", all_match, mismatch_detail)

# ---------------------------------------------------------------------------
# 3. Deterministic
# ---------------------------------------------------------------------------
r1 = py_batch_near_agents(
    sim.agents.pos[:n, :2], sim.agents.alive[:n].view(np.uint8),
    float(PERCEPTION_RADIUS_M))
r2 = py_batch_near_agents(
    sim.agents.pos[:n, :2], sim.agents.alive[:n].view(np.uint8),
    float(PERCEPTION_RADIUS_M))
det_ok = True
for i in range(n):
    if r1[i] != r2[i]:
        det_ok = False
        break
check("Batch near-agents deterministic", det_ok)

# ---------------------------------------------------------------------------
# 4. perceive() with near_cache matches without
# ---------------------------------------------------------------------------
row0 = int(alive_idx[0])
nc = batch_result[row0]
obs_with = perceive(sim.agents, row0, sim.streamer, grid=grid, tick=sim.tick + 1,
                    near_cache=nc)
obs_without = perceive(sim.agents, row0, sim.streamer, grid=grid, tick=sim.tick + 1,
                       near_cache=None)
near_match = (obs_with.near_agents == obs_without.near_agents)
agent_key_match = True
if "agent" in obs_without.nearest:
    if "agent" not in obs_with.nearest:
        agent_key_match = False
    else:
        d_diff = abs(obs_with.nearest["agent"].distance - obs_without.nearest["agent"].distance)
        agent_key_match = d_diff < 1e-6
check("perceive near_cache matches fallback", near_match and agent_key_match,
      f"near={near_match} agent_key={agent_key_match}")

# ---------------------------------------------------------------------------
# 5. sim.step() passes at 6 agents
# ---------------------------------------------------------------------------
cfg6 = SimConfig(seed=42, founders=6, bounds_km=(0.5, 0.5),
                 emergence_subsystems=False, life_emergence=False,
                 knowledge_layers=False, wind_advect_agents=False)
sim6 = Simulation(cfg6)
try:
    for _ in range(20):
        sim6.step()
    step_ok = True
    step_detail = f"tick={sim6.tick} alive={int(sim6.agents.alive[:sim6.agents.n_active].sum())}"
except Exception as e:
    step_ok = False
    step_detail = str(e)
check("sim.step() stable with batch near (6 agents, 20 ticks)", step_ok, step_detail)

# ---------------------------------------------------------------------------
# 6. Performance at 50 agents: perceive < 6ms
# ---------------------------------------------------------------------------
cfg50 = SimConfig(seed=42, founders=50, bounds_km=(0.5, 0.5),
                  emergence_subsystems=False, life_emergence=False,
                  knowledge_layers=False, wind_advect_agents=False)
sim50 = Simulation(cfg50)
for _ in range(5):
    sim50.step()
perc_times = []
for _ in range(10):
    stats = sim50.step()
    perc_times.append(stats.perceive_ms)
avg_perc = sum(perc_times) / len(perc_times)
check(f"50-agent perceive < 6ms (avg={avg_perc:.2f}ms)", avg_perc < 6.0,
      f"min={min(perc_times):.2f}ms max={max(perc_times):.2f}ms")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p108 -- Wave 58 Batch Near-Agent Scan ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) raté(s).")
    sys.exit(1)
print("OK -- Wave 58 batch near-agent scan validation complet.")
