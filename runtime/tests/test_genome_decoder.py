"""Wave 47 heritable genotype→phenotype decoder — semantic-closure step.

These tests assert the *properties* that distinguish a heritable evolvable
code from the legacy external decoder ``gene_to_trait``: determinism,
code-dependence (meaning set by the heritable regulatory region), heritability,
emergent pleiotropy, and epistasis.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.core import prf_rng
from engine.genome import (
    GENOME_SIZE, GENE_GROUP_APPEARANCE, attach_genome, crossover, gene_to_trait,
)
from engine.genome_decoder import (
    PhenotypeConfig, decode_phenotype, decode_population,
    phenotype_signature, phenotype_distance, phenotype_diversity,
    code_sensitivity, regulatory_weights, structural_features, decoder_summary,
)
from engine.sim import Simulation, SimConfig

CFG = PhenotypeConfig()
SEED = 0xC0FFEE_117


def _rand_genome(seed, idx):
    return prf_rng(seed, ["test", "genome"], [int(idx)]).random(
        GENOME_SIZE, dtype=np.float32)


def test_decode_shape_and_range():
    p = decode_phenotype(_rand_genome(SEED, 0), CFG)
    assert p.shape == (CFG.k_traits,)
    assert np.all(p > 0.0) and np.all(p < 1.0)


def test_decode_is_deterministic():
    a = decode_phenotype(_rand_genome(SEED, 1), CFG)
    b = decode_phenotype(_rand_genome(SEED, 1), CFG)
    assert np.array_equal(a, b)
    s1 = phenotype_signature(_rand_genome(SEED, 1), CFG)
    s2 = phenotype_signature(_rand_genome(SEED, 1), CFG)
    assert s1 == s2 and len(s1) == 64


def test_bad_genome_shape_raises():
    import pytest
    with pytest.raises(ValueError):
        decode_phenotype(np.zeros(10, dtype=np.float32), CFG)


def test_phenotype_depends_on_heritable_code():
    """Same structural genes S, different regulatory code R ⇒ different
    phenotype — while the legacy gene_to_trait on a structural group is
    insensitive to R. This is the semantic-closure signature."""
    base = _rand_genome(SEED, 2)
    g = base.copy()
    g[CFG.reg_start:CFG.reg_end] = _rand_genome(SEED, 99)[CFG.reg_start:CFG.reg_end]
    assert phenotype_distance(decode_phenotype(base, CFG),
                              decode_phenotype(g, CFG)) > 1e-3
    # APPEARANCE ⊂ structural region → legacy decoder cannot see the R change.
    assert abs(gene_to_trait(base, GENE_GROUP_APPEARANCE)
               - gene_to_trait(g, GENE_GROUP_APPEARANCE)) < 1e-9
    assert code_sensitivity(base, SEED, trials=24, cfg=CFG) > 1e-2


def test_regulatory_code_is_inherited():
    pa, pb = _rand_genome(SEED, 10), _rand_genome(SEED, 11)
    child = crossover(pa, pb, prf_rng(SEED, ["test", "xover"], [0]))
    from_parent = np.logical_or(np.isclose(child, pa, atol=1e-6),
                                np.isclose(child, pb, atol=1e-6))
    # Whole genome: at most a few mutated loci (rate 1e-4 over 256).
    assert int((~from_parent).sum()) <= 5
    # The regulatory region specifically is inherited, not externally fixed.
    assert int((~from_parent[CFG.reg_start:CFG.reg_end]).sum()) <= 2


def test_heritability_children_resemble_midparent():
    pa, pb = _rand_genome(SEED, 10), _rand_genome(SEED, 11)
    mid = 0.5 * (decode_phenotype(pa, CFG) + decode_phenotype(pb, CFG))
    child_d, rand_d = [], []
    for i in range(40):
        c = crossover(pa, pb, prf_rng(SEED, ["test", "child"], [i]))
        child_d.append(phenotype_distance(decode_phenotype(c, CFG), mid))
        rand_d.append(phenotype_distance(
            decode_phenotype(_rand_genome(SEED, 1000 + i), CFG), mid))
    assert np.mean(child_d) < np.mean(rand_d)


def test_emergent_pleiotropy():
    g = _rand_genome(SEED, 20)
    p0 = decode_phenotype(g, CFG)
    chunk = (CFG.struct_end - CFG.struct_start) // CFG.n_features
    g2 = g.copy()
    g2[CFG.struct_start:CFG.struct_start + chunk] = np.clip(
        g2[CFG.struct_start:CFG.struct_start + chunk] + 0.3, 0.0, 1.0)
    moved = int((np.abs(decode_phenotype(g2, CFG) - p0) > 1e-5).sum())
    assert moved >= 2          # one structural chunk feeds many traits


def test_epistasis_effect_depends_on_background():
    base = _rand_genome(SEED, 30)
    gA = base.copy()
    gB = base.copy()
    gB[CFG.reg_start:CFG.reg_end] = _rand_genome(SEED, 31)[CFG.reg_start:CFG.reg_end]
    chunk = (CFG.struct_end - CFG.struct_start) // CFG.n_features
    dS = slice(CFG.struct_start, CFG.struct_start + chunk)
    gA2 = gA.copy(); gA2[dS] = np.clip(gA2[dS] + 0.25, 0.0, 1.0)
    gB2 = gB.copy(); gB2[dS] = np.clip(gB2[dS] + 0.25, 0.0, 1.0)
    dA = decode_phenotype(gA2, CFG) - decode_phenotype(gA, CFG)
    dB = decode_phenotype(gB2, CFG) - decode_phenotype(gB, CFG)
    assert phenotype_distance(dA, dB) > 1e-3


def test_regulatory_weights_shape_and_sign():
    w = regulatory_weights(_rand_genome(SEED, 5), CFG)
    assert w.shape == (CFG.k_traits, CFG.n_features)
    # Mapped to [-gain, +gain]; a random genome should span both signs.
    assert w.min() < 0.0 < w.max()


def test_structural_features_in_unit_range():
    f = structural_features(_rand_genome(SEED, 6), CFG)
    assert f.shape == (CFG.n_features,)
    assert np.all(f >= 0.0) and np.all(f <= 1.0)


def test_empty_population_is_safe():
    empty = np.zeros((0, GENOME_SIZE), dtype=np.float32)
    assert decode_population(empty, CFG).shape == (0, CFG.k_traits)
    assert phenotype_diversity(empty, CFG) == 0.0


def test_real_founder_genomes_reproducible():
    def founders(seed):
        sim = Simulation(SimConfig(
            name=f"oe_dec_{seed}", seed=seed & 0xFFFFFFFFFFFFFFFF,
            founders=8, max_agents=20, bounds_km=(0.5, 0.5),
            spawn_radius_m=50.0, drive_accel=1500.0, cultures=1))
        sim.step()
        attach_genome(sim.agents, int(sim.cfg.seed))
        n = sim.agents.n_active
        return phenotype_diversity(np.array(sim.agents.genome[:n], copy=True), CFG), n

    d1, n1 = founders(SEED)
    d2, n2 = founders(SEED)
    assert n1 >= 2 and d1 > 0.0
    assert abs(d1 - d2) < 1e-9


def test_decoder_summary_layout():
    s = decoder_summary(CFG)
    assert s["n_weights"] == CFG.k_traits * CFG.n_features
    assert s["n_weights"] == CFG.reg_end - CFG.reg_start
    assert s["philosophy"] == "HERITABLE_EVOLVABLE_CODE"
