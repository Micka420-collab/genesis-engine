"""P64 — Wave 34 anatomy + wounds + blood smoke.

  1. Public API surface + 10 body parts + 4 wound kinds.
  2. Install creates AnatomyFields with correct shapes.
  3. Initial state : blood = 5.0 L, no wounds.
  4. ``inflict_wound`` adds severity at (row, part, kind).
  5. Bleeding decreases blood volume for cut/burn/fracture but not bruise.
  6. Hemorrhage : agent dies when blood < 1.5 L.
  7. Healing : wound severity decreases over time (per-kind rates).
  8. ``wound_from_action`` is deterministic via prf_rng.
  9. Action-coupling : MINE inflicts R_HAND cut wounds in expectation.
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
from engine.anatomy import (                                            # noqa: E402
    AnatomyFields, BodyPart, WoundKind,
    N_BODY_PARTS, N_WOUND_KINDS,
    BODY_PART_NAMES, WOUND_KIND_NAMES,
    BLOOD_VOLUME_INITIAL_L, BLOOD_DEATH_THRESHOLD_L,
    ACTION_WOUND_TABLE, ACTION_WOUND_PROBABILITY,
    inflict_wound, wound_from_action,
    install_anatomy, uninstall_anatomy, step_anatomy,
    anatomy_state,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xC0FFEE_64):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=10,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def main() -> int:
    print("=" * 78)
    print("P64 — Wave 34 anatomy + wounds + blood smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API + constants.
    ok = (N_BODY_PARTS == 10 and N_WOUND_KINDS == 4
          and len(BODY_PART_NAMES) == 10
          and len(WOUND_KIND_NAMES) == 4
          and BLOOD_VOLUME_INITIAL_L == 5.0
          and BLOOD_DEATH_THRESHOLD_L == 1.5
          and "inflict_wound" in globals()
          and "wound_from_action" in globals()
          and "install_anatomy" in globals()
          and "step_anatomy" in globals())
    print(_row("step 1 - API + constants exposed",
               ok, f"parts={N_BODY_PARTS} kinds={N_WOUND_KINDS} "
                   f"blood_init={BLOOD_VOLUME_INITIAL_L}"))
    if not ok:
        failures += 1

    # Step 2 — install creates correct-shape fields.
    sim = _build_sim("p64_anatomy")
    sim.step()  # bootstrap founders
    fields = install_anatomy(sim)
    N = sim.agents.capacity
    ok = (fields.blood_volume_l.shape == (N,)
          and fields.wound_severity.shape == (N, 10, 4)
          and fields.wound_severity.dtype == np.float32
          and fields.blood_volume_l.dtype == np.float32)
    print(_row("step 2 - AnatomyFields shapes correct",
               ok, f"blood={fields.blood_volume_l.shape} "
                   f"wounds={fields.wound_severity.shape}"))
    if not ok:
        failures += 1

    # Step 3 — initial state : 5.0 L, zero wounds.
    n = sim.agents.n_active
    ok = (np.allclose(fields.blood_volume_l[:n], 5.0)
          and fields.wound_severity[:n].sum() == 0.0)
    print(_row("step 3 - initial blood=5.0 + no wounds",
               ok, f"blood_min={float(fields.blood_volume_l[:n].min()):.2f} "
                   f"total_severity={float(fields.wound_severity[:n].sum()):.4f}"))
    if not ok:
        failures += 1

    # Step 4 — inflict_wound writes to the right cell.
    new_sev = inflict_wound(fields, 0, int(BodyPart.R_HAND),
                              int(WoundKind.CUT), 0.30)
    ok = (abs(fields.wound_severity[0, int(BodyPart.R_HAND),
                                       int(WoundKind.CUT)] - 0.30) < 1e-5
          and new_sev == 0.30
          and fields.wound_severity[0, int(BodyPart.L_HAND),
                                       int(WoundKind.CUT)] == 0.0)
    print(_row("step 4 - inflict_wound at (0, R_HAND, CUT)",
               ok, f"sev={new_sev:.3f}"))
    if not ok:
        failures += 1

    # Step 5 — bleeding : cut bleeds, bruise doesn't.
    # Inflict a heavy cut on agent 0 and a heavy bruise on agent 1.
    inflict_wound(fields, 1, int(BodyPart.TORSO),
                    int(WoundKind.BRUISE), 0.80)
    # Set agent 1 alive (founders are alive after bootstrap).
    fields.blood_volume_l[0] = 5.0
    fields.blood_volume_l[1] = 5.0
    # Step anatomy for 1 hour (3600 s) to make bleeding measurable.
    step_anatomy(sim, dt_s=3600.0)
    blood_0 = float(fields.blood_volume_l[0])
    blood_1 = float(fields.blood_volume_l[1])
    ok = (blood_0 < 5.0 and blood_1 == 5.0)
    print(_row("step 5 - cut bleeds, bruise doesn't",
               ok, f"cut_blood={blood_0:.3f} bruise_blood={blood_1:.3f}"))
    if not ok:
        failures += 1

    # Step 6 — hemorrhage : drain blood below threshold → death.
    fields.blood_volume_l[0] = 1.6  # just above threshold
    # Re-inflict to ensure agent 0 has a cut bleeding.
    inflict_wound(fields, 0, int(BodyPart.R_HAND),
                    int(WoundKind.CUT), 0.50)
    sim.agents.alive[0] = True  # reset in case prior step killed
    fields.death_by_hemorrhage[0] = False
    # Step for ~100 hours of bleeding to ensure death.
    for _ in range(20):
        step_anatomy(sim, dt_s=3600.0)
    ok = (not bool(sim.agents.alive[0])
          and bool(fields.death_by_hemorrhage[0])
          and fields.blood_volume_l[0] < BLOOD_DEATH_THRESHOLD_L)
    print(_row("step 6 - death by hemorrhage triggered",
               ok, f"alive={bool(sim.agents.alive[0])} "
                   f"hemo_flag={bool(fields.death_by_hemorrhage[0])} "
                   f"blood={float(fields.blood_volume_l[0]):.3f}"))
    if not ok:
        failures += 1

    # Step 7 — healing : wound severity decreases over a long step.
    sim2 = _build_sim("p64_heal", seed=0xC0FFEE_6411 & 0xFFFFFFFFFFFFFFFF)
    sim2.step()
    fields2 = install_anatomy(sim2)
    inflict_wound(fields2, 0, int(BodyPart.HEAD),
                    int(WoundKind.BRUISE), 0.80)
    inflict_wound(fields2, 0, int(BodyPart.R_HAND),
                    int(WoundKind.CUT), 0.80)
    sev_bruise_t0 = float(fields2.wound_severity[0, int(BodyPart.HEAD),
                                                     int(WoundKind.BRUISE)])
    sev_cut_t0 = float(fields2.wound_severity[0, int(BodyPart.R_HAND),
                                                  int(WoundKind.CUT)])
    # Step for ~3 days.
    for _ in range(3):
        step_anatomy(sim2, dt_s=86400.0)
    sev_bruise_t3 = float(fields2.wound_severity[0, int(BodyPart.HEAD),
                                                     int(WoundKind.BRUISE)])
    sev_cut_t3 = float(fields2.wound_severity[0, int(BodyPart.R_HAND),
                                                  int(WoundKind.CUT)])
    bruise_healed_more = (sev_bruise_t0 - sev_bruise_t3) > (sev_cut_t0 - sev_cut_t3)
    ok = (sev_bruise_t3 < sev_bruise_t0
          and sev_cut_t3 < sev_cut_t0
          and bruise_healed_more)
    print(_row("step 7 - healing per-kind rates (bruise > cut speed)",
               ok, f"bruise {sev_bruise_t0:.3f}→{sev_bruise_t3:.3f}, "
                   f"cut {sev_cut_t0:.3f}→{sev_cut_t3:.3f}"))
    if not ok:
        failures += 1

    # Step 8 — wound_from_action deterministic.
    sim3 = _build_sim("p64_det", seed=0xC0FFEE_6412 & 0xFFFFFFFFFFFFFFFF)
    sim3.step()
    f1 = install_anatomy(sim3)
    f2 = AnatomyFields(); f2.initialise(sim3.agents.capacity)
    n_inflicted_1 = 0
    n_inflicted_2 = 0
    for tick in range(50):
        out1 = wound_from_action(f1, 0, int(ActionKind.MINE),
                                    int(sim3.cfg.seed), tick)
        out2 = wound_from_action(f2, 0, int(ActionKind.MINE),
                                    int(sim3.cfg.seed), tick)
        n_inflicted_1 += len(out1)
        n_inflicted_2 += len(out2)
        if out1 != out2:
            break
    ok = (n_inflicted_1 == n_inflicted_2 > 0
          and np.array_equal(f1.wound_severity, f2.wound_severity))
    print(_row("step 8 - wound_from_action deterministic across 50 ticks",
               ok, f"n_inflicted={n_inflicted_1} (per-side) "
                   f"severity_match={np.array_equal(f1.wound_severity, f2.wound_severity)}"))
    if not ok:
        failures += 1

    # Step 9 — action-coupling : MINE inflicts R_HAND cuts statistically.
    sim4 = _build_sim("p64_action", seed=0xC0FFEE_6413 & 0xFFFFFFFFFFFFFFFF)
    sim4.step()
    f4 = install_anatomy(sim4)
    # Trigger MINE wounds many times across all founders.
    n_mine_calls = 0
    total_r_hand_cuts = 0
    for tick in range(200):
        for row in range(sim4.agents.n_active):
            out = wound_from_action(f4, row, int(ActionKind.MINE),
                                       int(sim4.cfg.seed), tick * 100 + row)
            n_mine_calls += 1
            for (part, kind, sev) in out:
                if part == int(BodyPart.R_HAND) and kind == int(WoundKind.CUT):
                    total_r_hand_cuts += 1
    # Expectation : ~25 % of MINE calls inflict wounds, ~half have R_HAND
    # entry. So ~12 % of calls produce a R_HAND cut.
    ratio = total_r_hand_cuts / max(n_mine_calls, 1)
    ok = ratio > 0.05  # well above random noise
    print(_row("step 9 - MINE → R_HAND cut emerges statistically",
               ok, f"calls={n_mine_calls} R_HAND_cuts={total_r_hand_cuts} "
                   f"ratio={ratio:.3f}"))
    if not ok:
        failures += 1

    # Diagnostic dump.
    state = anatomy_state(sim4)
    print(f"\nAnatomy state on sim4: {state}")

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
