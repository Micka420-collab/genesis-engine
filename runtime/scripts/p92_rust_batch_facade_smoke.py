#!/usr/bin/env python3
"""Smoke — Wave 42 Phase 3f : rayon batch + Python façade.

Vérifie :
  1. sample_terrain_batch parallel (25 chunks) retourne les mêmes valeurs que séquentiel
  2. Batch faster than sequential (rayon speedup)
  3. genesis_world.py_fbm_2d() matches Python fbm_2d
  4. genesis_world.py_sample_terrain() matches Python sample_terrain
  5. genesis_world.py_layer_salt() matches Python reference
  6. sample_terrain_batch with genesis macro grid
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

import hashlib
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
    native_ok = (hasattr(gw, "PyWorld") and
                 hasattr(gw, "py_fbm_2d") and
                 hasattr(gw, "py_sample_terrain") and
                 hasattr(gw, "py_layer_salt"))
except ImportError:
    print("\nSmoke p92 — SKIPPED (wheel genesis_world non installe)\n")
    sys.exit(0)

if not native_ok:
    print("\nSmoke p92 — SKIPPED (facade functions absent — rebuild required)\n")
    sys.exit(0)

from engine.world import (  # noqa: E402
    sample_terrain, fbm_2d, TerrainParams,
    CHUNK_SIZE, VOXEL_SIZE_M, CHUNK_SIDE_M,
)

SEED = 42
w = gw.PyWorld(seed=SEED)

# ---------------------------------------------------------------------------
# 1. Batch vs sequential consistency
# ---------------------------------------------------------------------------
try:
    coords = [(i % 5 - 2, i // 5 - 2) for i in range(25)]
    # Sequential
    seq_results = []
    w.clear_cache()
    for cx, cy in coords:
        d = w.sample_terrain_chunk(cx, cy)
        seq_results.append(np.asarray(d["elev"], dtype=np.float32).copy())

    # Batch (parallel)
    w.clear_cache()
    batch = w.sample_terrain_batch(coords)
    batch_results = [np.asarray(d["elev"], dtype=np.float32) for d in batch]

    all_match = True
    max_diff = 0.0
    for i, (s, b) in enumerate(zip(seq_results, batch_results)):
        d = np.abs(s - b).max()
        max_diff = max(max_diff, d)
        if d > 0:
            all_match = False

    check("Batch vs sequential consistency (25 chunks)",
          all_match,
          f"max_diff={max_diff:.6f}")
except Exception as e:
    check("Batch vs sequential consistency", False, str(e))

# ---------------------------------------------------------------------------
# 2. Batch performance (rayon speedup)
# ---------------------------------------------------------------------------
try:
    N = 50
    bench_coords = [(i % 10 - 5, i // 10 - 5) for i in range(N)]

    # Sequential benchmark
    w.clear_cache()
    t0 = time.perf_counter()
    for cx, cy in bench_coords:
        w.sample_terrain_chunk(cx, cy)
    seq_ms = (time.perf_counter() - t0) * 1000

    # Batch benchmark
    w.clear_cache()
    t0 = time.perf_counter()
    w.sample_terrain_batch(bench_coords)
    batch_ms = (time.perf_counter() - t0) * 1000

    # Rayon should be faster or at least not slower for 50 chunks.
    # On single-core, batch won't be slower (same work).
    # On multi-core, expect 2-4× speedup.
    ratio = seq_ms / max(batch_ms, 0.001)
    check(f"Batch performance ({N} chunks, {ratio:.1f}x)",
          batch_ms <= seq_ms * 1.5,  # Allow some overhead
          f"seq={seq_ms:.1f}ms batch={batch_ms:.1f}ms ratio={ratio:.1f}x")
except Exception as e:
    check("Batch performance", False, str(e))

# ---------------------------------------------------------------------------
# 3. py_fbm_2d matches Python fbm_2d
# ---------------------------------------------------------------------------
try:
    # Test a few points
    test_points = [(1.0, 2.0), (5.5, 3.3), (100.0, 200.0), (-1.0, -3.0)]
    max_diff = 0.0
    for x, y in test_points:
        py_val = float(fbm_2d(SEED, "elev", np.float32(x), np.float32(y), 6))
        rs_val = gw.py_fbm_2d(SEED, "elev", x, y, 6, 2.0, 0.5)
        max_diff = max(max_diff, abs(py_val - rs_val))

    check("py_fbm_2d matches Python fbm_2d",
          max_diff < 0.001,
          f"max_diff={max_diff:.6f}")
except Exception as e:
    check("py_fbm_2d matches Python fbm_2d", False, str(e))

# ---------------------------------------------------------------------------
# 4. py_sample_terrain matches Python sample_terrain
# ---------------------------------------------------------------------------
try:
    params = TerrainParams()
    test_pos = [(0.25, 0.25), (16.0, 8.0), (100.0, 50.0)]
    max_elev_diff = 0.0
    max_temp_diff = 0.0
    for xm, ym in test_pos:
        x_arr = np.array([[xm]], dtype=np.float32)
        y_arr = np.array([[ym]], dtype=np.float32)
        py_e, py_t, py_p = sample_terrain(SEED, params, x_arr, y_arr)
        rs_e, rs_t, rs_p = gw.py_sample_terrain(SEED, xm, ym)
        max_elev_diff = max(max_elev_diff, abs(float(py_e[0, 0]) - rs_e))
        max_temp_diff = max(max_temp_diff, abs(float(py_t[0, 0]) - rs_t))

    check("py_sample_terrain matches Python sample_terrain",
          max_elev_diff < 0.01 and max_temp_diff < 0.01,
          f"max_elev_diff={max_elev_diff:.6f} max_temp_diff={max_temp_diff:.6f}")
except Exception as e:
    check("py_sample_terrain matches Python sample_terrain", False, str(e))

# ---------------------------------------------------------------------------
# 5. py_layer_salt matches Python reference
# ---------------------------------------------------------------------------
try:
    def _py_salt(seed, layer):
        h = hashlib.blake2b(digest_size=8)
        h.update(int(seed).to_bytes(16, "little", signed=False))
        h.update(b"|")
        h.update(layer.encode("utf-8"))
        return int.from_bytes(h.digest(), "little", signed=False)

    tests = [
        (42, "elev", 0x2065ada467d908b5),
        (42, "temp", 0xda6bfa1e6f752847),
        (42, "precip", 0xb6121c545423b9b1),
    ]
    all_ok = True
    for seed, layer, expected in tests:
        rs_salt = gw.py_layer_salt(seed, layer)
        py_salt = _py_salt(seed, layer)
        if rs_salt != expected or py_salt != expected:
            all_ok = False

    check("py_layer_salt matches Python reference",
          all_ok,
          f"elev={gw.py_layer_salt(42, 'elev'):#018x}")
except Exception as e:
    check("py_layer_salt matches Python reference", False, str(e))

# ---------------------------------------------------------------------------
# 6. Batch with genesis macro grid
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

    coords = [(i % 5, i // 5) for i in range(25)]
    batch = wg.sample_terrain_batch(coords)
    ok = (len(batch) == 25 and
          all(np.asarray(d["elev"]).shape[0] == CHUNK_SIZE * CHUNK_SIZE for d in batch))
    check("Batch with genesis macro grid (25 chunks)",
          ok,
          f"chunks={len(batch)} genesis={wg.has_genesis()}")
except Exception as e:
    check("Batch with genesis macro grid", False, str(e))

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p92 — Wave 42 Phase 3f Batch + Façade ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK — Phase 3f batch + facade validation complet.")
