"""Genesis Engine simulation loop with Phase 4 detectors."""
from __future__ import annotations

import json
import math
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from engine.agent import (ActionKind, AgentRegistry, DeathCause, DriveKind,
                          SocialRelations)
from engine.annalist import Annalist
from engine.cognition import (Decision, MATURITY_TICKS, COOLDOWN_TICKS, MATING_RADIUS_M,
                              PERCEPTION_RADIUS_M,
                              apply_decision, decide, perceive)
from engine.core import TICK_DT_S, prf_rng
from engine.spatial import SpatialGrid
from engine.world import (CHUNK_SIDE_M, ChunkStreamer, TerrainParams, Weather,
                          _stable_bytes_sig, chunks_around,
                          regenerate_chunk_resources, weather_at,
                          world_to_chunk, world_to_cell)


DRIVE_ACCEL = 1500.0
HUNGER_PER_S = 1.0 / (14.0 * 86_400.0)
THIRST_PER_S = 1.0 / (3.0 * 86_400.0)
FATIGUE_PER_S = 1.0 / (1.0 * 86_400.0)
SLEEP_PER_S = 1.0 / (1.5 * 86_400.0)


@dataclass
class SimConfig:
    name: str = "default"
    seed: int = 0xC0FFEE_DEADBEEF
    founders: int = 12
    max_agents: int = 500
    bounds_km: Tuple[float, float] = (1.0, 1.0)
    spawn_radius_m: float = 60.0
    cultures: int = 1
    drive_accel: float = DRIVE_ACCEL
    catastrophe_at_tick: int = -1
    catastrophe_radius_m: float = 200.0
    catastrophe_damage: float = 0.6
    # Discovery-rule opt-outs (default False = pure emergence).
    # Set True only in legacy regression tests that depend on
    # pre-Wave-12 scripted seeding (P-NEW.7 hearth, etc.).
    scripted_hearth_seed: bool = False
    # Civilization emergence integrated in sim.step() (not external pipelines).
    emergence_subsystems: bool = True
    # Emergent life: appraise world → substrate → origins (no scripted founder cluster).
    life_emergence: bool = True
    full_biosphere: bool = False
    emergent_origins: bool = False
    max_emergent_founders: int = 2
    substrate_threshold: float = 0.85
    epidemic_observer: bool = True
    koeppen_refresh_every: int = 200
    observable_every: int = 25
    hydrology_cross_chunk: bool = True
    hydrology_mode: str = "stub"  # stub | sv1d | lbm
    # Physics + chemistry + architecture + social topology layers.
    knowledge_layers: bool = False
    # Macro settlement gravity trade → agent TRADE edges (needs genesis bootstrap).
    macro_commerce: bool = False
    # Observe all agent chunks each tick when native genesis_world is loaded.
    rust_worldgraph_prod: bool = False
    # EMERGENCE SIM v2: genome-encoded policy (NEAT-inspired), not heuristic decide().
    emergent_cognition: bool = False
    # L1 circulation: passive drift from macro/meteo wind field (physical, not AI goal).
    wind_advect_agents: bool = True
    # GraphCast-lite macro wind prior (DeepMind-inspired message passing, CPU numpy).
    graphcast_lite_prior: bool = False
    # Evolve novel world operators (generate → test → select → improve).
    algorithm_lab: bool = False
    # Terre autonome : noyau, plaques, transform matériaux (sans script civilisation).
    autonomous_world: bool = False
    emergent_construction: bool = True


@dataclass
class SimStats:
    tick: int = 0
    alive: int = 0
    cum_births: int = 0
    cum_deaths: int = 0
    cum_events: int = 0
    last_tick_ms: float = 0.0
    chunks_in_mem: int = 0


