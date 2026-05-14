"""Genesis Engine — physics knowledge base (Sprint B1, Pillar 1, Wave 1).

This module provides the **fundamental laws of physics** that the Genesis
Engine simulation and its AI agents can rely on when inventing materials,
designing structures, transferring heat, or simulating motion.

Until now the engine encoded gravity, thermal effects, and material
properties implicitly (or with magic numbers scattered throughout the code).
This module makes the underlying physical constants, laws, and material
properties **explicit, named, and importable** so that:

* The simulation core integrates dynamics with calibrated constants.
* AI agents (Builder, Inventor, Scientist) can query "real" physics when
  proposing artifacts or chemical reactions.
* Tests and dashboards can assert physically reasonable behavior.

References:

* Universal constants: CODATA 2018 recommended values.
* Material properties: CRC Handbook of Chemistry and Physics, 102nd ed.
  (values rounded to engineering precision; see caveats at bottom of file).

All helpers are pure functions that accept Python scalars *or* numpy arrays
and return the same shape, so they integrate naturally with the vectorized
simulation core.
"""
from __future__ import annotations

import math
from typing import Mapping

import numpy as np

ArrayLike = "np.ndarray | float | int"


# ----------------------------------------------------------------------------
# --- Constants (CODATA 2018 + standard conditions) -------------------------
# ----------------------------------------------------------------------------

# Mechanical / gravitational
G_EARTH: float = 9.81           # m/s^2 — standard gravity at Earth's surface
G_NEWTON: float = 6.67430e-11   # m^3 kg^-1 s^-2 — universal gravitational constant

# Thermodynamic
R_GAS: float = 8.314462618      # J/(mol*K) — ideal gas constant
K_B: float = 1.380649e-23       # J/K — Boltzmann constant
N_AVOGADRO: float = 6.02214076e23  # 1/mol — Avogadro constant
T_STANDARD: float = 298.15      # K — standard temperature (25 degC)
P_STANDARD: float = 101325.0    # Pa — standard atmospheric pressure
SIGMA_SB: float = 5.670374419e-8  # W/(m^2*K^4) — Stefan-Boltzmann constant

# Electromagnetic / quantum
EPSILON_0: float = 8.8541878128e-12  # F/m — vacuum permittivity
C_LIGHT: float = 299792458.0    # m/s — speed of light in vacuum (exact, SI)
H_PLANCK: float = 6.62607015e-34  # J*s — Planck constant (exact, SI)
E_CHARGE: float = 1.602176634e-19  # C — elementary charge (exact, SI)

# Convenience derived constants
RHO_AIR_STANDARD: float = 1.225  # kg/m^3 — dry air at sea level, 15 degC
RHO_WATER_STANDARD: float = 1000.0  # kg/m^3 — pure water at 4 degC


# ----------------------------------------------------------------------------
# --- Mechanics -------------------------------------------------------------
# ----------------------------------------------------------------------------

def weight(mass_kg: ArrayLike, g: float = G_EARTH) -> ArrayLike:
    """Gravitational weight (force) in Newtons. W = m * g."""
    return np.asarray(mass_kg) * g


def kinetic_energy(mass_kg: ArrayLike, velocity_ms: ArrayLike) -> ArrayLike:
    """Translational kinetic energy in Joules. E_k = 0.5 * m * v^2."""
    m = np.asarray(mass_kg)
    v = np.asarray(velocity_ms)
    return 0.5 * m * v * v


def potential_energy(mass_kg: ArrayLike, height_m: ArrayLike,
                     g: float = G_EARTH) -> ArrayLike:
    """Gravitational potential energy in Joules. E_p = m * g * h."""
    return np.asarray(mass_kg) * g * np.asarray(height_m)


# Friction coefficient tables. Values are typical engineering ranges from
# CRC Handbook; real surfaces vary widely with finish and contamination.
MU_STATIC: Mapping[str, float] = {
    "wood_wood": 0.5,
    "stone_stone": 0.7,
    "steel_steel": 0.74,
    "rubber_concrete": 1.0,
    "ice_ice": 0.10,
    "leather_wood": 0.4,
    "bone_wood": 0.45,
    "flesh_stone": 0.6,
}

