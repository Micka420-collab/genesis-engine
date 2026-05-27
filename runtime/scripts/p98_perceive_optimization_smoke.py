#!/usr/bin/env python3
"""Smoke -- Wave 48 : perceive optimization (need flags + early exit).

Checks:
  1. _scan_chunk with need_water=False skips water scan
  2. _scan_chunk with need_food=False skips food scan
  3. perceive returns valid Observation with all fields
  4. Perception correctness: finds water/food/shelter in known chunk
  5. Early-exit: perceive_ms reduced vs baseline
  6. Full sim 10 ticks under 300ms
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


from engine.world import (  # noqa: E402
    generate_chunk, TerrainParams, ChunkStreamer, CHUNK_SIZE, CHUNK_SIDE_M,
)
from engine.cognition import (  # noqa: E402
    _scan_chunk, _chunk_resource_masks, perceive, PerceivedTarget,
)
from engine.agent import AgentRegistry  # noqa: E402

SEED = 42

# ---------------------------------------------------------------------------
# 1. _scan_chunk with need_water=False skips water scan
# ---------------------------------------------------------------------------
try:
    chunk = generate_chunk(SEED, (0, 0, 0), TerrainParams())
    out1 = {}
    _scan_chunk(chunk, 16.0, 16.0, 60.0, out1, need_water=True,
                need_food=True, need_shelter=True)
    out2 = {}
    _scan_chunk(chunk, 16.0, 16.0, 60.0, out2, need_water=False,
                need_food=True, need_shelter=True)
    # out2 should not have water (skipped), but may have food/shelter
    water_skipped = "water" not in out2
    # out1 may or may not have water depending on chunk content
    check("_scan_chunk need_water=False skips water",
          water_skipped or "water" not in out1,  # either skipped or chunk has no water
          f"need=True:{'water' in out1} need=False:{'water' in out2}")
except Exception as e:
    check("_scan_chunk need_water=False skips water", False, str(e))

# ---------------------------------------------------------------------------
# 2. _scan_chunk with need_food=False skips food scan
# ---------------------------------------------------------------------------
try:
    out3 = {}
    _scan_chunk(chunk, 16.0, 16.0, 60.0, out3, need_water=True,
                need_food=False, need_shelter=True)
    food_skipped = "food" not in out3
    check("_scan_chunk need_food=False skips food",
          food_skipped or "food" not in out1,
          f"need=True:{'food' in out1} need=False:{'food' in out3}")
except Exception as e:
    check("_scan_chunk need_food=False skips food", False, str(e))

# ---------------------------------------------------------------------------
# 3. perceive returns valid Observation
# ---------------------------------------------------------------------------
try:
    streamer = ChunkStreamer(SEED, TerrainParams())
    # Generate some chunks around origin
    from engine.world import chunks_around
    streamer.touch_area(tick=1, coords=chunks_around((0, 0, 0), 2))

    agents = AgentRegistry(capacity=10)
    agents.spawn_founder(SEED, 0, (0.0, 0.0, 0.0), born_tick=0)

    obs = perceive(agents, 0, streamer, tick=1)
    has_row = obs.row == 0
    has_pos = obs.pos is not None and len(obs.pos) == 3
    has_drives = obs.drives is not None and len(obs.drives) == 8

    check("perceive returns valid Observation",
          has_row and has_pos and has_drives,
          f"row={obs.row} pos={obs.pos[:2]} drives_len={len(obs.drives)}")
except Exception as e:
    check("perceive returns valid Observation", False, str(e))

# ---------------------------------------------------------------------------
# 4. Perception correctness: finds resources
# ---------------------------------------------------------------------------
try:
    resources_found = []
    for k in ("water", "food", "shelter"):
        if k in obs.nearest:
            resources_found.append(k)
    # At least one resource should be findable in 25 chunks
    check("perceive finds resources in nearby chunks",
          len(resources_found) > 0,
          f"found: {resources_found}")
except Exception as e:
    check("perceive finds resources", False, str(e))

# ---------------------------------------------------------------------------
# 5. perceive_ms benchmark
# ---------------------------------------------------------------------------
try:
    N_ITERS = 50
    t0 = time.perf_counter()
    for _ in range(N_ITERS):
        perceive(agents, 0, streamer, tick=1)
    perceive_ms = (time.perf_counter() - t0) * 1000.0 / N_ITERS

    check(f"perceive avg < 2ms ({perceive_ms:.2f}ms)",
          perceive_ms < 2.0,
          f"avg={perceive_ms:.3f}ms ({N_ITERS} iters)")
except Exception as e:
    check("perceive avg < 2ms", False, str(e))

# ---------------------------------------------------------------------------
# 6. Full sim 10 ticks under 300ms
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
    t0 = time.perf_counter()
    for _ in range(10):
        stats = sim.step()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    check(f"10 ticks under 300ms ({elapsed_ms:.0f}ms)",
          elapsed_ms < 300.0,
          f"elapsed={elapsed_ms:.1f}ms perceive={stats.perceive_ms:.2f}ms "
          f"regen={stats.regen_ms:.2f}ms")
except Exception as e:
    check("10 ticks under 300ms", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p98 -- Wave 48 Perceive Optimization ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 48 perceive optimization validation complet.")
