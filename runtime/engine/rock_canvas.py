"""Genesis Engine — Substrate capability : la paroi à peindre (Cap. C20).

**La 2ᵉ brique de l'axe SYMBOLIQUE / du dessin** (le 5ᵉ pilier d'émergence). C18
``ochre_grinding`` a livré le **pigment** — la *matière* de la marque (ocre rouge
hématite, noir magnétite). Il manquait son pendant : le **support** — la *paroi* qui
**tient** la marque. C20 le rend perceptible : *cette paroi-ci, ici, accepte-t-elle un
pigment, et une marque y durera-t-elle ?* C'est l'exact pendant de C18 dans le couple
fondateur de l'art pariétal — **pigment × support** — tandis que C19 (fire) était une
métallurgie : C20 **rompt à nouveau vers le non-feu** (D9 1 → 0, alternance honorée) et
diversifie hors du cluster métallurgique C17/C19.

**Règle d'émergence absolue** (cf. ``surface_mineralization`` (C1) … ``ochre_grinding``
(C18)) : rien n'est scripté. Un agent ne *sait* pas qu'« on peint des chevaux sur les
parois calcaires ». Il **VOIT** une paroi blanche (le calcaire de C6), il **tient** un
pigment (C18), et **découvre** en frottant que la trace **prend** sur cette pierre-ci et
**y reste** — ou s'écaille. Ce module n'expose qu'un **signal physique véridique** du
*support* : adhérence (porosité du carbonate) × persistance (stabilité du site). Le
**geste** (tracer, la forme, le sens) reste **émergent** — c'est ``engine.art_discovery``
(couche L4) qui enregistre les traits et nomme l'archétype, sans jamais dire « cheval ».

Pourquoi ce module — il comble le trou L1 SOUS l'art L4
------------------------------------------------------
``engine.art_discovery`` (L4 Feedback, Wave 13) modélise déjà l'**acte** de dessin
(pigment + surface + N traits → empreinte → archétype émergent) avec un dictionnaire
**abstrait** ``PAINTABLE_SURFACES`` (``bedrock_calcite`` 0,95, ``bedrock_granite`` 0,55,
``bedrock_sandstone`` 0,80…). **Mais rien ne rendait perceptible, par lieu, QUELLE paroi
est là, ni si une marque y DURE.** Exactement comme C18 a comblé « quel pigment est ici »
(la matière), C20 comble « quel support est ici, et la marque y tiendra-t-elle » (le
substrat). Il **fonde** la chaîne de caractères ``"bedrock_calcite"`` de l'art L4 dans la
géologie + le climat réels — pont **L1↔L4** : ``CALCITE_ADHESION`` est byte-égale à
``art_discovery.PAINTABLE_SURFACES["bedrock_calcite"]`` (verrouillé par
``test_calcite_adhesion_bridges_art_discovery_l4``), sans **importer** la couche L4 (pas
d'inversion de dépendance : L1 porte la vérité, le test garde L4 calé dessus).

Une vérité de substrat, deux lectures — le combo avec C6
--------------------------------------------------------
C20 **compose C6 ``limestone_outcrop``** (la paroi carbonatée + ses états d'altération).
C6 calculait l'altération pour la **pierre de taille** (``dressable_now`` : se dresse-t-elle
en blocs ?) ; C20 relit la **même** vérité (``weather_state`` ∈ {SOUND, KARST, FROST})
pour une **autre** question : une marque peinte y **dure**-t-elle ? C'est l'effet 1+1>2
signature du projet (comme C15/C16 relisent le climat, C17/C18 relisent le gossan) — une
seule vérité de substrat, deux civilisations.

Physique du support — la veille 2026-06-23 (archéologie pariétale)
-----------------------------------------------------------------
Calculée, jamais arbitraire (méta-règle du substrat). Deux axes **orthogonaux** :

1. **Adhérence** (``adhesion`` ∈ [0,1], gouvernée par la PorOSITÉ du carbonate). *« The
   limestone cave walls provided a suitable porous substrate for the mineral pigments to
   bond effectively »* : le carbonate **fin et poreux** (craie / calcaire pur) agrippe le
   pigment ; le carbonate **dense recristallisé** (marbre poli) moins. Veille D1.
2. **Persistance** (``persistence`` ∈ [0,1], gouvernée par la STABILITÉ du site,
   ``weather_state`` de C6). *« Pigments overlain by whitish calcite deposits — a
   protective veil »* + *« sealed limestone environment, stable T/humidity »* : une paroi
   **SAINE** (sèche/tempérée, stable) développe un **voile de calcite** qui scelle la
   marque → permanence (Lascaux ~17 000 ans). Une paroi **KARST** (dissolution active) ou
   **FROST** (gélifraction, desquamation) **écaille** la marque. Veille D2.

``durability = adhesion × persistence``. Une marque DURE ssi ``durability ≥ MIN_DURABLE``.

Le mensonge rendu visible #11 — la belle paroi qui ne tient pas la marque
------------------------------------------------------------------------
La même falaise blanche conspicue (forte ``adhesion`` — c'est du calcaire) **ment** au
peintre quand elle est instable : KARST (dissolution) ou FROST (gel) → ``persistence``
effondrée → ``durability`` sous le seuil → ``holds_lasting_mark`` False. *« Looks markable
≠ holds a lasting mark »* — la marque prend… puis s'écaille. Seule la paroi **SAINE**
(voile de calcite) garde la marque. Et la **visibilité** ment aussi : un pigment dont la
couleur **épouse** celle du mur (``mark_visibility``) est une vraie peinture mais
**invisible** — c'est le contraste, pas la peinture, qui fait la marque.

N'introduit AUCUN nouveau « tell » — il COMPOSE (garde-fou D8)
-------------------------------------------------------------
Comme C7→C19, ce module **ne surface aucune nouvelle matière**, n'a **pas** de table
``_PROFILE`` et **ne crée aucune entrée** ``PY_TO_RUST`` / ``PY_CATALOGUE_ONLY`` (cf.
``test_geology_cross_language_contract``). C'est la **14ᵉ** capacité D8-par-composition.
Il *lit* une capacité déjà classée cross-langage — la **paroi carbonatée** de C6
``limestone_outcrop`` — et, pour le contraste, les couleurs de pigment **sorties** par C18
``ochre_grinding`` (qui ne sont pas des tells cross-langage). Le fichier est volontairement
**hors du glob** ``*_outcrop.py`` : ce n'est pas un affleurement, c'est un **support**.

Périmètre honnête (audit) — NON MUTANT, D10 gelé
------------------------------------------------
``canvas_preview`` / ``paint_outcome`` sont des **aperçus** : ils ne lisent ni ne mutent la
géologie (la peinture pariétale ne consomme pas la roche). La frontière de mutation reste
**gelée** (``crates/MUTATION-FRONTIER.md`` : un seul point mutant, ``geo.mine_at``).

Déterminisme
------------
L'oracle est pur : composition de ``limestone_cue_for_chunk`` (C6) — lui-même ``prf_rng`` /
dérivé du seed — avec des SSOT pures (adhérence par matériau, persistance par état
d'altération, contraste). Aucun RNG nouveau. Bit-identique entre deux runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — le support est une lecture dérivée du
substrat carbonaté (C6), comme C1→C18.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape (chunk → support),
sans rollout.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from engine.world import CHUNK_SIDE_M, world_to_chunk
# Single source of truth — composed verbatim, never re-modelled (garde-fou D8).
import engine.limestone_outcrop as li   # C6 — the carbonate wall + its weathering states
# (Pigment colours, e.g. from C18 ``ochre_grinding``, enter the contrast helper at the
# call site — this module is deliberately pigment-agnostic, taking any RGB.)

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# The art-layer (L4) surface-vocabulary key a carbonate wall maps to. ALL carbonate
# (limestone / chalk / marble / calcite / dolomite) is a "calcite bedrock" wall.
_CALCITE_SURFACE_KEY = "bedrock_calcite"

# --- Adhesion (pigment grip), governed by the carbonate's POROSITY (veille D1). The
# BEST (chalk-fine, very porous pure limestone) tops out at CALCITE_ADHESION — byte-equal
# with ``art_discovery.PAINTABLE_SURFACES["bedrock_calcite"]`` (the L1↔L4 bridge, locked by
# test). Denser recrystallised carbonate (polished marble) grips less.
CALCITE_ADHESION = 0.95
_ADHESION_BY_MATERIAL: Dict[str, float] = {
    "limestone_pure": 0.95,   # chalk-fine, very porous — the Lascaux ideal (= bridge value)
    "limestone":      0.92,   # common porous limestone
    "calcite":        0.85,   # vein calcite — crystalline, less porous
    "dolomite":       0.85,   # Ca-Mg carbonate, sugary granular
    "marble":         0.70,   # metamorphic, recrystallised dense — polished, low porosity
}
_DEFAULT_ADHESION = 0.90      # any other carbonate

# --- Persistence (does a mark LAST), governed by the SITE STABILITY = C6 weather state
# (veille D2). SOUND → a protective calcite veil forms → millennia (Lascaux). KARST
# (active dissolution) or FROST (cryoclastic spalling) flakes the mark off. Keyed on the
# integer value of ``li.WeatherState`` so no enum is re-declared here.
_PERSISTENCE_BY_WEATHER: Dict[int, float] = {
    int(li.WeatherState.SOUND): 0.90,   # dry/temperate, stable — calcite veil seals it
    int(li.WeatherState.KARST): 0.25,   # humid dissolution — the mark dissolves/flakes
    int(li.WeatherState.FROST): 0.10,   # freeze-thaw spalling — the surface sheds
}

# Below this final durability the wall is perceivable but a painted mark will NOT last
# (it flakes) — the lie #11: a conspicuous pale cliff that does not hold a mark.
MIN_DURABLE = 0.40

# Below this pigment/wall luminance+chroma contrast a real mark is effectively invisible.
MIN_VISIBLE_CONTRAST = 0.15

_MAX_RGB_DIST = math.sqrt(3.0 * 255.0 * 255.0)  # normaliser for Euclidean colour distance


def _luminance(rgb: Tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.299 * float(r) + 0.587 * float(g) + 0.114 * float(b)


def mark_contrast(wall_rgb: Tuple[int, int, int],
                  pigment_rgb: Tuple[int, int, int]) -> float:
    """Perceptual contrast in [0,1] of a pigment mark against a wall colour. Dominated by
    luminance difference (what the eye reads first), with a chroma-distance term. Pure."""
    lum = abs(_luminance(wall_rgb) - _luminance(pigment_rgb)) / 255.0
    eucl = math.sqrt(sum((float(a) - float(b)) ** 2
                         for a, b in zip(wall_rgb, pigment_rgb))) / _MAX_RGB_DIST
    return float(min(1.0, max(0.0, 0.6 * lum + 0.4 * eucl)))


def mark_visibility(wall_rgb: Tuple[int, int, int],
                    pigment_rgb: Tuple[int, int, int]) -> Tuple[float, bool]:
    """(contrast, visible) of a pigment mark on a wall — visible iff contrast ≥ threshold.
    The visibility lie: a pigment matching the wall colour is real paint yet invisible."""
    c = mark_contrast(wall_rgb, pigment_rgb)
    return c, bool(c >= MIN_VISIBLE_CONTRAST)


@dataclass(frozen=True)
class CanvasQuality:
    """Ground-truth markability of one carbonate wall material in one weathering state.
    Pure SSOT — no I/O, trivially unit-testable. ``durability = adhesion × persistence``;
    a mark LASTS iff ``durability ≥ MIN_DURABLE``."""
    surface_key: str               # the L4 art vocabulary key ("bedrock_calcite")
    material: str                  # the carbonate (C6 ground truth)
    adhesion: float                # pigment grip from porosity [0,1]
    persistence: float             # site-stability mark-retention [0,1]
    durability: float              # adhesion × persistence [0,1]
    holds_lasting_mark: bool       # durability ≥ MIN_DURABLE
    weather_state: int             # C6 WeatherState (SOUND/KARST/FROST) integer value


def canvas_quality(material: str, weather_state: int) -> CanvasQuality:
    """Deterministic SSOT for how well a carbonate wall takes and KEEPS a painted mark.

    ``adhesion`` is set by the carbonate's porosity (fine porous chalk grips best, dense
    marble least); ``persistence`` by the site's stability (a SOUND wall grows a calcite
    veil that seals the mark for millennia; a KARST/FROST wall flakes it off). Any module
    that *actually marks* a wall MUST read this, so the world never lies about whether a
    mark will last."""
    adhesion = _ADHESION_BY_MATERIAL.get(str(material), _DEFAULT_ADHESION)
    persistence = _PERSISTENCE_BY_WEATHER.get(int(weather_state), 0.0)
    durability = adhesion * persistence
    return CanvasQuality(
        surface_key=_CALCITE_SURFACE_KEY, material=str(material),
        adhesion=float(adhesion), persistence=float(persistence),
        durability=float(durability),
        holds_lasting_mark=bool(durability >= MIN_DURABLE),
        weather_state=int(weather_state))


@dataclass(frozen=True)
class CanvasCue:
    """A truthful paintable-wall affordance at one chunk.

    What an agent *could* discover by marking the carbonate wall C6 exposes here: the
    pigment takes (adhesion) and — crucially — whether the mark will LAST (durability). It
    is NOT handed to the agent as "paint here"; the agent learns the wall→mark-lasts
    correlation by marking. Emitted iff C6 surfaces a carbonate wall here."""
    coord: Tuple[int, int, int]
    biome: int
    material: str                  # ground-truth carbonate (C6)
    surface_key: str               # L4 art vocabulary ("bedrock_calcite")
    wall_rgb: Tuple[int, int, int]  # perceived pale wall colour (C6) — for contrast
    adhesion: float                # pigment grip [0,1]
    persistence: float             # site-stability retention [0,1]
    durability: float              # adhesion × persistence [0,1]
    holds_lasting_mark: bool       # a painted mark survives here
    weather_state: int             # C6 WeatherState int (SOUND/KARST/FROST)
    sound_wall: bool               # SOUND — calcite veil, durable
    karst_wall: bool               # KARST — dissolution, flakes (the lie)
    frost_wall: bool               # FROST — spalling, flakes (the lie)
    confidence: float              # reliability of the outcome [0,1]


# ---------------------------------------------------------------------------
# Core derivation — canvas cue from a C6 carbonate cue.
# ---------------------------------------------------------------------------

def _cue_from_limestone(coord, lime_cue) -> Optional[CanvasCue]:
    """Pure derivation (no ``sim`` — trivially unit-testable, like its siblings).
    Emits a cue iff C6 surfaces a carbonate wall here. The cue tells the truth: a SOUND
    wall holds a lasting mark; a KARST/FROST wall takes the pigment but flakes it off."""
    if lime_cue is None:
        return None
    material = getattr(lime_cue, "material", None)
    if material is None:
        return None
    ws = int(getattr(lime_cue, "weather_state", li.WeatherState.SOUND))
    q = canvas_quality(material, ws)
    wall_rgb = tuple(int(c) for c in getattr(lime_cue, "rgb", (235, 230, 222)))
    conf = float(getattr(lime_cue, "confidence", 0.0))
    confidence = float(min(1.0, conf * (0.5 + 0.5 * q.persistence)))
    return CanvasCue(
        coord=tuple(int(c) for c in coord),
        biome=int(getattr(lime_cue, "biome", 0)),
        material=str(material),
        surface_key=_CALCITE_SURFACE_KEY,
        wall_rgb=wall_rgb,
        adhesion=float(round(q.adhesion, 4)),
        persistence=float(round(q.persistence, 4)),
        durability=float(round(q.durability, 4)),
        holds_lasting_mark=bool(q.holds_lasting_mark),
        weather_state=ws,
        sound_wall=bool(ws == int(li.WeatherState.SOUND)),
        karst_wall=bool(ws == int(li.WeatherState.KARST)),
        frost_wall=bool(ws == int(li.WeatherState.FROST)),
        confidence=float(round(confidence, 4)))


# ---------------------------------------------------------------------------
# Painting outcome — composes the wall (this cap) with a pigment (C18).
# ---------------------------------------------------------------------------

def paint_outcome(cue: CanvasCue, pigment_rgb: Tuple[int, int, int],
                  *, pigment_lightfast: bool = True) -> Dict[str, object]:
    """**Non-mutating** outcome of marking ``cue``'s wall with a pigment of ``pigment_rgb``.

    Combines the WALL truth (this cap: adhesion × persistence) with the PIGMENT truth (C18:
    lightfastness + hue → contrast). A mark **lasts** iff the wall holds it AND the pigment
    is lightfast; it is **seen** iff the pigment contrasts the wall. The full lie #11: a
    real mark can be (a) made but not last (karst/frost wall), or (b) made but invisible
    (pigment ≈ wall colour). Touches nothing — it is the truth oracle, not the act."""
    contrast, visible = mark_visibility(cue.wall_rgb, pigment_rgb)
    mark_durability = cue.durability * (1.0 if pigment_lightfast else 0.4)
    lasts = bool(cue.holds_lasting_mark and pigment_lightfast)
    return {
        "adhesion": cue.adhesion,
        "persistence": cue.persistence,
        "wall_durability": cue.durability,
        "pigment_lightfast": bool(pigment_lightfast),
        "mark_durability": float(round(mark_durability, 4)),
        "lasts": lasts,
        "contrast": float(round(contrast, 4)),
        "visible": visible,
        "lasting_and_visible": bool(lasts and visible),
        "weather_state": cue.weather_state,
        "material": cue.material,
    }


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_rock_canvas(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim`` and ensures the
    composed capability (C6 limestone outcrop) is installed. Adds **zero** per-tick cost:
    the oracle is derived on query and memoised. Returns the cache dict
    (``sim._canvas_cue_cache``)."""
    li.install_limestone_outcrop(sim)
    cache = getattr(sim, "_canvas_cue_cache", None)
    if cache is None:
        cache = {}
        sim._canvas_cue_cache = cache
    return cache


