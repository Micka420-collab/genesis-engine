"""P65 — Wave 35 emergent machine discovery smoke.

Proves that composite machines (roue, levier, watermill, métier…)
emerge by deterministic fingerprinting — *no recipe table*. Two cultures
that assemble the same components for the same function recognise the
same fingerprint but auto-coin different CVCV names.

Checks
------
  1. API exposed + module loads without warnings.
  2. ``install_machine_emergence`` is idempotent.
  3. Single component → fails (machines need >= 2).
  4. Two cultures assemble (wood + stone) → 1 fingerprint, 2 names.
  5. Same culture reassembles the same fingerprint → 'recognized',
     no new invention counted.
  6. Five distinct fingerprints → 5 machines registered.
  7. Function aggregation: artifact components contribute their
     ``FunctionKind`` to the machine's function_kinds set.
  8. Static stability flag: very heavy + compact assembly → False.
  9. Determinism: two sims with identical seed discover the same names
     in the same order.
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

import numpy as np  # noqa: E402

from engine.sim import Simulation, SimConfig                  # noqa: E402
from engine.invention import (                                # noqa: E402
    Artifact, FunctionKind, InventionRegistry,
)
from engine.materials import MaterialKind                     # noqa: E402
from engine.machine_emergence import (                        # noqa: E402
    MIN_COMPONENTS_FOR_MACHINE,
    MachineComponent,
    auto_name_machine,
    compute_machine_fingerprint,
    install_machine_emergence,
    machine_emergence_state,
    try_assemble_machine,
    uninstall_machine_emergence,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:55s} {detail}"


def _build_sim(name: str, seed: int = 0xC0FFEE_35 & 0xFFFFFFFFFFFFFFFF):
    cfg = SimConfig(
        name=name, seed=seed,
        founders=4, max_agents=10,
        bounds_km=(0.2, 0.2), spawn_radius_m=50.0,
        drive_accel=1.0, cultures=2,
    )
    sim = Simulation(cfg)
    # Two distinct cultures available on rows 0 and 1.
    if not hasattr(sim.agents, "culture"):
        sim.agents.culture = np.zeros(sim.agents.capacity, dtype=np.int32)
    sim.agents.culture[0] = 0
    sim.agents.culture[1] = 99
    return sim


def _attach_invention_registry(sim) -> InventionRegistry:
    reg = InventionRegistry()
    sim._invention_registry = reg
    return reg


def _wood_stone_components() -> list:
    return [
        MachineComponent(kind="material", id_or_name="wood", mass_kg=3.0),
        MachineComponent(kind="material", id_or_name="stone", mass_kg=4.0),
    ]


def main() -> int:
    print("=" * 78)
    print("P65 — Wave 35 emergent machine discovery")
    print("=" * 78)
    failures = 0

    # ----- Step 1 — API surface ------------------------------------------
    api_ok = all([
        callable(install_machine_emergence),
        callable(try_assemble_machine),
        callable(machine_emergence_state),
        callable(uninstall_machine_emergence),
        callable(compute_machine_fingerprint),
        callable(auto_name_machine),
    ])
    print(_row("step 1 — public API exposed",
               api_ok, f"min_components={MIN_COMPONENTS_FOR_MACHINE}"))
    if not api_ok:
        failures += 1

    # ----- Step 2 — installer idempotent ---------------------------------
    sim = _build_sim("p65_idem")
    s1 = install_machine_emergence(sim)
    s2 = install_machine_emergence(sim)
    ok = s1 is s2 and getattr(sim, "_machine_state", None) is s1
    print(_row("step 2 — install_machine_emergence idempotent", ok))
    if not ok:
        failures += 1

    # ----- Step 3 — single component → fail ------------------------------
    sim = _build_sim("p65_single")
    install_machine_emergence(sim)
    succ, reason, machine = try_assemble_machine(
        sim, row=0,
        components=[MachineComponent(kind="material",
                                      id_or_name="wood", mass_kg=2.0)],
    )
    ok = (not succ) and reason.startswith("too_few_components") and machine is None
    print(_row("step 3 — single component → fail",
               ok, f"reason={reason!r}"))
    if not ok:
        failures += 1

    # ----- Step 4 — 2 cultures, same components, 1 fp / 2 names ---------
    sim = _build_sim("p65_2cult")
    install_machine_emergence(sim)
    succ_a, reason_a, m_a = try_assemble_machine(
        sim, row=0, components=_wood_stone_components(),
    )
    succ_b, reason_b, m_b = try_assemble_machine(
        sim, row=1, components=_wood_stone_components(),
    )
    same_fp = (m_a is not None and m_b is not None
                and m_a.fingerprint == m_b.fingerprint)
    diff_name = (m_a is not None and m_b is not None
                  and m_a.machine_id != m_b.machine_id)
    ok = succ_a and succ_b and same_fp and diff_name
    print(_row("step 4 — 2 cultures → same fp, different names",
               ok, f"a={m_a.machine_id if m_a else None!r} "
                   f"b={m_b.machine_id if m_b else None!r}"))
    if not ok:
        failures += 1

    # ----- Step 5 — recognition: re-assemble same fp same culture -------
    sim = _build_sim("p65_recog")
    install_machine_emergence(sim)
    succ_1, _, m1 = try_assemble_machine(
        sim, row=0, components=_wood_stone_components())
    succ_2, reason_2, m2 = try_assemble_machine(
        sim, row=0, components=_wood_stone_components())
    snap = machine_emergence_state(sim)
    ok = (succ_1 and succ_2 and reason_2 == "recognized"
          and m1 is not None and m2 is not None
          and m1.machine_id == m2.machine_id
          and snap.get("n_total_attempted") == 2
          and snap.get("n_total_invented") == 1)
    print(_row("step 5 — same culture re-assembly → recognized",
               ok,
               f"reason={reason_2!r} invented={snap.get('n_total_invented')}"))
    if not ok:
        failures += 1

    # ----- Step 6 — five distinct fingerprints → 5 machines -------------
    sim = _build_sim("p65_five")
    install_machine_emergence(sim)
    five_specs = [
        [MachineComponent("material", "wood",   2.0),
         MachineComponent("material", "stone",  3.0)],
        [MachineComponent("material", "wood",   5.0),
         MachineComponent("material", "stone",  4.0),
         MachineComponent("material", "fiber",  0.3)],
        [MachineComponent("material", "stone",  10.0),
         MachineComponent("material", "stone",  10.0)],
        [MachineComponent("material", "clay",   1.0),
         MachineComponent("material", "wood",   1.5)],
        [MachineComponent("material", "bone",   0.4),
         MachineComponent("material", "fiber",  0.2),
         MachineComponent("material", "wood",   1.0)],
    ]
    invented_names = []
    for spec in five_specs:
        succ, reason, m = try_assemble_machine(sim, row=0, components=spec)
        if succ and reason == "invented" and m is not None:
            invented_names.append(m.machine_id)
    snap = machine_emergence_state(sim)
    ok = (len(invented_names) == 5
          and len(set(invented_names)) == 5
          and snap.get("n_machines") == 5
          and snap.get("n_total_invented") == 5)
    print(_row("step 6 — five distinct fps → five machines",
               ok, f"names={invented_names}"))
    if not ok:
        failures += 1

    # ----- Step 7 — function aggregation from artifact components -------
    sim = _build_sim("p65_fnagg")
    install_machine_emergence(sim)
    inv = _attach_invention_registry(sim)
    # Two artifacts known to the simulation: a stone "cut" and a wood "strike".
    a_cut = Artifact(artifact_id=1, name="stone_cut",
                     function=FunctionKind.CUT,
                     primary_material=MaterialKind.STONE,
                     secondary_material=None,
                     inventor_row=0, invented_tick=0, effectiveness=0.7)
    a_strike = Artifact(artifact_id=2, name="wood_strike",
                        function=FunctionKind.STRIKE,
                        primary_material=MaterialKind.WOOD,
                        secondary_material=None,
                        inventor_row=0, invented_tick=0, effectiveness=0.6)
    inv.artifacts[1] = a_cut
    inv.artifacts[2] = a_strike
    succ, reason, m = try_assemble_machine(
        sim, row=0,
        components=[
            MachineComponent("artifact", "1", mass_kg=1.5),
            MachineComponent("artifact", "2", mass_kg=2.0),
            MachineComponent("material", "fiber", mass_kg=0.2),
        ],
    )
    expected_fns = {int(FunctionKind.CUT), int(FunctionKind.STRIKE)}
    got_fns = set(m.function_kinds) if m is not None else set()
    ok = succ and reason == "invented" and got_fns == expected_fns
    print(_row("step 7 — artifact components feed function_kinds",
               ok, f"got={sorted(got_fns)} expected={sorted(expected_fns)}"))
    if not ok:
        failures += 1

    # ----- Step 8 — static stability flag on heavy/compact assembly -----
    sim = _build_sim("p65_static")
    install_machine_emergence(sim)
    heavy = [
        MachineComponent("material", "stone", 600.0),
        MachineComponent("material", "stone", 600.0),
    ]
    succ_h, _, m_heavy = try_assemble_machine(sim, row=0, components=heavy)
    light = [
        MachineComponent("material", "wood", 1.0),
        MachineComponent("material", "fiber", 0.2),
        MachineComponent("material", "stone", 0.5),
        MachineComponent("material", "wood", 0.8),
    ]
    succ_l, _, m_light = try_assemble_machine(sim, row=0, components=light)
    ok = (succ_h and succ_l
          and m_heavy is not None and m_light is not None
          and m_heavy.is_static_stable is False
          and m_light.is_static_stable is True)
    print(_row("step 8 — heavy/compact → unstable, light → stable",
               ok,
               f"heavy_stable={m_heavy.is_static_stable if m_heavy else None} "
               f"light_stable={m_light.is_static_stable if m_light else None}"))
    if not ok:
        failures += 1

    # ----- Step 9 — determinism across two sims with same seed ----------
    def _run(seed: int):
        sim = _build_sim("p65_det", seed=seed)
        install_machine_emergence(sim)
        order = []
        for spec in five_specs:
            succ, reason, m = try_assemble_machine(
                sim, row=0, components=spec)
            if succ and reason == "invented" and m is not None:
                order.append(m.machine_id)
        return order

    seed = 0xDEADBEEF_35 & 0xFFFFFFFFFFFFFFFF
    order_a = _run(seed)
    order_b = _run(seed)
    ok = order_a == order_b and len(order_a) == 5
    print(_row("step 9 — determinism: same seed → same names/order",
               ok, f"A={order_a}"))
    if not ok:
        failures += 1

    # Final snapshot
    print()
    snap = machine_emergence_state(sim)
    print(f"machine emergence snapshot (last sim):")
    print(f"  attempted: {snap.get('n_total_attempted')}")
    print(f"  invented:  {snap.get('n_total_invented')}")
    print(f"  cultures with machines: {snap.get('n_cultures_with_machines')}")
    for cul, machines in (snap.get("by_culture") or {}).items():
        for m in machines:
            print(f"    culture {cul}: {m['name']!r:18s} "
                  f"fp={m['fingerprint']} stable={m['is_static_stable']}")
    print()

    if failures == 0:
        print(f"RESULT: PASS — Wave 35 machine_emergence smoke complete "
              f"(9/9).")
        return 0
    print(f"RESULT: FAIL — {failures}/9 check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
