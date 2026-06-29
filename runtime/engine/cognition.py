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
        # D12 wire: before wandering at random, a curious agent invests idle
        # time in useful resources it can SEE (survival is already satisfied here).
        # Gathering frost-detached clasts (C14) is tried first — where the cold
        # has already broken sound clasts loose at one's feet, stooping to pick
        # them up beats knapping an in-situ outcrop. Else, debit a knappable
        # outcrop (C2). With tool-stone secured (or none in sight), if it is chilly
        # (or has never made fire) it STRIKES a fire (C7, the VOÛTE) — warmth before
        # art. Having made fire, it puts that heat to its FIRST use on matter: it
        # TEMPERs a silica nodule (C8) for a keener edge than cold stone gives —
        # tools before art. It also DIGs workable clay (C5) into its clay store — the
        # matter of the future pot, a non-fire precursor. Then it grinds a usable ochre pigment (C18) — the symbol's matter
        # after the tool, on its own inventory — and, holding a colour, leaves a
        # MARK on a paintable carbonate wall (C20) — the symbol's mark after its
        # matter. All emergent, never scripted; each inert unless its capability is
        # installed, so none perturbs the others' scenarios.
        fc = _seek_frost_clast(agents, row, obs, sim)
        if fc is not None:
            return fc
        ts = _seek_toolstone(agents, row, obs, sim)
        if ts is not None:
            return ts
        fs = _seek_firesite(agents, row, obs, sim)
        if fs is not None:
            return fs
        tp = _seek_tempersite(agents, row, obs, sim)
        if tp is not None:
            return tp
        dg = _seek_clay(agents, row, obs, sim)
        if dg is not None:
            return dg
        oc = _seek_ochre(agents, row, obs, sim)
        if oc is not None:
            return oc
        mk = _seek_canvas(agents, row, obs, sim)
        if mk is not None:
            return mk
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


