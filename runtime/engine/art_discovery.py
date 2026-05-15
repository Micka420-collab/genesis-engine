"""Genesis Engine — Phase 5 / Wave 13 : art (drawing) discovery.

**Règle invariante** : aucun motif, aucun symbole, aucun "alphabet
préhistorique" n'est scripté. L'engine décrit la **physique du
pigment** (qu'est-ce qui marque une surface, qu'est-ce qui adhère,
qu'est-ce qui résiste au temps) et les agents découvrent par eux-mêmes :

1. Ils tiennent un **pigment** : un minéral marqueur (charbon, hématite,
   kaolin, manganèse, graphite, ocre…) extrait par
   :mod:`engine.geology`.
2. Ils tiennent (ou trouvent) une **surface** : roche-mère, paroi de
   grotte (chunk avec bedrock), céramique (matériau aged), cuir.
3. Ils dessinent **N coups** (strokes), chaque coup orienté + longueur.
4. L'engine calcule un **fingerprint** = (pigment, surface, N strokes
   modulo classe, dominant_orientation, closed_shape ?) sans jamais
   demander "est-ce un cheval, un soleil, une lance ?".
5. Le fingerprint devient un **archétype** dans la culture. Si une autre
   culture découvre un fingerprint identique, elle lui donne **son
   propre nom** — comme deux cultures isolées qui appellent un cheval
   stylisé différemment.

Cela imite la préhistoire réelle :
- Lascaux (-17 000) — charbon + hématite sur calcaire.
- Altamira (-36 000) — ocre + manganèse.
- Aboriginal rock art (-40 000) — pigments minéraux multiples.
- Cosquer (-27 000) — main négative au pigment soufflé.

Le module **n'enseigne pas** à un agent ce qu'est un "cheval". Il
enregistre la **forme géométrique** que l'agent a tracée et donne un
nom déterministe issu de la culture. La sémantique reste émergente.

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — culture × pigment × surface.
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — composable
multi-step art rollouts respecting pigment availability + surface
durability.
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from engine.core import prf_rng


# ---------------------------------------------------------------------------
# Calibration — physique du pigment
# ---------------------------------------------------------------------------

# Pigments connus de la science : ceux dont la composition chimique
# permet d'adhérer durablement à une surface minérale. Le **fait**
# qu'un minéral soit un pigment est une propriété physique de la
# matière (oxyde de fer rouge, carbone noir, kaolinite blanche) — pas
# une invention humaine. L'agent doit avoir extrait ce minéral pour
# s'en servir ; l'engine ne lui dit pas qu'il sert à dessiner.
PIGMENT_MINERALS: Dict[str, float] = {
    # mineral_name -> adhesion_factor [0..1] (réalisme historique)
    "hematite": 0.85,    # rouge — Lascaux, Altamira, Aboriginal
    "graphite": 0.75,    # gris-noir — préhistoire européenne
    "manganese": 0.80,   # noir — Altamira
    "kaolin": 0.65,      # blanc — préhistoire africaine
    "ochre": 0.90,       # jaune-rouge — universel
    "limonite": 0.70,    # jaune-brun — variantes ocre
}

# Surfaces minérales/organiques qui acceptent un pigment.
PAINTABLE_SURFACES: Dict[str, float] = {
    "bedrock_calcite":  0.95,  # paroi calcaire — Lascaux
    "bedrock_granite":  0.55,  # moins poreux
    "bedrock_sandstone": 0.80, # Aboriginal
    "ceramic":          0.85,  # poterie peinte
    "leather":          0.45,  # parchemin/cuir
    "wood":             0.40,  # surface bois
}

MIN_STROKES_FOR_ART = 3
MAX_STROKES_BUFFER = 64
MIN_CLOSED_RATIO = 0.30        # fraction de strokes formant boucle pour
                                # qualifier un "closed_shape"

# Orientations canoniques — la **physique** du mouvement humain (pas
# une bibliothèque de "symboles"). Une trace orientée à 0° vs 90° est
# géométriquement différente, indépendamment de toute culture.
ORIENTATIONS = ("E", "NE", "N", "NW", "W", "SW", "S", "SE")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Stroke:
    """Un coup de pigment — pure géométrie, aucun sens."""
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    @property
    def orientation(self) -> str:
        ang = math.degrees(math.atan2(self.y1 - self.y0, self.x1 - self.x0))
        # Snap to 8 cardinal classes.
        idx = int(((ang + 22.5) % 360) // 45) % 8
        return ORIENTATIONS[idx]


@dataclass(frozen=True)
class ArtFingerprint:
    """Empreinte géométrique d'un dessin — aucun nom de figure."""
    pigment: str
    surface: str
    n_strokes_class: int    # bin par puissance de 2 : 3-4, 5-8, 9-16, 17-32
    dominant_orientation: str
    closed: bool

    def short_key(self) -> str:
        return (f"{self.pigment}|{self.surface}|n{self.n_strokes_class}"
                f"|{self.dominant_orientation}|{'c' if self.closed else 'o'}")


