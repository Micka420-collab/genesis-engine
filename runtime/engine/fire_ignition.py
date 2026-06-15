"""Genesis Engine — Substrate capability : amorçage du feu (Cap. C7).

**Règle invariante du projet** (cf. ``surface_mineralization`` (C1),
``lithic_outcrop`` (C2), ``water_potability`` (C3), ``combustible_outcrop`` (C4),
``clay_outcrop`` (C5), ``limestone_outcrop`` (C6)) : rien n'est scripté. Un agent
ne *sait* pas qu'on fait du feu — il **VOIT** une pierre brun-rouille qui jette
des étincelles quand on la frappe (pyrite), une pierre dure et vitreuse pour la
percuter (silex), et de l'herbe sèche qui prend ; ou il **frotte** longuement
deux bois sur de l'amadou très sec. Ce module n'expose qu'un **signal physique
véridique** d'amorçage ; le briquet à pyrite, l'archet à feu, le foyer entretenu,
la cuisson, le four — toute la chaîne — restent **émergents**.

Pourquoi ce module — la voûte qui ferme l'arc C1→C6
---------------------------------------------------
C1→C6 ont rendu *perceptibles* les **matières** de l'âge de pierre : le minerai
(C1), la pierre taillable (C2), l'eau potable (C3), le combustible (C4),
l'argile (C5), le calcaire (C6). Mais **presque toutes** demandent ensuite *un
feu* : fondre le cuivre (C1), brûler le combustible (C4), cuire l'argile en
céramique (C5), calciner le calcaire en chaux (C6). Sans amorçage, ces capacités
restaient des matières inertes : l'agent voit le cuivre vert mais ne peut pas le
fondre, voit l'argile mais ne peut pas la cuire. **Le feu est la voûte** qui rend
l'arc C1→C6 *actionnable*.

Or l'amorçage *par l'agent* restait muet. ``engine.wildfire`` (Wave 14) modélise
bien le feu **spontané** (foudre → ignition → propagation Rothermel) — et son
propre docstring note que l'agent doit *déduire* que « le silex frappé produit la
même chose en petit ». Mais **aucun signal de substrat** ne disait, par site, si
un humain *peut effectivement allumer un feu ici, et comment*. Ce module comble ce
trou. Ce n'est **pas** un doublon de ``wildfire`` : celui-ci allume le monde
(foudre, propagation), celui-là expose l'**affordance d'amorçage anthropique**
(le briquet à pyrite, l'archet à feu) — complémentaires.

Ce n'est pas non plus un ``*_observer.py`` qui *mesure* le tick : c'est un
**signal de monde interrogeable** que les agents *consomment pour agir*, calculé
paresseusement par chunk et mémorisé — **coût de tick nul**. Il échappe au
moratoire observateurs (``CONTRIBUTING.md`` §"Moratoire observateurs").

N'introduit AUCUN nouveau « tell » minéral — il COMPOSE (garde-fou D8)
---------------------------------------------------------------------
Contrairement à C2/C4/C5/C6, ce module **ne surface aucune nouvelle matière** et
n'a donc **pas** de table ``_PROFILE`` : il ne crée pas d'entrée ``PY_TO_RUST`` /
``PY_CATALOGUE_ONLY`` (cf. ``test_geology_cross_language_contract``). Il *réutilise*
les tells déjà classés cross-langage :

* la **pyrite** (source d'étincelle) — c'est exactement le minéral du chapeau de
  fer (gossan) que C1 ``surface_mineralization`` surface déjà (``_RULES`` group
  ``gossan``) ;
* le **percuteur** (silex/obsidienne/quartzite/basalte dur) — exactement la
  pétrologie de taille de C2 ``lithic_outcrop`` (importée telle quelle :
  ``lo._candidates_in_layer`` / ``lo._has_carbonate_host`` — source unique de
  vérité, dont l'amélioration silex/chert ``CHERT_BONUS`` en hôte carbonaté).

Le garde-fou D8 ne vise (à dessein) que les fichiers ``*_outcrop.py`` portant un
``_PROFILE`` ; ce module n'en est pas un — c'est une **affordance composite**, pas
un affleurement. Décision consciente, documentée ici et asservie par
``test_fire_ignition.test_introduces_no_new_tell``.

Deux voies d'amorçage honnêtes et physiquement distinctes (veille 2026-06-15)
-----------------------------------------------------------------------------
La préhistoire réelle connaît deux familles de production du feu — toutes deux
modélisées, depuis le **substrat seul** :

1. **PERCUSSION (briquet à pierre / strike-a-light).** On frappe un nodule de
   **pyrite** (FeS₂ — sulfure de fer *pyrophorique* : l'éclat arraché s'oxyde en
   jetant une étincelle à ~800 °C) avec une **pierre dure** (silex/quartz). C'est
   la méthode d'Ötzi (pyrite + silex + amadou de polypore dans sa trousse, ~3300
   av. J.-C.) et du Mésolithique européen. Demande : pyrite peu profonde **ET**
   un percuteur **ET** un amadou (combustible fin) *assez* sec.

2. **FRICTION (archet/drille à feu).** Aucune pierre : on échauffe par frottement
   un foret de bois sur une planchette jusqu'à la braise, recueillie dans un
   amadou. Universelle (pas de pyrite requise) mais **plus exigeante en
   sécheresse** : un amadou humide tue la braise. Demande : combustible
   fin/ligneux **ET** un amadou *très* sec (seuil plus strict que la percussion).

La même prairie qu'on VOIT ne s'allume que **sèche** : effet 1+1>2 — géologie
(SYSTÈME C : pyrite + silex) × hydrologie de surface (SYSTÈME A : ``chunk.water``
→ humidité) × biome combustible (SYSTÈME E). Une seule vérité de substrat,
plusieurs lectures (C4 veut le combustible sec, C5 l'argile plastique, C6 la
pierre saine, C7 l'amadou sec).

Le monde ne ment jamais
-----------------------
Un site n'est déclaré inflammable QUE si les ingrédients existent réellement,
dans la même colonne ``chunk_geology`` que celle que ``mine_at`` exploite :
* ``can_percussion`` ⇒ une couche peu profonde porte de la **pyrite** dans son
  ``ore_mix`` (≥ seuil de visibilité) **et** un percuteur lithique réel est
  atteignable (``lo._candidates_in_layer`` ≥ qualité) **et** l'amadou est sec ;
* ``can_friction`` ⇒ combustible fin présent **et** humidité ≤ seuil friction.
Le site porte ``spark_depth_m`` : aller frapper là **rend** vraiment cette
pyrite. La réciproque est volontairement *faible* (absence d'amorçage ⇏ absence
d'ingrédient) : une pyrite sous 50 m de grès ne s'allume pas en surface. C'est
physiquement honnête et préserve l'émergence (on ne donne pas la recette).

Déterminisme
------------
Pur : fonction de ``chunk_geology`` (lui-même ``prf_rng``) + biome + champ
``chunk.water`` (issus du seed). Aucun RNG nouveau. Bit-identique entre deux runs
de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — l'affordance d'amorçage est une
lecture dérivée du substrat (géologie + eau + biome), comme C1→C6.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape
(chunk → affordance), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.geology import chunk_geology, install_geology, StrataLayer
from engine.world import CHUNK_SIDE_M, world_to_chunk
# Single source of truth for knapping petrology (the striker stone) — reused, not
# re-modelled. This keeps C7's percussion striker byte-consistent with C2's tells
# (incl. the flint/chert CHERT_BONUS upgrade in a carbonate host).
import engine.lithic_outcrop as lo

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

_OCEAN = 0

# A spark-source nodule (pyrite) is only perceivable / reachable for surface
# collection down to this depth (m). Same floor as the C1/C2/C5/C6 caps.
MAX_IGNITER_DEPTH_M = 6.0

# A pyrite ore-mix fraction must reach this to leave visible iron-stained float
# an agent can pick up and strike — same floor as C1 gossan visibility.
MIN_VISIBLE_FRACTION = 0.003

# Pyrophoric percussion spark sources. Striking iron disulfide shears off tiny
# particles that oxidise exothermically — the classic "firestone". Marcasite is
# the same FeS2 (not in the catalogue); only ``pyrite`` is modelled. NOTE: flint
# struck on flint barely sparks — it is flint struck *on pyrite* that ignites,
# which is exactly the C1(pyrite)+C2(flint striker) composition this cap reads.
_SPARK_MINERALS: Tuple[str, ...] = ("pyrite",)

# A lithic candidate this hard (C2 ``knap_quality``) can serve as a striker edge
# to spark pyrite. Equal to C2 ``MIN_KNAP_QUALITY``: any genuine hard stone works
# (flint/obsidian best — higher confidence; quartzite/basalt cobbles also spark).
STRIKER_MIN_QUALITY = 0.40

# Ambient ground moisture in [0,1] at/below which tinder catches a *spark*
# (percussion). Above it the tinder is too damp — the lie this cap exposes: the
# grass looks like tinder but a wet meadow will not take a spark.
PERCUSSION_DRY_MOISTURE = 0.58
# Friction (bow/hand drill) needs a *drier* tinder than a hot spark does — a damp
# punk kills the friction ember. Stricter threshold (veille 2026-06-15).
FRICTION_DRY_MOISTURE = 0.45

# Minimum fine-fuel availability to have any tinder at all (catch material).
FINE_FUEL_FLOOR = 0.30
# Friction also needs a woody spindle/hearth + more fuel than a spark — deserts
# (sparse fuel) fail friction even when bone dry; grass/forest pass.
FRICTION_FUEL_FLOOR = 0.45

# Surface-water field (litres, chunk mean) that saturates the wetness boost, and
# the maximum wetness it adds — identical to C4/C5/C6 (the one substrate model).
WATER_SATURATION_L = 200.0
MAX_WATER_BOOST = 0.30

# Ambient ground-moisture baseline by biome id — IDENTICAL to combustible_outcrop
# (C4), clay_outcrop (C5), limestone_outcrop (C6): the ONE shared substrate truth,
# read four ways (fuel wants dry, clay wants plastic, carbonate wants sound,
# tinder wants dry).
_BIOME_WETNESS: Dict[int, float] = {
    0: 1.00,   # OCEAN              — submerged (masked anyway)
    1: 0.80,   # ICE
    2: 0.70,   # TUNDRA
    3: 0.60,   # BOREAL_FOREST
    4: 0.50,   # TEMPERATE_FOREST
    5: 0.90,   # TEMPERATE_RAINFOREST
    6: 0.35,   # GRASSLAND          — dry grass = the canonical tinder
    7: 0.05,   # HOT_DESERT         — bone dry, but little fine fuel
    8: 0.10,   # COLD_DESERT
    9: 0.30,   # SAVANNA
    10: 0.40,  # TROPICAL_DRY_FOREST
    11: 0.95,  # TROPICAL_RAINFOREST
}

# Fine-fuel (grass / leaf-litter / fibrous tinder) availability by biome id. This
# is the tinder *load* — orthogonal to its dryness. Deserts and ice are dry but
# nearly fuel-less; grassland & forest are fuel-rich. A static, honest property
# of the biome type (like the wetness baseline), not a per-tick read.
_BIOME_FINE_FUEL: Dict[int, float] = {
    0: 0.00,   # OCEAN
    1: 0.05,   # ICE                — no fuel
    2: 0.35,   # TUNDRA             — sparse
    3: 0.70,   # BOREAL_FOREST
    4: 0.85,   # TEMPERATE_FOREST   — leaf litter / deadfall
    5: 0.90,   # TEMPERATE_RAINFOREST — abundant but damp
    6: 0.80,   # GRASSLAND          — cured grass, prime tinder
    7: 0.12,   # HOT_DESERT         — almost fuel-less
    8: 0.15,   # COLD_DESERT
    9: 0.75,   # SAVANNA            — tall dry grass
    10: 0.78,  # TROPICAL_DRY_FOREST
    11: 0.95,  # TROPICAL_RAINFOREST — abundant but soaked
}


class IgnitionMethod(IntEnum):
    """Easiest fire-making method available at a site (higher = easier/faster)."""
    NONE = 0        # no viable method here
    FRICTION = 1    # bow/hand drill — universal but slow & dryness-sensitive
    PERCUSSION = 2  # pyrite strike-a-light — fast, the preferred method


class TinderState(IntEnum):
    """Tinder condition governing whether a spark/ember catches."""
    NONE = 0   # no fine fuel (desert rock / ice / ocean)
    DAMP = 1   # fuel present but too wet to catch
    DRY = 2    # fuel present and dry enough for at least a hot spark


@dataclass(frozen=True)
class IgnitionCue:
    """A truthful fire-making affordance at one chunk.

    What an agent *perceives* on the ground: a brown iron-stained stone that
    throws sparks when struck (``spark_source``), a hard glassy/flinty cobble to
    strike it with (``striker_material``), and the state of the grass/litter
    tinder (``tinder_state``). It is NOT handed to the agent as "strike pyrite on
    flint over dry grass to make fire" — the agent must learn that correlation by
    acting. ``spark_source`` / ``spark_depth_m`` are the ground truth that proves
    the invariant (and that collecting there really yields the firestone).
    """
    coord: Tuple[int, int, int]
    biome: int
    # tinder
    ambient_moisture: float          # site wetness in [0,1] (biome + water)
    fine_fuel: float                 # tinder load in [0,1] (biome)
    tinder_state: TinderState
    # percussion ingredients (ground truth)
    spark_source: Optional[str]      # pyrophoric mineral reachable (or None)
    spark_depth_m: float             # depth that lands in the spark-source layer
    spark_fraction: float            # ore fraction of the spark source
    striker_material: Optional[str]  # hard stone to strike with (or None)
    striker_quality: float           # C2 knap_quality of the striker [0,1]
    # affordances
    can_percussion: bool             # pyrite + striker + dry-enough tinder
    can_friction: bool               # fuel + bone-dry tinder (no minerals)
    can_ignite: bool                 # percussion OR friction
    method: IgnitionMethod           # easiest method available
    confidence: float                # perceptual/practical confidence in [0,1]


# ---------------------------------------------------------------------------
# Core derivation — affordance from the same geology layers that mining reads.
# ---------------------------------------------------------------------------

def _dominant_biome(chunk) -> int:
    biomes, counts = np.unique(np.asarray(chunk.biome), return_counts=True)
    return int(biomes[int(np.argmax(counts))])


def _ambient_moisture(biome: int, chunk) -> float:
    """Site wetness in [0,1]: biome baseline + standing surface-water boost.

    Shared model with C4/C5/C6 so the capabilities agree on 'how wet is this
    ground' — the one substrate truth, several readings."""
    base = _BIOME_WETNESS.get(biome, 0.4)
    water = np.asarray(getattr(chunk, "water", None)) if hasattr(chunk, "water") else None
    boost = 0.0
    if water is not None and water.size:
        mean_w = float(water.mean())
        boost = MAX_WATER_BOOST * min(1.0, mean_w / WATER_SATURATION_L)
    return float(min(1.0, max(0.0, base + boost)))


