"""Registre unifié des propriétés physiques du monde (L0–L2).

Agrège constantes universelles, matériaux, minéraux et états de phase pour
que simulation, forge et IA consultent les mêmes lois.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from engine.materials import MATERIALS, Material, MaterialKind
from engine.physics import (
    C_LIGHT,
    G_EARTH,
    P_STANDARD,
    R_GAS,
    RHO_WATER_STANDARD,
    SIGMA_SB,
    T_STANDARD,
    thermal_conductivity_table,
)

PIPELINE_LAYER = "Genesis-L0 Physics"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


@dataclass(frozen=True)
class PhaseState:
    name: str
    density_kg_m3: float
    heat_capacity_j_kgk: float
    thermal_conductivity_w_mk: float


@dataclass(frozen=True)
class WorldMaterialProps:
    """Propriétés physiques complètes d'un matériau nommé."""
    name: str
    kind: str
    density_kg_m3: float
    hardness_mohs: float
    melting_point_k: Optional[float]
    boiling_point_k: Optional[float]
    young_modulus_gpa: float
    heat_capacity_j_kgk: float
    thermal_conductivity_w_mk: float
    electrical_resistivity_ohm_m: float
    combustible: bool
    calorific_mj_kg: float
    workability: float


# Young's modulus proxies (GPa) — engineering handbook rounded
_YOUNG_GPA = {
    MaterialKind.WOOD: 11.0,
    MaterialKind.STONE: 50.0,
    MaterialKind.FLINT: 70.0,
    MaterialKind.CLAY: 0.5,
    MaterialKind.COPPER: 120.0,
    MaterialKind.IRON: 200.0,
    MaterialKind.BRONZE: 100.0,
    MaterialKind.CERAMIC: 300.0,
}

_CP_J_KGK = {
    MaterialKind.WOOD: 1700.0,
    MaterialKind.STONE: 800.0,
    MaterialKind.IRON: 450.0,
    MaterialKind.COPPER: 385.0,
}


def material_props(kind: MaterialKind) -> WorldMaterialProps:
    m: Material = MATERIALS[kind]
    k = float(thermal_conductivity_table.get(m.name, 1.5))
    cp = _CP_J_KGK.get(kind, 900.0)
    young = _YOUNG_GPA.get(kind, 30.0)
    return WorldMaterialProps(
        name=m.name,
        kind=kind.name,
        density_kg_m3=m.density_kg_m3,
        hardness_mohs=m.hardness_mohs,
        melting_point_k=m.melting_point_k,
        boiling_point_k=None,
        young_modulus_gpa=young,
        heat_capacity_j_kgk=cp,
        thermal_conductivity_w_mk=k,
        electrical_resistivity_ohm_m=1e6 if m.name == "wood" else 1e-7,
        combustible=m.combustible,
        calorific_mj_kg=m.calorific_mj_kg,
        workability=m.workability,
    )


def universal_constants() -> Dict[str, float]:
    return {
        "g_earth_ms2": G_EARTH,
        "p_standard_pa": P_STANDARD,
        "t_standard_k": T_STANDARD,
        "r_gas_j_molk": R_GAS,
        "sigma_sb_w_m2k4": SIGMA_SB,
        "rho_water_kg_m3": RHO_WATER_STANDARD,
        "c_light_ms": C_LIGHT,
        "earth_rotation_rad_s": 7.2921159e-5,
        "earth_radius_m": 6.371e6,
        "core_radius_m": 3.48e6,
    }


def phase_table() -> Dict[str, PhaseState]:
    return {
        "solid": PhaseState("solid", 2700.0, 800.0, 2.5),
        "liquid": PhaseState("liquid", 1000.0, 4186.0, 0.6),
        "gas": PhaseState("gas", 1.2, 1005.0, 0.025),
        "magma": PhaseState("magma", 2800.0, 1200.0, 1.2),
    }


def registry_snapshot() -> Dict[str, Any]:
    mats = {m.name: {
        "density_kg_m3": p.density_kg_m3,
        "melting_point_k": p.melting_point_k,
        "thermal_conductivity_w_mk": p.thermal_conductivity_w_mk,
        "young_modulus_gpa": p.young_modulus_gpa,
    } for m, p in ((MATERIALS[k], material_props(k)) for k in MaterialKind)}
    return {
        "constants": universal_constants(),
        "phases": {k: {"density": v.density_kg_m3, "cp": v.heat_capacity_j_kgk}
                   for k, v in phase_table().items()},
        "materials": mats,
        "n_materials": len(mats),
    }


__all__ = [
    "WorldMaterialProps",
    "material_props",
    "universal_constants",
    "phase_table",
    "registry_snapshot",
]
