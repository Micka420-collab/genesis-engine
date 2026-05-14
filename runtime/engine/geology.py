"""Genesis Engine — Wave 10 geology (strates + extraction).

Each cached chunk receives a **vertical stratigraphic column** of
geological layers (top soil → regolith → weathered rock → bedrock).
The column is generated deterministically from the chunk's seed using
realistic stratigraphic principles :

  - **Topsoil** (0-1 m) — humic + clay, low ore content, fast to dig.
  - **Regolith** (1-5 m) — fragmented + weathered material from above.
    Can contain placer deposits (alluvial gold near rivers).
  - **Sedimentary cover** (5-200 m) — if biome is lowland/forest/
    grassland, layered limestone/sandstone/shale according to age.
  - **Igneous bedrock** (200+ m) — granite or basalt baseline. Deep
    mining hits metamorphic gneiss in mountain biomes.

Ore deposits are seeded inside layers based on the mineral's
``biome_affinity``, ``elevation_bias``, depth range, and chunk seed.
Each layer carries a ``Dict[mineral_name → mass_fraction]`` describing
the ore mix.

Mining
------
``mine_at(sim, state, row, target_depth_m, kg_to_extract)`` :
  1. Walk through the chunk's layers top-down, find the one straddling
     ``target_depth_m``.
  2. Compute available mass from layer thickness × density × mass_fraction.
  3. Subtract the extraction from the layer's mass budget.
  4. Yield a dict ``{mineral_name → kg}`` plus a side ``{element → kg}``
     derived from Wave 1 chemistry.
  5. Credit the agent's per-mineral inventory if a per-row dict is
     attached (otherwise sums into ``state.cumulative_extracted``).

Determinism
-----------
Strata generation is pure ``prf_rng``-based ; mining is event-driven
(no RNG). Bit-identical across runs same seed.

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — geology is the static
substrate beneath the simulation, just like ``earth_loader`` is for
elevation + biome. Strata are an extension of the seed.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — one-step lookup
``(chunk, depth) → ore mix``. No multi-step rollout (extraction is
state-mutating but doesn't compose like a Simulator).
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"  # arxiv 2604.22748

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.mineral_catalog import (
    MINERALS, MINERAL_BY_NAME, MineralCategory, Mineral, mineral_by_index,
)
from engine.world import CHUNK_SIDE_M, world_to_chunk


# ---------------------------------------------------------------------------
# Layer types + constants
# ---------------------------------------------------------------------------

# Default mass density per stratum type (kg/m³).
DENSITY_TOPSOIL = 1500.0
DENSITY_REGOLITH = 1800.0
DENSITY_SEDIMENT = 2300.0
DENSITY_IGNEOUS = 2700.0
DENSITY_METAMORPHIC = 2850.0

# Maximum reasonable extraction per call (kg). Cap so single mine action
# can't drain a layer instantly — agents must mine repeatedly.
MAX_EXTRACT_KG_PER_CALL = 50.0


@dataclass
class StrataLayer:
    """One geological stratum at a chunk."""
    depth_top_m: float
    depth_bottom_m: float
    rock_type: str                          # main rock mineral name
    density_kg_m3: float
    # Mineral content of the layer : name → mass fraction in [0, 1].
    # Mass fractions sum to ≤ 1.0 ; the remainder is "inert matrix".
    ore_mix: Dict[str, float] = field(default_factory=dict)
    # Mass budget that mining has already drained from this layer (kg).
    extracted_kg: float = 0.0

    def thickness_m(self) -> float:
        return self.depth_bottom_m - self.depth_top_m

    def total_mass_kg(self, area_m2: float = CHUNK_SIDE_M * CHUNK_SIDE_M) -> float:
        return self.thickness_m() * area_m2 * self.density_kg_m3

    def remaining_mass_kg(self, area_m2: float = CHUNK_SIDE_M * CHUNK_SIDE_M) -> float:
        return max(0.0, self.total_mass_kg(area_m2) - self.extracted_kg)


@dataclass
class ChunkGeology:
    """Stratigraphic column at one chunk."""
    coord: Tuple[int, int, int]
    layers: List[StrataLayer] = field(default_factory=list)
    # Per-mineral cumulative extracted mass (kg) at this chunk.
    extracted_by_mineral: Dict[str, float] = field(default_factory=dict)

    def find_layer_at(self, depth_m: float) -> Optional[StrataLayer]:
        for layer in self.layers:
            if layer.depth_top_m <= depth_m < layer.depth_bottom_m:
                return layer
        return None


@dataclass
class GeologyState:
    chunks: Dict[Tuple[int, int, int], ChunkGeology] = field(default_factory=dict)
    cumulative_extracted: Dict[str, float] = field(default_factory=dict)  # global stats
    mine_events: int = 0
    last_total_strata: int = 0


# ---------------------------------------------------------------------------
# Strata generation
# ---------------------------------------------------------------------------

def _dominant_biome(chunk) -> int:
    biomes, counts = np.unique(chunk.biome, return_counts=True)
    return int(biomes[np.argmax(counts)])


def _avg_elevation(chunk) -> float:
    return float(chunk.height.mean())


def _select_ore_mix(rng, biome: int, elevation_m: float,
                    depth_top_m: float, depth_bottom_m: float,
                    max_minerals: int = 3) -> Dict[str, float]:
    """Pick a handful of minerals that occur at this (biome, elevation,
    depth) and assign small mass fractions. Pure prf_rng — no globals.

    Returns ``{mineral_name → mass_fraction}`` summing to ≤ 0.30
    (rest = inert matrix).
    """
    elev_norm = max(-1.0, min(1.0, (elevation_m - 400.0) / 2000.0))
    candidates: List[Tuple[str, float]] = []
    for m in MINERALS:
        if biome not in m.biome_affinity:
            continue
        # Depth window check.
        if m.max_depth_m < depth_top_m or m.min_depth_m > depth_bottom_m:
            continue
        # Elevation bias scoring : higher score when chunk elevation matches.
        elev_score = 1.0 - 0.5 * abs(m.elevation_bias - elev_norm)
        # Inverse-rarity weight (common minerals more likely).
        rarity_w = (1.0 - m.rarity) ** 1.5
        score = max(0.0, elev_score * rarity_w)
        if score > 0.0:
            candidates.append((m.name, score))
    if not candidates:
        return {}
    # Weighted sampling without replacement.
    selected: Dict[str, float] = {}
    pool = candidates[:]
    n_to_pick = min(max_minerals, len(pool))
    for _ in range(n_to_pick):
        total = sum(s for _, s in pool)
        if total <= 0:
            break
        r = rng.random() * total
        acc = 0.0
        chosen_idx = 0
        for i, (_, s) in enumerate(pool):
            acc += s
            if acc >= r:
                chosen_idx = i
                break
        name, _ = pool.pop(chosen_idx)
        # Assign a fraction between 0.001 and 0.05 (rich vein) for picked.
        # Rarer minerals get smaller fractions.
        m = MINERAL_BY_NAME[name]
        base_frac = 0.001 + (1.0 - m.rarity) * 0.05
        # Random jitter via rng.
        frac = base_frac * (0.5 + rng.random())
        selected[name] = min(0.20, frac)
    # Normalise so total ≤ 0.30 (cap on ore content per layer).
    total_frac = sum(selected.values())
    if total_frac > 0.30:
        scale = 0.30 / total_frac
        selected = {k: v * scale for k, v in selected.items()}
    return selected


def _generate_layers(rng, biome: int, elevation_m: float) -> List[StrataLayer]:
    """Build the stratigraphic column appropriate for the chunk."""
    layers: List[StrataLayer] = []

    # Topsoil (always thin if elevation > 1500 m).
    topsoil_thickness = 1.0 if elevation_m < 1500 else 0.3
    layers.append(StrataLayer(
        depth_top_m=0.0,
        depth_bottom_m=topsoil_thickness,
        rock_type="shale",  # topsoil approximated as clay/shale
        density_kg_m3=DENSITY_TOPSOIL,
        ore_mix=_select_ore_mix(rng, biome, elevation_m, 0.0, topsoil_thickness,
                                max_minerals=2),
    ))

    # Regolith (1-5 m) — fragmented weathered material.
    regolith_bottom = topsoil_thickness + 4.0
    layers.append(StrataLayer(
        depth_top_m=topsoil_thickness,
        depth_bottom_m=regolith_bottom,
        rock_type="sandstone",
        density_kg_m3=DENSITY_REGOLITH,
        ore_mix=_select_ore_mix(rng, biome, elevation_m,
                                topsoil_thickness, regolith_bottom,
                                max_minerals=3),
    ))

    # Sedimentary cover (5-200 m) — if lowland or forest biome.
    sediment_bottom = regolith_bottom
    if elevation_m < 800.0:
        sediment_bottom = regolith_bottom + 195.0
        # Choose a dominant rock type by biome.
        if biome in (0, 4, 5, 6, 9, 10, 11):  # ocean/forest/grassland/tropical
            rock = "limestone"
        elif biome in (7, 8):  # deserts
            rock = "sandstone"
        else:
            rock = "shale"
        layers.append(StrataLayer(
            depth_top_m=regolith_bottom,
            depth_bottom_m=sediment_bottom,
            rock_type=rock,
            density_kg_m3=DENSITY_SEDIMENT,
            ore_mix=_select_ore_mix(rng, biome, elevation_m,
                                    regolith_bottom, sediment_bottom,
                                    max_minerals=4),
        ))

    # Bedrock — igneous baseline (granite or basalt).
    # Choice based on biome : oceanic / volcanic biomes → basalt ; else granite.
    if biome in (0, 7, 1):  # ocean / hot_desert / ice (volcanic Iceland) → basalt
        bedrock_rock = "basalt"
    else:
        bedrock_rock = "granite"
    bedrock_top = sediment_bottom
    bedrock_bottom = bedrock_top + 800.0
    layers.append(StrataLayer(
        depth_top_m=bedrock_top,
        depth_bottom_m=bedrock_bottom,
        rock_type=bedrock_rock,
        density_kg_m3=DENSITY_IGNEOUS,
        ore_mix=_select_ore_mix(rng, biome, elevation_m,
                                bedrock_top, bedrock_bottom,
                                max_minerals=3),
    ))

    # Metamorphic deep zone (mountains only).
    if elevation_m > 1200.0:
        deep_top = bedrock_bottom
        deep_bottom = deep_top + 2000.0
        layers.append(StrataLayer(
            depth_top_m=deep_top,
            depth_bottom_m=deep_bottom,
            rock_type="gneiss",
            density_kg_m3=DENSITY_METAMORPHIC,
            ore_mix=_select_ore_mix(rng, biome, elevation_m,
                                    deep_top, deep_bottom,
                                    max_minerals=3),
        ))

    return layers


def generate_chunk_geology(sim, chunk) -> ChunkGeology:
    """Produce a deterministic stratigraphic column for one chunk."""
    coord = chunk.coord if hasattr(chunk, "coord") else (0, 0, 0)
    biome = _dominant_biome(chunk)
    elevation = _avg_elevation(chunk)
    cx, cy, cz = coord
    rng = prf_rng(sim.cfg.seed, ["geology", "strata"],
                  [int(cx), int(cy), int(cz)])
    layers = _generate_layers(rng, biome, elevation)
    return ChunkGeology(coord=coord, layers=layers)


# ---------------------------------------------------------------------------
# Public install + reporter
# ---------------------------------------------------------------------------

# Module-level dispatch table : id(agents) -> (sim, state). Same
# pattern as engine.agriculture._AG_DISPATCH for the apply_decision
# wrapper that handles ActionKind.MINE.
_GEOLOGY_DISPATCH: Dict[int, Tuple[object, "GeologyState"]] = {}


def _geology_global_wrapper(agents, row, decision, streamer, tick):
    """Stacked wrapper around the previous ``apply_decision``.

    Handles ActionKind.MINE — extracts ore from the chunk's strata at
    a depth encoded in ``decision.target_x`` (metres). Other actions
    pass through to the inner handler.
    """
    import engine.cognition as _cog
    from engine.agent import ActionKind

    inner = getattr(_cog, "_geology_inner_apply_decision", None)
    if inner is None:
        return None
    pair = _GEOLOGY_DISPATCH.get(id(agents))
    if pair is None:
        return inner(agents, row, decision, streamer, tick)
    sim, _state = pair
    act = int(decision.action)

    if act == int(ActionKind.MINE):
        depth_m = max(0.0, float(getattr(decision, "target_x", 0.0)))
        if depth_m == 0.0:
            depth_m = 3.0  # default to regolith
        kg = float(getattr(decision, "target_y", 0.0)) or 10.0
        mine_at(sim, row, target_depth_m=depth_m, kg_to_extract=kg)
        try:
            agents.vel[row, :2] = 0.0
        except Exception:
            pass
        return []

    return inner(agents, row, decision, streamer, tick)


def _patch_actions(sim, state: "GeologyState") -> None:
    """Register sim in the dispatch table and install the wrapper once."""
    import engine.cognition as _cog
    import engine.sim as _sim_mod
    _GEOLOGY_DISPATCH[id(sim.agents)] = (sim, state)
    if getattr(_cog, "_geology_inner_apply_decision", None) is None:
        _cog._geology_inner_apply_decision = _cog.apply_decision
        _cog.apply_decision = _geology_global_wrapper
        if hasattr(_sim_mod, "apply_decision"):
            _sim_mod.apply_decision = _geology_global_wrapper


def install_geology(sim) -> GeologyState:
    """Idempotent installer. Lazily generates strata on first access.

    Also wires ``engine.cognition.apply_decision`` so agents executing
    ``ActionKind.MINE`` actually trigger ore extraction at the depth
    encoded in ``decision.target_x``.
    """
    existing: Optional[GeologyState] = getattr(sim, "_geology_state", None)
    if existing is not None:
        return existing
    state = GeologyState()
    sim._geology_state = state
    _patch_actions(sim, state)
    return state


def chunk_geology(sim, coord: Tuple[int, int, int]) -> Optional[ChunkGeology]:
    """Return (lazily creating) the geology for the chunk at ``coord``."""
    state = install_geology(sim)
    g = state.chunks.get(coord)
    if g is not None:
        return g
    chunk = sim.streamer.cache.get(coord)
    if chunk is None:
        return None
    g = generate_chunk_geology(sim, chunk)
    state.chunks[coord] = g
    return g


def mine_at(
    sim,
    row: int,
    target_depth_m: float,
    kg_to_extract: float = 5.0,
) -> Dict[str, float]:
    """Extract from the chunk under agent ``row`` at ``target_depth_m``.

    Returns a dict ``{mineral_name → kg}`` of what was extracted. Empty
    dict if no extractable ore is present.

    Side effects :
      * subtracts mass from the layer's ``extracted_kg``
      * increments ``state.cumulative_extracted`` + chunk's per-mineral counter
      * credits the agent's inventory based on element yields (Wave 1 bridge)
    """
    state = install_geology(sim)
    px = float(sim.agents.pos[row, 0])
    py = float(sim.agents.pos[row, 1])
    coord = world_to_chunk(px, py)
    g = chunk_geology(sim, coord)
    if g is None:
        return {}
    layer = g.find_layer_at(target_depth_m)
    if layer is None or not layer.ore_mix:
        return {}
    kg_to_extract = min(kg_to_extract, MAX_EXTRACT_KG_PER_CALL,
                        layer.remaining_mass_kg())
    if kg_to_extract <= 0.0:
        return {}
    out: Dict[str, float] = {}
    for mineral_name, frac in layer.ore_mix.items():
        kg = kg_to_extract * frac
        if kg <= 0:
            continue
        out[mineral_name] = kg
        g.extracted_by_mineral[mineral_name] = (
            g.extracted_by_mineral.get(mineral_name, 0.0) + kg)
        state.cumulative_extracted[mineral_name] = (
            state.cumulative_extracted.get(mineral_name, 0.0) + kg)
    layer.extracted_kg += kg_to_extract
    state.mine_events += 1
    _credit_agent_inventory(sim, row, out)
    return out


def _credit_agent_inventory(sim, row: int, ores: Dict[str, float]) -> None:
    """Add the right amount to existing inv_* fields where applicable.

    Maps mineral → known agent inventory slots:
      native_gold / silver / copper / cassiterite → inv_metal
      granite / basalt / limestone / sandstone / shale / marble / slate / gneiss → inv_stone
      coal / peat / oil_shale → no-op (no inv_fuel today; we just log)
      anything else → inv_metal (proxy for "ore")
    """
    if not ores:
        return
    inv_metal = getattr(sim.agents, "inv_metal", None)
    inv_stone = getattr(sim.agents, "inv_stone", None)
    capacity = getattr(sim.agents, "inv_capacity_kg", None)
    if inv_metal is None and inv_stone is None:
        return
    metal_keywords = ("native_", "hematite", "magnetite", "bauxite",
                      "cassiterite", "rutile", "chalcopyrite", "galena",
                      "sphalerite", "pyrite", "cinnabar", "calcite",
                      "dolomite", "feldspar", "mica_muscovite")
    stone_keywords = ("granite", "basalt", "obsidian", "limestone",
                      "sandstone", "shale", "marble", "slate", "gneiss",
                      "quartz")
    for mineral_name, kg in ores.items():
        if any(k in mineral_name for k in metal_keywords):
            if inv_metal is not None:
                inv_metal[row] = float(inv_metal[row]) + kg
        elif any(k in mineral_name for k in stone_keywords):
            if inv_stone is not None:
                inv_stone[row] = float(inv_stone[row]) + kg
        else:
            # Fallback : organics (peat/coal/oil_shale) and halides go to
            # inv_metal proxy.
            if inv_metal is not None:
                inv_metal[row] = float(inv_metal[row]) + kg


def geology_state(sim) -> Dict[str, object]:
    state: Optional[GeologyState] = getattr(sim, "_geology_state", None)
    if state is None:
        return {}
    # Recount strata.
    total_layers = sum(len(g.layers) for g in state.chunks.values())
    state.last_total_strata = total_layers
    # Top minerals extracted globally.
    top = sorted(state.cumulative_extracted.items(),
                 key=lambda kv: -kv[1])[:8]
    return {
        "n_chunks_with_geology": len(state.chunks),
        "total_layers": total_layers,
        "mine_events_total": state.mine_events,
        "top_extracted": [{"mineral": k, "total_kg": round(v, 2)}
                          for k, v in top],
        "cumulative_extracted_total_kg":
            round(sum(state.cumulative_extracted.values()), 2),
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_geology_state(sim, target_dir: str) -> bool:
    state: Optional[GeologyState] = getattr(sim, "_geology_state", None)
    if state is None:
        return False
    payload = {
        "mine_events": state.mine_events,
        "cumulative_extracted": state.cumulative_extracted,
        "chunks": {
            f"{c[0]}_{c[1]}_{c[2]}": {
                "extracted_by_mineral": g.extracted_by_mineral,
                "layers": [
                    {"depth_top_m": L.depth_top_m,
                     "depth_bottom_m": L.depth_bottom_m,
                     "rock_type": L.rock_type,
                     "density_kg_m3": L.density_kg_m3,
                     "ore_mix": L.ore_mix,
                     "extracted_kg": L.extracted_kg}
                    for L in g.layers
                ],
            }
            for c, g in state.chunks.items()
        },
    }
    with open(os.path.join(target_dir, "geology.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return True


def load_geology_state(sim, target_dir: str) -> bool:
    path = os.path.join(target_dir, "geology.json")
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state = install_geology(sim)
    state.mine_events = int(payload.get("mine_events", 0))
    state.cumulative_extracted = {
        str(k): float(v)
        for k, v in payload.get("cumulative_extracted", {}).items()
    }
    state.chunks.clear()
    for key, d in payload.get("chunks", {}).items():
        parts = key.split("_")
        coord = tuple(int(p) for p in parts)
        layers = [
            StrataLayer(
                depth_top_m=float(L["depth_top_m"]),
                depth_bottom_m=float(L["depth_bottom_m"]),
                rock_type=str(L["rock_type"]),
                density_kg_m3=float(L["density_kg_m3"]),
                ore_mix={str(k): float(v) for k, v in L.get("ore_mix", {}).items()},
                extracted_kg=float(L.get("extracted_kg", 0.0)))
            for L in d.get("layers", [])
        ]
        g = ChunkGeology(
            coord=coord,
            layers=layers,
            extracted_by_mineral={str(k): float(v)
                                  for k, v in d.get(
                                      "extracted_by_mineral", {}).items()},
        )
        state.chunks[coord] = g
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "StrataLayer", "ChunkGeology", "GeologyState",
    "DENSITY_TOPSOIL", "DENSITY_REGOLITH", "DENSITY_SEDIMENT",
    "DENSITY_IGNEOUS", "DENSITY_METAMORPHIC",
    "MAX_EXTRACT_KG_PER_CALL",
    "install_geology", "chunk_geology", "generate_chunk_geology",
    "mine_at",
    "geology_state",
    "save_geology_state", "load_geology_state",
]
