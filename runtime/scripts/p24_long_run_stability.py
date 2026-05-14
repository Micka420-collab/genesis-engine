"""P24 — Long-run stability sprint (PHASE13).

Validates that a fully wired Wave 1-4 Léman world survives ~100k ticks
(~60 sim-days at drive_accel=1500) without leaking memory, drifting
determinism, or collapsing in agent population.

Methodology
-----------
1. Build a real Léman world via :class:`WorldBuilder`
   (anchor 46.510 / 6.633, size 2.0 km, founders 30, max_agents 200,
   drive_accel 1500, seed ``0xDEC0DE_42``).
2. Install ALL Wave 1-4 modules:
     - ``sim_5cd_integration.install``     (Wave 1/2 — already by builder)
     - ``sim_lift.install_lift``           (L2 vegetation/erosion — by builder)
     - ``physiology.install_physiology``   (Wave 3)
     - ``photosynthesis.install_photosynthesis``  (Wave 4)
     - ``material_aging.install_material_aging``  (Wave 4)
3. Run the sim in 5000-tick segments, up to 100k ticks (or until all
   agents are dead). Record per segment:
     - Wall-clock seconds
     - Resident-set memory MB (psutil if available, else ctypes/None)
     - sim.tick, agents.n_active, alive count
     - SHA-256 first 16 hex over (alive, pos, hunger, thirst, vitality)
     - Wave 3/4 state snapshots (physiology, photosynthesis, material_aging)
4. Stream each segment as one JSON line to
   ``runtime/journals/p24_long_run.jsonl``.
5. Print a final summary (memory delta, wall-clock curve, mean alive
   over the last 5 segments).
6. Determinism re-check: rebuild a fresh world, run 5000 ticks, compare
   segment-1 hash. Must be bit-identical.

Exit codes
----------
0 — 100k ticks reached OR all-dead detected, memory growth < 200 MB,
    determinism check passes.
1 — Any of the above fails (test, not the sim).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from engine.world_builder import WorldBuilder  # noqa: E402
from engine.physiology import (install_physiology,                 # noqa: E402
                               physiology_state)
from engine.photosynthesis import (install_photosynthesis,         # noqa: E402
                                   photosynthesis_state)
from engine.material_aging import (install_material_aging,         # noqa: E402
                                   material_aging_state)


SEED = 0xDEC0DE_42 & 0xFFFFFFFFFFFFFFFF
SEGMENT_TICKS = 5000
MAX_TICKS = 100_000
TARGET_SEGMENTS = MAX_TICKS // SEGMENT_TICKS  # 20
JOURNAL_PATH = os.path.join(ROOT, "journals", "p24_long_run.jsonl")
MEMORY_BUDGET_MB = 200.0   # max allowable growth from segment 1 to last


# ---------------------------------------------------------------------------
# Memory probe — psutil > ctypes (Win32) > None
# ---------------------------------------------------------------------------

def _memory_mb() -> Optional[float]:
    try:
        import psutil
        return float(psutil.Process(os.getpid()).memory_info().rss) / (2 ** 20)
    except Exception:
        pass
    try:  # Win32 fallback via ctypes / PSAPI
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        h = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            h, ctypes.byref(counters), counters.cb)
        if ok:
            return float(counters.WorkingSetSize) / (2 ** 20)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# World construction — same recipe for both the main run and determinism check.
# ---------------------------------------------------------------------------

def _build_world(name: str):
    """Materialise the Wave 1-4 world. Identical recipe both runs."""
    world = (WorldBuilder(name)
             .anchor(lat=46.510, lon=6.633)
             .size_km(2.0)
             .founders(30)
             .max_agents(200)
             .cultures(2)
             .drive_accel(1500.0)
             .seed(SEED)
             .with_l1_earth(True)
             .with_l2_lift(True)
             .with_5cd(True)
             .build())
    # Wave 3 + Wave 4 installs — additive, idempotent.
    install_physiology(world.sim)
    install_photosynthesis(world.sim)
    install_material_aging(world.sim)
    return world


# ---------------------------------------------------------------------------
# Snapshot hash over (alive, pos, hunger, thirst, vitality).
# ---------------------------------------------------------------------------

def _state_hash(sim) -> str:
    n = sim.agents.n_active
    if n == 0:
        return hashlib.sha256(b"empty").hexdigest()[:16]
    h = hashlib.sha256()
    h.update(sim.agents.alive[:n].tobytes())
    h.update(np.ascontiguousarray(sim.agents.pos[:n], dtype=np.float32).tobytes())
    h.update(np.ascontiguousarray(sim.agents.hunger[:n], dtype=np.float32).tobytes())
    h.update(np.ascontiguousarray(sim.agents.thirst[:n], dtype=np.float32).tobytes())
    h.update(np.ascontiguousarray(sim.agents.vitality[:n], dtype=np.float32).tobytes())
    return h.hexdigest()[:16]


def _alive_count(sim) -> int:
    n = sim.agents.n_active
    if n == 0:
        return 0
    return int(sim.agents.alive[:n].sum())


# ---------------------------------------------------------------------------
# One segment of SEGMENT_TICKS, with timing + memory + snapshot.
# ---------------------------------------------------------------------------

def _run_segment(world, seg_idx: int) -> Tuple[Dict[str, Any], bool]:
    """Run SEGMENT_TICKS ticks. Returns (record, all_dead_flag)."""
    sim = world.sim
    t0 = time.perf_counter()
    mem_before = _memory_mb()
    all_dead = False
    death_tick: Optional[int] = None
    for _ in range(SEGMENT_TICKS):
        sim.step()
        if _alive_count(sim) == 0 and sim.agents.n_active > 0:
            # All spawned-but-now-dead — extinction.
            all_dead = True
            death_tick = int(sim.tick)
            break
    wall_s = time.perf_counter() - t0
    mem_after = _memory_mb()
    h = _state_hash(sim)
    alive = _alive_count(sim)

    # Wave 3/4 snapshots — defensive copies (floats only, JSON-safe).
    physio = physiology_state(sim) or {}
    photo = photosynthesis_state(sim) or {}
    aging = material_aging_state(sim) or {}

    rec = {
        "segment": int(seg_idx),
        "tick": int(sim.tick),
        "wall_s": round(wall_s, 3),
        "mem_mb_before": (None if mem_before is None
                          else round(mem_before, 1)),
        "mem_mb_after": (None if mem_after is None
                         else round(mem_after, 1)),
        "mem_delta_mb": (None if (mem_before is None or mem_after is None)
                         else round(mem_after - mem_before, 2)),
        "n_active": int(sim.agents.n_active),
        "alive": alive,
        "hash_16": h,
        "all_dead": bool(all_dead),
        "death_tick": death_tick,
        "physiology": _slim(physio),
        "photosynthesis": _slim(photo),
        "material_aging": _slim(aging),
    }
    return rec, all_dead


def _slim(d: Dict[str, Any]) -> Dict[str, Any]:
    """Drop nested non-JSON-friendly values; keep scalars + small dicts."""
    if not isinstance(d, dict):
        return {}
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, (int, float, str, bool)) or v is None:
            out[k] = v
        elif isinstance(v, dict):
            sub: Dict[str, Any] = {}
            for kk, vv in v.items():
                if isinstance(vv, (int, float, str, bool)) or vv is None:
                    sub[kk] = vv
            out[k] = sub
        elif isinstance(v, list):
            # Keep small numeric/string lists; truncate for compactness.
            if len(v) <= 20 and all(isinstance(x, (int, float, str, bool))
                                    for x in v):
                out[k] = v
    return out


# ---------------------------------------------------------------------------
# Main: the long run + determinism re-check.
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 78)
    print("P24 — Wave 1-4 long-run stability  (100k ticks, 5000/seg)")
    print("=" * 78)
    print(f"  seed             = {hex(SEED)}")
    print(f"  segment ticks    = {SEGMENT_TICKS}")
    print(f"  target ticks     = {MAX_TICKS}")
    print(f"  journal          = {JOURNAL_PATH}")
    print(f"  memory budget    = {MEMORY_BUDGET_MB:.0f} MB delta")
    print()

    # Reset journal file (line-oriented).
    os.makedirs(os.path.dirname(JOURNAL_PATH), exist_ok=True)
    if os.path.exists(JOURNAL_PATH):
        os.remove(JOURNAL_PATH)

    # ------------------------------------------------------------------
    # Phase A — build the world.
    # ------------------------------------------------------------------
    print("[build] Wave 1-4 Léman world ...", flush=True)
    t_build = time.perf_counter()
    world = _build_world("p24_long_run")
    print(f"[build] done in {time.perf_counter() - t_build:.2f}s, "
          f"spawned={world.n_spawned} alive={world.n_alive}",
          flush=True)
    sys.stdout.flush()

    # ------------------------------------------------------------------
    # Phase B — run segments until target or extinction.
    # ------------------------------------------------------------------
    records: List[Dict[str, Any]] = []
    stop_reason = "target-reached"
    first_segment_hash: Optional[str] = None

    overall_t0 = time.perf_counter()
    for seg in range(1, TARGET_SEGMENTS + 1):
        rec, all_dead = _run_segment(world, seg)
        records.append(rec)
        if first_segment_hash is None:
            first_segment_hash = rec["hash_16"]

        elapsed_total = time.perf_counter() - overall_t0
        print(f"[seg {seg:02d}/{TARGET_SEGMENTS}] "
              f"tick={rec['tick']:>6d}  wall={rec['wall_s']:>7.2f}s  "
              f"mem={rec['mem_mb_after']}  "
              f"alive={rec['alive']:>3d}/{rec['n_active']:>3d}  "
              f"hash={rec['hash_16']}  "
              f"cum={elapsed_total/60.0:.1f}min",
              flush=True)
        # Append JSONL.
        with open(JOURNAL_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        if all_dead:
            stop_reason = f"all-dead@tick={rec['death_tick']}"
            print(f"[stop] all agents dead at tick {rec['death_tick']}",
                  flush=True)
            break

    total_wall_s = time.perf_counter() - overall_t0
    final_tick = records[-1]["tick"] if records else 0

    # ------------------------------------------------------------------
    # Phase C — summary metrics.
    # ------------------------------------------------------------------
    print()
    print("-" * 78)
    print("[summary]")
    print(f"  stop reason          = {stop_reason}")
    print(f"  final tick           = {final_tick}")
    print(f"  total wall-clock     = {total_wall_s:.1f}s "
          f"({total_wall_s / 60.0:.2f} min)")
    print(f"  segments completed   = {len(records)} / {TARGET_SEGMENTS}")

    # Memory growth
    mem0 = records[0].get("mem_mb_after")
    mem_last = records[-1].get("mem_mb_after")
    mem_delta = (None if (mem0 is None or mem_last is None)
                 else mem_last - mem0)
    if mem0 is not None and mem_last is not None:
        print(f"  memory seg1 / seg{len(records)}      = "
              f"{mem0:.1f} MB / {mem_last:.1f} MB  "
              f"(Δ {mem_delta:+.1f} MB)")
    else:
        print(f"  memory probe unavailable")

    # Wall-clock per segment trajectory
    walls = [r["wall_s"] for r in records]
    print(f"  wall/seg first / mid / last  = "
          f"{walls[0]:.2f}s / {walls[len(walls)//2]:.2f}s / {walls[-1]:.2f}s")
    print(f"  wall/seg mean / max          = "
          f"{sum(walls)/len(walls):.2f}s / {max(walls):.2f}s")

    # Slowdown ratio: avg of last 3 / first 3
    if len(walls) >= 6:
        first_block = sum(walls[:3]) / 3.0
        last_block = sum(walls[-3:]) / 3.0
        slowdown = last_block / max(first_block, 1e-6)
        print(f"  perf slowdown ratio  = {slowdown:.3f}x "
              f"(last3 {last_block:.2f}s / first3 {first_block:.2f}s)")
    else:
        slowdown = 1.0

    # Mean alive over last 5 segments
    last5 = records[-5:]
    mean_alive_last5 = sum(r["alive"] for r in last5) / max(len(last5), 1)
    print(f"  mean alive (last {len(last5)} seg) = {mean_alive_last5:.2f}")

    # ------------------------------------------------------------------
    # Phase D — determinism re-check (fresh world, 5000 ticks).
    # ------------------------------------------------------------------
    print()
    print("-" * 78)
    print("[determinism] rebuilding fresh world for re-check ...",
          flush=True)
    t_det = time.perf_counter()
    world2 = _build_world("p24_det_check")
    sim2 = world2.sim
    for _ in range(SEGMENT_TICKS):
        sim2.step()
    repeat_hash = _state_hash(sim2)
    det_wall = time.perf_counter() - t_det
    det_match = (repeat_hash == first_segment_hash)
    print(f"[determinism] first run seg-1 hash : {first_segment_hash}")
    print(f"[determinism] repeat run seg-1 hash: {repeat_hash}")
    print(f"[determinism] match = {det_match}  ({det_wall:.1f}s)")

    # ------------------------------------------------------------------
    # Phase E — pass/fail.
    # ------------------------------------------------------------------
    print()
    print("-" * 78)
    failures = []
    target_reached = (final_tick >= MAX_TICKS)
    all_dead_clean = stop_reason.startswith("all-dead@")
    if not (target_reached or all_dead_clean):
        failures.append(f"stopped prematurely: {stop_reason}, "
                        f"tick={final_tick}/{MAX_TICKS}")
    if mem_delta is not None and abs(mem_delta) > MEMORY_BUDGET_MB:
        failures.append(f"memory grew {mem_delta:+.1f} MB > "
                        f"budget {MEMORY_BUDGET_MB:.0f} MB")
    if not det_match:
        failures.append("determinism re-check FAILED (hash mismatch)")

    if not failures:
        print("[result] PASS — 100k ticks survived (or graceful extinction)")
        print(f"         memory growth within budget, determinism preserved.")
        return 0
    print("[result] FAIL")
    for f in failures:
        print(f"   - {f}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[abort] interrupted by user", flush=True)
        sys.exit(2)
    except Exception:
        traceback.print_exc()
        sys.exit(3)
