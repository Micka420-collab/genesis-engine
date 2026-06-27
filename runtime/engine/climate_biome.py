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
        for coord, chunk in list(sim.streamer.cache.items()):
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

Orographic coupling (live elevation -> chunk climate)
-----------------------------------------------------

On top of the global anomaly source, every install adds a per-chunk
*orographic* term that **reads** (never writes) the live macro
``elevation_m`` field and converts its drift from the install-time baseline
into a temperature anomaly at the environmental lapse rate
(``earth_laws.LAPSE_K_PER_M``). When tectonics / erosion mutate
``elevation_m`` in the disjoint ``autonomous_world`` loop, that change now
becomes visible on the agent-facing chunk path : uplift cools and migrates
biomes down the cooling ladder, erosion warms and migrates them up. The
term is identically 0 on a static world, so prior behaviour is unchanged.
Set ``orographic_coupling=False`` to opt out.

Orographic *precipitation* coupling (live elevation -> chunk rainfall)
---------------------------------------------------------------------

The precipitation partner of the lapse-rate temperature term, and the
``precip_mm`` half of AUDIT-DELTA-2026-06-23 backlog #7 ("recoupler
l'atmosphère -> temp_c/precip_mm"). Each chunk's ``precip_proxy`` — the
moisture that drives the warming ladder's dry/wet branch (desert vs forest)
— was frozen at its install-time macro snapshot, blind to the live relief.
Wave 65 makes it respond to the live ``elevation_m`` by **re-using the
macro worldgen orographic model verbatim** (``world_genesis.
_orographic_precipitation`` + ``_base_precip_by_latitude``, SSOT — the same
windward-uplift gain ``orographic_gain`` and lee-side ``rain_shadow_decay``
that baked ``world.precip_mm`` at generation): a rising range wrings extra
rain from the windward air column and casts a **rain shadow** on its lee,
while erosion relaxes both. The per-chunk anomaly is ``field(live_elev) -
field(baseline_elev)`` sampled at the chunk centre; it is identically 0 on
a static world (same elevation -> bit-identical field), reversible (always
re-derived from the frozen baseline, never compounding) and pure (no RNG,
no macro write). Set ``orographic_precip_coupling=False`` to opt out.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.earth_laws import LAPSE_K_PER_M
from engine.world import (CHUNK_SIDE_M, Biome, invalidate_resource_masks,
                          _BIOME_NPP)
from engine.world_genesis import (GenesisAnchor, _base_precip_by_latitude,
                                  _orographic_precipitation)


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

# --- Orographic (live-elevation) coupling ---------------------------------
# The chunk biome map responds to the *live* macro ``elevation_m`` field
# through the environmental lapse rate (SSOT ``earth_laws.LAPSE_K_PER_M`` =
# 6.5 K/km — the same value already baked into the macro baseline temperature
# in ``world_genesis`` so the coupling is self-consistent). When tectonics /
# erosion mutate ``anchor.world.elevation_m`` (``plate_tectonics_live``,
# ``novel_operators``), each chunk's effective temperature anomaly moves by
# ``-LAPSE_K_PER_M * Δelevation_m``: uplift cools (drives the cooling biome
# ladder), erosion/subsidence warms. This is the term that wires the
# otherwise-disjoint live macro mutation onto the agent-visible chunk path
# (closes the chunk-path half of D11). It is identically 0 while the macro
# elevation is unchanged, so static worlds keep their exact prior behaviour.

