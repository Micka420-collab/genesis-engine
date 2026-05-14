"""Free-form invention from physical material properties.

Plutôt que de figer des recettes, on définit des FONCTIONS (couper, contenir,
isoler, allumer, fondre) avec des prérequis physiques tirés de materials.py.
Un agent qui détient des matériaux peut tenter de les combiner ; si la
combinaison satisfait une fonction qui n'avait pas encore d'artefact connu,
il invente un nouvel artefact ajouté au registre partagé.

Probabilité d'invention par tick :
    P = base × curiosité × intelligence × (1 - fatigue) × bonus_matériaux

Cela ouvre la voie à des outils que le concepteur n'a pas pré-écrits, à
condition que la physique des matériaux supporte la fonction (un caillou ne
fera jamais un récipient ; du bois ne fera jamais une enclume).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from engine.materials import MATERIALS, Material, MaterialKind


class FunctionKind(IntEnum):
    """Catégories fonctionnelles d'artefacts."""
    CUT = 0          # couper, trancher (outils de chasse, hache)
    STRIKE = 1       # frapper, marteler
    PIERCE = 2       # percer, transpercer (lance, alène)
    CONTAIN = 3      # contenir liquides / aliments (récipient)
    INSULATE = 4     # isoler du froid (habit, couverture)
    IGNITE = 5       # créer du feu (briquet, archet à feu)
    BIND = 6         # lier (corde, sangle)
    GRIND = 7        # broyer, moudre (meule)
    PROJECT = 8      # projeter (arc, fronde, javelot)
    SHELTER = 9      # abriter (déjà couvert par construction, ici pour outils mobiles)


@dataclass(frozen=True)
class FunctionRequirement:
    """Contraintes physiques qu'un matériau doit satisfaire pour servir une fonction.

    Toutes les comparaisons sont 'au moins' sauf indication contraire.
    """
    function: FunctionKind
    min_hardness: float = 0.0       # dureté Mohs minimale
    max_hardness: float = 10.0      # parfois la fonction veut un matériau souple
    min_density_kg_m3: float = 0.0
    max_density_kg_m3: float = 30000.0
    needs_combustible: bool = False
    needs_workable: float = 0.0     # workability minimale [0,1]
    needs_tool_edge: float = 0.0    # tool_score minimal [0,1]


# Cahier des charges fonctionnel (calé sur la science des matériaux).
FUNCTION_REQS: Dict[FunctionKind, FunctionRequirement] = {
    FunctionKind.CUT: FunctionRequirement(
        function=FunctionKind.CUT,
        min_hardness=4.5, needs_tool_edge=0.4),
    FunctionKind.STRIKE: FunctionRequirement(
        function=FunctionKind.STRIKE,
        min_hardness=3.0, min_density_kg_m3=1500.0),
    FunctionKind.PIERCE: FunctionRequirement(
        function=FunctionKind.PIERCE,
        min_hardness=3.5, needs_tool_edge=0.3),
    FunctionKind.CONTAIN: FunctionRequirement(
        function=FunctionKind.CONTAIN,
        needs_workable=0.5, max_density_kg_m3=4000.0),
    FunctionKind.INSULATE: FunctionRequirement(
        function=FunctionKind.INSULATE,
        max_density_kg_m3=1200.0, max_hardness=3.0, needs_workable=0.5),
    FunctionKind.IGNITE: FunctionRequirement(
        function=FunctionKind.IGNITE,
        needs_combustible=True, max_density_kg_m3=900.0),
    FunctionKind.BIND: FunctionRequirement(
        function=FunctionKind.BIND,
        max_density_kg_m3=900.0, max_hardness=1.5, needs_workable=0.8),
    FunctionKind.GRIND: FunctionRequirement(
        function=FunctionKind.GRIND,
        min_hardness=5.0, min_density_kg_m3=2000.0),
    FunctionKind.PROJECT: FunctionRequirement(
        function=FunctionKind.PROJECT,
        min_hardness=2.0, max_density_kg_m3=8000.0),
}


def material_satisfies(material: MaterialKind, function: FunctionKind) -> bool:
    """True si les propriétés du matériau passent le filtre de la fonction."""
    m = MATERIALS[material]
    r = FUNCTION_REQS[function]
    if m.hardness_mohs < r.min_hardness or m.hardness_mohs > r.max_hardness:
        return False
    if m.density_kg_m3 < r.min_density_kg_m3 or m.density_kg_m3 > r.max_density_kg_m3:
        return False
    if r.needs_combustible and not m.combustible:
        return False
    if m.workability < r.needs_workable:
        return False
    if m.tool_score < r.needs_tool_edge:
        return False
    return True


