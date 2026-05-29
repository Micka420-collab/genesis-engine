"""P117 — Wave 47 heritable genotype→phenotype decoder smoke.

  1. Public API surface.
  2. Decode shape/range : phenotype is (K,) and every trait ∈ (0, 1).
  3. Determinism : same genome → identical phenotype + sha256 signature.
  4. Semantic-closure signature : holding S fixed and varying the regulatory
     code R changes the phenotype, while the legacy gene_to_trait on a
     structural group is *insensitive* to R.
  5. The regulatory code R is itself inherited (child loci ∈ {parent_a,
     parent_b} apart from rare mutation).
  6. Heritability : crossover children resemble the midparent phenotype far
     more than unrelated random genomes do.
  7. Emergent pleiotropy : perturbing ONE structural chunk moves *many*
     phenotype traits (never hand-assigned).
  8. Epistasis : the SAME structural change has DIFFERENT phenotypic effect
     under DIFFERENT regulatory codes (effect depends on genetic background).
  9. Works on real sim founder genomes : positive phenotype diversity,
     reproducible across two same-seed builds.
 10. decoder_summary layout coherent (n_weights == K·F == |R|).
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
from engine.genome import (                                            # noqa: E402
    GENOME_SIZE, GENE_GROUP_APPEARANCE, attach_genome, crossover, gene_to_trait,
)
from engine.genome_decoder import (                                     # noqa: E402
    PhenotypeConfig, decode_phenotype, decode_population,
    phenotype_signature, phenotype_distance, phenotype_diversity,
    code_sensitivity, structural_features, regulatory_weights,
    decoder_summary,
)

CFG = PhenotypeConfig()
SEED = 0xC0FFEE_117


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _rand_genome(seed, idx):
    return prf_rng(seed, ["test", "genome"], [int(idx)]).random(
        GENOME_SIZE, dtype=np.float32)


def _build_sim(name, seed=SEED):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=8, max_agents=20,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def main() -> int:
    print("=" * 78)
    print("P117 — Wave 47 heritable genotype→phenotype decoder smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API.
    ok = all(name in globals() for name in (
        "PhenotypeConfig", "decode_phenotype", "decode_population",
        "phenotype_signature", "phenotype_distance", "phenotype_diversity",
        "code_sensitivity", "structural_features", "regulatory_weights",
        "decoder_summary",
    ))
    print(_row("step 1 - public API exposed", ok))
    if not ok:
        failures += 1

    # Step 2 — shape / range.
    g = _rand_genome(SEED, 0)
    p = decode_phenotype(g, CFG)
    ok = (p.shape == (CFG.k_traits,)
          and bool(np.all(p > 0.0)) and bool(np.all(p < 1.0)))
    print(_row("step 2 - phenotype shape (K,) and ∈ (0,1)",
               ok, f"shape={tuple(p.shape)} min={p.min():.4f} max={p.max():.4f}"))
    if not ok:
        failures += 1

    # Step 3 — determinism.
    sig_a = phenotype_signature(_rand_genome(SEED, 1), CFG)
    sig_b = phenotype_signature(_rand_genome(SEED, 1), CFG)
    p2a = decode_phenotype(_rand_genome(SEED, 1), CFG)
    p2b = decode_phenotype(_rand_genome(SEED, 1), CFG)
    ok = (sig_a == sig_b and len(sig_a) == 64
          and np.array_equal(p2a, p2b))
    print(_row("step 3 - deterministic decode + sha256 signature",
               ok, f"sig_match={sig_a == sig_b} sig_len={len(sig_a)}"))
    if not ok:
        failures += 1

    # Step 4 — semantic-closure signature : R matters, legacy ignores R.
    base = _rand_genome(SEED, 2)
    g_newcode = base.copy()
    g_newcode[CFG.reg_start:CFG.reg_end] = _rand_genome(SEED, 99)[
        CFG.reg_start:CFG.reg_end]
    phen_changed = phenotype_distance(
        decode_phenotype(base, CFG), decode_phenotype(g_newcode, CFG))
    legacy_appearance_same = abs(
        gene_to_trait(base, GENE_GROUP_APPEARANCE)
        - gene_to_trait(g_newcode, GENE_GROUP_APPEARANCE)) < 1e-9
    sens = code_sensitivity(base, SEED, trials=32, cfg=CFG)
    ok = (phen_changed > 1e-3 and legacy_appearance_same and sens > 1e-2)
    print(_row("step 4 - phenotype depends on heritable code R (legacy doesn't)",
               ok, f"Δphen={phen_changed:.3f} legacy_same={legacy_appearance_same} "
                   f"sensitivity={sens:.3f}"))
    if not ok:
        failures += 1

    # Step 5 — the regulatory code R is itself inherited.
    pa = _rand_genome(SEED, 10)
    pb = _rand_genome(SEED, 11)
    rng = prf_rng(SEED, ["test", "xover"], [0])
    child = crossover(pa, pb, rng)
    from_parent = np.logical_or(np.isclose(child, pa, atol=1e-6),
                                np.isclose(child, pb, atol=1e-6))
    n_offspec = int((~from_parent).sum())            # mutated loci only
    # The regulatory code R must itself be inherited: at most a couple of R
    # loci differ from both parents (per-gene mutation 1e-4 over 64 loci → ~0).
    reg_nonparental = int((~from_parent[CFG.reg_start:CFG.reg_end]).sum())
    reg_inherited = reg_nonparental <= 2
    ok = (n_offspec <= 5 and reg_inherited)
    print(_row("step 5 - regulatory code R inherited via crossover",
               ok, f"non_parental_loci={n_offspec}/256"))
    if not ok:
        failures += 1

    # Step 6 — heritability : children resemble midparent > random genomes.
    mid_phen = 0.5 * (decode_phenotype(pa, CFG) + decode_phenotype(pb, CFG))
    child_dists, rand_dists = [], []
    for i in range(40):
        rch = prf_rng(SEED, ["test", "child"], [i])
        c = crossover(pa, pb, rch)
        child_dists.append(phenotype_distance(decode_phenotype(c, CFG), mid_phen))
        r = _rand_genome(SEED, 1000 + i)
        rand_dists.append(phenotype_distance(decode_phenotype(r, CFG), mid_phen))
    mean_child = float(np.mean(child_dists))
    mean_rand = float(np.mean(rand_dists))
    ok = mean_child < mean_rand
    print(_row("step 6 - heritability : child closer to midparent than random",
               ok, f"d(child)={mean_child:.3f} < d(random)={mean_rand:.3f}"))
    if not ok:
        failures += 1

    # Step 7 — emergent pleiotropy : one structural chunk → many traits move.
    g7 = _rand_genome(SEED, 20)
    p7a = decode_phenotype(g7, CFG)
    g7b = g7.copy()
    chunk = (CFG.struct_end - CFG.struct_start) // CFG.n_features
    g7b[CFG.struct_start:CFG.struct_start + chunk] = np.clip(
        g7b[CFG.struct_start:CFG.struct_start + chunk] + 0.3, 0.0, 1.0)
    p7b = decode_phenotype(g7b, CFG)
    n_traits_moved = int((np.abs(p7b - p7a) > 1e-5).sum())
    ok = n_traits_moved >= 2
    print(_row("step 7 - pleiotropy : one structural chunk moves ≥2 traits",
               ok, f"traits_moved={n_traits_moved}/{CFG.k_traits}"))
    if not ok:
        failures += 1

    # Step 8 — epistasis : same ΔS, different effect under different code R.
    base8 = _rand_genome(SEED, 30)
    gA = base8.copy()
    gB = base8.copy()
    gB[CFG.reg_start:CFG.reg_end] = _rand_genome(SEED, 31)[
        CFG.reg_start:CFG.reg_end]
    dS = slice(CFG.struct_start, CFG.struct_start + chunk)
    gA2 = gA.copy(); gA2[dS] = np.clip(gA2[dS] + 0.25, 0.0, 1.0)
    gB2 = gB.copy(); gB2[dS] = np.clip(gB2[dS] + 0.25, 0.0, 1.0)
    delta_A = decode_phenotype(gA2, CFG) - decode_phenotype(gA, CFG)
    delta_B = decode_phenotype(gB2, CFG) - decode_phenotype(gB, CFG)
    epistasis = phenotype_distance(delta_A, delta_B)
    ok = epistasis > 1e-3
    print(_row("step 8 - epistasis : same ΔS, code-dependent effect",
               ok, f"||Δ_A − Δ_B||={epistasis:.3f}"))
    if not ok:
        failures += 1

    # Step 9 — real sim founder genomes : diversity + reproducibility.
    def _founder_diversity(seed):
        sim = _build_sim(f"p117_real_{seed}", seed=seed)
        sim.step()                              # ensure founders are spawned
        attach_genome(sim.agents, int(sim.cfg.seed))
        n = sim.agents.n_active
        genomes = np.array(sim.agents.genome[:n], copy=True)
        return phenotype_diversity(genomes, CFG), n
    div1, n1 = _founder_diversity(SEED)
    div2, n2 = _founder_diversity(SEED)
    ok = (n1 >= 2 and div1 > 0.0 and abs(div1 - div2) < 1e-9)
    print(_row("step 9 - real founder genomes : diversity>0, reproducible",
               ok, f"n={n1} diversity={div1:.4f} reproducible={abs(div1 - div2) < 1e-9}"))
    if not ok:
        failures += 1

    # Step 10 — summary layout coherent.
    summ = decoder_summary(CFG)
    ok = (summ["n_weights"] == CFG.k_traits * CFG.n_features
          == (CFG.reg_end - CFG.reg_start)
          and summ["philosophy"] == "HERITABLE_EVOLVABLE_CODE")
    print(_row("step 10 - decoder_summary coherent (n_weights == K·F == |R|)",
               ok, f"n_weights={summ['n_weights']} reg={summ['regulatory_region']}"))
    if not ok:
        failures += 1

    print(f"\nDecoder summary: {summ}")

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
