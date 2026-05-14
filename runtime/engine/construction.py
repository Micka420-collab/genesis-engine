"""Structures, construction projects, and recipes.

A Structure is a persistent built object on the world (hut, well, granary, kiln,
furnace). A ConstructionProject is an in-progress build site that collects
materials and labor until it completes into a Structure.

All recipes use real material kinds from engine.materials and rough
historically-grounded labor budgets (in agent-hours).
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

from engine.materials import MaterialKind, MATERIALS


class StructureKind(IntEnum):
    HEARTH = 0      # foyer — fire, light, cooking
    LEAN_TO = 1     # abri rustique — small thermal shelter (cap 2)
    HUT = 2         # hutte — proper shelter (cap 4), reproduction comfort
    WELL = 3        # puits — permanent water source
    GRANARY = 4     # grenier — food preservation
    WORKSHOP = 5    # atelier — enables tool crafting
    KILN = 6        # four ceramique — bake clay -> ceramic; smelt low-temp metals
    FURNACE = 7     # haut fourneau — smelt copper & bronze (1085-1200°C)
    BLOOMERY = 8    # bas fourneau — smelt iron (1200°C+)
    FARM_PLOT = 9   # parcelle agricole — grain cultivation


@dataclass(frozen=True)
class Recipe:
    """Static description of how to build a Structure."""
    structure: StructureKind
    name: str
    materials: Dict[MaterialKind, float]   # kg required of each material
    labor_hours: float                     # total person-hours
    min_builders: int                      # min concurrent builders
    requires_tech: Tuple[int, ...]         # tech IDs (from tech_tree) prerequired
    capacity: int                          # how many agents can shelter here
    radius_m: float                        # effect radius
    # Passive effects per tick on agents within radius:
    thermal_relief: float                  # decrement on thermal drive
    food_decay_factor: float               # multiplier on food spoilage (1.0=normal, 0.0=no decay)
    water_yield_l_tick: float              # water cells refreshed nearby
    grants_water_memory: bool              # auto-add to known_water_locations
    cooking_bonus: float                   # kcal multiplier on FORAGE near hearth
    enables_craft: bool                    # workshop-style: enables tool crafting
    smelting_temp_k: float                 # max temperature this structure can reach


# Recipes — labor hours are walltime-realistic for paleolithic/neolithic builds.
# (Hut figure of ~24 hrs is consistent with ethnographic data for small wooden frames.)
RECIPES: Dict[StructureKind, Recipe] = {
    StructureKind.HEARTH: Recipe(
        structure=StructureKind.HEARTH, name="hearth",
        materials={MaterialKind.STONE: 4.0, MaterialKind.WOOD: 2.0},
        labor_hours=2.0, min_builders=1, requires_tech=(0,),  # FIRE
        capacity=0, radius_m=10.0,
        thermal_relief=0.005, food_decay_factor=1.0,
        water_yield_l_tick=0.0, grants_water_memory=False,
        cooking_bonus=1.4, enables_craft=False, smelting_temp_k=800.0),
    StructureKind.LEAN_TO: Recipe(
        structure=StructureKind.LEAN_TO, name="lean-to",
        materials={MaterialKind.WOOD: 5.0, MaterialKind.FIBER: 2.0},
        labor_hours=1.5, min_builders=1, requires_tech=(),
        capacity=2, radius_m=4.0,
        thermal_relief=0.008, food_decay_factor=1.0,
        water_yield_l_tick=0.0, grants_water_memory=False,
        cooking_bonus=1.0, enables_craft=False, smelting_temp_k=0.0),
    StructureKind.HUT: Recipe(
        structure=StructureKind.HUT, name="hut",
        materials={MaterialKind.WOOD: 15.0, MaterialKind.FIBER: 8.0,
                   MaterialKind.STONE: 4.0},
        labor_hours=24.0, min_builders=2,
        requires_tech=(1,),  # STONE_TOOLS
        capacity=4, radius_m=6.0,
        thermal_relief=0.015, food_decay_factor=1.0,
        water_yield_l_tick=0.0, grants_water_memory=False,
        cooking_bonus=1.0, enables_craft=False, smelting_temp_k=0.0),
    StructureKind.WELL: Recipe(
        structure=StructureKind.WELL, name="well",
        materials={MaterialKind.STONE: 20.0},
        labor_hours=12.0, min_builders=2,
        requires_tech=(1,),  # STONE_TOOLS
        capacity=0, radius_m=20.0,
        thermal_relief=0.0, food_decay_factor=1.0,
        water_yield_l_tick=8.0, grants_water_memory=True,
        cooking_bonus=1.0, enables_craft=False, smelting_temp_k=0.0),
    StructureKind.GRANARY: Recipe(
        structure=StructureKind.GRANARY, name="granary",
        materials={MaterialKind.WOOD: 12.0, MaterialKind.FIBER: 8.0,
                   MaterialKind.CLAY: 4.0},
        labor_hours=16.0, min_builders=2,
        requires_tech=(1, 5),  # STONE_TOOLS + AGRICULTURE
        capacity=0, radius_m=8.0,
        thermal_relief=0.0, food_decay_factor=0.25,
        water_yield_l_tick=0.0, grants_water_memory=False,
        cooking_bonus=1.0, enables_craft=False, smelting_temp_k=0.0),
    StructureKind.WORKSHOP: Recipe(
        structure=StructureKind.WORKSHOP, name="workshop",
        materials={MaterialKind.WOOD: 20.0, MaterialKind.STONE: 10.0,
                   MaterialKind.FIBER: 4.0},
        labor_hours=20.0, min_builders=2,
        requires_tech=(1,),
        capacity=0, radius_m=8.0,
        thermal_relief=0.0, food_decay_factor=1.0,
        water_yield_l_tick=0.0, grants_water_memory=False,
        cooking_bonus=1.0, enables_craft=True, smelting_temp_k=0.0),
    StructureKind.KILN: Recipe(
        structure=StructureKind.KILN, name="kiln",
        materials={MaterialKind.STONE: 25.0, MaterialKind.CLAY: 8.0,
                   MaterialKind.WOOD: 4.0},
        labor_hours=10.0, min_builders=2,
        requires_tech=(6,),  # POTTERY
        capacity=0, radius_m=6.0,
        thermal_relief=0.0, food_decay_factor=1.0,
        water_yield_l_tick=0.0, grants_water_memory=False,
        cooking_bonus=1.0, enables_craft=True, smelting_temp_k=1273.15),  # 1000°C
    StructureKind.FURNACE: Recipe(
        structure=StructureKind.FURNACE, name="furnace",
        materials={MaterialKind.STONE: 50.0, MaterialKind.CLAY: 20.0,
                   MaterialKind.WOOD: 6.0},
        labor_hours=40.0, min_builders=3,
        requires_tech=(8,),  # COPPER_SMELT (knowledge of furnace)
        capacity=0, radius_m=6.0,
        thermal_relief=0.0, food_decay_factor=1.0,
        water_yield_l_tick=0.0, grants_water_memory=False,
        cooking_bonus=1.0, enables_craft=True, smelting_temp_k=1373.15),  # 1100°C
    StructureKind.BLOOMERY: Recipe(
        structure=StructureKind.BLOOMERY, name="bloomery",
        materials={MaterialKind.STONE: 80.0, MaterialKind.CLAY: 40.0,
                   MaterialKind.WOOD: 10.0},
        labor_hours=80.0, min_builders=3,
        requires_tech=(10,),  # IRON_SMELT
        capacity=0, radius_m=6.0,
        thermal_relief=0.0, food_decay_factor=1.0,
        water_yield_l_tick=0.0, grants_water_memory=False,
        cooking_bonus=1.0, enables_craft=True, smelting_temp_k=1573.15),  # 1300°C
    StructureKind.FARM_PLOT: Recipe(
        structure=StructureKind.FARM_PLOT, name="farm_plot",
        materials={MaterialKind.WOOD: 2.0, MaterialKind.FIBER: 1.0,
                   MaterialKind.GRAIN: 0.5},
        labor_hours=6.0, min_builders=1,
        requires_tech=(5,),  # AGRICULTURE
        capacity=0, radius_m=8.0,
        thermal_relief=0.0, food_decay_factor=1.0,
        water_yield_l_tick=0.0, grants_water_memory=False,
        cooking_bonus=1.0, enables_craft=False, smelting_temp_k=0.0),
}


# ---------------------------------------------------------------------------
# Runtime entities
# ---------------------------------------------------------------------------

@dataclass
class Structure:
    """A persistent built object on the world."""
    structure_id: int
    kind: StructureKind
    pos: Tuple[float, float, float]
    built_tick: int
    builders: List[int]                 # rows who participated
    group_id: Optional[int] = None      # if built by a group, propagates
    durability: float = 1.0             # 0..1, decays over time, repaired with materials
    occupants: List[int] = field(default_factory=list)

    @property
    def recipe(self) -> Recipe:
        return RECIPES[self.kind]


@dataclass
class ConstructionProject:
    """An in-progress build site."""
    project_id: int
    kind: StructureKind
    pos: Tuple[float, float, float]
    started_tick: int
    initiator: int                              # row that started it
    materials_needed: Dict[MaterialKind, float] # remaining
    materials_committed: Dict[MaterialKind, float]
    labor_needed: float                         # hours remaining
    labor_committed: float                      # hours done
    builders: List[int] = field(default_factory=list)
    group_id: Optional[int] = None

    @property
    def recipe(self) -> Recipe:
        return RECIPES[self.kind]

    def is_complete(self) -> bool:
        all_materials_in = all(v <= 1e-6 for v in self.materials_needed.values())
        return all_materials_in and self.labor_committed >= self.labor_needed

    def materials_progress(self) -> float:
        """0..1 fraction of materials delivered."""
        r = self.recipe
        total = sum(r.materials.values())
        if total <= 0:
            return 1.0
        delivered = sum(self.materials_committed.values())
        return min(1.0, delivered / total)

    def labor_progress(self) -> float:
        return min(1.0, self.labor_committed / max(self.labor_needed, 1e-6))

    def overall_progress(self) -> float:
        return 0.5 * (self.materials_progress() + self.labor_progress())


# ---------------------------------------------------------------------------
# Registry (held by the Simulation)
# ---------------------------------------------------------------------------

class ConstructionRegistry:
    """Holds active projects + completed structures."""
    def __init__(self):
        self.projects: Dict[int, ConstructionProject] = {}
        self.structures: Dict[int, Structure] = {}
        self._next_project_id: int = 1
        self._next_structure_id: int = 1

    # ---------- projects ----------
    def start_project(self, kind: StructureKind, pos: Tuple[float, float, float],
                      tick: int, initiator: int,
                      group_id: Optional[int] = None) -> ConstructionProject:
        recipe = RECIPES[kind]
        pid = self._next_project_id
        self._next_project_id += 1
        proj = ConstructionProject(
            project_id=pid, kind=kind, pos=pos, started_tick=tick,
            initiator=initiator,
            materials_needed=dict(recipe.materials),
            materials_committed={},
            labor_needed=recipe.labor_hours,
            labor_committed=0.0,
            builders=[initiator],
            group_id=group_id,
        )
        self.projects[pid] = proj
        return proj

    def deliver_material(self, project_id: int, mat: MaterialKind,
                         amount_kg: float) -> float:
        """Commit material to a project. Returns amount actually accepted."""
        proj = self.projects.get(project_id)
        if proj is None:
            return 0.0
        needed = proj.materials_needed.get(mat, 0.0)
        if needed <= 0:
            return 0.0
        delivered = min(amount_kg, needed)
        proj.materials_needed[mat] = needed - delivered
        proj.materials_committed[mat] = proj.materials_committed.get(mat, 0.0) + delivered
        return delivered

    def add_labor(self, project_id: int, hours: float, row: int) -> bool:
        """Add labor; returns True if the project completed this tick."""
        proj = self.projects.get(project_id)
        if proj is None:
            return False
        if not any(v <= 1e-6 for v in proj.materials_needed.values()):
            # Won't actually count labor until all materials are delivered
            pass
        # Allow labor only after at least 50% materials in (you can dig holes
        # before all the stone arrives, etc.)
        if proj.materials_progress() < 0.5:
            return False
        proj.labor_committed += hours
        if row not in proj.builders:
            proj.builders.append(row)
        if proj.is_complete():
            self._complete_project(proj)
            return True
        return False

    def _complete_project(self, proj: ConstructionProject) -> Structure:
        sid = self._next_structure_id
        self._next_structure_id += 1
        struct = Structure(
            structure_id=sid, kind=proj.kind, pos=proj.pos,
            built_tick=proj.started_tick + 1,  # filled by sim at apply time
            builders=list(proj.builders), group_id=proj.group_id,
        )
        self.structures[sid] = struct
        self.projects.pop(proj.project_id, None)
        return struct

    # ---------- queries ----------
    def structures_near(self, x: float, y: float, max_radius_m: float = 30.0
                        ) -> List[Structure]:
        out = []
        for s in self.structures.values():
            dx = s.pos[0] - x; dy = s.pos[1] - y
            if dx * dx + dy * dy <= max_radius_m * max_radius_m:
                out.append(s)
        return out

    def projects_near(self, x: float, y: float, max_radius_m: float = 30.0
                      ) -> List[ConstructionProject]:
        out = []
        for p in self.projects.values():
            dx = p.pos[0] - x; dy = p.pos[1] - y
            if dx * dx + dy * dy <= max_radius_m * max_radius_m:
                out.append(p)
        return out

    def can_satisfy_materials(self, kind: StructureKind,
                              available: Dict[MaterialKind, float]) -> bool:
        recipe = RECIPES[kind]
        for mat, qty in recipe.materials.items():
            if available.get(mat, 0.0) < qty * 0.5:  # need at least half on hand
                return False
        return True
