"""Genesis Engine — Substrate capability : l'ocre broyée (Cap. C18).

**Le 9ᵉ opérateur ORTHOGONAL — BROYER (grind / triturate)** et la **1ʳᵉ avancée de
l'axe symbolique** (le pigment, substrat de la marque/du dessin). C17
``iron_bloomery`` était *fire-based* (D9 redémarré à 1) ; C18 **rompt à nouveau** vers
le non-feu — comme l'a recommandé l'audit J+12 (``R-J12r3-1`` : *« prochaine cap
orthogonale OU non-fire »*). Elle n'allume rien, ne chauffe rien, ne fond rien, ne
consomme aucune géologie : elle ajoute le verbe **broyer** — réduire en poudre une
**terre colorée** que l'altération a déjà concentrée en surface.

C'est le 9ᵉ verbe primitif réellement nouveau : sentir / voir / tâter / **casser**
(C2) / boire / allumer (C7) / **ramasser** (C14) / **sécher au soleil** (C15) /
**broyer** (C18). Le pigment ocre — l'oxyde de fer terreux — est, dans la préhistoire
réelle, la **plus ancienne matière symbolique** : ocre rouge raclée, broyée et
appliquée dès Blombos (~100 ka) et Lomekwi, bien avant la poterie ou le métal. C18 est
donc la **première brique de l'émergence du dessin** (5ᵉ pilier d'émergence audité,
jusqu'ici immobile) : le monde rend perceptible *de quoi* faire une marque ; ce que
l'agent en fait (tracer, signifier) reste **émergent**.

**Règle d'émergence absolue** (cf. ``surface_mineralization`` (C1), ``cryoclasty``
(C14)) : rien n'est scripté. Un agent ne *sait* pas qu'« on broie la terre rouille
pour faire de la peinture rouge ». Il **VOIT** le chapeau de fer rouille (C1, gossan),
il **ramasse** une poignée de cette terre tendre altérée et, en la **frottant** sur une
pierre, il **découvre** qu'elle laisse une trace **rouge** durable (hématite) ou
**noire** (magnétite) — ou *aucune* couleur stable (pyrite, galène). Ce module n'expose
qu'un **signal physique véridique** : *cette terre-ci, broyée, rend tel pigment, de
telle force colorante, ou rien*. Le geste (frotter, mélanger à un liant, tracer) reste
émergent.

Le mensonge rendu visible #9 — le chapeau de fer ment AUSSI au peintre
---------------------------------------------------------------------
C17 a montré l'inversion **à cinq voies** sur le tell gossan pour le **métallurgiste**
(oxyde sain / pyrite red-short / plomb-zinc stérile). C18 prolonge le **même** tell
rouille vers un usage **orthogonal** — et le mensonge se rejoue, différemment :

* **hématite** (``Fe₂O₃``, oxyde) — la terre **rouge** : l'ocre rouge, le pigment le
  plus lightfast et universel. La récompense du peintre. (Chauffée, l'ocre jaune
  goethite vire au rouge — transformation *fire-based* différée honnêtement.)
* **magnétite** (``Fe₃O₄``, oxyde) — la terre **noire** : un noir d'oxyde de fer
  stable, le second pigment minéral. Récompense moindre (chroma plus faible) mais réel.
* **pyrite** (``FeS₂``, sulfure) — riche en fer, **rouille** à l'œil… mais c'est un
  **sulfure** : broyée, elle ne donne **aucun pigment terreux stable** (métallique,
  brassé, elle s'oxyde et ternit). Le mensonge du peintre : rouille ≠ rouge.
* **galène** / **sphalérite** (``PbS`` / ``ZnS``) — **aucun oxyde de fer** : le même
  chapeau rouille coiffe un sulfure de plomb / de zinc → broyé, **pas d'ocre**.

Donc, exactement comme C17 mais pour la couleur : ``best_ochre_site_near`` enseigne
**broie le chapeau oxyde** (rouge hématite, noir magnétite), **ignore** le chapeau
pyriteux / plombo-zincifère. Le monde ne ment pas : la même terre rouille « promet »
visuellement une couleur que seule la fraction **oxyde de fer** tient réellement.

C'est l'EXACT pendant orthogonal de C17 sur la MÊME matière (le gossan C1) :
**chaud → métal** (C17, *fire-based*, mutant) ; **froid, broyé → pigment** (C18,
*non-fire*, non mutant). Une seule lecture du monde, deux civilisations qui en sortent.

N'introduit AUCUN nouveau « tell » minéral — il COMPOSE (garde-fou D8)
---------------------------------------------------------------------
Comme C7→C17, ce module **ne surface aucune nouvelle matière**, n'a **pas** de table
``_PROFILE`` et **ne crée aucune entrée** ``PY_TO_RUST`` / ``PY_CATALOGUE_ONLY`` (cf.
``test_geology_cross_language_contract``). C'est la **12ᵉ** capacité D8-par-composition.
Il *lit* une seule capacité déjà classée cross-langage : le **chapeau de fer** gossan
de C1 ``surface_mineralization`` (``hematite`` / ``magnetite`` / ``pyrite`` — et la
négation visible ``galena`` / ``sphalerite``). La couleur du **pigment** (la poudre
*produite*) est une propriété de **sortie** du broyage (constantes du module, comme
``OXIDE_BLOOM_PURITY`` de C17), **pas** un tell de surface cross-langage : aucune
obligation de palette Rust n'est créée. Le fichier est volontairement **hors du glob**
``*_outcrop.py`` : ce n'est pas un affleurement, c'est un opérateur (broyer).

Périmètre honnête (audit) — non mutant, D10 gelé
------------------------------------------------
L'ocre est la **terre tendre altérée** du chapeau de fer : on en **racle une poignée
en surface** (``collect_depth_m == 0``, signature du verbe *gather/grind* — vs C2 qui
*casse* en profondeur), comme ``cryoclasty`` ramasse un gélifract. ``grind_ochre_at``
est donc un **aperçu non mutant** : il ne consomme NI ``chunk`` NI géologie
(contrairement au ``bloom_at`` mutant de C17 / ``smelt_at`` de C13). On reste dans la
voie perception/orthogonalité que l'audit réclame, sans rouvrir la frontière de
mutation (risque D10 gelé — ``crates/MUTATION-FRONTIER.md`` : un seul point mutant,
``geo.mine_at``).

Déterminisme
------------
L'oracle est pur : composition de ``surface_cue_for_chunk`` (C1) — lui-même ``prf_rng``
/ dérivé du seed — avec des SSOT pures (catégorie + teneur Fe du catalogue minéral,
constantes de pigment du module). Aucun RNG nouveau. Bit-identique entre deux runs de
même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — le pigment est une lecture/transformation
dérivée du substrat (le chapeau de fer altéré), comme C1→C17.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape (chunk → pigment
broyable), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from engine.world import CHUNK_SIDE_M, world_to_chunk
from engine.mineral_catalog import MINERAL_BY_NAME, MineralCategory
# Single source of truth — composed verbatim, never re-modelled (garde-fou D8).
import engine.surface_mineralization as sm  # C1 — the rusty gossan iron-hat surface tell

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# --- Grinding fineness model (dimensionless). Tinting strength of an earth pigment
# rises with how finely it is triturated (finer particles scatter/absorb more light),
# saturating. Even a coarse grind already carries most of the colour, hence a floor.
DEFAULT_FINENESS = 0.7      # a competent hand-grind on a quern stone
FINENESS_FLOOR = 0.4        # fraction of the chroma even a coarse grind delivers

# --- Pigment is the WEATHERED, earthy iron-oxide of the gossan cap; a single grind of
# that soft ochreous earth yields mostly usable powder (the rest is gangue grit).
PIGMENT_RECOVERY = 0.85     # kg of usable pigment powder per kg of ground oxide earth

# --- Below this final pigment quality the powder is too weak / impure to mark with:
# a perceivable rusty earth that nonetheless makes no usable paint (the world's "lie").
MIN_PIGMENT_QUALITY = 0.25

# --- Reference ore fraction at which an oxide cap tints at full richness (mirrors the
# C1 confidence scale). Below it, the cap is leaner and the pigment paler.
RICH_REF = 0.03

# --- Output pigment colours (the GROUND POWDER, not a surface tell). Module physics
# constants — NOT a cross-language palette (no Rust obligation; see module docstring).
RED_OCHRE_RGB = (132, 46, 28)     # hematite Fe2O3 → red ochre (the classic)
BLACK_OXIDE_RGB = (38, 34, 36)    # magnetite Fe3O4 → black iron-oxide pigment

# The gossan group whose minerals carry the rusty iron-hat tell C1 surfaces. Reused,
# not re-listed — these ARE the minerals C1's gossan cue surfaces.
_GOSSAN_GROUP = "gossan"

# Iron-OXIDE minerals → (pigment_class, base_chroma in [0,1], output rgb). ONLY the
# iron oxides give a stable earth pigment (the ochre). NOT named ``_PROFILE`` on
# purpose: this is an OUTPUT-colour map, not a surface "tell" table — the D8 guardrail
# auto-discovers ``_PROFILE`` and this module must declare none (test_introduces_no_new_tell).
_OXIDE_PIGMENT: Dict[str, Tuple[str, float, Tuple[int, int, int]]] = {
    "hematite":  ("red_ochre", 1.00, RED_OCHRE_RGB),
    "magnetite": ("black_oxide", 0.75, BLACK_OXIDE_RGB),
}
# Fallback chroma/colour for any other Fe-oxide host not enumerated above.
_GENERIC_OXIDE_PIGMENT: Tuple[str, float, Tuple[int, int, int]] = (
    "red_ochre", 0.60, RED_OCHRE_RGB)


@dataclass(frozen=True)
class OchreYield:
    """Ground-truth outcome of cold-grinding ``ore_kg`` of one gossan earth at a given
    ``fineness``. Pure SSOT — no rounding, no I/O, trivially unit-testable. The cue and
    ``grind_ochre_at`` both derive from this.

    ``is_pigment`` is True ONLY for an iron OXIDE (the ochre); a sulfide (pyrite) or a
    non-iron gossan (galena/sphalerite) grinds to **no usable pigment** — the lie #9."""
    pigment_class: str             # "red_ochre" | "black_oxide" | "none"
    is_pigment: bool               # an iron-oxide earth pigment was won
    lightfast: bool                # iron oxides are permanent (always True if pigment)
    grind_fineness: float          # how finely the earth was triturated [0,1]
    base_chroma: float             # intrinsic tinting potential of this oxide [0,1]
    tinting_strength: float        # base_chroma scaled by fineness [0,1]
    contained_fe_fraction: float   # catalogue Fe yield per kg of this earth
    pigment_kg: float              # usable pigment powder won (0 if not a pigment)
    hue: Tuple[int, int, int]      # colour of the ground powder ((0,0,0) if none)


