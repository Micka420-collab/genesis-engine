"""Découverte émergente d'outils — ZERO PRE-SCRIPT.

Les agents ne reçoivent aucune recette au départ. Ils **expérimentent** (BUILD/SMELT
choisi par le cerveau), réussissent ou échouent selon la physique, puis mémorisent
outils et techniques par imitation culturelle.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from engine.core import prf_rng
from engine.material_transform import TRANSFORM_RECIPES, can_transform, _local_temp_k
from engine.material_transform import _agent_inventory_map

# Prérequis « outils » avant certaines constructions (pas de quête — physique + mémoire).
TOOL_GATES: Dict[str, Set[str]] = {
    "struct_hearth": {"cordage_fiber"},
    "struct_lean-to": {"cordage_fiber"},
    "struct_hut": {"knapp_flint_tool", "cordage_fiber"},
    "struct_well": {"knapp_flint_tool"},
    "struct_workshop": {"knapp_flint_tool", "fire_clay_ceramic"},
    "struct_kiln": {"fire_clay_ceramic", "charcoal_fuel"},
    "stone_hut": {"knapp_flint_tool"},
    "stone_house": {"knapp_flint_tool", "fire_clay_ceramic"},
    "forge": {"bronze_ingot", "charcoal_fuel"},
    "brick_kiln": {"fire_clay_ceramic"},
}

# Ordre naturel d'expérimentation (matériaux bruts → outils).
TRIAL_TRANSFORM_ORDER: Tuple[str, ...] = (
    "cordage_fiber",
    "knapp_flint_tool",
    "charcoal_fuel",
    "fire_clay_ceramic",
    "bronze_ingot",
)


def agent_artifact_kinds(sim, row: int) -> Set[str]:
    """Outils/objets déjà fabriqués par l'agent."""
    kinds: Set[str] = set()
    mt = getattr(sim, "_material_transform", None)
    if mt is not None:
        for art in mt.artifacts.get(row, []):
            kinds.add(str(art.get("kind", "")))
            kinds.add(str(art.get("recipe", "")))
    return {k for k in kinds if k}


def known_recipes_for_agent(st, sim, row: int) -> Set[str]:
    """Recettes connues (personnel + culture + pool mémétique global)."""
    known: Set[str] = set(st.discovered)
    known.update(st.per_agent_discovered.get(row, []))
    cid = int(sim.agents.relations[row].culture_id)
    known.update(st.culture_discovered.get(cid, []))
    return known


def register_discovery(st, sim, row: int, recipe_key: str) -> bool:
    """Enregistre une découverte — retourne True si nouvelle pour l'agent."""
    if recipe_key not in st.discovered:
        st.discovered.append(recipe_key)
    agent_list = st.per_agent_discovered.setdefault(row, [])
    new_agent = recipe_key not in agent_list
    if new_agent:
        agent_list.append(recipe_key)
    cid = int(sim.agents.relations[row].culture_id)
    cult = st.culture_discovered.setdefault(cid, [])
    if recipe_key not in cult:
        cult.append(recipe_key)
    return new_agent


def has_tool_prereqs(recipe_key: str, known: Set[str], artifacts: Set[str]) -> bool:
    """Vérifie les prérequis outils pour structures / bâtiments réels."""
    need = TOOL_GATES.get(recipe_key)
    if not need:
        return True
    pool = known | artifacts
    return need.issubset(pool)


def score_material_proximity(sim, row: int, recipe_id: str) -> float:
    """0..1 — à quel point l'agent est proche des stocks pour tenter."""
    rec = TRANSFORM_RECIPES.get(recipe_id)
    if rec is None:
        return 0.0
    inv = _agent_inventory_map(sim.agents, row)
    scores: List[float] = []
    for mat, need in rec.inputs.items():
        have = inv.get(mat, 0.0)
        scores.append(min(1.0, have / max(need, 0.01)))
    T = _local_temp_k(sim, row)
    temp_ok = 1.0 if T >= rec.min_temp_k * 0.85 else max(0.0, (T - 250.0) / (rec.min_temp_k - 250.0))
    return min(scores) * temp_ok if scores else 0.0


def pick_experiment_recipe(sim, row: int, known: Set[str]) -> Tuple[Optional[str], float]:
    """Choisit une recette **inconnue** à tenter (curiosité + matériaux)."""
    candidates: List[Tuple[float, str]] = []
    for rid in TRIAL_TRANSFORM_ORDER:
        if rid in known:
            continue
        prox = score_material_proximity(sim, row, rid)
        if prox < 0.12:
            continue
        ok, _ = can_transform(sim, row, rid)
        boost = 0.35 if ok else prox * 0.5
        candidates.append((boost + float(sim.agents.curiosity[row]) * 0.1, rid))
    if not candidates:
        for rid in TRANSFORM_RECIPES:
            if rid in known:
                continue
            prox = score_material_proximity(sim, row, rid)
            if prox >= 0.15:
                candidates.append((prox, rid))
    if not candidates:
        return None, 0.0
    candidates.sort(key=lambda x: -x[0])
    rng = prf_rng(int(sim.cfg.seed), ["tool", "trial"], [row, sim.tick])
    idx = int(rng.integers(0, min(3, len(candidates))))
    return candidates[idx][1], candidates[idx][0]


def pick_known_build(sim, row: int, known: Set[str], catalog: Dict[str, Any]) -> List[Tuple[float, str]]:
    """Recettes déjà connues réalisables — l'agent choisit librement parmi elles."""
    scored: List[Tuple[float, str]] = []
    artifacts = agent_artifact_kinds(sim, row)
    curiosity = float(sim.agents.curiosity[row])
    for key, spec in catalog.items():
        if key not in known:
            continue
        if not has_tool_prereqs(key, known, artifacts):
            continue
        scored.append((0.5 + curiosity * 0.1, key))
    return scored


__all__ = [
    "TOOL_GATES",
    "TRIAL_TRANSFORM_ORDER",
    "agent_artifact_kinds",
    "known_recipes_for_agent",
    "register_discovery",
    "has_tool_prereqs",
    "score_material_proximity",
    "pick_experiment_recipe",
    "pick_known_build",
]
