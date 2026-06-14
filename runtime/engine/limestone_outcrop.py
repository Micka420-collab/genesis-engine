"""Genesis Engine — Substrate capability : affleurement calcaire (Cap. C6).

**Règle invariante du projet** (cf. ``surface_mineralization`` (C1),
``lithic_outcrop`` (C2), ``water_potability`` (C3), ``combustible_outcrop`` (C4),
``clay_outcrop`` (C5)) : rien n'est scripté. Un agent ne *sait* pas qu'une pierre
blanche fait du mortier — il **VOIT** une falaise blanche, en **détache** un bloc,
le **brûle** dans un feu très chaud (chaux vive), l'**éteint** à l'eau (pâte qui
durcit), et découvre le mortier / l'enduit. Ce module n'expose qu'un **signal
physique véridique** de carbonate ; la pierre de taille, le four à chaux, le
mortier, l'enduit, la maçonnerie — toute la chaîne — restent **émergents**.

Pourquoi ce module (et pourquoi ce n'est PAS un observateur)
------------------------------------------------------------
C5 a livré l'**argile** — le matériau qui *contient* (récipient, four, creuset,
brique). Son pendant exact est le calcaire — le matériau qui *bâtit* et *colle* :
la pierre de taille **et** la chaux qui lie les pierres entre elles. La veille du
jour (2026-06-14) ancre ce maillon dans l'âge de pierre : la **chaux est le plus
ancien liant connu**, néolithique (9000–6000 av. J.-C., sols d'enduit de chaux à
Göbekli Tepe ~9500 av. J.-C.), **antérieur à la métallurgie**, au verre, et
parfois à l'agriculture (Burning Lime — *the oldest chemical industry on Earth*).

Or **le calcaire restait muet** côté découverte : la géologie portait bien une
lithologie ``limestone`` (couverture sédimentaire des plateformes carbonatées) et
des ores carbonatés (``calcite``, ``dolomite``), mais **aucun signal Python ne les
rendait perceptibles** comme pierre à bâtir / source de chaux. Surtout, la crate
Rust ``genesis-geology`` réservait depuis Wave 43 un ``Mineral::LimestonePure``
(« Quicklime precursor — pure carbonate beds », couleur ``[245,240,225]``) —
**orphelin** : le contrat cross-langage le notait *« Python models as
limestone/calcite (catalogue), coarse Rust bins it »*. Ce module **comble ce
trou** : il rend le carbonate détectable ET enrichit le catalogue Python d'un vrai
``limestone_pure`` (calcaire de haute pureté), fermant l'orphelin Rust
``LimestonePure`` (garde-fou ADR-0007), exactement comme C5 a fermé ``FineClay``.

Ce n'est pas un ``*_observer.py`` qui *mesure* le tick — c'est un **signal de
monde interrogeable** que les agents *consomment pour agir*. Il n'ajoute **aucun
coût au tick** : les indices sont calculés paresseusement par chunk et mémorisés.
Il échappe donc au moratoire observateurs (``CONTRIBUTING.md`` §"Moratoire
observateurs") qui ne vise que les wrappers read-only de ``sim.step``.

Deux propriétés honnêtes et INDÉPENDANTES (veille 2026-06-14)
------------------------------------------------------------
Le calcaire porte deux vérités distinctes — pendant *enrichi* de C5 :

1. **Grade de chaux** (``lime_grade`` ∈ [0,1], gouverné par la PURETÉ carbonatée,
   D1) → fait ou non du **mortier**. La décarbonatation (CaCO3 → CaO + CO2) se
   produit vers 700–900 °C (max ~782 °C) : tout carbonate calcine, mais seul le
   carbonate **pur** donne une chaux vive réactive → mortier / enduit
   (``mortar_grade``). Le calcaire commun (légèrement argileux/marneux) ne donne
   qu'une chaux faible → pierre à bâtir seulement. C'est intrinsèque au matériau
   (on peut brûler une pierre fissurée : la chaux ne demande pas un bloc sain).

2. **Aptitude au dressage** (``dressable_now``, gouvernée par l'ALTÉRATION, D3) →
   se taille ou non en **blocs**. La même falaise blanche n'est pierre de taille
   que si elle est **saine**. L'eau de pluie légèrement acide dissout le carbonate
   (karstification — « plus la calcite est pure, plus elle se dissout ») : une
   exposition humide est **karst fissurée** (``karst_fissured`` — cavités, lapiez ;
   il faut carrer la roche saine en dessous) ; en climat gelant, la cryoclastie
   l'**éclate** (``frost_shattered`` — lien Wave 50 frost weathering). Seule une
   exposition sèche/tempérée est **saine** (``sound_quarry``) → dressable. C'est
   un effet 1+1>2 : hydrologie de surface (SYSTÈME A) × géologie (SYSTÈME C) ×
   gel (Wave 50), une seule vérité de substrat (biome + ``chunk.water``).

Les trois états d'altération sont mutuellement exclusifs et exhaustifs :
exactement un de {``sound_quarry``, ``karst_fissured``, ``frost_shattered``}.
``mortar_grade`` (chaux) et ``dressable_now`` (blocs) sont **orthogonaux** : un
calcaire pur karst-fissuré brûle en bon mortier mais ne se dresse pas en blocs ;
un calcaire commun sain se dresse en blocs mais ne fait qu'une chaux faible.

Le monde ne ment jamais
-----------------------
Un indice n'est émis QUE si le carbonate existe réellement, dans la même colonne
``chunk_geology`` que celle que ``mine_at`` exploite :
* source ``"lithology"`` ⇒ une couche peu profonde a un ``rock_type`` carbonaté
  (``limestone`` / ``marble``) ;
* source ``"ore"``        ⇒ une couche peu profonde a un minéral carbonaté
  (``limestone_pure`` / ``calcite`` / ``dolomite``) dans son ``ore_mix`` au-dessus
  du seuil de visibilité.
L'indice porte ``collect_depth_m`` : aller carrer/creuser là **rend** ce carbonate.
``mortar_grade`` ⇒ ``lime_grade`` ≥ seuil mortier ; ``dressable_now`` ⇒ exposition
saine ET pierre de taille. La réciproque est volontairement *faible* (absence
d'indice ⇏ absence de carbonate) : un banc calcaire sous 50 m de grès ne trahit
rien en surface. C'est physiquement honnête et cela préserve l'émergence (on ne
donne pas la carte des gîtes).

Déterminisme
------------
Pur : fonction de ``chunk_geology`` (lui-même ``prf_rng``) + biome + champ
``chunk.water`` (issus du seed). Aucun RNG nouveau. Bit-identique entre deux
runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — l'expression du carbonate est une
lecture dérivée du substrat géologique (lithologie + ore) et du champ d'eau,
comme C1/C2/C3/C4/C5.
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

# A carbonate bed is only perceivable / reachable for surface quarrying down to
# this depth (m). The ``limestone`` sedimentary cover crops out at ~5 m; deeper
# beds do not crop out. Same floor as C5 clay (6 m).
MAX_CARBONATE_DEPTH_M = 6.0

# A carbonate ore-mix fraction must reach this to leave a visible pale exposure
# (chalky bank / white outcrop) — same floor as C1/C2/C4/C5.
MIN_VISIBLE_FRACTION = 0.003

# Below this intrinsic lime grade a material is not carbonate enough to burn to
# any usable lime at all (none of the modelled carbonates falls below it).
MIN_LIME_GRADE = 0.30

# At/above this lime grade the carbonate calcines to a reactive quicklime that
# slakes to a true mortar / plaster (the keystone product, the binder that holds
# masonry together). Below it: only a weak / feebly-hydraulic lime → building
# stone, not plaster. Purity gate (veille D1) — mirrors C5 CERAMIC_GRADE.
MORTAR_GRADE = 0.80

# Weathering gate on *ambient ground moisture* in [0, 1] (veille D3).
# Above KARST_MOISTURE (and not freezing): the carbonate surface is dissolved /
# fissured (karst, lapiez, cavities) → poor blocks (quarry the sound rock below).
# Freezing biomes shatter it by cryoclasty regardless of moisture (Wave 50).
# A dry/temperate exposure below the threshold is sound → dressable into blocks.
KARST_MOISTURE = 0.62

# Biomes whose freeze-thaw cycling shatters an exposed carbonate face (Wave 50
# frost weathering). ICE / TUNDRA — periglacial cryoclasty.
_FROST_BIOMES = frozenset({1, 2})

# Surface-water field (litres, chunk mean) that saturates the wetness boost.
WATER_SATURATION_L = 200.0
# Maximum wetness added by standing surface water on top of the biome baseline.
MAX_WATER_BOOST = 0.30


class WeatherState(IntEnum):
    """Surface weathering state governing whether the stone dresses into blocks."""
    SOUND = 0    # dry / temperate massive rock → dressable into blocks
    KARST = 1    # humid → dissolution-fissured (cavities, lapiez) → blocks poor
    FROST = 2    # freezing → cryoclasty-shattered → blocks poor


class LimeClass(IntEnum):
    """Lime/building class governing what an agent can eventually do."""
    COMMON_CARBONATE = 0  # ordinary / dolomitic — building stone, weak lime
    PURE_CARBONATE = 1    # high-purity bed → reactive quicklime → mortar/plaster


# Ambient ground moisture baseline by biome id (the ONE shared substrate model,
# identical to C4 combustible_outcrop and C5 clay_outcrop). Wet/cold biomes are
# damp; deserts are dry. OCEAN is masked entirely (submerged).
_BIOME_WETNESS: Dict[int, float] = {
    0: 1.00,   # OCEAN              — submerged (masked anyway)
    1: 0.80,   # ICE
    2: 0.70,   # TUNDRA
    3: 0.60,   # BOREAL_FOREST
    4: 0.50,   # TEMPERATE_FOREST  — sound (below the karst threshold)
    5: 0.90,   # TEMPERATE_RAINFOREST — karst (wet)
    6: 0.35,   # GRASSLAND         — sound
    7: 0.05,   # HOT_DESERT        — sound (dry massive limestone = good stone)
    8: 0.10,   # COLD_DESERT       — sound
    9: 0.30,   # SAVANNA           — sound
    10: 0.40,  # TROPICAL_DRY_FOREST — sound
    11: 0.95,  # TROPICAL_RAINFOREST — karst (wet)
}

# Perceptual confidence modifier by biome (NOT a hard mask — a white carbonate
# cliff / chalk bank is a conspicuous terrain feature). OCEAN alone masks the cue.
_BIOME_EXPOSURE: Dict[int, float] = {
    0: 0.00,   # OCEAN — masked
    1: 0.55, 2: 0.80, 3: 0.65, 4: 0.70, 5: 0.55, 6: 0.90,
    7: 0.90, 8: 0.85, 9: 0.85, 10: 0.70, 11: 0.50,
}


@dataclass(frozen=True)
class CarbonateProfile:
    """Intrinsic character of one carbonate material an agent can quarry."""
    material: str                   # geology id (catalogue mineral / rock name)
    lime_class: LimeClass
    label: str                      # human label of the perceived exposure
    rgb: Tuple[int, int, int]       # perceived colour of the pale exposure
    lime_grade: float               # quicklime reactivity / carbonate purity [0,1]
    dimension_stone: bool           # yields dressable masonry blocks (not a vein)


# Carbonate ladder: common building stone < pure quicklime/mortar source. The
# ``limestone_pure`` rgb (245,240,225) is byte-exact with Rust
# ``Mineral::LimestonePure`` (the chalk-white tell an agent learns to seek for
# lime). Every material is a real entry of the mineral catalogue, so a cue can
# always be ground-truthed.
_PROFILES: Tuple[CarbonateProfile, ...] = (
    CarbonateProfile("limestone_pure", LimeClass.PURE_CARBONATE,
                     "banc calcaire blanc-crayeux (calcaire pur — chaux/mortier)",
                     rgb=(245, 240, 225), lime_grade=0.95, dimension_stone=True),
    CarbonateProfile("calcite", LimeClass.PURE_CARBONATE,
                     "veine de calcite blanche translucide (carbonate pur)",
                     rgb=(235, 230, 222), lime_grade=0.92, dimension_stone=False),
    CarbonateProfile("marble", LimeClass.PURE_CARBONATE,
                     "roche blanche veinée, dure et brillante (marbre)",
                     rgb=(236, 233, 226), lime_grade=0.86, dimension_stone=True),
    CarbonateProfile("limestone", LimeClass.COMMON_CARBONATE,
                     "falaise calcaire gris-beige (pierre à bâtir)",
                     rgb=(210, 205, 185), lime_grade=0.72, dimension_stone=True),
    CarbonateProfile("dolomite", LimeClass.COMMON_CARBONATE,
                     "roche beige-rosé sucrée au grain (dolomie)",
                     rgb=(206, 196, 178), lime_grade=0.55, dimension_stone=True),
)

# material name → profile (validated at import: every material is a real entry
# of the mineral catalogue, so a cue can always be ground-truthed).
_PROFILE: Dict[str, CarbonateProfile] = {}
for _p in _PROFILES:
    if _p.material not in MINERAL_BY_NAME:
        raise RuntimeError(
            f"limestone_outcrop: unknown material '{_p.material}' — fix table.")
    if _p.material in _PROFILE:
        raise RuntimeError(
            f"limestone_outcrop: material '{_p.material}' listed twice.")
    _PROFILE[_p.material] = _p


@dataclass(frozen=True)
class LimestoneCue:
    """A truthful carbonate-outcrop cue at one chunk.

    ``label``/``rgb``/``lime_class`` = what an agent *perceives*. ``material`` =
    the ground truth reachable below (used to resolve collection + prove the
    invariant). It is NOT handed to the agent as "this is pure limestone" — the
    agent must learn the white-stone→lime and sound→holds-an-edge correlations by
    acting.
    """
    coord: Tuple[int, int, int]
    material: str                   # ground-truth carbonate the exposure yields
    lime_class: LimeClass
    label: str
    rgb: Tuple[int, int, int]
    lime_grade: float               # quicklime reactivity / carbonate purity [0,1]
    dimension_stone: bool           # intrinsic: yields masonry blocks (not a vein)
    source: str                     # "lithology" | "ore" — which field proves it
    source_depth_m: float           # depth of the proving layer top (m)
    collect_depth_m: float          # a depth that lands inside the proving layer
    ambient_moisture: float         # site wetness in [0, 1] (biome + water)
    weather_state: WeatherState     # SOUND | KARST | FROST
    sound_quarry: bool              # dry/temperate massive rock
    karst_fissured: bool            # humid → dissolution-fissured
    frost_shattered: bool           # freezing → cryoclasty-shattered
    dressable_now: bool             # sound AND dimension stone → blocks now
    mortar_grade: bool              # calcines to reactive quicklime → mortar
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

    Shared model with ``combustible_outcrop`` (C4) and ``clay_outcrop`` (C5) so
    the capabilities agree on 'how wet is this ground' — the one substrate truth,
    several readings (fuel wants it dry, clay wants it plastic, carbonate wants it
    dry to stay sound)."""
    base = _BIOME_WETNESS.get(biome, 0.4)
    water = np.asarray(getattr(chunk, "water", None)) if hasattr(chunk, "water") else None
    boost = 0.0
    if water is not None and water.size:
        mean_w = float(water.mean())
        boost = MAX_WATER_BOOST * min(1.0, mean_w / WATER_SATURATION_L)
    return float(min(1.0, max(0.0, base + boost)))


