#!/usr/bin/env python3
"""Smoke — Wave 43 : indices visuels minéraux (substrate physique).

Vérifie le nouveau crate `genesis-geology` qui rend les minerais découvrables
par observation visuelle (color_hint), conformément à la règle d'émergence
absolue : l'agent ne sait jamais qu'un minerai existe — il VOIT du vert,
remembre, revient, creuse.

Checks :
  1.  Workspace : crate genesis-geology déclaré dans Cargo.toml
  2.  Cargo.toml crate : dépendance genesis-core (pour Prf déterministe)
  3.  lib.rs : ré-exporte Mineral, RockType, sample_surface
  4.  rock.rs : enum RockType avec 12 variants (Air..CoalSeam)
  5.  mineral.rs : enum Mineral avec 16 variants (Flint..None)
  6.  mineral.rs : Mineral::Malachite::surface_color() = [80, 140, 70] (vert vif)
  7.  mineral.rs : règles affinity rejettent Gold-in-Clay et Coal-hors-CoalSeam
  8.  visual.rs : sample_surface est pure fct (Prf, x, y, z, host) → SurfaceSample
  9.  visual.rs : DISCOVERY_THRESHOLD existe et < 1.0
  10. Tests Rust déclarés : déterminisme + gold_never_in_clay + clustering
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent  # genesis-engine/
NATIVE = REPO / "native" / "world-engine"
GEO = NATIVE / "crates" / "geology"

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
# 1. Workspace Cargo.toml referencing crates/geology
# ---------------------------------------------------------------------------
ws = NATIVE / "Cargo.toml"
try:
    ws_text = ws.read_text(encoding="utf-8")
    declared = '"crates/geology"' in ws_text
    check("Workspace declare crates/geology", declared,
          str(ws.relative_to(REPO)))
except Exception as e:
    check("Workspace declare crates/geology", False, str(e))

# ---------------------------------------------------------------------------
# 2. genesis-geology Cargo.toml depends on genesis-core
# ---------------------------------------------------------------------------
crate_toml = GEO / "Cargo.toml"
try:
    text = crate_toml.read_text(encoding="utf-8")
    has_core = "genesis-core" in text
    has_serde = "serde" in text
    check("geology/Cargo.toml depends on genesis-core + serde",
          has_core and has_serde,
          f"core={'oui' if has_core else 'NON'} serde={'oui' if has_serde else 'NON'}")
except Exception as e:
    check("geology/Cargo.toml depends on genesis-core + serde", False, str(e))

# ---------------------------------------------------------------------------
# 3. lib.rs re-exports public API
# ---------------------------------------------------------------------------
lib_rs = GEO / "src" / "lib.rs"
try:
    text = lib_rs.read_text(encoding="utf-8")
    reexports = ("pub use mineral::" in text
                 and "pub use rock::" in text
                 and "pub use visual::" in text)
    pub_funcs = "sample_surface" in text and "surface_color_hint" in text
    check("lib.rs re-exports Mineral / RockType / sample_surface",
          reexports and pub_funcs,
          "modules + sample_surface OK" if reexports and pub_funcs else "missing exports")
except Exception as e:
    check("lib.rs re-exports Mineral / RockType / sample_surface", False, str(e))

# ---------------------------------------------------------------------------
# 4. rock.rs — RockType enum with 12 variants
# ---------------------------------------------------------------------------
rock_rs = GEO / "src" / "rock.rs"
try:
    text = rock_rs.read_text(encoding="utf-8")
    expected_variants = [
        "Air", "Regolith", "Clay", "Sand", "Sandstone", "Limestone",
        "Basalt", "Granite", "Schist", "Marble", "Quartzite", "CoalSeam",
    ]
    missing = [v for v in expected_variants if re.search(rf"\b{v}\s*=", text) is None]
    count_const = "ROCK_TYPE_COUNT: usize = 12" in text
    check("rock.rs enum RockType 12 variants + ROCK_TYPE_COUNT",
          not missing and count_const,
          f"missing={missing} count_const={'oui' if count_const else 'NON'}")
except Exception as e:
    check("rock.rs enum RockType 12 variants + ROCK_TYPE_COUNT", False, str(e))

# ---------------------------------------------------------------------------
# 5. mineral.rs — Mineral enum with 16 variants
# ---------------------------------------------------------------------------
mineral_rs = GEO / "src" / "mineral.rs"
try:
    text = mineral_rs.read_text(encoding="utf-8")
    expected = [
        "Flint", "Copper", "Tin", "Iron", "Gold", "Silver", "Coal", "Salt",
        "Sulfur", "Obsidian", "FineClay", "Malachite", "Magnetite",
        "Quartz", "LimestonePure", "None",
    ]
    missing = [v for v in expected if re.search(rf"\b{v}\s*=", text) is None]
    count_const = "MINERAL_COUNT: usize = 16" in text
    check("mineral.rs enum Mineral 16 variants + MINERAL_COUNT",
          not missing and count_const,
          f"missing={missing} count_const={'oui' if count_const else 'NON'}")
except Exception as e:
    check("mineral.rs enum Mineral 16 variants + MINERAL_COUNT", False, str(e))

# ---------------------------------------------------------------------------
# 6. Malachite RGB hardcoded — [80, 140, 70] vivid green
# ---------------------------------------------------------------------------
try:
    text = mineral_rs.read_text(encoding="utf-8")
    malachite_match = re.search(
        r"Mineral::Malachite\s*=>\s*\[\s*80\s*,\s*140\s*,\s*70\s*\]", text
    )
    check("Mineral::Malachite -> [80,140,70] (copper visual cue)",
          malachite_match is not None,
          "RGB locked" if malachite_match else "RGB MOVED — agent vision regression")
except Exception as e:
    check("Mineral::Malachite -> [80,140,70] (copper visual cue)", False, str(e))

# ---------------------------------------------------------------------------
# 7. Forbidden pairings absent from affinity match arms
# ---------------------------------------------------------------------------
try:
    text = mineral_rs.read_text(encoding="utf-8")
    # Gold should NOT be listed with Clay as host
    gold_in_clay = re.search(r"M::Gold\s*,\s*R::Clay", text) is not None
    # Coal should ONLY appear with CoalSeam host
    coal_arms = re.findall(r"M::Coal\s*,\s*R::([A-Za-z]+)", text)
    coal_outside_seam = any(a != "CoalSeam" for a in coal_arms)
    # Copper should NOT spawn in pure Sand
    cu_in_sand = re.search(r"M::Copper\s*,\s*R::Sand", text) is not None
    forbidden_safe = not gold_in_clay and not coal_outside_seam and not cu_in_sand
    check("affinity rules — no Au-in-Clay / no Coal-elsewhere / no Cu-in-Sand",
          forbidden_safe,
          f"Au-clay={gold_in_clay} Coal-arms={coal_arms} Cu-sand={cu_in_sand}")
except Exception as e:
    check("affinity rules — no Au-in-Clay / no Coal-elsewhere / no Cu-in-Sand",
          False, str(e))

# ---------------------------------------------------------------------------
# 8. visual.rs — sample_surface signature
# ---------------------------------------------------------------------------
visual_rs = GEO / "src" / "visual.rs"
try:
    text = visual_rs.read_text(encoding="utf-8")
    sig = re.search(
        r"pub\s+fn\s+sample_surface\s*\(\s*prf:\s*Prf\s*,\s*world_x:\s*i32",
        text,
    )
    has_struct = "pub struct SurfaceSample" in text
    has_hint = "pub struct SurfaceColorHint" in text
    check("visual.rs : sample_surface(Prf, x, y, z, host) + structs",
          sig is not None and has_struct and has_hint,
          f"fn={'oui' if sig else 'NON'} struct={'oui' if has_struct else 'NON'}")
except Exception as e:
    check("visual.rs : sample_surface(Prf, x, y, z, host) + structs", False, str(e))

# ---------------------------------------------------------------------------
# 9. DISCOVERY_THRESHOLD const present and reasonable
# ---------------------------------------------------------------------------
try:
    text = visual_rs.read_text(encoding="utf-8")
    m = re.search(r"DISCOVERY_THRESHOLD\s*:\s*f32\s*=\s*([0-9.]+)", text)
    val = float(m.group(1)) if m else None
    ok = val is not None and 0.1 <= val <= 0.95
    check("DISCOVERY_THRESHOLD in (0.1, 0.95)", ok,
          f"value={val}" if val is not None else "MISSING")
except Exception as e:
    check("DISCOVERY_THRESHOLD in (0.1, 0.95)", False, str(e))

# ---------------------------------------------------------------------------
# 10. Critical Rust tests declared (will be exercised by `cargo test` in CI)
# ---------------------------------------------------------------------------
try:
    vtext = visual_rs.read_text(encoding="utf-8")
    mtext = mineral_rs.read_text(encoding="utf-8")
    expected_tests = [
        ("determinism_same_seed_same_output", vtext),
        ("different_seeds_diverge", vtext),
        ("air_voxel_never_has_deposit", vtext),
        ("gold_never_appears_in_clay", vtext),
        ("malachite_appears_at_shallow_schist_copper_belt", vtext),
        ("deposits_cluster_spatially", vtext),
        ("forbidden_pairings_are_zero", mtext),
        ("malachite_is_surface_marker_for_copper", mtext),
    ]
    missing = [name for name, src in expected_tests if f"fn {name}" not in src]
    check("All Wave 43 emergence tests declared",
          not missing,
          f"missing={missing}" if missing else f"{len(expected_tests)} tests OK")
except Exception as e:
    check("All Wave 43 emergence tests declared", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p113 — Wave 43 Mineral Visual Cues ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) raté(s).")
    sys.exit(1)
print("OK — tous les checks sont verts.")
