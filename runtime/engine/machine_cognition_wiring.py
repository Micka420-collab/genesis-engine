"""Genesis Engine — Wave 35b cognition wiring for machine_emergence.

Wave 35 livre `machine_emergence` mais laisse l'invocation de
``try_assemble_machine`` au caller (event-driven). Wave 35b ajoute le
**wiring autonome** : quand un agent exécute ``ActionKind.BUILD`` ET
dispose d'au moins 2 matériaux suffisants en inventaire (wood / stone /
metal), un roll ``prf_rng`` scalé par sa ``curiosity`` Big-Five tente
``try_assemble_machine``.

Pattern strictement identique à ``engine.agriculture._ag_global_wrapper``
et ``engine.geology._geology_global_wrapper`` : module-level dispatch
table + monkey-patch stacké de ``engine.cognition.apply_decision``.

Émergence (zéro script)
-----------------------

- Aucun "si agent X alors invente roue". L'agent choisit BUILD via sa
  cognition (Big-Five × needs).
- Le wrapper observe l'inventaire ET tente l'assemblage. Le fingerprint
  émerge des composants disponibles. Le nom CVCV émerge via
  ``prf_rng(seed, "machine", culture, hash(fp))``.
- ``curiosity`` agit comme un gating : agents curieux tentent plus
  souvent que les routiniers. Les agents avec peu de curiosity ne
  découvrent jamais — c'est cohérent avec l'observation
  anthropologique (innovation = trait individuel rare).

Compatibilité avec les autres wrappers
--------------------------------------

Le wrapper s'empile au-dessus d'agriculture, geology, etc. selon l'ordre
d'installation. Chaque module capture l'``apply_decision`` courante
comme ``_X_inner_apply_decision`` puis délègue à ``inner(...)`` pour
les actions non gérées. Le chaînage est LIFO transparent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Quantité minimale par matériau pour qu'il compte comme component.
MIN_COMPONENT_MASS_KG = {
    "wood":  1.0,
    "stone": 2.0,
    "metal": 0.5,
}

# Quantité maximale prélevée pour le component (évite tout consommer).
MAX_COMPONENT_MASS_KG = {
    "wood":  5.0,
    "stone": 10.0,
    "metal": 2.0,
}

# Probabilité de base par BUILD action que l'agent tente l'assemblage.
# Multipliée par curiosity ∈ [0, 1] → p_attempt ∈ [0, base].
ASSEMBLY_ATTEMPT_BASE_PROB = 0.20


# ---------------------------------------------------------------------------
# Dispatch table (module-level, pattern agriculture/geology)
# ---------------------------------------------------------------------------

_MACHINE_DISPATCH: Dict[int, Tuple[object, object]] = {}


# ---------------------------------------------------------------------------
# Wrapper
# ---------------------------------------------------------------------------

def _machine_global_wrapper(agents, row, decision, streamer, tick):
    """Stacked wrapper around the previous ``apply_decision``.

    Délègue d'abord à ``inner(...)`` (autres modules ou native handler),
    puis observe l'action BUILD pour rouler éventuellement
    ``try_assemble_machine``.

    Comme les autres wrappers (agriculture, geology), pas d'effet de
    bord destructif : si l'agent n'a pas les composants, no-op silent.
    """
    import engine.cognition as _cog
    from engine.agent import ActionKind

    inner = getattr(_cog, "_machine_inner_apply_decision", None)
    if inner is None:
        # Sécurité : si le wrapper n'a pas été installé correctement.
        return None

    pair = _MACHINE_DISPATCH.get(id(agents))
    if pair is None:
        return inner(agents, row, decision, streamer, tick)
    sim, _state = pair

    # Déléguer en premier — laisse les autres wrappers handle leurs actions.
    events = inner(agents, row, decision, streamer, tick)

    # Post-hook : si l'action était BUILD, roller pour l'assemblage.
    if int(decision.action) == int(ActionKind.BUILD):
        try:
            _maybe_assemble_machine(sim, agents, row, int(tick))
        except Exception:
            pass

    return events


def _maybe_assemble_machine(sim, agents, row: int, tick: int) -> Optional[str]:
    """Inspect l'inventaire de ``row``, roll, et tente l'assemblage.

    Returns ``None`` si rien tenté ; sinon le ``reason`` retourné par
    ``try_assemble_machine``.
    """
    from engine.machine_emergence import (try_assemble_machine,
                                            MachineComponent)
    from engine.core import prf_rng

    # Inventaire matériaux. Les noms sont stables dans engine.agent.AgentRegistry.
    try:
        inv_wood = float(agents.inv_wood[row])
        inv_stone = float(agents.inv_stone[row])
        inv_metal = float(agents.inv_metal[row])
    except (AttributeError, IndexError):
        return None

    components = []
    if inv_wood >= MIN_COMPONENT_MASS_KG["wood"]:
        components.append(MachineComponent(
            kind="material", id_or_name="wood",
            mass_kg=min(inv_wood, MAX_COMPONENT_MASS_KG["wood"])))
    if inv_stone >= MIN_COMPONENT_MASS_KG["stone"]:
        components.append(MachineComponent(
            kind="material", id_or_name="stone",
            mass_kg=min(inv_stone, MAX_COMPONENT_MASS_KG["stone"])))
    if inv_metal >= MIN_COMPONENT_MASS_KG["metal"]:
        components.append(MachineComponent(
            kind="material", id_or_name="metal",
            mass_kg=min(inv_metal, MAX_COMPONENT_MASS_KG["metal"])))

    if len(components) < 2:
        return None

    # Curiosity gating (Big-Five). Si curiosity absent → assume 0.5 neutral.
    curiosity = 0.5
    try:
        if hasattr(agents, "curiosity") and agents.curiosity is not None:
            curiosity = float(agents.curiosity[row])
    except (AttributeError, IndexError):
        pass

    p_attempt = ASSEMBLY_ATTEMPT_BASE_PROB * max(0.0, min(1.0, curiosity))

    rng = prf_rng(sim.cfg.seed,
                  ["machine_wiring", "attempt"],
                  [tick, row])
    if float(rng.random()) > p_attempt:
        return None

    # Tenter l'assemblage. Pas d'intended_function_kinds (laisse émerger).
    success, reason, _machine = try_assemble_machine(
        sim, row, components, intended_function_kinds=None)
    return reason


# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------

def install_machine_cognition_wiring(sim) -> bool:
    """Idempotent installer.

    1. S'assure que ``engine.machine_emergence`` est installé (idempotent).
    2. Enregistre ``sim`` dans le dispatch table.
    3. Monte le wrapper en haut de la pile ``engine.cognition.apply_decision``
       (et de ``engine.sim.apply_decision`` si présent), exactement
       comme agriculture/geology.

    Returns ``True`` si le wrapper a été installé pour la première fois,
    ``False`` si déjà actif (idempotent).
    """
    from engine.machine_emergence import install_machine_emergence
    state = install_machine_emergence(sim)
    _MACHINE_DISPATCH[id(sim.agents)] = (sim, state)

    import engine.cognition as _cog
    import engine.sim as _sim_mod

    if getattr(_cog, "_machine_inner_apply_decision", None) is not None:
        # Déjà installé globalement. Le dispatch update suffit.
        return False

    _cog._machine_inner_apply_decision = _cog.apply_decision
    _cog.apply_decision = _machine_global_wrapper
    if hasattr(_sim_mod, "apply_decision"):
        _sim_mod.apply_decision = _machine_global_wrapper
    return True


def uninstall_machine_cognition_wiring(sim) -> bool:
    """Detach le wrapper si présent. Restaure l'``apply_decision`` précédente.

    Returns ``True`` si quelque chose a été restauré.
    """
    import engine.cognition as _cog
    import engine.sim as _sim_mod

    _MACHINE_DISPATCH.pop(id(sim.agents), None)

    inner = getattr(_cog, "_machine_inner_apply_decision", None)
    if inner is None:
        return False
    _cog.apply_decision = inner
    _cog._machine_inner_apply_decision = None
    if hasattr(_sim_mod, "apply_decision"):
        _sim_mod.apply_decision = inner
    return True


def machine_cognition_wiring_state(sim) -> Dict[str, object]:
    """Diagnostic : est-ce que le wiring est actif pour cette sim ?"""
    import engine.cognition as _cog
    return {
        "installed_globally": (
            getattr(_cog, "_machine_inner_apply_decision", None) is not None),
        "dispatch_active_for_sim": id(sim.agents) in _MACHINE_DISPATCH,
        "n_sims_in_dispatch": len(_MACHINE_DISPATCH),
        "config": {
            "min_component_mass_kg": MIN_COMPONENT_MASS_KG,
            "max_component_mass_kg": MAX_COMPONENT_MASS_KG,
            "assembly_attempt_base_prob": ASSEMBLY_ATTEMPT_BASE_PROB,
        },
    }


__all__ = [
    "MIN_COMPONENT_MASS_KG",
    "MAX_COMPONENT_MASS_KG",
    "ASSEMBLY_ATTEMPT_BASE_PROB",
    "install_machine_cognition_wiring",
    "uninstall_machine_cognition_wiring",
    "machine_cognition_wiring_state",
]
