"""Genesis Engine — Substrate capability : le tirage forcé (Cap. C12).

**Le 2ᵉ APPARATUS** (après C11 ``kiln_draft``) — et la **VOÛTE que C9
``ceramic_firing`` ET C11 ``kiln_draft`` désignent toutes deux** explicitement par
leur potentiel non réalisé ``vitrifies_if_forced_draught``. Le four à tirage
*naturel* (C11) plafonne sous la vitrification de la porcelaine (~1250 °C) et sous
la métallurgie : ``vitrifies_watertight`` y reste (presque toujours) False. Le pas
qui manque est un **tirage FORCÉ** — un **soufflet** (ou une sarbacane) qui injecte
l'air, et un combustible **dense et propre** : du **charbon de bois**. Souffler de
l'air dans un foyer de charbon de bois enclos pousse la pointe dans le **régime du
bas-fourneau** (~1100–1400 °C) : assez chaud pour **vitrifier** le kaolin réfractaire
(céramique étanche, C9/C11 enfin réalisé) et pour **fondre le cuivre** (1085 °C —
le seuil chalcolithique, le premier métal). Ce module **réalise la vitrification** et
**ouvre la métallurgie**.

**Règle d'émergence absolue** (cf. ``surface_mineralization`` (C1) …
``kiln_draft`` (C11)) : rien n'est scripté. Un agent ne *sait* pas qu'« on souffle
de l'air sur du charbon pour fondre le métal ». Il sait déjà **faire un four** ici
(C11), il a vu sa braise **rugir** quand le vent s'y engouffre, il a remarqué que le
**bois carbonisé** (à demi-brûlé, étouffé sous la terre) brûle plus chaud et sans
flamme. En **soufflant** par hasard dans son foyer enclos — d'abord à la bouche, puis
avec une outre, une peau, un soufflet — il **découvre** que la chaleur monte assez
pour faire **suinter le métal** de la pierre verte (C1) et rendre ses pots
**étanches**. Ce module n'expose qu'un **signal physique véridique** : *un four enclos
de CETTE paroi-ci, nourri de charbon et d'un tirage forcé, atteindrait telle pointe,
y vitrifierait telle céramique et fondrait tel métal s'il est présent ici*. Le
soufflet, la tuyère, le charbonnage en meule, la coulée — toute la chaîne opératoire
reste **émergente**.

Ce n'est PAS une transformation de matière : c'est un APPARATUS (le pendant de C11)
-------------------------------------------------------------------------------------
C11 ``kiln_draft`` expose l'affordance « un **four** (feu enclos) *peut* être fait
ici ». C12 expose « un **four à tirage forcé** (soufflet + charbon) *peut* être fait
ici » — il faut un **four constructible** (C11) ET assez de **combustible ligneux**
pour en tirer du **charbon de bois** et alimenter le soufflet. Le tirage forcé ne
*fabrique* pas de matière ; il **élève encore la pointe** que voit la matière, et
c'est cette pointe plus haute qui **réalise** la vitrification (différée par C9 puis
C11) et **débloque** la métallurgie du cuivre. Le monde s'**engage** sur
``forced_draught_peak_c`` (déterministe, ground-truthé) : « si tu souffles sur ce
four de charbon, il atteindra *exactement* cette pointe ».

N'introduit AUCUN nouveau « tell » minéral — il COMPOSE (garde-fou D8)
---------------------------------------------------------------------
Comme C7/C8/C9/C10/C11, ce module **ne surface aucune nouvelle matière**, n'a **pas**
de table ``_PROFILE`` et **ne crée aucune entrée** ``PY_TO_RUST`` / ``PY_CATALOGUE_ONLY``
(cf. ``test_geology_cross_language_contract``). C'est la **6ᵉ** capacité D8-par-
composition. Il *lit* des capacités déjà classées cross-langage :

* le **four** — l'apparatus de C11 ``kiln_draft`` (``kiln_cue_for_chunk`` : paroi,
  ``wall_refractory``, ``fine_fuel`` qui gouverne la pointe, ``clay_pottery_grade``,
  ``clay_ceramic_grade``) ;
* le **cuivre** — le tell de surface de C1 ``surface_mineralization`` (la « tache
  verte » malachite/azurite : ``native_copper`` / ``chalcopyrite``, byte-exact ⇔
  ``Mineral::Malachite``) — lu pour savoir si un **minerai de cuivre est co-localisé**.

Et il **réutilise verbatim** les SSOT physiques de C11 (``kiln_peak_temp_c`` — *le
combo* : la base est la pointe du four naturel, le tirage forcé ne fait que la
pousser) et de C9 (``clay_maturation_temp_c``, ``fired_ware_quality``,
``VITRIFICATION_FIREDNESS``) — recomposées à la pointe forcée. Le fichier est
volontairement **hors du glob** ``*_outcrop.py`` : ce n'est pas un affleurement,
c'est un apparatus. Décision asservie par ``test_introduces_no_new_tell``.

Le COMBO de la veille 2026-06-18 — la thermodynamique du tirage forcé
---------------------------------------------------------------------
La pointe d'un four à tirage forcé est **gouvernée par la physique**, jamais
arbitraire (méta-règle du substrat). Deux quantités se rencontrent :

1. **Pointe du four naturel** (``cf.`` via ``kd.kiln_peak_temp_c`` — réemploi C11,
   *le combo* : un seul modèle de four, le tirage forcé ne fait que le pousser).
   ~1000–1150 °C selon la paroi.

2. **Gain du tirage forcé** (``FORCED_DRAUGHT_GAIN_C``). Le soufflet injecte l'O₂
   bien au-delà de la convection naturelle ; le charbon de bois (dense, sans
   volatils, sans flamme refroidissante) tient une braise incandescente → la pointe
   monte, et **plafonne à nouveau à la réfractarité de la paroi** :
   * paroi en argile **commune** (``shale``) — elle flue/s'effondre ; même un tirage
     forcé ne la pousse qu'un peu : plafond ``FORCED_COMMON_WALL_CAP_C`` (~1100 °C).
   * paroi en argile **réfractaire** (kaolin, *fire-clay* : service 1515–1775 °C) —
     elle **survit** au régime du bas-fourneau : plafond
     ``FORCED_REFRACTORY_WALL_CAP_C`` (~1400 °C).

Archéométrie (veille 2026-06-18) : feu nu ≤850 °C (C9) ; four à tirage naturel
~1000–1150 °C (C11) ; **soufflet + charbon de bois ~1100–1300 °C** — fusion du cuivre
(1085 °C), réduction de la malachite (~1100–1200 °C, Belovode ~5000 av. J.-C.), scorie
vitreuse, bas-fourneau du fer (~1200 °C, tuyères + soufflets, EXARC 2025).

L'inversion DE l'inversion, prolongée — le kaolin réfractaire ouvre TOUT
------------------------------------------------------------------------
C9 a posé le « mensonge du kaolin » (la plus belle argile sous-cuit au feu ouvert) ;
C11 l'a renversé (le kaolin réfractaire est la meilleure **paroi**). C12 le prolonge :
c'est *cette même paroi réfractaire* qui, sous tirage forcé, atteint la pointe qui
**vitrifie** enfin le corps de kaolin (céramique étanche) ET atteint le régime du
**fer** (1200 °C), là où une paroi commune plafonne juste au-dessus du cuivre. La
*pire* argile de poterie est la *seule* clé de la haute pyrotechnologie.

Le mensonge rendu visible — la promesse du cuivre vert (C1) qu'il faut le métal pour
tenir
------------------------------------------------------------------------------------
C1 montre la « tache verte » du cuivre comme une *enseigne lumineuse*. Mais la voir
ne donne pas le métal : il faut un four assez chaud. C12 expose la vérité honnête —
``copper_ore_here`` (C1 voit du cuivre dans cette colonne) ET
``reaches_copper_smelting_temp`` (le four forcé dépasse 1085 °C) →
``would_smelt_copper_here``. Le monde ne ment pas : il dit *où* le métal coulerait et
*pourquoi* (ou pourquoi pas — pas de minerai, ou four trop froid). La **fonte
effective** (consommer le minerai → produire le métal) reste une TRANSFORMATION
différée (Cap. C13), exactement comme C9/C11 différaient *vers* le four puis le
tirage forcé. La chaîne reste ouverte et honnête.

Effet 1+1>2 et « le monde ne ment jamais »
------------------------------------------
Le four à tirage forcé n'est possible QUE là où **les deux** conditions coexistent :
un four constructible (C11 : argile-de-paroi + feu) **ET** assez de combustible
ligneux pour le charbon et le soufflet (``CHARCOAL_FUEL_FLOOR``). Et il **réalise la
vitrification** (différée par C9 puis C11) tout en **ouvrant** la métallurgie. Si
``forced_cue_for_chunk`` renvoie une indication, ``forceable`` est vrai et le résultat
est **ground-truthé** : recomposer C9/C11 à ``forced_peak_c`` donne *exactement*
``vitrified_ware_quality`` / ``vitrifies_watertight``.

La marche différée honnête — la fonte du métal (C13+)
-----------------------------------------------------
``would_smelt_copper_here`` n'est qu'un **potentiel ground-truthé** : le four EST
assez chaud et le minerai EST là — mais le geste de réduction (consommer la
malachite, recueillir le bouton de cuivre, couler la scorie) est une transformation
qu'une capacité **future** (C13 ``copper_smelting``) réalisera, en lisant ce même
seuil. De même ``reaches_iron_bloomery_temp`` (~1200 °C) **porte plus loin** la
chaîne — vers le bas-fourneau du fer (paroi réfractaire requise), encore différé.

Déterminisme
------------
Pur : composition de ``kiln_cue_for_chunk`` (C11) et ``surface_cue_for_chunk`` (C1),
tous deux ``prf_rng`` / dérivés du seed, avec des SSOT purs (C9/C11). Aucun RNG
nouveau. Bit-identique entre deux runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — le tirage forcé est une lecture
dérivée du substrat (four + combustible + minerai), comme C1→C11.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape (chunk →
affordance d'apparatus), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from engine.world import CHUNK_SIDE_M, world_to_chunk
# Single sources of truth — reused verbatim, never re-modelled (garde-fou D8).
import engine.kiln_draft as kd            # C11 — the kiln apparatus (the base peak)
import engine.ceramic_firing as cf        # C9 — clay maturation + ware SSOTs
import engine.surface_mineralization as sm  # C1 — the copper surface tell (ore here?)

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# --- Forced-draught thermodynamics (°C). The extra peak a bellows + charcoal adds
# over a natural-draught kiln (C11). A bellows injects O2 far past natural
# convection; charcoal (dense, volatile-free) holds an incandescent bed — together
# they push the peak into the bloomery regime, again capped by the wall's slump
# limit (a refractory fire-clay wall survives; a common earthenware wall does not).
FORCED_DRAUGHT_GAIN_C = 250.0          # max extra °C a bellows + charcoal adds over a kiln

# Wall caps (°C) under forced draught: a common earthenware wall still fluxes and
# slumps — forced draught only nudges it a little above its natural-draught cap; a
# refractory kaolin / fire-clay wall (service T 1515–1775 °C) survives the full
# bloomery regime. The honest ceiling each wall material commits to under a bellows.
FORCED_COMMON_WALL_CAP_C = 1100.0      # common earthenware wall — slumps just past copper
FORCED_REFRACTORY_WALL_CAP_C = 1400.0  # refractory fire-clay wall — full bloomery regime

# Minimum fine/woody fuel (C7/C11 ``fine_fuel``) to char a batch of charcoal AND
# feed a forced fire. A bellows furnace is fuel-hungry: deserts/tundra (sparse fuel)
# cannot sustain it even when a modest pottery kiln is buildable. Equal to C7's
# friction-fuel floor — the same "enough woody biomass" substrate truth.
CHARCOAL_FUEL_FLOOR = 0.45

# Metallurgy thresholds (°C) — the honest temperatures the world commits to.
# Copper melts at 1085 °C; smelting malachite/native copper to a metal bead needs to
# cross it (veille: Belovode ~1100–1200 °C). This is the chalcolithic threshold — the
# first metal. The bloomery iron regime (~1200 °C, solid-state reduction under a
# strongly reducing CO atmosphere) lies further still — reachable only behind a
# refractory wall. Crossing a threshold is *potential*, never the smelt itself (C13+).
COPPER_SMELT_TEMP_C = 1085.0           # copper melting point — the chalcolithic threshold
IRON_BLOOMERY_TEMP_C = 1200.0          # bloomery iron regime — the next deferral (refractory only)

# Copper-bearing surface tell minerals (C1 ``copper`` expression group). Reused, not
# re-listed: these ARE the minerals C1's green malachite/azurite cue surfaces.
_COPPER_GROUP = "copper"


@dataclass(frozen=True)
class ForcedDraughtCue:
    """A truthful forced-draught (bellows + charcoal furnace) affordance at one chunk.

    What an agent *could* discover by blowing air into the charcoal-fed kiln it
    already builds (C11): the heat climbs into the bloomery regime — finally
    **vitrifying** the refractory kaolin body (watertight ceramic, the step C9 and
    C11 both deferred) and getting hot enough to **melt copper** out of the green
    stone C1 shows. It is NOT handed to the agent as "blow a bellows on charcoal to
    smelt copper" — the agent must learn the draught->heat->metal correlation by
    acting. ``forced_peak_c`` (and the recomposed ``vitrified_ware_quality`` /
    ``vitrifies_watertight``) are the ground truth the world commits to.
    """
    coord: Tuple[int, int, int]
    biome: int
    # the kiln this furnace is built upon (read from C11 kiln_draft)
    wall_material: str             # ground-truth clay the walls/body are made of
    wall_refractory: bool          # C11/C5 ceramic_grade — kaolin walls survive high heat
    clay_pottery_grade: float      # C5 intrinsic firing/vitrification rank [0,1]
    clay_ceramic_grade: bool       # C5: the body CAN vitrify watertight (enough heat)
    fine_fuel: float               # C7 fine/woody fuel load (drives the peak)
    # fuel for the forced draught
    charcoal_makeable: bool        # enough woody fuel here to char + feed a bellows
    # apparatus outcome (the truth the world commits to)
    forceable: bool                # a kiln AND charcoal-grade fuel coexist here
    kiln_peak_c: float             # the natural-draught kiln peak this builds on (C11)
    forced_peak_c: float           # what the bellows + charcoal furnace reaches (SSOT)
    forced_gain_c: float           # forced_peak - kiln_peak (the bellows win)
    wall_cap_c: float              # the ceiling these walls permit under forced draught
    # realized: vitrification (C9/C11 deferred — finally met here)
    clay_firedness: float          # min(1, forced_peak / maturation) for the body
    fires_clay_sound: bool         # the body fires to a SOUND vessel in this furnace
    vitrifies_watertight: bool     # REALIZED: refractory body vitrifies watertight here
    vitrified_ware_quality: float  # quality of the forced-fired vessel [0,1] (ground truth)
    # opened: metallurgy (copper — the chalcolithic threshold)
    reaches_copper_smelting_temp: bool   # forced_peak >= copper melting point (1085 °C)
    copper_ore_here: bool          # C1 sees a copper tell (malachite/azurite) in this column
    copper_mineral: Optional[str]  # the ground-truth copper ore C1 surfaces here (or None)
    would_smelt_copper_here: bool  # hot enough AND copper ore co-located (the 1+1>2)
    smelts_copper_if_ore_present: bool  # hot enough — needs ore + the smelt transform (C13)
    # deferred further: the bloomery iron regime
    reaches_iron_bloomery_temp: bool     # forced_peak >= ~1200 °C (refractory wall only; C13+)
    confidence: float              # reliability of achieving the forced outcome [0,1]


# ---------------------------------------------------------------------------
# Single source of truth — the forced-draught physics the world commits to.
# ---------------------------------------------------------------------------

def forced_draught_peak_c(fine_fuel: float, wall_refractory: bool) -> float:
    """Peak temperature (°C) a bellows + charcoal furnace reaches, from its fuel load
    and the refractoriness of its walls.

    Deterministic SSOT and *the combo*: the base is C11's natural-draught kiln peak
    (reused verbatim — the forced draught only pushes that same kiln), plus a forced
    gain that scales with the fuel, the whole capped by the wall material's slump
    ceiling under forced draught. A common-clay wall caps low
    (``FORCED_COMMON_WALL_CAP_C``, just past copper); a refractory fire-clay wall
    survives the full bloomery regime (``FORCED_REFRACTORY_WALL_CAP_C``)."""
    f = min(1.0, max(0.0, float(fine_fuel)))
    base = kd.kiln_peak_temp_c(f, wall_refractory)      # combo: reuse C11 SSOT
    gain = FORCED_DRAUGHT_GAIN_C * (0.5 + 0.5 * f)      # bellows + charcoal, fuel-scaled
    cap = FORCED_REFRACTORY_WALL_CAP_C if wall_refractory else FORCED_COMMON_WALL_CAP_C
    return float(min(base + gain, cap))


# ---------------------------------------------------------------------------
# Core derivation — apparatus outcome from a C11 kiln × charcoal fuel, with the
# C9 vitrification recomposed at the forced peak and the C1 copper tell composed in.
# ---------------------------------------------------------------------------

def _cue_from_inputs(coord, kiln_cue, copper_cue=None) -> Optional[ForcedDraughtCue]:
    """Pure derivation (no ``sim`` — trivially unit-testable, like its siblings).
    Emits a cue iff the site is **forceable** — a buildable kiln (C11) AND enough
    woody fuel to char + feed a bellows coexist here. The 1+1>2 gate: no kiln or
    too little fuel => no forced-draught affordance. ``copper_cue`` (C1) is optional:
    when it is a copper-group surface cue, the furnace reports it would smelt that
    co-located copper if hot enough."""
    if kiln_cue is None or not getattr(kiln_cue, "buildable", False):
        return None

    fine_fuel = float(getattr(kiln_cue, "fine_fuel", 0.0))
    charcoal_makeable = fine_fuel >= CHARCOAL_FUEL_FLOOR
    if not charcoal_makeable:
        return None  # a bellows furnace needs charcoal-grade fuel — the 1+1>2 gate

    wall_refractory = bool(kiln_cue.wall_refractory)
    wall_cap = (FORCED_REFRACTORY_WALL_CAP_C if wall_refractory
                else FORCED_COMMON_WALL_CAP_C)
    kiln_peak = float(kiln_cue.kiln_peak_c)
    forced_peak = forced_draught_peak_c(fine_fuel, wall_refractory)
    forced_gain = forced_peak - kiln_peak

    # Vitrification — recompose C9 at the forced peak (the local clay as the body).
    ceramic_grade = bool(kiln_cue.clay_ceramic_grade)
    maturation = cf.clay_maturation_temp_c(ceramic_grade)
    firedness = min(1.0, forced_peak / maturation) if maturation > 0 else 1.0
    fires_sound = firedness >= cf.SOUND_MATURATION
    # REALIZED here (where C9/C11 left it False): a refractory body reaching full
    # maturation vitrifies watertight. A common (non-ceramic) clay never vitrifies.
    vitrified = bool(ceramic_grade and firedness >= kd.VITRIFICATION_FIREDNESS)
    ware = cf.fired_ware_quality(float(kiln_cue.clay_pottery_grade), firedness)

    # Metallurgy — the chalcolithic copper threshold, plus the co-located ore (C1).
    reaches_copper = forced_peak >= COPPER_SMELT_TEMP_C
    reaches_iron = forced_peak >= IRON_BLOOMERY_TEMP_C
    copper_here = bool(copper_cue is not None
                       and getattr(copper_cue, "group", None) == _COPPER_GROUP)
    copper_mineral = (copper_cue.mineral if copper_here else None)
    would_smelt = bool(reaches_copper and copper_here)

    # Confidence: a refractory furnace at full charcoal is a near-certainty; a
    # marginal common-walled one is a chore. Scales with the kiln confidence (C11).
    kiln_conf = float(getattr(kiln_cue, "confidence", 0.0))
    fuel_factor = min(1.0, fine_fuel)
    confidence = float(min(1.0, kiln_conf * (0.6 + 0.4 * fuel_factor)))

    return ForcedDraughtCue(
        coord=tuple(int(c) for c in coord), biome=int(kiln_cue.biome),
        wall_material=kiln_cue.wall_material,
        wall_refractory=wall_refractory,
        clay_pottery_grade=float(round(kiln_cue.clay_pottery_grade, 4)),
        clay_ceramic_grade=ceramic_grade,
        fine_fuel=float(round(fine_fuel, 4)),
        charcoal_makeable=bool(charcoal_makeable),
        forceable=True,
        kiln_peak_c=float(round(kiln_peak, 1)),
        forced_peak_c=float(round(forced_peak, 1)),
        forced_gain_c=float(round(forced_gain, 1)),
        wall_cap_c=float(wall_cap),
        clay_firedness=float(round(firedness, 4)),
        fires_clay_sound=bool(fires_sound),
        vitrifies_watertight=bool(vitrified),
        vitrified_ware_quality=float(round(ware, 4)),
        reaches_copper_smelting_temp=bool(reaches_copper),
        copper_ore_here=bool(copper_here),
        copper_mineral=copper_mineral,
        would_smelt_copper_here=bool(would_smelt),
        smelts_copper_if_ore_present=bool(reaches_copper),
        reaches_iron_bloomery_temp=bool(reaches_iron),
        confidence=float(round(confidence, 4)))


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_forced_draught(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim`` and ensures
    the composed capabilities (C11 kiln, C1 surface mineralization) are installed.

    Adds **zero** per-tick cost: affordances are derived on query and memoised.
    Returns the cache dict (``sim._forced_draught_cue_cache``).
    """
    kd.install_kiln_draft(sim)
    sm.install_surface_mineralization(sim)
    cache = getattr(sim, "_forced_draught_cue_cache", None)
    if cache is None:
        cache = {}
        sim._forced_draught_cue_cache = cache
    return cache


