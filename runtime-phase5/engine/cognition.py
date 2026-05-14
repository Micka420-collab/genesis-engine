"""Perception -> Decision -> Action pipeline (Phase 5)."""
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


def perceive(agents, row, streamer, radius_m=PERCEPTION_RADIUS_M, grid=None):
    px, py, pz = (float(agents.pos[row, 0]), float(agents.pos[row, 1]), float(agents.pos[row, 2]))
    drives = np.array([agents.hunger[row], agents.thirst[row], agents.sleep[row],
                       agents.fatigue[row], agents.thermal[row], agents.pain[row],
                       agents.stress[row], agents.loneliness[row]], dtype=np.float32)
    nearest = {}
    chunk_center = world_to_chunk(px, py, pz)
    r_chunks = max(1, int(math.ceil(radius_m / CHUNK_SIDE_M)) + 1)
    for coord in chunks_around(chunk_center, r_chunks):
        chunk = streamer.cache.get(coord)
        if chunk is None:
            continue
        _scan_chunk(chunk, px, py, radius_m, nearest)

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
_CELL_GRID_CACHE_CAP = 2048
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
    for k in keys:
        _CACHED_CELL_GRID.pop(k, None)


def _scan_chunk(chunk, px, py, radius_m, out):
    XX, YY = _chunk_cell_world_xy(chunk)
    dx = XX - px
    dy = YY - py
    d2 = dx * dx + dy * dy
    r2 = radius_m * radius_m
    in_range = d2 <= r2
    if not in_range.any():
        return
    water_mask = in_range & (chunk.water > 5.0)
    if water_mask.any():
        d2w = np.where(water_mask, d2, np.float32(np.inf))
        idx = int(np.argmin(d2w))
        wy_idx, wx_idx = divmod(idx, CHUNK_SIZE)
        dist = float(np.sqrt(d2[wy_idx, wx_idx]))
        cur = out.get("water")
        if cur is None or dist < cur.distance:
            out["water"] = PerceivedTarget("water", float(XX[wy_idx, wx_idx]),
                                           float(YY[wy_idx, wx_idx]), dist,
                                           float(chunk.water[wy_idx, wx_idx]))
    food_mask = in_range & (chunk.food_kcal > 5.0)
    if food_mask.any():
        d2f = np.where(food_mask, d2, np.float32(np.inf))
        idx = int(np.argmin(d2f))
        wy_idx, wx_idx = divmod(idx, CHUNK_SIZE)
        dist = float(np.sqrt(d2[wy_idx, wx_idx]))
        cur = out.get("food")
        if cur is None or dist < cur.distance:
            out["food"] = PerceivedTarget("food", float(XX[wy_idx, wx_idx]),
                                          float(YY[wy_idx, wx_idx]), dist,
                                          float(chunk.food_kcal[wy_idx, wx_idx]))
    shelter_mask = in_range & ((chunk.wood > 30.0) | ((chunk.stone > 25.0) & (chunk.height > 800.0)))
    if shelter_mask.any():
        d2s = np.where(shelter_mask, d2, np.float32(np.inf))
        idx = int(np.argmin(d2s))
        wy_idx, wx_idx = divmod(idx, CHUNK_SIZE)
        dist = float(np.sqrt(d2[wy_idx, wx_idx]))
        cur = out.get("shelter")
        if cur is None or dist < cur.distance:
            out["shelter"] = PerceivedTarget("shelter", float(XX[wy_idx, wx_idx]),
                                             float(YY[wy_idx, wx_idx]), dist,
                                             float(chunk.wood[wy_idx, wx_idx] + chunk.stone[wy_idx, wx_idx]))


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

    # SHARE checked before MATE so surplus-food sharing wins over reproduction.
    # Threshold 0.05 kg matches per-tick FORAGE yield so stockpiles created in
    # a single forage tick are shareable before the next EAT consumes them.
    agreeableness = float(agents.agreeableness[row])
    if agreeableness > 0.40 and obs.near_agents and agents.inv_food[row] > 0.05:
        candidates = [(j, float(agents.hunger[j])) for j in obs.near_agents if agents.alive[j]]
        if candidates:
            best = max(candidates, key=lambda x: x[1])
            if best[1] > 0.40:
                tx = float(agents.pos[best[0], 0])
                ty = float(agents.pos[best[0], 1])
                d = math.hypot(tx - obs.pos[0], ty - obs.pos[1])
                if d < SOCIAL_TALK_RADIUS_M:
                    return Decision(int(ActionKind.SHARE), tx, ty, 0.6, best[0])

    if drives[int(DriveKind.HUNGER)] < 0.6 and drives[int(DriveKind.THIRST)] < 0.6:
        mate_target = _find_mate(agents, row, obs.near_agents)
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
        ang = float(agents.heading[row]) + (curiosity - 0.5) * 0.8
        tx = obs.pos[0] + math.cos(ang) * 20.0
        ty = obs.pos[1] + math.sin(ang) * 20.0
        return Decision(int(ActionKind.EXPLORE), tx, ty, 0.3)

    return Decision.idle()


