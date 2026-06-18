"""Genesis Engine — Substrate capability : la fonte du cuivre (Cap. C13).

**La 4ᵉ capacité de TRANSFORMATION** (après C8 ``lithic_tempering``, C9
``ceramic_firing``, C10 ``lime_burning``) — et la **PREMIÈRE TRANSFORMATION
MÉTALLURGIQUE** : le **seuil chalcolithique**, le **premier métal**. C12
``forced_draught`` a porté un four enclos (C11) soufflé au charbon **au-delà du point
de fusion du cuivre** (1085 °C) et exposé ``would_smelt_copper_here`` comme un
**potentiel ground-truthé** — explicitement en différant *« la fonte effective
(consommer le minerai → produire le métal) »* à **cette** capacité. C13 la **réalise** :
elle **consomme** réellement le minerai (mutation géologique via ``geo.mine_at``) et
**rend** un bouton de cuivre + de la scorie, exactement comme le monde s'y était engagé.

**Règle d'émergence absolue** (cf. ``surface_mineralization`` (C1) …
``forced_draught`` (C12)) : rien n'est scripté. Un agent ne *sait* pas qu'« on chauffe
la pierre verte dans un four soufflé pour en faire couler le métal ». Il **VOIT** la
tache verte (C1), il **SAIT faire** un four à tirage forcé ici (C12) — et en jetant par
hasard un fragment de roche verte dans sa braise rugissante de charbon, il **découvre**
qu'un perlé de métal **suinte** et se fige en une bille rouge, malléable, qu'on martèle.
Ce module n'expose qu'un **signal physique véridique** : *ce minerai-ci, fondu dans le
four atteignable ici, rendrait tant de cuivre, de telle pureté, avec tant de scorie — et
le ferait directement, ou seulement après l'avoir grillé*. Le creuset, la tuyère, le
fluxage à la silice, le moulage, le martelage — toute la chaîne opératoire reste
**émergente**.

Ce n'est pas un potentiel de plus : c'est la **fonte effective** (mutation)
----------------------------------------------------------------------------
C9/C10/C12 sont des **oracles non mutants** (le monde *prédit* l'issue ; l'acte reste
émergent). C13 conserve cet oracle (``smelt_cue_for_chunk`` / ``smelt_preview`` —
déterministes, non mutants, asservis par test) **mais ajoute** ``smelt_at`` — le seul
point d'entrée **mutant** de l'arc C1→C13 : il **extrait** une charge de minerai de la
colonne géologique (réemploi de la SSOT d'extraction ``geo.mine_at`` — le minerai
*disparaît* du sol) et **réduit** cette charge en métal selon la SSOT
``copper_smelt_yield``. C'est ce qui fait de C13 une vraie *transformation* et non un
3ᵉ potentiel : la promesse de C12 (« consommer le minerai → produire le métal ») est
tenue, à la lettre. « Le monde ne ment jamais » devient ici testable au sens fort :
le cuivre *réellement rendu* par ``smelt_at`` égale celui que l'oracle avait *promis*.

N'introduit AUCUN nouveau « tell » minéral — il COMPOSE (garde-fou D8)
---------------------------------------------------------------------
Comme C7→C12, ce module **ne surface aucune nouvelle matière**, n'a **pas** de table
``_PROFILE`` et **ne crée aucune entrée** ``PY_TO_RUST`` / ``PY_CATALOGUE_ONLY``
(cf. ``test_geology_cross_language_contract``). C'est la **7ᵉ** capacité D8-par-
composition. Il *lit* deux capacités déjà classées cross-langage :

* le **four** assez chaud — l'apparatus de C12 ``forced_draught``
  (``forced_cue_for_chunk`` : ``forced_peak_c``, ``reaches_copper_smelting_temp``,
  ``copper_ore_here`` / ``copper_mineral``, ``would_smelt_copper_here``) ;
* le **minerai de cuivre** — le tell de surface de C1 ``surface_mineralization`` (la
  « tache verte » malachite/azurite : ``native_copper`` / ``chalcopyrite``).

Et il **réutilise verbatim** le seuil de fusion ``fd.COPPER_SMELT_TEMP_C`` (C12) et,
comme SSOT métallurgique, le **rendement par élément** du catalogue minéral
(``Mineral.yields_per_kg_ore["Cu"]``, ``Mineral.category``) — aucune teneur n'est
re-déclarée ici. Le fichier est volontairement **hors du glob** ``*_outcrop.py`` : ce
n'est pas un affleurement, c'est une transformation. Décision asservie par
``test_introduces_no_new_tell``.

Le mensonge rendu visible #4 — le cuivre natif (facile) vs la chalcopyrite (sulfure)
-------------------------------------------------------------------------------------
C8 : l'obsidienne *semble* la pierre idéale mais la chauffer ne gagne rien (déjà verre).
C9 : le kaolin *semble* la meilleure argile mais sous-cuit au feu nu. C13 prolonge
l'inversion **sur le même tell vert** que C1 expose **identiquement** pour deux minerais
métallurgiquement opposés (veille 2026-06-18 ; les isotopes du plomb à Belovode montrent
que les fondeurs *connaissaient* la différence) :

* **cuivre natif** (``native_copper``, élément natif) — c'est **déjà** du métal. Pas de
  réduction : il suffit de le **fondre & coalescer** (≥1085 °C). Rendement élevé, pas de
  grillage. C'est le premier cuivre travaillé du Chalcolithique.
* **chalcopyrite** (``CuFeS₂``, sulfure) — **même tache verte** en surface, mais un
  **sulfure réfractaire** : le soufre et le fer **verrouillent** le cuivre dans une matte
  vitreuse. Tenter de la fondre *crue* dans un four soufflé ne rend **presque rien** — il
  faut d'abord la **griller** (oxydation partielle ~590 °C, qui chasse le SO₂ ; un simple
  feu ouvert C7/C9 suffit) **puis** la fondre en matte avec un fluxage à la silice. C'est
  pourquoi les minerais sulfurés sont venus **bien plus tard** que les oxydes/natifs.

La leçon émergente que ``best_smelt_site_near`` enseigne (il préfère le cuivre
*réellement* récupérable) : **fonds le vert natif, pas le vert sulfuré** — tant que tu
n'as pas découvert le grillage. Le monde ne ment pas : ``smelt_at`` sur une chalcopyrite
crue **consomme** la charge et ne rend **que de la scorie** (``recovered_cu_kg == 0``,
``required_roasting`` True) — la leçon coûteuse, physiquement vraie, du sulfure.

Physique de la fonte — la veille 2026-06-18 (archéométrie du cuivre)
--------------------------------------------------------------------
La fonte est **gouvernée par la thermo + la minéralogie**, jamais arbitraire (méta-règle
du substrat). Trois quantités se rencontrent :

1. **Pointe du four** (``fd.forced_peak_c``, réemploi C12). Doit franchir
   ``fd.COPPER_SMELT_TEMP_C`` = 1085 °C (Belovode : réduction de la malachite + charbon
   à ~1100–1200 °C → prills de cuivre + cuprite dans une matrice vitreuse silicatée).
2. **Classe du minerai** (``Mineral.category``, catalogue) → grillage requis ou non, et
   rendement de base : natif (fonte directe) > oxyde/carbonate (réduction directe) >
   sulfure (grillage + matte, multi-étapes, lossy).
3. **Teneur en cuivre** (``yields_per_kg_ore["Cu"]``, catalogue) : natif 1,0 ; chalcopyrite
   0,35 (le reste = Fe + S → scorie/matte). La fonte primitive **ne récupère jamais tout**
   le cuivre contenu (la scorie en retient toujours des prills ; veille MDPI 2025 : Cu
   dissous résiduel dans la scorie même industrielle) — d'où des plafonds de rendement
   honnêtes sous 1,0, montant avec la surchauffe (un bain plus chaud décante mieux le
   métal de la scorie).

La marche différée honnête — le bronze (C14+) et le fer
-------------------------------------------------------
Le cuivre seul est **mou**. Le **bronze** (Cu + Sn) exige de trouver *aussi* l'étain
(``cassiterite`` au catalogue) et de découvrir l'alliage — mais l'étain ne porte **aucun
tell de surface** (pas dans les groupes d'expression de C1) : l'agent doit l'explorer à
l'aveugle. C'est une capacité **future** (C14), différée honnêtement comme C9→C12
différaient vers le four puis le tirage forcé. Le **bas-fourneau du fer**
(``fd.reaches_iron_bloomery_temp``, paroi réfractaire requise, atmosphère réductrice CO)
porte la chaîne plus loin encore.

Déterminisme
------------
L'oracle est pur : composition de ``forced_cue_for_chunk`` (C12) — lui-même ``prf_rng`` /
dérivé du seed — avec des SSOT purs (seuil C12, catalogue minéral). Aucun RNG nouveau.
Bit-identique entre deux runs de même seed. (``smelt_at`` mute volontairement la
géologie — ce n'est pas l'oracle ; c'est l'acte.)

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — la fonte est une lecture/transformation
dérivée du substrat (four + minerai), comme C1→C12.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape (chunk → issue de
transformation), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from engine.world import CHUNK_SIDE_M, world_to_chunk
from engine.mineral_catalog import MINERAL_BY_NAME, MineralCategory
# Single sources of truth — reused verbatim, never re-modelled (garde-fou D8).
import engine.forced_draught as fd          # C12 — the hot-enough furnace + Cu threshold
import engine.surface_mineralization as sm  # C1 — the green copper surface tell (dig depth)
import engine.geology as geo                # the ore-extraction SSOT (mine_at)

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# --- Roasting threshold (°C). A primary sulfide (chalcopyrite) must be dead/partial-
# roasted to drive off SO2 before it can be smelted to a matte. Archaeometry (veille
# 2026-06-18): partial roast ~590 °C. A bare open fire (C7/C9, 600–850 °C) already
# clears this — the roast is *easy*; it is *knowing it is needed* that is the discovery.
ROAST_TEMP_C = 590.0

# --- Recovery model (°C / dimensionless). Primitive smelting never recovers ALL the
# contained copper (the slag always retains cuprite prills; veille MDPI 2025: residual
# soluble Cu even in industrial slag). Each ore class has an honest base recovery and a
# ceiling < 1.0; a hotter bath settles metal from slag better, so recovery rises with
# superheat above the melting point, saturating over SUPERHEAT_SPAN_C.
SUPERHEAT_SPAN_C = 200.0   # °C above the melt point for the full superheat bonus
SUPERHEAT_GAIN = 0.15      # extra recovery a well-superheated, well-settled bath wins

# Native metal — already copper; just melt & coalesce. Highest recovery, no roast.
NATIVE_BASE_RECOVERY = 0.80
NATIVE_RECOVERY_CEIL = 0.95
NATIVE_BEAD_PURITY = 0.97

# Oxide / carbonate (malachite-type) — direct reduction under a reducing CO atmosphere.
# (No such ore is seeded today — native + sulfide only — but modelled for honesty.)
OXIDE_BASE_RECOVERY = 0.60
OXIDE_RECOVERY_CEIL = 0.80
OXIDE_BEAD_PURITY = 0.92

# Sulfide (chalcopyrite) — roast then matte-smelt: multi-step, lossy, lower-purity
# blister copper (residual Fe + S). Only reachable AFTER a roast (else recovery 0).
SULFIDE_BASE_RECOVERY = 0.50
SULFIDE_RECOVERY_CEIL = 0.72
SULFIDE_BEAD_PURITY = 0.85

# Default ore charge (kg) a single smelt consumes from the column (mirrors mine_at).
DEFAULT_CHARGE_KG = 5.0

# Copper-bearing expression group (the same C1 surfaces as the green tell). Reused, not
# re-listed — these ARE the minerals C1's malachite/azurite cue surfaces.
_COPPER_GROUP = "copper"


@dataclass(frozen=True)
class SmeltYield:
    """Ground-truth metallurgical outcome of smelting ``ore_kg`` of one copper ore in a
    furnace whose peak is ``peak_c`` (optionally pre-roasted). Pure SSOT — no rounding,
    no I/O, trivially unit-testable. ``smelt_at`` and the cue both derive from this."""
    ore_class: str                 # "native_metal" | "oxide" | "sulfide" | "non_copper"
    requires_roasting: bool        # a sulfide must be roasted first (else recovery 0)
    contained_cu_fraction: float   # catalogue Cu yield per kg of this ore
    contained_cu_kg: float         # ore_kg * contained_cu_fraction (the copper *in* the ore)
    hot_enough: bool               # peak_c >= the copper melting point (C12 SSOT)
    recovery_efficiency: float     # fraction of contained Cu actually recovered [0,1)
    recovered_cu_kg: float         # the metal bead this smelt yields (kg)
    slag_kg: float                 # everything not recovered (gangue + lost Cu + Fe/S)
    bead_purity: float             # Cu mass fraction of the recovered metal (0 if none)


# ---------------------------------------------------------------------------
# Single source of truth — the smelt physics the world commits to.
# ---------------------------------------------------------------------------

def _ore_class_params(category: MineralCategory) -> Tuple[str, bool, float, float, float]:
    """(ore_class, requires_roasting, base_recovery, recovery_ceiling, bead_purity) for
    a mineral category. Keyed on the catalogue ``MineralCategory`` (SSOT — no ore-name
    duplication): native metal melts directly; oxide/carbonate reduce directly; a
    sulfide must be roasted then matte-smelted."""
    if category == MineralCategory.NATIVE_ELEMENT:
        return ("native_metal", False, NATIVE_BASE_RECOVERY,
                NATIVE_RECOVERY_CEIL, NATIVE_BEAD_PURITY)
    if category in (MineralCategory.OXIDE, MineralCategory.CARBONATE):
        return ("oxide", False, OXIDE_BASE_RECOVERY,
                OXIDE_RECOVERY_CEIL, OXIDE_BEAD_PURITY)
    if category == MineralCategory.SULFIDE:
        return ("sulfide", True, SULFIDE_BASE_RECOVERY,
                SULFIDE_RECOVERY_CEIL, SULFIDE_BEAD_PURITY)
    return ("non_copper", False, 0.0, 0.0, 0.0)


def copper_smelt_yield(ore_mineral: Optional[str], ore_kg: float, peak_c: float,
                       *, roasted: bool = False) -> SmeltYield:
    """Deterministic SSOT for the metal a copper smelt yields.

    ``ore_mineral`` is a catalogue name (C1 surfaces ``native_copper`` / ``chalcopyrite``
    as the green tell). The contained-copper fraction and the ore class come straight
    from the mineral catalogue — never re-declared here. The furnace must reach the
    copper melting point (``fd.COPPER_SMELT_TEMP_C``, reused from C12). A **sulfide**
    yields **nothing** unless it has been ``roasted`` first (the lie made visible — the
    same green tell hides a refractory sulfide). Recovery rises with superheat above the
    melting point and saturates below an honest ceiling < 1.0 (the slag always keeps
    some copper). Any module that *actually smelts* MUST read this, so the world never
    lies about what a smelt yields."""
    m = MINERAL_BY_NAME.get(ore_mineral) if ore_mineral else None
    if m is None:
        return SmeltYield("non_copper", False, 0.0, 0.0, False, 0.0, 0.0,
                          max(0.0, float(ore_kg)), 0.0)
    ore_kg = max(0.0, float(ore_kg))
    contained_fraction = float(m.yields_per_kg_ore.get("Cu", 0.0))
    ore_class, requires_roasting, base, ceil, purity = _ore_class_params(m.category)
    if contained_fraction <= 0.0:           # not a copper ore at all
        return SmeltYield("non_copper", False, 0.0, 0.0, False, 0.0, 0.0, ore_kg, 0.0)
    contained = ore_kg * contained_fraction
    hot = peak_c >= fd.COPPER_SMELT_TEMP_C
    superheat = min(1.0, max(0.0, (peak_c - fd.COPPER_SMELT_TEMP_C) / SUPERHEAT_SPAN_C))
    if not hot:
        eff = 0.0                            # furnace too cold — no melt, no metal
    elif requires_roasting and not roasted:
        eff = 0.0                            # un-roasted sulfide locks Cu into matte/slag
    else:
        eff = min(ceil, base + SUPERHEAT_GAIN * superheat)
    recovered = contained * eff
    slag = max(0.0, ore_kg - recovered)
    bead_purity = purity if recovered > 0.0 else 0.0
    return SmeltYield(
        ore_class=ore_class, requires_roasting=requires_roasting,
        contained_cu_fraction=contained_fraction, contained_cu_kg=contained,
        hot_enough=hot, recovery_efficiency=eff, recovered_cu_kg=recovered,
        slag_kg=slag, bead_purity=bead_purity)


@dataclass(frozen=True)
class SmeltCue:
    """A truthful copper-smelting affordance at one chunk.

    What an agent *could* discover by feeding the green stone C1 shows into the
    forced-draught furnace C12 builds: a bead of red metal weeps from the rock. It is
    NOT handed to the agent as "smelt malachite at 1100 °C" — the agent must learn the
    heat+ore→metal correlation by acting. ``recovered_cu_per_kg_ore`` (directly now) and
    ``recovered_cu_per_kg_ore_roasted`` (after a roast) are the ground truth the world
    commits to: ``smelt_at`` yields *exactly* this. Emitted iff C12 says
    ``would_smelt_copper_here`` (the furnace is hot enough AND a copper ore is here)."""
    coord: Tuple[int, int, int]
    biome: int
    # the ore (C1 ground truth) and its metallurgy (catalogue SSOT)
    copper_mineral: str            # ground-truth copper ore C1 surfaces (green tell)
    ore_class: str                 # "native_metal" | "oxide" | "sulfide"
    requires_roasting: bool        # a sulfide — must roast (≈590 °C) before it smelts
    contained_cu_fraction: float   # catalogue Cu per kg ore (native 1.0, chalcopyrite 0.35)
    # the furnace (C12 ground truth)
    forced_peak_c: float           # the forced-draught furnace peak (C12 SSOT)
    wall_refractory: bool          # C12: refractory kaolin wall (reaches further regimes)
    # the smelt outcome (SSOT, per kg of copper-ore charged)
    smeltable_now: bool            # directly yields metal here (native/oxide, hot enough)
    needs_roasting_first: bool     # sulfide & not yet roasted — the lie made visible
    recovery_efficiency: float     # direct (un-roasted) recovery fraction [0,1)
    recovered_cu_per_kg_ore: float        # metal yielded NOW (0 for an un-roasted sulfide)
    recovered_cu_per_kg_ore_roasted: float  # metal yielded after a roast (the potential)
    slag_per_kg_ore: float         # slag (direct path) per kg ore
    bead_purity: float             # Cu fraction of the bead on the achievable path
    roast_temp_c: float            # the roast temperature a sulfide needs first
    confidence: float              # reliability of achieving the outcome [0,1]


# ---------------------------------------------------------------------------
# Core derivation — smelt outcome from a C12 forced-draught cue.
# ---------------------------------------------------------------------------

def _cue_from_inputs(coord, forced_cue) -> Optional[SmeltCue]:
    """Pure derivation (no ``sim`` — trivially unit-testable, like its siblings).
    Emits a cue iff C12 reports ``would_smelt_copper_here`` — i.e. the forced-draught
    furnace here is hot enough (≥1085 °C) AND C1 sees a copper ore co-located. The
    1+1>2 gate: no hot furnace or no copper ⇒ no smelt affordance."""
    if forced_cue is None or not getattr(forced_cue, "would_smelt_copper_here", False):
        return None
    ore = getattr(forced_cue, "copper_mineral", None)
    if ore is None:
        return None
    peak = float(forced_cue.forced_peak_c)
    direct = copper_smelt_yield(ore, 1.0, peak, roasted=False)
    roasted = copper_smelt_yield(ore, 1.0, peak, roasted=True)
    needs_roast = bool(direct.requires_roasting and direct.recovered_cu_kg <= 0.0)
    smeltable_now = bool(direct.recovered_cu_kg > 0.0)
    achievable = roasted if needs_roast else direct

    conf = float(getattr(forced_cue, "confidence", 0.0))
    rich = min(1.0, direct.contained_cu_fraction)   # native 1.0, chalcopyrite 0.35
    confidence = float(min(1.0, conf * (0.6 + 0.4 * rich)))

    return SmeltCue(
        coord=tuple(int(c) for c in coord),
        biome=int(getattr(forced_cue, "biome", 0)),
        copper_mineral=str(ore),
        ore_class=direct.ore_class,
        requires_roasting=bool(direct.requires_roasting),
        contained_cu_fraction=float(round(direct.contained_cu_fraction, 4)),
        forced_peak_c=float(round(peak, 1)),
        wall_refractory=bool(getattr(forced_cue, "wall_refractory", False)),
        smeltable_now=smeltable_now,
        needs_roasting_first=needs_roast,
        recovery_efficiency=float(round(direct.recovery_efficiency, 4)),
        recovered_cu_per_kg_ore=float(round(direct.recovered_cu_kg, 6)),
        recovered_cu_per_kg_ore_roasted=float(round(roasted.recovered_cu_kg, 6)),
        slag_per_kg_ore=float(round(direct.slag_kg, 6)),
        bead_purity=float(round(achievable.bead_purity, 4)),
        roast_temp_c=float(ROAST_TEMP_C),
        confidence=float(round(confidence, 4)))


@dataclass(frozen=True)
class SmeltResult:
    """The realized outcome of an actual ``smelt_at`` — the **fonte effective**. The ore
    has been *consumed* from the geology column; this is what was *gotten*. The world
    never lies: ``recovered_cu_kg`` equals the cue's committed yield for ``ore_consumed_kg``."""
    coord: Tuple[int, int, int]
    copper_mineral: str
    ore_class: str
    ore_consumed_kg: float         # copper-ore mass actually extracted (mutation)
    recovered_cu_kg: float         # the copper bead recovered (0 for un-roasted sulfide)
    slag_kg: float                 # slag produced (spent ore + gangue, less the metal)
    bead_purity: float             # Cu fraction of the bead (0 if none)
    roasted: bool                  # whether the charge was roasted before smelting
    required_roasting: bool        # whether this ore *needed* roasting (sulfide)
    peak_c: float                  # the furnace peak the smelt ran at


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_copper_smelting(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim`` and ensures the
    composed capabilities (C12 forced draught, C1 surface mineralization, geology) are
    installed. Adds **zero** per-tick cost: the oracle is derived on query and memoised.
    Returns the cache dict (``sim._copper_smelt_cue_cache``)."""
    fd.install_forced_draught(sim)
    sm.install_surface_mineralization(sim)
    geo.install_geology(sim)
    cache = getattr(sim, "_copper_smelt_cue_cache", None)
    if cache is None:
        cache = {}
        sim._copper_smelt_cue_cache = cache
    return cache


def smelt_cue_for_chunk(sim, coord: Tuple[int, int, int]) -> Optional[SmeltCue]:
    """Truthful copper-smelting affordance at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, C12 ``forced_cue_for_chunk(sim, coord)`` reports
    ``would_smelt_copper_here`` (a forced furnace ≥1085 °C AND a co-located copper ore),
    and ``copper_mineral`` agrees with C1's copper-group surface cue."""
    coord = tuple(int(c) for c in coord)
    cache = install_copper_smelting(sim)
    if coord in cache:
        return cache[coord]
    forced = fd.forced_cue_for_chunk(sim, coord)
    cue = _cue_from_inputs(coord, forced)
    cache[coord] = cue
    return cue


def prospect_smelt(sim, world_x: float, world_y: float) -> Optional[SmeltCue]:
    """What an agent standing at world ``(x, y)`` could discover about smelting the
    copper ore here. Returns the cue (metal yield + truthful outcome) or None when
    nothing is smeltable underfoot (no hot-enough furnace or no copper ore)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return smelt_cue_for_chunk(sim, coord)


def smelt_preview(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of whether (and how much) copper a smelt at ``(x, y)``
    would yield — the ground-truthed outcome the perception cue must agree with.

    Touches NOTHING (no ore mined, no fire lit, no geology mutated): the truth oracle,
    not the act. Always returns a dict (even when not smeltable), naming the *missing*
    ingredient — the honest 'why not'. The lie this cap exposes: a green tell may be a
    refractory **sulfide** (``needs_roasting_first`` True, ``smeltable_now`` False — it
    *would* give metal, but only after a roast)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = smelt_cue_for_chunk(sim, coord)
    if cue is not None:
        return {"smeltable": True, "reason": "ok",
                "copper_mineral": cue.copper_mineral,
                "ore_class": cue.ore_class,
                "requires_roasting": cue.requires_roasting,
                "smeltable_now": cue.smeltable_now,
                "needs_roasting_first": cue.needs_roasting_first,
                "roast_temp_c": cue.roast_temp_c,
                "forced_peak_c": cue.forced_peak_c,
                "recovered_cu_per_kg_ore": cue.recovered_cu_per_kg_ore,
                "recovered_cu_per_kg_ore_roasted": cue.recovered_cu_per_kg_ore_roasted,
                "slag_per_kg_ore": cue.slag_per_kg_ore,
                "bead_purity": cue.bead_purity,
                "confidence": cue.confidence,
                "biome": cue.biome}
    # Not smeltable — recompute the diagnostic to name the missing ingredient.
    forced = fd.forced_cue_for_chunk(sim, coord)
    if forced is None or not getattr(forced, "forceable", False):
        return {"smeltable": False, "reason": "no forced-draught furnace buildable here",
                "has_furnace": False, "has_copper_ore": False}
    if not getattr(forced, "reaches_copper_smelting_temp", False):
        return {"smeltable": False,
                "reason": "furnace too cold to melt copper (needs >=1085 C)",
                "has_furnace": True, "has_copper_ore": bool(forced.copper_ore_here),
                "forced_peak_c": forced.forced_peak_c}
    if not getattr(forced, "copper_ore_here", False):  # pragma: no branch
        return {"smeltable": False, "reason": "no copper ore here to smelt",
                "has_furnace": True, "has_copper_ore": False,
                "forced_peak_c": forced.forced_peak_c}
    return {"smeltable": False, "reason": "not smeltable",  # pragma: no cover
            "has_furnace": True, "has_copper_ore": True}


def discover_smelt_sites_by_sight(sim, rows: List[int],
                                  perception_radius_m: float = 64.0
                                  ) -> Dict[int, List[SmeltCue]]:
    """For each agent ``row``, the smeltable sites perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    Turns the static substrate (a hot furnace + a copper ore) into a **perceivable,
    actionable** transformation signal — the agent then *chooses* to smelt.
    Deterministic order (by chunk distance, then coord)."""
    out: Dict[int, List[SmeltCue]] = {}
    if not rows:
        return out
    install_copper_smelting(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], SmeltCue]] = []
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
                cue = smelt_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def _achievable_yield(c: SmeltCue) -> float:
    """The copper a site can ultimately give (direct, or after a roast for a sulfide)."""
    return max(c.recovered_cu_per_kg_ore, c.recovered_cu_per_kg_ore_roasted)


def best_smelt_site_near(sim, row: int, perception_radius_m: float = 128.0,
                         *, require_direct: bool = False) -> Optional[SmeltCue]:
    """The most rewarding smelt site an agent at ``row`` can perceive — the actionable
    pick (highest achievable copper per kg ore; tie-break higher purity, then confidence,
    then nearest then coord).

    This is where the native-vs-sulfide inversion teaches: preferring the copper actually
    gotten, the agent learns to smelt the native green directly and to *roast* the sulfide
    green first. ``require_direct`` keeps only sites that yield metal NOW (native/oxide —
    no roast detour). Returns None when nothing smeltable is in sight."""
    cues = discover_smelt_sites_by_sight(sim, [int(row)], perception_radius_m
                                         ).get(int(row), [])
    pool = [c for c in cues if c.smeltable_now] if require_direct else cues
    if not pool:
        return None
    # already distance-sorted; prefer the most copper, then purest, then surest.
    return max(pool, key=lambda c: (_achievable_yield(c), c.bead_purity, c.confidence))


def smelt_at(sim, row: int, *, charge_kg: float = DEFAULT_CHARGE_KG,
             roasted: bool = False) -> Optional[SmeltResult]:
    """**The fonte effective** (the one MUTATING entry point of the C1→C13 arc).

    Smelt the copper ore under agent ``row`` in the forced-draught furnace buildable
    there. Side effects: **consumes** a charge of ore from the geology column (via the
    SSOT ``geo.mine_at`` — the ore is drained from ``extracted_kg``) and reduces it per
    ``copper_smelt_yield``. Returns a ``SmeltResult`` (metal bead + slag) or None when
    nothing is smeltable here (no hot-enough furnace, or no copper ore underfoot).

    The world never lies: the realized ``recovered_cu_kg`` equals the cue's committed
    per-kg yield × the ore actually consumed. ``roasted=False`` on a sulfide consumes the
    charge and yields **only slag** (``recovered_cu_kg == 0``) — the honest, costly lesson
    that the green tell hid a sulfide; the agent must discover roasting first."""
    install_copper_smelting(sim)
    pos = sim.agents.pos
    coord = world_to_chunk(float(pos[row, 0]), float(pos[row, 1]))
    cue = smelt_cue_for_chunk(sim, coord)
    if cue is None:
        return None
    c1 = sm.surface_cue_for_chunk(sim, coord)
    if c1 is None or c1.group != _COPPER_GROUP:   # invariant guarantees a copper tell here
        return None  # pragma: no cover
    mined = geo.mine_at(sim, row, float(c1.dig_depth_m), float(charge_kg))
    if not mined:
        return None
    ore_kg = float(mined.get(cue.copper_mineral, 0.0))
    gangue_kg = float(sum(v for k, v in mined.items() if k != cue.copper_mineral))
    y = copper_smelt_yield(cue.copper_mineral, ore_kg, cue.forced_peak_c, roasted=roasted)
    slag = float(y.slag_kg + gangue_kg)
    return SmeltResult(
        coord=tuple(int(c) for c in coord),
        copper_mineral=cue.copper_mineral, ore_class=y.ore_class,
        ore_consumed_kg=float(round(ore_kg, 6)),
        recovered_cu_kg=float(round(y.recovered_cu_kg, 6)),
        slag_kg=float(round(slag, 6)),
        bead_purity=float(round(y.bead_purity, 4)),
        roasted=bool(roasted), required_roasting=bool(y.requires_roasting),
        peak_c=float(round(cue.forced_peak_c, 1)))


def smelt_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the dashboard /
    smoke journal. Read-only; computes cues lazily."""
    install_copper_smelting(sim)
    by_class: Dict[str, int] = {}
    by_mineral: Dict[str, int] = {}
    n_chunks = 0
    n_sites = 0
    n_direct = 0
    n_needs_roast = 0
    best_recovered = 0.0
    best_purity = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = smelt_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_sites += 1
        if cue.smeltable_now:
            n_direct += 1
        if cue.needs_roasting_first:
            n_needs_roast += 1
        by_class[cue.ore_class] = by_class.get(cue.ore_class, 0) + 1
        by_mineral[cue.copper_mineral] = by_mineral.get(cue.copper_mineral, 0) + 1
        best_recovered = max(best_recovered, _achievable_yield(cue))
        best_purity = max(best_purity, cue.bead_purity)
    return {
        "n_chunks": n_chunks,
        "n_smelt_sites": n_sites,
        "smelt_rate": round(n_sites / n_chunks, 4) if n_chunks else 0.0,
        "n_direct_smeltable": n_direct,
        "n_needs_roasting": n_needs_roast,
        "best_recovered_cu_per_kg_ore": round(best_recovered, 6),
        "best_bead_purity": round(best_purity, 4),
        "by_ore_class": dict(sorted(by_class.items())),
        "by_mineral": dict(sorted(by_mineral.items())),
    }


__all__ = [
    "SmeltYield", "SmeltCue", "SmeltResult",
    "install_copper_smelting", "smelt_cue_for_chunk", "prospect_smelt",
    "smelt_preview", "discover_smelt_sites_by_sight", "best_smelt_site_near",
    "smelt_at", "smelt_summary",
    "copper_smelt_yield",
    "ROAST_TEMP_C", "SUPERHEAT_SPAN_C", "SUPERHEAT_GAIN",
    "NATIVE_BASE_RECOVERY", "NATIVE_RECOVERY_CEIL", "NATIVE_BEAD_PURITY",
    "OXIDE_BASE_RECOVERY", "OXIDE_RECOVERY_CEIL", "OXIDE_BEAD_PURITY",
    "SULFIDE_BASE_RECOVERY", "SULFIDE_RECOVERY_CEIL", "SULFIDE_BEAD_PURITY",
    "DEFAULT_CHARGE_KG",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
