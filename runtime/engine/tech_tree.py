"""Technology tree — discovery and transmission.

A small DAG of techniques anchored in the real history of human technology:
fire, stone tools, shelter, cooking, agriculture, weaving, pottery,
ceramics, copper smelting, bronze, iron smelting.

Each technology has prerequisites (parent techs) and a difficulty score.
Discovery probability per tick scales with curiosity × intelligence ×
prerequisite_factor × observation_bonus. Agents transmit techs to nearby
agents passively (observation) — colocated agents see what others do.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Tuple


class TechKind(IntEnum):
    FIRE = 0                # discovery of controlled fire
    STONE_TOOLS = 1         # knapped flint axes / hammers
    SHELTER = 2             # lean-tos, then huts
    COOKING = 3             # cooking food (requires FIRE + HEARTH)
    WEAVING = 4             # fiber rope, baskets
    AGRICULTURE = 5         # cultivation of grain
    POTTERY = 6             # hand-formed clay vessels
    CERAMICS = 7            # fired pottery (requires KILN)
    METALLURGY = 8          # copper smelting at 1085°C
    BRONZE = 9              # Cu+Sn alloy
    IRON_SMELT = 10         # bloomery iron at 1200°C
    WHEEL = 11              # wheel and axle
    WRITING = 12             # symbolic record-keeping
    NAVIGATION = 13         # celestial / coastal navigation


@dataclass(frozen=True)
class Tech:
    kind: TechKind
    name: str
    prerequisites: Tuple[TechKind, ...]
    difficulty: float       # 0..1, higher = harder to discover
    era: str                # paleolithic / mesolithic / neolithic / bronze_age / iron_age


# Real-history-anchored tree.
TECHS: Dict[TechKind, Tech] = {
    TechKind.FIRE: Tech(
        kind=TechKind.FIRE, name="fire",
        prerequisites=(), difficulty=0.30, era="paleolithic"),
    TechKind.STONE_TOOLS: Tech(
        kind=TechKind.STONE_TOOLS, name="stone_tools",
        prerequisites=(), difficulty=0.25, era="paleolithic"),
    TechKind.SHELTER: Tech(
        kind=TechKind.SHELTER, name="shelter",
        prerequisites=(TechKind.STONE_TOOLS,), difficulty=0.35,
        era="paleolithic"),
    TechKind.COOKING: Tech(
        kind=TechKind.COOKING, name="cooking",
        prerequisites=(TechKind.FIRE,), difficulty=0.20, era="paleolithic"),
    TechKind.WEAVING: Tech(
        kind=TechKind.WEAVING, name="weaving",
        prerequisites=(TechKind.STONE_TOOLS,), difficulty=0.40, era="mesolithic"),
    TechKind.AGRICULTURE: Tech(
        kind=TechKind.AGRICULTURE, name="agriculture",
        prerequisites=(TechKind.STONE_TOOLS, TechKind.SHELTER),
        difficulty=0.65, era="neolithic"),
    TechKind.POTTERY: Tech(
        kind=TechKind.POTTERY, name="pottery",
        prerequisites=(TechKind.FIRE,), difficulty=0.50, era="neolithic"),
    TechKind.CERAMICS: Tech(
        kind=TechKind.CERAMICS, name="ceramics",
        prerequisites=(TechKind.POTTERY,), difficulty=0.55, era="neolithic"),
    TechKind.METALLURGY: Tech(
        kind=TechKind.METALLURGY, name="metallurgy",
        prerequisites=(TechKind.CERAMICS,), difficulty=0.75, era="bronze_age"),
    TechKind.BRONZE: Tech(
        kind=TechKind.BRONZE, name="bronze",
        prerequisites=(TechKind.METALLURGY,), difficulty=0.80, era="bronze_age"),
    TechKind.IRON_SMELT: Tech(
        kind=TechKind.IRON_SMELT, name="iron_smelt",
        prerequisites=(TechKind.BRONZE,), difficulty=0.85, era="iron_age"),
    TechKind.WHEEL: Tech(
        kind=TechKind.WHEEL, name="wheel",
        prerequisites=(TechKind.STONE_TOOLS,), difficulty=0.65, era="neolithic"),
    TechKind.WRITING: Tech(
        kind=TechKind.WRITING, name="writing",
        prerequisites=(TechKind.AGRICULTURE,), difficulty=0.80, era="bronze_age"),
    TechKind.NAVIGATION: Tech(
        kind=TechKind.NAVIGATION, name="navigation",
        prerequisites=(TechKind.STONE_TOOLS,), difficulty=0.55, era="mesolithic"),
}


NUM_TECHS = len(TECHS)


def all_techs() -> List[Tech]:
    return [TECHS[TechKind(i)] for i in range(NUM_TECHS)]


def can_discover(tech: TechKind, known_mask) -> bool:
    """True if the agent knows all prerequisites of `tech`."""
    prereqs = TECHS[tech].prerequisites
    for p in prereqs:
        if not known_mask[int(p)]:
            return False
    return True


# Discovery rate calibration:
# Base prob per tick = curiosity × intelligence × (1 - difficulty) × 1e-4
# Scaled by `drive_accel` (because each tick covers many seconds of biological
# time). Observation bonus = +5× if a colocated agent already knows the tech.
DISCOVERY_BASE = 1.0e-4
OBSERVATION_BONUS = 5.0


def discovery_probability(curiosity: float, intelligence: float,
                          tech: TechKind, drive_accel: float,
                          observation: bool = False) -> float:
    """Return probability of discovering `tech` this tick."""
    t = TECHS[tech]
    base = DISCOVERY_BASE * curiosity * intelligence * (1.0 - t.difficulty)
    base *= max(1.0, drive_accel / 100.0)
    if observation:
        base *= OBSERVATION_BONUS
    return float(min(1.0, base))


def transmission_probability(curiosity: float, intelligence: float,
                              drive_accel: float) -> float:
    """Per-tick probability that an agent observing a tech-bearer acquires it."""
    base = 5.0e-4 * curiosity * intelligence
    base *= max(1.0, drive_accel / 100.0)
    return float(min(1.0, base))
