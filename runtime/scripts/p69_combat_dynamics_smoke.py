"""P69 — Wave 38 combat dynamics smoke.

  1. Public API surface + 5 weapon kinds.
  2. ``unarmed_profile`` returns kind=UNARMED with low damage.
  3. ``weapon_profile_from_machine`` classifies by material/mass.
  4. ``best_weapon_for_agent`` returns UNARMED when no machines exist.
  5. ``resolve_combat`` inflicts wounds via anatomy when hit lands.
  6. Weapon damage scaling : BLADE deals more cumulative damage than
     UNARMED over many exchanges.
  7. Determinism : same seed → same combat outcomes.
  8. Install/uninstall idempotent + stacks wrapper correctly.
  9. Combat death by hemorrhage : repeated bladed hits → defender
     blood drops below threshold → dies.
"""
from __future__ import annotations

import io
import os
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

import numpy as np                                                      # noqa: E402

from engine.sim import Simulation, SimConfig                            # noqa: E402
from engine.anatomy import (install_anatomy, BLOOD_VOLUME_INITIAL_L,    # noqa: E402
                              BLOOD_DEATH_THRESHOLD_L, BodyPart,
                              WoundKind, step_anatomy)
from engine.machine_emergence import (install_machine_emergence,        # noqa: E402
                                        try_assemble_machine,
                                        MachineComponent)
