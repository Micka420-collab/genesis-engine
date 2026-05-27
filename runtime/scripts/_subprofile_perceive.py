#!/usr/bin/env python3
"""Sub-profile the perceive+decide loop to find which sub-phase dominates."""
from __future__ import annotations
import sys, time, io
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import numpy as np
from engine.sim import Simulation, SimConfig
from engine.cognition import perceive, decide, apply_decision

cfg = SimConfig(seed=42, founders=6, bounds_km=(0.5, 0.5),
                emergence_subsystems=False, life_emergence=False,
                knowledge_layers=False, wind_advect_agents=False)
sim = Simulation(cfg)
for _ in range(10):
    sim.step()

# Now manually run the perceive+decide loop with sub-timing
t_perceive_total = 0.0
t_decide_total = 0.0
t_apply_total = 0.0
t_social_total = 0.0
call_count = 0
ticks = 30

for _ in range(ticks):
    sim.tick += 1
    # Reuse existing streamer state (already has chunks)
    sim._grid.rebuild(sim.agents.pos[:sim.agents.n_active, :2],
                      sim.agents.alive[:sim.agents.n_active])
    alive_idx = np.flatnonzero(sim.agents.alive[:sim.agents.n_active])

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
        # Social affinity update
        if obs.near_agents:
            for j in obs.near_agents[:3]:
                sim.agents.relations[row].update_affinity(j, +0.001)
        t4 = time.perf_counter()

        t_perceive_total += (t1 - t0)
        t_decide_total += (t2 - t1)
        t_apply_total += (t3 - t2)
        t_social_total += (t4 - t3)
        call_count += 1

total_calls = call_count
print(f"\nSub-profile perceive+decide loop ({ticks} ticks, {total_calls} calls)")
print(f"  {'Sub-phase':<20s} {'Total ms':>10s} {'Per-call ms':>12s} {'%':>8s}")
print("  " + "-" * 52)
grand_total = t_perceive_total + t_decide_total + t_apply_total + t_social_total
for label, t in [("perceive", t_perceive_total),
                 ("decide", t_decide_total),
                 ("apply", t_apply_total),
                 ("social", t_social_total)]:
    ms = t * 1000.0
    per_call = ms / total_calls if total_calls > 0 else 0
    pct = t / grand_total * 100 if grand_total > 0 else 0
    print(f"  {label:<20s} {ms:>9.2f}ms {per_call:>10.4f}ms {pct:>7.1f}%")
print(f"  {'TOTAL':<20s} {grand_total*1000:.2f}ms {grand_total*1000/total_calls:.4f}ms  100.0%")
