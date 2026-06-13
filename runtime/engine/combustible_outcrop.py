"""Genesis Engine — Substrate capability : affleurement de combustible (Cap. C4).

**Règle invariante du projet** (cf. ``surface_mineralization`` (C1),
``lithic_outcrop`` (C2), ``water_potability`` (C3), ``building_discovery``,
``art_discovery``) : rien n'est scripté. Un agent ne *sait* pas qu'une terre ou
une roche brûle — il **VOIT** une exposition noire et mate (une saignée de
tourbe spongieuse gorgée d'eau, une veine sombre de charbon dans un talus, le
brun-gris d'un schiste bitumineux) puis décide lui-même d'y mettre le feu. La
découverte est émergente ; ce module ne fait qu'exposer un **signal physique
véridique** de combustible.

Pourquoi ce module (et pourquoi ce n'est PAS un observateur)
------------------------------------------------------------
C1 a livré la découverte du **minerai** (gossan/malachite), C2 celle de la
**pierre taillable** (obsidienne/silex), C3 celle de l'**eau potable**
(salinité). Mais toute la branche **ORGANIQUE** de la géologie — ``peat`` /
``coal`` / ``oil_shale`` (catégorie ``MineralCategory.ORGANIC``), déjà semée
dans l'``ore_mix`` des couches par ``engine.geology`` — restait **muette** :
aucun signal de surface ne disait à un agent *où trouver la roche/terre qui
brûle*. Or « la roche noire mate qui brûle longtemps » est l'amorce de la
**révolution énergétique** du prompt (SYSTÈME F) : feu durable → four en argile
+ charbon → température de fusion → métallurgie.

Ce module ajoute la capacité manquante : la lecture de l'**exposition de
combustible** que tout coupeur de tourbe ou mineur de surface sait repérer. Ce
n'est pas un ``*_observer.py`` qui *mesure* le tick — c'est un **signal de monde
interrogeable** que les agents *consomment pour agir*. Il n'ajoute **aucun coût
au tick** : les indices sont calculés paresseusement par chunk et mémorisés. Il
échappe donc au moratoire observateurs (`CONTRIBUTING.md` §"Moratoire
observateurs") qui ne vise que les wrappers read-only de ``sim.step``.

Rang houiller & grade calorifique (veille 2026-06-13, Britannica/KGS)
--------------------------------------------------------------------
La série des combustibles fossiles s'ordonne par **rang** (maturité,
carbone fixe, pouvoir calorifique croissants) :

* **Tourbe** (``peat``) — rang le plus bas. Spongieuse, O/H élevés, humidité
  native > 75 %. Brûle, mais peu et seulement **une fois séchée**. C'est le
  **premier combustible portable** de l'humanité (coupe de tourbe).
* **Schiste bitumineux** (``oil_shale``) — roche fine riche en kérogène, grade
  intermédiaire.
* **Charbon** (``coal``) — veine noire mate mûre, grade le plus haut ici ; seul
  combustible de ce catalogue capable d'atteindre la **température de fusion**
  d'un four (``smelting_grade``). Le tell de surface du charbon est le **noir
  mat** ``(20,20,20)`` — aligné **byte-exact** sur le crate Rust
  ``genesis-geology`` (``Mineral::Coal::surface_color() = [20,20,20]``), miroir
  du tell cuivre/malachite ``(80,140,70)``.

Porte d'humidité — *moisture-of-extinction* (veille 2026-06-13, tourbières)
---------------------------------------------------------------------------
Une tourbière est un milieu **gorgé d'eau** (anoxique, acide) : la tourbe qu'on
y voit ne brûle **pas** tant qu'elle n'est pas **coupée puis séchée** — exactement
le seuil d'humidité d'extinction du modèle de Rothermel (prompt SYSTÈME E). Le
charbon (roche dense, peu hygroscopique) brûle là où il affleure ; la tourbe
(très hygroscopique) impose la boucle émergente **couper → sécher → brûler**.
Le module dérive donc une **humidité ambiante** (biome + champ ``chunk.water``),
pondérée par l'**hygroscopie** intrinsèque du matériau, et expose
``burnable_now`` (sec assez pour tenir un feu) vs ``dry_to_burn`` (bon
combustible mais trop humide ici-maintenant). C'est l'effet 1+1>2 du combo :
la géologie organique (SYSTÈME C) reliée à l'hydrologie de surface (SYSTÈME A).

Le monde ne ment jamais
-----------------------
Un indice n'est émis QUE si le combustible existe réellement, dans la même
colonne ``chunk_geology`` que celle que ``mine_at`` exploite :
* source ``"lithology"`` ⇒ une couche peu profonde a ``rock_type == material`` ;
* source ``"ore"``        ⇒ une couche peu profonde a ``material`` dans son
  ``ore_mix`` au-dessus du seuil de visibilité.
L'indice porte ``collect_depth_m`` : aller couper/creuser là **rend** ce
combustible. ``burnable_now`` ⇒ grade ≥ seuil **et** humidité effective ≤ seuil
d'extinction (toutes deux dérivées du substrat) ; ``smelting_grade`` ⇒ grade ≥
seuil de fusion. La réciproque est volontairement *faible* (absence d'indice ⇏
absence de combustible) — un filon enfoui sous 200 m de sédiment ne trahit rien
en surface, l'agent doit alors prospecter ailleurs. C'est physiquement honnête
et cela préserve l'émergence (on ne donne pas la carte des gîtes).

Différence d'exposition avec C1/C2 (note de conception honnête)
---------------------------------------------------------------
Contrairement au gossan (C1) ou à l'affleurement igné (C2) qui se lisent sur un
**sol nu aride**, une exposition de combustible est un **trait de terrain** :
la tourbière EST visible *parce qu*'elle est un sol ouvert gorgé d'eau (souvent
en milieu forestier/froid), la veine de charbon se lit dans une saignée
d'érosion. On ne masque donc PAS les biomes forestiers ; seul l'**océan** masque
(combustible submergé). Le biome ne fait que moduler la *confiance* perçue.

Déterminisme
------------
Pur : fonction de ``chunk_geology`` (lui-même ``prf_rng``) + biome + champ
``chunk.water`` (issus du seed). Aucun RNG nouveau. Bit-identique entre deux
runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — l'expression de combustible est
une lecture dérivée du substrat géologique (couche organique) + du champ d'eau,
comme C1/C2/C3.
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

# A combustible seam / bog is only perceivable / reachable for surface cutting
# down to this depth (m). Material buried deeper does not crop out.
MAX_SEAM_DEPTH_M = 6.0

# An ``ore_mix`` organic-fuel fraction must reach this to leave a visible dark
# exposure (cut bank / spongy ground) — same floor as C1/C2.
MIN_VISIBLE_FRACTION = 0.003

# Below this intrinsic calorific grade a material cannot sustain a useful fire
# at all (none of the modelled fuels falls below it — peat is the floor).
MIN_FUEL_GRADE = 0.30

# At/above this calorific grade the fuel can drive a kiln to metal-smelting
# temperature (only mature coal here). The emergent tech enabler.
SMELTING_GRADE = 0.70

# Rothermel-style moisture of extinction: above this *effective* moisture the
# fuel will not stay lit. Effective moisture = ambient × hygroscopy.
MOISTURE_EXTINCTION = 0.35

# Surface-water field (litres, chunk mean) that saturates the wetness boost.
WATER_SATURATION_L = 200.0
# Maximum wetness added by standing surface water on top of the biome baseline.
MAX_WATER_BOOST = 0.30


class FuelClass(IntEnum):
    """Combustion-rank class governing what an agent can eventually do with it."""
    PEAT = 0        # spongy immature fuel — lowest grade, very hygroscopic
    OIL_SHALE = 1   # kerogen-rich rock — medium grade
    COAL = 2        # mature black seam — highest grade, smelting-capable


# Ambient ground moisture baseline by biome id (cf. engine.mineral_catalog
# / surface_mineralization). Wet/cold biomes (where bogs form) are damp; deserts
# are dry. OCEAN is masked entirely (submerged).
_BIOME_WETNESS: Dict[int, float] = {
    0: 1.00,   # OCEAN              — submerged (masked anyway)
    1: 0.80,   # ICE               — frozen but saturates on melt
    2: 0.70,   # TUNDRA            — waterlogged active layer / mires
    3: 0.60,   # BOREAL_FOREST     — classic peat-bog + coal-basin terrain
    4: 0.50,   # TEMPERATE_FOREST
    5: 0.90,   # TEMPERATE_RAINFOREST — perpetually wet
    6: 0.35,   # GRASSLAND
    7: 0.05,   # HOT_DESERT        — bone dry
    8: 0.10,   # COLD_DESERT
    9: 0.30,   # SAVANNA
    10: 0.40,  # TROPICAL_DRY_FOREST
    11: 0.95,  # TROPICAL_RAINFOREST
}

# Perceptual confidence modifier by biome (NOT a hard mask — bogs/seams are
# terrain features, visible even under canopy). OCEAN alone masks the cue.
_BIOME_EXPOSURE: Dict[int, float] = {
    0: 0.00,   # OCEAN — masked
    1: 0.55, 2: 0.85, 3: 0.70, 4: 0.65, 5: 0.55, 6: 0.85,
    7: 0.95, 8: 0.90, 9: 0.80, 10: 0.65, 11: 0.45,
}


@dataclass(frozen=True)
class FuelProfile:
    """Intrinsic combustion character of one organic-fuel material."""
    material: str                   # geology id (ore mineral / rock name)
    fuel_class: FuelClass
    label: str                      # human label of the perceived exposure
    rgb: Tuple[int, int, int]       # perceived colour / luster of the exposure
    calorific_grade: float          # intrinsic energy density rank in [0, 1]
    hygroscopy: float               # how strongly it holds water in [0, 1]


# Coal-rank ladder: peat < oil_shale < coal (calorific_grade ascending).
# ``coal`` rgb (20,20,20) is byte-exact with Rust ``Mineral::Coal`` (the tell an
# agent learns to seek for a furnace). Peat is very hygroscopic (a wet bog won't
# burn until cut & dried); coal is a dense, barely hygroscopic rock.
_PROFILES: Tuple[FuelProfile, ...] = (
    FuelProfile("coal", FuelClass.COAL,
                "veine noire mate (charbon — brule tres longtemps, tres chaud)",
                rgb=(20, 20, 20), calorific_grade=0.85, hygroscopy=0.25),
    FuelProfile("oil_shale", FuelClass.OIL_SHALE,
                "schiste brun-gris bitumineux (brule en fumant)",
                rgb=(95, 85, 70), calorific_grade=0.55, hygroscopy=0.40),
    FuelProfile("peat", FuelClass.PEAT,
                "tourbe noire spongieuse (gorgee d'eau — secher avant de bruler)",
                rgb=(60, 45, 35), calorific_grade=0.35, hygroscopy=1.00),
)

# material name → profile (validated at import: every material is a real entry
# of the mineral catalogue, so a cue can always be ground-truthed).
_PROFILE: Dict[str, FuelProfile] = {}
for _p in _PROFILES:
    if _p.material not in MINERAL_BY_NAME:
        raise RuntimeError(
            f"combustible_outcrop: unknown material '{_p.material}' — fix table.")
    if _p.material in _PROFILE:
        raise RuntimeError(
            f"combustible_outcrop: material '{_p.material}' listed twice.")
    _PROFILE[_p.material] = _p


@dataclass(frozen=True)
class FuelCue:
    """A truthful combustible-outcrop cue at one chunk.

    ``label``/``rgb``/``fuel_class`` = what an agent *perceives*. ``material`` =
    the ground truth reachable below (used to resolve collection + prove the
    invariant). It is NOT handed to the agent as "this is coal" — the agent must
    learn the dark-matte→fire and dry→burns correlations by acting.
    """
    coord: Tuple[int, int, int]
    material: str                   # ground-truth fuel the exposure yields
    fuel_class: FuelClass
    label: str
    rgb: Tuple[int, int, int]
    calorific_grade: float          # intrinsic energy density rank in [0, 1]
    source: str                     # "lithology" | "ore" — which field proves it
    source_depth_m: float           # depth of the proving layer top (m)
    collect_depth_m: float          # a depth that lands inside the proving layer
    ambient_moisture: float         # site wetness in [0, 1] (biome + water)
    effective_moisture: float       # ambient × hygroscopy in [0, 1]
    burnable_now: bool              # grade ok AND dry enough to stay lit
    dry_to_burn: bool               # good fuel but too wet now → cut & dry first
    smelting_grade: bool            # grade high enough to reach a furnace temp
    biome: int
    confidence: float               # perceptual confidence in [0, 1]


# ---------------------------------------------------------------------------
# Core derivation — cue from the same geology layers that mining reads.
# ---------------------------------------------------------------------------

def _dominant_biome(chunk) -> int:
    biomes, counts = np.unique(np.asarray(chunk.biome), return_counts=True)
    return int(biomes[int(np.argmax(counts))])


def _ambient_moisture(biome: int, chunk) -> float:
    """Site wetness in [0,1]: biome baseline + standing surface-water boost."""
    base = _BIOME_WETNESS.get(biome, 0.4)
    water = np.asarray(getattr(chunk, "water", None)) if hasattr(chunk, "water") else None
    boost = 0.0
    if water is not None and water.size:
        mean_w = float(water.mean())
        boost = MAX_WATER_BOOST * min(1.0, mean_w / WATER_SATURATION_L)
    return float(min(1.0, max(0.0, base + boost)))


def _candidates_in_layer(layer: StrataLayer) -> List[Tuple[str, str]]:
    """All organic-fuel candidates reachable in ``layer``.

    Returns ``(material, source)`` tuples: the layer's own ``rock_type``
    (source ``"lithology"`` — e.g. a coal seam as bedrock) plus any fuel present
    in its ``ore_mix`` above the visibility fraction (source ``"ore"``).
    """
    out: List[Tuple[str, str]] = []
    rock = layer.rock_type
    if rock in _PROFILE:
        out.append((rock, "lithology"))
    for name, frac in layer.ore_mix.items():
        if frac < MIN_VISIBLE_FRACTION or name not in _PROFILE:
            continue
        if name == rock:
            continue  # already counted as lithology
        out.append((name, "ore"))
    return out


def _cue_from_geology(coord, layers: List[StrataLayer], biome: int, chunk
                      ) -> Optional[FuelCue]:
    """Pure derivation. The highest-grade fuel reachable shallow wins (then
    shallower, then class, then name — fully deterministic)."""
    if biome == _OCEAN:
        return None  # submerged: the exposure is masked
    best: Optional[Tuple[StrataLayer, str, str]] = None
    best_key: Optional[Tuple[float, float, int, str]] = None
    for layer in layers:
        if layer.depth_top_m > MAX_SEAM_DEPTH_M:
            continue
        for material, source in _candidates_in_layer(layer):
            prof = _PROFILE[material]
            key = (-prof.calorific_grade, layer.depth_top_m,
                   -int(prof.fuel_class), material)
            if best_key is None or key < best_key:
                best_key = key
                best = (layer, material, source)
    if best is None:
        return None
    layer, material, source = best
    prof = _PROFILE[material]
    thickness = max(layer.depth_bottom_m - layer.depth_top_m, 1e-3)
    collect_depth = layer.depth_top_m + min(0.5, 0.5 * thickness)
    ambient = _ambient_moisture(biome, chunk)
    effective = float(min(1.0, ambient * prof.hygroscopy))
    burnable_now = bool(prof.calorific_grade >= MIN_FUEL_GRADE
                        and effective <= MOISTURE_EXTINCTION)
    dry_to_burn = bool(prof.calorific_grade >= MIN_FUEL_GRADE
                       and not burnable_now)
    smelting = bool(prof.calorific_grade >= SMELTING_GRADE)
    exposure = _BIOME_EXPOSURE.get(biome, 0.5)
    confidence = float(min(1.0, exposure * (0.4 + 0.6 * prof.calorific_grade)))
    return FuelCue(
        coord=tuple(int(c) for c in coord),
        material=material, fuel_class=prof.fuel_class, label=prof.label,
        rgb=prof.rgb, calorific_grade=float(prof.calorific_grade),
        source=source, source_depth_m=float(layer.depth_top_m),
        collect_depth_m=float(collect_depth),
        ambient_moisture=float(round(ambient, 4)),
        effective_moisture=float(round(effective, 4)),
        burnable_now=burnable_now, dry_to_burn=dry_to_burn,
        smelting_grade=smelting, biome=int(biome), confidence=confidence)


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_combustible_outcrop(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim``.

    Adds **zero** per-tick cost: cues are derived on query and memoised.
    Returns the cache dict (``sim._combustible_cue_cache``).
    """
    install_geology(sim)  # ensure geology state exists
    cache = getattr(sim, "_combustible_cue_cache", None)
    if cache is None:
        cache = {}
        sim._combustible_cue_cache = cache
    return cache


