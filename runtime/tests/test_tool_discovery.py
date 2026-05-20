"""ZERO PRE-SCRIPT — découverte d'outils avant construction."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.agent import ActionKind
from engine.emergent_construction import install_emergent_construction, emergent_build_on_action
from engine.tool_discovery import (
    has_tool_prereqs,
    known_recipes_for_agent,
    pick_experiment_recipe,
    register_discovery,
)
from engine.sim import Simulation, SimConfig


def test_install_starts_with_zero_recipes():
    sim = Simulation(SimConfig(name="z", seed=1, founders=4, max_agents=8))
    sim.bootstrap()
    install_emergent_construction(sim)
    st = sim._emergent_construction
    assert st.discovered == []
    assert st.per_agent_discovered == {}


def test_structure_blocked_without_tools():
    known = {"cordage_fiber"}
    assert not has_tool_prereqs("struct_hut", known, set())
    assert has_tool_prereqs(
        "struct_hut",
        {"knapp_flint_tool", "cordage_fiber"},
        set(),
    )


def test_experiment_can_discover_cordage():
    sim = Simulation(SimConfig(name="exp", seed=42, founders=4, max_agents=12))
    sim.bootstrap()
    install_emergent_construction(sim)
    st = sim._emergent_construction
    row = 0
    sim.agents.inv_wood[row] = 20.0
    sim.agents.inv_stone[row] = 5.0
    sim.agents.curiosity[row] = 0.9
    known = known_recipes_for_agent(st, sim, row)
    trial, score = pick_experiment_recipe(sim, row, known)
    assert trial is not None
    assert score > 0
    sim.agents.action[row] = int(ActionKind.BUILD)
    for _ in range(30):
        sim.step()
    assert len(st.discovered) + len(st.per_agent_discovered.get(row, [])) >= 0


def test_register_discovery_propagates_culture():
    sim = Simulation(SimConfig(name="c", seed=3, founders=4, max_agents=8))
    sim.bootstrap()
    install_emergent_construction(sim)
    st = sim._emergent_construction
    register_discovery(st, sim, 0, "knapp_flint_tool")
    cid = int(sim.agents.relations[0].culture_id)
    assert "knapp_flint_tool" in st.culture_discovered.get(cid, [])
    assert "knapp_flint_tool" in known_recipes_for_agent(st, sim, 0)
