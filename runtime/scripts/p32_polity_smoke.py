"""P32 — Phase 4 polity smoke test.

Validates emergence + taxation + redistribution + leader election +
persistence + law enforcement.

  1. install_polity is idempotent.
  2. found_polity creates a polity with members.
  3. Tax tick: each member's inv_food drops by TAX_RATE, treasury rises.
  4. Redistribute tick: hungry members receive food from treasury.
  5. Leader election picks the agent with highest prestige (here:
     offspring_count).
  6. Polity disbands when members drop below threshold.
  7. ADR-0005 audit clean (14/14).
  8. Persistence round-trip preserves polities + treasuries.
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
from engine.polity import (                                 # noqa: E402
    install_polity, polity_state,
    tick_polity, _tax, _redistribute, _re_elect_leader,
    found_polity, TAX_RATE, REDISTRIBUTE_HUNGER_THRESHOLD,
    KCAL_PER_KG_FOOD, POLITY_DISBAND_MEMBERS,
    save_polity_state, load_polity_state)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:55s} {detail}"


def _build_sim(name: str, founders: int = 5):
    cfg = SimConfig(
        name=name, seed=0xC0FFEE_50 & 0xFFFFFFFFFFFFFFFF,
        founders=founders, max_agents=20,
        bounds_km=(0.5, 0.5), spawn_radius_m=80.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def main() -> int:
    print("=" * 78)
    print("P32 — Phase 4 polity smoke")
    print("=" * 78)
    failures = 0

    sim = _build_sim("p32_polity", founders=5)
    state = install_polity(sim)

    # Step 1 — idempotent
    s2 = install_polity(sim)
    print(_row("step 1 — install_polity idempotent",
               state is s2, ""))
    if state is not s2:
        failures += 1

    # Step 2 — found_polity manually
    members = [1, 2, 3, 4]  # 4 members + leader (0) = 5
    pid = found_polity(sim, state, founder_row=0, members=members,
                       name="testopia")
    polity = state.polities.get(pid)
    ok = (polity is not None and len(polity.member_rows) == 5
          and polity.leader_row == 0)
    print(_row("step 2 — found_polity creates polity with 5 members",
               ok, f"pid={pid} members={len(polity.member_rows) if polity else 0}"))
    if not ok:
        failures += 1

    # Pre-set agent inventories so tax + redistribute has something to do.
    for r in [0, 1, 2, 3, 4]:
        sim.agents.inv_food[r] = 2.0           # 2 kg = 5000 kcal each
        sim.agents.hunger[r] = 0.2             # not hungry yet
        sim.agents.inv_capacity_kg[r] = 10.0
        sim.agents.alive[r] = True

    # Step 3 — Tax tick
    treasury_before = polity.treasury_kcal
    inv_before = float(sim.agents.inv_food[1])
    collected = _tax(sim, polity)
    inv_after = float(sim.agents.inv_food[1])
    treasury_after = polity.treasury_kcal
    expected_levy = 2.0 * TAX_RATE
    ok = (abs(inv_before - inv_after - expected_levy) < 1e-3
          and treasury_after > treasury_before
          and collected > 0)
    print(_row("step 3 — tax: member inv_food drops, treasury rises",
               ok,
               f"member: {inv_before:.3f}→{inv_after:.3f}  "
               f"treasury: {treasury_before:.0f}→{treasury_after:.0f}"))
    if not ok:
        failures += 1

    # Step 4 — Redistribute : make agent 2 hungry, others not.
    sim.agents.hunger[2] = 0.85   # hungry enough to claim
    sim.agents.hunger[3] = 0.85
    inv2_before = float(sim.agents.inv_food[2])
    distributed = _redistribute(sim, polity)
    inv2_after = float(sim.agents.inv_food[2])
    ok = (distributed > 0 and inv2_after > inv2_before)
    print(_row("step 4 — redistribute fills hungry members",
               ok,
               f"distributed={distributed:.0f} kcal  "
               f"hungry inv: {inv2_before:.3f}→{inv2_after:.3f}"))
    if not ok:
        failures += 1

    # Step 5 — Leader election
    # Set offspring counts to pick a non-trivial new leader.
    sim.agents.offspring_count[0] = 0
    sim.agents.offspring_count[1] = 0
    sim.agents.offspring_count[2] = 5  # agent 2 = highest prestige
    sim.agents.offspring_count[3] = 0
    sim.agents.offspring_count[4] = 1
    _re_elect_leader(sim, polity, None)
    ok = polity.leader_row == 2
    print(_row("step 5 — leader election picks highest prestige",
               ok, f"new_leader={polity.leader_row} (expected 2)"))
    if not ok:
        failures += 1

    # Step 6 — Disband when members drop below threshold
    # Kill 4 members → only 1 alive → below DISBAND_MEMBERS=2.
    for r in [0, 1, 3, 4]:
        sim.agents.alive[r] = False
    # Run tick_polity to trigger prune + disband.
    tick_polity(sim, state)
    ok = state.polities.get(pid) is None
    print(_row("step 6 — polity disbands when members < threshold",
               ok, f"polities remaining: {len(state.polities)}"))
    if not ok:
        failures += 1

    # Step 7 — ADR-0005 audit
    from engine.world_model_capabilities import audit_modules
    table, lint_fails = audit_modules(strict=False)
    p_row = next((r for r in table["modules"]
                  if r["module"] == "engine.polity"), None)
    ok = p_row is not None and p_row["status"] == "ok" and not lint_fails
    print(_row("step 7 — ADR-0005 lists polity OK",
               ok, f"failures={lint_fails}"))
    if not ok:
        failures += 1

    # Step 8 — Persistence round-trip
    # Recreate a fresh polity to have something to save.
    sim2 = _build_sim("p32_polity_persist", founders=5)
    state2 = install_polity(sim2)
    for r in [0, 1, 2, 3, 4]:
        sim2.agents.alive[r] = True
        sim2.agents.inv_food[r] = 1.0
        sim2.agents.hunger[r] = 0.3
    pid2 = found_polity(sim2, state2, founder_row=0, members=[1, 2, 3, 4],
                        name="persistopia")
    polity2 = state2.polities[pid2]
    polity2.treasury_kcal = 123456.0
    polity2.enforced_laws.add("no_relief_upstream")
    polity2.violations = 3

    tmp = tempfile.mkdtemp(prefix="genesis_p32_")
    try:
        save_polity_state(sim2, tmp)
        sim3 = _build_sim("p32_polity_load", founders=5)
        ok_load = load_polity_state(sim3, tmp)
        state3 = sim3._polity_state
        p3 = state3.polities.get(pid2)
        ok = (ok_load and p3 is not None
              and abs(p3.treasury_kcal - 123456.0) < 0.1
              and "no_relief_upstream" in p3.enforced_laws
              and p3.violations == 3
              and len(p3.member_rows) == 5)
        print(_row("step 8 — persistence round-trip preserves polity",
                   ok,
                   f"treasury={p3.treasury_kcal if p3 else None} "
                   f"violations={p3.violations if p3 else None}"))
        if not ok:
            failures += 1
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    snap = polity_state(sim2)
    print(f"polity snapshot:")
    print(f"  n_polities: {snap.get('n_polities')}")
    print(f"  global_treasury_kcal: {snap.get('global_treasury_kcal')}")
    print(f"  global_members: {snap.get('global_members')}")
    print(f"  polities_founded_total: {snap.get('polities_founded_total')}")
    print()
    if failures == 0:
        print("RESULT: PASS — Phase 4 polity smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