def _best_spark_source(layers: List[StrataLayer]
                       ) -> Optional[Tuple[str, float, float]]:
    """Shallowest reachable pyrophoric spark source.

    Returns ``(material, depth_top_m, fraction)`` for the richest spark mineral
    in the shallowest qualifying layer, or None. Same ``ore_mix`` field C1's
    gossan rule reads and ``mine_at`` extracts."""
    best: Optional[Tuple[str, float, float]] = None
    best_key: Optional[Tuple[float, float]] = None
    for layer in layers:
        if layer.depth_top_m > MAX_IGNITER_DEPTH_M:
            continue
        for name in _SPARK_MINERALS:
            frac = float(layer.ore_mix.get(name, 0.0))
            if frac < MIN_VISIBLE_FRACTION:
                continue
            key = (layer.depth_top_m, -frac)  # shallower then richer
            if best_key is None or key < best_key:
                best_key = key
                best = (name, float(layer.depth_top_m), frac)
    return best


def _best_striker(layers: List[StrataLayer], biome: int
                  ) -> Optional[Tuple[str, float]]:
    """Best hard stone reachable shallow that can strike a spark off pyrite.

    Reuses C2's petrology verbatim (single source of truth, incl. the flint/chert
    CHERT_BONUS upgrade). Returns ``(material, knap_quality)`` or None."""
    carbonate_host = lo._has_carbonate_host(layers)
    best: Optional[Tuple[str, float]] = None
    for layer in layers:
        if layer.depth_top_m > lo.MAX_OUTCROP_DEPTH_M:
            continue
        for material, _source, quality in lo._candidates_in_layer(layer, carbonate_host):
            if quality < STRIKER_MIN_QUALITY:
                continue
            if best is None or quality > best[1]:
                best = (material, float(quality))
    return best