# --- Orographic (live-elevation) PRECIPITATION coupling -------------------
# The precipitation partner of the lapse-rate term above. No new tunables:
# the windward-uplift gain and lee-side rain-shadow decay are read from the
# world's own ``GenesisParams`` (``orographic_gain`` / ``rain_shadow_decay``)
# via the worldgen SSOT model ``world_genesis._orographic_precipitation`` —
# the exact code path that baked ``world.precip_mm`` at generation. The
# per-chunk precip proxy becomes ``baseline + (field(live_elev) -
# field(baseline_elev))`` sampled at the chunk centre, clamped at 0 mm.


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
    # Additive physical coupling: chunk temperature tracks the *live* macro
    # elevation through the lapse rate. On by default ; 0 on static worlds.
    orographic_coupling: bool = True
    # Precipitation partner: chunk precip proxy tracks the *live* macro relief
    # through the worldgen orographic model (windward gain / rain shadow).
    orographic_precip_coupling: bool = True
    # Sea level (m) for the orographic precip ocean mask (SSOT GenesisParams).
    sea_level_m: float = 0.0

    baseline_temp_c: Dict[Tuple[int, int, int], float] = field(
        default_factory=dict)
    baseline_elev_m: Dict[Tuple[int, int, int], float] = field(
        default_factory=dict)
    current_anomaly_c: Dict[Tuple[int, int, int], float] = field(
        default_factory=dict)
    chunk_biome_shifted: Dict[Tuple[int, int, int], int] = field(
        default_factory=dict)
    # Install-time per-chunk precip snapshot (the *baseline*, never mutated).
    chunk_precip_proxy: Dict[Tuple[int, int, int], float] = field(
        default_factory=dict)
    # Effective per-chunk precip actually fed to the biome ladder this tick
    # (= baseline + orographic anomaly). Diagnostics + downstream consumers.
    current_precip_proxy: Dict[Tuple[int, int, int], float] = field(
        default_factory=dict)

    # Full-field macro baselines for the orographic precip recompute (read-only
    # snapshots taken at install, before any tectonic mutation).
    base_elev_field: Optional[np.ndarray] = None
    base_precip_field: Optional[np.ndarray] = None   # field(base_elev), cached
    belt_precip_field: Optional[np.ndarray] = None   # latitudinal belt, cached

    global_anomaly_c: float = 0.0
    orographic_anomaly_c: float = 0.0
    orographic_precip_anomaly_mm: float = 0.0
    transitions_total: int = 0
    last_apply_tick: int = -1


# ---------------------------------------------------------------------------
# Helpers — macro sampling at chunk centre
# ---------------------------------------------------------------------------

def _chunk_frac_index(anchor: GenesisAnchor,
                      coord: Tuple[int, int, int]
                      ) -> Tuple[int, int, float, float]:
    """Fractional macro-grid index ``(ix, iy, tx, ty)`` at a chunk centre.

    Clamped to the macro map (coordinates outside it snap to the nearest
    border). Shared by every bilinear sampler below.
    """
    world = anchor.world
    p = world.params
    R = p.resolution
    cell_km = p.map_size_km / R
    cx, cy, _cz = coord
    x_km = (cx + 0.5) * CHUNK_SIDE_M / 1000.0 + anchor.sim_origin_macro_km[0]
    y_km = (cy + 0.5) * CHUNK_SIDE_M / 1000.0 + anchor.sim_origin_macro_km[1]
    fx = float(np.clip(x_km / cell_km - 0.5, 0.0, R - 1.001))
    fy = float(np.clip(y_km / cell_km - 0.5, 0.0, R - 1.001))
    ix = int(np.floor(fx))
    iy = int(np.floor(fy))
    return ix, iy, fx - ix, fy - iy


def _bilinear_at(arr: np.ndarray, ix: int, iy: int,
                 tx: float, ty: float) -> float:
    """Bilinear interpolation of ``arr`` at fractional index ``(ix+tx, iy+ty)``."""
    a = float(arr[iy, ix])
    b = float(arr[iy, ix + 1])
    c = float(arr[iy + 1, ix])
    d = float(arr[iy + 1, ix + 1])
    return (a * (1.0 - tx) * (1.0 - ty) + b * tx * (1.0 - ty)
            + c * (1.0 - tx) * ty + d * tx * ty)


def _sample_macro_at_chunk(anchor: GenesisAnchor,
                            coord: Tuple[int, int, int]) -> Dict[str, float]:
    """Bilinear macro sample at the centre of a chunk.

    Returns ``{'temp_c': ..., 'precip_mm': ..., 'elevation_m': ..., 'biome': int}``.
    Coordinates outside the macro map clamp to the nearest border.
    """
    world = anchor.world
    ix, iy, tx, ty = _chunk_frac_index(anchor, coord)
    return {
        "temp_c": _bilinear_at(world.temp_c, ix, iy, tx, ty),
        "precip_mm": _bilinear_at(world.precip_mm, ix, iy, tx, ty),
        "elevation_m": _bilinear_at(world.elevation_m, ix, iy, tx, ty),
        "biome": int(world.biome[iy, ix]),
    }


def _sample_field_at_chunk(anchor: GenesisAnchor,
                           coord: Tuple[int, int, int],
                           arr: np.ndarray) -> float:
    """Bilinear sample of an arbitrary ``(R, R)`` macro field at a chunk centre."""
    ix, iy, tx, ty = _chunk_frac_index(anchor, coord)
    return _bilinear_at(arr, ix, iy, tx, ty)


