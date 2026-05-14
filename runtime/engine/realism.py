"""Reality Engine — couches de réalisme par-dessus L1+L2.

Wires four extra subsystems into a Genesis ``Simulation`` so agents inhabit
a world that feels alive:

  * **Hydrology**  — D8 flow accumulation from the DEM → emergent rivers.
                     Cells with high accumulation become drainage channels.
  * **Wildlife**   — per-chunk populations of deer / fish / wolves with
                     Lotka-Volterra dynamics. Deer feed on grass, fish live
                     in water cells, wolves prey on deer.
  * **Trails**     — agent footprints deposit per-cell trail intensity that
                     decays slowly. High trail = path = boosted walkability
                     for everyone following.
  * **Seasons**    — Earth-real calendar driving day/night + winter/summer
                     temperature modulations consumed by ``world.weather_at``.

All four are **opt-in** and **deterministic** via ``engine.core.prf_rng``.

Usage::

    from engine.world_builder import WorldBuilder
    from engine.realism import install_realism

    world = WorldBuilder("lausanne").anchor(46.51, 6.63).size_km(2).build()
    install_realism(world.sim,
                    hydrology=True,
                    wildlife={"deer": 60, "fish": 200, "wolf": 4},
                    trails=True,
                    seasons={"year": 2026, "day_of_year": 120})
    world.run(2000)
    print(world.summary()["realism"])  # ← exposed automatically

The realism state is read by ``realism_state(sim)`` and surfaced through
``/api/realism_state`` if the dashboard is up.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.world import (Biome, CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M,
                          world_to_cell, world_to_chunk)


# ---------------------------------------------------------------------------
# Hydrology — D8 flow accumulation per chunk
# ---------------------------------------------------------------------------

@dataclass
class HydrologyField:
    """Per-chunk hydrology data.

    ``flow_acc`` is computed once on first visit and cached. ``river_mask``
    flags cells whose accumulation exceeds ``river_threshold``.
    """
    flow_acc: np.ndarray              # (CHUNK_SIZE, CHUNK_SIZE) float32
    river_mask: np.ndarray            # bool
    sea_drain: np.ndarray             # bool — flows off the chunk's edge

    @classmethod
    def from_chunk(cls, chunk, river_threshold: float = 8.0) -> "HydrologyField":
        h = chunk.height.astype(np.float32)
        n = h.shape[0]
        # Compute D8 flow direction: for each cell, neighbour with the lowest
        # height (ties broken deterministically by index order).
        pad = np.pad(h, 1, mode="constant", constant_values=np.float32("inf"))
        offsets = [(1, 0), (-1, 0), (0, 1), (0, -1),
                   (1, 1), (1, -1), (-1, 1), (-1, -1)]
        best_drop = np.full((n, n), 0.0, dtype=np.float32)
        best_dir = np.full((n, n), -1, dtype=np.int8)
        for k, (dy, dx) in enumerate(offsets):
            neigh = pad[1 + dy:1 + dy + n, 1 + dx:1 + dx + n]
            drop = h - neigh
            update = drop > best_drop
            best_drop[update] = drop[update]
            best_dir[update] = k
        flow = np.ones((n, n), dtype=np.float32)
        order = np.argsort(-h, axis=None)
        ys, xs = np.unravel_index(order, h.shape)
        for i in range(order.size):
            y = int(ys[i]); x = int(xs[i])
            d = int(best_dir[y, x])
            if d < 0:
                continue
            dy, dx = offsets[d]
            ny, nx = y + dy, x + dx
            if 0 <= ny < n and 0 <= nx < n:
                flow[ny, nx] += flow[y, x]
        # River cells: high-accumulation drainage OR pre-existing water from
        # the L1 WorldCover layer (lakes, ponds, perennial streams).
        l1_water = (chunk.water > 50.0)
        river_mask = (flow > river_threshold) | l1_water
        # Cells whose downhill direction points off the chunk edge are
        # "sea drains" — water exits the chunk here. Useful for joining
        # cross-chunk river networks in a future pass.
        sea = np.zeros((n, n), dtype=bool)
        for y in range(n):
            for x in range(n):
                d = int(best_dir[y, x])
                if d < 0:
                    continue
                dy, dx = offsets[d]
                ny, nx = y + dy, x + dx
                if not (0 <= ny < n and 0 <= nx < n):
                    sea[y, x] = True
        return cls(flow_acc=flow, river_mask=river_mask, sea_drain=sea)


def _ensure_hydrology(sim, coord: Tuple[int, int, int]
                       ) -> Optional[HydrologyField]:
    fields = sim._realism_hydro
    f = fields.get(coord)
    if f is not None:
        return f
    chunk = sim.streamer.cache.get(coord)
    if chunk is None:
        return None
    threshold = float(getattr(sim, "_realism_river_threshold", 50.0))
    f = HydrologyField.from_chunk(chunk, river_threshold=threshold)
    fields[coord] = f
    # Inject river water into the chunk so DRINK/FORAGE detect it.
    if f.river_mask.any():
        chunk.water[f.river_mask] = np.maximum(
            chunk.water[f.river_mask], 200.0)
    return f


# ---------------------------------------------------------------------------
# Wildlife — per-chunk Lotka-Volterra populations
# ---------------------------------------------------------------------------

@dataclass
class WildlifePool:
    """Per-chunk wildlife state. One pool per chunk per species."""
    deer: float = 0.0
    fish: float = 0.0
    wolf: float = 0.0
    last_tick: int = 0


def _init_wildlife_for_chunk(sim, coord, chunk) -> WildlifePool:
    # Use biome to seed initial populations. Configured counts are TOTAL
    # across the map — we distribute proportionally to suitable-biome chunks.
    biome_id = int(chunk.biome.flat[chunk.biome.size // 2])
    cfg = sim._realism_wildlife_cfg or {}
    rng = prf_rng(sim.cfg.seed, ["wildlife", str(coord)], [])
    forest = biome_id in (int(Biome.BOREAL_FOREST), int(Biome.TEMPERATE_FOREST),
                          int(Biome.TEMPERATE_RAINFOREST),
                          int(Biome.TROPICAL_DRY_FOREST),
                          int(Biome.TROPICAL_RAINFOREST))
    water = biome_id == int(Biome.OCEAN)
    grass = biome_id in (int(Biome.GRASSLAND), int(Biome.SAVANNA))
    # Estimate suitable-chunk count from the current cache. Cheap and
    # converges as more chunks load.
    n_chunks = max(1, len(sim.streamer.cache))
    deer_per_chunk = float(cfg.get("deer", 60)) / n_chunks
    fish_per_chunk = float(cfg.get("fish", 200)) / n_chunks
    wolf_per_chunk = float(cfg.get("wolf", 4)) / n_chunks
    if forest:
        deer = deer_per_chunk * (1.2 + 0.6 * float(rng.random()))
        fish = 0.0
        wolf = wolf_per_chunk * (1.0 + float(rng.random()))
    elif grass:
        deer = deer_per_chunk * (1.5 + 0.7 * float(rng.random()))
        fish = 0.0
        wolf = wolf_per_chunk * (1.2 + 0.6 * float(rng.random()))
    elif water:
        deer = 0.0
        fish = fish_per_chunk * (1.5 + float(rng.random()))
        wolf = 0.0
    else:
        deer = deer_per_chunk * 0.3 * float(rng.random())
        fish = 0.0
        wolf = wolf_per_chunk * 0.3 * float(rng.random())
    return WildlifePool(deer=deer, fish=fish, wolf=wolf,
                        last_tick=int(sim.tick))


WOLF_ATTACK_THRESHOLD = 2.0
WOLF_ATTACK_PROB = 0.005       # per tick when wolves >= threshold


def _tick_wolf_predation(sim) -> None:
    """Per-tick check : agents inside chunks with wolf >= 2.0 take damage.

    Determinism : per-(seed, tick, row) ``prf_rng`` so two runs with the same
    seed produce identical attack sequences. Damage is small (+0.10 injuries,
    -0.05 vitality) so a single attack rarely kills; sustained predation
    will. Events accumulate on ``sim._realism_event_buffer``.
    """
    pools = getattr(sim, "_realism_wildlife", None)
    if not pools:
        return
    agents = sim.agents
    n = agents.n_active
    if n == 0:
        return
    alive = np.flatnonzero(agents.alive[:n])
    buf = sim._realism_event_buffer
    for r in alive:
        r_i = int(r)
        x = float(agents.pos[r_i, 0]); y = float(agents.pos[r_i, 1])
        coord = world_to_chunk(x, y)
        pool = pools.get(coord)
        if pool is None or pool.wolf < WOLF_ATTACK_THRESHOLD:
            continue
        rng = prf_rng(sim.cfg.seed, ["wolf_attack"], [r_i, int(sim.tick)])
        if float(rng.random()) < WOLF_ATTACK_PROB:
            agents.injuries[r_i] = min(1.0, float(agents.injuries[r_i]) + 0.10)
            agents.vitality[r_i] = max(0.0, float(agents.vitality[r_i]) - 0.05)
            buf.append({"kind": "wolf_attack", "row": r_i})


def tick_wildlife(sim) -> None:
    """Lotka-Volterra step for every chunk, throttled to once per 25 ticks.

    Also handles wolf predation on agents : when a chunk holds >= 2 wolves
    and a living agent stands in it, a small probability per tick injures
    the agent. Events are buffered onto ``sim._realism_event_buffer`` to be
    flushed by the wrapped step.
    """
    _tick_wolf_predation(sim)
    every = int(getattr(sim, "_realism_wildlife_every", 25))
    if sim.tick % every != 0:
        return
    pools: Dict[Tuple[int, int, int], WildlifePool] = sim._realism_wildlife
    accel = float(sim.cfg.drive_accel)
    dt_days = accel * every / 86_400.0  # sim-days elapsed
    # Per-chunk capacities derived from total target population.
    n_chunks = max(1, len(sim.streamer.cache))
    deer_growth = 0.015 * dt_days
    deer_capacity = (float(sim._realism_wildlife_cfg.get("deer", 60))
                     / n_chunks) * 2.0
    wolf_growth = 0.01 * dt_days
    wolf_pred = 0.0008 * dt_days
    deer_pred_pressure = 0.015 * dt_days
    fish_growth = 0.012 * dt_days
    fish_cap = (float(sim._realism_wildlife_cfg.get("fish", 200))
                / n_chunks) * 1.5
    # Visit cached chunks
    for coord, chunk in list(sim.streamer.cache.items()):
        pool = pools.get(coord)
        if pool is None:
            pool = _init_wildlife_for_chunk(sim, coord, chunk)
            pools[coord] = pool
        # Logistic deer growth, reduced by wolves
        if pool.deer > 0:
            d = pool.deer
            d += deer_growth * d * (1.0 - d / deer_capacity)
            d -= deer_pred_pressure * pool.wolf
            pool.deer = max(0.0, d)
        # Wolves grow with deer, decay without
        if pool.wolf > 0 or pool.deer > 10:
            w = pool.wolf
            w += wolf_pred * pool.deer
            w -= wolf_growth * w  # natural decay
            pool.wolf = max(0.0, min(w, deer_capacity * 0.2))
        # Fish — logistic, independent
        if pool.fish > 0:
            ff = pool.fish
            ff += fish_growth * ff * (1.0 - ff / fish_cap)
            pool.fish = max(0.0, ff)
        pool.last_tick = int(sim.tick)


# ---------------------------------------------------------------------------
# Trails — agent footprints
# ---------------------------------------------------------------------------

@dataclass
class TrailField:
    intensity: np.ndarray              # (CHUNK_SIZE, CHUNK_SIZE) float32

    @classmethod
    def empty(cls) -> "TrailField":
        return cls(intensity=np.zeros((CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32))


def tick_walkability_from_trails(sim) -> None:
    """Trails become precursors to roads — boost local walkability where
    foot-traffic accumulates (Architecture §16 emergent urbanism).

    For every chunk that has BOTH a ``LiftField`` (L2) and a ``TrailField``
    (realism), recompute ``walkability = clip(base_walkability + trail_intensity
    * 0.3, 0, 1)``. Capped at +30% bonus per cell. Idempotent: starts from the
    immutable ``base_walkability`` snapshot taken at chunk-init, so the
    walkability field never drifts even if called every tick.
    """
    lift_fields = getattr(sim, "_lift_fields", None)
    trail_fields = getattr(sim, "_realism_trails", None)
    if not lift_fields or not trail_fields:
        return
    for coord, trail in trail_fields.items():
        lf = lift_fields.get(coord)
        if lf is None or lf.base_walkability is None:
            continue
        walk_boost = trail.intensity * 0.3
        np.clip(lf.base_walkability + walk_boost, 0.0, 1.0,
                out=lf.walkability)


def tick_trails(sim) -> None:
    """Deposit foot-prints + decay existing trails.

    Cheap O(N_agents) deposition + O(N_visited_chunks) decay every 5 ticks.
    """
    agents = sim.agents
    n = agents.n_active
    if n == 0:
        return
    fields: Dict[Tuple[int, int, int], TrailField] = sim._realism_trails
    alive = np.flatnonzero(agents.alive[:n])
    for r in alive:
        r_i = int(r)
        x = float(agents.pos[r_i, 0]); y = float(agents.pos[r_i, 1])
        coord = world_to_chunk(x, y)
        chunk = sim.streamer.cache.get(coord)
        if chunk is None:
            continue
        f = fields.get(coord)
        if f is None:
            f = TrailField.empty()
            fields[coord] = f
        cx, cy = world_to_cell(x, y, coord)
        # Light deposit + neighbour bleed
        f.intensity[cy, cx] = min(1.0, f.intensity[cy, cx] + 0.05)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < CHUNK_SIZE and 0 <= nx < CHUNK_SIZE and (dy or dx):
                    f.intensity[ny, nx] = min(1.0, f.intensity[ny, nx] + 0.005)
    # Decay every 5 ticks
    if sim.tick % 5 == 0:
        for f in fields.values():
            f.intensity *= 0.995
            np.clip(f.intensity, 0.0, 1.0, out=f.intensity)


# ---------------------------------------------------------------------------
# Seasons — Earth-real calendar
# ---------------------------------------------------------------------------

@dataclass
class SeasonalClock:
    year: int = 2026
    day_of_year: int = 1     # 1..365 (or 366 in leap years)
    seconds_into_day: float = 0.0  # 0..86400

    def advance(self, seconds: float) -> None:
        self.seconds_into_day += seconds
        while self.seconds_into_day >= 86_400.0:
            self.seconds_into_day -= 86_400.0
            self.day_of_year += 1
            if self.day_of_year > 365:
                self.day_of_year = 1
                self.year += 1

    @property
    def season_name(self) -> str:
        # Northern-hemisphere meteorological seasons.
        d = self.day_of_year
        if 60 <= d < 152:
            return "spring"
        if 152 <= d < 244:
            return "summer"
        if 244 <= d < 335:
            return "autumn"
        return "winter"

    @property
    def hour_of_day(self) -> float:
        return self.seconds_into_day / 3600.0


def tick_seasons(sim) -> None:
    """Advance the seasonal clock proportionally to drive_accel."""
    clk: SeasonalClock = sim._realism_seasons
    secs_this_tick = float(sim.cfg.drive_accel)
    clk.advance(secs_this_tick)


# ---------------------------------------------------------------------------
# Disease epidemics — minimal SIR overlay
# ---------------------------------------------------------------------------

def tick_disease(sim) -> None:
    """Probabilistic SIR contagion between agents within INTERACT_RADIUS.

    Uses existing ``agents.infectious_until`` field added by Phase 5cd. If
    not present, this tick is a no-op. Cheap O(N) with grid acceleration.
    """
    agents = sim.agents
    if not hasattr(agents, "infectious_until"):
        return
    n = agents.n_active
    if n < 2:
        return
    rng = sim._realism_rng
    grid = getattr(sim, "_grid", None)
    if grid is None or grid.n_indexed < 2:
        return
    cooldown_ticks = 200    # ~3 sim-hours of infectious window @ accel 1500
    transmission_p = 0.005
    every = int(getattr(sim, "_realism_disease_every", 10))
    if sim.tick % every != 0:
        return
    infectious_now = agents.infectious_until[:n] > sim.tick
    if infectious_now.sum() == 0:
        # Tiny chance of spontaneous outbreak when there's no infectious
        # agent, to keep things lively. ~once every ~5000 ticks at full pop.
        if rng.random() < 0.0001:
            row = int(rng.integers(0, n))
            if agents.alive[row]:
                agents.infectious_until[row] = sim.tick + cooldown_ticks
        return
    alive = np.flatnonzero(agents.alive[:n])
    for r in alive:
        if not infectious_now[int(r)]:
            continue
        px = float(agents.pos[r, 0]); py = float(agents.pos[r, 1])
        cands = grid.query_disk(px, py, 3.0, exclude_row=int(r))
        for j in cands or []:
            j_i = int(j)
            if not agents.alive[j_i]:
                continue
            if agents.infectious_until[j_i] > sim.tick:
                continue
            if rng.random() < transmission_p:
                agents.infectious_until[j_i] = sim.tick + cooldown_ticks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install_realism(sim, *,
                    hydrology: bool = True,
                    wildlife: Optional[Dict[str, float]] = None,
                    trails: bool = True,
                    seasons: Optional[Dict[str, int]] = None,
                    disease: bool = True,
                    river_threshold: float = 8.0) -> None:
    """Install the Reality Engine on ``sim``. Idempotent.

    Parameters
    ----------
    hydrology : whether to compute D8 flow accumulation per chunk
    wildlife  : dict of species seed populations, e.g. ``{"deer": 60, "fish": 200, "wolf": 4}``
                or ``None`` to disable.
    trails    : whether agent footprints accumulate into paths
    seasons   : ``{"year": 2026, "day_of_year": 120}`` or ``None``
    disease   : whether the SIR epidemic overlay runs
    river_threshold : flow accumulation above which a cell is classified river
    """
    if getattr(sim, "_realism_installed", False):
        return
    sim._realism_installed = True

    sim._realism_rng = prf_rng(sim.cfg.seed, ["realism"], [0])

    if hydrology:
        sim._realism_hydro: Dict[Tuple[int, int, int], HydrologyField] = {}
        sim._realism_river_threshold = float(river_threshold)

    if wildlife is not None:
        sim._realism_wildlife: Dict[Tuple[int, int, int], WildlifePool] = {}
        sim._realism_wildlife_cfg = dict(wildlife)
        sim._realism_wildlife_every = 25
        # Cross-module bridge : cognition.perceive / apply_decision read this
        # off the streamer to detect game and resolve HUNT actions.
        sim.streamer._wildlife_pools = sim._realism_wildlife
        # Buffer of wildlife->agent raw events flushed via annalist after step.
        sim._realism_event_buffer = []

    if trails:
        sim._realism_trails: Dict[Tuple[int, int, int], TrailField] = {}

    if seasons is not None:
        sim._realism_seasons = SeasonalClock(
            year=int(seasons.get("year", 2026)),
            day_of_year=int(seasons.get("day_of_year", 1)),
            seconds_into_day=float(seasons.get("seconds_into_day", 0.0)),
        )

    if disease:
        sim._realism_disease_every = 10

    # Wrap sim.step
    original_step = sim.step

    def wrapped_step():
        stats = original_step()
        try:
            if hydrology:
                # Lazy hydrology — fill in newly-visited chunks
                for coord in list(sim.streamer.cache.keys()):
                    if coord not in sim._realism_hydro:
                        _ensure_hydrology(sim, coord)
            if wildlife is not None:
                tick_wildlife(sim)
            if trails:
                tick_trails(sim)
                # Trails affect walkability live (throttled to every 10 ticks).
                if sim.tick % 10 == 0:
                    tick_walkability_from_trails(sim)
            if seasons is not None:
                tick_seasons(sim)
            if disease:
                tick_disease(sim)
            # Flush wildlife->agent events through the annalist so smoke
            # tests / dashboards see ``wolf_attack`` (and friends).
            buf = getattr(sim, "_realism_event_buffer", None)
            if buf:
                sim.annalist.record_tick(sim.tick, sim.agents,
                                         births=[], deaths=[],
                                         raw_events=list(buf))
                buf.clear()
        except Exception:
            if getattr(sim, "_realism_strict", False):
                raise
        return stats

    sim.step = wrapped_step


def realism_state(sim) -> Dict:
    """Aggregate diagnostic snapshot. JSON-serialisable.

    Includes : river-cell count, wildlife totals (deer/fish/wolf), trail
    intensity peak, season name + hour, infectious-agent count.
    """
    out: Dict = {}
    # Hydrology
    hydro = getattr(sim, "_realism_hydro", None)
    if hydro:
        river_cells = 0
        total_cells = 0
        for f in hydro.values():
            river_cells += int(f.river_mask.sum())
            total_cells += int(f.river_mask.size)
        out["hydrology"] = {
            "chunks_indexed": len(hydro),
            "river_cells_pct": round(
                (river_cells / total_cells) if total_cells else 0.0, 4),
            "river_threshold": float(getattr(sim, "_realism_river_threshold", 0.0)),
        }
    # Wildlife
    wl = getattr(sim, "_realism_wildlife", None)
    if wl:
        deer = 0.0; fish = 0.0; wolf = 0.0
        for p in wl.values():
            deer += p.deer; fish += p.fish; wolf += p.wolf
        out["wildlife"] = {
            "chunks_indexed": len(wl),
            "deer_total": round(deer, 1),
            "fish_total": round(fish, 1),
            "wolf_total": round(wolf, 1),
        }
    # Trails
    tr = getattr(sim, "_realism_trails", None)
    if tr:
        max_intensity = 0.0
        active_cells = 0
        for f in tr.values():
            max_intensity = max(max_intensity, float(f.intensity.max(initial=0.0)))
            active_cells += int((f.intensity > 0.1).sum())
        out["trails"] = {
            "chunks_indexed": len(tr),
            "max_intensity": round(max_intensity, 3),
            "well_trodden_cells": active_cells,
        }
    # Seasons
    sc: Optional[SeasonalClock] = getattr(sim, "_realism_seasons", None)
    if sc is not None:
        out["seasons"] = {
            "year": sc.year, "day_of_year": sc.day_of_year,
            "hour_of_day": round(sc.hour_of_day, 2),
            "season": sc.season_name,
        }
    # Disease
    if hasattr(sim.agents, "infectious_until"):
        n = sim.agents.n_active
        if n > 0:
            infected = int((sim.agents.infectious_until[:n] > sim.tick).sum())
            out["disease"] = {"infected_now": infected}
    return out


__all__ = [
    "install_realism", "realism_state",
    "HydrologyField", "WildlifePool", "TrailField", "SeasonalClock",
    "tick_walkability_from_trails",
]
