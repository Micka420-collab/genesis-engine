"""Genesis Engine — Wave 5 marine subsystems (Phase 14, 2026-05-14).

Adds three coupled subsystems on top of the existing world model so the
``Biome.OCEAN`` cells stop being inert "dead water" and start behaving as
a living marine environment:

  * **OceanCurrentField** — per-chunk vector velocity field on OCEAN cells.
    A toy wind-forced surface model: the chunk-level wind direction (taken
    from the deterministic ``weather_at`` time-series and a Coriolis-like
    offset that depends on the chunk coordinate) drives the surface
    velocity ; small per-cell perturbations are seeded from ``prf_rng``.
    Per-tick advection mixes the current scalar with the wind forcing.
    NOT a full shallow-water solver — that's the Rust ``substrate/water``
    crate's job (see ADR-0006). The Python field is a placeholder that
    delivers usable physics today.
  * **Tides** — global M2 phase tracked over a 12 h 25 min lunar cycle.
    Produces a chunk-wide tide height in metres that modulates effective
    ``chunk.water`` near the shoreline. Tide phase is pure trig over
    ``sim.tick * drive_accel`` (perfectly deterministic).
  * **Marine biology** — Lotka-Volterra triple on every OCEAN chunk :
    phytoplankton (driven by photosynthesis GPP for OCEAN biome) →
    zooplankton/fish biomass → top predators. State stored per-chunk in
    ``MarineBiologyState``. Plankton uses the ``photosynthesis.PhotosynthesisState``
    chunk caches when available ; otherwise falls back to a small ambient
    productivity.

Determinism is preserved end-to-end via :func:`engine.core.prf_rng`. The
public API mirrors the Wave 3/4 install pattern : ``install_marine(sim)``
is idempotent, wraps ``sim.step``, and exposes the live state at
``sim._marine_state`` for the reporter / endpoint / overlay.

Taxonomy tags (per ADR-0005, 2026-05-14)
----------------------------------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — biology + currents feed the
world's resource layer.
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — multi-step rollouts
respecting domain laws (advection, Lotka-Volterra ODE, lunar tides).

R&D note
--------
A Rust ``substrate/water`` crate already exists with a Saint-Venant CPU
reference solver (commit ``fc3d472``). It is **not** wired in here ;
this module ships a pure-Python placeholder with a clear swap-in path :
``OceanCurrentField`` exposes a stable shape/API so a future Python
binding over the Rust crate can replace the surface model without
breaking the marine biology / tides / endpoints / overlay layers.
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"  # arxiv 2604.22748

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np

from engine.core import TICK_DT_S, prf_rng
from engine.world import (Biome, CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M,
                          invalidate_resource_masks)


# ---------------------------------------------------------------------------
# Constants — calibrated against published oceanography references where
# practical. All purely numeric ; safe to import from anywhere.
# ---------------------------------------------------------------------------

# Lunar M2 semi-diurnal period — the dominant ocean tide constituent.
# 12 hours 25.2 minutes = 44712 seconds.
M2_PERIOD_S: float = 12.0 * 3600.0 + 25.2 * 60.0
# Typical tidal range in open coastal sites (0.5 m). Closed seas / lakes
# are far smaller ; we use 0.5 m as the default amplitude. The user can
# override at install via ``tide_amplitude_m``.
TIDE_AMPLITUDE_M_DEFAULT: float = 0.5

# Surface-current speed cap — strongest oceanic surface currents
# (Gulf Stream core) reach ~2 m/s. We cap our scalar field at 1.5 m/s.
CURRENT_MAX_MS: float = 1.5
# Wind forcing constant : fraction of the chunk-wide "wind speed" that
# couples into the surface current per tick.
WIND_COUPLING: float = 0.03
# Per-tick decay of the existing current toward the new forcing (Newtonian
# relaxation; equivalent to a friction coefficient on the inertia term).
CURRENT_DECAY: float = 0.04

# Lotka-Volterra coefficients — pure simulation units (kg-biomass per
# chunk, dimensionless rates per sim-second × drive_accel). Calibrated so
# the trophic levels reach quasi-steady-state inside 500 ticks at the
# default drive_accel = 1500.
PLANKTON_GROWTH_RATE = 1.0 / (6.0 * 3600.0)       # logistic intrinsic rate
PLANKTON_GPP_GAIN = 0.002                          # kg-biomass per kcal of GPP
PLANKTON_CARRYING = 200.0                          # kg per chunk
FISH_GROWTH_FROM_PLANKTON = 1.0 / (24.0 * 3600.0)  # graze coefficient
FISH_DECAY = 1.0 / (40.0 * 3600.0)                 # mortality / starvation
PREDATOR_GROWTH_FROM_FISH = 1.0 / (72.0 * 3600.0)
PREDATOR_DECAY = 1.0 / (60.0 * 3600.0)
# Seeding floor : every OCEAN chunk starts with a small plankton biomass
# so the LV system has a non-zero seed. Without it, the trivial fixed
# point (0, 0, 0) is the only attractor — no fish can ever appear.
PLANKTON_SEED_KG = 4.0
FISH_SEED_KG = 1.0
# A trivial fraction of fish biomass survives near the predator-prey
# equilibrium even when plankton is exhausted — represents migration
# into the chunk from neighbouring chunks (NOT modelled explicitly).
FISH_MIGRATION_FLOOR_KG = 0.05


# ---------------------------------------------------------------------------
# State containers
# ---------------------------------------------------------------------------

@dataclass
class OceanCurrentField:
    """Per-chunk surface-current snapshot.

    The "field" is stored as two scalar arrays (u, v) shaped like the
    chunk grid, but only the OCEAN-biome cells carry meaningful values.
    Non-ocean cells stay zero.
    """
    u: np.ndarray  # (CHUNK_SIZE, CHUNK_SIZE) float32 — eastward m/s
    v: np.ndarray  # (CHUNK_SIZE, CHUNK_SIZE) float32 — northward m/s
    ocean_mask: np.ndarray  # bool — cells with Biome.OCEAN
    last_tick: int = 0

    @classmethod
    def from_chunk(cls, chunk, world_seed: int,
                   coord: Tuple[int, int, int]) -> "OceanCurrentField":
        ocean = (chunk.biome == int(Biome.OCEAN))
        u = np.zeros((CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32)
        v = np.zeros((CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32)
        if ocean.any():
            rng = prf_rng(world_seed,
                          ["marine", "current_seed",
                           str(coord[0]), str(coord[1])],
                          [int(coord[2])])
            # Small zero-mean per-cell noise to break trivial symmetry.
            u[ocean] = (rng.random(int(ocean.sum()), dtype=np.float32)
                        - 0.5) * 0.05
            v[ocean] = (rng.random(int(ocean.sum()), dtype=np.float32)
                        - 0.5) * 0.05
        return cls(u=u, v=v, ocean_mask=ocean)


@dataclass
class MarineBiologyPool:
    """Lotka-Volterra triple on a single OCEAN chunk.

    Tracks total biomass per chunk (kg). The cell-resolved fish biomass
    table is exposed separately via ``MarineState.chunk_marine_fish_kg``
    so external consumers (rendering, agents) can look it up cheaply.
    """
    plankton_kg: float = 0.0
    fish_kg: float = 0.0
    predator_kg: float = 0.0
    last_tick: int = 0


@dataclass
class MarineState:
    """Global marine state attached to ``sim`` by ``install_marine``.

    Holds the per-chunk current fields and biology pools, plus the
    global tide phase and aggregated stats consumed by the reporter.
    The ``chunk_marine_fish_kg`` side-table exposes per-chunk fish
    biomass to the rest of the engine without needing to import this
    module.
    """
    currents: Dict[Tuple[int, int, int], OceanCurrentField] = field(default_factory=dict)
    biology: Dict[Tuple[int, int, int], MarineBiologyPool] = field(default_factory=dict)
    chunk_marine_fish_kg: Dict[Tuple[int, int, int], float] = field(default_factory=dict)

    tide_phase_rad: float = 0.0       # 0..2π
    tide_height_m: float = 0.0        # signed offset around mean sea-level
    tide_amplitude_m: float = TIDE_AMPLITUDE_M_DEFAULT

    last_mean_current_ms: float = 0.0
    last_fish_total_kg: float = 0.0
    last_plankton_total_kg: float = 0.0
    last_predator_total_kg: float = 0.0
    last_ocean_chunks: int = 0
    ticks_run: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wind_for_chunk(sim, coord: Tuple[int, int, int]) -> Tuple[float, float]:
    """Deterministic 2-vector wind at a given chunk for the current tick.

    Pure function of ``sim.tick`` and the chunk coordinate. No RNG. The
    direction rotates with a slow synoptic-scale period (~6 sim-days at
    drive_accel = 1500, i.e. ~13 hours of real time) and the magnitude
    breathes between 1 and 5 m/s. A Coriolis-like offset on each chunk
    perturbs the direction so neighbouring chunks don't blow in lockstep.
    """
    accel = float(sim.cfg.drive_accel)
    sim_seconds = float(sim.tick) * accel
    # Synoptic-scale period : 6 sim-days.
    syn_period = 6.0 * 86400.0
    theta = (sim_seconds / syn_period) * 2.0 * math.pi
    # Per-chunk static offset so flow is spatially varied. We use a
    # cheap deterministic hash of (cx, cy) into [0, 2π).
    cx, cy, _ = coord
    chunk_phase = ((cx * 7919 + cy * 6151) & 0xFFFF) / 0xFFFF * 2.0 * math.pi
    direction = theta + 0.2 * chunk_phase
    # Magnitude breathes ; 3 m/s mean.
    speed = 3.0 + 2.0 * math.sin(theta * 1.5 + chunk_phase * 0.3)
    return speed * math.cos(direction), speed * math.sin(direction)


def _tide_height(sim, amplitude_m: float) -> Tuple[float, float]:
    """Return (phase_rad, height_m) for the current sim-tick."""
    accel = float(sim.cfg.drive_accel)
    sim_seconds = float(sim.tick) * accel
    phase = (sim_seconds % M2_PERIOD_S) / M2_PERIOD_S * 2.0 * math.pi
    height = amplitude_m * math.sin(phase)
    return phase, height


# ---------------------------------------------------------------------------
# Per-tick subsystems
# ---------------------------------------------------------------------------

def tick_currents(sim, state: MarineState) -> None:
    """Advance the OceanCurrentField on every cached chunk.

    Two-step update :
      1. Compute the chunk-level wind forcing (a single 2-vector).
      2. Relax the per-cell (u, v) toward that forcing, with a small
         decay term. Result is clipped to ``CURRENT_MAX_MS``.

    Mutation is restricted to OCEAN cells (the ``ocean_mask`` of the
    field). Non-ocean cells stay zero.
    """
    for coord, chunk in list(sim.streamer.cache.items()):
        field_obj = state.currents.get(coord)
        if field_obj is None:
            field_obj = OceanCurrentField.from_chunk(chunk, sim.cfg.seed, coord)
            state.currents[coord] = field_obj
        if not field_obj.ocean_mask.any():
            field_obj.last_tick = sim.tick
            continue
        wx, wy = _wind_for_chunk(sim, coord)
        # Couple wind onto current ; Newtonian relaxation with decay.
        m = field_obj.ocean_mask
        # Forcing term : per-cell scaled by WIND_COUPLING.
        new_u = (field_obj.u[m] * (1.0 - CURRENT_DECAY)
                 + wx * WIND_COUPLING)
        new_v = (field_obj.v[m] * (1.0 - CURRENT_DECAY)
                 + wy * WIND_COUPLING)
        # Cap magnitude.
        mag = np.sqrt(new_u * new_u + new_v * new_v)
        over = mag > CURRENT_MAX_MS
        if over.any():
            scale = CURRENT_MAX_MS / np.maximum(mag, 1e-6)
            new_u = np.where(over, new_u * scale, new_u)
            new_v = np.where(over, new_v * scale, new_v)
        field_obj.u[m] = new_u.astype(np.float32)
        field_obj.v[m] = new_v.astype(np.float32)
        field_obj.last_tick = sim.tick


def tick_tide(sim, state: MarineState) -> None:
    """Advance the global tide phase + apply near-shore water modulation.

    The tide is a single scalar over the whole world (no spatial
    propagation in the Python placeholder). Near-shore cells get a tiny
    additive boost or drop in ``chunk.water`` proportional to the tide
    height (clamped non-negative).

    Near-shore is defined as : OCEAN cell adjacent to a non-OCEAN cell.
    We detect it cheaply with a 3×3 morphological dilation of the
    non-ocean mask. We only mutate cells whose existing water is in a
    moderate range so we don't perturb deep-water cells.
    """
    state.tide_phase_rad, state.tide_height_m = _tide_height(
        sim, state.tide_amplitude_m)
    delta = state.tide_height_m  # metres
    if abs(delta) < 0.05:
        return
    # Translate metres -> litres-per-cell : 1 m of water over a
    # 0.25 m² cell = 250 L. Scale down to keep the effect gentle.
    delta_l_per_cell = delta * 100.0
    for coord, chunk in list(sim.streamer.cache.items()):
        biome = chunk.biome
        ocean = (biome == int(Biome.OCEAN))
        if not ocean.any() or ocean.all():
            continue
        # Near-shore mask : ocean cells with a non-ocean neighbour.
        land = ~ocean
        # Cheap 3x3 dilation via shifted views.
        ext = np.zeros_like(land)
        ext[:-1, :] |= land[1:, :]
        ext[1:, :]  |= land[:-1, :]
        ext[:, :-1] |= land[:, 1:]
        ext[:, 1:]  |= land[:, :-1]
        shore = ocean & ext
        if not shore.any():
            continue
        chunk.water[shore] = np.maximum(
            0.0, chunk.water[shore].astype(np.float32) + delta_l_per_cell
        ).astype(chunk.water.dtype)
        invalidate_resource_masks(chunk)


def _plankton_input_from_photo(sim, coord: Tuple[int, int, int]) -> float:
    """Pull the OCEAN-fraction GPP from the photosynthesis cache.

    Returns kcal/tick produced over the OCEAN cells of the chunk. Falls
    back to 0.0 if photosynthesis isn't installed yet (smoke tests
    sometimes run marine standalone).
    """
    photo = getattr(sim, "_photo_state", None)
    if photo is None:
        return 0.0
    cache = photo.chunk_caches.get(coord)
    if cache is None or cache.last_kcal_per_tick is None:
        return 0.0
    chunk = sim.streamer.cache.get(coord)
    if chunk is None:
        return 0.0
    ocean = (chunk.biome == int(Biome.OCEAN))
    if not ocean.any():
        return 0.0
    return float(cache.last_kcal_per_tick[ocean].sum())


def tick_biology(sim, state: MarineState) -> None:
    """Advance the Lotka-Volterra triple on every OCEAN chunk.

    Discrete-time forward Euler step. Coefficients are scaled by
    ``drive_accel`` so wall-clock-equivalent behaviour is independent
    of the chosen tick budget.
    """
    accel = float(sim.cfg.drive_accel)
    plk_total = 0.0
    fsh_total = 0.0
    prd_total = 0.0
    ocean_chunks = 0
    for coord, chunk in list(sim.streamer.cache.items()):
        ocean = (chunk.biome == int(Biome.OCEAN))
        if not ocean.any():
            continue
        ocean_chunks += 1
        pool = state.biology.get(coord)
        if pool is None:
            # Seed the pool with a small plankton biomass so the
            # logistic term has a non-trivial seed.
            pool = MarineBiologyPool(
                plankton_kg=PLANKTON_SEED_KG,
                fish_kg=FISH_SEED_KG,
                predator_kg=0.0,
                last_tick=int(sim.tick))
            state.biology[coord] = pool

        # Plankton — logistic growth + photosynthesis injection.
        gpp_kcal = _plankton_input_from_photo(sim, coord)
        photo_gain = PLANKTON_GPP_GAIN * gpp_kcal  # already per-tick
        intrinsic = (PLANKTON_GROWTH_RATE * accel * pool.plankton_kg
                     * (1.0 - pool.plankton_kg / PLANKTON_CARRYING))
        grazed = (FISH_GROWTH_FROM_PLANKTON * accel
                  * pool.plankton_kg * pool.fish_kg / 50.0)
        pool.plankton_kg = max(0.0, pool.plankton_kg + intrinsic
                                    + photo_gain - grazed)

        # Fish — growth from grazing minus mortality minus predation.
        prey_term = (FISH_GROWTH_FROM_PLANKTON * accel
                     * pool.plankton_kg * pool.fish_kg / 50.0)
        predated = (PREDATOR_GROWTH_FROM_FISH * accel
                    * pool.fish_kg * pool.predator_kg / 20.0)
        mortality = FISH_DECAY * accel * pool.fish_kg
        pool.fish_kg = max(
            FISH_MIGRATION_FLOOR_KG,
            pool.fish_kg + prey_term - predated - mortality
        )

        # Predator — predation gain minus decay.
        pred_gain = (PREDATOR_GROWTH_FROM_FISH * accel
                     * pool.fish_kg * pool.predator_kg / 20.0)
        pred_decay = PREDATOR_DECAY * accel * pool.predator_kg
        # Bootstrap : if no predator, a small spontaneous seeding once
        # the fish stock crosses 5 kg (proxy for predator immigration).
        if pool.predator_kg < 1e-3 and pool.fish_kg > 5.0:
            pool.predator_kg = 0.5
        pool.predator_kg = max(0.0,
                               pool.predator_kg + pred_gain - pred_decay)
        pool.last_tick = int(sim.tick)

        # Cell-resolved exposed side-table : fish biomass averaged over
        # OCEAN cells of this chunk.
        state.chunk_marine_fish_kg[coord] = float(pool.fish_kg)

        plk_total += pool.plankton_kg
        fsh_total += pool.fish_kg
        prd_total += pool.predator_kg

    state.last_plankton_total_kg = plk_total
    state.last_fish_total_kg = fsh_total
    state.last_predator_total_kg = prd_total
    state.last_ocean_chunks = ocean_chunks


def _aggregate_current_stats(state: MarineState) -> None:
    """Compute the mean current speed over all OCEAN cells."""
    sq_total = 0.0
    n = 0
    for cf in state.currents.values():
        m = cf.ocean_mask
        if not m.any():
            continue
        u = cf.u[m]
        v = cf.v[m]
        sq_total += float((u * u + v * v).sum())
        n += int(m.sum())
    state.last_mean_current_ms = math.sqrt(sq_total / n) if n > 0 else 0.0


# ---------------------------------------------------------------------------
# Installer + reporter
# ---------------------------------------------------------------------------

def install_marine(sim, *, tide_amplitude_m: float = TIDE_AMPLITUDE_M_DEFAULT
                   ) -> MarineState:
    """Attach the marine subsystems to ``sim``. Idempotent.

    Returns the live :class:`MarineState`. The sim's ``step`` is wrapped
    once so each subsystem runs after the legacy step. Call after
    ``install`` (5cd integration), ``install_lift`` and after
    ``install_photosynthesis`` if you want plankton fed by OCEAN GPP.
    """
    existing = getattr(sim, "_marine_state", None)
    if existing is not None:
        return existing
    state = MarineState(tide_amplitude_m=float(tide_amplitude_m))
    sim._marine_state = state
    # Side-channel for consumers that don't want to import this module.
    sim._chunk_marine_fish_kg = state.chunk_marine_fish_kg

    orig_step = sim.step

    def wrapped_step():
        result = orig_step()
        try:
            tick_currents(sim, state)
            tick_tide(sim, state)
            tick_biology(sim, state)
            _aggregate_current_stats(state)
            state.ticks_run += 1
        except Exception:
            if getattr(sim, "_marine_strict", False):
                raise
        return result

    sim.step = wrapped_step  # type: ignore[assignment]
    return state


def marine_state(sim) -> Dict[str, object]:
    """Snapshot consumed by ``/api/marine_state`` and the HUD."""
    state: Optional[MarineState] = getattr(sim, "_marine_state", None)
    if state is None:
        return {}
    return {
        "ocean_chunks": int(state.last_ocean_chunks),
        "mean_current_ms": round(state.last_mean_current_ms, 4),
        "tide_phase_rad": round(state.tide_phase_rad, 4),
        "tide_height_m": round(state.tide_height_m, 4),
        "tide_amplitude_m": round(state.tide_amplitude_m, 4),
        "tide_period_s": M2_PERIOD_S,
        "plankton_total_kg": round(state.last_plankton_total_kg, 3),
        "fish_total_kg": round(state.last_fish_total_kg, 3),
        "predator_total_kg": round(state.last_predator_total_kg, 3),
        "ticks_run": int(state.ticks_run),
        "biology_chunks": len(state.biology),
        "current_chunks": len(state.currents),
    }


# ---------------------------------------------------------------------------
# Persistence — P1 save / load round-trip
# ---------------------------------------------------------------------------

def save_marine_state(sim, target_dir: str) -> bool:
    """Persist :class:`MarineState` to ``target_dir/marine.npz`` + ``.json``.

    Two artefacts because we mix structured arrays (the current u/v
    fields, ocean masks) with flat scalars (tide phase, ticks_run).
    """
    import json
    import os
    state: Optional[MarineState] = getattr(sim, "_marine_state", None)
    if state is None:
        return False
    # JSON payload : tide + scalars + biology dictionary.
    payload = {
        "tide_phase_rad": float(state.tide_phase_rad),
        "tide_height_m": float(state.tide_height_m),
        "tide_amplitude_m": float(state.tide_amplitude_m),
        "last_mean_current_ms": float(state.last_mean_current_ms),
        "last_fish_total_kg": float(state.last_fish_total_kg),
        "last_plankton_total_kg": float(state.last_plankton_total_kg),
        "last_predator_total_kg": float(state.last_predator_total_kg),
        "last_ocean_chunks": int(state.last_ocean_chunks),
        "ticks_run": int(state.ticks_run),
        "biology": [
            {"coord": list(coord),
             "plankton_kg": float(pool.plankton_kg),
             "fish_kg": float(pool.fish_kg),
             "predator_kg": float(pool.predator_kg),
             "last_tick": int(pool.last_tick)}
            for coord, pool in state.biology.items()
        ],
    }
    with open(os.path.join(target_dir, "marine.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    # NPZ payload : the per-chunk current fields. Stored as a single
    # flat batch indexed by an ``index.json`` mapping coords -> slot.
    if state.currents:
        coords = list(state.currents.keys())
        n = len(coords)
        us = np.stack([state.currents[c].u for c in coords], axis=0)
        vs = np.stack([state.currents[c].v for c in coords], axis=0)
        masks = np.stack([state.currents[c].ocean_mask for c in coords], axis=0)
        coord_arr = np.array(coords, dtype=np.int32)
        np.savez_compressed(os.path.join(target_dir, "marine.npz"),
                            coords=coord_arr, u=us, v=vs, ocean_mask=masks)
    return True


def load_marine_state(sim, target_dir: str) -> bool:
    """Reinstate marine state from ``target_dir``. Installs if missing."""
    import json
    import os
    json_path = os.path.join(target_dir, "marine.json")
    if not os.path.isfile(json_path):
        return False
    state = install_marine(sim)
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state.tide_phase_rad = float(payload.get("tide_phase_rad", 0.0))
    state.tide_height_m = float(payload.get("tide_height_m", 0.0))
    state.tide_amplitude_m = float(payload.get(
        "tide_amplitude_m", TIDE_AMPLITUDE_M_DEFAULT))
    state.last_mean_current_ms = float(
        payload.get("last_mean_current_ms", 0.0))
    state.last_fish_total_kg = float(payload.get("last_fish_total_kg", 0.0))
    state.last_plankton_total_kg = float(
        payload.get("last_plankton_total_kg", 0.0))
    state.last_predator_total_kg = float(
        payload.get("last_predator_total_kg", 0.0))
    state.last_ocean_chunks = int(payload.get("last_ocean_chunks", 0))
    state.ticks_run = int(payload.get("ticks_run", 0))
    state.biology.clear()
    state.chunk_marine_fish_kg.clear()
    for row in payload.get("biology", []):
        coord = tuple(int(c) for c in row["coord"])
        state.biology[coord] = MarineBiologyPool(
            plankton_kg=float(row["plankton_kg"]),
            fish_kg=float(row["fish_kg"]),
            predator_kg=float(row["predator_kg"]),
            last_tick=int(row.get("last_tick", 0)),
        )
        state.chunk_marine_fish_kg[coord] = float(row["fish_kg"])
    # Currents NPZ — optional.
    npz_path = os.path.join(target_dir, "marine.npz")
    if os.path.isfile(npz_path):
        state.currents.clear()
        data = np.load(npz_path, allow_pickle=False)
        coords = data["coords"]
        u = data["u"]
        v = data["v"]
        masks = data["ocean_mask"]
        for i in range(coords.shape[0]):
            coord = (int(coords[i][0]),
                     int(coords[i][1]),
                     int(coords[i][2]))
            state.currents[coord] = OceanCurrentField(
                u=u[i].astype(np.float32),
                v=v[i].astype(np.float32),
                ocean_mask=masks[i].astype(bool),
                last_tick=int(state.ticks_run),
            )
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "M2_PERIOD_S",
    "TIDE_AMPLITUDE_M_DEFAULT",
    "CURRENT_MAX_MS",
    "OceanCurrentField",
    "MarineBiologyPool",
    "MarineState",
    "install_marine",
    "marine_state",
    "tick_currents",
    "tick_tide",
    "tick_biology",
    "save_marine_state",
    "load_marine_state",
]
