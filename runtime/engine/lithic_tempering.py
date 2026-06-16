"""Genesis Engine — Substrate capability : trempe thermique de la pierre (Cap. C8).

**La première capacité de TRANSFORMATION** (recommandation audit J+5 §7-a). C1→C7
ont rendu *perceptibles* (et, pour C7, *amorçables*) les matières et le feu de
l'âge de pierre. C8 est la **première utilisation actionnable** qui *transforme*
une matière en une meilleure : on **chauffe une pierre siliceuse** (silex/chert)
dans un foyer pour **améliorer sa taille** — la plus ancienne pyrotechnologie
connue après le feu lui-même.

**Règle invariante du projet** (cf. ``surface_mineralization`` (C1),
``lithic_outcrop`` (C2), …, ``fire_ignition`` (C7)) : rien n'est scripté. Un agent
ne *sait* pas qu'on « traite la pierre par la chaleur ». Il **VOIT** un silex
qu'il taille déjà (C2), il **SAIT faire du feu** ici (C7) — et, en laissant par
hasard un nodule dans la braise, il **découvre** que le silex chauffé se débite
plus facilement et donne des bords plus nets. Ce module n'expose qu'un **signal
physique véridique** : *cette pierre-ci, chauffée, deviendrait taillable à tel
point*. Le four, l'enfouissement sous le foyer, la durée de chauffe, le
refroidissement lent — toute la chaîne opératoire reste **émergente**.

Pourquoi la trempe thermique — la première pyrotechnologie
----------------------------------------------------------
Le feu (C7) débloque la **fusion** (cuivre C1), la **combustion** durable
(combustible C4), la **cuisson** (argile C5), la **calcination** (calcaire C6).
Mais sa toute première application sur la pierre elle-même, **antérieure à la
poterie et à la métallurgie**, est le **traitement thermique de la silice
cryptocristalline** : chauffé lentement à ~250–400 °C, le silex/chert se
déshydrate et le gel de silice intergranulaire se réorganise — la fracture
conchoïdale devient **nettement plus régulière** (débitage plus facile, bords
plus tranchants, mais matière plus cassante). C'est attesté à **Pinnacle Point
(Afrique du Sud, ~72 ka)** sur le silcrète, et tout au long du Mésolithique /
Néolithique européen sur le chert. C8 rend cette **affordance de transformation**
perceptible — sans donner la recette.

Ce n'est PAS de la perception passive : c'est une **transformation**
----------------------------------------------------------------------
C1→C6 *montrent* une matière, C7 *amorce* un feu. C8 **change une propriété** :
``base_quality`` → ``tempered_quality``. Le monde s'**engage** sur le résultat
(``tempered_quality`` est déterministe et ground-truthé) : « si tu chauffes cette
pierre, elle deviendra taillable *exactement* à ce point ». L'agent découvre la
corrélation « feu + silex → meilleur outil » en agissant ; on ne la lui souffle
jamais.

N'introduit AUCUN nouveau « tell » minéral — il COMPOSE (garde-fou D8)
---------------------------------------------------------------------
Comme C7, ce module **ne surface aucune nouvelle matière**, n'a **pas** de table
``_PROFILE`` et **ne crée aucune entrée** ``PY_TO_RUST`` / ``PY_CATALOGUE_ONLY``
(cf. ``test_geology_cross_language_contract``). Il *lit* deux capacités déjà
classées cross-langage :

* la **pierre taillable** — exactement la pétrologie de C2 ``lithic_outcrop``
  (``lithic_cue_for_chunk`` : matière, classe de fracture, ``knap_quality``,
  incl. l'amélioration silex/chert ``CHERT_BONUS`` en hôte carbonaté) ;
* le **feu** — exactement l'affordance de C7 ``fire_ignition``
  (``ignition_cue_for_chunk`` : un foyer *peut* être fait ici).

Le fichier est volontairement **hors du glob** ``*_outcrop.py`` : ce n'est pas un
affleurement, c'est une transformation. Décision asservie par
``test_introduces_no_new_tell`` (garde-fou D8 respecté par composition).

Quelle silice répond à la chaleur — et laquelle ment
----------------------------------------------------
* **Silex / chert** (silice *cryptocristalline* — modélisé par ``quartz`` bonifié
  en hôte carbonaté côté C2) : **forte** réponse (``_TEMPER_GAIN["chert"]``). La
  matière reine du traitement thermique préhistorique.
* **Quartz / quartzite** (silice *macrocristalline*, hors hôte carbonaté) :
  réponse **modeste** — la roche est plus grossière, le gain réel est moindre.
* **Obsidienne** (déjà du *verre volcanique*) : **AUCUN** gain. C'est le mensonge
  que cette capacité rend visible : l'obsidienne est la *meilleure* pierre à
  tailler (``base_quality`` 1,0) et semble donc la candidate idéale au feu — mais
  la chauffer ne l'améliore pas (elle est déjà parfaite) et risque de la fendre.
  ``temperable=False``, raison explicite.
* **Pierre non conchoïdale** (basalte, ardoise, calcaire…) : pas de bord
  tranchant à gagner par la chaleur → pas d'affordance de trempe.

Effet 1+1>2 et « le monde ne ment jamais »
------------------------------------------
La trempe n'est possible QUE là où **les deux** ingrédients coexistent réellement
dans la même colonne : une pierre siliceuse réactive (C2) **ET** un feu faisable
(C7). Un silex dans une jungle détrempée (pas de feu, C7 muet) n'est pas
trempable *ici* ; une obsidienne au coin d'un foyer non plus (rien à gagner). Si
``temper_cue_for_chunk`` renvoie une indication, ``temperable`` est vrai et le
gain est **ground-truthé** : la pierre existe (C2 le prouve sur la même colonne
que ``mine_at``) et le feu est faisable (C7 le prouve). La réciproque reste
*faible* (pas d'affordance ⇏ pas de pierre) — on ne donne pas la carte.

Déterminisme
------------
Pur : composition de ``lithic_cue_for_chunk`` (C2) et ``ignition_cue_for_chunk``
(C7), tous deux ``prf_rng`` / dérivés du seed. Aucun RNG nouveau. Bit-identique
entre deux runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — la trempe est une lecture dérivée
du substrat (pierre + feu), comme C1→C7.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape
(chunk → affordance de transformation), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from engine.geology import chunk_geology, install_geology
from engine.world import CHUNK_SIDE_M, world_to_chunk
# Single sources of truth — reused verbatim, never re-modelled (garde-fou D8).
import engine.lithic_outcrop as lo      # C2 — the tool-stone & its knap petrology
import engine.fire_ignition as fi       # C7 — the fire-making affordance

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# Post-treatment knapping quality never beats fresh obsidian (1.0): heat-treated
# chert *approaches* glass-grade fracture but stays a hair below, and grows more
# brittle. This is the ceiling the world commits to.
TEMPER_CEILING = 0.95

# Additive Δ knap_quality the world grants when a heat-responsive silica is
# correctly heat-treated, keyed by silica character. Cryptocrystalline chert/flint
# responds strongly (the prehistoric workhorse of heat treatment); macrocrystalline
# quartz/quartzite responds modestly; obsidian (already glass) and non-silica are
# absent (gain 0). These are intrinsic to the stone — the fire only *enables* the
# transformation, it does not change the chemistry.
_TEMPER_GAIN: Dict[str, float] = {
    "chert":     0.20,   # cryptocrystalline silica (flint/chert/silcrete) — strong
    "quartzite": 0.12,   # macrocrystalline quartz — modest
}
_MAX_GAIN = max(_TEMPER_GAIN.values())


@dataclass(frozen=True)
class TemperCue:
    """A truthful heat-treatment (lithic-tempering) affordance at one chunk.

    What an agent *could* discover by leaving the stone it already knaps (C2) in
    the fire it already makes (C7): the silica gets easier to flake. It is NOT
    handed to the agent as "roast your flint to improve it" — the agent must learn
    the heat→edge correlation by acting. ``base_quality`` / ``tempered_quality``
    are the ground truth the world commits to (doing it yields exactly this).
    """
    coord: Tuple[int, int, int]
    biome: int
    # raw stone (read from C2 lithic_outcrop)
    stone_material: str           # ground-truth stone (e.g. "quartz", "obsidian")
    stone_label: str              # human label of the perceived outcrop
    silica_kind: str              # "chert" | "quartzite" | "obsidian" | "none"
    base_quality: float           # C2 intrinsic knap quality before treatment
    collect_depth_m: float        # depth that lands in the proving C2 layer
    # fire (read from C7 fire_ignition)
    fire_method: str              # easiest ignition method available here
    fire_confidence: float        # C7 reliability of making a fire here [0,1]
    # transformation outcome (the truth the world commits to)
    temperable: bool              # responsive silica AND a fire is makeable here
    tempered_quality: float       # post-treatment knap quality [0,1]
    quality_gain: float           # tempered_quality - base_quality (> 0)
    confidence: float             # reliability of achieving the gain [0,1]


# ---------------------------------------------------------------------------
# Core derivation — transformation outcome from C2 stone × C7 fire.
# ---------------------------------------------------------------------------

def _silica_kind(material: str, knap_class, carbonate_host: bool) -> str:
    """Classify a tool-stone's response to heat treatment.

    Only **conchoidal silica** responds. ``quartz`` in a carbonate host is the
    cryptocrystalline flint/chert C2 already upgrades (``CHERT_BONUS``) — strong
    responder; raw ``quartz`` is macrocrystalline quartzite — modest; obsidian is
    already glass — no gain; anything else does not temper for an edge.
    """
    if knap_class != lo.KnapClass.CONCHOIDAL:
        return "none"
    if material == "obsidian":
        return "obsidian"
    if material == "quartz":
        return "chert" if carbonate_host else "quartzite"
    return "none"


def tempered_quality(base_quality: float, silica_kind: str) -> float:
    """Single source of truth for the post-treatment knapping quality.

    Deterministic and bounded by ``TEMPER_CEILING``. A non-responsive stone
    (obsidian / non-silica) returns its ``base_quality`` unchanged. Any real
    action module that *applies* tempering MUST read this function, so the world
    never lies about what heat treatment yields.
    """
    gain = _TEMPER_GAIN.get(silica_kind, 0.0)
    if gain <= 0.0:
        return float(base_quality)
    return float(min(TEMPER_CEILING, base_quality + gain))


def _cue_from_inputs(coord, lithic_cue, fire_cue, carbonate_host: bool
                     ) -> Optional[TemperCue]:
    """Pure derivation. Emits a cue iff the site is **temperable** — a
    heat-responsive silica stone (C2) AND a makeable fire (C7) coexist here. The
    1+1>2 gate: either ingredient missing ⇒ no transformation affordance."""
    if lithic_cue is None:
        return None
    material = lithic_cue.material
    base = float(lithic_cue.knap_quality)
    kind = _silica_kind(material, lithic_cue.knap_class, carbonate_host)
    gain_const = _TEMPER_GAIN.get(kind, 0.0)
    fire_available = fire_cue is not None
    if gain_const <= 0.0 or not fire_available:
        return None  # obsidian / non-silica, or no fire here — not temperable

    tq = tempered_quality(base, kind)
    gain = tq - base
    fire_conf = float(getattr(fire_cue, "confidence", 0.0))
    # Reliability blends how reliably a fire starts here (C7) with how strongly the
    # stone responds: a marginal friction fire on a quartzite cobble is a chancy
    # gain; a confident hearth on a flint nodule is near-certain.
    confidence = float(min(1.0, fire_conf * (0.6 + 0.4 * min(1.0, gain_const / _MAX_GAIN))))
    method = fire_cue.method.name if hasattr(fire_cue, "method") else "NONE"

    return TemperCue(
        coord=tuple(int(c) for c in coord), biome=int(lithic_cue.biome),
        stone_material=material, stone_label=lithic_cue.label, silica_kind=kind,
        base_quality=float(round(base, 4)),
        collect_depth_m=float(lithic_cue.collect_depth_m),
        fire_method=method, fire_confidence=float(round(fire_conf, 4)),
        temperable=True, tempered_quality=float(round(tq, 4)),
        quality_gain=float(round(gain, 4)), confidence=float(round(confidence, 4)))


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_lithic_tempering(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim`` and
    ensures the composed capabilities (C2 lithic, C7 fire) are installed.

    Adds **zero** per-tick cost: affordances are derived on query and memoised.
    Returns the cache dict (``sim._temper_cue_cache``).
    """
    install_geology(sim)
    lo.install_lithic_outcrop(sim)
    fi.install_fire_ignition(sim)
    cache = getattr(sim, "_temper_cue_cache", None)
    if cache is None:
        cache = {}
        sim._temper_cue_cache = cache
    return cache


