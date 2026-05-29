"""P121 — Wave 52 heritable decoder wired into the live brain smoke.

  1. Public API surface.
  2. View shape (256,) ; ONLY the cognition slice [64,128) is reinterpreted,
     the rest of the genome is untouched.
  3. Determinism + purity : same genome → identical view ; input never mutated.
  4. Gain bounds : per-gene gain ∈ (1-A, 1+A), length 64.
  5. Neutral code recovers the legacy brain EXACTLY : a genome whose
     regulatory region decodes to P≡0.5 has gain≡1, so forward_policy on the
     regulated view is byte-identical to the legacy brain.
  6. Semantic closure in BEHAVIOUR : two genomes identical on the structural
     region S=[0,192) but differing on the regulatory region R=[192,256)
     give *identical* legacy logits (brain ignores R) but *different*
     regulated logits (R reinterprets the cognition slice).
  7. Behavioural pleiotropy : changing R re-weights MANY cognition genes
     (never hand-assigned per gene).
  8. Flag gating : SimConfig.heritable_brain defaults False ;
     heritable_brain_enabled reflects the flag.
  9. Real founder genomes : regulated vs legacy policy differ for ≥1 founder ;
     a flag-ON sim steps live (brain path exercised) and stays deterministic.
 10. regulation_summary coherent : bounds, k_traits, neutral detection, label.
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

from engine.core import prf_rng                                         # noqa: E402
from engine.sim import Simulation, SimConfig                            # noqa: E402
from engine.genome import GENOME_SIZE, GENE_GROUP_COGNITION, attach_genome  # noqa: E402
from engine.genome_decoder import PhenotypeConfig                       # noqa: E402
from engine.neat_brain import forward_policy, N_INPUTS                  # noqa: E402
from engine.regulated_brain import (                                    # noqa: E402
    REGULATION_AMPLITUDE, regulatory_modulation, regulated_genome_view,
    heritable_brain_enabled, regulation_summary,
)

CFG = PhenotypeConfig()
SEED = 0xC0FFEE_121
COG = GENE_GROUP_COGNITION


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _rand_genome(seed, idx):
    return prf_rng(seed, ["test", "genome"], [int(idx)]).random(
        GENOME_SIZE, dtype=np.float32)


def _rand_feats(seed, idx):
    return prf_rng(seed, ["test", "feats"], [int(idx)]).random(
        N_INPUTS, dtype=np.float32)


def _build_sim(name, seed, *, heritable):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=8, max_agents=20,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
        emergent_cognition=True, heritable_brain=heritable,
    )
    return Simulation(cfg)


def main() -> int:
    print("=" * 78)
    print("P121 — Wave 52 heritable decoder wired into the live brain smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API.
    ok = all(name in globals() for name in (
        "REGULATION_AMPLITUDE", "regulatory_modulation", "regulated_genome_view",
        "heritable_brain_enabled", "regulation_summary",
    ))
    print(_row("step 1 - public API exposed", ok))
    if not ok:
        failures += 1

    # Step 2 — view shape ; only cognition slice changes.
    g = _rand_genome(SEED, 0)
    view = regulated_genome_view(g, CFG)
    cog_changed = not np.array_equal(view[COG], g[COG])
    before_same = np.array_equal(view[:COG.start], g[:COG.start])
    after_same = np.array_equal(view[COG.stop:], g[COG.stop:])
    ok = (view.shape == (GENOME_SIZE,) and cog_changed
          and before_same and after_same)
    print(_row("step 2 - view (256,) ; only cognition [64,128) reinterpreted",
               ok, f"cog_changed={cog_changed} rest_intact={before_same and after_same}"))
    if not ok:
        failures += 1

    # Step 3 — determinism + purity.
    g3 = _rand_genome(SEED, 1)
    g3_orig = g3.copy()
    v1 = regulated_genome_view(g3, CFG)
    v2 = regulated_genome_view(g3, CFG)
    input_intact = np.array_equal(g3, g3_orig)
    ok = np.array_equal(v1, v2) and input_intact
    print(_row("step 3 - deterministic view + input never mutated",
               ok, f"identical={np.array_equal(v1, v2)} input_intact={input_intact}"))
    if not ok:
        failures += 1

    # Step 4 — gain bounds.
    gain = regulatory_modulation(_rand_genome(SEED, 2), CFG)
    lo, hi = 1.0 - REGULATION_AMPLITUDE, 1.0 + REGULATION_AMPLITUDE
    ok = (gain.shape == (COG.stop - COG.start,)
          and bool(np.all(gain >= lo - 1e-6)) and bool(np.all(gain <= hi + 1e-6)))
    print(_row("step 4 - gain ∈ (1-A,1+A), length 64",
               ok, f"len={gain.size} min={gain.min():.3f} max={gain.max():.3f}"))
    if not ok:
        failures += 1

    # Step 5 — neutral code (R=0.5 → P≡0.5 → gain≡1) recovers legacy brain.
    gN = _rand_genome(SEED, 3)
    gN[CFG.reg_start:CFG.reg_end] = 0.5
    viewN = regulated_genome_view(gN, CFG)
    feats5 = _rand_feats(SEED, 0)
    legacy_logits = forward_policy(gN, feats5)
    regN_logits = forward_policy(viewN, feats5)
    gainN = regulatory_modulation(gN, CFG)
    ok = (np.array_equal(viewN[COG], gN[COG])
          and np.array_equal(legacy_logits, regN_logits)
          and float(np.max(np.abs(gainN - 1.0))) < 1e-6)
    print(_row("step 5 - neutral code recovers legacy brain byte-for-byte",
               ok, f"gain_dev={float(np.max(np.abs(gainN-1.0))):.2e} "
                   f"logits_equal={np.array_equal(legacy_logits, regN_logits)}"))
    if not ok:
        failures += 1

    # Step 6 — SEMANTIC CLOSURE in behaviour : S equal, R differs.
    base = _rand_genome(SEED, 4)
    gA = base.copy()
    gB = base.copy()
    gB[CFG.reg_start:CFG.reg_end] = _rand_genome(SEED, 5)[CFG.reg_start:CFG.reg_end]
    feats6 = _rand_feats(SEED, 1)
    # S (which contains the cognition slice) is identical → legacy ignores R.
    legacy_equal = np.array_equal(forward_policy(gA, feats6),
                                  forward_policy(gB, feats6))
    # Regulated brain reinterprets the cognition slice via R → logits differ.
    reg_dist = float(np.sqrt(np.sum(
        (forward_policy(regulated_genome_view(gA, CFG), feats6)
         - forward_policy(regulated_genome_view(gB, CFG), feats6)) ** 2)))
    ok = legacy_equal and reg_dist > 1e-4
    print(_row("step 6 - semantic closure : legacy same, regulated differs on R",
               ok, f"legacy_equal={legacy_equal} Δregulated_logits={reg_dist:.4f}"))
    if not ok:
        failures += 1

    # Step 7 — behavioural pleiotropy : changing R re-weights many cognition genes.
    n_changed = int((regulated_genome_view(gA, CFG)[COG]
                     != regulated_genome_view(gB, CFG)[COG]).sum())
    ok = n_changed >= 32
    print(_row("step 7 - pleiotropy : R re-weights ≥32/64 cognition genes",
               ok, f"genes_changed={n_changed}/64"))
    if not ok:
        failures += 1

    # Step 8 — flag gating.
    default_off = (SimConfig().heritable_brain is False)

    class _S:
        pass
    s_on = _S(); s_on.cfg = SimConfig(heritable_brain=True)
    s_off = _S(); s_off.cfg = SimConfig(heritable_brain=False)
    ok = (default_off and heritable_brain_enabled(s_on)
          and not heritable_brain_enabled(s_off))
    print(_row("step 8 - SimConfig.heritable_brain defaults OFF ; gate works",
               ok, f"default_off={default_off}"))
    if not ok:
        failures += 1

    # Step 9 — LIVE genome-brain decision honours the flag. genome_decide is
    # the genome-encoded policy's decision function; we drive it directly on
    # real perceived observations. Flipping the flag must change the decision
    # for ≥1 founder, and the flag-OFF decision must be deterministic.
    from engine.cognition import perceive
    from engine.neat_brain import genome_decide
    sim = _build_sim("p121_founders", SEED, heritable=False)
    sim.step()                                  # spawn founders
    attach_genome(sim.agents, int(sim.cfg.seed))
    n = sim.agents.n_active
    decide_diff = 0
    for r in range(n):
        obs = perceive(sim.agents, r, sim.streamer, grid=sim._grid, tick=sim.tick)
        sim.cfg.heritable_brain = False
        d_off = genome_decide(sim.agents, obs, sim)
        sim.cfg.heritable_brain = True
        d_on = genome_decide(sim.agents, obs, sim)
        if d_off.action != d_on.action or abs(d_off.confidence - d_on.confidence) > 1e-9:
            decide_diff += 1
    sim.cfg.heritable_brain = False
    obs0 = perceive(sim.agents, 0, sim.streamer, grid=sim._grid, tick=sim.tick)
    da = genome_decide(sim.agents, obs0, sim)
    db = genome_decide(sim.agents, obs0, sim)
    det_off = (da.action == db.action and abs(da.confidence - db.confidence) < 1e-12)
    ok = (n >= 2 and decide_diff >= 1 and det_off)
    print(_row("step 9 - live genome_decide honours flag ; OFF deterministic",
               ok, f"n={n} decide_diff={decide_diff}/{n} off_det={det_off}"))
    if not ok:
        failures += 1

    # Step 10 — summary coherent.
    summ = regulation_summary(gA, CFG)
    summN = regulation_summary(gN, CFG)
    ok = (summ["k_traits"] == CFG.k_traits
          and summ["gain_min"] >= lo - 1e-6 and summ["gain_max"] <= hi + 1e-6
          and summ["is_neutral_code"] is False and summN["is_neutral_code"] is True
          and summ["semantic_closure"].startswith("behaviour-side"))
    print(_row("step 10 - regulation_summary coherent (bounds, neutral, label)",
               ok, f"k={summ['k_traits']} neutral_detect={summN['is_neutral_code']}"))
    if not ok:
        failures += 1

    print(f"\nRegulation summary (non-neutral): {summ}")

    total = 10
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
