"""Genesis Engine — Substrate capability : le four à tirage (Cap. C11).

**L'apparatus qui élève la température** — la VOÛTE que C9 ``ceramic_firing`` ET C10
``lime_burning`` désignent *toutes deux* explicitement. C9 laisse
``vitrifies_if_kiln_fired`` non réalisé ; C10 laisse ``would_mortar_if_kiln_fired``
non réalisé : **les deux pointent vers le même outil futur — un four**. Un feu nu
plafonne (~850 °C, SSOT C9) parce qu'il perd presque toute sa chaleur à l'air libre.
**Enfermer** ce feu dans une enceinte d'argile et lui donner un **tirage** (cheminée
/ tirage ascendant) le rend *plus chaud* et *plus longtemps* : c'est un **four à
tirage** (updraft kiln), ~1000–1100 °C — le régime qui cuit le calcaire pur **à
cœur** (mortier liant, C10 réalisé) et fritte le kaolin en **corps sain** (C9
racheté).

**Règle invariante du projet** (cf. ``surface_mineralization`` (C1) …
``lime_burning`` (C10)) : rien n'est scripté. Un agent ne *sait* pas qu'« on
construit un four pour cuire plus chaud ». Il sait déjà **faire du feu** ici (C7), il
**voit** l'argile collante du sol (C5) — et en **chemisant** par hasard son foyer de
cette argile (pour le contenir, le protéger du vent) il **découvre** que le feu
enclos *rugit* plus fort et que ses pots en sortent *durs et sonnants* là où le feu
nu les laissait friables. Ce module n'expose qu'un **signal physique véridique** : *un
feu enclos dans CETTE argile-ci, nourri de CE combustible-ci, atteindrait telle
température de pointe, et y cuirait telle matière à tel degré*. La forme du four, la
cheminée, le tirage, l'alandier, l'empilement — toute la chaîne opératoire reste
**émergente**.

Ce n'est PAS une transformation de matière : c'est un APPARATUS (le pendant de C7)
-------------------------------------------------------------------------------------
C7 ``fire_ignition`` expose l'affordance « un feu *peut* être fait ici ». C11 expose
l'affordance « un **four** (un feu enclos plus chaud) *peut* être fait ici » — il faut
de l'**argile de paroi** (C5) ET un **feu** (C7). Le four ne *fabrique* pas de
nouvelle matière ; il **élève la température de pointe** que voit la matière, et c'est
cette pointe plus haute qui débloque les transformations différées de C9 et C10. Le
monde s'**engage** sur ``kiln_peak_temp_c`` (déterministe, ground-truthé) : « si tu
enclos ce feu dans cette argile, il atteindra *exactement* cette pointe ».

N'introduit AUCUN nouveau « tell » minéral — il COMPOSE (garde-fou D8)
---------------------------------------------------------------------
Comme C7/C8/C9/C10, ce module **ne surface aucune nouvelle matière**, n'a **pas** de
table ``_PROFILE`` et **ne crée aucune entrée** ``PY_TO_RUST`` / ``PY_CATALOGUE_ONLY``
(cf. ``test_geology_cross_language_contract``). C'est la **5ᵉ** capacité D8-par-
composition. Il *lit* trois capacités déjà classées cross-langage :

* l'**argile** — pétrologie de C5 ``clay_outcrop`` (``clay_cue_for_chunk`` : matière,
  ``clay_class``, ``ceramic_grade`` = paroi réfractaire ⇔ kaolin, ``pottery_grade``) ;
* le **feu** — affordance de C7 ``fire_ignition`` (``ignition_cue_for_chunk`` :
  ``fine_fuel`` qui gouverne la pointe atteinte) ;
* le **calcaire** — pétrologie de C6 ``limestone_outcrop`` (pour réaliser le mortier).

Et il **réutilise verbatim** les SSOT physiques de C9 (``open_fire_peak_temp_c``,
``clay_maturation_temp_c``, ``fired_ware_quality``) et de C10 (``calcination_onset_c``,
``calcination_extent``, ``quicklime_quality``) — recomposées à la pointe du four. Le
fichier est volontairement **hors du glob** ``*_outcrop.py`` : ce n'est pas un
affleurement, c'est un apparatus. Décision asservie par ``test_introduces_no_new_tell``.

Le COMBO de la veille 2026-06-17 (run #2) — la thermodynamique de l'enceinte
----------------------------------------------------------------------------
La pointe d'un four est **gouvernée par la physique**, jamais arbitraire (méta-règle
du substrat). Deux quantités se rencontrent :

1. **Pointe du feu nu** (``cf.open_fire_peak_temp_c`` — réemploi C9, *le combo* : un
   seul modèle de feu, l'apparatus ne fait que l'enclore). 600–850 °C.

2. **Gain d'enceinte** (``KILN_ENCLOSURE_GAIN_C``). L'enceinte réduit les pertes ; le
   tirage ascendant apporte l'O₂ et intensifie la combustion → la pointe monte, et
   **plafonne à la réfractarité de la paroi** :
   * paroi en argile **commune** (``COMMON_CLAY``) — elle **flue / s'effondre**
     au-dessus de ~1000 °C : plafond ``KILN_COMMON_WALL_CAP_C``.
   * paroi en argile **réfractaire** (kaolin, ``PLASTIC_CLAY`` / ``ceramic_grade``) —
     la *fire-clay* tient 1515–1775 °C : elle **survit** et **isole**, permettant
     ``KILN_REFRACTORY_WALL_CAP_C`` (~1150 °C en tirage naturel).

Le mensonge rendu visible — l'inversion DE l'inversion (le rachat du kaolin C9)
------------------------------------------------------------------------------
C9 a posé le « mensonge du kaolin » : la plus belle argile (kaolin, ``ceramic_grade``)
**sous-cuit** comme *poterie* au feu ouvert (réfractaire). C11 **renverse** ce piège :
ce même kaolin réfractaire est la **MEILLEURE argile de PAROI** — c'est *grâce à lui*
qu'on bâtit le four assez chaud pour, enfin, cuire le kaolin **à cœur** (corps sain).
La matière piégée comme *objet* est précieuse comme *outil*. ``best_kiln_site_near``
(préfère la pointe la plus haute) enseigne donc : **chemise ton four de l'argile
blanche collante** — elle survit là où l'argile grise commune s'effondre.

Effet 1+1>2 et « le monde ne ment jamais »
------------------------------------------
Le four n'est possible QUE là où **les deux** ingrédients coexistent réellement dans
la même colonne : une argile de paroi (C5) **ET** un feu faisable (C7). Et il
**débloque deux transformations** d'un coup — le mortier liant (C10) et le kaolin
sain (C9). Si ``kiln_cue_for_chunk`` renvoie une indication, ``buildable`` est vrai et
le résultat est **ground-truthé** : recomposer C9/C10 à ``kiln_peak_c`` donne
*exactement* ``kiln_ware_quality`` / ``mortar_lime_yield``.

La marche différée honnête — le tirage FORCÉ (C12+)
---------------------------------------------------
Le tirage **naturel** de C11 plafonne sous la vitrification complète de la porcelaine
(~1250 °C) et sous la métallurgie. ``vitrifies_watertight`` reste donc (presque
toujours) False, et ``vitrifies_if_forced_draught`` porte le **potentiel non
réalisé** : un **soufflet** + du **charbon de bois** (1100–1300 °C, régime du bas-
fourneau) — exactement comme C9/C10 différaient *vers* le four, C11 diffère *vers* le
tirage forcé. La chaîne reste ouverte et honnête.

Déterminisme
------------
Pur : composition de ``clay_cue_for_chunk`` (C5), ``ignition_cue_for_chunk`` (C7) et
``limestone_cue_for_chunk`` (C6), tous ``prf_rng`` / dérivés du seed, avec des SSOT
purs (C9/C10). Aucun RNG nouveau. Bit-identique entre deux runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — le four est une lecture dérivée du
substrat (argile + feu), comme C1→C10.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape (chunk →
affordance d'apparatus), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from engine.world import CHUNK_SIDE_M, world_to_chunk
# Single sources of truth — reused verbatim, never re-modelled (garde-fou D8).
import engine.clay_outcrop as ci          # C5 — wall material + the pottery body
import engine.fire_ignition as fi         # C7 — the fire-making affordance (fuel)
import engine.limestone_outcrop as li     # C6 — the carbonate (mortar realization)
import engine.ceramic_firing as cf        # C9 — open-fire peak + clay maturation SSOTs
import engine.lime_burning as lb          # C10 — calcination onset/extent/quality SSOTs

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# --- Enclosure thermodynamics (°C). The peak an enclosed updraft kiln reaches over a
# bare open fire. A kiln captures heat (enclosure) and roars (draught), adding up to
# ``KILN_ENCLOSURE_GAIN_C`` above the open-fire peak — but the achievable ceiling is
# capped by how hot the *wall clay* can be held before it slumps.
KILN_ENCLOSURE_GAIN_C = 300.0        # max extra °C an enclosed updraft adds over a bare fire

# Wall caps (°C): a common clay wall fluxes and slumps near ~1000 °C; a refractory
# fire-clay (kaolin) wall survives far higher (service T 1515–1775 °C) and so permits
# a hotter natural-draught kiln. The honest ceiling each wall material commits to.
KILN_COMMON_WALL_CAP_C = 1000.0      # common earthenware clay walls — slump above this
KILN_REFRACTORY_WALL_CAP_C = 1150.0  # refractory kaolin / fire-clay walls — natural-draught ceiling

# Fraction of full clay maturation at/above which a ceramic-grade body turns fully
# *watertight* (vitrified, porcelain-like). A natural-draught kiln (<= refractory cap)
# never quite reaches it for refractory kaolin (maturation ~1250 °C): that final step
# needs FORCED draught (bellows + charcoal), the deferred next tier. So
# ``vitrifies_watertight`` stays False here and ``vitrifies_if_forced_draught`` carries
# the unrealized potential — the exact counterpart of C9/C10's ``*_if_kiln_fired``.
VITRIFICATION_FIREDNESS = 0.98


@dataclass(frozen=True)
class KilnCue:
    """A truthful kiln (enclosed-updraft-fire) affordance at one chunk.

    What an agent *could* discover by lining the fire it already makes (C7) with the
    clay it already shapes (C5): an enclosed, drafted fire that runs **hotter** than a
    bare bonfire, finally hard-burning pure limestone to **binding mortar** (C10
    realized) and firing kaolin to a **sound body** (C9 redeemed). It is NOT handed to
    the agent as "build a kiln to fire hotter" — the agent must learn the
    enclosure->heat correlation by acting. ``kiln_peak_c`` (and the recomposed
    ``kiln_ware_quality`` / ``mortar_lime_yield``) are the ground truth the world
    commits to (doing it yields exactly this).
    """
    coord: Tuple[int, int, int]
    biome: int
    # wall material AND pottery body (read from C5 clay_outcrop)
    wall_material: str             # ground-truth clay the walls/body are made of
    wall_clay_class: str           # C5 ClayClass name (COMMON_/PLASTIC_CLAY)
    wall_refractory: bool          # C5 ceramic_grade — kaolin walls survive high heat
    clay_pottery_grade: float      # C5 intrinsic firing/vitrification rank [0,1]
    clay_ceramic_grade: bool       # C5: the body CAN vitrify watertight (enough heat)
    collect_depth_m: float         # depth that lands in the proving C5 layer
    # fuel (read from C7 fire_ignition)
    fire_method: str               # easiest ignition method available here
    fire_confidence: float         # C7 reliability of making a fire here [0,1]
    fine_fuel: float               # C7 fine-fuel load (drives the peak temperature)
    # apparatus outcome (the truth the world commits to)
    buildable: bool                # wall-clay AND a fire are makeable here
    open_fire_peak_c: float        # what a *bare* fire here would reach (C9 baseline)
    wall_cap_c: float              # the ceiling these walls permit (slump limit)
    kiln_peak_c: float             # what this enclosed updraft kiln reaches (SSOT)
    draft_gain_c: float            # kiln_peak - open_fire_peak (the enclosure win)
    # unlocked: pottery (C9 SSOTs recomposed at the kiln peak)
    clay_firedness: float          # min(1, kiln_peak / maturation) for the local clay
    fires_clay_sound: bool         # the local clay fires to a SOUND body in this kiln
    kiln_ware_quality: float       # quality of the kiln-fired vessel [0,1] (ground truth)
    vitrifies_watertight: bool     # natural draught ~ never vitrifies -> usually False
    vitrifies_if_forced_draught: bool  # unrealized potential — bellows + charcoal (C12+)
    # unlocked: mortar (C10 SSOTs recomposed at the kiln peak — C6 limestone here)
    limestone_here: bool           # a carbonate (C6) is also reachable in this column
    realizes_binding_mortar: bool  # the kiln hard-burns a pure limestone to mortar (C10 realized)
    mortar_lime_yield: float       # quality of the mortar-grade lime the kiln yields [0,1]
    confidence: float              # reliability of achieving the kiln outcome [0,1]


# ---------------------------------------------------------------------------
# Single source of truth — the enclosure physics the world commits to.
# ---------------------------------------------------------------------------

def kiln_peak_temp_c(fine_fuel: float, wall_refractory: bool) -> float:
    """Peak temperature (°C) an enclosed updraft kiln reaches, from its fuel load and
    the refractoriness of its walls.

    Deterministic SSOT and *the combo*: the base is C9's open-fire peak (reused
    verbatim — the apparatus only encloses that same fire), plus an enclosure gain
    that scales with the fuel, the whole capped by the wall material's slump ceiling.
    A common-clay wall caps low (``KILN_COMMON_WALL_CAP_C``); a refractory kaolin /
    fire-clay wall survives higher (``KILN_REFRACTORY_WALL_CAP_C``). A natural-draught
    kiln never reaches forced-draught (bloomery) temperatures — the honest ceiling
    this capability commits to."""
    f = min(1.0, max(0.0, float(fine_fuel)))
    base = cf.open_fire_peak_temp_c(f)                 # combo: reuse C9 SSOT
    gain = KILN_ENCLOSURE_GAIN_C * (0.5 + 0.5 * f)     # enclosure + draught, fuel-scaled
    cap = KILN_REFRACTORY_WALL_CAP_C if wall_refractory else KILN_COMMON_WALL_CAP_C
    return float(min(base + gain, cap))


# ---------------------------------------------------------------------------
# Core derivation — apparatus outcome from C5 clay (walls/body) x C7 fire (fuel),
# with C9/C10 transformations recomposed at the kiln's peak.
# ---------------------------------------------------------------------------

def _cue_from_inputs(coord, clay_cue, fire_cue, lime_cue=None) -> Optional[KilnCue]:
    """Pure derivation (no ``sim`` — trivially unit-testable, like its siblings).
    Emits a cue iff the site is **buildable** — wall-clay (C5) AND a makeable fire
    (C7) coexist here. The 1+1>2 gate: either ingredient missing => no kiln
    affordance. ``lime_cue`` (C6) is optional: when present, the kiln's peak is
    recomposed through C10 to report whether it *realizes* binding mortar."""
    if clay_cue is None or fire_cue is None:
        return None

    fine_fuel = float(getattr(fire_cue, "fine_fuel", 0.0))
    wall_refractory = bool(clay_cue.ceramic_grade)
    wall_cap = KILN_REFRACTORY_WALL_CAP_C if wall_refractory else KILN_COMMON_WALL_CAP_C
    open_peak = cf.open_fire_peak_temp_c(fine_fuel)
    peak = kiln_peak_temp_c(fine_fuel, wall_refractory)
    draft_gain = peak - open_peak

    # Pottery in the kiln — recompose C9 at the kiln peak (the local clay as body).
    maturation = cf.clay_maturation_temp_c(bool(clay_cue.ceramic_grade))
    firedness = min(1.0, peak / maturation) if maturation > 0 else 1.0
    fires_sound = firedness >= cf.SOUND_MATURATION
    ware = cf.fired_ware_quality(clay_cue.pottery_grade, firedness)
    vitrified = bool(clay_cue.ceramic_grade and firedness >= VITRIFICATION_FIREDNESS)
    # the unrealized step a forced-draught (bellows + charcoal) kiln would finish.
    vitrifies_forced = bool(clay_cue.ceramic_grade and not vitrified)

    # Mortar in the kiln — recompose C10 at the kiln peak if a carbonate is here too.
    limestone_here = lime_cue is not None
    realizes_mortar = False
    mortar_yield = 0.0
    if lime_cue is not None:
        onset = lb.calcination_onset_c(lime_cue.lime_class)
        extent = lb.calcination_extent(peak, onset)
        mortar_grade = bool(getattr(lime_cue, "mortar_grade", False))
        realizes_mortar = bool(mortar_grade and extent >= lb.MORTAR_CALCINATION)
        mortar_yield = lb.quicklime_quality(lime_cue.lime_grade, extent)

    fire_conf = float(getattr(fire_cue, "confidence", 0.0))
    clay_conf = float(getattr(clay_cue, "confidence", 0.0))
    confidence = float(min(1.0, fire_conf * (0.5 + 0.5 * clay_conf)))
    method = fire_cue.method.name if hasattr(fire_cue, "method") else "NONE"

    return KilnCue(
        coord=tuple(int(c) for c in coord), biome=int(clay_cue.biome),
        wall_material=clay_cue.material,
        wall_clay_class=clay_cue.clay_class.name,
        wall_refractory=wall_refractory,
        clay_pottery_grade=float(round(clay_cue.pottery_grade, 4)),
        clay_ceramic_grade=bool(clay_cue.ceramic_grade),
        collect_depth_m=float(clay_cue.collect_depth_m),
        fire_method=method, fire_confidence=float(round(fire_conf, 4)),
        fine_fuel=float(round(fine_fuel, 4)),
        buildable=True,
        open_fire_peak_c=float(round(open_peak, 1)),
        wall_cap_c=float(wall_cap),
        kiln_peak_c=float(round(peak, 1)),
        draft_gain_c=float(round(draft_gain, 1)),
        clay_firedness=float(round(firedness, 4)),
        fires_clay_sound=bool(fires_sound),
        kiln_ware_quality=float(round(ware, 4)),
        vitrifies_watertight=bool(vitrified),
        vitrifies_if_forced_draught=bool(vitrifies_forced),
        limestone_here=bool(limestone_here),
        realizes_binding_mortar=bool(realizes_mortar),
        mortar_lime_yield=float(round(mortar_yield, 4)),
        confidence=float(round(confidence, 4)))


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_kiln_draft(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim`` and ensures
    the composed capabilities (C5 clay walls, C7 fire, C6 carbonate) are installed.

    Adds **zero** per-tick cost: affordances are derived on query and memoised.
    Returns the cache dict (``sim._kiln_draft_cue_cache``).
    """
    ci.install_clay_outcrop(sim)
    fi.install_fire_ignition(sim)
    li.install_limestone_outcrop(sim)
    cache = getattr(sim, "_kiln_draft_cue_cache", None)
    if cache is None:
        cache = {}
        sim._kiln_draft_cue_cache = cache
    return cache


