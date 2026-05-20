"""Algorithm evolution lab — generate, test, select, improve, repeat.

Evolves :class:`novel_operators.OperatorGenome` candidates on a Genesis
macro world using multi-metric fitness (coherence, diversity, balance).
Deterministic via ``prf_rng`` for mutations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.novel_operators import (
    OPERATOR_IDS,
    PARAM_SPECS,
    OperatorGenome,
    apply_operator,
    clamp_params,
    default_params,
    restore_world_arrays,
    snapshot_world_arrays,
)
from engine.world_genesis import GenesisParams, GenesisWorld, generate_world

PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


@dataclass
class EvolutionConfig:
    seed: int = 0xA1B0_BEEE
    generations: int = 10
    population_size: int = 20
    elite_count: int = 3
    tournament_k: int = 3
    mutation_rate: float = 0.35
    mutation_scale: float = 0.15
    genesis_resolution: int = 40
    world_seed: int = 0xFACE_CAFE


@dataclass
class EvolutionResult:
    best: OperatorGenome
    history_best_fitness: List[float] = field(default_factory=list)
    hall_of_fame: List[OperatorGenome] = field(default_factory=list)
    generations_run: int = 0


def _wind_coherence(wu: np.ndarray, wv: np.ndarray) -> float:
    spd = np.sqrt(wu * wu + wv * wv) + 1e-6
    ux, uy = wu / spd, wv / spd
    ux_m = _neighbor_mean_scalar(ux)
    uy_m = _neighbor_mean_scalar(uy)
    align = ux * ux_m + uy * uy_m
    return float(np.clip(np.mean(align), -1.0, 1.0))


def _neighbor_mean_scalar(arr: np.ndarray) -> np.ndarray:
    s = arr.copy()
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        sh = np.roll(arr, (dy, dx), axis=(0, 1))
        if dy == -1:
            sh[0, :] = arr[0, :]
        if dy == 1:
            sh[-1, :] = arr[-1, :]
        if dx == -1:
            sh[:, 0] = arr[:, 0]
        if dx == 1:
            sh[:, -1] = arr[:, -1]
        s += sh
    return s / 5.0


def _biome_entropy(biome: np.ndarray) -> float:
    land = biome[biome > 0]
    if land.size == 0:
        return 0.0
    counts = np.bincount(land.astype(np.int32), minlength=12)
    p = counts[counts > 0].astype(np.float64)
    p /= p.sum()
    ent = -np.sum(p * np.log2(p + 1e-12))
    return float(ent / np.log2(max(len(p), 2)))


def _orographic_score(elev: np.ndarray, precip: np.ndarray) -> float:
    land = elev > 10.0
    if not land.any():
        return 0.0
    grad = np.abs(np.gradient(elev)[0]) + np.abs(np.gradient(elev)[1])
    g = grad[land]
    pr = precip[land]
    if g.std() < 1e-6 or pr.std() < 1e-6:
        return 0.0
    corr = float(np.corrcoef(g, pr)[0, 1])
    return float(np.clip(corr, -1.0, 1.0))


def _energy_balance(temp_c: np.ndarray, precip: np.ndarray) -> float:
    """Prefer mid-range continental climates (not uniform / not chaotic)."""
    land = temp_c > -40.0
    if not land.any():
        return 0.0
    t = temp_c[land]
    p = precip[land]
    t_score = 1.0 - abs(float(np.mean(t)) - 12.0) / 35.0
    p_score = 1.0 - abs(float(np.mean(p)) - 900.0) / 2000.0
    return float(np.clip(0.5 * t_score + 0.5 * p_score, 0.0, 1.0))


def evaluate_genome(
    genome: OperatorGenome,
    world: GenesisWorld,
) -> Tuple[float, Dict[str, float]]:
    """Fitness after applying operator (higher = better). Restores world after."""
    snap = snapshot_world_arrays(world)
    activity = apply_operator(genome, world)
    metrics = {
        "wind_coherence": _wind_coherence(world.wind_u, world.wind_v),
        "biome_entropy": _biome_entropy(world.biome),
        "orographic": _orographic_score(world.elevation_m, world.precip_mm),
        "energy_balance": _energy_balance(world.temp_c, world.precip_mm),
        "activity": float(activity),
    }
    # Composite: reward coherence + diversity + orographic + balance
    # Penalize operators that barely change anything or explode fields
    delta_precip = float(np.mean(np.abs(world.precip_mm - snap["precip_mm"])))
    delta_temp = float(np.mean(np.abs(world.temp_c - snap["temp_c"])))
    change_score = float(np.clip((delta_precip / 50.0 + delta_temp / 3.0) / 2.0, 0.0, 1.0))
    fitness = (
        0.28 * metrics["wind_coherence"]
        + 0.22 * metrics["biome_entropy"]
        + 0.22 * metrics["orographic"]
        + 0.18 * metrics["energy_balance"]
        + 0.10 * change_score
    )
    if not np.isfinite(fitness):
        fitness = 0.0
    restore_world_arrays(world, snap)
    metrics["change_score"] = change_score
    metrics["fitness"] = fitness
    return fitness, metrics


def random_genome(seed: int, genome_id: int, operator_id: Optional[str] = None) -> OperatorGenome:
    rng = prf_rng(seed, ["algo_evo", "spawn"], [genome_id])
    op = operator_id or OPERATOR_IDS[int(rng.integers(0, len(OPERATOR_IDS)))]
    spec = PARAM_SPECS[op]
    params: Dict[str, float] = {}
    for name, (lo, hi, _) in spec.items():
        params[name] = float(lo + rng.random() * (hi - lo))
    return OperatorGenome(
        operator_id=op,
        params=clamp_params(op, params),
        generation=0,
        genome_id=genome_id,
    )


def mutate(genome: OperatorGenome, seed: int, generation: int) -> OperatorGenome:
    cfg = EvolutionConfig()
    rng = prf_rng(seed, ["algo_evo", "mutate"], [genome.genome_id, generation])
    child = genome.clone()
    child.generation = generation
    child.genome_id = int(rng.integers(0, 2**31))
    if rng.random() < 0.08:
        child.operator_id = OPERATOR_IDS[int(rng.integers(0, len(OPERATOR_IDS)))]
        child.params = default_params(child.operator_id)
    spec = PARAM_SPECS[child.operator_id]
    for name, (lo, hi, _) in spec.items():
        if rng.random() < cfg.mutation_rate:
            span = hi - lo
            delta = float(rng.normal(0.0, cfg.mutation_scale * span))
            child.params[name] = child.params.get(name, lo) + delta
    child.params = clamp_params(child.operator_id, child.params)
    return child


def crossover(a: OperatorGenome, b: OperatorGenome, seed: int, generation: int) -> OperatorGenome:
    rng = prf_rng(seed, ["algo_evo", "cross"], [a.genome_id, b.genome_id, generation])
    op = a.operator_id if rng.random() < 0.5 else b.operator_id
    if a.operator_id != b.operator_id:
        op = a.operator_id if rng.random() < 0.5 else b.operator_id
    spec = PARAM_SPECS[op]
    params: Dict[str, float] = {}
    for name in spec:
        src = a if (rng.random() < 0.5 and a.operator_id == op) else b
        if src.operator_id != op:
            src = a if a.operator_id == op else b
        params[name] = src.params.get(name, spec[name][2])
    return OperatorGenome(
        operator_id=op,
        params=clamp_params(op, params),
        generation=generation,
        genome_id=int(rng.integers(0, 2**31)),
    )


def tournament_select(scored: List[Tuple[float, OperatorGenome]], k: int, seed: int, gen: int) -> OperatorGenome:
    rng = prf_rng(seed, ["algo_evo", "tournament"], [gen, k])
    picks = [scored[int(rng.integers(0, len(scored)))][1] for _ in range(k)]
    return max(picks, key=lambda g: g.fitness)


def evolve_operators(cfg: Optional[EvolutionConfig] = None) -> EvolutionResult:
    """Full generate → test → select → improve loop."""
    cfg = cfg or EvolutionConfig()
    world = generate_world(GenesisParams(
        seed=int(cfg.world_seed) & 0xFFFFFFFFFFFFFFFF,
        resolution=cfg.genesis_resolution,
    ))
    pop: List[OperatorGenome] = [
        random_genome(cfg.seed, i) for i in range(cfg.population_size)
    ]
    history: List[float] = []
    hall: List[OperatorGenome] = []

    for gen in range(cfg.generations):
        scored: List[Tuple[float, OperatorGenome]] = []
        for g in pop:
            fit, _ = evaluate_genome(g, world)
            g.fitness = fit
            scored.append((fit, g))
        scored.sort(key=lambda x: -x[0])
        best_fit, best_g = scored[0]
        history.append(best_fit)
        hall.append(best_g.clone())
        next_pop = [g.clone() for _, g in scored[: cfg.elite_count]]
        gid = len(pop) + gen * cfg.population_size
        while len(next_pop) < cfg.population_size:
            p1 = tournament_select(scored, cfg.tournament_k, cfg.seed, gen * 1000 + gid)
            p2 = tournament_select(scored, cfg.tournament_k, cfg.seed, gen * 1000 + gid + 1)
            gid += 2
            if prf_rng(cfg.seed, ["cross"], [gid]).random() < 0.55:
                child = crossover(p1, p2, cfg.seed, gen + 1)
            else:
                child = p1.clone()
            child = mutate(child, cfg.seed, gen + 1)
            next_pop.append(child)
        pop = next_pop

    best = hall[-1] if hall else pop[0]
    return EvolutionResult(
        best=best,
        history_best_fitness=history,
        hall_of_fame=hall,
        generations_run=cfg.generations,
    )


def improve_until_plateau(
    cfg: Optional[EvolutionConfig] = None,
    *,
    max_rounds: int = 5,
    min_gain: float = 0.002,
) -> EvolutionResult:
    """Repeat evolution cycles until fitness gain stalls."""
    cfg = cfg or EvolutionConfig()
    best_result: Optional[EvolutionResult] = None
    prev = -1.0
    for rnd in range(max_rounds):
        sub = EvolutionConfig(
            seed=cfg.seed + rnd * 9973,
            generations=cfg.generations,
            population_size=cfg.population_size,
            elite_count=cfg.elite_count,
            genesis_resolution=cfg.genesis_resolution,
            world_seed=cfg.world_seed + rnd,
        )
        if best_result is not None:
            # Seed population with previous best mutated
            sub.population_size = cfg.population_size
        result = evolve_operators(sub)
        fit = result.history_best_fitness[-1] if result.history_best_fitness else 0.0
        if best_result is None or fit > best_result.best.fitness:
            best_result = result
        if fit - prev < min_gain and rnd > 0:
            break
        prev = fit
    assert best_result is not None
    return best_result


__all__ = [
    "EvolutionConfig",
    "EvolutionResult",
    "evaluate_genome",
    "evolve_operators",
    "improve_until_plateau",
    "mutate",
    "crossover",
    "random_genome",
]
