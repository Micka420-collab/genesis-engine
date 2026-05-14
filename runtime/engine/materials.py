"""Real-world material properties for the Genesis Engine.

Each material has physically meaningful properties (density, Mohs hardness,
melting point in Kelvin, calorific value, etc.) so that construction
recipes, tool durability, and metallurgy thresholds are anchored in real
science rather than arbitrary numbers.

Values are sourced from public physics/chemistry references (CRC Handbook,
Materials Project) — see PHASE5-RESEARCH-DOSSIER.md for citations.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, Optional


class MaterialKind(IntEnum):
    WOOD = 0      # generic seasoned hardwood
    STONE = 1     # generic limestone / sandstone
    FLINT = 2     # knappable for tools
    CLAY = 3      # fire-able to ceramic
    FIBER = 4     # plant fiber (cordage, basketry)
    LEATHER = 5   # tanned animal hide
    BONE = 6      # for tools, awls, needles
    COPPER = 7    # native copper or smelted
    TIN = 8       # for bronze alloying
    BRONZE = 9    # Cu + Sn alloy
    IRON = 10     # smelted iron (bloomery output)
    CERAMIC = 11  # fired clay
    CHARCOAL = 12 # fire fuel + bronze/iron smelting reductant
    GRAIN = 13    # cereal seeds (storable food)


@dataclass(frozen=True)
class Material:
    """Physical properties of a material at room conditions.

    All fields are in SI units unless noted.
    """
    kind: MaterialKind
    name: str
    density_kg_m3: float          # density at 20°C
    hardness_mohs: float          # 0-10
    melting_point_k: Optional[float]   # K, None = decomposes before melting
    combustible: bool             # burns with O2
    calorific_mj_kg: float        # heat content if combustible
    workability: float            # 0-1, ease of shaping with stone tools
    tool_score: float             # 0-1, makes a useful cutting/striking edge
    stack_kg: float               # convenient inventory stack size


# Reference table — values from CRC Handbook + Tylecote (metallurgy)
MATERIALS: Dict[MaterialKind, Material] = {
    MaterialKind.WOOD: Material(
        kind=MaterialKind.WOOD, name="wood",
        density_kg_m3=700.0, hardness_mohs=2.5,
        melting_point_k=None, combustible=True, calorific_mj_kg=15.0,
        workability=0.85, tool_score=0.3, stack_kg=2.0),
    MaterialKind.STONE: Material(
        kind=MaterialKind.STONE, name="stone",
        density_kg_m3=2700.0, hardness_mohs=6.0,
        melting_point_k=1450.0 + 273.15, combustible=False, calorific_mj_kg=0.0,
        workability=0.20, tool_score=0.5, stack_kg=5.0),
    MaterialKind.FLINT: Material(
        kind=MaterialKind.FLINT, name="flint",
        density_kg_m3=2600.0, hardness_mohs=7.0,
        melting_point_k=1986.0, combustible=False, calorific_mj_kg=0.0,
        workability=0.45, tool_score=0.95, stack_kg=2.0),
    MaterialKind.CLAY: Material(
        kind=MaterialKind.CLAY, name="clay",
        density_kg_m3=2000.0, hardness_mohs=1.5,
        melting_point_k=1700.0, combustible=False, calorific_mj_kg=0.0,
        workability=0.95, tool_score=0.0, stack_kg=3.0),
    MaterialKind.FIBER: Material(
        kind=MaterialKind.FIBER, name="fiber",
        density_kg_m3=400.0, hardness_mohs=0.5,
        melting_point_k=None, combustible=True, calorific_mj_kg=16.5,
        workability=0.95, tool_score=0.0, stack_kg=0.5),
    MaterialKind.LEATHER: Material(
        kind=MaterialKind.LEATHER, name="leather",
        density_kg_m3=900.0, hardness_mohs=1.0,
        melting_point_k=None, combustible=True, calorific_mj_kg=18.0,
        workability=0.80, tool_score=0.0, stack_kg=1.0),
    MaterialKind.BONE: Material(
        kind=MaterialKind.BONE, name="bone",
        density_kg_m3=1900.0, hardness_mohs=3.5,
        melting_point_k=None, combustible=True, calorific_mj_kg=4.0,
        workability=0.55, tool_score=0.65, stack_kg=1.0),
    MaterialKind.COPPER: Material(
        kind=MaterialKind.COPPER, name="copper",
        density_kg_m3=8960.0, hardness_mohs=3.0,
        melting_point_k=1085.0 + 273.15, combustible=False, calorific_mj_kg=0.0,
        workability=0.80, tool_score=0.7, stack_kg=3.0),
    MaterialKind.TIN: Material(
        kind=MaterialKind.TIN, name="tin",
        density_kg_m3=7310.0, hardness_mohs=1.5,
        melting_point_k=232.0 + 273.15, combustible=False, calorific_mj_kg=0.0,
        workability=0.95, tool_score=0.2, stack_kg=3.0),
    MaterialKind.BRONZE: Material(
        kind=MaterialKind.BRONZE, name="bronze",
        density_kg_m3=8800.0, hardness_mohs=3.5,
        melting_point_k=950.0 + 273.15, combustible=False, calorific_mj_kg=0.0,
        workability=0.70, tool_score=0.85, stack_kg=3.0),
    MaterialKind.IRON: Material(
        kind=MaterialKind.IRON, name="iron",
        density_kg_m3=7870.0, hardness_mohs=4.0,
        melting_point_k=1538.0 + 273.15, combustible=False, calorific_mj_kg=0.0,
        workability=0.55, tool_score=0.95, stack_kg=3.0),
    MaterialKind.CERAMIC: Material(
        kind=MaterialKind.CERAMIC, name="ceramic",
        density_kg_m3=2300.0, hardness_mohs=5.5,
        melting_point_k=1900.0, combustible=False, calorific_mj_kg=0.0,
        workability=0.10, tool_score=0.3, stack_kg=2.0),
    MaterialKind.CHARCOAL: Material(
        kind=MaterialKind.CHARCOAL, name="charcoal",
        density_kg_m3=350.0, hardness_mohs=1.0,
        melting_point_k=None, combustible=True, calorific_mj_kg=33.0,
        workability=0.50, tool_score=0.0, stack_kg=1.0),
    MaterialKind.GRAIN: Material(
        kind=MaterialKind.GRAIN, name="grain",
        density_kg_m3=750.0, hardness_mohs=0.5,
        melting_point_k=None, combustible=True, calorific_mj_kg=15.5,
        workability=0.0, tool_score=0.0, stack_kg=1.0),
}


def material_of(kind: MaterialKind) -> Material:
    return MATERIALS[kind]


def can_melt(material: MaterialKind, temperature_k: float) -> bool:
    """True if the temperature is enough to liquefy this material."""
    m = MATERIALS[material]
    return m.melting_point_k is not None and temperature_k >= m.melting_point_k


def calorific_value(material: MaterialKind) -> float:
    """Returns MJ/kg released by combustion (0 if non-combustible)."""
    m = MATERIALS[material]
    return m.calorific_mj_kg if m.combustible else 0.0


# Smelting temperature thresholds (K) — needed to produce each metal.
# From Tylecote, A History of Metallurgy.
SMELTING_TEMP_K: Dict[MaterialKind, float] = {
    MaterialKind.COPPER: 1085.0 + 273.15,   # 1358 K
    MaterialKind.BRONZE: 950.0 + 273.15,    # 1223 K  (alloy melt)
    MaterialKind.IRON: 1200.0 + 273.15,     # 1473 K  (bloomery, below pure-Fe melt)
}


# Discovery / availability flags from world terrain.
# Used by harvest decisions to know what each biome can yield.
BIOME_YIELDS: Dict[int, Dict[MaterialKind, float]] = {
    # biome_id -> {material: yield_per_harvest_kg}
    0:  {},                                                    # OCEAN
    1:  {MaterialKind.STONE: 0.5},                             # ICE
    2:  {MaterialKind.STONE: 1.0, MaterialKind.FIBER: 0.2},    # TUNDRA
    3:  {MaterialKind.WOOD: 3.0, MaterialKind.STONE: 1.0,
         MaterialKind.FIBER: 0.5, MaterialKind.FLINT: 0.2},    # BOREAL_FOREST
    4:  {MaterialKind.WOOD: 5.0, MaterialKind.STONE: 1.5,
         MaterialKind.FIBER: 1.0, MaterialKind.FLINT: 0.3,
         MaterialKind.CLAY: 0.6},                              # TEMPERATE_FOREST
    5:  {MaterialKind.WOOD: 6.0, MaterialKind.FIBER: 1.5,
         MaterialKind.CLAY: 0.8},                              # TEMPERATE_RAINFOREST
    6:  {MaterialKind.FIBER: 2.0, MaterialKind.STONE: 1.5,
         MaterialKind.CLAY: 0.5, MaterialKind.GRAIN: 0.8},     # GRASSLAND
    7:  {MaterialKind.STONE: 3.0, MaterialKind.FLINT: 0.6},    # HOT_DESERT
    8:  {MaterialKind.STONE: 3.0, MaterialKind.FLINT: 0.5},    # COLD_DESERT
    9:  {MaterialKind.WOOD: 1.5, MaterialKind.FIBER: 2.0,
         MaterialKind.STONE: 1.0, MaterialKind.GRAIN: 0.6},    # SAVANNA
    10: {MaterialKind.WOOD: 3.0, MaterialKind.FIBER: 1.5,
         MaterialKind.STONE: 1.0, MaterialKind.CLAY: 0.6},     # TROPICAL_DRY_FOREST
    11: {MaterialKind.WOOD: 7.0, MaterialKind.FIBER: 2.5,
         MaterialKind.CLAY: 0.8},                              # TROPICAL_RAINFOREST
}


def biome_yield(biome_id: int) -> Dict[MaterialKind, float]:
    return BIOME_YIELDS.get(int(biome_id), {})
