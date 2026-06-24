"""Perception -> Decision -> Action pipeline (Phase 4)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from engine.agent import ActionKind, AgentRegistry, DriveKind
from engine.spatial import SpatialGrid
from engine.world import (Biome, CHUNK_SIDE_M, CHUNK_SIZE, ChunkStreamer,
                          VOXEL_SIZE_M, _stable_bytes_sig, biome_npp,
                          biome_habitability, world_to_chunk, world_to_cell,
                          chunks_around, chunks_around_sorted,
                          invalidate_resource_masks)


PERCEPTION_RADIUS_M = 60.0
INTERACT_RADIUS_M = 1.8

# Wave 52: Rust perception — try to import scan_chunk from genesis_world.
try:
    from genesis_world import py_scan_chunk as _rust_scan_chunk
    _HAS_RUST_SCAN = True
except ImportError:
    _HAS_RUST_SCAN = False
CRITICAL_THRESHOLD = 0.85
ACT_THRESHOLD = 0.40
MATURITY_TICKS = 1_000
COOLDOWN_TICKS = 5_000
MATING_RADIUS_M = 2.0
SOCIAL_TALK_RADIUS_M = 3.5


@dataclass
class PerceivedTarget:
    kind: str
    x: float
    y: float
    distance: float
    qty: float
    other_row: Optional[int] = None


@dataclass
class Observation:
    row: int
    pos: Tuple[float, float, float]
    drives: np.ndarray
    vitality: float
    nearest: dict
    near_agents: List[int]
    dominant_drive: int
    tick: Optional[int] = None
    reproduction_readiness: float = 0.0


def _dominant_drive(drives):
    candidates = [DriveKind.THIRST, DriveKind.HUNGER, DriveKind.THERMAL,
                  DriveKind.SLEEP, DriveKind.FATIGUE]
    best, bv = candidates[0], -1.0
    for k in candidates:
        v = float(drives[int(k)])
        if v > bv:
            bv, best = v, k
    return int(best)


def perceive(agents, row, streamer, radius_m=PERCEPTION_RADIUS_M, grid=None, tick=None, near_cache=None, resource_cache=None):
    px, py, pz = (float(agents.pos[row, 0]), float(agents.pos[row, 1]), float(agents.pos[row, 2]))
    # Wave 55: tuple instead of np.array (saves ~3μs per call, 8-element array).
    # Only used for indexing + comparison, never for numpy math.
    drives = (float(agents.hunger[row]), float(agents.thirst[row]),
              float(agents.sleep[row]), float(agents.fatigue[row]),
              float(agents.thermal[row]), float(agents.pain[row]),
              float(agents.stress[row]), float(agents.loneliness[row]))
    nearest = {}
    chunk_center = world_to_chunk(px, py, pz)
    # r_chunks formula tightened (sprint 2026-05-16, optim #3):
    #   Previously: ``ceil(radius / CHUNK_SIDE_M) + 1`` -> 3 at radius=60m,side=32m
    #               -> 7x7 = 49 chunks in the outer window.
    #   Now:        ``ceil(radius / CHUNK_SIDE_M)``      -> 2
    #               -> 5x5 = 25 chunks (-49 %).
    # Geometric proof : the closest point of an offset-r chunk to an agent
    # anywhere inside its home chunk is at distance ``(r-1) * CHUNK_SIDE_M``.
    # For r=3 (32 m * 2 = 64 m) that already exceeds 60 m perception, so the
    # extra +1 ring was redundant. The bbox prefilter below already throws
    # away mid-ring chunks whose closest cell is out of range.
    r_chunks = max(1, int(math.ceil(radius_m / CHUNK_SIDE_M)))
    r_eff_sq = radius_m * radius_m
    wildlife_pools = getattr(streamer, "_wildlife_pools", None)

    # Wave 60: batch resource cache — Rust pre-computed water/food/shelter
    # for this agent across ALL chunks in a single FFI call.  Skip the
    # per-chunk Python scan loop entirely; only the lightweight wildlife
    # (game) scan still runs in Python (dict lookups only, no FFI).
    if resource_cache is not None:
        w_hit, f_hit, s_hit = resource_cache
        if w_hit is not None:
            nearest["water"] = PerceivedTarget(
                "water", float(w_hit[0]), float(w_hit[1]),
                float(w_hit[2]), float(w_hit[3]))
        if f_hit is not None:
            nearest["food"] = PerceivedTarget(
                "food", float(f_hit[0]), float(f_hit[1]),
                float(f_hit[2]), float(f_hit[3]))
        if s_hit is not None:
            nearest["shelter"] = PerceivedTarget(
                "shelter", float(s_hit[0]), float(s_hit[1]),
                float(s_hit[2]), float(s_hit[3]))
        # Wildlife / game scan — lightweight dict lookups only.
        if wildlife_pools is not None:
            for coord in chunks_around_sorted(chunk_center, r_chunks):
                pool = wildlife_pools.get(coord)
                if pool is None or pool.deer < 1.0:
                    continue
                cx0 = coord[0] * CHUNK_SIDE_M
                cy0 = coord[1] * CHUNK_SIDE_M
                gx = cx0 + CHUNK_SIDE_M * 0.5
                gy = cy0 + CHUNK_SIDE_M * 0.5
                gdist = float(math.hypot(gx - px, gy - py))
                if gdist <= radius_m:
                    cur = nearest.get("game")
                    if cur is None or gdist < cur.distance:
                        nearest["game"] = PerceivedTarget(
                            "game", gx, gy, gdist, float(pool.deer))
    else:
        # Python fallback — per-chunk scan with edge-d² pruning.
        # Wave 50: sorted chunk iteration (closest-first) + chunk-edge
        # distance pruning for aggressive early-exit.  Instead of
        # INTERACT_RADIUS_M (1.8 m — tight), compare to the actual
        # minimum agent-to-chunk-edge distance so we skip chunks that
        # provably cannot contain a closer resource.
        for coord in chunks_around_sorted(chunk_center, r_chunks):
            chunk = streamer.cache.get(coord)
            if chunk is None:
                continue
            cx0 = coord[0] * CHUNK_SIDE_M
            cy0 = coord[1] * CHUNK_SIDE_M
            cx1 = cx0 + CHUNK_SIDE_M
            cy1 = cy0 + CHUNK_SIDE_M
            dx = 0.0 if (cx0 <= px <= cx1) else (cx0 - px if px < cx0 else px - cx1)
            dy = 0.0 if (cy0 <= py <= cy1) else (cy0 - py if py < cy0 else py - cy1)
            chunk_edge_d2 = dx * dx + dy * dy
            if chunk_edge_d2 > r_eff_sq:
                continue
            # Wave 50: all-found break — if all 3 resources already found
            # closer than this chunk's nearest edge, no cell here can improve.
            _w_found = "water" in nearest
            _f_found = "food" in nearest
            _s_found = "shelter" in nearest
            if _w_found and _f_found and _s_found:
                _w_d2 = nearest["water"].distance * nearest["water"].distance
                _f_d2 = nearest["food"].distance * nearest["food"].distance
                _s_d2 = nearest["shelter"].distance * nearest["shelter"].distance
                if _w_d2 <= chunk_edge_d2 and _f_d2 <= chunk_edge_d2 and _s_d2 <= chunk_edge_d2:
                    # Only game scan remains relevant for outer chunks.
                    if wildlife_pools is not None:
                        pool = wildlife_pools.get(coord)
                        if pool is not None and pool.deer >= 1.0:
                            gx = (cx0 + cx1) * 0.5
                            gy = (cy0 + cy1) * 0.5
                            gdist = float(math.hypot(gx - px, gy - py))
                            if gdist <= radius_m:
                                cur = nearest.get("game")
                                if cur is None or gdist < cur.distance:
                                    nearest["game"] = PerceivedTarget(
                                        "game", gx, gy, gdist, float(pool.deer))
                    continue
            # Wave 50: chunk-edge distance pruning per resource.
            need_w = not _w_found or (nearest["water"].distance * nearest["water"].distance > chunk_edge_d2)
            need_f = not _f_found or (nearest["food"].distance * nearest["food"].distance > chunk_edge_d2)
            need_s = not _s_found or (nearest["shelter"].distance * nearest["shelter"].distance > chunk_edge_d2)
            _scan_chunk(chunk, px, py, radius_m, nearest, tick,
                        need_water=need_w, need_food=need_f, need_shelter=need_s)
            # Wildlife pool check : chunk holds >= 1 deer -> mark its centre as game.
            if wildlife_pools is not None:
                pool = wildlife_pools.get(coord)
                if pool is not None and pool.deer >= 1.0:
                    gx = (cx0 + cx1) * 0.5
                    gy = (cy0 + cy1) * 0.5
                    gdist = float(math.hypot(gx - px, gy - py))
                    if gdist <= radius_m:
                        cur = nearest.get("game")
                        if cur is None or gdist < cur.distance:
                            nearest["game"] = PerceivedTarget(
                                "game", gx, gy, gdist, float(pool.deer))

    # Wave 58: batch near-agent scan (Rust) or Wave 55 scalar fallback.
    near_agents = []
    _pos = agents.pos
    if near_cache is not None:
        # Wave 58: pre-computed by Rust py_batch_near_agents — already
        # sorted by distance, truncated to max_k=16.
        for j_dist in near_cache:
            j = int(j_dist[0])
            d = float(j_dist[1])
            near_agents.append(j)
            if "agent" not in nearest or d < nearest["agent"].distance:
                nearest["agent"] = PerceivedTarget(
                    "agent", float(_pos[j, 0]), float(_pos[j, 1]),
                    d, 1.0, other_row=j)
    else:
        # Wave 55: scalar near-agent scan — Python fallback.
        r2 = radius_m * radius_m
        _alive = agents.alive
        n = agents.n_active
        if grid is not None and grid.n_indexed > 1:
            candidates = grid.query_disk(px, py, radius_m, exclude_row=row)
        elif n > 1:
            candidates = [j for j in range(n) if j != row]
        else:
            candidates = None
        if candidates:
            _hits = []
            for j in candidates:
                if not _alive[j]:
                    continue
                dx = float(_pos[j, 0]) - px
                dy = float(_pos[j, 1]) - py
                d2_j = dx * dx + dy * dy
                if d2_j < r2:
                    _hits.append((d2_j, j))
            if _hits:
                _hits.sort()
                for d2_j, j in _hits[:16]:
                    d = math.sqrt(d2_j)
                    near_agents.append(j)
                    if "agent" not in nearest or d < nearest["agent"].distance:
                        nearest["agent"] = PerceivedTarget(
                            "agent", float(_pos[j, 0]), float(_pos[j, 1]),
                            d, 1.0, other_row=j)

    mem = agents.memory[row]
    if "water" not in nearest and drives[int(DriveKind.THIRST)] >= ACT_THRESHOLD and mem.known_water_locations:
        wx, wy = mem.known_water_locations[-1]
        nearest["water_remembered"] = PerceivedTarget("water", float(wx), float(wy),
                                                      float(math.hypot(wx - px, wy - py)), 1.0)
    if "food" not in nearest and drives[int(DriveKind.HUNGER)] >= ACT_THRESHOLD and mem.known_food_locations:
        fx, fy = mem.known_food_locations[-1]
        nearest["food_remembered"] = PerceivedTarget("food", float(fx), float(fy),
                                                     float(math.hypot(fx - px, fy - py)), 1.0)

    return Observation(row=row, pos=(px, py, pz), drives=drives,
                       vitality=float(agents.vitality[row]),
                       nearest=nearest, near_agents=near_agents,
                       dominant_drive=_dominant_drive(drives),
                       tick=tick, reproduction_readiness=0.0)


_CACHED_CELL_GRID = {}
_CELL_GRID_CACHE_CAP = 2048  # bounded - eviction is FIFO via insertion order
_CELL_OFFSETS_X = ((np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)
_CELL_OFFSETS_Y = ((np.arange(CHUNK_SIZE) + 0.5) * VOXEL_SIZE_M).astype(np.float32)


def _chunk_cell_world_xy(chunk):
    key = chunk.coord
    cached = _CACHED_CELL_GRID.get(key)
    if cached is not None:
        return cached
    cx, cy, _ = chunk.coord
    ox = cx * CHUNK_SIDE_M
    oy = cy * CHUNK_SIDE_M
    xs = ox + _CELL_OFFSETS_X
    ys = oy + _CELL_OFFSETS_Y
    XX, YY = np.meshgrid(xs, ys, indexing="xy")
    if len(_CACHED_CELL_GRID) >= _CELL_GRID_CACHE_CAP:
        oldest = next(iter(_CACHED_CELL_GRID))
        _CACHED_CELL_GRID.pop(oldest, None)
    _CACHED_CELL_GRID[key] = (XX, YY)
    return XX, YY


def evict_cell_grid_cache(keys):
    """Drop cached cell-grid arrays for the given chunk coords."""
    for k in keys:
        _CACHED_CELL_GRID.pop(k, None)


def _chunk_resource_masks(chunk):
    """Return cached resource masks + presence flags, recomputing only
    when invalidated.

    Tuple shape : ``(water_mask, food_mask, shelter_mask,
    has_water, has_food, has_shelter)`` — the three masks are
    ``(64, 64) bool`` arrays, the three flags are Python ``bool``
    (computed once on cache fill so per-call ``.any()`` checks become
    O(1) attribute reads).

    The cache is invalidated by ``engine.world.invalidate_resource_masks``
    which **must** be called from every site that mutates ``chunk.water``,
    ``chunk.food_kcal``, ``chunk.wood``, ``chunk.stone`` or
    ``chunk.height``. Stale masks would break bit-perfect determinism
    when a mid-tick DRINK/FORAGE crosses the resource threshold.
    """
    cached = chunk._mask_cache
    if cached is not None:
        return cached
    water_mask = chunk.water > np.float32(5.0)
    food_mask = chunk.food_kcal > np.float32(5.0)
    shelter_mask = (
        (chunk.wood > np.float32(30.0))
        | ((chunk.stone > np.float32(25.0))
           & (chunk.height > np.float32(800.0)))
    )
    has_water = bool(water_mask.any())
    has_food = bool(food_mask.any())
    has_shelter = bool(shelter_mask.any())
    entry = (water_mask, food_mask, shelter_mask,
             has_water, has_food, has_shelter)
    chunk._mask_cache = entry
    return entry


def _scan_chunk(chunk, px, py, radius_m, out, tick=None, need_water=True,
                need_food=True, need_shelter=True):
    """Find the nearest water / food / shelter cell in ``chunk``.

    Wave 52: uses Rust ``scan_chunk`` when available (single-pass over
    all cells, no temporary numpy arrays). Falls back to the Python
    vectorised path when the Rust backend is unavailable.

    Determinism : both paths find the nearest cell by minimum d² with
    row-major tie-break for equal distances.
    """
    if _HAS_RUST_SCAN:
        _scan_chunk_rust(chunk, px, py, radius_m, out, need_water, need_food, need_shelter)
        return
    _scan_chunk_py(chunk, px, py, radius_m, out, need_water, need_food, need_shelter)


def _scan_chunk_rust(chunk, px, py, radius_m, out, need_water, need_food, need_shelter):
    """Wave 52: Rust-backed chunk scan — single pass, no temp arrays."""
    cx, cy, _ = chunk.coord
    chunk_ox = cx * CHUNK_SIDE_M
    chunk_oy = cy * CHUNK_SIDE_M
    w_hit, f_hit, s_hit = _rust_scan_chunk(
        chunk.water.ravel(), chunk.food_kcal.ravel(),
        chunk.wood.ravel(), chunk.stone.ravel(), chunk.height.ravel(),
        chunk_ox, chunk_oy, VOXEL_SIZE_M,
        px, py, radius_m,
        need_water, need_food, need_shelter,
    )
    if w_hit is not None:
        x, y, dist, qty = w_hit
        cur = out.get("water")
        if cur is None or dist < cur.distance:
            out["water"] = PerceivedTarget("water", x, y, dist, qty)
    if f_hit is not None:
        x, y, dist, qty = f_hit
        cur = out.get("food")
        if cur is None or dist < cur.distance:
            out["food"] = PerceivedTarget("food", x, y, dist, qty)
    if s_hit is not None:
        x, y, dist, qty = s_hit
        cur = out.get("shelter")
        if cur is None or dist < cur.distance:
            out["shelter"] = PerceivedTarget("shelter", x, y, dist, qty)


def _scan_chunk_py(chunk, px, py, radius_m, out, need_water, need_food, need_shelter):
    """Python fallback: dense vectorised path (optim #3c+)."""
    (water_mask, food_mask, shelter_mask,
     has_water, has_food, has_shelter) = _chunk_resource_masks(chunk)
    scan_water = has_water and need_water
    scan_food = has_food and need_food
    scan_shelter = has_shelter and need_shelter
    if not (scan_water or scan_food or scan_shelter):
        return

    XX, YY = _chunk_cell_world_xy(chunk)
    dx = XX - np.float32(px)
    dy = YY - np.float32(py)
    d2 = dx * dx + dy * dy
    r2 = np.float32(radius_m * radius_m)
    in_r = d2 <= r2
    if not in_r.any():
        return

    if scan_water:
        m = in_r & water_mask
        if m.any():
            d2m = np.where(m, d2, np.float32(np.inf))
            flat_idx = int(np.argmin(d2m))
            ay, ax = divmod(flat_idx, d2.shape[1])
            dist = float(math.sqrt(float(d2[ay, ax])))
            cur = out.get("water")
            if cur is None or dist < cur.distance:
                out["water"] = PerceivedTarget(
                    "water", float(XX[ay, ax]), float(YY[ay, ax]), dist,
                    float(chunk.water[ay, ax]))

    if scan_food:
        m = in_r & food_mask
        if m.any():
            d2m = np.where(m, d2, np.float32(np.inf))
            flat_idx = int(np.argmin(d2m))
            ay, ax = divmod(flat_idx, d2.shape[1])
            dist = float(math.sqrt(float(d2[ay, ax])))
            cur = out.get("food")
            if cur is None or dist < cur.distance:
                out["food"] = PerceivedTarget(
                    "food", float(XX[ay, ax]), float(YY[ay, ax]), dist,
                    float(chunk.food_kcal[ay, ax]))

    if scan_shelter:
        m = in_r & shelter_mask
        if m.any():
            d2m = np.where(m, d2, np.float32(np.inf))
            flat_idx = int(np.argmin(d2m))
            ay, ax = divmod(flat_idx, d2.shape[1])
            dist = float(math.sqrt(float(d2[ay, ax])))
            cur = out.get("shelter")
            if cur is None or dist < cur.distance:
                out["shelter"] = PerceivedTarget(
                    "shelter", float(XX[ay, ax]), float(YY[ay, ax]), dist,
                    float(chunk.wood[ay, ax] + chunk.stone[ay, ax]))


@dataclass
class Decision:
    action: int
    target_x: float = 0.0
    target_y: float = 0.0
    confidence: float = 0.0
    other_row: Optional[int] = None

    @staticmethod
    def idle():
        return Decision(action=int(ActionKind.IDLE), confidence=0.0)


def decide(agents, obs, sim=None):
    row = obs.row
    drives = obs.drives
    nearest = obs.nearest

    if sim is not None:
        st = getattr(sim, "_life_emergence", None)
        if st is not None:
            ap = st.last_appraisals.get(row)
            if ap is not None:
                obs.reproduction_readiness = ap.reproduction_readiness
            elif ap is None and obs.tick is not None:
                from engine.appraise import appraise_agent
                ap = appraise_agent(agents, row, sim.streamer, sim.tick, sim)
                st.last_appraisals[row] = ap
                obs.reproduction_readiness = ap.reproduction_readiness

    for k in (DriveKind.THIRST, DriveKind.HUNGER, DriveKind.THERMAL,
              DriveKind.SLEEP, DriveKind.FATIGUE):
        if drives[int(k)] >= CRITICAL_THRESHOLD:
            d = _act_on(agents, row, obs, int(k))
            if d is not None:
                return d

    # AUDIT FIX 2026-05-19 — pro-social SHARE must out-prioritise mating when
    # a hungry neighbour is adjacent and the agent holds surplus food. Without
    # this re-order, mate_target was always returned first (any near agent
    # passed _find_mate) and SHARE never fired — see
    # tests/test_engine.py::test_share_fires_under_stockpile_conditions.
    agreeableness = float(agents.agreeableness[row])
    if agreeableness > 0.40 and obs.near_agents and agents.inv_food[row] > 0.15:
        candidates = [(j, float(agents.hunger[j])) for j in obs.near_agents if agents.alive[j]]
        if candidates:
            best = max(candidates, key=lambda x: x[1])
            if best[1] > 0.40:
                tx = float(agents.pos[best[0], 0])
                ty = float(agents.pos[best[0], 1])
                d = math.hypot(tx - obs.pos[0], ty - obs.pos[1])
                if d < SOCIAL_TALK_RADIUS_M:
                    return Decision(int(ActionKind.SHARE), tx, ty, 0.6, best[0])
                # Walk toward the hungry neighbour if pro-sociality is high
                # enough (>0.65) and they are within perception range. This
                # gives the agent a real chance to close the gap and SHARE
                # rather than getting hijacked by the mating branch below.
                if (agreeableness > 0.65 and d < PERCEPTION_RADIUS_M):
                    return Decision(int(ActionKind.WALK_TO), tx, ty, 0.55, best[0])

    if (drives[int(DriveKind.HUNGER)] < 0.6 and drives[int(DriveKind.THIRST)] < 0.6
            and obs.reproduction_readiness >= 0.35):
        mate_target = _find_mate(agents, row, obs.near_agents, sim=sim)
        if mate_target is not None:
            tx = float(agents.pos[mate_target, 0])
            ty = float(agents.pos[mate_target, 1])
            d = math.hypot(tx - obs.pos[0], ty - obs.pos[1])
            if d < MATING_RADIUS_M:
                return Decision(int(ActionKind.MATE), tx, ty, 0.7, mate_target)
            return Decision(int(ActionKind.WALK_TO), tx, ty, 0.5, mate_target)

    aggression = float(agents.aggression[row])
    stress = float(drives[int(DriveKind.STRESS)])
    if aggression > 0.70 and stress > 0.35 and obs.near_agents:
        for j in obs.near_agents:
            if agents.alive[j]:
                aff = agents.relations[row].affinity.get(j, 0.0)
                if aff < -0.10:
                    tx = float(agents.pos[j, 0])
                    ty = float(agents.pos[j, 1])
                    d = math.hypot(tx - obs.pos[0], ty - obs.pos[1])
                    if d < INTERACT_RADIUS_M:
                        return Decision(int(ActionKind.FIGHT), tx, ty, 0.65, j)
                    if d < PERCEPTION_RADIUS_M:
                        return Decision(int(ActionKind.WALK_TO), tx, ty, 0.45, j)

    extra = float(agents.extraversion[row])
    if (extra > 0.40 and obs.near_agents
            and drives[int(DriveKind.HUNGER)] < 0.65
            and drives[int(DriveKind.THIRST)] < 0.65):
        for j in obs.near_agents:
            if not agents.alive[j]:
                continue
            tx = float(agents.pos[j, 0]); ty = float(agents.pos[j, 1])
            d = math.hypot(tx - obs.pos[0], ty - obs.pos[1])
            if d < SOCIAL_TALK_RADIUS_M:
                return Decision(int(ActionKind.SPEAK), tx, ty, 0.35, j)

    dom = obs.dominant_drive
    if drives[dom] >= ACT_THRESHOLD:
        d = _act_on(agents, row, obs, dom)
        if d is not None:
            return d

    curiosity = float(agents.curiosity[row])
    if curiosity > 0.6:
        # D12 wire: before wandering at random, a curious agent that perceives
        # a knappable tool-stone outcrop (C2) goes to debit it. Emergent, not
        # scripted — survival is already satisfied here, so this is the agent
        # *choosing* to invest idle time in a useful stone it can see.
        ts = _seek_toolstone(agents, row, obs, sim)
        if ts is not None:
            return ts
        ang = float(agents.heading[row]) + (curiosity - 0.5) * 0.8
        tx = obs.pos[0] + math.cos(ang) * 20.0
        ty = obs.pos[1] + math.sin(ang) * 20.0
        return Decision(int(ActionKind.EXPLORE), tx, ty, 0.3)

    return Decision.idle()


def _jitter_target(row, tx, ty, drive_kind):
    """Deterministic per-(row,drive) offset inside +-GOAL_JITTER_M of target.

    Uses a splitmix64-style hash mixer. uint64 wraparound is the intended
    behaviour, but numpy emits an overflow ``RuntimeWarning`` on the
    multiply, so we silence it explicitly with ``np.errstate``.
    """
    with np.errstate(over="ignore"):
        seed = (np.uint64(row) ^ (np.uint64(int(drive_kind)) * _JITTER_PRIME_X))
        seed = (seed ^ (seed >> np.uint64(33))) * _JITTER_PRIME_Y
        seed = seed ^ (seed >> np.uint64(33))
    u = (float(int(seed) & 0xFFFF) / 65535.0) * 2.0 - 1.0
    v = (float((int(seed) >> 16) & 0xFFFF) / 65535.0) * 2.0 - 1.0
    return tx + u * GOAL_JITTER_M, ty + v * GOAL_JITTER_M


def _seek_toolstone(agents, row, obs, sim):
    """Emergent stone-age foraging — the agent loop's consumption of C2.

    A survival-satisfied, curious agent that SEES a knappable tool-stone
    outcrop (``lithic_outcrop.best_toolstone_near``) heads there and knaps a
    flake rather than wandering at random. Utility-based action selection: a
    sharp, useful stone outranks blind exploration. Nothing is scripted — the
    agent perceives a glassy / sharp-edged outcrop and *chooses* to debit it;
    the WORLD decides whether that stone actually yields an edge (the cue's
    ``knap_quality``). The agent learns the stone→edge link by acting.

    Gated on C2 being installed on the world (its cue cache exists). Two hot-loop
    safety rules, mirroring the C3/DRINK wire: (1) we only *read* an already
    installed C2 — never ``install_*`` mid-iteration (``install_lithic_outcrop``
    only re-enters the idempotent ``install_geology``, which early-returns once
    ``_geology_state`` exists, so no wrapper-chain is re-patched); (2) any error
    degrades to ``None`` (plain exploration), never crashes the tick.

    Returns a ``Decision`` (KNAP if standing on the outcrop, else WALK_TO) or
    ``None`` to fall through to ordinary exploration.
    """
    if sim is None or getattr(sim, "_lithic_cue_cache", None) is None:
        return None
    if float(agents.inv_stone[row]) >= TOOLSTONE_SATED_KG:
        return None
    if _inventory_mass(agents, row) >= float(agents.inv_capacity_kg[row]) - 1e-3:
        return None
    try:
        from engine import lithic_outcrop as lo
        cue = lo.best_toolstone_near(sim, int(row),
                                     perception_radius_m=TOOLSTONE_PERCEPT_M)
    except Exception:
        return None
    if cue is None:
        return None
    tx = (cue.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (cue.coord[1] + 0.5) * CHUNK_SIDE_M
    px, py = obs.pos[0], obs.pos[1]
    d = math.hypot(tx - px, ty - py)
    # Confidence sits above random EXPLORE (0.3) but below survival actions, so
    # tool-stone foraging never out-prioritises hunger / thirst / shelter.
    conf = 0.30 + 0.20 * float(cue.confidence)
    if d < INTERACT_RADIUS_M:
        return Decision(int(ActionKind.KNAP), tx, ty, conf)
    return Decision(int(ActionKind.WALK_TO), tx, ty, min(conf, 0.34))


def _act_on(agents, row, obs, drive_kind):
    nearest = obs.nearest
    if drive_kind == int(DriveKind.THIRST):
        t = nearest.get("water") or nearest.get("water_remembered")
        if t is None:
            return None
        if t.distance < INTERACT_RADIUS_M:
            return Decision(int(ActionKind.DRINK), t.x, t.y, 0.95)
        jx, jy = _jitter_target(row, t.x, t.y, drive_kind)
        return Decision(int(ActionKind.WALK_TO), jx, jy, 0.85)
    if drive_kind == int(DriveKind.HUNGER):
        if agents.inv_food[row] > 0.1:
            return Decision(int(ActionKind.EAT), 0.0, 0.0, 0.9)
        # Hunt nearby game (chunk-resident deer) if perceived. Hunters need
        # at least moderate aggression OR risk_tolerance to engage.
        game = nearest.get("game")
        if game is not None:
            hunt_drive = float(agents.aggression[row]) + float(agents.risk_tolerance[row])
            if hunt_drive >= 0.40:
                if game.distance < HUNT_RADIUS_M:
                    return Decision(int(ActionKind.HUNT), game.x, game.y, 0.95)
                jx, jy = _jitter_target(row, game.x, game.y, drive_kind)
                return Decision(int(ActionKind.WALK_TO), jx, jy, 0.80)
        t = nearest.get("food") or nearest.get("food_remembered")
        if t is None:
            return None
        if t.distance < INTERACT_RADIUS_M:
            return Decision(int(ActionKind.FORAGE), t.x, t.y, 0.9)
        jx, jy = _jitter_target(row, t.x, t.y, drive_kind)
        return Decision(int(ActionKind.WALK_TO), jx, jy, 0.75)
    if drive_kind == int(DriveKind.THERMAL):
        t = nearest.get("shelter")
        if t is None:
            return None
        if t.distance < INTERACT_RADIUS_M:
            return Decision(int(ActionKind.SEEK_SHELTER), t.x, t.y, 0.85)
        return Decision(int(ActionKind.WALK_TO), t.x, t.y, 0.7)
    if drive_kind in (int(DriveKind.SLEEP), int(DriveKind.FATIGUE)):
        return Decision(int(ActionKind.SLEEP), 0.0, 0.0, 0.8)
    return None


def _find_mate(agents, row, near, sim=None):
    if not near:
        return None
    best, bs = None, -1e9
    my_aff = agents.relations[row].affinity
    for j in near:
        if not agents.alive[j]:
            continue
        if sim is not None and getattr(sim, "_life_emergence", None) is not None:
            from engine.life_emergence import mate_compatibility
            score = mate_compatibility(sim, row, j)
        else:
            a = my_aff.get(j, 0.0)
            score = a + float(agents.agreeableness[j]) * 0.4 - float(agents.aggression[j]) * 0.2
        if score > bs:
            bs, best = score, j
    if best is not None and bs < 0.25:
        return None
    return best


ARRIVE_RADIUS_M = 1.5
DRINK_RELIEF = 0.30
EAT_RELIEF = 0.25


def _hydration_factor(ppt: float, potable: bool) -> float:
    """Signed hydration factor of drinking water of salinity ``ppt`` — composes the
    C3 ``water_potability`` truth so the world never lies in *behaviour*.

    Fresh water sustains fully (+1.0); brackish-but-drinkable water helps less
    (down to +0.4 at the potability ceiling); sea / brine water causes **net
    dehydration** (negative, scaling with salinity toward −1.0 at seawater) — the
    osmotic load costs the body more water than the drink provides. The agent
    discovers this by acting; nothing is scripted."""
    from engine import water_potability as wp
    if potable:
        if ppt <= wp.FRESH_MAX_PPT:
            return 1.0
        span = max(1e-6, wp.POTABLE_MAX_PPT - wp.FRESH_MAX_PPT)
        return float(max(0.4, 1.0 - 0.6 * (ppt - wp.FRESH_MAX_PPT) / span))
    span = max(1e-6, wp.SEAWATER_PPT - wp.POTABLE_MAX_PPT)
    frac = min(1.0, max(0.0, (ppt - wp.POTABLE_MAX_PPT) / span))
    return float(-frac)


def _drink_factor(sim, chunk, chunk_c) -> float:
    """Hydration factor of the water at ``chunk_c`` for a DRINK action.

    Gated on the C3 ``water_potability`` capability being **already installed** on
    ``sim`` (its cue cache exists) — this is the first real consumption of a
    substrate capability by the agent loop. When C3 is active, hydration follows
    the true salinity (fresh sustains; sea / brine net-dehydrates). When it is
    NOT active there is no salinity truth in the world, so we keep the legacy
    full-hydration behaviour (factor 1.0) — drinking is just drinking.

    Two safety rules for the hot loop: (1) never trigger ``install_*`` here — the
    geology installer patches ``apply_decision`` and doing that mid-iteration
    corrupts the wrapper chain; we only *read* an already-installed C3. (2) a
    biome-only fallback is deliberately NOT used: ``Biome.OCEAN == 0`` is
    indistinguishable from an unpopulated (all-zero) biome array, so it would
    falsely dehydrate agents drinking inland water in lightweight sims."""
    try:
        if sim is not None and getattr(sim, "_water_cue_cache", None) is not None:
            from engine import water_potability as wp
            cue = wp.water_cue_for_chunk(sim, tuple(int(c) for c in chunk_c))
            if cue is not None:
                return _hydration_factor(float(cue.salinity_ppt), bool(cue.potable))
    except Exception:
        return 1.0
    return 1.0   # no salinity capability active → legacy full hydration
SLEEP_RELIEF = 0.40
FORAGE_RATE = 18.0
FORAGE_KCAL_PER_KG = 300.0
GOAL_JITTER_M = 0.45
HUNT_RADIUS_M = 6.0          # chunk-scale: agent + deer share the chunk
HUNT_KCAL_PER_DEER = 800.0   # successful deer hunt = ~800 kcal returned home
# AUDIT FIX 2026-05-17 — share/fight/speak/flee tunables.
SHARE_RADIUS_M = 3.5
SHARE_MIN_INV_KG = 0.15      # giver must hold at least this much food
SHARE_QTY_KG = 0.10          # transfer per SHARE action (capped by giver inv)
FIGHT_RADIUS_M = 1.8
FIGHT_DAMAGE_BASE = 0.18     # injury delta to victim before defence modulation
FIGHT_RETALIATION_AFFINITY = -0.05
SHARE_AFFINITY_BONUS = +0.05
SPEAK_AFFINITY_BONUS = +0.005
FLEE_SPEED_MULT = 1.0        # FLEE always runs (uses run_max_ms)

# D12 wire (2026-06-24) — emergent stone-age tool-stone foraging. The agent
# loop consumes the C2 ``lithic_outcrop`` capability: a survival-satisfied,
# curious agent that PERCEIVES a knappable outcrop walks to it and knaps a
# flake instead of wandering at random. Nothing is scripted — the agent picks
# up a sharp-looking stone; the WORLD decides (via LithicCue.knap_quality)
# whether it truly yields a cutting edge. The first real agent consumer of a
# *resource-gathering* affordance from the arc (DRINK only corrected physiology).
TOOLSTONE_PERCEPT_M = 96.0   # sight range for outcrops (chunk-scale; cues memoised)
TOOLSTONE_SATED_KG = 3.0     # stop seeking once this much raw tool-stone is carried
KNAP_STONE_KG = 1.5          # raw stone debited per KNAP action
KNAP_TOOL_YIELD = 0.6        # usable cutting edge per unit of true knap_quality
INV_TOOLS_MAX = 5.0          # tool inventory ceiling
_JITTER_PRIME_X = np.uint64(0x9E3779B97F4A7C15)
_JITTER_PRIME_Y = np.uint64(0xBF58476D1CE4E5B9)

_INVENTORY_MASS_FIELDS = (
    "inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal",
    "inv_flint", "inv_clay", "inv_fiber", "inv_leather", "inv_bone",
    "inv_copper", "inv_tin", "inv_bronze", "inv_iron", "inv_ceramic",
    "inv_charcoal", "inv_grain",
)


def _inventory_mass(agents, row: int) -> float:
    """Sum the kg-equivalent mass of all inventory fields present on agents."""
    total = 0.0
    for fld in _INVENTORY_MASS_FIELDS:
        arr = getattr(agents, fld, None)
        if arr is None:
            continue
        try:
            total += float(arr[row])
        except (IndexError, TypeError):
            continue
    return total


# AUDIT FIX 2026-05-17 -----------------------------------------------------
# Episodic memory helpers. The AgentRegistry.memory[row] objects expose
# `short_term` / `long_term` lists with capacity bounds, but no engine
# code ever wrote to them before this fix. We add a single conservative
# write-site so the data structure is actually used; salience-weighted
# eviction is left for future work.

def remember_short(agents, row: int, kind: str, payload: dict) -> None:
    """Append a small event record to the agent's short-term memory.

    Bounded by ``EpisodicMemory.capacity_short``; FIFO eviction.
    """
    mem = agents.memory[row]
    if mem is None:
        return
    mem.short_term.append({"kind": kind, "data": payload})
    over = len(mem.short_term) - int(getattr(mem, "capacity_short", 32))
    if over > 0:
        del mem.short_term[:over]


def promote_memories(agents, row: int, min_repeats: int = 2) -> int:
    """Promote frequent short-term entries to long-term, return count moved.

    A naive but useful rule: any (kind, data) pair that appears at least
    ``min_repeats`` times in short-term gets consolidated into long-term
    once, then the redundant short-term copies are pruned. Bounded by
    ``EpisodicMemory.capacity_long``.
    """
    mem = agents.memory[row]
    if mem is None:
        return 0
    if not mem.short_term:
        return 0
    seen: dict = {}
    for entry in mem.short_term:
        key = (entry.get("kind"), repr(entry.get("data")))
        seen[key] = seen.get(key, 0) + 1
    moved = 0
    long_cap = int(getattr(mem, "capacity_long", 256))
    for (kind, _data_repr), n_seen in seen.items():
        if n_seen < min_repeats:
            continue
        # Find the first matching short-term entry and copy it long-term.
        for entry in mem.short_term:
            if entry.get("kind") == kind:
                mem.long_term.append(entry)
                moved += 1
                break
        # Prune all but one short-term copy of this kind.
        kept = False
        new_short = []
        for entry in mem.short_term:
            if entry.get("kind") == kind:
                if kept:
                    continue
                kept = True
            new_short.append(entry)
        mem.short_term = new_short
    over = len(mem.long_term) - long_cap
    if over > 0:
        del mem.long_term[:over]
    return moved


def apply_decision(agents, row, decision, streamer, tick, sim=None):
    events = []
    act = decision.action
    px, py = float(agents.pos[row, 0]), float(agents.pos[row, 1])

    if act == int(ActionKind.IDLE):
        agents.vel[row, :2] = 0.0
        return events

    if act in (int(ActionKind.WALK_TO), int(ActionKind.EXPLORE)):
        tx, ty = decision.target_x, decision.target_y
        dx, dy = tx - px, ty - py
        d = math.hypot(dx, dy)
        if d < ARRIVE_RADIUS_M:
            agents.vel[row, :2] = 0.0
            agents.pos[row, 0] = tx; agents.pos[row, 1] = ty
            return events
        nx, ny = dx / max(d, 1e-6), dy / max(d, 1e-6)
        any_crit = (agents.hunger[row] >= CRITICAL_THRESHOLD or
                    agents.thirst[row] >= CRITICAL_THRESHOLD or
                    agents.thermal[row] >= CRITICAL_THRESHOLD)
        speed = float(agents.run_max_ms[row]) if any_crit else float(agents.walk_max_ms[row])
        # Modulate speed by local walkability (trails-as-roads, §16). Lift
        # fields are exposed on the streamer by install_lift. Floor at 0.3
        # so impassable cells don't fully freeze the agent.
        lift_fields = getattr(streamer, "_lift_fields", None)
        if lift_fields is not None:
            ccoord = world_to_chunk(px, py)
            lf = lift_fields.get(ccoord)
            if lf is not None and getattr(lf, "walkability", None) is not None:
                ccx, ccy = world_to_cell(px, py, ccoord)
                walk = float(lf.walkability[ccy, ccx])
                speed *= max(0.3, walk)
        agents.vel[row, 0] = nx * speed
        agents.vel[row, 1] = ny * speed
        agents.heading[row] = math.atan2(ny, nx)
        return events

    if act == int(ActionKind.DRINK):
        agents.vel[row, :2] = 0.0
        chunk_c = world_to_chunk(px, py)
        chunk = streamer.get(tick, chunk_c)
        cx, cy = world_to_cell(px, py, chunk_c)
        avail = float(chunk.water[cy, cx])
        consumed = min(avail, 5.0)
        chunk.water[cy, cx] = avail - consumed
        invalidate_resource_masks(chunk)
        if consumed > 0:
            # The world must not lie in BEHAVIOUR: hydration depends on the water's
            # salinity (C3 water_potability). Fresh water sustains; brackish helps
            # less; sea / brine water causes NET DEHYDRATION — the agent drinks but
            # is harmed (thirst rises). The agent discovers this by acting.
            factor = _drink_factor(sim, chunk, chunk_c)
            relief = DRINK_RELIEF * (consumed / 5.0) * factor
            agents.thirst[row] = float(
                np.clip(float(agents.thirst[row]) - relief, 0.0, 1.0))
            if factor > 0.0:
                # only drinkable water replenishes the canteen and is remembered as
                # a reliable water source (emergent: brine traps are not recorded).
                agents.inv_water[row] = min(
                    float(agents.inv_water[row]) + 0.5 * factor, 2.0)
                mem = agents.memory[row]
                mem.known_water_locations.append((px, py))
                if len(mem.known_water_locations) > 8:
                    mem.known_water_locations.pop(0)
        return events

    if act == int(ActionKind.EAT):
        agents.vel[row, :2] = 0.0
        amount = min(float(agents.inv_food[row]), 0.5)
        if amount > 0:
            agents.inv_food[row] -= amount
            agents.hunger[row] = max(0.0, float(agents.hunger[row]) - EAT_RELIEF * (amount / 0.5))
        return events

    if act == int(ActionKind.FORAGE):
        agents.vel[row, :2] = 0.0
        chunk_c = world_to_chunk(px, py)
        chunk = streamer.get(tick, chunk_c)
        cx, cy = world_to_cell(px, py, chunk_c)
        avail = float(chunk.food_kcal[cy, cx])
        skill = 0.5 + 0.25 * float(agents.intelligence[row]) + 0.25 * float(agents.conscientiousness[row])
        extracted = min(avail, FORAGE_RATE * skill)
        chunk.food_kcal[cy, cx] = avail - extracted
        invalidate_resource_masks(chunk)
        cap_left = max(0.0, float(agents.inv_capacity_kg[row]) - _inventory_mass(agents, row))
        added = min(extracted / FORAGE_KCAL_PER_KG, cap_left)
        agents.inv_food[row] += added
        if extracted > 0:
            agents.hunger[row] = max(0.0, float(agents.hunger[row]) - 0.005)
            mem = agents.memory[row]
            mem.known_food_locations.append((px, py))
            if len(mem.known_food_locations) > 8:
                mem.known_food_locations.pop(0)
        return events

    if act == int(ActionKind.KNAP):
        # Debit the knappable outcrop the agent is standing on (C2). The world
        # never lies: raw stone always comes, but a usable CUTTING EDGE emerges
        # only in proportion to the stone's TRUE knapping quality — obsidian /
        # flint give razor tools, a quern-grade boulder barely any. The agent
        # learns the stone→edge link by acting; brine-trap analogue: a location
        # the world says is barren (no cue here) yields nothing and isn't
        # remembered. Surface gather only — NOT a geology mutation (no
        # geo.mine_at), so the mutation frontier (D10) stays frozen.
        agents.vel[row, :2] = 0.0
        if sim is None or getattr(sim, "_lithic_cue_cache", None) is None:
            return events
        cap_left = max(0.0, float(agents.inv_capacity_kg[row]) - _inventory_mass(agents, row))
        if cap_left <= 1e-3:
            return events
        try:
            from engine import lithic_outcrop as lo
            cue = lo.prospect_toolstone(sim, px, py)
        except Exception:
            return events
        if cue is None:
            return events   # the world says: no knappable stone crops out here
        gained = min(KNAP_STONE_KG, cap_left)
        agents.inv_stone[row] = float(agents.inv_stone[row]) + gained
        tool_gain = KNAP_TOOL_YIELD * float(cue.knap_quality) * (gained / KNAP_STONE_KG)
        agents.inv_tools[row] = float(
            min(float(agents.inv_tools[row]) + tool_gain, INV_TOOLS_MAX))
        mem = agents.memory[row]
        if mem is not None:
            locs = getattr(mem, "known_toolstone_locations", None)
            if locs is not None:
                locs.append((px, py))
                if len(locs) > 8:
                    locs.pop(0)
            remember_short(agents, row, "toolstone",
                           {"class": int(cue.knap_class), "material": cue.material})
        events.append({
            "kind": "knap",
            "row": int(row),
            "knap_class": int(cue.knap_class),
            "stone_kg": round(float(gained), 4),
            "tool_gain": round(float(tool_gain), 4),
        })
        return events

    if act == int(ActionKind.SLEEP):
        agents.vel[row, :2] = 0.0
        agents.sleep[row] = max(0.0, float(agents.sleep[row]) - SLEEP_RELIEF)
        agents.fatigue[row] = max(0.0, float(agents.fatigue[row]) - SLEEP_RELIEF * 0.7)
        return events

    if act == int(ActionKind.SEEK_SHELTER):
        agents.vel[row, :2] = 0.0
        agents.thermal[row] = max(0.0, float(agents.thermal[row]) - 0.20)
        return events

    if act == int(ActionKind.MATE):
        agents.vel[row, :2] = 0.0
        return events

    # AUDIT FIX 2026-05-17 — SHARE was decided but never applied.
    if act == int(ActionKind.SHARE):
        agents.vel[row, :2] = 0.0
        j = decision.other_row
        if (j is None or j < 0 or j >= agents.n_active
                or not bool(agents.alive[int(j)])):
            return events
        # Both agents must be within social radius for SHARE to land.
        ox = float(agents.pos[int(j), 0])
        oy = float(agents.pos[int(j), 1])
        if math.hypot(ox - px, oy - py) > SHARE_RADIUS_M:
            return events
        giver_inv = float(agents.inv_food[row])
        if giver_inv < SHARE_MIN_INV_KG:
            return events
        qty = min(SHARE_QTY_KG, giver_inv - 0.5 * SHARE_MIN_INV_KG)
        if qty <= 0.0:
            return events
        agents.inv_food[row] = max(0.0, giver_inv - qty)
        agents.inv_food[int(j)] = float(agents.inv_food[int(j)]) + qty
        agents.hunger[int(j)] = max(
            0.0, float(agents.hunger[int(j)]) - EAT_RELIEF * (qty / 0.5))
        # Pro-social relationship update on both sides.
        try:
            agents.relations[row].update_affinity(int(j), SHARE_AFFINITY_BONUS)
            agents.relations[int(j)].update_affinity(row, SHARE_AFFINITY_BONUS)
        except Exception:
            pass
        # Empathy reward — the giver feels less stress / more vitality.
        try:
            agents.stress[row] = max(
                0.0, float(agents.stress[row]) - 0.01)
        except Exception:
            pass
        remember_short(agents, row, "shared", {"to": int(j), "qty": float(qty)})
        events.append({
            "kind": "share",
            "from": int(row),
            "to": int(j),
            "qty": float(qty),
        })
        return events

    # AUDIT FIX 2026-05-17 — FIGHT was decided but never applied.
    if act == int(ActionKind.FIGHT):
        agents.vel[row, :2] = 0.0
        j = decision.other_row
        if (j is None or j < 0 or j >= agents.n_active
                or not bool(agents.alive[int(j)])):
            return events
        ox = float(agents.pos[int(j), 0])
        oy = float(agents.pos[int(j), 1])
        if math.hypot(ox - px, oy - py) > FIGHT_RADIUS_M:
            return events
        # Damage scales with attacker aggression × inverse of victim
        # vitality. We clip injuries at 1.0 — mortality handler in sim.py
        # converts >=1.0 injuries to a VIOLENCE death.
        agg = float(agents.aggression[row])
        vit_v = max(0.05, float(agents.vitality[int(j)]))
        damage = FIGHT_DAMAGE_BASE * (0.5 + agg) / vit_v
        damage = float(max(0.0, min(0.6, damage)))
        agents.injuries[int(j)] = float(
            min(1.0, float(agents.injuries[int(j)]) + damage))
        agents.pain[int(j)] = float(
            min(1.5, float(agents.pain[int(j)]) + damage * 0.5))
        agents.stress[int(j)] = float(
            min(1.5, float(agents.stress[int(j)]) + damage * 0.8))
        try:
            agents.relations[int(j)].update_affinity(
                row, FIGHT_RETALIATION_AFFINITY)
            agents.relations[row].update_affinity(
                int(j), FIGHT_RETALIATION_AFFINITY * 0.5)
        except Exception:
            pass
        remember_short(agents, row, "fought",
                       {"vs": int(j), "dmg": float(damage)})
        events.append({
            "kind": "fight",
            "attacker": int(row),
            "victim": int(j),
            "damage": float(damage),
        })
        return events

    # AUDIT FIX 2026-05-17 — SPEAK was decided but only buffered when
    # sim_5cd_integration was installed. Without 5cd, no vocalize event
    # ever reached the annalist. Emit a baseline event here; the 5cd
    # patched_apply still buffers SPEAK BEFORE calling original_apply, so
    # both paths now produce exactly one vocalize event per SPEAK action
    # (the 5cd buffer is processed in tick_speech, and that path runs
    # only when 5cd is installed — see sim_5cd_integration.patched_apply
    # which captures SPEAK targets and then routes through tick_speech).
    if act == int(ActionKind.SPEAK):
        agents.vel[row, :2] = 0.0
        j = decision.other_row
        if j is None or j < 0 or j >= agents.n_active:
            return events
        if not bool(agents.alive[int(j)]):
            return events
        # Skip emission if the 5cd buffer is going to handle it — avoids
        # double-counting vocalize events when 5cd is installed.
        if getattr(agents, "_5cd_speak_handled", False):
            return events
        try:
            agents.relations[row].update_affinity(
                int(j), SPEAK_AFFINITY_BONUS)
            agents.relations[int(j)].update_affinity(
                row, SPEAK_AFFINITY_BONUS * 0.5)
        except Exception:
            pass
        # Deterministic lex signature from row + lexicon hash + tick %.
        try:
            lex = agents.lexicon[row]
            lex_sig = int(_stable_bytes_sig(
                lex.astype(np.float32).tobytes())) & 0xFFFF
        except Exception:
            lex_sig = (int(row) * 17 + int(tick) % 1009) & 0xFFFF
        remember_short(agents, row, "spoke", {"to": int(j),
                                              "lex_sig": int(lex_sig)})
        events.append({
            "kind": "vocalize",
            "from": int(row),
            "to": int(j),
            "lex_sig": int(lex_sig),
        })
        return events

    # AUDIT FIX 2026-05-17 — FLEE wasn't issued by core decide() but a
    # later policy may issue it. Move directly away from the perceived
    # threat at run speed.
    if act == int(ActionKind.FLEE):
        tx = float(decision.target_x)
        ty = float(decision.target_y)
        dx = px - tx
        dy = py - ty
        d = math.hypot(dx, dy)
        if d < 1e-6:
            # Degenerate — pick a deterministic direction by row.
            dx = 1.0 if (row % 2 == 0) else -1.0
            dy = 1.0 if ((row // 2) % 2 == 0) else -1.0
            d = math.hypot(dx, dy)
        nx, ny = dx / d, dy / d
        speed = float(agents.run_max_ms[row]) * FLEE_SPEED_MULT
        agents.vel[row, 0] = nx * speed
        agents.vel[row, 1] = ny * speed
        agents.heading[row] = math.atan2(ny, nx)
        try:
            agents.stress[row] = float(
                min(1.5, float(agents.stress[row]) + 0.01))
        except Exception:
            pass
        return events

    if act == int(ActionKind.HUNT):
        agents.vel[row, :2] = 0.0
        wildlife_pools = getattr(streamer, "_wildlife_pools", None)
        if wildlife_pools is None:
            return events
        # Look up the agent's chunk and any chunk within HUNT_RADIUS_M that
        # still holds >= 1 deer. Prefer the agent's own chunk first.
        chunk_c = world_to_chunk(px, py)
        target_coord = None
        pool = wildlife_pools.get(chunk_c)
        if pool is not None and pool.deer >= 1.0:
            target_coord = chunk_c
        else:
            # Fall back to neighbour chunks within hunt range.
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    cand = (chunk_c[0] + dx, chunk_c[1] + dy, chunk_c[2])
                    p = wildlife_pools.get(cand)
                    if p is not None and p.deer >= 1.0:
                        cx0 = cand[0] * CHUNK_SIDE_M + CHUNK_SIDE_M * 0.5
                        cy0 = cand[1] * CHUNK_SIDE_M + CHUNK_SIDE_M * 0.5
                        if math.hypot(cx0 - px, cy0 - py) <= HUNT_RADIUS_M + CHUNK_SIDE_M:
                            target_coord = cand
                            pool = p
                            break
                if target_coord is not None:
                    break
        if target_coord is None or pool is None:
            return events
        pool.deer = max(0.0, pool.deer - 1.0)
        # Convert kcal -> kg of meat at the same conversion FORAGE uses.
        kcal = HUNT_KCAL_PER_DEER
        kg_meat = kcal / FORAGE_KCAL_PER_KG
        cap_left = max(0.0, float(agents.inv_capacity_kg[row]) - _inventory_mass(agents, row))
        added = min(kg_meat, cap_left)
        agents.inv_food[row] += added
        agents.hunger[row] = max(0.0, float(agents.hunger[row]) - 0.10)
        mem = agents.memory[row]
        mem.known_food_locations.append((px, py))
        if len(mem.known_food_locations) > 8:
            mem.known_food_locations.pop(0)
        events.append({"kind": "hunt_success", "row": int(row),
                       "prey": "deer", "kcal": float(kcal)})
        return events

    return events