def _weather_state(biome: int, ambient: float) -> WeatherState:
    """Surface weathering state of an exposed carbonate face (veille D3).

    Freezing biome → cryoclasty (FROST); else humid → dissolution (KARST); else
    dry/temperate massive rock (SOUND). Deterministic, exhaustive partition."""
    if biome in _FROST_BIOMES:
        return WeatherState.FROST
    if ambient > KARST_MOISTURE:
        return WeatherState.KARST
    return WeatherState.SOUND


def _candidates_in_layer(layer: StrataLayer) -> List[Tuple[str, str]]:
    """All carbonate candidates reachable in ``layer``.

    Returns ``(material, source)`` tuples: the layer's own ``rock_type`` if it is
    a carbonate rock (source ``"lithology"`` — limestone cover / marble) plus any
    carbonate present in its ``ore_mix`` above the visibility fraction (source
    ``"ore"`` — pure limestone bed / calcite vein / dolomite)."""
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
                      ) -> Optional[LimestoneCue]:
    """Pure derivation. The highest lime-grade carbonate reachable shallow wins
    (then shallower, then class, then name — fully deterministic)."""
    if biome == _OCEAN:
        return None  # submerged: the exposure is masked
    best: Optional[Tuple[StrataLayer, str, str]] = None
    best_key: Optional[Tuple[float, float, int, str]] = None
    for layer in layers:
        if layer.depth_top_m > MAX_CARBONATE_DEPTH_M:
            continue
        for material, source in _candidates_in_layer(layer):
            prof = _PROFILE[material]
            key = (-prof.lime_grade, layer.depth_top_m,
                   -int(prof.lime_class), material)
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
    state = _weather_state(biome, ambient)
    sound = bool(state == WeatherState.SOUND)
    karst = bool(state == WeatherState.KARST)
    frost = bool(state == WeatherState.FROST)
    dressable = bool(sound and prof.dimension_stone)
    mortar = bool(prof.lime_grade >= MORTAR_GRADE)
    exposure = _BIOME_EXPOSURE.get(biome, 0.5)
    confidence = float(min(1.0, exposure * (0.4 + 0.6 * prof.lime_grade)))
    return LimestoneCue(
        coord=tuple(int(c) for c in coord),
        material=material, lime_class=prof.lime_class, label=prof.label,
        rgb=prof.rgb, lime_grade=float(prof.lime_grade),
        dimension_stone=bool(prof.dimension_stone),
        source=source, source_depth_m=float(layer.depth_top_m),
        collect_depth_m=float(collect_depth),
        ambient_moisture=float(round(ambient, 4)),
        weather_state=state, sound_quarry=sound, karst_fissured=karst,
        frost_shattered=frost, dressable_now=dressable, mortar_grade=mortar,
        biome=int(biome), confidence=confidence)


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_limestone_outcrop(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim``.

    Adds **zero** per-tick cost: cues are derived on query and memoised.
    Returns the cache dict (``sim._limestone_cue_cache``).
    """
    install_geology(sim)  # ensure geology state exists
    cache = getattr(sim, "_limestone_cue_cache", None)
    if cache is None:
        cache = {}
        sim._limestone_cue_cache = cache
    return cache


def limestone_cue_for_chunk(sim, coord: Tuple[int, int, int]
                            ) -> Optional[LimestoneCue]:
    """Truthful carbonate-outcrop cue at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, ``chunk_geology(sim, coord)`` has a layer
    at ``collect_depth_m`` whose ``rock_type`` (source ``lithology``) or
    ``ore_mix`` (source ``ore``) carries ``material``.
    """
    coord = tuple(int(c) for c in coord)
    cache = install_limestone_outcrop(sim)
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


def prospect_limestone(sim, world_x: float, world_y: float
                       ) -> Optional[LimestoneCue]:
    """What an agent standing at world ``(x, y)`` perceives of the carbonate
    exposure at the surface. Returns the cue (pale stone + truthful target) or
    None."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return limestone_cue_for_chunk(sim, coord)


def work_preview(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of what working the carbonate at ``(x, y)``
    yields — the ground-truthed outcome the perception cue must agree with.

    Touches NOTHING (no stone quarried, no geology mutated): it is the truth
    oracle, not the action. The two outcomes are **orthogonal**:
    ``burns_to_quicklime`` is True for a pure carbonate (calcines to reactive
    quicklime → mortar / plaster), independent of weathering — you can burn
    fissured rubble for lime. ``can_dress`` is True only when the exposure is
    SOUND *and* the material is a dimension stone — i.e. it would actually hold a
    dressed block. A karst-fissured cliff returns ``can_dress=False`` with
    ``karst_fissured=True`` (the lie this cap exposes: it looks like building
    stone, but it crumbles — quarry the sound rock below); a frost-shattered face
    returns ``frost_shattered=True``."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = limestone_cue_for_chunk(sim, coord)
    if cue is None:
        return {"material": None, "lime_class": None, "lime_grade": 0.0,
                "can_dress": False, "burns_to_quicklime": False,
                "karst_fissured": False, "frost_shattered": False,
                "weather_state": None, "ambient_moisture": 0.0}
    return {"material": cue.material, "lime_class": cue.lime_class.name,
            "lime_grade": cue.lime_grade,
            "can_dress": cue.dressable_now,
            "burns_to_quicklime": cue.mortar_grade,
            "karst_fissured": cue.karst_fissured,
            "frost_shattered": cue.frost_shattered,
            "weather_state": cue.weather_state.name,
            "ambient_moisture": cue.ambient_moisture}


def discover_limestone_by_sight(sim, rows: List[int],
                                perception_radius_m: float = 64.0
                                ) -> Dict[int, List[LimestoneCue]]:
    """For each agent ``row``, the carbonate exposures perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    This is the capability that turns the static, buried carbonate field into a
    **perceivable, actionable** signal — the agent then *chooses* to quarry +
    dress + burn + slake. Deterministic order (by chunk distance then coord).
    """
    out: Dict[int, List[LimestoneCue]] = {}
    if not rows:
        return out
    install_limestone_outcrop(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], LimestoneCue]] = []
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
                cue = limestone_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_limestone_near(sim, row: int, perception_radius_m: float = 128.0,
                        *, require_dressable: bool = False,
                        require_mortar: bool = False) -> Optional[LimestoneCue]:
    """The best carbonate exposure an agent at ``row`` can perceive — the
    actionable pick (highest ``lime_grade``; tie-break nearest then coord).

    ``require_dressable`` keeps only sound dimension stone right now (the pick
    when an agent seeks masonry blocks, skipping karst/frost exposures).
    ``require_mortar`` keeps only quicklime-grade pure carbonate — the pick when
    an agent seeks the binder (mortar / plaster). Returns None when nothing
    matching is in sight (a physically honest 'no usable stone here')."""
    cues = discover_limestone_by_sight(sim, [int(row)], perception_radius_m
                                       ).get(int(row), [])
    pool = cues
    if require_mortar:
        pool = [c for c in pool if c.mortar_grade]
    if require_dressable:
        pool = [c for c in pool if c.dressable_now]
    if not pool:
        return None
    # already distance-sorted; pick max grade, ties keep nearest order.
    return max(pool, key=lambda c: c.lime_grade)


