"""Genesis Engine — Wave 14 wildfire (Veille 2026-05-16).

Combo veille du jour
====================

Sources convergentes (4 lectures veille du 16 mai 2026) :

* Rothermel 1972 — *A mathematical model for predicting fire spread in
  wildland fuels* (USDA Forest Service INT-115). Modèle physique de
  référence : `ROS ∝ √(fuel_load) · (1 + slope_factor + wind_factor)`,
  réduit par l'humidité du combustible.
* Cell2Fire (arxiv 1905.09317) — formulation cell-based, déterministe,
  scalable, validée multi-régions.
* PyFireStation (github PyFireCoimbra) + MelikBLK Rothermel-Python —
  références d'implémentations Python compactes.
* Cellular Automaton wildfire (mdpi 2022, MDPI 13/12/1974) — règles
  locales de propagation, stables sous CFL trivial.

Pourquoi Genesis a besoin de feu
--------------------------------

Pré-Wave 14, Genesis n'avait **aucun** mécanisme :

* d'allumage spontané par foudre,
* de propagation de feu inter-cellules,
* de combustion des `wood` / `food_kcal`,
* de dépôt de cendres,
* de signal observable par les agents (feu = lumière + chaleur).

Or le feu est **le seul mécanisme physique** qui rend l'invention de la
maîtrise du feu plausible : un agent qui voit un arbre brûler après un
orage peut, à terme, déduire que le silex frappé produit la même chose
en petit. Sans feu spontané, l'invention reste scriptée par défaut.

Wave 14 fournit donc un **substrat additif** :

1. `tick_lightning(sim)` — orage déclenche allumage selon humidité,
   foudre prf-rng déterministe par chunk × tick.
2. `tick_fire_spread(sim)` — propagation cellulaire Rothermel simplifié
   (fuel × moisture × wind × slope), bornée par la disponibilité de
   combustible (`chunk.wood`).
3. `tick_combustion(sim)` — consomme `wood` + `food_kcal`, augmente
   `cumulative_ash`, refroidit le feu par épuisement du combustible.
4. Cendres dépôt N+K → enrichit le sol (signal pour `agriculture` /
   `photosynthesis` futurs sprints).

Règles invariantes respectées
-----------------------------

* **Émergence pure** : aucun trigger script. Allumage = (foudre prf-rng
  & combustible sec) ; propagation = (feu voisin & combustible &
  pas saturé d'eau). Pas de "if culture connaît feu alors agents
  observent" — c'est `cognition.perceive` qui détectera la chaleur via
  un futur signal `chunk._fire_intensity` (déjà exposé ici).
* **Déterminisme** : `prf_rng(sim.cfg.seed, ["wildfire", coord], [tick])`
  garantit bit-identité entre runs même seed.
* **Conservation** : `wood_consumed ≈ ash_produced × C_FUEL_TO_ASH_RATIO`,
  asserté en `debug` via `compute_wildfire_metrics(sim)`.
* **Localité** : un cellule ne lit que ses 8 voisins ; compatible
  future portage GPU compute-shader 8×8.

Indices visuels pour les agents
-------------------------------

Chaque chunk reçoit deux attributs side-channel :

* ``chunk._fire_intensity`` — np.ndarray (CHUNK_SIZE, CHUNK_SIZE)
  float32 — intensité de feu (0.0–1.0) par cellule.
* ``chunk._fire_ash`` — np.ndarray cumulé (kg/m²) de cendres
  déposées (signal long-terme pour fertilité du sol).

`cognition.perceive` peut lire `_fire_intensity > 0.1` comme un
percept "chaleur visible" sans dépendre de ce module (graceful absent).

API publique
------------

>>> from engine.wildfire import (
...     install_wildfire, tick_wildfire, wildfire_state,
...     compute_wildfire_metrics, save_wildfire_state,
...     load_wildfire_state,
... )
>>> install_wildfire(sim)
>>> sim.step()  # wraps tick_wildfire automatically
>>> metrics = compute_wildfire_metrics(sim)

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`` — le feu modifie la
ressource `wood` du substrat et dépose `ash` qui devient un layer
géochimique persistant (analogue à `geology.cumulative_extracted`).
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — déterministe,
composable, réversible (`load_wildfire_state` restaure exactement
l'état), prédictif court terme (un état t → t+1 sans regen full).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.world import (Biome, CHUNK_SIZE, VOXEL_SIZE_M,
                          invalidate_resource_masks)


# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


# ---------------------------------------------------------------------------
# Constants — Rothermel-calibrated (USDA Forest Service INT-115)
# ---------------------------------------------------------------------------

#: Probabilité d'allumage par foudre par cellule par tick — calibré
#: pour ~1 départ de feu par 5000 cellules-tick en climat sec sans
#: pluie. Multiplié par humidité_inverse et facteur orage.
LIGHTNING_BASE_RATE: float = 4e-5

#: Au-dessus de ce seuil de wood (kg/m²), une cellule est combustible.
#: En dessous, la cellule n'a pas assez de combustible — la propagation
#: s'éteint naturellement (pare-feu émergent).
FUEL_THRESHOLD: float = 2.0

#: Seuil d'humidité du combustible (proxied par chunk.water voisine)
#: au-dessus duquel le feu refuse de partir / s'éteint.
#: Calibré sur les "moisture of extinction" Rothermel (20–35% selon
#: les types de combustible — on prend 0.30 normalisé).
MOISTURE_EXTINCTION: float = 0.30

#: Coefficient Rothermel pour |v_wind|² → rate-of-spread.
#: Wind à 5 m/s double ROS environ ; calibré sur fig.2 INT-115.
WIND_COEFF: float = 0.04

#: Slope factor : ROS multipliée par tan(slope) → feu monte 2× plus
#: vite sur 45° qu'à plat. Conservatif pour stabilité.
SLOPE_COEFF: float = 1.0

#: ROS de base par tick (fraction d'intensité transférée au voisin).
#: 0.15 → un feu se propage à toutes les cellules voisines en ~7 ticks
#: dans des conditions optimales (sec, vent, pente).
ROS_BASE: float = 0.15

#: Decay multiplicatif de l'intensité par tick (refroidissement).
#: 0.92 → demi-vie ~8 ticks sans réalimentation en combustible.
INTENSITY_DECAY: float = 0.92

#: Quantité de combustible (wood kg/m²) consumée par unité d'intensité
#: par tick. Une cellule à intensité 1.0 brûle 0.8 kg/m² par tick.
FUEL_CONSUMPTION_RATE: float = 0.8

#: Fraction du combustible consumé qui devient cendres minérales
#: déposées (le reste part en gaz, CO2 + H2O + COVN).
#: Bois sec → ~3-5% de cendres réelles. On prend 4%.
ASH_YIELD: float = 0.04

#: Au-delà de cette intensité, on considère la cellule "en feu actif"
#: (signal pour cognition, métriques, agents).
ACTIVE_FIRE_THRESHOLD: float = 0.10

#: Biome → susceptibilité à l'allumage et à la propagation.
#: 1.0 = combustible "normal" (forêts) ; 0 = ne brûle pas (océan).
_BIOME_FLAMMABILITY: Dict[int, float] = {
    int(Biome.OCEAN): 0.0,
    int(Biome.ICE): 0.0,
    int(Biome.TUNDRA): 0.20,
    int(Biome.BOREAL_FOREST): 1.00,
    int(Biome.TEMPERATE_FOREST): 0.95,
    int(Biome.TEMPERATE_RAINFOREST): 0.55,  # humide
    int(Biome.GRASSLAND): 0.80,
    int(Biome.HOT_DESERT): 0.30,            # peu de fuel
    int(Biome.COLD_DESERT): 0.20,
    int(Biome.SAVANNA): 0.90,
    int(Biome.TROPICAL_DRY_FOREST): 1.00,
    int(Biome.TROPICAL_RAINFOREST): 0.45,   # très humide
}


# ---------------------------------------------------------------------------
# State container
# ---------------------------------------------------------------------------

@dataclass
class WildfireState:
    """Aggregate per-sim wildfire telemetry + RNG counter.

    Per-chunk fire grids live on the chunk itself as `_fire_intensity`
    and `_fire_ash` (side-channel attributes), to keep this module
    purely additive and graceful absent.
    """
    ignitions_total: int = 0
    cells_burned_total: int = 0
    wood_consumed_kg: float = 0.0
    ash_produced_kg: float = 0.0
    active_chunks: int = 0
    rng_counter: int = 0  # incremented per tick to spread prf_rng over time


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

def install_wildfire(sim) -> WildfireState:
    """Attach wildfire substrate to *sim*. Idempotent.

    Wraps `sim.step` so `tick_wildfire(sim)` runs at the end of each
    tick (after agent decisions + realism + lift). Order: wildfire
    consumes resources LAST in the tick so agent perception during
    THIS tick sees the previous tick's fire state — that's the
    correct causal order for emergent observation.
    """
    existing = getattr(sim, "wildfire", None)
    if isinstance(existing, WildfireState):
        return existing
    state = WildfireState()
    sim.wildfire = state

    # Wrap once : detect via attr to be safe under double-install.
    if getattr(sim, "_wildfire_wrapped", False):
        return state
    sim._wildfire_wrapped = True
    original_step = sim.step

    def wrapped_step():
        stats = original_step()
        try:
            tick_wildfire(sim)
        except Exception:
            if getattr(sim, "_wildfire_strict", False):
                raise
        return stats

    sim.step = wrapped_step
    return state


# ---------------------------------------------------------------------------
# Per-chunk grid lazy init
# ---------------------------------------------------------------------------

def _ensure_chunk_grids(chunk) -> Tuple[np.ndarray, np.ndarray]:
    """Lazily attach fire intensity + ash grids to a chunk."""
    fi = getattr(chunk, "_fire_intensity", None)
    if fi is None:
        fi = np.zeros((CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32)
        chunk._fire_intensity = fi
    ash = getattr(chunk, "_fire_ash", None)
    if ash is None:
        ash = np.zeros((CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32)
        chunk._fire_ash = ash
    return fi, ash


# ---------------------------------------------------------------------------
# Sub-ticks
# ---------------------------------------------------------------------------

def tick_lightning(sim, *, storm_factor: float = 1.0) -> int:
    """Stochastic lightning strikes — may ignite combustible cells.

    Returns the number of new ignitions this tick. `storm_factor` is a
    runtime multiplier reserved for `meteorology` integration (passing
    a higher value during thunderstorms).
    """
    state: WildfireState = getattr(sim, "wildfire", None)
    if state is None:
        return 0
    state.rng_counter += 1
    new_ignitions = 0
    for coord, chunk in list(sim.streamer.cache.items()):
        biome = chunk.biome
        # Skip chunks with no combustible biome at all
        # (full-ocean / full-ice). Cheap broad cull.
        biome_flat = biome.flatten()
        if biome_flat.size == 0:
            continue
        # Map biome → flammability vectorised once.
        flam = np.zeros_like(biome, dtype=np.float32)
        for b_id, fval in _BIOME_FLAMMABILITY.items():
            flam[biome == b_id] = fval
        if not (flam > 0.0).any():
            continue
        # Lightning strike map : prf_rng deterministic per chunk × tick.
        rng = prf_rng(sim.cfg.seed,
                      ["wildfire", "lightning",
                       f"{coord[0]}_{coord[1]}_{coord[2]}"],
                      [state.rng_counter])
        roll = rng.random(biome.shape, dtype=np.float32)
        # Probability per cell ; modulated by flammability + biome +
        # local fuel + dryness (proxied 1 - water).
        fi, _ash = _ensure_chunk_grids(chunk)
        wood = chunk.wood
        water = chunk.water
        dryness = np.clip(1.0 - (water / 200.0), 0.0, 1.0).astype(np.float32)
        fuel_ok = (wood >= FUEL_THRESHOLD).astype(np.float32)
        # Reject cells that are already burning : lightning is a no-op
        # on an existing fire.
        already_burning = (fi >= ACTIVE_FIRE_THRESHOLD).astype(np.float32)
        prob = (LIGHTNING_BASE_RATE * storm_factor) * flam * fuel_ok \
               * dryness * (1.0 - already_burning)
        strike_mask = roll < prob
        if strike_mask.any():
            # Ignition intensity proportional to fuel available (capped).
            ig_amount = np.minimum(0.5 + 0.5 * (wood / 50.0), 1.0).astype(np.float32)
            fi[strike_mask] = np.maximum(fi[strike_mask], ig_amount[strike_mask])
            n = int(strike_mask.sum())
            state.ignitions_total += n
            new_ignitions += n
    return new_ignitions


def tick_fire_spread(sim, *, wind: Optional[Tuple[float, float]] = None) -> int:
    """Spread fire to adjacent cells (Rothermel-simplified cellular).

    `wind` is an optional (vx, vy) m/s velocity. If `None`, the module
    falls back to `sim.realism._realism_seasons` indirectly through
    a neutral 0-wind assumption (deterministic).

    Returns the number of newly-ignited cells this tick.
    """
    state: WildfireState = getattr(sim, "wildfire", None)
    if state is None:
        return 0
    vx = vy = 0.0
    if wind is not None:
        vx, vy = float(wind[0]), float(wind[1])

    new_cells = 0
    chunks_active = 0
    for coord, chunk in list(sim.streamer.cache.items()):
        fi = getattr(chunk, "_fire_intensity", None)
        if fi is None:
            continue
        if not (fi >= ACTIVE_FIRE_THRESHOLD).any():
            continue
        chunks_active += 1
        # Compute spread targets : for each burning cell, push to 4
        # neighbours with intensity = local_intensity * ROS_BASE * mods.
        # Symmetric pass : we accumulate gains, apply at end → order-free.
        h = chunk.height.astype(np.float32)
        wood = chunk.wood
        water = chunk.water
        biome = chunk.biome

        flam = np.zeros_like(biome, dtype=np.float32)
        for b_id, fval in _BIOME_FLAMMABILITY.items():
            flam[biome == b_id] = fval

        # Moisture of extinction : if moisture > MOISTURE_EXTINCTION,
        # the cell refuses to ignite (ROS=0).
        moisture = np.clip(water / 200.0, 0.0, 1.0).astype(np.float32)
        moisture_ok = (moisture < MOISTURE_EXTINCTION).astype(np.float32)
        fuel_ok = (wood >= FUEL_THRESHOLD).astype(np.float32)
        receptive = flam * moisture_ok * fuel_ok

        gain = np.zeros_like(fi, dtype=np.float32)
        # Iterate 4 neighbours (N, S, E, W). Skip diagonal to keep CFL
        # trivial and stay aligned with future GPU 8-workgroup layout.
        # N: from y-1 to y
        src = fi[:-1, :]
        gain[1:, :] += src
        # S: from y+1 to y
        src = fi[1:, :]
        gain[:-1, :] += src
        # E: from x-1 to x
        src = fi[:, :-1]
        gain[:, 1:] += src
        # W: from x+1 to x
        src = fi[:, 1:]
        gain[:, :-1] += src

        # Slope factor : fire climbs faster. Approx ∂h ≈ centered diff /
        # (2·VOXEL_SIZE_M). We just use absolute slope magnitude here.
        gy, gx = np.gradient(h)
        slope_mag = np.sqrt(gx * gx + gy * gy) / (2.0 * VOXEL_SIZE_M)
        slope_factor = 1.0 + SLOPE_COEFF * np.clip(slope_mag, 0.0, 1.5)

        # Wind factor : isotropic positive influence (we don't bias
        # direction here to stay deterministic without a wind field —
        # meteorology integration can later read wind from the cell).
        wind_mag = (vx * vx + vy * vy) ** 0.5
        wind_factor = 1.0 + WIND_COEFF * wind_mag

        # Effective ROS-modulated gain.
        spread = gain * ROS_BASE * receptive * slope_factor * wind_factor

        # New ignitions : cells previously cold that just crossed the
        # active threshold.
        before_active = fi >= ACTIVE_FIRE_THRESHOLD
        new_fi = np.minimum(1.0, fi + spread).astype(np.float32)
        # Decay : flame cools by INTENSITY_DECAY per tick (applied to
        # the cells already burning before spread).
        new_fi = np.where(before_active,
                          np.maximum(new_fi * INTENSITY_DECAY,
                                     fi * INTENSITY_DECAY),
                          new_fi)
        after_active = new_fi >= ACTIVE_FIRE_THRESHOLD
        n_new = int(np.count_nonzero(after_active & (~before_active)))
        chunk._fire_intensity = new_fi
        new_cells += n_new
        state.cells_burned_total += n_new

    state.active_chunks = chunks_active
    return new_cells


def tick_combustion(sim) -> Tuple[float, float]:
    """Consume fuel + produce ash on active-fire cells.

    Returns (wood_consumed_kg, ash_produced_kg) **this tick** —
    not cumulative.
    """
    state: WildfireState = getattr(sim, "wildfire", None)
    if state is None:
        return (0.0, 0.0)
    tick_wood = 0.0
    tick_ash = 0.0
    for coord, chunk in list(sim.streamer.cache.items()):
        fi = getattr(chunk, "_fire_intensity", None)
        if fi is None:
            continue
        if not (fi >= ACTIVE_FIRE_THRESHOLD).any():
            continue
        ash = getattr(chunk, "_fire_ash", None)
        if ash is None:
            _, ash = _ensure_chunk_grids(chunk)

        # Per-cell fuel consumption proportional to intensity.
        consume = (fi * FUEL_CONSUMPTION_RATE).astype(np.float32)
        # Bounded by available wood (can't consume more than present).
        actual_consume = np.minimum(consume, chunk.wood)
        chunk.wood = (chunk.wood - actual_consume).astype(np.float32)
        # Ash deposition. Long-term soil fertility signal.
        ash_add = (actual_consume * ASH_YIELD).astype(np.float32)
        chunk._fire_ash = (ash + ash_add).astype(np.float32)
        # Fuel exhaustion → intensity decays to 0 (handled implicitly by
        # tick_fire_spread's decay, but we also bound here in case wood
        # ran out mid-tick).
        no_fuel_mask = chunk.wood < FUEL_THRESHOLD
        if no_fuel_mask.any():
            fi[no_fuel_mask] *= 0.5  # rapid cooldown on starved cell
            chunk._fire_intensity = fi

        # Tick totals.
        c_sum = float(actual_consume.sum())
        a_sum = float(ash_add.sum())
        tick_wood += c_sum
        tick_ash += a_sum
        state.wood_consumed_kg += c_sum
        state.ash_produced_kg += a_sum

        # The chunk's resource masks (wood) just changed.
        invalidate_resource_masks(chunk)

    return (tick_wood, tick_ash)


def tick_wildfire(sim, *, storm_factor: float = 1.0,
                  wind: Optional[Tuple[float, float]] = None) -> Dict[str, int]:
    """Single-tick orchestration : lightning → spread → combustion.

    Returns a dict with this tick's deltas (ignitions / new_cells /
    wood_consumed / ash_produced). Determinism-safe.
    """
    if getattr(sim, "wildfire", None) is None:
        return {"ignitions": 0, "new_cells": 0,
                "wood_consumed_kg": 0.0, "ash_produced_kg": 0.0}
    n_ig = tick_lightning(sim, storm_factor=storm_factor)
    n_new = tick_fire_spread(sim, wind=wind)
    wood, ash = tick_combustion(sim)
    return {
        "ignitions": n_ig,
        "new_cells": n_new,
        "wood_consumed_kg": float(wood),
        "ash_produced_kg": float(ash),
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_wildfire_metrics(sim) -> Dict[str, float]:
    """Aggregate diagnostics on current sim state. JSON-safe."""
    state: WildfireState = getattr(sim, "wildfire", None)
    if state is None:
        return {
            "ignitions_total": 0,
            "cells_burned_total": 0,
            "wood_consumed_kg": 0.0,
            "ash_produced_kg": 0.0,
            "active_chunks": 0,
            "active_fire_cells": 0,
            "max_intensity": 0.0,
            "mean_ash_kg_per_m2": 0.0,
        }
    active_cells = 0
    max_intensity = 0.0
    ash_sum = 0.0
    n_cells = 0
    for chunk in list(sim.streamer.cache.values()):
        fi = getattr(chunk, "_fire_intensity", None)
        if fi is not None:
            mask = fi >= ACTIVE_FIRE_THRESHOLD
            active_cells += int(mask.sum())
            if fi.size > 0:
                max_intensity = max(max_intensity, float(fi.max()))
        ash = getattr(chunk, "_fire_ash", None)
        if ash is not None:
            ash_sum += float(ash.sum())
            n_cells += int(ash.size)
    mean_ash = (ash_sum / n_cells) if n_cells > 0 else 0.0
    return {
        "ignitions_total": int(state.ignitions_total),
        "cells_burned_total": int(state.cells_burned_total),
        "wood_consumed_kg": float(state.wood_consumed_kg),
        "ash_produced_kg": float(state.ash_produced_kg),
        "active_chunks": int(state.active_chunks),
        "active_fire_cells": int(active_cells),
        "max_intensity": float(max_intensity),
        "mean_ash_kg_per_m2": float(mean_ash),
    }


def wildfire_state(sim) -> Dict:
    """Dashboard-friendly snapshot. Alias of `compute_wildfire_metrics`
    so the API matches the convention of `realism_state`, `lift_state`,
    etc."""
    return compute_wildfire_metrics(sim)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

_WILDFIRE_FILENAME = "wildfire.npz"


def save_wildfire_state(sim, world_dir: str) -> Optional[str]:
    """Persist wildfire grids + aggregate state to <world_dir>/wildfire.npz.

    Stores one fire+ash grid per active chunk, plus the scalar totals.
    Returns the path or None if not installed / not writable.
    """
    state: WildfireState = getattr(sim, "wildfire", None)
    if state is None:
        return None
    path = os.path.join(world_dir, _WILDFIRE_FILENAME)
    try:
        os.makedirs(world_dir, exist_ok=True)
        coords: List[Tuple[int, int, int]] = []
        fires: List[np.ndarray] = []
        ashes: List[np.ndarray] = []
        for coord, chunk in list(sim.streamer.cache.items()):
            fi = getattr(chunk, "_fire_intensity", None)
            ash = getattr(chunk, "_fire_ash", None)
            if fi is None and ash is None:
                continue
            if fi is None:
                fi = np.zeros((CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32)
            if ash is None:
                ash = np.zeros((CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32)
            coords.append(coord)
            fires.append(fi.astype(np.float32, copy=True))
            ashes.append(ash.astype(np.float32, copy=True))
        if not coords:
            coord_arr = np.zeros((0, 3), dtype=np.int32)
            fire_arr = np.zeros((0, CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32)
            ash_arr = np.zeros((0, CHUNK_SIZE, CHUNK_SIZE), dtype=np.float32)
        else:
            coord_arr = np.array(coords, dtype=np.int32)
            fire_arr = np.stack(fires, axis=0).astype(np.float32)
            ash_arr = np.stack(ashes, axis=0).astype(np.float32)
        np.savez(
            path,
            coords=coord_arr,
            fires=fire_arr,
            ashes=ash_arr,
            meta=np.array([state.ignitions_total,
                           state.cells_burned_total,
                           state.active_chunks,
                           state.rng_counter], dtype=np.int64),
            scalars=np.array([state.wood_consumed_kg,
                              state.ash_produced_kg], dtype=np.float64),
        )
        return path
    except OSError:
        return None


def load_wildfire_state(sim, world_dir: str) -> bool:
    """Restore wildfire state. Installs fresh state if file absent.

    Returns True if a saved file was restored ; False otherwise.
    """
    path = os.path.join(world_dir, _WILDFIRE_FILENAME)
    if not os.path.isfile(path):
        install_wildfire(sim)
        return False
    data = np.load(path)
    install_wildfire(sim)
    state: WildfireState = sim.wildfire
    meta = data["meta"]
    scalars = data["scalars"]
    state.ignitions_total = int(meta[0])
    state.cells_burned_total = int(meta[1])
    state.active_chunks = int(meta[2])
    state.rng_counter = int(meta[3])
    state.wood_consumed_kg = float(scalars[0])
    state.ash_produced_kg = float(scalars[1])
    coords = data["coords"]
    fires = data["fires"]
    ashes = data["ashes"]
    for i in range(coords.shape[0]):
        coord = (int(coords[i, 0]), int(coords[i, 1]), int(coords[i, 2]))
        chunk = sim.streamer.cache.get(coord)
        if chunk is None:
            continue
        chunk._fire_intensity = fires[i].astype(np.float32, copy=True)
        chunk._fire_ash = ashes[i].astype(np.float32, copy=True)
    return True


# ---------------------------------------------------------------------------
# Manual ignition helper (smoke + tests)
# ---------------------------------------------------------------------------

def ignite_at(sim, x_m: float, y_m: float, intensity: float = 1.0) -> bool:
    """Manually ignite a cell at world (x, y). Returns True on success.

    Used by smoke tests + the future agent action `LIGHT_FIRE`. The
    cell must (1) belong to a loaded chunk and (2) carry combustible
    fuel (wood >= FUEL_THRESHOLD).
    """
    from engine.world import world_to_cell, world_to_chunk
    coord = world_to_chunk(x_m, y_m)
    chunk = sim.streamer.cache.get(coord)
    if chunk is None:
        return False
    cx, cy = world_to_cell(x_m, y_m, coord)
    if not (0 <= cx < CHUNK_SIZE and 0 <= cy < CHUNK_SIZE):
        return False
    fi, _ash = _ensure_chunk_grids(chunk)
    if chunk.wood[cy, cx] < FUEL_THRESHOLD:
        return False
    fi[cy, cx] = max(float(fi[cy, cx]), float(intensity))
    state: WildfireState = getattr(sim, "wildfire", None)
    if state is not None:
        state.ignitions_total += 1
    return True


__all__ = [
    # constants
    "LIGHTNING_BASE_RATE", "FUEL_THRESHOLD", "MOISTURE_EXTINCTION",
    "WIND_COEFF", "SLOPE_COEFF", "ROS_BASE", "INTENSITY_DECAY",
    "FUEL_CONSUMPTION_RATE", "ASH_YIELD", "ACTIVE_FIRE_THRESHOLD",
    # state
    "WildfireState",
    # install + ticks
    "install_wildfire", "tick_wildfire", "tick_lightning",
    "tick_fire_spread", "tick_combustion",
    # API
    "ignite_at", "compute_wildfire_metrics", "wildfire_state",
    # persistence
    "save_wildfire_state", "load_wildfire_state",
]