# ---------------------------------------------------------------------------
# Single source of truth — the cold-grind pigment physics the world commits to.
# ---------------------------------------------------------------------------

def _tinting(base_chroma: float, fineness: float) -> float:
    """Tinting strength = intrinsic chroma scaled by grind fineness, saturating.
    Monotone in fineness; capped at the oxide's intrinsic chroma (≤ 1)."""
    f = min(1.0, max(0.0, float(fineness)))
    return float(min(1.0, base_chroma * (FINENESS_FLOOR + (1.0 - FINENESS_FLOOR) * f)))


def ochre_grind_yield(ore_mineral: Optional[str], ore_kg: float,
                      *, fineness: float = DEFAULT_FINENESS) -> OchreYield:
    """Deterministic SSOT for the pigment powder a cold grind of one gossan earth yields.

    ``ore_mineral`` is a catalogue name (C1 surfaces ``hematite`` / ``magnetite`` /
    ``pyrite`` — and ``galena`` / ``sphalerite`` — under the one rusty gossan tell). The
    pigment is the **weathered iron OXIDE** itself (ochre): only an oxide of iron yields
    a stable earth pigment (hematite → red, magnetite → black). A **sulfide** (pyrite)
    or a **non-iron** gossan (galena, sphalerite) yields **no pigment** — it grinds to a
    metallic, unstable, colourless-as-paint dust (the lie #9). Tinting strength rises
    with grinding fineness, saturating at the oxide's intrinsic chroma. Any module that
    *actually grinds* pigment MUST read this, so the world never lies about colour."""
    ore_kg = max(0.0, float(ore_kg))
    m = MINERAL_BY_NAME.get(ore_mineral) if ore_mineral else None
    _barren = OchreYield(
        pigment_class="none", is_pigment=False, lightfast=False,
        grind_fineness=min(1.0, max(0.0, float(fineness))),
        base_chroma=0.0, tinting_strength=0.0, contained_fe_fraction=0.0,
        pigment_kg=0.0, hue=(0, 0, 0))
    if m is None:
        return _barren
    contained_fe = float(m.yields_per_kg_ore.get("Fe", 0.0))
    # Only an iron OXIDE is an ochre. Sulfide iron (pyrite) and non-iron (lead/zinc)
    # gossans look rusty but grind to no stable earth pigment.
    if m.category != MineralCategory.OXIDE or contained_fe <= 0.0:
        return _barren
    pclass, base_chroma, rgb = _OXIDE_PIGMENT.get(
        m.name, _GENERIC_OXIDE_PIGMENT)
    tint = _tinting(base_chroma, fineness)
    pigment_kg = ore_kg * PIGMENT_RECOVERY
    return OchreYield(
        pigment_class=pclass, is_pigment=True, lightfast=True,
        grind_fineness=min(1.0, max(0.0, float(fineness))),
        base_chroma=float(base_chroma), tinting_strength=float(tint),
        contained_fe_fraction=contained_fe, pigment_kg=float(pigment_kg), hue=rgb)