MU_KINETIC: Mapping[str, float] = {
    "wood_wood": 0.3,
    "stone_stone": 0.55,
    "steel_steel": 0.57,
    "rubber_concrete": 0.8,
    "ice_ice": 0.03,
    "leather_wood": 0.3,
    "bone_wood": 0.35,
    "flesh_stone": 0.4,
}

# Backwards-friendly named aliases for the most common cases.
MU_STATIC_WOOD_WOOD: float = MU_STATIC["wood_wood"]
MU_KINETIC_WOOD_WOOD: float = MU_KINETIC["wood_wood"]
MU_STATIC_STONE_STONE: float = MU_STATIC["stone_stone"]
MU_KINETIC_STONE_STONE: float = MU_KINETIC["stone_stone"]


def friction_force(normal_N: ArrayLike, mu: float) -> ArrayLike:
    """Magnitude of the friction force in Newtons. f = mu * N.

    The same formula serves for static (max) and kinetic friction; pass the
    appropriate coefficient from MU_STATIC / MU_KINETIC.
    """
    return np.asarray(normal_N) * mu


def stress(force_N: ArrayLike, area_m2: ArrayLike) -> ArrayLike:
    """Mechanical stress in Pascals. sigma = F / A."""
    a = np.asarray(area_m2)
    if np.any(np.asarray(a) <= 0):
        raise ValueError("area_m2 must be strictly positive")
    return np.asarray(force_N) / a


def strain(deformation_m: ArrayLike, length_m: ArrayLike) -> ArrayLike:
    """Engineering strain (dimensionless). epsilon = delta_L / L_0."""
    l0 = np.asarray(length_m)
    if np.any(np.asarray(l0) <= 0):
        raise ValueError("length_m must be strictly positive")
    return np.asarray(deformation_m) / l0


# ----------------------------------------------------------------------------
# --- Thermodynamics --------------------------------------------------------
# ----------------------------------------------------------------------------

# Specific heat capacities, c_p, J/(kg*K) — near 25 degC, ambient pressure.
heat_capacity_table: Mapping[str, float] = {
    "water": 4186.0,
    "ice": 2090.0,
    "steam": 2010.0,
    "air": 1005.0,
    "iron": 449.0,
    "steel": 490.0,
    "copper": 385.0,
    "aluminum": 897.0,
    "wood": 1700.0,   # average dry wood
    "stone": 800.0,   # average dense rock
    "concrete": 880.0,
    "glass": 840.0,
    "flesh": 3500.0,  # animal soft tissue, hydrated
    "bone": 1300.0,
}

# Thermal conductivity, k, W/(m*K) at ~25 degC.
thermal_conductivity_table: Mapping[str, float] = {
    "water": 0.6,
    "air": 0.026,
    "iron": 80.0,
    "steel": 50.0,
    "copper": 401.0,
    "aluminum": 237.0,
    "wood": 0.15,
    "stone": 2.5,
    "concrete": 1.4,
    "glass": 0.96,
    "ice": 2.2,
    "flesh": 0.5,
    "bone": 0.4,
}


def heat_transfer_conduction(k: float, area_m2: ArrayLike,
                             dT_K: ArrayLike,
                             thickness_m: ArrayLike) -> ArrayLike:
    """Steady-state Fourier conduction. Q_dot = k * A * dT / L  (in Watts).

    Parameters
    ----------
    k : float
        Thermal conductivity, W/(m*K). Use ``thermal_conductivity_table``.
    area_m2 : array_like
        Cross-section area normal to heat flow, m^2.
    dT_K : array_like
        Temperature difference (T_hot - T_cold), K.
    thickness_m : array_like
        Path length through the material, m.
    """
    thickness = np.asarray(thickness_m)
    if np.any(thickness <= 0):
        raise ValueError("thickness_m must be strictly positive")
    return k * np.asarray(area_m2) * np.asarray(dT_K) / thickness


def heat_transfer_radiation(emissivity: float, area_m2: ArrayLike,
                            T_hot_K: ArrayLike,
                            T_cold_K: ArrayLike) -> ArrayLike:
    """Stefan-Boltzmann net radiative exchange in Watts.

    Q_dot = epsilon * sigma * A * (T_hot^4 - T_cold^4)
    """
    if not (0.0 <= emissivity <= 1.0):
        raise ValueError("emissivity must lie in [0, 1]")
    Th = np.asarray(T_hot_K, dtype=float)
    Tc = np.asarray(T_cold_K, dtype=float)
    return emissivity * SIGMA_SB * np.asarray(area_m2) * (Th ** 4 - Tc ** 4)


