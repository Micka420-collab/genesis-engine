#!/usr/bin/env python3
"""Smoke — Wave 42 Phase 3e : Rust genesis-anchor terrain blend.

Vérifie :
  1. GENM v2 export contient temp + precip (taille correcte)
  2. PyWorld(macro_grid_bytes=...) charge le macro grid (has_genesis=True)
  3. Genesis-blend chunk valide (elev, temp, precip, biome)
  4. Rust genesis elev corrélé au macro grid (pas pur-FBM)
  5. Rust vs Python genesis terrain match < tolérance
  6. Performance : Rust genesis plus rapide que Python genesis
"""
from __future__ import annotations

import io
import struct
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
# 0. Import natif + genesis world
# ---------------------------------------------------------------------------
try:
    import genesis_world as gw
    native_ok = hasattr(gw, "PyWorld") and hasattr(gw.PyWorld, "has_genesis")
except ImportError:
    print("\nSmoke p91 — SKIPPED (wheel genesis_world non installe)\n")
    sys.exit(0)

if not native_ok:
    print("\nSmoke p91 — SKIPPED (PyWorld.has_genesis absent — rebuild required)\n")
    sys.exit(0)

from engine.world import (  # noqa: E402
    sample_terrain_with_genesis, TerrainParams,
    CHUNK_SIZE, VOXEL_SIZE_M, CHUNK_SIDE_M,
    classify_biome_array, ChunkStreamer, generate_chunk,
)
from engine.world_genesis import (  # noqa: E402
    generate_world, GenesisParams, make_anchor,
)
from engine.macro_grid_export import export_macro_grid_bytes, VERSION  # noqa: E402

SEED = 42

# Generate a small GenesisWorld for testing.
gparams = GenesisParams(seed=SEED, resolution=32, map_size_km=1000.0)
gworld = generate_world(gparams)
anchor = make_anchor(gworld, blend=1.0, micro_amp_m=80.0,
                     micro_amp_temp_c=1.5, micro_amp_precip_mm=150.0)
tparams = TerrainParams()

# ---------------------------------------------------------------------------
# 1. GENM v2 export
# ---------------------------------------------------------------------------
try:
    genm_bytes = export_macro_grid_bytes(gworld)
    # Header: GENM(4) + ver(4) + W(4) + H(4) + cell_km(4) + ox(4) + oy(4) = 28
    # + 3 * W*H*4 (elev+temp+precip) + W*H (biome)
    n = gparams.resolution * gparams.resolution
    expected_size = 28 + n * 4 * 3 + n
    ver = struct.unpack_from("<I", genm_bytes, 4)[0]
    check("GENM v2 export (version + size)",
          ver == 2 and len(genm_bytes) == expected_size,
          f"ver={ver} size={len(genm_bytes)} expected={expected_size}")
except Exception as e:
    check("GENM v2 export", False, str(e))

# ---------------------------------------------------------------------------
# 2. PyWorld loads macro grid
# ---------------------------------------------------------------------------
try:
    ox_km, oy_km = anchor.sim_origin_macro_km
    w = gw.PyWorld(
        seed=SEED,
        macro_grid_bytes=genm_bytes,
        sim_origin_x_km=float(ox_km),
        sim_origin_y_km=float(oy_km),
        blend=float(anchor.blend),
        micro_amp_m=float(anchor.micro_amp_m),
        micro_amp_temp_c=float(anchor.micro_amp_temp_c),
        micro_amp_precip_mm=float(anchor.micro_amp_precip_mm),
    )
    check("PyWorld(macro_grid_bytes) has_genesis=True",
          w.has_genesis(),
          repr(w))
except Exception as e:
    check("PyWorld(macro_grid_bytes) has_genesis=True", False, str(e))

# ---------------------------------------------------------------------------
# 3. Genesis-blend chunk valid
# ---------------------------------------------------------------------------
try:
    d = w.sample_terrain_chunk(0, 0)
    rs_elev = np.asarray(d["elev"], dtype=np.float32)
    rs_temp = np.asarray(d["temp"], dtype=np.float32)
    rs_precip = np.asarray(d["precip"], dtype=np.float32)
    valid = (rs_elev.shape[0] == CHUNK_SIZE * CHUNK_SIZE and
             rs_temp.shape[0] == CHUNK_SIZE * CHUNK_SIZE and
             rs_precip.shape[0] == CHUNK_SIZE * CHUNK_SIZE)
    obs = w.observe_chunk(0, 0, 0)
    rs_biome = np.asarray(obs["biome"], dtype=np.uint8)
    valid = valid and rs_biome.shape[0] == CHUNK_SIZE * CHUNK_SIZE
    valid = valid and all(b < 12 for b in rs_biome)
    check("Genesis-blend chunk valid (elev, temp, precip, biome)",
          valid,
          f"elev_range=[{rs_elev.min():.1f}, {rs_elev.max():.1f}]m")