def kiln_cue_for_chunk(sim, coord: Tuple[int, int, int]) -> Optional[KilnCue]:
    """Truthful kiln affordance at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, ``buildable`` is True — C5
    ``clay_cue_for_chunk(sim, coord)`` proves wall-clay is reachable in the same
    column and C7 ``ignition_cue_for_chunk(sim, coord)`` proves a fire can be made
    here. ``kiln_peak_c`` is the ground-truth peak temperature the enclosure reaches.
    """
    coord = tuple(int(c) for c in coord)
    cache = install_kiln_draft(sim)
    if coord in cache:
        return cache[coord]
    clay = ci.clay_cue_for_chunk(sim, coord)
    fire = fi.ignition_cue_for_chunk(sim, coord)
    lime = li.limestone_cue_for_chunk(sim, coord)
    cue = _cue_from_inputs(coord, clay, fire, lime)
    cache[coord] = cue
    return cue


def prospect_kiln(sim, world_x: float, world_y: float) -> Optional[KilnCue]:
    """What an agent standing at world ``(x, y)`` could discover about building a
    kiln here. Returns the cue (kiln peak + unlocked outcomes) or None when no
    wall-clay-plus-fire is underfoot."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return kiln_cue_for_chunk(sim, coord)


def kiln_preview(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of whether (and how hot) a kiln at ``(x, y)`` would
    run, and what it would unlock — the ground-truthed outcome the perception cue
    must agree with.

    Touches NOTHING (no clay dug, no fire lit, no wall built): the truth oracle, not
    the action. Always returns a dict (even when not buildable), naming the *missing*
    ingredient — the honest 'why not'. The inversion-of-the-inversion this cap
    exposes: a refractory kaolin clay (the 'bad' pottery clay of C9) makes the
    *hottest* walls (``wall_refractory`` True, highest ``kiln_peak_c``)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = kiln_cue_for_chunk(sim, coord)
    if cue is not None:
        return {"buildable": True, "reason": "ok",
                "wall_material": cue.wall_material,
                "wall_refractory": cue.wall_refractory,
                "open_fire_peak_c": cue.open_fire_peak_c,
                "kiln_peak_c": cue.kiln_peak_c,
                "draft_gain_c": cue.draft_gain_c,
                "wall_cap_c": cue.wall_cap_c,
                "fires_clay_sound": cue.fires_clay_sound,
                "kiln_ware_quality": cue.kiln_ware_quality,
                "vitrifies_watertight": cue.vitrifies_watertight,
                "vitrifies_if_forced_draught": cue.vitrifies_if_forced_draught,
                "limestone_here": cue.limestone_here,
                "realizes_binding_mortar": cue.realizes_binding_mortar,
                "mortar_lime_yield": cue.mortar_lime_yield,
                "fire_method": cue.fire_method,
                "confidence": cue.confidence,
                "biome": cue.biome}
    # Not buildable — recompute the diagnostic to name the missing ingredient.
    clay = ci.clay_cue_for_chunk(sim, coord)
    fire = fi.ignition_cue_for_chunk(sim, coord)
    if clay is None:
        reason = "no wall-clay here to line a kiln"
    elif fire is None:
        reason = "no fire can be made here to run a kiln"
    else:  # pragma: no cover — both present would have produced a cue
        reason = "not buildable"
    return {"buildable": False, "reason": reason,
            "wall_material": (clay.material if clay is not None else None),
            "has_clay": bool(clay is not None),
            "has_fire": bool(fire is not None)}


def discover_kiln_sites_by_sight(sim, rows: List[int],
                                 perception_radius_m: float = 64.0
                                 ) -> Dict[int, List[KilnCue]]:
    """For each agent ``row``, the kiln-buildable sites perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    Turns the static substrate (a clay outcrop + a fire-makeable spot) into a
    **perceivable, actionable** apparatus signal — the agent then *chooses* to line
    a fire with the clay. Deterministic order (by chunk distance, then coord).
    """
    out: Dict[int, List[KilnCue]] = {}
    if not rows:
        return out
    install_kiln_draft(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], KilnCue]] = []
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
                cue = kiln_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_kiln_site_near(sim, row: int, perception_radius_m: float = 128.0,
                        *, require_refractory: bool = False) -> Optional[KilnCue]:
    """The hottest kiln an agent at ``row`` can perceive — the actionable pick
    (highest ``kiln_peak_c``; tie-break higher confidence, then nearest then coord).

    This is where the inversion-of-the-inversion teaches: preferring the hottest
    kiln, the agent learns to line its fire with the refractory white clay (kaolin)
    that survives the heat — the very clay that under-fires as a *pot* in an open
    fire (C9). ``require_refractory`` keeps only kilns walled with refractory clay.
    Returns None when nothing buildable is in sight."""
    cues = discover_kiln_sites_by_sight(sim, [int(row)], perception_radius_m
                                        ).get(int(row), [])
    pool = [c for c in cues if c.wall_refractory] if require_refractory else cues
    if not pool:
        return None
    # already distance-sorted; prefer the hottest kiln, then the surest build.
    return max(pool, key=lambda c: (c.kiln_peak_c, c.confidence))


def kiln_draft_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_kiln_draft(sim)
    by_wall: Dict[str, int] = {}
    n_chunks = 0
    n_buildable = 0
    n_refractory = 0
    n_realizes_mortar = 0
    n_fires_sound = 0
    best_peak = 0.0
    best_gain = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = kiln_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_buildable += 1
        if cue.wall_refractory:
            n_refractory += 1
        if cue.realizes_binding_mortar:
            n_realizes_mortar += 1
        if cue.fires_clay_sound:
            n_fires_sound += 1
        by_wall[cue.wall_material] = by_wall.get(cue.wall_material, 0) + 1
        best_peak = max(best_peak, cue.kiln_peak_c)
        best_gain = max(best_gain, cue.draft_gain_c)
    return {
        "n_chunks": n_chunks,
        "n_chunks_buildable": n_buildable,
        "buildable_rate": round(n_buildable / n_chunks, 4) if n_chunks else 0.0,
        "n_refractory_walled": n_refractory,
        "n_realizes_binding_mortar": n_realizes_mortar,
        "n_fires_clay_sound": n_fires_sound,
        "best_kiln_peak_c": round(best_peak, 1),
        "best_draft_gain_c": round(best_gain, 1),
        "by_wall_material": dict(sorted(by_wall.items())),
    }


__all__ = [
    "KilnCue",
    "install_kiln_draft", "kiln_cue_for_chunk", "prospect_kiln",
    "kiln_preview", "discover_kiln_sites_by_sight", "best_kiln_site_near",
    "kiln_draft_summary",
    "kiln_peak_temp_c",
    "KILN_ENCLOSURE_GAIN_C", "KILN_COMMON_WALL_CAP_C", "KILN_REFRACTORY_WALL_CAP_C",
    "VITRIFICATION_FIREDNESS",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
