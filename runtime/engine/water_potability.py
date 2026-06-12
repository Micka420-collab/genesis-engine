"""Genesis Engine — Substrate capability : potabilité de l'eau (Cap. C3).

**Règle invariante du projet** (cf. ``surface_mineralization`` (C1),
``lithic_outcrop`` (C2), ``building_discovery``, ``art_discovery``) : rien
n'est scripté. Un agent ne *sait* pas quelle eau le sustente — il **PERÇOIT**
un signal véridique (le **goût** salé, la **croûte** blanche d'efflorescence
sur un rivage stérile, le miroitement d'une source claire) puis décide
lui-même de boire — ou de cracher. La découverte est émergente ; ce module ne
fait qu'exposer un **signal physique véridique** de salinité.

Pourquoi ce module (et pourquoi ce n'est PAS un observateur)
------------------------------------------------------------
C1 a livré la découverte du **minerai** (gossan/malachite), C2 celle de la
**pierre taillable** (obsidienne/silex). Mais la ressource la **plus
fondamentale de toutes** — l'eau potable, sans laquelle un agent meurt en
~3 jours, avant la faim, avant l'outil — restait **muette d'une façon
physiquement fausse** : ``engine.physiology`` (action ``DRINK``) réduit la
soif pour **n'importe quelle** cellule d'eau, **y compris l'eau de mer**.
Le monde laissait un agent « boire l'océan » et être hydraté. Aucun signal ne
distinguait l'eau douce qui sauve de la saumure qui tue.

Ce module ajoute la capacité manquante : la lecture de la **salinité** que
tout être vivant fait par le goût. Ce n'est pas un ``*_observer.py`` qui
*mesure* le tick — c'est un **signal de monde interrogeable** que les agents
*consomment pour agir*. Il n'ajoute **aucun coût au tick** : les indices sont
calculés paresseusement par chunk et mémorisés. Il échappe donc au moratoire
observateurs (`CONTRIBUTING.md` §"Moratoire observateurs") qui ne vise que les
wrappers read-only de ``sim.step``.

**Perception-seule, pas de sanction comportementale** : on rend la salinité
*perceptible* ; on ne réécrit PAS ``DRINK`` pour refuser l'eau de mer (ce
serait un changement comportemental risqué, hors moratoire). L'agent doit
apprendre la corrélation goût↔hydratation en agissant. C3 rend le mensonge du
monde *visible* ; le corriger côté physiologie est un travail futur honnête.

Échelle de salinité (veille 2026-06-12, WHO/EPA TDS + océanographie)
-------------------------------------------------------------------
* **Eau douce** (fresh)      : < 0.5 ppt  → potable, palatable (EPA TDS
  secondaire < 500 mg/L ; WHO « bon » < 600 mg/L). L'eau « dure » chargée en
  carbonate (calcaire dissous) reste douce mais minéralisée (~0.2–0.45 ppt).
* **Saumâtre** (brackish)    : 0.5 – 30 ppt. Marginalement potable jusqu'à
  ~3 ppt (``POTABLE_MAX_PPT``) ; au-delà, déshydratation nette (> ~5 ppt =
  5000 mg/L de sel = impropre à la consommation régulière).
* **Eau de mer**             : ~35 ppt (``SEAWATER_PPT`` — densité 1025 kg/m³,
  cf. tableau des constantes du prompt). Létale à la consommation.
* **Saumure évaporitique**   : 35 – ~300 ppt : une source qui percole un banc
  de **halite** (sel gemme) peu profond approche la saturation.

Le monde ne ment jamais
-----------------------
Un indice est dérivé de **vérités indépendantes** du substrat — jamais d'un
nombre arbitraire :
* **mer**  ⇐ biome dominant ``OCEAN`` (vérité de biome) ⇒ 35 ppt, non potable ;
* **saumure** ⇐ couche de ``halite`` peu profonde dans ``chunk_geology``
  (la **même** colonne que lit ``mine_at`` / la croûte de sel de C1) ⇒
  ppt ∝ teneur, non potable ;
* **côtier**  ⇐ eau posée au niveau / sous le niveau marin (élévation moyenne
  ≤ ``COASTAL_MARGIN_M``) ⇒ mélange estuarien linéaire 35 → 0 ppt ;
* **douce** ⇐ eau intérieure en altitude, sans halite ⇒ charge dissoute faible
  (dureté carbonatée), potable.

Invariants prouvés (smoke ``p135`` + ``tests/test_water_potability``) :
1. tout indice ⇒ le chunk a de **vraies** cellules d'eau (``water ≥
   WET_CELL_MIN``) : il y a bien de quoi boire là ;
2. indice **potable** ⇒ biome dominant ≠ ``OCEAN`` **et** pas de halite de
   saumure peu profonde **et** ``salinity_ppt ≤ POTABLE_MAX_PPT`` : on ne
   qualifie JAMAIS l'eau de mer / la saumure de potable ;
3. indice **mer** ⇒ biome dominant ``OCEAN`` ; indice **saumure** ⇒ halite peu
   profonde réellement présente.
La réciproque est volontairement *faible* (une eau peut être potable sans
indice si l'agent ne l'a pas encore goûtée) — on ne donne pas la carte des
points d'eau ; l'agent prospecte. C'est honnête et préserve l'émergence.

Périmètre honnête (audit)
-------------------------
* La **nappe phréatique** (groundwater / loi de Darcy du prompt SYSTÈME A)
  n'est PAS modélisée : l'eau est un champ de **surface** (``chunk.water``).
  La salinité d'une source intérieure est donc dérivée de la géologie peu
  profonde, pas d'un solveur d'écoulement souterrain. Piste future =
  hydrologie différentiable (veille D3, δHBV-globe).
* ``drink_at`` est un **aperçu non mutant** (preview) de ce que boire
  donnerait : il ne touche NI ``chunk.water`` NI ``agents.thirst``. La
  consommation réelle reste celle de ``physiology`` (que l'on n'altère pas).

Déterminisme
------------
Pur : fonction de ``chunk.biome`` / ``chunk.height`` / ``chunk.water`` (tous
issus du seed) + ``chunk_geology`` (lui-même ``prf_rng``). Aucun RNG nouveau.
Bit-identique entre deux runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — la salinité perçue est une
lecture dérivée du substrat (biome + géologie + champ d'eau), comme C1/C2.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape
(chunk → indice), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.geology import chunk_geology, install_geology, StrataLayer
from engine.world import Biome, CHUNK_SIDE_M, world_to_chunk

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

_OCEAN = int(Biome.OCEAN)

# A cell must hold at least this much water (litres) to be a drinkable source.
# Mirrors engine.physiology's own "water near a cell" predicate (> 5 L) so a
# cue can only appear where an agent could actually perform DRINK.
WET_CELL_MIN = 5.0

# --- Salinity bands (ppt = g/kg ≈ g/L). Calibrated on WHO/EPA + oceanography
#     (veille 2026-06-12). See module docstring.
FRESH_MAX_PPT = 0.5         # oceanographic freshwater ceiling
POTABLE_MAX_PPT = 3.0       # physiological net-dehydration threshold for drinking
BRACKISH_MAX_PPT = 30.0     # brackish ↔ saline boundary
SEAWATER_PPT = 35.0         # standard seawater (prompt constants table)
BRINE_SAT_PPT = 300.0       # near-saturation evaporitic brine spring

# Fresh water dissolved-solids load: soft (silicate catchment) vs hard
# (carbonate catchment). Both stay below FRESH_MAX_PPT → always potable.
FRESH_SOFT_PPT = 0.05
FRESH_HARD_PPT = 0.40

# A shallow halite bed within this depth (m) leaches into the local water,
# turning surface springs brackish-to-brine.
BRINE_LEACH_DEPTH_M = 8.0
# Minimum halite mass fraction (or rock_type halite) to brine the water.
# Same visibility floor as C1/C2 so the same shallow bed both shows a salt
# crust (C1) and salts the spring (C3) — one truthful substrate, two cues.
HALITE_BRINE_MIN_FRACTION = 0.003
# Halite fraction that maps to full seawater salinity; richer beds → brine.
HALITE_REF_FRACTION = 0.05
# Carbonate host raises fresh-water hardness within this depth (m).
HARDNESS_DEPTH_M = 8.0
# Water sitting at / below this mean elevation (m) mixes marine intrusion
# (estuary). Above it, inland water is fresh unless an evaporite salts it.
COASTAL_MARGIN_M = 3.0

_CARBONATE_HOSTS = frozenset({"limestone", "marble", "dolomite", "calcite"})


class WaterTaste(IntEnum):
    """Perceived gustatory class of a water body (what an agent tastes)."""
    FRESH = 0       # sweet, soft fresh water
    MINERAL = 1     # hard / mineralised but still fresh & potable
    BRACKISH = 2    # noticeably salty; marginal (potable ≤ POTABLE_MAX_PPT)
    SALINE = 3      # strongly salty — not potable
    BRINE = 4       # sea / evaporitic brine — undrinkable


# Perceived surface colour / luster of the water body (RGB). Brine leaves a
# white efflorescence rime (aligned with C1's salt cue rgb (235,235,240)).
_TASTE_RGB: Dict[WaterTaste, Tuple[int, int, int]] = {
    WaterTaste.FRESH:    (55, 110, 165),   # clear blue open water
    WaterTaste.MINERAL:  (70, 130, 150),   # slightly turquoise hard water
    WaterTaste.BRACKISH: (90, 130, 130),   # murky brackish
    WaterTaste.SALINE:   (110, 140, 150),  # dull marine
    WaterTaste.BRINE:    (235, 235, 240),  # white salt crust / efflorescence
}

_TASTE_LABEL: Dict[WaterTaste, str] = {
    WaterTaste.FRESH:    "eau claire (douce, goût sucré)",
    WaterTaste.MINERAL:  "eau minéralisée (dure mais douce)",
    WaterTaste.BRACKISH: "eau saumâtre (légèrement salée)",
    WaterTaste.SALINE:   "eau salée (imbuvable)",
    WaterTaste.BRINE:    "saumure / mer (croûte de sel, létale)",
}


@dataclass(frozen=True)
class WaterCue:
    """A truthful water-potability cue at one chunk.

    ``taste``/``label``/``rgb`` = what an agent *perceives* (sight + taste).
    ``salinity_ppt``/``potable`` = the ground truth it must agree with. It is
    NOT handed to the agent as "this is potable" — the agent learns the
    taste→hydration correlation by drinking (emergence).
    """
    coord: Tuple[int, int, int]
    source: str                 # "sea" | "brine_spring" | "coastal" | "fresh"
    taste: WaterTaste
    label: str
    salinity_ppt: float
    potable: bool
    rgb: Tuple[int, int, int]
    water_litres: float         # max water at the chunk (how much to drink)
    biome: int
    confidence: float           # perceptual confidence in [0, 1]


# ---------------------------------------------------------------------------
# Core derivation — salinity from independent substrate truths.
# ---------------------------------------------------------------------------

def _dominant_biome(biome_arr) -> int:
    biomes, counts = np.unique(np.asarray(biome_arr), return_counts=True)
    return int(biomes[int(np.argmax(counts))])


def _shallow_halite_fraction(layers: List[StrataLayer]) -> float:
    """Max halite content reachable within ``BRINE_LEACH_DEPTH_M`` (rock_type
    halite counts as 1.0). This is the same truth C1's salt crust reads."""
    best = 0.0
    for layer in layers:
        if layer.depth_top_m > BRINE_LEACH_DEPTH_M:
            continue
        frac = float(layer.ore_mix.get("halite", 0.0))
        if layer.rock_type == "halite":
            frac = max(frac, 1.0)
        best = max(best, frac)
    return best


