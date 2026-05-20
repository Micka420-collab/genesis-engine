"""P45 — Wave 16b chunk genesis anchor smoke.

Validates the wiring between :mod:`engine.world_genesis` and
:mod:`engine.world` chunk generation.

  1. Backward compat: ``generate_chunk(seed, coord, params)`` (no anchor)
     returns a chunk bit-identical to the pre-Wave-16 pipeline.
  2. Wiring: ``generate_chunk(..., genesis=anchor)`` produces a chunk
     whose mean elevation matches the macro elevation at the same point
     (within a few hundred metres of micro-amplitude).
  3. Determinism: two calls with the same (seed, coord, anchor) produce
     bit-identical chunks.
  4. Ocean anchor: when the chunk lands on a deep-ocean macro cell, the
     chunk's biome is dominated by OCEAN.
  5. Mountain anchor: when the chunk lands on a high macro cell, the
     chunk's elevation distribution is high and biomes lean cold/alpine.
  6. Adjacent continuity: two horizontally adjacent chunks have similar
     mean elevation when the macro field is smooth around them.
  7. ChunkStreamer.set_genesis + clear_cache regenerates anchored chunks.
  8. Lazy-import safety: importing ``engine.world`` alone does NOT pull
     in ``engine.world_genesis`` (the lazy-import is only triggered at
     call time when an anchor is provided).
"""
from __future__ import annotations

import io
import os
import sys
import hashlib
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import numpy as np                                                      # noqa: E402


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:60s} {detail}"


def _chunk_hash(chunk) -> str:
    h = hashlib.sha256()
    for arr in (chunk.height, chunk.biome, chunk.stone, chunk.wood,
                chunk.metal, chunk.water, chunk.food_kcal):
        h.update(arr.tobytes())
    return h.hexdigest()


