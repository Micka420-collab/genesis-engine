"""P22 — Wave 4 material aging smoke test.

Validates the per-instance degradation model :

  1. Iron rusts faster than bronze under humid air.
  2. Salt water multiplies iron loss by ~6x vs humid air.
  3. Oiling cuts iron loss roughly in half.
  4. Wood instances die out in a few simulated years.
  5. Granite barely loses integrity over a sim year.
  6. ADR-0005 audit lists engine.material_aging as required-tagged.

No real sim needed — the registry operates on its own clock.
"""
from __future__ import annotations

import io
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stdout.buffer.detach() if False
                                  else sys.stderr.buffer,
                                  encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.material_aging import (  # noqa: E402
    MaterialAgingRegistry,
)


YEAR_TICKS = 365 * 86400  # at TICK_DT_S = 1 and drive_accel = 1.0


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:50s} {detail}"


def _make_reg():
    return MaterialAgingRegistry()


def main() -> int:
    print("=" * 78)
    print("P22 — Wave 4 material aging smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — Iron vs bronze under humid air for one sim-year.
    reg = _make_reg()
    iron = reg.spawn(material_id=1, material_name="alloy_Fe98C2",
                     owner_culture=1, spawned_tick=0,
                     exposure_mode="humid_air")
    bronze = reg.spawn(material_id=2, material_name="alloy_Cu70Sn30",
                       owner_culture=1, spawned_tick=0,
                       exposure_mode="humid_air")
    reg.tick(YEAR_TICKS, drive_accel=1.0)
    di = 1.0 - iron.integrity
    db = 1.0 - bronze.integrity
    ok = di > db * 5.0
    print(_row("step 1 — iron rusts faster than bronze 1 yr humid",
               ok, f"Δiron={di:.4f} Δbronze={db:.4f} ratio={di/max(db,1e-9):.1f}"))
    if not ok:
        failures += 1

    # Step 2 — salt water multiplier on iron.
    reg = _make_reg()
    iron_humid = reg.spawn(1, "alloy_Fe98C2", 1, 0, "humid_air")
    iron_salt = reg.spawn(1, "alloy_Fe98C2", 1, 0, "salt_water")
    reg.tick(YEAR_TICKS, drive_accel=1.0)
    dh = 1.0 - iron_humid.integrity
    ds = 1.0 - iron_salt.integrity
    ratio = ds / max(dh, 1e-9)
    ok = 4.0 < ratio < 9.0
    print(_row("step 2 — salt water ≈ 6× humid for iron",
               ok, f"Δhumid={dh:.4f} Δsalt={ds:.4f} ratio={ratio:.2f}"))
    if not ok:
        failures += 1

    # Step 3 — oiling cuts iron loss roughly in half.
    reg = _make_reg()
    plain = reg.spawn(1, "alloy_Fe98C2", 1, 0, "humid_air")
    oiled = reg.spawn(1, "alloy_Fe98C2", 2, 0, "humid_air")
    reg.teach_practice(2, "oiling")
    reg.tick(YEAR_TICKS, drive_accel=1.0)
    dp = 1.0 - plain.integrity
    do = 1.0 - oiled.integrity
    ratio = do / max(dp, 1e-9)
    ok = 0.30 < ratio < 0.55
    print(_row("step 3 — oiling drops iron decay to ~0.4× plain",
               ok, f"Δplain={dp:.4f} Δoiled={do:.4f} ratio={ratio:.3f}"))
    if not ok:
        failures += 1

    # Step 4 — wood rots out within a few years if humid + wet soil.
    reg = _make_reg()
    log = reg.spawn(1, "wood_oak", 1, 0, "wet_soil")
    # 5 sim-years of wet contact.
    reg.tick(5 * YEAR_TICKS, drive_accel=1.0)
    ok = log.integrity < 0.30
    print(_row("step 4 — wet wood lost > 70 % integrity in 5 yr",
               ok, f"integrity={log.integrity:.4f}"))
    if not ok:
        failures += 1

    # Step 5 — granite barely loses anything in 1 yr.
    reg = _make_reg()
    g = reg.spawn(1, "stone_granite", 1, 0, "humid_air")
    reg.tick(YEAR_TICKS, drive_accel=1.0)
    dg = 1.0 - g.integrity
    ok = dg < 1e-3
    print(_row("step 5 — granite loses < 0.001 in 1 yr",
               ok, f"loss={dg:.6f}"))
    if not ok:
        failures += 1

    # Step 6 — ADR-0005 audit.
    from engine.world_model_capabilities import audit_modules
    table, lint_fails = audit_modules(strict=False)
    rows = table["modules"]
    aging_row = next((r for r in rows
                      if r["module"] == "engine.material_aging"), None)
    ok = aging_row is not None and aging_row["status"] == "ok" and not lint_fails
    print(_row("step 6 — ADR-0005 lists material_aging OK",
               ok,
               f"status={aging_row['status'] if aging_row else 'missing'}"))
    if not ok:
        failures += 1

    print()
    if failures == 0:
        print("RESULT: PASS — Wave 4 material aging smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
