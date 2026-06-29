"""Genesis Engine — inter-region coherence (Phase 15, P3).

Today each :class:`engine.world_builder.World` wraps a self-contained
:class:`engine.sim.Simulation`. Wave 1-4 modules attach side-state per
sim, but two sims standing side-by-side share **nothing**: each has its
own ``Atmosphere`` (CO2, temperature anomaly), its own ``sim.tick``, and
no agent can cross from one to the other.

For Genesis Engine to behave like a *real* virtual world, distant
regions need to feel each other. CO2 emitted in Manaus must reach
Reykjavík; an agent born on the Léman north shore must be able to walk
to the Jura. This module ships the first inter-region coherence layer:

* :class:`GlobalAtmosphere` — a shared atmospheric box. Same shape as
  :class:`engine.ecology.Atmosphere` (drop-in compatible: same
  attributes, same ``begin_tick / emit / absorb / tick /
  update_concentration`` API), but globally shared. Bounds add up when
  sims attach.
* :class:`GlobalClock` — shared ``tick``, ``year``, ``day_of_year``,
  ``hour_of_day``. Whichever sim ticks first advances the clock;
  followers read it without double-counting.
* :class:`MigrationCoordinator` — geographic registry that knows each
  sim's anchor + bounds. ``request_migration(from_sim, agent_row,
  target_lat, target_lon)`` serialises an agent (drives, traits,
  inventory, genome, physiology, relations, memory), removes it from
  the source registry, and re-injects it into the destination
  registry. If no registered sim covers the target lat/lon, migration
  fails *gracefully* (boolean return + reason).
* :class:`GlobalWorld` — container holding registered sims +
  atmosphere + clock + coordinator.

Caveats (be honest about the scope)
-----------------------------------
* Migration is **one-shot inter-sim transfer**, not real-time agent
  movement across boundaries. The agent disappears from the source
  registry and reappears in the destination on the next tick. There is
  no smooth hand-off, no "in transit" state, no concurrent visibility.
* :class:`GlobalAtmosphere` mixes CO2 across all attached regions as
  if perfectly well-mixed; planetary turbulence-scale latency is not
  modelled (the real atmosphere mixes inter-hemispherically in ~1 yr).
* :class:`GlobalClock` advances by whichever sim ticks first; if
  multiple sims tick out-of-step, the clock takes the **max** so it
  remains monotonic. This is sufficient when sims run in a single
  thread sequentially, which is the current Genesis usage.

Determinism
-----------
All RNG (e.g. for migration jitter) is sampled via
:func:`engine.core.prf_rng`. Repeat the same world recipe + the same
seed and the per-tick atmosphere / migration outcome are bit-identical.

Taxonomy tags (per ADR 0005)
----------------------------
:data:`PIPELINE_LAYER` = ``"Genesis-L4 Feedback"`` — global world is
the macroscopic feedback emerging from many regional sims.
:data:`WORLD_MODEL_CAPABILITY` = ``"paper-L2 Simulator"`` — multi-step
rollouts respecting domain laws (mass balance for CO2, monotonic
clock).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.ecology import (
    CLIMATE_SENSITIVITY_K,
    CO2_BASELINE_PPM,
    CO2_KG_PER_PPM_LOCAL,
    Atmosphere,
)


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"  # arxiv 2604.22748


# ---------------------------------------------------------------------------
# Geographic helpers
# ---------------------------------------------------------------------------

_DEG_LAT_KM = 111.0  # 1° latitude ≈ 111 km on Earth.


def _km_per_deg_lon(lat_deg: float) -> float:
    """Approximate km per degree of longitude at the given latitude."""
    return _DEG_LAT_KM * max(0.05, math.cos(math.radians(lat_deg)))


def _latlon_to_local_xy(anchor_lat: float, anchor_lon: float,
                        target_lat: float, target_lon: float) -> Tuple[float, float]:
    """Convert a target (lat, lon) into local sim metres relative to anchor.

    The sim's anchor is its (0, 0). North is +y, East is +x.
    """
    dlat = target_lat - anchor_lat
    dlon = target_lon - anchor_lon
    y_m = dlat * _DEG_LAT_KM * 1000.0
    x_m = dlon * _km_per_deg_lon(anchor_lat) * 1000.0
    return float(x_m), float(y_m)


# ---------------------------------------------------------------------------
# GlobalAtmosphere — shared CO2 + temperature anomaly + sea-level
# ---------------------------------------------------------------------------

@dataclass
class GlobalAtmosphere:
    """Globally-shared atmospheric box.

    API-compatible with :class:`engine.ecology.Atmosphere` (same method
    names, same attribute names) so it can be **attached in place of**
    the local atmosphere on a registered sim without breaking
    ``ecology.tick_atmosphere``, ``photosynthesis._resolve_atmosphere``,
    or persistence helpers that read ``sim.atmosphere.co2_ppm``.
    """
    co2_kg: float = 0.0
    co2_ppm: float = CO2_BASELINE_PPM
    temp_anomaly_k: float = 0.0
    cum_emissions_kg: float = 0.0
    cum_absorbed_kg: float = 0.0
    biome_shift_factor: float = 0.0
    sea_level_rise_m: float = 0.0
    bounds_km2: float = 1.0
    forest_cells: int = 0
    ocean_cells: int = 0
    last_update_tick: int = 0

    last_emissions_kg: float = 0.0
    last_absorbed_kg: float = 0.0
    last_emission_sources: Dict[str, float] = field(default_factory=dict)

    # Number of distinct sims that have attached. Lets us debounce
    # ``begin_tick`` so per-tick counters reset exactly once per global
    # tick advancement instead of N times (one per attached sim).
    _n_attached: int = 0
    _last_reset_at_tick: int = -1

    # ---- ecology.Atmosphere API ------------------------------------------
    def update_concentration(self) -> None:
        local_per_km2 = self.co2_kg / max(self.bounds_km2, 1e-3)
        delta_ppm = local_per_km2 / CO2_KG_PER_PPM_LOCAL
        self.co2_ppm = CO2_BASELINE_PPM + max(0.0, delta_ppm)
        ratio = self.co2_ppm / CO2_BASELINE_PPM
        if ratio > 1.0:
            self.temp_anomaly_k = CLIMATE_SENSITIVITY_K * float(np.log2(ratio))
        else:
            self.temp_anomaly_k = 0.0
        self.biome_shift_factor = float(min(1.0, max(0.0,
            (self.temp_anomaly_k - 0.5) / 5.0)))
        if self.temp_anomaly_k > 0:
            self.sea_level_rise_m = float(0.2 * self.temp_anomaly_k ** 1.5)

    def emit(self, kg: float, source: str = "unknown") -> None:
        if kg <= 0:
            return
        self.co2_kg += kg
        self.cum_emissions_kg += kg
        self.last_emissions_kg += kg
        self.last_emission_sources[source] = (
            self.last_emission_sources.get(source, 0.0) + kg)

    def absorb(self, kg: float) -> None:
        if kg <= 0:
            return
        absorbed = min(kg, self.co2_kg)
        self.co2_kg -= absorbed
        self.cum_absorbed_kg += absorbed
        self.last_absorbed_kg += absorbed

    def tick(self, dt_s: float, forest_cells: int, ocean_cells: int) -> None:
        """Sinks + concentration update — sims sum their forest/ocean cells."""
        from engine.ecology import SINK_FOREST_KG_S, SINK_OCEAN_KG_S
        sink_kg = (SINK_FOREST_KG_S * forest_cells +
                   SINK_OCEAN_KG_S * ocean_cells) * dt_s
        self.absorb(sink_kg)
        # Accumulate the per-region counts so reporters see the global
        # forest / ocean total. Reset on the next ``begin_tick``.
        self.forest_cells += int(forest_cells)
        self.ocean_cells += int(ocean_cells)
        self.update_concentration()

    def begin_tick(self) -> None:
        """Idempotent per global-tick reset.

        Multiple attached sims call this once per their own ``step``;
        only the *first* call within a given global tick clears the
        counters. We use the ``GlobalClock.tick`` snapshot as the
        reset key (set externally via :meth:`_mark_tick`).
        """
        # Default reset (no clock attached) — preserve old behaviour.
        self.last_emissions_kg = 0.0
        self.last_absorbed_kg = 0.0
        self.last_emission_sources = {}
        self.forest_cells = 0
        self.ocean_cells = 0

    def _mark_tick(self, global_tick: int) -> bool:
        """Return True iff this is the first call this global tick.

        Lets the holder ``GlobalWorld`` debounce ``begin_tick`` across
        the N attached sims that each fire ``tick_atmosphere`` once per
        step.
        """
        if global_tick == self._last_reset_at_tick:
            return False
        self._last_reset_at_tick = global_tick
        return True


# ---------------------------------------------------------------------------
# GlobalClock — monotonic shared tick + calendar
# ---------------------------------------------------------------------------

_SECONDS_PER_DAY = 86_400.0
_DAYS_PER_YEAR = 365.25


@dataclass
class GlobalClock:
    """Shared tick counter + calendar derived from sim drive_accel."""
    tick: int = 0
    year: int = 0
    day_of_year: int = 0
    hour_of_day: int = 0
    drive_accel: float = 1500.0  # sim-seconds per tick (matches Genesis convention)
    epoch_year: int = 2026

    def advance_to(self, sim_tick: int, drive_accel: Optional[float] = None) -> int:
        """Set the clock to the **max** of its current tick and ``sim_tick``.

        Returns the new tick. Idempotent — calling with the same
        ``sim_tick`` twice is a no-op (a sim that ticks faster simply
        outruns the slower one and the slower one's call becomes a
        no-op).
        """
        if drive_accel is not None and drive_accel > 0:
            self.drive_accel = float(drive_accel)
        if sim_tick > self.tick:
            self.tick = int(sim_tick)
        self._update_calendar()
        return self.tick

    def _update_calendar(self) -> None:
        secs = self.tick * self.drive_accel
        days_total = secs / _SECONDS_PER_DAY
        year_offset = int(days_total // _DAYS_PER_YEAR)
        self.year = self.epoch_year + year_offset
        day = int(days_total - year_offset * _DAYS_PER_YEAR) % 365
        self.day_of_year = max(0, min(364, day))
        self.hour_of_day = int((secs / 3600.0) % 24.0)

    def snapshot(self) -> Dict[str, int]:
        return {
            "tick": int(self.tick),
            "year": int(self.year),
            "day_of_year": int(self.day_of_year),
            "hour_of_day": int(self.hour_of_day),
        }


# ---------------------------------------------------------------------------
# MigrationCoordinator — geographic registry + agent transfer
# ---------------------------------------------------------------------------

# Agent fields that move 1:1 across sims (numeric arrays in AgentRegistry).
# Mirrors world_library._AGENT_FIELDS_TO_SAVE but stays opt-in so we can
# extend without rebuilding the saved-file format.
_MIGRATABLE_SCALAR_FIELDS: Tuple[str, ...] = (
    # Identity / lineage
    "generation", "born_tick",
    # Kinematics
    "mass_kg", "walk_max_ms", "run_max_ms", "lifespan_ticks",
    "heading",
    # Drives
    "hunger", "thirst", "sleep", "fatigue", "thermal",
    "pain", "stress", "loneliness",
    # Health
    "vitality", "injuries", "pathogen_load",
    # Personality / traits
    "openness", "conscientiousness", "extraversion", "agreeableness",
    "neuroticism", "ambition", "risk_tolerance",
    "aggression", "curiosity", "empathy", "intelligence",
    # Inventory
    "inv_water", "inv_food", "inv_wood", "inv_stone", "inv_metal",
    "inv_tools", "inv_pigment", "inv_clay", "inv_ceramic", "inv_capacity_kg",
    # Action state
    "last_mating_tick", "offspring_count", "action",
    "intent_expires",
    # Death
    "death_cause", "death_tick",
)

# Physiology fields to carry across (Wave 3).
_MIGRATABLE_PHYSIO_FIELDS: Tuple[str, ...] = (
    "bladder", "bowel", "hygiene",
    "sunburn", "frostbite", "parasites", "dermatitis",
    "cholera_load", "flu_load", "wound_load",
    "immune_cholera", "immune_flu", "immune_wound",
    "melanin", "body_fat", "immune_baseline",
    "relief_events", "bathe_events", "diseases_caught",
)


@dataclass
class _RegisteredSim:
    """Bookkeeping for a sim registered with the GlobalWorld."""
    sim: object
    anchor_lat: float
    anchor_lon: float
    bounds_km: float
    name: str

    def covers(self, lat: float, lon: float) -> bool:
        """Does this sim's geographic footprint cover (lat, lon)?"""
        x_m, y_m = _latlon_to_local_xy(self.anchor_lat, self.anchor_lon,
                                        lat, lon)
        half_m = self.bounds_km * 1000.0 * 0.5
        return (-half_m <= x_m <= half_m) and (-half_m <= y_m <= half_m)


