"""P19 — Wave 2 integration smoke (FUTURE-VISION Wave 2).

End-to-end exercise of the four Wave 2 mechanisms that the
:mod:`engine.material_synthesis` module now supports on top of Wave 1
(physics, chemistry, material_synthesis, statics):

  1. Ternary alloy synthesis — Fe + C + Mn (steel) emerges from a
     reducing-atmosphere bloomery, validating that the existing
     ``synthesize()`` API correctly handles 3-component compositions.

  2. Non-linear doping — pure Fe (Mohs ~1.8) vs steel (Fe + 1.5 % C +
     1.5 % Mn → Mohs ~6.2) demonstrates the interstitial-carbon boost
     introduced for Wave 2. Phosphor bronze (Cu host with Sn + P) is
     tagged as a doped composition while plain bronze (Cu70Sn30) is
     not (binary near-50/50 stays under the linear Vegard rule).

  3. Per-culture material registry — culture A (bronze-age, mid-temp
     furnace) discovers bronze; culture B (proto-industrial, hot forge)
     discovers steel. The registry tracks who knows what; ``culture_known``
     returns disjoint sets at this point.

  4. Recipe transmission — culture A teaches bronze to culture B via
     ``MaterialRegistry.transmit`` with a deterministic RNG seeded for
     reproducibility. After transmission, culture B knows both bronze
     and steel; culture A still only knows bronze.

The script prints a readable matrix and exits 0 on success, 1 on any
failed assertion. Determinism: every RNG call goes through a seeded
``random.Random``; the smoke is bit-stable across runs.
"""
from __future__ import annotations

import io
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
    MaterialRegistry,
    SynthesisConditions,
    SynthesizedMaterial,
    synthesize,
)


def _row(label: str, ok: bool, detail: str = "") -> str:
    mark = "OK  " if ok else "FAIL"
    return f"  [{mark}] {label:42s} {detail}"


def _expect(actual, op, expected, label: str):
    """Asserts and returns formatted row."""
    if op == ">=":
        ok = actual >= expected
    elif op == ">":
        ok = actual > expected
    elif op == "==":
        ok = actual == expected
    elif op == "approx":
        ok = abs(actual - expected) < 0.5
    else:
        ok = False
    detail = f"actual={actual!r} {op} {expected!r}"
    return ok, _row(label, ok, detail)


def main() -> int:
    print("=" * 78)
    print("P19 — Wave 2 integration (ternary + doping + registry + transmit)")
    print("=" * 78)

    failures = 0

    # ------------------------------------------------------------------
    # Step 1 — ternary alloy synthesis (steel)
    # ------------------------------------------------------------------
    rng_steel = random.Random(0xB155EE21)
    steel = synthesize(
        composition={"Fe": 0.97, "C": 0.015, "Mn": 0.015},
        conditions=SynthesisConditions(
            temperature_K=1800.0, atmosphere="reducing", time_s=7200.0,
        ),
        tools_available=("forge", "bloomery", "crucible"),
        culture_id=2,
        tick=100,
        rng=rng_steel,
    )
    ok = steel is not None and "Fe" in (steel.composition if steel else {})
    print(_row("step 1 — ternary steel synthesis",
               ok, f"name={steel.name if steel else 'None'}"))
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Step 2 — doping makes a measurable non-linear difference
    # ------------------------------------------------------------------
    rng_fe = random.Random(0xFE12011D)
    pure_fe = synthesize(
        composition={"Fe": 1.0},
        conditions=SynthesisConditions(
            temperature_K=1900.0, atmosphere="reducing"),
        tools_available=("forge", "bloomery"),
        culture_id=2,
        tick=99,
        rng=rng_fe,
    )
    h_fe = pure_fe.properties["hardness_mohs_estimate"] if pure_fe else 0
    h_steel = steel.properties["hardness_mohs_estimate"] if steel else 0
    delta_doping = (steel.properties["doping_boost_mohs"]
                    if steel else 0)
    ok, row = _expect(h_steel, ">=", h_fe + 3.0,
                      "step 2 — steel >= Fe + 3 Mohs")
    print(row)
    if not ok:
        failures += 1
    ok, row = _expect(delta_doping, ">=", 3.0,
                      "step 2 — doping boost >= 3.0 Mohs")
    print(row)
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Step 3 — non-doped vs doped recognition
    # ------------------------------------------------------------------
    rng_br = random.Random(0xB10AB10A)
    bronze = synthesize(
        composition={"Cu": 0.70, "Sn": 0.30},
        conditions=SynthesisConditions(
            temperature_K=1200.0, atmosphere="reducing"),
        tools_available=("forge",),
        culture_id=1,
        tick=50,
        rng=rng_br,
    )
    rng_ph = random.Random(0xC0B12_F0)
    phosphor_bronze = synthesize(
        composition={"Cu": 0.94, "Sn": 0.05, "P": 0.01},
        conditions=SynthesisConditions(
            temperature_K=1300.0, atmosphere="reducing"),
        tools_available=("forge", "crucible"),
        culture_id=1,
        tick=60,
        rng=rng_ph,
    )
    ok = (bronze is not None
          and bronze.properties["is_doped"] == 0.0
          and phosphor_bronze is not None
          and phosphor_bronze.properties["is_doped"] == 1.0)
    print(_row("step 3 — Cu70Sn30 not doped, Cu94Sn5P1 is doped",
               ok,
               (f"bronze.is_doped={bronze.properties['is_doped']:.0f}, "
                f"phbronze.is_doped="
                f"{phosphor_bronze.properties['is_doped']:.0f}")
               if (bronze and phosphor_bronze) else "synth failed"))
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Step 4 — per-culture registry isolation
    # ------------------------------------------------------------------
    reg = MaterialRegistry()
    bronze_id = reg.register(bronze)             # culture 1
    phbronze_id = reg.register(phosphor_bronze)  # culture 1
    steel_id = reg.register(steel)               # culture 2

    known_1 = {m.name for m in reg.culture_known(1)}
    known_2 = {m.name for m in reg.culture_known(2)}
    ok = (bronze.name in known_1
          and phosphor_bronze.name in known_1
          and steel.name not in known_1
          and steel.name in known_2
          and bronze.name not in known_2)
    print(_row("step 4 — cultures know disjoint subsets initially",
               ok,
               f"c1={sorted(known_1)} / c2={sorted(known_2)}"))
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Step 5 — recipe transmission with deterministic RNG
    # ------------------------------------------------------------------
    rng_trans = random.Random(0x123_45)
    learned = reg.transmit(
        from_culture=1, to_culture=2, material_id=bronze_id,
        rng=rng_trans, success_prob=0.95,
    )
    known_2_after = {m.name for m in reg.culture_known(2)}
    ok = (learned
          and bronze.name in known_2_after
          and steel.name in known_2_after)
    print(_row("step 5 — culture 1 transmits bronze to culture 2",
               ok, f"learned={learned}, c2={sorted(known_2_after)}"))
    if not ok:
        failures += 1

    # Sanity — transmission of a material the sender doesn't know
    rng_x = random.Random(0xFA1_FED)
    cannot = reg.transmit(
        from_culture=99, to_culture=2, material_id=bronze_id,
        rng=rng_x, success_prob=1.0,
    )
    ok = cannot is False
    print(_row("step 5b — non-knowing sender cannot transmit",
               ok, f"returned={cannot}"))
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    if failures == 0:
        print("RESULT: PASS — Wave 2 integration smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} assertion(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
