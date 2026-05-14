"""Real-world chemistry knowledge base for the Genesis Engine.

This module ingests the periodic table (40+ most relevant elements for
archaeology / civilisation modelling), covalent bond enthalpies, and a
handful of small helpers that AI agents and material-invention pipelines
use to reason about composition, alloys, and reactivity.

All values are hardcoded from public references (PubChem 2024 / NIST):
  - Atomic mass: standard atomic weights (IUPAC 2021).
  - Electronegativity: Pauling scale.
  - Densities: g/cm^3 at 20 C / 1 atm (gases at STP).
  - Melting / boiling points: Kelvin.
  - Bond enthalpies (kJ/mol): mean values for single covalent bonds.

The module has **zero dependencies** beyond the Python standard library.
It is purely deterministic and intended to be safe to import anywhere
(no I/O, no RNG).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Element dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Element:
    """An entry in the periodic table.

    Properties are at room temperature / 1 atm unless noted. ``density_g_cm3``
    is reported in g/cm^3 (so multiply by 1000 to obtain kg/m^3). Melting and
    boiling points are in Kelvin. ``common_oxidation`` is a tuple of the most
    frequently observed oxidation states (cation positive, anion negative).
    """

    symbol: str
    name: str
    atomic_number: int
    atomic_mass: float
    electronegativity: float
    density_g_cm3: float
    melting_point_K: float
    boiling_point_K: float
    common_oxidation: Tuple[int, ...]
    group: int
    period: int
    category: str


# Category strings used below. Kept loose (plain strings) so that helper
# checks can extend the set without changing a frozen Enum.
_METAL_CATEGORIES = {
    "alkali_metal",
    "alkaline_earth",
    "transition_metal",
    "post_transition_metal",
    "lanthanide",
    "actinide",
}

_METALLOID_CATEGORIES = {"metalloid"}


# ---------------------------------------------------------------------------
# Periodic table (50 most common elements)
# ---------------------------------------------------------------------------
# Electronegativity 0.0 is used as a sentinel for noble gases where the
# Pauling scale is undefined. Densities for gases are at STP.
_ELEMENT_TABLE: Tuple[Element, ...] = (
    # Period 1
    Element("H",  "Hydrogen",     1,   1.008,  2.20, 0.00008988,   13.99,   20.27, (1, -1),   1, 1, "nonmetal"),
    Element("He", "Helium",       2,   4.0026, 0.00, 0.0001785,     0.95,    4.22, (0,),    18, 1, "noble_gas"),

    # Period 2
    Element("Li", "Lithium",      3,   6.94,   0.98, 0.534,        453.65, 1603.0, (1,),     1, 2, "alkali_metal"),
    Element("Be", "Beryllium",    4,   9.0122, 1.57, 1.85,        1560.0,  2742.0, (2,),     2, 2, "alkaline_earth"),
    Element("B",  "Boron",        5,  10.81,   2.04, 2.34,        2349.0,  4200.0, (3,),    13, 2, "metalloid"),
    Element("C",  "Carbon",       6,  12.011,  2.55, 2.267,       3823.0,  4098.0, (4, -4), 14, 2, "nonmetal"),
    Element("N",  "Nitrogen",     7,  14.007,  3.04, 0.0012506,    63.15,   77.36, (-3, 3, 5), 15, 2, "nonmetal"),
    Element("O",  "Oxygen",       8,  15.999,  3.44, 0.001429,     54.36,   90.20, (-2,),   16, 2, "nonmetal"),
    Element("F",  "Fluorine",     9,  18.998,  3.98, 0.001696,     53.53,   85.03, (-1,),   17, 2, "halogen"),
    Element("Ne", "Neon",        10,  20.180,  0.00, 0.0008999,    24.56,   27.07, (0,),    18, 2, "noble_gas"),

    # Period 3
    Element("Na", "Sodium",      11,  22.990,  0.93, 0.971,        370.87, 1156.0, (1,),     1, 3, "alkali_metal"),
    Element("Mg", "Magnesium",   12,  24.305,  1.31, 1.738,        923.0,  1363.0, (2,),     2, 3, "alkaline_earth"),
    Element("Al", "Aluminium",   13,  26.982,  1.61, 2.70,         933.47, 2792.0, (3,),    13, 3, "post_transition_metal"),
    Element("Si", "Silicon",     14,  28.085,  1.90, 2.3296,      1687.0,  3538.0, (4, -4), 14, 3, "metalloid"),
    Element("P",  "Phosphorus",  15,  30.974,  2.19, 1.823,        317.30, 553.65, (-3, 3, 5), 15, 3, "nonmetal"),
    Element("S",  "Sulfur",      16,  32.06,   2.58, 2.07,         388.36, 717.87, (-2, 4, 6), 16, 3, "nonmetal"),
    Element("Cl", "Chlorine",    17,  35.45,   3.16, 0.003214,     171.65, 239.11, (-1, 1, 5, 7), 17, 3, "halogen"),
    Element("Ar", "Argon",       18,  39.948,  0.00, 0.0017837,     83.80,  87.30, (0,),    18, 3, "noble_gas"),
    Element("K",  "Potassium",   19,  39.098,  0.82, 0.862,        336.53, 1032.0, (1,),     1, 4, "alkali_metal"),
    Element("Ca", "Calcium",     20,  40.078,  1.00, 1.54,        1115.0,  1757.0, (2,),     2, 4, "alkaline_earth"),

    # Period 4 transition metals + post-transition
    Element("Ti", "Titanium",    22,  47.867,  1.54, 4.506,       1941.0,  3560.0, (4, 3),   4, 4, "transition_metal"),
    Element("V",  "Vanadium",    23,  50.942,  1.63, 6.0,         2183.0,  3680.0, (5, 4, 3, 2), 5, 4, "transition_metal"),
    Element("Cr", "Chromium",    24,  51.996,  1.66, 7.19,        2180.0,  2944.0, (3, 6, 2), 6, 4, "transition_metal"),
    Element("Mn", "Manganese",   25,  54.938,  1.55, 7.21,        1519.0,  2334.0, (2, 4, 7), 7, 4, "transition_metal"),
    Element("Fe", "Iron",        26,  55.845,  1.83, 7.874,       1811.0,  3134.0, (2, 3),   8, 4, "transition_metal"),
    Element("Co", "Cobalt",      27,  58.933,  1.88, 8.90,        1768.0,  3200.0, (2, 3),   9, 4, "transition_metal"),
    Element("Ni", "Nickel",      28,  58.693,  1.91, 8.908,       1728.0,  3186.0, (2, 3),  10, 4, "transition_metal"),
    Element("Cu", "Copper",      29,  63.546,  1.90, 8.96,        1357.77, 2835.0, (1, 2),  11, 4, "transition_metal"),
    Element("Zn", "Zinc",        30,  65.38,   1.65, 7.14,         692.68, 1180.0, (2,),    12, 4, "transition_metal"),

    # Period 4 / 5 metalloids and halogens
    Element("As", "Arsenic",     33,  74.922,  2.18, 5.727,       1090.0,   887.0, (-3, 3, 5), 15, 4, "metalloid"),
    Element("Br", "Bromine",     35,  79.904,  2.96, 3.1028,       265.95, 332.0, (-1, 1, 5), 17, 4, "halogen"),

    # Period 5 (silver / tin family)
    Element("Ag", "Silver",      47, 107.868,  1.93, 10.49,       1234.93, 2435.0, (1,),    11, 5, "transition_metal"),
    Element("Sn", "Tin",         50, 118.710,  1.96, 7.265,        505.08, 2875.0, (2, 4),  14, 5, "post_transition_metal"),
    Element("I",  "Iodine",      53, 126.904,  2.66, 4.933,        386.85, 457.4,  (-1, 1, 5, 7), 17, 5, "halogen"),
    Element("Xe", "Xenon",       54, 131.293,  2.60, 0.005887,     161.40, 165.03, (0,),    18, 5, "noble_gas"),

    # Period 6 (gold / mercury / lead family) + lanthanides
    Element("Nd", "Neodymium",   60, 144.242,  1.14, 7.01,        1297.0,  3347.0, (3,),     3, 6, "lanthanide"),
    Element("Sm", "Samarium",    62, 150.36,   1.17, 7.52,        1345.0,  2067.0, (2, 3),   3, 6, "lanthanide"),
    Element("W",  "Tungsten",    74, 183.84,   2.36, 19.25,       3695.0,  6203.0, (6, 4),   6, 6, "transition_metal"),
    Element("Pt", "Platinum",    78, 195.084,  2.28, 21.45,       2041.4,  4098.0, (2, 4),  10, 6, "transition_metal"),
    Element("Au", "Gold",        79, 196.967,  2.54, 19.30,       1337.33, 3129.0, (1, 3),  11, 6, "transition_metal"),
    Element("Hg", "Mercury",     80, 200.592,  2.00, 13.534,       234.32, 629.88, (1, 2),  12, 6, "transition_metal"),
    Element("Pb", "Lead",        82, 207.2,    2.33, 11.34,        600.61, 2022.0, (2, 4),  14, 6, "post_transition_metal"),

    # Period 7 (modern / nuclear era)
    Element("U",  "Uranium",     92, 238.029,  1.38, 19.1,        1405.3,  4404.0, (3, 4, 5, 6), 3, 7, "actinide"),
)

# Public index: PERIODIC_TABLE["Fe"] -> Element(...)
PERIODIC_TABLE: Dict[str, Element] = {e.symbol: e for e in _ELEMENT_TABLE}


# ---------------------------------------------------------------------------
# Bond enthalpies (kJ/mol). Stored once per unordered pair.
# ---------------------------------------------------------------------------
def _pair(a: str, b: str) -> Tuple[str, str]:
    """Return a canonical sorted (a, b) tuple used as a dict key."""
    return (a, b) if a <= b else (b, a)


# Single-bond mean enthalpies. Source: standard chemistry handbooks
# (Atkins, Lange's, NIST). When several values are reported, the
# textbook "mean bond energy" is used.
_RAW_BONDS: Dict[Tuple[str, str], float] = {
    # Common diatomic / homonuclear
    _pair("H",  "H"):  432.0,
    _pair("C",  "C"):  347.0,
    _pair("N",  "N"):  167.0,   # single bond; triple N#N is 945
    _pair("O",  "O"):  146.0,   # peroxide-type; O=O double is 498
    _pair("F",  "F"):  155.0,
    _pair("Cl", "Cl"): 240.0,
    _pair("Br", "Br"): 190.0,
    _pair("I",  "I"):  149.0,
    _pair("S",  "S"):  226.0,
    _pair("P",  "P"):  201.0,
    _pair("Si", "Si"): 222.0,

    # Hydrogen-X
    _pair("C",  "H"):  413.0,
    _pair("N",  "H"):  391.0,
    _pair("O",  "H"):  467.0,
    _pair("S",  "H"):  347.0,
    _pair("Si", "H"):  318.0,
    _pair("P",  "H"):  322.0,
    _pair("F",  "H"):  565.0,
    _pair("Cl", "H"):  431.0,
    _pair("Br", "H"):  366.0,
    _pair("I",  "H"):  299.0,

    # Carbon-X
    _pair("C",  "N"):  305.0,
    _pair("C",  "O"):  358.0,
    _pair("C",  "F"):  485.0,
    _pair("C",  "Cl"): 339.0,
    _pair("C",  "Br"): 285.0,
    _pair("C",  "I"):  213.0,
    _pair("C",  "S"):  259.0,
    _pair("C",  "Si"): 318.0,

    # Nitrogen / oxygen mixed
    _pair("N",  "O"):  201.0,
    _pair("N",  "F"):  272.0,
    _pair("N",  "Cl"): 200.0,
    _pair("O",  "F"):  190.0,
    _pair("O",  "Cl"): 203.0,
    _pair("S",  "O"):  522.0,   # S=O average; included for sulphates / oxidation modelling
    _pair("P",  "O"):  335.0,

    # Silicon / oxide chemistry
    _pair("Si", "O"):  452.0,
    _pair("Si", "C"):  318.0,
    _pair("Si", "F"):  565.0,
    _pair("Si", "Cl"): 381.0,

    # Metal-oxide single-bond enthalpies (approximate, drawn from metal-O
    # diatomic / oxide formation enthalpies). Useful for ore reduction.
    _pair("Fe", "O"):  409.0,
    _pair("Al", "O"):  511.0,
    _pair("Cu", "O"):  287.0,
    _pair("Mg", "O"):  377.0,
    _pair("Ca", "O"):  402.0,
    _pair("Ti", "O"):  662.0,
    _pair("Zn", "O"):  284.0,
    _pair("Sn", "O"):  528.0,
    _pair("Pb", "O"):  382.0,
    _pair("Mn", "O"):  362.0,
    _pair("Cr", "O"):  461.0,
    _pair("U",  "O"):  755.0,

    # Salt-like (mostly for electronegativity-difference helpers)
    _pair("Na", "Cl"): 411.0,
    _pair("K",  "Cl"): 425.0,
    _pair("Na", "O"):  270.0,
}

# Public mapping kept for inspection / dump.
BOND_ENERGY: Dict[Tuple[str, str], float] = dict(_RAW_BONDS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def bond_energy(a: str, b: str) -> float:
    """Return the mean single-bond enthalpy of A-B in kJ/mol.

    Returns ``0.0`` if the pair is not in the table. The lookup is symmetric
    (``bond_energy("O", "H") == bond_energy("H", "O")``).
    """
    return float(BOND_ENERGY.get(_pair(a, b), 0.0))


def electronegativity_difference(a: str, b: str) -> float:
    """Absolute electronegativity difference between elements A and B.

    Useful as a rule-of-thumb to classify bonds:
        - < 0.4  -> mostly covalent
        - 0.4 .. 1.7 -> polar covalent
        - > 1.7  -> ionic
    Raises ``KeyError`` if either symbol is unknown.
    """
    ea = PERIODIC_TABLE[a].electronegativity
    eb = PERIODIC_TABLE[b].electronegativity
    return abs(ea - eb)


def is_metal(symbol: str) -> bool:
    """True if the element is classified as a metal in this table."""
    el = PERIODIC_TABLE.get(symbol)
    if el is None:
        return False
    return el.category in _METAL_CATEGORIES


def is_metalloid(symbol: str) -> bool:
    """True if the element is a metalloid (B, Si, As, ...)."""
    el = PERIODIC_TABLE.get(symbol)
    if el is None:
        return False
    return el.category in _METALLOID_CATEGORIES


def is_nonmetal(symbol: str) -> bool:
    """True if the element is a non-metal (H, C, N, O, halogens, noble gases)."""
    el = PERIODIC_TABLE.get(symbol)
    if el is None:
        return False
    return el.category in {"nonmetal", "halogen", "noble_gas"}


def _normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    """Normalise a mass-fraction dict so that the values sum to 1.0.

    Unknown symbols are dropped. Negative entries are clipped to 0. If the
    total mass is zero or no known symbol is present, an empty dict is
    returned.
    """
    cleaned = {
        sym: max(0.0, float(frac))
        for sym, frac in weights.items()
        if sym in PERIODIC_TABLE
    }
    total = sum(cleaned.values())
    if total <= 0.0:
        return {}
    return {sym: frac / total for sym, frac in cleaned.items()}


def density_alloy(weights: Dict[str, float]) -> float:
    """Estimate the density of an alloy from mass fractions.

    The rule used is the inverse rule of mixtures (also called Wilke's
    formula), which is exact for ideal mixing:

        1 / rho_mix = sum_i (w_i / rho_i)

    where ``w_i`` are normalised mass fractions and ``rho_i`` element
    densities (g/cm^3). Returns ``0.0`` on empty / invalid input.
    """
    w = _normalize_weights(weights)
    if not w:
        return 0.0
    inv_rho = 0.0
    for sym, frac in w.items():
        rho_i = PERIODIC_TABLE[sym].density_g_cm3
        if rho_i <= 0.0:
            # Skip phantom densities (noble-gas sentinels etc.)
            continue
        inv_rho += frac / rho_i
    if inv_rho <= 0.0:
        return 0.0
    return 1.0 / inv_rho


def melting_point_estimate(composition: Dict[str, float]) -> float:
    """Estimate the melting point of a mixture by the rule of mixtures.

    Returns a mass-weighted mean of the constituents' melting points (K).
    This is a deliberately simple Vegard's-law style approximation; real
    alloys often exhibit eutectic depressions that this function does not
    capture. Returns ``0.0`` on empty input.
    """
    w = _normalize_weights(composition)
    if not w:
        return 0.0
    return sum(PERIODIC_TABLE[s].melting_point_K * frac for s, frac in w.items())


def molar_mass(composition: Dict[str, float]) -> float:
    """Mass-weighted mean molar mass (g/mol) of a composition."""
    w = _normalize_weights(composition)
    if not w:
        return 0.0
    return sum(PERIODIC_TABLE[s].atomic_mass * frac for s, frac in w.items())


def list_elements_by_category(category: str) -> Tuple[str, ...]:
    """Return symbols of all known elements in a given category."""
    return tuple(sym for sym, el in PERIODIC_TABLE.items() if el.category == category)


__all__ = [
    "Element",
    "PERIODIC_TABLE",
    "BOND_ENERGY",
    "bond_energy",
    "electronegativity_difference",
    "is_metal",
    "is_metalloid",
    "is_nonmetal",
    "density_alloy",
    "melting_point_estimate",
    "molar_mass",
    "list_elements_by_category",
]
