"""Genesis Engine — Substrate capability : pierre gélifractée (Cap. C14).

**Le 7ᵉ opérateur ORTHOGONAL — RAMASSER (gather).** Réponse directe au verrou
P0 ``R-J8-1`` de l'audit J+8 (``native/world-engine/AUDIT-DELTA-2026-06-18.md``) :
sept capacités consécutives (C7→C13) empilaient toutes sur le **foyer** (allumer).
Cette capacité **rompt le treadmill** : elle n'allume rien, ne chauffe rien, ne
casse rien. Elle ajoute le verbe **ramasser** — collecter une pierre que la
**nature a déjà détachée** par le gel.

**Règle invariante du projet** (cf. ``lithic_outcrop`` (C2), ``water_potability``
(C3)) : rien n'est scripté. Un agent ne *sait* pas que l'éboulis d'un versant
froid recèle des éclats taillables — il **VOIT** un champ de gélifracts (cailloux
anguleux épars au pied d'une pente gelée, un felsenmeer de blocs sur la toundra)
puis décide lui-même d'aller **ramasser**. La découverte est émergente ; ce module
ne fait qu'exposer un **signal physique véridique**.

Pourquoi ce module — et la dette de transparence qu'il ferme
------------------------------------------------------------
La Wave 50 (``engine.frost_weathering``) a livré, le 2026-05-29, l'**observateur**
de cryoclastie : indice de fissuration par le gel (FCI, Walder & Hallet 1985),
masques talus / permafrost / alpin. Mais — comme l'a relevé l'audit (R-J4-1) —
**aucun agent n'a jamais *vu* ce champ** : l'observateur *mesure* le tick, il ne
*sert* personne. Le présent module est la **première consommation agent** du champ
de gel : il lit `frost_weathering.compute_frost_cracking_index` au point où se
trouve l'agent, et en tire un signal de ressource. La cryoclastie passe ainsi du
statut d'instrument de mesure à celui de **fait du monde perceptible**.

Ce n'est PAS un ``*_observer.py`` qui *mesure* le tick — c'est un **signal de monde
interrogeable** que les agents *consomment pour agir*. Coût tick **nul** : les
indices sont calculés paresseusement par chunk et mémorisés. Il échappe au moratoire
observateurs (``CONTRIBUTING.md`` §"Moratoire observateurs").

L'orthogonalité (pourquoi C14 ≠ C2)
-----------------------------------
* **C2 ``lithic_outcrop``** = *casser* un affleurement : la pierre est dans une
  couche (``collect_depth_m > 0``), il faut la débiter au percuteur (percussion).
* **C14 ``cryoclasty``** = *ramasser* un gélifract : la pierre gît **en surface**
  (``collect_depth_m == 0``), déjà détachée par des centaines de cycles gel-dégel.
  Aucune percussion : on se baisse et on prend.

C'est le 7ᵉ verbe primitif réellement nouveau : sentir / voir / tâter / **casser**
(C2) / boire / allumer (C7) / **ramasser** (C14). Le talus périglaciaire est, dans
la préhistoire réelle, une **matière première de choix** : le gel trie et expose
des nucléus sains, prêts à tailler, sans effort d'extraction (Paléolithique de la
ceinture lœssique, sources de silex de versant).

La physique du tri par le gel (gélifraction)
--------------------------------------------
Le gel ne fragmente pas toutes les roches de la même façon (Hall & Thorn ;
French, *The Periglacial Environment*) :

* **Macrogélivation** — détachement de blocs sains le long des fractures :
  roches vitreuses / cryptocristallines / à débit tabulaire (obsidienne, silex,
  ardoise) → **éclats anguleux propres, prêts à tailler**. Bonus.
* **Désagrégation granulaire** — la roche cristalline grenue (granite, gneiss,
  grès) se délite en **arène** (gruss, sable grossier) : abondante à l'œil,
  **inutile au tailleur**. Pénalité forte.
* **Carbonate tendre** (calcaire, marbre) — le gel le réduit en gravats sans
  arête durable. Pénalité.

D'où le **MENSONGE RENDU VISIBLE #5** (pendant de l'obsidienne C8 « déjà verre »,
du kaolin réfractaire C9, du cuivre natif/sulfure C13) : un versant **froid et
raide** sur **granite** offre un éboulis spectaculaire… d'arène stérile. Le même
versant sur **obsidienne / silex** livre des éclats-rasoir prêts à l'emploi.
« Froid + raide » n'est PAS un signal fiable de bonne pierre : l'agent doit
apprendre la corrélation avec le **fabric de la roche**. Le monde montre l'éboulis
(vrai) ; ``clast_quality`` dit la vérité sur son utilité.

Le monde ne ment jamais
-----------------------
Un indice n'est émis QUE si **deux vérités indépendantes** coïncident :
* le **champ de gel** y est réellement actif : ``fci ≥ FROST_ACTIVE_MIN`` (dérivé
  des champs macro ``temp_c`` / ``precip_mm`` / ``biome`` via la Wave 50) ;
* une **lithologie taillable réelle** affleure peu profond (même colonne
  ``chunk_geology`` que lit ``mine_at`` — la roche qui se fait gélifracter).

``clast_quality = base_quality(C2) × frost_response(fabric)`` reflète honnêtement
l'arête qu'on en tirera ; ``workable`` n'est vrai qu'au-dessus de
``MIN_CLAST_QUALITY``. La réciproque est volontairement *faible* (pas de gélifracts
perçus ⇏ pas de pierre) : on ne donne pas la carte des gîtes ; l'agent prospecte.

N'introduit AUCUN nouveau tell
------------------------------
COMPOSE la Wave 50 (champ de gel) × C2 (``lithic_outcrop._PROFILE`` — la même
table de roches taillables). Pas de ``_PROFILE`` propre, pas d'entrée
``PY_TO_RUST`` (garde-fou **D8 — 8ᵉ fois par composition** ; voir
``test_geology_cross_language_contract.py`` et ``test_cryoclasty.py``). Hors glob
``*_outcrop.py`` : le fichier s'appelle ``cryoclasty.py`` à dessein.

Périmètre honnête (audit)
-------------------------
* ``gather_at`` est un **aperçu non mutant** (preview) de ce que ramasser donnerait
  — il ne consomme NI ``chunk`` NI géologie (contrairement au ``smelt_at`` mutant
  de C13). On reste dans la voie perception/orthogonalité que l'audit réclame, sans
  ouvrir davantage la frontière de mutation (risque D10).
* Le champ de gel est dérivé des champs **macro** (Wave 50) échantillonnés au point
  de l'agent ; la pente est dérivée du relief **chunk** (résolution 0,5 m, plus
  fine et plus juste pour un éboulis que la maille macro ~31 km de la Wave 50).

Déterminisme
------------
Pur : fonction des champs macro (issus du seed) + ``chunk_geology`` (``prf_rng``) +
``chunk.height``. Aucun RNG nouveau. Bit-identique entre deux runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — le gélifract est une lecture dérivée
du substrat (champ de gel + géologie), comme C1/C2/C3.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape
(point → indice), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine import frost_weathering as fw
from engine import lithic_outcrop as lo
from engine.geology import chunk_geology, install_geology, StrataLayer
from engine.world import CHUNK_SIDE_M, world_to_chunk
from engine.world_genesis import sample_macro

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# Below this Frost Cracking Index the periglacial process is too weak to detach
# usable clasts: no frost field, no cue (truthful silence). A touch below the
# Wave 50 alpine_fci_min (0.2) so cold deserts / tundra blockfields (felsenmeer,
# cryoturbation) still register — they shatter rock at lower FCI than steep talus.
FROST_ACTIVE_MIN = 0.15

# A frost-clast field is a SURFACE deposit: clasts lie ON the ground, gravity-
# detached by freeze-thaw. ``collect_depth_m == 0`` is the orthogonal signature
# vs C2's "break into an outcrop" (collect_depth_m > 0). This is the 7th verb.
SURFACE_COLLECT_DEPTH_M = 0.0

# Below this final clast quality the debris is grus / rubble (no durable edge):
# perceivable as a frost field, but archaeologically barren — the world's "lie".
MIN_CLAST_QUALITY = 0.30

# FCI at or above which scree is copious (a strong periglacial spot buries the
# slope in clasts; below, the field is sparse and the cue fainter).
ABUNDANT_FCI = 0.30

# --- Zone thresholds: mirror the Wave 50 FrostConfig defaults so the agent
#     perceives exactly the masks the observer computes (talus/alpine/permafrost).
TALUS_SLOPE_DEG = fw.FrostConfig().talus_slope_deg      # 25.0
TALUS_FCI_MIN = fw.FrostConfig().talus_fci_min          # 0.4
ALPINE_ELEV_M = fw.FrostConfig().alpine_elev_m          # 1500.0
ALPINE_FCI_MIN = fw.FrostConfig().alpine_fci_min        # 0.2
PERMAFROST_TEMP_C = fw.FrostConfig().permafrost_temp_c  # -2.0


# Frost-fabric response per material (see module docstring). How a rock breaks
# under freeze-thaw governs whether a frost field yields knappable clasts or
# barren grus. Values are dimensionless multipliers in [0, 1].
_FROST_RESPONSE_BY_MATERIAL: Dict[str, float] = {
    # Conchoidal flakers: frost sorts out sound, sharp clasts (the prize).
    "obsidian": 1.00,
    "quartz": 1.00,
    # Tabular: freeze-thaw splits cleanly along schistosity.
    "slate": 0.95,
    "shale": 0.85,
    # Fine-grained mafic ground-stone: macrogelivation → usable blocks.
    "basalt": 0.70,
    # Coarse crystalline: granular disintegration → grus (sand). Barren.
    "granite": 0.25,
    "gneiss": 0.25,
    "sandstone": 0.20,
    # Soft carbonate: frost-rives to edgeless rubble.
    "limestone": 0.20,
    "marble": 0.20,
}

# Fallback by fracture class for any catalogue material absent above.
_FROST_RESPONSE_BY_CLASS: Dict[int, float] = {
    int(lo.KnapClass.CONCHOIDAL): 0.90,
    int(lo.KnapClass.TABULAR): 0.85,
    int(lo.KnapClass.GROUND): 0.40,
    int(lo.KnapClass.SOFT): 0.20,
}


def _frost_response(material: str) -> float:
    """Fabric-dependent frost-fragmentation factor for ``material`` in [0, 1]."""
    if material in _FROST_RESPONSE_BY_MATERIAL:
        return _FROST_RESPONSE_BY_MATERIAL[material]
    prof = lo._PROFILE.get(material)
    if prof is None:
        return 0.0
    return _FROST_RESPONSE_BY_CLASS.get(int(prof.knap_class), 0.3)


@dataclass(frozen=True)
class FrostClastCue:
    """A truthful frost-shattered tool-stone (gelifract) cue at one chunk.

    ``label``/``rgb``/``zone`` = what an agent *perceives* (an angular scree on
    a cold slope). ``material``/``clast_quality``/``workable`` = the ground truth
    it must agree with. It is NOT handed to the agent as "this is good flint" —
    the agent learns the cold+rock→edge correlation by gathering and knapping
    (emergence). ``collect_depth_m == 0`` marks the orthogonal GATHER verb.
    """
    coord: Tuple[int, int, int]
    material: str               # ground-truth parent rock the clasts are made of
    label: str
    knap_class: lo.KnapClass
    base_quality: float         # C2 intrinsic edge potential of the rock [0, 1]
    frost_response: float       # fabric frost-fragmentation factor [0, 1]
    clast_quality: float        # workable edge potential of the gathered clast
    workable: bool              # clast_quality ≥ MIN_CLAST_QUALITY
    fci: float                  # local Frost Cracking Index (Wave 50) [0, 1]
    slope_deg: float            # local chunk-scale slope (degrees)
    temp_c: float               # local mean annual temperature (°C)
    elevation_m: float          # local elevation (m)
    zone: str                   # "talus" | "alpine" | "permafrost" | "frost_field"
    abundant: bool              # copious scree (talus / strong FCI)
    collect_depth_m: float      # 0.0 — surface gather (the orthogonal signature)
    rgb: Tuple[int, int, int]   # perceived colour of the scree (rock, frost-paled)
    biome: int
    confidence: float           # perceptual confidence in [0, 1]


# ---------------------------------------------------------------------------
# Frost-field access (read the Wave 50 macro field at a point).
# ---------------------------------------------------------------------------

def _resolve_anchor(sim) -> Tuple[Optional[object], Optional[Tuple[float, float]]]:
    """Locate the GenesisWorld + its sim→macro origin (km). Mirrors
    :func:`engine.frost_weathering._resolve_world` but also returns the anchor
    origin needed to map sim metres → macro km."""
    boot = getattr(sim, "_genesis_bootstrap_state", None)
    if boot is not None:
        anchor = getattr(boot, "anchor", None)
        if anchor is not None and getattr(anchor, "world", None) is not None:
            return anchor.world, tuple(anchor.sim_origin_macro_km)
    streamer = getattr(sim, "streamer", None)
    if streamer is not None:
        anchor = getattr(streamer, "genesis", None)
        if anchor is not None and getattr(anchor, "world", None) is not None:
            return anchor.world, tuple(anchor.sim_origin_macro_km)
    return None, None


def _fci_at(temp_c: float, precip_mm: float, biome: int) -> float:
    """Scalar Frost Cracking Index — reuses the Wave 50 physics verbatim
    (window × moisture × biome amplitude), so the agent perceives exactly the
    field the observer measures."""
    val = fw.compute_frost_cracking_index(
        np.array([[temp_c]], dtype=np.float32),
        np.array([[precip_mm]], dtype=np.float32),
        np.array([[int(biome)]], dtype=np.int32),
    )
    return float(val[0, 0])


def _chunk_slope_deg(chunk) -> float:
    """Representative local slope (deg) from the chunk's own relief, at the
    chunk's native resolution — far finer (≈0.5 m cells) than the Wave 50 macro
    grid, hence physically right for scree on a *local* steep face."""
    height = np.asarray(getattr(chunk, "height", None))
    if height.ndim != 2 or height.shape[0] < 2:
        return 0.0
    cell_km = (CHUNK_SIDE_M / float(height.shape[0])) / 1000.0
    slope = fw.compute_slope_field(height.astype(np.float32), cell_km)
    return float(np.mean(slope))


def _frost_paled(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """The perceived colour of frost-shattered scree: the parent rock's hue,
    paled toward frost-grey (angular fresh fracture faces catch light)."""
    pale = (235, 238, 242)
    return tuple(int(round(0.75 * c + 0.25 * p)) for c, p in zip(rgb, pale))


# ---------------------------------------------------------------------------
# Core derivation — pure, testable with synthetic frost inputs.
# ---------------------------------------------------------------------------

def _classify_zone(fci: float, slope_deg: float, temp_c: float,
                   elevation_m: float) -> str:
    """Which Wave 50 periglacial zone the agent stands in (strongest first)."""
    if slope_deg >= TALUS_SLOPE_DEG and fci >= TALUS_FCI_MIN:
        return "talus"            # scree cone / rockfall toe (steep + active)
    if elevation_m >= ALPINE_ELEV_M and fci >= ALPINE_FCI_MIN:
        return "alpine"           # high-altitude active periglacial belt
    if temp_c <= PERMAFROST_TEMP_C:
        return "permafrost"       # continuous-permafrost ground
    return "frost_field"          # cryoturbated blockfield / felsenmeer (flat)


def _clast_from_inputs(coord, layers: List[StrataLayer], biome: int,
                       fci: float, slope_deg: float, temp_c: float,
                       elevation_m: float) -> Optional[FrostClastCue]:
    """Pure derivation of the gelifract cue from explicit frost + geology inputs.

    Returns ``None`` (truthful silence) where the frost field is inactive or no
    knappable lithology crops out shallow. Otherwise the single best-clast
    material wins (highest ``clast_quality``; tie-break shallower, then name)."""
    if fci < FROST_ACTIVE_MIN:
        return None  # not periglacial enough → no frost clasts (truthful)
    carbonate_host = lo._has_carbonate_host(layers)
    best: Optional[Tuple[str, float, float, float]] = None
    best_key: Optional[Tuple[float, float, str]] = None
    for layer in layers:
        if layer.depth_top_m > lo.MAX_OUTCROP_DEPTH_M:
            continue
        for material, _source, base_q in lo._candidates_in_layer(layer, carbonate_host):
            resp = _frost_response(material)
            cq = base_q * resp
            key = (-cq, layer.depth_top_m, material)
            if best_key is None or key < best_key:
                best_key = key
                best = (material, base_q, resp, cq)
    if best is None:
        return None  # no rock fabric to shatter here → silent (truthful)
    material, base_q, resp, cq = best
    prof = lo._PROFILE[material]
    zone = _classify_zone(fci, slope_deg, temp_c, elevation_m)
    workable = cq >= MIN_CLAST_QUALITY
    abundant = (zone == "talus") or (fci >= ABUNDANT_FCI)
    # Confidence rises with how active the field is and how good the clast is;
    # an unmistakable talus of sharp flint reads loud, a sparse grus field faint.
    fci_norm = min(1.0, fci / TALUS_FCI_MIN)
    confidence = float(min(1.0, fci_norm * (0.5 + 0.5 * cq)))
    return FrostClastCue(
        coord=tuple(int(c) for c in coord),
        material=material, label=prof.label, knap_class=prof.knap_class,
        base_quality=float(base_q), frost_response=float(resp),
        clast_quality=float(round(cq, 6)), workable=bool(workable),
        fci=float(round(fci, 6)), slope_deg=float(round(slope_deg, 4)),
        temp_c=float(round(temp_c, 4)), elevation_m=float(round(elevation_m, 4)),
        zone=zone, abundant=bool(abundant),
        collect_depth_m=SURFACE_COLLECT_DEPTH_M,
        rgb=_frost_paled(prof.rgb), biome=int(biome),
        confidence=confidence)


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_cryoclasty(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim``.

    Adds **zero** per-tick cost: cues are derived on query and memoised.
    Returns the cache dict (``sim._cryoclasty_cue_cache``)."""
    install_geology(sim)  # ensure geology state exists
    cache = getattr(sim, "_cryoclasty_cue_cache", None)
    if cache is None:
        cache = {}
        sim._cryoclasty_cue_cache = cache
    return cache


