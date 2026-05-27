#!/usr/bin/env python3
"""Smoke -- Wave 45 : adaptive streaming (sorted chunks, budget, stats).

Checks:
  1. chunks_around_sorted returns center-first spiral order
  2. ChunkStreamer.touch_area with max_new budget limits generation
  3. ChunkStreamer.stats() returns valid metrics
  4. Cache hits tracked correctly on repeated access
  5. GC eviction updates stats
  6. Sorted loading is faster for nearby-first access pattern
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
    chunks_around, chunks_around_sorted, ChunkStreamer,
    TerrainParams, CHUNK_SIZE,
)

SEED = 42

# ---------------------------------------------------------------------------
# 1. chunks_around_sorted returns center-first spiral order
# ---------------------------------------------------------------------------
try:
    center = (5, 5, 0)
    radius = 3
    sorted_chunks = chunks_around_sorted(center, radius)
    unsorted_chunks = chunks_around(center, radius)

    # Same set of chunks
    same_set = set(sorted_chunks) == set(unsorted_chunks)
    # First chunk is center
    center_first = sorted_chunks[0] == center
    # Distances are non-decreasing (Chebyshev)
    dists = [max(abs(c[0] - center[0]), abs(c[1] - center[1])) for c in sorted_chunks]
    monotonic = all(dists[i] <= dists[i+1] for i in range(len(dists) - 1))

    check("chunks_around_sorted: center-first spiral order",
          same_set and center_first and monotonic,
          f"same_set={same_set} center_first={center_first} monotonic={monotonic} n={len(sorted_chunks)}")
except Exception as e:
    check("chunks_around_sorted: center-first spiral order", False, str(e))

# ---------------------------------------------------------------------------
# 2. touch_area with max_new budget limits generation
# ---------------------------------------------------------------------------
try:
    streamer = ChunkStreamer(SEED, TerrainParams())
    coords = chunks_around_sorted((0, 0, 0), 3)  # 49 chunks
    # Budget: only generate 10 new chunks
    generated = streamer.touch_area(tick=1, coords=coords, max_new=10)
    cache_size = len(streamer.cache)

    check("touch_area max_new=10 limits generation",
          generated == 10 and cache_size == 10,
          f"generated={generated} cache_size={cache_size}")
except Exception as e:
    check("touch_area max_new=10 limits generation", False, str(e))

# ---------------------------------------------------------------------------
# 3. stats() returns valid metrics after generation
# ---------------------------------------------------------------------------
try:
    s = streamer.stats()
    has_keys = all(k in s for k in [
        "cache_size", "hits", "misses", "hit_rate",
        "generated", "avg_gen_ms", "total_gen_ms",
        "batch_calls", "gc_evicted"])
    valid_counts = (s["generated"] == 10 and
                    s["misses"] == 10 and
                    s["cache_size"] == 10 and
                    s["avg_gen_ms"] >= 0)

    check("stats() returns valid metrics",
          has_keys and valid_counts,
          f"gen={s['generated']} misses={s['misses']} avg_ms={s['avg_gen_ms']:.2f}")
except Exception as e:
    check("stats() returns valid metrics", False, str(e))

# ---------------------------------------------------------------------------
# 4. Cache hits tracked correctly on repeated access
# ---------------------------------------------------------------------------
try:
    streamer2 = ChunkStreamer(SEED, TerrainParams())
    coords25 = chunks_around_sorted((0, 0, 0), 2)  # 25 chunks
    # First pass: all misses
    streamer2.touch_area(tick=1, coords=coords25)
    # Second pass: all hits
    streamer2.touch_area(tick=2, coords=coords25)
    s2 = streamer2.stats()
    # Should have 25 misses (first pass) + 25 hits (second pass)
    # Also individual .get() should track
    _ = streamer2.get(3, (0, 0, 0))  # hit
    s2 = streamer2.stats()
    hits_ok = s2["hits"] == 26  # 25 from second touch_area + 1 from get
    misses_ok = s2["misses"] == 25

    check("Cache hits tracked (touch_area + get)",
          hits_ok and misses_ok,
          f"hits={s2['hits']} misses={s2['misses']} hit_rate={s2['hit_rate']}")
except Exception as e:
    check("Cache hits tracked (touch_area + get)", False, str(e))

# ---------------------------------------------------------------------------
# 5. GC eviction updates stats
# ---------------------------------------------------------------------------
try:
    streamer3 = ChunkStreamer(SEED, TerrainParams(), keep_alive_ticks=5)
    coords9 = chunks_around_sorted((0, 0, 0), 1)  # 9 chunks
    streamer3.touch_area(tick=1, coords=coords9)
    # Advance tick far enough to trigger GC
    evicted = streamer3.gc(tick=100)
    s3 = streamer3.stats()
    gc_ok = s3["gc_evicted"] == evicted and evicted == 9
    cache_empty = s3["cache_size"] == 0

    check("GC eviction updates stats",
          gc_ok and cache_empty,
          f"evicted={evicted} gc_evicted={s3['gc_evicted']} cache_size={s3['cache_size']}")
except Exception as e:
    check("GC eviction updates stats", False, str(e))

# ---------------------------------------------------------------------------
# 6. Sorted loading prioritizes nearby chunks
# ---------------------------------------------------------------------------
try:
    # Verify that with a budget, sorted loading produces the closest chunks
    streamer4 = ChunkStreamer(SEED, TerrainParams())
    center = (10, 10, 0)
    sorted_coords = chunks_around_sorted(center, 4)  # 81 chunks
    # Budget: only 9 chunks (the 3x3 center)
    streamer4.touch_area(tick=1, coords=sorted_coords, max_new=9)

    # All 9 generated chunks should be within Chebyshev distance 1 of center
    cached = set(streamer4.cache.keys())
    max_dist = max(max(abs(c[0] - center[0]), abs(c[1] - center[1])) for c in cached)
    all_close = max_dist <= 1  # 3x3 = 9 chunks, all within distance 1

    check("Sorted + budget loads closest chunks first",
          len(cached) == 9 and all_close,
          f"cached={len(cached)} max_dist={max_dist}")
except Exception as e:
    check("Sorted + budget loads closest chunks first", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p95 -- Wave 45 Adaptive Streaming ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 45 adaptive streaming validation complet.")