@dataclass(frozen=True)
class OchreCue:
    """A truthful ochre-grinding affordance at one chunk.

    What an agent *could* discover by raking the rusty gossan earth C1 shows and grinding
    it: a red (hematite) or black (magnetite) pigment powder — or, for a pyrite / lead /
    zinc gossan, *no usable colour at all*. It is NOT handed to the agent as "grind
    hematite for red paint" — the agent must learn the rusty-earth→colour correlation by
    grinding. Emitted whenever C1 surfaces a **gossan** here; ``is_pigment`` /
    ``pigment_quality`` carry the truth about whether grinding it yields a paint."""
    coord: Tuple[int, int, int]
    biome: int
    mineral: str                   # ground-truth gossan ore C1 surfaces (rusty tell)
    pigment_class: str             # "red_ochre" | "black_oxide" | "none"
    is_pigment: bool               # an iron-oxide earth pigment is winnable here
    usable: bool                   # is_pigment AND pigment_quality ≥ MIN_PIGMENT_QUALITY
    lightfast: bool                # the pigment is permanent (iron oxide)
    base_chroma: float             # intrinsic tinting potential of the oxide [0,1]
    tinting_strength: float        # chroma at the default grind fineness [0,1]
    richness: float                # cap-richness factor from C1 mass_fraction [0,1]
    pigment_quality: float         # tinting_strength × richness — the actionable score
    contained_fe_fraction: float   # catalogue Fe per kg (hematite 0.70, magnetite 0.72)
    hue: Tuple[int, int, int]      # colour of the ground powder
    grind_fineness: float          # the default grind fineness the cue reports
    tell_rgb: Tuple[int, int, int]  # the rusty SURFACE tell C1 shows (the same for all)
    collect_depth_m: float         # 0.0 — surface gather (the orthogonal signature)
    confidence: float              # reliability of perceiving/achieving the outcome [0,1]


