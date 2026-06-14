"""Genesis Engine — Substrate capability : affleurement d'argile (Cap. C5).

**Règle invariante du projet** (cf. ``surface_mineralization`` (C1),
``lithic_outcrop`` (C2), ``water_potability`` (C3), ``combustible_outcrop``
(C4)) : rien n'est scripté. Un agent ne *sait* pas qu'une terre se façonne en
pot — il **VOIT** une berge de terre lisse beige-ocre, la **malaxe** entre ses
doigts (elle est *plastique* : elle tient une forme), la sèche, la **cuit**, et
découvre la céramique. Ce module n'expose qu'un **signal physique véridique**
d'argile ; la poterie, la brique, le four, le creuset — toute la chaîne — restent
**émergents**.

Pourquoi ce module (et pourquoi ce n'est PAS un observateur)
------------------------------------------------------------
C1 a livré la découverte du **minerai**, C2 celle de la **pierre taillable**,
C3 celle de l'**eau potable**, C4 celle du **combustible**. Le combustible (C4)
était l'amorce de la révolution énergétique ; sa propre docstring l'écrit :
« feu durable → **four en argile** + charbon → température de fusion →
métallurgie ». Or **l'argile elle-même restait muette** : la géologie portait
le schiste argileux (``shale`` = *clay_consolidated*) en surface partout, et la
crate Rust ``genesis-geology`` réservait depuis Wave 43 un ``Mineral::FineClay``
(« Plastic clay suitable for pottery / brick », couleur ``[180,140,110]``) —
mais **aucun côté Python ne le rendait perceptible** (le contrat cross-langage
le notait explicitement orphelin : *« Python uses rock_type/clay vocabulary, no
catalogue mineral of this name »*). Ce module **comble ce trou** : il rend
l'argile détectable ET enrichit le catalogue Python d'un vrai ``fine_clay``
(kaolinite), fermant l'orphelin Rust ``FineClay`` (garde-fou ADR-0007).

L'argile est la **clé de voûte** stone-age : récipient (stockage d'eau C3, de
grain), four (qui contient le feu C4), creuset (qui contient le métal fondu),
brique (qui bâtit). C'est le matériau qui *contient* tous les autres.

Ce n'est pas un ``*_observer.py`` qui *mesure* le tick — c'est un **signal de
monde interrogeable** que les agents *consomment pour agir*. Il n'ajoute **aucun
coût au tick** : les indices sont calculés paresseusement par chunk et mémorisés.
Il échappe donc au moratoire observateurs (``CONTRIBUTING.md`` §"Moratoire
observateurs") qui ne vise que les wrappers read-only de ``sim.step``.

Hiérarchie de l'argile (veille 2026-06-14)
------------------------------------------
Deux grades, comme le rang houiller de C4 (tourbe < schiste < charbon) :

* **Argile schisteuse** (``shale``, source ``lithology``) — le schiste argileux
  altéré du sol de surface (présent quasi partout : ``shale`` est la lithologie
  du topsoil). Grade **brique** : se façonne et durcit, mais reste poreux ; ne
  fait pas une céramique étanche. C'est l'argile *commune*, celle qui explique
  que la poterie ait été inventée indépendamment d'innombrables fois.
* **Argile plastique / kaolin** (``fine_clay``, source ``ore``) — l'argile
  résiduelle de kaolinite (altération humide de roche feldspathique), plus rare
  et localisée. Grade **céramique** : cuite, elle vitrifie en poterie durable et
  étanche → seul grade capable de tenir un creuset / un four de fusion. C'est le
  ``FineClay`` du crate Rust, dont on verrouille le tell ``[180,140,110]``
  **byte-exact** (miroir du tell cuivre/malachite ``(80,140,70)`` et du tell
  charbon ``(20,20,20)``).

Porte de plasticité — limites d'Atterberg (veille 2026-06-14, mécanique des sols)
---------------------------------------------------------------------------------
L'argile n'est **façonnable** que dans une **fenêtre d'humidité** (Atterberg
1911, fondement de la mécanique des sols) :

* sous la **limite de plasticité** (``PLASTIC_LIMIT``) : l'argile est sèche,
  friable, s'émiette — *vue* mais ``too_dry_to_shape`` (il faut la mouiller /
  corroyer) ;
* entre PL et la **limite de liquidité** (``LIQUID_LIMIT``) : l'argile est
  **plastique** — ``workable_now`` (elle tient la forme qu'on lui donne) ;
* au-dessus de LL : l'argile est une boue qui flue — *vue* mais
  ``too_wet_slurry`` (il faut la laisser drainer / sécher).

C'est exactement le pendant *inversé* de la porte d'humidité de C4 : le
combustible veut être **sec** pour brûler, l'argile veut être **humide** (juste
ce qu'il faut) pour se façonner. L'humidité ambiante est dérivée du **même**
substrat que C4 (biome + champ ``chunk.water``) → effet 1+1>2 du combo :
hydrologie de surface (SYSTÈME A) reliée à la géologie sédimentaire (SYSTÈME C),
elle-même reliée au feu de C4 (SYSTÈME F) qui transforme l'argile crue en
céramique permanente.

Le monde ne ment jamais
-----------------------
Un indice n'est émis QUE si l'argile existe réellement, dans la même colonne
``chunk_geology`` que celle que ``mine_at`` exploite :
* source ``"lithology"`` ⇒ une couche peu profonde a ``rock_type == "shale"`` ;
* source ``"ore"``        ⇒ une couche peu profonde a ``fine_clay`` dans son
  ``ore_mix`` au-dessus du seuil de visibilité.
L'indice porte ``collect_depth_m`` : aller creuser là **rend** cette argile.
``workable_now`` ⇒ humidité ambiante dans la fenêtre de plasticité (toutes deux
dérivées du substrat) ; ``ceramic_grade`` ⇒ grade poterie ≥ seuil céramique. La
réciproque est volontairement *faible* (absence d'indice ⇏ absence d'argile) :
un lit d'argile sous 50 m de grès ne trahit rien en surface. C'est physiquement
honnête et cela préserve l'émergence (on ne donne pas la carte des gîtes).

Déterminisme
------------
Pur : fonction de ``chunk_geology`` (lui-même ``prf_rng``) + biome + champ
``chunk.water`` (issus du seed). Aucun RNG nouveau. Bit-identique entre deux
runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — l'expression d'argile est une
lecture dérivée du substrat géologique (lithologie + couche résiduelle) et du
champ d'eau, comme C1/C2/C3/C4.
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

# A clay bed is only perceivable / reachable for surface digging down to this
# depth (m). Material buried deeper does not crop out.
MAX_CLAY_DEPTH_M = 6.0

# A ``fine_clay`` ore-mix fraction must reach this to leave a visible smooth
# exposure (cut bank / slick mud) — same floor as C1/C2/C4.
MIN_VISIBLE_FRACTION = 0.003

# Below this intrinsic pottery grade a material is not clay enough to hold a
# moulded shape at all (none of the modelled clays falls below it).
MIN_POTTERY_GRADE = 0.30

# At/above this pottery grade the clay fires to a durable, watertight ceramic —
# the grade that can line a crucible / smelting kiln (only kaolinite here). The
# emergent tech enabler (the vessel that contains C3 water, C4 fire, the metal).
CERAMIC_GRADE = 0.70

# Atterberg plasticity window on *ambient ground moisture* in [0, 1].
# Below PLASTIC_LIMIT: crumbly / friable → cannot be shaped (must wet & wedge).
# Between PL and LL: plastic → workable now (holds a moulded shape).
# Above LIQUID_LIMIT: slurry → slumps (must drain & dry first).
PLASTIC_LIMIT = 0.18
LIQUID_LIMIT = 0.55

# Surface-water field (litres, chunk mean) that saturates the wetness boost.
WATER_SATURATION_L = 200.0
# Maximum wetness added by standing surface water on top of the biome baseline.
MAX_WATER_BOOST = 0.30


class ClayClass(IntEnum):
    """Workability/firing class governing what an agent can eventually do."""
    SHALE_CLAY = 0    # weathered shaly clay — brick grade, porous when fired
    PLASTIC_CLAY = 1  # residual kaolinite — ceramic grade, vitrifies watertight


# Ambient ground moisture baseline by biome id (shared with C4
# combustible_outcrop). Wet/cold biomes are damp; deserts are dry. OCEAN is
# masked entirely (submerged).
_BIOME_WETNESS: Dict[int, float] = {
    0: 1.00,   # OCEAN              — submerged (masked anyway)
    1: 0.80,   # ICE
    2: 0.70,   # TUNDRA
    3: 0.60,   # BOREAL_FOREST
    4: 0.50,   # TEMPERATE_FOREST  — squarely in the workable band
    5: 0.90,   # TEMPERATE_RAINFOREST
    6: 0.35,   # GRASSLAND         — workable
    7: 0.05,   # HOT_DESERT        — too dry to shape (must wet & wedge)
    8: 0.10,   # COLD_DESERT
    9: 0.30,   # SAVANNA           — workable
    10: 0.40,  # TROPICAL_DRY_FOREST
    11: 0.95,  # TROPICAL_RAINFOREST — too wet (slurry)
}

# Perceptual confidence modifier by biome (NOT a hard mask — a clay cut bank is
# a terrain feature, visible even under canopy). OCEAN alone masks the cue.
_BIOME_EXPOSURE: Dict[int, float] = {
    0: 0.00,   # OCEAN — masked
    1: 0.45, 2: 0.80, 3: 0.65, 4: 0.70, 5: 0.55, 6: 0.90,
    7: 0.85, 8: 0.80, 9: 0.85, 10: 0.70, 11: 0.50,
}


@dataclass(frozen=True)
class ClayProfile:
    """Intrinsic character of one clay material an agent can dig."""
    material: str                   # geology id (catalogue mineral / rock name)
    clay_class: ClayClass
    label: str                      # human label of the perceived exposure
    rgb: Tuple[int, int, int]       # perceived colour of the smooth exposure
    pottery_grade: float            # firing/vitrification rank in [0, 1]


# Clay ladder: shale (brick) < fine_clay (ceramic, kiln-capable). ``fine_clay``
# rgb (180,140,110) is byte-exact with Rust ``Mineral::FineClay`` (the smooth
# ochre tell an agent learns to seek for a pot). Both materials are real entries
# of the mineral catalogue, so a cue can always be ground-truthed.
_PROFILES: Tuple[ClayProfile, ...] = (
    ClayProfile("fine_clay", ClayClass.PLASTIC_CLAY,
                "terre lisse beige-ocre, grasse au toucher (argile plastique)",
                rgb=(180, 140, 110), pottery_grade=0.85),
    ClayProfile("shale", ClayClass.SHALE_CLAY,
                "berge de terre grise compacte (argile schisteuse — brique)",
                rgb=(150, 120, 95), pottery_grade=0.45),
)

# material name → profile (validated at import: every material is a real entry
# of the mineral catalogue, so a cue can always be ground-truthed).
_PROFILE: Dict[str, ClayProfile] = {}
for _p in _PROFILES:
    if _p.material not in MINERAL_BY_NAME:
        raise RuntimeError(
            f"clay_outcrop: unknown material '{_p.material}' — fix table.")
    if _p.material in _PROFILE:
        raise RuntimeError(
            f"clay_outcrop: material '{_p.material}' listed twice.")
    _PROFILE[_p.material] = _p


@dataclass(frozen=True)
class ClayCue:
    """A truthful clay-outcrop cue at one chunk.

    ``label``/``rgb``/``clay_class`` = what an agent *perceives*. ``material`` =
    the ground truth reachable below (used to resolve collection + prove the
    invariant). It is NOT handed to the agent as "this is kaolinite" — the agent
    must learn the smooth-ochre→pot and plastic→holds-shape correlations by
    acting.
    """
    coord: Tuple[int, int, int]
    material: str                   # ground-truth clay the exposure yields
    clay_class: ClayClass
    label: str
    rgb: Tuple[int, int, int]
    pottery_grade: float            # firing/vitrification rank in [0, 1]
    source: str                     # "lithology" | "ore" — which field proves it
    source_depth_m: float           # depth of the proving layer top (m)
    collect_depth_m: float          # a depth that lands inside the proving layer
    ambient_moisture: float         # site wetness in [0, 1] (biome + water)
    workable_now: bool              # ambient moisture inside the plastic window
    too_dry_to_shape: bool          # below plastic limit → wet & wedge first
    too_wet_slurry: bool            # above liquid limit → drain & dry first
    ceramic_grade: bool             # fires to durable watertight ceramic
    biome: int
    confidence: float               # perceptual confidence in [0, 1]


# ---------------------------------------------------------------------------
# Core derivation — cue from the same geology layers that mining reads.
# ---------------------------------------------------------------------------

def _dominant_biome(chunk) -> int:
    biomes, counts = np.unique(np.asarray(chunk.biome), return_counts=True)
    return int(biomes[int(np.argmax(counts))])


def _ambient_moisture(biome: int, chunk) -> float:
    """Site wetness in [0,1]: biome baseline + standing surface-water boost.

    Shared model with ``combustible_outcrop`` so the two capabilities agree on
    'how wet is this ground' — the one substrate truth, two readings (fuel wants
    it dry, clay wants it plastic)."""
    base = _BIOME_WETNESS.get(biome, 0.4)
    water = np.asarray(getattr(chunk, "water", None)) if hasattr(chunk, "water") else None
    boost = 0.0
    if water is not None and water.size:
        mean_w = float(water.mean())
        boost = MAX_WATER_BOOST * min(1.0, mean_w / WATER_SATURATION_L)
    return float(min(1.0, max(0.0, base + boost)))


def _candidates_in_layer(layer: StrataLayer) -> List[Tuple[str, str]]:
    """All clay candidates reachable in ``layer``.

    Returns ``(material, source)`` tuples: the layer's own ``rock_type`` if it
    is a clay-bearing rock (source ``"lithology"`` — shale topsoil) plus any
    clay present in its ``ore_mix`` above the visibility fraction (source
    ``"ore"`` — residual kaolinite)."""
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
                      ) -> Optional[ClayCue]:
    """Pure derivation. The highest pottery-grade clay reachable shallow wins
    (then shallower, then class, then name — fully deterministic)."""
    if biome == _OCEAN:
        return None  # submerged: the exposure is masked
    best: Optional[Tuple[StrataLayer, str, str]] = None
    best_key: Optional[Tuple[float, float, int, str]] = None
    for layer in layers:
        if layer.depth_top_m > MAX_CLAY_DEPTH_M:
            continue
        for material, source in _candidates_in_layer(layer):
            prof = _PROFILE[material]
            key = (-prof.pottery_grade, layer.depth_top_m,
                   -int(prof.clay_class), material)
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
    workable = bool(PLASTIC_LIMIT <= ambient <= LIQUID_LIMIT)
    too_dry = bool(ambient < PLASTIC_LIMIT)
    too_wet = bool(ambient > LIQUID_LIMIT)
    ceramic = bool(prof.pottery_grade >= CERAMIC_GRADE)
    exposure = _BIOME_EXPOSURE.get(biome, 0.5)
    confidence = float(min(1.0, exposure * (0.4 + 0.6 * prof.pottery_grade)))
    return ClayCue(
        coord=tuple(int(c) for c in coord),
        material=material, clay_class=prof.clay_class, label=prof.label,
        rgb=prof.rgb, pottery_grade=float(prof.pottery_grade),
        source=source, source_depth_m=float(layer.depth_top_m),
        collect_depth_m=float(collect_depth),
        ambient_moisture=float(round(ambient, 4)),
        workable_now=workable, too_dry_to_shape=too_dry,
        too_wet_slurry=too_wet, ceramic_grade=ceramic,
        biome=int(biome), confidence=confidence)


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_clay_outcrop(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim``.

    Adds **zero** per-tick cost: cues are derived on query and memoised.
    Returns the cache dict (``sim._clay_cue_cache``).
    """
    install_geology(sim)  # ensure geology state exists
    cache = getattr(sim, "_clay_cue_cache", None)
    if cache is None:
        cache = {}
        sim._clay_cue_cache = cache
    return cache


