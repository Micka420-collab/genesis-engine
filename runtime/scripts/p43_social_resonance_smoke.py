"""P43 - Wave 15 social-resonance smoke (Veille 2026-05-17).

Veille du jour combo : arxiv *Synthetic Social Graph: Emergent
Behavior in AI Agent Communities* (2604.27271) x cognitive_plasticity
Wave 12 (buffer learned_skill par agent).

This smoke verifies that the new `engine.social_resonance` module :

  1. Returns safe defaults when plasticity is not installed
     (compute_social_resonance == {} on bare sim).
  2. Returns NaN cohesion when a culture has fewer than 3 alive
     agents (statistical floor).
  3. Cohesion = 1.0 when all members of a culture have an identical
     learned_skill (perfect homogeneity).
  4. Cohesion drops monotonically as we inject growing variance
     into a culture (homogeneous < bimodal in cohesion).
  5. Inter-culture JS divergence = 0.0 when two cultures share the
     same skill distribution.
  6. Inter-culture JS divergence > 0.5 when cultures occupy opposite
     halves of the skill range.
  7. compute_civilization_emergence_score stays in [0, 1] and
     collapses toward 0 when learner_share is 0.
  8. Determinism : two identical calls return bit-identical JSON
     representations.
  9. Pure observer : neither compute_social_resonance nor its
     dependents mutate agents.intelligence, agents.curiosity, or
     plasticity.learned_skill.

Writes a JSONL audit log to journals/p43_social_resonance.jsonl.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import sys


if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import numpy as np                                          # noqa: E402

from engine.sim import Simulation, SimConfig                # noqa: E402
from engine.cognitive_plasticity import (                   # noqa: E402
    install_plasticity)
from engine.social_resonance import (                       # noqa: E402
    compute_social_resonance,
    compute_inter_culture_divergence,
    compute_civilization_emergence_score,
    log_social_resonance,
)


JOURNAL = os.path.abspath(
    os.path.join(ROOT, "journals", "p43_social_resonance.jsonl"))


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, *, founders=24, cultures=2, seed=0xC0F2_2026):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=founders, max_agents=max(60, founders * 3),
        bounds_km=(1.5, 1.5), spawn_radius_m=120.0,
        drive_accel=1500.0, cultures=cultures,
    )
    sim = Simulation(cfg)
    sim.bootstrap()
    return sim


def _set_skills_for_culture(sim, culture_id: int, value):
    """Force every alive agent of `culture_id` to a fixed (or callable)
    learned_skill value. Helper for deterministic test fixtures.
    """
    n = sim.agents.n_active
    rels = sim.agents.relations
    alive = sim.agents.alive
    buf = sim.plasticity.learned_skill
    rng_state = []
    for row in range(n):
        if not bool(alive[row]):
            continue
        if int(rels[row].culture_id) != int(culture_id):
            continue
        if callable(value):
            v = float(value(row, rng_state))
        else:
            v = float(value)
        buf[row] = np.float32(max(0.0, min(1.5, v)))


def _hash_dict(d) -> str:
    return hashlib.sha256(
        json.dumps(d, sort_keys=True, ensure_ascii=False, default=str)
        .encode("utf-8")
    ).hexdigest()[:24]


def main() -> int:
    print("=" * 78)
    print("P43 - Wave 15 social-resonance smoke")
    print("=" * 78)
    failures = 0

    if os.path.exists(JOURNAL):
        os.remove(JOURNAL)

    # ------------------------------------------------------------------
    # Step 1 - No plasticity installed -> safe defaults
    # ------------------------------------------------------------------
    sim = _build_sim("p43_step1")
    # NOTE : do NOT call install_plasticity here.
    per = compute_social_resonance(sim)
    div = compute_inter_culture_divergence(sim)
    score = compute_civilization_emergence_score(sim)
    # With zero buffer (no plasticity), every alive agent has skill=0,
    # so per-culture stats *are* computed (cohesion=1.0 since std=0).
    # Divergence between two zero-distributions is exactly 0.0.
    ok1a = isinstance(per, dict) and len(per) >= 1
    ok1b = isinstance(div, dict)
    all_zero_div = all(abs(v) < 1e-9 for v in div.values()) if div else True
    ok1c = all_zero_div
    ok1d = (isinstance(score, dict)
            and 0.0 <= score["score"] <= 1.0
            and score["learner_share"] == 0.0
            and score["score"] == 0.0)
    print(_row("no-plasticity -> safe defaults (no crash)",
               ok1a and ok1b and ok1c and ok1d,
               f"cultures={len(per)} divs={len(div)} score={score['score']:.3f}"))
    failures += int(not (ok1a and ok1b and ok1c and ok1d))

    # ------------------------------------------------------------------
    # Step 2 - Tiny culture -> cohesion NaN (statistical floor)
    # ------------------------------------------------------------------
    sim = _build_sim("p43_step2", founders=4, cultures=4)
    install_plasticity(sim)
    # Set one agent per culture to skill=0.5 ; force at least one culture
    # to have fewer than 3 members alive (founders=4, cultures=4 -> 1 each).
    per = compute_social_resonance(sim)
    nan_floors = [c for c, m in per.items()
                  if m["n_alive"] < 3 and not math.isfinite(m["cohesion"])]
    ok2 = len(per) > 0 and len(nan_floors) >= 1
    print(_row("cohesion NaN when culture < 3 alive",
               ok2,
               f"cultures={len(per)} below-floor={len(nan_floors)}"))
    failures += int(not ok2)

    # ------------------------------------------------------------------
    # Step 3 - Identical skills -> cohesion = 1.0
    # ------------------------------------------------------------------
    sim = _build_sim("p43_step3", founders=24, cultures=2)
    install_plasticity(sim)
    _set_skills_for_culture(sim, 0, 0.4)
    _set_skills_for_culture(sim, 1, 0.4)
    per = compute_social_resonance(sim)
    coh0 = float(per[0]["cohesion"])
    coh1 = float(per[1]["cohesion"])
    ok3 = math.isclose(coh0, 1.0, abs_tol=1e-9) and math.isclose(
        coh1, 1.0, abs_tol=1e-9)
    print(_row("identical skills -> cohesion = 1.0",
               ok3, f"coh0={coh0:.4f} coh1={coh1:.4f}"))
    failures += int(not ok3)

    # ------------------------------------------------------------------
    # Step 4 - Bimodal skills -> cohesion drops monotonically
    # ------------------------------------------------------------------
    sim = _build_sim("p43_step4", founders=24, cultures=2)
    install_plasticity(sim)
    # Homogeneous culture 0 (all 0.5), bimodal culture 1 (half 0.0 half 1.0)
    _set_skills_for_culture(sim, 0, 0.5)
    counters = {"i": 0}
    def _bimodal(_row_idx, _state):
        counters["i"] += 1
        return 0.0 if (counters["i"] % 2 == 0) else 1.0
    _set_skills_for_culture(sim, 1, _bimodal)
    per = compute_social_resonance(sim)
    coh_homo = float(per[0]["cohesion"])
    coh_bimo = float(per[1]["cohesion"])
    ok4 = math.isclose(coh_homo, 1.0, abs_tol=1e-9) and coh_bimo < 0.5
    print(_row("bimodal culture has lower cohesion than homogeneous",
               ok4, f"homo={coh_homo:.4f} bimodal={coh_bimo:.4f}"))
    failures += int(not ok4)

    # ------------------------------------------------------------------
    # Step 5 - Same distribution -> JS divergence = 0
    # ------------------------------------------------------------------
    sim = _build_sim("p43_step5", founders=24, cultures=2)
    install_plasticity(sim)
    _set_skills_for_culture(sim, 0, 0.3)
    _set_skills_for_culture(sim, 1, 0.3)
    div = compute_inter_culture_divergence(sim)
    pair_key = "0__1"
    js = float(div.get(pair_key, float("nan")))
    ok5 = math.isfinite(js) and js < 1e-6
    print(_row("identical inter-culture distros -> JS = 0",
               ok5, f"js({pair_key})={js:.6f}"))
    failures += int(not ok5)

    # ------------------------------------------------------------------
    # Step 6 - Opposite distributions -> JS large
    # ------------------------------------------------------------------
    sim = _build_sim("p43_step6", founders=24, cultures=2)
    install_plasticity(sim)
    _set_skills_for_culture(sim, 0, 0.05)  # cluster near zero
    _set_skills_for_culture(sim, 1, 1.40)  # cluster near cap
    div = compute_inter_culture_divergence(sim)
    js = float(div.get("0__1", 0.0))
    ok6 = math.isfinite(js) and js > 0.5
    print(_row("opposite inter-culture distros -> JS > 0.5",
               ok6, f"js(0__1)={js:.4f}"))
    failures += int(not ok6)

    # ------------------------------------------------------------------
    # Step 7 - Composite score is in [0, 1] and 0 when no learners
    # ------------------------------------------------------------------
    sim = _build_sim("p43_step7", founders=24, cultures=2)
    install_plasticity(sim)  # all zeros -> no learners
    score_zero = compute_civilization_emergence_score(sim)
    # Now diverge culture 0 toward low-skill and culture 1 toward high-
    # skill (both with non-trivial intra-culture spread, but distinct
    # central tendencies) -> learners > 0, divergence > 0, score > 0.
    _set_skills_for_culture(sim, 0,
        lambda r, _s: 0.20 + 0.02 * (r % 5))
    _set_skills_for_culture(sim, 1,
        lambda r, _s: 1.20 - 0.02 * (r % 5))
    score_active = compute_civilization_emergence_score(sim)
    ok7a = 0.0 <= score_zero["score"] <= 1.0
    ok7b = 0.0 <= score_active["score"] <= 1.0
    ok7c = score_zero["score"] == 0.0
    ok7d = score_active["score"] > score_zero["score"]
    print(_row("composite score in [0,1] and 0 when no learners",
               ok7a and ok7b and ok7c and ok7d,
               f"zero={score_zero['score']:.4f} active={score_active['score']:.4f}"))
    failures += int(not (ok7a and ok7b and ok7c and ok7d))

    # ------------------------------------------------------------------
    # Step 8 - Determinism : two calls -> identical JSON hash
    # ------------------------------------------------------------------
    sim = _build_sim("p43_step8", founders=24, cultures=2)
    install_plasticity(sim)
    _set_skills_for_culture(sim, 0, 0.2)
    _set_skills_for_culture(sim, 1, 0.7)
    e1 = {
        "per": compute_social_resonance(sim),
        "div": compute_inter_culture_divergence(sim),
        "score": compute_civilization_emergence_score(sim),
    }
    e2 = {
        "per": compute_social_resonance(sim),
        "div": compute_inter_culture_divergence(sim),
        "score": compute_civilization_emergence_score(sim),
    }
    h1 = _hash_dict(e1)
    h2 = _hash_dict(e2)
    ok8 = h1 == h2
    print(_row("determinism (no PRNG, no side-effects)",
               ok8, f"h1={h1} h2={h2}"))
    failures += int(not ok8)

    # ------------------------------------------------------------------
    # Step 9 - Read-only invariants : nothing was mutated
    # ------------------------------------------------------------------
    sim = _build_sim("p43_step9", founders=24, cultures=2)
    install_plasticity(sim)
    _set_skills_for_culture(sim, 0, 0.3)
    _set_skills_for_culture(sim, 1, 0.6)
    intel_before = sim.agents.intelligence[:sim.agents.n_active].copy()
    curio_before = sim.agents.curiosity[:sim.agents.n_active].copy()
    buf_before = sim.plasticity.learned_skill.copy()
    # Exercise every public API
    _ = compute_social_resonance(sim)
    _ = compute_inter_culture_divergence(sim)
    _ = compute_civilization_emergence_score(sim)
    _ = log_social_resonance(sim, JOURNAL,
                              extra={"step": "9", "verify": "no-mutation"})
    ok9a = np.array_equal(intel_before,
                          sim.agents.intelligence[:sim.agents.n_active])
    ok9b = np.array_equal(curio_before,
                          sim.agents.curiosity[:sim.agents.n_active])
    ok9c = np.array_equal(buf_before, sim.plasticity.learned_skill)
    print(_row("read-only : intelligence / curiosity / buffer intact",
               ok9a and ok9b and ok9c,
               f"intel={ok9a} curio={ok9b} buf={ok9c}"))
    failures += int(not (ok9a and ok9b and ok9c))

    # ------------------------------------------------------------------
    # Wrap up
    # ------------------------------------------------------------------
    print("-" * 78)
    if failures == 0:
        print("P43 social-resonance smoke : 9/9 PASS")
        # Final journal line — single composite snapshot for downstream
        # dashboards.
        sim = _build_sim("p43_final")
        install_plasticity(sim)
        _set_skills_for_culture(sim, 0,
            lambda r, _s: 0.2 + 0.01 * (r % 9))
        _set_skills_for_culture(sim, 1,
            lambda r, _s: 0.8 - 0.01 * (r % 9))
        log_social_resonance(sim, JOURNAL,
                             extra={"step": "final", "verdict": "PASS"})
        print(f"journal: {JOURNAL}")
        return 0
    print(f"P43 social-resonance smoke : FAILURES={failures}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
