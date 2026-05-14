"""P17 — Wave 1 integration smoke (Sprint B5).

End-to-end consumer of the four Wave 1 modules (physics, chemistry,
material_synthesis, statics). Scenario:

    "A Bronze Age civilisation invents bronze and builds a wall."

  Step 1: physics.gibbs_free_energy — verify that a simple exothermic
          reaction (dH=-50 kJ, dS=+10 J/K @ 1200 K) is spontaneous.
  Step 2: chemistry.PERIODIC_TABLE["Cu"] + density_alloy({"Cu":0.7,"Sn":0.3})
          to characterise the alloy at the periodic-table level.
  Step 3: material_synthesis.synthesize(...) at 1200 K in a reducing
          atmosphere with a forge tool — expect a valid SynthesizedMaterial.
  Step 4: statics.Structure with 10 bronze blocks in a 5x2 wall, verify
          that ``is_structurally_stable()`` returns True.

Exit codes:
  0  - all four steps passed
  1  - one or more Wave 1 modules failed to import (B1-B4 not committed)
  2  - modules imported OK but at least one scenario step failed
"""
from __future__ import annotations

import io
import os
import sys
import traceback

# UTF-8 stdout (Windows console safety)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)


# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------
MODULES = ("physics", "chemistry", "material_synthesis", "statics")
loaded: dict[str, object] = {}
import_errors: dict[str, str] = {}

for name in MODULES:
    try:
        mod = __import__(f"engine.{name}", fromlist=[name])
        loaded[name] = mod
    except Exception as exc:  # noqa: BLE001 - we want to report any failure
        import_errors[name] = f"{type(exc).__name__}: {exc}"


def _row(label: str, ok: bool, detail: str = "") -> str:
    mark = "OK  " if ok else "FAIL"
    return f"  [{mark}] {label:38s} {detail}"


def main() -> int:
    print("=" * 78)
    print(" P17 — FUTURE-VISION Wave 1 integration smoke")
    print("=" * 78)

    # ----- Module load report -------------------------------------------
    print("\n[1/2] Module load report")
    for name in MODULES:
        if name in loaded:
            print(_row(f"engine.{name}", True, "loaded"))
        else:
            print(_row(f"engine.{name}", False, import_errors.get(name, "?")))

    if import_errors:
        print("\n*** Wave 1 module(s) not yet committed at smoke time. ***")
        for name, err in import_errors.items():
            print(f"    - engine.{name}: {err}")
        return 1

    physics = loaded["physics"]
    chemistry = loaded["chemistry"]
    material_synthesis = loaded["material_synthesis"]
    statics = loaded["statics"]

    # ----- Scenario steps ------------------------------------------------
    print("\n[2/2] Bronze Age scenario")
    results: list[tuple[str, bool, str]] = []

    # Step 1 — Gibbs free energy negative for exothermic reaction at 1200 K
    try:
        dG = physics.gibbs_free_energy(dH_J=-50_000.0, T_K=1200.0,
                                       dS_J_per_K=10.0)
        ok = bool(physics.is_thermodynamically_favorable(dG))
        results.append(("S1 gibbs_free_energy spontaneous",
                        ok, f"dG = {float(dG):+.1f} J/mol"))
    except Exception as exc:  # noqa: BLE001
        results.append(("S1 gibbs_free_energy spontaneous", False,
                        f"{type(exc).__name__}: {exc}"))

    # Step 2 — Copper entry + alloy density
    try:
        cu = chemistry.PERIODIC_TABLE["Cu"]
        rho = chemistry.density_alloy({"Cu": 0.7, "Sn": 0.3})
        ok = (cu.symbol == "Cu") and (rho > 0.0)
        results.append(("S2 PERIODIC_TABLE + density_alloy",
                        ok, f"Cu Z={cu.atomic_number}, rho={rho:.2f} g/cm^3"))
    except Exception as exc:  # noqa: BLE001
        results.append(("S2 PERIODIC_TABLE + density_alloy", False,
                        f"{type(exc).__name__}: {exc}"))

    # Step 3 — material_synthesis.synthesize -> SynthesizedMaterial
    # The B3 entry point may return ``None`` if the physical-validity check
    # rejects the proposal, or raise if its internal contract with the B2
    # periodic table differs (e.g. dict-style vs dataclass access).
    try:
        SynthesisConditions = material_synthesis.SynthesisConditions
        conditions = SynthesisConditions(temperature_K=1200.0,
                                         atmosphere="reducing")
        material = material_synthesis.synthesize(
            composition={"Cu": 0.7, "Sn": 0.3},
            conditions=conditions,
            tools_available=("forge",),
        )
        # A valid synthesis returns a SynthesizedMaterial; rejection -> None.
        ok = material is not None
        detail = (f"-> {material.name}" if ok
                  else "synthesize() returned None (validity check failed)")
        results.append(("S3 material_synthesis.synthesize bronze", ok, detail))
    except Exception as exc:  # noqa: BLE001
        results.append(("S3 material_synthesis.synthesize bronze", False,
                        f"{type(exc).__name__}: {exc}"))
        material = None  # type: ignore[assignment]

    # Step 4 — statics.Structure 5x2 bronze wall, stable
    # B4 exposes ``Structure(structure_id, blocks=[VoxelBlock,...])`` and
    # module-level ``is_structurally_stable(structure)``. We build the wall
    # via ``Structure.from_positions(...)`` to keep the call site short.
    try:
        Structure = statics.Structure
        positions = [(col, 0, row) for row in range(2) for col in range(5)]
        wall = Structure.from_positions(
            structure_id=1,
            positions=positions,
            material="bronze",
        )
        stable, reason = statics.is_structurally_stable(wall)
        results.append(("S4 statics bronze wall 5x2 stable",
                        bool(stable),
                        f"blocks={len(wall.blocks)}, reason={reason}"))
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc(limit=2)
        results.append(("S4 statics bronze wall 5x2 stable", False,
                        f"{type(exc).__name__}: {exc}"))

    for label, ok, detail in results:
        print(_row(label, ok, detail))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("\n" + "-" * 78)
    print(f" Steps passed: {passed} / {total}")
    print("-" * 78)

    if passed == total:
        print("\n[PASS] P17 Wave 1 integration scenario complete.")
        return 0
    print("\n[FAIL] P17 Wave 1 integration scenario incomplete.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
