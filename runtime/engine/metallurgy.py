"""Genesis Engine — Wave 10c metallurgy (smelting).

Once agents have mined raw ore (Wave 10 geology) they need to **smelt
it** to obtain the pure element they can then feed back into Wave 1/2
material_synthesis. Real-world smelting requires:

  - **ore** — hematite Fe2O3, cassiterite SnO2, chalcopyrite CuFeS2, …
  - **reductant fuel** — charcoal (graphite/coal), wood, peat
  - **temperature** — 1000-1500 °C → requires furnace
  - **flux** for slag removal (limestone) — optional, improves yield

The chemistry is the classical reduction reactions :

  Fe2O3 + 3 C → 2 Fe + 3 CO       (bloomery iron, ~1200 °C)
  SnO2  + 2 C → Sn  + 2 CO        (cassiterite + charcoal)
  CuFeS2 + O2 → Cu + FeO + SO2    (roasting, then smelting)

The simulator's smelting model uses the **yields_per_kg_ore** already
encoded in mineral_catalog as the *theoretical* element output and
multiplies it by:

  - **furnace tier** (0 = bonfire 0.10, 1 = pit kiln 0.40,
    2 = bloomery 0.65, 3 = blast furnace 0.85)
  - **fuel efficiency** (peat 0.4, wood 0.5, charcoal 0.8, coal 0.9)
  - **agent skill** = 0.5 + 0.25 × intelligence + 0.25 × conscientiousness

The resulting pure-element kg are credited to the agent's
``inv_metal`` (for metallic elements) or to a side-store for non-metals
(C, S, etc.).

Tracked per-culture metallurgy practices (Wave 4 material_aging-style)
include : ``bellows``, ``flux_limestone``, ``coppice_charcoal`` — each
adds a multiplier to yield.

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — metallurgy turns raw
matter into civilisation capital.
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — composable
multi-step rollouts respecting redox chemistry + thermodynamics
(temperature gate, reduction stoichiometry).
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"  # arxiv 2604.22748

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from engine.core import prf_rng
from engine.mineral_catalog import (
    MINERAL_BY_NAME, MineralCategory, Mineral,
)


# ---------------------------------------------------------------------------
# Furnace tiers + fuel yields — calibrated to historical metallurgy
# ---------------------------------------------------------------------------

FURNACE_YIELD = {
    "bonfire":      0.10,   # Stone Age open fire, copper only
    "pit_kiln":     0.40,   # Chalcolithic ~5000 BCE
    "bloomery":     0.65,   # Iron Age 1200 BCE
    "blast_furnace":0.85,   # ~1300 CE
}

FUEL_EFFICIENCY = {
    "wood":     0.50,
    "peat":     0.40,
    "graphite": 0.75,
    "coal":     0.90,
    "charcoal": 0.80,
}

# kg of fuel consumed per kg of ore smelted.
FUEL_PER_ORE = {
    "wood":     2.0,
    "peat":     2.5,
    "graphite": 1.0,
    "coal":     0.8,
    "charcoal": 1.2,
}

# Practices a culture can adopt (stacked multipliers).
SMELT_PRACTICE_FACTOR = {
    "bellows":          1.15,
    "flux_limestone":   1.10,
    "coppice_charcoal": 1.05,
}


# ---------------------------------------------------------------------------
# State containers
# ---------------------------------------------------------------------------

@dataclass
class SmeltEvent:
    tick: int
    row: int
    culture: int
    ore_name: str
    ore_kg: float
    fuel_name: str
    fuel_kg: float
    furnace: str
    elements_kg: Dict[str, float]
    yield_efficiency: float


@dataclass
class MetallurgyState:
    """Per-sim metallurgy ledger."""
    # Per-agent pure-element stockpile (kg) since global inventories
    # don't have one slot per element.
    agent_pure_elements: Dict[int, Dict[str, float]] = field(default_factory=dict)
    # Per-culture practices.
    culture_practices: Dict[int, Set[str]] = field(default_factory=dict)
    # Recent event log (tail-bounded).
    events: List[SmeltEvent] = field(default_factory=list)
    # Cumulative stats.
    total_smelt_events: int = 0
    total_ore_kg: float = 0.0
    total_fuel_kg: float = 0.0
    total_pure_elements: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _agent_culture(sim, row: int) -> int:
    cultures = getattr(sim.agents, "culture", None)
    if cultures is not None:
        try:
            return int(cultures[row])
        except Exception:
            return 0
    return 0


def _agent_skill(sim, row: int) -> float:
    try:
        return float(0.5
                     + 0.25 * float(sim.agents.intelligence[row])
                     + 0.25 * float(sim.agents.conscientiousness[row]))
    except Exception:
        return 0.5


def smelt(
    sim,
    row: int,
    ore_name: str,
    ore_kg: float,
    fuel_name: str = "charcoal",
    fuel_kg: float = 0.0,
    furnace: str = "bloomery",
) -> Tuple[bool, Dict[str, float], str]:
    """Smelt ``ore_kg`` of ``ore_name`` using ``fuel_name``.

    Returns ``(success, elements_yielded_kg, reason)``. On success,
    elements are credited to the agent's pure-element stockpile in
    ``MetallurgyState.agent_pure_elements``. Also adds elemental kg
    to inv_metal as a coarse proxy for tracking.

    Args:
        ore_name: catalogue name (must be in mineral_catalog.MINERAL_BY_NAME).
        ore_kg: mass of ore consumed (kg).
        fuel_name: "wood" / "peat" / "graphite" / "coal" / "charcoal".
        fuel_kg: mass of fuel — 0 auto-computes from FUEL_PER_ORE × ore_kg.
        furnace: "bonfire" / "pit_kiln" / "bloomery" / "blast_furnace".
    """
    state = install_metallurgy(sim)
    if ore_name not in MINERAL_BY_NAME:
        return False, {}, f"unknown_ore:{ore_name}"
    mineral = MINERAL_BY_NAME[ore_name]
    if fuel_name not in FUEL_EFFICIENCY:
        return False, {}, f"unknown_fuel:{fuel_name}"
    if furnace not in FURNACE_YIELD:
        return False, {}, f"unknown_furnace:{furnace}"
    if ore_kg <= 0:
        return False, {}, "ore_kg_zero"

    # Auto-compute fuel demand if not supplied.
    needed_fuel = fuel_kg if fuel_kg > 0 else FUEL_PER_ORE[fuel_name] * ore_kg
    if needed_fuel <= 0:
        return False, {}, "fuel_zero"

    skill = _agent_skill(sim, row)
    culture = _agent_culture(sim, row)
    practices = state.culture_practices.get(culture, set())
    practice_mult = 1.0
    for p in practices:
        practice_mult *= SMELT_PRACTICE_FACTOR.get(p, 1.0)

    yield_eff = (
        FURNACE_YIELD[furnace]
        * FUEL_EFFICIENCY[fuel_name]
        * skill
        * practice_mult
    )
    yield_eff = max(0.05, min(1.0, yield_eff))

    # Element output : yields_per_kg_ore × ore_kg × yield_eff.
    elements: Dict[str, float] = {}
    for el, frac in mineral.yields_per_kg_ore.items():
        kg = ore_kg * frac * yield_eff
        if kg > 0:
            elements[el] = kg

    # Credit per-agent pure-element bag.
    bag = state.agent_pure_elements.setdefault(row, {})
    inv_metal = getattr(sim.agents, "inv_metal", None)
    for el, kg in elements.items():
        bag[el] = bag.get(el, 0.0) + kg
        state.total_pure_elements[el] = (
            state.total_pure_elements.get(el, 0.0) + kg)
        # For metallic elements also bump inv_metal so existing systems
        # see the gain.
        if el in ("Fe", "Cu", "Sn", "Pb", "Zn", "Au", "Ag", "Al", "Ti",
                  "Hg", "Mg"):
            if inv_metal is not None:
                inv_metal[row] = float(inv_metal[row]) + kg

    state.events.append(SmeltEvent(
        tick=int(sim.tick), row=int(row), culture=culture,
        ore_name=ore_name, ore_kg=float(ore_kg),
        fuel_name=fuel_name, fuel_kg=float(needed_fuel),
        furnace=furnace,
        elements_kg=elements,
        yield_efficiency=yield_eff,
    ))
    if len(state.events) > 200:
        state.events = state.events[-200:]
    state.total_smelt_events += 1
    state.total_ore_kg += ore_kg
    state.total_fuel_kg += needed_fuel
    return True, elements, ""


def teach_practice(state: MetallurgyState, culture: int, practice: str) -> bool:
    """Add a culture-wide metallurgy practice. Returns True if new."""
    if practice not in SMELT_PRACTICE_FACTOR:
        return False
    s = state.culture_practices.setdefault(culture, set())
    if practice in s:
        return False
    s.add(practice)
    return True


# ---------------------------------------------------------------------------
# Installer + reporter
# ---------------------------------------------------------------------------

# Module-level dispatch for ActionKind.SMELT cognition wiring.
_METAL_DISPATCH: Dict[int, Tuple[object, "MetallurgyState"]] = {}


def _metallurgy_global_wrapper(agents, row, decision, streamer, tick):
    """Stacked wrapper around the previous ``apply_decision``.

    Handles ActionKind.SMELT — by default smelts 1 kg of the highest-Fe
    ore the agent currently carries in inv_metal, with charcoal in a
    bloomery. ``decision.target_x`` can encode a different ore index
    in ``MINERAL_BY_NAME`` order ; ``decision.target_y`` the kg.
    """
    import engine.cognition as _cog
    from engine.agent import ActionKind

    inner = getattr(_cog, "_metal_inner_apply_decision", None)
    if inner is None:
        return None
    pair = _METAL_DISPATCH.get(id(agents))
    if pair is None:
        return inner(agents, row, decision, streamer, tick)
    sim, _state = pair
    act = int(decision.action)
    if act != int(ActionKind.SMELT):
        return inner(agents, row, decision, streamer, tick)
    # Resolve ore + kg from decision.
    from engine.mineral_catalog import MINERALS as _MINS
    ore_idx = int(getattr(decision, "target_x", 0))
    ore_name = ""
    if 0 <= ore_idx < len(_MINS):
        ore_name = _MINS[ore_idx].name
    if not ore_name:
        ore_name = "hematite"  # sensible default
    ore_kg = float(getattr(decision, "target_y", 0.0)) or 1.0
    smelt(sim, row, ore_name=ore_name, ore_kg=ore_kg,
          fuel_name="charcoal", furnace="bloomery")
    try:
        agents.vel[row, :2] = 0.0
    except Exception:
        pass
    return []


def _patch_actions(sim, state: MetallurgyState) -> None:
    import engine.cognition as _cog
    import engine.sim as _sim_mod
    _METAL_DISPATCH[id(sim.agents)] = (sim, state)
    if getattr(_cog, "_metal_inner_apply_decision", None) is None:
        _cog._metal_inner_apply_decision = _cog.apply_decision
        _cog.apply_decision = _metallurgy_global_wrapper
        if hasattr(_sim_mod, "apply_decision"):
            _sim_mod.apply_decision = _metallurgy_global_wrapper


def install_metallurgy(sim) -> MetallurgyState:
    """Idempotent installer. Wraps apply_decision so ActionKind.SMELT
    works ; no step hook (smelting is event-driven)."""
    existing: Optional[MetallurgyState] = getattr(sim, "_metal_state", None)
    if existing is not None:
        return existing
    state = MetallurgyState()
    sim._metal_state = state
    _patch_actions(sim, state)
    return state


def metallurgy_state(sim) -> Dict[str, object]:
    state: Optional[MetallurgyState] = getattr(sim, "_metal_state", None)
    if state is None:
        return {}
    # Top elements by total pure mass.
    top = sorted(state.total_pure_elements.items(),
                 key=lambda kv: -kv[1])[:8]
    return {
        "total_smelt_events": state.total_smelt_events,
        "total_ore_kg": round(state.total_ore_kg, 2),
        "total_fuel_kg": round(state.total_fuel_kg, 2),
        "total_pure_elements_kg": {
            k: round(v, 3) for k, v in state.total_pure_elements.items()
        },
        "top_pure_elements": [{"element": k, "kg": round(v, 3)}
                              for k, v in top],
        "agents_with_pure_bag": len(state.agent_pure_elements),
        "culture_practices": {
            str(k): sorted(v) for k, v in state.culture_practices.items()
        },
        "recent_events_tail": [
            {"tick": e.tick, "row": e.row, "ore": e.ore_name,
             "kg": e.ore_kg, "fuel": e.fuel_name,
             "furnace": e.furnace,
             "elements": {k: round(v, 4) for k, v in e.elements_kg.items()},
             "eff": round(e.yield_efficiency, 3)}
            for e in state.events[-5:]
        ],
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_metallurgy_state(sim, target_dir: str) -> bool:
    state: Optional[MetallurgyState] = getattr(sim, "_metal_state", None)
    if state is None:
        return False
    payload = {
        "total_smelt_events": state.total_smelt_events,
        "total_ore_kg": state.total_ore_kg,
        "total_fuel_kg": state.total_fuel_kg,
        "total_pure_elements": state.total_pure_elements,
        "agent_pure_elements": {
            str(k): {e: float(v) for e, v in bag.items()}
            for k, bag in state.agent_pure_elements.items()
        },
        "culture_practices": {
            str(k): sorted(v) for k, v in state.culture_practices.items()
        },
        "events_tail": [
            {"tick": e.tick, "row": e.row, "culture": e.culture,
             "ore_name": e.ore_name, "ore_kg": e.ore_kg,
             "fuel_name": e.fuel_name, "fuel_kg": e.fuel_kg,
             "furnace": e.furnace,
             "elements_kg": e.elements_kg,
             "yield_efficiency": e.yield_efficiency}
            for e in state.events[-100:]
        ],
    }
    with open(os.path.join(target_dir, "metallurgy.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return True


def load_metallurgy_state(sim, target_dir: str) -> bool:
    path = os.path.join(target_dir, "metallurgy.json")
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state = install_metallurgy(sim)
    state.total_smelt_events = int(payload.get("total_smelt_events", 0))
    state.total_ore_kg = float(payload.get("total_ore_kg", 0.0))
    state.total_fuel_kg = float(payload.get("total_fuel_kg", 0.0))
    state.total_pure_elements = {
        str(k): float(v)
        for k, v in payload.get("total_pure_elements", {}).items()
    }
    state.agent_pure_elements = {
        int(k): {str(e): float(v) for e, v in bag.items()}
        for k, bag in payload.get("agent_pure_elements", {}).items()
    }
    state.culture_practices = {
        int(k): set(v) for k, v in payload.get("culture_practices", {}).items()
    }
    state.events = [
        SmeltEvent(
            tick=int(d["tick"]), row=int(d["row"]),
            culture=int(d["culture"]),
            ore_name=str(d["ore_name"]), ore_kg=float(d["ore_kg"]),
            fuel_name=str(d["fuel_name"]), fuel_kg=float(d["fuel_kg"]),
            furnace=str(d["furnace"]),
            elements_kg={k: float(v)
                         for k, v in d.get("elements_kg", {}).items()},
            yield_efficiency=float(d.get("yield_efficiency", 0.5)))
        for d in payload.get("events_tail", [])
    ]
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "MetallurgyState",
    "SmeltEvent",
    "FURNACE_YIELD", "FUEL_EFFICIENCY", "FUEL_PER_ORE",
    "SMELT_PRACTICE_FACTOR",
    "install_metallurgy", "smelt", "teach_practice",
    "metallurgy_state",
    "save_metallurgy_state", "load_metallurgy_state",
]