def _cue_from_geology(coord, layers: List[StrataLayer], biome: int, chunk
                      ) -> Optional[IgnitionCue]:
    """Pure derivation. Emits a cue iff a viable fire-making method exists here
    (``can_ignite``) — the actionable discovery. Ocean is masked."""
    if biome == _OCEAN:
        return None  # submerged
    moisture = _ambient_moisture(biome, chunk)
    fine_fuel = _BIOME_FINE_FUEL.get(biome, 0.4)

    tinder_available = fine_fuel >= FINE_FUEL_FLOOR
    spark_catchable = tinder_available and moisture <= PERCUSSION_DRY_MOISTURE
    friction_dry = (fine_fuel >= FRICTION_FUEL_FLOOR
                    and moisture <= FRICTION_DRY_MOISTURE)
    if not tinder_available:
        tinder_state = TinderState.NONE
    elif spark_catchable:
        tinder_state = TinderState.DRY
    else:
        tinder_state = TinderState.DAMP

    spark = _best_spark_source(layers)
    striker = _best_striker(layers, biome)

    can_percussion = bool(spark is not None and striker is not None
                          and spark_catchable)
    can_friction = bool(friction_dry)
    can_ignite = can_percussion or can_friction
    if not can_ignite:
        return None

    if can_percussion:
        method = IgnitionMethod.PERCUSSION
    elif can_friction:
        method = IgnitionMethod.FRICTION
    else:  # pragma: no cover — unreachable given can_ignite
        method = IgnitionMethod.NONE

    spark_name = spark[0] if spark is not None else None
    spark_depth = spark[1] if spark is not None else 0.0
    spark_frac = spark[2] if spark is not None else 0.0
    striker_name = striker[0] if striker is not None else None
    striker_q = striker[1] if striker is not None else 0.0

    # Confidence: how reliably a fire starts here. Percussion with a sharp flint
    # over dry grass is a near-certainty; a marginal friction site is a chore.
    dryness = max(0.0, 1.0 - moisture)
    if can_percussion:
        base = 0.55 + 0.45 * min(1.0, striker_q)
    else:
        base = 0.30 + 0.40 * dryness
    confidence = float(min(1.0, base * (0.5 + 0.5 * min(1.0, fine_fuel))))

    return IgnitionCue(
        coord=tuple(int(c) for c in coord), biome=int(biome),
        ambient_moisture=float(round(moisture, 4)),
        fine_fuel=float(round(fine_fuel, 4)), tinder_state=tinder_state,
        spark_source=spark_name, spark_depth_m=float(spark_depth),
        spark_fraction=float(spark_frac),
        striker_material=striker_name, striker_quality=float(striker_q),
        can_percussion=can_percussion, can_friction=can_friction,
        can_ignite=can_ignite, method=method, confidence=confidence)


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_fire_ignition(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim``.

    Adds **zero** per-tick cost: affordances are derived on query and memoised.
    Returns the cache dict (``sim._ignition_cue_cache``).
    """
    install_geology(sim)  # ensure geology state exists
    cache = getattr(sim, "_ignition_cue_cache", None)
    if cache is None:
        cache = {}
        sim._ignition_cue_cache = cache
    return cache


def ignition_cue_for_chunk(sim, coord: Tuple[int, int, int]
                           ) -> Optional[IgnitionCue]:
    """Truthful fire-making affordance at ``coord`` (or None if no method). Memoised.

    Invariant: if this returns a cue, ``can_ignite`` is True and every positive
    claim is grounded — ``can_percussion`` ⇒ ``chunk_geology(sim, coord)`` has a
    shallow layer whose ``ore_mix`` carries ``spark_source`` and a reachable
    striker; ``can_friction`` ⇒ moisture ≤ friction threshold with fuel.
    """
    coord = tuple(int(c) for c in coord)
    cache = install_fire_ignition(sim)
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


def prospect_ignition(sim, world_x: float, world_y: float
                      ) -> Optional[IgnitionCue]:
    """What an agent standing at world ``(x, y)`` perceives of the fire-making
    affordance here. Returns the cue (spark stone + striker + tinder) or None."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return ignition_cue_for_chunk(sim, coord)


def ignition_preview(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of whether (and how) a fire can be started at
    ``(x, y)`` — the ground-truthed outcome the perception cue must agree with.

    Touches NOTHING (no spark struck, no geology mutated): it is the truth
    oracle, not the action. Always returns a dict (even when ``can_ignite`` is
    False), naming the *missing* ingredient — the honest 'why not'. The lie this
    cap exposes: a lush damp meadow looks like tinder (``tinder_available``) but a
    spark won't take when wet (``tinder_state == DAMP``)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    g = chunk_geology(sim, coord)
    chunk = sim.streamer.cache.get(coord)
    if g is None or chunk is None:
        return {"can_ignite": False, "method": None, "reason": "unloaded chunk"}
    biome = _dominant_biome(chunk)
    cue = _cue_from_geology(coord, g.layers, biome, chunk)
    if cue is not None:
        reason = "ok"
    else:
        # Recompute the diagnostic (cue is None precisely when not ignitable).
        moisture = _ambient_moisture(biome, chunk)
        fine_fuel = _BIOME_FINE_FUEL.get(biome, 0.4)
        if biome == _OCEAN:
            reason = "submerged"
        elif fine_fuel < FINE_FUEL_FLOOR:
            reason = "no fine fuel (no tinder)"
        elif moisture > PERCUSSION_DRY_MOISTURE:
            reason = "tinder too damp to catch"
        else:
            reason = "no spark source and friction tinder too damp"
        return {"can_ignite": False, "method": "none", "reason": reason,
                "biome": int(biome),
                "ambient_moisture": float(round(moisture, 4)),
                "fine_fuel": float(round(fine_fuel, 4)),
                "tinder_available": bool(fine_fuel >= FINE_FUEL_FLOOR)}
    return {"can_ignite": True, "method": cue.method.name,
            "reason": reason,
            "can_percussion": cue.can_percussion,
            "can_friction": cue.can_friction,
            "spark_source": cue.spark_source,
            "spark_depth_m": cue.spark_depth_m,
            "striker_material": cue.striker_material,
            "striker_quality": cue.striker_quality,
            "tinder_state": cue.tinder_state.name,
            "tinder_available": True,
            "ambient_moisture": cue.ambient_moisture,
            "fine_fuel": cue.fine_fuel,
            "biome": cue.biome}


def discover_firesites_by_sight(sim, rows: List[int],
                                perception_radius_m: float = 64.0
                                ) -> Dict[int, List[IgnitionCue]]:
    """For each agent ``row``, the fire-makeable sites perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    This is the capability that turns the static substrate (buried pyrite, hard
    stone, dry grass) into a **perceivable, actionable** signal — the agent then
    *chooses* to strike or drill. Deterministic order (by chunk distance, coord).
    """
    out: Dict[int, List[IgnitionCue]] = {}
    if not rows:
        return out
    install_fire_ignition(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], IgnitionCue]] = []
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
                cue = ignition_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_firesite_near(sim, row: int, perception_radius_m: float = 128.0,
                       *, require_percussion: bool = False) -> Optional[IgnitionCue]:
    """The easiest fire-making site an agent at ``row`` can perceive — the
    actionable pick (percussion preferred, then highest confidence; tie-break
    nearest then coord).

    ``require_percussion`` keeps only pyrite strike-a-light sites (the pick when
    an agent has learned the fast method and seeks a firestone). Returns None when
    nothing matching is in sight (a physically honest 'no fire to be made here').
    """
    cues = discover_firesites_by_sight(sim, [int(row)], perception_radius_m
                                       ).get(int(row), [])
    pool = [c for c in cues if c.can_percussion] if require_percussion else cues
    if not pool:
        return None
    # already distance-sorted; prefer easier method, then confidence.
    return max(pool, key=lambda c: (int(c.method), c.confidence))


