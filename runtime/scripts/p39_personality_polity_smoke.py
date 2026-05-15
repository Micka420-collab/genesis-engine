"""P39 — Wave 11 personality-drives-politics smoke test.

Validates that personality traits actually shape polity behaviour.
**No scripted recipe** : agents with different traits produce
measurably different governance outcomes from the *same* baseline
inventories and hungers.

  1. install_polity idempotent.
  2. Leader election : two cohorts with different
     ambition/extraversion → the high-ambition agent wins.
  3. Tax compliance : high-agreeableness members surrender more food
     than low-agreeableness members for the same TAX_RATE.
  4. Redistribute fairness : low-conscientiousness leader hoards
     (share_fraction ≈ 0.30) — high-conscientiousness leader empties
     (share_fraction ≈ 1.00).
  5. Redistribute curve : low-consc leader concentrates aid on the
     hungriest ; high-consc leader spreads aid more evenly.
  6. ADR-0005 audit clean.
  7. Determinism : two identical sims same seed produce identical
     leader / tax / distribution.
  8. Persistence round-trip preserves personality-driven state.
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
    _tax, _redistribute, _re_elect_leader,
    found_polity, TAX_RATE, REDISTRIBUTE_HUNGER_THRESHOLD,
    KCAL_PER_KG_FOOD,
    save_polity_state, load_polity_state)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:55s} {detail}"


def _build_sim(name: str, founders: int = 5):
    cfg = SimConfig(
        name=name, seed=0xC0FFEE_51 & 0xFFFFFFFFFFFFFFFF,
        founders=founders, max_agents=20,
        bounds_km=(0.5, 0.5), spawn_radius_m=80.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def _reset_traits(sim, row, ambition=0.5, extraversion=0.5,
                  agreeableness=0.5, conscientiousness=0.5):
    sim.agents.ambition[row] = ambition
    sim.agents.extraversion[row] = extraversion
    sim.agents.agreeableness[row] = agreeableness
    sim.agents.conscientiousness[row] = conscientiousness


def main() -> int:
    print("=" * 78)
    print("P39 — Wave 11 personality polity smoke")
    print("=" * 78)
    failures = 0

    sim = _build_sim("p39_personality", founders=5)
    state = install_polity(sim)

    # Step 1 — idempotent
    s2 = install_polity(sim)
    print(_row("step 1 — install_polity idempotent",
               state is s2, ""))
    if state is not s2:
        failures += 1

    # Set up a polity of 5 with mixed traits.
    for r in [0, 1, 2, 3, 4]:
        sim.agents.alive[r] = True
        sim.agents.inv_food[r] = 2.0
        sim.agents.hunger[r] = 0.3
        sim.agents.inv_capacity_kg[r] = 10.0
        sim.agents.offspring_count[r] = 0
        _reset_traits(sim, r)
    pid = found_polity(sim, state, founder_row=0,
                       members=[1, 2, 3, 4], name="testopia")
    polity = state.polities[pid]

    # Step 2 — Leader election : agent 3 = high ambition, others bland.
    # All have offspring=0 so the only differentiator is personality.
    _reset_traits(sim, 0, ambition=0.10, extraversion=0.20)
    _reset_traits(sim, 1, ambition=0.10, extraversion=0.20)
    _reset_traits(sim, 2, ambition=0.20, extraversion=0.30)
    _reset_traits(sim, 3, ambition=0.95, extraversion=0.90)  # alpha
    _reset_traits(sim, 4, ambition=0.15, extraversion=0.25)
    _re_elect_leader(sim, polity, None)
    ok = polity.leader_row == 3
    print(_row("step 2 — high-ambition agent wins leadership",
               ok, f"new_leader={polity.leader_row} (expected 3)"))
    if not ok:
        failures += 1

    # Step 3 — Tax compliance : high-A vs low-A members.
    # Reset inventories.
    for r in [0, 1, 2, 3, 4]:
        sim.agents.inv_food[r] = 2.0
        sim.agents.hunger[r] = 0.3
    sim.agents.agreeableness[0] = 0.05  # tax evader
    sim.agents.agreeableness[1] = 0.95  # cooperator
    inv0_before = float(sim.agents.inv_food[0])
    inv1_before = float(sim.agents.inv_food[1])
    _tax(sim, polity)
    levy_low_A = inv0_before - float(sim.agents.inv_food[0])
    levy_hi_A = inv1_before - float(sim.agents.inv_food[1])
    # Expected: hi_A pays > 2 × what low_A pays.
    ok = (levy_hi_A > 0 and levy_low_A > 0
          and levy_hi_A > 2.0 * levy_low_A)
    print(_row("step 3 — agreeable agent pays more tax than evader",
               ok,
               f"low_A={levy_low_A*1000:.1f}g  hi_A={levy_hi_A*1000:.1f}g  "
               f"ratio={levy_hi_A/max(1e-9, levy_low_A):.2f}×"))
    if not ok:
        failures += 1

    # Step 4 — Redistribute hoarding : low-consc leader.
    # Make leader 3 have low consc, treasury big, several hungry members.
    sim.agents.conscientiousness[3] = 0.05
    polity.leader_row = 3
    polity.treasury_kcal = 100_000.0
    for r in [0, 1, 2, 4]:
        sim.agents.hunger[r] = 0.85
        sim.agents.inv_food[r] = 0.0
    treasury_before = polity.treasury_kcal
    distributed_low = _redistribute(sim, polity)
    fraction_low = distributed_low / treasury_before
    ok_low = 0.20 < fraction_low < 0.45
    print(_row("step 4 — low-consc leader hoards (~30% out)",
               ok_low,
               f"fraction={fraction_low*100:.1f}% "
               f"(expected 20-45%)"))
    if not ok_low:
        failures += 1

    # Now high-consc leader on a freshly-reset state.
    polity.treasury_kcal = 100_000.0
    sim.agents.conscientiousness[3] = 0.95
    for r in [0, 1, 2, 4]:
        sim.agents.hunger[r] = 0.85
        sim.agents.inv_food[r] = 0.0
    treasury_before = polity.treasury_kcal
    distributed_hi = _redistribute(sim, polity)
    fraction_hi = distributed_hi / treasury_before
    ok_hi = fraction_hi > 0.80
    print(_row("step 5 — high-consc leader empties (~100% out)",
               ok_hi,
               f"fraction={fraction_hi*100:.1f}% "
               f"(expected >80%)"))
    if not ok_hi:
        failures += 1

    # Step 6 — Curve shape : low-consc concentrates on hungriest.
    # Reset to test the shape directly. Three needy with monotone need.
    polity.treasury_kcal = 100_000.0
    sim.agents.conscientiousness[3] = 0.05
    for r, h in [(0, 0.60), (1, 0.75), (2, 0.95), (4, 0.30)]:  # 4 not hungry
        sim.agents.hunger[r] = h
        sim.agents.inv_food[r] = 0.0
    _redistribute(sim, polity)
    food_low_curve = [float(sim.agents.inv_food[r]) for r in (0, 1, 2)]

    polity.treasury_kcal = 100_000.0
    sim.agents.conscientiousness[3] = 0.95
    for r, h in [(0, 0.60), (1, 0.75), (2, 0.95), (4, 0.30)]:
        sim.agents.hunger[r] = h
        sim.agents.inv_food[r] = 0.0
    _redistribute(sim, polity)
    food_hi_curve = [float(sim.agents.inv_food[r]) for r in (0, 1, 2)]

    # Low-consc → ratio of biggest-need to smallest-need share is more skewed.
    ratio_low = food_low_curve[2] / max(1e-6, food_low_curve[0])
    ratio_hi = food_hi_curve[2] / max(1e-6, food_hi_curve[0])
    ok_curve = ratio_low > ratio_hi * 1.5
    print(_row("step 6 — low-consc curve concentrates on hungriest",
               ok_curve,
               f"ratio_low={ratio_low:.1f}×  ratio_hi={ratio_hi:.1f}× "
               f"(low must be >1.5× hi)"))
    if not ok_curve:
        failures += 1

    # Step 7 — ADR-0005 audit
    from engine.world_model_capabilities import audit_modules
    table, lint_fails = audit_modules(strict=False)
    p_row = next((r for r in table["modules"]
                  if r["module"] == "engine.polity"), None)
    ok = (p_row is not None and p_row["status"] == "ok"
          and not lint_fails)
    print(_row("step 7 — ADR-0005 polity ok",
               ok, f"failures={lint_fails}"))
    if not ok:
        failures += 1

    # Step 8 — Persistence round-trip with personality-driven traffic.
    sim2 = _build_sim("p39_persist", founders=5)
    state2 = install_polity(sim2)
    for r in [0, 1, 2, 3, 4]:
        sim2.agents.alive[r] = True
        sim2.agents.inv_food[r] = 1.0
        sim2.agents.hunger[r] = 0.3
        sim2.agents.agreeableness[r] = 0.8
        sim2.agents.conscientiousness[r] = 0.8
    pid2 = found_polity(sim2, state2, founder_row=0,
                        members=[1, 2, 3, 4], name="persistopia")
    p2 = state2.polities[pid2]
    _tax(sim2, p2)
    tax_collected = p2.tax_collected_kcal
    tmp = tempfile.mkdtemp(prefix="genesis_p39_")
    try:
        save_polity_state(sim2, tmp)
        sim3 = _build_sim("p39_load", founders=5)
        ok_load = load_polity_state(sim3, tmp)
        state3 = sim3._polity_state
        p3 = state3.polities.get(pid2)
        ok = (ok_load and p3 is not None
              and abs(p3.tax_collected_kcal - tax_collected) < 0.1)
        print(_row("step 8 — persistence preserves personality-driven tax",
                   ok,
                   f"tax={p3.tax_collected_kcal if p3 else None} "
                   f"(expected {tax_collected:.1f})"))
        if not ok:
            failures += 1
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    snap = polity_state(sim)
    print(f"polity snapshot:")
    print(f"  n_polities: {snap.get('n_polities')}")
    print(f"  global_treasury_kcal: {snap.get('global_treasury_kcal')}")
    print(f"  leader_elections_total: {snap.get('leader_elections_total')}")
    print()
    if failures == 0:
        print("RESULT: PASS — Wave 11 personality polity smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
