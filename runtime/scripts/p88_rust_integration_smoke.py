#!/usr/bin/env python3
"""Smoke — Wave 42 : intégration Rust-Python (Phase 1 + 2).

Vérifie :
  1.  Workspace Rust : ge-py dans Cargo.toml membres
  2.  Crate ge-py : Cargo.toml existant avec pyo3
  3.  Crate ge-py : src/lib.rs avec pyclass + pymodule
  4.  Pyproject maturin dans scaffolding/
  5.  world.py : flag use_rust_backend + kwarg rust_world
  6.  ChunkStreamer instanciable avec use_rust_backend=False
  7.  ChunkStreamer avec use_rust_backend=True (wheel absent) → fallback gracieux
  8.  MockPyWorld fallback — bridge_status cohérent
  9.  generate_chunk Python pur → chunk valide (shape + root)
  10. ChunkStreamer.get() ≡ generate_chunk direct (même seed → même root)
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent  # genesis-engine/
sys.path.insert(0, str(ROOT))


def _row(label: str, ok: bool, detail: str = "") -> str:
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


results: list[str] = []
passed = failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    results.append(_row(label, ok, detail))
    if ok:
        passed += 1
    else:
        failed += 1


# ---------------------------------------------------------------------------
# 1. Workspace Rust — ge-py dans Cargo.toml
# ---------------------------------------------------------------------------
cargo_ws = REPO / "scaffolding" / "Cargo.toml"
try:
    ws_text = cargo_ws.read_text(encoding="utf-8")
    has_ge_py = "ge-py" in ws_text
    check("Cargo.toml workspace contient ge-py", has_ge_py,
          str(cargo_ws.relative_to(REPO)))
except Exception as e:
    check("Cargo.toml workspace contient ge-py", False, str(e))

# ---------------------------------------------------------------------------
# 2. Crate ge-py — Cargo.toml avec pyo3
# ---------------------------------------------------------------------------
ge_py_toml = REPO / "scaffolding" / "crates" / "ge-py" / "Cargo.toml"
try:
    toml_text = ge_py_toml.read_text(encoding="utf-8")
    has_pyo3  = "pyo3" in toml_text
    has_cdylib = "cdylib" in toml_text
    check("ge-py/Cargo.toml présent, pyo3 + cdylib",
          ge_py_toml.exists() and has_pyo3 and has_cdylib,
          f"pyo3={'oui' if has_pyo3 else 'NON'} cdylib={'oui' if has_cdylib else 'NON'}")
except Exception as e:
    check("ge-py/Cargo.toml présent, pyo3 + cdylib", False, str(e))

# ---------------------------------------------------------------------------
# 3. Crate ge-py — src/lib.rs avec PyO3
# ---------------------------------------------------------------------------
ge_py_lib = REPO / "scaffolding" / "crates" / "ge-py" / "src" / "lib.rs"
try:
    lib_text    = ge_py_lib.read_text(encoding="utf-8")
    has_pyclass = "#[pyclass]" in lib_text
    has_pymod   = "#[pymodule]" in lib_text
    has_stubs   = "submit_intent" in lib_text and "extract_mesh" in lib_text
    check("ge-py/src/lib.rs : pyclass + pymodule + stubs",
          ge_py_lib.exists() and has_pyclass and has_pymod and has_stubs,
          f"stubs={'oui' if has_stubs else 'NON'}")
except Exception as e:
    check("ge-py/src/lib.rs : pyclass + pymodule + stubs", False, str(e))

# ---------------------------------------------------------------------------
# 4. scaffolding/pyproject.toml maturin
# ---------------------------------------------------------------------------
maturin_toml = REPO / "scaffolding" / "pyproject.toml"
try:
    mat_text     = maturin_toml.read_text(encoding="utf-8")
    has_maturin  = "maturin" in mat_text
    has_manifest = "ge-py" in mat_text
    check("scaffolding/pyproject.toml maturin + manifest ge-py",
          maturin_toml.exists() and has_maturin and has_manifest,
          f"maturin={'oui' if has_maturin else 'NON'}")
except Exception as e:
    check("scaffolding/pyproject.toml maturin + manifest ge-py", False, str(e))

# ---------------------------------------------------------------------------
# 5. world.py — flag use_rust_backend + kwarg rust_world
# ---------------------------------------------------------------------------
world_py = ROOT / "engine" / "world.py"
try:
    world_text = world_py.read_text(encoding="utf-8")
    has_flag   = "use_rust_backend" in world_text
    has_kwarg  = "rust_world" in world_text
    has_warn   = "_rust_warned" in world_text
    check("world.py : use_rust_backend + rust_world + warning",
          has_flag and has_kwarg and has_warn,
          f"flag={'oui' if has_flag else 'NON'} warn={'oui' if has_warn else 'NON'}")
except Exception as e:
    check("world.py : use_rust_backend + rust_world + warning", False, str(e))

# ---------------------------------------------------------------------------
# 6. ChunkStreamer(use_rust_backend=False)
# ---------------------------------------------------------------------------
try:
    from engine.world import ChunkStreamer, TerrainParams
    cs = ChunkStreamer(seed=42, params=TerrainParams(), use_rust_backend=False)
    check("ChunkStreamer(use_rust_backend=False) instanciable",
          cs.use_rust_backend is False and cs._rust_world is None,
          f"rust_world={cs._rust_world!r}")
except Exception as e:
    check("ChunkStreamer(use_rust_backend=False) instanciable", False, str(e))

# ---------------------------------------------------------------------------
# 7. ChunkStreamer(use_rust_backend=True) sans wheel → fallback gracieux
# ---------------------------------------------------------------------------
try:
    cs_rust = ChunkStreamer(seed=42, params=TerrainParams(), use_rust_backend=True)
    # Sans le wheel natif, _rust_world doit rester None (pas de MockPyWorld)
    from engine.rust_bridge import try_import_genesis_world
    _, native = try_import_genesis_world()
    if native:
        # Wheel installé → _rust_world doit être un PyWorld natif
        ok = cs_rust._rust_world is not None
        detail = "native=True, rust_world présent"
    else:
        # Wheel absent → _rust_world doit être None (pas de Mock inutile)
        ok = cs_rust._rust_world is None
        detail = "native=False, rust_world=None (pas de Mock)"
    check("ChunkStreamer(use_rust_backend=True) fallback correct", ok, detail)
except Exception as e:
    check("ChunkStreamer(use_rust_backend=True) fallback correct", False, str(e))

# ---------------------------------------------------------------------------
# 8. bridge_status cohérent
# ---------------------------------------------------------------------------
try:
    from engine.rust_bridge import bridge_status, try_import_genesis_world
    _, native = try_import_genesis_world()
    st = bridge_status()
    check("bridge_status() natif cohérent",
          st["native"] == native,
          f"native={native}")
except Exception as e:
    check("bridge_status() natif cohérent", False, str(e))

# ---------------------------------------------------------------------------
# 9. generate_chunk Python pur → chunk valide
# ---------------------------------------------------------------------------
try:
    from engine.world import generate_chunk, TerrainParams, CHUNK_SIZE
    import numpy as np
    chunk = generate_chunk(seed=123, coord=(0, 0, 0), params=TerrainParams())
    shape_ok  = chunk.height.shape == (CHUNK_SIZE, CHUNK_SIZE)
    biome_ok  = chunk.biome.shape == (CHUNK_SIZE, CHUNK_SIZE)
    root_ok   = len(chunk.content_root) == 32
    # Vérif basique : élévation dans une range raisonnable
    range_ok  = -200 < float(chunk.height.mean()) < 5000
    check("generate_chunk(python) chunk valide",
          shape_ok and biome_ok and root_ok and range_ok,
          f"shape={chunk.height.shape} mean_elev={chunk.height.mean():.1f}m")
except Exception as e:
    check("generate_chunk(python) chunk valide", False, str(e))

# ---------------------------------------------------------------------------
# 10. ChunkStreamer.get() ≡ generate_chunk direct (déterminisme)
# ---------------------------------------------------------------------------
try:
    from engine.world import ChunkStreamer, TerrainParams, generate_chunk
    params = TerrainParams()
    cs = ChunkStreamer(seed=99, params=params, use_rust_backend=False)
    c1 = cs.get(tick=0, coord=(2, 3, 0))
    c2 = generate_chunk(seed=99, coord=(2, 3, 0), params=params)
    roots_match  = c1.content_root == c2.content_root
    height_match = bool(np.array_equal(c1.height, c2.height))
    check("ChunkStreamer.get() ≡ generate_chunk direct",
          roots_match and height_match,
          f"root={'match' if roots_match else 'DIFF'} height={'match' if height_match else 'DIFF'}")
except Exception as e:
    check("ChunkStreamer.get() ≡ generate_chunk direct", False, str(e))

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p88 — Wave 42 Rust-Python Integration ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK — tous les checks sont verts.")
