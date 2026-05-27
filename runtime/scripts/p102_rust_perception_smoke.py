#!/usr/bin/env python3
"""Smoke -- Wave 52 : Rust perception (_scan_chunk in Rust).

Checks:
  1. Rust scan_chunk available and imported
  2. Rust scan finds same resources as Python scan
  3. perceive returns valid Observation with Rust backend
  4. perceive_ms < 1ms (Rust: ~0.59ms vs Python 1.02ms)
  5. Total sim tick < 3ms
  6. Overall 10 ticks under 150ms
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


SEED = 42

# ---------------------------------------------------------------------------
# 1. Rust scan_chunk available
# ---------------------------------------------------------------------------
try:
    from engine.cognition import _HAS_RUST_SCAN
    check("Rust scan_chunk imported",
          _HAS_RUST_SCAN,
          f"_HAS_RUST_SCAN={_HAS_RUST_SCAN}")
except Exception as e:
    check("Rust scan_chunk imported", False, str(e))

# ---------------------------------------------------------------------------
# 2. Rust scan finds same resources as Python scan
# ---------------------------------------------------------------------------
try:
    from engine.world import generate_chunk, TerrainParams, CHUNK_SIDE_M, VOXEL_SIZE_M
    from engine.cognition import (
        _scan_chunk_rust, _scan_chunk_py, PerceivedTarget,
    )

    chunk = generate_chunk(SEED, (0, 0, 0), TerrainParams())
    px, py_ = 10.0, 10.0
    radius = 60.0

    # Python scan
    out_py = {}
    _scan_chunk_py(chunk, px, py_, radius, out_py, True, True, True)

    # Rust scan
    out_rs = {}
    _scan_chunk_rust(chunk, px, py_, radius, out_rs, True, True, True)

    # Compare: same resource types found
    py_keys = set(out_py.keys())
    rs_keys = set(out_rs.keys())
    same_types = py_keys == rs_keys

    # Compare distances (allow small tolerance for float differences)
    dist_ok = True
    max_diff = 0.0
    for k in py_keys & rs_keys:
        d_py = out_py[k].distance
        d_rs = out_rs[k].distance
        diff = abs(d_py - d_rs)
        max_diff = max(max_diff, diff)
        if diff > 0.5:  # allow 0.5m tolerance for different argmin tie-breaking
            dist_ok = False

    check("Rust scan matches Python scan",
          same_types and dist_ok,
          f"py_keys={py_keys} rs_keys={rs_keys} max_dist_diff={max_diff:.4f}")
except Exception as e:
    check("Rust scan matches Python scan", False, str(e))

# ---------------------------------------------------------------------------
# 3. perceive returns valid Observation
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

    is_obs = isinstance(obs, Observation)
    has_resources = len(obs.nearest) > 0
    resource_types = list(obs.nearest.keys())

    check("perceive with Rust backend returns valid Observation",
          is_obs and has_resources,
          f"nearest_keys={resource_types}")
except Exception as e:
    check("perceive with Rust backend", False, str(e))

# ---------------------------------------------------------------------------
# 4. perceive_ms < 1ms
# ---------------------------------------------------------------------------
try:
    sim2 = Simulation(cfg)
    for _ in range(5):
        sim2.step()

    perceive_times = []
    for _ in range(10):
        stats = sim2.step()
        perceive_times.append(stats.perceive_ms)
    avg_perceive = sum(perceive_times) / len(perceive_times)

    check(f"perceive_ms < 1ms ({avg_perceive:.2f}ms)",
          avg_perceive < 1.0,
          f"avg={avg_perceive:.2f}ms (Rust backend)")
except Exception as e:
    check("perceive_ms < 1ms", False, str(e))

# ---------------------------------------------------------------------------
# 5. Total tick < 3ms
# ---------------------------------------------------------------------------
try:
    tick_times = []
    for _ in range(10):
        stats = sim2.step()
        tick_times.append(stats.last_tick_ms)
    avg_tick = sum(tick_times) / len(tick_times)

    check(f"Sim tick < 3ms ({avg_tick:.2f}ms)",
          avg_tick < 3.0,
          f"stream={stats.stream_ms:.2f} perceive={stats.perceive_ms:.2f} regen={stats.regen_ms:.2f}")
except Exception as e:
    check("Sim tick < 3ms", False, str(e))

# ---------------------------------------------------------------------------
# 6. 10 ticks under 150ms
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
    check("10 ticks under 150ms", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p102 -- Wave 52 Rust Perception ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 52 Rust perception validation complet.")