class Simulation:
    def __init__(self, config: SimConfig, journal_path: Optional[str] = None):
        self.cfg = config
        self.sim_id = str(uuid.uuid4())
        self.tick: int = 0
        self.agents = AgentRegistry(capacity=config.max_agents)
        self.streamer = ChunkStreamer(config.seed, TerrainParams())
        self.annalist = Annalist(self.sim_id, journal_path)
        self.stats = SimStats()
        self._bootstrapped = False
        self._next_child_idx = 0
        self._reproductions_pending: List[Tuple[int, int]] = []
        self._catastrophe_applied = False
        self._grid = SpatialGrid(cell_size_m=PERCEPTION_RADIUS_M / 2.0)
        self._groups: Dict[int, Dict] = {}
        self._next_group_id = 1
        # Phase 4: rate-limit competition penalties per (a,b) pair.
        self._last_competition_tick: Dict[Tuple[int, int], int] = {}
        self._competition_cooldown_ticks = 20
        # Shared with dashboard HTTP threads and run_earth_console step loop.
        self.api_lock = threading.RLock()
        if config.emergence_subsystems:
            from engine.sim_emergence import wire_civilization_emergence
            epidemic_every = 5 if config.catastrophe_at_tick > 0 else 20
            wire_civilization_emergence(
                self,
                koeppen_refresh_every=config.koeppen_refresh_every,
                observable_every=config.observable_every,
                hydrology_cross_chunk=config.hydrology_cross_chunk,
                hydrology_mode=config.hydrology_mode,
                epidemic_snapshot_every=epidemic_every,
                install_epidemic=config.epidemic_observer,
            )
        if config.life_emergence:
            from engine.life_emergence import wire_life_emergence
            wire_life_emergence(self)
        if config.knowledge_layers:
            from engine.knowledge_layers import install_knowledge_layers
            install_knowledge_layers(self)

    def bootstrap(self) -> None:
        if self._bootstrapped:
            return
        cfg = self.cfg
        if cfg.emergent_origins:
            # Life appears from substrate — no scripted founder cluster.
            rng = prf_rng(cfg.seed, ["emergent", "bootstrap", "stream"], [0])
            bx_m = cfg.bounds_km[0] * 1000.0 * 0.5
            by_m = cfg.bounds_km[1] * 1000.0 * 0.5
            for _ in range(12):
                x = float(rng.uniform(-bx_m, bx_m))
                y = float(rng.uniform(-by_m, by_m))
                self.streamer.get(self.tick, world_to_chunk(x, y))
            self._stream_around_agents()
            self.annalist.record_tick(self.tick, self.agents, births=[], deaths=[],
                                      raw_events=[], foundings=[])
            self._bootstrapped = True
            return
        rng = prf_rng(cfg.seed, ["bootstrap"], [cfg.founders])
        per_culture = max(1, cfg.founders // cfg.cultures)
        founder_idx = 0
        for cult in range(cfg.cultures):
            cluster = self._pick_land_position(rng, cfg.bounds_km, max_tries=80)
            for _ in range(per_culture):
                if founder_idx >= cfg.founders:
                    break
                offset = rng.uniform(-cfg.spawn_radius_m, cfg.spawn_radius_m, size=2)
                pos = (float(cluster[0] + offset[0]), float(cluster[1] + offset[1]), 1.0)
                self.agents.spawn_founder(cfg.seed, founder_idx, pos, self.tick, culture_id=cult)
                founder_idx += 1
        self._stream_around_agents()
        foundings = [(r,) for r in range(self.agents.n_active)]
        self.annalist.record_tick(self.tick, self.agents, births=[], deaths=[],
                                  raw_events=[], foundings=foundings)
        self._bootstrapped = True

    def _pick_land_position(self, rng, bounds_km, max_tries: int) -> Tuple[float, float]:
        bx_m = bounds_km[0] * 1000.0 * 0.5
        by_m = bounds_km[1] * 1000.0 * 0.5
        best = None
        best_score = -1.0
        for _ in range(max_tries):
            x = float(rng.uniform(-bx_m, bx_m))
            y = float(rng.uniform(-by_m, by_m))
            coord = world_to_chunk(x, y)
            chunk = self.streamer.get(self.tick, coord)
            cx, cy = world_to_cell(x, y, coord)
            if chunk.height[cy, cx] <= 1.0:
                continue
            if chunk.food_capacity[cy, cx] < 50.0:
                continue
            w_avail = float(chunk.water[max(0,cy-3):cy+4, max(0,cx-3):cx+4].max(initial=0.0))
            f_avail = float(chunk.food_capacity[max(0,cy-2):cy+3, max(0,cx-2):cx+3].mean())
            score = (w_avail / 100.0) + (f_avail / 100.0)
            if w_avail > 5.0 and score > best_score:
                best_score = score
                best = (x, y)
        return best if best is not None else (0.0, 0.0)

    def step(self) -> SimStats:
        with self.api_lock:
            return self._step_unlocked()

    def _step_unlocked(self) -> SimStats:
        t0 = time.monotonic()
        if not self._bootstrapped:
            self.bootstrap()
        self.tick += 1
        self._stream_around_agents()
        for chunk in list(self.streamer.cache.values()):
            base_t = float(np.mean(chunk.height) * -0.0065 + 15.0)
            avg_precip = float(np.mean(chunk.food_capacity) * 3.0)
            w = weather_at(self.tick * int(self.cfg.drive_accel), base_t, avg_precip)
            regenerate_chunk_resources(chunk, w, dt_s=float(self.cfg.drive_accel))
        if self.cfg.emergence_subsystems:
            from engine.sim_emergence import tick_emergence_world
            tick_emergence_world(self)
        self._tick_drives()

        raw_events: List[dict] = []
        if self.cfg.life_emergence:
            from engine.life_emergence import tick_life_emergence
            raw_events.extend(tick_life_emergence(self))
        mate_intents: List[Tuple[int, int]] = []
        n = self.agents.n_active
        self._grid.rebuild(self.agents.pos[:n, :2], self.agents.alive[:n])
        alive_idx = np.flatnonzero(self.agents.alive[:n])
        for row in alive_idx:
            row = int(row)
            obs = perceive(self.agents, row, self.streamer, grid=self._grid, tick=self.tick)
            d = decide(self.agents, obs, sim=self)
            self.agents.action[row] = d.action
            self.agents.target_x[row] = d.target_x
            self.agents.target_y[row] = d.target_y
            ev = apply_decision(self.agents, row, d, self.streamer, self.tick)
            for e in ev:
                if e.get("kind") == "mate_attempt":
                    mate_intents.append((e["a"], e["b"]))
                else:
                    raw_events.append(e)
            if obs.near_agents:
                for j in obs.near_agents[:3]:
                    self.agents.relations[row].update_affinity(j, +0.001)

        RESOURCE_ACTIONS = (int(ActionKind.WALK_TO),)
        target_xy = np.column_stack([self.agents.target_x[:n],
                                     self.agents.target_y[:n]])
        comp_grid = SpatialGrid(cell_size_m=2.0)
        comp_pairs = comp_grid.find_target_collisions(
            target_xy, self.agents.action[:n], self.agents.alive[:n],
            RESOURCE_ACTIONS)
        for a, b in comp_pairs:
            key = (a, b) if a < b else (b, a)
            last = self._last_competition_tick.get(key, -10_000)
            if self.tick - last < self._competition_cooldown_ticks:
                continue
            self._last_competition_tick[key] = self.tick
            self.agents.relations[a].update_affinity(b, -0.03)
            self.agents.relations[b].update_affinity(a, -0.03)
            raw_events.append({"kind": "competition", "a": a, "b": b})

        self.agents.pos[:n, :2] += self.agents.vel[:n, :2] * TICK_DT_S
        bx_m = self.cfg.bounds_km[0] * 1000.0 * 0.5
        by_m = self.cfg.bounds_km[1] * 1000.0 * 0.5
        np.clip(self.agents.pos[:n, 0], -bx_m, bx_m, out=self.agents.pos[:n, 0])
        np.clip(self.agents.pos[:n, 1], -by_m, by_m, out=self.agents.pos[:n, 1])

        self._tick_thermal()

        if (self.cfg.catastrophe_at_tick > 0 and
                not self._catastrophe_applied and
                self.tick >= self.cfg.catastrophe_at_tick):
            self._apply_catastrophe(raw_events)
            self._catastrophe_applied = True

        deaths = self._check_mortality()
        births = self._resolve_matings(mate_intents, raw_events)

        if self.tick % 25 == 0:
            self._detect_groups(raw_events)

        if getattr(self, "_social_topology", None) is not None:
            from engine.social_topology import tick_social_topology
            raw_events.extend(tick_social_topology(self, self._social_topology))

        self.annalist.record_tick(self.tick, self.agents, births=births, deaths=deaths,
                                  raw_events=raw_events)

        if self.tick % 200 == 0:
            self.streamer.gc(self.tick)

        self.stats.tick = self.tick
        self.stats.alive = int(self.agents.alive[:self.agents.n_active].sum())
        self.stats.cum_births = self.annalist.cum_births
        self.stats.cum_deaths = self.annalist.cum_deaths
        self.stats.cum_events = self.annalist.events_emitted
        self.stats.chunks_in_mem = len(self.streamer.cache)
        self.stats.last_tick_ms = (time.monotonic() - t0) * 1000.0
        return self.stats

    def _stream_around_agents(self) -> None:
        n = self.agents.n_active
        alive = np.flatnonzero(self.agents.alive[:n])
        seen = set()
        for r in alive:
            x = float(self.agents.pos[int(r), 0]); y = float(self.agents.pos[int(r), 1])
            ccoord = world_to_chunk(x, y)
            for c in chunks_around(ccoord, radius=2):
                seen.add(c)
        self.streamer.touch_area(self.tick, seen)

    def _tick_drives(self) -> None:
        n = self.agents.n_active
        m = self.agents.alive[:n]
        accel = self.cfg.drive_accel
        for arr, rate in ((self.agents.hunger, HUNGER_PER_S),
                          (self.agents.thirst, THIRST_PER_S),
                          (self.agents.fatigue, FATIGUE_PER_S),
                          (self.agents.sleep, SLEEP_PER_S)):
            arr[:n][m] = np.clip(arr[:n][m] + rate * accel, 0.0, 1.5)
        self.agents.pain[:n][m] = np.maximum(self.agents.pain[:n][m] - 0.001 * accel, 0.0)
        self.agents.stress[:n][m] = np.clip(self.agents.stress[:n][m]
                                            + (self.agents.hunger[:n][m] + self.agents.thirst[:n][m]) * 0.001 * accel
                                            - 0.0005 * accel, 0.0, 1.5)
        self.agents.injuries[:n][m] = np.maximum(self.agents.injuries[:n][m] - 0.00005 * accel, 0.0)
        calm = ((self.agents.hunger[:n] < 0.4) & (self.agents.thirst[:n] < 0.4)
                & (self.agents.injuries[:n] < 0.3))
        recover = m & calm
        self.agents.vitality[:n][recover] = np.minimum(self.agents.vitality[:n][recover] + 0.0001 * accel, 1.0)

    def _tick_thermal(self) -> None:
        """Vectorised thermal-load update.

        Bucket alive agents by chunk coord, look the chunk up once, then
        update the whole bucket in a single numpy op.  At 200 agents this
        is ~5-10× faster than the per-row loop because chunk lookup and
        ``weather_at`` are amortised over many agents instead of run
        per-agent.
        """
        n = self.agents.n_active
        if n == 0:
            return
        live_rows = np.flatnonzero(self.agents.alive[:n])
        if live_rows.size == 0:
            return
        pos = self.agents.pos[live_rows]
        # Compute chunk coord for every live agent in one shot
        cxs = np.floor(pos[:, 0] / CHUNK_SIDE_M).astype(np.int64)
        cys = np.floor(pos[:, 1] / CHUNK_SIDE_M).astype(np.int64)
        # Group by chunk coord — usually only a handful of distinct chunks
        # contain agents, so this dramatically cuts the Python loop length.
        unique_coords: Dict[Tuple[int, int], List[int]] = {}
        for k, (cx, cy) in enumerate(zip(cxs.tolist(), cys.tolist())):
            unique_coords.setdefault((cx, cy), []).append(int(live_rows[k]))
        accel = float(self.cfg.drive_accel)
        weather_tick = self.tick * int(accel)
        for (cx, cy), rows in unique_coords.items():
            chunk = self.streamer.cache.get((cx, cy, 0))
            if chunk is None:
                continue
            rows_arr = np.array(rows, dtype=np.int64)
            xs = self.agents.pos[rows_arr, 0]
            ys = self.agents.pos[rows_arr, 1]
            lx = np.clip(((xs - cx * CHUNK_SIDE_M) / 0.5).astype(np.int64), 0, 63)
            ly = np.clip(((ys - cy * CHUNK_SIDE_M) / 0.5).astype(np.int64), 0, 63)
            base_t = chunk.height[ly, lx].astype(np.float32) * np.float32(-0.0065) + np.float32(15.0)
            # Sample ambient temp once per cell — weather_at is stateless,
            # so we compute one scalar w per row using its own base_t.
            therm = self.agents.thermal[rows_arr]
            for i in range(rows_arr.size):
                w = weather_at(weather_tick, float(base_t[i]), 200.0)
                comfort = 1.0
                if w.temp_c < 0.0:
                    comfort = 1.0 + (0.0 - w.temp_c) * 0.01
                elif w.temp_c > 35.0:
                    comfort = 1.0 + (w.temp_c - 35.0) * 0.01
                therm[i] = float(np.clip(
                    therm[i] + (comfort - 1.0) * 0.02 * accel * 0.001 - 0.005,
                    0.0, 1.5))
            self.agents.thermal[rows_arr] = therm

    def _check_mortality(self) -> List[Tuple[int, int]]:
        n = self.agents.n_active
        deaths: List[Tuple[int, int]] = []
        for row in np.flatnonzero(self.agents.alive[:n]):
            row = int(row)
            cause: Optional[DeathCause] = None
            if self.agents.injuries[row] >= 1.0 or self.agents.vitality[row] <= 0.0:
                cause = DeathCause.VIOLENCE if self.agents.injuries[row] >= 1.0 else DeathCause.EXHAUSTION
            elif self.agents.thirst[row] >= 1.0:
                cause = DeathCause.DEHYDRATION
            elif self.agents.hunger[row] >= 1.0:
                cause = DeathCause.STARVATION
            elif self.agents.thermal[row] >= 1.0:
                cause = DeathCause.COLD
            elif (self.agents.fatigue[row] >= 1.0 and self.agents.sleep[row] >= 1.0):
                cause = DeathCause.EXHAUSTION
            elif (self.tick - int(self.agents.born_tick[row])) > int(self.agents.lifespan_ticks[row] // self.cfg.drive_accel):
                cause = DeathCause.OLD_AGE
            if cause is not None:
                self.agents.kill(row, cause, self.tick)
                deaths.append((row, int(cause)))
        return deaths

    def _resolve_matings(self, intents, raw_events):
        births = []
        seen = set()
        for a, b in intents:
            if not self.agents.alive[a] or not self.agents.alive[b]:
                continue
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            if not self._is_fertile(a) or not self._is_fertile(b):
                continue
            if math.hypot(float(self.agents.pos[a, 0] - self.agents.pos[b, 0]),
                          float(self.agents.pos[a, 1] - self.agents.pos[b, 1])) > MATING_RADIUS_M:
                continue
            child_pos = (
                float((self.agents.pos[a, 0] + self.agents.pos[b, 0]) * 0.5),
                float((self.agents.pos[a, 1] + self.agents.pos[b, 1]) * 0.5),
                float(self.agents.pos[a, 2]),
            )
            self._next_child_idx += 1
            child = self.agents.spawn_offspring(self.cfg.seed, a, b, self.tick,
                                                self._next_child_idx, child_pos)
            if child < 0:
                continue
            self.agents.last_mating_tick[a] = self.tick
            self.agents.last_mating_tick[b] = self.tick
            raw_events.append({"kind": "mating_success", "a": a, "b": b})
            births.append((child, a, b))
        return births

    def _is_fertile(self, row: int) -> bool:
        if self.tick - int(self.agents.born_tick[row]) < (MATURITY_TICKS // max(1, int(self.cfg.drive_accel / 10))):
            return False
        last = int(self.agents.last_mating_tick[row])
        if last >= 0 and (self.tick - last) < (COOLDOWN_TICKS // max(1, int(self.cfg.drive_accel / 10))):
            return False
        if self.agents.hunger[row] > 0.7 or self.agents.thirst[row] > 0.7:
            return False
        return True

    def _detect_groups(self, raw_events: List[dict]) -> None:
        n = self.agents.n_active
        live_rows = np.flatnonzero(self.agents.alive[:n])
        if live_rows.size < 3:
            # All small groups are by definition dissolved — emit closures.
            for gid in list(self._groups.keys()):
                raw_events.append({"kind": "group_dissolved", "group_id": gid,
                                   "reason": "population_too_small"})
                self._groups.pop(gid, None)
            return
        CLUSTER_RADIUS_M = 15.0
        AFFINITY_THRESHOLD = 0.10
        grid = self._grid
        parent = {int(r): int(r) for r in live_rows}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for row in live_rows:
            row_i = int(row)
            px = float(self.agents.pos[row_i, 0])
            py = float(self.agents.pos[row_i, 1])
            cands = grid.query_disk(px, py, CLUSTER_RADIUS_M, exclude_row=row_i)
            aff_map = self.agents.relations[row_i].affinity
            for j in cands:
                if not self.agents.alive[j]:
                    continue
                aff_ij = aff_map.get(j, 0.0)
                aff_ji = self.agents.relations[j].affinity.get(row_i, 0.0)
                if aff_ij < AFFINITY_THRESHOLD or aff_ji < AFFINITY_THRESHOLD:
                    continue
                dx = float(self.agents.pos[j, 0]) - px
                dy = float(self.agents.pos[j, 1]) - py
                if dx * dx + dy * dy > CLUSTER_RADIUS_M * CLUSTER_RADIUS_M:
                    continue
                union(row_i, j)

        comps = {}
        for r in live_rows:
            r_i = int(r)
            root = find(r_i)
            comps.setdefault(root, []).append(r_i)

        for _root, members in comps.items():
            if len(members) < 3:
                continue
            existing_ids = {self.agents.relations[m].group_id
                            for m in members
                            if self.agents.relations[m].group_id is not None}
            if existing_ids:
                gid = min(existing_ids)
            else:
                gid = self._next_group_id
                self._next_group_id += 1
                xs = [float(self.agents.pos[m, 0]) for m in members]
                ys = [float(self.agents.pos[m, 1]) for m in members]
                cx = sum(xs) / len(xs)
                cy = sum(ys) / len(ys)
                lex = np.mean([self.agents.lexicon[m] for m in members], axis=0)
                sig = _stable_bytes_sig(lex.astype(np.float32).tobytes())
                self._groups[gid] = {"formed_tick": self.tick, "size": len(members),
                                     "centroid": (cx, cy), "lex_sig": sig}
                raw_events.append({"kind": "group_formed", "group_id": gid,
                                   "size": len(members), "centroid": (cx, cy),
                                   "lex_sig": sig, "members": members[:32]})
            for m in members:
                self.agents.relations[m].group_id = gid

        # ---- group lifecycle: detect dissolution ----
        # A group is dissolved when its live in-cluster membership falls below
        # the formation threshold of 3.  We count live members whose
        # currently-recorded group_id matches the persisted gid.
        alive_set: Set[int] = set(int(r) for r in live_rows)
        live_per_gid: Dict[int, int] = {}
        for r in live_rows:
            g = self.agents.relations[int(r)].group_id
            if g is not None:
                live_per_gid[g] = live_per_gid.get(g, 0) + 1
        for gid in list(self._groups.keys()):
            if live_per_gid.get(gid, 0) < 3:
                raw_events.append({"kind": "group_dissolved", "group_id": gid,
                                   "reason": "membership_below_threshold"})
                self._groups.pop(gid, None)
                # Clear references on now-orphaned agents so they can rejoin.
                for r in live_rows:
                    if self.agents.relations[int(r)].group_id == gid:
                        self.agents.relations[int(r)].group_id = None

    def _apply_catastrophe(self, raw_events: List[dict]) -> None:
        n = self.agents.n_active
        cx, cy = 0.0, 0.0
        for row in np.flatnonzero(self.agents.alive[:n]):
            row = int(row)
            dx = float(self.agents.pos[row, 0] - cx)
            dy = float(self.agents.pos[row, 1] - cy)
            d = math.hypot(dx, dy)
            if d > self.cfg.catastrophe_radius_m:
                continue
            falloff = max(0.0, 1.0 - d / self.cfg.catastrophe_radius_m)
            dmg = self.cfg.catastrophe_damage * falloff
            self.agents.injuries[row] = float(min(1.0, self.agents.injuries[row] + dmg))
            self.agents.stress[row] = float(min(1.5, self.agents.stress[row] + dmg))
            self.agents.pain[row] = float(min(1.5, self.agents.pain[row] + dmg))
        for chunk in list(self.streamer.cache.values()):
            ccx, ccy, _ = chunk.coord
            chunk_center_x = ccx * CHUNK_SIDE_M + CHUNK_SIDE_M / 2
            chunk_center_y = ccy * CHUNK_SIDE_M + CHUNK_SIDE_M / 2
            d = math.hypot(chunk_center_x - cx, chunk_center_y - cy)
            if d < self.cfg.catastrophe_radius_m:
                falloff = max(0.0, 1.0 - d / self.cfg.catastrophe_radius_m)
                chunk.food_kcal *= (1.0 - 0.7 * falloff)
                chunk.water *= (1.0 - 0.5 * falloff)
        raw_events.append({"kind": "catastrophe"})

    def snapshot_agents(self):
        out = []
        n = self.agents.n_active
        for row in range(n):
            if not self.agents.alive[row]:
                continue
            out.append({
                "row": row, "uuid": str(self.agents.uuid[row]),
                "gen": int(self.agents.generation[row]),
                "born": int(self.agents.born_tick[row]),
                "pos": [float(self.agents.pos[row, 0]), float(self.agents.pos[row, 1])],
                "drives": [float(self.agents.hunger[row]), float(self.agents.thirst[row]),
                           float(self.agents.sleep[row]), float(self.agents.fatigue[row]),
                           float(self.agents.thermal[row])],
                "vit": float(self.agents.vitality[row]),
                "action": int(self.agents.action[row]),
                "culture": int(self.agents.relations[row].culture_id),
                "group_id": self.agents.relations[row].group_id,
                "offspring": int(self.agents.offspring_count[row]),
                "openness": float(self.agents.openness[row]),
                "aggression": float(self.agents.aggression[row]),
                "agreeableness": float(self.agents.agreeableness[row]),
            })
        return out

    def snapshot(self):
        out = {
            "sim_id": self.sim_id, "tick": self.tick,
            "alive": int(self.stats.alive),
            "cum_births": int(self.stats.cum_births),
            "cum_deaths": int(self.stats.cum_deaths),
            "cum_events": int(self.stats.cum_events),
            "chunks_in_mem": int(self.stats.chunks_in_mem),
            "last_tick_ms": float(self.stats.last_tick_ms),
            "wall_clock_s": self.annalist.wall_clock_s(),
            "groups_active": len(self._groups),
        }
        errors: Dict[str, str] = {}
        if self.cfg.emergence_subsystems:
            try:
                from engine.sim_emergence import emergence_snapshot
                out["emergence"] = emergence_snapshot(self)
            except Exception as exc:
                errors["emergence"] = f"{type(exc).__name__}: {exc}"
        if self.cfg.life_emergence:
            try:
                from engine.life_emergence import life_emergence_snapshot
                out["life_emergence"] = life_emergence_snapshot(self)
            except Exception as exc:
                errors["life_emergence"] = f"{type(exc).__name__}: {exc}"
        if self.cfg.knowledge_layers:
            try:
                from engine.knowledge_layers import knowledge_layers_snapshot
                out["knowledge_layers"] = knowledge_layers_snapshot(self)
            except Exception as exc:
                errors["knowledge_layers"] = f"{type(exc).__name__}: {exc}"
        if errors:
            out["snapshot_errors"] = errors
        return out
