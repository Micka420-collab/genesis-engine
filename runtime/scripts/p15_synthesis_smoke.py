"""Sprint B3 smoke — physics-constrained material synthesis.

Pass criteria (>=3/4 tests must succeed):
    1. Bronze synth      : Cu70Sn30 @ 1200 K reducing forge -> material.
    2. Cold rejection    : same Cu70Sn30 @ 200 K -> None, temperature reason.
    3. Mass conservation : Cu50Sn30 (sum 0.80) -> None, mass_conservation.
    4. Property sanity   : bronze density ~8.5 g/cm^3, melting ~1200 K.
"""
from __future__ import annotations

import io
import json
import os
import random
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.material_synthesis import (  # noqa: E402
    MaterialRegistry, SynthesisConditions, check_physical_validity, synthesize,
)


def _ok(name: str, ok: bool, detail: str = "") -> bool:
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name}" + (f" -- {detail}" if detail else ""))
    return ok


def main() -> int:
    print("=" * 60)
    print("Sprint B3 smoke test -- material_synthesis")
    print("=" * 60)
    rng = random.Random(42)
    registry = MaterialRegistry()
    results = []

    # ------------------------------------------------------------------
    # Test 1 -- bronze synthesis (valid)
    # ------------------------------------------------------------------
    print("\n[Test 1] Bronze synthesis (Cu70Sn30, T=1200K, reducing, forge)")
    composition = {"Cu": 0.7, "Sn": 0.3}
    conds = SynthesisConditions(
        temperature_K=1200.0,
        atmosphere="reducing",
        time_s=3600.0,
    )
    bronze = synthesize(
        composition, conds,
        tools_available=("forge",),
        culture_id=1, tick=100, rng=rng,
    )
    t1 = bronze is not None
    if bronze is not None:
        registry.register(bronze)
        print(f"    name        : {bronze.name}")
        print(f"    composition : {bronze.composition}")
        print(f"    density     : {bronze.properties['density_g_cm3']:.2f} g/cm^3")
        print(f"    melting     : {bronze.properties['melting_point_K']:.0f} K")
        print(f"    hardness    : {bronze.properties['hardness_mohs_estimate']:.1f} Mohs")
        print(f"    metal frac  : {bronze.properties['metal_fraction']:.2f}")
    else:
        ok, reason = check_physical_validity(composition, conds, ("forge",))
        print(f"    UNEXPECTED None -- reason='{reason}'")
    results.append(_ok("bronze_synth_valid", t1))

    # ------------------------------------------------------------------
    # Test 2 -- temperature too low
    # ------------------------------------------------------------------
    print("\n[Test 2] Cold rejection (Cu70Sn30, T=200K)")
    cold = SynthesisConditions(temperature_K=200.0, atmosphere="reducing")
    cold_mat = synthesize(composition, cold, tools_available=("forge",))
    ok2, reason2 = check_physical_validity(composition, cold, ("forge",))
    t2 = (cold_mat is None) and ("temperature" in reason2.lower())
    print(f"    material    : {cold_mat}")
    print(f"    reason      : '{reason2}'")
    results.append(_ok("temperature_rejection", t2, reason2))

    # ------------------------------------------------------------------
    # Test 3 -- mass conservation violation
    # ------------------------------------------------------------------
    print("\n[Test 3] Mass conservation (Cu50Sn30, sum=0.80)")
    bad = {"Cu": 0.5, "Sn": 0.3}
    bad_conds = SynthesisConditions(temperature_K=1200.0, atmosphere="reducing")
    bad_mat = synthesize(bad, bad_conds, tools_available=("forge",))
    ok3, reason3 = check_physical_validity(bad, bad_conds, ("forge",))
    t3 = (bad_mat is None) and reason3.startswith("mass_conservation")
    print(f"    material    : {bad_mat}")
    print(f"    reason      : '{reason3}'")
    results.append(_ok("mass_conservation", t3, reason3))

    # ------------------------------------------------------------------
    # Test 4 -- property sanity (bronze ~8.5 g/cm^3, melting ~1200 K)
    # ------------------------------------------------------------------
    print("\n[Test 4] Property sanity (bronze density & melting point)")
    if bronze is not None:
        rho = bronze.properties["density_g_cm3"]
        mp = bronze.properties["melting_point_K"]
        rho_ok = 7.5 <= rho <= 9.5
        # Real bronze melts ~1200 K; Vegard rule on Cu(1357)+Sn(505) at 70/30
        # gives ~1102 K. Accept anything in [950, 1400] K as physically sane.
        mp_ok = 950.0 <= mp <= 1400.0
        t4 = rho_ok and mp_ok
        print(f"    density     : {rho:.2f} g/cm^3 (target 8.5, accept 7.5-9.5) -> {rho_ok}")
        print(f"    melting     : {mp:.0f} K (target ~1200, accept 950-1400) -> {mp_ok}")
    else:
        t4 = False
        print("    bronze missing -- cannot evaluate properties")
    results.append(_ok("property_sanity", t4))

    # ------------------------------------------------------------------
    # Bonus: registry round-trip
    # ------------------------------------------------------------------
    if bronze is not None:
        looked = registry.lookup_by_name(bronze.name)
        print(f"\n[Bonus] registry.lookup_by_name -> {looked.name if looked else None}")
        culture_mats = registry.culture_known(1)
        print(f"        culture 1 knows {len(culture_mats)} material(s)")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    n_pass = sum(results)
    n_total = len(results)
    print("\n" + "=" * 60)
    print(f"Result : {n_pass}/{n_total} tests passed")
    print("=" * 60)
    return 0 if n_pass >= 3 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