def gibbs_free_energy(dH_J: ArrayLike, T_K: ArrayLike,
                      dS_J_per_K: ArrayLike) -> ArrayLike:
    """Gibbs free-energy change. dG = dH - T * dS  (Joules)."""
    return np.asarray(dH_J) - np.asarray(T_K) * np.asarray(dS_J_per_K)


def is_thermodynamically_favorable(dG_J: ArrayLike) -> "np.ndarray | bool":
    """Return True where dG < 0 (spontaneous at the given T)."""
    arr = np.asarray(dG_J)
    if arr.ndim == 0:
        return bool(arr < 0.0)
    return arr < 0.0


def arrhenius_rate(A: ArrayLike, Ea_J_per_mol: ArrayLike,
                   T_K: ArrayLike) -> ArrayLike:
    """Arrhenius rate constant k = A * exp(-Ea / (R * T))."""
    T = np.asarray(T_K, dtype=float)
    if np.any(T <= 0):
        raise ValueError("T_K must be strictly positive")
    return np.asarray(A) * np.exp(-np.asarray(Ea_J_per_mol) / (R_GAS * T))


# ----------------------------------------------------------------------------
# --- Simulation derivatives ------------------------------------------------
# ----------------------------------------------------------------------------

def compute_acceleration(force_N: ArrayLike, mass_kg: ArrayLike) -> ArrayLike:
    """Newton's second law. a = F / m  (m/s^2)."""
    m = np.asarray(mass_kg)
    if np.any(m <= 0):
        raise ValueError("mass_kg must be strictly positive")
    return np.asarray(force_N) / m


def compute_terminal_velocity(mass_kg: ArrayLike, drag_coef: float,
                              area_m2: ArrayLike,
                              rho_air: float = RHO_AIR_STANDARD,
                              g: float = G_EARTH) -> ArrayLike:
    """Terminal velocity under quadratic drag.

    v_t = sqrt( 2 * m * g / (rho * C_d * A) )

    The fluid is assumed to be air at sea level by default; pass
    ``rho_air=RHO_WATER_STANDARD`` for water etc.
    """
    if drag_coef <= 0:
        raise ValueError("drag_coef must be strictly positive")
    a = np.asarray(area_m2)
    if np.any(a <= 0):
        raise ValueError("area_m2 must be strictly positive")
    return np.sqrt(2.0 * np.asarray(mass_kg) * g / (rho_air * drag_coef * a))


def compute_orbital_period(major_axis_m: ArrayLike,
                           mass_central_kg: float) -> ArrayLike:
    """Kepler's third law. T = 2*pi * sqrt(a^3 / (G * M))  (seconds)."""
    if mass_central_kg <= 0:
        raise ValueError("mass_central_kg must be strictly positive")
    a = np.asarray(major_axis_m, dtype=float)
    if np.any(a <= 0):
        raise ValueError("major_axis_m must be strictly positive")
    return 2.0 * math.pi * np.sqrt(a ** 3 / (G_NEWTON * mass_central_kg))


__all__ = [
    # constants
    "G_EARTH", "G_NEWTON", "R_GAS", "K_B", "N_AVOGADRO",
    "T_STANDARD", "P_STANDARD", "SIGMA_SB",
    "EPSILON_0", "C_LIGHT", "H_PLANCK", "E_CHARGE",
    "RHO_AIR_STANDARD", "RHO_WATER_STANDARD",
    # mechanics
    "weight", "kinetic_energy", "potential_energy",
    "MU_STATIC", "MU_KINETIC",
    "MU_STATIC_WOOD_WOOD", "MU_KINETIC_WOOD_WOOD",
    "MU_STATIC_STONE_STONE", "MU_KINETIC_STONE_STONE",
    "friction_force", "stress", "strain",
    # thermo
    "heat_capacity_table", "thermal_conductivity_table",
    "heat_transfer_conduction", "heat_transfer_radiation",
    "gibbs_free_energy", "is_thermodynamically_favorable",
    "arrhenius_rate",
    # simulation
    "compute_acceleration", "compute_terminal_velocity",
    "compute_orbital_period",
]
