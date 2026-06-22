"""Genesis Engine — Substrate capability : salaison / conservation par le sel (Cap. C16).

**La 1ʳᵉ capacité qui CONSOMME le produit de C15 — saler pour conserver.** Réponse
directe à la reco ``R-J9r2-3 (a)`` de l'audit J+9 run #2
(``native/world-engine/AUDIT-DELTA-2026-06-19-run2.md``) : « le sel rendu
perceptible ouvre, *par composition future sans nouveau tell*, la **conservation**
(salaison de la viande/poisson → autonomie alimentaire, compose C15 × physiologie) ».

C15 (``salt_evaporation``) a rendu le **sel** perceptible et récoltable. Mais le
sel n'est pas une fin : c'est le premier **agent de transformation différée** de
l'âge de pierre. Saler la viande et le poisson **arrête la pourriture** — c'est ce
qui transforme une chasse fugace en **réserve**, donc en **surplus**, donc en
**sédentarité** et en **commerce** (l'« or blanc »). Cette capacité expose la
**vérité physique** de cette conservation : combien de temps un aliment tient
selon la dose de sel et le climat.

**Règle invariante du projet** (cf. ``salt_evaporation`` (C15), ``cryoclasty``
(C14)) : rien n'est scripté. Un agent ne *sait* pas que le sel conserve. Il
observe — par l'usage — que la viande **fraîche** (la plus appétissante) **pourrit
en quelques jours**, alors que la viande **salée** (terne, dure, très salée)
**tient des mois**. La découverte est émergente ; ce module n'expose qu'un
**signal physique véridique** : la durée de conservation (``shelf_life_days``).

Ce qu'elle consomme — la 1ʳᵉ consommation du PRODUIT de C15
-----------------------------------------------------------
C1..C6 ont exposé des **indices** (tells) ; C7..C13 des **transformations par le
feu** ; C14/C15 des **opérateurs orthogonaux** (ramasser / sécher au soleil). C16
est différente : c'est la **1ʳᵉ capacité dont l'intrant est le PRODUIT récolté
d'une capacité précédente** — le **sel** de C15. Sans sel récoltable à proximité
(``salt_evaporation.best_saltpan_near`` → aucun marais salant), la dose accessible
est **nulle** et l'aliment reste **périssable** : *le monde ne ment jamais* — pas
de sel, pas de conservation. Plus le marais est riche (SALAR ≥ ``ABUNDANT_KG_M2``),
plus la dose atteignable est forte, jusqu'à la **saumure saturée**.

La physique de la salaison (eau libre / activité de l'eau a_w)
--------------------------------------------------------------
La pourriture microbienne s'arrête quand l'**activité de l'eau** (``a_w``, l'eau
*libre* disponible aux micro-organismes) chute. Le sel (NaCl) abaisse ``a_w`` par
**osmose** : il déshydrate la phase aqueuse de l'aliment.

* Une saumure **saturée** (~26,4 % NaCl en masse) plafonne ``a_w`` à **0,75**
  (fait FIPS d'hygrométrie : c'est la base du sel comme étalon d'humidité à 75 %).
* La plupart des bactéries d'altération s'arrêtent sous ``a_w ≈ 0,91`` ; les plus
  résistantes (halophiles, moisissures xérophiles) sous ``a_w ≈ 0,60``.
* La vitesse de pourriture suit aussi la **température** (loi Q10 ≈ 2,5 : ×2,5 par
  +10 °C) — le froid conserve, la chaleur accélère.

Le modèle (pur, déterministe, sans solveur transitoire) :

    a_w          = a_w_frais − (a_w_frais − 0,75) · min(1, saturation_saumure)
    croissance   = ((a_w − 0,60)/(0,99 − 0,60))^5 · périssabilité · Q10^((T−25)/10)
    shelf_life   = min(SHELF_MAX, SHELF_BASE / croissance)   [jours]

Viande maigre fraîche à 25 °C (``a_w ≈ 0,99``) → ~2 jours ; salée à saturation
(``a_w = 0,75``) → des **mois** (la dynamique réelle du salaison ~100×).

Le MENSONGE RENDU VISIBLE #7
----------------------------
(pendant de l'obsidienne C8, du kaolin C9, du cuivre C13, de l'arène C14, de la
lagune humide C15.) L'aliment **le plus appétissant** — la chair **fraîche**,
rouge vif, parfumée, la plus nourrissante — est **le plus périssable** : il trahit
en quelques jours. L'aliment **terne** — la chair salée, grise, dure, trop salée —
**tient des mois**. « Frais = meilleur » est le mensonge : la fraîcheur **se paie
en pourriture**. L'agent qui apprend à **échanger l'attrait immédiat contre la
conservation** débloque le **surplus alimentaire** — la vraie charge utile
civilisationnelle du sel. Le monde montre l'attrait (``appeal_rgb``, vrai) ;
``shelf_life_days`` dit la vérité sur ce qui restera mangeable.

Le prix de la conservation (le compromis émergent)
--------------------------------------------------
Saler n'est pas gratuit : ``palatability`` (agrément) **baisse** avec la dose (la
chair devient âpre, saumâtre) et ``nutrient_retention`` baisse modérément (l'osmose
lessive les nutriments hydrosolubles). L'agent **arbitre** : peu de sel = bon goût
mais conservation courte ; saturation = goût rude mais des mois. Aucune dose n'est
« la bonne » — c'est le contexte (chaleur, besoin de réserve) qui tranche.

Le monde ne ment jamais
-----------------------
``shelf_life_days`` est dérivé **uniquement** de la dose de sel, de l'eau de
l'aliment et de la température macro (issue du seed). Aucune valeur n'est inventée :
sans sel (``salt_dose_frac == 0``) l'aliment garde sa durée **fraîche** véridique ;
sans marais salant à portée, ``achievable_cure_near`` retourne précisément cette
durée fraîche (réciproque honnête : pas de sel ⇒ pas de conservation).

N'introduit AUCUN nouveau tell
------------------------------
COMPOSE C15 (``salt_evaporation`` — le sel) × le champ macro de température (climat,
comme C14/C15). Pas de ``_PROFILE`` propre, pas d'entrée ``PY_TO_RUST`` (garde-fou
**D8 — 10ᵉ fois par composition** ; voir ``test_geology_cross_language_contract.py``
et ``test_food_curing.py``). Hors glob ``*_outcrop.py`` : le fichier s'appelle
``food_curing.py`` à dessein. Réutilise la **lecture climat** de C15
(``se._resolve_anchor`` / ``se._climate_at``) — une seule implémentation, zéro
dérive (SSOT).

Périmètre honnête (audit)
-------------------------
* ``cure_food_at`` / ``achievable_cure_near`` sont des **aperçus non mutants**
  (preview) : ils ne consomment NI le sel, NI l'aliment, NI ``chunk.water``
  (contrairement au ``smelt_at`` mutant de C13). **D10 (frontière de mutation
  cross-langage) reste donc gelé** — comme ``harvest_salt_at`` (C15), cf. R-J9-2.
* ``a_w`` est plafonné à **0,75** (saumure saturée NaCl) : on ne modélise pas le
  **séchage** (qui pousserait ``a_w`` plus bas — charqui/biltong). Le séchage
  solaire de la chair (compose C16 × l'aridité de C15) est une **extension future**.
* La température est le champ **macro** (seed) au point de l'agent, comme C14/C15 :
  un climat annuel, à l'altitude perception/stone-age — pas un thermomètre de
  cellule de stockage.
* La **rancidité oxydative** des graisses (``FATTY_MEAT``) n'est pas modélisée : ce
  module ne couvre que la pourriture **microbienne** (gouvernée par ``a_w``).

Déterminisme
------------
Pur : fonction de la dose de sel (issue de C15 → seed), de l'aliment (paramètre)
et de la température macro (seed). Aucun RNG nouveau. Bit-identique entre deux runs
de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — la conservation est une lecture
dérivée du substrat (sel C15 + climat), comme C1/C2/C3/C14/C15.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — prédiction en forme close
(intrants → durée), sans rollout tick à tick.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, Optional, Tuple

from engine import salt_evaporation as se
from engine.world import world_to_chunk

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# --- Water-activity physics (NaCl) -----------------------------------------
# Water activity of a SATURATED NaCl brine (~26.4 % w/w) — the canonical 0.75 a_w
# reference used worldwide as a humidity standard. Salt cannot drop a_w below this.
SAT_BRINE_AW = 0.75
# Mass fraction of NaCl in a saturated aqueous phase (26.4 g per 100 g solution).
SAT_BRINE_FRAC = 0.264
# a_w of fresh muscle/fish reference (free water everywhere) — the growth-curve top.
A_W_FRESH_REF = 0.99
# Below this water activity even xerophilic/halophilic spoilage halts → shelf-stable.
A_W_NO_GROWTH = 0.60
# Steepness of the microbial-growth falloff with a_w (microbial rate is sharply
# non-linear near the inhibition threshold — a low power would understate curing).
AW_EXP = 5.0

# --- Temperature physics (mesophilic spoilage flora) -----------------------
Q10 = 2.5            # spoilage-rate multiplier per +10 °C
T_REF_C = 25.0       # reference temperature at which SHELF_BASE_DAYS is calibrated
T_MIN_GROWTH_C = -2.0  # brine depresses freezing; below this, growth ≈ floor
TEMP_FACTOR_FLOOR = 0.03

# --- Shelf-life calibration ------------------------------------------------
# Fresh lean meat at 25 °C (a_w≈0.99) spoils in ~2 days (real warm-climate figure).
SHELF_BASE_DAYS = 2.0
# Cap: at/above this the food reads "shelf-stable" for perception (2 years).
SHELF_MAX_DAYS = 730.0

# Preservation-class day thresholds.
SEMI_CURED_DAYS = 14.0
CURED_DAYS = 90.0

# --- Curing cost (the trade-off) -------------------------------------------
PALAT_SALT_PENALTY = 0.7    # full-saturation salting drops palatability to ~0.3
NUTRIENT_SALT_PENALTY = 0.35  # osmosis leaches water-soluble nutrients (modest)


class FoodKind(IntEnum):
    """A perishable animal food an agent may try to preserve by salting."""
    LEAN_MEAT = 0    # game muscle — the canonical salting target
    FATTY_MEAT = 1   # marbled meat — less water (easier a_w drop); fat goes rancid*
    FISH = 2         # high water, spoils fastest fresh — the classic salt-fish
    OFFAL = 3        # organ meat — extremely perishable (high enzyme activity)


class PreservationClass(IntEnum):
    """What the agent learns the food has *become* (by spoilage time)."""
    PERISHABLE = 0    # days — fresh, the most appealing AND the lie #7
    SEMI_CURED = 1    # ~weeks — lightly salted
    CURED = 2         # months — properly salted
    SHELF_STABLE = 3  # capped — saturation-salted (keeps a year+)


@dataclass(frozen=True)
class _FoodProfile:
    """Intrinsic, salting-relevant properties of a perishable food."""
    water_frac: float       # mass fraction of water (drives the a_w response)
    a_w_fresh: float        # water activity when fresh (free water)
    perishability: float    # spoilage-rate multiplier vs lean meat (1.0)
    fresh_rgb: Tuple[int, int, int]  # the appealing fresh look (the lie)
    label: str


# Real moisture fractions (USDA-grade orders of magnitude). The fresh RGB is the
# *appeal* signal — what looks best — never the truth about shelf life.
_FOOD: Dict[FoodKind, _FoodProfile] = {
    FoodKind.LEAN_MEAT:  _FoodProfile(0.74, 0.99, 1.0, (190, 45, 45),
                                      "viande maigre"),
    FoodKind.FATTY_MEAT: _FoodProfile(0.55, 0.98, 0.85, (205, 120, 110),
                                      "viande grasse"),
    FoodKind.FISH:       _FoodProfile(0.80, 0.99, 1.6, (170, 180, 195),
                                      "poisson"),
    FoodKind.OFFAL:      _FoodProfile(0.78, 0.99, 2.2, (140, 30, 40),
                                      "abats"),
}

# The drab cured look — what salted food *becomes* (less appealing, keeps longer).
_CURED_RGB: Tuple[int, int, int] = (155, 130, 110)


@dataclass(frozen=True)
class CuringCue:
    """A truthful salt-curing outcome for one food at one salt dose + climate.

    ``appeal_rgb``/``label`` = what the agent *perceives* (fresh chair looks best).
    ``shelf_life_days``/``water_activity``/``preservation_class`` = the ground truth
    it must agree with. The agent is NOT told "salt preserves" — it learns the
    salt+cool→keeps correlation by watching fresh food rot and salted food last.
    Composes C15: ``salt_source``/``salt_yield_kg_m2`` record the pan that enabled it.
    """
    food: FoodKind
    food_label: str
    salt_dose_frac: float      # kg salt per kg food applied
    brine_saturation: float    # fraction of saturated brine reached in [0, 1]
    water_activity: float      # a_w — the free-water the microbes see (ground truth)
    temp_c: float              # local mean annual temperature (°C, macro seed)
    shelf_life_days: float     # days until spoilage — THE ground truth
    preservation_class: PreservationClass
    palatability: float        # agreeableness in [0, 1] — drops with salt (the cost)
    nutrient_retention: float  # in [0, 1] — drops modestly with salt (the cost)
    appeal_rgb: Tuple[int, int, int]  # perceived look (fresh = appealing = the lie)
    is_fresh: bool             # dose == 0 (the appealing-but-perishable lie #7)
    salt_limited: bool         # dose was capped by available salt (C15), not choice
    salt_source: Optional[str]  # C15 origin of the enabling salt ("sea"/...) or None
    salt_yield_kg_m2: float    # C15 yield of the enabling pan (0 if none)
    confidence: float          # perceptual confidence in [0, 1]


# ---------------------------------------------------------------------------
# Core physics — pure, testable with synthetic inputs (no world needed).
# ---------------------------------------------------------------------------

def _saturation_dose(water_frac: float) -> float:
    """kg salt per kg food needed to drive the aqueous phase to a SATURATED brine.

    From ``brine_frac = salt/(salt+water) = SAT_BRINE_FRAC`` →
    ``salt = SAT_BRINE_FRAC/(1−SAT_BRINE_FRAC) · water``. For lean meat
    (water 0.74) this is ~0.27 kg/kg — the real dry-cure dose. Salt beyond this
    just precipitates; it cannot lower a_w further."""
    return SAT_BRINE_FRAC / (1.0 - SAT_BRINE_FRAC) * float(water_frac)


def _brine_saturation(food: _FoodProfile, salt_dose_frac: float) -> float:
    """Fraction of a saturated brine the aqueous phase reaches, in [0, 1]."""
    salt = max(0.0, float(salt_dose_frac))
    water = food.water_frac
    denom = salt + water
    if denom <= 0.0:
        return 0.0
    brine_frac = salt / denom
    return min(1.0, brine_frac / SAT_BRINE_FRAC)


def _water_activity(food: _FoodProfile, salt_dose_frac: float) -> float:
    """a_w after salting: linear in brine saturation, floored at the NaCl limit."""
    sat = _brine_saturation(food, salt_dose_frac)
    a_w = food.a_w_fresh - (food.a_w_fresh - SAT_BRINE_AW) * sat
    return max(SAT_BRINE_AW, min(food.a_w_fresh, a_w))


def _aw_growth_factor(a_w: float) -> float:
    """Relative microbial growth as a function of water activity (sharp falloff)."""
    if a_w <= A_W_NO_GROWTH:
        return 0.0
    norm = (a_w - A_W_NO_GROWTH) / (A_W_FRESH_REF - A_W_NO_GROWTH)
    return max(0.0, min(1.0, norm)) ** AW_EXP


def _temp_factor(temp_c: float) -> float:
    """Q10 temperature multiplier on spoilage rate (cold preserves, heat rots)."""
    t = max(T_MIN_GROWTH_C, float(temp_c))
    return max(TEMP_FACTOR_FLOOR, Q10 ** ((t - T_REF_C) / 10.0))


def _shelf_life_days(food: _FoodProfile, a_w: float, temp_c: float) -> float:
    """Days until spoilage = SHELF_BASE / (growth), capped. Growth 0 → shelf-stable."""
    growth = _aw_growth_factor(a_w) * food.perishability * _temp_factor(temp_c)
    if growth <= 0.0:
        return SHELF_MAX_DAYS
    return min(SHELF_MAX_DAYS, SHELF_BASE_DAYS / growth)


def _classify(shelf_days: float) -> PreservationClass:
    if shelf_days >= SHELF_MAX_DAYS:
        return PreservationClass.SHELF_STABLE
    if shelf_days >= CURED_DAYS:
        return PreservationClass.CURED
    if shelf_days >= SEMI_CURED_DAYS:
        return PreservationClass.SEMI_CURED
    return PreservationClass.PERISHABLE


def _cure_from_inputs(food_kind: FoodKind, salt_dose_frac: float, temp_c: float,
                      *, salt_source: Optional[str] = None,
                      salt_yield_kg_m2: float = 0.0,
                      salt_limited: bool = False) -> CuringCue:
    """Pure derivation of the curing outcome from explicit dose + climate.

    Always returns a cue (an agent always perceives the food's look); the truth
    lives in ``shelf_life_days`` / ``water_activity`` / ``preservation_class``."""
    food = _FOOD[FoodKind(food_kind)]
    dose = max(0.0, float(salt_dose_frac))
    sat = _brine_saturation(food, dose)
    a_w = _water_activity(food, dose)
    shelf = _shelf_life_days(food, a_w, temp_c)
    cls = _classify(shelf)
    is_fresh = dose <= 0.0
    palat = max(0.2, 1.0 - PALAT_SALT_PENALTY * sat)
    nutrient = max(0.6, 1.0 - NUTRIENT_SALT_PENALTY * sat)
    appeal = food.fresh_rgb if is_fresh else _CURED_RGB
    # Confidence rises with how strongly the food is cured (a salar-salted haunch
    # reads unambiguous; a faint rub reads ambiguous between fresh and cured).
    confidence = float(min(1.0, 0.45 + 0.55 * sat))
    return CuringCue(
        food=FoodKind(food_kind), food_label=food.label,
        salt_dose_frac=float(round(dose, 6)),
        brine_saturation=float(round(sat, 6)),
        water_activity=float(round(a_w, 6)),
        temp_c=float(round(temp_c, 4)),
        shelf_life_days=float(round(shelf, 4)),
        preservation_class=cls,
        palatability=float(round(palat, 6)),
        nutrient_retention=float(round(nutrient, 6)),
        appeal_rgb=appeal, is_fresh=bool(is_fresh),
        salt_limited=bool(salt_limited),
        salt_source=(str(salt_source) if salt_source is not None else None),
        salt_yield_kg_m2=float(round(salt_yield_kg_m2, 6)),
        confidence=confidence)


def fresh_vs_cured(food_kind: FoodKind, temp_c: float
                   ) -> Tuple[CuringCue, CuringCue]:
    """The lie #7, side by side: the SAME food at the SAME climate, fresh vs
    saturation-salted. Fresh = appealing + perishable ; cured = drab + keeps."""
    food = _FOOD[FoodKind(food_kind)]
    fresh = _cure_from_inputs(food_kind, 0.0, temp_c)
    cured = _cure_from_inputs(food_kind, _saturation_dose(food.water_frac), temp_c)
    return fresh, cured


# ---------------------------------------------------------------------------
# Salt access — the C15 composition (more pan → more curing power; none → fresh).
# ---------------------------------------------------------------------------

def _dose_from_yield(salt_yield_kg_m2: float, food: _FoodProfile) -> float:
    """Achievable salt dose (kg/kg) given a pan's solar-salt yield (C15).

    A copious salar (yield ≥ ``se.ABUNDANT_KG_M2``) supplies enough to reach
    full saturation; a meagre flat supplies a partial cure; a barren lagoon
    (yield 0 / not harvestable) supplies nothing → the food stays fresh. The
    world never lies: no real salt, no real preservation."""
    if salt_yield_kg_m2 <= 0.0:
        return 0.0
    frac = min(1.0, float(salt_yield_kg_m2) / se.ABUNDANT_KG_M2)
    return _saturation_dose(food.water_frac) * frac


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_food_curing(sim) -> Dict:
    """Idempotent installer. Ensures C15 (salt) exists; adds **zero** tick cost.

    Returns the (presently trivial) per-sim marker dict so the install contract
    matches the other capabilities (idempotent, no ``sim.step`` wrapping)."""
    se.install_salt_evaporation(sim)  # ensure C15 salt perception exists
    marker = getattr(sim, "_food_curing_state", None)
    if marker is None:
        marker = {}
        sim._food_curing_state = marker
    return marker


def cure_food_at(sim, world_x: float, world_y: float, food_kind: FoodKind,
                 salt_dose_frac: float) -> CuringCue:
    """**Non-mutating** preview: if an agent salts ``food_kind`` at this salt dose
    at world ``(x, y)``, this is the truthful outcome (shelf life + a_w + the cost).

    Reads the local macro climate (temperature) exactly as C15 does — same SSOT
    climate path, no drift. Touches nothing (no salt/food/water consumed)."""
    install_food_curing(sim)
    temp_c = _temp_at(sim, world_x, world_y)
    return _cure_from_inputs(food_kind, salt_dose_frac, temp_c)


def achievable_cure_near(sim, row: int, food_kind: FoodKind,
                         perception_radius_m: float = 192.0) -> CuringCue:
    """The best curing an agent at ``row`` can actually achieve for ``food_kind``
    here — bounded by the salt it can perceive/harvest nearby (C15).

    Composes C15: uses ``se.best_saltpan_near`` to find the richest harvestable
    pan in range, derives the achievable dose from its yield, and prices the cure
    against the local climate. **No harvestable pan in range → dose 0 → the food
    stays fresh/perishable** (the honest floor). Non-mutating preview."""
    install_food_curing(sim)
    food = _FOOD[FoodKind(food_kind)]
    pan = se.best_saltpan_near(sim, int(row), perception_radius_m)
    ax = float(sim.agents.pos[int(row), 0])
    ay = float(sim.agents.pos[int(row), 1])
    temp_c = _temp_at(sim, ax, ay)
    if pan is None:
        return _cure_from_inputs(food_kind, 0.0, temp_c, salt_limited=True)
    dose = _dose_from_yield(pan.salt_yield_kg_m2, food)
    sat_dose = _saturation_dose(food.water_frac)
    return _cure_from_inputs(food_kind, dose, temp_c, salt_source=pan.source,
                             salt_yield_kg_m2=pan.salt_yield_kg_m2,
                             salt_limited=dose < sat_dose - 1e-9)


def _temp_at(sim, world_x: float, world_y: float) -> float:
    """Local mean annual temperature (°C) of the macro climate at ``(x, y)``.

    Reuses C15's climate-read path (``se._resolve_anchor`` / ``se._climate_at``) —
    one implementation, zero drift. Falls back to ``T_REF_C`` if the world anchor
    is unavailable (keeps the pure physics well-defined)."""
    world, origin = se._resolve_anchor(sim)
    if world is None or origin is None:
        return T_REF_C
    coord = world_to_chunk(float(world_x), float(world_y))
    temp_c, _precip = se._climate_at(world, origin, coord)
    return float(temp_c)


def food_curing_summary(sim, food_kind: FoodKind = FoodKind.LEAN_MEAT
                        ) -> Dict[str, object]:
    """Aggregate, over the saltpans currently in the streamer cache, what curing
    of ``food_kind`` they enable — for the dashboard / smoke journal. Read-only.

    For every chunk that C15 reports as a *harvestable* salt pan, derive the cure
    its salt makes possible (at that chunk's climate) and tally the classes."""
    install_food_curing(sim)
    by_class: Dict[str, int] = {}
    n_pans = 0
    n_enables_cure = 0          # pans whose salt lifts the food past PERISHABLE
    best_shelf = 0.0
    food = _FOOD[FoodKind(food_kind)]
    for coord in list(sim.streamer.cache.keys()):
        pan = se.saltpan_cue_for_chunk(sim, coord)
        if pan is None or not pan.harvestable:
            continue
        n_pans += 1
        dose = _dose_from_yield(pan.salt_yield_kg_m2, food)
        cue = _cure_from_inputs(food_kind, dose, pan.temp_c,
                                salt_source=pan.source,
                                salt_yield_kg_m2=pan.salt_yield_kg_m2)
        by_class[cue.preservation_class.name] = \
            by_class.get(cue.preservation_class.name, 0) + 1
        if cue.preservation_class != PreservationClass.PERISHABLE:
            n_enables_cure += 1
        best_shelf = max(best_shelf, cue.shelf_life_days)
    return {
        "food": FoodKind(food_kind).name,
        "n_harvestable_pans": n_pans,
        "n_pans_enabling_cure": n_enables_cure,
        "cure_enable_rate": round(n_enables_cure / n_pans, 4) if n_pans else 0.0,
        "best_shelf_life_days": round(best_shelf, 2),
        "by_class": dict(sorted(by_class.items())),
    }


__all__ = [
    "FoodKind", "PreservationClass", "CuringCue",
    "install_food_curing", "cure_food_at", "achievable_cure_near",
    "fresh_vs_cured", "food_curing_summary",
    "SAT_BRINE_AW", "SAT_BRINE_FRAC", "A_W_FRESH_REF", "A_W_NO_GROWTH",
    "Q10", "SHELF_BASE_DAYS", "SHELF_MAX_DAYS", "SEMI_CURED_DAYS", "CURED_DAYS",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
