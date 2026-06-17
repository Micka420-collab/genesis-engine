"""Genesis Engine — Substrate capability : cuisson de la chaux (Cap. C10).

**La troisième capacité de TRANSFORMATION** (après C8 ``lithic_tempering`` et C9
``ceramic_firing``) et le **pendant exact de C9** : C9 cuit l'**argile** (C5) dans
un **feu** (C7) → céramique ; C10 brûle le **calcaire** (C6) dans le même feu (C7)
→ **chaux**. L'argile *contient*, le calcaire *lie* : la chaux est le plus ancien
liant chimique connu — enduits de sol néolithiques de Göbekli Tepe (~9500 av.
J.-C.), *« Burning Lime, the oldest chemical industry on Earth »* — antérieure à
la métallurgie et parfois à l'agriculture.

**Règle invariante du projet** (cf. ``surface_mineralization`` (C1) …
``ceramic_firing`` (C9)) : rien n'est scripté. Un agent ne *sait* pas qu'« on
brûle la pierre blanche pour faire du mortier ». Il **VOIT** une falaise calcaire
qu'il sait déjà tailler (C6), il **SAIT faire du feu** ici (C7) — et en jetant par
hasard un éclat de calcaire dans un grand brasier il **découvre** qu'il devient une
pierre légère et caustique qui *bout* et chauffe quand on la mouille (extinction de
la chaux vive, lien C3), puis durcit en séchant. Ce module n'expose qu'un **signal
physique véridique** : *ce calcaire-ci, calciné dans le feu faisable ici, donnerait
une chaux de telle qualité, cuite à tel degré*. Le tas de cuisson, le four à chaux,
le mortier, l'enduit, la maçonnerie — toute la chaîne opératoire reste **émergente**.

Ce n'est PAS de la perception passive : c'est une **transformation**
----------------------------------------------------------------------
C1→C6 *montrent* une matière, C7 *amorce* un feu, C8 *trempe* une pierre, C9 *cuit*
une argile. C10 **décarbonate une pierre** : CaCO₃ → CaO + CO₂↑. La calcite est
détruite ; la chaux vive (CaO) obtenue est un matériau **qui n'existe pas dans la
nature** (elle se réhydrate aussitôt). Le monde s'**engage** sur le résultat
(``calcination_extent`` / ``lime_yield`` déterministes et ground-truthés) : « si tu
brûles ce calcaire dans ce feu, tu obtiendras une chaux *exactement* de ce niveau ».
L'agent découvre la corrélation « calcaire + grand feu → liant » en agissant ; on
ne la lui souffle jamais.

N'introduit AUCUN nouveau « tell » minéral — il COMPOSE (garde-fou D8)
---------------------------------------------------------------------
Comme C7/C8/C9, ce module **ne surface aucune nouvelle matière**, n'a **pas** de
table ``_PROFILE`` et **ne crée aucune entrée** ``PY_TO_RUST`` / ``PY_CATALOGUE_ONLY``
(cf. ``test_geology_cross_language_contract``). C'est la **4ᵉ** capacité D8-par-
composition. Il *lit* deux capacités déjà classées cross-langage :

* le **calcaire** — exactement la pétrologie de C6 ``limestone_outcrop``
  (``limestone_cue_for_chunk`` : matière, ``lime_grade``, ``lime_class``,
  ``mortar_grade``, incl. le tell ``limestone_pure`` byte-exact) ;
* le **feu** — exactement l'affordance de C7 ``fire_ignition``
  (``ignition_cue_for_chunk`` : un foyer *peut* être fait ici, et son ``fine_fuel``
  gouverne la température de pointe atteinte).

Le fichier est volontairement **hors du glob** ``*_outcrop.py`` : ce n'est pas un
affleurement, c'est une transformation. Décision asservie par
``test_introduces_no_new_tell`` (garde-fou D8 respecté par composition — la 4ᵉ
fois après C7, C8 et C9).

Le COMBO de la veille — réemploi de la physique du feu de C9
------------------------------------------------------------
C9 a introduit la **température de pointe du feu ouvert** ``open_fire_peak_temp_c``
(600–850 °C selon ``fine_fuel``). C10 **réutilise cette même SSOT verbatim**
(``import engine.ceramic_firing``) au lieu de la re-modéliser : un seul feu, deux
pyrotransformations (cuire l'argile, calciner le calcaire). Si la physique du feu
ouvert change, les deux capacités bougent ensemble. C'est le combo retenu de la
veille 2026-06-17 (réemploi d'un composant existant plutôt qu'extension).

Physique de la calcination — la veille 2026-06-17 (archéométrie de la chaux)
----------------------------------------------------------------------------
La cuisson de la chaux est **gouvernée par la température**, jamais arbitraire
(méta-règle du substrat). Deux quantités physiques se rencontrent :

1. **Température de pointe du feu ouvert** (``cf.open_fire_peak_temp_c`` — réemploi
   C9). Le seul « four » disponible depuis C7 seul est un **feu nu** : ~600–850 °C.

2. **Seuil de décarbonatation du carbonate** (``calcination_onset_c``). La calcite
   pure est le carbonate le plus **thermodynamiquement stable** : à P(CO₂)=1 atm sa
   décomposition complète n'intervient qu'à ~**898 °C** (Boynton, *Chemistry and
   Technology of Lime and Limestone*). Mais :
   * **carbonate commun / dolomitique** (``COMMON_CARBONATE``) — les fondants
     (argile, Fe, alcalins) et surtout le **MgCO₃** de la dolomie **abaissent** le
     seuil : la décarbonatation s'amorce bas (~680 °C). Une pierre banale brûle
     donc en chaux **dans un simple grand feu**.
   * **carbonate pur** (``PURE_CARBONATE`` : ``limestone_pure`` / ``calcite`` /
     ``marble``) — **réfractaire au sens thermodynamique** : il faut s'approcher de
     ~898 °C. Dans un feu ouvert (≤ ~850 °C, ~800 °C en prairie) il reste
     **sous-cuit** : un cœur de calcaire cru, une chaux maigre et peu réactive.

``calcination_extent = (peak − onset) / (full − onset)`` ∈ [0,1] mesure le degré de
décarbonatation. Au-dessus de ``SOUND_CALCINATION`` la chaux est **bien cuite**
(chaux aérienne utilisable : enduit, badigeon) ; en-dessous elle est **sous-cuite**
(cœur cru, se recarbonate, ne lie pas).

Le mensonge rendu visible — l'inversion réfractaire (le pendant de C9/C8)
------------------------------------------------------------------------
C8 : l'obsidienne *semble* la pierre idéale mais la chauffer ne gagne rien. C9 : le
**kaolin** *semble* la meilleure argile mais **sous-cuit** au feu ouvert. C10 expose
le **même piège** sur le calcaire : la pierre **la plus blanche et la plus pure**
(``limestone_pure``, ``lime_grade`` 0,95, ``mortar_grade`` True — elle *peut*
devenir le meilleur mortier) **attire le bâtisseur** — mais dans un **feu ouvert**
elle **sous-cuit** (réfractaire), et donne une chaux **pire** qu'un humble calcaire
gris commun (ou une dolomie) calciné à cœur. La leçon émergente que
``best_burning_site_near`` enseigne (il préfère la plus haute ``lime_yield``) :
**brûle la pierre grise banale, pas la belle pierre blanche** — tant que tu n'as
qu'un feu nu. Réaliser le potentiel du calcaire pur (mortier liant) exigera un
**four à chaux** (≥ ~900 °C soutenu) — une capacité future. Le monde ne ment pas :
il montre le mortier comme un *potentiel* (``would_mortar_if_kiln_fired``) que **ce**
feu **ne réalise pas** (``mortar_ready`` toujours False en feu ouvert — la pointe
max d'un feu nu n'atteint jamais ``MORTAR_CALCINATION``).

Effet 1+1>2 et « le monde ne ment jamais »
------------------------------------------
La calcination n'est possible QUE là où **les deux** ingrédients coexistent
réellement dans la même colonne : un calcaire (C6) **ET** un feu faisable (C7). Si
``lime_burning_cue_for_chunk`` renvoie une indication, ``burnable`` est vrai et le
résultat est **ground-truthé** : le carbonate existe (C6 le prouve sur la même
colonne que ``mine_at``) et le feu est faisable (C7 le prouve). La réciproque reste
*faible* (pas d'affordance ⇏ pas de calcaire) — on ne donne pas la carte des gîtes.

Déterminisme
------------
Pur : composition de ``limestone_cue_for_chunk`` (C6) et ``ignition_cue_for_chunk``
(C7), tous deux ``prf_rng`` / dérivés du seed. Aucun RNG nouveau. Bit-identique
entre deux runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — la calcination est une lecture
dérivée du substrat (calcaire + feu), comme C1→C9.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape
(chunk → affordance de transformation), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from engine.world import CHUNK_SIDE_M, world_to_chunk
# Single sources of truth — reused verbatim, never re-modelled (garde-fou D8).
import engine.limestone_outcrop as li   # C6 — the carbonate & its lime petrology
import engine.fire_ignition as fi       # C7 — the fire-making affordance
import engine.ceramic_firing as cf      # C9 — the open-fire peak-temperature SSOT

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# --- Calcination thresholds (°C): the temperature a carbonate must reach to
# decarbonate (CaCO3 -> CaO + CO2). Keyed on C6's own ``lime_class`` (single source
# of truth — no carbonate-name duplication). Pure calcite is the most stable
# carbonate (high decomposition T); a fluxed / magnesian common carbonate
# decarbonates lower (clay/Fe/alkali fluxes + MgCO3 in dolomite lower the onset).
CALCINATION_ONSET_FLUXED_C = 680.0   # common / dolomitic carbonate — low-firing
CALCINATION_ONSET_PURE_C = 770.0     # pure calcite — refractory, needs a kiln
# Full decarbonation of pure CaCO3 at P(CO2)=1 atm (Boynton) — only a kiln, which
# sustains a CO2-rich high heat, reaches it. The honest ceiling C10 commits to.
CALCINATION_FULL_C = 898.0

# Fraction of decarbonation at/above which the lime is *well burnt* — a usable (if
# only aerial / non-hydraulic) lime for plaster / limewash. Below it the body is
# under-burnt: a raw core that re-carbonates and will not bind.
SOUND_CALCINATION = 0.45

# Fraction of decarbonation a true *binding mortar* needs — a hard burn an open
# fire never reaches (its peak <= OPEN_FIRE_MAX_C caps the extent below this), so
# ``mortar_ready`` is always False in an open fire: the unrealized kiln potential.
MORTAR_CALCINATION = 0.92

# Ceiling on the quality an *under-burnt* lime can reach (a crumbly maigre lime is
# a poor binder however pure the stone). The honest cap on the inversion — the
# exact counterpart of C9's ``UNDERFIRED_CEILING``.
UNDERBURNT_CEILING = 0.25


@dataclass(frozen=True)
class LimeBurnCue:
    """A truthful lime-burning (calcination) affordance at one chunk.

    What an agent *could* discover by throwing the limestone it already quarries
    (C6) into a big fire (C7): the white stone becomes a light, caustic quicklime
    that boils when wetted (slaking, link to water C3) and sets hard. It is NOT
    handed to the agent as "burn limestone at 900 C for mortar" — the agent must
    learn the heat->binder correlation by acting. ``calcination_extent`` /
    ``lime_yield`` are the ground truth the world commits to (doing it yields
    exactly this).
    """
    coord: Tuple[int, int, int]
    biome: int
    # raw carbonate (read from C6 limestone_outcrop)
    carbonate_material: str       # ground-truth carbonate (e.g. "limestone")
    carbonate_label: str          # human label of the perceived exposure
    lime_class: str               # C6 LimeClass name (COMMON_/PURE_CARBONATE)
    lime_grade: float             # C6 intrinsic carbonate purity / lime rank [0,1]
    mortar_grade: bool            # C6: pure enough to bind a true mortar (if hard-burnt)
    collect_depth_m: float        # depth that lands in the proving C6 layer
    also_dressable_stone: bool    # C6: the same sound outcrop also dresses to blocks
    # fire (read from C7 fire_ignition)
    fire_method: str              # easiest ignition method available here
    fire_confidence: float        # C7 reliability of making a fire here [0,1]
    fine_fuel: float              # C7 fine-fuel load (drives the peak temperature)
    # transformation outcome (the truth the world commits to)
    burnable: bool                # carbonate AND a fire is makeable here
    peak_temp_c: float            # peak temperature this open fire reaches (C)
    calcination_onset_c: float    # temperature this carbonate starts decarbonating
    calcination_extent: float     # (peak-onset)/(full-onset) in [0,1] — degree burnt
    well_burnt: bool              # extent >= SOUND_CALCINATION (usable aerial lime)
    underburnt: bool              # not well burnt (raw core / re-carbonates)
    mortar_ready: bool            # open fire never hard-burns -> always False
    would_mortar_if_kiln_fired: bool  # unrealized binding-mortar potential (kiln)
    lime_yield: float             # quality of the burnt lime [0,1] (ground truth)
    confidence: float             # reliability of achieving lime_yield [0,1]


# ---------------------------------------------------------------------------
# Single sources of truth — the physics the world commits to.
# ---------------------------------------------------------------------------

def calcination_onset_c(lime_class: "li.LimeClass") -> float:
    """Onset temperature (C) a carbonate must reach to begin decarbonating.

    Keyed on C6's ``lime_class`` (SSOT, no carbonate-name duplication): a pure
    carbonate is refractory (high onset, kiln-grade); a common / dolomitic
    carbonate is fluxed and decarbonates low (open-fire-grade)."""
    if lime_class == li.LimeClass.PURE_CARBONATE:
        return CALCINATION_ONSET_PURE_C
    return CALCINATION_ONSET_FLUXED_C


def calcination_extent(peak_temp_c: float, onset_c: float) -> float:
    """Degree of decarbonation in [0,1] from the fire's peak and the carbonate's
    onset.

    Deterministic SSOT: 0 below the onset (the stone stays raw), rising linearly
    toward 1 at ``CALCINATION_FULL_C`` (full conversion — only a kiln reaches it).
    A bare fire never fully calcines a refractory pure carbonate: the honest
    ceiling this capability commits to."""
    peak = float(peak_temp_c)
    onset = float(onset_c)
    if peak <= onset:
        return 0.0
    span = CALCINATION_FULL_C - onset
    if span <= 0.0:  # pragma: no cover — onsets are below full by construction
        return 1.0
    return float(min(1.0, (peak - onset) / span))


def quicklime_quality(lime_grade: float, extent: float) -> float:
    """Single source of truth for the burnt-lime quality.

    Deterministic, bounded [0,1]. A *well-burnt* lime (``extent`` >=
    ``SOUND_CALCINATION``) yields a lime of the stone's intrinsic ``lime_grade``
    (an open fire cannot exceed it — no hard burn). An *under-burnt* body is capped
    hard by ``UNDERBURNT_CEILING`` scaled by how close it came: this is the
    refractory inversion — a pure white limestone under-burnt in a campfire scores
    *below* a humble common limestone burnt to soundness. Any real action module
    that *burns* limestone MUST read this function, so the world never lies about
    what a fire yields. The exact counterpart of C9's ``fired_ware_quality``.
    """
    lg = min(1.0, max(0.0, float(lime_grade)))
    ce = min(1.0, max(0.0, float(extent)))
    if ce >= SOUND_CALCINATION:
        return lg
    # under-burnt: maigre, crumbly lime, capped low and scaled by burn progress.
    return float(lg * UNDERBURNT_CEILING * (ce / SOUND_CALCINATION))


# ---------------------------------------------------------------------------
# Core derivation — transformation outcome from C6 carbonate x C7 fire.
# ---------------------------------------------------------------------------

def _cue_from_inputs(coord, lime_cue, fire_cue) -> Optional[LimeBurnCue]:
    """Pure derivation. Emits a cue iff the site is **burnable** — a carbonate
    (C6) AND a makeable fire (C7) coexist here. The 1+1>2 gate: either ingredient
    missing => no calcination affordance."""
    if lime_cue is None or fire_cue is None:
        return None

    fine_fuel = float(getattr(fire_cue, "fine_fuel", 0.0))
    peak = cf.open_fire_peak_temp_c(fine_fuel)          # combo: reuse C9 SSOT
    onset = calcination_onset_c(lime_cue.lime_class)
    extent = calcination_extent(peak, onset)
    well_burnt = extent >= SOUND_CALCINATION
    lime_yield = quicklime_quality(lime_cue.lime_grade, extent)
    mortar_grade = bool(getattr(lime_cue, "mortar_grade", False))
    mortar_ready = bool(well_burnt and mortar_grade and extent >= MORTAR_CALCINATION)

    fire_conf = float(getattr(fire_cue, "confidence", 0.0))
    confidence = float(min(1.0, fire_conf * (0.4 + 0.6 * extent)))
    method = fire_cue.method.name if hasattr(fire_cue, "method") else "NONE"

    return LimeBurnCue(
        coord=tuple(int(c) for c in coord), biome=int(lime_cue.biome),
        carbonate_material=lime_cue.material, carbonate_label=lime_cue.label,
        lime_class=lime_cue.lime_class.name,
        lime_grade=float(round(lime_cue.lime_grade, 4)),
        mortar_grade=mortar_grade,
        collect_depth_m=float(lime_cue.collect_depth_m),
        also_dressable_stone=bool(getattr(lime_cue, "dressable_now", False)),
        fire_method=method, fire_confidence=float(round(fire_conf, 4)),
        fine_fuel=float(round(fine_fuel, 4)),
        burnable=True, peak_temp_c=float(round(peak, 1)),
        calcination_onset_c=float(onset),
        calcination_extent=float(round(extent, 4)),
        well_burnt=bool(well_burnt), underburnt=bool(not well_burnt),
        mortar_ready=bool(mortar_ready),  # an open fire never hard-burns -> False
        would_mortar_if_kiln_fired=mortar_grade,
        lime_yield=float(round(lime_yield, 4)),
        confidence=float(round(confidence, 4)))


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_lime_burning(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim`` and
    ensures the composed capabilities (C6 carbonate, C7 fire) are installed.

    Adds **zero** per-tick cost: affordances are derived on query and memoised.
    Returns the cache dict (``sim._lime_burn_cue_cache``).
    """
    li.install_limestone_outcrop(sim)
    fi.install_fire_ignition(sim)
    cache = getattr(sim, "_lime_burn_cue_cache", None)
    if cache is None:
        cache = {}
        sim._lime_burn_cue_cache = cache
    return cache


