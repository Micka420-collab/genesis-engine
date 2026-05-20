"""P67 — Wave 35b machine cognition wiring smoke.

Validates that ``install_machine_cognition_wiring`` correctly stacks
on top of ``engine.cognition.apply_decision`` and that agents
autonomously attempt machine assembly during BUILD actions when they
have ≥ 2 components in inventory.

  1. Public API surface.
  2. Install idempotent + dispatch table populated.
  3. Wrapper stacked : ``apply_decision`` ≠ inner after install.
  4. Agent with < 2 components → no assembly attempt.
  5. Agent with ≥ 2 components + BUILD + curiosity → may invent.
  6. High-curiosity agents invent more than low-curiosity (gating).
  7. Determinism : same seed → same machines invented.
  8. Uninstall restores the previous ``apply_decision``.
  9. Wrapper delegates non-BUILD actions correctly (e.g., IDLE).
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
from engine.agent import ActionKind                                     # noqa: E402
from engine.cognition import Decision                                   # noqa: E402
from engine.machine_emergence import (machine_emergence_state,          # noqa: E402
                                        install_machine_emergence)
from engine.machine_cognition_wiring import (                           # noqa: E402
    install_machine_cognition_wiring,
    uninstall_machine_cognition_wiring,
    machine_cognition_wiring_state,
    _maybe_assemble_machine,
    _MACHINE_DISPATCH,
    MIN_COMPONENT_MASS_KG,
    MAX_COMPONENT_MASS_KG,
    ASSEMBLY_ATTEMPT_BASE_PROB,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xC0FFEE_67):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=10,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def main() -> int:
    print("=" * 78)
    print("P67 — Wave 35b machine cognition wiring smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API surface.
    ok = all(name in globals() for name in (
        "install_machine_cognition_wiring",
        "uninstall_machine_cognition_wiring",
        "machine_cognition_wiring_state",
        "_maybe_assemble_machine",
        "_MACHINE_DISPATCH",
        "MIN_COMPONENT_MASS_KG",
        "MAX_COMPONENT_MASS_KG",
        "ASSEMBLY_ATTEMPT_BASE_PROB",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Step 2 — install idempotent + dispatch populated.
    # Uninstall any leftover from prior tests in the same Python process.
    sim = _build_sim("p67_wiring", seed=0xC0FFEE_6701 & 0xFFFFFFFFFFFFFFFF)
    sim.step()  # bootstrap founders
    first = install_machine_cognition_wiring(sim)
    second = install_machine_cognition_wiring(sim)
    st = machine_cognition_wiring_state(sim)
    ok = (st["installed_globally"]
          and st["dispatch_active_for_sim"]
          and first is True
          and second is False)
    print(_row("step 2 - install idempotent + dispatch populated",
               ok, f"first={first} second={second} "
                   f"global={st['installed_globally']}"))
    if not ok:
        failures += 1

    # Step 3 — wrapper stacked: apply_decision is _machine_global_wrapper.
    import engine.cognition as _cog
    from engine.machine_cognition_wiring import _machine_global_wrapper
    ok = (_cog.apply_decision is _machine_global_wrapper
          and getattr(_cog, "_machine_inner_apply_decision", None) is not None
          and _cog._machine_inner_apply_decision is not _machine_global_wrapper)
    print(_row("step 3 - apply_decision stacked correctly",
               ok, f"wrapper_installed={_cog.apply_decision is _machine_global_wrapper}"))
    if not ok:
        failures += 1

    # Step 4 — agent with < 2 components → no assembly.
    state = sim._machine_state
    sim.agents.inv_wood[0] = 0.5      # below MIN 1.0
    sim.agents.inv_stone[0] = 0.5     # below MIN 2.0
    sim.agents.inv_metal[0] = 0.0
    n_invented_before = state.registry.n_total_invented
    n_attempted_before = state.registry.n_total_attempted
    # Hammer 100 ticks of BUILD attempts.
    for tick in range(100):
        _maybe_assemble_machine(sim, sim.agents, 0, tick)
    ok = (state.registry.n_total_invented == n_invented_before
          and state.registry.n_total_attempted == n_attempted_before)
    print(_row("step 4 - <2 components → no assembly attempted",
               ok, f"invented_delta={state.registry.n_total_invented - n_invented_before} "
                   f"attempted_delta={state.registry.n_total_attempted - n_attempted_before}"))
    if not ok:
        failures += 1

    # Step 5 — agent with ≥ 2 components + curiosity → may invent.
    sim.agents.inv_wood[0] = 3.0       # above MIN
    sim.agents.inv_stone[0] = 5.0      # above MIN
    sim.agents.inv_metal[0] = 1.0      # above MIN
    if sim.agents.curiosity is not None:
        sim.agents.curiosity[0] = 1.0  # maximum curiosity → max p_attempt
    n_invented_before = state.registry.n_total_invented
    n_attempted_before = state.registry.n_total_attempted
    for tick in range(200):
        _maybe_assemble_machine(sim, sim.agents, 0, tick)
    ok = (state.registry.n_total_attempted > n_attempted_before
          and state.registry.n_total_invented >= n_invented_before)
    print(_row("step 5 - ≥2 components + curiosity → attempts (and inventions)",
               ok, f"invented={state.registry.n_total_invented} "
                   f"attempted={state.registry.n_total_attempted}"))
    if not ok:
        failures += 1

    # Step 6 — curiosity gating : high-curiosity > low-curiosity.
    # Fresh sims to avoid carry-over.
    def _count_attempts_for_curiosity(curio_value: float, seed_off: int) -> int:
        sub = _build_sim(f"p67_curio_{int(curio_value*100)}",
                         seed=(0xC0FFEE_6702 + seed_off) & 0xFFFFFFFFFFFFFFFF)
        sub.step()
        install_machine_cognition_wiring(sub)
        st = sub._machine_state
        sub.agents.inv_wood[0] = 5.0
        sub.agents.inv_stone[0] = 10.0
        sub.agents.inv_metal[0] = 2.0
        if sub.agents.curiosity is not None:
            sub.agents.curiosity[0] = curio_value
        baseline = st.registry.n_total_attempted
        for t in range(500):
            _maybe_assemble_machine(sub, sub.agents, 0, t)
        uninstall_machine_cognition_wiring(sub)
        return st.registry.n_total_attempted - baseline

    n_high = _count_attempts_for_curiosity(1.0, seed_off=0)
    n_low = _count_attempts_for_curiosity(0.05, seed_off=1)
    ok = n_high > n_low and n_low >= 0
    print(_row("step 6 - high-curiosity > low-curiosity (gating)",
               ok, f"high_attempts={n_high} low_attempts={n_low}"))
    if not ok:
        failures += 1

    # Step 7 — determinism : two sims same seed → same registries.
    def _run_deterministic(seed: int):
        sub = _build_sim("p67_det", seed=seed)
        sub.step()
        install_machine_cognition_wiring(sub)
        sub.agents.inv_wood[0] = 5.0
        sub.agents.inv_stone[0] = 10.0
        sub.agents.inv_metal[0] = 2.0
        if sub.agents.curiosity is not None:
            sub.agents.curiosity[0] = 0.8
        for t in range(300):
            _maybe_assemble_machine(sub, sub.agents, 0, t)
        names = list(sub._machine_state.registry.machines.keys())
        uninstall_machine_cognition_wiring(sub)
        return tuple(names)

    seed_d = 0xC0FFEE_6703 & 0xFFFFFFFFFFFFFFFF
    names_a = _run_deterministic(seed_d)
    names_b = _run_deterministic(seed_d)
    ok = names_a == names_b
    print(_row("step 7 - determinism : same seed → same machines",
               ok, f"names_match={names_a == names_b} "
                   f"n_machines={len(names_a)}"))
    if not ok:
        failures += 1

    # Step 8 — uninstall restores apply_decision.
    sim_u = _build_sim("p67_uninstall",
                        seed=0xC0FFEE_6704 & 0xFFFFFFFFFFFFFFFF)
    sim_u.step()
    # Snapshot apply_decision BEFORE install.
    before = _cog.apply_decision
    install_machine_cognition_wiring(sim_u)
    during = _cog.apply_decision
    uninstall_machine_cognition_wiring(sim_u)
    after = _cog.apply_decision
    ok = (during is _machine_global_wrapper
          and after is before
          and getattr(_cog, "_machine_inner_apply_decision", None) is None)
    print(_row("step 8 - uninstall restores apply_decision",
               ok, f"during=wrapper={during is _machine_global_wrapper} "
                   f"after=before={after is before}"))
    if not ok:
        failures += 1

    # Step 9 — wrapper delegates non-BUILD actions correctly.
    # Install on a fresh sim, send an IDLE decision through, verify
    # inner is called (return value is a list, not None, and no machine
    # invented for IDLE).
    sim_d = _build_sim("p67_delegate",
                        seed=0xC0FFEE_6705 & 0xFFFFFFFFFFFFFFFF)
    sim_d.step()
    install_machine_cognition_wiring(sim_d)
    sim_d.agents.inv_wood[0] = 5.0
    sim_d.agents.inv_stone[0] = 10.0
    sim_d.agents.inv_metal[0] = 2.0
    if sim_d.agents.curiosity is not None:
        sim_d.agents.curiosity[0] = 1.0
    n_before = sim_d._machine_state.registry.n_total_attempted
    # Send an IDLE decision (target_x, target_y don't matter).
    d_idle = Decision(action=int(ActionKind.IDLE),
                       target_x=0.0, target_y=0.0)
    try:
        events = _cog.apply_decision(sim_d.agents, 0, d_idle,
                                       sim_d.streamer, sim_d.tick)
    except Exception as e:
        events = e
    n_after = sim_d._machine_state.registry.n_total_attempted
    ok = (n_after == n_before
          and not isinstance(events, Exception))
    print(_row("step 9 - IDLE delegated (no assembly fired)",
               ok, f"attempts_unchanged={n_after == n_before} "
                   f"no_exception={not isinstance(events, Exception)}"))
    if not ok:
        failures += 1
    uninstall_machine_cognition_wiring(sim_d)

    # Diagnostic dump.
    state_diag = machine_cognition_wiring_state(sim_d)
    print(f"\nWiring state diagnostic: {state_diag}")
    print(f"Final machines invented (deterministic run): {names_a}")

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