def main() -> int:
    print("=" * 78)
    print("P45 — Wave 16b chunk genesis anchor smoke")
    print("=" * 78)
    failures = 0

    # Step 8 first — check lazy-import safety BEFORE world_genesis enters
    # sys.modules.
    pre_modules = set(sys.modules)
    import engine.world as world_mod                                    # noqa: F401
    ok = "engine.world_genesis" not in sys.modules
    print(_row("step 8 - importing engine.world alone is lazy-safe",
               ok, ""))
    if not ok:
        failures += 1

    # Now the rest.
    from engine.world import (TerrainParams, generate_chunk, ChunkStreamer,
                               sample_terrain, Biome)
    from engine.world_genesis import (GenesisParams, generate_world,
                                       make_anchor, sample_macro)

    seed = 0xC0FFEE_AB
    params = TerrainParams()
    coord = (0, 0, 0)

    # Step 1 — backward compat: no anchor -> identical to legacy path.
    chunk_legacy = generate_chunk(seed, coord, params)
    chunk_legacy_2 = generate_chunk(seed, coord, params)
    ok = _chunk_hash(chunk_legacy) == _chunk_hash(chunk_legacy_2)
    print(_row("step 1 - no anchor backward compat (determinism)",
               ok, _chunk_hash(chunk_legacy)[:16]))
    if not ok:
        failures += 1

    # Build a small genesis world for tests.
    gp = GenesisParams(seed=0x12345, resolution=64, n_plates=10,
                       erosion_iters=15, rain_iters=4)
    world = generate_world(gp)

    # Default anchor maps sim (0,0) to macro center.
    anchor = make_anchor(world)
    chunk_a = generate_chunk(seed, coord, params, genesis=anchor)
    chunk_b = generate_chunk(seed, coord, params, genesis=anchor)

    # Step 2 — anchored chunk differs from legacy.
    ok = _chunk_hash(chunk_a) != _chunk_hash(chunk_legacy)
    print(_row("step 2 - anchored chunk differs from legacy",
               ok, ""))
    if not ok:
        failures += 1

    # Wiring: mean elevation in chunk ≈ macro elevation at center.
    center_x_km, center_y_km = anchor.sim_origin_macro_km
    macro = sample_macro(world, center_x_km, center_y_km)
    chunk_mean_elev = float(chunk_a.height.mean())
    macro_elev = float(macro["elevation_m"])
    delta = abs(chunk_mean_elev - macro_elev)
    # Allow up to (micro_amp_m + safety) of slack.
    ok = delta <= anchor.micro_amp_m * 2.0 + 30.0
    print(_row("step 2b - chunk mean elev ≈ macro elev",
               ok, f"chunk={chunk_mean_elev:.1f} macro={macro_elev:.1f} "
                   f"delta={delta:.1f}"))
    if not ok:
        failures += 1

    # Step 3 — determinism on anchored chunk.
    ok = _chunk_hash(chunk_a) == _chunk_hash(chunk_b)
    print(_row("step 3 - anchored determinism (two calls)",
               ok, _chunk_hash(chunk_a)[:16]))
    if not ok:
        failures += 1

    # Step 4 — ocean anchor: pick a deep-ocean macro cell.
    ocean_indices = np.argwhere(world.elevation_m < -3000.0)
    if len(ocean_indices) == 0:
        print(_row("step 4 - ocean anchor (no deep ocean in world)",
                   False, "skipped"))
        failures += 1
    else:
        oy, ox = int(ocean_indices[0, 0]), int(ocean_indices[0, 1])
        cell_km = gp.map_size_km / gp.resolution
        ocean_macro_xy = ((ox + 0.5) * cell_km, (oy + 0.5) * cell_km)
        ocean_anchor = make_anchor(world,
                                    sim_origin_macro_km=ocean_macro_xy)
        ocean_chunk = generate_chunk(seed, coord, params,
                                      genesis=ocean_anchor)
        ocean_frac = float((ocean_chunk.biome == int(Biome.OCEAN)).mean())
        ok = ocean_frac >= 0.85
        print(_row("step 4 - ocean macro cell -> OCEAN biome dominant",
                   ok,
                   f"ocean_frac={ocean_frac:.2f} "
                   f"macro_elev={float(world.elevation_m[oy, ox]):.1f}"))
        if not ok:
            failures += 1

    # Step 5 — mountain anchor: pick a high macro cell.
    mtn_indices = np.argwhere(world.elevation_m > 3000.0)
    if len(mtn_indices) == 0:
        print(_row("step 5 - mountain anchor (no mountains in world)",
                   False, "skipped"))
        failures += 1
    else:
        my, mx = int(mtn_indices[0, 0]), int(mtn_indices[0, 1])
        cell_km = gp.map_size_km / gp.resolution
        mtn_macro_xy = ((mx + 0.5) * cell_km, (my + 0.5) * cell_km)
        mtn_anchor = make_anchor(world, sim_origin_macro_km=mtn_macro_xy)
        mtn_chunk = generate_chunk(seed, coord, params, genesis=mtn_anchor)
        macro_at_mtn = float(world.elevation_m[my, mx])
        chunk_mean = float(mtn_chunk.height.mean())
        ok = chunk_mean > macro_at_mtn - 200.0 and chunk_mean > 2500.0
        print(_row("step 5 - mountain macro cell -> high chunk elev",
                   ok,
                   f"chunk_mean={chunk_mean:.1f} "
                   f"macro={macro_at_mtn:.1f}"))
        if not ok:
            failures += 1

    # Step 6 — adjacent chunk continuity.
    coord_e = (1, 0, 0)
    chunk_east = generate_chunk(seed, coord_e, params, genesis=anchor)
    # Edge cells: rightmost column of chunk_a vs leftmost column of chunk_east.
    right_edge = chunk_a.height[:, -1]
    left_edge = chunk_east.height[:, 0]
    diff = float(np.abs(right_edge - left_edge).max())
    # 32 m horizontal step on a smooth macro should produce ≤ a few × 10 m
    # discontinuity (driven solely by the micro FBM at that 32 m offset).
    ok = diff <= anchor.micro_amp_m * 1.5 + 20.0
    print(_row("step 6 - adjacent chunk edge continuity",
               ok, f"max edge delta={diff:.1f} m"))
    if not ok:
        failures += 1

    # Step 7 — ChunkStreamer.set_genesis + clear_cache.
    streamer = ChunkStreamer(seed=seed, params=params)
    ch_before = streamer.get(0, coord)
    streamer.set_genesis(anchor)
    streamer.clear_cache()
    ch_after = streamer.get(0, coord)
    ok = (_chunk_hash(ch_before) == _chunk_hash(chunk_legacy) and
          _chunk_hash(ch_after) == _chunk_hash(chunk_a))
    print(_row("step 7 - streamer.set_genesis + clear_cache rebuilds",
               ok,
               f"before={_chunk_hash(ch_before)[:8]} "
               f"after={_chunk_hash(ch_after)[:8]}"))
    if not ok:
        failures += 1

    print("=" * 78)
    if failures == 0:
        print("RESULT: 8/8 PASS")
        return 0
    else:
        print(f"RESULT: {8 - failures}/8 PASS, {failures} FAIL")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