def lime_burning_cue_for_chunk(sim, coord: Tuple[int, int, int]
                               ) -> Optional[LimeBurnCue]:
    """Truthful lime-burning affordance at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, ``burnable`` is True — C6
    ``limestone_cue_for_chunk(sim, coord)`` proves a carbonate is reachable shallow
    in the same column ``mine_at`` reads, and C7 ``ignition_cue_for_chunk(sim,
    coord)`` proves a fire can be made here.
    """
    coord = tuple(int(c) for c in coord)
    cache = install_lime_burning(sim)
    if coord in cache:
        return cache[coord]
    lime = li.limestone_cue_for_chunk(sim, coord)
    fire = fi.ignition_cue_for_chunk(sim, coord)
    cue = _cue_from_inputs(coord, lime, fire)
    cache[coord] = cue
    return cue


def prospect_lime_burning(sim, world_x: float, world_y: float
                          ) -> Optional[LimeBurnCue]:
    """What an agent standing at world ``(x, y)`` could discover about burning the
    limestone here. Returns the cue (lime yield + truthful outcome) or None when
    nothing burnable is underfoot."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return lime_burning_cue_for_chunk(sim, coord)


def burn_preview(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of whether (and how well) the limestone at
    ``(x, y)`` would burn to lime — the ground-truthed outcome the perception cue
    must agree with.

    Touches NOTHING (no stone quarried, no fire lit, no geology mutated): the truth
    oracle, not the action. Always returns a dict (even when not burnable), naming
    the *missing* ingredient — the honest 'why not'. The lie this cap exposes: a
    pure white limestone looks like the prime mortar stone, yet an open fire
    under-burns it (``underburnt`` True, ``would_mortar_if_kiln_fired`` True — it
    *would* bind, but only burnt in a kiln this fire is not)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = lime_burning_cue_for_chunk(sim, coord)
    if cue is not None:
        return {"burnable": True, "reason": "ok",
                "carbonate_material": cue.carbonate_material,
                "lime_grade": cue.lime_grade,
                "peak_temp_c": cue.peak_temp_c,
                "calcination_onset_c": cue.calcination_onset_c,
                "calcination_extent": cue.calcination_extent,
                "well_burnt": cue.well_burnt,
                "underburnt": cue.underburnt,
                "mortar_ready": cue.mortar_ready,
                "would_mortar_if_kiln_fired": cue.would_mortar_if_kiln_fired,
                "lime_yield": cue.lime_yield,
                "fire_method": cue.fire_method,
                "also_dressable_stone": cue.also_dressable_stone,
                "confidence": cue.confidence,
                "biome": cue.biome}
    # Not burnable — recompute the diagnostic to name the missing ingredient.
    lime = li.limestone_cue_for_chunk(sim, coord)
    fire = fi.ignition_cue_for_chunk(sim, coord)
    if lime is None:
        reason = "no limestone here to quarry and burn"
    elif fire is None:
        reason = "no fire can be made here to burn the limestone"
    else:  # pragma: no cover — both present would have produced a cue
        reason = "not burnable"
    return {"burnable": False, "reason": reason,
            "carbonate_material": (lime.material if lime is not None else None),
            "has_limestone": bool(lime is not None),
            "has_fire": bool(fire is not None)}


def discover_burning_sites_by_sight(sim, rows: List[int],
                                    perception_radius_m: float = 64.0
                                    ) -> Dict[int, List[LimeBurnCue]]:
    """For each agent ``row``, the burnable sites perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    Turns the static substrate (a carbonate outcrop + a fire-makeable spot) into a
    **perceivable, actionable** transformation signal — the agent then *chooses*
    to quarry and burn the stone. Deterministic order (by chunk distance, then coord).
    """
    out: Dict[int, List[LimeBurnCue]] = {}
    if not rows:
        return out
    install_lime_burning(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], LimeBurnCue]] = []
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
                cue = lime_burning_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_burning_site_near(sim, row: int, perception_radius_m: float = 128.0,
                           *, require_well_burnt: bool = False
                           ) -> Optional[LimeBurnCue]:
    """The most rewarding lime-burning site an agent at ``row`` can perceive — the
    actionable pick (highest ``lime_yield``; tie-break higher confidence, then
    nearest then coord).

    This is where the refractory inversion teaches: preferring ``lime_yield``, the
    agent learns to burn the humble common limestone (well-burnt) over the pretty
    pure white stone (under-burnt) — until it has a kiln. ``require_well_burnt``
    keeps only burns that yield a usable lime. Returns None when nothing burnable
    is in sight (a physically honest 'no lime to be made here')."""
    cues = discover_burning_sites_by_sight(sim, [int(row)], perception_radius_m
                                           ).get(int(row), [])
    pool = [c for c in cues if c.well_burnt] if require_well_burnt else cues
    if not pool:
        return None
    # already distance-sorted; prefer the best lime, then the surest burn.
    return max(pool, key=lambda c: (c.lime_yield, c.confidence))


def lime_burning_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_lime_burning(sim)
    by_material: Dict[str, int] = {}
    n_chunks = 0
    n_burnable = 0
    n_well_burnt = 0
    n_underburnt = 0
    best_lime = 0.0
    best_peak = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = lime_burning_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_burnable += 1
        if cue.well_burnt:
            n_well_burnt += 1
        else:
            n_underburnt += 1
        by_material[cue.carbonate_material] = \
            by_material.get(cue.carbonate_material, 0) + 1
        best_lime = max(best_lime, cue.lime_yield)
        best_peak = max(best_peak, cue.peak_temp_c)
    return {
        "n_chunks": n_chunks,
        "n_chunks_burnable": n_burnable,
        "burnable_rate": round(n_burnable / n_chunks, 4) if n_chunks else 0.0,
        "n_well_burnt": n_well_burnt,
        "n_underburnt": n_underburnt,
        "best_lime_yield": round(best_lime, 4),
        "best_peak_temp_c": round(best_peak, 1),
        "by_carbonate_material": dict(sorted(by_material.items())),
    }


__all__ = [
    "LimeBurnCue",
    "install_lime_burning", "lime_burning_cue_for_chunk", "prospect_lime_burning",
    "burn_preview", "discover_burning_sites_by_sight", "best_burning_site_near",
    "lime_burning_summary",
    "calcination_onset_c", "calcination_extent", "quicklime_quality",
    "CALCINATION_ONSET_FLUXED_C", "CALCINATION_ONSET_PURE_C", "CALCINATION_FULL_C",
    "SOUND_CALCINATION", "MORTAR_CALCINATION", "UNDERBURNT_CEILING",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
