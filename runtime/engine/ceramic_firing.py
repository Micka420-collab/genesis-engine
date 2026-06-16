"""Genesis Engine — Substrate capability : cuisson de la céramique (Cap. C9).

**La deuxième capacité de TRANSFORMATION** (après C8 ``lithic_tempering``). C1→C7
ont rendu *perceptibles* (et, pour C7, *amorçables*) les matières et le feu de
l'âge de pierre ; C8 a *transformé* une pierre (trempe du silex). C9 est la
**transformation néolithique fondatrice** : on **cuit une argile** (C5) dans un
**feu** (C7) — et la terre molle, façonnée puis chauffée, devient **céramique**
irréversible. C'est le matériau qui *contient* tous les autres (l'eau C3, le grain,
le métal fondu) : le récipient qui rend le stockage — donc le surplus, donc la
sédentarité — possible.

**Règle invariante du projet** (cf. ``surface_mineralization`` (C1) …
``lithic_tempering`` (C8)) : rien n'est scripté. Un agent ne *sait* pas qu'« on
cuit l'argile pour faire un pot ». Il **VOIT** une berge d'argile qu'il malaxe
déjà (C5), il **SAIT faire du feu** ici (C7) — et en oubliant par hasard une
boulette d'argile séchée dans la braise, il **découvre** qu'elle durcit *pour
toujours*, ne se redélite plus à l'eau, et tient un liquide. Ce module n'expose
qu'un **signal physique véridique** : *cette argile-ci, cuite dans le feu
faisable ici, donnerait une poterie de telle qualité, cuite à tel point*. La
boulette, le colombin, le tour, le four — toute la chaîne opératoire reste
**émergente**.

Pourquoi la cuisson — la transformation qui change le matériau, pas son tranchant
---------------------------------------------------------------------------------
C8 améliore une pierre (gain marginal sur ``knap_quality``). C9 fait bien plus :
elle **crée un matériau qui n'existe pas dans la nature**. L'argile crue, séchée,
se redélite à la première pluie ; cuite au-delà de ~550–600 °C, la **déshydroxy­
lation** de l'illite/kaolinite est irréversible et les grains **frittent** — la
terre devient pierre artificielle. C'est, après le feu lui-même, l'acte
pyrotechnologique le plus lourd de conséquences de la préhistoire.

Ce n'est PAS de la perception passive : c'est une **transformation**
----------------------------------------------------------------------
C1→C6 *montrent* une matière, C7 *amorce* un feu, C8 *trempe* une pierre. C9
**change l'état d'une matière** : argile crue → tesson cuit. Le monde s'**engage**
sur le résultat (``ware_quality`` / ``firedness`` déterministes et ground-truthés)
: « si tu cuis cette argile dans ce feu, elle deviendra une poterie *exactement* de
ce niveau ». L'agent découvre la corrélation « argile + feu → récipient durable »
en agissant ; on ne la lui souffle jamais.

N'introduit AUCUN nouveau « tell » minéral — il COMPOSE (garde-fou D8)
---------------------------------------------------------------------
Comme C7 et C8, ce module **ne surface aucune nouvelle matière**, n'a **pas** de
table ``_PROFILE`` et **ne crée aucune entrée** ``PY_TO_RUST`` / ``PY_CATALOGUE_ONLY``
(cf. ``test_geology_cross_language_contract``). Il *lit* deux capacités déjà
classées cross-langage :

* l'**argile** — exactement la pétrologie de C5 ``clay_outcrop`` (``clay_cue_for_chunk``
  : matière, ``pottery_grade``, ``ceramic_grade``, fenêtre de plasticité
  d'Atterberg, incl. le tell kaolin ``fine_clay`` byte-exact) ;
* le **feu** — exactement l'affordance de C7 ``fire_ignition``
  (``ignition_cue_for_chunk`` : un foyer *peut* être fait ici, et son ``fine_fuel``
  gouverne la température de pointe atteinte).

Le fichier est volontairement **hors du glob** ``*_outcrop.py`` : ce n'est pas un
affleurement, c'est une transformation. Décision asservie par
``test_introduces_no_new_tell`` (garde-fou D8 respecté par composition — la 3ᵉ
fois après C7 et C8).

Physique de la cuisson — la veille 2026-06-16 (archéométrie céramique)
----------------------------------------------------------------------
La cuisson est **gouvernée par la température**, jamais arbitraire (méta-règle du
substrat). Deux quantités physiques se rencontrent :

1. **Température de pointe du feu ouvert** (``open_fire_peak_temp_c``). Le seul
   « four » disponible depuis C7 seul est un **feu nu** (foyer / fosse) : pas
   d'enceinte, pas de tirage. La littérature (Gibson & Woods *Bonfire*, EXARC
   2025, expériences Santa Margarida) place un feu ouvert entre **~600 °C** (le
   plancher où une terre commune cuit, *« earthenware fired as low as 600 °C »*)
   et **~850 °C** (plafond honnête d'un grand feu de plein air ; les fosses
   gérées atteignent ~950 mais c'est déjà presque un four). On interpole sur la
   **charge de combustible fin** (``fine_fuel`` de C7) : plus de combustible →
   feu plus chaud et plus durable.

2. **Température de maturation de l'argile** (``clay_maturation_temp_c``). Chaque
   argile fritte/mûrit à une température caractéristique :
   * **terre commune ferrugineuse / schisteuse** (``shale``, ``ceramic_grade``
     False) — fondants (Fe, chaux, alcalins) **abaissent** le point de
     vitrification : mûrit bas (~700 °C). C'est pourquoi la poterie a été
     inventée d'innombrables fois, partout : la terre banale **cuit dans un simple
     feu de camp**.
   * **kaolin / argile plastique** (``fine_clay``, ``ceramic_grade`` True) —
     **réfractaire** : il faut ~1200–1300 °C pour la mûrir/vitrifier. Dans un feu
     ouvert (≤ ~850 °C) elle reste **sous-cuite** : tesson crayeux, blanc,
     friable, fragile.

``firedness = min(1, peak / maturation)`` mesure à quel point l'argile a mûri.
Au-dessus de ``SOUND_MATURATION`` le tesson est **sain** (récipient utilisable,
poreux) ; en-dessous il est **sous-cuit** (crayeux, se délite encore).

Le mensonge rendu visible — l'inversion réfractaire (le pendant de l'obsidienne C8)
-----------------------------------------------------------------------------------
C8 : l'obsidienne *semble* la pierre idéale (``base_quality`` 1,0) mais la chauffer
ne gagne **rien** (déjà du verre). C9 expose l'inverse symétrique : le **kaolin**
*semble* la meilleure argile (``pottery_grade`` 0,85, ``ceramic_grade`` True — il
*peut* vitrifier en poterie étanche) et **attire donc le potier** — mais dans un
**feu ouvert** il **sous-cuit** et donne un objet **pire** qu'une humble terre
schisteuse cuite à cœur. La leçon émergente que ``best_firing_site_near`` enseigne
(il préfère la plus haute ``ware_quality``) : **cuis la terre banale, pas la belle
argile blanche** — tant que tu n'as qu'un feu nu. Réaliser le potentiel du kaolin
exigera un **four** (≥ ~1100 °C) — une capacité future. Le monde ne ment pas : il
montre l'étanchéité comme un *potentiel* (``vitrifies_if_kiln_fired``) que **ce**
feu **ne réalise pas** (``watertight`` toujours False en feu ouvert).

Effet 1+1>2 et « le monde ne ment jamais »
------------------------------------------
La cuisson n'est possible QUE là où **les deux** ingrédients coexistent réellement
dans la même colonne : une argile (C5) **ET** un feu faisable (C7). Une argile
dans une jungle détrempée (pas de feu, C7 muet) n'est pas cuisible *ici* ; un feu
sur une dalle rocheuse sans argile non plus. Si ``firing_cue_for_chunk`` renvoie
une indication, ``fireable`` est vrai et le résultat est **ground-truthé** :
l'argile existe (C5 le prouve sur la même colonne que ``mine_at``) et le feu est
faisable (C7 le prouve). La réciproque reste *faible* (pas d'affordance ⇏ pas
d'argile) — on ne donne pas la carte. La fenêtre de plasticité d'Atterberg (C5)
est reportée en *garde honnête* : une argile hors fenêtre est cuisible mais il
faut d'abord la **mouiller & corroyer** (``must_wet_clay_first`` — lien implicite
à l'eau C3) ou la **laisser drainer** (``must_dry_clay_first``).

Déterminisme
------------
Pur : composition de ``clay_cue_for_chunk`` (C5) et ``ignition_cue_for_chunk``
(C7), tous deux ``prf_rng`` / dérivés du seed. Aucun RNG nouveau. Bit-identique
entre deux runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — la cuisson est une lecture dérivée
du substrat (argile + feu), comme C1→C8.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape
(chunk → affordance de transformation), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from engine.world import CHUNK_SIDE_M, world_to_chunk
# Single sources of truth — reused verbatim, never re-modelled (garde-fou D8).
import engine.clay_outcrop as cl       # C5 — the clay & its pottery petrology
import engine.fire_ignition as fi      # C7 — the fire-making affordance

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# --- Open-fire peak temperature (°C). The only "kiln" available from C7 alone is
# a bare bonfire/pit: no enclosure, no forced draught. Archaeometry (veille
# 2026-06-16) brackets a bare open fire between an earthenware-maturing floor and
# an honest open-air ceiling; peak scales with how much fine fuel feeds it.
OPEN_FIRE_MIN_C = 600.0   # earthenware fires as low as 600 °C (bonfire floor)
OPEN_FIRE_MAX_C = 850.0   # honest open-air ceiling (managed pits creep toward ~950)

# --- Clay maturation thresholds (°C): the temperature a clay must reach to fritt
# into a *sound* (usable) body. Keyed on C5's own ``ceramic_grade`` classification
# (single source of truth — no clay-name duplication): a clay that CAN vitrify
# watertight (kaolin) is **refractory** (high-firing); a common iron/lime-fluxed
# earthenware clay matures low and so fires in a simple campfire.
EARTHENWARE_MATURATION_C = 700.0   # fluxed common clay (shale) — low-firing
REFRACTORY_MATURATION_C = 1250.0   # kaolin (fine_clay) — needs a kiln, not a fire

# Fraction of maturation at/above which the ware is *sound* (a usable, if porous,
# vessel). Below it the body is under-fired: chalky, friable, re-slakes in water.
SOUND_MATURATION = 0.85

# Ceiling on the quality an *under-fired* body can reach (a crumbly object is a
# poor vessel however fine the clay). The honest cap on the inversion.
UNDERFIRED_CEILING = 0.25


@dataclass(frozen=True)
class FiringCue:
    """A truthful ceramic-firing (clay-firing) affordance at one chunk.

    What an agent *could* discover by leaving the clay it already shapes (C5) in
    the fire it already makes (C7): the soft earth becomes irreversible pottery.
    It is NOT handed to the agent as "fire your pot at 700 °C" — the agent must
    learn the heat→hardened-vessel correlation by acting. ``firedness`` /
    ``ware_quality`` are the ground truth the world commits to (doing it yields
    exactly this).
    """
    coord: Tuple[int, int, int]
    biome: int
    # raw clay (read from C5 clay_outcrop)
    clay_material: str            # ground-truth clay (e.g. "shale", "fine_clay")
    clay_label: str               # human label of the perceived exposure
    clay_class: str               # C5 ClayClass name
    pottery_grade: float          # C5 intrinsic firing/vitrification rank [0,1]
    ceramic_grade: bool           # C5: CAN vitrify watertight (with enough heat)
    collect_depth_m: float        # depth that lands in the proving C5 layer
    clay_workable_now: bool       # clay in the Atterberg plastic window right now
    must_wet_clay_first: bool     # clay too dry to shape — wet & wedge first
    must_dry_clay_first: bool     # clay a slurry — drain & dry first
    # fire (read from C7 fire_ignition)
    fire_method: str              # easiest ignition method available here
    fire_confidence: float        # C7 reliability of making a fire here [0,1]
    fine_fuel: float              # C7 fine-fuel load (drives the peak temperature)
    # transformation outcome (the truth the world commits to)
    fireable: bool                # clay AND a fire is makeable here
    peak_temp_c: float            # peak temperature this open fire reaches (°C)
    maturation_temp_c: float      # temperature this clay must reach to be sound
    firedness: float              # min(1, peak / maturation) — how fully it matured
    is_sound: bool                # firedness >= SOUND_MATURATION (usable vessel)
    underfired: bool              # not sound (chalky / re-slakes)
    watertight: bool              # open fire never vitrifies → always False
    vitrifies_if_kiln_fired: bool # unrealized kaolin potential (needs a kiln)
    ware_quality: float           # quality of the fired vessel [0,1] (ground truth)
    confidence: float             # reliability of achieving ware_quality [0,1]


# ---------------------------------------------------------------------------
# Single sources of truth — the physics the world commits to.
# ---------------------------------------------------------------------------

def open_fire_peak_temp_c(fine_fuel: float) -> float:
    """Peak temperature (°C) a bare open fire reaches, from its fine-fuel load.

    Deterministic SSOT: linear between ``OPEN_FIRE_MIN_C`` (a feeble fire) and
    ``OPEN_FIRE_MAX_C`` (a fuel-rich one). A bare fire never reaches kiln
    temperatures — that is the honest ceiling this capability commits to."""
    f = min(1.0, max(0.0, float(fine_fuel)))
    return float(OPEN_FIRE_MIN_C + f * (OPEN_FIRE_MAX_C - OPEN_FIRE_MIN_C))


def clay_maturation_temp_c(ceramic_grade: bool) -> float:
    """Maturation temperature (°C) a clay must reach to fritt into a sound body.

    Keyed on C5's ``ceramic_grade`` (SSOT, no clay-name duplication): a clay that
    can vitrify watertight is refractory (kiln-grade kaolin); a common earthenware
    clay matures low (campfire-grade)."""
    return REFRACTORY_MATURATION_C if ceramic_grade else EARTHENWARE_MATURATION_C


def fired_ware_quality(pottery_grade: float, firedness: float) -> float:
    """Single source of truth for the fired-vessel quality.

    Deterministic, bounded [0,1]. A *sound* firing (``firedness`` ≥
    ``SOUND_MATURATION``) yields a vessel of the clay's intrinsic ``pottery_grade``
    (an open fire cannot exceed it — no vitrification). An *under-fired* body is
    capped hard by ``UNDERFIRED_CEILING`` scaled by how close it came: this is the
    refractory inversion — a fine kaolin under-fired in a campfire scores *below*
    a humble earthenware fired to soundness. Any real action module that *fires*
    clay MUST read this function, so the world never lies about what a fire yields.
    """
    pg = min(1.0, max(0.0, float(pottery_grade)))
    fd = min(1.0, max(0.0, float(firedness)))
    if fd >= SOUND_MATURATION:
        return pg
    # under-fired: crumbly object, capped low and scaled by maturation progress.
    return float(pg * UNDERFIRED_CEILING * (fd / SOUND_MATURATION))


# ---------------------------------------------------------------------------
# Core derivation — transformation outcome from C5 clay × C7 fire.
# ---------------------------------------------------------------------------

def _cue_from_inputs(coord, clay_cue, fire_cue) -> Optional[FiringCue]:
    """Pure derivation. Emits a cue iff the site is **fireable** — a clay (C5)
    AND a makeable fire (C7) coexist here. The 1+1>2 gate: either ingredient
    missing ⇒ no firing affordance."""
    if clay_cue is None or fire_cue is None:
        return None

    fine_fuel = float(getattr(fire_cue, "fine_fuel", 0.0))
    peak = open_fire_peak_temp_c(fine_fuel)
    maturation = clay_maturation_temp_c(bool(clay_cue.ceramic_grade))
    firedness = min(1.0, peak / maturation)
    is_sound = firedness >= SOUND_MATURATION
    ware = fired_ware_quality(clay_cue.pottery_grade, firedness)

    fire_conf = float(getattr(fire_cue, "confidence", 0.0))
    # Shaping readiness (C5 Atterberg window): an out-of-window clay can still be
    # fired, but only after wetting/drying it — a chore that lowers confidence.
    shaping = 1.0 if clay_cue.workable_now else 0.7
    confidence = float(min(1.0, fire_conf * shaping * (0.5 + 0.5 * firedness)))
    method = fire_cue.method.name if hasattr(fire_cue, "method") else "NONE"

    return FiringCue(
        coord=tuple(int(c) for c in coord), biome=int(clay_cue.biome),
        clay_material=clay_cue.material, clay_label=clay_cue.label,
        clay_class=clay_cue.clay_class.name,
        pottery_grade=float(round(clay_cue.pottery_grade, 4)),
        ceramic_grade=bool(clay_cue.ceramic_grade),
        collect_depth_m=float(clay_cue.collect_depth_m),
        clay_workable_now=bool(clay_cue.workable_now),
        must_wet_clay_first=bool(clay_cue.too_dry_to_shape),
        must_dry_clay_first=bool(clay_cue.too_wet_slurry),
        fire_method=method, fire_confidence=float(round(fire_conf, 4)),
        fine_fuel=float(round(fine_fuel, 4)),
        fireable=True, peak_temp_c=float(round(peak, 1)),
        maturation_temp_c=float(maturation),
        firedness=float(round(firedness, 4)),
        is_sound=bool(is_sound), underfired=bool(not is_sound),
        watertight=False,  # an open fire never vitrifies (no watertight ware)
        vitrifies_if_kiln_fired=bool(clay_cue.ceramic_grade),
        ware_quality=float(round(ware, 4)),
        confidence=float(round(confidence, 4)))


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_ceramic_firing(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim`` and
    ensures the composed capabilities (C5 clay, C7 fire) are installed.

    Adds **zero** per-tick cost: affordances are derived on query and memoised.
    Returns the cache dict (``sim._firing_cue_cache``).
    """
    cl.install_clay_outcrop(sim)
    fi.install_fire_ignition(sim)
    cache = getattr(sim, "_firing_cue_cache", None)
    if cache is None:
        cache = {}
        sim._firing_cue_cache = cache
    return cache


