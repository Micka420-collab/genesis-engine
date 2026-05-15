"""P40 — Wave 13 emergent art discovery smoke.

Same invariant as p38 buildings : **no script, agents discover**.
Here it's drawings : an agent picks a pigment + a surface + draws
strokes. The engine doesn't know what a "horse" or "sun" is — it
records the geometric fingerprint (pigment, surface, stroke count
class, dominant orientation, closed/open) and a deterministic
auto-name diverges per culture.

  1. install_art_discovery idempotent
  2. unknown pigment → rejected
  3. unknown surface → rejected
  4. too-few strokes → rejected
  5. closed ring with hematite on bedrock_calcite → archetype emerges
  6. same culture redraws the same fingerprint → same name (recognized)
  7. different culture draws same fingerprint → different name
  8. ADR-0005 19/19 OK
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

from engine.sim import Simulation, SimConfig                # noqa: E402
from engine.art_discovery import (                          # noqa: E402
    install_art_discovery, begin_drawing, add_stroke,
    complete_drawing, abandon_drawing, art_state)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:55s} {detail}"


def _build_sim(name: str):
    cfg = SimConfig(
        name=name, seed=0xC0FFEE_A47 & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=10,
        bounds_km=(0.2, 0.2), spawn_radius_m=50.0,
        drive_accel=1.0, cultures=2,
    )
    return Simulation(cfg)


def _draw_closed_square(sim, row, pigment="hematite",
                        surface="bedrock_calcite"):
    """Helper: closed 4-stroke ring (square)."""
    ok, _ = begin_drawing(sim, row, pigment, surface)
    if not ok:
        return False
    add_stroke(sim, row, 0.0, 0.0, 4.0, 0.0)     # E
    add_stroke(sim, row, 4.0, 0.0, 4.0, 4.0)     # N
    add_stroke(sim, row, 4.0, 4.0, 0.0, 4.0)     # W
    add_stroke(sim, row, 0.0, 4.0, 0.0, 0.0)     # S → back to start (closed)
    return True


def main() -> int:
    print("=" * 78)
    print("P40 — Wave 13 emergent art discovery")
    print("=" * 78)
    failures = 0

    sim = _build_sim("p40_art")
    state = install_art_discovery(sim)

    # Force the founders alive + cultures.
    for r in range(4):
        sim.agents.alive[r] = True
    sim.agents.culture = [0, 0, 1, 1]   # row 0,1 = culture 0 ; row 2,3 = culture 1

    # Step 1 — idempotent
    s2 = install_art_discovery(sim)
    print(_row("step 1 — install idempotent", state is s2, ""))
    if state is not s2:
        failures += 1

    # Step 2 — unknown pigment
    ok, reason = begin_drawing(sim, 0, "moonstone", "bedrock_calcite")
    ok_step = (not ok and reason.startswith("unknown_pigment"))
    print(_row("step 2 — unknown pigment rejected",
               ok_step, f"reason={reason}"))
    if not ok_step:
        failures += 1

    # Step 3 — unknown surface
    ok, reason = begin_drawing(sim, 0, "hematite", "glass")
    ok_step = (not ok and reason.startswith("unknown_surface"))
    print(_row("step 3 — unknown surface rejected",
               ok_step, f"reason={reason}"))
    if not ok_step:
        failures += 1

    # Step 4 — too-few strokes
    begin_drawing(sim, 0, "hematite", "bedrock_calcite")
    add_stroke(sim, 0, 0.0, 0.0, 1.0, 0.0)
    add_stroke(sim, 0, 1.0, 0.0, 2.0, 0.0)   # only 2 strokes < 3
    success, art_id, reason = complete_drawing(sim, 0)
    ok_step = (not success and reason == "too_few_strokes")
    print(_row("step 4 — too few strokes rejected",
               ok_step, f"reason={reason}"))
    if not ok_step:
        failures += 1

    # Step 5 — closed hematite ring culture 0
    _draw_closed_square(sim, 0)
    success, art_id_5, name_5 = complete_drawing(sim, 0)
    ok_step = (success and art_id_5 is not None and name_5
               and name_5.startswith("hematite_ring_"))
    print(_row("step 5 — closed ring archetype emerges (culture 0)",
               ok_step, f"name='{name_5}'"))
    if not ok_step:
        failures += 1

    # Step 6 — same culture redraws same fingerprint
    _draw_closed_square(sim, 1)   # row 1 also culture 0
    success, art_id_6, name_6 = complete_drawing(sim, 1)
    ok_step = (success and name_6 == name_5)
    print(_row("step 6 — same culture, same fingerprint → same name",
               ok_step,
               f"reused='{name_6}' (count={state.cultural_archetypes[0].get(state.discovered[art_id_5].archetype_key)})"))
    if not ok_step:
        failures += 1

    # Step 7 — different culture, same fingerprint → DIFFERENT name
    _draw_closed_square(sim, 2)   # row 2 = culture 1
    success, art_id_7, name_7 = complete_drawing(sim, 2)
    ok_step = (success and name_7 != name_5
               and name_7.startswith("hematite_ring_"))
    print(_row("step 7 — different culture → different name (emergent)",
               ok_step, f"culture0='{name_5}'  culture1='{name_7}'"))
    if not ok_step:
        failures += 1

    # Step 8 — ADR-0005 audit
    from engine.world_model_capabilities import audit_modules
    table, lint_fails = audit_modules(strict=False)
    p_row = next((r for r in table["modules"]
                  if r["module"] == "engine.art_discovery"), None)
    ok_step = (p_row is not None and p_row["status"] == "ok"
               and not lint_fails)
    print(_row("step 8 — ADR-0005 lists art_discovery OK",
               ok_step, f"failures={lint_fails}"))
    if not ok_step:
        failures += 1

    print()
    snap = art_state(sim)
    print(f"art snapshot:")
    print(f"  n_drawings: {snap.get('n_drawings')}")
    print(f"  n_cultural_archetypes: {snap.get('n_cultural_archetypes')}")
    print(f"  completed: {snap.get('drawings_completed_total')}")
    print(f"  rejected (too_few): {snap.get('rejected_too_few_strokes')}")
    print(f"  rejected (no_pigment): {snap.get('rejected_no_pigment')}")
    print(f"  rejected (no_surface): {snap.get('rejected_no_surface')}")
    print()
    if failures == 0:
        print("RESULT: PASS — Wave 13 art discovery smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
