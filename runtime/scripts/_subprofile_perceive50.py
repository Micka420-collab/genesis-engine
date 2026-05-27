#!/usr/bin/env python3
"""Sub-profile INSIDE perceive at 50 agents."""
from __future__ import annotations
import sys, time, io, math
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import numpy as np
from engine.sim import Simulation, SimConfig
from engine.cognition import perceive
from engine.spatial import SpatialGrid
from engine.cognition import PERCEPTION_RADIUS_M

cfg = SimConfig(seed=42, founders=50, bounds_km=(0.5, 0.5),
                emergence_subsystems=False, life_emergence=False,
                knowledge_layers=False, wind_advect_agents=False)
sim = Simulation(cfg)
for _ in range(10):
    sim.step()

# Instrument individual perceive calls
t_total = []
chunks_scanned_list = []
near_agent_count_list = []

n = sim.agents.n_active
grid = SpatialGrid(cell_size_m=PERCEPTION_RADIUS_M / 2.0)
grid.rebuild(sim.agents.pos[:n, :2], sim.agents.alive[:n])
alive_idx = np.flatnonzero(sim.agents.alive[:n])

for row in alive_idx:
    row = int(row)
    t0 = time.perf_counter()
    obs = perceive(sim.agents, row, sim.streamer, grid=grid, tick=sim.tick + 1)
    t1 = time.perf_counter()
    t_total.append((t1 - t0) * 1e6)  # microseconds
    near_agent_count_list.append(len(obs.near_agents))

times = np.array(t_total)
print(f"\nPerceive at 50 agents ({len(times)} calls):")
print(f"  Mean:   {times.mean():.1f}μs")
print(f"  Median: {np.median(times):.1f}μs")
print(f"  Min:    {times.min():.1f}μs")
print(f"  Max:    {times.max():.1f}μs")
print(f"  P95:    {np.percentile(times, 95):.1f}μs")
print(f"  Near-agents avg: {np.mean(near_agent_count_list):.1f}")

# Histogram of times
bins = [0, 50, 75, 100, 150, 200, 500]
hist, _ = np.histogram(times, bins=bins)
print(f"\n  Distribution:")
for i in range(len(bins) - 1):
    print(f"    {bins[i]:>4d}-{bins[i+1]:>4d}μs: {hist[i]:>3d} ({hist[i]/len(times)*100:.0f}%)")