def firing_cue_for_chunk(sim, coord: Tuple[int, int, int]) -> Optional[FiringCue]:
    """Truthful ceramic-firing affordance at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, ``fireable`` is True — C5
    ``clay_cue_for_chunk(sim, coord)`` proves a clay is reachable shallow in the
    same column ``mine_at`` reads, and C7 ``ignition_cue_for_chunk(sim, coord)``
    proves a fire can be made here.
    """
    coord = tuple(int(c) for c in coord)
    cache = install_ceramic_firing(sim)
    if coord in cache:
        return cache[coord]
    clay = cl.clay_cue_for_chunk(sim, coord)
    fire = fi.ignition_cue_for_chunk(sim, coord)
    cue = _cue_from_inputs(coord, clay, fire)
    cache[coord] = cue
    return cue


def prospect_firing(sim, world_x: float, world_y: float) -> Optional[FiringCue]:
    """What an agent standing at world ``(x, y)`` could discover about firing the
    clay here. Returns the cue (ware quality + truthful outcome) or None when
    nothing fireable is underfoot."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return firing_cue_for_chunk(sim, coord)


def firing_preview(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of whether (and how well) the clay at ``(x, y)``
    would fire — the ground-truthed outcome the perception cue must agree with.

    Touches NOTHING (no clay dug, no fire lit, no geology mutated): the truth
    oracle, not the action. Always returns a dict (even when not fireable), naming
    the *missing* ingredient — the honest 'why not'. The lie this cap exposes: a
    fine kaolin outcrop looks like the prime potter's clay, yet an open fire
    under-fires it (``underfired`` True, ``vitrifies_if_kiln_fired`` True — it
    *would* be watertight, but only in a kiln this fire is not)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = firing_cue_for_chunk(sim, coord)
    if cue is not None:
        return {"fireable": True, "reason": "ok",
                "clay_material": cue.clay_material,
                "pottery_grade": cue.pottery_grade,
                "peak_temp_c": cue.peak_temp_c,
                "maturation_temp_c": cue.maturation_temp_c,
                "firedness": cue.firedness,
                "is_sound": cue.is_sound,
                "underfired": cue.underfired,
                "watertight": cue.watertight,
                "vitrifies_if_kiln_fired": cue.vitrifies_if_kiln_fired,
                "ware_quality": cue.ware_quality,
                "fire_method": cue.fire_method,
                "must_wet_clay_first": cue.must_wet_clay_first,
                "must_dry_clay_first": cue.must_dry_clay_first,
                "confidence": cue.confidence,
                "biome": cue.biome}
    # Not fireable — recompute the diagnostic to name the missing ingredient.
    clay = cl.clay_cue_for_chunk(sim, coord)
    fire = fi.ignition_cue_for_chunk(sim, coord)
    if clay is None:
        reason = "no clay here to shape and fire"
    elif fire is None:
        reason = "no fire can be made here to fire the clay"
    else:  # pragma: no cover — both present would have produced a cue
        reason = "not fireable"
    return {"fireable": False, "reason": reason,
            "clay_material": (clay.material if clay is not None else None),
            "has_clay": bool(clay is not None),
            "has_fire": bool(fire is not None)}


def discover_firing_sites_by_sight(sim, rows: List[int],
                                   perception_radius_m: float = 64.0
                                   ) -> Dict[int, List[FiringCue]]:
    """For each agent ``row``, the fireable sites perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    Turns the static substrate (a clay bank + a fire-makeable spot) into a
    **perceivable, actionable** transformation signal — the agent then *chooses*
    to shape and fire the clay. Deterministic order (by chunk distance, then coord).
    """
    out: Dict[int, List[FiringCue]] = {}
    if not rows:
        return out
    install_ceramic_firing(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], FiringCue]] = []
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
                cue = firing_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_firing_site_near(sim, row: int, perception_radius_m: float = 128.0,
                          *, require_sound: bool = False) -> Optional[FiringCue]:
    """The most rewarding firing site an agent at ``row`` can perceive — the
    actionable pick (highest ``ware_quality``; tie-break higher confidence, then
    nearest then coord).

    This is where the refractory inversion teaches: preferring ``ware_quality``,
    the agent learns to fire the humble earthenware clay (sound) over the pretty
    kaolin (under-fired) — until it has a kiln. ``require_sound`` keeps only
    firings that yield a usable vessel. Returns None when nothing fireable is in
    sight (a physically honest 'no pot to be fired here')."""
    cues = discover_firing_sites_by_sight(sim, [int(row)], perception_radius_m
                                          ).get(int(row), [])
    pool = [c for c in cues if c.is_sound] if require_sound else cues
    if not pool:
        return None
    # already distance-sorted; prefer the best ware, then surest firing.
    return max(pool, key=lambda c: (c.ware_quality, c.confidence))


def firing_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_ceramic_firing(sim)
    by_material: Dict[str, int] = {}
    n_chunks = 0
    n_fireable = 0
    n_sound = 0
    n_underfired = 0
    best_ware = 0.0
    best_peak = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = firing_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_fireable += 1
        if cue.is_sound:
            n_sound += 1
        else:
            n_underfired += 1
        by_material[cue.clay_material] = by_material.get(cue.clay_material, 0) + 1
        best_ware = max(best_ware, cue.ware_quality)
        best_peak = max(best_peak, cue.peak_temp_c)
    return {
        "n_chunks": n_chunks,
        "n_chunks_fireable": n_fireable,
        "fireable_rate": round(n_fireable / n_chunks, 4) if n_chunks else 0.0,
        "n_sound": n_sound,
        "n_underfired": n_underfired,
        "best_ware_quality": round(best_ware, 4),
        "best_peak_temp_c": round(best_peak, 1),
        "by_clay_material": dict(sorted(by_material.items())),
    }


__all__ = [
    "FiringCue",
    "install_ceramic_firing", "firing_cue_for_chunk", "prospect_firing",
    "firing_preview", "discover_firing_sites_by_sight", "best_firing_site_near",
    "firing_summary",
    "open_fire_peak_temp_c", "clay_maturation_temp_c", "fired_ware_quality",
    "OPEN_FIRE_MIN_C", "OPEN_FIRE_MAX_C",
    "EARTHENWARE_MATURATION_C", "REFRACTORY_MATURATION_C",
    "SOUND_MATURATION", "UNDERFIRED_CEILING",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
