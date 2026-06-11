"""Genesis Engine — Substrate capability : surface mineralization cues.

**Règle invariante du projet** (cf. ``building_discovery``,
``art_discovery``) : rien n'est scripté. Les agents ne *savent* pas
qu'un minerai existe — ils **VOIENT** un indice de surface (une couleur
d'altération) puis décident eux-mêmes de creuser. La découverte est
émergente ; ce module ne fait qu'exposer un **signal physique véridique**.

Pourquoi ce module (et pourquoi ce n'est PAS un observateur)
------------------------------------------------------------
La couche ``engine.geology`` sème des minerais *en profondeur* (chaque
``StrataLayer`` porte un ``ore_mix``) et ``mine_at`` les extrait. Mais
jusqu'ici **aucun signal de surface** ne permettait à un agent de
*découvrir par la vue* un gisement enfoui : la décision ``MINE`` partait
d'une profondeur par défaut (3 m) sans aucun indice. Le monde portait la
ressource mais restait muet.

Ce module ajoute la capacité manquante : le **chapeau de fer / la tache
d'altération** que les prospecteurs lisent depuis l'âge du bronze
(gossan, malachite, efflorescence saline, placers). Ce n'est pas un
``*_observer.py`` qui *mesure* le tick — c'est un **signal de monde
interrogeable** que les agents *consomment pour agir*. Il n'ajoute
**aucun coût au tick** : les indices sont calculés paresseusement par
chunk et mémorisés. Il échappe donc au moratoire observateurs
(`CONTRIBUTING.md` §"Moratoire observateurs") qui ne vise que les
wrappers read-only de ``sim.step``.

Le monde ne ment jamais
-----------------------
Un indice n'est émis QUE s'il existe réellement, dans la même colonne
``chunk_geology`` que celle que ``mine_at`` exploite, une couche peu
profonde dont l'``ore_mix`` contient le minéral correspondant à la
couleur. L'indice porte ``dig_depth_m`` : creuser là **rend** ce minéral.
La réciproque est volontairement *faible* (absence d'indice ⇏ absence de
minerai) — beaucoup de gisements ne trahissent aucune couleur en surface,
et l'agent doit alors explorer/creuser à l'aveugle. C'est physiquement
honnête et cela préserve l'émergence (on ne donne pas la carte).

Géochimie de surface (veille 2026-06-11, gossans / oxydation supergène)
----------------------------------------------------------------------
* Cuivre (cuivre natif, chalcopyrite) → carbonate vert (**malachite**),
  azurite bleue : « l'enseigne lumineuse du cuivre ». Vert vif.
* Sulfures de fer (pyrite, etc.) + oxydes de fer → **chapeau de fer**
  (gossan) : limonite brune, hématite rouge, jarosite jaune. Brun-rouille.
* Soufre natif → croûte jaune près des fumerolles. Jaune.
* Halite (sel) → **efflorescence** blanche / source au goût salé. Blanc.
* Or alluvionnaire → paillettes (**placer**) dans le régolithe des lits
  de rivière. Doré.

Couleurs alignées sur le crate Rust ``genesis-geology``
(``Mineral::Malachite::surface_color() = [80,140,70]``) afin que les
indices Python (sim live) et Rust (world-engine) concordent visuellement.

Déterminisme
------------
Pur : fonction de ``chunk_geology`` (lui-même ``prf_rng``) + biome. Aucun
RNG nouveau. Bit-identique entre deux runs de même seed.

ADR-0005
--------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — l'expression de surface est
une lecture dérivée du substrat géologique, comme la datation relative.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — lookup une étape
(chunk → indice), sans rollout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.geology import chunk_geology, install_geology, StrataLayer
from engine.mineral_catalog import MINERAL_BY_NAME
from engine.world import CHUNK_SIDE_M, world_to_chunk

# ADR-0005 tags (audited by engine.world_model_capabilities).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# Biome ids (cf. engine.mineral_catalog._BIOME).
_OCEAN = 0

# A shallow ore body needs at least this mass fraction in a near-surface
# layer to tint the surface enough to be seen. Model threshold (the
# ``ore_mix`` fraction is an abstraction of concentration).
MIN_VISIBLE_FRACTION = 0.003

# Below this biome visibility the cue is masked (canopy / snow / water).
VISIBILITY_FLOOR = 0.30

# Outcrop / weathering-cue visibility by biome id. Gossans are classically
# read in arid, sparsely-vegetated terrain; dense canopy and ice hide them;
# the sea masks them entirely.
_BIOME_VISIBILITY: Dict[int, float] = {
    0: 0.00,   # OCEAN              — underwater, masked
    1: 0.15,   # ICE               — snow/ice cover
    2: 0.75,   # TUNDRA            — sparse, good exposure
    3: 0.45,   # BOREAL_FOREST
    4: 0.40,   # TEMPERATE_FOREST
    5: 0.25,   # TEMPERATE_RAINFOREST — dense canopy + leaching
    6: 0.70,   # GRASSLAND
    7: 1.00,   # HOT_DESERT        — classic gossan terrain
    8: 0.95,   # COLD_DESERT
    9: 0.80,   # SAVANNA
    10: 0.55,  # TROPICAL_DRY_FOREST
    11: 0.20,  # TROPICAL_RAINFOREST — deep weathering + canopy
}


@dataclass(frozen=True)
class ExpressionRule:
    """Surface weathering expression of an ore group."""
    group: str                      # stable id of the expression group
    label: str                      # human label of the surface stain
    rgb: Tuple[int, int, int]       # perceived colour of the stain
    minerals: Tuple[str, ...]       # ore minerals that produce this stain
    max_expression_depth_m: float   # body top must be ≤ this to tint surface
    priority: int                   # higher wins when several groups co-occur


# Ordered by descending diagnostic priority. Each ore mineral belongs to
# exactly ONE expression group (its diagnostic surface colour). Iron is the
# most common cap, so it has the LOWEST priority: a rarer, more telling
# signal (copper green, sulfur yellow, salt white, placer gold) dominates
# the visible surface when it co-occurs with a generic iron cap.
_RULES: Tuple[ExpressionRule, ...] = (
    ExpressionRule(
        group="copper", label="tache verte (malachite/azurite)",
        rgb=(80, 140, 70),
        minerals=("native_copper", "chalcopyrite"),
        max_expression_depth_m=40.0, priority=5),
    ExpressionRule(
        group="sulfur", label="croute jaune (soufre / fumerolle)",
        rgb=(220, 200, 60),
        minerals=("native_sulfur",),
        max_expression_depth_m=20.0, priority=4),
    ExpressionRule(
        group="salt", label="efflorescence blanche (sel)",
        rgb=(235, 235, 240),
        minerals=("halite",),
        max_expression_depth_m=12.0, priority=3),
    ExpressionRule(
        group="gold_placer", label="paillettes dorees (placer alluvial)",
        rgb=(212, 175, 55),
        minerals=("native_gold",),
        max_expression_depth_m=8.0, priority=2),
    ExpressionRule(
        group="gossan", label="chapeau de fer (limonite/hematite/jarosite)",
        rgb=(150, 75, 40),
        minerals=("pyrite", "hematite", "magnetite", "galena", "sphalerite"),
        max_expression_depth_m=50.0, priority=1),
)

# mineral name → its expression rule (built + validated at import time).
_MINERAL_RULE: Dict[str, ExpressionRule] = {}
for _rule in _RULES:
    for _m in _rule.minerals:
        if _m not in MINERAL_BY_NAME:
            raise RuntimeError(
                f"surface_mineralization: unknown mineral '{_m}' in "
                f"expression group '{_rule.group}' — fix the table.")
        if _m in _MINERAL_RULE:
            raise RuntimeError(
                f"surface_mineralization: mineral '{_m}' assigned to two "
                f"expression groups — each must belong to exactly one.")
        _MINERAL_RULE[_m] = _rule


@dataclass(frozen=True)
class SurfaceCue:
    """A truthful surface mineralization cue at one chunk.

    ``rgb``/``label`` = what an agent *perceives*. ``mineral`` = the ground
    truth diggable below (used to resolve a dig + prove the invariant); it
    is NOT handed to the agent as "this is copper" — the agent must learn
    the colour→ore correlation by acting.
    """
    coord: Tuple[int, int, int]
    group: str
    label: str
    rgb: Tuple[int, int, int]
    mineral: str                    # ground-truth ore that digging yields
    mass_fraction: float            # ore fraction in the expressing layer
    expression_depth_m: float       # depth of the ore body top (m)
    dig_depth_m: float              # a depth that lands inside the ore layer
    biome: int
    confidence: float               # perceptual confidence in [0, 1]


# ---------------------------------------------------------------------------
# Core derivation — cue from the same geology layers that mining reads.
# ---------------------------------------------------------------------------

def _dominant_biome(chunk) -> int:
    biomes, counts = np.unique(np.asarray(chunk.biome), return_counts=True)
    return int(biomes[int(np.argmax(counts))])


def _best_rule_in_layer(layer: StrataLayer) -> Optional[Tuple[ExpressionRule, str, float]]:
    """Return (rule, mineral, fraction) for the highest-priority expression
    group present in this layer above the visibility threshold, or None."""
    best: Optional[Tuple[ExpressionRule, str, float]] = None
    for name, frac in layer.ore_mix.items():
        if frac < MIN_VISIBLE_FRACTION:
            continue
        rule = _MINERAL_RULE.get(name)
        if rule is None:
            continue
        if layer.depth_top_m > rule.max_expression_depth_m:
            continue
        if best is None or rule.priority > best[0].priority or (
                rule.priority == best[0].priority and frac > best[2]):
            best = (rule, name, float(frac))
    return best


def _cue_from_geology(coord, layers: List[StrataLayer], biome: int) -> Optional[SurfaceCue]:
    """Pure derivation. Shallowest qualifying layer wins (topmost weathering
    expression dominates the visible surface)."""
    visibility = _BIOME_VISIBILITY.get(biome, 0.5)
    if visibility < VISIBILITY_FLOOR:
        return None
    chosen: Optional[Tuple[StrataLayer, ExpressionRule, str, float]] = None
    for layer in sorted(layers, key=lambda L: L.depth_top_m):
        hit = _best_rule_in_layer(layer)
        if hit is None:
            continue
        rule, mineral, frac = hit
        chosen = (layer, rule, mineral, frac)
        break  # shallowest qualifying layer dominates
    if chosen is None:
        return None
    layer, rule, mineral, frac = chosen
    thickness = max(layer.depth_bottom_m - layer.depth_top_m, 1e-3)
    dig_depth = layer.depth_top_m + min(0.5, 0.5 * thickness)
    # confidence rises with both visibility and ore richness (saturating).
    confidence = float(min(1.0, visibility * (0.5 + min(frac / 0.05, 1.0) * 0.5)))
    return SurfaceCue(
        coord=tuple(int(c) for c in coord),
        group=rule.group, label=rule.label, rgb=rule.rgb,
        mineral=mineral, mass_fraction=frac,
        expression_depth_m=float(layer.depth_top_m),
        dig_depth_m=float(dig_depth), biome=int(biome),
        confidence=confidence)


# ---------------------------------------------------------------------------
# Public capability API
# ---------------------------------------------------------------------------

def install_surface_mineralization(sim) -> Dict:
    """Idempotent installer. Adds a lazy per-chunk cue cache to ``sim``.

    Adds **zero** per-tick cost: cues are derived on query and memoised.
    Returns the cache dict (``sim._surface_cue_cache``).
    """
    install_geology(sim)  # ensure geology state exists
    cache = getattr(sim, "_surface_cue_cache", None)
    if cache is None:
        cache = {}
        sim._surface_cue_cache = cache
    return cache


def surface_cue_for_chunk(sim, coord: Tuple[int, int, int]) -> Optional[SurfaceCue]:
    """Truthful surface cue at ``coord`` (or None). Memoised per chunk.

    Invariant: if this returns a cue, ``chunk_geology(sim, coord)`` has a
    layer at ``dig_depth_m`` whose ``ore_mix`` contains ``mineral``.
    """
    coord = tuple(int(c) for c in coord)
    cache = install_surface_mineralization(sim)
    if coord in cache:
        return cache[coord]
    g = chunk_geology(sim, coord)
    chunk = sim.streamer.cache.get(coord)
    if g is None or chunk is None:
        cache[coord] = None
        return None
    biome = _dominant_biome(chunk)
    cue = _cue_from_geology(coord, g.layers, biome)
    cache[coord] = cue
    return cue


def surface_cue_rgb_grid(sim, coord: Tuple[int, int, int]) -> Optional[np.ndarray]:
    """Per-chunk RGB ``color_hint`` grid (H, W, 3) uint8 for visual layers
    (Earth Console). Uniform cue colour if a cue exists, else None (caller
    falls back to the terrain colour). Mirrors the Rust ``color_hint``."""
    cue = surface_cue_for_chunk(sim, coord)
    if cue is None:
        return None
    chunk = sim.streamer.cache.get(coord)
    if chunk is None:
        return None
    h, w = np.asarray(chunk.biome).shape[:2]
    grid = np.empty((h, w, 3), dtype=np.uint8)
    grid[:, :] = cue.rgb
    return grid


def prospect(sim, world_x: float, world_y: float) -> Optional[SurfaceCue]:
    """What an agent standing at world ``(x, y)`` visually perceives at the
    surface. Returns the cue (colour + truthful diggable target) or None."""
    coord = world_to_chunk(float(world_x), float(world_y))
    return surface_cue_for_chunk(sim, coord)


def discover_by_sight(sim, rows: List[int],
                      perception_radius_m: float = 64.0
                      ) -> Dict[int, List[SurfaceCue]]:
    """For each agent ``row``, the surface cues perceivable within
    ``perception_radius_m`` (scans chunks whose centre falls in range).

    This is the capability that turns the static, buried ore field into a
    **perceivable, actionable** signal — the agent then *chooses* to mine.
    Deterministic order (by chunk distance then coord).
    """
    out: Dict[int, List[SurfaceCue]] = {}
    if not rows:
        return out
    install_surface_mineralization(sim)
    pos = sim.agents.pos
    span = int(perception_radius_m // CHUNK_SIDE_M) + 1
    r2 = perception_radius_m * perception_radius_m
    for row in rows:
        ax = float(pos[row, 0])
        ay = float(pos[row, 1])
        ccx, ccy, ccz = world_to_chunk(ax, ay)
        found: List[Tuple[float, Tuple[int, int, int], SurfaceCue]] = []
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
                cue = surface_cue_for_chunk(sim, coord)
                if cue is not None:
                    found.append((d2, coord, cue))
        found.sort(key=lambda t: (t[0], t[1]))
        out[int(row)] = [c for _, _, c in found]
    return out


def surface_cue_summary(sim) -> Dict[str, object]:
    """Aggregate stats over chunks currently in the streamer cache — for the
    dashboard / smoke journal. Read-only; computes cues lazily."""
    install_surface_mineralization(sim)
    by_group: Dict[str, int] = {}
    by_mineral: Dict[str, int] = {}
    n_chunks = 0
    n_cued = 0
    for coord in list(sim.streamer.cache.keys()):
        n_chunks += 1
        cue = surface_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_cued += 1
        by_group[cue.group] = by_group.get(cue.group, 0) + 1
        by_mineral[cue.mineral] = by_mineral.get(cue.mineral, 0) + 1
    return {
        "n_chunks": n_chunks,
        "n_chunks_with_cue": n_cued,
        "cue_rate": round(n_cued / n_chunks, 4) if n_chunks else 0.0,
        "by_group": dict(sorted(by_group.items())),
        "by_mineral": dict(sorted(by_mineral.items())),
    }


__all__ = [
    "SurfaceCue", "ExpressionRule",
    "install_surface_mineralization", "surface_cue_for_chunk",
    "surface_cue_rgb_grid", "prospect", "discover_by_sight",
    "surface_cue_summary",
    "MIN_VISIBLE_FRACTION", "VISIBILITY_FLOOR",
    "PIPELINE_LAYER", "WORLD_MODEL_CAPABILITY",
]