@dataclass
class DiscoveredArt:
    art_id: int
    name: str
    archetype_key: str
    culture: int
    artist_row: int
    pigment: str
    surface: str
    n_strokes: int
    durability: float       # adhesion × surface accept
    discovered_tick: int


@dataclass
class ArtDiscoveryState:
    discovered: Dict[int, DiscoveredArt] = field(default_factory=dict)
    next_id: int = 1
    pending_strokes: Dict[int, List[Stroke]] = field(default_factory=dict)
    pending_pigment: Dict[int, str] = field(default_factory=dict)
    pending_surface: Dict[int, str] = field(default_factory=dict)
    cultural_archetypes: Dict[int, Dict[str, int]] = field(default_factory=dict)
    archetype_names: Dict[Tuple[int, str], str] = field(default_factory=dict)
    # Stats.
    rejected_too_few_strokes: int = 0
    rejected_no_pigment: int = 0
    rejected_no_surface: int = 0
    drawings_completed: int = 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install_art_discovery(sim) -> ArtDiscoveryState:
    """Idempotent installer. No tick wrapper — art is event-driven."""
    existing: Optional[ArtDiscoveryState] = getattr(sim, "_art_state", None)
    if existing is not None:
        return existing
    state = ArtDiscoveryState()
    sim._art_state = state
    return state


def begin_drawing(sim, row: int, pigment: str, surface: str) -> Tuple[bool, str]:
    """Commit pigment + surface for an upcoming drawing. Returns (ok, reason)."""
    state = install_art_discovery(sim)
    if pigment not in PIGMENT_MINERALS:
        state.rejected_no_pigment += 1
        return False, f"unknown_pigment:{pigment}"
    if surface not in PAINTABLE_SURFACES:
        state.rejected_no_surface += 1
        return False, f"unknown_surface:{surface}"
    state.pending_pigment[row] = pigment
    state.pending_surface[row] = surface
    state.pending_strokes[row] = []
    return True, ""


def add_stroke(sim, row: int, x0: float, y0: float,
               x1: float, y1: float) -> Tuple[bool, str]:
    """Append one stroke to the row's pending buffer."""
    state = install_art_discovery(sim)
    if row not in state.pending_strokes:
        return False, "no_drawing_in_progress"
    buf = state.pending_strokes[row]
    if len(buf) >= MAX_STROKES_BUFFER:
        return False, "stroke_buffer_full"
    buf.append(Stroke(x0=x0, y0=y0, x1=x1, y1=y1))
    return True, ""


def abandon_drawing(sim, row: int) -> int:
    """Discard the pending buffer for `row`. Returns count of strokes dropped."""
    state = install_art_discovery(sim)
    n = len(state.pending_strokes.pop(row, []))
    state.pending_pigment.pop(row, None)
    state.pending_surface.pop(row, None)
    return n


