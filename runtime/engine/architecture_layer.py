"""Architecture émergente — voxel + statique intégrés.

Installe :mod:`building_discovery` et expose placement voxel validé par
:mod:`physics_layer.check_voxel_structure_stable`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from engine.building_discovery import (
    BuildingDiscoveryState,
    install_building_discovery,
    place_block,
)
from engine.physics_layer import check_voxel_structure_stable


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


@dataclass
class ArchitectureLayerState:
    blocks_placed: int = 0
    blocks_rejected_statics: int = 0
    buildings_completed: int = 0
    pending_blocks: Dict[int, List[Tuple[int, int, int, str]]] = field(
        default_factory=dict)


def install_architecture_layer(sim) -> ArchitectureLayerState:
    existing = getattr(sim, "_architecture_layer", None)
    if existing is not None:
        return existing
    install_building_discovery(sim)
    st = ArchitectureLayerState()
    sim._architecture_layer = st
    return st


def agent_place_voxel(
    sim,
    row: int,
    ix: int,
    iy: int,
    iz: int,
    material: str,
) -> Tuple[bool, str]:
    """Place one voxel: statics pre-check then building_discovery."""
    arch: ArchitectureLayerState = sim._architecture_layer

    pending = arch.pending_blocks.setdefault(row, [])
    trial = pending + [(ix, iy, iz, material)]
    ok, reason = check_voxel_structure_stable(trial)
    if not ok:
        arch.blocks_rejected_statics += 1
        return False, reason

    place_block(sim, row, (ix, iy, iz), material)
    pending.append((ix, iy, iz, material))
    arch.blocks_placed += 1
    phy = getattr(sim, "_physics_layer", None)
    if phy is not None:
        from engine.physics_layer import structure_stability_score
        phy.last_stability_score = structure_stability_score(trial)
        phy.structures_checked += 1
        if phy.last_stability_score > 0.15:
            phy.structures_stable += 1
    return True, "placed"


def try_complete_building(sim, row: int) -> Tuple[bool, str]:
    from engine.building_discovery import complete_structure

    arch: ArchitectureLayerState = sim._architecture_layer
    ok, _bid, reason = complete_structure(sim, row)
    if ok:
        arch.buildings_completed += 1
        arch.pending_blocks.pop(row, None)
        return True, reason
    return False, reason


def architecture_layer_snapshot(sim) -> Dict[str, object]:
    st: Optional[ArchitectureLayerState] = getattr(sim, "_architecture_layer", None)
    if st is None:
        return {}
    bd = getattr(sim, "_building_discovery_state", None)
    n_arch = 0
    if bd is not None:
        n_arch = sum(len(v) for v in bd.cultural_archetypes.values())
    return {
        "blocks_placed": st.blocks_placed,
        "blocks_rejected_statics": st.blocks_rejected_statics,
        "buildings_completed": st.buildings_completed,
        "cultural_archetypes": n_arch,
        "agents_with_pending": len(st.pending_blocks),
    }


__all__ = [
    "ArchitectureLayerState",
    "install_architecture_layer",
    "agent_place_voxel",
    "try_complete_building",
    "architecture_layer_snapshot",
]
