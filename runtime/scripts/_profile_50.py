#!/usr/bin/env python3
"""Quick profiling script — 50 agents, 30 ticks."""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
from engine.sim import Simulation, SimConfig

cfg = SimConfig(seed=42, founders=100, bounds_km=(0.5,0.5),
                emergence_subsystems=False, life_emergence=False,
                knowledge_layers=False, wind_advect_agents=False)
sim = Simulation(cfg)
for _ in range(10):
    sim.step()

stats_list = []
for _ in range(30):
    st = sim.step()
    stats_list.append(st)

keys = ['stream_ms','regen_ms','drives_ms','perceive_ms','thermal_ms','post_ms']
avgs = {}
for k in keys:
    vals = [getattr(s, k) for s in stats_list]
    avgs[k] = sum(vals)/len(vals)

total_wall = sum(avgs[k] for k in keys)

print("Profile at 50 agents (30 ticks, tick %d):" % sim.tick)
for k in keys:
    label = k.replace('_ms','')
    pct = 100*avgs[k]/total_wall if total_wall > 0 else 0
    print("  %-12s %7.3fms  %5.1f%%" % (label, avgs[k], pct))
print("  %-12s %7.3fms" % ("total", total_wall))
print("")
print("  alive=%d tick=%d" % (int(sim.agents.alive[:sim.agents.n_active].sum()), sim.tick))
