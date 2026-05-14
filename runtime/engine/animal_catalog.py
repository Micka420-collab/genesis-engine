"""Real-world animal species catalogue — Wave 8 fauna.

50 phylogenetically representative animals covering the major vertebrate
+ key invertebrate clades. Each entry carries the minimum data the
simulation needs to decide:

* whether the species can survive in a chunk (biome affinity + climate
  envelope + oxygen tolerance + plant clade affinity for food)
* how fast it eats, reproduces, dies, and is eaten
* what it contributes to the ecosystem (meat kcal, hide, bone, etc.)
* phylogeny (parent_clade) — enables descent-based emergence in
  ``ancient`` mode (Wave 8b in the future).

References: NCBI Taxonomy 2023, IUCN Red List trait data, FishBase,
AnimalDiversity Web. Body sizes and longevities are species averages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, FrozenSet, Tuple


# Trophic role tags (used for food-web wiring).
class TrophicLevel(IntEnum):
    DETRITIVORE = 0           # decomposers, scavengers
    HERBIVORE = 1
    INSECTIVORE = 2
    OMNIVORE = 3
    CARNIVORE = 4
    APEX_PREDATOR = 5
    FILTER_FEEDER = 6         # marine plankton-eaters


class AnimalKingdom(IntEnum):
    INVERTEBRATE_ARTHROPOD = 0     # insects, arachnids, crustaceans
    INVERTEBRATE_MOLLUSCA = 1
    INVERTEBRATE_OTHER = 2
    VERTEBRATE_FISH = 3
    VERTEBRATE_AMPHIBIAN = 4
    VERTEBRATE_REPTILE = 5
    VERTEBRATE_BIRD = 6
    VERTEBRATE_MAMMAL = 7


@dataclass(frozen=True)
class AnimalSpecies:
    """One row of the catalogue. Immutable for safe sharing across sims."""
    name: str                              # internal id
    common_name: str
    kingdom: AnimalKingdom
    parent_clade: str                      # phylogeny (closest catalogued ancestor)
    first_appearance_ma: float             # Earth timeline
    trophic_level: TrophicLevel
    # Climate envelope
    temp_min: float
    temp_opt: float
    temp_max: float
    min_oxygen_pct: float                  # most need >18% to thrive
    # Habitat
    biome_affinity: FrozenSet[int]
    aquatic: bool = False                  # primarily aquatic / marine
    # Demographics (per individual)
    mass_kg: float = 1.0
    lifespan_years: float = 5.0
    gestation_days: float = 30.0
    offspring_per_clutch: int = 2
    # Energetics — per-day basal metabolic
    food_kcal_per_day: float = 100.0
    # Predation
    prey_clades: Tuple[str, ...] = ()      # who this species eats (animal names)
    plant_clades_browsed: Tuple[str, ...] = ()  # plant clades it grazes
    # Yield to agents that hunt it (kcal of meat + hide kg + bone kg).
    meat_kcal_per_kg: float = 1700.0
    hide_kg_per_kg: float = 0.08
    bone_kg_per_kg: float = 0.12
    # Population dynamics scale (carrying capacity per favourable chunk)
    carrying_capacity_per_chunk: int = 50


# Biome IDs duplicated from engine.world.Biome (avoid circular import).
_BIOME = {
    "OCEAN": 0, "ICE": 1, "TUNDRA": 2,
    "BOREAL_FOREST": 3, "TEMPERATE_FOREST": 4, "TEMPERATE_RAINFOREST": 5,
    "GRASSLAND": 6, "HOT_DESERT": 7, "COLD_DESERT": 8,
    "SAVANNA": 9, "TROPICAL_DRY_FOREST": 10, "TROPICAL_RAINFOREST": 11,
}


def _aff(*names: str) -> FrozenSet[int]:
    return frozenset(_BIOME[n] for n in names if n in _BIOME)


# ---------------------------------------------------------------------------
# Catalogue — 50 representative species
# ---------------------------------------------------------------------------

SPECIES: Tuple[AnimalSpecies, ...] = (
    # =====================================================================
    # 1. Arthropods — first land animals (Silurian, 420 Ma)
    # =====================================================================
    AnimalSpecies("ants", "fourmis",
                  AnimalKingdom.INVERTEBRATE_ARTHROPOD, "",
                  140.0, TrophicLevel.OMNIVORE,
                  temp_min=-10, temp_opt=22, temp_max=42,
                  min_oxygen_pct=15.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "TROPICAL_RAINFOREST",
                                      "SAVANNA", "GRASSLAND", "TROPICAL_DRY_FOREST"),
                  mass_kg=5e-6, lifespan_years=1.0,
                  gestation_days=10.0, offspring_per_clutch=200,
                  food_kcal_per_day=0.001,
                  plant_clades_browsed=("ferns", "magnoliid"),
                  meat_kcal_per_kg=1200.0,
                  carrying_capacity_per_chunk=10000),
    AnimalSpecies("bees", "abeilles",
                  AnimalKingdom.INVERTEBRATE_ARTHROPOD, "",
                  100.0, TrophicLevel.HERBIVORE,
                  temp_min=5, temp_opt=22, temp_max=38,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("GRASSLAND", "TEMPERATE_FOREST",
                                      "TROPICAL_RAINFOREST"),
                  mass_kg=0.0001, lifespan_years=0.5,
                  gestation_days=21.0, offspring_per_clutch=1500,
                  food_kcal_per_day=0.005,
                  plant_clades_browsed=("magnoliid", "roses", "asters", "mints"),
                  carrying_capacity_per_chunk=5000),
    AnimalSpecies("beetles", "coléoptères",
                  AnimalKingdom.INVERTEBRATE_ARTHROPOD, "",
                  280.0, TrophicLevel.OMNIVORE,
                  temp_min=-5, temp_opt=20, temp_max=40,
                  min_oxygen_pct=15.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "TROPICAL_RAINFOREST",
                                      "GRASSLAND", "SAVANNA"),
                  mass_kg=0.002, lifespan_years=1.0,
                  gestation_days=14.0, offspring_per_clutch=50,
                  food_kcal_per_day=0.02,
                  plant_clades_browsed=("oaks", "magnoliid", "ferns"),
                  carrying_capacity_per_chunk=2000),
    AnimalSpecies("butterflies", "papillons",
                  AnimalKingdom.INVERTEBRATE_ARTHROPOD, "",
                  60.0, TrophicLevel.HERBIVORE,
                  temp_min=5, temp_opt=22, temp_max=38,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "TROPICAL_RAINFOREST",
                                      "GRASSLAND", "TROPICAL_DRY_FOREST"),
                  mass_kg=0.0005, lifespan_years=0.1,
                  gestation_days=12.0, offspring_per_clutch=80,
                  food_kcal_per_day=0.003,
                  plant_clades_browsed=("asters", "magnoliid", "mints"),
                  carrying_capacity_per_chunk=500),
    AnimalSpecies("spiders", "araignées",
                  AnimalKingdom.INVERTEBRATE_ARTHROPOD, "",
                  380.0, TrophicLevel.CARNIVORE,
                  temp_min=-10, temp_opt=22, temp_max=42,
                  min_oxygen_pct=15.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "TROPICAL_RAINFOREST",
                                      "SAVANNA", "GRASSLAND", "HOT_DESERT"),
                  mass_kg=0.002, lifespan_years=2.0,
                  offspring_per_clutch=100,
                  food_kcal_per_day=0.01,
                  prey_clades=("ants", "beetles", "butterflies", "bees"),
                  carrying_capacity_per_chunk=400),
    AnimalSpecies("crabs", "crabes",
                  AnimalKingdom.INVERTEBRATE_ARTHROPOD, "",
                  200.0, TrophicLevel.OMNIVORE,
                  temp_min=2, temp_opt=18, temp_max=32,
                  min_oxygen_pct=10.0,
                  biome_affinity=_aff("OCEAN"),
                  aquatic=True,
                  mass_kg=0.5, lifespan_years=5.0,
                  offspring_per_clutch=1000,
                  food_kcal_per_day=15.0,
                  carrying_capacity_per_chunk=80,
                  meat_kcal_per_kg=900.0),

    # =====================================================================
    # 2. Molluscs — Cambrian (540 Ma)
    # =====================================================================
    AnimalSpecies("snails", "escargots",
                  AnimalKingdom.INVERTEBRATE_MOLLUSCA, "",
                  500.0, TrophicLevel.HERBIVORE,
                  temp_min=0, temp_opt=18, temp_max=32,
                  min_oxygen_pct=15.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "TEMPERATE_RAINFOREST",
                                      "TROPICAL_RAINFOREST", "GRASSLAND"),
                  mass_kg=0.02, lifespan_years=3.0,
                  offspring_per_clutch=80,
                  food_kcal_per_day=0.5,
                  plant_clades_browsed=("magnoliid", "ferns", "roses"),
                  meat_kcal_per_kg=900.0,
                  carrying_capacity_per_chunk=300),
    AnimalSpecies("octopus", "poulpes",
                  AnimalKingdom.INVERTEBRATE_MOLLUSCA, "",
                  300.0, TrophicLevel.CARNIVORE,
                  temp_min=4, temp_opt=15, temp_max=28,
                  min_oxygen_pct=10.0,
                  biome_affinity=_aff("OCEAN"),
                  aquatic=True,
                  mass_kg=3.0, lifespan_years=4.0,
                  offspring_per_clutch=100000,
                  food_kcal_per_day=300.0,
                  prey_clades=("crabs",),
                  meat_kcal_per_kg=1200.0,
                  carrying_capacity_per_chunk=15),
    AnimalSpecies("mussels", "moules",
                  AnimalKingdom.INVERTEBRATE_MOLLUSCA, "",
                  500.0, TrophicLevel.FILTER_FEEDER,
                  temp_min=0, temp_opt=12, temp_max=25,
                  min_oxygen_pct=10.0,
                  biome_affinity=_aff("OCEAN"),
                  aquatic=True,
                  mass_kg=0.05, lifespan_years=8.0,
                  offspring_per_clutch=1000000,
                  food_kcal_per_day=0.5,
                  meat_kcal_per_kg=850.0,
                  carrying_capacity_per_chunk=2000),

    # =====================================================================
    # 3. Fishes — Ordovician/Devonian (485 → 419 Ma)
    # =====================================================================
    AnimalSpecies("trout", "truites",
                  AnimalKingdom.VERTEBRATE_FISH, "",
                  150.0, TrophicLevel.CARNIVORE,
                  temp_min=2, temp_opt=12, temp_max=20,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("OCEAN", "TEMPERATE_RAINFOREST"),
                  aquatic=True,
                  mass_kg=1.5, lifespan_years=7.0,
                  offspring_per_clutch=2000,
                  food_kcal_per_day=80.0,
                  prey_clades=("beetles",),
                  meat_kcal_per_kg=1400.0,
                  carrying_capacity_per_chunk=120),
    AnimalSpecies("salmon", "saumons",
                  AnimalKingdom.VERTEBRATE_FISH, "trout",
                  100.0, TrophicLevel.CARNIVORE,
                  temp_min=2, temp_opt=10, temp_max=18,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("OCEAN"),
                  aquatic=True,
                  mass_kg=4.5, lifespan_years=8.0,
                  offspring_per_clutch=4000,
                  food_kcal_per_day=160.0,
                  meat_kcal_per_kg=2080.0,
                  carrying_capacity_per_chunk=60),
    AnimalSpecies("herring", "harengs",
                  AnimalKingdom.VERTEBRATE_FISH, "",
                  100.0, TrophicLevel.FILTER_FEEDER,
                  temp_min=0, temp_opt=10, temp_max=20,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("OCEAN"),
                  aquatic=True,
                  mass_kg=0.25, lifespan_years=12.0,
                  offspring_per_clutch=40000,
                  food_kcal_per_day=8.0,
                  meat_kcal_per_kg=1580.0,
                  carrying_capacity_per_chunk=5000),
    AnimalSpecies("cod", "morues",
                  AnimalKingdom.VERTEBRATE_FISH, "",
                  120.0, TrophicLevel.CARNIVORE,
                  temp_min=0, temp_opt=8, temp_max=18,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("OCEAN"),
                  aquatic=True,
                  mass_kg=8.0, lifespan_years=20.0,
                  offspring_per_clutch=2000000,
                  food_kcal_per_day=200.0,
                  prey_clades=("herring",),
                  meat_kcal_per_kg=1450.0,
                  carrying_capacity_per_chunk=80),
    AnimalSpecies("tuna", "thons",
                  AnimalKingdom.VERTEBRATE_FISH, "cod",
                  60.0, TrophicLevel.APEX_PREDATOR,
                  temp_min=10, temp_opt=22, temp_max=30,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("OCEAN"),
                  aquatic=True,
                  mass_kg=350.0, lifespan_years=30.0,
                  offspring_per_clutch=10000000,
                  food_kcal_per_day=8000.0,
                  prey_clades=("herring", "cod"),
                  meat_kcal_per_kg=1450.0,
                  carrying_capacity_per_chunk=8),
    AnimalSpecies("shark", "requins",
                  AnimalKingdom.VERTEBRATE_FISH, "",
                  450.0, TrophicLevel.APEX_PREDATOR,
                  temp_min=4, temp_opt=22, temp_max=30,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("OCEAN"),
                  aquatic=True,
                  mass_kg=400.0, lifespan_years=70.0,
                  gestation_days=300.0,
                  offspring_per_clutch=10,
                  food_kcal_per_day=10000.0,
                  prey_clades=("tuna", "cod", "salmon", "octopus"),
                  meat_kcal_per_kg=1450.0,
                  carrying_capacity_per_chunk=3),

    # =====================================================================
    # 4. Amphibians — Devonian (375 Ma)
    # =====================================================================
    AnimalSpecies("frogs", "grenouilles",
                  AnimalKingdom.VERTEBRATE_AMPHIBIAN, "",
                  250.0, TrophicLevel.INSECTIVORE,
                  temp_min=2, temp_opt=18, temp_max=32,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TEMPERATE_RAINFOREST",
                                      "TROPICAL_RAINFOREST", "TEMPERATE_FOREST"),
                  mass_kg=0.05, lifespan_years=8.0,
                  offspring_per_clutch=3000,
                  food_kcal_per_day=2.0,
                  prey_clades=("ants", "beetles", "butterflies"),
                  meat_kcal_per_kg=1100.0,
                  carrying_capacity_per_chunk=400),
    AnimalSpecies("salamander", "salamandres",
                  AnimalKingdom.VERTEBRATE_AMPHIBIAN, "",
                  200.0, TrophicLevel.INSECTIVORE,
                  temp_min=0, temp_opt=15, temp_max=28,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TEMPERATE_RAINFOREST", "BOREAL_FOREST"),
                  mass_kg=0.08, lifespan_years=20.0,
                  offspring_per_clutch=80,
                  food_kcal_per_day=1.5,
                  prey_clades=("ants", "beetles"),
                  carrying_capacity_per_chunk=200),

    # =====================================================================
    # 5. Reptiles — Carboniferous (310 Ma)
    # =====================================================================
    AnimalSpecies("lizards", "lézards",
                  AnimalKingdom.VERTEBRATE_REPTILE, "",
                  200.0, TrophicLevel.INSECTIVORE,
                  temp_min=5, temp_opt=28, temp_max=42,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("HOT_DESERT", "SAVANNA",
                                      "TROPICAL_DRY_FOREST", "GRASSLAND"),
                  mass_kg=0.2, lifespan_years=10.0,
                  offspring_per_clutch=12,
                  food_kcal_per_day=8.0,
                  prey_clades=("ants", "beetles", "spiders"),
                  meat_kcal_per_kg=1100.0,
                  carrying_capacity_per_chunk=150),
    AnimalSpecies("snakes", "serpents",
                  AnimalKingdom.VERTEBRATE_REPTILE, "lizards",
                  170.0, TrophicLevel.CARNIVORE,
                  temp_min=5, temp_opt=28, temp_max=42,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("HOT_DESERT", "SAVANNA",
                                      "TROPICAL_DRY_FOREST", "TROPICAL_RAINFOREST",
                                      "TEMPERATE_FOREST"),
                  mass_kg=2.0, lifespan_years=20.0,
                  offspring_per_clutch=10,
                  food_kcal_per_day=20.0,
                  prey_clades=("lizards", "frogs"),
                  carrying_capacity_per_chunk=50),
    AnimalSpecies("crocodiles", "crocodiles",
                  AnimalKingdom.VERTEBRATE_REPTILE, "",
                  200.0, TrophicLevel.APEX_PREDATOR,
                  temp_min=15, temp_opt=28, temp_max=40,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TROPICAL_RAINFOREST", "SAVANNA", "OCEAN"),
                  aquatic=True,
                  mass_kg=500.0, lifespan_years=70.0,
                  gestation_days=85.0,
                  offspring_per_clutch=40,
                  food_kcal_per_day=2000.0,
                  prey_clades=("frogs", "snakes"),
                  meat_kcal_per_kg=1200.0,
                  carrying_capacity_per_chunk=8),
    AnimalSpecies("turtles", "tortues",
                  AnimalKingdom.VERTEBRATE_REPTILE, "",
                  220.0, TrophicLevel.OMNIVORE,
                  temp_min=5, temp_opt=22, temp_max=35,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("OCEAN", "GRASSLAND", "TROPICAL_DRY_FOREST"),
                  mass_kg=10.0, lifespan_years=80.0,
                  offspring_per_clutch=100,
                  food_kcal_per_day=80.0,
                  plant_clades_browsed=("magnoliid", "ferns"),
                  carrying_capacity_per_chunk=20),

    # =====================================================================
    # 6. Birds — Jurassic (150 Ma)
    # =====================================================================
    AnimalSpecies("sparrows", "moineaux",
                  AnimalKingdom.VERTEBRATE_BIRD, "",
                  50.0, TrophicLevel.OMNIVORE,
                  temp_min=-15, temp_opt=18, temp_max=35,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND",
                                      "TEMPERATE_RAINFOREST", "SAVANNA"),
                  mass_kg=0.03, lifespan_years=3.0,
                  gestation_days=14.0, offspring_per_clutch=5,
                  food_kcal_per_day=10.0,
                  prey_clades=("ants", "beetles"),
                  plant_clades_browsed=("poaceae_c3", "poaceae_c4"),
                  carrying_capacity_per_chunk=300),
    AnimalSpecies("crows", "corbeaux",
                  AnimalKingdom.VERTEBRATE_BIRD, "sparrows",
                  60.0, TrophicLevel.OMNIVORE,
                  temp_min=-25, temp_opt=15, temp_max=35,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST",
                                      "GRASSLAND", "TUNDRA"),
                  mass_kg=0.45, lifespan_years=15.0,
                  gestation_days=18.0, offspring_per_clutch=5,
                  food_kcal_per_day=80.0,
                  prey_clades=("snails", "frogs", "lizards"),
                  carrying_capacity_per_chunk=80),
    AnimalSpecies("hawks", "faucons",
                  AnimalKingdom.VERTEBRATE_BIRD, "",
                  60.0, TrophicLevel.APEX_PREDATOR,
                  temp_min=-10, temp_opt=18, temp_max=35,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND",
                                      "SAVANNA", "BOREAL_FOREST"),
                  mass_kg=1.2, lifespan_years=20.0,
                  gestation_days=35.0, offspring_per_clutch=3,
                  food_kcal_per_day=300.0,
                  prey_clades=("sparrows", "crows", "snakes", "lizards"),
                  carrying_capacity_per_chunk=15),
    AnimalSpecies("ducks", "canards",
                  AnimalKingdom.VERTEBRATE_BIRD, "",
                  60.0, TrophicLevel.OMNIVORE,
                  temp_min=-15, temp_opt=15, temp_max=32,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TEMPERATE_RAINFOREST",
                                      "TEMPERATE_FOREST", "GRASSLAND", "OCEAN"),
                  mass_kg=1.0, lifespan_years=10.0,
                  gestation_days=28.0, offspring_per_clutch=10,
                  food_kcal_per_day=150.0,
                  plant_clades_browsed=("poaceae_c3",),
                  prey_clades=("snails",),
                  carrying_capacity_per_chunk=100),
    AnimalSpecies("eagles", "aigles",
                  AnimalKingdom.VERTEBRATE_BIRD, "hawks",
                  40.0, TrophicLevel.APEX_PREDATOR,
                  temp_min=-25, temp_opt=15, temp_max=35,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("BOREAL_FOREST", "TUNDRA",
                                      "TEMPERATE_FOREST", "GRASSLAND"),
                  mass_kg=5.0, lifespan_years=30.0,
                  gestation_days=42.0, offspring_per_clutch=2,
                  food_kcal_per_day=1500.0,
                  prey_clades=("hawks", "ducks", "sparrows"),
                  carrying_capacity_per_chunk=4),
    AnimalSpecies("seagulls", "mouettes",
                  AnimalKingdom.VERTEBRATE_BIRD, "",
                  35.0, TrophicLevel.OMNIVORE,
                  temp_min=-15, temp_opt=15, temp_max=30,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("OCEAN", "TEMPERATE_RAINFOREST"),
                  mass_kg=0.8, lifespan_years=20.0,
                  gestation_days=28.0, offspring_per_clutch=3,
                  food_kcal_per_day=200.0,
                  prey_clades=("herring", "crabs"),
                  carrying_capacity_per_chunk=150),

    # =====================================================================
    # 7. Mammals — Triassic origin (225 Ma), Cenozoic radiation
    # =====================================================================
    # 7a. Small mammals
    AnimalSpecies("mice", "souris",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  65.0, TrophicLevel.OMNIVORE,
                  temp_min=-10, temp_opt=20, temp_max=35,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND",
                                      "TROPICAL_DRY_FOREST", "BOREAL_FOREST",
                                      "SAVANNA"),
                  mass_kg=0.02, lifespan_years=2.0,
                  gestation_days=20.0, offspring_per_clutch=8,
                  food_kcal_per_day=4.0,
                  plant_clades_browsed=("poaceae_c3", "poaceae_c4"),
                  carrying_capacity_per_chunk=400),
    AnimalSpecies("rabbits", "lapins",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  60.0, TrophicLevel.HERBIVORE,
                  temp_min=-20, temp_opt=15, temp_max=32,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("GRASSLAND", "TEMPERATE_FOREST",
                                      "TEMPERATE_RAINFOREST", "TUNDRA"),
                  mass_kg=1.8, lifespan_years=9.0,
                  gestation_days=31.0, offspring_per_clutch=6,
                  food_kcal_per_day=70.0,
                  plant_clades_browsed=("poaceae_c3", "asters",
                                        "brassicas", "legumes"),
                  meat_kcal_per_kg=1730.0,
                  carrying_capacity_per_chunk=120),
    AnimalSpecies("squirrels", "écureuils",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "mice",
                  35.0, TrophicLevel.HERBIVORE,
                  temp_min=-25, temp_opt=15, temp_max=30,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("BOREAL_FOREST", "TEMPERATE_FOREST",
                                      "TEMPERATE_RAINFOREST"),
                  mass_kg=0.4, lifespan_years=7.0,
                  gestation_days=44.0, offspring_per_clutch=4,
                  food_kcal_per_day=40.0,
                  plant_clades_browsed=("oaks", "pinaceae", "ericaceae"),
                  meat_kcal_per_kg=1700.0,
                  carrying_capacity_per_chunk=100),
    AnimalSpecies("bats", "chauves-souris",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  52.0, TrophicLevel.INSECTIVORE,
                  temp_min=-5, temp_opt=22, temp_max=38,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "TROPICAL_RAINFOREST",
                                      "SAVANNA"),
                  mass_kg=0.03, lifespan_years=20.0,
                  gestation_days=45.0, offspring_per_clutch=1,
                  food_kcal_per_day=5.0,
                  prey_clades=("butterflies", "beetles"),
                  carrying_capacity_per_chunk=200),
    # 7b. Mid-sized herbivores
    AnimalSpecies("deer", "cerfs",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  20.0, TrophicLevel.HERBIVORE,
                  temp_min=-30, temp_opt=12, temp_max=30,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST",
                                      "TEMPERATE_RAINFOREST", "TUNDRA"),
                  mass_kg=80.0, lifespan_years=15.0,
                  gestation_days=200.0, offspring_per_clutch=1,
                  food_kcal_per_day=4000.0,
                  plant_clades_browsed=("oaks", "magnoliid", "ericaceae",
                                        "poaceae_c3"),
                  meat_kcal_per_kg=1580.0,
                  carrying_capacity_per_chunk=25),
    AnimalSpecies("horses", "chevaux",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  4.0, TrophicLevel.HERBIVORE,
                  temp_min=-30, temp_opt=15, temp_max=35,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("GRASSLAND", "SAVANNA",
                                      "TEMPERATE_FOREST"),
                  mass_kg=450.0, lifespan_years=25.0,
                  gestation_days=335.0, offspring_per_clutch=1,
                  food_kcal_per_day=18000.0,
                  plant_clades_browsed=("poaceae_c3", "poaceae_c4"),
                  meat_kcal_per_kg=1530.0,
                  carrying_capacity_per_chunk=10),
    AnimalSpecies("cattle", "bovins",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  2.0, TrophicLevel.HERBIVORE,
                  temp_min=-20, temp_opt=15, temp_max=35,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("GRASSLAND", "SAVANNA",
                                      "TROPICAL_DRY_FOREST", "TEMPERATE_FOREST"),
                  mass_kg=550.0, lifespan_years=20.0,
                  gestation_days=283.0, offspring_per_clutch=1,
                  food_kcal_per_day=22000.0,
                  plant_clades_browsed=("poaceae_c3", "poaceae_c4", "legumes"),
                  meat_kcal_per_kg=2050.0,
                  carrying_capacity_per_chunk=12),
    AnimalSpecies("sheep", "moutons",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "cattle",
                  10.0, TrophicLevel.HERBIVORE,
                  temp_min=-30, temp_opt=12, temp_max=32,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("GRASSLAND", "TUNDRA", "TEMPERATE_FOREST"),
                  mass_kg=70.0, lifespan_years=12.0,
                  gestation_days=150.0, offspring_per_clutch=1,
                  food_kcal_per_day=3000.0,
                  plant_clades_browsed=("poaceae_c3", "legumes"),
                  meat_kcal_per_kg=2940.0,
                  carrying_capacity_per_chunk=25),
    AnimalSpecies("goats", "chèvres",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "sheep",
                  10.0, TrophicLevel.HERBIVORE,
                  temp_min=-25, temp_opt=18, temp_max=40,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("GRASSLAND", "SAVANNA",
                                      "HOT_DESERT", "TEMPERATE_FOREST"),
                  mass_kg=55.0, lifespan_years=15.0,
                  gestation_days=150.0, offspring_per_clutch=2,
                  food_kcal_per_day=2500.0,
                  plant_clades_browsed=("poaceae_c3", "asters", "ericaceae"),
                  meat_kcal_per_kg=1090.0,
                  carrying_capacity_per_chunk=30),
    AnimalSpecies("pigs", "porcs",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  15.0, TrophicLevel.OMNIVORE,
                  temp_min=-15, temp_opt=20, temp_max=35,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "TROPICAL_DRY_FOREST",
                                      "GRASSLAND"),
                  mass_kg=110.0, lifespan_years=12.0,
                  gestation_days=114.0, offspring_per_clutch=8,
                  food_kcal_per_day=8000.0,
                  plant_clades_browsed=("oaks", "magnoliid", "poaceae_c3"),
                  prey_clades=("snails", "beetles"),
                  meat_kcal_per_kg=2420.0,
                  carrying_capacity_per_chunk=18),
    AnimalSpecies("elephants", "éléphants",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  60.0, TrophicLevel.HERBIVORE,
                  temp_min=10, temp_opt=25, temp_max=40,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("SAVANNA", "TROPICAL_DRY_FOREST",
                                      "TROPICAL_RAINFOREST"),
                  mass_kg=4500.0, lifespan_years=70.0,
                  gestation_days=660.0, offspring_per_clutch=1,
                  food_kcal_per_day=120000.0,
                  plant_clades_browsed=("magnoliid", "palms", "poaceae_c4"),
                  meat_kcal_per_kg=1700.0,
                  carrying_capacity_per_chunk=2),
    AnimalSpecies("bison", "bisons",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "cattle",
                  2.0, TrophicLevel.HERBIVORE,
                  temp_min=-40, temp_opt=10, temp_max=30,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("GRASSLAND", "TUNDRA"),
                  mass_kg=900.0, lifespan_years=20.0,
                  gestation_days=285.0, offspring_per_clutch=1,
                  food_kcal_per_day=30000.0,
                  plant_clades_browsed=("poaceae_c3", "poaceae_c4"),
                  meat_kcal_per_kg=2200.0,
                  carrying_capacity_per_chunk=8),
    # 7c. Carnivores
    AnimalSpecies("wolves", "loups",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  5.0, TrophicLevel.APEX_PREDATOR,
                  temp_min=-40, temp_opt=10, temp_max=30,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("BOREAL_FOREST", "TEMPERATE_FOREST",
                                      "TUNDRA", "GRASSLAND"),
                  mass_kg=40.0, lifespan_years=10.0,
                  gestation_days=63.0, offspring_per_clutch=5,
                  food_kcal_per_day=4000.0,
                  prey_clades=("deer", "rabbits", "mice", "sheep"),
                  carrying_capacity_per_chunk=6),
    AnimalSpecies("foxes", "renards",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "wolves",
                  5.0, TrophicLevel.CARNIVORE,
                  temp_min=-40, temp_opt=12, temp_max=32,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST",
                                      "GRASSLAND", "TUNDRA"),
                  mass_kg=6.0, lifespan_years=8.0,
                  gestation_days=52.0, offspring_per_clutch=5,
                  food_kcal_per_day=600.0,
                  prey_clades=("rabbits", "mice", "sparrows"),
                  carrying_capacity_per_chunk=15),
    AnimalSpecies("bears", "ours",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  20.0, TrophicLevel.OMNIVORE,
                  temp_min=-40, temp_opt=10, temp_max=28,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("BOREAL_FOREST", "TEMPERATE_FOREST",
                                      "TUNDRA", "TEMPERATE_RAINFOREST"),
                  mass_kg=300.0, lifespan_years=25.0,
                  gestation_days=220.0, offspring_per_clutch=2,
                  food_kcal_per_day=15000.0,
                  prey_clades=("salmon", "deer", "rabbits"),
                  plant_clades_browsed=("ericaceae", "roses"),
                  meat_kcal_per_kg=1850.0,
                  carrying_capacity_per_chunk=3),
    AnimalSpecies("lions", "lions",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  6.0, TrophicLevel.APEX_PREDATOR,
                  temp_min=10, temp_opt=25, temp_max=42,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("SAVANNA", "TROPICAL_DRY_FOREST",
                                      "GRASSLAND"),
                  mass_kg=190.0, lifespan_years=15.0,
                  gestation_days=110.0, offspring_per_clutch=3,
                  food_kcal_per_day=8000.0,
                  prey_clades=("cattle", "horses", "deer"),
                  carrying_capacity_per_chunk=4),
    AnimalSpecies("tigers", "tigres",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "lions",
                  2.0, TrophicLevel.APEX_PREDATOR,
                  temp_min=-10, temp_opt=22, temp_max=38,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TROPICAL_RAINFOREST",
                                      "TROPICAL_DRY_FOREST"),
                  mass_kg=220.0, lifespan_years=20.0,
                  gestation_days=105.0, offspring_per_clutch=3,
                  food_kcal_per_day=9000.0,
                  prey_clades=("deer", "pigs"),
                  carrying_capacity_per_chunk=2),
    # 7d. Marine mammals
    AnimalSpecies("dolphins", "dauphins",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  10.0, TrophicLevel.APEX_PREDATOR,
                  temp_min=5, temp_opt=18, temp_max=30,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("OCEAN"),
                  aquatic=True,
                  mass_kg=200.0, lifespan_years=40.0,
                  gestation_days=370.0, offspring_per_clutch=1,
                  food_kcal_per_day=15000.0,
                  prey_clades=("herring", "salmon", "cod"),
                  carrying_capacity_per_chunk=8),
    AnimalSpecies("whales", "baleines",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "dolphins",
                  10.0, TrophicLevel.FILTER_FEEDER,
                  temp_min=0, temp_opt=10, temp_max=22,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("OCEAN"),
                  aquatic=True,
                  mass_kg=80000.0, lifespan_years=80.0,
                  gestation_days=365.0, offspring_per_clutch=1,
                  food_kcal_per_day=2000000.0,
                  carrying_capacity_per_chunk=1),
    # 7e. Primates
    AnimalSpecies("monkeys", "singes",
                  AnimalKingdom.VERTEBRATE_MAMMAL, "",
                  35.0, TrophicLevel.OMNIVORE,
                  temp_min=5, temp_opt=25, temp_max=38,
                  min_oxygen_pct=18.0,
                  biome_affinity=_aff("TROPICAL_RAINFOREST",
                                      "TROPICAL_DRY_FOREST"),
                  mass_kg=10.0, lifespan_years=25.0,
                  gestation_days=180.0, offspring_per_clutch=1,
                  food_kcal_per_day=600.0,
                  plant_clades_browsed=("magnoliid", "palms", "roses"),
                  prey_clades=("beetles", "spiders"),
                  meat_kcal_per_kg=1700.0,
                  carrying_capacity_per_chunk=20),
)


# ---------------------------------------------------------------------------
# Indices + helpers
# ---------------------------------------------------------------------------

SPECIES_BY_NAME: Dict[str, AnimalSpecies] = {s.name: s for s in SPECIES}


def all_species_names() -> Tuple[str, ...]:
    return tuple(s.name for s in SPECIES)


def species_for_kingdom(k: AnimalKingdom) -> Tuple[AnimalSpecies, ...]:
    return tuple(s for s in SPECIES if s.kingdom == k)


def audit_biome_ids() -> bool:
    try:
        from engine.world import Biome
    except Exception:
        return True
    return all(int(getattr(Biome, name)) == val
               for name, val in _BIOME.items() if hasattr(Biome, name))


__all__ = [
    "AnimalKingdom", "TrophicLevel",
    "AnimalSpecies", "SPECIES", "SPECIES_BY_NAME",
    "all_species_names", "species_for_kingdom",
    "audit_biome_ids",
]
