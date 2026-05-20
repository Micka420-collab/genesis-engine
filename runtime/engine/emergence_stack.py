"""Wire EMERGENCE SIM v2 stack on a Simulation (idempotent)."""
from __future__ import annotations

from typing import Any, Dict


def wire_emergence_v2(sim, *,
                      genome_brain: bool = True,
                      metrics: bool = True,
                      hydrology_mode: str | None = None,
                      memetic: bool = True,
                      graphcast_lite: bool = False,
                      nca_learned: bool = False,
                      algorithm_lab: bool = False,
                      autonomous_world: bool = False) -> Dict[str, Any]:
    """Enable genome policy + L0 laws + hydrology sv1d + memetic (Earth Console)."""
    out: Dict[str, Any] = {
        "genome_brain": False,
        "metrics": False,
        "earth_laws": False,
        "hydrology": False,
        "memetic": False,
    }

    if genome_brain:
        from engine.emergent_action import install_emergent_cognition
        install_emergent_cognition(sim, enable=True)
        out["genome_brain"] = True

    from engine.earth_laws import install_earth_laws
    install_earth_laws(sim, physics=True)
    out["earth_laws"] = True

    mode = hydrology_mode or getattr(sim.cfg, "hydrology_mode", "sv1d")
    if getattr(sim.cfg, "emergence_subsystems", False):
        from engine.sim_emergence import wire_civilization_emergence
        em = wire_civilization_emergence(
            sim,
            observable_every=max(10, int(getattr(sim.cfg, "observable_every", 25))),
            hydrology_cross_chunk=True,
            hydrology_mode=str(mode),
        )
        em.hydrology_mode = str(mode)
        out["hydrology"] = True
        out["hydrology_mode"] = str(mode)

    if memetic:
        from engine.memetic_engine import install_memetic_engine
        install_memetic_engine(sim)
        out["memetic"] = True

    from engine.atmospheric_circulation import install_atmospheric_circulation
    install_atmospheric_circulation(sim)
    out["circulation"] = True

    if graphcast_lite or nca_learned:
        from engine.deepmind_world_prior import install_deepmind_world_prior
        wp = install_deepmind_world_prior(
            sim,
            graphcast_passes=2,
            nca_learned=nca_learned,
        )
        out["world_prior"] = wp

    if algorithm_lab:
        from engine.algorithm_lab import run_discovery_lab, install_best_operator
        run_discovery_lab(sim, plateau=True)
        out["algorithm_lab"] = install_best_operator(sim)

    from engine.speech_audio_bridge import install_speech_audio
    out["speech_audio"] = install_speech_audio(sim)

    if autonomous_world or getattr(sim.cfg, "autonomous_world", False):
        from engine.autonomous_world import install_autonomous_world
        out["autonomous_world"] = install_autonomous_world(sim)
    elif getattr(sim.cfg, "emergent_construction", False):
        from engine.emergent_construction import install_emergent_construction
        install_emergent_construction(sim)
        out["emergent_construction"] = True

    if metrics and getattr(sim, "_emergence", None) is not None:
        out["metrics"] = True

    sim._emergence_v2 = True
    return out


__all__ = ["wire_emergence_v2"]
