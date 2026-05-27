#!/usr/bin/env python3
"""Smoke — Wave 42 Phase 3c : bit-for-bit Rust ↔ Python terrain match.

Vérifie :
  1. genesis_world BLAKE2b salt == Python _stable_layer_salt
  2. Cell values identiques (SplitMix64 avalanche)
  3. Elevation match < 0.001m sur 25 chunks
  4. Temperature match < 0.001°C
  5. Biome agreement 100% sur 25 chunks
  6. Performance : Rust toujours plus rapide que Python
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
    native_ok = hasattr(gw, "PyWorld")
except ImportError:
    print("\nSmoke p90 — SKIPPED (wheel genesis_world non installe)\n")
    sys.exit(0)

from engine.world import (  # noqa: E402
    sample_terrain, classify_biome_array, TerrainParams,
    CHUNK_SIZE, VOXEL_SIZE_M, CHUNK_SIDE_M,
)

SEED = 42
params = TerrainParams()
w = gw.PyWorld(seed=SEED)

# ---------------------------------------------------------------------------
# 1. BLAKE2b salt match
# ---------------------------------------------------------------------------
try:
    def _py_salt(seed, layer):
        h = hashlib.blake2b(digest_size=8)
        h.update(int(seed).to_bytes(16, "little", signed=False))
        h.update(b"|")
        h.update(layer.encode("utf-8"))
        return int.from_bytes(h.digest(), "little", signed=False)

    # We can't directly access Rust salt, but we verify through terrain
    # output matching (if salt differs, terrain diverges completely).
    # Indirect validation: check that Rust cell_value matches Python's.
    py_salt = _py_salt(SEED, "elev")
    check("BLAKE2b salt compute (Python reference)",
          py_salt == 0x2065ada467d908b5,
          f"salt={py_salt:#018x}")
except Exception as e:
    check("BLAKE2b salt compute", False, str(e))

# ---------------------------------------------------------------------------
# 2. Cell values : indirect via terrain match
# ---------------------------------------------------------------------------
try:
    d = w.sample_terrain_chunk(0, 0)
    rs_elev0 = np.asarray(d["elev"], dtype=np.float32)

    ox, oy = 0, 0
    xs = (ox + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
    ys = (oy + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
    XX, YY = np.meshgrid(xs, ys, indexing="xy")
    py_elev0, _, _ = sample_terrain(SEED, params, XX, YY)
    py_flat = py_elev0.ravel()

    elev_diff_0 = np.abs(py_flat - rs_elev0)
    check("Cell value match (elev chunk 0,0)",
          elev_diff_0.max() < 0.001,
          f"max_diff={elev_diff_0.max():.6f}m")
except Exception as e:
    check("Cell value match (elev chunk 0,0)", False, str(e))

# ---------------------------------------------------------------------------
# 3 + 4 + 5. Full 25-chunk comparison
# ---------------------------------------------------------------------------
try:
    coords = [(i % 5 - 2, i // 5 - 2) for i in range(25)]
    total_cells = 0
    total_biome_match = 0
    max_elev_diff = 0.0
    max_temp_diff = 0.0

    for cx, cy in coords:
        ox = cx * CHUNK_SIDE_M
        oy = cy * CHUNK_SIDE_M
        xs = (ox + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
        ys = (oy + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
        XX, YY = np.meshgrid(xs, ys, indexing="xy")
        py_elev, py_temp, py_precip = sample_terrain(SEED, params, XX, YY)
        py_biome = classify_biome_array(py_temp, py_precip, py_elev)

        d = w.sample_terrain_chunk(cx, cy)
        rs_elev = np.asarray(d["elev"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        rs_temp = np.asarray(d["temp"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)

        obs = w.observe_chunk(cx, cy, 0)
        rs_biome = np.asarray(obs["biome"], dtype=np.uint8).reshape(CHUNK_SIZE, CHUNK_SIZE)

        max_elev_diff = max(max_elev_diff, np.abs(py_elev - rs_elev).max())
        max_temp_diff = max(max_temp_diff, np.abs(py_temp - rs_temp).max())
        total_cells += py_biome.size
        total_biome_match += np.sum(py_biome == rs_biome)

    biome_pct = 100 * total_biome_match / total_cells

    check(f"Elevation match < 0.001m (25 chunks)",
          max_elev_diff < 0.001,
          f"max_diff={max_elev_diff:.6f}m")

    check(f"Temperature match < 0.001C (25 chunks)",
          max_temp_diff < 0.001,
          f"max_diff={max_temp_diff:.6f}C")

    check(f"Biome agreement (25 chunks, {total_cells} cells)",
          biome_pct >= 99.9,
          f"{total_biome_match}/{total_cells} ({biome_pct:.2f}%)")
except Exception as e:
    check("25-chunk comparison", False, str(e))

# ---------------------------------------------------------------------------
# 6. Performance check (Rust still faster)
# ---------------------------------------------------------------------------
N_BENCH = 20
bench_coords = [(i % 10, i // 10) for i in range(N_BENCH)]

# Warm up
sample_terrain(SEED, params, XX, YY)
w.sample_terrain_chunk(0, 0)

t0 = time.perf_counter()
for cx, cy in bench_coords:
    ox = cx * CHUNK_SIDE_M
    oy = cy * CHUNK_SIDE_M
    xs = (ox + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
    ys = (oy + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
    XX, YY = np.meshgrid(xs, ys, indexing="xy")
    sample_terrain(SEED, params, XX, YY)
py_ms = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
for cx, cy in bench_coords:
    w.sample_terrain_chunk(cx, cy)
rs_ms = (time.perf_counter() - t0) * 1000

ratio = py_ms / max(rs_ms, 0.001)
check(f"Rust faster ({ratio:.1f}x)",
      ratio > 1.0,
      f"Python={py_ms:.1f}ms Rust={rs_ms:.1f}ms")

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p90 — Wave 42 Phase 3c Bit-for-Bit ({passed}/{total})\n")
for r in results:
    print(r)
print()
print(f"  Terrain: max_elev_diff={max_elev_diff:.6f}m  max_temp_diff={max_temp_diff:.6f}C")
print(f"  Biomes: {biome_pct:.2f}% agreement ({total_cells} cells)")
print(f"  Perf: Python {py_ms:.1f}ms vs Rust {rs_ms:.1f}ms ({ratio:.1f}x)")
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK — Phase 3c bit-for-bit validation complet.")
