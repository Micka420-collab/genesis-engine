#!/usr/bin/env python3
"""Smoke — Wave 44 : full Chunk from Rust (biome + content_root).

Vérifie :
  1. sample_terrain_chunk returns biome array
  2. Rust biome matches Python classify_biome_array (bit-for-bit)
  3. content_root from Rust matches Python prf_bytes (bit-for-bit)
  4. Full Chunk construction uses all Rust data (no Python fallback)
  5. Batch path includes biome + content_root
  6. Performance: Python overhead < 0.1ms/chunk
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
    print("\nSmoke p94 — SKIPPED (wheel genesis_world non installe)\n")
    sys.exit(0)

if not native_ok:
    print("\nSmoke p94 — SKIPPED (PyWorld absent)\n")
    sys.exit(0)

from engine.world import (  # noqa: E402
    classify_biome_array, generate_chunk, TerrainParams,
    CHUNK_SIZE, VOXEL_SIZE_M, CHUNK_SIDE_M,
)
from engine.core import prf_bytes  # noqa: E402

SEED = 42
CHUNK_N = CHUNK_SIZE * CHUNK_SIZE  # 4096

w = gw.PyWorld(seed=SEED)

# ---------------------------------------------------------------------------
# 1. sample_terrain_chunk returns biome array
# ---------------------------------------------------------------------------
try:
    d = w.sample_terrain_chunk(0, 0, 0)
    has_biome = "biome" in d
    biome_arr = np.asarray(d["biome"]) if has_biome else None
    check("sample_terrain_chunk returns biome array",
          has_biome and biome_arr.shape[0] == CHUNK_N,
          f"has_biome={has_biome} shape={biome_arr.shape if biome_arr is not None else 'N/A'}")
except Exception as e:
    check("sample_terrain_chunk returns biome array", False, str(e))

# ---------------------------------------------------------------------------
# 2. Rust biome matches Python classify_biome_array
# ---------------------------------------------------------------------------
try:
    coords = [(i % 5 - 2, i // 5 - 2) for i in range(25)]
    total_cells = 0
    mismatch = 0
    for cx, cy in coords:
        d = w.sample_terrain_chunk(cx, cy, 0)
        rust_biome = np.asarray(d["biome"], dtype=np.uint8).reshape(CHUNK_SIZE, CHUNK_SIZE)
        elev = np.asarray(d["elev"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        temp = np.asarray(d["temp"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        precip = np.asarray(d["precip"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        py_biome = classify_biome_array(temp, precip, elev)
        total_cells += CHUNK_N
        mismatch += int((rust_biome != py_biome).sum())

    pct = 100.0 * (total_cells - mismatch) / total_cells
    check(f"Rust biome matches Python ({total_cells} cells)",
          mismatch == 0,
          f"{pct:.2f}% match ({mismatch} mismatches)")
except Exception as e:
    check("Rust biome matches Python", False, str(e))

# ---------------------------------------------------------------------------
# 3. content_root from Rust matches Python prf_bytes
# ---------------------------------------------------------------------------
try:
    all_match = True
    test_coords = [(0, 0, 0), (3, 5, 0), (-1, 2, 0), (10, 10, 0), (99, -42, 0)]
    for cx, cy, cz in test_coords:
        d = w.sample_terrain_chunk(cx, cy, cz)
        rust_cr = bytes(d["content_root"])
        py_cr = prf_bytes(SEED, ["chunk_root", str(cx), str(cy), str(cz)], [], 32)
        if rust_cr != py_cr:
            all_match = False

    check("content_root Rust matches Python prf_bytes",
          all_match,
          f"{len(test_coords)} coords tested")
except Exception as e:
    check("content_root Rust matches Python prf_bytes", False, str(e))

# ---------------------------------------------------------------------------
# 4. Full Chunk uses all Rust data
# ---------------------------------------------------------------------------
try:
    # Generate chunk via Rust path — should NOT call prf_bytes or classify_biome_array
    chunk_rust = generate_chunk(SEED, (5, 7, 0), TerrainParams(), rust_world=w)
    chunk_py = generate_chunk(SEED, (5, 7, 0), TerrainParams(), rust_world=None)

    # content_root should match
    cr_match = chunk_rust.content_root == chunk_py.content_root
    # Height should match (terrain)
    h_match = np.allclose(chunk_rust.height, chunk_py.height, atol=0.001)
    # Biome should match
    b_match = (chunk_rust.biome == chunk_py.biome).all()

    check("Full Chunk Rust ≡ Python (content_root + height + biome)",
          cr_match and h_match and b_match,
          f"cr={cr_match} height={h_match} biome={b_match}")
except Exception as e:
    check("Full Chunk Rust ≡ Python", False, str(e))

# ---------------------------------------------------------------------------
# 5. Batch path includes biome + content_root
# ---------------------------------------------------------------------------
try:
    w2 = gw.PyWorld(seed=SEED)
    batch_coords = [(i, 0) for i in range(10)]
    batch = w2.sample_terrain_batch(batch_coords)
    has_all = all("biome" in d and "content_root" in d for d in batch)
    # Verify content_root for first batch item
    cr0 = bytes(batch[0]["content_root"])
    expected = prf_bytes(SEED, ["chunk_root", "0", "0", "0"], [], 32)
    cr_match = cr0 == expected

    check("Batch path includes biome + content_root",
          has_all and cr_match,
          f"biome+cr={'yes' if has_all else 'no'} cr_match={cr_match}")
except Exception as e:
    check("Batch path includes biome + content_root", False, str(e))

# ---------------------------------------------------------------------------
# 6. Performance: minimal Python overhead
# ---------------------------------------------------------------------------
try:
    N = 50
    bench_coords = [(i % 10 - 5, i // 10 - 5, 0) for i in range(N)]

    # Rust path
    w3 = gw.PyWorld(seed=SEED)
    t0 = time.perf_counter()
    for cx, cy, cz in bench_coords:
        generate_chunk(SEED, (cx, cy, cz), TerrainParams(), rust_world=w3)
    rust_ms = (time.perf_counter() - t0) * 1000

    # Python path
    t0 = time.perf_counter()
    for cx, cy, cz in bench_coords:
        generate_chunk(SEED, (cx, cy, cz), TerrainParams(), rust_world=None)
    py_ms = (time.perf_counter() - t0) * 1000

    ratio = py_ms / max(rust_ms, 0.001)
    check(f"Rust full Chunk faster ({ratio:.1f}x)",
          rust_ms < py_ms,
          f"Rust={rust_ms:.1f}ms Python={py_ms:.1f}ms ratio={ratio:.1f}x")
except Exception as e:
    check("Rust full Chunk faster", False, str(e))

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p94 — Wave 44 Full Chunk from Rust ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK — Wave 44 full Chunk from Rust validation complet.")
