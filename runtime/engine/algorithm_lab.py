"""Algorithm lab — install evolved operators on live simulations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from engine.algorithm_evolution import (
    EvolutionConfig,
    EvolutionResult,
    evaluate_genome,
    evolve_operators,
    improve_until_plateau,
)
from engine.novel_operators import OPERATOR_IDS, OperatorGenome, apply_operator

PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


@dataclass
class AlgorithmLabState:
    runs: int = 0
    best: Optional[OperatorGenome] = None
    last_metrics: Dict[str, float] = field(default_factory=dict)
    history_fitness: List[float] = field(default_factory=list)
    installed: bool = False


def run_discovery_lab(
    sim=None,
    *,
    cfg: Optional[EvolutionConfig] = None,
    plateau: bool = True,
) -> EvolutionResult:
    """Generate → test → select → improve; optionally persist on sim."""
    cfg = cfg or EvolutionConfig()
    if plateau:
        result = improve_until_plateau(cfg)
    else:
        result = evolve_operators(cfg)

    st = getattr(sim, "_algorithm_lab", None) if sim is not None else None
    if st is None and sim is not None:
        st = AlgorithmLabState()
        sim._algorithm_lab = st
    if st is not None:
        st.runs += 1
        st.best = result.best.clone()
        st.history_fitness = list(result.history_best_fitness)
        anchor = getattr(sim.streamer, "genesis", None) if sim else None
        if anchor is not None:
            fit, metrics = evaluate_genome(result.best, anchor.world)
            st.last_metrics = metrics
            result.best.fitness = fit
    return result


def install_best_operator(sim) -> Dict[str, Any]:
    """Apply hall-of-fame operator to Genesis macro world (one-shot + tick hook)."""
    st: Optional[AlgorithmLabState] = getattr(sim, "_algorithm_lab", None)
    if st is None or st.best is None:
        result = run_discovery_lab(sim, plateau=True)
        st = sim._algorithm_lab
        st.best = result.best

    anchor = getattr(sim.streamer, "genesis", None)
    if anchor is None:
        return {"installed": False, "reason": "no_genesis_anchor"}

    genome = st.best.clone()
    activity = apply_operator(genome, anchor.world)
    st.installed = True

    if not getattr(sim, "_algorithm_lab_step_patched", False):
        sim._algorithm_lab_step_patched = True
        orig = sim.step

        def wrapped():
            stats = orig()
            g = st.best
            if g is not None:
                apply_operator(g.clone(), anchor.world)
            return stats

        sim.step = wrapped

    return {
        "installed": True,
        "operator_id": genome.operator_id,
        "params": genome.params,
        "fitness": round(genome.fitness, 5),
        "activity": round(activity, 5),
        "generation": genome.generation,
    }


def algorithm_lab_snapshot(sim) -> Dict[str, Any]:
    st: Optional[AlgorithmLabState] = getattr(sim, "_algorithm_lab", None)
    if st is None:
        return {"runs": 0, "installed": False}
    best = st.best
    return {
        "runs": st.runs,
        "installed": st.installed,
        "history_fitness": st.history_fitness[-12:],
        "last_metrics": st.last_metrics,
        "best": {
            "operator_id": best.operator_id,
            "params": best.params,
            "fitness": round(best.fitness, 5),
            "generation": best.generation,
        } if best else None,
        "operators_available": list(OPERATOR_IDS),
    }


__all__ = [
    "AlgorithmLabState",
    "run_discovery_lab",
    "install_best_operator",
    "algorithm_lab_snapshot",
]
