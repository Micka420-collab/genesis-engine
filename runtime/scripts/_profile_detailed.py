#!/usr/bin/env python3
"""Detailed per-phase profile within the perceive loop."""
import sys, io, time, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
from engine.sim import Simulation, SimConfig
from engine.cognition import perceive, decide, apply_decision

cfg = SimConfig(seed=42, founders=100, bounds_km=(0.5,0.5),
                emergence_subsystems=False, life_emergence=False,
                knowledge_layers=False, wind_advect_agents=False)
sim = Simulation(cfg)
for _ in range(20):
    sim.step()

# Now run one tick manually with detailed timing
n = sim.agents.n_active
alive_idx = np.where(sim.agents.alive[:n])[0]
print("alive=%d" % len(alive_idx))

# Simulate the batch pre-computation
from engine.sim import _HAS_RUST_BATCH_NEAR, _HAS_RUST_BATCH_SCAN
from engine.cognition import PERCEPTION_RADIUS_M
from engine.world import CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M

_near_cache = None
if _HAS_RUST_BATCH_NEAR and alive_idx.size > 1:
    from genesis_world import py_batch_near_agents
    t0 = time.monotonic()
    _near_cache = py_batch_near_agents(
        sim.agents.pos[:n, :2],
        sim.agents.alive[:n].view(np.uint8),
        float(PERCEPTION_RADIUS_M))
    t_near = (time.monotonic() - t0) * 1000.0
    print("batch_near:   %.3fms" % t_near)

_resource_cache = None
if _HAS_RUST_BATCH_SCAN and alive_idx.size > 0:
    from genesis_world import py_batch_scan_resources
    _perceived_coords = sim._stream_around_agents()
    _cx_list, _cy_list = [], []
    _w_list, _f_list, _wd_list, _st_list, _ht_list = [], [], [], [], []
    for coord in _perceived_coords:
        chunk = sim.streamer.cache.get(coord)
        if chunk is None:
            continue
        _cx_list.append(coord[0])
        _cy_list.append(coord[1])
        _w_list.append(chunk.water.ravel())
        _f_list.append(chunk.food_kcal.ravel())
        _wd_list.append(chunk.wood.ravel())
        _st_list.append(chunk.stone.ravel())
        _ht_list.append(chunk.height.ravel())
    if _cx_list:
        t0 = time.monotonic()
        _resource_cache = py_batch_scan_resources(
            sim.agents.pos[:n, :2], sim.agents.alive[:n].view(np.uint8),
            _cx_list, _cy_list, _w_list, _f_list, _wd_list, _st_list, _ht_list,
            float(PERCEPTION_RADIUS_M), float(VOXEL_SIZE_M),
            float(CHUNK_SIDE_M), int(CHUNK_SIZE))
        t_scan = (time.monotonic() - t0) * 1000.0
        print("batch_scan:   %.3fms (%d chunks)" % (t_scan, len(_cx_list)))

# Per-agent detailed timing
t_perceive_total = 0.0
t_decide_total = 0.0
t_apply_total = 0.0
t_overhead_total = 0.0
N_RUNS = 3

for run in range(N_RUNS):
    for row in alive_idx:
        row = int(row)

        t0 = time.monotonic()
        _nc = _near_cache[row] if _near_cache is not None else None
        _rc = _resource_cache[row] if _resource_cache is not None else None
        t1 = time.monotonic()

        obs = perceive(sim.agents, row, sim.streamer, grid=sim._grid, tick=sim.tick,
                       near_cache=_nc, resource_cache=_rc)
        t2 = time.monotonic()

        d = decide(sim.agents, obs, sim=sim)
        t3 = time.monotonic()

        ev = apply_decision(sim.agents, row, d, sim.streamer, sim.tick)
        t4 = time.monotonic()

        t_overhead_total += (t1 - t0)
        t_perceive_total += (t2 - t1)
        t_decide_total += (t3 - t2)
        t_apply_total += (t4 - t3)

n_agents = len(alive_idx)
total_calls = n_agents * N_RUNS
print("\nPer-agent breakdown (avg of %d calls over %d agents x %d runs):" % (total_calls, n_agents, N_RUNS))
print("  overhead:  %.1f us/agent" % (t_overhead_total / total_calls * 1e6))
print("  perceive:  %.1f us/agent" % (t_perceive_total / total_calls * 1e6))
print("  decide:    %.1f us/agent" % (t_decide_total / total_calls * 1e6))
print("  apply:     %.1f us/agent" % (t_apply_total / total_calls * 1e6))
total_per = (t_overhead_total + t_perceive_total + t_decide_total + t_apply_total) / total_calls * 1e6
print("  TOTAL:     %.1f us/agent" % total_per)
print("  x %d agents = %.3f ms" % (n_agents, total_per * n_agents / 1000.0))