def frost_clast_cue_for_chunk(sim, coord: Tuple[int, int, int]
                              ) -> Optional[FrostClastCue]:
    """Truthful frost-shattered tool-stone cue at ``coord`` (or None). Memoised.

    Invariant: a returned cue means (1) the Wave 50 frost field is genuinely
    active here (``fci ≥ FROST_ACTIVE_MIN``) and (2) a real knappable lithology
    crops out within ``MAX_OUTCROP_DEPTH_M`` in the same ``chunk_geology`` column
    mining reads. ``clast_quality`` truthfully reflects whether that rock's frost
    fabric yields an edge."""
    coord = tuple(int(c) for c in coord)
    cache = install_cryoclasty(sim)
    if coord in cache:
        return cache[coord]
    world, origin = _resolve_anchor(sim)
    chunk = sim.streamer.cache.get(coord)
    if world is None or origin is None or chunk is None:
        cache[coord] = None
        return None
    g = chunk_geology(sim, coord)
    layers = g.layers if g is not None else []
    # Sim metres → macro km (cf. engine.world generate_chunk: x_km = x_m*1e-3 + ox).
    cx, cy, _cz = coord
    x_m = (cx + 0.5) * CHUNK_SIDE_M
    y_m = (cy + 0.5) * CHUNK_SIDE_M
    x_km = x_m * 0.001 + float(origin[0])
    y_km = y_m * 0.001 + float(origin[1])
    m = sample_macro(world, x_km, y_km)
    fci = _fci_at(m["temp_c"], m["precip_mm"], m["biome"])
    slope_deg = _chunk_slope_deg(chunk)
    biome_dom = lo._dominant_biome(chunk)
    cue = _clast_from_inputs(coord, layers, biome_dom, fci, slope_deg,
                             temp_c=float(m["temp_c"]),
                             elevation_m=float(m["elevation_m"]))
    cache[coord] = cue
    return cue