except Exception as e:
    check("Genesis-blend chunk valid", False, str(e))

# ---------------------------------------------------------------------------
# 4. Rust genesis elev correlated with macro grid
# ---------------------------------------------------------------------------
try:
    # A PyWorld WITHOUT macro grid should produce different terrain
    w_pure = gw.PyWorld(seed=SEED)
    d_pure = w_pure.sample_terrain_chunk(0, 0)
    pure_elev = np.asarray(d_pure["elev"], dtype=np.float32)
    # They should differ significantly (different layer names + macro blend)
    diff = np.abs(rs_elev - pure_elev).mean()
    check("Rust genesis differs from pure-FBM",
          diff > 10.0,
          f"mean_diff={diff:.1f}m")
except Exception as e:
    check("Rust genesis differs from pure-FBM", False, str(e))

# ---------------------------------------------------------------------------
# 5. Rust vs Python genesis terrain match
# ---------------------------------------------------------------------------
try:
    test_coords = [(i % 5, i // 5) for i in range(25)]
    max_elev_diff = 0.0
    max_temp_diff = 0.0
    total_cells = 0
    total_biome_match = 0

    for cx, cy in test_coords:
        ox = cx * CHUNK_SIDE_M
        oy = cy * CHUNK_SIDE_M
        xs = (ox + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
        ys = (oy + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
        XX, YY = np.meshgrid(xs, ys, indexing="xy")
        py_elev, py_temp, py_precip = sample_terrain_with_genesis(
            SEED, tparams, XX, YY, anchor)
        py_biome = classify_biome_array(py_temp, py_precip, py_elev)

        d = w.sample_terrain_chunk(cx, cy)
        rs_e = np.asarray(d["elev"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        rs_t = np.asarray(d["temp"], dtype=np.float32).reshape(CHUNK_SIZE, CHUNK_SIZE)
        obs = w.observe_chunk(cx, cy, 0)
        rs_b = np.asarray(obs["biome"], dtype=np.uint8).reshape(CHUNK_SIZE, CHUNK_SIZE)

        max_elev_diff = max(max_elev_diff, np.abs(py_elev - rs_e).max())
        max_temp_diff = max(max_temp_diff, np.abs(py_temp - rs_t).max())
        total_cells += py_biome.size
        total_biome_match += np.sum(py_biome == rs_b)

    biome_pct = 100.0 * total_biome_match / total_cells
    # Tolerance is looser than pure-FBM (macro bilinear interp has float
    # precision differences). Elevation within 0.5m, biomes >= 95%.
    elev_ok = max_elev_diff < 0.5
    biome_ok = biome_pct >= 95.0
    check(f"Rust vs Python genesis match (25 chunks, {total_cells} cells)",
          elev_ok and biome_ok,
          f"max_elev_diff={max_elev_diff:.4f}m biome={biome_pct:.1f}%")
except Exception as e:
    check("Rust vs Python genesis match", False, str(e))

# ---------------------------------------------------------------------------
# 6. Performance
# ---------------------------------------------------------------------------
N_BENCH = 20
bench_coords = [(i % 10, i // 10) for i in range(N_BENCH)]

# Warm up both paths
xs = (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M
ys = xs.copy()
XX, YY = np.meshgrid(xs.astype(np.float32), ys.astype(np.float32), indexing="xy")
sample_terrain_with_genesis(SEED, tparams, XX, YY, anchor)
w.sample_terrain_chunk(0, 0)

# Clear Rust cache to benchmark compute, not cache hits.
w.clear_cache()

t0 = time.perf_counter()
for cx, cy in bench_coords:
    ox = cx * CHUNK_SIDE_M
    oy = cy * CHUNK_SIDE_M
    xs = (ox + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
    ys = (oy + (np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
    XX, YY = np.meshgrid(xs, ys, indexing="xy")
    sample_terrain_with_genesis(SEED, tparams, XX, YY, anchor)
py_ms = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
for cx, cy in bench_coords:
    w.sample_terrain_chunk(cx, cy)
rs_ms = (time.perf_counter() - t0) * 1000

ratio = py_ms / max(rs_ms, 0.001)
check(f"Rust genesis faster ({ratio:.1f}x)",
      ratio > 1.0,
      f"Python={py_ms:.1f}ms Rust={rs_ms:.1f}ms")

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p91 — Wave 42 Phase 3e Genesis Anchor ({passed}/{total})\n")
for r in results:
    print(r)
print()
print(f"  Genesis: max_elev_diff={max_elev_diff:.4f}m  biome={biome_pct:.1f}%")
print(f"  Perf: Python {py_ms:.1f}ms vs Rust {rs_ms:.1f}ms ({ratio:.1f}x)")
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK — Phase 3e genesis anchor validation complet.")