def _seek_frost_clast(agents, row, obs, sim):
    """Emergent gelifract gathering — the agent loop's consumption of C14.

    A survival-satisfied, curious agent that SEES a frost-shattered scree of
    workable clasts (``cryoclasty.best_frost_clast_near``) walks there and
    GATHERS a ready flake — no percussion, the cold already did the breaking.
    Utility-based action selection: where freeze-thaw has detached sound clasts
    at one's feet, stooping to gather them outranks knapping an outcrop (less
    effort) and blind exploration. So this is tried *before* ``_seek_toolstone``.

    Nothing is scripted — the agent perceives an angular scree on a cold slope
    and *chooses* to gather; the WORLD decides whether those clasts carry an edge
    (the cue's ``clast_quality`` = C2 base × frost fabric response). A cold
    granite scree is spectacular grus that yields nothing; the same cold on
    obsidian / flint yields razor clasts. The agent learns cold+rock→edge by
    acting (the « mensonge rendu visible » #5).

    Gated on C14 being installed on the world (its cue cache exists) — so this is
    fully inert wherever cryoclasty was never installed (every other smoke / the
    plain bootstrap), exactly like the C2/C3 wires gate on their own caches. Two
    hot-loop safety rules mirror the KNAP wire: (1) only *read* an already
    installed C14 — never ``install_*`` mid-iteration; (2) any error degrades to
    ``None`` (ordinary exploration), never crashes the tick. Surface gather only
    (the cue's ``collect_depth_m == 0``) — no geology mutation (D10 frozen).

    Returns a ``Decision`` (GATHER if standing on the scree, else WALK_TO) or
    ``None`` to fall through to ``_seek_toolstone`` / ordinary exploration.
    """
    if sim is None or getattr(sim, "_cryoclasty_cue_cache", None) is None:
        return None
    if float(agents.inv_stone[row]) >= TOOLSTONE_SATED_KG:
        return None
    if _inventory_mass(agents, row) >= float(agents.inv_capacity_kg[row]) - 1e-3:
        return None
    try:
        from engine import cryoclasty as cc
        cue = cc.best_frost_clast_near(sim, int(row),
                                       perception_radius_m=FROST_CLAST_PERCEPT_M)
    except Exception:
        return None
    if cue is None:
        return None
    tx = (cue.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (cue.coord[1] + 0.5) * CHUNK_SIDE_M
    px, py = obs.pos[0], obs.pos[1]
    d = math.hypot(tx - px, ty - py)
    # Same confidence band as KNAP: above random EXPLORE (0.3), below survival
    # actions — gathering never out-prioritises hunger / thirst / shelter.
    conf = 0.30 + 0.20 * float(cue.confidence)
    if d < INTERACT_RADIUS_M:
        return Decision(int(ActionKind.GATHER), tx, ty, conf)
    return Decision(int(ActionKind.WALK_TO), tx, ty, min(conf, 0.34))


def _seek_ochre(agents, row, obs, sim):
    """Emergent ochre grinding — the agent loop's consumption of C18.

    A survival-satisfied, curious agent that SEES a rusty iron-hat earth it could grind
    into colour (``ochre_grinding.best_ochre_site_near``) walks there and GRINDS a handful
    of it into pigment. Utility-based action selection: with tool-stone already secured (or
    none in sight), investing idle time in a usable pigment beats blind exploration. So
    this is tried *after* ``_seek_toolstone`` — survival tools first, then symbol. It runs
    on its OWN inventory (``inv_pigment``), so it never competes with the raw tool-stone
    pool.

    Nothing is scripted — the agent perceives a rusty weathered earth and *chooses* to
    grind it; the WORLD decides whether that earth carries a stable colour (the cue's
    ``pigment_quality`` = oxide chroma × cap richness). An oxide gossan (hematite / magnetite)
    grinds to lightfast red / black ochre; a pyrite / lead / zinc gossan looks just as rusty
    but grinds to nothing (``best_ochre_site_near`` only ever returns ``usable`` sites, so the
    agent walks to a real one; standing on a barren one and grinding teaches the lie #9 —
    rust ≠ red). The first agent behaviour to advance the SYMBOLIC pillar (pigment = the
    substrate of the future mark).

    Gated on C18 being installed on the world (its cue cache exists) — so this is fully
    inert wherever ochre grinding was never installed (every other smoke / the plain
    bootstrap), exactly like the C2 / C3 / C14 wires gate on their own caches. Two hot-loop
    safety rules mirror the KNAP / GATHER wires: (1) only *read* an already installed C18 —
    never ``install_*`` mid-iteration; (2) any error degrades to ``None`` (ordinary
    exploration), never crashes the tick. Surface grind only (the cue's
    ``collect_depth_m == 0``) — no geology mutation (D10 frozen).

    Returns a ``Decision`` (GRIND if standing on the ochre earth, else WALK_TO) or ``None``
    to fall through to ordinary exploration.
    """
    if sim is None or getattr(sim, "_ochre_cue_cache", None) is None:
        return None
    inv_pig = getattr(agents, "inv_pigment", None)
    if inv_pig is not None and float(inv_pig[row]) >= PIGMENT_SATED_KG:
        return None
    try:
        from engine import ochre_grinding as og
        cue = og.best_ochre_site_near(sim, int(row),
                                      perception_radius_m=OCHRE_PERCEPT_M)
    except Exception:
        return None
    if cue is None:
        return None
    tx = (cue.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (cue.coord[1] + 0.5) * CHUNK_SIDE_M
    px, py = obs.pos[0], obs.pos[1]
    d = math.hypot(tx - px, ty - py)
    # Same confidence band as KNAP / GATHER: above random EXPLORE (0.3), below survival.
    conf = 0.30 + 0.20 * float(cue.confidence)
    if d < INTERACT_RADIUS_M:
        return Decision(int(ActionKind.GRIND), tx, ty, conf)
    return Decision(int(ActionKind.WALK_TO), tx, ty, min(conf, 0.34))


def _seek_canvas(agents, row, obs, sim):
    """Emergent rock-wall marking — the agent loop's consumption of C20.

    A survival-satisfied, curious agent that already HOLDS ground pigment (C18) and SEES a
    pale carbonate wall it could paint (``rock_canvas.best_canvas_near``) walks there and
    leaves a MARK, instead of wandering. Utility-based action selection: with a colour in
    hand, investing idle time in a lasting mark beats blind exploration. So this is tried
    *after* ``_seek_ochre`` — you must grind the pigment (the symbol's matter) before you
    can paint with it (the symbol's mark). The SECOND agent behaviour to advance the
    SYMBOLIC pillar.

    Nothing is scripted — the agent perceives a pale wall and *chooses* to mark it; the
    WORLD decides whether the mark LASTS (the cue's ``durability`` = adhesion × persistence)
    and whether it is SEEN (the pigment/wall contrast). A SOUND limestone face seals the
    mark under a calcite veil; the same conspicuous cliff when KARST / FROST takes the
    pigment then sheds it (mensonge #11). The agent steers to the BEST wall in sight (most
    durable) and LIVES the inversion by marking it — a karst wall takes the pigment and
    flakes it off, teaching ``looks markable ≠ holds a lasting mark``.

    Gated on C20 being installed (its cue cache exists) — so this is fully inert wherever
    rock canvas was never installed, exactly like the C2 / C3 / C14 / C18 wires gate on
    their own caches. Two hot-loop safety rules mirror the GRIND wire: (1) only *read* an
    already installed C20 — never ``install_*`` mid-iteration; (2) any error degrades to
    ``None`` (ordinary exploration), never crashes the tick. Non-mutating — painting does
    not consume the rock (no ``geo.mine_at``; D10 frozen).

    Returns a ``Decision`` (MARK if standing on the wall, else WALK_TO) or ``None`` to fall
    through to ordinary exploration.
    """
    if sim is None or getattr(sim, "_canvas_cue_cache", None) is None:
        return None
    inv_pig = getattr(agents, "inv_pigment", None)
    if inv_pig is None or float(inv_pig[row]) < MARK_MIN_PIGMENT_KG:
        return None   # no colour in hand → nothing to paint with
    mem = agents.memory[row]
    hue = getattr(mem, "last_pigment_hue", None) if mem is not None else None
    if hue is None:
        return None   # has not ground a known colour yet → nothing to paint with
    try:
        from engine import rock_canvas as rc
        cue = rc.best_canvas_near(sim, int(row), perception_radius_m=CANVAS_PERCEPT_M)
    except Exception:
        return None
    if cue is None:
        return None
    tx = (cue.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (cue.coord[1] + 0.5) * CHUNK_SIDE_M
    px, py = obs.pos[0], obs.pos[1]
    d = math.hypot(tx - px, ty - py)
    # Same confidence band as KNAP / GATHER / GRIND: above random EXPLORE (0.3), below survival.
    conf = 0.30 + 0.20 * float(cue.confidence)
    if d < INTERACT_RADIUS_M:
        return Decision(int(ActionKind.MARK), tx, ty, conf)
    return Decision(int(ActionKind.WALK_TO), tx, ty, min(conf, 0.34))


def _seek_firesite(agents, row, obs, sim):
    """Emergent fire-making — the agent loop's consumption of C7 (the VOÛTE of the arc).

    A survival-satisfied, curious agent that is mildly chilly (or has never made fire) and
    SEES a site where a spark can truly take (``fire_ignition.best_firesite_near``) walks
    there and STRIKES a fire rather than wandering. Utility-based action selection: warming
    oneself (and learning the firestone→flame link) outranks blind exploration. Tried *after*
    ``_seek_toolstone`` (secure stone first) and *before* the symbolic ``_seek_ochre`` /
    ``_seek_canvas`` (warmth before art).

    Nothing is scripted — the agent perceives a brown spark-stone, a hard striker and dry
    grass, and *chooses* to strike; the WORLD decides whether a spark catches (the cue's
    ``can_ignite`` / ``method``): PERCUSSION over a pyrite firestone + striker on dry-enough
    tinder, FRICTION over bone-dry tinder with no minerals; a lush DAMP meadow looks like
    tinder but a spark won't catch (the fire lie). The agent learns the correlation by acting.

    Self-limiting and honest: it is sought only when warmth is actually wanted
    (``thermal >= FIRE_SEEK_THERMAL_MIN``) OR on the very first discovery (curiosity), so a
    warm agent that already knows fire does not re-strike every tick.

    Gated on C7 being installed (its cue cache exists) — fully inert wherever fire_ignition
    was never installed, exactly like the C2 / C14 / C18 / C20 wires gate on their own caches.
    Two hot-loop safety rules mirror those wires: (1) only *read* an already installed C7 —
    never ``install_*`` mid-iteration; (2) any error degrades to ``None`` (ordinary
    exploration), never crashes the tick. Non-mutating — striking a spark does not consume the
    rock (no ``geo.mine_at``; D10 frozen).

    Returns a ``Decision`` (IGNITE if standing on the firesite, else WALK_TO) or ``None`` to
    fall through to ``_seek_ochre`` / ``_seek_canvas`` / ordinary exploration.
    """
    if sim is None or getattr(sim, "_ignition_cue_cache", None) is None:
        return None
    mem = agents.memory[row]
    thermal = float(obs.drives[int(DriveKind.THERMAL)])
    already = bool(getattr(mem, "has_made_fire", False)) if mem is not None else False
    if thermal < FIRE_SEEK_THERMAL_MIN and already:
        return None   # warm enough and already knows fire → no need to strike one now
    try:
        from engine import fire_ignition as fi
        cue = fi.best_firesite_near(sim, int(row), perception_radius_m=FIRESITE_PERCEPT_M)
    except Exception:
        return None
    if cue is None:
        return None   # the world says: no fire to be made within sight
    tx = (cue.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (cue.coord[1] + 0.5) * CHUNK_SIDE_M
    px, py = obs.pos[0], obs.pos[1]
    d = math.hypot(tx - px, ty - py)
    # Same confidence band as KNAP / GATHER / GRIND / MARK: above random EXPLORE (0.3),
    # below survival.
    conf = 0.30 + 0.20 * float(cue.confidence)
    if d < INTERACT_RADIUS_M:
        return Decision(int(ActionKind.IGNITE), tx, ty, conf)
    return Decision(int(ActionKind.WALK_TO), tx, ty, min(conf, 0.34))


def _seek_tempersite(agents, row, obs, sim):
    """Emergent heat treatment — the agent loop's consumption of C8 (fire's FIRST USE on matter).

    A survival-satisfied, curious agent that ALREADY KNOWS FIRE (``mem.has_made_fire``) and SEES
    a heat-responsive silica it could roast (``lithic_tempering.best_temper_site_near``) walks
    there and TEMPERs it — heating a flint/chert nodule in the fire it can make to win a keener
    cutting edge than cold-knapping the same stone. Utility-based action selection: with warmth
    secured, investing the fire's heat into a *better tool* outranks blind exploration. The first
    behaviour that uses C7 fire as a *means* rather than an end — tried *after* ``_seek_firesite``
    (you must have made fire before you can heat-treat with it) and *before* the symbolic
    ``_seek_ochre`` / ``_seek_canvas`` (tools before art).

    Nothing is scripted — the agent perceives a silica outcrop beside a fire-makeable spot and
    *chooses* to roast it; the WORLD decides the gain (the cue's ``tempered_quality`` = C2 base +
    silica heat response, bounded by ``TEMPER_CEILING``). Cryptocrystalline chert responds strongly,
    quartzite modestly, and OBSIDIAN — the best raw knapping stone, the obvious-looking candidate —
    gains NOTHING (already glass): ``best_temper_site_near`` never routes to an obsidian/ no-fire
    site (gain 0 → no cue), and standing on one and tempering teaches the lie #12 by acting.

    Gated on C8 being installed (its cue cache exists) AND on the fire skill being learned first —
    so this is fully inert wherever lithic tempering was never installed, or before the agent has
    ever made a fire, exactly like the C7 wire gates on ``_ignition_cue_cache``. Two hot-loop safety
    rules mirror those wires: (1) only *read* an already installed C8 — never ``install_*``
    mid-iteration; (2) any error degrades to ``None`` (ordinary exploration), never crashes the tick.
    Non-mutating — roasting a nodule consumes no geology (no ``geo.mine_at``; D10 frozen).

    Returns a ``Decision`` (TEMPER if standing on the site, else WALK_TO) or ``None`` to fall
    through to ``_seek_ochre`` / ``_seek_canvas`` / ordinary exploration.
    """
    if sim is None or getattr(sim, "_temper_cue_cache", None) is None:
        return None
    mem = agents.memory[row]
    # Fire's FIRST consumer: you must have learned to make fire before you can heat-treat with it.
    if mem is None or not bool(getattr(mem, "has_made_fire", False)):
        return None
    if float(agents.inv_tools[row]) >= TEMPER_TOOLS_SATED:
        return None   # already tool-rich → no need to roast more stone now
    try:
        from engine import lithic_tempering as lt
        cue = lt.best_temper_site_near(sim, int(row), perception_radius_m=TEMPER_PERCEPT_M)
    except Exception:
        return None
    if cue is None:
        return None   # the world says: no stone worth roasting (no responsive silica + fire) in sight
    tx = (cue.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (cue.coord[1] + 0.5) * CHUNK_SIDE_M
    px, py = obs.pos[0], obs.pos[1]
    d = math.hypot(tx - px, ty - py)
    # Same confidence band as KNAP / GATHER / GRIND / MARK / IGNITE: above random EXPLORE (0.3),
    # below survival.
    conf = 0.30 + 0.20 * float(cue.confidence)
    if d < INTERACT_RADIUS_M:
        return Decision(int(ActionKind.TEMPER), tx, ty, conf)
    return Decision(int(ActionKind.WALK_TO), tx, ty, min(conf, 0.34))


def _seek_clay(agents, row, obs, sim):
    """Emergent clay digging — the agent loop's consumption of C5 (a non-fire precursor).

    A survival-satisfied, curious agent that SEES a clay bank it could work
    (``clay_outcrop.best_clay_near``, C5) walks there and DIGs a handful into its clay store
    (``inv_clay``). Utility-based action selection: with tools/fire already handled, stocking the
    matter of the future pot beats blind exploration. Tried *after* the tool/fire/temper cluster
    and *before* the symbolic ``_seek_ochre`` / ``_seek_canvas`` (useful matter before art). It
    runs on its OWN inventory (``inv_clay``), so it never competes with the stone / pigment pools.

    Nothing is scripted — the agent perceives a smooth ochre bank and *chooses* to dig; the WORLD
    decides whether that earth is real workable clay (the cue's ``pottery_grade`` × workability). A
    plastic kaolinite digs into fine ceramic-grade clay; a silty shale bank looks similar but works
    poorly, and a bank outside the plastic window (too dry / too wet) yields little until conditioned
    (mensonge #13 — learned only by digging). ``best_clay_near`` routes to the highest-grade bank in
    sight; standing on a poor one and digging teaches the lie by acting.

    Gated on C5 being installed (its cue cache exists) — fully inert wherever clay_outcrop was never
    installed, exactly like the C2 / C8 wires gate on their own caches. Two hot-loop safety rules
    mirror the KNAP wire: (1) only *read* an already installed C5 — never ``install_*`` mid-iteration;
    (2) any error degrades to ``None`` (ordinary exploration), never crashes the tick. Surface dig
    only — no geology mutation (no ``geo.mine_at``; D10 frozen).

    Returns a ``Decision`` (DIG if standing on the bank, else WALK_TO) or ``None`` to fall through.
    """
    if sim is None or getattr(sim, "_clay_cue_cache", None) is None:
        return None
    if float(agents.inv_clay[row]) >= CLAY_SATED_KG:
        return None
    if _inventory_mass(agents, row) >= float(agents.inv_capacity_kg[row]) - 1e-3:
        return None
    try:
        from engine import clay_outcrop as clo
        cue = clo.best_clay_near(sim, int(row), perception_radius_m=CLAY_PERCEPT_M)
    except Exception:
        return None
    if cue is None:
        return None
    tx = (cue.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (cue.coord[1] + 0.5) * CHUNK_SIDE_M
    px, py = obs.pos[0], obs.pos[1]
    d = math.hypot(tx - px, ty - py)
    # Same confidence band as KNAP / GATHER / GRIND / TEMPER: above random EXPLORE (0.3), below survival.
    conf = 0.30 + 0.20 * float(cue.confidence)
    if d < INTERACT_RADIUS_M:
        return Decision(int(ActionKind.DIG), tx, ty, conf)
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

# D12 wire (2026-06-25) — emergent frost-clast gathering. The agent loop consumes
# the C14 ``cryoclasty`` capability: where freeze-thaw has detached sound clasts
# at the surface, a curious, survival-satisfied agent GATHERS a ready flake with
# no percussion. The WORLD decides (via FrostClastCue.clast_quality = C2 base ×
# frost fabric response) whether that cold scree truly carries an edge — obsidian
# / flint give razor clasts, a cold granite slope gives barren grus. Shares the
# raw tool-stone pool (and TOOLSTONE_SATED_KG gate) with KNAP: enough stone is
# enough, however it was won. Gathering is effortless, so it yields a touch more
# raw mass where the scree is copious (talus / strong frost field).
FROST_CLAST_PERCEPT_M = 96.0  # sight range for scree fields (chunk-scale, memoised)
GATHER_STONE_KG = 1.5         # raw clast mass gathered per GATHER on a sparse field
GATHER_ABUNDANT_MULT = 1.25   # copious scree (talus / strong FCI) → more per stoop
GATHER_TOOL_YIELD = 0.6       # usable cutting edge per unit of true clast_quality

# D12 wire (2026-06-27) — emergent ochre grinding. The agent loop consumes the C18
# ``ochre_grinding`` capability: a curious, survival-satisfied agent that PERCEIVES a
# rusty iron-hat earth it could grind into colour (``ochre_grinding.best_ochre_site_near``)
# walks there and GRINDS a handful of it. The WORLD decides (via OchreCue.pigment_quality
# = oxide chroma × cap richness) whether that rusty earth truly yields a stable pigment —
# an OXIDE gossan (hematite → red ochre, magnetite → black) gives lightfast colour, a
# pyrite / lead / zinc gossan looks just as rusty but grinds to nothing (mensonge #9:
# rust ≠ red). This is the FIRST agent consumer to advance the SYMBOLIC pillar: the
# pigment powder (``inv_pigment``) is the substrate of the future mark / drawing. GRIND
# is a distinct verb (9th orthogonal operator) on its OWN inventory, so it never
# competes with the raw tool-stone pool — it is tried after KNAP / GATHER, when no
# tool-stone is in sight (or the agent is already stone-sated) but pigment is.
OCHRE_PERCEPT_M = 96.0        # sight range for rusty-earth ochre sites (chunk-scale, memoised)
PIGMENT_SATED_KG = 2.0        # stop seeking once this much pigment powder is carried
GRIND_PIGMENT_YIELD = 1.2     # pigment powder won per GRIND, scaled by true pigment_quality
INV_PIGMENT_MAX = 8.0         # pigment inventory ceiling

# D12 wire (2026-06-28) — emergent rock-wall marking. The agent loop consumes the C20
# ``rock_canvas`` capability: a curious, survival-satisfied agent that HOLDS ground pigment
# (C18) and PERCEIVES a pale carbonate wall it could paint (``rock_canvas.best_canvas_near``)
# walks there and leaves a MARK. The WORLD decides (via CanvasCue.durability = adhesion ×
# persistence, plus the pigment/wall contrast) whether the mark LASTS and is VISIBLE — a
# SOUND limestone face grows a calcite veil that seals the mark for millennia; the same
# conspicuous cliff when KARST (dissolution) or FROST (spalling) takes the pigment then
# flakes it off (mensonge #11: looks markable ≠ holds a lasting mark). This is the SECOND
# agent consumer of the SYMBOLIC pillar (after C18 GRIND): the pigment becomes the mark
# itself. The gesture / meaning (the figure, the archetype) stays emergent in
# ``engine.art_discovery`` (L4) — MARK only deposits colour. Tried AFTER GRIND (you must
# hold a colour before you can paint with it). NON-MUTATING: painting does not consume the
# rock (no ``geo.mine_at`` — the mutation frontier D10 stays frozen).
CANVAS_PERCEPT_M = 96.0        # sight range for paintable carbonate walls (chunk-scale, memoised)
MARK_MIN_PIGMENT_KG = 0.05    # need at least this much pigment in hand to leave a mark
MARK_PIGMENT_COST_KG = 0.02   # pigment spent per mark

# D12 wire (2026-06-28) — emergent fire-making, the VOÛTE of the stone-age arc. The agent
# loop consumes the C7 ``fire_ignition`` capability: a curious, survival-satisfied agent that
# is mildly chilly (or has never made fire) and PERCEIVES a site where a spark can truly take
# (``fire_ignition.best_firesite_near``) walks there and STRIKES a fire (``ActionKind.IGNITE``)
# instead of wandering. The WORLD decides (via the IgnitionCue) whether a spark actually
# catches — PERCUSSION where the geology carries a pyrophoric firestone (pyrite gossan, C1) +
# a hard striker (C2) over dry-enough tinder, FRICTION where bone-dry tinder lets a hand-drill
# ember take with no minerals at all; a lush DAMP meadow looks like tinder but a spark won't
# catch (the fire lie). Unlike KNAP / GATHER / GRIND it fills no portable inventory — the
# product is WARMTH (the agent's own thermal drive eases) and the learned skill
# (``has_made_fire``), the keystone that makes the C1→C6 matters *actionable* (cook, smelt,
# fire clay/lime). Tried AFTER KNAP / GATHER (secure stone first) and BEFORE the symbolic
# GRIND / MARK (warmth before art). NON-MUTATING: striking a spark consumes no geology (no
# ``geo.mine_at`` — the mutation frontier D10 stays frozen).
FIRESITE_PERCEPT_M = 96.0      # sight range for fire-makeable sites (chunk-scale, memoised)
FIRE_SEEK_THERMAL_MIN = 0.15  # seek a fire when at least this chilly (else only on first discovery)
FIRE_WARMTH_RELIEF = 0.18     # thermal-drive relief from sitting at a struck fire (cf. SEEK_SHELTER 0.20)

# D12 wire (2026-06-29) — heat-treat a silica stone in the fire (consumes C8 lithic_tempering,
# fire's FIRST USE on a material — the oldest pyrotechnology). A survival-satisfied, curious
# agent that ALREADY KNOWS FIRE (``has_made_fire``) and SEES a heat-responsive silica it could
# roast (``lithic_tempering.best_temper_site_near``) walks there and TEMPERs it → a keener
# cutting edge than cold-knapping the same stone (``tempered_quality`` ≥ base, the world-committed
# pyrotechnology premium). The lie made visible #12: OBSIDIAN is the best stone to knap raw
# (base 1.0) and looks the prime candidate for the fire — yet heat yields it NO gain (already
# glass); ``best_temper_site_near`` never routes there (gain 0 → no cue), and standing on an
# obsidian outcrop and tempering teaches it by acting (cue None → no edge). Gated on C8 installed
# AND on the fire skill being learned first — so TEMPER is fire's first consumer, tried AFTER
# ``_seek_firesite`` (make fire first) and BEFORE the symbolic GRIND / MARK (tools before art).
# Reuses ``inv_tools`` (NO new inventory field → no persistence migration). NON-MUTATING: roasting
# a nodule consumes no geology (no ``geo.mine_at`` — the mutation frontier D10 stays frozen).
TEMPER_PERCEPT_M = 96.0       # sight range for heat-treatable silica sites (chunk-scale, memoised)
TEMPER_TOOLS_SATED = 4.0      # stop seeking to temper once this much usable edge is carried (< INV_TOOLS_MAX 5.0)
TEMPER_TOOL_YIELD = 0.6       # usable cutting edge per unit of true tempered_quality (cf. KNAP_TOOL_YIELD)

# D12 wire (2026-06-29) — dig workable clay from a clay exposure (consumes C5 clay_outcrop, a
# NON-FIRE precursor — restores the fire/non-fire alternation after IGNITE/TEMPER). A
# survival-satisfied, curious agent that SEES a clay bank it could work
# (``clay_outcrop.best_clay_near``) walks there and DIGs a handful into its clay store
# (``inv_clay``, an EXISTING field shared with river-clay foraging → no new inventory field, no
# persistence migration). The matter of the future pot: clay is the substrate C9 ceramic_firing
# will one day consume. The lie made visible #13: a conspicuous clay bank may be OUTSIDE the
# plastic window right now (too dry to shape / too wet a slurry → ``workable_now`` False) or a
# silty SHALE_CLAY that fires poorly vs a PLASTIC_CLAY kaolinite — the yield tracks the world's
# real ``pottery_grade`` × workability, learned only by digging. Tried after the tool/fire/temper
# cluster and before the symbolic GRIND / MARK (useful matter before art). NON-MUTATING: surface
# clay collection (cue ``collect_depth_m`` shallow), no ``geo.mine_at`` (D10 frozen).
CLAY_PERCEPT_M = 96.0         # sight range for clay banks (chunk-scale, memoised)
CLAY_SATED_KG = 4.0           # stop seeking clay once this much is carried
CLAY_DIG_KG = 1.5             # raw clay dug per DIG, scaled by true pottery_grade
DAMP_CLAY_FACTOR = 0.25       # clay outside the plastic window yields little usable clay (the lie)
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

    if act == int(ActionKind.GATHER):
        # Pick up frost-detached surface clasts the agent is standing on (C14).
        # The world never lies: raw stone always comes, but a usable CUTTING EDGE
        # emerges only in proportion to the clast's TRUE quality (C2 base × frost
        # fabric response) — obsidian / flint scree give razor flakes, a cold
        # granite slope gives edgeless grus (mensonge #5). A spot the world says
        # is barren (no frost field / no rock → no cue) yields nothing and isn't
        # remembered. Surface GATHER only — NOT a geology mutation (no
        # geo.mine_at), so the mutation frontier (D10) stays frozen.
        agents.vel[row, :2] = 0.0
        if sim is None or getattr(sim, "_cryoclasty_cue_cache", None) is None:
            return events
        cap_left = max(0.0, float(agents.inv_capacity_kg[row]) - _inventory_mass(agents, row))
        if cap_left <= 1e-3:
            return events
        try:
            from engine import cryoclasty as cc
            cue = cc.prospect_frost_clasts(sim, px, py)
        except Exception:
            return events
        if cue is None:
            return events   # the world says: no frost-shattered clasts lie here
        nominal = GATHER_STONE_KG * (GATHER_ABUNDANT_MULT if cue.abundant else 1.0)
        gained = min(nominal, cap_left)
        agents.inv_stone[row] = float(agents.inv_stone[row]) + gained
        tool_gain = GATHER_TOOL_YIELD * float(cue.clast_quality) * (gained / nominal)
        agents.inv_tools[row] = float(
            min(float(agents.inv_tools[row]) + tool_gain, INV_TOOLS_MAX))
        mem = agents.memory[row]
        if mem is not None:
            locs = getattr(mem, "known_frost_clast_locations", None)
            if locs is not None:
                locs.append((px, py))
                if len(locs) > 8:
                    locs.pop(0)
            remember_short(agents, row, "frost_clast",
                           {"zone": cue.zone, "material": cue.material})
        events.append({
            "kind": "gather",
            "row": int(row),
            "zone": cue.zone,
            "stone_kg": round(float(gained), 4),
            "tool_gain": round(float(tool_gain), 4),
            "abundant": bool(cue.abundant),
        })
        return events

    if act == int(ActionKind.GRIND):
        # Cold-grind the rusty iron-hat earth the agent stands on into pigment (C18).
        # The world never lies about COLOUR: an OXIDE gossan (hematite → red ochre,
        # magnetite → black) grinds to a stable, lightfast pigment in proportion to its
        # true quality (oxide chroma × cap richness); a pyrite / lead / zinc gossan looks
        # just as rusty but grinds to NO usable pigment (mensonge #9: rust ≠ red). A spot
        # the world says has no gossan yields nothing and isn't remembered. Surface grind
        # only (cue.collect_depth_m == 0) — NOT a geology mutation (no geo.mine_at), so the
        # mutation frontier (D10) stays frozen. The first agent behaviour to fill the
        # SYMBOLIC inventory (inv_pigment), the substrate of the future mark.
        agents.vel[row, :2] = 0.0
        if sim is None or getattr(sim, "_ochre_cue_cache", None) is None:
            return events
        inv_pig = getattr(agents, "inv_pigment", None)
        if inv_pig is None:
            return events
        try:
            from engine import ochre_grinding as og
            cue = og.prospect_ochre(sim, px, py)
        except Exception:
            return events
        if cue is None or not cue.usable:
            return events   # no gossan here, or a rusty-but-barren lie → no pigment
        pigment_gain = GRIND_PIGMENT_YIELD * float(cue.pigment_quality)
        inv_pig[row] = float(min(float(inv_pig[row]) + pigment_gain, INV_PIGMENT_MAX))
        mem = agents.memory[row]
        if mem is not None:
            locs = getattr(mem, "known_ochre_locations", None)
            if locs is not None:
                locs.append((px, py))
                if len(locs) > 8:
                    locs.pop(0)
            remember_short(agents, row, "ochre",
                           {"class": cue.pigment_class, "material": cue.mineral})
            # Carry the colour just ground — a later MARK (C20) paints with THIS hue, and
            # learns whether it shows on the wall (the visibility lie, mensonge #11).
            mem.last_pigment_hue = tuple(int(c) for c in cue.hue)
        events.append({
            "kind": "grind",
            "row": int(row),
            "pigment_class": cue.pigment_class,
            "pigment_kg": round(float(pigment_gain), 4),
            "pigment_quality": round(float(cue.pigment_quality), 4),
            "hue": list(int(c) for c in cue.hue),
        })
        return events

    if act == int(ActionKind.MARK):
        # Leave a pigment mark on the carbonate wall the agent stands on (C20). The world
        # never lies about PERMANENCE: a SOUND limestone face (calcite veil) keeps the mark
        # for millennia; a KARST / FROST wall takes the pigment then flakes it off (mensonge
        # #11: a conspicuous pale cliff that does not hold a mark). Nor about VISIBILITY: a
        # pigment matching the wall colour is real paint yet invisible (it is contrast, not
        # paint, that makes a mark). Painting does NOT consume the rock — no geo.mine_at, so
        # the mutation frontier (D10) stays frozen. The SECOND agent behaviour on the
        # SYMBOLIC pillar: the pigment of C18 GRIND becomes the mark itself. The gesture /
        # meaning (the figure, the archetype) stays emergent in engine.art_discovery (L4) —
        # MARK only deposits the colour the world says is there.
        agents.vel[row, :2] = 0.0
        if sim is None or getattr(sim, "_canvas_cue_cache", None) is None:
            return events
        inv_pig = getattr(agents, "inv_pigment", None)
        if inv_pig is None or float(inv_pig[row]) < MARK_MIN_PIGMENT_KG:
            return events   # no colour in hand → no mark
        mem = agents.memory[row]
        hue = getattr(mem, "last_pigment_hue", None) if mem is not None else None
        if hue is None:
            return events   # has not ground a known colour yet
        try:
            from engine import rock_canvas as rc
            cue = rc.prospect_canvas(sim, px, py)
        except Exception:
            return events
        if cue is None:
            return events   # no carbonate wall underfoot → nothing to mark
        outcome = rc.paint_outcome(cue, tuple(int(c) for c in hue), pigment_lightfast=True)
        spent = min(MARK_PIGMENT_COST_KG, float(inv_pig[row]))
        inv_pig[row] = float(inv_pig[row]) - spent
        if mem is not None:
            locs = getattr(mem, "known_canvas_locations", None)
            if locs is not None:
                locs.append((px, py))
                if len(locs) > 8:
                    locs.pop(0)
            remember_short(agents, row, "mark",
                           {"material": cue.material, "lasts": bool(outcome["lasts"]),
                            "visible": bool(outcome["visible"])})
        events.append({
            "kind": "mark",
            "row": int(row),
            "material": cue.material,
            "pigment_kg": round(float(spent), 4),
            "lasts": bool(outcome["lasts"]),
            "visible": bool(outcome["visible"]),
            "mark_durability": round(float(outcome["mark_durability"]), 4),
            "contrast": round(float(outcome["contrast"]), 4),
            "weather_state": int(cue.weather_state),
        })
        return events

    if act == int(ActionKind.IGNITE):
        # Strike a fire at the firestone site the agent stands on (C7 fire_ignition). The
        # world never lies: a spark takes ONLY where the geology truly carries a pyrophoric
        # firestone (pyrite gossan, C1) + a hard striker (C2) over dry-enough tinder
        # (PERCUSSION), or where bone-dry tinder lets a hand-drill ember take with no minerals
        # (FRICTION); a lush DAMP meadow looks like tinder but a spark won't catch (the fire
        # lie — prospect_ignition returns None). Unlike KNAP / GATHER / GRIND this fills no
        # portable inventory — the product is WARMTH (the agent's own thermal drive eases) and
        # the learned skill (has_made_fire / last_fire_method), the VOÛTE that makes the
        # C1→C6 matters actionable (cook, smelt, fire clay/lime). NON-MUTATING — striking a
        # spark consumes no geology (no geo.mine_at), so the mutation frontier (D10) stays
        # frozen. The agent learns the firestone→flame link by acting.
        agents.vel[row, :2] = 0.0
        if sim is None or getattr(sim, "_ignition_cue_cache", None) is None:
            return events
        try:
            from engine import fire_ignition as fi
            cue = fi.prospect_ignition(sim, px, py)
        except Exception:
            return events
        if cue is None or not cue.can_ignite:
            return events   # the world says: no fire to be made here (damp / no firestone)
        # Warmth — the honest physical effect of a struck fire (eases only the AGENT's own
        # thermal state; touches no geology). Curiosity-gated, so it can never mask a freezing
        # emergency (a critically cold agent took SEEK_SHELTER in the survival branch).
        agents.thermal[row] = max(0.0, float(agents.thermal[row]) - FIRE_WARMTH_RELIEF)
        method = cue.method.name
        mem = agents.memory[row]
        if mem is not None:
            locs = getattr(mem, "known_firesite_locations", None)
            if locs is not None:
                locs.append((px, py))
                if len(locs) > 8:
                    locs.pop(0)
            mem.has_made_fire = True
            mem.last_fire_method = method
            remember_short(agents, row, "fire",
                           {"method": method, "tinder": cue.tinder_state.name})
        events.append({
            "kind": "ignite",
            "row": int(row),
            "method": method,
            "tinder_state": cue.tinder_state.name,
            "can_percussion": bool(cue.can_percussion),
            "can_friction": bool(cue.can_friction),
            "confidence": round(float(cue.confidence), 4),
        })
        return events

    if act == int(ActionKind.TEMPER):
        # Heat-treat the silica stone the agent stands on, in the fire it knows how to make (C8
        # lithic_tempering — fire's FIRST USE on a material). The world never lies about the GAIN:
        # a cryptocrystalline chert/flint nodule roasted slow yields a keener edge than cold
        # knapping (``tempered_quality`` ≥ base, the pyrotechnology premium the world commits to);
        # quartzite gains modestly; OBSIDIAN — the best raw stone, the obvious-looking candidate —
        # gains NOTHING (already glass): ``prospect_tempering`` returns None there, so roasting it
        # teaches the lie #12 by acting (no cue → no edge). Requires the fire skill to be learned
        # first (``has_made_fire``) — this is C7's first downstream consumer. Reuses ``inv_tools``
        # (the cutting edge), fills NO new inventory, and is NON-MUTATING: roasting a nodule
        # consumes no geology (no geo.mine_at), so the mutation frontier (D10) stays frozen.
        agents.vel[row, :2] = 0.0
        if sim is None or getattr(sim, "_temper_cue_cache", None) is None:
            return events
        mem = agents.memory[row]
        if mem is None or not bool(getattr(mem, "has_made_fire", False)):
            return events   # cannot heat-treat without first knowing how to make a fire
        try:
            from engine import lithic_tempering as lt
            cue = lt.prospect_tempering(sim, px, py)
        except Exception:
            return events
        if cue is None or not cue.temperable:
            return events   # obsidian / non-silica / no fire here → the heat yields no edge (the lie)
        tool_gain = TEMPER_TOOL_YIELD * float(cue.tempered_quality)
        agents.inv_tools[row] = float(
            min(float(agents.inv_tools[row]) + tool_gain, INV_TOOLS_MAX))
        locs = getattr(mem, "known_temper_locations", None)
        if locs is not None:
            locs.append((px, py))
            if len(locs) > 8:
                locs.pop(0)
        mem.has_tempered_stone = True
        mem.last_temper_gain = float(cue.quality_gain)
        remember_short(agents, row, "temper",
                       {"silica": cue.silica_kind, "material": cue.stone_material})
        events.append({
            "kind": "temper",
            "row": int(row),
            "silica_kind": cue.silica_kind,
            "base_quality": round(float(cue.base_quality), 4),
            "tempered_quality": round(float(cue.tempered_quality), 4),
            "quality_gain": round(float(cue.quality_gain), 4),
            "tool_gain": round(float(tool_gain), 4),
            "fire_method": cue.fire_method,
        })
        return events

    if act == int(ActionKind.DIG):
        # Dig workable clay from the bank the agent stands on (C5 clay_outcrop). The world never
        # lies about WORKABILITY or GRADE: a plastic kaolinite inside its plastic window digs into
        # fine ceramic-grade clay (yield ∝ pottery_grade); a silty SHALE_CLAY looks similar but
        # works poorly, and a bank too dry to shape / too wet a slurry yields little usable clay
        # until conditioned (mensonge #13: a conspicuous clay bank that won't hold a shape now). A
        # spot the world says has no clay yields nothing and isn't remembered. Surface dig only
        # (cue.collect_depth_m shallow) — NOT a geology mutation (no geo.mine_at), so the mutation
        # frontier (D10) stays frozen. Fills inv_clay (the matter the future C9 ceramic_firing
        # consumes); a non-fire precursor that restores the fire/non-fire alternation.
        agents.vel[row, :2] = 0.0
        if sim is None or getattr(sim, "_clay_cue_cache", None) is None:
            return events
        cap_left = max(0.0, float(agents.inv_capacity_kg[row]) - _inventory_mass(agents, row))
        if cap_left <= 1e-3:
            return events
        try:
            from engine import clay_outcrop as clo
            cue = clo.prospect_clay(sim, px, py)
        except Exception:
            return events
        if cue is None:
            return events   # the world says: no clay bank crops out here
        workable = bool(cue.workable_now)
        nominal = CLAY_DIG_KG * float(cue.pottery_grade) * (1.0 if workable else DAMP_CLAY_FACTOR)
        gained = min(nominal, cap_left)
        agents.inv_clay[row] = float(agents.inv_clay[row]) + gained
        mem = agents.memory[row]
        if mem is not None:
            locs = getattr(mem, "known_clay_locations", None)
            if locs is not None:
                locs.append((px, py))
                if len(locs) > 8:
                    locs.pop(0)
            mem.last_clay_class = cue.clay_class.name
            remember_short(agents, row, "clay",
                           {"class": cue.clay_class.name, "material": cue.material})
        events.append({
            "kind": "dig",
            "row": int(row),
            "clay_class": cue.clay_class.name,
            "material": cue.material,
            "clay_kg": round(float(gained), 4),
            "pottery_grade": round(float(cue.pottery_grade), 4),
            "workable_now": workable,
            "ceramic_grade": bool(cue.ceramic_grade),
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
