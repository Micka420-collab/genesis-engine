"""Genesis Engine — Substrate capability : affleurements de pierre taillable.

**Règle invariante du projet** (cf. ``surface_mineralization``,
``building_discovery``, ``art_discovery``) : rien n'est scripté. Les agents
ne *savent* pas qu'une pierre est bonne à tailler — ils **VOIENT** un
affleurement (un éclat vitreux d'obsidienne, un galet de silex, une dalle de
basalte) puis décident eux-mêmes d'aller le **débiter**. La découverte est
émergente ; ce module ne fait qu'exposer un **signal physique véridique**.

Pourquoi ce module (et pourquoi ce n'est PAS un observateur)
------------------------------------------------------------
Hier, ``surface_mineralization`` (Cap. C1) a livré la découverte **visuelle
du minerai métallique** (gossan, malachite…) : l'enseigne de l'âge du bronze.
Mais la technologie **plus fondamentale encore** — la pierre taillée de l'âge
de pierre — restait muette : ``engine.geology`` portait bien la lithologie
(``StrataLayer.rock_type``) et les silicates taillables (``obsidian``,
``quartz`` dans ``ore_mix``), mais **aucun signal de surface** ne disait à un
agent *où trouver une pierre qui fait des lames tranchantes*.

Ce module ajoute la capacité manquante : la lecture de l'**affleurement** que
tout tailleur paléolithique sait repérer. Ce n'est pas un ``*_observer.py``
qui *mesure* le tick — c'est un **signal de monde interrogeable** que les
agents *consomment pour agir*. Il n'ajoute **aucun coût au tick** : les
indices sont calculés paresseusement par chunk et mémorisés. Il échappe donc
au moratoire observateurs (`CONTRIBUTING.md` §"Moratoire observateurs") qui
ne vise que les wrappers read-only de ``sim.step``.

Pétrologie de la taille (knapping)
----------------------------------
La qualité d'une pierre à tailler tient à son **mode de fracture** :

* **Conchoïdale** (verre / cryptocristallin) → bords-rasoir, lames, pointes.
  L'``obsidian`` (verre volcanique) est l'étalon ; le **silex / chert**
  (silice cryptocristalline) se forme en **rognons dans les carbonates**
  (craie, calcaire) — on le modélise via ``quartz`` *bonifié* quand un hôte
  carbonaté est présent dans la colonne. Le quartz/quartzite brut est
  taillable mais médiocre (cassant, esquilleux).
* **Tabulaire** (schistosité) → débitage en plaques : grattoirs, lames
  plates. L'``slate`` (ardoise) en est l'archétype.
* **Pierre à percuter / polir** (``GROUND``) → haches polies, meules,
  percuteurs : ``basalt``, ``granite``, ``gneiss``, ``sandstone`` (abrasif).
* **Tendre** (``SOFT``) → taille de gravure mais pas d'arête durable :
  ``limestone``, ``marble``.

Seules les pierres dont la **qualité de taille intrinsèque** dépasse
``MIN_KNAP_QUALITY`` émettent un indice perceptible : la pierre tendre et le
grès de régolithe sont *partout* — nul besoin de les « découvrir ». Le signal
porte donc sur la ressource archéologiquement signifiante (obsidienne, silex)
— celle qui, dans la préhistoire réelle, structure des réseaux d'échange.

Le monde ne ment jamais
-----------------------
Un indice n'est émis QUE si la matière existe réellement, dans la même colonne
``chunk_geology`` que celle que ``mine_at`` exploite :
* source ``"lithology"`` ⇒ une couche peu profonde a ``rock_type == material`` ;
* source ``"ore"`` ⇒ une couche peu profonde a ``material`` dans son ``ore_mix``
  au-dessus du seuil de visibilité.
L'indice porte ``collect_depth_m`` : aller débiter là **rend** cette matière.
La réciproque est volontairement *faible* (absence d'indice ⇏ absence de
pierre) — le socle enfoui sous 200 m de sédiment ne s'affleure pas, et l'agent
doit alors prospecter ailleurs. C'est physiquement honnête et cela préserve
l'émergence (on ne donne pas la carte des gîtes).

Affleurement vs enfouissement
-----------------------------
Le socle igné (granite/basalte) n'**affleure** que là où la couverture est
mince : en altitude, ``engine.geology`` n'empile pas les 195 m de sédiment des
basses terres, donc ``bedrock_top ≈ 5 m`` — il affleure. En plaine il est
enfoui à ~200 m : pas d'indice lithologique, seuls les silicates taillables
des couches superficielles (``ore_mix``) trahissent une source. C'est
exactement la géographie réelle des gîtes de matière première lithique.

Déterminisme
------------
Pur : fonction de ``chunk_geology`` (lui-même ``prf_rng``) + biome. Aucun RNG
nouveau. Bit-identique entre deux runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — l'expression d'affleurement est
une lecture dérivée du substrat géologique, comme ``surface_mineralization``.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape
(chunk → indice), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.geology import chunk_geology, install_geology, StrataLayer
from engine.mineral_catalog import MINERAL_BY_NAME
from engine.world import CHUNK_SIDE_M, world_to_chunk

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

_OCEAN = 0

# A tool-stone outcrop is only perceivable / reachable for surface collection
# down to this depth (m). Bedrock buried deeper does not crop out.
MAX_OUTCROP_DEPTH_M = 6.0

# An ``ore_mix`` flaking-stone fraction must reach this to leave visible float
# (eroded pebbles / glassy chips) on the ground.
MIN_VISIBLE_FRACTION = 0.003

# Below this intrinsic knapping quality the stone is ubiquitous crude material
# (regolith sandstone, soft carbonate) that needs no "discovery": no cue.
MIN_KNAP_QUALITY = 0.40

# Below this biome visibility the outcrop is masked (canopy / snow / water).
VISIBILITY_FLOOR = 0.30

# Cryptocrystalline silica (flint / chert) nucleates as nodules in carbonate
# host rock. When such a host co-occurs, raw ``quartz`` is upgraded to a
# proper flakeable flint by this bonus.
CHERT_BONUS = 0.30
_CARBONATE_HOSTS = frozenset({"limestone", "marble", "dolomite", "calcite"})


class KnapClass(IntEnum):
    """Fracture behaviour governing what tools a stone yields."""
    SOFT = 0        # carves, no durable edge (limestone, marble)
    GROUND = 1      # pecked / ground: axes, hammers, querns (basalt, granite)
    TABULAR = 2     # splits to flat blades / scrapers (slate)
    CONCHOIDAL = 3  # razor blades / points (obsidian, flint, quartzite)


# Outcrop exposure by biome id (cf. engine.mineral_catalog._BIOME). Bedrock
# crops out where soil + canopy are thin; the sea and ice hide it entirely.
_BIOME_VISIBILITY: Dict[int, float] = {
    0: 0.00,   # OCEAN              — underwater
    1: 0.20,   # ICE               — snow/ice cover
    2: 0.85,   # TUNDRA            — bare frost-shattered rock
    3: 0.45,   # BOREAL_FOREST
    4: 0.40,   # TEMPERATE_FOREST
    5: 0.25,   # TEMPERATE_RAINFOREST — dense canopy
    6: 0.70,   # GRASSLAND
    7: 1.00,   # HOT_DESERT        — bare rock, classic outcrops
    8: 0.95,   # COLD_DESERT
    9: 0.75,   # SAVANNA
    10: 0.55,  # TROPICAL_DRY_FOREST
    11: 0.20,  # TROPICAL_RAINFOREST — deep weathering + canopy
}


@dataclass(frozen=True)
class KnapProfile:
    """Intrinsic knapping character of one rock / mineral material."""
    material: str                   # geology id (rock_type or ore mineral name)
    label: str                      # human label of the perceived outcrop
    knap_class: KnapClass
    base_quality: float             # intrinsic edge potential in [0, 1]
    rgb: Tuple[int, int, int]       # perceived colour / luster of the outcrop


# Each known geology material → its knapping profile. ``base_quality`` ranks
# real archaeological preference: obsidian > flint(chert) > quartzite > basalt
# > granite/gneiss/slate ; soft & regolith stone falls below MIN_KNAP_QUALITY.
_PROFILES: Tuple[KnapProfile, ...] = (
    # Conchoidal flakers (come up as ore_mix float OR — for obsidian — exposed).
    KnapProfile("obsidian", "obsidienne (verre volcanique, tranchant rasoir)",
                KnapClass.CONCHOIDAL, 1.00, rgb=(25, 20, 30)),
    KnapProfile("quartz", "quartz / quartzite (galets siliceux)",
                KnapClass.CONCHOIDAL, 0.42, rgb=(225, 220, 215)),
    # Tabular splitters.
    KnapProfile("slate", "ardoise (dalles, grattoirs)",
                KnapClass.TABULAR, 0.40, rgb=(70, 75, 85)),
    KnapProfile("shale", "argilite (friable)",
                KnapClass.TABULAR, 0.18, rgb=(110, 100, 85)),
    # Ground / pecked stone (bedrock outcrops).
    KnapProfile("basalt", "basalte (hache polie, meule)",
                KnapClass.GROUND, 0.45, rgb=(60, 60, 65)),
    KnapProfile("gneiss", "gneiss (percuteur, meule)",
                KnapClass.GROUND, 0.42, rgb=(140, 130, 125)),
    KnapProfile("granite", "granite (percuteur, meule)",
                KnapClass.GROUND, 0.40, rgb=(170, 160, 150)),
    KnapProfile("sandstone", "grès (polissoir, abrasif)",
                KnapClass.GROUND, 0.35, rgb=(200, 175, 130)),
    # Soft carbonate (no durable edge — also flags chert host below).
    KnapProfile("marble", "marbre (gravure tendre)",
                KnapClass.SOFT, 0.20, rgb=(235, 235, 230)),
    KnapProfile("limestone", "calcaire (gravure tendre)",
                KnapClass.SOFT, 0.15, rgb=(205, 200, 185)),
)

# material name → profile (validated at import: every material is a real entry
# of the mineral/rock catalogue, so a cue can always be ground-truthed).
_PROFILE: Dict[str, KnapProfile] = {}
for _p in _PROFILES:
    if _p.material not in MINERAL_BY_NAME:
        raise RuntimeError(
            f"lithic_outcrop: unknown material '{_p.material}' — fix the table.")
    if _p.material in _PROFILE:
        raise RuntimeError(
            f"lithic_outcrop: material '{_p.material}' listed twice.")
    _PROFILE[_p.material] = _p

# Conchoidal flakers that can show up as eroded float in a shallow ``ore_mix``.
_FLAKER_MINERALS: Tuple[str, ...] = tuple(
    m for m, p in _PROFILE.items() if p.knap_class == KnapClass.CONCHOIDAL)


@dataclass(frozen=True)
class LithicCue:
    """A truthful knappable-stone outcrop cue at one chunk.

    ``label``/``rgb``/``knap_class`` = what an agent *perceives*. ``material``
    = the ground truth reachable below (used to resolve collection + prove the
    invariant). It is NOT handed to the agent as "this is obsidian" — the agent
    must learn the stone→edge correlation by acting.
    """
    coord: Tuple[int, int, int]
    material: str                   # ground-truth stone the outcrop yields
    label: str
    knap_class: KnapClass
    knap_quality: float             # intrinsic edge potential in [0, 1]
    rgb: Tuple[int, int, int]
    source: str                     # "lithology" | "ore" — which field proves it
    source_depth_m: float           # depth of the proving layer top (m)
    collect_depth_m: float          # a depth that lands inside the proving layer
    biome: int
    confidence: float               # perceptual confidence in [0, 1]


# ---------------------------------------------------------------------------
# Core derivation — cue from the same geology layers that mining reads.
# ---------------------------------------------------------------------------

def _dominant_biome(chunk) -> int:
    biomes, counts = np.unique(np.asarray(chunk.biome), return_counts=True)
    return int(biomes[int(np.argmax(counts))])


def _has_carbonate_host(layers: List[StrataLayer]) -> bool:
    """True iff the column has a carbonate host (chert/flint can nucleate)."""
    for layer in layers:
        if layer.rock_type in _CARBONATE_HOSTS:
            return True
        for name in layer.ore_mix:
            if name in _CARBONATE_HOSTS:
                return True
    return False


def _material_quality(material: str, carbonate_host: bool) -> float:
    """Intrinsic knapping quality, with the flint/chert upgrade for quartz."""
    prof = _PROFILE[material]
    q = prof.base_quality
    if material == "quartz" and carbonate_host:
        q = min(1.0, q + CHERT_BONUS)   # cryptocrystalline chert / flint
    return q


def _candidates_in_layer(layer: StrataLayer, carbonate_host: bool
                         ) -> List[Tuple[str, str, float]]:
    """All knappable candidates reachable in ``layer``.

    Returns ``(material, source, quality)`` tuples: the layer's own
    ``rock_type`` (source ``"lithology"``) plus any conchoidal flaker present
    in its ``ore_mix`` above the visibility fraction (source ``"ore"``).
    """
    out: List[Tuple[str, str, float]] = []
    rock = layer.rock_type
    if rock in _PROFILE:
        out.append((rock, "lithology", _material_quality(rock, carbonate_host)))
    for name, frac in layer.ore_mix.items():
        if frac < MIN_VISIBLE_FRACTION or name not in _FLAKER_MINERALS:
            continue
        out.append((name, "ore", _material_quality(name, carbonate_host)))
    return out


def _cue_from_geology(coord, layers: List[StrataLayer], biome: int
                     ) -> Optional[LithicCue]:
    """Pure derivation. The single best-knapping outcrop reachable shallow
    wins (highest quality; tie-break shallower, then sharper class, then name).
    """
    visibility = _BIOME_VISIBILITY.get(biome, 0.5)
    if visibility < VISIBILITY_FLOOR:
        return None
    carbonate_host = _has_carbonate_host(layers)
    best: Optional[Tuple[StrataLayer, str, str, float]] = None
    best_key: Optional[Tuple[float, float, int, str]] = None
    for layer in layers:
        if layer.depth_top_m > MAX_OUTCROP_DEPTH_M:
            continue
        for material, source, quality in _candidates_in_layer(layer, carbonate_host):
            if quality < MIN_KNAP_QUALITY:
                continue
            # ranking key: higher quality, then shallower, then sharper class,
            # then material name — fully deterministic.
            key = (-quality, layer.depth_top_m,
                   -int(_PROFILE[material].knap_class), material)
            if best_key is None or key < best_key:
                best_key = key
                best = (layer, material, source, quality)
    if best is None:
        return None
    layer, material, source, quality = best
    prof = _PROFILE[material]
    thickness = max(layer.depth_bottom_m - layer.depth_top_m, 1e-3)
    collect_depth = layer.depth_top_m + min(0.5, 0.5 * thickness)
    confidence = float(min(1.0, visibility * (0.5 + 0.5 * quality)))
    return LithicCue(
        coord=tuple(int(c) for c in coord),
        material=material, label=prof.label, knap_class=prof.knap_class,
        knap_quality=float(quality), rgb=prof.rgb, source=source,
        source_depth_m=float(layer.depth_top_m),
        collect_depth_m=float(collect_depth), biome=int(biome),
        confidence=confidence)


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_lithic_outcrop(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim``.

    Adds **zero** per-tick cost: cues are derived on query and memoised.
    Returns the cache dict (``sim._lithic_cue_cache``).
    """
    install_geology(sim)  # ensure geology state exists
    cache = getattr(sim, "_lithic_cue_cache", None)
    if cache is None:
        cache = {}
        sim._lithic_cue_cache = cache
    return cache


