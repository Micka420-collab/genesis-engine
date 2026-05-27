#!/usr/bin/env python3
"""Smoke — Wave 43 : resource computation in Rust.

Vérifie :
  1. sample_terrain_chunk returns resource arrays (stone/wood/metal/water/food)
  2. Resources have correct shape and non-negative values
  3. Resource diversity (not all zero, not all identical)
  4. Rust resource pipeline faster than Python-only path
  5. Batch path returns resources too
  6. Genesis path returns resources too
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


# ---------------------------------------------------------------------------
# 0. Import natif
# ---------------------------------------------------------------------------
try:
    import genesis_world as gw
    native_ok = hasattr(gw, "PyWorld")
except ImportError:
    print("\nSmoke p93 — SKIPPED (wheel genesis_world non installe)\n")
    sys.exit(0)

if not native_ok:
    print("\nSmoke p93 — SKIPPED (PyWorld absent)\n")
    sys.exit(0)

SEED = 42
CHUNK_SIZE = gw.CHUNK_SIZE  # 64
CHUNK_N = CHUNK_SIZE * CHUNK_SIZE  # 4096

w = gw.PyWorld(seed=SEED)

# ---------------------------------------------------------------------------
# 1. sample_terrain_chunk returns resource arrays
# ---------------------------------------------------------------------------
try:
    d = w.sample_terrain_chunk(0, 0)
    resource_keys = ["stone", "wood", "metal", "water", "food_kcal", "food_capacity"]
    has_all = all(k in d for k in resource_keys)
    check("sample_terrain_chunk returns resource arrays",
          has_all,
          f"keys={sorted(d.keys())}")
except Exception as e:
    check("sample_terrain_chunk returns resource arrays", False, str(e))

# ---------------------------------------------------------------------------
# 2. Resources have correct shape and non-negative values
# ---------------------------------------------------------------------------
try:
    d = w.sample_terrain_chunk(1, 1)
    shapes_ok = True
    nonneg_ok = True
    details = []
    for key in resource_keys:
        arr = np.asarray(d[key], dtype=np.float32)
        if arr.shape[0] != CHUNK_N:
            shapes_ok = False
            details.append(f"{key}.shape={arr.shape}")
        if arr.min() < 0:
            nonneg_ok = False
            details.append(f"{key}.min={arr.min():.3f}")
    ok = shapes_ok and nonneg_ok
    check("Resources shape + non-negative",
          ok,
          " ".join(details) if details else f"all {CHUNK_N} ok, >=0")
except Exception as e:
    check("Resources shape + non-negative", False, str(e))

# ---------------------------------------------------------------------------
# 3. Resource diversity
# ---------------------------------------------------------------------------
try:
    d = w.sample_terrain_chunk(3, 5)
    stone = np.asarray(d["stone"])
    wood = np.asarray(d["wood"])
    metal = np.asarray(d["metal"])
    water = np.asarray(d["water"])
    food = np.asarray(d["food_kcal"])

    # Stone should have variation (noise-driven)
    stone_var = stone.max() - stone.min() > 0.1
    # Some cells should have wood > 0 (for forested biomes)
    wood_any = (wood > 0).sum()
    # Food should not be all zero (some biome has NPP > 0)
    food_any = (food > 0).sum()

    ok = stone_var and food_any > 0
    check("Resource diversity (variation + non-trivial)",
          ok,
          f"stone_range={stone.max()-stone.min():.2f} wood_cells={wood_any} food_cells={food_any}")
except Exception as e:
    check("Resource diversity", False, str(e))

# ---------------------------------------------------------------------------
# 4. Rust resource pipeline faster than Python-only path
# ---------------------------------------------------------------------------
try:
    from engine.world import (
        generate_chunk, ChunkStreamer, TerrainParams,
        CHUNK_SIZE as CS, VOXEL_SIZE_M, CHUNK_SIDE_M,
    )

    N_BENCH = 20
    coords = [(i % 5 - 2, i // 5 - 2, 0) for i in range(N_BENCH)]

    # Rust path (terrain + resources in Rust, content_root in Python)
    w_bench = gw.PyWorld(seed=SEED)
    t0 = time.perf_counter()
    for cx, cy, cz in coords:
        generate_chunk(SEED, (cx, cy, cz), TerrainParams(), rust_world=w_bench)
    rust_ms = (time.perf_counter() - t0) * 1000

    # Python-only path (no Rust)
    t0 = time.perf_counter()
    for cx, cy, cz in coords:
        generate_chunk(SEED, (cx, cy, cz), TerrainParams(), rust_world=None)
    py_ms = (time.perf_counter() - t0) * 1000

    ratio = py_ms / max(rust_ms, 0.001)
    check(f"Rust resource pipeline faster ({ratio:.1f}x)",
          rust_ms < py_ms,
          f"Rust={rust_ms:.1f}ms Python={py_ms:.1f}ms ratio={ratio:.1f}x")
except Exception as e:
    check("Rust resource pipeline faster", False, str(e))

# ---------------------------------------------------------------------------
# 5. Batch path returns resources
# ---------------------------------------------------------------------------
try:
    w2 = gw.PyWorld(seed=SEED)
    batch_coords = [(i, 0) for i in range(10)]
    batch = w2.sample_terrain_batch(batch_coords)
    has_res = all("stone" in d and "wood" in d and "food_kcal" in d for d in batch)
    check("Batch path returns resources",
          has_res and len(batch) == 10,
          f"chunks={len(batch)} resources={'yes' if has_res else 'no'}")
except Exception as e:
    check("Batch path returns resources", False, str(e))

# ---------------------------------------------------------------------------
# 6. Genesis path returns resources
# ---------------------------------------------------------------------------
try:
    from engine.world_genesis import generate_world, GenesisParams, make_anchor
    from engine.macro_grid_export import export_macro_grid_bytes

    gp = GenesisParams(seed=SEED, resolution=32, map_size_km=1000.0)
    gworld = generate_world(gp)
    anchor = make_anchor(gworld)
    genm = export_macro_grid_bytes(gworld)
    ox_km, oy_km = anchor.sim_origin_macro_km

    wg = gw.PyWorld(
        seed=SEED,
        macro_grid_bytes=genm,
        sim_origin_x_km=float(ox_km),
        sim_origin_y_km=float(oy_km),
        blend=1.0,
        micro_amp_m=80.0,
        micro_amp_temp_c=1.5,
        micro_amp_precip_mm=150.0,
    )

    d = wg.sample_terrain_chunk(0, 0)
    has_res = all(k in d for k in resource_keys)
    stone_ok = np.asarray(d["stone"]).shape[0] == CHUNK_N
    check("Genesis path returns resources",
          has_res and stone_ok,
          f"genesis={wg.has_genesis()} resources={'yes' if has_res else 'no'}")
except Exception as e:
    check("Genesis path returns resources", False, str(e))

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p93 — Wave 43 Resource Pipeline ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK — Wave 43 resource pipeline validation complet.")
