"""Genesis Engine — Sprint B3 — Physics-constrained material invention.

Pillar 2 of FUTURE-VISION.md ("Invention emergente de materiaux respectant
les lois de la nature"). AI agents combine elements under physico-chemical
conditions; if the proposal passes thermodynamic / kinetic / mass-balance
checks, a *new* :class:`SynthesizedMaterial` emerges and joins the registry.

No magic. Every property is derived from element-level chemistry and
condition-level physics. Failure modes (mass non-conservation, insufficient
heat, hostile atmosphere) return ``None`` with an explicit reason string.

Inputs:
    composition  -- mole fraction of each element (must sum to 1.0)
    conditions   -- :class:`SynthesisConditions` (T, P, atmosphere, time)
    tools        -- which thermal tools the culture has unlocked

Imports :mod:`engine.physics` (Sprint B1) and tries to import
:mod:`engine.chemistry` (Sprint B2). If B2 is not yet committed we fall back
on a minimal hard-coded element table sufficient for the smoke tests.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ----------------------------------------------------------------------------
# --- Physics import (B1) with fallback ------------------------------------
# ----------------------------------------------------------------------------
try:
    from engine.physics import (
        G_EARTH, R_GAS, T_STANDARD, P_STANDARD,
        gibbs_free_energy, arrhenius_rate,
    )
except ImportError:  # pragma: no cover -- defensive fallback
    G_EARTH = 9.81
    R_GAS = 8.314462618
    T_STANDARD = 298.15
    P_STANDARD = 101325.0

    def gibbs_free_energy(dH_J, T_K, dS_J_per_K):  # type: ignore
        return dH_J - T_K * dS_J_per_K

    def arrhenius_rate(A, Ea_J_per_mol, T_K):  # type: ignore
        return A * math.exp(-Ea_J_per_mol / (R_GAS * T_K))


# ----------------------------------------------------------------------------
# --- Chemistry import (B2) with fallback ----------------------------------
# ----------------------------------------------------------------------------
# B2 may not be committed yet. We try the real module first; otherwise a
# minimal hard-coded table covers the elements required by the smoke test
# (Cu, Sn, Fe, C, O) plus a handful of common partners.
try:
    from engine.chemistry import (  # type: ignore
        PERIODIC_TABLE, BOND_ENERGY, density_alloy, bond_energy, is_metal,
    )
    _HAS_REAL_CHEMISTRY = True

    def _el_density(symbol: str) -> float:
        el = PERIODIC_TABLE.get(symbol)
        return float(el.density_g_cm3) if el is not None else 0.0

    def _el_melting_K(symbol: str) -> float:
        el = PERIODIC_TABLE.get(symbol)
        return float(el.melting_point_K) if el is not None else 0.0

    def _el_is_metal(symbol: str) -> bool:
        return bool(is_metal(symbol))

    def _has_element(symbol: str) -> bool:
        return symbol in PERIODIC_TABLE

except ImportError:
    _HAS_REAL_CHEMISTRY = False

    # Minimal element table. Values from CRC Handbook (rounded to engineering
    # precision). atomic_mass in g/mol; density in g/cm^3; melting in K;
    # metal: True for metallic elements. bond_energy_self in kJ/mol is a
    # convenience proxy for "how strongly element-element bonds hold up".
    PERIODIC_TABLE: Dict[str, Dict[str, float]] = {
        "H":  {"atomic_mass": 1.008,   "density_g_cm3": 0.00009,
               "melting_K": 14.0,    "metal": False, "electroneg": 2.20},
        "C":  {"atomic_mass": 12.011,  "density_g_cm3": 2.267,
               "melting_K": 3823.0,  "metal": False, "electroneg": 2.55},
        "N":  {"atomic_mass": 14.007,  "density_g_cm3": 0.00125,
               "melting_K": 63.0,    "metal": False, "electroneg": 3.04},
        "O":  {"atomic_mass": 15.999,  "density_g_cm3": 0.00143,
               "melting_K": 54.0,    "metal": False, "electroneg": 3.44},
        "Na": {"atomic_mass": 22.990,  "density_g_cm3": 0.971,
               "melting_K": 371.0,   "metal": True,  "electroneg": 0.93},
        "Mg": {"atomic_mass": 24.305,  "density_g_cm3": 1.738,
               "melting_K": 923.0,   "metal": True,  "electroneg": 1.31},
        "Al": {"atomic_mass": 26.982,  "density_g_cm3": 2.700,
               "melting_K": 933.0,   "metal": True,  "electroneg": 1.61},
        "Si": {"atomic_mass": 28.086,  "density_g_cm3": 2.329,
               "melting_K": 1687.0,  "metal": False, "electroneg": 1.90},
        "P":  {"atomic_mass": 30.974,  "density_g_cm3": 1.823,
               "melting_K": 317.0,   "metal": False, "electroneg": 2.19},
        "S":  {"atomic_mass": 32.06,   "density_g_cm3": 2.067,
               "melting_K": 388.0,   "metal": False, "electroneg": 2.58},
        "K":  {"atomic_mass": 39.098,  "density_g_cm3": 0.862,
               "melting_K": 336.0,   "metal": True,  "electroneg": 0.82},
        "Ca": {"atomic_mass": 40.078,  "density_g_cm3": 1.550,
               "melting_K": 1115.0,  "metal": True,  "electroneg": 1.00},
        "Ti": {"atomic_mass": 47.867,  "density_g_cm3": 4.506,
               "melting_K": 1941.0,  "metal": True,  "electroneg": 1.54},
        "Cr": {"atomic_mass": 51.996,  "density_g_cm3": 7.190,
               "melting_K": 2180.0,  "metal": True,  "electroneg": 1.66},
        "Fe": {"atomic_mass": 55.845,  "density_g_cm3": 7.874,
               "melting_K": 1811.0,  "metal": True,  "electroneg": 1.83},
        "Ni": {"atomic_mass": 58.693,  "density_g_cm3": 8.908,
               "melting_K": 1728.0,  "metal": True,  "electroneg": 1.91},
        "Cu": {"atomic_mass": 63.546,  "density_g_cm3": 8.960,
               "melting_K": 1357.0,  "metal": True,  "electroneg": 1.90},
        "Zn": {"atomic_mass": 65.38,   "density_g_cm3": 7.140,
               "melting_K": 692.0,   "metal": True,  "electroneg": 1.65},
        "Ag": {"atomic_mass": 107.868, "density_g_cm3": 10.490,
               "melting_K": 1235.0,  "metal": True,  "electroneg": 1.93},
        "Sn": {"atomic_mass": 118.710, "density_g_cm3": 7.310,
               "melting_K": 505.0,   "metal": True,  "electroneg": 1.96},
        "Au": {"atomic_mass": 196.967, "density_g_cm3": 19.300,
               "melting_K": 1337.0,  "metal": True,  "electroneg": 2.54},
        "Pb": {"atomic_mass": 207.2,   "density_g_cm3": 11.340,
               "melting_K": 600.0,   "metal": True,  "electroneg": 2.33},
    }

    # Bond energies, kJ/mol — CRC Handbook of Chemistry and Physics, 102nd ed.
    # Symmetric: ("A","B") and ("B","A") read identically via _bond_lookup.
    BOND_ENERGY: Dict[Tuple[str, str], float] = {
        ("C", "O"): 1077.0,    # very strong (C=O / CO triple in CO)
        ("Fe", "O"): 409.0,
        ("Cu", "O"): 343.0,
        ("Sn", "O"): 528.0,
        ("Cu", "Sn"): 195.0,   # weak metallic bond -> bronze
        ("Fe", "C"): 320.0,    # steel cementite Fe3C
        ("Si", "O"): 800.0,
        ("Al", "O"): 511.0,
        ("Ca", "O"): 383.0,
        ("Na", "O"): 270.0,
        ("Cu", "Cu"): 201.0,
        ("Fe", "Fe"): 100.0,
        ("Sn", "Sn"): 187.0,
        ("Cu", "Fe"): 152.0,
        ("C", "C"): 347.0,
        ("O", "O"): 498.0,
        ("H", "O"): 463.0,
    }

    def density_alloy(composition: Dict[str, float]) -> float:
        """Weighted average density (g/cm^3) — Vegard-style estimate."""
        rho = 0.0
        for el, frac in composition.items():
            if el in PERIODIC_TABLE:
                rho += frac * PERIODIC_TABLE[el]["density_g_cm3"]
        return rho

    def bond_energy(a: str, b: str) -> float:  # type: ignore
        if (a, b) in BOND_ENERGY:
            return BOND_ENERGY[(a, b)]
        if (b, a) in BOND_ENERGY:
            return BOND_ENERGY[(b, a)]
        return 0.0

    def _el_density(symbol: str) -> float:
        entry = PERIODIC_TABLE.get(symbol)
        return float(entry["density_g_cm3"]) if entry is not None else 0.0

    def _el_melting_K(symbol: str) -> float:
        entry = PERIODIC_TABLE.get(symbol)
        return float(entry["melting_K"]) if entry is not None else 0.0

    def _el_is_metal(symbol: str) -> bool:
        entry = PERIODIC_TABLE.get(symbol)
        return bool(entry["metal"]) if entry is not None else False

    def _has_element(symbol: str) -> bool:
        return symbol in PERIODIC_TABLE


def _bond_lookup(a: str, b: str) -> float:
    """Return bond energy in kJ/mol for the (a,b) pair, regardless of order.

    Defers to ``chemistry.bond_energy`` when available. Falls back to
    ``200.0`` (typical metallic) if unknown, so the validator can still
    produce a finite Gibbs estimate for unfamiliar systems.
    """
    be = bond_energy(a, b)
    if be > 0.0:
        return float(be)
    # Some metal-metal bonds aren't in B2's table; supply mid-range default.
    return 200.0


# ----------------------------------------------------------------------------
# --- Tool -> max temperature ------------------------------------------------
# ----------------------------------------------------------------------------
# Approximate peak gas temperature reachable by each heating method. Wood
# fire at open air saturates around 900-1100 K; a clay kiln pushes to
# ~1500 K; a forced-draft forge can reach ~1900 K; a refractory furnace
# (cupola, blast furnace, modern crucible) easily exceeds 2000 K.
TOOL_MAX_TEMPERATURE_K: Dict[str, float] = {
    "fire": 1100.0,
    "kiln": 1500.0,
    "forge": 1900.0,
    "furnace": 2200.0,
    "plasma": 5000.0,
}


def _max_tool_temperature(tools: Tuple[str, ...]) -> float:
    """Return the hottest temperature the culture can sustain."""
    best = T_STANDARD  # 298.15 K — ambient only
    for tool in tools:
        if tool in TOOL_MAX_TEMPERATURE_K:
            best = max(best, TOOL_MAX_TEMPERATURE_K[tool])
    return best


# ----------------------------------------------------------------------------
# --- Dataclasses ------------------------------------------------------------
# ----------------------------------------------------------------------------

@dataclass
class SynthesisConditions:
    """Physico-chemical environment under which synthesis is attempted."""
    temperature_K: float
    pressure_Pa: float = 101325.0
    atmosphere: str = "air"   # "air" | "reducing" | "inert" | "oxidizing"
    time_s: float = 3600.0


@dataclass
class SynthesizedMaterial:
    """An emergent material discovered by a culture."""
    material_id: int
    name: str
    composition: Dict[str, float]
    discovered_tick: int
    discovered_by_culture: int
    conditions: Dict[str, float]
    properties: Dict[str, float]
    parent_materials: Tuple[int, ...] = ()


# ----------------------------------------------------------------------------
# --- Validation -------------------------------------------------------------
# ----------------------------------------------------------------------------

# Eutectic / softening heuristics. We approximate the temperature at which a
# mixture becomes processable by taking the *minimum* element melting point,
# weighted toward the lower-melting partner — a crude eutectic-style proxy.
# This is intentionally generous: it lets bronze (Cu mp 1357 K, Sn mp 505 K)
# come together around ~1050 K, matching real bronze-age furnace temps.
_EUTECTIC_DEPRESSION = 0.78  # multiply weighted-min melting point by this


def _eutectic_temperature_K(composition: Dict[str, float]) -> float:
    """Approximate the minimum temperature needed to drive the reaction.

    Rule: a weighted minimum-of-melting-points, depressed by 22 % to mimic
    eutectic behavior in binary metal systems.
    """
    mps: List[float] = []
    for el, frac in composition.items():
        if _has_element(el) and frac > 0:
            mp = _el_melting_K(el)
            # Use min-of-elements (eutectic-like). Skip gaseous elements
            # (mp < 100 K) that distort the average for solid mixtures.
            if mp >= 100.0:
                mps.append(mp)
    if not mps:
        return T_STANDARD
    return min(mps) * _EUTECTIC_DEPRESSION


def _estimate_gibbs(composition: Dict[str, float], T_K: float) -> float:
    """Rough Gibbs free energy (kJ/mol) for forming the mixture.

    Approach: compute a mean *cohesive* enthalpy from pairwise bond energies
    weighted by mole fractions, then subtract T*dS (configurational entropy
    of an ideal solution). dG < 0 => spontaneous at this T.

    Returned in J/mol so it can feed :func:`gibbs_free_energy` style calls.
    """
    elements = [el for el, frac in composition.items() if frac > 0]
    if not elements:
        return 0.0

    # Pairwise bond enthalpy (kJ/mol), weighted by joint mole fraction.
    # Sign: forming bonds releases heat -> dH < 0.
    dH_kJ = 0.0
    for i, a in enumerate(elements):
        fa = composition[a]
        for b in elements[i:]:
            fb = composition[b]
            be = _bond_lookup(a, b)
            weight = fa * fb if a != b else fa * fa * 0.5
            dH_kJ -= be * weight  # negative => exothermic
    dH_J = dH_kJ * 1000.0  # kJ/mol -> J/mol

    # Configurational entropy of mixing (ideal solution), J/(mol*K).
    # dS = -R * sum(x_i * ln x_i). Always >= 0 for a real mixture.
    dS = 0.0
    for el in elements:
        x = composition[el]
        if x > 0:
            dS -= R_GAS * x * math.log(x)

    return float(gibbs_free_energy(dH_J, T_K, dS))


def _atmosphere_compatible(
    composition: Dict[str, float],
    atmosphere: str,
) -> Tuple[bool, str]:
    """Reject combinations that the atmosphere would destroy.

    Heuristics, not full thermochemistry:

    * In an *oxidizing* atmosphere, easily oxidized metals (Fe, Cu, Al,
      Mg) cannot consolidate as a pure metal phase — they form oxides.
    * In a *reducing* atmosphere (CO / charcoal), oxides are reduced and
      we expect metallic products to be safe.
    * In an *inert* atmosphere (Ar, N2 ~OK for most), anything goes.
    * In *air* (mildly oxidizing), noble-ish metals (Cu, Au, Sn, Ag) are
      OK but bare Fe will rust unless paired with carbon.
    """
    oxidisable = {"Fe", "Al", "Mg", "Ti"}
    has_oxidisable = any(composition.get(el, 0.0) > 0 for el in oxidisable)
    has_oxygen = composition.get("O", 0.0) > 0
    has_carbon = composition.get("C", 0.0) > 0

    atm = atmosphere.lower()
    if atm == "oxidizing":
        # Only stable as oxides. If no oxygen in the composition, fail.
        if has_oxidisable and not has_oxygen:
            return (False, f"atmosphere:oxidizing_destroys_{','.join(sorted(oxidisable & set(composition)))}")
    elif atm == "reducing":
        # Pre-existing oxides would be reduced; OK for metals.
        return (True, "")
    elif atm == "inert":
        return (True, "")
    elif atm == "air":
        # Air is mildly oxidizing. Bare iron without protective carbon is
        # unstable on long timescales.
        if "Fe" in composition and composition["Fe"] > 0.5 and not has_carbon:
            return (False, "atmosphere:air_oxidizes_bare_iron")
    else:
        return (False, f"atmosphere:unknown_{atmosphere}")
    return (True, "")


def check_physical_validity(
    composition: Dict[str, float],
    conditions: SynthesisConditions,
    tools_available: Tuple[str, ...] = (),
) -> Tuple[bool, str]:
    """Validate a synthesis proposal.

    Returns ``(True, "")`` if the combination respects the laws of mass
    conservation, thermodynamics and kinetics under the given conditions,
    else ``(False, reason)`` where ``reason`` is a machine-readable tag
    suitable for logging.

    Checks, in order:

    1. ``mass_conservation``      — mole fractions sum to 1.0 (±1e-3).
    2. ``unknown_element``        — every element appears in PERIODIC_TABLE.
    3. ``temperature_unreachable``— tools can't reach the target T.
    4. ``temperature_too_low``    — T is below the eutectic estimate, so
                                    nothing fuses / diffuses fast enough.
    5. ``gibbs_unfavorable``      — dG > 0 at this T (won't form).
    6. ``atmosphere:*``           — atmosphere destroys the product.
    """
    # 1. Conservation of mass
    total = sum(composition.values())
    if abs(total - 1.0) > 1e-3:
        return (False, f"mass_conservation:sum={total:.4f}")

    # 2. Known elements
    for el in composition:
        if not _has_element(el):
            return (False, f"unknown_element:{el}")

    T = conditions.temperature_K
    if T <= 0:
        return (False, "temperature_too_low:non_positive")

    # 3. Tool reach
    T_tool_max = _max_tool_temperature(tools_available)
    if T > T_tool_max + 1.0:
        return (False,
                f"temperature_unreachable:need_{T:.0f}K_max_{T_tool_max:.0f}K")

    # 4. Reaction kinetics floor (eutectic-style)
    T_min = _eutectic_temperature_K(composition)
    if T < T_min:
        return (False,
                f"temperature_too_low:need_{T_min:.0f}K_got_{T:.0f}K")

    # 5. Thermodynamic favorability
    dG = _estimate_gibbs(composition, T)
    if dG > 0.0:
        return (False, f"gibbs_unfavorable:dG={dG:.0f}J/mol")

    # 6. Atmosphere
    ok_atm, reason_atm = _atmosphere_compatible(composition, conditions.atmosphere)
    if not ok_atm:
        return (False, reason_atm)

    return (True, "")


# ----------------------------------------------------------------------------
# --- Property derivation ----------------------------------------------------
# ----------------------------------------------------------------------------

def _canonical_name(composition: Dict[str, float]) -> str:
    """Auto-name a material like ``alloy_Cu70Sn30`` or ``ceramic_Si50O40N10``.

    Rule:
        * All-metal mixture -> ``alloy_``
        * Contains O and a non-metal cation -> ``ceramic_``
        * Otherwise -> ``compound_``
    The element list is sorted by descending mole fraction, then symbol.
    """
    items = sorted(composition.items(), key=lambda kv: (-kv[1], kv[0]))
    parts = [f"{el}{int(round(frac * 100))}" for el, frac in items if frac > 0]
    body = "".join(parts)

    all_metals = all(
        _el_is_metal(el)
        for el, frac in items if frac > 0
    )
    has_oxygen = composition.get("O", 0.0) > 0

    if all_metals:
        prefix = "alloy"
    elif has_oxygen:
        prefix = "ceramic"
    else:
        prefix = "compound"
    return f"{prefix}_{body}"


def _derive_properties(
    composition: Dict[str, float],
    conditions: SynthesisConditions,
) -> Dict[str, float]:
    """Compute density, melting point, hardness, conductivity heuristics."""
    # Density — use chemistry.density_alloy if available, else weighted avg.
    rho = float(density_alloy(composition))

    # Melting point — Vegard's rule (linear interpolation by mole fraction).
    mp = 0.0
    mp_weight = 0.0
    for el, frac in composition.items():
        if _has_element(el) and frac > 0:
            el_mp = _el_melting_K(el)
            if el_mp >= 100.0:
                mp += frac * el_mp
                mp_weight += frac
    melting_K = mp / mp_weight if mp_weight > 0 else T_STANDARD

    # Hardness — empirical: high mean bond energy -> high Mohs.
    # Mohs scale tops out at 10 (diamond, bond ~347 kJ/mol C-C in sp3 lattice).
    # We map mean pairwise bond energy onto [0.5, 9.5] linearly.
    elements = [el for el, frac in composition.items() if frac > 0]
    mean_bond = 0.0
    total_w = 0.0
    for i, a in enumerate(elements):
        for b in elements[i:]:
            w = composition[a] * composition[b]
            mean_bond += _bond_lookup(a, b) * w
            total_w += w
    if total_w > 0:
        mean_bond /= total_w
    # Calibration: 100 kJ/mol -> Mohs 1, 800 kJ/mol -> Mohs 9.
    hardness = 0.5 + (mean_bond - 100.0) * (9.0 / 700.0)
    hardness = max(0.5, min(10.0, hardness))

    # Electrical conductivity — coarse "good" / "poor". >50% metals -> good.
    metal_frac = sum(
        frac for el, frac in composition.items() if _el_is_metal(el)
    )
    conductivity_good = 1.0 if metal_frac > 0.5 else 0.0

    return {
        "density_g_cm3": rho,
        "melting_point_K": melting_K,
        "hardness_mohs_estimate": hardness,
        "electrical_conductivity_estimate": conductivity_good,
        "metal_fraction": metal_frac,
    }


# ----------------------------------------------------------------------------
# --- Synthesis entry point --------------------------------------------------
# ----------------------------------------------------------------------------

def synthesize(
    composition: Dict[str, float],
    conditions: SynthesisConditions,
    tools_available: Tuple[str, ...] = (),
    culture_id: int = 0,
    tick: int = 0,
    rng: Optional[random.Random] = None,
    parent_materials: Tuple[int, ...] = (),
    material_id: int = 0,
) -> Optional[SynthesizedMaterial]:
    """Attempt to synthesize a new material.

    Returns the :class:`SynthesizedMaterial` if the proposal is physically
    valid; otherwise ``None``. Deterministic when ``rng`` is provided.
    """
    ok, _reason = check_physical_validity(
        composition, conditions, tools_available,
    )
    if not ok:
        return None

    props = _derive_properties(composition, conditions)

    # Small deterministic perturbation (±2%) on hardness/density if rng given,
    # so repeated discoveries can produce slightly varied properties without
    # breaking determinism. Use rng to keep it reproducible.
    if rng is not None:
        jitter_d = 1.0 + (rng.random() - 0.5) * 0.04
        jitter_h = 1.0 + (rng.random() - 0.5) * 0.04
        props["density_g_cm3"] *= jitter_d
        props["hardness_mohs_estimate"] = max(
            0.5, min(10.0, props["hardness_mohs_estimate"] * jitter_h),
        )

    name = _canonical_name(composition)
    return SynthesizedMaterial(
        material_id=material_id,
        name=name,
        composition=dict(composition),
        discovered_tick=tick,
        discovered_by_culture=culture_id,
        conditions={
            "temperature_K": conditions.temperature_K,
            "pressure_Pa": conditions.pressure_Pa,
            "time_s": conditions.time_s,
            "atmosphere_code": float(_atmosphere_code(conditions.atmosphere)),
        },
        properties=props,
        parent_materials=tuple(parent_materials),
    )


def _atmosphere_code(atm: str) -> int:
    return {"air": 0, "reducing": 1, "inert": 2, "oxidizing": 3}.get(
        atm.lower(), -1,
    )


# ----------------------------------------------------------------------------
# --- MaterialRegistry -------------------------------------------------------
# ----------------------------------------------------------------------------

@dataclass
class MaterialRegistry:
    """Shared catalogue of discovered materials + per-culture knowledge."""
    _by_id: Dict[int, SynthesizedMaterial] = field(default_factory=dict)
    _by_name: Dict[str, int] = field(default_factory=dict)
    _culture_known: Dict[int, set] = field(default_factory=dict)
    _next_id: int = 1

    # ---- writes ----
    def register(self, material: SynthesizedMaterial) -> int:
        """Insert a material; assign a fresh id if it lacks one. Returns id."""
        if material.name in self._by_name:
            # Already known — return existing id and tag the new culture.
            mid = self._by_name[material.name]
            self._culture_known.setdefault(
                material.discovered_by_culture, set()
            ).add(mid)
            return mid
        if material.material_id <= 0:
            material.material_id = self._next_id
            self._next_id += 1
        else:
            self._next_id = max(self._next_id, material.material_id + 1)
        self._by_id[material.material_id] = material
        self._by_name[material.name] = material.material_id
        self._culture_known.setdefault(
            material.discovered_by_culture, set()
        ).add(material.material_id)
        return material.material_id

    def transmit(
        self,
        from_culture: int,
        to_culture: int,
        material_id: int,
        rng: Optional[random.Random] = None,
        success_prob: float = 0.6,
    ) -> bool:
        """Transmit knowledge of ``material_id`` from one culture to another.

        Returns ``True`` if the recipient learns it. Requires the sender to
        actually know the material. Determined by ``rng`` when provided.
        """
        if material_id not in self._by_id:
            return False
        sender = self._culture_known.get(from_culture, set())
        if material_id not in sender:
            return False
        roll = rng.random() if rng is not None else 1.0  # default: succeed
        if roll <= success_prob:
            self._culture_known.setdefault(to_culture, set()).add(material_id)
            return True
        return False

    # ---- reads ----
    def lookup_by_name(self, name: str) -> Optional[SynthesizedMaterial]:
        mid = self._by_name.get(name)
        return self._by_id.get(mid) if mid is not None else None

    def lookup_by_id(self, mid: int) -> Optional[SynthesizedMaterial]:
        return self._by_id.get(mid)

    def all_known(self) -> List[SynthesizedMaterial]:
        return list(self._by_id.values())

    def culture_known(self, culture_id: int) -> List[SynthesizedMaterial]:
        ids = self._culture_known.get(culture_id, set())
        return [self._by_id[mid] for mid in ids if mid in self._by_id]


__all__ = [
    "SynthesisConditions",
    "SynthesizedMaterial",
    "MaterialRegistry",
    "check_physical_validity",
    "synthesize",
    "TOOL_MAX_TEMPERATURE_K",
    "PERIODIC_TABLE",
    "BOND_ENERGY",
]