# ---------------------------------------------------------------------------
# Inventions — registre partagé
# ---------------------------------------------------------------------------

@dataclass
class Artifact:
    """Un type d'objet inventé. Persiste dans la culture."""
    artifact_id: int
    name: str                                  # auto-généré
    function: FunctionKind
    primary_material: MaterialKind
    secondary_material: Optional[MaterialKind]
    inventor_row: int
    invented_tick: int
    effectiveness: float                       # 0..1 qualité fonctionnelle


@dataclass
class InventionRegistry:
    """Tous les artefacts inventés au cours de la simulation."""
    artifacts: Dict[int, Artifact] = field(default_factory=dict)
    _next_id: int = 1
    # Index par (function, material) pour éviter les doublons exacts
    known_combos: Set[Tuple[int, int, int]] = field(default_factory=set)
    # Apprentissage par agent : ensemble d'artifact_id connus
    known_by_agent: Dict[int, Set[int]] = field(default_factory=dict)

    def try_invent(self, agent_row: int, has_materials: Dict[MaterialKind, float],
                   curiosity: float, intelligence: float, fatigue: float,
                   tick: int, drive_accel: float, rng) -> Optional[Artifact]:
        """Tente une invention ; retourne l'Artifact si réussite."""
        if intelligence < 0.25 or curiosity < 0.20:
            return None
        if fatigue > 0.90:
            return None
        # Proba de tentative ce tick
        base = 5.0e-5 * curiosity * intelligence * (1.0 - 0.7 * fatigue)
        base *= max(1.0, drive_accel / 100.0)
        if rng.random() > min(1.0, base):
            return None
        # Pick a material in hand
        owned = [m for m, q in has_materials.items() if q >= 0.3]
        if not owned:
            return None
        primary = owned[int(rng.random() * len(owned)) % len(owned)]
        secondary: Optional[MaterialKind] = None
        if len(owned) > 1 and rng.random() < 0.5:
            others = [m for m in owned if m != primary]
            secondary = others[int(rng.random() * len(others)) % len(others)]
        # Pick a function to try
        fn_list = list(FunctionKind)
        function = fn_list[int(rng.random() * len(fn_list)) % len(fn_list)]
        if not material_satisfies(primary, function):
            return None
        combo_key = (int(function), int(primary), int(secondary) if secondary else -1)
        if combo_key in self.known_combos:
            # Reinforces personal knowledge but no new artifact globally
            for art in self.artifacts.values():
                if (art.function == function and art.primary_material == primary
                        and art.secondary_material == secondary):
                    self.known_by_agent.setdefault(agent_row, set()).add(art.artifact_id)
                    return None
            return None
        # New invention!
        self.known_combos.add(combo_key)
        m = MATERIALS[primary]
        # Effectiveness from material properties relative to function reqs
        r = FUNCTION_REQS[function]
        eff = 0.5
        if r.min_hardness > 0:
            eff += 0.3 * min(1.0, (m.hardness_mohs - r.min_hardness) / 4.0)
        if r.needs_tool_edge > 0:
            eff += 0.2 * (m.tool_score - r.needs_tool_edge)
        eff = float(np.clip(eff, 0.1, 1.0))
        sec_name = ("_" + MATERIALS[secondary].name) if secondary else ""
        name = f"{m.name}{sec_name}_{function.name.lower()}"
        art = Artifact(
            artifact_id=self._next_id, name=name, function=function,
            primary_material=primary, secondary_material=secondary,
            inventor_row=agent_row, invented_tick=tick,
            effectiveness=eff,
        )
        self.artifacts[self._next_id] = art
        self._next_id += 1
        self.known_by_agent.setdefault(agent_row, set()).add(art.artifact_id)
        return art

    def transmit(self, from_row: int, to_row: int, rng, prob: float = 0.3) -> int:
        """Transmettre des connaissances d'un agent voyant à un voisin observant.

        Retourne le nombre d'artefacts transmis ce tick.
        """
        src = self.known_by_agent.get(from_row, set())
        dst = self.known_by_agent.setdefault(to_row, set())
        new = src - dst
        if not new:
            return 0
        gained = 0
        for art_id in list(new):
            if rng.random() < prob:
                dst.add(art_id)
                gained += 1
        return gained
