"""Genesis Engine — Wave 4 photosynthesis (Farquhar-von Caemmerer-Berry).

Scientifically calibrated leaf-level CO2 assimilation model integrated
over a chunk's cells to drive chunk.food_capacity dynamically.

The literature standard for terrestrial GPP is the Farquhar–von
Caemmerer–Berry (FvCB, 1980) C3 model, with the Collatz et al. (1992)
C4 extension, and a simplified CAM approximation for succulents.

Three plant-functional types
----------------------------
* **C3** — most temperate vegetation, all broadleaf trees, wheat, rice.
  Rubisco fixes CO2 directly. Photorespiration losses near the
  CO2-compensation point Γ*. Limited by light or by Rubisco.
* **C4** — savanna grasses, maize, sugarcane, sorghum. A PEP-carboxylase
  concentrating mechanism nearly eliminates photorespiration, so
  assimilation saturates with respect to CO2 (above ~150 ppm), is
  light-saturated only above ~1500 μmol/m²/s PAR, and is more efficient
  at high temperature. Lower V_cmax but higher quantum yield.
* **CAM** — cacti, agaves. Nocturnal CO2 fixation; very low daytime
  assimilation. Modelled here as a constant-low rate with strong
  water-use efficiency (so CAM dominates in deserts).

Biome → pathway mole-fraction table is derived from published global
ecosystem surveys (Sage 2004, Still 2003) — see ``BIOME_PATHWAY_MIX``.

Per-cell instantaneous CO2 assimilation::

    A_cell_umol_m2_s = sum( frac_pathway × A_pathway(C_i, PAR, T, water) )

Then converted to ``kcal/cell/tick``::

    1 μmol CO2 / m² / s
      × 0.25 m² / cell             (VOXEL_SIZE_M = 0.5 m)
      × 1e-6 × 30 g glucose / mol  (CO2 → glucose at 12 g C → 30 g sugar)
      × 4 kcal / g glucose          (food calorie convention)
      × TICK_DT_S
      × drive_accel

Determinism
-----------
No RNG inside the module — every per-tick computation is a pure
numpy function of the chunk's deterministic fields plus the atmosphere
state. Bit-identical for identical (chunk, atm, weather) tuples.

Taxonomy tags (ADR 0005)
------------------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — biology shaping food
availability shaping civilisations.
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — physically-grounded
multi-step rollout (Rubisco kinetics, light-CO2 saturation, water
stress) respecting Farquhar's laws.
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"  # arxiv 2604.22748

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Optional, Tuple

import numpy as np

from engine.core import TICK_DT_S
from engine.world import (Biome, CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M,
                          invalidate_resource_masks)


# ---------------------------------------------------------------------------
# Pathway constants
# ---------------------------------------------------------------------------

class Pathway(IntEnum):
    C3 = 0
    C4 = 1
    CAM = 2


# Biome → (C3, C4, CAM) mole-fraction mix.
# References:
#   Sage RF (2004). The evolution of C4 photosynthesis. New Phytologist.
#   Still CJ et al. (2003). Global distribution of C3 and C4 vegetation.
# Tables are intentionally coarse but anchored on global vegetation
# surveys; sum to ~1.0 per biome (deserts are partially non-vegetated).
BIOME_PATHWAY_MIX: Dict[int, Tuple[float, float, float]] = {
    int(Biome.OCEAN):              (1.00, 0.00, 0.00),  # phytoplankton (C3-like) — Wave 5 marine
    int(Biome.ICE):                (0.00, 0.00, 0.00),
    int(Biome.TUNDRA):             (0.98, 0.02, 0.00),
    int(Biome.BOREAL_FOREST):      (1.00, 0.00, 0.00),
    int(Biome.TEMPERATE_FOREST):   (1.00, 0.00, 0.00),
    int(Biome.TEMPERATE_RAINFOREST):(1.00, 0.00, 0.00),
    int(Biome.GRASSLAND):          (0.45, 0.55, 0.00),  # tallgrass C4 + temperate C3
    int(Biome.HOT_DESERT):         (0.10, 0.35, 0.55),  # CAM-dominated
    int(Biome.COLD_DESERT):        (0.85, 0.10, 0.05),
    int(Biome.SAVANNA):            (0.10, 0.90, 0.00),
    int(Biome.TROPICAL_DRY_FOREST):(0.60, 0.40, 0.00),
    int(Biome.TROPICAL_RAINFOREST):(1.00, 0.00, 0.00),
}


# C3 — Farquhar–von Caemmerer–Berry parameters at 25 °C (Sharkey 2007 ranges).
V_CMAX_C3_25 = 60.0        # μmol CO2 / m² / s
K_C_25 = 404.0             # ppm; Michaelis constant for Rubisco carboxylation
K_O_25 = 278.0e3           # ppm O2; Michaelis for oxygenation
O_PPM = 210000.0           # atmospheric O2 ≈ 21 %
GAMMA_STAR_25 = 42.0       # ppm; CO2 compensation point in absence of mit. resp.
R_D_C3_25 = 1.5            # μmol/m²/s; dark respiration
ALPHA_C3 = 0.24            # mol e- / mol photons (Berry 1989)

# Activation energies (J/mol) — Bernacchi et al 2001
E_A_VCMAX = 65330.0
E_A_KC = 79430.0
E_A_KO = 36380.0
E_A_GAMMA = 37830.0
E_A_RD = 46390.0
R_GAS = 8.314462618        # J / (mol K)

# C4 — Collatz et al 1992 parameters
V_CMAX_C4_25 = 40.0
K_CO2_C4 = 250.0           # PEP carboxylase Michaelis (ppm)
R_D_C4_25 = 1.0
ALPHA_C4 = 0.067           # mol CO2 / mol photons (effective quantum yield)

# CAM — calibrated low: nocturnal fixation only, small daytime contribution.
V_CMAX_CAM_25 = 8.0
R_D_CAM_25 = 0.4
ALPHA_CAM = 0.04

# Stomatal conductance proxy : Ci / Ca ratio when water non-limiting.
CI_CA_RATIO_C3 = 0.70
CI_CA_RATIO_C4 = 0.40

# Water stress : full GPP when water_avail_factor >= 1.0, linear to 0 at 0.0.
# water_avail_factor combines local chunk.water > threshold and weather rain.

# Conversion : 1 μmol CO2 / m² / s × CELL_AREA × g_per_mol × kcal_per_g.
CELL_AREA_M2 = VOXEL_SIZE_M * VOXEL_SIZE_M
# Mass conservation : 6 CO2 + 6 H2O -> C6H12O6 + 6 O2. So 1 mol CO2 -> 1/6 mol
# glucose = 30 g glucose. Glucose energy: 3.74 kcal/g (Atwater factor).
G_GLUCOSE_PER_MOL_CO2 = 30.0
KCAL_PER_G_GLUCOSE = 3.74


# ---------------------------------------------------------------------------
# Temperature scaling (Arrhenius for activation, peaked at optimum)
# ---------------------------------------------------------------------------

def _arrhenius(value_25: float, ea_j: float, T_K: float) -> float:
    """Arrhenius scaling from 25 °C to T_K."""
    T_REF = 298.15
    return value_25 * np.exp(ea_j * (T_K - T_REF) / (R_GAS * T_REF * T_K))


def _temp_factor_c3(T_C: float) -> float:
    """C3 temperature response (Sharkey 2007 envelope).

    Wide curve : boreal C3 (spruce, etc.) maintains net positive A from
    ~0 °C up to ~40 °C. Optimum 22 °C, half-max at 2 °C and 42 °C, zero
    below -8 °C and above 52 °C.
    """
    if T_C < -8.0 or T_C > 52.0:
        return 0.0
    return max(0.0, 1.0 - ((T_C - 22.0) / 30.0) ** 2)


def _temp_factor_c4(T_C: float) -> float:
    """C4 optimum 30 °C, net positive 5-55 °C."""
    if T_C < 5.0 or T_C > 55.0:
        return 0.0
    return max(0.0, 1.0 - ((T_C - 30.0) / 25.0) ** 2)


def _temp_factor_cam(T_C: float) -> float:
    """CAM optimum 28 °C, slow at frost, tolerant of heat."""
    if T_C < 5.0 or T_C > 55.0:
        return 0.0
    return max(0.0, 1.0 - ((T_C - 28.0) / 25.0) ** 2)


# ---------------------------------------------------------------------------
# Leaf-level assimilation (returns μmol CO2 / m² / s — leaf cross-section)
# ---------------------------------------------------------------------------

def assimilation_c3(Ca_ppm: float, par_umol_m2_s: float,
                    T_C: float, water_factor: float) -> float:
    """Farquhar-von Caemmerer-Berry net assimilation rate for C3 leaves.

    Args:
        Ca_ppm: ambient CO2 concentration (ppm).
        par_umol_m2_s: photosynthetically active radiation (μmol photons/m²/s).
        T_C: leaf temperature (°C).
        water_factor: 0..1, 1 = unstressed.

    Returns:
        Net rate in μmol CO2 / m² / s (may be slightly negative at night).
    """
    T_K = float(T_C) + 273.15
    if water_factor <= 0.0:
        return -R_D_C3_25 * _temp_factor_c3(T_C)
    tfact = _temp_factor_c3(T_C)
    if tfact <= 0.0:
        return 0.0
    vcmax = _arrhenius(V_CMAX_C3_25, E_A_VCMAX, T_K) * tfact
    kc = _arrhenius(K_C_25, E_A_KC, T_K)
    ko = _arrhenius(K_O_25, E_A_KO, T_K)
    gamma = _arrhenius(GAMMA_STAR_25, E_A_GAMMA, T_K)
    rd = _arrhenius(R_D_C3_25, E_A_RD, T_K)

    # Stomatal conductance proxy.
    Ci = max(gamma, CI_CA_RATIO_C3 * Ca_ppm * (0.4 + 0.6 * water_factor))

    # Rubisco-limited (Ac).
    Ac = vcmax * (Ci - gamma) / (Ci + kc * (1.0 + O_PPM / ko))
    # Electron-transport limited (Aj).
    J = ALPHA_C3 * par_umol_m2_s
    Aj = J * (Ci - gamma) / (4.0 * Ci + 8.0 * gamma)
    return float(min(Ac, Aj) - rd)


def assimilation_c4(Ca_ppm: float, par_umol_m2_s: float,
                    T_C: float, water_factor: float) -> float:
    """Collatz C4 simplified."""
    if water_factor <= 0.0:
        return -R_D_C4_25 * _temp_factor_c4(T_C)
    tfact = _temp_factor_c4(T_C)
    if tfact <= 0.0:
        return 0.0
    vcmax = V_CMAX_C4_25 * tfact
    Ci = max(0.0, CI_CA_RATIO_C4 * Ca_ppm * (0.4 + 0.6 * water_factor))
    # CO2 limited by PEP carboxylase.
    Ac = vcmax * Ci / (Ci + K_CO2_C4)
    # Light limited.
    Aj = ALPHA_C4 * par_umol_m2_s
    return float(min(Ac, Aj) - R_D_C4_25)


def assimilation_cam(Ca_ppm: float, par_umol_m2_s: float,
                     T_C: float, water_factor: float) -> float:
    """Highly simplified CAM — small constant daytime + water-tolerant."""
    if water_factor < 0.0:
        return 0.0
    tfact = _temp_factor_cam(T_C)
    if tfact <= 0.0:
        return 0.0
    vcmax = V_CMAX_CAM_25 * tfact
    light_term = ALPHA_CAM * par_umol_m2_s
    return float(min(vcmax, light_term) * max(0.3, water_factor) - R_D_CAM_25)


# ---------------------------------------------------------------------------
# Chunk-level GPP integration
# ---------------------------------------------------------------------------

def _par_from_weather(weather) -> float:
    """Estimate PAR (μmol photons / m² / s) at canopy top.

    Direct-beam plus diffuse. ``weather.cloud`` in [0, 1]. Noon peak
    ~2000 μmol/m²/s clear; ~400 μmol/m²/s overcast.
    """
    is_day = bool(getattr(weather, "is_day", True))
    if not is_day:
        return 0.0
    cloud = float(getattr(weather, "cloud", 0.5))
    return float(1800.0 * (1.0 - 0.6 * cloud) + 200.0 * cloud)


def _water_factor_for_chunk(chunk) -> np.ndarray:
    """Per-cell stomatal water factor in [0, 1].

    Plants close stomata when local water reserve is low. Calibration :
    cells with water >= 50 L are unstressed (factor = 1) ; cells with
    water == 0 are dormant (factor = 0) ; linear in between.
    """
    return np.clip(chunk.water.astype(np.float32) / 50.0, 0.0, 1.0)


@dataclass
class ChunkGppCache:
    """Memo of the last per-cell GPP rate computed for a chunk.

    Updated every photosynthesis tick. Consumed by visualisation
    (NDVI overlay) and by the food_capacity adjustment path.
    """
    last_gpp_umol: np.ndarray = field(default=None)   # μmol CO2 / m² / s per cell
    last_kcal_per_tick: np.ndarray = field(default=None)  # kcal/cell/tick


def compute_chunk_gpp(
    chunk,
    weather,
    Ca_ppm: float,
    drive_accel: float,
) -> ChunkGppCache:
    """Return per-cell instantaneous GPP for ``chunk``.

    The function is pure : no chunk mutation, no RNG. Cache returned
    for the caller to attach / store / consume.
    """
    par = _par_from_weather(weather)
    T_C = float(getattr(weather, "temp_c", 15.0))
    water_factor = _water_factor_for_chunk(chunk)  # per-cell (CHUNK_SIZE,CHUNK_SIZE)

    biome = chunk.biome.astype(np.int32)
    gpp = np.zeros_like(chunk.food_kcal, dtype=np.float32)

    # Scalar-per-pathway leaf rates (μmol/m²/s) at this temperature & PAR.
    # We use a single chunk-wide water factor mean for the leaf rate
    # estimate (per-cell stomatal stress applies multiplicatively below).
    wf_mean = float(water_factor.mean()) if water_factor.size else 0.0
    a_c3 = max(0.0, assimilation_c3(Ca_ppm, par, T_C, wf_mean))
    a_c4 = max(0.0, assimilation_c4(Ca_ppm, par, T_C, wf_mean))
    a_cam = max(0.0, assimilation_cam(Ca_ppm, par, T_C, wf_mean))

    # Build a (CHUNK_SIZE, CHUNK_SIZE) field by indexing the biome mix.
    for b_int, mix in BIOME_PATHWAY_MIX.items():
        m = biome == b_int
        if not m.any():
            continue
        c3, c4, cam = mix
        leaf_rate = c3 * a_c3 + c4 * a_c4 + cam * a_cam
        gpp[m] = leaf_rate

    # Apply per-cell water multiplier.
    gpp *= water_factor

    # Convert to kcal/cell/tick.
    kcal_per_s_per_cell = (
        gpp * CELL_AREA_M2 * 1e-6  # mol/s/cell
        * G_GLUCOSE_PER_MOL_CO2     # g glucose / s / cell
        * KCAL_PER_G_GLUCOSE        # kcal / s / cell
    )
    kcal_per_tick = kcal_per_s_per_cell * TICK_DT_S * drive_accel

    return ChunkGppCache(last_gpp_umol=gpp, last_kcal_per_tick=kcal_per_tick)


# ---------------------------------------------------------------------------
# Per-sim install + tick
# ---------------------------------------------------------------------------

@dataclass
class PhotosynthesisState:
    """Global state attached to ``sim`` by install_photosynthesis."""
    chunk_caches: Dict[Tuple[int, int, int], ChunkGppCache] = field(default_factory=dict)
    last_global_gpp_kcal_per_tick: float = 0.0
    last_per_biome_gpp: Dict[int, float] = field(default_factory=dict)
    last_par: float = 0.0
    last_temp_c: float = 15.0
    last_ca_ppm: float = 280.0
    ticks_run: int = 0


def _resolve_atmosphere(sim):
    """Return the live Atmosphere instance attached to sim or None."""
    atm = getattr(sim, "_ecology_atmosphere", None)
    if atm is not None:
        return atm
    # Try realism/ecology attribute conventions.
    eco = getattr(sim, "ecology", None)
    if eco is not None and hasattr(eco, "atmosphere"):
        return eco.atmosphere
    return None


def _resolve_weather(sim):
    """Best-effort weather sample (chunk-mean temperature + cloud)."""
    try:
        from engine.world import weather_at
        # Sample one centre-ish point so we have day/temp/precip.
        return weather_at(sim.tick * int(sim.cfg.drive_accel), 15.0, 1.0)
    except Exception:
        # Minimal fallback weather.
        @dataclass
        class _W:
            temp_c: float = 15.0
            rain_mm_h: float = 1.0
            cloud: float = 0.5
            is_day: bool = True
        return _W()


def tick_photosynthesis(sim, state: PhotosynthesisState) -> None:
    """Run one tick of photosynthesis over every cached chunk.

    Updates ``chunk.food_kcal`` toward ``chunk.food_capacity`` at a rate
    proportional to the locally computed GPP, replacing the legacy
    fixed-rate regeneration. Invalidates the resource mask cache for
    every chunk we touch so cognition sees the new state.
    """
    atm = _resolve_atmosphere(sim)
    Ca_ppm = float(getattr(atm, "co2_ppm", 280.0)) if atm else 280.0
    weather = _resolve_weather(sim)
    drive_accel = float(sim.cfg.drive_accel)

    global_kcal = 0.0
    per_biome: Dict[int, float] = {}
    cache_store = state.chunk_caches

    cache_iter = sim.streamer.cache
    # In some sim builds the cache is a dict-like; iterate via .items().
    for coord, chunk in list(cache_iter.items()):
        gpp_cache = compute_chunk_gpp(chunk, weather, Ca_ppm, drive_accel)
        cache_store[coord] = gpp_cache
        # Inject the locally produced kcal into food_kcal, clipped at
        # food_capacity so we don't overshoot the chunk's local biome
        # carrying capacity.
        new_food = chunk.food_kcal + gpp_cache.last_kcal_per_tick
        np.minimum(new_food, chunk.food_capacity, out=new_food)
        chunk.food_kcal[:] = new_food
        invalidate_resource_masks(chunk)
        # Aggregate stats.
        produced = float(gpp_cache.last_kcal_per_tick.sum())
        global_kcal += produced
        # Per-biome aggregation : use the dominant biome of the chunk.
        biomes, counts = np.unique(chunk.biome, return_counts=True)
        dominant = int(biomes[np.argmax(counts)])
        per_biome[dominant] = per_biome.get(dominant, 0.0) + produced

    state.last_global_gpp_kcal_per_tick = global_kcal
    state.last_per_biome_gpp = per_biome
    state.last_par = _par_from_weather(weather)
    state.last_temp_c = float(getattr(weather, "temp_c", 15.0))
    state.last_ca_ppm = Ca_ppm
    state.ticks_run += 1


def install_photosynthesis(sim) -> PhotosynthesisState:
    """Idempotent installer. Wraps sim.step with a photosynthesis sub-tick.

    Returns the live PhotosynthesisState so callers (smoke / endpoint)
    can poll global GPP and per-biome aggregates.
    """
    state: Optional[PhotosynthesisState] = getattr(sim, "_photo_state", None)
    if state is not None:
        return state
    state = PhotosynthesisState()
    sim._photo_state = state
    orig_step = sim.step

    def wrapped_step():
        orig_step()
        tick_photosynthesis(sim, state)

    sim.step = wrapped_step
    return state


def photosynthesis_state(sim) -> Dict[str, object]:
    """Snapshot consumed by ``/api/photosynthesis_state``."""
    state: Optional[PhotosynthesisState] = getattr(sim, "_photo_state", None)
    if state is None:
        return {}
    # Map biome ids to readable names for the endpoint.
    biome_name = {int(b): b.name for b in Biome}
    per_biome_named = {biome_name.get(b, str(b)): round(v, 6)
                       for b, v in state.last_per_biome_gpp.items()}
    return {
        "global_gpp_kcal_per_tick": round(state.last_global_gpp_kcal_per_tick, 4),
        "global_gpp_kcal_per_hour_real": round(
            state.last_global_gpp_kcal_per_tick * 3600.0
            / max(1.0, float(sim.cfg.drive_accel)), 4),
        "per_biome_kcal_per_tick": per_biome_named,
        "Ca_ppm": round(state.last_ca_ppm, 2),
        "PAR_umol_m2_s": round(state.last_par, 2),
        "temp_c": round(state.last_temp_c, 2),
        "ticks_run": int(state.ticks_run),
        "chunks_tracked": len(state.chunk_caches),
    }


# ---------------------------------------------------------------------------
# Persistence — P1 save / load round-trip support
# ---------------------------------------------------------------------------

def save_photo_state(sim, target_dir: str) -> bool:
    """Persist :class:`PhotosynthesisState` to ``target_dir/photosynthesis.json``.

    Only the scalar summary + counters are written. The per-chunk
    ``last_gpp_umol`` rasters are *not* serialised — they regenerate
    deterministically from the first ``tick_photosynthesis`` call after
    load (weather + atmosphere + chunk biome are all restored already).
    """
    import json, os
    state: Optional[PhotosynthesisState] = getattr(sim, "_photo_state", None)
    if state is None:
        return False
    payload = {
        "last_global_gpp_kcal_per_tick":
            float(state.last_global_gpp_kcal_per_tick),
        "last_per_biome_gpp": {int(k): float(v)
                               for k, v in state.last_per_biome_gpp.items()},
        "last_par": float(state.last_par),
        "last_temp_c": float(state.last_temp_c),
        "last_ca_ppm": float(state.last_ca_ppm),
        "ticks_run": int(state.ticks_run),
    }
    with open(os.path.join(target_dir, "photosynthesis.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return True


def load_photo_state(sim, target_dir: str) -> bool:
    """Reinstate :class:`PhotosynthesisState` scalars. Installs if missing."""
    import json, os
    path = os.path.join(target_dir, "photosynthesis.json")
    if not os.path.isfile(path):
        return False
    state = install_photosynthesis(sim)
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state.last_global_gpp_kcal_per_tick = float(
        payload.get("last_global_gpp_kcal_per_tick", 0.0))
    state.last_per_biome_gpp = {int(k): float(v)
                                for k, v in payload.get(
                                    "last_per_biome_gpp", {}).items()}
    state.last_par = float(payload.get("last_par", 0.0))
    state.last_temp_c = float(payload.get("last_temp_c", 15.0))
    state.last_ca_ppm = float(payload.get("last_ca_ppm", 280.0))
    state.ticks_run = int(payload.get("ticks_run", 0))
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "Pathway",
    "BIOME_PATHWAY_MIX",
    "assimilation_c3",
    "assimilation_c4",
    "assimilation_cam",
    "compute_chunk_gpp",
    "install_photosynthesis",
    "tick_photosynthesis",
    "photosynthesis_state",
    "save_photo_state",
    "load_photo_state",
    "PhotosynthesisState",
]