def ignition_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_fire_ignition(sim)
    by_method: Dict[str, int] = {}
    by_tinder: Dict[str, int] = {}
    n_chunks = 0
    n_ignitable = 0
    n_percussion = 0
    n_friction = 0
    best_conf = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = ignition_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_ignitable += 1
        if cue.can_percussion:
            n_percussion += 1
        if cue.can_friction:
            n_friction += 1
        by_method[cue.method.name] = by_method.get(cue.method.name, 0) + 1
        by_tinder[cue.tinder_state.name] = by_tinder.get(cue.tinder_state.name, 0) + 1
        best_conf = max(best_conf, cue.confidence)
    return {
        "n_chunks": n_chunks,
        "n_chunks_ignitable": n_ignitable,
        "ignitable_rate": round(n_ignitable / n_chunks, 4) if n_chunks else 0.0,
        "n_percussion": n_percussion,
        "n_friction": n_friction,
        "best_confidence": round(best_conf, 4),
        "by_method": dict(sorted(by_method.items())),
        "by_tinder": dict(sorted(by_tinder.items())),
    }


__all__ = [
    "IgnitionCue", "IgnitionMethod", "TinderState",
    "install_fire_ignition", "ignition_cue_for_chunk", "prospect_ignition",
    "ignition_preview", "discover_firesites_by_sight", "best_firesite_near",
    "ignition_summary",
    "MAX_IGNITER_DEPTH_M", "MIN_VISIBLE_FRACTION", "STRIKER_MIN_QUALITY",
    "PERCUSSION_DRY_MOISTURE", "FRICTION_DRY_MOISTURE", "FINE_FUEL_FLOOR",
    "FRICTION_FUEL_FLOOR", "WATER_SATURATION_L", "MAX_WATER_BOOST",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