def forced_cue_for_chunk(sim, coord: Tuple[int, int, int]
                         ) -> Optional[ForcedDraughtCue]:
    """Truthful forced-draught affordance at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, ``forceable`` is True — C11
    ``kiln_cue_for_chunk(sim, coord)`` proves a kiln is buildable in the same column
    and the fuel is charcoal-grade. ``forced_peak_c`` is the ground-truth peak the
    bellows + charcoal furnace reaches; ``copper_ore_here`` agrees with C1's cue.
    """
    coord = tuple(int(c) for c in coord)
    cache = install_forced_draught(sim)
    if coord in cache:
        return cache[coord]
    kiln = kd.kiln_cue_for_chunk(sim, coord)
    copper = sm.surface_cue_for_chunk(sim, coord)
    cue = _cue_from_inputs(coord, kiln, copper)
    cache[coord] = cue
    return cue


def prospect_forced_draught(sim, world_x: float, world_y: float
                            ) -> Optional[ForcedDraughtCue]:
    """What an agent standing at world ``(x, y)`` could discover about building a
    forced-draught (bellows + charcoal) furnace here. Returns the cue (forced peak +
    realized vitrification + metallurgy potential) or None when no charcoal-fed kiln
    is buildable underfoot."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return forced_cue_for_chunk(sim, coord)


def forced_draught_preview(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of whether (and how hot) a forced-draught furnace at
    ``(x, y)`` would run, and what it realizes/unlocks — the ground-truthed outcome
    the perception cue must agree with.

    Touches NOTHING (no clay dug, no fire lit, no ore mined): the truth oracle, not
    the action. Always returns a dict (even when not forceable), naming the *missing*
    ingredient — the honest 'why not'. The payoff this cap exposes: a refractory
    kaolin furnace finally **vitrifies watertight** (``vitrifies_watertight`` True),
    the step C9 and C11 both deferred."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = forced_cue_for_chunk(sim, coord)
    if cue is not None:
        return {"forceable": True, "reason": "ok",
                "wall_material": cue.wall_material,
                "wall_refractory": cue.wall_refractory,
                "kiln_peak_c": cue.kiln_peak_c,
                "forced_peak_c": cue.forced_peak_c,
                "forced_gain_c": cue.forced_gain_c,
                "wall_cap_c": cue.wall_cap_c,
                "charcoal_makeable": cue.charcoal_makeable,
                "fires_clay_sound": cue.fires_clay_sound,
                "vitrifies_watertight": cue.vitrifies_watertight,
                "vitrified_ware_quality": cue.vitrified_ware_quality,
                "reaches_copper_smelting_temp": cue.reaches_copper_smelting_temp,
                "copper_ore_here": cue.copper_ore_here,
                "copper_mineral": cue.copper_mineral,
                "would_smelt_copper_here": cue.would_smelt_copper_here,
                "reaches_iron_bloomery_temp": cue.reaches_iron_bloomery_temp,
                "confidence": cue.confidence,
                "biome": cue.biome}
    # Not forceable — recompute the diagnostic to name the missing ingredient.
    kiln = kd.kiln_cue_for_chunk(sim, coord)
    if kiln is None:
        reason = "no kiln buildable here to force-draught"
        return {"forceable": False, "reason": reason,
                "has_kiln": False, "charcoal_makeable": False}
    charcoal = float(getattr(kiln, "fine_fuel", 0.0)) >= CHARCOAL_FUEL_FLOOR
    if not charcoal:  # pragma: no branch — the only other gate
        reason = "too little woody fuel to char + feed a bellows"
    else:  # pragma: no cover — kiln + charcoal would have produced a cue
        reason = "not forceable"
    return {"forceable": False, "reason": reason,
            "has_kiln": True, "wall_material": kiln.wall_material,
            "charcoal_makeable": bool(charcoal)}


def discover_forced_sites_by_sight(sim, rows: List[int],
                                   perception_radius_m: float = 64.0
                                   ) -> Dict[int, List[ForcedDraughtCue]]:
    """For each agent ``row``, the forced-draught-buildable sites perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    Turns the static substrate (a buildable kiln + abundant fuel + maybe copper) into
    a **perceivable, actionable** apparatus signal — the agent then *chooses* to blow
    a bellows on charcoal. Deterministic order (by chunk distance, then coord).
    """
    out: Dict[int, List[ForcedDraughtCue]] = {}
    if not rows:
        return out
    install_forced_draught(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], ForcedDraughtCue]] = []
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
                cue = forced_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_forced_site_near(sim, row: int, perception_radius_m: float = 128.0,
                          *, require_smelting: bool = False,
                          require_vitrifying: bool = False
                          ) -> Optional[ForcedDraughtCue]:
    """The hottest forced-draught furnace an agent at ``row`` can perceive — the
    actionable pick (highest ``forced_peak_c``; tie-break higher confidence, then
    nearest then coord).

    This continues the inversion-of-the-inversion: preferring the hottest furnace,
    the agent again learns to wall it with the refractory white clay (kaolin) — the
    very clay that under-fires as a pot (C9) but now both **vitrifies watertight**
    and reaches the metal-smelting regime. ``require_smelting`` keeps only furnaces
    that would smelt co-located copper; ``require_vitrifying`` keeps only those that
    vitrify a watertight body. Returns None when nothing matching is in sight."""
    cues = discover_forced_sites_by_sight(sim, [int(row)], perception_radius_m
                                          ).get(int(row), [])
    pool = cues
    if require_smelting:
        pool = [c for c in pool if c.would_smelt_copper_here]
    if require_vitrifying:
        pool = [c for c in pool if c.vitrifies_watertight]
    if not pool:
        return None
    # already distance-sorted; prefer the hottest furnace, then the surest build.
    return max(pool, key=lambda c: (c.forced_peak_c, c.confidence))


def forced_draught_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_forced_draught(sim)
    by_wall: Dict[str, int] = {}
    n_chunks = 0
    n_forceable = 0
    n_refractory = 0
    n_vitrifies = 0
    n_reaches_copper = 0
    n_copper_here = 0
    n_would_smelt = 0
    n_reaches_iron = 0
    best_peak = 0.0
    best_gain = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = forced_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_forceable += 1
        if cue.wall_refractory:
            n_refractory += 1
        if cue.vitrifies_watertight:
            n_vitrifies += 1
        if cue.reaches_copper_smelting_temp:
            n_reaches_copper += 1
        if cue.copper_ore_here:
            n_copper_here += 1
        if cue.would_smelt_copper_here:
            n_would_smelt += 1
        if cue.reaches_iron_bloomery_temp:
            n_reaches_iron += 1
        by_wall[cue.wall_material] = by_wall.get(cue.wall_material, 0) + 1
        best_peak = max(best_peak, cue.forced_peak_c)
        best_gain = max(best_gain, cue.forced_gain_c)
    return {
        "n_chunks": n_chunks,
        "n_chunks_forceable": n_forceable,
        "forceable_rate": round(n_forceable / n_chunks, 4) if n_chunks else 0.0,
        "n_refractory_walled": n_refractory,
        "n_vitrifies_watertight": n_vitrifies,
        "n_reaches_copper_smelt": n_reaches_copper,
        "n_copper_ore_here": n_copper_here,
        "n_would_smelt_copper": n_would_smelt,
        "n_reaches_iron_bloomery": n_reaches_iron,
        "best_forced_peak_c": round(best_peak, 1),
        "best_forced_gain_c": round(best_gain, 1),
        "by_wall_material": dict(sorted(by_wall.items())),
    }


__all__ = [
    "ForcedDraughtCue",
    "install_forced_draught", "forced_cue_for_chunk", "prospect_forced_draught",
    "forced_draught_preview", "discover_forced_sites_by_sight",
    "best_forced_site_near", "forced_draught_summary",
    "forced_draught_peak_c",
    "FORCED_DRAUGHT_GAIN_C", "FORCED_COMMON_WALL_CAP_C",
    "FORCED_REFRACTORY_WALL_CAP_C", "CHARCOAL_FUEL_FLOOR",
    "COPPER_SMELT_TEMP_C", "IRON_BLOOMERY_TEMP_C",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
