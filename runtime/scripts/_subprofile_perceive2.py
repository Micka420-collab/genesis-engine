#!/usr/bin/env python3
"""Sub-profile INSIDE perceive() — find which sub-step dominates."""
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
from engine.cognition import (
    PERCEPTION_RADIUS_M, CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M,
    PerceivedTarget, Observation, DriveKind, ACT_THRESHOLD,
    _scan_chunk, _dominant_drive, world_to_chunk, chunks_around_sorted,
)
from engine.spatial import SpatialGrid

cfg = SimConfig(seed=42, founders=6, bounds_km=(0.5, 0.5),
                emergence_subsystems=False, life_emergence=False,
                knowledge_layers=False, wind_advect_agents=False)
sim = Simulation(cfg)
for _ in range(10):
    sim.step()

# Instrument perceive internals
t_drives = 0.0
t_setup = 0.0
t_chunk_loop = 0.0
t_agent_scan = 0.0
t_memory = 0.0
t_obs_create = 0.0
calls = 0
chunks_scanned = 0
ticks = 30
radius_m = PERCEPTION_RADIUS_M

for _ in range(ticks):
    sim.tick += 1
    n = sim.agents.n_active
    grid = SpatialGrid(cell_size_m=radius_m / 2.0)
    grid.rebuild(sim.agents.pos[:n, :2], sim.agents.alive[:n])
    alive_idx = np.flatnonzero(sim.agents.alive[:n])
    agents = sim.agents
    streamer = sim.streamer

    for row in alive_idx:
        row = int(row)
        calls += 1

        # 1. Drive array
        t0 = time.perf_counter()
        px, py, pz = float(agents.pos[row, 0]), float(agents.pos[row, 1]), float(agents.pos[row, 2])
        drives = np.array([agents.hunger[row], agents.thirst[row], agents.sleep[row],
                           agents.fatigue[row], agents.thermal[row], agents.pain[row],
                           agents.stress[row], agents.loneliness[row]], dtype=np.float32)
        t1 = time.perf_counter()
        t_drives += (t1 - t0)

        # 2. Setup (chunk coords, r_chunks)
        chunk_center = world_to_chunk(px, py, pz)
        r_chunks = max(1, int(math.ceil(radius_m / CHUNK_SIDE_M)))
        r_eff_sq = radius_m * radius_m
        t2 = time.perf_counter()
        t_setup += (t2 - t1)

        # 3. Chunk loop (scan)
        nearest = {}
        for coord in chunks_around_sorted(chunk_center, r_chunks):
            chunk = streamer.cache.get(coord)
            if chunk is None:
                continue
            cx0 = coord[0] * CHUNK_SIDE_M
            cy0 = coord[1] * CHUNK_SIDE_M
            cx1 = cx0 + CHUNK_SIDE_M
            cy1 = cy0 + CHUNK_SIDE_M
            dx = 0.0 if (cx0 <= px <= cx1) else (cx0 - px if px < cx0 else px - cx1)
            dy = 0.0 if (cy0 <= py <= cy1) else (cy0 - py if py < cy0 else py - cy1)
            chunk_edge_d2 = dx * dx + dy * dy
            if chunk_edge_d2 > r_eff_sq:
                continue
            _w_found = "water" in nearest
            _f_found = "food" in nearest
            _s_found = "shelter" in nearest
            if _w_found and _f_found and _s_found:
                _w_d2 = nearest["water"].distance * nearest["water"].distance
                _f_d2 = nearest["food"].distance * nearest["food"].distance
                _s_d2 = nearest["shelter"].distance * nearest["shelter"].distance
                if _w_d2 <= chunk_edge_d2 and _f_d2 <= chunk_edge_d2 and _s_d2 <= chunk_edge_d2:
                    continue
            need_w = not _w_found or (nearest["water"].distance * nearest["water"].distance > chunk_edge_d2)
            need_f = not _f_found or (nearest["food"].distance * nearest["food"].distance > chunk_edge_d2)
            need_s = not _s_found or (nearest["shelter"].distance * nearest["shelter"].distance > chunk_edge_d2)
            _scan_chunk(chunk, px, py, radius_m, nearest, sim.tick,
                        need_water=need_w, need_food=need_f, need_shelter=need_s)
            chunks_scanned += 1
        t3 = time.perf_counter()
        t_chunk_loop += (t3 - t2)

        # 4. Near-agent scan
        near_agents = []
        r2 = radius_m * radius_m
        if grid is not None and grid.n_indexed > 1:
            candidates = grid.query_disk(px, py, radius_m, exclude_row=row)
            if candidates:
                cand_arr = np.array(candidates, dtype=np.int32)
                cand_arr = cand_arr[agents.alive[cand_arr]]
                if cand_arr.size > 0:
                    diffs = agents.pos[cand_arr, :2] - np.array([px, py], dtype=np.float32)
                    d2 = (diffs ** 2).sum(axis=1)
                    mask = d2 < r2
                    in_idx = cand_arr[mask]
                    in_d2 = d2[mask]
                    order = np.argsort(in_d2)[:16]
                    for k in order:
                        j = int(in_idx[k])
                        d = float(math.sqrt(in_d2[k]))
                        near_agents.append(j)
                        if "agent" not in nearest or d < nearest["agent"].distance:
                            nearest["agent"] = PerceivedTarget("agent", float(agents.pos[j, 0]),
                                                              float(agents.pos[j, 1]), d, 1.0, other_row=j)
        t4 = time.perf_counter()
        t_agent_scan += (t4 - t3)

        # 5. Memory recall
        mem = agents.memory[row]
        if "water" not in nearest and drives[int(DriveKind.THIRST)] >= ACT_THRESHOLD and mem.known_water_locations:
            wx, wy = mem.known_water_locations[-1]
            nearest["water_remembered"] = PerceivedTarget("water", float(wx), float(wy),
                                                          float(math.hypot(wx - px, wy - py)), 1.0)
        if "food" not in nearest and drives[int(DriveKind.HUNGER)] >= ACT_THRESHOLD and mem.known_food_locations:
            fx, fy = mem.known_food_locations[-1]
            nearest["food_remembered"] = PerceivedTarget("food", float(fx), float(fy),
                                                         float(math.hypot(fx - px, fy - py)), 1.0)
        t5 = time.perf_counter()
        t_memory += (t5 - t4)

        # 6. Create Observation
        obs = Observation(row=row, pos=(px, py, pz), drives=drives,
                          vitality=float(agents.vitality[row]),
                          nearest=nearest, near_agents=near_agents,
                          dominant_drive=_dominant_drive(drives),
                          tick=sim.tick, reproduction_readiness=0.0)
        t6 = time.perf_counter()
        t_obs_create += (t6 - t5)

print(f"\nSub-profile INSIDE perceive ({ticks} ticks, {calls} calls, {chunks_scanned} scans)")
print(f"  {'Sub-step':<20s} {'Total ms':>10s} {'Per-call us':>12s} {'%':>8s}")
print("  " + "-" * 52)
grand = t_drives + t_setup + t_chunk_loop + t_agent_scan + t_memory + t_obs_create
for label, t in [("drives array", t_drives),
                 ("setup", t_setup),
                 ("chunk scan loop", t_chunk_loop),
                 ("near-agent", t_agent_scan),
                 ("memory recall", t_memory),
                 ("Observation()", t_obs_create)]:
    ms = t * 1000.0
    us = ms * 1000.0 / calls if calls > 0 else 0
    pct = t / grand * 100 if grand > 0 else 0
    print(f"  {label:<20s} {ms:>9.2f}ms {us:>10.1f}μs {pct:>7.1f}%")
print(f"  {'TOTAL':<20s} {grand*1000:.2f}ms {grand*1000*1000/calls:.1f}μs  100.0%")
print(f"  chunks_scanned/call: {chunks_scanned/calls:.1f}")