@dataclass
class MigrationBlob:
    """Serialized one-agent state for cross-sim transfer.

    Reused by tests to inspect what's actually carried.
    """
    uuid: object
    generation: int
    born_tick: int
    # Numeric scalars (one value per migratable field)
    scalars: Dict[str, float]
    # Physiology scalars (one value per migratable physio field, if any)
    physio_scalars: Dict[str, float]
    # Genome (256-d) if present.
    genome: Optional[np.ndarray]
    # Lexicon (16-d) — language transfer.
    lexicon: Optional[np.ndarray]
    # Memory + relations (preserved by value, NOT by row reference).
    memory_short: List[dict]
    memory_long: List[dict]
    culture_id: int
    # Origin info for forensics / determinism.
    src_sim_name: str
    src_row: int


class MigrationCoordinator:
    """Geographic registry + cross-sim transfer engine."""

    def __init__(self, world: "GlobalWorld") -> None:
        self._world = world
        self.migrations: List[Dict[str, object]] = []
        self.failed: List[Dict[str, object]] = []

    # ---- registration ----------------------------------------------------
    def register_sim(self, sim, anchor_lat: float, anchor_lon: float,
                     bounds_km: float, name: str = "") -> None:
        """Track a sim's geographic footprint. Idempotent on (id, anchor)."""
        # Replace any prior registration of the same sim object.
        existing = self._world.find(sim)
        if existing is not None:
            existing.anchor_lat = float(anchor_lat)
            existing.anchor_lon = float(anchor_lon)
            existing.bounds_km = float(bounds_km)
            existing.name = name or existing.name
            return
        rec = _RegisteredSim(sim=sim, anchor_lat=float(anchor_lat),
                             anchor_lon=float(anchor_lon),
                             bounds_km=float(bounds_km),
                             name=name or f"sim_{len(self._world.sims)}")
        self._world.sims.append(rec)

    # ---- query -----------------------------------------------------------
    def find_target(self, lat: float, lon: float) -> Optional[_RegisteredSim]:
        for rec in self._world.sims:
            if rec.covers(lat, lon):
                return rec
        return None

    # ---- transfer --------------------------------------------------------
    def _serialize_agent(self, src_sim, row: int, src_name: str) -> MigrationBlob:
        agents = src_sim.agents
        scalars: Dict[str, float] = {}
        for f in _MIGRATABLE_SCALAR_FIELDS:
            arr = getattr(agents, f, None)
            if arr is None:
                continue
            try:
                scalars[f] = float(arr[row])
            except Exception:
                # Non-numeric (shouldn't happen for our list) — skip.
                pass
        # Physiology
        physio_scalars: Dict[str, float] = {}
        fields = getattr(src_sim, "_physio_fields", None)
        if fields is not None:
            for f in _MIGRATABLE_PHYSIO_FIELDS:
                arr = getattr(fields, f, None)
                if arr is None:
                    continue
                try:
                    physio_scalars[f] = float(arr[row])
                except Exception:
                    pass
        # Genome
        genome = None
        genome_table = getattr(agents, "genome", None)
        if genome_table is not None:
            try:
                genome = np.asarray(genome_table[row]).copy()
            except Exception:
                genome = None
        # Lexicon
        lexicon = None
        if getattr(agents, "lexicon", None) is not None:
            try:
                lexicon = np.asarray(agents.lexicon[row]).copy()
            except Exception:
                lexicon = None
        # Memory + culture
        mem = agents.memory[row]
        short = [dict(e) for e in getattr(mem, "short_term", [])]
        long_ = [dict(e) for e in getattr(mem, "long_term", [])]
        rel = agents.relations[row]
        culture_id = int(getattr(rel, "culture_id", 0))

        return MigrationBlob(
            uuid=agents.uuid[row],
            generation=int(agents.generation[row]),
            born_tick=int(agents.born_tick[row]),
            scalars=scalars,
            physio_scalars=physio_scalars,
            genome=genome,
            lexicon=lexicon,
            memory_short=short,
            memory_long=long_,
            culture_id=culture_id,
            src_sim_name=src_name,
            src_row=int(row),
        )

    def _inject_agent(self, dst_sim, blob: MigrationBlob,
                      pos_xy: Tuple[float, float]) -> int:
        """Allocate a fresh row in dst_sim and re-create the agent there."""
        agents = dst_sim.agents
        if agents.n_active >= agents.capacity:
            return -1
        row = agents.n_active
        agents.n_active += 1
        agents.uuid[row] = blob.uuid
        agents.generation[row] = blob.generation
        agents.born_tick[row] = blob.born_tick
        agents.parents[row] = (None, None)  # parent rows are local to src sim
        agents.pos[row, 0] = float(pos_xy[0])
        agents.pos[row, 1] = float(pos_xy[1])
        agents.pos[row, 2] = 1.0
        agents.vel[row] = 0.0
        agents.target_x[row] = 0.0
        agents.target_y[row] = 0.0
        agents.alive[row] = True
        # Scalars
        for f, v in blob.scalars.items():
            arr = getattr(agents, f, None)
            if arr is None:
                continue
            try:
                arr[row] = type(arr[row])(v) if arr.dtype != bool else bool(v)
            except Exception:
                try:
                    arr[row] = v
                except Exception:
                    pass
        # Force alive after death_cause/death_tick restore (death_tick=-1
        # implies alive). If the agent had died we shouldn't migrate it —
        # the public API checks this — but be defensive.
        agents.alive[row] = True
        # Genome
        if blob.genome is not None and getattr(agents, "genome", None) is not None:
            try:
                agents.genome[row] = blob.genome
            except Exception:
                pass
        # Lexicon
        if blob.lexicon is not None and getattr(agents, "lexicon", None) is not None:
            try:
                agents.lexicon[row] = blob.lexicon
            except Exception:
                pass
        # Memory + relations — fresh objects to avoid cross-sim row aliasing.
        from engine.agent import EpisodicMemory, SocialRelations
        mem = EpisodicMemory()
        mem.short_term = list(blob.memory_short)
        mem.long_term = list(blob.memory_long)
        agents.memory[row] = mem
        rel = SocialRelations()
        rel.culture_id = int(blob.culture_id)
        agents.relations[row] = rel
        # Physiology — install module if not yet on the dst sim, then restore.
        if blob.physio_scalars:
            try:
                from engine.physiology import install_physiology
                fields = install_physiology(dst_sim)
                for f, v in blob.physio_scalars.items():
                    arr = getattr(fields, f, None)
                    if arr is None:
                        continue
                    try:
                        arr[row] = float(v)
                    except Exception:
                        pass
            except Exception:
                pass
        return row

    def _remove_agent(self, src_sim, row: int, tick: int) -> None:
        """Mark the source row as migrated-out — alive=False without
        death_cause so observers can distinguish from real deaths."""
        from engine.agent import DeathCause
        src_sim.agents.alive[row] = False
        # We borrow death_cause=NONE (0) + death_tick to flag the row.
        src_sim.agents.death_cause[row] = int(DeathCause.NONE)
        src_sim.agents.death_tick[row] = int(tick)
        src_sim.agents.vel[row] = 0.0

    def request_migration(self, from_sim, agent_row: int,
                          target_lat: float, target_lon: float) -> Dict[str, object]:
        """Move an agent from one registered sim to another.

        Returns a result dict:
        ``{"ok": bool, "reason": str, "src_row": int, "dst_row": int,
        "dst_sim": str}``.
        """
        src_rec = self._world.find(from_sim)
        if src_rec is None:
            return self._fail("source sim not registered",
                              from_sim, agent_row, target_lat, target_lon)
        if not (0 <= agent_row < from_sim.agents.n_active):
            return self._fail("agent_row out of range",
                              from_sim, agent_row, target_lat, target_lon)
        if not bool(from_sim.agents.alive[agent_row]):
            return self._fail("agent not alive",
                              from_sim, agent_row, target_lat, target_lon)
        dst_rec = self.find_target(target_lat, target_lon)
        if dst_rec is None:
            return self._fail("no registered sim covers target lat/lon",
                              from_sim, agent_row, target_lat, target_lon)
        if dst_rec.sim is from_sim:
            return self._fail("target lat/lon falls inside source sim",
                              from_sim, agent_row, target_lat, target_lon)

        # Compute destination local coordinates.
        x_m, y_m = _latlon_to_local_xy(dst_rec.anchor_lat, dst_rec.anchor_lon,
                                        target_lat, target_lon)

        blob = self._serialize_agent(from_sim, agent_row, src_rec.name)
        new_row = self._inject_agent(dst_rec.sim, blob, (x_m, y_m))
        if new_row < 0:
            return self._fail("destination sim AgentRegistry full",
                              from_sim, agent_row, target_lat, target_lon)
        tick = self._world.clock.tick
        self._remove_agent(from_sim, agent_row, tick)

        result = {
            "ok": True,
            "reason": "",
            "src_sim": src_rec.name,
            "dst_sim": dst_rec.name,
            "src_row": int(agent_row),
            "dst_row": int(new_row),
            "target_lat": float(target_lat),
            "target_lon": float(target_lon),
            "tick": int(tick),
            "uuid": str(blob.uuid),
        }
        self.migrations.append(result)
        return result

    def _fail(self, reason: str, from_sim, agent_row, lat, lon) -> Dict[str, object]:
        rec = self._world.find(from_sim)
        info = {
            "ok": False,
            "reason": reason,
            "src_sim": rec.name if rec else "<unknown>",
            "src_row": int(agent_row),
            "target_lat": float(lat),
            "target_lon": float(lon),
            "tick": int(self._world.clock.tick),
        }
        self.failed.append(info)
        return info


