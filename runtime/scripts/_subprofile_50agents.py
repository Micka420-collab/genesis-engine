#!/usr/bin/env python3
"""Sub-profile perceive at 50 agents — find what scales poorly."""
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
from engine.cognition import perceive, decide, apply_decision

cfg = SimConfig(seed=42, founders=50, bounds_km=(0.5, 0.5),
                emergence_subsystems=False, life_emergence=False,
                knowledge_layers=False, wind_advect_agents=False)
sim = Simulation(cfg)
for _ in range(10):
    sim.step()

# Sub-profile the perceive+decide loop
t_perceive_total = 0.0
t_decide_total = 0.0
t_apply_total = 0.0
t_social_total = 0.0
call_count = 0
ticks = 10

for _ in range(ticks):
    sim.tick += 1
    n = sim.agents.n_active
    sim._grid.rebuild(sim.agents.pos[:n, :2], sim.agents.alive[:n])
    alive_idx = np.flatnonzero(sim.agents.alive[:n])

    for row in alive_idx:
        row = int(row)
        t0 = time.perf_counter()
        obs = perceive(sim.agents, row, sim.streamer, grid=sim._grid, tick=sim.tick)
        t1 = time.perf_counter()
        d = decide(sim.agents, obs, sim=sim)
        t2 = time.perf_counter()
        sim.agents.action[row] = d.action
        sim.agents.target_x[row] = d.target_x
        sim.agents.target_y[row] = d.target_y
        ev = apply_decision(sim.agents, row, d, sim.streamer, sim.tick)
        t3 = time.perf_counter()
        if obs.near_agents:
            for j in obs.near_agents[:3]:
                sim.agents.relations[row].update_affinity(j, +0.001)
        t4 = time.perf_counter()

        t_perceive_total += (t1 - t0)
        t_decide_total += (t2 - t1)
        t_apply_total += (t3 - t2)
        t_social_total += (t4 - t3)
        call_count += 1

print(f"\nSub-profile 50 agents ({ticks} ticks, {call_count} calls)")
print(f"  {'Sub-phase':<20s} {'Total ms':>10s} {'Per-call ms':>12s} {'%':>8s}")
print("  " + "-" * 52)
grand = t_perceive_total + t_decide_total + t_apply_total + t_social_total
for label, t in [("perceive", t_perceive_total),
                 ("decide", t_decide_total),
                 ("apply", t_apply_total),
                 ("social", t_social_total)]:
    ms = t * 1000.0
    per_call = ms / call_count if call_count > 0 else 0
    pct = t / grand * 100 if grand > 0 else 0
    print(f"  {label:<20s} {ms:>9.2f}ms {per_call:>10.4f}ms {pct:>7.1f}%")
print(f"  {'TOTAL':<20s} {grand*1000:.2f}ms {grand*1000/call_count:.4f}ms  100.0%")
