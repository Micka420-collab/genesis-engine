"""P71 — Wave 40 lineage observer smoke.

  1. Public API surface.
  2. Fresh sim with founders only → all founders, no descendants, gen 0.
  3. ``is_founder`` returns True for spawn_founder rows, False after spawn_offspring.
  4. ``spawn_offspring`` creates a child : parents recorded, generation = 1.
  5. **Trait inheritance** : child intelligence ≈ midparent ± mutation.
  6. ``build_ancestors`` walks correctly (child → 2 parents).
  7. ``build_descendants`` reverse-walks (parent → child).
  8. ``inbreeding_coefficient`` : 0.0 for unrelated couple, 0.25 siblings.
  9. ``install_lineage_observer`` captures snapshots determinism.
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
from engine.lineage_observer import (                                   # noqa: E402
    TRAIT_NAMES, FOUNDER_PARENT_SENTINEL,
    LineageConfig, LineageSnapshot, LineageHistory,
    is_founder, build_ancestors, build_descendants,
    inbreeding_coefficient, observe_lineage,
    install_lineage_observer, uninstall_lineage_observer,
    lineage_state_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xC0FFEE_71):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=20,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def main() -> int:
    print("=" * 78)
    print("P71 — Wave 40 lineage observer smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API.
    ok = all(name in globals() for name in (
        "LineageConfig", "LineageSnapshot", "LineageHistory",
        "is_founder", "build_ancestors", "build_descendants",
        "inbreeding_coefficient", "observe_lineage",
        "install_lineage_observer", "uninstall_lineage_observer",
        "lineage_state_summary",
        "TRAIT_NAMES", "FOUNDER_PARENT_SENTINEL",
    )) and len(TRAIT_NAMES) == 11
    print(_row("step 1 - public API exposed (11 traits)",
               ok, f"n_traits={len(TRAIT_NAMES)}"))
    if not ok:
        failures += 1

    # Step 2 — fresh sim : founders only.
    sim = _build_sim("p71_fresh")
    sim.step()
    snap = observe_lineage(sim)
    ok = (snap.n_founders == sim.agents.n_active
          and snap.n_descendants == 0
          and snap.max_generation == 0)
    print(_row("step 2 - fresh sim : all founders, no descendants",
               ok, f"founders={snap.n_founders} descendants={snap.n_descendants} "
                   f"max_gen={snap.max_generation}"))
    if not ok:
        failures += 1

    # Step 3 — is_founder.
    sim2 = _build_sim("p71_isfounder",
                        seed=0xC0FFEE_7111 & 0xFFFFFFFFFFFFFFFF)
    sim2.step()
    n_founders = sim2.agents.n_active
    all_founders = all(is_founder(sim2, r) for r in range(n_founders))
    # Spawn an offspring : not a founder.
    pa, pb = 0, 1
    pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    child_row = sim2.agents.spawn_offspring(int(sim2.cfg.seed),
                                              pa, pb, int(sim2.tick),
                                              0, pos)
    ok = (all_founders and child_row >= 0
          and not is_founder(sim2, child_row))
    print(_row("step 3 - is_founder distinguishes founders vs offspring",
               ok, f"all_founders={all_founders} "
                   f"child_row={child_row} "
                   f"child_is_founder={is_founder(sim2, child_row)}"))
    if not ok:
        failures += 1

    # Step 4 — child has parents + generation=1.
    parents_arr = np.asarray(sim2.agents.parents[child_row])
    gen_child = int(sim2.agents.generation[child_row])
    ok = (parents_arr[0] in (pa, pb) and parents_arr[1] in (pa, pb)
          and parents_arr[0] != parents_arr[1]
          and gen_child == 1)
    print(_row("step 4 - child parents recorded + generation=1",
               ok, f"parents={tuple(parents_arr)} gen={gen_child}"))
    if not ok:
        failures += 1

    # Step 5 — trait inheritance : child intelligence ≈ midparent.
    intel_pa = float(sim2.agents.intelligence[pa])
    intel_pb = float(sim2.agents.intelligence[pb])
    intel_child = float(sim2.agents.intelligence[child_row])
    midparent = (intel_pa + intel_pb) * 0.5
    # Mutation σ = 0.05 → expect within ~3σ = 0.15 of midparent.
    ok = abs(intel_child - midparent) < 0.15
    print(_row("step 5 - intelligence inheritance midparent ± 3σ",
               ok, f"pa={intel_pa:.3f} pb={intel_pb:.3f} "
                   f"midparent={midparent:.3f} child={intel_child:.3f} "
                   f"|delta|={abs(intel_child - midparent):.3f}"))
    if not ok:
        failures += 1

    # Step 6 — build_ancestors finds parents.
    ancestors = build_ancestors(sim2, child_row)
    ok = (pa in ancestors and pb in ancestors)
    print(_row("step 6 - build_ancestors walks to parents",
               ok, f"ancestors={sorted(ancestors)} expected_includes={pa},{pb}"))
    if not ok:
        failures += 1

    # Step 7 — build_descendants reverse-walks.
    descendants_pa = build_descendants(sim2, pa)
    ok = child_row in descendants_pa
    print(_row("step 7 - build_descendants reverse walks",
               ok, f"descendants_of_{pa}={sorted(descendants_pa)}"))
    if not ok:
        failures += 1

    # Step 8 — inbreeding coefficient.
    # Unrelated couple → F = 0.
    F_unrelated = inbreeding_coefficient(sim2, child_row)
    # Now create a sibling pair sharing parents (pa, pb) and have a
    # child from them → F = 0.25.
    sibling_row = sim2.agents.spawn_offspring(int(sim2.cfg.seed),
                                                 pa, pb, int(sim2.tick) + 1,
                                                 1, pos)
    # Sibling pair (child_row, sibling_row) share parents pa, pb.
    # Make them mate (incestuous).
    incest_child = sim2.agents.spawn_offspring(int(sim2.cfg.seed),
                                                  child_row, sibling_row,
                                                  int(sim2.tick) + 2, 2, pos)
    F_incest = inbreeding_coefficient(sim2, incest_child)
    ok = abs(F_unrelated) < 1e-6 and abs(F_incest - 0.25) < 1e-6
    print(_row("step 8 - inbreeding F : unrelated=0, siblings child=0.25",
               ok, f"F_unrelated={F_unrelated:.4f} F_incest={F_incest:.4f}"))
    if not ok:
        failures += 1

    # Step 9 — install observer captures snapshots determinism.
    def _run_observed(seed):
        sub = _build_sim(f"p71_det_{seed}", seed=seed)
        sub.step()
        install_lineage_observer(
            sub, LineageConfig(snapshot_every=5))
        # Spawn an offspring or two to make snapshots non-trivial.
        sub.agents.spawn_offspring(int(sub.cfg.seed), 0, 1,
                                     int(sub.tick), 0,
                                     np.array([0,0,0], dtype=np.float32))
        for _ in range(15):
            sub.step()
        snaps = sub._lineage_state.history.snapshots
        return tuple(
            (s.tick, s.n_alive, s.n_founders, s.n_descendants,
             s.max_generation,
             tuple(sorted(s.generation_counts.items())))
            for s in snaps
        )
    seed_d = 0xC0FFEE_7113 & 0xFFFFFFFFFFFFFFFF
    h_a = _run_observed(seed_d)
    h_b = _run_observed(seed_d)
    ok = h_a == h_b and len(h_a) >= 1
    print(_row("step 9 - install observer determinism",
               ok, f"len={len(h_a)} match={h_a == h_b}"))
    if not ok:
        failures += 1

    # Diagnostic dump.
    final_summary = lineage_state_summary(sim2)
    print(f"\nLineage summary on sim2: {final_summary}")

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