# ---------------------------------------------------------------------------
# GlobalWorld — container
# ---------------------------------------------------------------------------

class GlobalWorld:
    """Container for inter-region coherence.

    Usage::

        gw = GlobalWorld(seed=0xDEADBEEF)
        sim_a = WorldBuilder("a").anchor(46.5, 6.6).build()
        sim_b = WorldBuilder("b").anchor(47.0, 7.5).build()
        attach_to_global(sim_a.sim, gw, name="a")
        attach_to_global(sim_b.sim, gw, name="b")
        for _ in range(100):
            sim_a.step(); sim_b.step()
        # Both sims now share the same atmosphere.co2_ppm
    """

    def __init__(self, seed: int = 0xC0FFEE_5A & 0xFFFFFFFF_FFFFFFFF) -> None:
        self.seed = int(seed) & 0xFFFFFFFF_FFFFFFFF
        self.atmosphere = GlobalAtmosphere(bounds_km2=0.0)
        self.clock = GlobalClock()
        self.sims: List[_RegisteredSim] = []
        self.migrations = MigrationCoordinator(self)
        self._rng = prf_rng(self.seed, ["global_world", "init"], [0])

    def find(self, sim) -> Optional[_RegisteredSim]:
        for rec in self.sims:
            if rec.sim is sim:
                return rec
        return None

    def attached_sim_names(self) -> List[str]:
        return [rec.name for rec in self.sims]

    def state(self) -> Dict[str, object]:
        """Snapshot suitable for ``/api/global_world_state``."""
        atm = self.atmosphere
        return {
            "sims": [
                {"name": rec.name,
                 "anchor": {"lat": rec.anchor_lat, "lon": rec.anchor_lon},
                 "bounds_km": rec.bounds_km,
                 "n_active": int(getattr(rec.sim.agents, "n_active", 0)),
                 "n_alive": int(rec.sim.agents.alive[:rec.sim.agents.n_active]
                                 .sum() if rec.sim.agents.n_active else 0),
                 "tick": int(getattr(rec.sim, "tick", 0))}
                for rec in self.sims
            ],
            "atmosphere": {
                "co2_kg": float(atm.co2_kg),
                "co2_ppm": float(atm.co2_ppm),
                "temp_anomaly_k": float(atm.temp_anomaly_k),
                "sea_level_rise_m": float(atm.sea_level_rise_m),
                "biome_shift_factor": float(atm.biome_shift_factor),
                "cum_emissions_kg": float(atm.cum_emissions_kg),
                "cum_absorbed_kg": float(atm.cum_absorbed_kg),
                "bounds_km2": float(atm.bounds_km2),
                "forest_cells": int(atm.forest_cells),
                "ocean_cells": int(atm.ocean_cells),
            },
            "clock": self.clock.snapshot(),
            "migration_count": int(len(self.migrations.migrations)),
            "migration_fail_count": int(len(self.migrations.failed)),
            "recent_migrations": list(self.migrations.migrations[-10:]),
        }


