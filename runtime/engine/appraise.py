"""World and agent appraisal — perceive → appraise → decide.

Scores local viability from chunk physics (water, food, biome, thermal)
without scripting outcomes. Used by cognition and life_emergence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from engine.world import (Biome, biome_habitability, biome_npp, weather_at,
                          world_to_cell, world_to_chunk)


@dataclass(frozen=True)
class CellAppraisal:
    """Viability of one world cell for sustaining life [0, 1]."""
    water: float
    food: float
    thermal: float
    habitability: float
    npp: float

    @property
    def viability(self) -> float:
        """Weighted composite — no hard thresholds, smooth product blend."""
        base = (
            0.28 * self.water
            + 0.28 * self.food
            + 0.18 * self.thermal
            + 0.16 * self.habitability
            + 0.10 * self.npp
        )
        return float(np.clip(base, 0.0, 1.0))


@dataclass
class AgentAppraisal:
    """Appraisal of one agent's life situation at the current tick."""
    row: int
    cell: CellAppraisal
    vitality: float
    life_stage_idx: int  # 0..7 when genome wired, else coarse 0..3
    reproduction_readiness: float  # [0, 1] emergent, not boolean script
    can_seek_mate: bool


def appraise_cell(streamer, x: float, y: float, tick: int,
                  *, drive_accel: int = 1500) -> CellAppraisal:
    """Score one (x, y) location from streamed chunk data."""
    coord = world_to_chunk(x, y)
    chunk = streamer.cache.get(coord)
    if chunk is None:
        return CellAppraisal(0.0, 0.0, 0.0, 0.0, 0.0)

    cx, cy = world_to_cell(x, y, coord)
    h = float(chunk.height[cy, cx])
    if h <= 1.0:
        return CellAppraisal(0.0, 0.0, 0.0, 0.0, 0.0)

    w_local = float(chunk.water[max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3].max(initial=0.0))
    f_local = float(chunk.food_capacity[max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3].mean())
    water_s = float(np.clip(w_local / 80.0, 0.0, 1.0))
    food_s = float(np.clip(f_local / 120.0, 0.0, 1.0))

    base_t = h * -0.0065 + 15.0
    w = weather_at(tick * int(drive_accel), base_t, float(f_local) * 3.0)
    if 5.0 <= w.temp_c <= 32.0:
        thermal_s = 1.0
    else:
        thermal_s = float(np.clip(1.0 - abs(w.temp_c - 18.5) / 35.0, 0.0, 1.0))

    biome = Biome(int(chunk.biome[cy, cx])) if hasattr(chunk, "biome") else Biome.GRASSLAND
    hab = biome_habitability(biome)
    npp = float(np.clip(biome_npp(biome) / 1.2, 0.0, 1.0))
    return CellAppraisal(water_s, food_s, thermal_s, hab, npp)


def appraise_agent(agents, row: int, streamer, tick: int, sim) -> AgentAppraisal:
    """Appraise agent ``row`` — life stage + reproduction readiness from world + body."""
    x = float(agents.pos[row, 0])
    y = float(agents.pos[row, 1])
    cell = appraise_cell(streamer, x, y, tick, drive_accel=int(sim.cfg.drive_accel))

    vitality = float(agents.vitality[row])
    stage_idx = _life_stage_index(agents, row, sim)

    # Emergent reproduction readiness: age curve × health × local world × loneliness inverse
    age_factor = _age_reproduction_factor(agents, row, sim, stage_idx)
    health = float(np.clip(
        (1.0 - agents.hunger[row]) * (1.0 - agents.thirst[row])
        * vitality * (1.0 - agents.injuries[row] * 0.5),
        0.0, 1.0))
    world_factor = cell.viability
    social = float(np.clip(0.35 + agents.extraversion[row] * 0.4
                           - agents.loneliness[row] * 0.25, 0.0, 1.0))
    readiness = float(np.clip(age_factor * health * world_factor * social, 0.0, 1.0))

    # Soft gate: seek mate when readiness exceeds emergent band (not fixed tick count)
    can_seek = readiness >= 0.42 and stage_idx >= 2

    return AgentAppraisal(
        row=row,
        cell=cell,
        vitality=vitality,
        life_stage_idx=stage_idx,
        reproduction_readiness=readiness,
        can_seek_mate=can_seek,
    )


def _life_stage_index(agents, row: int, sim) -> int:
    if getattr(agents, "_genome_attached", False):
        try:
            from engine.genome import current_life_stage
            return int(current_life_stage(agents, row, sim))
        except Exception:
            pass
    accel = max(1, int(sim.cfg.drive_accel))
    lifespan = max(1, int(agents.lifespan_ticks[row]) // accel)
    age = max(0, int(sim.tick) - int(agents.born_tick[row]))
    ratio = age / float(lifespan)
    return min(3, int(ratio * 4))


def _age_reproduction_factor(agents, row: int, sim, stage_idx: int) -> float:
    """Bell-shaped reproductive window from life stage — peaks young-adult."""
    if stage_idx <= 0:
        return 0.05
    if stage_idx == 1:
        return 0.35
    if stage_idx in (2, 3, 4):
        return 1.0
    if stage_idx == 5:
        return 0.75
    if stage_idx == 6:
        return 0.35
    return 0.08


def prebiotic_potential(cell: CellAppraisal) -> float:
    """Accumulation rate for abiogenesis substrate [0, 1] per tick."""
    return float(cell.viability ** 2 * cell.habitability)


__all__ = [
    "CellAppraisal",
    "AgentAppraisal",
    "appraise_cell",
    "appraise_agent",
    "prebiotic_potential",
]