# ---------------------------------------------------------------------------
# Core derivation — ochre outcome from a C1 gossan cue.
# ---------------------------------------------------------------------------

def _richness_factor(mass_fraction: float) -> float:
    """Cap-richness factor in [0.5, 1.0] from the C1 ore fraction (mirrors the C1
    confidence scale: a half floor + a richness ramp)."""
    return 0.5 + 0.5 * min(1.0, max(0.0, float(mass_fraction)) / RICH_REF)


def _cue_from_gossan(coord, gossan_cue) -> Optional[OchreCue]:
    """Pure derivation (no ``sim`` — trivially unit-testable, like its siblings).
    Emits a cue iff C1 surfaces a **gossan** here. The cue tells the truth: an oxide
    gossan grinds to pigment (``is_pigment`` True, red/black), a pyrite/lead/zinc gossan
    grinds to nothing (``is_pigment`` False, ``pigment_quality`` 0)."""
    if gossan_cue is None or getattr(gossan_cue, "group", None) != _GOSSAN_GROUP:
        return None
    ore = getattr(gossan_cue, "mineral", None)
    if ore is None:
        return None
    y = ochre_grind_yield(ore, 1.0, fineness=DEFAULT_FINENESS)
    richness = _richness_factor(getattr(gossan_cue, "mass_fraction", 0.0))
    quality = y.tinting_strength * richness if y.is_pigment else 0.0
    usable = bool(y.is_pigment and quality >= MIN_PIGMENT_QUALITY)
    tell_rgb = tuple(int(c) for c in getattr(gossan_cue, "rgb", (150, 75, 40)))
    conf = float(getattr(gossan_cue, "confidence", 0.0))
    confidence = float(min(1.0, conf * (0.5 + 0.5 * (quality if y.is_pigment else 0.0))))
    return OchreCue(
        coord=tuple(int(c) for c in coord),
        biome=int(getattr(gossan_cue, "biome", 0)),
        mineral=str(ore),
        pigment_class=y.pigment_class,
        is_pigment=bool(y.is_pigment),
        usable=usable,
        lightfast=bool(y.lightfast),
        base_chroma=float(round(y.base_chroma, 4)),
        tinting_strength=float(round(y.tinting_strength, 4)),
        richness=float(round(richness, 4)),
        pigment_quality=float(round(quality, 4)),
        contained_fe_fraction=float(round(y.contained_fe_fraction, 4)),
        hue=tuple(int(c) for c in y.hue),
        grind_fineness=float(round(y.grind_fineness, 4)),
        tell_rgb=tell_rgb,
        collect_depth_m=0.0,
        confidence=float(round(confidence, 4)))


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_ochre_grinding(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim`` and ensures the
    composed capability (C1 surface mineralization) is installed. Adds **zero** per-tick
    cost: the oracle is derived on query and memoised. Returns the cache dict
    (``sim._ochre_cue_cache``)."""
    sm.install_surface_mineralization(sim)
    cache = getattr(sim, "_ochre_cue_cache", None)
    if cache is None:
        cache = {}
        sim._ochre_cue_cache = cache
    return cache


def ochre_cue_for_chunk(sim, coord: Tuple[int, int, int]) -> Optional[OchreCue]:
    """Truthful ochre-grinding affordance at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, C1 ``surface_cue_for_chunk(sim, coord)`` is a
    **gossan** whose ``mineral`` equals ``mineral``; ``is_pigment`` is True iff that
    mineral is an iron OXIDE (hematite/magnetite). No gossan here ⇒ None."""
    coord = tuple(int(c) for c in coord)
    cache = install_ochre_grinding(sim)
    if coord in cache:
        return cache[coord]
    gossan = sm.surface_cue_for_chunk(sim, coord)
    cue = _cue_from_gossan(coord, gossan)
    cache[coord] = cue
    return cue


def prospect_ochre(sim, world_x: float, world_y: float) -> Optional[OchreCue]:
    """What an agent standing at world ``(x, y)`` could discover about grinding the rusty
    gossan earth here. Returns the cue (pigment + truthful outcome) or None when no
    gossan is exposed underfoot."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return ochre_cue_for_chunk(sim, coord)


def grind_ochre_at(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of what cold-grinding the gossan earth at ``(x, y)``
    yields — the ground-truthed outcome the perception cue must agree with.

    Touches NOTHING (no earth removed, no geology mutated — unlike C17 ``bloom_at``): it
    is the truth oracle of the GRIND verb, not the act. Always returns a dict (even when
    barren), naming the *why not* — including the painter's lie: a **pyrite** gossan
    reports ``reason='sulfide grinds to no stable pigment'``; a **lead/zinc** gossan
    reports ``reason='gossan caps a non-iron ore (no ochre)'``."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = ochre_cue_for_chunk(sim, coord)
    if cue is None:
        return {"grindable": False, "reason": "no gossan (rusty earth) exposed here",
                "is_pigment": False, "pigment_class": "none",
                "collect_depth_m": 0.0}
    if not cue.is_pigment:
        gloss = ("sulfide grinds to no stable pigment"
                 if MINERAL_BY_NAME.get(cue.mineral)
                 and MINERAL_BY_NAME[cue.mineral].category == MineralCategory.SULFIDE
                 and MINERAL_BY_NAME[cue.mineral].yields_per_kg_ore.get("Fe", 0.0) > 0.0
                 else "gossan caps a non-iron ore (no ochre)")
        return {"grindable": True, "reason": gloss, "is_pigment": False,
                "pigment_class": "none", "mineral": cue.mineral,
                "pigment_quality": 0.0, "collect_depth_m": cue.collect_depth_m}
    return {"grindable": True, "reason": "ok", "is_pigment": True,
            "pigment_class": cue.pigment_class, "usable": cue.usable,
            "mineral": cue.mineral, "hue": cue.hue, "lightfast": cue.lightfast,
            "tinting_strength": cue.tinting_strength, "richness": cue.richness,
            "pigment_quality": cue.pigment_quality,
            "grind_fineness": cue.grind_fineness,
            "collect_depth_m": cue.collect_depth_m, "biome": cue.biome}


def discover_ochre_by_sight(sim, rows: List[int],
                            perception_radius_m: float = 64.0
                            ) -> Dict[int, List[OchreCue]]:
    """For each agent ``row``, the ochre-grinding sites perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    Turns the static gossan field into a **perceivable, actionable** pigment signal — the
    agent then *chooses* to grind. Deterministic order (by chunk distance, then coord)."""
    out: Dict[int, List[OchreCue]] = {}
    if not rows:
        return out
    install_ochre_grinding(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], OchreCue]] = []
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
                cue = ochre_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_ochre_site_near(sim, row: int, perception_radius_m: float = 128.0,
                         *, pigment_class: Optional[str] = None) -> Optional[OchreCue]:
    """The most rewarding **usable** ochre site an agent at ``row`` can perceive — the
    actionable pick (highest ``pigment_quality``; tie-break higher confidence, then
    nearest then coord).

    This is where the oxide-vs-sulfide-vs-non-iron inversion teaches: preferring the
    pigment actually winnable, the agent learns to grind the oxide gossan (red hematite,
    black magnetite) and to ignore the rusty-but-barren pyrite / lead / zinc gossan.
    ``pigment_class`` (e.g. ``"red_ochre"``) keeps only that colour. Returns None when
    nothing usable is in sight."""
    cues = discover_ochre_by_sight(sim, [int(row)], perception_radius_m
                                   ).get(int(row), [])
    pool = [c for c in cues if c.usable]
    if pigment_class is not None:
        pool = [c for c in pool if c.pigment_class == pigment_class]
    if not pool:
        return None
    # already distance-sorted; prefer the strongest pigment, then surest.
    return max(pool, key=lambda c: (c.pigment_quality, c.confidence))


