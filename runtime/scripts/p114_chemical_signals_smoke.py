#!/usr/bin/env python3
"""Smoke — Wave 44 : signaux chimiques (canal olfactif géologique).

Vérifie le module `geology::chemical` qui rend les minerais odorants
(sulfur / coal / salt) détectables à distance via une dispersion gaussienne
dépendante du vent. L'agent ne reçoit qu'une intensité (0–1), jamais
l'identité de la source.

Checks :
  1.  Module chemical.rs présent dans le crate genesis-geology
  2.  lib.rs ré-exporte SignalKind, ChemicalEmission, emission_at, intensity_at
  3.  SignalKind : 3 variants (Pungent, Acrid, Saline) + decay_length_m
  4.  emission_for_mineral : map exact Sulfur/Coal/Salt -> Pungent/Acrid/Saline
  5.  Gold/Iron/Malachite NE doivent PAS émettre (canal olfactif silencieux)
  6.  intensity_at signature (emission, sx,sy,sz, ox,oy,oz, wind_xy)
  7.  Decay length ordonné : Pungent > Acrid > Saline (physique réaliste)
  8.  Test downwind > upwind présent (asymétrie vent obligatoire)
  9.  Test calm_wind_is_isotropic présent (sécurité dans cas wind=0)
  10. Test determinism_of_emission_sampling présent
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
GEO = REPO / "native" / "world-engine" / "crates" / "geology"
CHEM_RS = GEO / "src" / "chemical.rs"
LIB_RS = GEO / "src" / "lib.rs"

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
# 1. chemical.rs present
# ---------------------------------------------------------------------------
check("chemical.rs present in geology crate", CHEM_RS.exists(),
      str(CHEM_RS.relative_to(REPO)) if CHEM_RS.exists() else "MISSING")

# ---------------------------------------------------------------------------
# 2. lib.rs re-exports
# ---------------------------------------------------------------------------
try:
    text = LIB_RS.read_text(encoding="utf-8")
    expected = ["SignalKind", "ChemicalEmission", "emission_at",
                "intensity_at", "emission_for_mineral"]
    missing = [s for s in expected if s not in text]
    check("lib.rs re-exports chemical symbols", not missing,
          f"missing={missing}" if missing else "all 5 symbols exported")
except Exception as e:
    check("lib.rs re-exports chemical symbols", False, str(e))

# ---------------------------------------------------------------------------
# 3. SignalKind enum + decay_length_m + base_strength
# ---------------------------------------------------------------------------
try:
    text = CHEM_RS.read_text(encoding="utf-8")
    variants = ["Pungent", "Acrid", "Saline"]
    missing = [v for v in variants if re.search(rf"\b{v}\s*=", text) is None]
    has_decay = "decay_length_m" in text
    has_strength = "base_strength" in text
    ok = not missing and has_decay and has_strength
    check("SignalKind { Pungent, Acrid, Saline } + decay + strength",
          ok,
          f"missing={missing} decay={has_decay} strength={has_strength}")
except Exception as e:
    check("SignalKind { Pungent, Acrid, Saline } + decay + strength", False, str(e))

# ---------------------------------------------------------------------------
# 4. emission_for_mineral mappings
# ---------------------------------------------------------------------------
try:
    text = CHEM_RS.read_text(encoding="utf-8")
    sulfur_ok = re.search(r"Mineral::Sulfur\s*=>\s*Some\(SignalKind::Pungent\)", text)
    coal_ok = re.search(r"Mineral::Coal\s*=>\s*Some\(SignalKind::Acrid\)", text)
    salt_ok = re.search(r"Mineral::Salt\s*=>\s*Some\(SignalKind::Saline\)", text)
    ok = sulfur_ok and coal_ok and salt_ok
    check("emission_for_mineral : Sulfur/Coal/Salt mapped correctly", bool(ok),
          f"S={bool(sulfur_ok)} C={bool(coal_ok)} Sa={bool(salt_ok)}")
except Exception as e:
    check("emission_for_mineral : Sulfur/Coal/Salt mapped correctly", False, str(e))

# ---------------------------------------------------------------------------
# 5. Odourless minerals not listed in emission match
# ---------------------------------------------------------------------------
try:
    text = CHEM_RS.read_text(encoding="utf-8")
    # extract the emission_for_mineral block
    block_match = re.search(
        r"emission_for_mineral.*?\{(.+?)^\}", text, re.DOTALL | re.MULTILINE
    )
    block = block_match.group(1) if block_match else text
    forbidden = ["Mineral::Gold", "Mineral::Iron", "Mineral::Malachite",
                 "Mineral::Silver", "Mineral::Quartz"]
    leaks = [m for m in forbidden
             if re.search(rf"{re.escape(m)}\s*=>\s*Some\(", block)]
    check("Odourless minerals stay odourless (Gold/Iron/etc.)",
          not leaks,
          f"leaks={leaks}" if leaks else "5 odourless minerals silent")
except Exception as e:
    check("Odourless minerals stay odourless (Gold/Iron/etc.)", False, str(e))

# ---------------------------------------------------------------------------
# 6. intensity_at signature
# ---------------------------------------------------------------------------
try:
    text = CHEM_RS.read_text(encoding="utf-8")
    sig = re.search(
        r"pub\s+fn\s+intensity_at\s*\(\s*emission:\s*ChemicalEmission",
        text,
    )
    wind_param = "wind_xy" in text
    check("intensity_at(emission, src, obs, wind_xy) signature",
          sig is not None and wind_param,
          f"fn={bool(sig)} wind_param={wind_param}")
except Exception as e:
    check("intensity_at(emission, src, obs, wind_xy) signature", False, str(e))

# ---------------------------------------------------------------------------
# 7. Decay lengths ordered Pungent > Acrid > Saline
# ---------------------------------------------------------------------------
try:
    text = CHEM_RS.read_text(encoding="utf-8")
    pung = re.search(r"SignalKind::Pungent\s*=>\s*([\d.]+)", text)
    acr = re.search(r"SignalKind::Acrid\s*=>\s*([\d.]+)", text)
    sal = re.search(r"SignalKind::Saline\s*=>\s*([\d.]+)", text)
    values = {
        "Pungent": float(pung.group(1)) if pung else None,
        "Acrid": float(acr.group(1)) if acr else None,
        "Saline": float(sal.group(1)) if sal else None,
    }
    ordered = (
        values["Pungent"] and values["Acrid"] and values["Saline"]
        and values["Pungent"] > values["Acrid"] > values["Saline"]
    )
    check("Decay lengths : Pungent > Acrid > Saline (physical realism)",
          ordered,
          f"values={values}")
except Exception as e:
    check("Decay lengths : Pungent > Acrid > Saline (physical realism)", False, str(e))

# ---------------------------------------------------------------------------
# 8/9/10. Critical tests declared (will run via cargo test in CI)
# ---------------------------------------------------------------------------
try:
    text = CHEM_RS.read_text(encoding="utf-8")
    critical_tests = [
        "intensity_decays_with_distance",
        "downwind_gets_more_than_upwind",
        "calm_wind_is_isotropic",
        "at_source_returns_full_strength",
        "determinism_of_emission_sampling",
        "coal_seam_emits_acrid_signal",
        "decay_lengths_are_ordered",
        "only_smelly_minerals_emit",
    ]
    missing = [t for t in critical_tests if f"fn {t}" not in text]
    check("Wave 44 critical Rust tests declared",
          not missing,
          f"missing={missing}" if missing else f"{len(critical_tests)} tests OK")
except Exception as e:
    check("Wave 44 critical Rust tests declared", False, str(e))

# Bonus check : tests appear via #[cfg(test)] (so they will be picked up).
try:
    text = CHEM_RS.read_text(encoding="utf-8")
    has_cfg = "#[cfg(test)]" in text and "mod tests" in text
    check("chemical.rs gates tests behind #[cfg(test)] mod tests", has_cfg,
          "test module present" if has_cfg else "test module MISSING")
except Exception as e:
    check("chemical.rs gates tests behind #[cfg(test)] mod tests", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p114 — Wave 44 Chemical Signals ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) raté(s).")
    sys.exit(1)
print("OK — tous les checks sont verts.")
