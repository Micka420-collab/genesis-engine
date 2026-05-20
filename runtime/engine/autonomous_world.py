"""Monde autonome — Terre qui tourne sans orchestrateur IA.

Branche en une passe :
  - Dynamo (noyau, rotation, géothermie, jour/nuit)
  - Plaques tectoniques mobiles
  - Registre propriétés physiques
  - Transformation matériaux → objets
  - Coupler multi-taux (météo, écologie, tectonique)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

PIPELINE_LAYER = "Genesis-L1 World"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


def install_autonomous_world(sim, *, multi_rate: bool = True) -> Dict[str, Any]:
    """Idempotent — le monde évolue seul à chaque tick."""
    if getattr(sim, "_autonomous_world", False):
        return {"skipped": True}
    out: Dict[str, Any] = {}

    from engine.earth_dynamo import install_earth_dynamo
    install_earth_dynamo(sim)
    out["earth_dynamo"] = True

    from engine.plate_tectonics_live import install_plate_tectonics_live
    install_plate_tectonics_live(sim)
    out["plate_tectonics_live"] = True

    from engine.emergent_construction import install_emergent_construction
    install_emergent_construction(sim)
    out["emergent_construction"] = True

    sim._world_physics_registry = True
    out["physics_registry"] = True

    if multi_rate and not getattr(sim, "_coupler_wrapped", False):
        from engine.multi_rate_coupler import (
            DomainConfig,
            TickDomain,
            install_multi_rate_coupler,
        )
        dt = int(getattr(sim.cfg, "drive_accel", 1800))
        install_multi_rate_coupler(sim, configs=[
            DomainConfig(TickDomain.Agent, dt),
            DomainConfig(TickDomain.Weather, 300),
            DomainConfig(TickDomain.Ecology, 86_400),
            DomainConfig(TickDomain.Tectonics, max(dt * 80, 50_000)),
        ])
        _patch_tectonics_handler(sim)
        out["multi_rate_coupler"] = True
    elif getattr(sim, "_coupler_wrapped", False):
        _patch_tectonics_handler(sim)
        out["multi_rate_coupler"] = "patched"

    sim._autonomous_world = True
    return out


def _patch_tectonics_handler(sim) -> None:
    """Replace stub tectonics tick with live plate motion."""
    from engine import multi_rate_coupler as mrc
    from engine.plate_tectonics_live import tick_plate_tectonics_live

    def _live_tectonics(s):
        events = tick_plate_tectonics_live(s)
        st = getattr(s, "_coupler_tectonics", None)
        if st is None:
            st = {}
            s._coupler_tectonics = st
        st["epochs"] = int(st.get("epochs", 0)) + 1
        st["events"] = len(events)
        if hasattr(s, "_coupler") and s._coupler is not None:
            st["domain_tick"] = s._coupler.domain_tick(mrc.TickDomain.Tectonics)

    mrc._DOMAIN_HANDLERS[mrc.TickDomain.Tectonics] = _live_tectonics


def autonomous_world_snapshot(sim) -> Dict[str, Any]:
    from engine.earth_dynamo import dynamo_snapshot
    from engine.plate_tectonics_live import plate_tectonics_snapshot
    from engine.emergent_construction import emergent_construction_snapshot
    from engine.material_transform import material_transform_snapshot
    from engine.world_physics_registry import registry_snapshot

    return {
        "autonomous": bool(getattr(sim, "_autonomous_world", False)),
        "dynamo": dynamo_snapshot(sim),
        "tectonics": plate_tectonics_snapshot(sim),
        "construction": emergent_construction_snapshot(sim),
        "transform": material_transform_snapshot(sim),
        "physics_registry": registry_snapshot(),
    }


__all__ = [
    "install_autonomous_world",
    "autonomous_world_snapshot",
]
