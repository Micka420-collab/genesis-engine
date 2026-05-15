"""P37 — Wave 10e emergent building discovery smoke.

The "rule" of the project : nothing is scripted, everything must be
discovered. This smoke proves that the building system has zero
recipe table — agents that place blocks have their structure
*validated* by Wave 1 statics, and if it's stable + functional, an
archetype emerges with an auto-generated name.

  1. install idempotent
  2. Place too few blocks → function_failure (no recipe, no scripting)
  3. Place a tall but unsupported overhang → structural_failure
  4. Place a closed 3×3×2 stone shelter → succeeds, archetype emerges
  5. Same culture builds the same shape → matches existing archetype
     (cultural recognition without external recipe table)
  6. Different culture builds the same shape → DIFFERENT name
     (independent cultural naming — like real cultures)
  7. Persistence round-trip preserves archetypes
  8. ADR-0005 18/18 OK
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.sim import Simulation, SimConfig                # noqa: E402
from engine.building_discovery import (                     # noqa: E402
    install_building_discovery, place_block, complete_structure,
    abandon_pending, building_discovery_state,
    save_building_discovery_state, load_building_discovery_state)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:55s} {detail}"


def _build_sim(name: str):
    cfg = SimConfig(
        name=name, seed=0xC0FFEE_10E & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=10,
        bounds_km=(0.2, 0.2), spawn_radius_m=50.0,
        drive_accel=1.0, cultures=2,
    )
    return Simulation(cfg)


def _build_3x3x2_shelter(sim, row, material="stone"):
    """Helper: stack a 3×3×2 stone shelter (with roof)."""
    # Bottom layer (3×3 = 9 blocks)
    for x in range(3):
        for y in range(3):
            # Skip a doorway hole at (1,1) of the bottom layer.
            if (x, y) == (1, 1):
                continue
            place_block(sim, row, (x, y, 0), material)
    # Top layer (3×3 = 9 blocks roof) - keep full coverage
    for x in range(3):
        for y in range(3):
            place_block(sim, row, (x, y, 1), material)


def main() -> int:
    print("=" * 78)
    print("P37 — Wave 10e emergent building discovery")
    print("=" * 78)
    failures = 0

    sim = _build_sim("p37_disc")
    state = install_building_discovery(sim)

    # Step 1 — idempotent
    s2 = install_building_discovery(sim)
    print(_row("step 1 — install_building_discovery idempotent",
               state is s2))
    if state is not s2:
        failures += 1

    # Step 2 — too few blocks → function_failure
    row = 0
    place_block(sim, row, (0, 0, 0), "stone")
    place_block(sim, row, (0, 0, 1), "stone")
    ok_c, bid, reason = complete_structure(sim, row)
    ok = (not ok_c) and reason.startswith("function:")
    print(_row("step 2 — too few blocks → function_failure",
               ok, f"reason={reason!r}"))
    if not ok:
        failures += 1

    # Step 3 — A floating overhang that's not supported.
    # (single block at z=5 with nothing under it)
    abandon_pending(sim, row)
    # Build 8 blocks but with all of them floating (z=10)
    for x in range(2):
        for y in range(2):
            for z in range(10, 12):
                place_block(sim, row, (x, y, z), "stone")
    ok_c, bid, reason = complete_structure(sim, row)
    ok = (not ok_c) and reason.startswith("unstable:")
    print(_row("step 3 — floating blocks → structural_failure",
               ok, f"reason={reason[:60]!r}"))
    if not ok:
        failures += 1

    # Step 4 — A real 3×3×2 stone shelter (no recipe, just blocks).
    abandon_pending(sim, row)
    _build_3x3x2_shelter(sim, row, material="stone")
    ok_c, bid, name = complete_structure(sim, row)
    ok = ok_c and bid is not None and name and "stone" in name
    print(_row("step 4 — 3x3x2 stone shelter → archetype emerges",
               ok, f"name={name!r} bid={bid}"))
    if not ok:
        failures += 1

    # Step 5 — same culture builds an identical shape → same archetype.
    first_name = name
    _build_3x3x2_shelter(sim, row, material="stone")
    ok_c, bid2, name2 = complete_structure(sim, row)
    ok = ok_c and name2 == first_name
    print(_row("step 5 — same culture same shape → same archetype",
               ok, f"first={first_name} second={name2}"))
    if not ok:
        failures += 1

    # Step 6 — different culture (agent row=1, culture=1 if available).
    # We can't actually set culture via sim.agents.culture (attribute doesn't
    # exist by default). So we patch it on the agents object.
    import numpy as np
    if not hasattr(sim.agents, "culture"):
        sim.agents.culture = np.zeros(sim.agents.capacity, dtype=np.int32)
    sim.agents.culture[1] = 99  # row 1 in culture 99
    _build_3x3x2_shelter(sim, 1, material="stone")
    ok_c, bid3, name3 = complete_structure(sim, 1)
    ok = ok_c and name3 != first_name  # different culture → different name
    print(_row("step 6 — different culture → different name",
               ok, f"culture_0={first_name} culture_99={name3}"))
    if not ok:
        failures += 1

    # Step 7 — persistence round-trip
    tmp = tempfile.mkdtemp(prefix="genesis_p37_")
    try:
        save_building_discovery_state(sim, tmp)
        sim2 = _build_sim("p37_load")
        install_building_discovery(sim2)
        ok_load = load_building_discovery_state(sim2, tmp)
        s2 = sim2._building_discovery_state
        ok = (ok_load
              and len(s2.buildings) == len(state.buildings)
              and sum(len(d) for d in s2.cultural_archetypes.values())
                  == sum(len(d) for d in state.cultural_archetypes.values()))
        print(_row("step 7 — persistence round-trip",
                   ok,
                   f"buildings={len(s2.buildings)}/{len(state.buildings)}"))
        if not ok:
            failures += 1
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # Step 8 — ADR-0005 audit
    from engine.world_model_capabilities import audit_modules
    table, lint_fails = audit_modules(strict=False)
    b_row = next((r for r in table["modules"]
                  if r["module"] == "engine.building_discovery"), None)
    ok = b_row is not None and b_row["status"] == "ok" and not lint_fails
    print(_row("step 8 — ADR-0005 lists building_discovery OK",
               ok, f"failures={lint_fails}"))
    if not ok:
        failures += 1

    print()
    snap = building_discovery_state(sim)
    print(f"discovery snapshot:")
    print(f"  attempts: {snap.get('attempts_total')}")
    print(f"  successes: {snap.get('successes_total')}")
    print(f"  structural_failures: {snap.get('structural_failures')}")
    print(f"  function_failures: {snap.get('function_failures')}")
    print(f"  archetypes per culture:")
    for cul, archs in (snap.get("archetypes_per_culture") or {}).items():
        for a in archs:
            print(f"    culture {cul}: {a['name']} ({a['instances']}x)")
    print()
    if failures == 0:
        print("RESULT: PASS — Wave 10e building discovery smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