def prospect_frost_clasts(sim, world_x: float, world_y: float
                          ) -> Optional[FrostClastCue]:
    """What an agent at world ``(x, y)`` perceives of the frost-shattered stone
    field at the surface here: the scree's look + truthful clast quality, or
    None if no frost field / no rock crops out."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return frost_clast_cue_for_chunk(sim, coord)


def gather_at(sim, world_x: float, world_y: float) -> Dict[str, object]:
    """**Non-mutating** preview of what gathering surface clasts at ``(x, y)``
    yields — the ground-truthed outcome the perception cue must agree with.

    Touches NOTHING (no geology consumed, unlike C13 ``smelt_at``): it is the
    truth oracle of the GATHER verb, not the action. ``workable`` is True only
    when the gathered clast carries a durable edge — i.e. gathering it would
    actually furnish a tool (grus / rubble → False, the lie this cap exposes)."""
    coord = world_to_chunk(float(world_x), float(world_y))
    cue = frost_clast_cue_for_chunk(sim, coord)
    if cue is None:
        return {"material": None, "clast_quality": 0.0, "workable": False,
                "zone": None, "collect_depth_m": SURFACE_COLLECT_DEPTH_M,
                "abundant": False}
    return {"material": cue.material, "clast_quality": cue.clast_quality,
            "workable": cue.workable, "zone": cue.zone,
            "collect_depth_m": cue.collect_depth_m, "abundant": cue.abundant,
            "knap_class": cue.knap_class.name}


def discover_frost_clasts_by_sight(sim, rows: List[int],
                                   perception_radius_m: float = 96.0
                                   ) -> Dict[int, List[FrostClastCue]]:
    """For each agent ``row``, the frost-clast fields perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    Turns the static frost field into a **perceivable, actionable** signal — the
    agent then *chooses* where to gather. Deterministic order (chunk distance
    then coord)."""
    out: Dict[int, List[FrostClastCue]] = {}
    if not rows:
        return out
    install_cryoclasty(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], FrostClastCue]] = []
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
                cue = frost_clast_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def best_frost_clast_near(sim, row: int, perception_radius_m: float = 128.0
                          ) -> Optional[FrostClastCue]:
    """The single best **workable** frost-clast field an agent at ``row`` can
    perceive — the actionable pick when seeking a cutting edge with no quarrying.

    Skips barren grus / rubble fields (``workable == False``): an agent on a cold
    granite scree must keep walking to find sound flint, exactly as in reality.
    Returns None if every perceivable frost field is barren (or none in sight)."""
    cues = discover_frost_clasts_by_sight(sim, [int(row)], perception_radius_m
                                          ).get(int(row), [])
    workable = [c for c in cues if c.workable]
    if not workable:
        return None
    # distance-sorted already; pick the sharpest clast, ties keep nearest order.
    return max(workable, key=lambda c: c.clast_quality)


def cryoclasty_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily. Includes the
    macro Wave 50 frost snapshot the agent is now perceiving (transparency)."""
    install_cryoclasty(sim)
    by_zone: Dict[str, int] = {}
    by_material: Dict[str, int] = {}
    n_chunks = 0
    n_cued = 0
    n_workable = 0
    best_q = 0.0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = frost_clast_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_cued += 1
        if cue.workable:
            n_workable += 1
        by_zone[cue.zone] = by_zone.get(cue.zone, 0) + 1
        by_material[cue.material] = by_material.get(cue.material, 0) + 1
        best_q = max(best_q, cue.clast_quality)
    macro = fw.observe_frost_weathering(sim)
    macro_frost = None
    if macro is not None:
        macro_frost = {
            "mean_fci_land": round(macro.mean_fci_land, 6),
            "max_fci": round(macro.max_fci, 6),
            "fci_strong_fraction": round(macro.fci_strong_fraction, 6),
            "talus_cells": macro.talus_cells,
            "permafrost_cells": macro.permafrost_cells,
            "alpine_cells": macro.alpine_cells,
        }
    return {
        "n_chunks": n_chunks,
        "n_chunks_with_clasts": n_cued,
        "n_workable": n_workable,
        "clast_rate": round(n_cued / n_chunks, 4) if n_chunks else 0.0,
        "workable_rate": round(n_workable / n_cued, 4) if n_cued else 0.0,
        "best_clast_quality": round(best_q, 4),
        "by_zone": dict(sorted(by_zone.items())),
        "by_material": dict(sorted(by_material.items())),
        "macro_frost": macro_frost,
    }


__all__ = [
    "FrostClastCue",
    "install_cryoclasty", "frost_clast_cue_for_chunk",
    "prospect_frost_clasts", "gather_at", "discover_frost_clasts_by_sight",
    "best_frost_clast_near", "cryoclasty_summary",
    "FROST_ACTIVE_MIN", "MIN_CLAST_QUALITY", "ABUNDANT_FCI",
    "SURFACE_COLLECT_DEPTH_M",
    "TALUS_SLOPE_DEG", "TALUS_FCI_MIN", "ALPINE_ELEV_M", "ALPINE_FCI_MIN",
    "PERMAFROST_TEMP_C",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