def _fingerprint(strokes: List[Stroke], pigment: str,
                 surface: str) -> ArtFingerprint:
    """Compute a deterministic fingerprint of the drawing's geometry."""
    n = len(strokes)
    # Class by power-of-2 bin : 3-4, 5-8, 9-16, 17-32, 33-64.
    n_class = 0
    if n >= 33:
        n_class = 5
    elif n >= 17:
        n_class = 4
    elif n >= 9:
        n_class = 3
    elif n >= 5:
        n_class = 2
    else:
        n_class = 1
    # Dominant orientation.
    counts: Dict[str, int] = {}
    for s in strokes:
        counts[s.orientation] = counts.get(s.orientation, 0) + 1
    dom = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
    # Closed shape detection : count strokes whose endpoint is within
    # 1.0 unit of another stroke's startpoint (loop indicator).
    endpoints = [(s.x1, s.y1) for s in strokes]
    starts = [(s.x0, s.y0) for s in strokes]
    closed_count = 0
    for ex, ey in endpoints:
        for sx, sy in starts:
            if abs(ex - sx) < 1.0 and abs(ey - sy) < 1.0:
                closed_count += 1
                break
    closed = closed_count >= max(1, int(MIN_CLOSED_RATIO * n))
    return ArtFingerprint(
        pigment=pigment, surface=surface,
        n_strokes_class=n_class, dominant_orientation=dom,
        closed=closed,
    )


def _auto_name_art(sim, culture: int, fp: ArtFingerprint) -> str:
    """Deterministic name via prf_rng — different cultures, different names."""
    rng = prf_rng(sim.cfg.seed,
                  ["art_discovery", "name", fp.short_key()],
                  [int(culture)])
    consonants = "kmnprstvlh"
    vowels = "aeiou"
    suffix = (consonants[int(rng.random() * len(consonants))]
              + vowels[int(rng.random() * len(vowels))]
              + consonants[int(rng.random() * len(consonants))]
              + vowels[int(rng.random() * len(vowels))])
    closed_tag = "ring" if fp.closed else "line"
    return f"{fp.pigment}_{closed_tag}_{fp.dominant_orientation}_{suffix}"


def _agent_culture(sim, row: int) -> int:
    cultures = getattr(sim.agents, "culture", None)
    if cultures is not None:
        try:
            return int(cultures[row])
        except Exception:
            return 0
    return 0


def complete_drawing(sim, row: int) -> Tuple[bool, Optional[int], str]:
    """Submit the buffered strokes for archetype emergence.

    Returns (success, art_id_or_None, name_or_reason).
    """
    state = install_art_discovery(sim)
    strokes = state.pending_strokes.get(row)
    pigment = state.pending_pigment.get(row)
    surface = state.pending_surface.get(row)
    if strokes is None or pigment is None or surface is None:
        return False, None, "no_drawing_in_progress"
    if len(strokes) < MIN_STROKES_FOR_ART:
        abandon_drawing(sim, row)
        state.rejected_too_few_strokes += 1
        return False, None, "too_few_strokes"
    fp = _fingerprint(strokes, pigment, surface)
    culture = _agent_culture(sim, row)
    key = fp.short_key()
    archetypes = state.cultural_archetypes.setdefault(culture, {})
    if key in archetypes:
        archetypes[key] += 1
        name = state.archetype_names[(culture, key)]
    else:
        archetypes[key] = 1
        name = _auto_name_art(sim, culture, fp)
        state.archetype_names[(culture, key)] = name
    art_id = state.next_id
    state.next_id += 1
    durability = (PIGMENT_MINERALS[pigment]
                  * PAINTABLE_SURFACES[surface])
    state.discovered[art_id] = DiscoveredArt(
        art_id=art_id, name=name, archetype_key=key,
        culture=culture, artist_row=row,
        pigment=pigment, surface=surface,
        n_strokes=len(strokes),
        durability=durability,
        discovered_tick=int(sim.tick),
    )
    state.drawings_completed += 1
    abandon_drawing(sim, row)
    return True, art_id, name


