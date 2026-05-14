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
                          chunks_around)


PERCEPTION_RADIUS_M = 60.0
INTERACT_RADIUS_M = 1.8
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


def _dominant_drive(drives):
    candidates = [DriveKind.THIRST, DriveKind.HUNGER, DriveKind.THERMAL,
                  DriveKind.SLEEP, DriveKind.FATIGUE]
    best, bv = candidates[0], -1.0
    for k in candidates:
        v = float(drives[int(k)])
        if v > bv:
            bv, best = v, k
    return int(best)


def perceive(agents, row, streamer, radius_m=PERCEPTION_RADIUS_M, grid=None, tick=None):
    px, py, pz = (float(agents.pos[row, 0]), float(agents.pos[row, 1]), float(agents.pos[row, 2]))
    drives = np.array([agents.hunger[row], agents.thirst[row], agents.sleep[row],
                       agents.fatigue[row], agents.thermal[row], agents.pain[row],
                       agents.stress[row], agents.loneliness[row]], dtype=np.float32)
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
    for coord in chunks_around(chunk_center, r_chunks):
        chunk = streamer.cache.get(coord)
        if chunk is None:
            continue
        cx0 = coord[0] * CHUNK_SIDE_M
        cy0 = coord[1] * CHUNK_SIDE_M
        cx1 = cx0 + CHUNK_SIDE_M
        cy1 = cy0 + CHUNK_SIDE_M
        dx = 0.0 if (cx0 <= px <= cx1) else (cx0 - px if px < cx0 else px - cx1)
        dy = 0.0 if (cy0 <= py <= cy1) else (cy0 - py if py < cy0 else py - cy1)
        if dx * dx + dy * dy > r_eff_sq:
            continue
        _scan_chunk(chunk, px, py, radius_m, nearest, tick)
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

    n = agents.n_active
    near_agents = []
    r2 = radius_m * radius_m
    if grid is not None and grid.n_indexed > 1:
        candidates = grid.query_disk(px, py, radius_m, exclude_row=row)
        if candidates:
            cand_arr = np.array(candidates, dtype=np.int32)
            cand_arr = cand_arr[agents.alive[cand_arr]]
            if cand_arr.size > 0:
                diffs = agents.pos[cand_arr, :2] - np.array([px, py], dtype=np.float32)
                d2 = (diffs ** 2).sum(axis=1)
                mask = d2 < r2
                in_idx = cand_arr[mask]
                in_d2 = d2[mask]
                order = np.argsort(in_d2)[:16]
                for k in order:
                    j = int(in_idx[k])
                    d = float(math.sqrt(in_d2[k]))
                    near_agents.append(j)
                    if "agent" not in nearest or d < nearest["agent"].distance:
                        nearest["agent"] = PerceivedTarget("agent", float(agents.pos[j, 0]),
                                                          float(agents.pos[j, 1]), d, 1.0, other_row=j)
    elif n > 1:
        diffs = agents.pos[:n, :2] - np.array([px, py], dtype=np.float32)
        d2 = (diffs ** 2).sum(axis=1)
        mask = agents.alive[:n] & (d2 < r2)
        mask[row] = False
        idxs = np.flatnonzero(mask)
        idxs = idxs[np.argsort(d2[idxs])][:16]
        for j in idxs:
            j = int(j)
            d = float(math.sqrt(d2[j]))
            near_agents.append(j)
            if "agent" not in nearest or d < nearest["agent"].distance:
                nearest["agent"] = PerceivedTarget("agent", float(agents.pos[j, 0]),
                                                  float(agents.pos[j, 1]), d, 1.0, other_row=j)

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
                       dominant_drive=_dominant_drive(drives))


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


