"""Cognition wiring for knowledge layers (BUILD → voxel, SMELT → synthesis).

Stacks on :func:`engine.cognition.apply_decision` like agriculture/geology
wrappers. Active when ``sim._knowledge_layers_installed`` is set.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

from engine.agent import ActionKind
from engine.material_synthesis import SynthesisConditions
from engine.world import world_to_cell, world_to_chunk

VOXEL_SIZE_M = 0.25

_KNOWLEDGE_DISPATCH: Dict[int, Tuple[object, object]] = {}


def _pick_build_material(agents, row: int) -> Optional[str]:
    stone = float(getattr(agents, "inv_stone", [0])[row])
    wood = float(getattr(agents, "inv_wood", [0])[row])
    if stone >= 0.5:
        return "stone"
    if wood >= 0.5:
        return "wood"
    return None


def _world_to_voxel(px: float, py: float, elev_m: float = 0.0
                    ) -> Tuple[int, int, int]:
    ix = int(px / VOXEL_SIZE_M)
    iy = int(py / VOXEL_SIZE_M)
    iz = max(0, int(elev_m / VOXEL_SIZE_M))
    return ix, iy, iz


def _maybe_build_voxel(sim, agents, row: int) -> Optional[dict]:
    mat = _pick_build_material(agents, row)
    if mat is None:
        return None
    px = float(agents.pos[row, 0])
    py = float(agents.pos[row, 1])
    chunk_c = world_to_chunk(px, py)
    chunk = sim.streamer.get(int(sim.tick), chunk_c)
    cx, cy = world_to_cell(px, py, chunk_c)
    elev = float(chunk.height[cy, cx])
    ix, iy, iz = _world_to_voxel(px, py, elev)

    if hasattr(sim, "_architecture_layer"):
        from engine.architecture_layer import agent_place_voxel
        ok, msg = agent_place_voxel(sim, row, ix, iy, iz, mat)
    else:
        from engine.building_discovery import place_block
        from engine.physics_layer import check_voxel_structure_stable
        place_block(sim, row, (ix, iy, iz), mat)
        ok, msg = True, "placed"

    if not ok:
        return None
    if mat == "stone":
        agents.inv_stone[row] = max(0.0, float(agents.inv_stone[row]) - 0.25)
    else:
        agents.inv_wood[row] = max(0.0, float(agents.inv_wood[row]) - 0.25)
    return {"kind": "voxel_placed", "row": row, "pos": (ix, iy, iz), "material": mat}


def _maybe_smelt(sim, agents, row: int) -> Optional[dict]:
    mp = getattr(sim, "_materials_project", None)
    if mp is None:
        return None
    cu = float(getattr(agents, "inv_copper", [0])[row])
    sn = float(getattr(agents, "inv_tin", [0])[row])
    if cu < 0.1 or sn < 0.05:
        return None
    from engine.materials_project import run_synthesis_pipeline

    tools = ("forge",) if float(getattr(agents, "inv_metal", [0])[row]) > 1.0 else ("fire",)
    temp = 1100.0 if tools == ("fire",) else 1200.0
    reg = getattr(sim, "_synthesis_registry", None)
    mat = run_synthesis_pipeline(
        {"Cu": 0.7, "Sn": 0.3},
        SynthesisConditions(temperature_K=temp, time_s=7200.0, atmosphere="reducing"),
        mp,
        reg,
        tools_available=tools,
    )
    if mat is None:
        return None
    agents.inv_copper[row] = max(0.0, cu - 0.1)
    agents.inv_tin[row] = max(0.0, sn - 0.05)
    agents.inv_bronze[row] = float(getattr(agents, "inv_bronze", [0])[row]) + 0.08
    return {"kind": "smelt_bronze", "row": row, "material": getattr(mat, "name", "bronze")}


def _knowledge_global_wrapper(agents, row, decision, streamer, tick, *args, **kwargs):
    import engine.cognition as _cog

    inner = getattr(_cog, "_knowledge_inner_apply_decision", None)
    if inner is None:
        return None
    pair = _KNOWLEDGE_DISPATCH.get(id(agents))
    if pair is None:
        return inner(agents, row, decision, streamer, tick, *args, **kwargs)
    sim, _state = pair

    act = int(decision.action)
    events = inner(agents, row, decision, streamer, tick, *args, **kwargs)
    if events is None:
        events = []

    if act == int(ActionKind.BUILD):
        if getattr(sim, "_emergent_construction_patched", False):
            return events
        agents.vel[row, :2] = 0.0
        ev = _maybe_build_voxel(sim, agents, row)
        if ev:
            events.append(ev)
        return events
    if act == int(ActionKind.SMELT):
        agents.vel[row, :2] = 0.0
        ev = _maybe_smelt(sim, agents, row)
        if ev:
            events.append(ev)
        return events

    return events


def _knowledge_decide_wrapper(agents, obs, sim=None):
    import engine.cognition as _cog
    from engine.cognition import Decision, DriveKind, ACT_THRESHOLD

    inner = getattr(_cog, "_knowledge_inner_decide", _cog.decide)
    if sim is None or not getattr(sim, "_knowledge_layers_installed", False):
        return inner(agents, obs, sim)

    # ZERO PRE-SCRIPT : pas de « construis un abri » scripté — le cerveau décide.
    if getattr(sim, "_emergent_construction_patched", False):
        return inner(agents, obs, sim)

    row = obs.row
    drives = obs.drives
    cu = float(getattr(agents, "inv_copper", [0])[row])
    sn = float(getattr(agents, "inv_tin", [0])[row])
    if (cu >= 0.1 and sn >= 0.05
            and drives[int(DriveKind.HUNGER)] < 0.55
            and drives[int(DriveKind.THIRST)] < 0.55):
        return Decision(int(ActionKind.SMELT), 0.0, 0.0, 0.7)

    stone = float(agents.inv_stone[row])
    wood = float(agents.inv_wood[row])
    build_mat = stone >= 0.5 or wood >= 0.5
    shelter_need = drives[int(DriveKind.THERMAL)] >= ACT_THRESHOLD * 0.8
    curious = float(agents.curiosity[row]) > 0.45
    if build_mat and (shelter_need or curious):
        return Decision(int(ActionKind.BUILD), obs.pos[0], obs.pos[1], 0.65)

    return inner(agents, obs, sim)


def wire_knowledge_cognition(sim) -> None:
    """Monkey-patch cognition when knowledge layers are installed."""
    import engine.cognition as _cog
    import engine.sim as _sim_mod

    _KNOWLEDGE_DISPATCH[id(sim.agents)] = (sim, None)

    if getattr(_cog, "_knowledge_inner_apply_decision", None) is None:
        _cog._knowledge_inner_apply_decision = _cog.apply_decision
        _cog.apply_decision = _knowledge_global_wrapper
        if hasattr(_sim_mod, "apply_decision"):
            _sim_mod.apply_decision = _knowledge_global_wrapper

    if getattr(_cog, "_knowledge_inner_decide", None) is None:
        _cog._knowledge_inner_decide = _cog.decide
        _cog.decide = _knowledge_decide_wrapper


__all__ = ["wire_knowledge_cognition"]