def lithic_cue_for_chunk(sim, coord: Tuple[int, int, int]) -> Optional[LithicCue]:
    """Truthful tool-stone outcrop cue at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, ``chunk_geology(sim, coord)`` has a layer
    at ``collect_depth_m`` whose ``rock_type`` (source ``lithology``) or
    ``ore_mix`` (source ``ore``) carries ``material``.
    """
    coord = tuple(int(c) for c in coord)
    cache = install_lithic_outcrop(sim)
    if coord in cache:
        return cache[coord]
    g = chunk_geology(sim, coord)
    chunk = sim.streamer.cache.get(coord)
    if g is None or chunk is None:
        cache[coord] = None
        return None
    biome = _dominant_biome(chunk)
    cue = _cue_from_geology(coord, g.layers, biome)
    cache[coord] = cue
    return cue


def prospect_toolstone(sim, world_x: float, world_y: float) -> Optional[LithicCue]:
    """What an agent standing at world ``(x, y)`` perceives of the tool-stone
    outcrop at the surface. Returns the cue (luster + truthful target) or None."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return lithic_cue_for_chunk(sim, coord)


def discover_toolstone_by_sight(sim, rows: List[int],
                                perception_radius_m: float = 64.0
                                ) -> Dict[int, List[LithicCue]]:
    """For each agent ``row``, the outcrop cues perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    This is the capability that turns the static, buried tool-stone field into
    a **perceivable, actionable** signal — the agent then *chooses* to knap.
    Deterministic order (by chunk distance then coord).
    """
    out: Dict[int, List[LithicCue]] = {}
    if not rows:
        return out
    install_lithic_outcrop(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], LithicCue]] = []
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
                cue = lithic_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_toolstone_near(sim, row: int, perception_radius_m: float = 128.0
                        ) -> Optional[LithicCue]:
    """The single best knapping outcrop an agent at ``row`` can perceive — the
    actionable pick (highest ``knap_quality``; tie-break nearest then coord).

    This is the stone-age decision support: an agent seeking a cutting edge
    walks to the sharpest stone it can see. A flat / random pick here would be
    an observable refutation of the perception model (obsidian must outrank a
    quern-grade boulder)."""
    cues = discover_toolstone_by_sight(sim, [int(row)], perception_radius_m
                                       ).get(int(row), [])
    if not cues:
        return None
    # cues already distance-sorted; pick max quality, ties keep nearest order.
    return max(cues, key=lambda c: c.knap_quality)


def lithic_cue_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_lithic_outcrop(sim)
    by_class: Dict[str, int] = {}
    by_material: Dict[str, int] = {}
    n_chunks = 0
    n_cued = 0
    best_q = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = lithic_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_cued += 1
        cls = cue.knap_class.name
        by_class[cls] = by_class.get(cls, 0) + 1
        by_material[cue.material] = by_material.get(cue.material, 0) + 1
        best_q = max(best_q, cue.knap_quality)
    return {
        "n_chunks": n_chunks,
        "n_chunks_with_cue": n_cued,
        "cue_rate": round(n_cued / n_chunks, 4) if n_chunks else 0.0,
        "best_knap_quality": round(best_q, 4),
        "by_class": dict(sorted(by_class.items())),
        "by_material": dict(sorted(by_material.items())),
    }


__all__ = [
    "LithicCue", "KnapProfile", "KnapClass",
    "install_lithic_outcrop", "lithic_cue_for_chunk",
    "prospect_toolstone", "discover_toolstone_by_sight",
    "best_toolstone_near", "lithic_cue_summary",
    "MIN_KNAP_QUALITY", "MIN_VISIBLE_FRACTION", "MAX_OUTCROP_DEPTH_M",
    "VISIBILITY_FLOOR", "CHERT_BONUS",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
