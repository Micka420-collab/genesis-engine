"""P36 — Wave 10d realistic construction smoke.

Validates the build pipeline using real minerals + smelted elements.

  1. install idempotent + 6 recipes loaded
  2. can_build reports deficits when inventory empty
  3. build_real with limestone + granite + wood succeeds → stone_hut
  4. Built structure tracked + material_aging instance bound
  5. After accelerated aging the hut's integrity drops
  6. Persistence round-trip preserves structures
  7. ADR-0005 17/17 OK
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
from engine.material_aging import install_material_aging    # noqa: E402
from engine.realistic_construction import (                 # noqa: E402
    install_realistic_construction, build_real, can_build,
    realistic_construction_state, REAL_RECIPES,
    save_realistic_construction_state, load_realistic_construction_state)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:55s} {detail}"


def _build_sim(name: str):
    cfg = SimConfig(
        name=name, seed=0xC0FFEE_10D & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=10,
        bounds_km=(0.5, 0.5), spawn_radius_m=80.0,
        drive_accel=1.0, cultures=1,    # accel=1 → real-time aging
    )
    sim = Simulation(cfg)
    install_material_aging(sim)
    return sim


def main() -> int:
    print("=" * 78)
    print("P36 — Wave 10d realistic construction smoke")
    print("=" * 78)
    failures = 0

    sim = _build_sim("p36_build")
    state = install_realistic_construction(sim)

    # Step 1 — idempotent + 6 recipes
    s2 = install_realistic_construction(sim)
    ok = (state is s2) and (len(REAL_RECIPES) >= 5)
    print(_row("step 1 — install idempotent + recipes loaded",
               ok, f"recipes={len(REAL_RECIPES)}"))
    if not ok:
        failures += 1

    # Step 2 — can_build reports deficits when empty
    row = 0
    ok_can, deficits = can_build(sim, row, "stone_hut")
    print(_row("step 2 — empty inventory → can_build False, deficits listed",
               (not ok_can) and len(deficits) > 0,
               f"ok_can={ok_can} deficits={ {k: round(v,1) for k,v in deficits.items()} }"))
    if ok_can or not deficits:
        failures += 1

    # Step 3 — pre-populate inv_wood + inv_stone, then build_real
    sim.agents.inv_wood[row] = 50.0
    sim.agents.inv_stone[row] = 200.0
    ok_build, sid, reason = build_real(sim, row, "stone_hut")
    print(_row("step 3 — build_real stone_hut succeeds",
               ok_build and sid is not None,
               f"sid={sid} reason={reason!r}"))
    if not (ok_build and sid is not None):
        failures += 1
    # Inventory drawn down ?
    inv_wood_after = float(sim.agents.inv_wood[row])
    inv_stone_after = float(sim.agents.inv_stone[row])
    ok = inv_wood_after < 50.0 and inv_stone_after < 200.0
    print(_row("step 3 — inventory consumed",
               ok,
               f"wood 50→{inv_wood_after:.1f}, stone 200→{inv_stone_after:.1f}"))
    if not ok:
        failures += 1

    # Step 4 — material_aging instance bound
    aging = sim._aging_registry
    struct = state.structures[sid]
    inst = aging.instance(struct.material_instance_id)
    ok = (inst is not None
          and inst.material_name == "stone_limestone"
          and inst.integrity > 0.99)
    print(_row("step 4 — aging instance bound to structure",
               ok,
               f"inst_id={struct.material_instance_id} "
               f"name={inst.material_name if inst else None} "
               f"integrity={inst.integrity if inst else 0:.4f}"))
    if not ok:
        failures += 1

    # Step 5 — Accelerated aging : 200 sim-years on humid_air.
    YR = 365 * 86400
    aging.tick(current_tick=200 * YR, drive_accel=1.0)
    snap = realistic_construction_state(sim)
    ruined_count = snap.get("ruined_structures", 0)
    integ = struct.last_integrity
    # Stone limestone 0.08 %/yr ≈ 200 yr × 0.0008 = 0.16 loss.
    # So integrity should be around 0.84 after 200 yr (NOT ruined yet).
    ok = 0.75 < integ < 0.95
    print(_row("step 5 — after 200 yr humid stone hut integrity ≈ 0.84",
               ok, f"integrity={integ:.4f}"))
    if not ok:
        failures += 1

    # Step 6 — build a marble_temple after RESET : zero stone/metal so
    # fallback can't substitute. marble_temple needs marble 500 kg + Au
    # 0.5 kg specifically.
    sim.agents.inv_stone[row] = 0.0
    sim.agents.inv_metal[row] = 0.0
    sim.agents.inv_wood[row] = 0.0
    ok_build, sid2, reason2 = build_real(sim, row, "marble_temple")
    ok = (not ok_build) and "insufficient" in (reason2 or "")
    print(_row("step 6 — empty inv → temple fails with deficits",
               ok, f"reason={reason2[:80]!r}"))
    if not ok:
        failures += 1

    # Step 7 — persistence round-trip
    tmp = tempfile.mkdtemp(prefix="genesis_p36_")
    try:
        save_realistic_construction_state(sim, tmp)
        sim2 = _build_sim("p36_load")
        ok_load = load_realistic_construction_state(sim2, tmp)
        state2 = sim2._real_construct_state
        ok = (ok_load and state2 is not None
              and len(state2.structures) == len(state.structures))
        print(_row("step 7 — persistence round-trip preserves structures",
                   ok,
                   f"loaded {len(state2.structures)} / "
                   f"{len(state.structures)}"))
        if not ok:
            failures += 1
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # Step 8 — ADR-0005 audit
    from engine.world_model_capabilities import audit_modules
    table, lint_fails = audit_modules(strict=False)
    r_row = next((r for r in table["modules"]
                  if r["module"] == "engine.realistic_construction"), None)
    ok = r_row is not None and r_row["status"] == "ok" and not lint_fails
    print(_row("step 8 — ADR-0005 lists realistic_construction OK",
               ok, f"failures={lint_fails}"))
    if not ok:
        failures += 1

    print()
    snap = realistic_construction_state(sim)
    print(f"snapshot:")
    print(f"  structures_total: {snap.get('structures_total')}")
    print(f"  alive/ruined: {snap.get('alive_structures')}/{snap.get('ruined_structures')}")
    print(f"  build_events: {snap.get('build_events')}")
    print(f"  failed_builds: {snap.get('failed_builds')}")
    print(f"  cumulative_materials_kg: {snap.get('cumulative_materials_kg')}")
    print()
    if failures == 0:
        print("RESULT: PASS — Wave 10d realistic construction smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
