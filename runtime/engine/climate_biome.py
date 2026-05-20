"""Genesis Engine — Wave 20 climate-driven biome migration.

Couples the **macro temperature anomaly** (computed from the
:class:`engine.world_genesis.GenesisWorld` baseline + per-tick warming)
into the **per-chunk biome map** so that long simulations expose the
visible footprint of climate change at chunk resolution.

Background
----------

Wave 16-19 built a coherent macro world : tectonics, hydrology, climate
bands. Each ``engine.world.Chunk`` is born with its biome frozen at
generation time from a snapshot of macro ``temp_c`` / ``precip_mm`` /
``elevation_m`` via the Whittaker classifier. After that the biome
**never moves**, even if the simulation runs for tens of thousands of
ticks and the sim-years roll past.

In reality a +2 K warming over a few sim-centuries pushes the tree line
hundreds of km north, shrinks the cryosphere and expands the tropics.
Wave 20 implements that : every tick, a per-cell coin flip decides
whether the cell shifts to the warmer (or cooler) neighbour biome in a
Whittaker-style succession ladder.

Pipeline
--------

::

    install_climate_biome(sim, anchor, *, anomaly_source, warming_rate_c_per_year,
                                          transition_speed)
        ├─ snapshot baseline_temp_c[coord] for every cached chunk
        ├─ monkey-patch sim.step()  ->  apply_climate_biome_step(sim) after
        │                              the original step.
        └─ store state on sim._climate_biome_state

    apply_climate_biome_step(sim):
        global_dT = _anomaly_for_tick(state, sim)             # linear or macro
        for coord, chunk in sim.streamer.cache.items():
            dT = global_dT + per-chunk jitter
            state.current_anomaly_c[coord] = dT
            if |dT| < threshold: continue
            rng   = prf_rng(sim.cfg.seed, ['climate_biome','transition'],
                            [sim.tick, cx, cy, cz])
            probs = rng.random(chunk.biome.shape)
            cell_should_shift = probs < transition_speed * f(|dT|)
            new_biome = _shift_biomes(chunk.biome, dT > 0, chunk.precip[approx])
            chunk.biome = np.where(cell_should_shift & changed, new_biome,
                                    chunk.biome)
            chunk.food_capacity = _npp_table[chunk.biome] * 500.0
            invalidate_resource_masks(chunk)

Shift rules (warming) :

    OCEAN              -> OCEAN  (no change, water dominated)
    ICE                -> TUNDRA
    TUNDRA             -> BOREAL_FOREST
    BOREAL_FOREST      -> TEMPERATE_FOREST
    TEMPERATE_FOREST   -> TROPICAL_DRY_FOREST   if  precip_proxy < 1500
                        TROPICAL_RAINFOREST     otherwise
    TEMPERATE_RAINFOR  -> TROPICAL_RAINFOREST
    GRASSLAND          -> SAVANNA
    COLD_DESERT        -> GRASSLAND
    SAVANNA            -> HOT_DESERT            if precip < 500
                        TROPICAL_DRY_FOREST     otherwise
    TROPICAL_DRY_FOR.  -> TROPICAL_RAINFOREST
    HOT_DESERT         -> HOT_DESERT  (terminal)
    TROPICAL_RAINFOR.  -> TROPICAL_RAINFOREST  (terminal)

Cooling reverses the ladder (e.g. BOREAL_FOREST -> TUNDRA,
TEMPERATE_FOREST -> BOREAL_FOREST, etc.).

Determinism
-----------

All RNG flows through :func:`engine.core.prf_rng` keyed by
``(sim.cfg.seed, ['climate_biome', 'transition'], [tick, cx, cy, cz])``.
The per-cell decision draws a single ``rng.random(shape)`` array : two
sims with the same seed see bit-identical shifted cells.

Read-only contract
------------------

The :class:`engine.world_genesis.GenesisWorld` macro arrays are never
mutated. Only ``chunk.biome`` and ``chunk.food_capacity`` change ; the
streamer cache is the authoritative source for downstream consumers
(:mod:`engine.cognition`, :mod:`engine.agriculture`, …).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np

from engine.core import prf_rng, TICK_DT_S
from engine.world import (CHUNK_SIDE_M, Biome, invalidate_resource_masks,
                          _BIOME_NPP)
from engine.world_genesis import GenesisAnchor


PIPELINE_LAYER = "Genesis-L2 Climate"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

# Below this absolute anomaly (in °C) we don't bother running the per-cell
# pass. Avoids per-tick overhead on undisturbed worlds.
ANOMALY_DEADBAND_C = 0.05

# Maximum probability multiplier from anomaly amplitude. The per-cell shift
# probability is ``transition_speed * clip(|dT| / SCALE, 0, MAX_MULT)``.
ANOMALY_PROB_SCALE_C = 1.0
ANOMALY_PROB_MAX_MULT = 6.0

# Per-chunk per-tick spatial jitter on the temperature anomaly (°C). Off by
# default — deterministic transitions across the cache.
DEFAULT_JITTER_C = 0.0

# Convert sim-tick to sim-year with engine.core.TICK_DT_S (=1 sim-second)
# and ``sim.cfg.drive_accel`` (=accelerated real-time multiplier).
SECONDS_PER_YEAR = 86_400.0 * 365.0


# ---------------------------------------------------------------------------
# Transition matrices — Biome enum (12 entries) -> Biome enum
# ---------------------------------------------------------------------------

# These are 12-entry uint8 arrays, indexed by current Biome -> target Biome
# under a warming shift. Terminal biomes (HOT_DESERT, TROPICAL_RAINFOREST,
# OCEAN) map to themselves. ``_WARMING_TO_DRY`` and ``_WARMING_TO_WET``
# disambiguate the precip-conditional transitions in two paths so the apply
# routine can index by a precip mask.

_WARMING_TO_DRY = np.array([
    int(Biome.OCEAN),                # 0  OCEAN -> OCEAN
    int(Biome.TUNDRA),                # 1  ICE -> TUNDRA
    int(Biome.BOREAL_FOREST),         # 2  TUNDRA -> BOREAL_FOREST
    int(Biome.TEMPERATE_FOREST),      # 3  BOREAL_FOREST -> TEMPERATE_FOREST
    int(Biome.TROPICAL_DRY_FOREST),   # 4  TEMPERATE_FOREST (dry) -> TDF
    int(Biome.TROPICAL_RAINFOREST),   # 5  TEMP_RAINFOREST -> TROP_RAINFOREST
    int(Biome.SAVANNA),               # 6  GRASSLAND -> SAVANNA
    int(Biome.HOT_DESERT),            # 7  HOT_DESERT (terminal)
    int(Biome.GRASSLAND),             # 8  COLD_DESERT -> GRASSLAND
    int(Biome.HOT_DESERT),            # 9  SAVANNA (dry) -> HOT_DESERT
    int(Biome.TROPICAL_RAINFOREST),   # 10 TROP_DRY -> TROP_RAINFOREST
    int(Biome.TROPICAL_RAINFOREST),   # 11 TROP_RAINFOREST (terminal)
], dtype=np.uint8)

_WARMING_TO_WET = np.array([
    int(Biome.OCEAN),
    int(Biome.TUNDRA),
    int(Biome.BOREAL_FOREST),
    int(Biome.TEMPERATE_FOREST),
    int(Biome.TROPICAL_RAINFOREST),   # 4  TEMPERATE_FOREST (wet) -> TROP_RAIN
    int(Biome.TROPICAL_RAINFOREST),
    int(Biome.SAVANNA),
    int(Biome.HOT_DESERT),
    int(Biome.GRASSLAND),
    int(Biome.TROPICAL_DRY_FOREST),   # 9  SAVANNA (wet) -> TROP_DRY_FOREST
    int(Biome.TROPICAL_RAINFOREST),
    int(Biome.TROPICAL_RAINFOREST),
], dtype=np.uint8)

# Cooling ladder — opposite direction. Terminal: ICE and OCEAN.
_COOLING = np.array([
    int(Biome.OCEAN),                 # 0  OCEAN -> OCEAN
    int(Biome.ICE),                   # 1  ICE (terminal)
    int(Biome.ICE),                   # 2  TUNDRA -> ICE
    int(Biome.TUNDRA),                # 3  BOREAL_FOREST -> TUNDRA
    int(Biome.BOREAL_FOREST),         # 4  TEMPERATE_FOREST -> BOREAL
    int(Biome.TEMPERATE_FOREST),      # 5  TEMP_RAINFOREST -> TEMPERATE_FOREST
    int(Biome.COLD_DESERT),           # 6  GRASSLAND -> COLD_DESERT
    int(Biome.SAVANNA),               # 7  HOT_DESERT -> SAVANNA
    int(Biome.TUNDRA),                # 8  COLD_DESERT -> TUNDRA
    int(Biome.GRASSLAND),             # 9  SAVANNA -> GRASSLAND
    int(Biome.SAVANNA),               # 10 TROP_DRY -> SAVANNA
    int(Biome.TROPICAL_DRY_FOREST),   # 11 TROP_RAINFOREST -> TROP_DRY
], dtype=np.uint8)


# Pre-computed NPP per-biome as float32 array, for vectorised food_capacity
# recomputation after a shift.
_NPP_BY_BIOME = np.array([_BIOME_NPP[Biome(i)] for i in range(12)],
                         dtype=np.float32)


# ---------------------------------------------------------------------------
# Sim state
# ---------------------------------------------------------------------------

@dataclass
class ClimateBiomeState:
    """Per-sim state of the climate-biome coupling."""
    anchor: GenesisAnchor
    anomaly_source: str = "linear_warming"
    warming_rate_c_per_year: float = 0.02
    temperature_jitter_amplitude: float = DEFAULT_JITTER_C
    transition_speed: float = 0.001

    baseline_temp_c: Dict[Tuple[int, int, int], float] = field(
        default_factory=dict)
    current_anomaly_c: Dict[Tuple[int, int, int], float] = field(
        default_factory=dict)
    chunk_biome_shifted: Dict[Tuple[int, int, int], int] = field(
        default_factory=dict)
    chunk_precip_proxy: Dict[Tuple[int, int, int], float] = field(
        default_factory=dict)

    global_anomaly_c: float = 0.0
    transitions_total: int = 0
    last_apply_tick: int = -1


# ---------------------------------------------------------------------------
# Helpers — macro sampling at chunk centre
# ---------------------------------------------------------------------------

def _sample_macro_at_chunk(anchor: GenesisAnchor,
                            coord: Tuple[int, int, int]) -> Dict[str, float]:
    """Bilinear macro sample at the centre of a chunk.

    Returns ``{'temp_c': ..., 'precip_mm': ..., 'biome': int}``.
    Coordinates outside the macro map clamp to the nearest border.
    """
    world = anchor.world
    p = world.params
    R = p.resolution
    cell_km = p.map_size_km / R
    cx, cy, _cz = coord
    chunk_center_x_m = (cx + 0.5) * CHUNK_SIDE_M
    chunk_center_y_m = (cy + 0.5) * CHUNK_SIDE_M
    x_km = chunk_center_x_m / 1000.0 + anchor.sim_origin_macro_km[0]
    y_km = chunk_center_y_m / 1000.0 + anchor.sim_origin_macro_km[1]
    fx = float(np.clip(x_km / cell_km - 0.5, 0.0, R - 1.001))
    fy = float(np.clip(y_km / cell_km - 0.5, 0.0, R - 1.001))
    ix = int(np.floor(fx)); iy = int(np.floor(fy))
    tx = fx - ix; ty = fy - iy

    def _bil(arr: np.ndarray) -> float:
        a = float(arr[iy, ix]); b = float(arr[iy, ix + 1])
        c = float(arr[iy + 1, ix]); d = float(arr[iy + 1, ix + 1])
        return (a * (1.0 - tx) * (1.0 - ty) + b * tx * (1.0 - ty)
                + c * (1.0 - tx) * ty + d * tx * ty)

    return {
        "temp_c": _bil(world.temp_c),
        "precip_mm": _bil(world.precip_mm),
        "biome": int(world.biome[iy, ix]),
    }


def _ensure_baseline(state: ClimateBiomeState,
                       coord: Tuple[int, int, int]) -> Tuple[float, float]:
    """Idempotently install a baseline (temp, precip) snapshot for ``coord``.

    Returns the ``(baseline_temp_c, precip_proxy_mm)`` pair after the call.
    """
    if coord not in state.baseline_temp_c:
        sample = _sample_macro_at_chunk(state.anchor, coord)
        state.baseline_temp_c[coord] = float(sample["temp_c"])
        state.chunk_precip_proxy[coord] = float(sample["precip_mm"])
    return (state.baseline_temp_c[coord],
            state.chunk_precip_proxy.get(coord, 800.0))


def _anomaly_for_tick(state: ClimateBiomeState, sim) -> float:
    """Global temperature anomaly (°C) at ``sim.tick``.

    For ``anomaly_source='linear_warming'``: ``warming_rate * sim_years``
    where ``sim_years = tick * drive_accel / SECONDS_PER_YEAR``.

    For ``anomaly_source='macro'``: read the current mean of the macro
    ``temp_c`` field on the anchor (static for now — placeholder so
    integrations with future dynamic-macro waves can substitute).
    """
    if state.anomaly_source == "linear_warming":
        accel = float(getattr(sim.cfg, "drive_accel", 1.0))
        sim_years = float(sim.tick) * accel / SECONDS_PER_YEAR
        return float(state.warming_rate_c_per_year * sim_years)
    elif state.anomaly_source == "macro":
        # Static anchor : current = baseline -> anomaly = 0. Hook to be
        # replaced when a dynamic-macro Wave ships.
        return 0.0
    else:
        return 0.0


# ---------------------------------------------------------------------------
# Vectorised biome shifting
# ---------------------------------------------------------------------------

def _shift_biomes_array(biome: np.ndarray, warming: bool,
                          precip_proxy_mm: float) -> np.ndarray:
    """Return the post-shift biome array using the precip-conditional
    transition matrix. Pure function, no RNG."""
    if warming:
        # Wet branch (>= 1500 mm) takes _WARMING_TO_WET ; dry branch
        # takes _WARMING_TO_DRY ; the only differing entries are
        # TEMPERATE_FOREST (4) and SAVANNA (9). For SAVANNA the dry
        # threshold is 500 mm not 1500 mm.
        if precip_proxy_mm < 500.0:
            # Both TEMPERATE_FOREST and SAVANNA go DRY.
            return _WARMING_TO_DRY[biome]
        elif precip_proxy_mm < 1500.0:
            # TEMPERATE_FOREST goes DRY (TROP_DRY_FOREST), SAVANNA goes
            # WET (TROP_DRY_FOREST).
            shift = _WARMING_TO_DRY[biome].copy()
            sav_mask = (biome == int(Biome.SAVANNA))
            shift[sav_mask] = _WARMING_TO_WET[biome[sav_mask]]
            return shift
        else:
            # Both go WET.
            return _WARMING_TO_WET[biome]
    else:
        return _COOLING[biome]


def _apply_shift_to_chunk(sim, state: ClimateBiomeState,
                            coord: Tuple[int, int, int],
                            chunk, anomaly_c: float) -> int:
    """Mutate ``chunk.biome`` and ``chunk.food_capacity`` in place. Return
    the number of cells whose biome was changed in this call."""
    if abs(anomaly_c) < ANOMALY_DEADBAND_C:
        return 0

    biome = chunk.biome  # uint8, shape (CHUNK_SIZE, CHUNK_SIZE)
    if biome.size == 0:
        return 0

    # Per-cell probability scales with |anomaly|, capped.
    amp = float(min(ANOMALY_PROB_MAX_MULT,
                     abs(anomaly_c) / max(ANOMALY_PROB_SCALE_C, 1e-6)))
    p_shift = float(np.clip(state.transition_speed * amp, 0.0, 1.0))

    # Deterministic RNG keyed by (seed, ['climate_biome','transition'],
    # [tick, cx, cy, cz]). One draw per cell — vectorised so the order of
    # consumption is fixed by numpy.
    cx, cy, cz = coord
    rng = prf_rng(int(sim.cfg.seed) & 0xFFFFFFFFFFFFFFFF,
                   ["climate_biome", "transition"],
                   [int(sim.tick), int(cx), int(cy), int(cz)])
    probs = rng.random(biome.shape, dtype=np.float32)
    shift_mask = probs < p_shift

    if not shift_mask.any():
        return 0

    warming = anomaly_c > 0.0
    precip_proxy = state.chunk_precip_proxy.get(coord, 800.0)
    target = _shift_biomes_array(biome, warming, precip_proxy)

    # Only cells where the target is different from current matter.
    changed_mask = shift_mask & (target != biome)
    n_shifted = int(changed_mask.sum())
    if n_shifted == 0:
        return 0

    new_biome = np.where(changed_mask, target, biome).astype(np.uint8)
    chunk.biome = new_biome

    # Recompute food_capacity from NPP (same convention as
    # engine.world.generate_chunk : npp * 500.0).
    npp = _NPP_BY_BIOME[new_biome]
    new_capacity = (npp * np.float32(500.0)).astype(np.float32)
    # Cap food_kcal at the new capacity so a shrinking biome can't carry
    # more than its new ceiling.
    if hasattr(chunk, "food_kcal"):
        chunk.food_kcal = np.minimum(chunk.food_kcal, new_capacity)
    chunk.food_capacity = new_capacity

    invalidate_resource_masks(chunk)

    return n_shifted


# ---------------------------------------------------------------------------
# Public API — install / step / state / uninstall
# ---------------------------------------------------------------------------

def install_climate_biome(sim,
                            anchor: GenesisAnchor,
                            *,
                            anomaly_source: str = "linear_warming",
                            warming_rate_c_per_year: float = 0.02,
                            temperature_jitter_amplitude: float = DEFAULT_JITTER_C,
                            transition_speed: float = 0.001,
                            ) -> ClimateBiomeState:
    """Idempotent installer.

    Snapshots ``baseline_temp_c`` for every cached chunk and monkey-patches
    :meth:`Simulation.step` so :func:`apply_climate_biome_step` runs after
    each tick.

    Calling install twice on the same sim is a no-op : the existing state
    is returned with its parameters updated (anchor, rates, source).
    """
    existing: Optional[ClimateBiomeState] = getattr(
        sim, "_climate_biome_state", None)
    if existing is not None:
        existing.anchor = anchor
        existing.anomaly_source = str(anomaly_source)
        existing.warming_rate_c_per_year = float(warming_rate_c_per_year)
        existing.temperature_jitter_amplitude = float(
            temperature_jitter_amplitude)
        existing.transition_speed = float(transition_speed)
        # Top up the baseline for any chunks that have entered cache since
        # the previous install (idempotent ; existing baselines kept).
        for coord in list(sim.streamer.cache.keys()):
            _ensure_baseline(existing, coord)
        return existing

    state = ClimateBiomeState(
        anchor=anchor,
        anomaly_source=str(anomaly_source),
        warming_rate_c_per_year=float(warming_rate_c_per_year),
        temperature_jitter_amplitude=float(temperature_jitter_amplitude),
        transition_speed=float(transition_speed),
    )
    sim._climate_biome_state = state

    # Snapshot baseline for every chunk already in the cache.
    for coord in list(sim.streamer.cache.keys()):
        _ensure_baseline(state, coord)

    # Monkey-patch sim.step ; store original on the sim for uninstall.
    if getattr(sim, "_climate_biome_orig_step", None) is None:
        orig_step = sim.step

        def _patched_step():
            stats = orig_step()
            st: Optional[ClimateBiomeState] = getattr(
                sim, "_climate_biome_state", None)
            if st is not None:
                apply_climate_biome_step(sim)
            return stats

        sim._climate_biome_orig_step = orig_step
        sim.step = _patched_step  # type: ignore[assignment]

    return state


def apply_climate_biome_step(sim) -> Dict[str, float]:
    """One tick of the climate-biome coupling.

    Recomputes the current anomaly, then for every chunk in
    ``sim.streamer.cache`` mutates ``chunk.biome`` + ``chunk.food_capacity``
    in place according to the per-cell shift probabilities.

    Returns a small dict ``{'cells_shifted_this_step', 'global_anomaly_c'}``
    useful for smoke / dashboard probes.
    """
    state: Optional[ClimateBiomeState] = getattr(
        sim, "_climate_biome_state", None)
    if state is None:
        return {"cells_shifted_this_step": 0, "global_anomaly_c": 0.0}

    global_dT = _anomaly_for_tick(state, sim)
    state.global_anomaly_c = float(global_dT)
    state.last_apply_tick = int(sim.tick)

    cells_shifted = 0
    jitter_amp = float(state.temperature_jitter_amplitude)

    for coord, chunk in list(sim.streamer.cache.items()):
        # Make sure we have a baseline for this chunk (may have been
        # streamed in since install).
        _ensure_baseline(state, coord)

        # Optional per-chunk jitter on the anomaly, deterministic via PRF.
        local_dT = global_dT
        if jitter_amp > 0.0:
            cx, cy, cz = coord
            jrng = prf_rng(int(sim.cfg.seed) & 0xFFFFFFFFFFFFFFFF,
                            ["climate_biome", "jitter"],
                            [int(sim.tick), int(cx), int(cy), int(cz)])
            local_dT = float(global_dT + jrng.uniform(-jitter_amp, jitter_amp))
        state.current_anomaly_c[coord] = float(local_dT)

        n = _apply_shift_to_chunk(sim, state, coord, chunk, local_dT)
        if n > 0:
            state.chunk_biome_shifted[coord] = (
                state.chunk_biome_shifted.get(coord, 0) + n)
            cells_shifted += n

    state.transitions_total += cells_shifted

    return {
        "cells_shifted_this_step": int(cells_shifted),
        "global_anomaly_c": float(global_dT),
    }


def climate_biome_state(sim) -> Dict[str, object]:
    """Diagnostic reporter."""
    state: Optional[ClimateBiomeState] = getattr(
        sim, "_climate_biome_state", None)
    if state is None:
        return {"installed": False}
    return {
        "installed": True,
        "anomaly_source": state.anomaly_source,
        "warming_rate_c_per_year": state.warming_rate_c_per_year,
        "transition_speed": state.transition_speed,
        "temperature_jitter_amplitude": state.temperature_jitter_amplitude,
        "global_anomaly_c": float(state.global_anomaly_c),
        "transitions_total": int(state.transitions_total),
        "chunks_tracked": int(len(state.baseline_temp_c)),
        "chunks_with_shifts": int(len(state.chunk_biome_shifted)),
        "last_apply_tick": int(state.last_apply_tick),
    }


def uninstall_climate_biome(sim) -> bool:
    """Detach the climate-biome overlay and restore ``sim.step``.

    Returns ``True`` if anything was uninstalled. Does **not** revert the
    biomes that were already shifted ; the world has aged.
    """
    state = getattr(sim, "_climate_biome_state", None)
    if state is None:
        return False
    orig = getattr(sim, "_climate_biome_orig_step", None)
    if orig is not None:
        sim.step = orig
        sim._climate_biome_orig_step = None
    del sim._climate_biome_state
    return True