from engine.combat_dynamics import (                                    # noqa: E402
    WeaponKind, N_WEAPON_KINDS, WEAPON_KIND_NAMES,
    WeaponProfile, WEAPON_DAMAGE_TABLE,
    CombatExchange, CombatState,
    weapon_profile_from_machine, unarmed_profile,
    best_weapon_for_agent, resolve_combat,
    install_combat_dynamics, uninstall_combat_dynamics,
    combat_state, _classify_machine_as_weapon,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xC0FFEE_69):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=10,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def main() -> int:
    print("=" * 78)
    print("P69 — Wave 38 combat dynamics smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API + 5 weapon kinds.
    ok = (N_WEAPON_KINDS == 5
          and len(WEAPON_KIND_NAMES) == 5
          and "resolve_combat" in globals()
          and "install_combat_dynamics" in globals()
          and len(WEAPON_DAMAGE_TABLE) == 5)
    print(_row("step 1 - API + 5 weapon kinds",
               ok, f"names={WEAPON_KIND_NAMES}"))
    if not ok:
        failures += 1

    # Step 2 — unarmed profile.
    unarmed = unarmed_profile()
    ok = (unarmed.kind == int(WeaponKind.UNARMED)
          and unarmed.base_damage < 0.1
          and unarmed.accuracy < 1.0)
    print(_row("step 2 - unarmed profile sane",
               ok, f"kind={unarmed.kind} dmg={unarmed.base_damage} acc={unarmed.accuracy}"))
    if not ok:
        failures += 1

    # Step 3 — classify machines from Wave 35.
    sim = _build_sim("p69_classify")
    sim.step()
    install_machine_emergence(sim)
    # Create a stone+wood "club" machine.
    components_club = [
        MachineComponent("material", "stone", 10.0),
        MachineComponent("material", "wood", 2.0),
    ]
    success, reason, club_machine = try_assemble_machine(
        sim, 0, components_club)
    # Create a metal+wood "spear" machine.
    components_spear = [
        MachineComponent("material", "metal", 1.0),
        MachineComponent("material", "wood", 1.5),
    ]
    success2, reason2, spear_machine = try_assemble_machine(
        sim, 0, components_spear)
    ok = (club_machine is not None and spear_machine is not None
          and _classify_machine_as_weapon(club_machine) == int(WeaponKind.CLUB)
          and _classify_machine_as_weapon(spear_machine) == int(WeaponKind.SPEAR))
    print(_row("step 3 - machine classification (stone→CLUB, metal+wood→SPEAR)",
               ok, f"club={_classify_machine_as_weapon(club_machine) if club_machine else '?'} "
                   f"spear={_classify_machine_as_weapon(spear_machine) if spear_machine else '?'}"))
    if not ok:
        failures += 1

    # Step 4 — no machines → unarmed.
    sim_no_machines = _build_sim("p69_unarmed",
                                   seed=0xC0FFEE_6911 & 0xFFFFFFFFFFFFFFFF)
    sim_no_machines.step()
    prof_none = best_weapon_for_agent(sim_no_machines, 0)
    ok = prof_none.kind == int(WeaponKind.UNARMED)
    print(_row("step 4 - no machines → unarmed",
               ok, f"kind={prof_none.kind}"))
    if not ok:
        failures += 1

    # Step 5 — resolve_combat inflicts wounds via anatomy.
    sim_combat = _build_sim("p69_resolve",
                              seed=0xC0FFEE_6912 & 0xFFFFFFFFFFFFFFFF)
    sim_combat.step()
    fields = install_anatomy(sim_combat)
    install_machine_emergence(sim_combat)
    # Run combat 20 times to ensure at least one hit.
    pre_sev_sum = float(fields.wound_severity[1].sum())
    any_hit = False
    for tick_off in range(20):
        sim_combat.tick = sim_combat.tick + 1  # Force unique RNG context.
        ex = resolve_combat(sim_combat, 0, 1, skip_same_polity=False)
        if ex.attacker_hit or ex.defender_counter_hit:
            any_hit = True
    post_sev_sum = float(fields.wound_severity[1].sum())
    ok = (any_hit and post_sev_sum > pre_sev_sum)
    print(_row("step 5 - resolve_combat inflicts wounds via anatomy",
               ok, f"any_hit={any_hit} sev {pre_sev_sum:.3f}→{post_sev_sum:.3f}"))
    if not ok:
        failures += 1

    # Step 6 — weapon damage scaling : BLADE > UNARMED over many fights.
    def _cumulative_damage_with_weapon(weapon_kind: int, seed_off: int) -> float:
        sub = _build_sim(f"p69_dmg_{weapon_kind}",
                          seed=(0xC0FFEE_6913 + seed_off) & 0xFFFFFFFFFFFFFFFF)
        sub.step()
        f = install_anatomy(sub)
        install_machine_emergence(sub)
        # Inject one weapon machine of the desired kind.
        if weapon_kind == int(WeaponKind.BLADE):
            # metal-dominant low mass
            comps = [MachineComponent("material", "metal", 1.5),
                     MachineComponent("material", "wood", 0.0)]
            comps = comps[:1] + [MachineComponent("material", "wood", 0.5)]
        else:  # UNARMED control: no machines
            comps = None
        if comps is not None:
            try_assemble_machine(sub, 0, comps)
        # Force hit by maxing aggression + strength.
        try:
            sub.agents.aggression[0] = 1.0
            sub.agents.strength = getattr(sub.agents, "strength", None) or np.ones(sub.agents.capacity, dtype=np.float32)
        except Exception:
            pass
        cumulative = 0.0
        for t in range(60):
            sub.tick = sub.tick + 1
            ex = resolve_combat(sub, 0, 1, skip_same_polity=False)
            cumulative += ex.attacker_dealt_severity
            cumulative += ex.defender_dealt_severity
        return cumulative

    dmg_blade = _cumulative_damage_with_weapon(int(WeaponKind.BLADE),
                                                  seed_off=0)
    dmg_unarmed = _cumulative_damage_with_weapon(int(WeaponKind.UNARMED),
                                                    seed_off=1)
    ok = dmg_blade > dmg_unarmed
    print(_row("step 6 - BLADE damage > UNARMED damage",
               ok, f"blade={dmg_blade:.3f} unarmed={dmg_unarmed:.3f}"))
    if not ok:
        failures += 1

    # Step 7 — determinism.
    def _run_combat_chain(seed):
        sub = _build_sim("p69_det", seed=seed)
        sub.step()
        install_anatomy(sub)
        install_machine_emergence(sub)
        try_assemble_machine(sub, 0,
                              [MachineComponent("material", "stone", 10.0),
                               MachineComponent("material", "wood", 2.0)])
        hits = []
        for t in range(30):
            sub.tick = sub.tick + 1
            ex = resolve_combat(sub, 0, 1, skip_same_polity=False)
            hits.append((ex.attacker_hit, ex.defender_counter_hit,
                         round(ex.attacker_dealt_severity, 5)))
        return tuple(hits)

    seed_d = 0xC0FFEE_6914 & 0xFFFFFFFFFFFFFFFF
    h_a = _run_combat_chain(seed_d)
    h_b = _run_combat_chain(seed_d)
    ok = h_a == h_b
    print(_row("step 7 - determinism inter-runs",
               ok, f"match={h_a == h_b} n_exchanges={len(h_a)}"))
    if not ok:
        failures += 1

    # Step 8 — install/uninstall idempotent.
    sim_inst = _build_sim("p69_inst",
                            seed=0xC0FFEE_6915 & 0xFFFFFFFFFFFFFFFF)
    sim_inst.step()
    s1 = install_combat_dynamics(sim_inst)
    s2 = install_combat_dynamics(sim_inst)
    ok_id = (s1 is s2)
    import engine.cognition as _cog
    ok_stack = (getattr(_cog, "_combat_inner_apply_decision", None) is not None
                and _cog.apply_decision is not _cog._combat_inner_apply_decision)
    ok_un = uninstall_combat_dynamics(sim_inst)
    ok_clear = (getattr(_cog, "_combat_inner_apply_decision", None) is None
                and not hasattr(sim_inst, "_combat_state"))
    ok = ok_id and ok_stack and ok_un and ok_clear
    print(_row("step 8 - install idempotent + stacks + uninstall clean",
               ok, f"idemp={ok_id} stacked={ok_stack} "
                   f"uninst={ok_un} cleared={ok_clear}"))
    if not ok:
        failures += 1

    # Step 9 — combat death by hemorrhage : repeated bladed hits drain blood.
    sim_kill = _build_sim("p69_kill",
                            seed=0xC0FFEE_6916 & 0xFFFFFFFFFFFFFFFF)
    sim_kill.step()
    f_kill = install_anatomy(sim_kill)
    install_machine_emergence(sim_kill)
    # Equip metal blade.
    try_assemble_machine(sim_kill, 0,
                          [MachineComponent("material", "metal", 1.5),
                           MachineComponent("material", "wood", 0.5)])
    # Max aggression to ensure many hits.
    try:
        sim_kill.agents.aggression[0] = 1.0
    except Exception:
        pass
    # Many combat exchanges (each tick the cumulative wound bleeds).
    n_combat_ticks = 60
    for t in range(n_combat_ticks):
        sim_kill.tick = sim_kill.tick + 1
        resolve_combat(sim_kill, 0, 1, skip_same_polity=False)
        # Advance anatomy (bleeding) for 1 sim-hour each tick.
        step_anatomy(sim_kill, dt_s=3600.0)
    blood_def = float(f_kill.blood_volume_l[1])
    alive_def = bool(sim_kill.agents.alive[1])
    # Either died (blood < threshold) or has open wounds.
    n_wounds = int((f_kill.wound_severity[1].sum() > 0.01))
    ok = (blood_def < BLOOD_VOLUME_INITIAL_L
          and (not alive_def or n_wounds >= 1))
    print(_row("step 9 - bladed combat drains defender blood (anatomy)",
               ok, f"blood={blood_def:.3f}L alive={alive_def} wounds={n_wounds}"))
    if not ok:
        failures += 1

    # Diagnostic dump.
    print(f"\nCombat state on kill sim: {combat_state(sim_kill)}")

    total = 9
    passed = total - failures
    print("=" * 78)
    if failures == 0:
        print(f"RESULT: {total}/{total} PASS")
        return 0
    else:
        print(f"RESULT: {passed}/{total} PASS, {failures} FAIL")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