def _carbonate_hardness_ppt(layers: List[StrataLayer]) -> float:
    """Fresh-water dissolved load: hard if a carbonate host is shallow."""
    for layer in layers:
        if layer.depth_top_m > HARDNESS_DEPTH_M:
            continue
        if layer.rock_type in _CARBONATE_HOSTS:
            return FRESH_HARD_PPT
        for name in layer.ore_mix:
            if name in _CARBONATE_HOSTS:
                return FRESH_HARD_PPT
    return FRESH_SOFT_PPT


def _classify_salinity(layers: List[StrataLayer], dom_biome: int,
                       mean_elev_m: float) -> Tuple[float, str]:
    """Return ``(salinity_ppt, source)`` from independent substrate truths.

    Order = strongest evidence first : marine biome, then evaporitic brine,
    then coastal estuary mixing, else fresh inland water.
    """
    if dom_biome == _OCEAN:
        return SEAWATER_PPT, "sea"
    halite = _shallow_halite_fraction(layers)
    if halite >= HALITE_BRINE_MIN_FRACTION:
        ppt = SEAWATER_PPT * (halite / HALITE_REF_FRACTION)
        ppt = max(FRESH_MAX_PPT + 1e-6, min(BRINE_SAT_PPT, ppt))
        return ppt, "brine_spring"
    if mean_elev_m <= COASTAL_MARGIN_M:
        # estuary: fully marine at sea level → fresh at the margin.
        f = min(1.0, max(0.0, mean_elev_m / COASTAL_MARGIN_M))
        ppt = max(_carbonate_hardness_ppt(layers), SEAWATER_PPT * (1.0 - f))
        return ppt, "coastal"
    return _carbonate_hardness_ppt(layers), "fresh"


