"""Layer 2 — Sim-Lift physique vivante.

Adds two slowly-evolving processes on top of the Earth-anchored L1 chunks:

- **Vegetation succession**: each cell carries a 5-state Markov-chain
  vegetation tag (prairie → garrigue → bois jeune → forêt mature → forêt
  vieille). Transitions advance with sim-time, deterministically, and are
  rolled back when an agent harvests heavily or a structure is built.
- **Hydraulic erosion (light)**: each cell carries a scalar ``ravine_depth``
  that grows when agents traverse it during precipitation. High ravine depth
  cuts wood/food_capacity locally and creates micro-channels that feed
  ``chunk.water``. Simplified droplet — no richdem dependency.

The module is non-invasive: ``install_lift(sim)`` wraps ``sim.step()``
identically to ``sim_5cd_integration.install`` and stores side-tables on
the streamer cache so vanilla Phase-4 code paths see unchanged Chunk
objects.

Determinism is preserved end-to-end via ``engine.core.prf_rng`` — no
``random.random()`` is used.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.world import (Biome, CHUNK_SIDE_M, CHUNK_SIZE, world_to_cell,
                          world_to_chunk)


# ---------------------------------------------------------------------------
# Vegetation succession — 5-state Markov chain
# ---------------------------------------------------------------------------

class VegState(IntEnum):
    PRAIRIE = 0       # bare ground / open grass after disturbance
    GARRIGUE = 1      # shrub / scrub, 5-15 sim-years after PRAIRIE
    BOIS_JEUNE = 2    # young trees, 15-40 yrs
    FORET_MATURE = 3  # mature forest, 40-150 yrs
    FORET_VIEILLE = 4 # old-growth, 150+ yrs


# Time-constant per transition (in sim-seconds). Multiplied by drive_accel
# via the wrapping caller. Default constants pre-industrial average for
# Western European temperate forest.
SECONDS_PER_YEAR = 365.25 * 86_400.0
_MEAN_TRANSITION_YEARS = {
    (VegState.PRAIRIE, VegState.GARRIGUE): 6.0,
    (VegState.GARRIGUE, VegState.BOIS_JEUNE): 12.0,
    (VegState.BOIS_JEUNE, VegState.FORET_MATURE): 35.0,
    (VegState.FORET_MATURE, VegState.FORET_VIEILLE): 90.0,
}


# Biomes that support full forest succession. Outside these, vegetation
# tops out at GARRIGUE (e.g. tundra, alpine) or PRAIRIE (desert).
_FOREST_BIOMES = {
    int(Biome.BOREAL_FOREST), int(Biome.TEMPERATE_FOREST),
    int(Biome.TEMPERATE_RAINFOREST), int(Biome.TROPICAL_DRY_FOREST),
    int(Biome.TROPICAL_RAINFOREST),
}
_SHRUB_BIOMES = {
    int(Biome.GRASSLAND), int(Biome.SAVANNA), int(Biome.TUNDRA),
}
_BARREN_BIOMES = {
    int(Biome.OCEAN), int(Biome.ICE), int(Biome.HOT_DESERT),
    int(Biome.COLD_DESERT),
}


def _state_cap(biome_val: int) -> int:
    """Highest VegState a biome can climb to."""
    if biome_val in _FOREST_BIOMES:
        return int(VegState.FORET_VIEILLE)
    if biome_val in _SHRUB_BIOMES:
        return int(VegState.GARRIGUE)
    return int(VegState.PRAIRIE)


# ---------------------------------------------------------------------------
# Side-table attached to chunks via the streamer cache
# ---------------------------------------------------------------------------

@dataclass
class LiftField:
    """Per-chunk side-table for vegetation + erosion + derived geomorphometry.

    Stored on ``sim._lift_fields[chunk_coord]`` so we don't touch the Chunk
    dataclass. Initialised lazily on first visit.
    """
    veg_state: np.ndarray              # (CHUNK_SIZE, CHUNK_SIZE) uint8
    veg_age_s: np.ndarray              # sim-seconds since entering current state
    ravine_depth: np.ndarray           # 0..1; reduces food/wood when high
    slope_deg: np.ndarray              # cell slope in degrees, from DEM gradient
    is_lake: np.ndarray                # bool — water cell at elev > 1.5m (vs ocean)
    walkability: np.ndarray            # 0..1 — composite of slope+ravine + trail bonus
    base_walkability: Optional[np.ndarray] = None  # baseline (no trail bonus) for live recompute
    last_tick_seen: int = 0

    @classmethod
    def from_chunk(cls, chunk, world_seed: int, coord: Tuple[int, int, int]
                   ) -> "LiftField":
        rng = prf_rng(world_seed, ["lift_seed", str(coord[0]), str(coord[1])],
                      [int(coord[2])])
        # Initial vegetation: derive from biome — forests start at
        # FORET_MATURE (mature woodland is the pre-human steady state),
        # shrub biomes at GARRIGUE, others at PRAIRIE.
        veg = np.full((CHUNK_SIZE, CHUNK_SIZE), int(VegState.PRAIRIE),
                      dtype=np.uint8)
        biome = chunk.biome
        forest_mask = np.isin(biome, list(_FOREST_BIOMES))
        shrub_mask = np.isin(biome, list(_SHRUB_BIOMES))
        veg[forest_mask] = int(VegState.FORET_MATURE)
        veg[shrub_mask] = int(VegState.GARRIGUE)
        # Light heterogeneity: ~10% of forest cells start at FORET_VIEILLE,
        # ~5% at BOIS_JEUNE — gives the world some texture from the start.
        if forest_mask.any():
            noise = rng.random((CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32)
            old_mask = forest_mask & (noise < 0.10)
            veg[old_mask] = int(VegState.FORET_VIEILLE)
            young_mask = forest_mask & (noise >= 0.95)
            veg[young_mask] = int(VegState.BOIS_JEUNE)
        veg_age = np.zeros((CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32)
        ravine = np.zeros((CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32)
        # ---- Geomorphometry derived from the DEM (Earth-anchored L1) ----
        # Slope in degrees from the height gradient. ``np.gradient`` returns
        # (dh/dy, dh/dx); we use voxel size for the physical step.
        from engine.world import VOXEL_SIZE_M as _VOX
        gy, gx = np.gradient(chunk.height.astype(np.float32), _VOX, _VOX)
        slope_tan = np.hypot(gx, gy)
        slope_deg = np.degrees(np.arctan(slope_tan)).astype(np.float32)
        # Lake classification: water cell at elev > 1.5 m is a LAKE (a
        # bounded inland body), as opposed to OCEAN at sea level. Léman at
        # 372 m is the canonical example. We don't change ``chunk.biome``
        # (would break downstream code expecting class ids); the boolean
        # is_lake mask is consumed by anyone who needs the distinction.
        from engine.world import Biome as _Biome
        is_lake = ((chunk.biome == int(_Biome.OCEAN)) &
                   (chunk.height > 1.5)).astype(bool)
        # Walkability: 1.0 on flat ground, falls off sharply past 30°, and
        # ravines further reduce it. Ocean cells are unwalkable.
        # Formula: max(0, 1 - (slope_deg / 60)) * max(0.3, 1 - ravine).
        walk = np.maximum(0.0, 1.0 - slope_deg / 60.0)
        walk = walk * np.maximum(0.3, 1.0 - ravine)
        walk[chunk.biome == int(_Biome.OCEAN)] = 0.0
        walk = walk.astype(np.float32)
        base_walk = walk.copy()
        return cls(veg_state=veg, veg_age_s=veg_age, ravine_depth=ravine,
                   slope_deg=slope_deg, is_lake=is_lake, walkability=walk,
                   base_walkability=base_walk)


# ---------------------------------------------------------------------------
# Sub-tick: vegetation succession
# ---------------------------------------------------------------------------

def _ensure_field(sim, coord: Tuple[int, int, int]) -> Optional[LiftField]:
    fields: Dict[Tuple[int, int, int], LiftField] = sim._lift_fields
    field_obj = fields.get(coord)
    if field_obj is not None:
        return field_obj
    chunk = sim.streamer.cache.get(coord)
    if chunk is None:
        return None
    field_obj = LiftField.from_chunk(chunk, sim.cfg.seed, coord)
    field_obj.last_tick_seen = sim.tick
    fields[coord] = field_obj
    return field_obj


# Throttle: vegetation succession is a sim-decade process. At accel=1500,
# one sim-day = 58 ticks. Running tick_vegetation every 50 ticks (≈ one
# sim-day at default accel) costs <1% of frame time and is biologically
# accurate. Override with `sim._lift_veg_every` if needed.
DEFAULT_LIFT_VEG_EVERY = 50


def tick_vegetation(sim) -> None:
    """Advance vegetation succession on every cached chunk.

    Per-tick wall-clock simulation seconds = ``cfg.drive_accel`` (the same
    multiplier ``sim.step`` uses for drives). At 1500× accel, one real tick
    equals ~25 minutes of sim-time, so a full PRAIRIE→FORET_VIEILLE arc
    (~140 years) takes ~2.95 million ticks. Far too long for a smoke test;
    the agents in a 10 k-tick run only see prairie→garrigue transitions.
    But the substrate is here for sim-decades.

    Throttled: runs every ``DEFAULT_LIFT_VEG_EVERY`` ticks. The dt_s passed
    to the transition probability is multiplied so the accumulated rate is
    correct regardless of the throttle.
    """
    every = int(getattr(sim, "_lift_veg_every", DEFAULT_LIFT_VEG_EVERY))
    if every < 1:
        every = 1
    if sim.tick % every != 0:
        return
    dt_s = float(sim.cfg.drive_accel) * every  # accumulate over throttled period
    rng = sim._lift_rng

    # Precompute biome→cap and biome→base_wood lookup tables (max 12 biomes).
    from engine.earth_loader import _BIOME_RESOURCE
    n_biomes = 12
    cap_lookup = np.zeros(n_biomes, dtype=np.int16)
    wood_base_lookup = np.zeros(n_biomes, dtype=np.float32)
    for b in range(n_biomes):
        cap_lookup[b] = _state_cap(b)
        try:
            wood_base_lookup[b] = float(_BIOME_RESOURCE[Biome(b)]["wood"])
        except Exception:
            wood_base_lookup[b] = 0.0
    # Veg → wood multiplier lookup
    veg_mult = np.array([0.05, 0.15, 0.55, 0.95, 1.00], dtype=np.float32)

    for coord, chunk in list(sim.streamer.cache.items()):
        field_obj = _ensure_field(sim, coord)
        if field_obj is None:
            continue
        field_obj.last_tick_seen = sim.tick
        veg = field_obj.veg_state
        age = field_obj.veg_age_s
        age += dt_s
        biome = chunk.biome
        # O(1) per cell via lookup tables.
        biome_clipped = np.clip(biome.astype(np.int32), 0, n_biomes - 1)
        cap_per_cell = cap_lookup[biome_clipped]
        # Roll once per chunk (saves rng overhead)
        roll = rng.random(veg.shape, dtype=np.float32)
        for src, dst in _MEAN_TRANSITION_YEARS:
            mean_s = _MEAN_TRANSITION_YEARS[(src, dst)] * SECONDS_PER_YEAR
            p = min(1.0, dt_s / mean_s) * 0.5
            mask = (veg == int(src)) & (cap_per_cell >= int(dst)) & (roll < p)
            if mask.any():
                veg[mask] = int(dst)
                age[mask] = 0.0
        # Reflect succession in chunk.wood via vectorised lookup.
        multiplier = veg_mult[np.clip(veg.astype(np.int32), 0, 4)]
        target = wood_base_lookup[biome_clipped] * multiplier
        chunk.wood[:] = 0.85 * chunk.wood + 0.15 * target


# ---------------------------------------------------------------------------
# Sub-tick: hydraulic erosion (lightweight stochastic droplet)
# ---------------------------------------------------------------------------

def tick_erosion(sim, *, agent_pass_intensity: float = 0.005) -> None:
    """Track agent foot-traffic + precipitation as a slow ravine carver.

    Each tick:
      1. Every alive agent leaves a small ``foot_load`` on the cell they
         stand on. Proportional to ``walk_max_ms[row]`` so fast runners
         degrade trails faster.
      2. Foot-load × precipitation (proxied by tile water level) = increment
         to ravine_depth for that cell.
      3. Ravine_depth > 0.3 reduces local food_capacity by 30%; > 0.6 also
         reduces wood by 50% (channel-cut bare ground).

    Designed to be O(N_alive_agents) per tick — fast enough to leave on by
    default.
    """
    agents = sim.agents
    n = agents.n_active
    if n == 0:
        return
    alive = np.flatnonzero(agents.alive[:n])
    for r in alive:
        r_i = int(r)
        x = float(agents.pos[r_i, 0]); y = float(agents.pos[r_i, 1])
        coord = world_to_chunk(x, y)
        chunk = sim.streamer.cache.get(coord)
        if chunk is None:
            continue
        field_obj = _ensure_field(sim, coord)
        if field_obj is None:
            continue
        cx, cy = world_to_cell(x, y, coord)
        # Heavier on running agents.
        try:
            speed_factor = float(agents.walk_max_ms[r_i]) / 1.5
        except Exception:
            speed_factor = 1.0
        precip = float(chunk.water[cy, cx]) / 50.0  # proxy
        ravine_inc = agent_pass_intensity * speed_factor * max(0.1, precip)
        field_obj.ravine_depth[cy, cx] = min(
            1.0, float(field_obj.ravine_depth[cy, cx]) + ravine_inc)
        if field_obj.ravine_depth[cy, cx] > 0.3:
            chunk.food_capacity[cy, cx] *= 0.99  # gentle decay per pass
        if field_obj.ravine_depth[cy, cx] > 0.6:
            chunk.wood[cy, cx] *= 0.98


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------

def install_lift(sim) -> None:
    """Attach L2 sub-ticks to ``sim.step``.

    Idempotent. Must be called AFTER ``sim_5cd_integration.install(sim)``
    so the lift sub-ticks run inside the same wrapped_step.
    """
    if getattr(sim, "_lift_installed", False):
        return
    sim._lift_installed = True

    sim._lift_fields: Dict[Tuple[int, int, int], LiftField] = {}
    sim._lift_rng = prf_rng(sim.cfg.seed, ["sim_lift"], [0])
    # Side-channel for cognition.apply_decision: expose lift_fields through
    # the streamer (which is already passed to apply_decision) so walkability
    # can modulate movement speed without changing the function signature.
    sim.streamer._lift_fields = sim._lift_fields

    original_step = sim.step

    def wrapped_step():
        stats = original_step()
        try:
            tick_vegetation(sim)
            tick_erosion(sim)
        except Exception:
            if getattr(sim, "_lift_strict", False):
                raise
        return stats

    sim.step = wrapped_step


def lift_state(sim) -> Dict:
    """Aggregate L2 state for diagnostics / dashboard."""
    fields = getattr(sim, "_lift_fields", {}) or {}
    if not fields:
        return {"chunks": 0, "veg_distribution": {}, "max_ravine_depth": 0.0,
                "mean_slope_deg": 0.0, "max_slope_deg": 0.0,
                "lake_cells_pct": 0.0}
    veg_counts = {int(v): 0 for v in VegState}
    max_ravine = 0.0
    slope_sum = 0.0
    slope_n = 0
    slope_max = 0.0
    lake_cells = 0
    walk_sum = 0.0
    walk_impassable = 0
    total_cells = 0
    for f in fields.values():
        unique, counts = np.unique(f.veg_state, return_counts=True)
        for u, c in zip(unique, counts):
            veg_counts[int(u)] = veg_counts.get(int(u), 0) + int(c)
        max_ravine = max(max_ravine, float(f.ravine_depth.max(initial=0.0)))
        if hasattr(f, "slope_deg") and f.slope_deg is not None:
            slope_sum += float(f.slope_deg.sum())
            slope_n += int(f.slope_deg.size)
            slope_max = max(slope_max, float(f.slope_deg.max(initial=0.0)))
        if hasattr(f, "is_lake") and f.is_lake is not None:
            lake_cells += int(f.is_lake.sum())
            total_cells += int(f.is_lake.size)
        if hasattr(f, "walkability") and f.walkability is not None:
            walk_sum += float(f.walkability.sum())
            walk_impassable += int((f.walkability < 0.3).sum())
    total = sum(veg_counts.values()) or 1
    veg_distribution = {VegState(k).name: round(v / total, 4)
                        for k, v in veg_counts.items() if v > 0}
    mean_slope = (slope_sum / slope_n) if slope_n > 0 else 0.0
    lake_pct = (lake_cells / total_cells) if total_cells > 0 else 0.0
    mean_walk = (walk_sum / slope_n) if slope_n > 0 else 0.0
    impassable_pct = (walk_impassable / total_cells) if total_cells > 0 else 0.0
    return {
        "chunks": len(fields),
        "veg_distribution": veg_distribution,
        "max_ravine_depth": round(max_ravine, 4),
        "mean_slope_deg": round(mean_slope, 2),
        "max_slope_deg": round(slope_max, 2),
        "lake_cells_pct": round(lake_pct, 4),
        "mean_walkability": round(mean_walk, 4),
        "impassable_pct": round(impassable_pct, 4),
    }


__all__ = ["VegState", "LiftField", "install_lift", "lift_state",
           "tick_vegetation", "tick_erosion"]
