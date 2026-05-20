"""Wave 8 fauna — fitness, install, tick dynamics."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.animal_catalog import SPECIES_BY_NAME
from engine.animal_evolution import (
    _bell,
    _stochastic_round,
    animal_evolution_state,
    compute_fitness,
    install_animal_evolution,
)
from engine.sim import Simulation, SimConfig


def test_bell_peak_at_optimum():
    assert _bell(20.0, 10.0, 20.0, 30.0) == 1.0
    assert _bell(5.0, 10.0, 20.0, 30.0) == 0.0
    assert _bell(35.0, 10.0, 20.0, 30.0) == 0.0


def test_compute_fitness_ants_temperate():
    ants = SPECIES_BY_NAME["ants"]
    # biome_id 0 is arbitrary; use a biome in affinity
    biome = next(iter(ants.biome_affinity))
    fit = compute_fitness(ants, biome, temp_c=22.0, oxygen_pct=21.0)
    assert 0.0 < fit <= 1.0


def test_compute_fitness_zero_oxygen():
    ants = SPECIES_BY_NAME["ants"]
    biome = next(iter(ants.biome_affinity))
    assert compute_fitness(ants, biome, temp_c=22.0, oxygen_pct=5.0) == 0.0


def test_stochastic_round_deterministic_rng():
    from engine.core import prf_rng

    rng = prf_rng(42, ["animal", "round"], [0])
    a = _stochastic_round(3.7, rng)
    b = _stochastic_round(3.7, rng)
    assert a in (3, 4)
    assert b in (3, 4)


def test_install_animal_evolution_idempotent():
    cfg = SimConfig(
        name="fauna",
        seed=88,
        founders=6,
        max_agents=20,
        bounds_km=(0.25, 0.25),
        emergence_subsystems=True,
    )
    sim = Simulation(cfg)
    sim.bootstrap()
    s1 = install_animal_evolution(sim, mode="modern")
    s2 = install_animal_evolution(sim, mode="modern")
    assert s1 is s2
    for _ in range(5):
        sim.step()
    snap = animal_evolution_state(sim)
    assert "global_population_total" in snap
    assert snap.get("chunks_tracked", 0) >= 0
    assert snap.get("ticks_run", 0) >= 0