def _scan_chunk(chunk, px, py, radius_m, out, tick=None):
    """Find the nearest water / food / shelter cell in ``chunk``.

    Dense vectorised path (optim #3b, sprint 2026-05-14 session 11) :
    computes the single 64×64 ``d2`` array once and reuses it for all three
    resources. The earlier ``np.nonzero`` + fancy-indexing path looked
    cheaper on paper but was measured 2.4× slower per call on the Léman
    workload (lac → ~12 % of cells pass the water threshold, so the sparse
    arrays are still hundreds of elements and the fancy-indexing allocation
    cost dominates). The ``tick`` argument is kept for API compatibility
    but is no longer consulted (no per-tick scratch state).

    Determinism : ``np.argmin`` on a 4096-flat ``np.where(mask, d2, inf)``
    picks the same row-major tie-break as the previous implementation, so
    SHA-256 of the agents snapshot stays bit-identical across runs.
    """
    XX, YY = _chunk_cell_world_xy(chunk)
    dx = XX - np.float32(px)
    dy = YY - np.float32(py)
    d2 = dx * dx + dy * dy
    r2 = np.float32(radius_m * radius_m)
    in_r = d2 <= r2
    if not in_r.any():
        return

    water_mask = in_r & (chunk.water > np.float32(5.0))
    if water_mask.any():
        d2m = np.where(water_mask, d2, np.float32(np.inf))
        flat_idx = int(np.argmin(d2m))
        ay, ax = divmod(flat_idx, d2.shape[1])
        dist = float(math.sqrt(float(d2[ay, ax])))
        cur = out.get("water")
        if cur is None or dist < cur.distance:
            out["water"] = PerceivedTarget(
                "water", float(XX[ay, ax]), float(YY[ay, ax]), dist,
                float(chunk.water[ay, ax]))

    food_mask = in_r & (chunk.food_kcal > np.float32(5.0))
    if food_mask.any():
        d2m = np.where(food_mask, d2, np.float32(np.inf))
        flat_idx = int(np.argmin(d2m))
        ay, ax = divmod(flat_idx, d2.shape[1])
        dist = float(math.sqrt(float(d2[ay, ax])))
        cur = out.get("food")
        if cur is None or dist < cur.distance:
            out["food"] = PerceivedTarget(
                "food", float(XX[ay, ax]), float(YY[ay, ax]), dist,
                float(chunk.food_kcal[ay, ax]))

    shelter_mask = in_r & (
        (chunk.wood > np.float32(30.0))
        | ((chunk.stone > np.float32(25.0)) & (chunk.height > np.float32(800.0)))
    )
    if shelter_mask.any():
        d2m = np.where(shelter_mask, d2, np.float32(np.inf))
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


def decide(agents, obs):
    row = obs.row
    drives = obs.drives
    nearest = obs.nearest

    for k in (DriveKind.THIRST, DriveKind.HUNGER, DriveKind.THERMAL,
              DriveKind.SLEEP, DriveKind.FATIGUE):
        if drives[int(k)] >= CRITICAL_THRESHOLD:
            d = _act_on(agents, row, obs, int(k))
            if d is not None:
                return d

    if drives[int(DriveKind.HUNGER)] < 0.6 and drives[int(DriveKind.THIRST)] < 0.6:
        mate_target = _find_mate(agents, row, obs.near_agents)
        if mate_target is not None:
            tx = float(agents.pos[mate_target, 0])
            ty = float(agents.pos[mate_target, 1])
            d = math.hypot(tx - obs.pos[0], ty - obs.pos[1])
            if d < MATING_RADIUS_M:
                return Decision(int(ActionKind.MATE), tx, ty, 0.7, mate_target)
            return Decision(int(ActionKind.WALK_TO), tx, ty, 0.5, mate_target)

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
        ang = float(agents.heading[row]) + (curiosity - 0.5) * 0.8
        tx = obs.pos[0] + math.cos(ang) * 20.0
        ty = obs.pos[1] + math.sin(ang) * 20.0
        return Decision(int(ActionKind.EXPLORE), tx, ty, 0.3)

    return Decision.idle()


def _jitter_target(row, tx, ty, drive_kind):
    """Deterministic per-(row,drive) offset inside +-GOAL_JITTER_M of target."""
    seed = (np.uint64(row) ^ (np.uint64(int(drive_kind)) * _JITTER_PRIME_X))
    seed = (seed ^ (seed >> np.uint64(33))) * _JITTER_PRIME_Y
    seed = seed ^ (seed >> np.uint64(33))
    u = (float(int(seed) & 0xFFFF) / 65535.0) * 2.0 - 1.0
    v = (float((int(seed) >> 16) & 0xFFFF) / 65535.0) * 2.0 - 1.0
    return tx + u * GOAL_JITTER_M, ty + v * GOAL_JITTER_M


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


def _find_mate(agents, row, near):
    if not near:
        return None
    best, bs = None, -1e9
    my_aff = agents.relations[row].affinity
    for j in near:
        if not agents.alive[j]:
            continue
        a = my_aff.get(j, 0.0)
        score = a + float(agents.agreeableness[j]) * 0.4 - float(agents.aggression[j]) * 0.2
        if score > bs:
            bs, best = score, j
    return best


ARRIVE_RADIUS_M = 1.5
DRINK_RELIEF = 0.30
EAT_RELIEF = 0.25
SLEEP_RELIEF = 0.40
FORAGE_RATE = 18.0
FORAGE_KCAL_PER_KG = 300.0
GOAL_JITTER_M = 0.45
HUNT_RADIUS_M = 6.0          # chunk-scale: agent + deer share the chunk
HUNT_KCAL_PER_DEER = 800.0   # successful deer hunt = ~800 kcal returned home
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


def apply_decision(agents, row, decision, streamer, tick):
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
        if consumed > 0:
            agents.thirst[row] = max(0.0, float(agents.thirst[row]) - DRINK_RELIEF * (consumed / 5.0))
            agents.inv_water[row] = min(float(agents.inv_water[row]) + 0.5, 2.0)
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