def limestone_cue_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_limestone_outcrop(sim)
    by_class: Dict[str, int] = {}
    by_material: Dict[str, int] = {}
    by_weather: Dict[str, int] = {}
    n_chunks = 0
    n_cued = 0
    n_dressable = 0
    n_mortar = 0
    best_grade = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = limestone_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_cued += 1
        if cue.dressable_now:
            n_dressable += 1
        if cue.mortar_grade:
            n_mortar += 1
        by_class[cue.lime_class.name] = by_class.get(cue.lime_class.name, 0) + 1
        by_material[cue.material] = by_material.get(cue.material, 0) + 1
        by_weather[cue.weather_state.name] = \
            by_weather.get(cue.weather_state.name, 0) + 1
        best_grade = max(best_grade, cue.lime_grade)
    return {
        "n_chunks": n_chunks,
        "n_chunks_with_cue": n_cued,
        "cue_rate": round(n_cued / n_chunks, 4) if n_chunks else 0.0,
        "n_dressable_now": n_dressable,
        "n_mortar_grade": n_mortar,
        "best_lime_grade": round(best_grade, 4),
        "by_class": dict(sorted(by_class.items())),
        "by_material": dict(sorted(by_material.items())),
        "by_weather": dict(sorted(by_weather.items())),
    }


__all__ = [
    "LimestoneCue", "CarbonateProfile", "LimeClass", "WeatherState",
    "install_limestone_outcrop", "limestone_cue_for_chunk",
    "prospect_limestone", "work_preview", "discover_limestone_by_sight",
    "best_limestone_near", "limestone_cue_summary",
    "MIN_LIME_GRADE", "MORTAR_GRADE", "KARST_MOISTURE",
    "MIN_VISIBLE_FRACTION", "MAX_CARBONATE_DEPTH_M",
    "WATER_SATURATION_L", "MAX_WATER_BOOST",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