def _ensure_baseline(state: ClimateBiomeState,
                       coord: Tuple[int, int, int]) -> Tuple[float, float]:
    """Idempotently install a baseline (temp, precip) snapshot for ``coord``.

    Returns the ``(baseline_temp_c, precip_proxy_mm)`` pair after the call.
    """
    if coord not in state.baseline_temp_c:
        sample = _sample_macro_at_chunk(state.anchor, coord)
        state.baseline_temp_c[coord] = float(sample["temp_c"])
        state.chunk_precip_proxy[coord] = float(sample["precip_mm"])
        state.baseline_elev_m[coord] = float(sample["elevation_m"])
    return (state.baseline_temp_c[coord],
            state.chunk_precip_proxy.get(coord, 800.0))


def _orographic_anomaly_for_chunk(state: ClimateBiomeState,
                                   coord: Tuple[int, int, int]) -> float:
    """Lapse-rate temperature anomaly (°C) from the *live* macro elevation.

    Re-samples ``anchor.world.elevation_m`` at the chunk centre (the world
    object is read live, so tectonic/erosion mutations are seen) and compares
    it to the baseline elevation captured at install. Returns
    ``-LAPSE_K_PER_M * (current - baseline)`` : uplift → negative (cooling),
    erosion/subsidence → positive (warming). Returns ``0.0`` when no baseline
    exists yet or the elevation is unchanged. Pure / deterministic — no RNG.
    """
    base = state.baseline_elev_m.get(coord)
    if base is None:
        return 0.0
    cur = float(_sample_macro_at_chunk(state.anchor, coord)["elevation_m"])
    # Lapse applies only above sea level (consistent with the macro baseline
    # temperature in world_genesis, which uses max(elev, 0) / 1000). Elevation
    # excursions below 0 m (submerged land) carry no extra lapse anomaly.
    return float(-LAPSE_K_PER_M * (max(cur, 0.0) - max(base, 0.0)))


# ---------------------------------------------------------------------------
# Helpers — orographic precipitation (live elevation -> rainfall field)
# ---------------------------------------------------------------------------

def _belt_precip(state: ClimateBiomeState) -> np.ndarray:
    """Latitudinal precipitation belt (mm/yr), cached. Wind and latitude do
    not move with relief, so the belt is the install-time SSOT value."""
    if state.belt_precip_field is None:
        world = state.anchor.world
        state.belt_precip_field = _base_precip_by_latitude(
            world.params, world.latitude_deg)
    return state.belt_precip_field


def _orographic_precip_field(state: ClimateBiomeState,
                             elev_m: np.ndarray) -> np.ndarray:
    """Full macro precipitation field (mm/yr) for a given elevation, all else
    baseline. Re-uses the worldgen orographic model verbatim (SSOT) so a
    recompute at the baseline elevation reproduces ``world.precip_mm`` exactly.
    Pure / deterministic — no RNG."""
    world = state.anchor.world
    return _orographic_precipitation(
        world.params, np.asarray(elev_m, dtype=np.float32), _belt_precip(state),
        world.wind_u, world.wind_v, state.sea_level_m)


def _baseline_precip_field(state: ClimateBiomeState) -> np.ndarray:
    """``P0``: orographic precip at the install-time elevation, cached."""
    if state.base_precip_field is None:
        state.base_precip_field = _orographic_precip_field(
            state, state.base_elev_field)
    return state.base_precip_field


def _ensure_elev_baseline(state: ClimateBiomeState) -> None:
    """Idempotently snapshot the full macro elevation field + sea level. Set at
    install (before any mutation) ; this is only a fallback for states built
    before the precip coupling existed."""
    if state.base_elev_field is None:
        world = state.anchor.world
        state.base_elev_field = np.asarray(
            world.elevation_m, dtype=np.float32).copy()
        state.sea_level_m = float(world.params.sea_level_m)