def _carbonate_host_at(sim, coord) -> bool:
    g = chunk_geology(sim, coord)
    return bool(lo._has_carbonate_host(g.layers)) if g is not None else False


def temper_cue_for_chunk(sim, coord: Tuple[int, int, int]) -> Optional[TemperCue]:
    """Truthful heat-treatment affordance at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, ``temperable`` is True — C2
    ``lithic_cue_for_chunk(sim, coord)`` proves a heat-responsive silica stone is
    reachable shallow in the same column ``mine_at`` reads, and C7
    ``ignition_cue_for_chunk(sim, coord)`` proves a fire can be made here.
    """
    coord = tuple(int(c) for c in coord)
    cache = install_lithic_tempering(sim)
    if coord in cache:
        return cache[coord]
    lithic = lo.lithic_cue_for_chunk(sim, coord)
    fire = fi.ignition_cue_for_chunk(sim, coord)
    carb = _carbonate_host_at(sim, coord)
    cue = _cue_from_inputs(coord, lithic, fire, carb)
    cache[coord] = cue
    return cue


def prospect_tempering(sim, world_x: float, world_y: float) -> Optional[TemperCue]:
    """What an agent standing at world ``(x, y)`` could discover about
    heat-treating the stone here. Returns the cue (gain + truthful outcome) or
    None when nothing temperable is underfoot."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return temper_cue_for_chunk(sim, coord)


def temper_preview(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of whether (and how much) heat treatment would
    improve the stone at ``(x, y)`` — the ground-truthed outcome the perception
    cue must agree with.

    Touches NOTHING (no stone heated, no geology mutated): the truth oracle, not
    the action. Always returns a dict (even when not temperable), naming the
    *missing* ingredient — the honest 'why not'. The lie this cap exposes: an
    obsidian outcrop looks like the prime knapping stone, yet the fire yields it
    no edge gain (``silica_kind == "obsidian"``)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = temper_cue_for_chunk(sim, coord)
    if cue is not None:
        return {"temperable": True, "reason": "ok",
                "stone_material": cue.stone_material,
                "silica_kind": cue.silica_kind,
                "base_quality": cue.base_quality,
                "tempered_quality": cue.tempered_quality,
                "quality_gain": cue.quality_gain,
                "fire_method": cue.fire_method,
                "confidence": cue.confidence,
                "biome": cue.biome}
    # Not temperable — recompute the diagnostic to name the missing ingredient.
    lithic = lo.lithic_cue_for_chunk(sim, coord)
    fire = fi.ignition_cue_for_chunk(sim, coord)
    if lithic is None:
        reason = "no knappable tool-stone here"
        kind = "none"
    else:
        kind = _silica_kind(lithic.material,
                            lithic.knap_class, _carbonate_host_at(sim, coord))
        if kind == "obsidian":
            reason = "stone is already volcanic glass (obsidian) — heat yields no edge gain"
        elif _TEMPER_GAIN.get(kind, 0.0) <= 0.0:
            reason = "stone does not respond to heat treatment (not cryptocrystalline silica)"
        elif fire is None:
            reason = "no fire can be made here to heat-treat the stone"
        else:  # pragma: no cover — temperable would have produced a cue
            reason = "not temperable"
    return {"temperable": False, "reason": reason,
            "silica_kind": kind,
            "stone_material": (lithic.material if lithic is not None else None),
            "has_fire": bool(fire is not None)}


def discover_temper_sites_by_sight(sim, rows: List[int],
                                   perception_radius_m: float = 64.0
                                   ) -> Dict[int, List[TemperCue]]:
    """For each agent ``row``, the heat-treatable sites perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    Turns the static substrate (a silica outcrop + a fire-makeable spot) into a
    **perceivable, actionable** transformation signal — the agent then *chooses*
    to roast the stone. Deterministic order (by chunk distance, then coord).
    """
    out: Dict[int, List[TemperCue]] = {}
    if not rows:
        return out
    install_lithic_tempering(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], TemperCue]] = []
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
                cue = temper_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_temper_site_near(sim, row: int, perception_radius_m: float = 128.0
                          ) -> Optional[TemperCue]:
    """The most rewarding heat-treatment site an agent at ``row`` can perceive —
    the actionable pick (largest ``quality_gain``; tie-break higher confidence,
    then nearest then coord). Returns None when nothing temperable is in sight (a
    physically honest 'no stone worth roasting here')."""
    cues = discover_temper_sites_by_sight(sim, [int(row)], perception_radius_m
                                          ).get(int(row), [])
    if not cues:
        return None
    # already distance-sorted; prefer the biggest gain, then surest fire.
    return max(cues, key=lambda c: (c.quality_gain, c.confidence))


def tempering_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_lithic_tempering(sim)
    by_kind: Dict[str, int] = {}
    n_chunks = 0
    n_temperable = 0
    best_gain = 0.0
    best_tempered = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = temper_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_temperable += 1
        by_kind[cue.silica_kind] = by_kind.get(cue.silica_kind, 0) + 1
        best_gain = max(best_gain, cue.quality_gain)
        best_tempered = max(best_tempered, cue.tempered_quality)
    return {
        "n_chunks": n_chunks,
        "n_chunks_temperable": n_temperable,
        "temperable_rate": round(n_temperable / n_chunks, 4) if n_chunks else 0.0,
        "best_quality_gain": round(best_gain, 4),
        "best_tempered_quality": round(best_tempered, 4),
        "by_silica_kind": dict(sorted(by_kind.items())),
    }


__all__ = [
    "TemperCue",
    "install_lithic_tempering", "temper_cue_for_chunk", "prospect_tempering",
    "temper_preview", "discover_temper_sites_by_sight", "best_temper_site_near",
    "tempering_summary", "tempered_quality",
    "TEMPER_CEILING",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