def _taste_for_ppt(ppt: float) -> WaterTaste:
    if ppt <= FRESH_SOFT_PPT * 4.0:        # ≤ 0.2 ppt
        return WaterTaste.FRESH
    if ppt <= FRESH_MAX_PPT:               # ≤ 0.5 ppt — hard but fresh
        return WaterTaste.MINERAL
    if ppt <= POTABLE_MAX_PPT:             # ≤ 3 ppt — marginal brackish
        return WaterTaste.BRACKISH
    if ppt <= BRACKISH_MAX_PPT:            # ≤ 30 ppt — saline
        return WaterTaste.SALINE
    return WaterTaste.BRINE                # sea / evaporitic brine


def _cue_from_chunk(coord, layers: List[StrataLayer], chunk) -> Optional[WaterCue]:
    """Pure derivation. Returns a cue only where there is real surface water."""
    water = np.asarray(chunk.water)
    w_max = float(water.max()) if water.size else 0.0
    if w_max < WET_CELL_MIN:
        return None  # nothing to drink here → the world is silent (truthful)
    biome_arr = np.asarray(chunk.biome)
    dom_biome = _dominant_biome(biome_arr)
    mean_elev = float(np.mean(np.asarray(chunk.height)))
    ppt, source = _classify_salinity(layers, dom_biome, mean_elev)
    taste = _taste_for_ppt(ppt)
    potable = ppt <= POTABLE_MAX_PPT
    # Visual confidence rises with the fraction of the chunk that is wet
    # (a broad lake / sea is unmistakable; a thin seep is faint).
    wet_frac = float((water >= WET_CELL_MIN).mean()) if water.size else 0.0
    confidence = float(min(1.0, 0.4 + 0.6 * wet_frac))
    return WaterCue(
        coord=tuple(int(c) for c in coord),
        source=source, taste=taste, label=_TASTE_LABEL[taste],
        salinity_ppt=float(round(ppt, 4)), potable=bool(potable),
        rgb=_TASTE_RGB[taste], water_litres=w_max, biome=int(dom_biome),
        confidence=confidence)


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_water_potability(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim``.

    Adds **zero** per-tick cost: cues are derived on query and memoised.
    Returns the cache dict (``sim._water_cue_cache``).
    """
    install_geology(sim)  # ensure geology state exists (for evaporite truth)
    cache = getattr(sim, "_water_cue_cache", None)
    if cache is None:
        cache = {}
        sim._water_cue_cache = cache
    return cache


def water_cue_for_chunk(sim, coord: Tuple[int, int, int]) -> Optional[WaterCue]:
    """Truthful water-potability cue at ``coord`` (or None). Memoised.

    Invariant: a returned cue's ``salinity_ppt`` / ``potable`` agree with the
    chunk's independent biome / geology / water-field truths (proven by the
    smoke + tests). A ``None`` means no perceivable surface water here.
    """
    coord = tuple(int(c) for c in coord)
    cache = install_water_potability(sim)
    if coord in cache:
        return cache[coord]
    chunk = sim.streamer.cache.get(coord)
    if chunk is None:
        cache[coord] = None
        return None
    g = chunk_geology(sim, coord)
    layers = g.layers if g is not None else []
    cue = _cue_from_chunk(coord, layers, chunk)
    cache[coord] = cue
    return cue


def prospect_water(sim, world_x: float, world_y: float) -> Optional[WaterCue]:
    """What an agent at world ``(x, y)`` perceives of the water body here:
    its luster + truthful taste/potability, or None if no water is in sight."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return water_cue_for_chunk(sim, coord)


