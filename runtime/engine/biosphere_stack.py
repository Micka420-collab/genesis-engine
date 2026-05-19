"""Install the full emergent biosphere tick chain (photo → flora → fauna).

Called when ``SimConfig.full_biosphere`` is true. All layers use ``ancient``
boot modes so nothing is pre-seeded as Holocene Earth — life must climb
the ladder from chemistry upward.
"""
from __future__ import annotations

from typing import Any, Dict


def install_biosphere_stack(sim) -> Dict[str, Any]:
    """Idempotent: photosynthesis + ancient plant + ancient animal evolution."""
    installed: Dict[str, Any] = {}
    try:
        from engine.photosynthesis import install_photosynthesis
        installed["photosynthesis"] = install_photosynthesis(sim)
    except Exception as exc:
        installed["photosynthesis_error"] = str(exc)

    try:
        from engine.plant_evolution import install_plant_evolution
        # Do not pre-seed all clades — only cyanobacteria after protocell grad.
        st = install_plant_evolution(sim, mode="ancient")
        # Clear auto-seeded cyanobacteria; protocells graduate first.
        if hasattr(st, "chunk_vegetation"):
            st.chunk_vegetation.clear()
        st.available_clades.clear()
        installed["plant_evolution"] = st
    except Exception as exc:
        installed["plant_error"] = str(exc)

    try:
        from engine.animal_evolution import install_animal_evolution
        ast = install_animal_evolution(sim, mode="ancient")
        ast.chunk_fauna.clear()
        installed["animal_evolution"] = ast
    except Exception as exc:
        installed["animal_error"] = str(exc)

    sim._biosphere_stack_installed = True
    return installed


__all__ = ["install_biosphere_stack"]
