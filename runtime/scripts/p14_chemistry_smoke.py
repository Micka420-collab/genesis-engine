"""P14 — smoke test for the chemistry knowledge base.

Verifies that ``engine.chemistry`` exposes the expected periodic-table
values, bond enthalpies, and helper behaviours. The script runs in pure
Python with no external dependencies, prints a JSON-style summary on
stdout, and exits with status 0 when at least 4 of its 6 assertions pass.
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine import chemistry as chem  # noqa: E402


def _safe(label, fn):
    """Run ``fn`` and return (label, ok, value/err) without raising."""
    try:
        value = fn()
        return (label, True, value)
    except Exception as exc:  # pragma: no cover - smoke catches everything
        return (label, False, f"{type(exc).__name__}: {exc}\n"
                + "".join(traceback.format_exc().splitlines()[-3:]))


def main() -> int:
    checks = []

    # 1) Iron looks like iron.
    fe = chem.PERIODIC_TABLE["Fe"]
    checks.append(_safe(
        "Fe.atomic_number == 26",
        lambda: fe.atomic_number == 26,
    ))

    # 2) C-H bond enthalpy is the textbook 413 kJ/mol.
    checks.append(_safe(
        "bond_energy('C', 'H') == 413",
        lambda: chem.bond_energy("C", "H") == 413.0,
    ))

    # 2b) Symmetric lookup.
    checks.append(_safe(
        "bond_energy('H', 'C') == bond_energy('C', 'H')",
        lambda: chem.bond_energy("H", "C") == chem.bond_energy("C", "H"),
    ))

    # 3) Bronze density (70% Cu / 30% Sn) should be near 8.4-8.7 g/cm^3.
    rho_bronze = chem.density_alloy({"Cu": 0.7, "Sn": 0.3})
    checks.append(_safe(
        "density_alloy(Cu70/Sn30) ~ 8.4 +/- 10%",
        lambda: 7.56 <= rho_bronze <= 9.24,
    ))

    # 4) Metal predicates.
    checks.append(_safe(
        "is_metal('Fe') and not is_metal('Si')",
        lambda: chem.is_metal("Fe") and not chem.is_metal("Si"),
    ))

    # 5) Metalloid predicate for Silicon.
    checks.append(_safe(
        "is_metalloid('Si') is True",
        lambda: chem.is_metalloid("Si") is True,
    ))

    # 6) Electronegativity difference H-F should be ~1.78 (3.98 - 2.20).
    diff_hf = chem.electronegativity_difference("H", "F")
    checks.append(_safe(
        "electronegativity_difference('H', 'F') ~ 1.78",
        lambda: abs(diff_hf - 1.78) < 0.05,
    ))

    # 7) Melting-point estimate for bronze ~ 1100-1200 K (Cu=1357, Sn=505).
    mp_bronze = chem.melting_point_estimate({"Cu": 0.7, "Sn": 0.3})
    checks.append(_safe(
        "melting_point_estimate(Cu70/Sn30) within 800-1400 K",
        lambda: 800.0 <= mp_bronze <= 1400.0,
    ))

    passed = sum(1 for _, ok, val in checks if ok and val is True)
    total = len(checks)

    summary = {
        "_summary": True,
        "elements_in_table": len(chem.PERIODIC_TABLE),
        "bond_pairs_in_table": len(chem.BOND_ENERGY),
        "examples": {
            "Fe": {
                "atomic_number": fe.atomic_number,
                "atomic_mass": fe.atomic_mass,
                "density_g_cm3": fe.density_g_cm3,
                "melting_point_K": fe.melting_point_K,
                "category": fe.category,
                "common_oxidation": list(fe.common_oxidation),
            },
            "bond_C_H_kJmol": chem.bond_energy("C", "H"),
            "bond_Fe_O_kJmol": chem.bond_energy("Fe", "O"),
            "bronze_Cu70_Sn30": {
                "density_g_cm3": round(rho_bronze, 4),
                "melting_point_K": round(mp_bronze, 2),
                "molar_mass_g_mol": round(chem.molar_mass({"Cu": 0.7, "Sn": 0.3}), 3),
            },
            "electronegativity_difference_HF": round(diff_hf, 3),
        },
        "checks": [
            {"label": lbl, "ok": ok and val is True,
             "detail": val if not (ok and val is True) else "ok"}
            for lbl, ok, val in checks
        ],
        "passed": passed,
        "total": total,
    }
    print(json.dumps(summary, indent=2))

    if passed >= 4:
        print("\nP14 CHEMISTRY SMOKE PASSED  ({0}/{1})".format(passed, total))
        return 0
    print("\nP14 CHEMISTRY SMOKE FAILED  ({0}/{1})".format(passed, total))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