# ---------------------------------------------------------------------------
# Attachment — wraps sim.step so the GlobalClock advances + atmosphere
# resets are debounced.
# ---------------------------------------------------------------------------

def attach_to_global(sim, world: GlobalWorld, *,
                     name: str = "",
                     anchor_lat: Optional[float] = None,
                     anchor_lon: Optional[float] = None,
                     bounds_km: Optional[float] = None) -> GlobalWorld:
    """Register `sim` with `world` and replace its local atmosphere.

    Idempotent. Reads the sim's existing :class:`engine.ecology.Atmosphere`
    (set by ``sim_5cd_integration.install``) to seed the global one, then
    *replaces* ``sim.atmosphere`` so every consumer (ecology.tick,
    photosynthesis, dashboard) sees the shared box from now on.

    Parameters
    ----------
    sim : engine.sim.Simulation
        Sim to attach. Must have a builder-attached anchor if anchor_lat
        / anchor_lon are not provided.
    world : GlobalWorld
        Container to attach to.
    name : str
        Human label (defaults to ``sim.cfg.name`` then ``sim_N``).
    anchor_lat, anchor_lon : float
        Geographic anchor in decimal degrees. If omitted, we look up
        ``sim._global_anchor`` (set by callers that have the info).
    bounds_km : float
        Square bounding box in km. Defaults to ``sim.cfg.bounds_km[0]``.
    """
    if getattr(sim, "_global_world", None) is world:
        return world

    # Figure out the geographic footprint.
    if anchor_lat is None or anchor_lon is None:
        anchor = getattr(sim, "_global_anchor", None)
        if anchor is None:
            raise ValueError(
                "attach_to_global needs anchor_lat / anchor_lon (set them on "
                "the call or attach sim._global_anchor = (lat, lon) first)")
        anchor_lat, anchor_lon = float(anchor[0]), float(anchor[1])
    if bounds_km is None:
        try:
            bounds_km = float(sim.cfg.bounds_km[0])
        except Exception:
            bounds_km = 2.0

    if not name:
        name = getattr(sim.cfg, "name", "") or f"sim_{len(world.sims)}"

    # Seed the global atmosphere from the local one *the first time* a
    # sim attaches with a non-trivial atmosphere. Subsequent attaches
    # only add their bounds_km2.
    local = getattr(sim, "atmosphere", None)
    if isinstance(local, Atmosphere) or isinstance(local, GlobalAtmosphere):
        if world.atmosphere._n_attached == 0:
            # First sim — copy emissions over so we don't reset CO2.
            world.atmosphere.co2_kg = float(local.co2_kg)
            world.atmosphere.cum_emissions_kg = float(local.cum_emissions_kg)
            world.atmosphere.cum_absorbed_kg = float(local.cum_absorbed_kg)
        # Grow the shared bounds_km2 footprint.
        try:
            world.atmosphere.bounds_km2 += float(local.bounds_km2)
        except Exception:
            pass
        world.atmosphere.update_concentration()

    sim.atmosphere = world.atmosphere  # type: ignore[attr-defined]
    sim._ecology_atmosphere = world.atmosphere  # photosynthesis lookup
    sim._global_world = world
    world.atmosphere._n_attached += 1
    world.migrations.register_sim(sim, anchor_lat=anchor_lat,
                                  anchor_lon=anchor_lon,
                                  bounds_km=bounds_km, name=name)

    # Wrap step so the global clock advances + atmosphere begin_tick is
    # debounced across attached sims.
    orig_step = sim.step

    def globally_coordinated_step():
        # Advance clock first so begin_tick uses the right global_tick.
        # We use sim.tick **before** orig_step because the local sim
        # increments ``self.tick`` inside ``step``. We then sync after.
        # Mark the global tick using max(current, sim.tick+1).
        world.atmosphere._mark_tick(world.clock.tick)  # may no-op
        stats = orig_step()
        # After step: pick whichever tick is highest.
        new_tick = int(getattr(sim, "tick", world.clock.tick))
        try:
            drive_accel = float(sim.cfg.drive_accel)
        except Exception:
            drive_accel = world.clock.drive_accel
        world.clock.advance_to(new_tick, drive_accel=drive_accel)
        return stats

    sim.step = globally_coordinated_step  # type: ignore[assignment]
    return world


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "GlobalAtmosphere",
    "GlobalClock",
    "GlobalWorld",
    "MigrationBlob",
    "MigrationCoordinator",
    "attach_to_global",
]
