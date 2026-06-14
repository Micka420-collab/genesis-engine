"""Real-world mineral + rock catalogue — Wave 10 geology.

35 representative materials covering Earth's crust : native elements,
oxide ores, sulfide ores, silicates, evaporites, organics. Each entry
carries the data the simulator needs to decide *where it occurs*, *how
hard it is to extract*, *what elements you get from it*, and *how
useful it is to a Wave 1/2 synthesis recipe*.

References
----------
- Mineralogy Database (mindat.org) — composition + hardness + density
- Earth's crust composition: Wedepohl 1995 / Rudnick & Gao 2003
- Ore deposit distribution: Pohl 2011 "Economic Geology"
- USGS Mineral Resources data, public domain

Layout
------
Each MineralKind enum value is an integer; the catalogue
``MINERALS`` is a tuple of Mineral dataclasses. Indexes are stable —
add new entries at the end so persistence doesn't break.

For each mineral we store the **element yield per kg of ore** so the
material_synthesis layer can use mining output directly. Example :
hematite → 0.70 kg Fe per kg ore (Fe2O3 = 70% Fe by mass).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, FrozenSet, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MineralCategory(IntEnum):
    NATIVE_ELEMENT = 0    # native gold, copper, sulfur, carbon
    OXIDE = 1             # hematite, magnetite, bauxite
    SULFIDE = 2           # chalcopyrite, galena, sphalerite
    HALIDE = 3            # halite, sylvite
    CARBONATE = 4         # calcite, dolomite
    SILICATE = 5          # quartz, feldspar
    ROCK_IGNEOUS = 6      # granite, basalt, obsidian
    ROCK_SEDIMENTARY = 7  # limestone, sandstone, shale
    ROCK_METAMORPHIC = 8  # marble, slate, gneiss
    ORGANIC = 9           # peat, coal, oil shale


# Biome IDs duplicated from engine.world.Biome.
_BIOME = {
    "OCEAN": 0, "ICE": 1, "TUNDRA": 2,
    "BOREAL_FOREST": 3, "TEMPERATE_FOREST": 4, "TEMPERATE_RAINFOREST": 5,
    "GRASSLAND": 6, "HOT_DESERT": 7, "COLD_DESERT": 8,
    "SAVANNA": 9, "TROPICAL_DRY_FOREST": 10, "TROPICAL_RAINFOREST": 11,
}


def _aff(*names: str) -> FrozenSet[int]:
    return frozenset(_BIOME[n] for n in names if n in _BIOME)


@dataclass(frozen=True)
class Mineral:
    """Physical + chemical + occurrence parameters for one mineral.

    Immutable so the catalogue is safe to share across sims.
    """
    name: str                                  # internal id
    common_name: str                           # human label
    category: MineralCategory
    formula: str                               # e.g. "Fe2O3"
    density_g_cm3: float
    mohs_hardness: float
    # Where it forms
    biome_affinity: FrozenSet[int]             # biomes where exposed
    min_depth_m: float                         # shallowest extractable depth
    max_depth_m: float                         # deepest extractable depth
    elevation_bias: float = 0.0                # +1 = mountains, -1 = lowlands
    rarity: float = 0.5                        # 0=common, 1=very rare
    # Per-kg ore extraction yield by element symbol (Wave 1 chemistry bridge).
    # E.g. hematite Fe2O3 → {"Fe": 0.70} (70 % Fe by mass).
    yields_per_kg_ore: Dict[str, float] = field(default_factory=dict)
    # Civilisation utility — what tier of agent technology unlocks it.
    # 0 = surface pickup (Stone Age), 1 = shallow dig (Neolithic),
    # 2 = mine shaft (Bronze Age), 3 = deep mine (Iron Age).
    tech_tier: int = 0


# ---------------------------------------------------------------------------
# The catalogue — 35 entries
# ---------------------------------------------------------------------------

MINERALS: Tuple[Mineral, ...] = (
    # ===========================================================
    # Native elements (Stone Age pickup — surface exposures)
    # ===========================================================
    Mineral("native_gold", "or natif",
            MineralCategory.NATIVE_ELEMENT, "Au",
            density_g_cm3=19.3, mohs_hardness=2.5,
            biome_affinity=_aff("OCEAN", "GRASSLAND",
                                "TEMPERATE_FOREST", "TROPICAL_RAINFOREST"),
            min_depth_m=0.0, max_depth_m=50.0,
            elevation_bias=0.3, rarity=0.95,
            yields_per_kg_ore={"Au": 1.0},
            tech_tier=0),
    Mineral("native_silver", "argent natif",
            MineralCategory.NATIVE_ELEMENT, "Ag",
            density_g_cm3=10.49, mohs_hardness=2.7,
            biome_affinity=_aff("GRASSLAND", "TEMPERATE_FOREST",
                                "BOREAL_FOREST"),
            min_depth_m=0.0, max_depth_m=80.0,
            elevation_bias=0.3, rarity=0.90,
            yields_per_kg_ore={"Ag": 1.0},
            tech_tier=1),
    Mineral("native_copper", "cuivre natif",
            MineralCategory.NATIVE_ELEMENT, "Cu",
            density_g_cm3=8.96, mohs_hardness=3.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST",
                                "GRASSLAND", "SAVANNA"),
            min_depth_m=0.0, max_depth_m=30.0,
            elevation_bias=0.2, rarity=0.75,
            yields_per_kg_ore={"Cu": 1.0},
            tech_tier=0),
    Mineral("native_sulfur", "soufre natif",
            MineralCategory.NATIVE_ELEMENT, "S",
            density_g_cm3=2.07, mohs_hardness=1.5,
            biome_affinity=_aff("HOT_DESERT", "TROPICAL_DRY_FOREST"),
            min_depth_m=0.0, max_depth_m=20.0,
            elevation_bias=0.5, rarity=0.60,
            yields_per_kg_ore={"S": 1.0},
            tech_tier=0),
    Mineral("graphite", "graphite",
            MineralCategory.NATIVE_ELEMENT, "C",
            density_g_cm3=2.23, mohs_hardness=1.5,
            biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST"),
            min_depth_m=2.0, max_depth_m=200.0,
            elevation_bias=0.4, rarity=0.70,
            yields_per_kg_ore={"C": 1.0},
            tech_tier=1),
    Mineral("diamond", "diamant",
            MineralCategory.NATIVE_ELEMENT, "C",
            density_g_cm3=3.52, mohs_hardness=10.0,
            biome_affinity=_aff("SAVANNA", "HOT_DESERT"),
            min_depth_m=10.0, max_depth_m=300.0,
            elevation_bias=0.0, rarity=0.99,
            yields_per_kg_ore={"C": 1.0},
            tech_tier=2),

    # ===========================================================
    # Oxide ores (Bronze + Iron Age workhorse)
    # ===========================================================
    Mineral("hematite", "hématite",
            MineralCategory.OXIDE, "Fe2O3",
            density_g_cm3=5.26, mohs_hardness=6.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND",
                                "SAVANNA", "TROPICAL_DRY_FOREST",
                                "HOT_DESERT"),
            min_depth_m=0.0, max_depth_m=200.0,
            elevation_bias=0.4, rarity=0.30,
            yields_per_kg_ore={"Fe": 0.70, "O": 0.30},
            tech_tier=1),
    Mineral("magnetite", "magnétite",
            MineralCategory.OXIDE, "Fe3O4",
            density_g_cm3=5.17, mohs_hardness=6.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST",
                                "GRASSLAND", "TUNDRA"),
            min_depth_m=2.0, max_depth_m=300.0,
            elevation_bias=0.6, rarity=0.40,
            yields_per_kg_ore={"Fe": 0.72, "O": 0.28},
            tech_tier=2),
    Mineral("bauxite", "bauxite",
            MineralCategory.OXIDE, "AlO(OH)",
            density_g_cm3=2.55, mohs_hardness=3.0,
            biome_affinity=_aff("TROPICAL_RAINFOREST", "TROPICAL_DRY_FOREST",
                                "SAVANNA"),
            min_depth_m=0.0, max_depth_m=50.0,
            elevation_bias=0.0, rarity=0.55,
            yields_per_kg_ore={"Al": 0.35, "O": 0.45, "H": 0.05},
            tech_tier=3),  # aluminium smelting late
    Mineral("cassiterite", "cassitérite",
            MineralCategory.OXIDE, "SnO2",
            density_g_cm3=6.99, mohs_hardness=6.5,
            biome_affinity=_aff("BOREAL_FOREST", "TEMPERATE_FOREST",
                                "GRASSLAND", "COLD_DESERT"),
            min_depth_m=0.0, max_depth_m=100.0,
            elevation_bias=0.7, rarity=0.85,
            yields_per_kg_ore={"Sn": 0.79, "O": 0.21},
            tech_tier=1),  # essential for bronze
    Mineral("rutile", "rutile",
            MineralCategory.OXIDE, "TiO2",
            density_g_cm3=4.23, mohs_hardness=6.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "OCEAN"),
            min_depth_m=0.0, max_depth_m=80.0,
            elevation_bias=0.2, rarity=0.70,
            yields_per_kg_ore={"Ti": 0.60, "O": 0.40},
            tech_tier=3),

    # ===========================================================
    # Sulfide ores
    # ===========================================================
    Mineral("chalcopyrite", "chalcopyrite",
            MineralCategory.SULFIDE, "CuFeS2",
            density_g_cm3=4.20, mohs_hardness=3.5,
            biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST",
                                "GRASSLAND"),
            min_depth_m=5.0, max_depth_m=400.0,
            elevation_bias=0.6, rarity=0.45,
            yields_per_kg_ore={"Cu": 0.35, "Fe": 0.30, "S": 0.35},
            tech_tier=2),
    Mineral("galena", "galène",
            MineralCategory.SULFIDE, "PbS",
            density_g_cm3=7.50, mohs_hardness=2.5,
            biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND",
                                "COLD_DESERT"),
            min_depth_m=2.0, max_depth_m=300.0,
            elevation_bias=0.5, rarity=0.55,
            yields_per_kg_ore={"Pb": 0.87, "S": 0.13},
            tech_tier=2),
    Mineral("sphalerite", "sphalérite",
            MineralCategory.SULFIDE, "ZnS",
            density_g_cm3=4.04, mohs_hardness=3.7,
            biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST"),
            min_depth_m=5.0, max_depth_m=350.0,
            elevation_bias=0.5, rarity=0.60,
            yields_per_kg_ore={"Zn": 0.67, "S": 0.33},
            tech_tier=2),
    Mineral("pyrite", "pyrite (or des fous)",
            MineralCategory.SULFIDE, "FeS2",
            density_g_cm3=5.01, mohs_hardness=6.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND",
                                "SAVANNA", "BOREAL_FOREST"),
            min_depth_m=0.0, max_depth_m=200.0,
            elevation_bias=0.3, rarity=0.20,
            yields_per_kg_ore={"Fe": 0.47, "S": 0.53},
            tech_tier=1),
    Mineral("cinnabar", "cinabre",
            MineralCategory.SULFIDE, "HgS",
            density_g_cm3=8.10, mohs_hardness=2.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "TROPICAL_DRY_FOREST"),
            min_depth_m=0.0, max_depth_m=100.0,
            elevation_bias=0.5, rarity=0.92,
            yields_per_kg_ore={"Hg": 0.86, "S": 0.14},
            tech_tier=2),

    # ===========================================================
    # Halides + salts (evaporites)
    # ===========================================================
    Mineral("halite", "sel gemme",
            MineralCategory.HALIDE, "NaCl",
            density_g_cm3=2.17, mohs_hardness=2.5,
            biome_affinity=_aff("HOT_DESERT", "COLD_DESERT",
                                "OCEAN"),
            min_depth_m=0.0, max_depth_m=2000.0,
            elevation_bias=-0.2, rarity=0.20,
            yields_per_kg_ore={"Na": 0.39, "Cl": 0.61},
            tech_tier=0),  # essential for food preservation
    Mineral("sylvite", "sylvite",
            MineralCategory.HALIDE, "KCl",
            density_g_cm3=1.99, mohs_hardness=2.0,
            biome_affinity=_aff("HOT_DESERT", "COLD_DESERT"),
            min_depth_m=10.0, max_depth_m=1000.0,
            elevation_bias=-0.2, rarity=0.70,
            yields_per_kg_ore={"K": 0.52, "Cl": 0.48},
            tech_tier=2),
    Mineral("gypsum", "gypse",
            MineralCategory.HALIDE, "CaSO4·2H2O",
            density_g_cm3=2.32, mohs_hardness=2.0,
            biome_affinity=_aff("HOT_DESERT", "COLD_DESERT",
                                "GRASSLAND"),
            min_depth_m=0.0, max_depth_m=200.0,
            elevation_bias=0.0, rarity=0.30,
            yields_per_kg_ore={"Ca": 0.23, "S": 0.19,
                                "O": 0.56, "H": 0.02},
            tech_tier=1),

    # ===========================================================
    # Carbonates
    # ===========================================================
    Mineral("calcite", "calcite",
            MineralCategory.CARBONATE, "CaCO3",
            density_g_cm3=2.71, mohs_hardness=3.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND",
                                "TROPICAL_RAINFOREST", "OCEAN"),
            min_depth_m=0.0, max_depth_m=500.0,
            elevation_bias=0.1, rarity=0.10,
            yields_per_kg_ore={"Ca": 0.40, "C": 0.12, "O": 0.48},
            tech_tier=0),
    Mineral("dolomite", "dolomie",
            MineralCategory.CARBONATE, "CaMg(CO3)2",
            density_g_cm3=2.85, mohs_hardness=3.7,
            biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND",
                                "COLD_DESERT"),
            min_depth_m=0.0, max_depth_m=400.0,
            elevation_bias=0.3, rarity=0.30,
            yields_per_kg_ore={"Ca": 0.22, "Mg": 0.13,
                                "C": 0.13, "O": 0.52},
            tech_tier=1),

    # ===========================================================
    # Silicates / quartz
    # ===========================================================
    Mineral("quartz", "quartz",
            MineralCategory.SILICATE, "SiO2",
            density_g_cm3=2.65, mohs_hardness=7.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST",
                                "GRASSLAND", "HOT_DESERT",
                                "COLD_DESERT", "OCEAN", "TUNDRA"),
            min_depth_m=0.0, max_depth_m=2000.0,
            elevation_bias=0.4, rarity=0.05,
            yields_per_kg_ore={"Si": 0.47, "O": 0.53},
            tech_tier=0),  # flint tools, glass
    Mineral("feldspar", "feldspath",
            MineralCategory.SILICATE, "KAlSi3O8",
            density_g_cm3=2.56, mohs_hardness=6.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST",
                                "GRASSLAND"),
            min_depth_m=0.0, max_depth_m=1000.0,
            elevation_bias=0.3, rarity=0.10,
            yields_per_kg_ore={"K": 0.14, "Al": 0.10,
                                "Si": 0.30, "O": 0.46},
            tech_tier=1),
    Mineral("mica_muscovite", "mica blanc",
            MineralCategory.SILICATE, "KAl3Si3O10(OH)2",
            density_g_cm3=2.82, mohs_hardness=2.5,
            biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST"),
            min_depth_m=0.0, max_depth_m=500.0,
            elevation_bias=0.5, rarity=0.40,
            yields_per_kg_ore={"K": 0.09, "Al": 0.18,
                                "Si": 0.23, "O": 0.47, "H": 0.005},
            tech_tier=1),

    # ===========================================================
    # Rocks — igneous
    # ===========================================================
    Mineral("granite", "granite",
            MineralCategory.ROCK_IGNEOUS, "(K,Na)AlSi3O8 / SiO2 mix",
            density_g_cm3=2.70, mohs_hardness=6.5,
            biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST",
                                "GRASSLAND", "TUNDRA", "COLD_DESERT"),
            min_depth_m=0.0, max_depth_m=10000.0,
            elevation_bias=0.6, rarity=0.05,
            yields_per_kg_ore={"Si": 0.35, "Al": 0.08,
                                "K": 0.05, "Na": 0.03,
                                "O": 0.46, "Ca": 0.02, "Fe": 0.01},
            tech_tier=0),
    Mineral("basalt", "basalte",
            MineralCategory.ROCK_IGNEOUS, "mafic",
            density_g_cm3=3.00, mohs_hardness=6.0,
            biome_affinity=_aff("OCEAN", "TUNDRA",
                                "HOT_DESERT", "GRASSLAND"),
            min_depth_m=0.0, max_depth_m=10000.0,
            elevation_bias=0.2, rarity=0.10,
            yields_per_kg_ore={"Si": 0.23, "Al": 0.08,
                                "Fe": 0.08, "Ca": 0.07,
                                "Mg": 0.05, "Na": 0.02,
                                "O": 0.46, "K": 0.01},
            tech_tier=0),
    Mineral("obsidian", "obsidienne",
            MineralCategory.ROCK_IGNEOUS, "volcanic_glass",
            density_g_cm3=2.40, mohs_hardness=5.5,
            biome_affinity=_aff("HOT_DESERT", "TUNDRA",
                                "TROPICAL_DRY_FOREST"),
            min_depth_m=0.0, max_depth_m=30.0,
            elevation_bias=0.8, rarity=0.70,
            yields_per_kg_ore={"Si": 0.32, "Al": 0.07,
                                "K": 0.04, "Na": 0.03,
                                "O": 0.46, "Fe": 0.01},
            tech_tier=0),  # sharpest stone-age blade

    # ===========================================================
    # Rocks — sedimentary
    # ===========================================================
    Mineral("limestone", "calcaire",
            MineralCategory.ROCK_SEDIMENTARY, "CaCO3 sedimentary",
            density_g_cm3=2.45, mohs_hardness=3.5,
            biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND",
                                "TROPICAL_RAINFOREST", "OCEAN",
                                "SAVANNA"),
            min_depth_m=0.0, max_depth_m=2000.0,
            elevation_bias=0.0, rarity=0.05,
            yields_per_kg_ore={"Ca": 0.38, "C": 0.12,
                                "O": 0.48, "Si": 0.02},
            tech_tier=0),  # building stone + cement source
    Mineral("sandstone", "grès",
            MineralCategory.ROCK_SEDIMENTARY, "SiO2 cemented",
            density_g_cm3=2.30, mohs_hardness=6.0,
            biome_affinity=_aff("HOT_DESERT", "COLD_DESERT",
                                "TEMPERATE_FOREST", "GRASSLAND"),
            min_depth_m=0.0, max_depth_m=3000.0,
            elevation_bias=0.0, rarity=0.10,
            yields_per_kg_ore={"Si": 0.43, "O": 0.50,
                                "Al": 0.03, "Fe": 0.02},
            tech_tier=0),
    Mineral("shale", "schiste argileux",
            MineralCategory.ROCK_SEDIMENTARY, "clay_consolidated",
            density_g_cm3=2.50, mohs_hardness=3.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND",
                                "BOREAL_FOREST", "OCEAN"),
            min_depth_m=0.0, max_depth_m=4000.0,
            elevation_bias=-0.2, rarity=0.15,
            yields_per_kg_ore={"Si": 0.25, "Al": 0.10,
                                "Fe": 0.04, "K": 0.03,
                                "O": 0.50, "Mg": 0.02},
            tech_tier=0),

    # ===========================================================
    # Rocks — metamorphic
    # ===========================================================
    Mineral("marble", "marbre",
            MineralCategory.ROCK_METAMORPHIC, "CaCO3 metamorphosed",
            density_g_cm3=2.65, mohs_hardness=3.5,
            biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND"),
            min_depth_m=10.0, max_depth_m=500.0,
            elevation_bias=0.4, rarity=0.50,
            yields_per_kg_ore={"Ca": 0.40, "C": 0.12, "O": 0.48},
            tech_tier=1),
    Mineral("slate", "ardoise",
            MineralCategory.ROCK_METAMORPHIC, "shale_metamorphosed",
            density_g_cm3=2.75, mohs_hardness=4.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST"),
            min_depth_m=2.0, max_depth_m=500.0,
            elevation_bias=0.4, rarity=0.35,
            yields_per_kg_ore={"Si": 0.27, "Al": 0.12,
                                "Fe": 0.05, "O": 0.50, "K": 0.04},
            tech_tier=1),
    Mineral("gneiss", "gneiss",
            MineralCategory.ROCK_METAMORPHIC, "granite_metamorphosed",
            density_g_cm3=2.80, mohs_hardness=7.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "TUNDRA",
                                "COLD_DESERT"),
            min_depth_m=5.0, max_depth_m=5000.0,
            elevation_bias=0.7, rarity=0.30,
            yields_per_kg_ore={"Si": 0.32, "Al": 0.09,
                                "Fe": 0.04, "K": 0.05,
                                "Na": 0.03, "O": 0.45,
                                "Ca": 0.01, "Mg": 0.01},
            tech_tier=1),

    # ===========================================================
    # Organics
    # ===========================================================
    Mineral("peat", "tourbe",
            MineralCategory.ORGANIC, "partially_decomposed",
            density_g_cm3=0.30, mohs_hardness=0.5,
            biome_affinity=_aff("TUNDRA", "BOREAL_FOREST",
                                "TEMPERATE_RAINFOREST"),
            min_depth_m=0.0, max_depth_m=15.0,
            elevation_bias=-0.3, rarity=0.20,
            yields_per_kg_ore={"C": 0.50, "H": 0.05,
                                "O": 0.35, "N": 0.02},
            tech_tier=0),  # fuel for cold climates
    Mineral("coal", "charbon",
            MineralCategory.ORGANIC, "C_with_volatiles",
            density_g_cm3=1.35, mohs_hardness=2.5,
            biome_affinity=_aff("TEMPERATE_FOREST", "BOREAL_FOREST",
                                "GRASSLAND"),
            min_depth_m=10.0, max_depth_m=2000.0,
            elevation_bias=0.0, rarity=0.40,
            yields_per_kg_ore={"C": 0.75, "H": 0.05,
                                "O": 0.15, "S": 0.02, "N": 0.01},
            tech_tier=2),  # iron-age coal mining
    Mineral("oil_shale", "schiste bitumineux",
            MineralCategory.ORGANIC, "kerogen_in_shale",
            density_g_cm3=2.10, mohs_hardness=3.0,
            biome_affinity=_aff("HOT_DESERT", "COLD_DESERT",
                                "GRASSLAND"),
            min_depth_m=20.0, max_depth_m=3000.0,
            elevation_bias=-0.2, rarity=0.65,
            yields_per_kg_ore={"C": 0.15, "H": 0.02,
                                "Si": 0.20, "Al": 0.07,
                                "O": 0.50, "Fe": 0.03},
            tech_tier=3),  # industrial-era resource

    # ===========================================================
    # Plastic clay (Neolithic pottery / brick) — appended last so
    # MINERAL_INDEX stays stable (Cap. C5 clay_outcrop, 2026-06-14).
    # Residual / secondary kaolinite: the plastic potter's clay that
    # closes the Rust ``Mineral::FineClay`` orphan (cross-language
    # contract). Forms by humid weathering of feldspathic / argillaceous
    # rock; shallow, low-elevation (floodplain / lacustrine) bias.
    # ===========================================================
    Mineral("fine_clay", "argile plastique (kaolin)",
            MineralCategory.SILICATE, "Al2Si2O5(OH)4",
            density_g_cm3=2.60, mohs_hardness=2.0,
            biome_affinity=_aff("TEMPERATE_FOREST", "GRASSLAND",
                                "SAVANNA", "TROPICAL_DRY_FOREST",
                                "TROPICAL_RAINFOREST", "BOREAL_FOREST"),
            min_depth_m=0.0, max_depth_m=12.0,
            elevation_bias=-0.2, rarity=0.55,
            yields_per_kg_ore={"Al": 0.21, "Si": 0.22,
                                "O": 0.49, "H": 0.015},
            tech_tier=0),  # pottery + brick + kiln → ceramics
)


# ---------------------------------------------------------------------------
# Indices + helpers
# ---------------------------------------------------------------------------

MINERAL_BY_NAME: Dict[str, Mineral] = {m.name: m for m in MINERALS}
MINERAL_INDEX: Dict[str, int] = {m.name: i for i, m in enumerate(MINERALS)}


def mineral_by_index(idx: int) -> Mineral:
    return MINERALS[idx]


def all_mineral_names() -> Tuple[str, ...]:
    return tuple(m.name for m in MINERALS)


def for_category(cat: MineralCategory) -> Tuple[Mineral, ...]:
    return tuple(m for m in MINERALS if m.category == cat)


def audit_biome_ids() -> bool:
    try:
        from engine.world import Biome
    except Exception:
        return True
    return all(int(getattr(Biome, name)) == val
               for name, val in _BIOME.items() if hasattr(Biome, name))


__all__ = [
    "MineralCategory",
    "Mineral",
    "MINERALS",
    "MINERAL_BY_NAME",
    "MINERAL_INDEX",
    "mineral_by_index",
    "all_mineral_names",
    "for_category",
    "audit_biome_ids",
]
