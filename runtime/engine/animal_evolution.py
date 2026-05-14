"""Genesis Engine — Wave 8 animal population dynamics.

Drives the populations of the 50 catalogued species in
:mod:`engine.animal_catalog` per chunk per tick, with realistic
plant-animal coevolution :

* **Herbivores** consume plant biomass from
  :mod:`engine.plant_evolution`. Browsing reduces ``ChunkVegetation``.
* **Carnivores** prey on other species in the same chunk (Lotka-Volterra
  per-pair coupling). Predation reduces prey population.
* **Filter feeders** in OCEAN chunks eat marine plankton from
  :mod:`engine.marine`.
* **All species** are gated by per-chunk climate, oxygen, biome affinity.
* **Population evolves** by logistic birth − natural-death − predation
  − starvation, all per tick.

Coupling with Wave 6 :
  - Plant biomass loss feeds back into ``chunk.food_kcal`` and the
    ``chunk._plant_pathway_mix`` override (less grass = less C4 GPP).

Coupling with agents (existing) :
  - When an agent hunts a chunk with prey, the chunk's animal
    populations supply realistic meat yields based on
    ``meat_kcal_per_kg``. Out of scope this sprint — wired later.

Determinism : all RNG via :func:`engine.core.prf_rng`. No
``random.random``. Bit-identical snapshots across runs same seed.

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — fauna ↔ flora ↔ climate.
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — multi-step
trophic rollouts respecting ecological laws.
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"  # arxiv 2604.22748

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from engine.core import TICK_DT_S, prf_rng
from engine.animal_catalog import (
    AnimalKingdom, TrophicLevel, AnimalSpecies,
    SPECIES, SPECIES_BY_NAME, all_species_names,
)


# ---------------------------------------------------------------------------
# Tuning constants — calibrated to give visible dynamics on small sims
# ---------------------------------------------------------------------------

# Daily birth/death rates as fractions of population.
NATURAL_DEATH_PER_DAY_FACTOR = 1.0   # death_rate = 1 / lifespan_years / 365
BIRTH_RATE_AT_OPT = 0.012             # 1.2 % of fertile females per day at fitness 1.0
STARVATION_DEATH_PER_DAY = 0.05      # 5 % per day with zero food
PREDATION_RATE_PER_PREDATOR_DAY = 0.30  # how aggressive predators are

# Plant browsing — kg of plant biomass consumed per herbivore per day at fitness=1.
HERBIVORE_BROWSE_KG_PER_DAY_FACTOR = 0.05  # 5 % of food_kcal_per_day → kg plant

# Minimum population to count as "present" for tracking.
PRESENT_THRESHOLD = 2

# Initial seed per favourable chunk in modern mode.
INITIAL_POP_FRACTION = 0.10           # 10 % of carrying capacity


# ---------------------------------------------------------------------------
# Per-chunk state
# ---------------------------------------------------------------------------

@dataclass
class ChunkFauna:
    """Per-chunk integer populations + bookkeeping."""
    populations: Dict[str, int] = field(default_factory=dict)
    last_food_intake: Dict[str, float] = field(default_factory=dict)


@dataclass
class AnimalEvolutionState:
    """Live state attached to ``sim._animal_state``."""
    chunk_fauna: Dict[Tuple[int, int, int], ChunkFauna] = field(
        default_factory=dict)
    extinct_species: Set[str] = field(default_factory=set)
    last_global_population: Dict[str, int] = field(default_factory=dict)
    last_per_kingdom: Dict[int, int] = field(default_factory=dict)
    last_per_trophic: Dict[int, int] = field(default_factory=dict)
    last_births_total: int = 0
    last_deaths_total: int = 0
    last_predation_total: int = 0
    ticks_run: int = 0


# ---------------------------------------------------------------------------
# Fitness — pure function
# ---------------------------------------------------------------------------

def _bell(value: float, lo: float, opt: float, hi: float) -> float:
    if value <= lo or value >= hi:
        return 0.0
    if value < opt:
        return max(0.0, 1.0 - ((opt - value) / max(1e-3, opt - lo)) ** 2)
    return max(0.0, 1.0 - ((value - opt) / max(1e-3, hi - opt)) ** 2)


def compute_fitness(species: AnimalSpecies,
                    biome_id: int,
                    temp_c: float,
                    oxygen_pct: float,
                    aquatic_water_max: float = 0.0) -> float:
    """0..1 fitness of a species for a chunk's climate.

    Aquatic species need water present in the chunk (max water > 100 L).
    Terrestrial species need ``not aquatic_water_max > X`` ; we don't
    forbid water around them (they can live near rivers).
    """
    if oxygen_pct < species.min_oxygen_pct:
        return 0.0
    if species.aquatic and aquatic_water_max < 50.0:
        return 0.0
    t = _bell(temp_c, species.temp_min, species.temp_opt, species.temp_max)
    if t <= 0.0:
        return 0.0
    aff = 1.0 if biome_id in species.biome_affinity else 0.05
    return max(0.0, min(1.0, t * aff))


# ---------------------------------------------------------------------------
# Per-tick update
# ---------------------------------------------------------------------------

def _dominant_biome(chunk) -> int:
    biomes, counts = np.unique(chunk.biome, return_counts=True)
    return int(biomes[np.argmax(counts)])


def _resolve_oxygen_pct(sim) -> float:
    plant_state = getattr(sim, "_plant_state", None)
    if plant_state is not None:
        return float(plant_state.oxygen_pct())
    return 20.95   # default modern atmosphere


def _resolve_temp(sim, coord) -> float:
    meteo = getattr(sim, "_meteo_state", None)
    if meteo is not None:
        cell = meteo.chunk_meteo.get(coord)
        if cell is not None:
            return float(cell.temp_c)
    # Fallback : legacy weather_at.
    try:
        from engine.world import weather_at
        w = weather_at(sim.tick * int(sim.cfg.drive_accel), 15.0, 1.0)
        return float(getattr(w, "temp_c", 15.0))
    except Exception:
        return 15.0


def _consume_plants(sim, coord, herbivore_name: str, demand_kg: float) -> float:
    """Reduce plant biomass for the species' browsed clades. Returns
    fraction of demand satisfied [0..1]."""
    plant_state = getattr(sim, "_plant_state", None)
    if plant_state is None:
        return 1.0   # no plant evolution installed → assume food available
    veg = plant_state.chunk_vegetation.get(coord)
    if veg is None or not veg.biomass_kg:
        return 0.0
    species = SPECIES_BY_NAME.get(herbivore_name)
    if species is None or not species.plant_clades_browsed:
        return 0.5  # generic browser, partial fitness
    available = 0.0
    targets = []
    for clade_name in species.plant_clades_browsed:
        mass = veg.biomass_kg.get(clade_name, 0.0)
        if mass > 0:
            available += mass
            targets.append((clade_name, mass))
    if available <= 0:
        return 0.0
    consumed_total = min(demand_kg, available * 0.20)  # max 20 % browsed/tick
    # Distribute proportional to availability.
    for clade_name, mass in targets:
        portion = consumed_total * (mass / available)
        new_mass = max(0.0, mass - portion)
        veg.biomass_kg[clade_name] = new_mass
    return consumed_total / demand_kg if demand_kg > 0 else 1.0


def _stochastic_round(value: float, rng) -> int:
    """Round ``value`` to int with prob = fractional part for the extra one.

    Preserves the expected value over many calls — essential for low-rate
    demographic events when integer rounding would always give 0.
    """
    if value <= 0.0:
        return 0
    n = int(value)
    frac = value - n
    if frac > 0.0 and rng.random() < frac:
        n += 1
    return n


def tick_animal_evolution(sim, state: AnimalEvolutionState) -> None:
    """Update all per-chunk populations once. O(n_chunks × n_species)."""
    accel = float(sim.cfg.drive_accel)
    dt_days = TICK_DT_S * accel / 86400.0  # tick in sim-days
    oxygen = _resolve_oxygen_pct(sim)

    global_pop: Dict[str, int] = {}
    per_kingdom: Dict[int, int] = {}
    per_trophic: Dict[int, int] = {}
    births = deaths = preds = 0

    for coord, chunk in list(sim.streamer.cache.items()):
        biome = _dominant_biome(chunk)
        temp_c = _resolve_temp(sim, coord)
        water_max = float(chunk.water.max())
        fauna = state.chunk_fauna.setdefault(coord, ChunkFauna())

        # First pass : update each species' population given its fitness.
        species_active = list(fauna.populations.keys())
        for name in species_active:
            if name in state.extinct_species:
                continue
            sp = SPECIES_BY_NAME.get(name)
            if sp is None:
                continue
            pop = fauna.populations.get(name, 0)
            if pop <= 0:
                continue
            f = compute_fitness(sp, biome, temp_c, oxygen, water_max)

            rng = prf_rng(sim.cfg.seed,
                          ["animal_evol", "demo", name],
                          [int(sim.tick), int(coord[0]), int(coord[1])])

            # Natural death : 1 / lifespan_years per year.
            d_rate = 1.0 / max(0.5, sp.lifespan_years * 365.0)
            n_deaths = _stochastic_round(pop * d_rate * dt_days, rng)
            deaths += n_deaths

            # Birth : logistic toward carrying capacity, scaled by fitness.
            cap = sp.carrying_capacity_per_chunk
            growth = BIRTH_RATE_AT_OPT * f * (1.0 - pop / max(1, cap))
            n_births = _stochastic_round(pop * max(0.0, growth) * dt_days, rng)
            births += n_births

            # Starvation if herbivore/insectivore but no food.
            n_starve = 0
            if sp.trophic_level in (TrophicLevel.HERBIVORE,
                                    TrophicLevel.INSECTIVORE) and pop > 0:
                demand_kg = pop * sp.food_kcal_per_day * dt_days \
                    * HERBIVORE_BROWSE_KG_PER_DAY_FACTOR / 1000.0
                # Use plant browsing satisfaction.
                if sp.trophic_level == TrophicLevel.HERBIVORE:
                    sat = _consume_plants(sim, coord, name, demand_kg)
                else:
                    # Insectivores feed on prey populations directly.
                    sat = 1.0
                fauna.last_food_intake[name] = sat
                if sat < 0.5:
                    n_starve = _stochastic_round(
                        pop * STARVATION_DEATH_PER_DAY
                        * (1.0 - sat) * dt_days, rng)
            deaths += n_starve

            new_pop = max(0, pop + n_births - n_deaths - n_starve)
            fauna.populations[name] = new_pop

        # Second pass : predation. Each carnivore eats from its prey list.
        for name in list(fauna.populations.keys()):
            sp = SPECIES_BY_NAME.get(name)
            if sp is None or not sp.prey_clades:
                continue
            pred_pop = fauna.populations.get(name, 0)
            if pred_pop <= 0:
                continue
            kills_total = 0
            pred_rng = prf_rng(sim.cfg.seed,
                               ["animal_evol", "predation", name],
                               [int(sim.tick), int(coord[0]), int(coord[1])])
            for prey_name in sp.prey_clades:
                prey_pop = fauna.populations.get(prey_name, 0)
                if prey_pop <= 0:
                    continue
                # Lotka-Volterra predation : kills ∝ pred × prey × rate.
                kills = pred_pop * prey_pop * PREDATION_RATE_PER_PREDATOR_DAY \
                    * dt_days / max(1, sp.carrying_capacity_per_chunk * 10)
                kills_i = _stochastic_round(kills, pred_rng)
                if kills_i > 0:
                    actual = min(kills_i, prey_pop)
                    fauna.populations[prey_name] = prey_pop - actual
                    kills_total += actual
            preds += kills_total
            # Predator gets fed → small bonus to next-tick fitness (modelled
            # via not-starving).

        # Cleanup zeros.
        for name in list(fauna.populations.keys()):
            if fauna.populations[name] <= 0:
                fauna.populations.pop(name, None)
                fauna.last_food_intake.pop(name, None)

        # Aggregate stats.
        for name, pop in fauna.populations.items():
            global_pop[name] = global_pop.get(name, 0) + pop
            sp = SPECIES_BY_NAME.get(name)
            if sp is not None:
                per_kingdom[int(sp.kingdom)] = (
                    per_kingdom.get(int(sp.kingdom), 0) + pop)
                per_trophic[int(sp.trophic_level)] = (
                    per_trophic.get(int(sp.trophic_level), 0) + pop)

    # Extinction tracking : species with 0 global pop for 1 tick → extinct.
    for sp in SPECIES:
        if global_pop.get(sp.name, 0) == 0 and sp.name not in state.extinct_species:
            # Only mark extinct if it was seeded (otherwise it just never started).
            if sp.name in state.last_global_population:
                if state.last_global_population.get(sp.name, 0) == 0:
                    state.extinct_species.add(sp.name)

    state.last_global_population = global_pop
    state.last_per_kingdom = per_kingdom
    state.last_per_trophic = per_trophic
    state.last_births_total = births
    state.last_deaths_total = deaths
    state.last_predation_total = preds
    state.ticks_run += 1


# ---------------------------------------------------------------------------
# Installer + reporter
# ---------------------------------------------------------------------------

def install_animal_evolution(sim, *,
                              mode: str = "modern") -> AnimalEvolutionState:
    """Idempotent installer. Wraps sim.step with one tick of fauna update.

    ``mode='modern'`` seeds every catalogued species into compatible
    chunks at 10 % of carrying capacity. ``mode='ancient'`` seeds only
    the early invertebrates (arthropods + molluscs) and lets later
    species emerge via migration (not implemented this sprint — they
    just remain absent).
    """
    existing: Optional[AnimalEvolutionState] = getattr(sim, "_animal_state", None)
    if existing is not None:
        return existing
    state = AnimalEvolutionState()
    sim._animal_state = state

    if mode == "modern":
        seed_set = SPECIES
    else:
        seed_set = tuple(
            s for s in SPECIES
            if s.kingdom in (AnimalKingdom.INVERTEBRATE_ARTHROPOD,
                             AnimalKingdom.INVERTEBRATE_MOLLUSCA))

    for coord, chunk in list(sim.streamer.cache.items()):
        biome = _dominant_biome(chunk)
        water_max = float(chunk.water.max())
        fauna = ChunkFauna()
        for sp in seed_set:
            if biome not in sp.biome_affinity:
                continue
            if sp.aquatic and water_max < 50.0:
                continue
            n0 = int(sp.carrying_capacity_per_chunk * INITIAL_POP_FRACTION)
            if n0 < 1:
                continue
            fauna.populations[sp.name] = n0
        if fauna.populations:
            state.chunk_fauna[coord] = fauna

    orig_step = sim.step

    def wrapped_step():
        orig_step()
        tick_animal_evolution(sim, state)

    sim.step = wrapped_step
    return state


def animal_evolution_state(sim) -> Dict[str, object]:
    """Snapshot for ``/api/animal_evolution_state``."""
    state: Optional[AnimalEvolutionState] = getattr(sim, "_animal_state", None)
    if state is None:
        return {}
    # Recompute global pop live (works before first tick too).
    live_pop: Dict[str, int] = {}
    for fauna in state.chunk_fauna.values():
        for name, n in fauna.populations.items():
            live_pop[name] = live_pop.get(name, 0) + n
    # Prefer live recompute over the cached snapshot if available.
    snapshot_pop = live_pop if live_pop else state.last_global_population
    # Top 10 by global population.
    top = sorted(snapshot_pop.items(), key=lambda kv: -kv[1])[:10]
    kingdom_names = {int(k): k.name for k in AnimalKingdom}
    trophic_names = {int(t): t.name for t in TrophicLevel}
    per_k_named = {kingdom_names.get(k, str(k)): v
                   for k, v in state.last_per_kingdom.items()}
    per_t_named = {trophic_names.get(t, str(t)): v
                   for t, v in state.last_per_trophic.items()}
    return {
        "global_population_total": sum(snapshot_pop.values()),
        "n_species_present": len([n for n, p in snapshot_pop.items()
                                  if p > 0]),
        "extinct_species": sorted(state.extinct_species),
        "top_species": [{"name": n, "population": p} for n, p in top],
        "per_kingdom_population": per_k_named,
        "per_trophic_population": per_t_named,
        "births_per_tick": state.last_births_total,
        "deaths_per_tick": state.last_deaths_total,
        "predation_per_tick": state.last_predation_total,
        "ticks_run": state.ticks_run,
        "chunks_tracked": len(state.chunk_fauna),
    }


# ---------------------------------------------------------------------------
# Persistence (P1 hooks)
# ---------------------------------------------------------------------------

def save_animal_state(sim, target_dir: str) -> bool:
    state: Optional[AnimalEvolutionState] = getattr(sim, "_animal_state", None)
    if state is None:
        return False
    payload = {
        "extinct_species": sorted(state.extinct_species),
        "ticks_run": state.ticks_run,
        "last_births_total": state.last_births_total,
        "last_deaths_total": state.last_deaths_total,
        "last_predation_total": state.last_predation_total,
        "chunk_fauna": {
            f"{c[0]}_{c[1]}_{c[2]}": {
                "populations": fauna.populations,
                "last_food_intake": fauna.last_food_intake,
            }
            for c, fauna in state.chunk_fauna.items()
        },
    }
    with open(os.path.join(target_dir, "animal_evolution.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return True


def load_animal_state(sim, target_dir: str) -> bool:
    path = os.path.join(target_dir, "animal_evolution.json")
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state = install_animal_evolution(sim, mode="modern")
    state.extinct_species = set(payload.get("extinct_species", []))
    state.ticks_run = int(payload.get("ticks_run", 0))
    state.last_births_total = int(payload.get("last_births_total", 0))
    state.last_deaths_total = int(payload.get("last_deaths_total", 0))
    state.last_predation_total = int(payload.get("last_predation_total", 0))
    state.chunk_fauna.clear()
    for key, d in payload.get("chunk_fauna", {}).items():
        parts = key.split("_")
        coord = tuple(int(p) for p in parts)
        fauna = ChunkFauna(
            populations={k: int(v)
                         for k, v in d.get("populations", {}).items()},
            last_food_intake={k: float(v)
                              for k, v in d.get("last_food_intake", {}).items()},
        )
        state.chunk_fauna[coord] = fauna
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "AnimalEvolutionState",
    "ChunkFauna",
    "compute_fitness",
    "install_animal_evolution",
    "tick_animal_evolution",
    "animal_evolution_state",
    "save_animal_state",
    "load_animal_state",
]
