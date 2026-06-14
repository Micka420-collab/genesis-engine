"""D5/D6 guardrail: Python ↔ Rust geology cross-language contract.

Why this file exists
--------------------
The 2026-06-12 delta-audit (``native/world-engine/AUDIT-DELTA-2026-06-12.md``)
formalised risk **D6** — *double source of truth for geology*:

  > Trois sessions, trois capacités (C1 surface_mineralization, C2 lithic_outcrop,
  > C3 water_potability) dérivent un signal géologique côté **Python**
  > (``engine.geology`` / ``engine.mineral_catalog``) tandis que la crate Rust
  > ``native/world-engine/crates/geology`` (1095 lignes, palette RGB + minéraux)
  > reste orpheline. Le couplage est *un protocole non documenté* : les deux
  > côtés DOIVENT s'accorder sur les noms de minéraux et la palette « tell »,
  > mais **« sans test cross-langage, rien ne le garantit »** (§3.3).

Audit option (a) step 4 prescribes exactly this test:
``test_geology_palette_matches_rust()``. The environment has **no cargo**, so we
cannot compile/bind the Rust crate — but we *can* read its source as text and
assert the contract. That is what we do here: the Rust enum becomes a
read-only oracle and this test fails the moment either side drifts.

This is **not** a new capability and **not** an observer (no ``sim.step`` hook,
zero tick cost) — it respects the Wave-64+ moratorium. It is a guardrail in the
same spirit as ``test_observer_budget.py`` (D1).

What the contract actually is
-----------------------------
The Rust ``Mineral`` enum is a **coarse 16-variant gameplay "tell" palette**;
the Python ``mineral_catalog`` is a **fine-grained 35-mineral scientific
catalogue**. They are deliberately *not* 1:1. The genuine, must-hold contract is:

  1. The Rust enum's identity is frozen (16 named variants + ``MINERAL_COUNT``).
     Any add / rename / removal trips this test → forces the human to update the
     documented map below (the guardrail working as designed).
  2. Every "tell" mineral the **live Python runtime** surfaces to agents maps to
     a real Rust variant (``PY_TO_RUST``), and every Python name exists in the
     catalogue. Drift on either side breaks the build.
  3. The byte-exact colour cross-references that the code documents stay locked:
     — the **malachite copper tell** (``surface_mineralization.py`` rgb (80,140,70)
       ⇔ ``Mineral::Malachite::surface_color()`` ``[80,140,70]``) ;
     — the **matte-black coal tell** (``combustible_outcrop.py`` coal rgb
       (20,20,20) ⇔ ``Mineral::Coal::surface_color()`` ``[20,20,20]``).
  4. The intra-Python salt contract (C1 salt cue rgb == C3 brine rgb) that
     ``water_potability.py:161`` claims in a comment is enforced, not just hoped.

Cap. C4 (``combustible_outcrop``) enrichment (ADR-0007 guardrail)
-----------------------------------------------------------------
The Wave-64+ moratorium guardrail requires **every new capability to enrich
``PY_TO_RUST``**. C4 surfaces the organic-fuel branch (peat / coal / oil_shale)
as live runtime tells, so it (a) finally exercises the ``coal`` entry that was
mapped here speculatively, (b) adds ``peat`` and ``oil_shale`` (both binned to
the coarse Rust ``Coal`` tell — there is no finer organic variant), and (c)
locks the matte-black coal tell byte-exact, mirroring the malachite copper tell.

Cap. C5 (``clay_outcrop``) enrichment (ADR-0007 guardrail)
----------------------------------------------------------
C5 surfaces plastic clay as a live runtime tell. It **closes the FineClay
orphan**: a real ``fine_clay`` (kaolinite) catalogue entry is added, mapped to
the Rust ``FineClay`` variant (moved out of ``RUST_ONLY``), and the smooth-ochre
clay tell ``(180,140,110)`` is locked byte-exact ⇔
``Mineral::FineClay::surface_color()`` — the third locked colour cross-reference
after malachite (copper) and coal.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Tuple

import pytest

from engine import surface_mineralization as sm
from engine import water_potability as wp
from engine import combustible_outcrop as co
from engine import clay_outcrop as cl
from engine.mineral_catalog import MINERAL_BY_NAME


# --------------------------------------------------------------------------- #
# Locate the Rust geology source (read-only oracle).                          #
# --------------------------------------------------------------------------- #

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUST_MINERAL_RS = (
    _REPO_ROOT / "native" / "world-engine" / "crates" / "geology" / "src" / "mineral.rs"
)


def _require_rust_source() -> str:
    if not _RUST_MINERAL_RS.is_file():
        pytest.skip(
            f"Rust geology source absent ({_RUST_MINERAL_RS}); cross-language "
            "contract is only checkable when the native tree is present."
        )
    return _RUST_MINERAL_RS.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Minimal Rust-source parser (regex; no toolchain required).                  #
# --------------------------------------------------------------------------- #

def _parse_enum_variants(src: str) -> Tuple[str, ...]:
    """Variant names declared in ``pub enum Mineral { ... }`` (in order)."""
    m = re.search(r"pub enum Mineral\s*\{(.*?)\}", src, re.DOTALL)
    assert m, "could not locate `pub enum Mineral { ... }` in mineral.rs"
    body = m.group(1)
    # Each variant: `    Flint = 0,` — ignore `///` doc lines and attributes.
    return tuple(re.findall(r"^\s*([A-Z][A-Za-z0-9]+)\s*=\s*\d+\s*,", body, re.MULTILINE))


def _parse_mineral_count(src: str) -> int:
    m = re.search(r"MINERAL_COUNT\s*:\s*usize\s*=\s*(\d+)", src)
    assert m, "could not locate `MINERAL_COUNT: usize = N` in mineral.rs"
    return int(m.group(1))


def _parse_surface_palette(src: str) -> Dict[str, Tuple[int, int, int]]:
    """Map ``Mineral::Variant => [r, g, b]`` from the surface_color() arm."""
    palette: Dict[str, Tuple[int, int, int]] = {}
    for name, r, g, b in re.findall(
        r"Mineral::(\w+)\s*=>\s*\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]", src
    ):
        palette[name] = (int(r), int(g), int(b))
    return palette


# --------------------------------------------------------------------------- #
# The documented contract (single place the protocol is written down).        #
# --------------------------------------------------------------------------- #

# Frozen identity of the Rust `Mineral` enum. If Rust changes this set, the
# test fails *on purpose* so a human updates the map deliberately (D6 guardrail).
EXPECTED_RUST_VARIANTS = frozenset({
    "Flint", "Copper", "Tin", "Iron", "Gold", "Silver", "Coal", "Salt",
    "Sulfur", "Obsidian", "FineClay", "Malachite", "Magnetite", "Quartz",
    "LimestonePure", "None",
})

# Python live-runtime "tell" mineral  ->  Rust Mineral variant.
# Only pairs that BOTH sides model as a distinct concept. Verified by the test:
# every key must exist in MINERAL_BY_NAME, every value must be a real variant.
PY_TO_RUST: Dict[str, str] = {
    "native_copper": "Copper",
    "native_sulfur": "Sulfur",
    "halite":        "Salt",
    "native_gold":   "Gold",
    "native_silver": "Silver",
    "cassiterite":   "Tin",       # tin ore (Rust enum is coarser: just "Tin")
    "hematite":      "Iron",
    "magnetite":     "Magnetite",
    "obsidian":      "Obsidian",
    "quartz":        "Quartz",
    "coal":          "Coal",
    # Cap. C4 (combustible_outcrop) organic fuels. The coarse Rust enum has a
    # single "Coal" tell; the finer Python organics (immature peat, kerogen oil
    # shale) bin to it — same dark carbonaceous "burnable" gameplay signal.
    "peat":          "Coal",
    "oil_shale":     "Coal",
    # Cap. C5 (clay_outcrop) plastic clay. Closes the former FineClay orphan:
    # the new ``fine_clay`` (kaolinite) catalogue entry IS the Rust FineClay tell
    # an agent learns to seek for a pot. (Shale, the brick-grade clay C5 also
    # surfaces, keeps its own catalogue identity and is not mapped here.)
    "fine_clay":     "FineClay",
}

# Rust variants intentionally without a same-named Python catalogue entry.
# Documented so their presence is asserted (removal trips the test) and their
# Python-side modelling strategy is recorded.
RUST_ONLY = {
    "Flint":         "modelled in Python as quartz upgraded by CHERT_BONUS in a carbonate host",
    "Malachite":     "weathering product of native_copper; it IS the copper surface tell colour",
    "LimestonePure": "Python models as limestone/calcite (catalogue), coarse Rust bins it",
    "None":          "sentinel for 'no deposit'",
}


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #

def test_rust_enum_identity_is_frozen():
    """The Rust Mineral enum has exactly the 16 documented variants."""
    src = _require_rust_source()
    variants = set(_parse_enum_variants(src))
    assert variants == EXPECTED_RUST_VARIANTS, (
        "Rust `Mineral` enum drifted from the documented contract.\n"
        f"  added in Rust   : {sorted(variants - EXPECTED_RUST_VARIANTS)}\n"
        f"  missing in Rust : {sorted(EXPECTED_RUST_VARIANTS - variants)}\n"
        "Update PY_TO_RUST / RUST_ONLY in this file deliberately (D6 guardrail)."
    )


def test_mineral_count_matches_variant_count():
    """`MINERAL_COUNT` stays in sync with the enum it counts."""
    src = _require_rust_source()
    variants = _parse_enum_variants(src)
    assert _parse_mineral_count(src) == len(variants) == 16


def test_every_contract_variant_is_classified():
    """Each Rust variant is either mapped from Python or explicitly Rust-only."""
    mapped = set(PY_TO_RUST.values())
    classified = mapped | set(RUST_ONLY)
    assert classified == EXPECTED_RUST_VARIANTS, (
        "Some Rust variant is neither in PY_TO_RUST nor RUST_ONLY: "
        f"{sorted(EXPECTED_RUST_VARIANTS - classified)}"
    )


def test_python_tell_minerals_exist_both_sides():
    """Every PY_TO_RUST pair is real on both sides (no silent rename)."""
    src = _require_rust_source()
    variants = set(_parse_enum_variants(src))
    for py_name, rust_name in PY_TO_RUST.items():
        assert py_name in MINERAL_BY_NAME, (
            f"Python catalogue lost mineral '{py_name}' referenced by the "
            "cross-language contract — rename in mineral_catalog or fix PY_TO_RUST."
        )
        assert rust_name in variants, (
            f"Rust enum lost variant '{rust_name}' (mapped from '{py_name}')."
        )


def test_malachite_copper_tell_is_byte_exact():
    """The one documented colour cross-reference stays locked.

    surface_mineralization copper cue rgb (80,140,70) == Rust
    `Mineral::Malachite::surface_color()` — the canonical "the world never
    lies" copper tell. This is the colour an agent sees and learns to dig.
    """
    src = _require_rust_source()
    palette = _parse_surface_palette(src)
    assert "Malachite" in palette, "Rust surface_color() lost the Malachite arm"
    copper_rule = next(r for r in sm._RULES if r.group == "copper")
    assert tuple(copper_rule.rgb) == palette["Malachite"], (
        f"Copper tell drift: Python {tuple(copper_rule.rgb)} != "
        f"Rust Malachite {palette['Malachite']}"
    )


def test_coal_tell_is_byte_exact():
    """The matte-black coal tell stays locked cross-language (Cap. C4).

    combustible_outcrop coal cue rgb (20,20,20) == Rust
    `Mineral::Coal::surface_color()` — the colour an agent learns to seek for a
    furnace. Mirrors the malachite copper tell; drift on either side breaks the
    build (D6 guardrail).
    """
    src = _require_rust_source()
    palette = _parse_surface_palette(src)
    assert "Coal" in palette, "Rust surface_color() lost the Coal arm"
    assert co._PROFILE["coal"].rgb == palette["Coal"], (
        f"Coal tell drift: Python {co._PROFILE['coal'].rgb} != "
        f"Rust Coal {palette['Coal']}"
    )


def test_fine_clay_tell_is_byte_exact():
    """The smooth-ochre clay tell stays locked cross-language (Cap. C5).

    clay_outcrop fine_clay cue rgb (180,140,110) == Rust
    ``Mineral::FineClay::surface_color()`` — the colour an agent learns to seek
    for a pot. This wiring closes the former FineClay orphan; drift on either
    side breaks the build (D6 guardrail). Mirrors the malachite/coal tells.
    """
    src = _require_rust_source()
    palette = _parse_surface_palette(src)
    assert "FineClay" in palette, "Rust surface_color() lost the FineClay arm"
    assert cl._PROFILE["fine_clay"].rgb == palette["FineClay"], (
        f"Clay tell drift: Python {cl._PROFILE['fine_clay'].rgb} != "
        f"Rust FineClay {palette['FineClay']}"
    )


def test_rust_palette_is_complete():
    """Every non-sentinel Rust variant has a surface_color() entry."""
    src = _require_rust_source()
    palette = _parse_surface_palette(src)
    for variant in EXPECTED_RUST_VARIANTS - {"None"}:
        # `None` legitimately maps to [0,0,0] but we don't require it.
        assert variant in palette, f"Rust surface_color() missing arm for {variant}"


def test_salt_cue_shared_between_c1_and_c3():
    """Intra-Python contract claimed in water_potability.py:161 is enforced.

    The shallow halite bed is ONE truthful substrate that must look the same
    whether perceived as a surface salt crust (C1) or as a brine rime (C3).
    """
    salt_rule = next(r for r in sm._RULES if r.group == "salt")
    brine_rgb = wp._TASTE_RGB[wp.WaterTaste.BRINE]
    assert tuple(salt_rule.rgb) == tuple(brine_rgb), (
        f"Salt-crust (C1) {tuple(salt_rule.rgb)} diverged from brine rime (C3) "
        f"{tuple(brine_rgb)} — they share one halite substrate and must match."
    )
