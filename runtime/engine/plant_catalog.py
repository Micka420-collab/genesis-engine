"""Real-world plant clade catalogue — Wave 6 evolutionary biology.

40 phylogenetically representative clades covering Earth's vegetation
history, from oxygenic cyanobacteria (3.5 Ga) to modern angiosperms
(~140 Ma + diversification ~100 Ma + C4 grasses ~30 Ma).

Each clade entry carries the **minimum data the simulation needs** to
decide *whether* the clade can grow here, *how fast*, and *what it
produces* for agents and the carbon cycle:

* phylogeny (``parent_clade``)
* first appearance time (``first_appearance_ma``) — when this clade
  could *first* emerge in Earth history. The simulator uses it as a
  gate when the user enables ``geological_replay`` mode ; in default
  ``modern`` mode all clades are seeded together and divergence is
  driven by environmental conditions, not deep time.
* photosynthetic pathway (C3 / C4 / CAM) — drives the
  :mod:`engine.photosynthesis` per-chunk Farquhar mix.
* climate envelope (``temp_min`` / ``temp_opt`` / ``temp_max``,
  ``water_min``, ``min_oxygen_pct``, ``max_co2_ppm``).
* biome affinity — which Genesis biomes welcome this clade strongly.
* trait : ``height_m``, ``edible_kcal_per_kg`` (>0 only if humans
  historically eat it), ``wood_yield_kg_per_kgbio``,
  ``growth_kg_per_day`` (under optimal conditions).

References: phylogeny per APG IV (2016) / Tree of Life (tolweb.org).
First-appearance ages per Knoll 2008 / Niklas 2016 / Magallón 2015.

This file is **pure data** with no behaviour. The module
:mod:`engine.plant_evolution` consumes it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, FrozenSet, Tuple

# Pathway tags reproduce the values in engine.photosynthesis.Pathway so
# we avoid the circular import. Keep in sync.
PATHWAY_C3 = 0
PATHWAY_C4 = 1
PATHWAY_CAM = 2


class CladeKingdom(IntEnum):
    """Top-level grouping for visualisation. Smaller than full phylogeny."""
    PROKARYOTE_AUTOTROPH = 0      # cyanobacteria
    ALGAE = 1                     # eukaryotic algae (green, red, brown, diatoms)
    BRYOPHYTE = 2                 # mosses, liverworts, hornworts
    PTERIDOPHYTE = 3              # ferns, horsetails, club mosses
    GYMNOSPERM = 4                # cycads, ginkgo, conifers, gnetales
    ANGIOSPERM_MONOCOT = 5        # grasses, palms, lilies, orchids
    ANGIOSPERM_DICOT = 6          # most flowering plants


@dataclass(frozen=True)
class PlantClade:
    """One row of the catalogue (immutable for safe sharing across sims)."""
    name: str
    common_name: str
    kingdom: CladeKingdom
    parent_clade: str             # "" for root (cyanobacteria)
    first_appearance_ma: float    # millions of years ago, Earth timeline
    pathway: int                  # PATHWAY_C3 / C4 / CAM
    # Climate envelope. ``temp_*`` in °C.
    temp_min: float
    temp_opt: float
    temp_max: float
    water_min: float              # chunk.water L/cell threshold below which it cannot survive
    min_oxygen_pct: float         # atmospheric O2 % required (0..100)
    max_co2_ppm: float            # CO2 above which the clade is stressed/dying
    # Biome affinities (set of biome ids, see engine.world.Biome).
    biome_affinity: FrozenSet[int] = frozenset()
    # Traits.
    height_m: float = 0.5
    edible_kcal_per_kg: float = 0.0   # 0 = inedible to humans
    wood_yield_kg_per_kgbio: float = 0.0
    growth_kg_per_day_opt: float = 0.01  # under optimal conditions


# ---------------------------------------------------------------------------
# Biome ids — duplicated from engine.world.Biome to avoid circular import.
# Keep in sync with world.Biome (we do, see audit_biome_ids() below).
# ---------------------------------------------------------------------------

_BIOME = {
    "OCEAN": 0, "ICE": 1, "TUNDRA": 2,
    "BOREAL_FOREST": 3, "TEMPERATE_FOREST": 4, "TEMPERATE_RAINFOREST": 5,
    "GRASSLAND": 6, "HOT_DESERT": 7, "COLD_DESERT": 8,
    "SAVANNA": 9, "TROPICAL_DRY_FOREST": 10, "TROPICAL_RAINFOREST": 11,
}


def _aff(*names: str) -> FrozenSet[int]:
    return frozenset(_BIOME[n] for n in names if n in _BIOME)


# ---------------------------------------------------------------------------
# The catalogue — 40 representative clades, Earth-real first appearances
# ---------------------------------------------------------------------------

CLADES: Tuple[PlantClade, ...] = (
    # ===================================================================
    # Group 1 : Prokaryote autotrophs (Archaean) — 3.5 → ∞ Ga
    # ===================================================================
    PlantClade(
        name="cyanobacteria",
        common_name="cyanobactéries",
        kingdom=CladeKingdom.PROKARYOTE_AUTOTROPH,
        parent_clade="",                                # root
        first_appearance_ma=3500.0,
        pathway=PATHWAY_C3,
        temp_min=-5, temp_opt=30, temp_max=70,
        water_min=1.0,
        min_oxygen_pct=0.0,                              # they MAKE oxygen
        max_co2_ppm=20000.0,
        biome_affinity=_aff("OCEAN", "TROPICAL_RAINFOREST"),
        height_m=0.0001,
        growth_kg_per_day_opt=0.002,
    ),

    # ===================================================================
    # Group 2 : Eukaryotic algae (Proterozoic) — 1500 → 700 Ma
    # ===================================================================
    PlantClade(
        name="green_algae",
        common_name="algues vertes",
        kingdom=CladeKingdom.ALGAE,
        parent_clade="cyanobacteria",
        first_appearance_ma=1400.0,
        pathway=PATHWAY_C3,
        temp_min=-2, temp_opt=20, temp_max=40,
        water_min=2.0,
        min_oxygen_pct=1.0,
        max_co2_ppm=10000.0,
        biome_affinity=_aff("OCEAN", "TEMPERATE_RAINFOREST", "TROPICAL_RAINFOREST"),
        height_m=0.001,
        growth_kg_per_day_opt=0.005,
    ),
    PlantClade(
        name="red_algae",
        common_name="algues rouges",
        kingdom=CladeKingdom.ALGAE,
        parent_clade="cyanobacteria",
        first_appearance_ma=1200.0,
        pathway=PATHWAY_C3,
        temp_min=0, temp_opt=18, temp_max=35,
        water_min=2.0, min_oxygen_pct=1.0, max_co2_ppm=8000.0,
        biome_affinity=_aff("OCEAN"),
        height_m=0.1,
        edible_kcal_per_kg=200.0,
        growth_kg_per_day_opt=0.004,
    ),
    PlantClade(
        name="brown_algae",
        common_name="algues brunes (varech)",
        kingdom=CladeKingdom.ALGAE,
        parent_clade="cyanobacteria",
        first_appearance_ma=700.0,
        pathway=PATHWAY_C3,
        temp_min=-1, temp_opt=12, temp_max=25,
        water_min=2.0, min_oxygen_pct=2.0, max_co2_ppm=5000.0,
        biome_affinity=_aff("OCEAN"),
        height_m=20.0,
        edible_kcal_per_kg=350.0,
        growth_kg_per_day_opt=0.20,
    ),
    PlantClade(
        name="diatoms",
        common_name="diatomées",
        kingdom=CladeKingdom.ALGAE,
        parent_clade="cyanobacteria",
        first_appearance_ma=250.0,
        pathway=PATHWAY_C3,
        temp_min=-2, temp_opt=15, temp_max=30,
        water_min=2.0, min_oxygen_pct=10.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("OCEAN"),
        height_m=0.00005,
        growth_kg_per_day_opt=0.002,
    ),

    # ===================================================================
    # Group 3 : Bryophytes (Ordovician land colonisation) — 470 Ma
    # ===================================================================
    PlantClade(
        name="liverworts",
        common_name="hépatiques",
        kingdom=CladeKingdom.BRYOPHYTE,
        parent_clade="green_algae",
        first_appearance_ma=470.0,
        pathway=PATHWAY_C3,
        temp_min=0, temp_opt=15, temp_max=30,
        water_min=5.0, min_oxygen_pct=5.0, max_co2_ppm=4000.0,
        biome_affinity=_aff("TEMPERATE_RAINFOREST", "TROPICAL_RAINFOREST",
                            "BOREAL_FOREST"),
        height_m=0.02,
        growth_kg_per_day_opt=0.002,
    ),
    PlantClade(
        name="hornworts",
        common_name="anthocérotes",
        kingdom=CladeKingdom.BRYOPHYTE,
        parent_clade="green_algae",
        first_appearance_ma=450.0,
        pathway=PATHWAY_C3,
        temp_min=0, temp_opt=15, temp_max=30,
        water_min=4.0, min_oxygen_pct=5.0, max_co2_ppm=4000.0,
        biome_affinity=_aff("TEMPERATE_RAINFOREST", "TROPICAL_RAINFOREST"),
        height_m=0.01,
        growth_kg_per_day_opt=0.001,
    ),
    PlantClade(
        name="sphagnum_moss",
        common_name="sphaigne",
        kingdom=CladeKingdom.BRYOPHYTE,
        parent_clade="liverworts",
        first_appearance_ma=300.0,
        pathway=PATHWAY_C3,
        temp_min=-10, temp_opt=10, temp_max=25,
        water_min=8.0, min_oxygen_pct=8.0, max_co2_ppm=3000.0,
        biome_affinity=_aff("TUNDRA", "BOREAL_FOREST", "TEMPERATE_RAINFOREST"),
        height_m=0.10,
        growth_kg_per_day_opt=0.003,
    ),
    PlantClade(
        name="true_moss",
        common_name="mousses (Bryum)",
        kingdom=CladeKingdom.BRYOPHYTE,
        parent_clade="liverworts",
        first_appearance_ma=400.0,
        pathway=PATHWAY_C3,
        temp_min=-15, temp_opt=15, temp_max=35,
        water_min=3.0, min_oxygen_pct=8.0, max_co2_ppm=3000.0,
        biome_affinity=_aff("TUNDRA", "BOREAL_FOREST", "TEMPERATE_FOREST",
                            "TEMPERATE_RAINFOREST", "GRASSLAND"),
        height_m=0.05,
        growth_kg_per_day_opt=0.003,
    ),

    # ===================================================================
    # Group 4 : Pteridophytes (Devonian vascular tissue) — 410 Ma
    # ===================================================================
    PlantClade(
        name="lycopodium",
        common_name="lycopodes",
        kingdom=CladeKingdom.PTERIDOPHYTE,
        parent_clade="true_moss",
        first_appearance_ma=410.0,
        pathway=PATHWAY_C3,
        temp_min=-5, temp_opt=15, temp_max=30,
        water_min=4.0, min_oxygen_pct=15.0, max_co2_ppm=2500.0,
        biome_affinity=_aff("BOREAL_FOREST", "TEMPERATE_FOREST",
                            "TEMPERATE_RAINFOREST"),
        height_m=0.30,
        growth_kg_per_day_opt=0.008,
    ),
    PlantClade(
        name="selaginella",
        common_name="sélaginelles",
        kingdom=CladeKingdom.PTERIDOPHYTE,
        parent_clade="lycopodium",
        first_appearance_ma=380.0,
        pathway=PATHWAY_C3,
        temp_min=0, temp_opt=20, temp_max=33,
        water_min=4.0, min_oxygen_pct=15.0, max_co2_ppm=2500.0,
        biome_affinity=_aff("TROPICAL_RAINFOREST", "TROPICAL_DRY_FOREST"),
        height_m=0.20,
        growth_kg_per_day_opt=0.005,
    ),
    PlantClade(
        name="equisetum",
        common_name="prêles",
        kingdom=CladeKingdom.PTERIDOPHYTE,
        parent_clade="true_moss",
        first_appearance_ma=370.0,
        pathway=PATHWAY_C3,
        temp_min=-10, temp_opt=15, temp_max=30,
        water_min=6.0, min_oxygen_pct=15.0, max_co2_ppm=2500.0,
        biome_affinity=_aff("BOREAL_FOREST", "TEMPERATE_FOREST",
                            "TEMPERATE_RAINFOREST", "GRASSLAND"),
        height_m=0.80,
        edible_kcal_per_kg=120.0,  # young shoots
        growth_kg_per_day_opt=0.015,
    ),
    PlantClade(
        name="ferns",
        common_name="fougères",
        kingdom=CladeKingdom.PTERIDOPHYTE,
        parent_clade="true_moss",
        first_appearance_ma=360.0,
        pathway=PATHWAY_C3,
        temp_min=-3, temp_opt=20, temp_max=33,
        water_min=5.0, min_oxygen_pct=15.0, max_co2_ppm=2500.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "TEMPERATE_RAINFOREST",
                            "TROPICAL_DRY_FOREST", "TROPICAL_RAINFOREST",
                            "BOREAL_FOREST"),
        height_m=1.5,
        edible_kcal_per_kg=140.0,  # fiddleheads
        growth_kg_per_day_opt=0.025,
    ),

    # ===================================================================
    # Group 5 : Gymnosperms (Carboniferous) — 360 Ma
    # ===================================================================
    PlantClade(
        name="cycads",
        common_name="cycadales",
        kingdom=CladeKingdom.GYMNOSPERM,
        parent_clade="ferns",
        first_appearance_ma=300.0,
        pathway=PATHWAY_C3,
        temp_min=5, temp_opt=25, temp_max=40,
        water_min=3.0, min_oxygen_pct=15.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("TROPICAL_DRY_FOREST", "TROPICAL_RAINFOREST",
                            "SAVANNA"),
        height_m=3.0,
        wood_yield_kg_per_kgbio=0.4,
        growth_kg_per_day_opt=0.05,
    ),
    PlantClade(
        name="ginkgo",
        common_name="ginkgo",
        kingdom=CladeKingdom.GYMNOSPERM,
        parent_clade="ferns",
        first_appearance_ma=270.0,
        pathway=PATHWAY_C3,
        temp_min=-25, temp_opt=18, temp_max=32,
        water_min=4.0, min_oxygen_pct=15.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "TEMPERATE_RAINFOREST",
                            "BOREAL_FOREST"),
        height_m=30.0,
        wood_yield_kg_per_kgbio=0.6,
        growth_kg_per_day_opt=0.06,
    ),
    PlantClade(
        name="pinaceae",
        common_name="pins, épicéas, sapins",
        kingdom=CladeKingdom.GYMNOSPERM,
        parent_clade="ferns",
        first_appearance_ma=200.0,
        pathway=PATHWAY_C3,
        temp_min=-50, temp_opt=15, temp_max=30,
        water_min=3.0, min_oxygen_pct=15.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("BOREAL_FOREST", "TEMPERATE_FOREST",
                            "TUNDRA", "COLD_DESERT"),
        height_m=40.0,
        wood_yield_kg_per_kgbio=0.65,
        growth_kg_per_day_opt=0.08,
    ),
    PlantClade(
        name="cupressaceae",
        common_name="cyprès, genévriers",
        kingdom=CladeKingdom.GYMNOSPERM,
        parent_clade="ferns",
        first_appearance_ma=200.0,
        pathway=PATHWAY_C3,
        temp_min=-30, temp_opt=18, temp_max=40,
        water_min=2.0, min_oxygen_pct=15.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "TEMPERATE_RAINFOREST",
                            "HOT_DESERT", "COLD_DESERT", "SAVANNA"),
        height_m=25.0,
        wood_yield_kg_per_kgbio=0.60,
        growth_kg_per_day_opt=0.06,
    ),
    PlantClade(
        name="podocarpaceae",
        common_name="podocarpes (hémisphère sud)",
        kingdom=CladeKingdom.GYMNOSPERM,
        parent_clade="ferns",
        first_appearance_ma=240.0,
        pathway=PATHWAY_C3,
        temp_min=-10, temp_opt=20, temp_max=32,
        water_min=4.0, min_oxygen_pct=15.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("TEMPERATE_RAINFOREST", "TROPICAL_RAINFOREST"),
        height_m=25.0,
        wood_yield_kg_per_kgbio=0.55,
        growth_kg_per_day_opt=0.05,
    ),
    PlantClade(
        name="gnetales",
        common_name="gnétales",
        kingdom=CladeKingdom.GYMNOSPERM,
        parent_clade="ferns",
        first_appearance_ma=145.0,
        pathway=PATHWAY_C3,
        temp_min=-5, temp_opt=25, temp_max=45,
        water_min=2.0, min_oxygen_pct=18.0, max_co2_ppm=1500.0,
        biome_affinity=_aff("HOT_DESERT", "SAVANNA"),
        height_m=2.0,
        growth_kg_per_day_opt=0.02,
    ),

    # ===================================================================
    # Group 6 : Angiosperms — Monocots (Cretaceous) — 140 Ma
    # ===================================================================
    PlantClade(
        name="magnoliid",
        common_name="magnolias, lauriers",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="ferns",
        first_appearance_ma=140.0,
        pathway=PATHWAY_C3,
        temp_min=-5, temp_opt=22, temp_max=35,
        water_min=4.0, min_oxygen_pct=18.0, max_co2_ppm=1500.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "TEMPERATE_RAINFOREST",
                            "TROPICAL_RAINFOREST", "TROPICAL_DRY_FOREST"),
        height_m=20.0,
        wood_yield_kg_per_kgbio=0.50,
        growth_kg_per_day_opt=0.07,
    ),
    PlantClade(
        name="poaceae_c3",
        common_name="graminées C3 (blé, orge, riz tempéré)",
        kingdom=CladeKingdom.ANGIOSPERM_MONOCOT,
        parent_clade="magnoliid",
        first_appearance_ma=80.0,
        pathway=PATHWAY_C3,
        temp_min=-10, temp_opt=18, temp_max=32,
        water_min=3.0, min_oxygen_pct=18.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("GRASSLAND", "TEMPERATE_FOREST", "TUNDRA",
                            "BOREAL_FOREST"),
        height_m=1.2,
        edible_kcal_per_kg=3300.0,  # cereal grain
        growth_kg_per_day_opt=0.04,
    ),
    PlantClade(
        name="poaceae_c4",
        common_name="graminées C4 (maïs, sorgho, canne)",
        kingdom=CladeKingdom.ANGIOSPERM_MONOCOT,
        parent_clade="poaceae_c3",
        first_appearance_ma=30.0,
        pathway=PATHWAY_C4,
        temp_min=5, temp_opt=30, temp_max=45,
        water_min=2.0, min_oxygen_pct=20.0, max_co2_ppm=600.0,  # C4 emerged under low CO2!
        biome_affinity=_aff("SAVANNA", "GRASSLAND", "TROPICAL_DRY_FOREST"),
        height_m=2.5,
        edible_kcal_per_kg=3500.0,
        growth_kg_per_day_opt=0.10,
    ),
    PlantClade(
        name="palms",
        common_name="palmiers",
        kingdom=CladeKingdom.ANGIOSPERM_MONOCOT,
        parent_clade="magnoliid",
        first_appearance_ma=85.0,
        pathway=PATHWAY_C3,
        temp_min=5, temp_opt=28, temp_max=42,
        water_min=4.0, min_oxygen_pct=18.0, max_co2_ppm=1500.0,
        biome_affinity=_aff("TROPICAL_RAINFOREST", "TROPICAL_DRY_FOREST",
                            "SAVANNA"),
        height_m=25.0,
        edible_kcal_per_kg=1500.0,  # dates / coconut
        wood_yield_kg_per_kgbio=0.30,
        growth_kg_per_day_opt=0.08,
    ),
    PlantClade(
        name="lilies",
        common_name="lis, tulipes",
        kingdom=CladeKingdom.ANGIOSPERM_MONOCOT,
        parent_clade="magnoliid",
        first_appearance_ma=120.0,
        pathway=PATHWAY_C3,
        temp_min=-15, temp_opt=20, temp_max=32,
        water_min=4.0, min_oxygen_pct=18.0, max_co2_ppm=1500.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND", "TEMPERATE_RAINFOREST"),
        height_m=0.5,
        edible_kcal_per_kg=900.0,  # some bulbs edible
        growth_kg_per_day_opt=0.01,
    ),
    PlantClade(
        name="orchids",
        common_name="orchidées",
        kingdom=CladeKingdom.ANGIOSPERM_MONOCOT,
        parent_clade="lilies",
        first_appearance_ma=80.0,
        pathway=PATHWAY_CAM,
        temp_min=0, temp_opt=22, temp_max=33,
        water_min=2.0, min_oxygen_pct=18.0, max_co2_ppm=1500.0,
        biome_affinity=_aff("TROPICAL_RAINFOREST", "TEMPERATE_RAINFOREST"),
        height_m=0.4,
        growth_kg_per_day_opt=0.005,
    ),

    # ===================================================================
    # Group 7 : Angiosperms — Dicots (Cretaceous-Paleogene radiation)
    # ===================================================================
    PlantClade(
        name="oaks",
        common_name="chênes, hêtres",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="magnoliid",
        first_appearance_ma=90.0,
        pathway=PATHWAY_C3,
        temp_min=-20, temp_opt=15, temp_max=32,
        water_min=4.0, min_oxygen_pct=18.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "TEMPERATE_RAINFOREST",
                            "BOREAL_FOREST"),
        height_m=30.0,
        edible_kcal_per_kg=1800.0,  # acorns
        wood_yield_kg_per_kgbio=0.60,
        growth_kg_per_day_opt=0.07,
    ),
    PlantClade(
        name="maples",
        common_name="érables",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="oaks",
        first_appearance_ma=60.0,
        pathway=PATHWAY_C3,
        temp_min=-30, temp_opt=15, temp_max=30,
        water_min=4.0, min_oxygen_pct=18.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST"),
        height_m=25.0,
        wood_yield_kg_per_kgbio=0.55,
        growth_kg_per_day_opt=0.06,
    ),
    PlantClade(
        name="legumes",
        common_name="légumineuses (haricots, pois)",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="magnoliid",
        first_appearance_ma=60.0,
        pathway=PATHWAY_C3,
        temp_min=0, temp_opt=22, temp_max=35,
        water_min=3.0, min_oxygen_pct=18.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("GRASSLAND", "TEMPERATE_FOREST", "SAVANNA",
                            "TROPICAL_DRY_FOREST"),
        height_m=0.8,
        edible_kcal_per_kg=3400.0,  # legumes high-protein
        growth_kg_per_day_opt=0.03,
    ),
    PlantClade(
        name="roses",
        common_name="rosacées (pommes, prunes, amandes)",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="magnoliid",
        first_appearance_ma=65.0,
        pathway=PATHWAY_C3,
        temp_min=-25, temp_opt=18, temp_max=32,
        water_min=4.0, min_oxygen_pct=18.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "TEMPERATE_RAINFOREST",
                            "BOREAL_FOREST", "GRASSLAND"),
        height_m=8.0,
        edible_kcal_per_kg=520.0,  # apples, almonds
        wood_yield_kg_per_kgbio=0.40,
        growth_kg_per_day_opt=0.04,
    ),
    PlantClade(
        name="asters",
        common_name="composées (tournesol, marguerite)",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="magnoliid",
        first_appearance_ma=50.0,
        pathway=PATHWAY_C3,
        temp_min=-15, temp_opt=20, temp_max=38,
        water_min=2.0, min_oxygen_pct=18.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("GRASSLAND", "TEMPERATE_FOREST", "SAVANNA",
                            "TUNDRA"),
        height_m=2.5,
        edible_kcal_per_kg=2600.0,  # sunflower seeds
        growth_kg_per_day_opt=0.03,
    ),
    PlantClade(
        name="mints",
        common_name="lamiacées (menthes, basilic)",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="asters",
        first_appearance_ma=40.0,
        pathway=PATHWAY_C3,
        temp_min=-5, temp_opt=20, temp_max=35,
        water_min=3.0, min_oxygen_pct=18.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND", "SAVANNA"),
        height_m=0.6,
        edible_kcal_per_kg=320.0,
        growth_kg_per_day_opt=0.02,
    ),
    PlantClade(
        name="brassicas",
        common_name="brassicacées (choux, navets)",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="magnoliid",
        first_appearance_ma=40.0,
        pathway=PATHWAY_C3,
        temp_min=-10, temp_opt=15, temp_max=30,
        water_min=4.0, min_oxygen_pct=18.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND", "BOREAL_FOREST"),
        height_m=1.0,
        edible_kcal_per_kg=300.0,
        growth_kg_per_day_opt=0.03,
    ),
    PlantClade(
        name="solanaceae",
        common_name="solanacées (tomate, pomme de terre)",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="mints",
        first_appearance_ma=35.0,
        pathway=PATHWAY_C3,
        temp_min=5, temp_opt=22, temp_max=33,
        water_min=4.0, min_oxygen_pct=18.0, max_co2_ppm=1800.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND", "TROPICAL_DRY_FOREST"),
        height_m=1.0,
        edible_kcal_per_kg=750.0,  # tubers + fruits
        growth_kg_per_day_opt=0.04,
    ),
    PlantClade(
        name="cacti",
        common_name="cactacées",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="magnoliid",
        first_appearance_ma=35.0,
        pathway=PATHWAY_CAM,
        temp_min=0, temp_opt=30, temp_max=50,
        water_min=0.5, min_oxygen_pct=18.0, max_co2_ppm=1500.0,
        biome_affinity=_aff("HOT_DESERT", "SAVANNA"),
        height_m=4.0,
        edible_kcal_per_kg=400.0,  # prickly pear fruit
        growth_kg_per_day_opt=0.01,
    ),
    PlantClade(
        name="crassulaceae",
        common_name="crassulacées (succulentes)",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="magnoliid",
        first_appearance_ma=70.0,
        pathway=PATHWAY_CAM,
        temp_min=-5, temp_opt=22, temp_max=40,
        water_min=1.0, min_oxygen_pct=18.0, max_co2_ppm=1500.0,
        biome_affinity=_aff("HOT_DESERT", "COLD_DESERT", "TEMPERATE_FOREST"),
        height_m=0.3,
        growth_kg_per_day_opt=0.005,
    ),
    PlantClade(
        name="ericaceae",
        common_name="éricacées (myrtille, bruyère)",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="magnoliid",
        first_appearance_ma=70.0,
        pathway=PATHWAY_C3,
        temp_min=-30, temp_opt=12, temp_max=28,
        water_min=4.0, min_oxygen_pct=18.0, max_co2_ppm=1800.0,
        biome_affinity=_aff("BOREAL_FOREST", "TUNDRA", "TEMPERATE_FOREST"),
        height_m=1.5,
        edible_kcal_per_kg=570.0,  # blueberries
        growth_kg_per_day_opt=0.02,
    ),
    PlantClade(
        name="ranunculaceae",
        common_name="renonculacées (boutons d'or)",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="magnoliid",
        first_appearance_ma=80.0,
        pathway=PATHWAY_C3,
        temp_min=-15, temp_opt=18, temp_max=30,
        water_min=4.0, min_oxygen_pct=18.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND", "TUNDRA"),
        height_m=0.5,
        growth_kg_per_day_opt=0.01,
    ),
    PlantClade(
        name="cucurbits",
        common_name="cucurbitacées (courges, melons)",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="magnoliid",
        first_appearance_ma=70.0,
        pathway=PATHWAY_C3,
        temp_min=5, temp_opt=25, temp_max=38,
        water_min=5.0, min_oxygen_pct=18.0, max_co2_ppm=1500.0,
        biome_affinity=_aff("GRASSLAND", "TROPICAL_DRY_FOREST", "TEMPERATE_FOREST"),
        height_m=0.5,
        edible_kcal_per_kg=300.0,
        growth_kg_per_day_opt=0.06,
    ),
    PlantClade(
        name="apiaceae",
        common_name="apiacées (carottes, persil)",
        kingdom=CladeKingdom.ANGIOSPERM_DICOT,
        parent_clade="magnoliid",
        first_appearance_ma=50.0,
        pathway=PATHWAY_C3,
        temp_min=-15, temp_opt=18, temp_max=30,
        water_min=4.0, min_oxygen_pct=18.0, max_co2_ppm=2000.0,
        biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND"),
        height_m=1.5,
        edible_kcal_per_kg=400.0,
        growth_kg_per_day_opt=0.02,
    ),
)


# ---------------------------------------------------------------------------
# Lookups / indices
# ---------------------------------------------------------------------------

CLADE_BY_NAME: Dict[str, PlantClade] = {c.name: c for c in CLADES}

# Phylogeny adjacency: parent → list of children (computed once).
_CHILDREN: Dict[str, Tuple[str, ...]] = {}
for _c in CLADES:
    _CHILDREN.setdefault(_c.parent_clade, ())
    _CHILDREN[_c.parent_clade] = _CHILDREN[_c.parent_clade] + (_c.name,)
del _c


def children_of(clade_name: str) -> Tuple[str, ...]:
    """Direct phylogenetic descendants of ``clade_name``."""
    return _CHILDREN.get(clade_name, ())


def ancestors_of(clade_name: str) -> Tuple[str, ...]:
    """Root-ward chain (including ``clade_name`` itself)."""
    out: list = []
    name = clade_name
    seen = set()
    while name and name not in seen:
        seen.add(name)
        c = CLADE_BY_NAME.get(name)
        out.append(name)
        if c is None:
            break
        name = c.parent_clade
    return tuple(out)


def all_clade_names() -> Tuple[str, ...]:
    return tuple(c.name for c in CLADES)


def audit_biome_ids() -> bool:
    """Soft check that the local ``_BIOME`` table agrees with
    :class:`engine.world.Biome`. Returns ``True`` when in sync."""
    try:
        from engine.world import Biome
    except Exception:
        return True
    return all(int(getattr(Biome, name)) == val
               for name, val in _BIOME.items() if hasattr(Biome, name))


__all__ = [
    "CladeKingdom",
    "PlantClade",
    "CLADES",
    "CLADE_BY_NAME",
    "PATHWAY_C3", "PATHWAY_C4", "PATHWAY_CAM",
    "children_of",
    "ancestors_of",
    "all_clade_names",
    "audit_biome_ids",
]