def ochre_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the dashboard /
    smoke journal. Read-only; computes cues lazily."""
    install_ochre_grinding(sim)
    by_class: Dict[str, int] = {}
    by_mineral: Dict[str, int] = {}
    n_chunks = 0
    n_sites = 0
    n_pigment = 0
    n_usable = 0
    n_lie = 0
    best_quality = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = ochre_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_sites += 1
        if cue.is_pigment:
            n_pigment += 1
        else:
            n_lie += 1
        if cue.usable:
            n_usable += 1
        by_class[cue.pigment_class] = by_class.get(cue.pigment_class, 0) + 1
        by_mineral[cue.mineral] = by_mineral.get(cue.mineral, 0) + 1
        best_quality = max(best_quality, cue.pigment_quality)
    return {
        "n_chunks": n_chunks,
        "n_ochre_sites": n_sites,
        "ochre_rate": round(n_sites / n_chunks, 4) if n_chunks else 0.0,
        "n_pigment": n_pigment,
        "n_usable": n_usable,
        "n_lie": n_lie,
        "best_pigment_quality": round(best_quality, 4),
        "by_pigment_class": dict(sorted(by_class.items())),
        "by_mineral": dict(sorted(by_mineral.items())),
    }


__all__ = [
    "OchreYield", "OchreCue",
    "install_ochre_grinding", "ochre_cue_for_chunk", "prospect_ochre",
    "grind_ochre_at", "discover_ochre_by_sight", "best_ochre_site_near",
    "ochre_summary", "ochre_grind_yield",
    "DEFAULT_FINENESS", "FINENESS_FLOOR", "PIGMENT_RECOVERY",
    "MIN_PIGMENT_QUALITY", "RICH_REF",
    "RED_OCHRE_RGB", "BLACK_OXIDE_RGB",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
