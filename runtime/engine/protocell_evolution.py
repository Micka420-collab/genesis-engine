"""Protocellular life — self-replicating compartments before microbes.

Inspired by autopoietic / autocatalytic abiogenesis models (random chemistry
→ self-copying structures at the "edge of chaos"). Protocells accumulate
energy from prebiotic substrate, grow complexity, and divide when local
world viability supports it. No scripted spawn: only local rules.

Graduation to cyanobacteria happens via :mod:`engine.life_emergence` when
pools exceed thresholds and :mod:`engine.plant_evolution` is active.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.appraise import appraise_cell, prebiotic_potential
from engine.core import prf_rng


PROTOCELL_ENERGY_PER_SUBSTRATE = 0.15
DIVISION_ENERGY_THRESHOLD = 1.2
DIVISION_COMPLEXITY_MIN = 0.35
DEATH_RATE_PER_TICK = 0.004
MUTATION_SIGMA = 0.02
GRADUATION_COUNT = 80.0
GRADUATION_COMPLEXITY = 0.55


@dataclass
class ProtocellPool:
    """Autocatalytic compartment population in one chunk."""
    count: float = 0.0
    mean_complexity: float = 0.0
    energy: float = 0.0
    generations: int = 0


@dataclass
class ProtocellState:
    pools: Dict[Tuple[int, int, int], ProtocellPool] = field(default_factory=dict)
    total_divisions: int = 0
    total_deaths: float = 0.0
    graduations: int = 0


def tick_protocells(sim, substrate: Dict[Tuple[int, int, int], float],
                    state: ProtocellState) -> List[dict]:
    """Consume substrate, replicate protocells, return emergence events."""
    events: List[dict] = []
    accel = float(sim.cfg.drive_accel)

    for coord, chunk in list(sim.streamer.cache.items()):
        cx = float(coord[0] * 32 + 16)
        cy = float(coord[1] * 32 + 16)
        cell = appraise_cell(sim.streamer, cx, cy, sim.tick,
                             drive_accel=int(sim.cfg.drive_accel))
        viability = cell.viability
        if viability < 0.08:
            continue

        pool = state.pools.setdefault(coord, ProtocellPool())
        sub = float(substrate.get(coord, 0.0))
        if sub > 0.01:
            uptake = min(sub, sub * viability * 0.04 * accel * 1e-4)
            substrate[coord] = max(0.0, sub - uptake)
            pool.energy += uptake * PROTOCELL_ENERGY_PER_SUBSTRATE
            if pool.count < 1.0 and uptake > 0.001:
                pool.count = max(pool.count, uptake * 2.0)
                pool.mean_complexity = max(pool.mean_complexity, 0.05)

        if pool.count <= 0.0:
            continue

        # Metabolism: complexity rises with energy and habitability.
        pool.mean_complexity = float(np.clip(
            pool.mean_complexity
            + pool.energy * 0.01 * viability * cell.habitability,
            0.0, 1.0,
        ))
        pool.energy *= 0.995

        # Replication (binary fission) — stochastic tie-break for determinism.
        rng = prf_rng(sim.cfg.seed, ["protocell", "divide"],
                      [int(sim.tick), int(coord[0]), int(coord[1])])
        while (pool.count >= 1.0
               and pool.energy >= DIVISION_ENERGY_THRESHOLD
               and pool.mean_complexity >= DIVISION_COMPLEXITY_MIN):
            pool.count *= 0.5
            pool.energy *= 0.45
            mut = float(rng.normal(0.0, MUTATION_SIGMA))
            pool.mean_complexity = float(np.clip(pool.mean_complexity + mut, 0.0, 1.0))
            pool.generations += 1
            state.total_divisions += 1
            events.append({
                "kind": "protocell_division",
                "chunk": coord,
                "count": float(pool.count),
                "complexity": float(pool.mean_complexity),
            })

        # Mortality under harsh conditions.
        death_frac = DEATH_RATE_PER_TICK * (1.0 - viability) * accel * 1e-4
        if death_frac > 0:
            lost = pool.count * death_frac
            pool.count = max(0.0, pool.count - lost)
            state.total_deaths += lost

        state.pools[coord] = pool

    return events


def pool_ready_for_microbes(pool: ProtocellPool) -> bool:
    return (pool.count >= GRADUATION_COUNT
            and pool.mean_complexity >= GRADUATION_COMPLEXITY)


def graduate_to_cyanobacteria(sim, coord: Tuple[int, int, int],
                              pool: ProtocellPool) -> bool:
    """Transfer protocell pool into plant-evolution cyanobacteria biomass."""
    plant_state = getattr(sim, "_plant_state", None)
    if plant_state is None:
        return False
    if "cyanobacteria" not in plant_state.available_clades:
        plant_state.available_clades.add("cyanobacteria")

    from engine.plant_evolution import ChunkVegetation, SEED_BIOMASS_ANCIENT

    veg = plant_state.chunk_vegetation.setdefault(coord, ChunkVegetation())
    kg = float(np.clip(pool.count * 0.05 + SEED_BIOMASS_ANCIENT, 1.0, 500.0))
    veg.biomass_kg["cyanobacteria"] = veg.biomass_kg.get("cyanobacteria", 0.0) + kg
    veg.present_since_tick.setdefault("cyanobacteria", sim.tick)
    pool.count = 0.0
    pool.energy = 0.0
    return True


def protocell_snapshot(state: Optional[ProtocellState]) -> Dict[str, object]:
    if state is None:
        return {}
    counts = [p.count for p in state.pools.values() if p.count > 0]
    compl = [p.mean_complexity for p in state.pools.values() if p.count > 0]
    return {
        "active_chunks": len(counts),
        "total_protocells": float(sum(counts)) if counts else 0.0,
        "mean_complexity": float(np.mean(compl)) if compl else 0.0,
        "divisions": state.total_divisions,
        "graduations": state.graduations,
    }


__all__ = [
    "ProtocellPool",
    "ProtocellState",
    "tick_protocells",
    "pool_ready_for_microbes",
    "graduate_to_cyanobacteria",
    "protocell_snapshot",
]
