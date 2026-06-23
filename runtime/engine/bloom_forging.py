"""Genesis Engine — Substrate capability : le cinglage de la loupe (Cap. C19).

**La 6ᵉ capacité de TRANSFORMATION et la 3ᵉ MÉTALLURGIQUE** (après C13
``copper_smelting`` et C17 ``iron_bloomery``) — elle **ferme la chaîne opératoire du
fer**. C17 a **réduit** le minerai en une **loupe** (bloom) : une **éponge** de fer
métallique imprégnée de scorie de fayalite, qui ne **coule jamais** (le fer ne fond
qu'à 1538 °C, hors d'atteinte) et porte donc invariablement ``is_solid_bloom`` /
``requires_forging`` True. C17 s'arrêtait là, en différant **honnêtement** *« le
martelage de consolidation (forge), le cinglage — toute la chaîne opératoire reste
émergente »*. C19 la **réalise** : marteler la loupe spongieuse **à chaud** pour en
**expulser la scorie** et la **consolider** en **fer forgé** (wrought iron) — exactement
ce à quoi le monde s'était engagé. C'est l'exécution de la reco ``R-J12r3-2`` de l'audit
J+12 (« la forge de consolidation ferme la chaîne du fer — sans nouveau tell, sans feu
nouveau »).

**Règle d'émergence absolue** (cf. ``surface_mineralization`` (C1) …
``iron_bloomery`` (C17)) : rien n'est scripté. Un agent ne *sait* pas qu'« on martèle la
loupe au rouge pour en chasser la scorie ». Il **OBTIENT** une éponge de métal gris
récalcitrante (C17), s'attend peut-être au bouton coulé du cuivre (C13) — et **découvre**
qu'à froid elle se brise, qu'au rouge elle se compacte et qu'un liquide noir (la scorie)
en sort sous le marteau. Ce module n'expose qu'un **signal physique véridique** : *cette
loupe-ci, cinglée à cette chaleur, en tant de chaudes, rendrait tant de fer forgé, de
telle santé, en perdant tant en battitures et tant en scorie expulsée — ou se
fissurerait (red-short) en n'en rendant presque rien*. Le geste (la tuyère, l'enclume,
la cadence du marteau, le corroyage en barres) reste **émergent**.

Le mensonge rendu visible #10 — le fer du chapeau pyriteux se brise sous le marteau
-----------------------------------------------------------------------------------
C17 a montré l'inversion **à cinq voies** du chapeau de fer pour le *fondeur* (oxyde sain
/ pyrite red-short / plomb-zinc stérile). C19 prolonge le **même** verdict métallurgique
au *forgeron* — et le mensonge se rejoue, plus tard et plus cher dans la chaîne :

* La loupe d'**oxyde** (hématite / magnétite) est **saine** : martelée au rouge, le fer
  austénitique se soude sur lui-même tandis que la **fayalite** (``Fe₂SiO₄``, liquide
  ~1150–1300 °C) gicle hors des pores → un billon de **fer forgé** dense et résiliant.
  La récompense du forgeron.
* La loupe de **pyrite** (sulfure) est **red-short** : le soufre forme du **FeS** aux
  joints de grain, qui **fond sous la température de forge** → une phase liquide
  intergranulaire qui **fissure le métal pendant le martelage à chaud** (*hot-shortness*,
  veille 2026-06-23). Le forgeron qui cingle cette loupe comme une loupe d'oxyde obtient
  un billon **fendu**, qui s'émiette : rendement de fer forgé **effondré**, santé plafonnée
  bien sous le seuil utilisable. Exactement le pendant, à l'étape suivante, du
  ``red_short`` que C17 portait déjà : le chapeau de fer a livré du fer… qui **ne se forge
  pas**.

Donc, comme C17 mais pour le marteau : ``best_forge_site_near`` enseigne **cingle la loupe
d'oxyde**, **méfie-toi de la loupe pyriteuse** (elle se brise). Le monde ne ment pas :
``consolidate_bloom`` sur une loupe red-short rend honnêtement un billon presque vide
(``cracked`` True, ``wrought_iron_kg`` effondré) — la leçon coûteuse, physiquement vraie,
de la forge.

Le fer ne FOND toujours pas — fer forgé, jamais fonte (le solid-state se poursuit)
-----------------------------------------------------------------------------------
La consolidation reste un travail **à l'état SOLIDE** : on **soude** des grains de fer
austénitique (~900 °C+) en chassant la scorie liquide — on ne **coule** rien. Le produit
est du **fer forgé** (wrought iron, ~fer quasi pur veiné de filets de scorie résiduelle),
**jamais** de la fonte (cast iron, qui exigerait de **fondre** le fer à 1538 °C → le
haut-fourneau, hors d'atteinte ici). Invariablement : ``melted == False``,
``is_wrought == True``. La fonte est différée **honnêtement** (comme C9→C12 différaient
vers le four puis le tirage forcé, et C17 vers cette forge).

La chaleur de forge — pourquoi C19 réutilise le foyer de C12, pas le feu nu de C7
---------------------------------------------------------------------------------
La méta-règle du substrat exige que la physique soit **calculée, jamais arbitraire**. Le
**cinglage primaire** — l'expulsion de la scorie — n'est possible que tant que la
**fayalite reste liquide** : il faut tenir la loupe **au-dessus de ~1150–1300 °C** (veille
2026-06-23 : *« le bloom est réchauffé pour que la scorie fayalitique devienne fondue,
1200–1300 °C »*). Un **feu nu** (C7 / C9, ≤ 850 °C) est **trop froid** : la scorie y fige
et reste piégée. C'est donc le **même foyer à tirage forcé** (C12) qui a *fait* la loupe
qui la tient assez chaude pour la *cingler*. C19 réutilise ainsi le seuil SSOT
``fd.IRON_BLOOMERY_TEMP_C`` (1200 °C, le régime où la fayalite coule) — **aucun nouveau
feu**, exactement comme le promettait ``R-J12r3-2``. C'est fire-based : D9 (chaîne
fire-based) passe **0 → 1** après le non-feu C18 — une **alternance** propre, pas un
treadmill (la forge à chaud est physiquement obligatoire ; aucun travail à froid ne
chasse la scorie d'une loupe).

N'introduit AUCUN nouveau « tell » minéral — il COMPOSE (garde-fou D8)
---------------------------------------------------------------------
Comme C7→C18, ce module **ne surface aucune nouvelle matière**, n'a **pas** de table
``_PROFILE`` et **ne crée aucune entrée** ``PY_TO_RUST`` / ``PY_CATALOGUE_ONLY`` (cf.
``test_geology_cross_language_contract``). C'est la **13ᵉ** capacité D8-par-composition.
Il *lit* une seule capacité déjà classée cross-langage — la **loupe** de C17
``iron_bloomery`` (``bloom_cue_for_chunk`` : ``bloom_iron_per_kg_ore`` direct/roasted,
``bloom_purity``, ``red_short``, ``ore_class``, ``forced_peak_c``) — laquelle compose
elle-même C12 (le four) × C1 (le chapeau de fer). Le fichier est volontairement **hors du
glob** ``*_outcrop.py`` : ce n'est pas un affleurement, c'est une transformation.
Décision asservie par ``test_introduces_no_new_tell``.

Périmètre honnête (audit) — NON MUTANT, D10 gelé
------------------------------------------------
``consolidate_bloom`` transforme un **produit déjà obtenu** (la loupe que ``bloom_at`` de
C17 a rendue), il ne **lit ni ne mute la géologie** (contrairement au ``bloom_at`` mutant
de C17 / ``smelt_at`` de C13). C'est une transformation pure d'un matériau tenu, comme la
trempe lithique C8 ou la cuisson céramique C9. La frontière de mutation reste donc
**gelée** (``crates/MUTATION-FRONTIER.md`` : un seul point mutant, ``geo.mine_at``).

Physique du cinglage — la veille 2026-06-23 (archéométrie de la consolidation)
------------------------------------------------------------------------------
La consolidation est **gouvernée par la thermo + la métallurgie**, jamais arbitraire.
Quatre quantités se rencontrent :

1. **Chaleur de forge** (``forge_temp_c`` = ``fd.forced_peak_c``, réemploi C12). Doit
   franchir ``fd.IRON_BLOOMERY_TEMP_C`` pour garder la fayalite liquide → expulsable.
2. **Nombre de chaudes** (``n_heats``). Chaque chaude+martelage expulse une fraction
   **géométrique** de la scorie résiduelle (``EXPEL_PER_HEAT``) et **consolide** un peu
   plus (``CONSOLIDATION_PER_HEAT``, saturant) — mais **brûle** aussi du fer en
   **battitures** (oxyde FeO, ``SCALE_LOSS_PER_HEAT`` par chaude, en feu oxydant).
3. **Classe de la loupe** (``red_short``). Une loupe d'oxyde se consolide jusqu'à saine ;
   une loupe sulfurée **se fissure** (``RED_SHORT_CRACK_LOSS`` du fer part en éclats,
   santé plafonnée ``RED_SHORT_SOUNDNESS_CEIL``).
4. **Pureté** (``bloom_purity``, C17). L'expulsion de scorie **monte** la fraction de Fe
   du billon vers un plafond de fer forgé — moindre pour une loupe red-short (le soufre
   reste).

Conservation : ``wrought_iron_kg + scale_loss_kg + crack_loss_kg == bloom_iron_kg`` (tout
le fer de la loupe est rendu, brûlé en battitures ou perdu en fissures). La scorie
expulsée ≤ la scorie initialement piégée.

Déterminisme
------------
L'oracle est pur : composition de ``bloom_cue_for_chunk`` (C17) — lui-même ``prf_rng`` /
dérivé du seed — avec des SSOT pures (seuil C12, constantes de cinglage du module).
Aucun RNG nouveau. Bit-identique entre deux runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — la consolidation est une
lecture/transformation dérivée du substrat (la loupe + le foyer), comme C1→C18.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape (chunk → issue de
forge), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from engine.world import CHUNK_SIDE_M, world_to_chunk
# Single sources of truth — composed verbatim, never re-modelled (garde-fou D8).
import engine.iron_bloomery as ib   # C17 — the spongy iron bloom (composes C12×C1)
import engine.forced_draught as fd  # C12 — the hot-enough hearth + bloomery threshold (SSOT)

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# --- Slag-expulsion / welding heat (°C). Primary shingling only works while the fayalite
# slag (Fe2SiO4) stays MOLTEN (~1150-1300 °C, veille 2026-06-23). A bare open fire
# (<=850 °C, C7/C9) is too cold — the slag freezes in. So the SAME forced-draught hearth
# (C12) that smelted the bloom keeps it hot to forge it. Reused verbatim from C12 — no
# new threshold is invented (the bloomery regime IS the temperature at which fayalite
# flows). NOT a magic number.
SLAG_EXPULSION_TEMP_C = fd.IRON_BLOOMERY_TEMP_C

# --- The iron melting point (°C). Forging stays SOLID-STATE: we weld austenitic iron
# grains, we never pour. Pure iron melts at 1538 °C, far above any bloomery/forge hearth
# (capped ~1400 °C by the refractory wall, C12). Modelled so the world can state the honest
# deferral (cast iron / blast furnace lies beyond this — never reachable here).
IRON_MELT_TEMP_C = ib.IRON_MELT_TEMP_C

# --- Consolidation model (dimensionless). A raw bloom is a sponge of metallic iron with
# entrapped fayalite slag and voids; hot-working expels the slag and welds the iron.
DEFAULT_HEATS = 3            # typical reheat+hammer cycles for primary consolidation
EXPEL_PER_HEAT = 0.55        # fraction of REMAINING entrapped slag driven out per heat
SCALE_LOSS_PER_HEAT = 0.05   # fraction of iron oxidised to fire scale (FeO) per heat
CONSOLIDATION_PER_HEAT = 0.5  # soundness gained per heat (geometric, saturating)

# Entrapped slag in a RAW sponge bloom, per kg of metallic iron. Raw blooms are notoriously
# ~25-50% slag/voids by mass (veille); 0.5 kg slag / kg iron ≈ a 1/3-slag bloom.
RAW_SLAG_PER_IRON = 0.5

# --- Red-short (sulfide-derived) penalty. FeS at the grain boundaries liquefies below
# forging heat → intergranular cracking under the hammer (hot-shortness, veille 2026-06-23).
RED_SHORT_CRACK_LOSS = 0.5      # fraction of iron that shatters off forging a red-short bloom
RED_SHORT_SOUNDNESS_CEIL = 0.35  # a red-short bloom can never weld into a sound billet

# --- Soundness above which the consolidated billet is usable "sound wrought iron" (it
# holds an edge / takes a tool). Below it: a cracked, slag-streaked, near-useless billon.
SOUND_THRESHOLD = 0.70

# --- Final Fe fraction a fully-shingled billet approaches as slag is expelled (wrought
# iron is ~99% Fe). A red-short billet caps lower — residual sulfur stays in.
WROUGHT_PURITY_CEIL = 0.99
RED_SHORT_PURITY_CEIL = 0.85


def _geom_done(rate: float, n: int) -> float:
    """Fraction completed after ``n`` geometric steps each removing ``rate`` of the
    remainder: 1 - (1-rate)^n. Monotone in n, saturating at 1."""
    r = min(1.0, max(0.0, float(rate)))
    n = max(0, int(n))
    return float(1.0 - (1.0 - r) ** n)


@dataclass(frozen=True)
class WroughtYield:
    """Ground-truth outcome of *hot*-consolidating a bloom of ``bloom_iron_kg``
    metallic iron (purity ``bloom_purity``, ``red_short`` or not) at a
    forge heat ``forge_temp_c`` over ``n_heats`` reheat+hammer cycles. Pure SSOT — no
    rounding, no I/O, trivially unit-testable. The cue and ``consolidate_bloom`` both
    derive from this.

    ``melted`` is **always False** (solid-state welding — iron's 1538 °C is unreachable);
    the product is wrought iron, never cast. Conservation holds:
    ``wrought_iron_kg + scale_loss_kg + crack_loss_kg == bloom_iron_kg``."""
    hot_enough: bool               # forge_temp_c >= slag-expulsion heat (else slag freezes in)
    melted: bool                   # ALWAYS False — solid-state forging, never a pour
    is_wrought: bool               # soundness >= SOUND_THRESHOLD → usable sound wrought iron
    cracked: bool                  # red-short bloom fissured under the hammer (hot-shortness)
    red_short: bool                # passthrough: sulfide-derived, sulfur-embrittled
    n_heats: int                   # reheat+hammer cycles applied
    slag_expelled_fraction: float  # fraction of the entrapped slag driven out [0,1]
    slag_expelled_kg: float        # entrapped fayalite slag squeezed out (kg)
    scale_loss_kg: float           # iron lost to fire scale (FeO) over the heats (kg)
    crack_loss_kg: float           # iron lost to red-short cracking (kg; 0 if sound)
    wrought_iron_kg: float         # consolidated wrought iron recovered (kg)
    soundness: float               # how welded/slag-free the billet is [0,1]
    final_purity: float            # Fe fraction of the consolidated billet [0,1]
    consolidation_ratio: float     # wrought_iron_kg / bloom_iron_kg [0,1]


# ---------------------------------------------------------------------------
# Single source of truth — the bloom-consolidation physics the world commits to.
# ---------------------------------------------------------------------------

def wrought_yield(bloom_iron_kg: float, bloom_purity: float, red_short: bool,
                  forge_temp_c: float, *, n_heats: int = DEFAULT_HEATS) -> WroughtYield:
    """Deterministic SSOT for the wrought iron a hot consolidation of one bloom yields.

    The bloom (``bloom_iron_kg`` of metallic iron, Fe fraction ``bloom_purity``, possibly
    ``red_short``) is reheated to ``forge_temp_c`` and hammered ``n_heats`` times. The
    hearth must reach ``SLAG_EXPULSION_TEMP_C`` (= the C12 bloomery regime, where fayalite
    flows) or the slag stays frozen in and **nothing consolidates** (``hot_enough`` False,
    no wrought iron). Otherwise each heat expels a geometric fraction of the entrapped slag
    and welds the iron a little more, while burning some iron to fire scale. A **red-short**
    (sulfide) bloom **cracks** under the hammer: a large fraction of the iron shatters off
    and the billet can never reach a sound weld. Any module that *actually forges* a bloom
    MUST read this, so the world never lies about what the hammer yields. ``melted`` is
    **always False** — the iron is welded solid (1538 °C melt point is unreachable)."""
    bloom_iron_kg = max(0.0, float(bloom_iron_kg))
    n_heats = max(0, int(n_heats))
    hot = float(forge_temp_c) >= SLAG_EXPULSION_TEMP_C
    entrapped0 = bloom_iron_kg * RAW_SLAG_PER_IRON

    if bloom_iron_kg <= 0.0 or not hot or n_heats <= 0:
        # Too cold (slag frozen in) / nothing to forge → no consolidation at all.
        return WroughtYield(
            hot_enough=hot, melted=False, is_wrought=False, cracked=False,
            red_short=bool(red_short), n_heats=n_heats,
            slag_expelled_fraction=0.0, slag_expelled_kg=0.0,
            scale_loss_kg=0.0, crack_loss_kg=0.0, wrought_iron_kg=0.0,
            soundness=0.0, final_purity=0.0, consolidation_ratio=0.0)

    expelled_frac = _geom_done(EXPEL_PER_HEAT, n_heats)
    slag_expelled = entrapped0 * expelled_frac

    # Iron losses: fire scale every heat, plus red-short cracking (hot-shortness).
    scale_frac = _geom_done(SCALE_LOSS_PER_HEAT, n_heats)
    scale_loss = bloom_iron_kg * scale_frac
    iron_after_scale = bloom_iron_kg - scale_loss
    crack_loss = iron_after_scale * RED_SHORT_CRACK_LOSS if red_short else 0.0
    wrought = max(0.0, iron_after_scale - crack_loss)

    # Soundness: geometric consolidation with heats, capped low for a red-short bloom.
    soundness = _geom_done(CONSOLIDATION_PER_HEAT, n_heats)
    if red_short:
        soundness = min(soundness, RED_SHORT_SOUNDNESS_CEIL)

    # Purity rises toward the wrought ceiling as the slag is expelled (lower for red-short).
    ceil = RED_SHORT_PURITY_CEIL if red_short else WROUGHT_PURITY_CEIL
    base_purity = min(float(bloom_purity), ceil)
    final_purity = base_purity + (ceil - base_purity) * expelled_frac

    return WroughtYield(
        hot_enough=True, melted=False,
        is_wrought=bool(soundness >= SOUND_THRESHOLD and wrought > 0.0),
        cracked=bool(red_short), red_short=bool(red_short), n_heats=n_heats,
        slag_expelled_fraction=float(expelled_frac),
        slag_expelled_kg=float(slag_expelled),
        scale_loss_kg=float(scale_loss),
        crack_loss_kg=float(crack_loss),
        wrought_iron_kg=float(wrought),
        soundness=float(soundness),
        final_purity=float(final_purity),
        consolidation_ratio=float(wrought / bloom_iron_kg) if bloom_iron_kg > 0 else 0.0)


@dataclass(frozen=True)
class ForgeCue:
    """A truthful bloom-consolidation affordance at one chunk.

    What an agent *could* discover by reheating the spongy bloom obtainable here (C17) in
    the same forced-draught hearth (C12) and hammering it: a dense billet of wrought iron
    forms as the fayalite slag gushes out — unless the bloom is red-short (pyrite), in which
    case it cracks. It is NOT handed to the agent as "hammer the oxide bloom at 1200 °C" —
    the agent must learn the heat+hammer→billet correlation by acting. The per-kg-ore
    figures are the ground truth the world commits to; emitted iff C17 yields a bloom cue
    here (a refractory furnace ≥1200 °C over an iron-bearing gossan)."""
    coord: Tuple[int, int, int]
    biome: int
    iron_mineral: str              # ground-truth iron ore (C17/C1 gossan tell)
    ore_class: str                 # "oxide_iron" | "sulfide_iron"
    red_short: bool                # pyrite-derived bloom — cracks under the hammer
    forge_temp_c: float            # the forge heat (= C12 forced_peak_c; keeps slag molten)
    hot_enough: bool               # forge_temp_c >= slag-expulsion heat (True if cue exists)
    melted: bool                   # ALWAYS False — solid-state welding, never cast
    is_wrought: bool               # the consolidated billet is sound (oxide) — not for red-short
    cracked: bool                  # red-short → fissured (the lie made visible)
    n_heats: int                   # reheat+hammer cycles the cue reports (DEFAULT_HEATS)
    bloom_iron_per_kg_ore: float   # iron in the achievable bloom (C17, direct or roasted)
    wrought_iron_per_kg_ore: float  # consolidated wrought iron after forging (per kg ore)
    slag_expelled_per_kg_ore: float  # entrapped slag squeezed out (per kg ore)
    scale_loss_per_kg_ore: float   # iron lost to fire scale (per kg ore)
    crack_loss_per_kg_ore: float   # iron lost to red-short cracking (per kg ore)
    soundness: float               # billet soundness [0,1]
    final_purity: float            # Fe fraction of the billet [0,1]
    consolidation_ratio: float     # wrought / bloom iron [0,1]
    confidence: float              # reliability of achieving the outcome [0,1]


# ---------------------------------------------------------------------------
# Core derivation — forge outcome from a C17 bloom cue.
# ---------------------------------------------------------------------------

def _achievable_bloom_iron(bloom_cue) -> float:
    """The iron in the bloom a site can ultimately give (direct, or after a roast for a
    sulfide) — mirrors ``ib._achievable_yield`` so C19 forges what C17 can actually make."""
    return max(float(getattr(bloom_cue, "bloom_iron_per_kg_ore", 0.0)),
               float(getattr(bloom_cue, "bloom_iron_per_kg_ore_roasted", 0.0)))


def _cue_from_bloom(coord, bloom_cue, *, n_heats: int = DEFAULT_HEATS
                    ) -> Optional[ForgeCue]:
    """Pure derivation (no ``sim`` — trivially unit-testable, like its siblings).
    Emits a cue iff C17 yields a bloom here. The cue tells the truth: an oxide bloom
    consolidates to sound wrought iron; a red-short (pyrite) bloom cracks and yields little.
    Forged 'per kg ore' so it composes directly onto C17's per-kg-ore bloom figures."""
    if bloom_cue is None:
        return None
    bloom_iron = _achievable_bloom_iron(bloom_cue)
    if bloom_iron <= 0.0:
        return None
    red_short = bool(getattr(bloom_cue, "red_short", False))
    purity = float(getattr(bloom_cue, "bloom_purity", 0.0))
    peak = float(getattr(bloom_cue, "forced_peak_c", 0.0))
    y = wrought_yield(bloom_iron, purity, red_short, peak, n_heats=n_heats)

    conf = float(getattr(bloom_cue, "confidence", 0.0))
    # surer when the billet is sound; a cracking red-short site is a less reliable win.
    confidence = float(min(1.0, conf * (0.5 + 0.5 * y.soundness)))

    return ForgeCue(
        coord=tuple(int(c) for c in coord),
        biome=int(getattr(bloom_cue, "biome", 0)),
        iron_mineral=str(getattr(bloom_cue, "iron_mineral", "")),
        ore_class=str(getattr(bloom_cue, "ore_class", "")),
        red_short=red_short,
        forge_temp_c=float(round(peak, 1)),
        hot_enough=bool(y.hot_enough),
        melted=False,
        is_wrought=bool(y.is_wrought),
        cracked=bool(y.cracked),
        n_heats=int(n_heats),
        bloom_iron_per_kg_ore=float(round(bloom_iron, 6)),
        wrought_iron_per_kg_ore=float(round(y.wrought_iron_kg, 6)),
        slag_expelled_per_kg_ore=float(round(y.slag_expelled_kg, 6)),
        scale_loss_per_kg_ore=float(round(y.scale_loss_kg, 6)),
        crack_loss_per_kg_ore=float(round(y.crack_loss_kg, 6)),
        soundness=float(round(y.soundness, 4)),
        final_purity=float(round(y.final_purity, 4)),
        consolidation_ratio=float(round(y.consolidation_ratio, 4)),
        confidence=float(round(confidence, 4)))


@dataclass(frozen=True)
class WroughtResult:
    """The realized outcome of an actual ``consolidate_bloom`` — the iron **forgé
    effectif**. The (agent-held) bloom has been hammer-consolidated; this is the wrought
    billet that was *gotten*. NON-MUTATING of the world (no geology touched — D10 frozen):
    a transformation of a product already obtained from C17 ``bloom_at``. The world never
    lies: the figures equal ``wrought_yield`` for the bloom's iron + purity + class."""
    iron_mineral: str
    ore_class: str
    bloom_iron_kg: float           # the metallic iron in the raw bloom that went in
    wrought_iron_kg: float         # the consolidated wrought iron recovered
    slag_expelled_kg: float        # entrapped fayalite slag squeezed out
    scale_loss_kg: float           # iron lost to fire scale (FeO)
    crack_loss_kg: float           # iron lost to red-short cracking (0 if sound)
    soundness: float               # billet soundness [0,1]
    final_purity: float            # Fe fraction of the billet [0,1]
    is_wrought: bool               # sound, usable wrought iron
    cracked: bool                  # red-short fissuring occurred
    red_short: bool                # the bloom was sulfur-embrittled
    melted: bool                   # ALWAYS False — solid-state, never cast
    n_heats: int                   # reheat+hammer cycles applied
    forge_temp_c: float            # the hearth heat the consolidation ran at


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_bloom_forging(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim`` and ensures the
    composed capability (C17 iron bloomery, itself C12×C1) is installed. Adds **zero**
    per-tick cost: the oracle is derived on query and memoised. Returns the cache dict
    (``sim._forge_cue_cache``)."""
    ib.install_iron_bloomery(sim)
    cache = getattr(sim, "_forge_cue_cache", None)
    if cache is None:
        cache = {}
        sim._forge_cue_cache = cache
    return cache


def forge_cue_for_chunk(sim, coord: Tuple[int, int, int], *,
                        n_heats: int = DEFAULT_HEATS) -> Optional[ForgeCue]:
    """Truthful bloom-consolidation affordance at ``coord`` (or None). Memoised at the
    default heat count.

    Invariant: if this returns a cue, C17 ``bloom_cue_for_chunk(sim, coord)`` yields an
    iron-bearing bloom here whose ``iron_mineral`` equals this cue's; ``cracked`` is True
    iff that bloom is ``red_short`` (pyrite). No bloom here ⇒ None."""
    coord = tuple(int(c) for c in coord)
    cache = install_bloom_forging(sim)
    key = (coord, int(n_heats))
    if key in cache:
        return cache[key]
    bloom = ib.bloom_cue_for_chunk(sim, coord)
    cue = _cue_from_bloom(coord, bloom, n_heats=n_heats)
    cache[key] = cue
    return cue


def prospect_forge(sim, world_x: float, world_y: float, *,
                   n_heats: int = DEFAULT_HEATS) -> Optional[ForgeCue]:
    """What an agent standing at world ``(x, y)`` could discover about forging the bloom
    obtainable here. Returns the cue (wrought yield + truthful outcome) or None when no
    bloom is winnable underfoot (no refractory furnace ≥1200 °C, or no iron-bearing gossan)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return forge_cue_for_chunk(sim, coord, n_heats=n_heats)


def forge_preview(sim, world_x: float, world_y: float, *,
                  n_heats: int = DEFAULT_HEATS) -> Dict[str, object]:
    """**Non-mutating** preview of what consolidating the bloom at ``(x, y)`` yields — the
    ground-truthed outcome the perception cue must agree with.

    Touches NOTHING (no ore mined, no geology mutated — unlike C17 ``bloom_at``): the truth
    oracle of the FORGE verb, not the act. Always returns a dict (even when nothing is
    forgeable), naming the *why not* — including the smith's lie: a **pyrite** bloom reports
    ``cracked=True`` with a collapsed ``wrought_iron_per_kg_ore`` (red-short)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = forge_cue_for_chunk(sim, coord, n_heats=n_heats)
    if cue is None:
        # Recompute the diagnostic to name the missing ingredient (no bloom here).
        return {"forgeable": False,
                "reason": "no iron bloom winnable here (no refractory furnace >=1200 C, "
                          "or no iron-bearing gossan)",
                "is_wrought": False, "cracked": False}
    return {"forgeable": True, "reason": "ok",
            "iron_mineral": cue.iron_mineral, "ore_class": cue.ore_class,
            "red_short": cue.red_short, "cracked": cue.cracked,
            "is_wrought": cue.is_wrought, "melted": cue.melted,
            "forge_temp_c": cue.forge_temp_c, "n_heats": cue.n_heats,
            "bloom_iron_per_kg_ore": cue.bloom_iron_per_kg_ore,
            "wrought_iron_per_kg_ore": cue.wrought_iron_per_kg_ore,
            "slag_expelled_per_kg_ore": cue.slag_expelled_per_kg_ore,
            "scale_loss_per_kg_ore": cue.scale_loss_per_kg_ore,
            "crack_loss_per_kg_ore": cue.crack_loss_per_kg_ore,
            "soundness": cue.soundness, "final_purity": cue.final_purity,
            "consolidation_ratio": cue.consolidation_ratio,
            "confidence": cue.confidence, "biome": cue.biome}


def consolidate_bloom(bloom_result, *, n_heats: int = DEFAULT_HEATS,
                      forge_temp_c: Optional[float] = None) -> WroughtResult:
    """**The forge effective** — hammer-consolidate an agent-held bloom into wrought iron.

    Takes a C17 ``ib.BloomResult`` (or any object carrying ``bloom_iron_kg``,
    ``bloom_purity``, ``red_short``, ``peak_c``, ``iron_mineral``, ``ore_class``) and
    returns a ``WroughtResult``. **NON-MUTATING of the world** (no ``sim``, no geology —
    D10 frozen): it transforms a product already obtained, like C8 tempering / C9 firing.
    The forge heat defaults to the bloom's own ``peak_c`` (the same forced-draught hearth);
    pass ``forge_temp_c`` to override.

    The world never lies: the figures equal ``wrought_yield`` for the bloom's iron, purity
    and class. A **red-short** bloom returns ``cracked`` True with a collapsed
    ``wrought_iron_kg`` (hot-shortness) — the honest, costly lesson that the rusty hat hid a
    sulfide whose iron will not forge sound. ``melted`` is always False (solid-state)."""
    bloom_iron = float(getattr(bloom_result, "bloom_iron_kg", 0.0))
    purity = float(getattr(bloom_result, "bloom_purity", 0.0))
    red_short = bool(getattr(bloom_result, "red_short", False))
    peak = float(forge_temp_c if forge_temp_c is not None
                 else getattr(bloom_result, "peak_c", 0.0))
    y = wrought_yield(bloom_iron, purity, red_short, peak, n_heats=n_heats)
    return WroughtResult(
        iron_mineral=str(getattr(bloom_result, "iron_mineral", "")),
        ore_class=str(getattr(bloom_result, "ore_class", "")),
        bloom_iron_kg=float(round(bloom_iron, 6)),
        wrought_iron_kg=float(round(y.wrought_iron_kg, 6)),
        slag_expelled_kg=float(round(y.slag_expelled_kg, 6)),
        scale_loss_kg=float(round(y.scale_loss_kg, 6)),
        crack_loss_kg=float(round(y.crack_loss_kg, 6)),
        soundness=float(round(y.soundness, 4)),
        final_purity=float(round(y.final_purity, 4)),
        is_wrought=bool(y.is_wrought), cracked=bool(y.cracked),
        red_short=bool(red_short), melted=False,
        n_heats=int(n_heats), forge_temp_c=float(round(peak, 1)))


def discover_forge_sites_by_sight(sim, rows: List[int],
                                  perception_radius_m: float = 64.0,
                                  *, n_heats: int = DEFAULT_HEATS
                                  ) -> Dict[int, List[ForgeCue]]:
    """For each agent ``row``, the bloom-forgeable sites perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    Turns the static substrate (a refractory hearth + an iron gossan → a bloom) into a
    **perceivable, actionable** consolidation signal — the agent then *chooses* to forge.
    Deterministic order (by chunk distance, then coord)."""
    out: Dict[int, List[ForgeCue]] = {}
    if not rows:
        return out
    install_bloom_forging(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], ForgeCue]] = []
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
                cue = forge_cue_for_chunk(sim, coord, n_heats=n_heats)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_forge_site_near(sim, row: int, perception_radius_m: float = 128.0,
                         *, n_heats: int = DEFAULT_HEATS,
                         require_sound: bool = False) -> Optional[ForgeCue]:
    """The most rewarding bloom-forgeable site an agent at ``row`` can perceive — the
    actionable pick (most wrought iron per kg ore; tie-break higher soundness, then
    confidence, then nearest then coord).

    This is where the oxide-vs-red-short inversion teaches at the anvil: preferring the
    wrought iron actually gotten *and sound*, the agent learns to forge the oxide bloom and
    to distrust the pyrite bloom (which cracks). ``require_sound`` rejects the cracking
    red-short sites. Returns None when nothing forgeable is in sight."""
    cues = discover_forge_sites_by_sight(sim, [int(row)], perception_radius_m,
                                         n_heats=n_heats).get(int(row), [])
    pool = cues
    if require_sound:
        pool = [c for c in pool if c.is_wrought and not c.cracked]
    if not pool:
        return None
    # already distance-sorted; prefer the most wrought iron, then soundest, then surest.
    return max(pool, key=lambda c: (c.wrought_iron_per_kg_ore, c.soundness, c.confidence))


def forge_summary(sim, *, n_heats: int = DEFAULT_HEATS) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the dashboard /
    smoke journal. Read-only; computes cues lazily."""
    install_bloom_forging(sim)
    by_class: Dict[str, int] = {}
    by_mineral: Dict[str, int] = {}
    n_chunks = 0
    n_sites = 0
    n_sound = 0
    n_cracked = 0
    best_wrought = 0.0
    best_soundness = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = forge_cue_for_chunk(sim, coord, n_heats=n_heats)
        if cue is None:
            continue
        n_sites += 1
        if cue.is_wrought:
            n_sound += 1
        if cue.cracked:
            n_cracked += 1
        by_class[cue.ore_class] = by_class.get(cue.ore_class, 0) + 1
        by_mineral[cue.iron_mineral] = by_mineral.get(cue.iron_mineral, 0) + 1
        best_wrought = max(best_wrought, cue.wrought_iron_per_kg_ore)
        best_soundness = max(best_soundness, cue.soundness)
    return {
        "n_chunks": n_chunks,
        "n_forge_sites": n_sites,
        "forge_rate": round(n_sites / n_chunks, 4) if n_chunks else 0.0,
        "n_sound_wrought": n_sound,
        "n_cracked_red_short": n_cracked,
        "best_wrought_iron_per_kg_ore": round(best_wrought, 6),
        "best_soundness": round(best_soundness, 4),
        "by_ore_class": dict(sorted(by_class.items())),
        "by_mineral": dict(sorted(by_mineral.items())),
    }


__all__ = [
    "WroughtYield", "ForgeCue", "WroughtResult",
    "install_bloom_forging", "forge_cue_for_chunk", "prospect_forge",
    "forge_preview", "consolidate_bloom", "discover_forge_sites_by_sight",
    "best_forge_site_near", "forge_summary", "wrought_yield",
    "SLAG_EXPULSION_TEMP_C", "IRON_MELT_TEMP_C", "DEFAULT_HEATS",
    "EXPEL_PER_HEAT", "SCALE_LOSS_PER_HEAT", "CONSOLIDATION_PER_HEAT",
    "RAW_SLAG_PER_IRON", "RED_SHORT_CRACK_LOSS", "RED_SHORT_SOUNDNESS_CEIL",
    "SOUND_THRESHOLD", "WROUGHT_PURITY_CEIL", "RED_SHORT_PURITY_CEIL",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