def canvas_cue_for_chunk(sim, coord: Tuple[int, int, int]) -> Optional[CanvasCue]:
    """Truthful paintable-wall affordance at ``coord`` (or None). Memoised.

    Invariant: if this returns a cue, C6 ``limestone_cue_for_chunk(sim, coord)`` is a
    carbonate wall whose ``material`` equals ``material``; ``holds_lasting_mark`` is True
    iff the wall is SOUND enough (durability ≥ threshold). No carbonate here ⇒ None."""
    coord = tuple(int(c) for c in coord)
    cache = install_rock_canvas(sim)
    if coord in cache:
        return cache[coord]
    lime = li.limestone_cue_for_chunk(sim, coord)
    cue = _cue_from_limestone(coord, lime)
    cache[coord] = cue
    return cue


def prospect_canvas(sim, world_x: float, world_y: float) -> Optional[CanvasCue]:
    """What an agent standing at world ``(x, y)`` perceives of the paintable wall here.
    Returns the cue (pale wall + truthful mark-retention) or None when no carbonate wall is
    exposed underfoot."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return canvas_cue_for_chunk(sim, coord)


def canvas_preview(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of whether the wall at ``(x, y)`` is a paintable canvas —
    the ground-truthed outcome the perception cue must agree with.

    Touches NOTHING (painting does not consume rock — and unlike C17 ``bloom_at`` no
    geology is mutated): the truth oracle, not the act. Always returns a dict (even when
    no wall), naming the *why not* — including the lie #11: a karst/frost carbonate wall
    reports ``markable=True`` but ``holds_lasting_mark=False`` (``reason='wall flakes:
    the mark will not last'``)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = canvas_cue_for_chunk(sim, coord)
    if cue is None:
        return {"markable": False, "reason": "no carbonate wall exposed here",
                "holds_lasting_mark": False}
    reason = "ok" if cue.holds_lasting_mark else (
        "wall flakes: the mark will not last (karst dissolution)" if cue.karst_wall
        else "wall flakes: the mark will not last (frost spalling)" if cue.frost_wall
        else "wall too weak to hold a lasting mark")
    return {"markable": True, "reason": reason, "material": cue.material,
            "surface_key": cue.surface_key, "wall_rgb": cue.wall_rgb,
            "adhesion": cue.adhesion, "persistence": cue.persistence,
            "wall_durability": cue.durability,
            "holds_lasting_mark": cue.holds_lasting_mark,
            "sound_wall": cue.sound_wall, "karst_wall": cue.karst_wall,
            "frost_wall": cue.frost_wall, "biome": cue.biome}


def discover_canvas_by_sight(sim, rows: List[int],
                             perception_radius_m: float = 64.0
                             ) -> Dict[int, List[CanvasCue]]:
    """For each agent ``row``, the paintable walls perceivable within ``perception_radius_m``
    (scans chunks whose centre falls in range).

    Turns the static carbonate field into a **perceivable, actionable** canvas signal — the
    agent then *chooses* to mark. Deterministic order (by chunk distance, then coord)."""
    out: Dict[int, List[CanvasCue]] = {}
    if not rows:
        return out
    install_rock_canvas(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], CanvasCue]] = []
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
                cue = canvas_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_canvas_near(sim, row: int, perception_radius_m: float = 128.0,
                     *, require_lasting: bool = False) -> Optional[CanvasCue]:
    """The best paintable wall an agent at ``row`` can perceive — the actionable pick
    (highest ``durability``; tie-break higher adhesion, then confidence, then nearest).

    This is where the sound-vs-karst/frost inversion teaches: preferring the wall that
    actually KEEPS a mark, the agent learns to paint the sound calcite face and to ignore
    the conspicuous-but-flaking karst/frost cliff. ``require_lasting`` keeps only walls that
    hold a lasting mark. Returns None when nothing matching is in sight."""
    cues = discover_canvas_by_sight(sim, [int(row)], perception_radius_m
                                    ).get(int(row), [])
    pool = cues
    if require_lasting:
        pool = [c for c in pool if c.holds_lasting_mark]
    if not pool:
        return None
    # already distance-sorted; prefer the most durable, then grippiest, then surest.
    return max(pool, key=lambda c: (c.durability, c.adhesion, c.confidence))


def canvas_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the dashboard /
    smoke journal. Read-only; computes cues lazily."""
    install_rock_canvas(sim)
    by_material: Dict[str, int] = {}
    by_weather: Dict[str, int] = {}
    n_chunks = 0
    n_walls = 0
    n_lasting = 0
    n_flaking = 0
    best_durability = 0.0
    _names = {int(li.WeatherState.SOUND): "SOUND", int(li.WeatherState.KARST): "KARST",
              int(li.WeatherState.FROST): "FROST"}
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = canvas_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_walls += 1
        if cue.holds_lasting_mark:
            n_lasting += 1
        else:
            n_flaking += 1
        by_material[cue.material] = by_material.get(cue.material, 0) + 1
        wname = _names.get(cue.weather_state, str(cue.weather_state))
        by_weather[wname] = by_weather.get(wname, 0) + 1
        best_durability = max(best_durability, cue.durability)
    return {
        "n_chunks": n_chunks,
        "n_canvas_walls": n_walls,
        "canvas_rate": round(n_walls / n_chunks, 4) if n_chunks else 0.0,
        "n_lasting": n_lasting,
        "n_flaking": n_flaking,
        "best_durability": round(best_durability, 4),
        "by_material": dict(sorted(by_material.items())),
        "by_weather": dict(sorted(by_weather.items())),
    }


__all__ = [
    "CanvasQuality", "CanvasCue",
    "install_rock_canvas", "canvas_cue_for_chunk", "prospect_canvas",
    "canvas_preview", "paint_outcome", "discover_canvas_by_sight",
    "best_canvas_near", "canvas_summary",
    "canvas_quality", "mark_contrast", "mark_visibility",
    "CALCITE_ADHESION", "MIN_DURABLE", "MIN_VISIBLE_CONTRAST",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
