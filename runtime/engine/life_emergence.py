"""Emergent biosphere: appraise → protocells → microbes → fauna → sapients → civilization.

Pipeline (100 % local rules, no scripted founders when ``emergent_origins``)::

    prebiotic substrate (world viability)
        → protocell replication (binary fission + mutation)
        → cyanobacteria (plant_evolution)
        → O₂ rise → plant clades → animal species (phylogeny)
        → primate populations → sapient agents
        → reproduction + civilization stages from observed events

References: autopoietic abiogenesis (self-copying compartments at viable
sites), Earth-analog ancient modes in plant/animal_evolution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from engine.appraise import (AgentAppraisal, appraise_agent, appraise_cell,
                             prebiotic_potential)
from engine.protocell_evolution import (ProtocellState, graduate_to_cyanobacteria,
                                        pool_ready_for_microbes, protocell_snapshot,
                                        tick_protocells)


class BiosphereStage(IntEnum):
    """Taxonomic / evolutionary ladder — detected, never assigned by script."""
    VOID = 0
    PREBIOTIC = 1
    PROTOCELL = 2
    MICROBE = 3
    FLORA = 4
    FAUNA = 5
    SAPient = 6


class CivilizationStage(IntEnum):
    NONE = 0
    FOUNDING = 2
    BAND = 3
    TRIBE = 4
    VILLAGE = 5
    POLITY = 6
    PROTO_STATE = 7


_BIOSPHERE_NAMES = tuple(s.name.lower() for s in BiosphereStage)
_STAGE_NAMES = tuple(s.name.lower() for s in CivilizationStage)

SAPIENT_SPECIES = "monkeys"
SAPIENT_POP_PER_CHUNK = 6
SAPIENT_O2_PCT = 17.5
SAPIENT_COMPLEXITY_MIN = 0.45


@dataclass
class LifeEmergenceConfig:
    enabled: bool = True
    emergent_origins: bool = False
    full_biosphere: bool = True
    max_emergent_founders: int = 2
    min_founder_separation_m: float = 45.0
    substrate_threshold: float = 0.85
    substrate_decay: float = 0.998
    scan_every_ticks: int = 5
    use_emergent_fertility: bool = True
    mate_readiness_min: float = 0.42
    mate_cooldown_ticks: int = 5000


@dataclass
class LifeEmergenceState:
    config: LifeEmergenceConfig
    substrate_by_chunk: Dict[Tuple[int, int, int], float] = field(default_factory=dict)
    protocells: ProtocellState = field(default_factory=ProtocellState)
    biosphere_stage: BiosphereStage = BiosphereStage.VOID
    civilization_stage: CivilizationStage = CivilizationStage.NONE
    emergent_founder_count: int = 0
    last_appraisals: Dict[int, AgentAppraisal] = field(default_factory=dict)
    biosphere_history: List[Tuple[int, str]] = field(default_factory=list)
    stage_history: List[Tuple[int, str]] = field(default_factory=list)
    _next_emergent_idx: int = 0


def wire_life_emergence(sim, cfg: Optional[LifeEmergenceConfig] = None) -> LifeEmergenceState:
    existing: Optional[LifeEmergenceState] = getattr(sim, "_life_emergence", None)
    if existing is not None:
        return existing

    if cfg is None:
        emergent = bool(getattr(sim.cfg, "emergent_origins", False))
        full_bio = bool(getattr(sim.cfg, "full_biosphere", False)) or emergent
        cfg = LifeEmergenceConfig(
            enabled=True,
            emergent_origins=emergent,
            full_biosphere=full_bio,
            max_emergent_founders=max(1, int(getattr(sim.cfg, "max_emergent_founders", 2))),
            substrate_threshold=float(getattr(sim.cfg, "substrate_threshold", 0.85)),
            use_emergent_fertility=bool(getattr(sim.cfg, "life_emergence", True)),
        )

    st = LifeEmergenceState(config=cfg)
    sim._life_emergence = st

    if cfg.full_biosphere and not getattr(sim, "_biosphere_stack_installed", False):
        from engine.biosphere_stack import install_biosphere_stack
        install_biosphere_stack(sim)

    if cfg.use_emergent_fertility and not getattr(sim, "_emergent_fertility_patched", False):
        sim._emergent_fertility_patched = True
        sim._is_fertile_base = sim._is_fertile
        sim._is_fertile = lambda row: emergent_is_fertile(sim, row)

    return st


def tick_life_emergence(sim) -> List[dict]:
    st: Optional[LifeEmergenceState] = getattr(sim, "_life_emergence", None)
    if st is None or not st.config.enabled:
        return []

    events: List[dict] = []
    cfg = st.config

    if sim.tick % cfg.scan_every_ticks == 0:
        _accumulate_substrate(sim, st)
        events.extend(tick_protocells(sim, st.substrate_by_chunk, st.protocells))
        events.extend(_graduate_protocells(sim, st))
        if cfg.emergent_origins:
            events.extend(_try_sapient_emergence(sim, st))
        elif st.config.full_biosphere:
            # Legacy path: direct jump only if biosphere off — disabled when full stack on
            pass

    _detect_biosphere_stage(sim, st)
    _refresh_agent_appraisals(sim, st)
    _update_civilization_stage(sim, st, events)
    return events


def _accumulate_substrate(sim, st: LifeEmergenceState) -> None:
    decay = st.config.substrate_decay
    for coord, chunk in list(sim.streamer.cache.items()):
        cx = float(coord[0] * 32 + 16)
        cy = float(coord[1] * 32 + 16)
        cell = appraise_cell(sim.streamer, cx, cy, sim.tick,
                             drive_accel=int(sim.cfg.drive_accel))
        delta = prebiotic_potential(cell) * 0.002
        prev = st.substrate_by_chunk.get(coord, 0.0) * decay
        st.substrate_by_chunk[coord] = float(np.clip(prev + delta, 0.0, 2.0))


def _graduate_protocells(sim, st: LifeEmergenceState) -> List[dict]:
    events: List[dict] = []
    for coord, pool in list(st.protocells.pools.items()):
        if not pool_ready_for_microbes(pool):
            continue
        if graduate_to_cyanobacteria(sim, coord, pool):
            st.protocells.graduations += 1
            events.append({
                "kind": "microbe_emergence",
                "chunk": coord,
                "clade": "cyanobacteria",
            })
    return events


def _try_sapient_emergence(sim, st: LifeEmergenceState) -> List[dict]:
    """Sapient agents emerge from primate populations — not from raw substrate."""
    events: List[dict] = []
    cfg = st.config
    if st.emergent_founder_count >= cfg.max_emergent_founders:
        return events
    if sim.agents.n_active >= sim.cfg.max_agents:
        return events

    animal_state = getattr(sim, "_animal_state", None)
    plant_state = getattr(sim, "_plant_state", None)
    if animal_state is None:
        return events

    o2 = 0.0
    if plant_state is not None:
        o2 = float(plant_state.oxygen_pct())
    if o2 < SAPIENT_O2_PCT:
        return events

    best: Optional[Tuple[Tuple[int, int, int], int, float]] = None
    for coord, fauna in animal_state.chunk_fauna.items():
        pop = int(fauna.populations.get(SAPIENT_SPECIES, 0))
        if pop < SAPIENT_POP_PER_CHUNK:
            continue
        cx = float(coord[0] * 32 + 16)
        cy = float(coord[1] * 32 + 16)
        cell = appraise_cell(sim.streamer, cx, cy, sim.tick,
                             drive_accel=int(sim.cfg.drive_accel))
        score = pop * cell.viability
        proto = st.protocells.pools.get(coord)
        if proto and proto.mean_complexity > 0:
            score *= (1.0 + proto.mean_complexity * 0.2)
        if best is None or score > best[2]:
            best = (coord, pop, score)

    if best is None:
        return events

    coord, pop, score = best
    x = float(coord[0] * 32 + 16)
    y = float(coord[1] * 32 + 16)
    if not _far_enough_from_agents(sim, x, y, cfg.min_founder_separation_m):
        return events

    st._next_emergent_idx += 1
    idx = st._next_emergent_idx
    row = sim.agents.spawn_founder(sim.cfg.seed, 20_000 + idx, (x, y, 1.0), sim.tick, culture_id=0)
    st.emergent_founder_count += 1

    # Sapients draw down local primate population (ecological cost).
    fauna = animal_state.chunk_fauna.get(coord)
    if fauna and SAPIENT_SPECIES in fauna.populations:
        fauna.populations[SAPIENT_SPECIES] = max(
            0, fauna.populations[SAPIENT_SPECIES] - SAPIENT_POP_PER_CHUNK)

    events.append({
        "kind": "sapient_emergence",
        "row": row,
        "chunk": coord,
        "from_species": SAPIENT_SPECIES,
        "primate_pop": pop,
        "oxygen_pct": o2,
        "score": float(score),
    })
    _set_biosphere(st, sim.tick, BiosphereStage.SAPient)
    return events


def _far_enough_from_agents(sim, x: float, y: float, min_m: float) -> bool:
    for r in range(sim.agents.n_active):
        if not sim.agents.alive[r]:
            continue
        if np.hypot(sim.agents.pos[r, 0] - x, sim.agents.pos[r, 1] - y) < min_m:
            return False
    return True


def _detect_biosphere_stage(sim, st: LifeEmergenceState) -> None:
    if sim.agents.n_active > 0:
        _set_biosphere(st, sim.tick, BiosphereStage.SAPient)
        return

    animal_state = getattr(sim, "_animal_state", None)
    plant_state = getattr(sim, "_plant_state", None)

    fauna_total = 0
    if animal_state:
        for fauna in animal_state.chunk_fauna.values():
            fauna_total += sum(fauna.populations.values())
    if fauna_total > 50:
        _set_biosphere(st, sim.tick, BiosphereStage.FAUNA)
        return

    flora_kg = 0.0
    if plant_state:
        flora_kg = float(plant_state.last_global_biomass_kg)
        if flora_kg > 10.0 or plant_state.oxygen_pct() > 5.0:
            _set_biosphere(st, sim.tick, BiosphereStage.FLORA)
            return
        if "cyanobacteria" in plant_state.available_clades:
            _set_biosphere(st, sim.tick, BiosphereStage.MICROBE)
            return

    proto_total = sum(p.count for p in st.protocells.pools.values())
    if proto_total > 1.0:
        _set_biosphere(st, sim.tick, BiosphereStage.PROTOCELL)
        return

    if st.substrate_by_chunk:
        _set_biosphere(st, sim.tick, BiosphereStage.PREBIOTIC)
        return

    _set_biosphere(st, sim.tick, BiosphereStage.VOID)


def _set_biosphere(st: LifeEmergenceState, tick: int, stage: BiosphereStage) -> None:
    if stage == st.biosphere_stage:
        return
    st.biosphere_stage = stage
    st.biosphere_history.append((tick, _BIOSPHERE_NAMES[int(stage)]))


def emergent_is_fertile(sim, row: int) -> bool:
    st: Optional[LifeEmergenceState] = getattr(sim, "_life_emergence", None)
    cfg = st.config if st else LifeEmergenceConfig()
    if not sim.agents.alive[row]:
        return False
    ap = (st.last_appraisals.get(row) if st else None) or appraise_agent(
        sim.agents, row, sim.streamer, sim.tick, sim)
    if ap.life_stage_idx < 2:
        return False
    if ap.reproduction_readiness < cfg.mate_readiness_min:
        return False
    if sim.agents.hunger[row] > 0.75 or sim.agents.thirst[row] > 0.75:
        return False
    last = int(sim.agents.last_mating_tick[row])
    accel = max(1, int(sim.cfg.drive_accel // 10))
    if last >= 0 and (sim.tick - last) < (cfg.mate_cooldown_ticks // accel):
        return False
    if ap.cell.viability < 0.25:
        return False
    return True


def mate_compatibility(sim, row_a: int, row_b: int) -> float:
    st = getattr(sim, "_life_emergence", None)
    ap_a = (st.last_appraisals.get(row_a) if st else None) or appraise_agent(
        sim.agents, row_a, sim.streamer, sim.tick, sim)
    ap_b = (st.last_appraisals.get(row_b) if st else None) or appraise_agent(
        sim.agents, row_b, sim.streamer, sim.tick, sim)
    aff = sim.agents.relations[row_a].affinity.get(row_b, 0.0)
    world = min(ap_a.cell.viability, ap_b.cell.viability)
    readiness = min(ap_a.reproduction_readiness, ap_b.reproduction_readiness)
    genetic = 1.0
    if row_a in sim.agents.relations[row_b].parents or row_b in sim.agents.relations[row_a].parents:
        genetic = 0.15
    return float(np.clip(
        0.35 * aff + 0.30 * readiness + 0.25 * world + 0.10 * genetic
        + float(sim.agents.agreeableness[row_b]) * 0.05, 0.0, 1.0))


def _update_civilization_stage(sim, st: LifeEmergenceState, tick_events: List[dict]) -> None:
    n_alive = int(sim.agents.alive[:sim.agents.n_active].sum())
    if n_alive == 0:
        return
    stage = CivilizationStage.FOUNDING
    if n_alive >= 3:
        stage = CivilizationStage.BAND
    if n_alive >= 6 and sim.annalist.cum_matings > 0:
        stage = CivilizationStage.TRIBE
    for raw in tick_events:
        k = raw.get("kind")
        if k in ("agriculture_discover", "plant_success", "harvest_success",
                 "build_complete", "structure_stable"):
            stage = max(stage, CivilizationStage.VILLAGE, key=int)
        if k in ("polity_formed", "leader_elected"):
            stage = max(stage, CivilizationStage.POLITY, key=int)
        if k in ("inscription", "smelt_success", "trade_route"):
            stage = max(stage, CivilizationStage.PROTO_STATE, key=int)
    _set_civ_stage(st, sim.tick, stage)


def _set_civ_stage(st: LifeEmergenceState, tick: int, stage: CivilizationStage) -> None:
    if stage == st.civilization_stage:
        return
    st.civilization_stage = stage
    st.stage_history.append((tick, _STAGE_NAMES[int(stage)]))


def _refresh_agent_appraisals(sim, st: LifeEmergenceState) -> None:
    st.last_appraisals.clear()
    n = sim.agents.n_active
    for r in np.flatnonzero(sim.agents.alive[:n]):
        row = int(r)
        st.last_appraisals[row] = appraise_agent(
            sim.agents, row, sim.streamer, sim.tick, sim)


def life_emergence_snapshot(sim) -> Dict[str, Any]:
    st: Optional[LifeEmergenceState] = getattr(sim, "_life_emergence", None)
    if st is None:
        return {}
    pools = list(st.substrate_by_chunk.values())
    snap = {
        "biosphere_stage": _BIOSPHERE_NAMES[int(st.biosphere_stage)],
        "civilization_stage": _STAGE_NAMES[int(st.civilization_stage)],
        "emergent_sapients": st.emergent_founder_count,
        "substrate_cells": len(st.substrate_by_chunk),
        "substrate_max": float(max(pools)) if pools else 0.0,
        "biosphere_history_tail": st.biosphere_history[-10:],
        "stage_history_tail": st.stage_history[-8:],
        "appraised_agents": len(st.last_appraisals),
    }
    snap.update(protocell_snapshot(st.protocells))
    plant_state = getattr(sim, "_plant_state", None)
    if plant_state is not None:
        snap["oxygen_pct"] = round(float(plant_state.oxygen_pct()), 3)
        snap["flora_biomass_kg"] = round(float(plant_state.last_global_biomass_kg), 2)
    animal_state = getattr(sim, "_animal_state", None)
    if animal_state is not None:
        snap["fauna_species"] = len(animal_state.available_species)
        snap["monkeys_global"] = sum(
            f.populations.get(SAPIENT_SPECIES, 0)
            for f in animal_state.chunk_fauna.values())
    return snap


__all__ = [
    "BiosphereStage",
    "CivilizationStage",
    "LifeEmergenceConfig",
    "LifeEmergenceState",
    "wire_life_emergence",
    "tick_life_emergence",
    "emergent_is_fertile",
    "mate_compatibility",
    "life_emergence_snapshot",
    "SAPIENT_SPECIES",
]