# ---------------------------------------------------------------------------
# Reporter + persistence
# ---------------------------------------------------------------------------

def art_state(sim) -> Dict[str, object]:
    state: Optional[ArtDiscoveryState] = getattr(sim, "_art_state", None)
    if state is None:
        return {}
    return {
        "n_drawings": len(state.discovered),
        "n_cultural_archetypes": sum(
            len(v) for v in state.cultural_archetypes.values()),
        "drawings_completed_total": state.drawings_completed,
        "rejected_too_few_strokes": state.rejected_too_few_strokes,
        "rejected_no_pigment": state.rejected_no_pigment,
        "rejected_no_surface": state.rejected_no_surface,
    }


def save_art_state(sim, target_dir: str) -> bool:
    state: Optional[ArtDiscoveryState] = getattr(sim, "_art_state", None)
    if state is None:
        return False
    payload = {
        "next_id": state.next_id,
        "drawings_completed": state.drawings_completed,
        "rejected_too_few_strokes": state.rejected_too_few_strokes,
        "rejected_no_pigment": state.rejected_no_pigment,
        "rejected_no_surface": state.rejected_no_surface,
        "discovered": [
            {"art_id": d.art_id, "name": d.name,
             "archetype_key": d.archetype_key,
             "culture": d.culture, "artist_row": d.artist_row,
             "pigment": d.pigment, "surface": d.surface,
             "n_strokes": d.n_strokes,
             "durability": d.durability,
             "discovered_tick": d.discovered_tick}
            for d in state.discovered.values()
        ],
        "cultural_archetypes": {
            str(k): dict(v) for k, v in state.cultural_archetypes.items()
        },
        "archetype_names": [
            {"culture": int(c), "key": k, "name": n}
            for (c, k), n in state.archetype_names.items()
        ],
    }
    with open(os.path.join(target_dir, "art.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return True


def load_art_state(sim, target_dir: str) -> bool:
    path = os.path.join(target_dir, "art.json")
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state = install_art_discovery(sim)
    state.next_id = int(payload.get("next_id", 1))
    state.drawings_completed = int(payload.get("drawings_completed", 0))
    state.rejected_too_few_strokes = int(payload.get(
        "rejected_too_few_strokes", 0))
    state.rejected_no_pigment = int(payload.get("rejected_no_pigment", 0))
    state.rejected_no_surface = int(payload.get("rejected_no_surface", 0))
    state.discovered.clear()
    state.cultural_archetypes.clear()
    state.archetype_names.clear()
    for d in payload.get("discovered", []):
        state.discovered[int(d["art_id"])] = DiscoveredArt(
            art_id=int(d["art_id"]), name=str(d["name"]),
            archetype_key=str(d["archetype_key"]),
            culture=int(d["culture"]), artist_row=int(d["artist_row"]),
            pigment=str(d["pigment"]), surface=str(d["surface"]),
            n_strokes=int(d["n_strokes"]),
            durability=float(d["durability"]),
            discovered_tick=int(d["discovered_tick"]),
        )
    for k_str, v in payload.get("cultural_archetypes", {}).items():
        state.cultural_archetypes[int(k_str)] = dict(v)
    for entry in payload.get("archetype_names", []):
        state.archetype_names[(int(entry["culture"]),
                               str(entry["key"]))] = str(entry["name"])
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "PIGMENT_MINERALS",
    "PAINTABLE_SURFACES",
    "MIN_STROKES_FOR_ART",
    "Stroke",
    "ArtFingerprint",
    "DiscoveredArt",
    "ArtDiscoveryState",
    "install_art_discovery",
    "begin_drawing",
    "add_stroke",
    "abandon_drawing",
    "complete_drawing",
    "art_state",
    "save_art_state",
    "load_art_state",
]