def combustible_cue_for_chunk(sim, coord: Tuple[int, int, int]) -> Optional[FuelCue]:
    """Truthful combustible-outcrop cue at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, ``chunk_geology(sim, coord)`` has a layer
    at ``collect_depth_m`` whose ``rock_type`` (source ``lithology``) or
    ``ore_mix`` (source ``ore``) carries ``material``.
    """
    coord = tuple(int(c) for c in coord)
    cache = install_combustible_outcrop(sim)
    if coord in cache:
        return cache[coord]
    g = chunk_geology(sim, coord)
    chunk = sim.streamer.cache.get(coord)
    if g is None or chunk is None:
        cache[coord] = None
        return None
    biome = _dominant_biome(chunk)
    cue = _cue_from_geology(coord, g.layers, biome, chunk)
    cache[coord] = cue
    return cue


def prospect_fuel(sim, world_x: float, world_y: float) -> Optional[FuelCue]:
    """What an agent standing at world ``(x, y)`` perceives of the combustible
    exposure at the surface. Returns the cue (luster + truthful target) or None."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return combustible_cue_for_chunk(sim, coord)


def ignite_preview(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of what burning the fuel at ``(x, y)`` yields —
    the ground-truthed outcome the perception cue must agree with.

    Touches NOTHING (no fire started, no geology mutated): it is the truth
    oracle, not the action. ``sustains_fire`` is True only when a real,
    dry-enough, sufficient-grade fuel is present here — i.e. lighting it would
    actually keep burning. A wet peat bog returns ``sustains_fire=False`` with
    ``dry_to_burn=True`` (the lie this cap exposes: it looks burnable, but it
    must be cut & dried first)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = combustible_cue_for_chunk(sim, coord)
    if cue is None:
        return {"material": None, "fuel_class": None, "calorific_grade": 0.0,
                "sustains_fire": False, "dry_to_burn": False,
                "smelting_grade": False, "effective_moisture": 0.0}
    return {"material": cue.material, "fuel_class": cue.fuel_class.name,
            "calorific_grade": cue.calorific_grade,
            "sustains_fire": cue.burnable_now, "dry_to_burn": cue.dry_to_burn,
            "smelting_grade": cue.smelting_grade,
            "effective_moisture": cue.effective_moisture}


def discover_fuel_by_sight(sim, rows: List[int],
                           perception_radius_m: float = 64.0
                           ) -> Dict[int, List[FuelCue]]:
    """For each agent ``row``, the combustible exposures perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    This is the capability that turns the static, buried organic-fuel field into
    a **perceivable, actionable** signal — the agent then *chooses* to gather +
    burn. Deterministic order (by chunk distance then coord).
    """
    out: Dict[int, List[FuelCue]] = {}
    if not rows:
        return out
    install_combustible_outcrop(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], FuelCue]] = []
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
                cue = combustible_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_fuel_near(sim, row: int, perception_radius_m: float = 128.0,
                   *, require_burnable: bool = False,
                   require_smelting: bool = False) -> Optional[FuelCue]:
    """The best combustible exposure an agent at ``row`` can perceive — the
    actionable pick (highest ``calorific_grade``; tie-break nearest then coord).

    ``require_burnable`` skips fuel too wet to light right now (forcing the agent
    to either pick a drier source or cut+dry the bog). ``require_smelting`` keeps
    only furnace-grade fuel (mature coal) — the pick when an agent seeks
    metal-melting heat. Returns None when nothing matching is in sight (a
    physically honest 'no fuel here')."""
    cues = discover_fuel_by_sight(sim, [int(row)], perception_radius_m
                                  ).get(int(row), [])
    pool = cues
    if require_smelting:
        pool = [c for c in pool if c.smelting_grade]
    if require_burnable:
        pool = [c for c in pool if c.burnable_now]
    if not pool:
        return None
    # already distance-sorted; pick max grade, ties keep nearest order.
    return max(pool, key=lambda c: c.calorific_grade)


def combustible_cue_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_combustible_outcrop(sim)
    by_class: Dict[str, int] = {}
    by_material: Dict[str, int] = {}
    n_chunks = 0
    n_cued = 0
    n_burnable = 0
    n_smelting = 0
    best_grade = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = combustible_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_cued += 1
        if cue.burnable_now:
            n_burnable += 1
        if cue.smelting_grade:
            n_smelting += 1
        by_class[cue.fuel_class.name] = by_class.get(cue.fuel_class.name, 0) + 1
        by_material[cue.material] = by_material.get(cue.material, 0) + 1
        best_grade = max(best_grade, cue.calorific_grade)
    return {
        "n_chunks": n_chunks,
        "n_chunks_with_cue": n_cued,
        "cue_rate": round(n_cued / n_chunks, 4) if n_chunks else 0.0,
        "n_burnable_now": n_burnable,
        "n_smelting_grade": n_smelting,
        "best_calorific_grade": round(best_grade, 4),
        "by_class": dict(sorted(by_class.items())),
        "by_material": dict(sorted(by_material.items())),
    }


__all__ = [
    "FuelCue", "FuelProfile", "FuelClass",
    "install_combustible_outcrop", "combustible_cue_for_chunk",
    "prospect_fuel", "ignite_preview", "discover_fuel_by_sight",
    "best_fuel_near", "combustible_cue_summary",
    "MIN_FUEL_GRADE", "SMELTING_GRADE", "MOISTURE_EXTINCTION",
    "MIN_VISIBLE_FRACTION", "MAX_SEAM_DEPTH_M",
    "WATER_SATURATION_L", "MAX_WATER_BOOST",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
