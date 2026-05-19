"""Install the four knowledge layers on a Simulation (opt-in).

1. Physics — gravity, thermo, statics helpers
2. Chemistry — Materials Project bundle + synthesis pipeline
3. Architecture — voxel placement + building_discovery
4. Social — arbitrary typed-edge topologies
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from engine.architecture_layer import install_architecture_layer
from engine.materials_project import install_materials_project
from engine.physics_layer import install_physics_layer
from engine.social_topology import install_social_topology


def install_knowledge_layers(
    sim,
    *,
    physics: bool = True,
    chemistry: bool = True,
    architecture: bool = True,
    social: bool = True,
    mp_bundle_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Idempotent installer for all requested layers."""
    installed: Dict[str, Any] = {}
    if physics:
        installed["physics"] = install_physics_layer(sim)
    if chemistry:
        installed["chemistry"] = install_materials_project(sim, bundle_path=mp_bundle_path)
    if architecture:
        installed["architecture"] = install_architecture_layer(sim)
    if social:
        installed["social"] = install_social_topology(sim)
    sim._knowledge_layers_installed = True
    from engine.knowledge_wiring import wire_knowledge_cognition
    wire_knowledge_cognition(sim)
    return installed


def knowledge_layers_snapshot(sim) -> Dict[str, object]:
    out: Dict[str, object] = {}
    if getattr(sim, "_physics_layer", None):
        from engine.physics_layer import physics_layer_snapshot
        out["physics"] = physics_layer_snapshot(sim)
    if getattr(sim, "_materials_project", None):
        from engine.materials_project import materials_project_snapshot
        out["chemistry"] = materials_project_snapshot(sim)
    if getattr(sim, "_architecture_layer", None):
        from engine.architecture_layer import architecture_layer_snapshot
        out["architecture"] = architecture_layer_snapshot(sim)
    if getattr(sim, "_social_topology", None):
        from engine.social_topology import social_topology_snapshot
        out["social"] = social_topology_snapshot(sim)
    return out


__all__ = ["install_knowledge_layers", "knowledge_layers_snapshot"]