def _anomaly_for_tick(state: ClimateBiomeState, sim) -> float:
    """Global temperature anomaly (°C) at ``sim.tick``.

    For ``anomaly_source='linear_warming'``: ``warming_rate * sim_years``
    where ``sim_years = tick * drive_accel / SECONDS_PER_YEAR``.

    This returns only the *global* (spatially-uniform) component. The live,
    spatially-varying physical signal is the per-chunk orographic term
    (:func:`_orographic_anomaly_for_chunk`, added in the apply loop).

    For ``anomaly_source='macro'``: there is no synthetic global trend — the
    world's climate is driven purely by the live macro state via the
    orographic coupling, so the global component is 0.
    """
    if state.anomaly_source == "linear_warming":
        accel = float(getattr(sim.cfg, "drive_accel", 1.0))
        sim_years = float(sim.tick) * accel / SECONDS_PER_YEAR
        return float(state.warming_rate_c_per_year * sim_years)
    elif state.anomaly_source == "macro":
        # No synthetic global trend ; the real (spatially-varying) signal is
        # supplied per-chunk by the orographic coupling from live elevation.
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
                            chunk, anomaly_c: float,
                            precip_proxy: float) -> int:
    """Mutate ``chunk.biome`` and ``chunk.food_capacity`` in place. Return
    the number of cells whose biome was changed in this call. ``precip_proxy``
    is the *effective* (live, orographically-coupled) rainfall fed to the
    warming dry/wet branch."""
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
    target = _shift_biomes_array(biome, warming, float(precip_proxy))

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
                            orographic_coupling: bool = True,
                            orographic_precip_coupling: bool = True,
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
        existing.orographic_coupling = bool(orographic_coupling)
        existing.orographic_precip_coupling = bool(orographic_precip_coupling)
        _ensure_elev_baseline(existing)
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
        orographic_coupling=bool(orographic_coupling),
        orographic_precip_coupling=bool(orographic_precip_coupling),
    )
    sim._climate_biome_state = state

    # Snapshot the full macro elevation field NOW (before any tectonic mutation)
    # so the orographic precip anomaly is measured against the pristine relief.
    _ensure_elev_baseline(state)

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
    max_oro = 0.0
    max_dp = 0.0

    # Live orographic precipitation: recompute the full macro rainfall field for
    # the current relief and diff it against the install-time baseline. Computed
    # once per tick (not per chunk) and only when the elevation has actually
    # moved — on a static world ``precip_delta`` stays None and every chunk keeps
    # its frozen baseline precip (exact back-compat).
    precip_delta: Optional[np.ndarray] = None
    if state.orographic_precip_coupling:
        _ensure_elev_baseline(state)
        live_elev = np.asarray(state.anchor.world.elevation_m, dtype=np.float32)
        if (state.base_elev_field is not None
                and not np.array_equal(live_elev, state.base_elev_field)):
            precip_delta = (_orographic_precip_field(state, live_elev)
                            - _baseline_precip_field(state))

    for coord, chunk in list(sim.streamer.cache.items()):
        # Make sure we have a baseline for this chunk (may have been
        # streamed in since install).
        _ensure_baseline(state, coord)

        local_dT = global_dT

        # Additive physical coupling: per-chunk lapse-rate response to the
        # live macro elevation (0 while elevation is unchanged).
        if state.orographic_coupling:
            oro = _orographic_anomaly_for_chunk(state, coord)
            local_dT += oro
            if abs(oro) > abs(max_oro):
                max_oro = oro

        # Optional per-chunk jitter on the anomaly, deterministic via PRF.
        if jitter_amp > 0.0:
            cx, cy, cz = coord
            jrng = prf_rng(int(sim.cfg.seed) & 0xFFFFFFFFFFFFFFFF,
                            ["climate_biome", "jitter"],
                            [int(sim.tick), int(cx), int(cy), int(cz)])
            local_dT = float(local_dT + jrng.uniform(-jitter_amp, jitter_amp))
        state.current_anomaly_c[coord] = float(local_dT)

        # Effective rainfall fed to the warming dry/wet branch: frozen baseline
        # plus the live orographic anomaly (windward gain / rain shadow),
        # clamped at 0 mm. Equals the baseline exactly when relief is unchanged.
        base_precip = state.chunk_precip_proxy.get(coord, 800.0)
        eff_precip = base_precip
        if precip_delta is not None:
            dp = _sample_field_at_chunk(state.anchor, coord, precip_delta)
            eff_precip = max(0.0, base_precip + dp)
            if abs(dp) > abs(max_dp):
                max_dp = float(dp)
        state.current_precip_proxy[coord] = float(eff_precip)

        n = _apply_shift_to_chunk(sim, state, coord, chunk, local_dT, eff_precip)
        if n > 0:
            state.chunk_biome_shifted[coord] = (
                state.chunk_biome_shifted.get(coord, 0) + n)
            cells_shifted += n

    state.transitions_total += cells_shifted
    state.orographic_anomaly_c = float(max_oro)
    state.orographic_precip_anomaly_mm = float(max_dp)

    return {
        "cells_shifted_this_step": int(cells_shifted),
        "global_anomaly_c": float(global_dT),
        "orographic_anomaly_c": float(max_oro),
        "orographic_precip_anomaly_mm": float(max_dp),
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
        "orographic_coupling": bool(state.orographic_coupling),
        "orographic_precip_coupling": bool(state.orographic_precip_coupling),
        "global_anomaly_c": float(state.global_anomaly_c),
        "orographic_anomaly_c": float(state.orographic_anomaly_c),
        "orographic_precip_anomaly_mm": float(state.orographic_precip_anomaly_mm),
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