GOAL_JITTER_M = 0.45
_JITTER_PRIME_X = np.uint64(0x9E3779B97F4A7C15)
_JITTER_PRIME_Y = np.uint64(0xBF58476D1CE4E5B9)


def _jitter_target(row, tx, ty, drive_kind):
    with np.errstate(over="ignore"):
        seed = (np.uint64(int(row)) ^ (np.uint64(int(drive_kind)) * _JITTER_PRIME_X))
        seed = (seed ^ (seed >> np.uint64(33))) * _JITTER_PRIME_Y
        seed = seed ^ (seed >> np.uint64(33))
    s_int = int(seed)
    u = (float(s_int & 0xFFFF) / 65535.0) * 2.0 - 1.0
    v = (float((s_int >> 16) & 0xFFFF) / 65535.0) * 2.0 - 1.0
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


def apply_decision(agents, row, decision, streamer, tick):
    events = []
    act = decision.action
    px, py = float(agents.pos[row, 0]), float(agents.pos[row, 1])

    if act == int(ActionKind.IDLE):
        agents.vel[row, :2] = 0.0
        return events

    if act in (int(ActionKind.WALK_TO), int(ActionKind.EXPLORE)):
        tx, ty = float(decision.target_x), float(decision.target_y)
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
        agents.thermal[row] = max(0.0, float(agents.thermal[row]) - 0.03)
        return events

    if act == int(ActionKind.SHARE):
        other = decision.other_row
        if other is not None and agents.alive[other]:
            give = min(float(agents.inv_food[row]), 0.5)
            agents.inv_food[row] -= give
            agents.inv_food[other] += give
            agents.relations[row].update_affinity(other, +0.05)
            agents.relations[other].update_affinity(row, +0.10)
            events.append({"kind": "share", "from": row, "to": other, "qty": give})
        return events

    if act == int(ActionKind.FIGHT):
        other = decision.other_row
        if other is not None and agents.alive[other]:
            my_str = float(agents.aggression[row]) * float(agents.vitality[row])
            their_str = float(agents.aggression[other]) * float(agents.vitality[other])
            damage = 0.05 + 0.10 * my_str
            agents.injuries[other] = min(1.0, float(agents.injuries[other]) + damage)
            agents.vitality[other] = max(0.0, float(agents.vitality[other]) - damage * 0.3)
            agents.pain[other] = min(1.5, float(agents.pain[other]) + 0.3)
            counter = 0.03 + 0.07 * their_str
            agents.injuries[row] = min(1.0, float(agents.injuries[row]) + counter)
            agents.vitality[row] = max(0.0, float(agents.vitality[row]) - counter * 0.3)
            agents.relations[row].update_affinity(other, -0.20)
            agents.relations[other].update_affinity(row, -0.30)
            events.append({"kind": "fight", "attacker": row, "victim": other, "damage": damage})
        return events

    if act == int(ActionKind.MATE):
        other = decision.other_row
        if other is not None and agents.alive[other]:
            events.append({"kind": "mate_attempt", "a": row, "b": other})
        return events

    if act == int(ActionKind.SPEAK):
        other = decision.other_row
        if other is not None and agents.alive[other]:
            agents.relations[row].update_affinity(other, +0.02)
            agents.relations[other].update_affinity(row, +0.02)
            lex_a = agents.lexicon[row]
            lex_b = agents.lexicon[other]
            drift = 0.05
            new_a = lex_a + drift * (lex_b - lex_a)
            new_b = lex_b + drift * (lex_a - lex_b)
            agents.lexicon[row] = new_a
            agents.lexicon[other] = new_b
            sig = _stable_bytes_sig(new_a.astype(np.float32).tobytes())
            events.append({"kind": "vocalize", "from": row, "to": other, "lex_sig": sig})
        return events

    return events


def _inventory_mass(agents, row):
    return float(agents.inv_water[row] + agents.inv_food[row] + agents.inv_wood[row]
                 + agents.inv_stone[row] + agents.inv_metal[row] + agents.inv_tools[row])
