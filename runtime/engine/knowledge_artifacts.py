"""Livres, parchemins, tablettes — savoir matérialisé qui persiste.

Quand un agent possède la tech WRITING (et l'inventaire approprié), il peut
écrire un KnowledgeArtifact qui encode une technologie connue, un récit, ou
une carte. L'artefact existe physiquement sur la carte ; un autre agent qui
le trouve et le lit acquiert le savoir encodé.

Les artefacts se dégradent : durabilité décroît à chaque tick, plus vite
sous la pluie / humidité, plus lentement sur tablette de pierre ou
céramique qu'une fibre.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

from engine.materials import MaterialKind
from engine.tech_tree import TechKind


class ArtifactMedium(IntEnum):
    PARCHMENT = 0    # fiber + ink, fragile (durability decay 0.001/tick)
    TABLET = 1       # clay, sturdy (0.0001/tick), heavy
    INSCRIPTION = 2  # stone carving, near-permanent (1e-5/tick)
    CERAMIC = 3      # fired clay tablet, very sturdy


MEDIUM_DECAY = {
    ArtifactMedium.PARCHMENT: 1.0e-3,
    ArtifactMedium.TABLET: 1.0e-4,
    ArtifactMedium.INSCRIPTION: 1.0e-5,
    ArtifactMedium.CERAMIC: 5.0e-5,
}

# Quantity of base material needed to make one artifact (kg).
MEDIUM_COST = {
    ArtifactMedium.PARCHMENT: {MaterialKind.FIBER: 0.5},
    ArtifactMedium.TABLET: {MaterialKind.CLAY: 1.0},
    ArtifactMedium.INSCRIPTION: {MaterialKind.STONE: 2.0},
    ArtifactMedium.CERAMIC: {MaterialKind.CERAMIC: 0.5},
}

# Hours of labor to inscribe/write one artifact.
MEDIUM_LABOR_HOURS = {
    ArtifactMedium.PARCHMENT: 0.3,
    ArtifactMedium.TABLET: 0.5,
    ArtifactMedium.INSCRIPTION: 4.0,
    ArtifactMedium.CERAMIC: 0.8,
}


class KnowledgeKind(IntEnum):
    TECH = 0          # transmet une tech
    STORY = 1         # un récit (mythe, événement marquant)
    MAP = 2           # carte de positions d'eau / nourriture connues
    NAME_LIST = 3     # liste des morts / ancêtres
    LAW = 4           # règle collective acceptée par un groupe
    INVENTION = 5     # description d'un artefact inventé


@dataclass
class KnowledgeArtifact:
    artifact_id: int
    medium: ArtifactMedium
    pos: Tuple[float, float, float]
    author_row: int
    created_tick: int
    kind: KnowledgeKind
    # Contenu encodé (selon kind)
    tech_encoded: Optional[TechKind] = None
    story_text: str = ""              # encodé en pseudo-phonèmes ou structuré
    map_locations: List[Tuple[float, float, str]] = field(default_factory=list)
    name_list: List[str] = field(default_factory=list)
    invention_id: Optional[int] = None
    # Etat physique
    durability: float = 1.0           # 0 -> détruit
    times_read: int = 0
    last_read_tick: int = -1

    def is_destroyed(self) -> bool:
        return self.durability <= 0.0

    def decay_per_tick(self, weather_humidity: float = 0.5) -> float:
        base = MEDIUM_DECAY[self.medium]
        # Humidité augmente la dégradation des médias organiques
        if self.medium in (ArtifactMedium.PARCHMENT,):
            base *= (1.0 + 2.0 * weather_humidity)
        return base


@dataclass
class KnowledgeRegistry:
    """Tous les artefacts de savoir présents dans le monde."""
    artifacts: Dict[int, KnowledgeArtifact] = field(default_factory=dict)
    _next_id: int = 1

    def create(self, medium: ArtifactMedium, pos: Tuple[float, float, float],
               author_row: int, created_tick: int, kind: KnowledgeKind,
               **payload) -> KnowledgeArtifact:
        aid = self._next_id; self._next_id += 1
        ka = KnowledgeArtifact(
            artifact_id=aid, medium=medium, pos=pos, author_row=author_row,
            created_tick=created_tick, kind=kind,
            tech_encoded=payload.get("tech_encoded"),
            story_text=payload.get("story_text", ""),
            map_locations=list(payload.get("map_locations", [])),
            name_list=list(payload.get("name_list", [])),
            invention_id=payload.get("invention_id"),
        )
        self.artifacts[aid] = ka
        return ka

    def near(self, x: float, y: float, max_distance_m: float = 30.0
             ) -> List[KnowledgeArtifact]:
        out = []
        for ka in self.artifacts.values():
            if ka.is_destroyed():
                continue
            dx = ka.pos[0] - x; dy = ka.pos[1] - y
            if dx * dx + dy * dy <= max_distance_m * max_distance_m:
                out.append(ka)
        return out

    def tick_decay(self, current_tick: int, humidity: float = 0.5) -> int:
        """Décroissance par tick ; retourne le nombre d'artefacts détruits."""
        destroyed = 0
        to_remove = []
        for aid, ka in self.artifacts.items():
            ka.durability -= ka.decay_per_tick(humidity)
            if ka.is_destroyed():
                to_remove.append(aid)
                destroyed += 1
        for aid in to_remove:
            del self.artifacts[aid]
        return destroyed

    def read(self, artifact_id: int, reader_row: int, current_tick: int,
             known_techs) -> dict:
        """Un agent lit l'artefact. Retourne le delta de savoir transmis."""
        ka = self.artifacts.get(artifact_id)
        if ka is None or ka.is_destroyed():
            return {"ok": False, "reason": "artifact_missing"}
        ka.times_read += 1
        ka.last_read_tick = current_tick
        # Légère usure à chaque lecture
        ka.durability = max(0.0, ka.durability - 0.005)
        delta = {"ok": True, "kind": int(ka.kind)}
        if ka.kind == KnowledgeKind.TECH and ka.tech_encoded is not None:
            already = bool(known_techs[reader_row, int(ka.tech_encoded)])
            known_techs[reader_row, int(ka.tech_encoded)] = True
            delta["tech_acquired"] = int(ka.tech_encoded)
            delta["already_knew"] = already
        elif ka.kind == KnowledgeKind.MAP:
            delta["map_locations"] = ka.map_locations
        elif ka.kind == KnowledgeKind.NAME_LIST:
            delta["names"] = ka.name_list
        elif ka.kind == KnowledgeKind.STORY:
            delta["story"] = ka.story_text
        elif ka.kind == KnowledgeKind.INVENTION:
            delta["invention_id"] = ka.invention_id
        return delta
