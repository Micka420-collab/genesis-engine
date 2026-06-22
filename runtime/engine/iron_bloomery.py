"""Genesis Engine — Substrate capability : le bas-fourneau du fer (Cap. C17).

**La 5ᵉ capacité de TRANSFORMATION et la 2ᵉ MÉTALLURGIQUE** (après C13
``copper_smelting``) — le **seuil de l'âge du fer**. C12 ``forced_draught`` a porté
un four soufflé au charbon **au-delà de 1200 °C** (régime du bas-fourneau) et exposé
``reaches_iron_bloomery_temp`` comme un **potentiel ground-truthé** — en différant
explicitement *« le bas-fourneau du fer (paroi réfractaire requise, atmosphère
réductrice CO) »* à une capacité future. C17 la **réalise** : elle **consomme**
réellement le minerai (mutation géologique via ``geo.mine_at``) et **rend** une
**loupe de fer** (bloom) spongieuse + de la scorie de fayalite, exactement comme le
monde s'y était engagé. C'est la **2ᵉ mutation** de l'arc C1→C17 après ``smelt_at``
(C13) — d'où l'ouverture de ``crates/MUTATION-FRONTIER.md`` (reco ``R-J9-2`` /
``R-J9r2-2``).

**Règle d'émergence absolue** (cf. ``surface_mineralization`` (C1) …
``copper_smelting`` (C13)) : rien n'est scripté. Un agent ne *sait* pas qu'« on
réduit la roche rouille dans un four soufflé pour en tirer le fer ». Il **VOIT** le
chapeau de fer rouille (C1, gossan), il **SAIT faire** un four à tirage forcé à paroi
réfractaire (C12) — et en y entassant la roche rouge avec son charbon, il **découvre**
qu'une **éponge** de métal gris se forme au fond, qu'il faut **marteler** pour en
chasser la scorie. Ce module n'expose qu'un **signal physique véridique** : *ce
minerai-ci, réduit dans le four atteignable ici, rendrait tant de fer, de telle
qualité, avec tant de scorie — et le ferait directement (oxyde), ou seulement après
l'avoir grillé (sulfure), ou pas du tout (galène/sphalérite : ce n'est pas du fer)*.
La tuyère, le martelage de consolidation (forge), le cinglage — toute la chaîne
opératoire reste **émergente**.

Le mensonge rendu visible #8 — le chapeau de fer ment (gossan polyminéral)
-------------------------------------------------------------------------
C13 a montré l'inversion **binaire** sur le tell vert (cuivre natif facile vs
chalcopyrite sulfurée). C17 la prolonge en une inversion **à cinq voies** sur **un
seul tell** : le **chapeau de fer** (gossan, « tache rouille brune ») que C1 expose
**identiquement** coiffe (veille 2026-06-22 ; les gossans étaient des guides de
prospection *ambigus*) :

* **hématite** (``Fe₂O₃``, oxyde) & **magnétite** (``Fe₃O₄``, oxyde) — les **vrais**
  minerais de fer. Réduction directe par le CO → loupe de fer **saine**. Le prix.
* **pyrite** (``FeS₂``, « or des fous », sulfure) — riche en fer (47 %) mais le
  **soufre est quasi impossible à chasser** au bas-fourneau → loupe **cassante à
  chaud** (*red-short*). Historiquement un **mauvais** minerai de fer pour exactement
  cette raison. Il faut d'abord la **griller** (oxydation, qui chasse le SO₂) — et même
  alors le fer reste fragilisé. ``red_short=True``.
* **galène** (``PbS`` → **plomb**) & **sphalérite** (``ZnS`` → **zinc**) — **aucun
  fer**. Le même chapeau rouille coiffe un sulfure de plomb / de zinc : réduit, il ne
  rend **pas de fer du tout**. Le mensonge le plus profond du gossan.

``best_bloomery_site_near`` enseigne donc : réduis le chapeau **oxyde** (hématite,
magnétite), méfie-toi du chapeau **pyriteux** (grille-le, et tolère sa fragilité),
fuis le chapeau qui coiffe du plomb/zinc. Le monde ne ment pas : ``bloom_at`` sur un
gossan non ferreux **consomme** la charge et ne rend **que de la scorie**
(``bloom_iron_kg == 0``) — la leçon coûteuse, physiquement vraie, du chapeau de fer.

Le MENSONGE PHYSIQUE — le fer ne FOND jamais (vs le cuivre qui coule)
---------------------------------------------------------------------
La différence métallurgique fondamentale entre C13 (cuivre) et C17 (fer), et la
raison pour laquelle l'âge du fer arrive **bien après** l'âge du cuivre malgré un
minerai bien **plus abondant** :

* Le **cuivre** FOND à 1085 °C : dans un four soufflé il **coule** en un bouton
  liquide qui décante sous la scorie, qu'on **verse** (C13).
* Le **fer** fond à **1538 °C** — une température **hors d'atteinte** de tout
  bas-fourneau (≤ ~1400 °C, plafond de paroi réfractaire C12). Le fer est donc réduit
  **à l'état SOLIDE** : le CO diffuse à travers l'oxyde chaud (réduction
  solide-solide, ~1100–1300 °C, veille 2026-06-22) et laisse une **éponge** (loupe)
  de fer métallique **imprégnée de scorie de fayalite** (``Fe₂SiO₄``, liquide
  ~1150–1200 °C, qui s'écoule). La loupe **n'est pas coulable** : elle doit être
  **martelée** à chaud pour en expulser la scorie et la consolider en fer forgé. Un
  agent qui s'attend au bouton coulé du cuivre obtient une éponge récalcitrante : la
  **forge** (le martelage) devient nécessaire et **émerge** de là.

Donc, invariablement : ``melts == False``, ``is_solid_bloom == True``,
``requires_forging == True``. La fonte (fer liquide → fonte/cast iron, haut-fourneau)
est différée **honnêtement** (``furnace_reaches_iron_melt`` toujours False ici), comme
C9→C12 différaient vers le four puis le tirage forcé.

N'introduit AUCUN nouveau « tell » minéral — il COMPOSE (garde-fou D8)
---------------------------------------------------------------------
Comme C7→C13, ce module **ne surface aucune nouvelle matière**, n'a **pas** de table
``_PROFILE`` et **ne crée aucune entrée** ``PY_TO_RUST`` / ``PY_CATALOGUE_ONLY`` (cf.
``test_geology_cross_language_contract``). C'est la **11ᵉ** capacité D8-par-
composition. Il *lit* deux capacités déjà classées cross-langage :

* le **four** assez chaud — l'apparatus de C12 ``forced_draught``
  (``forced_cue_for_chunk`` : ``forced_peak_c``, ``reaches_iron_bloomery_temp``,
  ``wall_refractory``) ;
* le **minerai de fer** — le tell de surface de C1 ``surface_mineralization`` (le
  **chapeau de fer** gossan : ``hematite`` / ``magnetite`` / ``pyrite`` — et la
  négation visible ``galena`` / ``sphalerite``).

Et il **réutilise verbatim** le seuil du régime bas-fourneau ``fd.IRON_BLOOMERY_TEMP_C``
(C12) et, comme SSOT métallurgique, le **rendement par élément** du catalogue minéral
(``Mineral.yields_per_kg_ore["Fe"]``, ``Mineral.category``) — aucune teneur n'est
re-déclarée ici. Le fichier est volontairement **hors du glob** ``*_outcrop.py`` : ce
n'est pas un affleurement, c'est une transformation. Décision asservie par
``test_introduces_no_new_tell``.

Physique de la réduction — la veille 2026-06-22 (archéométrie du bas-fourneau)
------------------------------------------------------------------------------
La réduction est **gouvernée par la thermo + la minéralogie**, jamais arbitraire
(méta-règle du substrat). Trois quantités se rencontrent :

1. **Pointe du four** (``fd.forced_peak_c``, réemploi C12). Doit franchir
   ``fd.IRON_BLOOMERY_TEMP_C`` = 1200 °C (régime de réduction solide + scorie de
   fayalite liquide ~1150–1200 °C, qui s'écoule de l'éponge ; veille npj Heritage
   Science 2024). Atteignable **uniquement** derrière une paroi réfractaire (C12).
2. **Classe du minerai** (``Mineral.category`` + présence de Fe au catalogue) →
   oxyde (réduction directe, fer sain) / sulfure ferreux (griller d'abord, fer
   *red-short*) / non ferreux (aucun fer).
3. **Teneur en fer** (``yields_per_kg_ore["Fe"]``, catalogue) : hématite 0,70 ;
   magnétite 0,72 ; pyrite 0,47. Le bas-fourneau **ne récupère jamais tout** le fer :
   une part importante part dans la **fayalite** de la scorie (veille : la scorie de
   bas-fourneau EST de la fayalite riche en Fe) — d'où des plafonds de rendement
   honnêtes sous 1,0, montant avec la surchauffe (un bain plus chaud sépare mieux la
   loupe de la scorie liquide).

Déterminisme
------------
L'oracle est pur : composition de ``forced_cue_for_chunk`` (C12) + ``surface_cue_for_chunk``
(C1) — eux-mêmes ``prf_rng`` / dérivés du seed — avec des SSOT pures (seuil C12,
catalogue minéral). Aucun RNG nouveau. Bit-identique entre deux runs de même seed.
(``bloom_at`` mute volontairement la géologie — ce n'est pas l'oracle ; c'est l'acte.)

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — la réduction est une
lecture/transformation dérivée du substrat (four + minerai), comme C1→C13.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape (chunk → issue de
transformation), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from engine.world import CHUNK_SIDE_M, world_to_chunk
from engine.mineral_catalog import MINERAL_BY_NAME, MineralCategory
# Single sources of truth — reused verbatim, never re-modelled (garde-fou D8).
import engine.forced_draught as fd          # C12 — the hot-enough furnace + iron-bloomery threshold
import engine.surface_mineralization as sm  # C1 — the rusty gossan iron-hat surface tell (dig depth)
import engine.geology as geo                # the ore-extraction SSOT (mine_at)

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# --- The iron melting point (°C). Pure iron melts at 1538 °C — far ABOVE any bloomery
# (capped ~1400 °C by the refractory wall, C12). The bloomery therefore reduces iron in
# the SOLID STATE: the product is a spongy bloom, never a molten pour. Modelled so the
# world can state the honest deferral (cast iron / blast furnace lies beyond this).
IRON_MELT_TEMP_C = 1538.0

# --- Roasting threshold (°C). A sulfide iron ore (pyrite FeS2) must be roasted to drive
# off SO2 (FeS2 + O2 -> Fe2O3 + SO2) before it can be reduced. A bare open fire (C7/C9,
# 600-850 °C) already clears this. But even roasted, residual sulfur embrittles the iron
# (red-short) — pyrite is a notoriously poor iron ore (veille 2026-06-22). The roast is
# *easy*; knowing it is needed — and that the iron stays brittle — is the discovery.
ROAST_TEMP_C = 590.0

# --- Recovery model (°C / dimensionless). A bloomery never recovers ALL the contained
# iron: a large fraction is locked into the fayalite (Fe2SiO4) slag (veille: bloomery
# slag IS iron-rich fayalite). Each ore class has an honest base recovery and a ceiling
# < 1.0; a hotter bath separates the solid bloom from the liquid slag better, so
# recovery rises with superheat above the bloomery threshold, saturating over a span.
SUPERHEAT_SPAN_C = 200.0   # °C above the bloomery threshold for the full superheat bonus
SUPERHEAT_GAIN = 0.12      # extra recovery a hotter, better-separated bloom wins

# Oxide iron (hematite Fe2O3, magnetite Fe3O4) — the real ore. Direct CO reduction to a
# SOUND solid bloom; no roast. Lossy (slag keeps much Fe) but the iron is good.
OXIDE_BASE_RECOVERY = 0.50
OXIDE_RECOVERY_CEIL = 0.65
OXIDE_BLOOM_PURITY = 0.96      # wrought iron after forging is nearly pure Fe

# Sulfide iron (pyrite FeS2) — roast then reduce: the iron is RED-SHORT (sulfur
# embrittles it). Reachable only AFTER a roast (else recovery 0); lower recovery, lower
# usable purity. The lie: a rich iron tell that gives brittle, near-useless iron.
SULFIDE_BASE_RECOVERY = 0.28
SULFIDE_RECOVERY_CEIL = 0.40
SULFIDE_BLOOM_PURITY = 0.80    # sulfur-contaminated, brittle bloom

# Default ore charge (kg) a single bloomery run consumes from the column (mirrors mine_at).
DEFAULT_CHARGE_KG = 5.0

# The C1 surface expression group whose minerals carry the iron tell (the rusty gossan
# "iron hat"). Reused, not re-listed — these ARE the minerals C1's gossan cue surfaces.
_GOSSAN_GROUP = "gossan"


@dataclass(frozen=True)
class BloomYield:
    """Ground-truth metallurgical outcome of reducing ``ore_kg`` of one gossan ore in a
    bloomery whose peak is ``peak_c`` (optionally pre-roasted). Pure SSOT — no rounding,
    no I/O, trivially unit-testable. ``bloom_at`` and the cue both derive from this.

    ``melts`` is **always False**: the iron is reduced in the solid state (the furnace
    never reaches iron's 1538 °C melt point) — the bloom is a sponge, not a pour."""
    ore_class: str                 # "oxide_iron" | "sulfide_iron" | "non_iron"
    requires_roasting: bool        # a sulfide must be roasted first (else recovery 0)
    red_short: bool                # sulfide-derived iron is sulfur-embrittled (brittle hot)
    contained_fe_fraction: float   # catalogue Fe yield per kg of this ore
    contained_fe_kg: float         # ore_kg * contained_fe_fraction (the iron *in* the ore)
    hot_enough: bool               # peak_c >= the bloomery threshold (C12 SSOT)
    melts: bool                    # ALWAYS False — iron melts at 1538 °C, out of reach
    reduction_efficiency: float    # fraction of contained Fe actually won into the bloom [0,1)
    bloom_iron_kg: float           # the solid iron bloom this run yields (kg)
    slag_kg: float                 # fayalite slag + gangue + Fe lost to slag
    bloom_purity: float            # Fe mass fraction of the consolidated bloom (0 if none)


# ---------------------------------------------------------------------------
# Single source of truth — the bloomery reduction physics the world commits to.
# ---------------------------------------------------------------------------

def _ore_class_params(category: MineralCategory, contained_fe: float
                      ) -> Tuple[str, bool, bool, float, float, float]:
    """(ore_class, requires_roasting, red_short, base_recovery, recovery_ceiling,
    bloom_purity) for a gossan ore. Keyed on the catalogue ``MineralCategory`` + whether
    it carries iron (SSOT — no ore-name duplication): an OXIDE iron ore reduces directly
    to sound iron; a SULFIDE iron ore (pyrite) must be roasted and stays red-short; a
    gossan with no iron (galena -> lead, sphalerite -> zinc) yields no iron at all."""
    if contained_fe <= 0.0:
        return ("non_iron", False, False, 0.0, 0.0, 0.0)
    if category == MineralCategory.OXIDE:
        return ("oxide_iron", False, False, OXIDE_BASE_RECOVERY,
                OXIDE_RECOVERY_CEIL, OXIDE_BLOOM_PURITY)
    if category == MineralCategory.SULFIDE:
        return ("sulfide_iron", True, True, SULFIDE_BASE_RECOVERY,
                SULFIDE_RECOVERY_CEIL, SULFIDE_BLOOM_PURITY)
    # Any other Fe-bearing host (e.g. an Fe-rich silicate rock) — treat as a poor,
    # directly-reducible oxide-like source (no roast, no embrittlement, low yield).
    return ("oxide_iron", False, False, OXIDE_BASE_RECOVERY * 0.5,
            OXIDE_RECOVERY_CEIL * 0.5, OXIDE_BLOOM_PURITY)


def iron_bloom_yield(ore_mineral: Optional[str], ore_kg: float, peak_c: float,
                     *, roasted: bool = False) -> BloomYield:
    """Deterministic SSOT for the solid iron bloom a bloomery run yields.

    ``ore_mineral`` is a catalogue name (C1 surfaces ``hematite`` / ``magnetite`` /
    ``pyrite`` — and ``galena`` / ``sphalerite`` — under the one rusty gossan tell). The
    contained-iron fraction and the ore class come straight from the mineral catalogue —
    never re-declared here. The furnace must reach the bloomery threshold
    (``fd.IRON_BLOOMERY_TEMP_C``, reused from C12). A **sulfide** (pyrite) yields
    **nothing** unless ``roasted`` first, and even then the bloom is **red-short**
    (``red_short`` True, lower usable purity). A **non-iron** gossan (galena, sphalerite)
    yields **no iron** at all (the deepest lie of the iron hat). Recovery rises with
    superheat above the threshold and saturates below an honest ceiling < 1.0 (the
    fayalite slag always keeps iron). ``melts`` is **always False** — the iron is reduced
    solid (1538 °C melt point is unreachable). Any module that *actually reduces* iron
    MUST read this, so the world never lies about what a bloomery yields."""
    m = MINERAL_BY_NAME.get(ore_mineral) if ore_mineral else None
    ore_kg = max(0.0, float(ore_kg))
    _barren = BloomYield(
        ore_class="non_iron", requires_roasting=False, red_short=False,
        contained_fe_fraction=0.0, contained_fe_kg=0.0, hot_enough=False,
        melts=False, reduction_efficiency=0.0, bloom_iron_kg=0.0,
        slag_kg=ore_kg, bloom_purity=0.0)
    if m is None:
        return _barren
    contained_fraction = float(m.yields_per_kg_ore.get("Fe", 0.0))
    ore_class, requires_roasting, red_short, base, ceil, purity = _ore_class_params(
        m.category, contained_fraction)
    if ore_class == "non_iron":             # a gossan with no iron (lead/zinc ore)
        return _barren
    contained = ore_kg * contained_fraction
    hot = peak_c >= fd.IRON_BLOOMERY_TEMP_C
    superheat = min(1.0, max(0.0, (peak_c - fd.IRON_BLOOMERY_TEMP_C) / SUPERHEAT_SPAN_C))
    if not hot:
        eff = 0.0                            # furnace too cold — no reduction, no bloom
    elif requires_roasting and not roasted:
        eff = 0.0                            # un-roasted sulfide: SO2 locks the iron in slag
    else:
        eff = min(ceil, base + SUPERHEAT_GAIN * superheat)
    bloom = contained * eff
    slag = max(0.0, ore_kg - bloom)
    bloom_purity = purity if bloom > 0.0 else 0.0
    return BloomYield(
        ore_class=ore_class, requires_roasting=requires_roasting, red_short=red_short,
        contained_fe_fraction=contained_fraction, contained_fe_kg=contained,
        hot_enough=hot, melts=False, reduction_efficiency=eff,
        bloom_iron_kg=bloom, slag_kg=slag, bloom_purity=bloom_purity)


@dataclass(frozen=True)
class BloomCue:
    """A truthful iron-bloomery affordance at one chunk.

    What an agent *could* discover by feeding the rusty gossan stone C1 shows into the
    refractory forced-draught furnace C12 builds: a spongy bloom of grey iron forms (it
    never melts; it must be hammered). It is NOT handed to the agent as "reduce hematite
    at 1200 °C" — the agent must learn the heat+ore->bloom correlation by acting.
    ``bloom_iron_per_kg_ore`` (directly) and ``bloom_iron_per_kg_ore_roasted`` (after a
    roast) are the ground truth the world commits to: ``bloom_at`` yields *exactly* this.
    Emitted iff C12 says ``reaches_iron_bloomery_temp`` AND C1 surfaces an **iron-bearing**
    gossan here (hematite/magnetite/pyrite). A lead/zinc gossan yields no cue (no iron)."""
    coord: Tuple[int, int, int]
    biome: int
    # the ore (C1 gossan ground truth) and its metallurgy (catalogue SSOT)
    iron_mineral: str              # ground-truth iron ore C1 surfaces (rusty gossan tell)
    ore_class: str                 # "oxide_iron" | "sulfide_iron"
    requires_roasting: bool        # a sulfide (pyrite) — roast (≈590 °C) before reducing
    red_short: bool                # pyrite-derived iron is sulfur-embrittled (brittle)
    contained_fe_fraction: float   # catalogue Fe per kg ore (hematite 0.70, pyrite 0.47)
    # the furnace (C12 ground truth)
    forced_peak_c: float           # the forced-draught furnace peak (C12 SSOT)
    wall_refractory: bool          # C12: refractory kaolin wall — required to reach 1200 °C
    reaches_bloomery_temp: bool    # forced_peak >= bloomery threshold (always True if cue exists)
    # the iron is solid — never molten (the deep lie vs copper C13)
    is_solid_bloom: bool           # ALWAYS True — reduced solid, a sponge not a pour
    requires_forging: bool         # ALWAYS True — the bloom must be hammer-consolidated
    furnace_reaches_iron_melt: bool  # peak >= 1538 °C — ALWAYS False (cast iron deferred)
    # the bloom outcome (SSOT, per kg of iron-ore charged)
    reducible_now: bool            # directly yields a bloom here (oxide, hot enough)
    needs_roasting_first: bool     # sulfide & not yet roasted — the lie made visible
    reduction_efficiency: float    # direct (un-roasted) recovery fraction [0,1)
    bloom_iron_per_kg_ore: float          # iron won NOW (0 for an un-roasted sulfide)
    bloom_iron_per_kg_ore_roasted: float  # iron won after a roast (the potential)
    slag_per_kg_ore: float         # fayalite slag (direct path) per kg ore
    bloom_purity: float            # Fe fraction of the bloom on the achievable path
    roast_temp_c: float            # the roast temperature a sulfide needs first
    dig_depth_m: float             # C1 depth to reach the ore (used by bloom_at)
    confidence: float              # reliability of achieving the outcome [0,1]


# ---------------------------------------------------------------------------
# Core derivation — bloom outcome from a C12 forced cue + a C1 gossan cue.
# ---------------------------------------------------------------------------

def _cue_from_inputs(coord, forced_cue, gossan_cue) -> Optional[BloomCue]:
    """Pure derivation (no ``sim`` — trivially unit-testable, like its siblings).
    Emits a cue iff the forced furnace here reaches the bloomery regime (≥1200 °C —
    refractory wall, C12) AND C1's gossan tell here caps an **iron-bearing** ore
    (hematite/magnetite/pyrite). The 1+1>2 gate: a cool furnace, or a gossan that
    caps lead/zinc (no iron), ⇒ no bloomery affordance."""
    if forced_cue is None or not getattr(forced_cue, "reaches_iron_bloomery_temp", False):
        return None
    if gossan_cue is None or getattr(gossan_cue, "group", None) != _GOSSAN_GROUP:
        return None
    ore = getattr(gossan_cue, "mineral", None)
    if ore is None:
        return None
    peak = float(forced_cue.forced_peak_c)
    direct = iron_bloom_yield(ore, 1.0, peak, roasted=False)
    if direct.ore_class == "non_iron":      # gossan over lead/zinc — no iron to win
        return None
    roasted = iron_bloom_yield(ore, 1.0, peak, roasted=True)
    needs_roast = bool(direct.requires_roasting and direct.bloom_iron_kg <= 0.0)
    reducible_now = bool(direct.bloom_iron_kg > 0.0)
    achievable = roasted if needs_roast else direct

    conf = float(getattr(forced_cue, "confidence", 0.0))
    rich = min(1.0, direct.contained_fe_fraction)   # hematite 0.70, magnetite 0.72, pyrite 0.47
    confidence = float(min(1.0, conf * (0.6 + 0.4 * rich)))

    return BloomCue(
        coord=tuple(int(c) for c in coord),
        biome=int(getattr(forced_cue, "biome", 0)),
        iron_mineral=str(ore),
        ore_class=direct.ore_class,
        requires_roasting=bool(direct.requires_roasting),
        red_short=bool(direct.red_short),
        contained_fe_fraction=float(round(direct.contained_fe_fraction, 4)),
        forced_peak_c=float(round(peak, 1)),
        wall_refractory=bool(getattr(forced_cue, "wall_refractory", False)),
        reaches_bloomery_temp=True,
        is_solid_bloom=True,
        requires_forging=True,
        furnace_reaches_iron_melt=bool(peak >= IRON_MELT_TEMP_C),
        reducible_now=reducible_now,
        needs_roasting_first=needs_roast,
        reduction_efficiency=float(round(direct.reduction_efficiency, 4)),
        bloom_iron_per_kg_ore=float(round(direct.bloom_iron_kg, 6)),
        bloom_iron_per_kg_ore_roasted=float(round(roasted.bloom_iron_kg, 6)),
        slag_per_kg_ore=float(round(direct.slag_kg, 6)),
        bloom_purity=float(round(achievable.bloom_purity, 4)),
        roast_temp_c=float(ROAST_TEMP_C),
        dig_depth_m=float(round(float(getattr(gossan_cue, "dig_depth_m", 0.0)), 4)),
        confidence=float(round(confidence, 4)))


@dataclass(frozen=True)
class BloomResult:
    """The realized outcome of an actual ``bloom_at`` — the iron **réduction effective**.
    The ore has been *consumed* from the geology column; this is the spongy bloom that was
    *gotten*. The world never lies: ``bloom_iron_kg`` equals the cue's committed yield for
    ``ore_consumed_kg``. ``is_solid_bloom`` is always True (a sponge, hammered, not poured)."""
    coord: Tuple[int, int, int]
    iron_mineral: str
    ore_class: str
    ore_consumed_kg: float         # iron-ore mass actually extracted (mutation)
    bloom_iron_kg: float           # the solid iron bloom recovered (0 for un-roasted sulfide / non-iron)
    slag_kg: float                 # fayalite slag produced (spent ore + gangue, less the bloom)
    bloom_purity: float            # Fe fraction of the bloom (0 if none)
    red_short: bool                # sulfide-derived iron is brittle (red-short)
    roasted: bool                  # whether the charge was roasted before reducing
    required_roasting: bool        # whether this ore *needed* roasting (sulfide)
    is_solid_bloom: bool           # ALWAYS True — solid sponge, must be forged
    peak_c: float                  # the furnace peak the run ran at


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_iron_bloomery(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim`` and ensures the
    composed capabilities (C12 forced draught, C1 surface mineralization, geology) are
    installed. Adds **zero** per-tick cost: the oracle is derived on query and memoised.
    Returns the cache dict (``sim._iron_bloom_cue_cache``)."""
    fd.install_forced_draught(sim)
    sm.install_surface_mineralization(sim)
    geo.install_geology(sim)
    cache = getattr(sim, "_iron_bloom_cue_cache", None)
    if cache is None:
        cache = {}
        sim._iron_bloom_cue_cache = cache
    return cache


def bloom_cue_for_chunk(sim, coord: Tuple[int, int, int]) -> Optional[BloomCue]:
    """Truthful iron-bloomery affordance at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, C12 ``forced_cue_for_chunk(sim, coord)`` reports
    ``reaches_iron_bloomery_temp`` (a refractory forced furnace ≥1200 °C), and C1's
    ``surface_cue_for_chunk`` here is an **iron-bearing** gossan whose ``mineral`` equals
    ``iron_mineral``. A lead/zinc gossan or a cool furnace ⇒ None."""
    coord = tuple(int(c) for c in coord)
    cache = install_iron_bloomery(sim)
    if coord in cache:
        return cache[coord]
    forced = fd.forced_cue_for_chunk(sim, coord)
    gossan = sm.surface_cue_for_chunk(sim, coord)
    cue = _cue_from_inputs(coord, forced, gossan)
    cache[coord] = cue
    return cue


def prospect_bloom(sim, world_x: float, world_y: float) -> Optional[BloomCue]:
    """What an agent standing at world ``(x, y)`` could discover about reducing the iron
    ore here. Returns the cue (bloom yield + truthful outcome) or None when nothing is
    reducible underfoot (no refractory furnace ≥1200 °C, or no iron-bearing gossan)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return bloom_cue_for_chunk(sim, coord)


def bloom_preview(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of whether (and how much) iron a bloomery run at
    ``(x, y)`` would yield — the ground-truthed outcome the perception cue must agree with.

    Touches NOTHING (no ore mined, no fire lit, no geology mutated): the truth oracle, not
    the act. Always returns a dict (even when not reducible), naming the *missing*
    ingredient — the honest 'why not', including the iron-hat lies: a gossan over **lead**
    (galena) or **zinc** (sphalerite) reports ``reason='gossan caps a non-iron ore'``; a
    **pyrite** gossan reports ``needs_roasting_first`` + ``red_short``."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = bloom_cue_for_chunk(sim, coord)
    if cue is not None:
        return {"reducible": True, "reason": "ok",
                "iron_mineral": cue.iron_mineral,
                "ore_class": cue.ore_class,
                "requires_roasting": cue.requires_roasting,
                "red_short": cue.red_short,
                "reducible_now": cue.reducible_now,
                "needs_roasting_first": cue.needs_roasting_first,
                "roast_temp_c": cue.roast_temp_c,
                "forced_peak_c": cue.forced_peak_c,
                "is_solid_bloom": cue.is_solid_bloom,
                "requires_forging": cue.requires_forging,
                "furnace_reaches_iron_melt": cue.furnace_reaches_iron_melt,
                "bloom_iron_per_kg_ore": cue.bloom_iron_per_kg_ore,
                "bloom_iron_per_kg_ore_roasted": cue.bloom_iron_per_kg_ore_roasted,
                "slag_per_kg_ore": cue.slag_per_kg_ore,
                "bloom_purity": cue.bloom_purity,
                "confidence": cue.confidence,
                "biome": cue.biome}
    # Not reducible — recompute the diagnostic to name the missing ingredient.
    forced = fd.forced_cue_for_chunk(sim, coord)
    gossan = sm.surface_cue_for_chunk(sim, coord)
    has_iron_gossan = bool(
        gossan is not None and getattr(gossan, "group", None) == _GOSSAN_GROUP
        and MINERAL_BY_NAME.get(getattr(gossan, "mineral", ""),
                                None) is not None
        and MINERAL_BY_NAME[gossan.mineral].yields_per_kg_ore.get("Fe", 0.0) > 0.0)
    if forced is None or not getattr(forced, "forceable", False):
        return {"reducible": False, "reason": "no forced-draught furnace buildable here",
                "has_furnace": False, "has_iron_ore": has_iron_gossan}
    if not getattr(forced, "reaches_iron_bloomery_temp", False):
        return {"reducible": False,
                "reason": "furnace too cold for the bloomery regime (needs >=1200 C; refractory wall)",
                "has_furnace": True, "has_iron_ore": has_iron_gossan,
                "wall_refractory": bool(getattr(forced, "wall_refractory", False)),
                "forced_peak_c": forced.forced_peak_c}
    if gossan is None or getattr(gossan, "group", None) != _GOSSAN_GROUP:
        return {"reducible": False, "reason": "no iron-hat (gossan) tell here to reduce",
                "has_furnace": True, "has_iron_ore": False,
                "forced_peak_c": forced.forced_peak_c}
    # A gossan IS here but it caps a non-iron ore (galena -> lead, sphalerite -> zinc).
    return {"reducible": False, "reason": "gossan caps a non-iron ore (lead/zinc, not iron)",
            "has_furnace": True, "has_iron_ore": False,
            "gossan_mineral": getattr(gossan, "mineral", None),
            "forced_peak_c": forced.forced_peak_c}


def discover_bloomery_sites_by_sight(sim, rows: List[int],
                                     perception_radius_m: float = 64.0
                                     ) -> Dict[int, List[BloomCue]]:
    """For each agent ``row``, the iron-reducible sites perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    Turns the static substrate (a refractory furnace + an iron gossan) into a
    **perceivable, actionable** transformation signal — the agent then *chooses* to
    reduce iron. Deterministic order (by chunk distance, then coord)."""
    out: Dict[int, List[BloomCue]] = {}
    if not rows:
        return out
    install_iron_bloomery(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], BloomCue]] = []
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
                cue = bloom_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def _achievable_yield(c: BloomCue) -> float:
    """The iron a site can ultimately give (direct, or after a roast for a sulfide)."""
    return max(c.bloom_iron_per_kg_ore, c.bloom_iron_per_kg_ore_roasted)


def best_bloomery_site_near(sim, row: int, perception_radius_m: float = 128.0,
                            *, require_direct: bool = False,
                            require_sound: bool = False) -> Optional[BloomCue]:
    """The most rewarding iron-reducible site an agent at ``row`` can perceive — the
    actionable pick (highest achievable iron per kg ore; tie-break higher purity, then
    confidence, then nearest then coord).

    This is where the oxide-vs-sulfide-vs-non-iron inversion teaches: preferring the iron
    actually gotten *and usable*, the agent learns to reduce the oxide gossan directly,
    to roast (and distrust) the pyrite gossan, and to ignore the lead/zinc gossan.
    ``require_direct`` keeps only sites that yield iron NOW (oxide — no roast detour).
    ``require_sound`` additionally rejects red-short (pyrite) iron. Returns None when
    nothing reducible is in sight."""
    cues = discover_bloomery_sites_by_sight(sim, [int(row)], perception_radius_m
                                            ).get(int(row), [])
    pool = cues
    if require_direct:
        pool = [c for c in pool if c.reducible_now]
    if require_sound:
        pool = [c for c in pool if not c.red_short]
    if not pool:
        return None
    # already distance-sorted; prefer the most iron, then purest, then surest.
    return max(pool, key=lambda c: (_achievable_yield(c), c.bloom_purity, c.confidence))


def bloom_at(sim, row: int, *, charge_kg: float = DEFAULT_CHARGE_KG,
             roasted: bool = False) -> Optional[BloomResult]:
    """**The réduction effective** (the 2nd MUTATING entry point of the C1→C17 arc,
    after C13 ``smelt_at`` — see ``crates/MUTATION-FRONTIER.md``).

    Reduce the iron gossan ore under agent ``row`` in the refractory forced-draught
    furnace buildable there. Side effects: **consumes** a charge of ore from the geology
    column (via the SSOT ``geo.mine_at`` — the ore is drained from ``extracted_kg``) and
    reduces it per ``iron_bloom_yield``. Returns a ``BloomResult`` (solid iron bloom +
    fayalite slag) or None when nothing is reducible here (no refractory furnace ≥1200 °C,
    or no iron-bearing gossan underfoot).

    The world never lies: the realized ``bloom_iron_kg`` equals the cue's committed
    per-kg yield × the ore actually consumed. ``roasted=False`` on a pyrite gossan
    consumes the charge and yields **only slag** (``bloom_iron_kg == 0``) — the honest,
    costly lesson that the rusty tell hid a sulfide; the agent must discover roasting
    first (and that the iron stays red-short). The bloom is always a **solid sponge**
    (``is_solid_bloom`` True) — it must be forged, never poured."""
    install_iron_bloomery(sim)
    pos = sim.agents.pos
    coord = world_to_chunk(float(pos[row, 0]), float(pos[row, 1]))
    cue = bloom_cue_for_chunk(sim, coord)
    if cue is None:
        return None
    c1 = sm.surface_cue_for_chunk(sim, coord)
    if c1 is None or c1.group != _GOSSAN_GROUP:   # invariant guarantees an iron gossan here
        return None  # pragma: no cover
    mined = geo.mine_at(sim, row, float(c1.dig_depth_m), float(charge_kg))
    if not mined:
        return None
    ore_kg = float(mined.get(cue.iron_mineral, 0.0))
    gangue_kg = float(sum(v for k, v in mined.items() if k != cue.iron_mineral))
    y = iron_bloom_yield(cue.iron_mineral, ore_kg, cue.forced_peak_c, roasted=roasted)
    slag = float(y.slag_kg + gangue_kg)
    return BloomResult(
        coord=tuple(int(c) for c in coord),
        iron_mineral=cue.iron_mineral, ore_class=y.ore_class,
        ore_consumed_kg=float(round(ore_kg, 6)),
        bloom_iron_kg=float(round(y.bloom_iron_kg, 6)),
        slag_kg=float(round(slag, 6)),
        bloom_purity=float(round(y.bloom_purity, 4)),
        red_short=bool(y.red_short),
        roasted=bool(roasted), required_roasting=bool(y.requires_roasting),
        is_solid_bloom=True,
        peak_c=float(round(cue.forced_peak_c, 1)))


def bloom_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the dashboard /
    smoke journal. Read-only; computes cues lazily."""
    install_iron_bloomery(sim)
    by_class: Dict[str, int] = {}
    by_mineral: Dict[str, int] = {}
    n_chunks = 0
    n_sites = 0
    n_direct = 0
    n_needs_roast = 0
    n_red_short = 0
    best_bloom = 0.0
    best_purity = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = bloom_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_sites += 1
        if cue.reducible_now:
            n_direct += 1
        if cue.needs_roasting_first:
            n_needs_roast += 1
        if cue.red_short:
            n_red_short += 1
        by_class[cue.ore_class] = by_class.get(cue.ore_class, 0) + 1
        by_mineral[cue.iron_mineral] = by_mineral.get(cue.iron_mineral, 0) + 1
        best_bloom = max(best_bloom, _achievable_yield(cue))
        best_purity = max(best_purity, cue.bloom_purity)
    return {
        "n_chunks": n_chunks,
        "n_bloomery_sites": n_sites,
        "bloomery_rate": round(n_sites / n_chunks, 4) if n_chunks else 0.0,
        "n_direct_reducible": n_direct,
        "n_needs_roasting": n_needs_roast,
        "n_red_short": n_red_short,
        "best_bloom_iron_per_kg_ore": round(best_bloom, 6),
        "best_bloom_purity": round(best_purity, 4),
        "by_ore_class": dict(sorted(by_class.items())),
        "by_mineral": dict(sorted(by_mineral.items())),
    }


__all__ = [
    "BloomYield", "BloomCue", "BloomResult",
    "install_iron_bloomery", "bloom_cue_for_chunk", "prospect_bloom",
    "bloom_preview", "discover_bloomery_sites_by_sight", "best_bloomery_site_near",
    "bloom_at", "bloom_summary",
    "iron_bloom_yield",
    "IRON_MELT_TEMP_C", "ROAST_TEMP_C", "SUPERHEAT_SPAN_C", "SUPERHEAT_GAIN",
    "OXIDE_BASE_RECOVERY", "OXIDE_RECOVERY_CEIL", "OXIDE_BLOOM_PURITY",
    "SULFIDE_BASE_RECOVERY", "SULFIDE_RECOVERY_CEIL", "SULFIDE_BLOOM_PURITY",
    "DEFAULT_CHARGE_KG",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
