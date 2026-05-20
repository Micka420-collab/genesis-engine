"""Algorithm evolution lab + novel operators."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.algorithm_evolution import (
    EvolutionConfig,
    crossover,
    evolve_operators,
    mutate,
    random_genome,
)
from engine.novel_operators import OPERATOR_IDS, OperatorGenome, default_params
from engine.world_genesis import GenesisParams, generate_world


def test_random_genome_in_spec():
    for op in OPERATOR_IDS:
        g = random_genome(1, 0, op)
        assert g.operator_id == op
        for k in default_params(op):
            assert k in g.params


def test_evolve_improves_or_maintains():
    cfg = EvolutionConfig(seed=123, generations=5, population_size=10, genesis_resolution=24)
    r = evolve_operators(cfg)
    assert r.best.fitness >= 0.0
    assert len(r.history_best_fitness) == 5
    assert r.best.operator_id in OPERATOR_IDS


def test_crossover_mutate_deterministic():
    a = random_genome(7, 1, "mycorrhizal_mesh")
    b = random_genome(7, 2, "aurora_ionosphere")
    c = crossover(a, b, seed=7, generation=1)
    m = mutate(c, seed=7, generation=2)
    assert m.operator_id in OPERATOR_IDS


def test_evolve_reproducible():
    cfg = EvolutionConfig(seed=999, generations=4, population_size=8, genesis_resolution=20)
    r1 = evolve_operators(cfg)
    r2 = evolve_operators(cfg)
    assert r1.best.operator_id == r2.best.operator_id
    assert abs(r1.best.fitness - r2.best.fitness) < 1e-6