def clay_cue_for_chunk(sim, coord: Tuple[int, int, int]) -> Optional[ClayCue]:
    """Truthful clay-outcrop cue at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, ``chunk_geology(sim, coord)`` has a layer
    at ``collect_depth_m`` whose ``rock_type`` (source ``lithology``) or
    ``ore_mix`` (source ``ore``) carries ``material``.
    """
    coord = tuple(int(c) for c in coord)
    cache = install_clay_outcrop(sim)
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


def prospect_clay(sim, world_x: float, world_y: float) -> Optional[ClayCue]:
    """What an agent standing at world ``(x, y)`` perceives of the clay exposure
    at the surface. Returns the cue (smooth ochre + truthful target) or None."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return clay_cue_for_chunk(sim, coord)


def shape_preview(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of what shaping the clay at ``(x, y)`` yields —
    the ground-truthed outcome the perception cue must agree with.

    Touches NOTHING (no clay dug, no geology mutated): it is the truth oracle,
    not the action. ``can_shape`` is True only when a real clay is present here
    AND the ground is in the plastic window — i.e. moulding it would actually
    hold. A bone-dry desert clay returns ``can_shape=False`` with
    ``too_dry_to_shape=True`` (the lie this cap exposes: it looks like clay, but
    it must be wetted & wedged first); a waterlogged bed returns
    ``too_wet_slurry=True``. ``fires_to_ceramic`` flags the kaolinite that
    vitrifies into watertight pottery."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = clay_cue_for_chunk(sim, coord)
    if cue is None:
        return {"material": None, "clay_class": None, "pottery_grade": 0.0,
                "can_shape": False, "too_dry_to_shape": False,
                "too_wet_slurry": False, "fires_to_ceramic": False,
                "ambient_moisture": 0.0}
    return {"material": cue.material, "clay_class": cue.clay_class.name,
            "pottery_grade": cue.pottery_grade,
            "can_shape": cue.workable_now,
            "too_dry_to_shape": cue.too_dry_to_shape,
            "too_wet_slurry": cue.too_wet_slurry,
            "fires_to_ceramic": cue.ceramic_grade,
            "ambient_moisture": cue.ambient_moisture}


def discover_clay_by_sight(sim, rows: List[int],
                           perception_radius_m: float = 64.0
                           ) -> Dict[int, List[ClayCue]]:
    """For each agent ``row``, the clay exposures perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    This is the capability that turns the static, buried clay field into a
    **perceivable, actionable** signal — the agent then *chooses* to dig + wedge
    + shape + fire. Deterministic order (by chunk distance then coord).
    """
    out: Dict[int, List[ClayCue]] = {}
    if not rows:
        return out
    install_clay_outcrop(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], ClayCue]] = []
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
                cue = clay_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_clay_near(sim, row: int, perception_radius_m: float = 128.0,
                   *, require_workable: bool = False,
                   require_ceramic: bool = False) -> Optional[ClayCue]:
    """The best clay exposure an agent at ``row`` can perceive — the actionable
    pick (highest ``pottery_grade``; tie-break nearest then coord).

    ``require_workable`` skips clay outside the plastic window right now (forcing
    the agent to either pick a wetter/drier source or wet/dry this one).
    ``require_ceramic`` keeps only kiln-grade kaolinite — the pick when an agent
    seeks a watertight pot or a crucible. Returns None when nothing matching is
    in sight (a physically honest 'no clay here')."""
    cues = discover_clay_by_sight(sim, [int(row)], perception_radius_m
                                  ).get(int(row), [])
    pool = cues
    if require_ceramic:
        pool = [c for c in pool if c.ceramic_grade]
    if require_workable:
        pool = [c for c in pool if c.workable_now]
    if not pool:
        return None
    # already distance-sorted; pick max grade, ties keep nearest order.
    return max(pool, key=lambda c: c.pottery_grade)


def clay_cue_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_clay_outcrop(sim)
    by_class: Dict[str, int] = {}
    by_material: Dict[str, int] = {}
    n_chunks = 0
    n_cued = 0
    n_workable = 0
    n_ceramic = 0
    best_grade = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = clay_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_cued += 1
        if cue.workable_now:
            n_workable += 1
        if cue.ceramic_grade:
            n_ceramic += 1
        by_class[cue.clay_class.name] = by_class.get(cue.clay_class.name, 0) + 1
        by_material[cue.material] = by_material.get(cue.material, 0) + 1
        best_grade = max(best_grade, cue.pottery_grade)
    return {
        "n_chunks": n_chunks,
        "n_chunks_with_cue": n_cued,
        "cue_rate": round(n_cued / n_chunks, 4) if n_chunks else 0.0,
        "n_workable_now": n_workable,
        "n_ceramic_grade": n_ceramic,
        "best_pottery_grade": round(best_grade, 4),
        "by_class": dict(sorted(by_class.items())),
        "by_material": dict(sorted(by_material.items())),
    }


__all__ = [
    "ClayCue", "ClayProfile", "ClayClass",
    "install_clay_outcrop", "clay_cue_for_chunk",
    "prospect_clay", "shape_preview", "discover_clay_by_sight",
    "best_clay_near", "clay_cue_summary",
    "MIN_POTTERY_GRADE", "CERAMIC_GRADE",
    "PLASTIC_LIMIT", "LIQUID_LIMIT",
    "MIN_VISIBLE_FRACTION", "MAX_CLAY_DEPTH_M",
    "WATER_SATURATION_L", "MAX_WATER_BOOST",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