def drink_at(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of what drinking at ``(x, y)`` yields — the
    ground-truthed outcome the perception cue must agree with.

    Reads the real ``chunk.water`` field that ``physiology.DRINK`` consumes,
    plus the true salinity. Touches NOTHING (no thirst, no water depletion):
    it is the truth oracle, not the action. ``hydrating`` is True only when
    real fresh-enough water is present — i.e. drinking it would actually
    sustain the agent (seawater / brine → False, the lie this cap exposes).
    """
    coord = world_to_chunk(float(world_x), float(world_y))
    chunk = sim.streamer.cache.get(coord)
    if chunk is None:
        return {"water_litres": 0.0, "salinity_ppt": 0.0, "potable": False,
                "hydrating": False, "taste": None, "source": None}
    cue = water_cue_for_chunk(sim, coord)
    water = np.asarray(chunk.water)
    w_max = float(water.max()) if water.size else 0.0
    if cue is None:
        return {"water_litres": w_max, "salinity_ppt": 0.0, "potable": False,
                "hydrating": False, "taste": None, "source": None}
    hydrating = bool(cue.potable and w_max >= WET_CELL_MIN)
    return {"water_litres": w_max, "salinity_ppt": cue.salinity_ppt,
            "potable": cue.potable, "hydrating": hydrating,
            "taste": cue.taste.name, "source": cue.source}


def discover_water_by_sight(sim, rows: List[int],
                            perception_radius_m: float = 96.0
                            ) -> Dict[int, List[WaterCue]]:
    """For each agent ``row``, the water bodies perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    Turns the static water field into a **perceivable, actionable** signal —
    the agent then *chooses* where to drink. Deterministic order (by chunk
    distance then coord)."""
    out: Dict[int, List[WaterCue]] = {}
    if not rows:
        return out
    install_water_potability(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], WaterCue]] = []
        for dy in range(-span, span + 1):
            for dx in range(-span, span + 1):
                coord = (ccx + dx, ccy + dy, ccz)
                if sim.streamer.cache.get(coord) is None:
                    continue
                cx_center = (coord[0] + 0.5) * CHUNK_SIDE_M
                cy_center = (coord[1] + 0.5) * CHUNK_SIDE_M
                d2 = (cx_center - ax) ** 2 + (cy_center - ay) ** 2
                if d2 > r2:
                    continue
                cue = water_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def nearest_potable_water(sim, row: int, perception_radius_m: float = 192.0
                          ) -> Optional[WaterCue]:
    """The nearest **drinkable** water source an agent at ``row`` can perceive
    — the actionable pick when thirsty. Saline / brine bodies are skipped: an
    agent dying of thirst at the sea must walk inland, exactly as in reality.

    Returns None if every perceivable water body is undrinkable (or none is in
    sight) — a physically honest 'no relief here'."""
    cues = discover_water_by_sight(sim, [int(row)], perception_radius_m
                                   ).get(int(row), [])
    for cue in cues:                 # already distance-sorted; first potable wins
        if cue.potable:
            return cue
    return None


def water_cue_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_water_potability(sim)
    by_source: Dict[str, int] = {}
    by_taste: Dict[str, int] = {}
    n_chunks = 0
    n_water = 0
    n_potable = 0
    min_ppt = float("inf")
    max_ppt = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = water_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_water += 1
        if cue.potable:
            n_potable += 1
        by_source[cue.source] = by_source.get(cue.source, 0) + 1
        by_taste[cue.taste.name] = by_taste.get(cue.taste.name, 0) + 1
        min_ppt = min(min_ppt, cue.salinity_ppt)
        max_ppt = max(max_ppt, cue.salinity_ppt)
    return {
        "n_chunks": n_chunks,
        "n_chunks_with_water": n_water,
        "n_potable": n_potable,
        "potable_rate": round(n_potable / n_water, 4) if n_water else 0.0,
        "salinity_ppt_range": [
            round(min_ppt, 4) if n_water else 0.0, round(max_ppt, 4)],
        "by_source": dict(sorted(by_source.items())),
        "by_taste": dict(sorted(by_taste.items())),
    }


__all__ = [
    "WaterCue", "WaterTaste",
    "install_water_potability", "water_cue_for_chunk",
    "prospect_water", "drink_at", "discover_water_by_sight",
    "nearest_potable_water", "water_cue_summary",
    "WET_CELL_MIN", "FRESH_MAX_PPT", "POTABLE_MAX_PPT", "BRACKISH_MAX_PPT",
    "SEAWATER_PPT", "BRINE_SAT_PPT", "BRINE_LEACH_DEPTH_M",
    "HALITE_BRINE_MIN_FRACTION", "COASTAL_MARGIN_M",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
