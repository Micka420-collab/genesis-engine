"""Genesis Engine — Wave 6 plant evolutionary biology.

Drives the **emergence**, **growth**, **extinction** and **speciation** of
the 40 plant clades catalogued in :mod:`engine.plant_catalog` across
every cached chunk of a Simulation. The model is scientifically grounded
in real Earth phylogeny but the *outcomes* of any given run diverge
from our world's history based on:

* atmospheric CO2 (lowered by photosynthesis, raised by ecology
  emissions) — high CO2 stresses C4 grasses (they evolved under low
  CO2 ≈ 280 ppm); low CO2 hampers C3 plants.
* atmospheric O2 — gated by global cyanobacteria + algae GPP integrated
  over time. Bryophytes need >5%, ferns >15%, angiosperms >18%.
* per-chunk climate (T, water) — drives the bell-curve fitness per clade.
* biome affinity — clades survive *much* better in their preferred biomes.
* agent feedback — deforestation by agents reduces wood biomass directly,
  changing which clades dominate.

Two boot modes
--------------
* ``modern`` (default) — all 40 catalogued clades are seeded into
  ``available_clades`` at install time, present at low biomass in
  every biome-compatible chunk. This is "Holocene Earth".
* ``ancient`` — only cyanobacteria are seeded. New clades emerge as
  atmospheric O2 + their parent clade's biomass reach the thresholds
  baked into :class:`PlantClade`. This is the **counter-factual replay
  of Earth's plant evolution** the FUTURE-VISION asked for.

Speciation
----------
A clade present continuously in a chunk for ``SPECIATION_INCUBATION_TICKS``
sim-ticks has a tiny prf_rng-gated probability per tick of mutating
into a **synthetic clade** — a new entry with ±10 % perturbed
``temp_opt``, ``water_min``, ``max_co2_ppm`` and a fresh name like
``oaks_mut_42``. The synthetic clade joins ``available_clades`` and
can itself further speciate.

Per-chunk pathway override
--------------------------
Once a chunk has measurable biomass, this module writes a
``chunk._plant_pathway_mix`` attribute holding a fresh (C3, C4, CAM)
tuple weighted by which clades actually grow there. The Farquhar code
in :mod:`engine.photosynthesis` reads it preferentially over the
fixed ``BIOME_PATHWAY_MIX`` — this is how AI-driven divergence in plant
composition feeds back into measurable GPP.

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — biology↔atmosphere↔climate
feedback loop.
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — composable
multi-step rollouts respecting phylogenetic + ecological laws.
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"  # arxiv 2604.22748

import json
import os
import math
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from engine.core import TICK_DT_S, prf_rng
from engine.plant_catalog import (
    CLADES, CLADE_BY_NAME, CladeKingdom, PlantClade,
    PATHWAY_C3, PATHWAY_C4, PATHWAY_CAM,
    children_of, all_clade_names,
)


# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

# How much biomass (kg per chunk) counts as "present" for clade tracking.
PRESENT_THRESHOLD_KG = 0.5
# Carrying capacity per chunk per clade (kg). Past this point growth stops.
CARRYING_CAPACITY_KG = 5000.0
# Per-tick base decay rate when fitness drops to zero.
DECAY_PER_S = 1.0 / (90.0 * 86400.0)
# Global ticks of continuous chunk presence before speciation can fire.
SPECIATION_INCUBATION_TICKS = 30 * 86400      # 30 sim-days × accel
# Per-tick speciation roll on a primed chunk (tiny).
SPECIATION_PROB_PER_S = 1.0 / (30.0 * 86400.0)
# Ticks with zero global biomass before a clade is declared extinct.
EXTINCTION_WAIT_TICKS = 30 * 86400
# Initial seed mass in modern mode (kg per compatible chunk).
SEED_BIOMASS_MODERN = 50.0
# Initial seed mass in ancient mode (only cyanobacteria).
SEED_BIOMASS_ANCIENT = 5.0

# Atmospheric O2 dynamics — Genesis-realistic but simplified.
O2_BASELINE_PCT_MODERN = 20.95
O2_BASELINE_PCT_ANCIENT = 0.1
# kg of O2 produced per kg of glucose at 6 CO2 + 6 H2O → C6H12O6 + 6 O2.
KG_O2_PER_KG_GLUCOSE = 32.0 / 30.0  # ~1.067
# How much "Earth atmospheric mass per ppm O2" we use in the local model
# (intentionally tiny so the sim is reactive — 1 chunk-scale change per
# millennium is visible inside 1 sim-month).
O2_KG_PER_PCT_LOCAL = 5.0e3


# ---------------------------------------------------------------------------
# State containers
# ---------------------------------------------------------------------------

@dataclass
class ChunkVegetation:
    """Per-chunk biomass dict + bookkeeping."""
    biomass_kg: Dict[str, float] = field(default_factory=dict)
    present_since_tick: Dict[str, int] = field(default_factory=dict)


@dataclass
class SpeciationEvent:
    parent_clade: str
    child_clade: str
    chunk_coord: Tuple[int, int, int]
    tick: int
    why: str


@dataclass
class PlantEvolutionState:
    """Live state attached to ``sim._plant_state``."""
    mode: str = "modern"
    chunk_vegetation: Dict[Tuple[int, int, int], ChunkVegetation] = (
        field(default_factory=dict))
    available_clades: Set[str] = field(default_factory=set)
    extinct_clades: Set[str] = field(default_factory=set)
    synthetic_clades: Dict[str, PlantClade] = field(default_factory=dict)
    speciation_log: List[SpeciationEvent] = field(default_factory=list)
    # Tracker for extinction debouncing.
    clade_last_seen_tick: Dict[str, int] = field(default_factory=dict)
    # Atmospheric O2 mass (kg) — accumulates from cyanobacteria.
    oxygen_kg_delta: float = 0.0
    # Stats.
    ticks_run: int = 0
    last_global_biomass_kg: float = 0.0
    last_per_kingdom_biomass: Dict[int, float] = field(default_factory=dict)

    # --- helpers ---
    def oxygen_pct(self) -> float:
        """Current atmospheric O2 percentage (mode-aware)."""
        base = (O2_BASELINE_PCT_MODERN if self.mode == "modern"
                else O2_BASELINE_PCT_ANCIENT)
        return base + self.oxygen_kg_delta / O2_KG_PER_PCT_LOCAL

    def clade(self, name: str) -> Optional[PlantClade]:
        c = CLADE_BY_NAME.get(name)
        if c is not None:
            return c
        return self.synthetic_clades.get(name)


# ---------------------------------------------------------------------------
# Fitness — pure function (clade, environment) → [0, 1]
# ---------------------------------------------------------------------------

def _bell(value: float, lo: float, opt: float, hi: float) -> float:
    """Asymmetric bell centred on ``opt`` (=1.0), zero at ``lo``/``hi``."""
    if value <= lo or value >= hi:
        return 0.0
    if value < opt:
        return max(0.0, 1.0 - ((opt - value) / max(1e-3, opt - lo)) ** 2)
    return max(0.0, 1.0 - ((value - opt) / max(1e-3, hi - opt)) ** 2)


def compute_fitness(
    clade: PlantClade,
    biome_id: int,
    temp_c: float,
    chunk_water_max_l: float,
    oxygen_pct: float,
    co2_ppm: float,
) -> float:
    """Return fitness in [0, 1]. 0 means the clade cannot survive here.

    Pure function. No RNG. Composes :
      * temperature bell curve
      * water threshold (linear soft below water_min, 1.0 above)
      * O2 floor (hard cutoff below min_oxygen_pct)
      * CO2 ceiling (hard cutoff above max_co2_ppm)
      * biome affinity multiplier (1.0 if in affinity, 0.10 if not)
    """
    if oxygen_pct < clade.min_oxygen_pct:
        return 0.0
    if co2_ppm > clade.max_co2_ppm:
        return 0.0
    t_factor = _bell(temp_c, clade.temp_min, clade.temp_opt, clade.temp_max)
    if t_factor <= 0.0:
        return 0.0
    # Water : soft below threshold, capped at 1 above.
    if chunk_water_max_l < clade.water_min:
        w_factor = max(0.0, chunk_water_max_l / max(1.0, clade.water_min))
    else:
        w_factor = 1.0
    if w_factor <= 0.0:
        return 0.0
    aff = 1.0 if biome_id in clade.biome_affinity else 0.10
    return max(0.0, min(1.0, t_factor * w_factor * aff))


# ---------------------------------------------------------------------------
# Atmospheric coupling
# ---------------------------------------------------------------------------

def _resolve_atmosphere(sim):
    atm = getattr(sim, "atmosphere", None)
    if atm is not None:
        return atm
    atm = getattr(sim, "_ecology_atmosphere", None)
    if atm is not None:
        return atm
    return None


def _resolve_weather(sim):
    try:
        from engine.world import weather_at
        return weather_at(sim.tick * int(sim.cfg.drive_accel), 15.0, 1.0)
    except Exception:
        @dataclass
        class _W:
            temp_c: float = 15.0
            rain_mm_h: float = 1.0
            cloud: float = 0.5
            is_day: bool = True
        return _W()


# ---------------------------------------------------------------------------
# Per-chunk update
# ---------------------------------------------------------------------------

def _dominant_biome(chunk) -> int:
    biomes, counts = np.unique(chunk.biome, return_counts=True)
    return int(biomes[np.argmax(counts)])


def _update_chunk(
    sim, state: PlantEvolutionState,
    coord: Tuple[int, int, int], chunk,
    temp_c: float, oxygen_pct: float, co2_ppm: float,
    accel: float,
) -> Tuple[float, Dict[int, float], float]:
    """Tick one chunk. Returns (chunk_biomass_total, per_kingdom, o2_produced_kg)."""
    biome = _dominant_biome(chunk)
    chunk_water_max = float(chunk.water.max())
    veg = state.chunk_vegetation.setdefault(coord, ChunkVegetation())
    per_kingdom: Dict[int, float] = {}
    total = 0.0
    o2_kg = 0.0
    dt_s = TICK_DT_S * accel

    # Iterate over a snapshot of clades (so we can add synthetics mid-loop).
    clade_names = list(state.available_clades - state.extinct_clades)
    for name in clade_names:
        clade = state.clade(name)
        if clade is None:
            continue
        fit = compute_fitness(clade, biome, temp_c, chunk_water_max,
                              oxygen_pct, co2_ppm)
        cur = veg.biomass_kg.get(name, 0.0)
        if fit > 0.0:
            # Logistic-style growth toward carrying capacity.
            grow = (clade.growth_kg_per_day_opt / 86400.0) * dt_s * fit
            density = cur / CARRYING_CAPACITY_KG
            cur = cur + max(0.0, grow * (1.0 - density))
            # First time present — log incubation start.
            if cur >= PRESENT_THRESHOLD_KG and name not in veg.present_since_tick:
                veg.present_since_tick[name] = sim.tick
        else:
            # Decay when conditions hostile.
            decay = DECAY_PER_S * dt_s * cur
            cur = max(0.0, cur - decay)
            if cur < PRESENT_THRESHOLD_KG:
                veg.present_since_tick.pop(name, None)

        if cur > 0.0:
            veg.biomass_kg[name] = cur
            total += cur
            k = int(clade.kingdom)
            per_kingdom[k] = per_kingdom.get(k, 0.0) + cur
            state.clade_last_seen_tick[name] = sim.tick
            # O2 production from photoautotrophs : approximate gross
            # productivity from current biomass and pathway-independent
            # baseline rate. Cyanobacteria + algae dominate this term
            # historically.
            if clade.kingdom in (CladeKingdom.PROKARYOTE_AUTOTROPH,
                                 CladeKingdom.ALGAE):
                # 0.05 g glucose per kg biomass per second under good conditions
                gpp_kg_glucose = 5e-5 * cur * fit * dt_s
                o2_kg += gpp_kg_glucose * KG_O2_PER_KG_GLUCOSE
        else:
            veg.biomass_kg.pop(name, None)

    # Speciation roll : any clade primed for INCUBATION_TICKS can mutate.
    if veg.present_since_tick:
        rng = prf_rng(sim.cfg.seed, ["plant_evol", "speciate"],
                      [int(sim.tick), int(coord[0]), int(coord[1])])
        for name, since in list(veg.present_since_tick.items()):
            age = sim.tick - since
            if age < SPECIATION_INCUBATION_TICKS:
                continue
            p = SPECIATION_PROB_PER_S * dt_s
            if rng.random() < p:
                _spawn_synthetic_clade(state, name, coord, sim.tick)

    # Write pathway-mix override on the chunk so photosynthesis picks it up.
    if total > 1.0:
        c3 = c4 = cam = 0.0
        for name, mass in veg.biomass_kg.items():
            clade = state.clade(name)
            if clade is None:
                continue
            w = mass / total
            if clade.pathway == PATHWAY_C3:
                c3 += w
            elif clade.pathway == PATHWAY_C4:
                c4 += w
            elif clade.pathway == PATHWAY_CAM:
                cam += w
        chunk._plant_pathway_mix = (c3, c4, cam)
    return total, per_kingdom, o2_kg


def _spawn_synthetic_clade(
    state: PlantEvolutionState,
    parent_name: str,
    chunk_coord: Tuple[int, int, int],
    tick: int,
) -> None:
    """Create a perturbed variant clade and register it as available."""
    parent = state.clade(parent_name)
    if parent is None:
        return
    n = sum(1 for c in state.synthetic_clades.values()
            if c.parent_clade == parent_name) + 1
    new_name = f"{parent_name}_mut_{n}"
    rng = prf_rng(0xC0DE_BEAF, ["speciation_perturb", new_name], [tick])
    def jitter(v: float, frac: float = 0.10) -> float:
        return v * (1.0 + (rng.random() - 0.5) * 2.0 * frac)
    variant = replace(
        parent,
        name=new_name,
        common_name=f"{parent.common_name} (variant)",
        first_appearance_ma=0.0,
        temp_opt=jitter(parent.temp_opt, 0.08),
        water_min=max(0.5, jitter(parent.water_min, 0.15)),
        max_co2_ppm=max(300.0, jitter(parent.max_co2_ppm, 0.10)),
        growth_kg_per_day_opt=max(0.001,
                                  jitter(parent.growth_kg_per_day_opt, 0.20)),
    )
    state.synthetic_clades[new_name] = variant
    state.available_clades.add(new_name)
    state.speciation_log.append(SpeciationEvent(
        parent_clade=parent_name, child_clade=new_name,
        chunk_coord=chunk_coord, tick=tick,
        why="speciation_after_incubation",
    ))


# ---------------------------------------------------------------------------
# Global per-tick driver
# ---------------------------------------------------------------------------

def tick_plant_evolution(sim, state: PlantEvolutionState) -> None:
    """Advance one tick. Pure-numpy where possible, prf_rng-gated."""
    atm = _resolve_atmosphere(sim)
    weather = _resolve_weather(sim)
    co2_ppm = float(getattr(atm, "co2_ppm", 280.0)) if atm is not None else 280.0
    temp_c = float(getattr(weather, "temp_c", 15.0))
    accel = float(sim.cfg.drive_accel)
    oxygen_pct = state.oxygen_pct()

    # 1. Per-chunk biomass update.
    global_total = 0.0
    per_kingdom: Dict[int, float] = {}
    o2_total_kg = 0.0
    for coord, chunk in list(sim.streamer.cache.items()):
        t, k_dict, o2 = _update_chunk(
            sim, state, coord, chunk,
            temp_c, oxygen_pct, co2_ppm, accel)
        global_total += t
        for k, v in k_dict.items():
            per_kingdom[k] = per_kingdom.get(k, 0.0) + v
        o2_total_kg += o2
    state.oxygen_kg_delta += o2_total_kg

    # 2. Emergence : any unavailable clade whose parent is present and
    #    whose global atmospheric conditions allow can be added to the
    #    available pool (small probability per tick to avoid bulk flooding).
    if state.mode == "ancient":
        rng_em = prf_rng(sim.cfg.seed, ["plant_evol", "emerge"],
                         [int(sim.tick)])
        for clade in CLADES:
            if clade.name in state.available_clades:
                continue
            if clade.name in state.extinct_clades:
                continue
            # Parent must be present somewhere.
            parent_present = (clade.parent_clade == ""
                              or clade.parent_clade in state.available_clades)
            if not parent_present:
                continue
            # Global atmospheric conditions must allow the *minima*.
            if oxygen_pct < clade.min_oxygen_pct:
                continue
            # Small per-tick chance to emerge.
            if rng_em.random() < 1.0 / (10.0 * 86400.0) * accel * TICK_DT_S:
                state.available_clades.add(clade.name)

    # 3. Extinction debouncing.
    for name in list(state.available_clades):
        if name in state.extinct_clades:
            continue
        last = state.clade_last_seen_tick.get(name, sim.tick)
        if sim.tick - last > EXTINCTION_WAIT_TICKS:
            state.extinct_clades.add(name)

    state.last_global_biomass_kg = global_total
    state.last_per_kingdom_biomass = per_kingdom
    state.ticks_run += 1


# ---------------------------------------------------------------------------
# Public installer + reporter
# ---------------------------------------------------------------------------

def install_plant_evolution(sim, *, mode: str = "modern") -> PlantEvolutionState:
    """Attach a :class:`PlantEvolutionState` to ``sim`` and wrap step.

    ``mode='modern'`` seeds all 40 catalogued clades immediately.
    ``mode='ancient'`` seeds only ``cyanobacteria`` and lets evolution
    re-discover the others as atmospheric O2 climbs.
    """
    existing: Optional[PlantEvolutionState] = getattr(sim, "_plant_state", None)
    if existing is not None:
        return existing

    state = PlantEvolutionState(mode=mode)
    if mode == "modern":
        for c in CLADES:
            state.available_clades.add(c.name)
        # Pre-seed a low biomass into every cached chunk so the FIRST tick
        # already has measurable biomass (test-friendly + immediate visual).
        for coord, chunk in list(sim.streamer.cache.items()):
            veg = ChunkVegetation()
            biome = _dominant_biome(chunk)
            for c in CLADES:
                if biome in c.biome_affinity:
                    veg.biomass_kg[c.name] = SEED_BIOMASS_MODERN
                    veg.present_since_tick[c.name] = sim.tick
            if veg.biomass_kg:
                state.chunk_vegetation[coord] = veg
    else:
        state.available_clades.add("cyanobacteria")
        for coord, chunk in list(sim.streamer.cache.items()):
            veg = ChunkVegetation()
            veg.biomass_kg["cyanobacteria"] = SEED_BIOMASS_ANCIENT
            veg.present_since_tick["cyanobacteria"] = sim.tick
            state.chunk_vegetation[coord] = veg

    sim._plant_state = state
    orig_step = sim.step

    def wrapped_step():
        stats = orig_step()
        tick_plant_evolution(sim, state)
        return stats

    sim.step = wrapped_step
    return state


def plant_evolution_state(sim) -> Dict[str, object]:
    """Snapshot for ``/api/plant_evolution_state``."""
    state: Optional[PlantEvolutionState] = getattr(sim, "_plant_state", None)
    if state is None:
        return {}
    # Top 5 clades by global biomass.
    global_per_clade: Dict[str, float] = {}
    for veg in state.chunk_vegetation.values():
        for name, mass in veg.biomass_kg.items():
            global_per_clade[name] = global_per_clade.get(name, 0.0) + mass
    top = sorted(global_per_clade.items(), key=lambda kv: -kv[1])[:8]
    kingdom_names = {int(k): k.name for k in CladeKingdom}
    per_kingdom_named = {
        kingdom_names.get(k, str(k)): round(v, 1)
        for k, v in state.last_per_kingdom_biomass.items()
    }
    recent_speciations = [
        {"parent": e.parent_clade, "child": e.child_clade,
         "tick": e.tick, "chunk": list(e.chunk_coord)}
        for e in state.speciation_log[-5:]
    ]
    return {
        "mode": state.mode,
        "oxygen_pct": round(state.oxygen_pct(), 3),
        "global_biomass_kg": round(state.last_global_biomass_kg, 1),
        "available_clades": sorted(state.available_clades),
        "extinct_clades": sorted(state.extinct_clades),
        "synthetic_count": len(state.synthetic_clades),
        "top_clades": [{"name": n, "biomass_kg": round(m, 1)} for n, m in top],
        "per_kingdom_biomass_kg": per_kingdom_named,
        "recent_speciations": recent_speciations,
        "speciation_total": len(state.speciation_log),
        "ticks_run": state.ticks_run,
        "chunks_tracked": len(state.chunk_vegetation),
    }


# ---------------------------------------------------------------------------
# Persistence (P1 hooks)
# ---------------------------------------------------------------------------

def save_plant_state(sim, target_dir: str) -> bool:
    """Persist :class:`PlantEvolutionState` to disk."""
    state: Optional[PlantEvolutionState] = getattr(sim, "_plant_state", None)
    if state is None:
        return False
    payload = {
        "mode": state.mode,
        "available_clades": sorted(state.available_clades),
        "extinct_clades": sorted(state.extinct_clades),
        "synthetic_clades": {
            name: {
                "name": c.name,
                "common_name": c.common_name,
                "kingdom": int(c.kingdom),
                "parent_clade": c.parent_clade,
                "first_appearance_ma": c.first_appearance_ma,
                "pathway": c.pathway,
                "temp_min": c.temp_min, "temp_opt": c.temp_opt, "temp_max": c.temp_max,
                "water_min": c.water_min,
                "min_oxygen_pct": c.min_oxygen_pct,
                "max_co2_ppm": c.max_co2_ppm,
                "biome_affinity": sorted(c.biome_affinity),
                "height_m": c.height_m,
                "edible_kcal_per_kg": c.edible_kcal_per_kg,
                "wood_yield_kg_per_kgbio": c.wood_yield_kg_per_kgbio,
                "growth_kg_per_day_opt": c.growth_kg_per_day_opt,
            }
            for name, c in state.synthetic_clades.items()
        },
        "speciation_log": [
            {"parent": e.parent_clade, "child": e.child_clade,
             "chunk_coord": list(e.chunk_coord), "tick": e.tick, "why": e.why}
            for e in state.speciation_log
        ],
        "clade_last_seen_tick": dict(state.clade_last_seen_tick),
        "oxygen_kg_delta": state.oxygen_kg_delta,
        "ticks_run": state.ticks_run,
        "chunk_vegetation": {
            f"{c[0]}_{c[1]}_{c[2]}": {
                "biomass_kg": v.biomass_kg,
                "present_since_tick": v.present_since_tick,
            }
            for c, v in state.chunk_vegetation.items()
        },
    }
    with open(os.path.join(target_dir, "plant_evolution.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return True


def load_plant_state(sim, target_dir: str) -> bool:
    """Reinstate :class:`PlantEvolutionState` from disk."""
    path = os.path.join(target_dir, "plant_evolution.json")
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state = install_plant_evolution(sim, mode=payload.get("mode", "modern"))
    state.available_clades = set(payload.get("available_clades", []))
    state.extinct_clades = set(payload.get("extinct_clades", []))
    state.oxygen_kg_delta = float(payload.get("oxygen_kg_delta", 0.0))
    state.ticks_run = int(payload.get("ticks_run", 0))
    state.clade_last_seen_tick = {
        str(k): int(v)
        for k, v in payload.get("clade_last_seen_tick", {}).items()
    }
    # Synthetic clades.
    state.synthetic_clades.clear()
    for name, d in payload.get("synthetic_clades", {}).items():
        state.synthetic_clades[name] = PlantClade(
            name=str(d["name"]),
            common_name=str(d.get("common_name", "")),
            kingdom=CladeKingdom(int(d.get("kingdom", 0))),
            parent_clade=str(d.get("parent_clade", "")),
            first_appearance_ma=float(d.get("first_appearance_ma", 0.0)),
            pathway=int(d.get("pathway", 0)),
            temp_min=float(d.get("temp_min", -5)),
            temp_opt=float(d.get("temp_opt", 20)),
            temp_max=float(d.get("temp_max", 35)),
            water_min=float(d.get("water_min", 1.0)),
            min_oxygen_pct=float(d.get("min_oxygen_pct", 0.0)),
            max_co2_ppm=float(d.get("max_co2_ppm", 2000.0)),
            biome_affinity=frozenset(int(b) for b in d.get("biome_affinity", [])),
            height_m=float(d.get("height_m", 0.5)),
            edible_kcal_per_kg=float(d.get("edible_kcal_per_kg", 0.0)),
            wood_yield_kg_per_kgbio=float(d.get("wood_yield_kg_per_kgbio", 0.0)),
            growth_kg_per_day_opt=float(d.get("growth_kg_per_day_opt", 0.01)),
        )
    # Speciation log.
    state.speciation_log = [
        SpeciationEvent(
            parent_clade=e["parent"], child_clade=e["child"],
            chunk_coord=tuple(e["chunk_coord"]),
            tick=int(e["tick"]), why=str(e.get("why", "")))
        for e in payload.get("speciation_log", [])
    ]
    # Chunk vegetation.
    state.chunk_vegetation.clear()
    for key, d in payload.get("chunk_vegetation", {}).items():
        parts = key.split("_")
        coord = tuple(int(p) for p in parts)
        veg = ChunkVegetation(
            biomass_kg={k: float(v) for k, v in d.get("biomass_kg", {}).items()},
            present_since_tick={k: int(v)
                                for k, v in d.get("present_since_tick", {}).items()},
        )
        state.chunk_vegetation[coord] = veg
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "PlantEvolutionState",
    "ChunkVegetation",
    "SpeciationEvent",
    "compute_fitness",
    "install_plant_evolution",
    "tick_plant_evolution",
    "plant_evolution_state",
    "save_plant_state",
    "load_plant_state",
]
