"""Présence humaine agents."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.agent import ActionKind
from engine.agent_presence import human_presence, POSTURE_BUILD, enrich_lite_agent
from engine.sim import Simulation, SimConfig


def test_build_posture():
    sim = Simulation(SimConfig(name="hp", seed=1, founders=4, max_agents=8))
    sim.bootstrap()
    row = 0
    sim.agents.action[row] = int(ActionKind.BUILD)
    pres = human_presence(sim, row)
    assert pres["posture"] == POSTURE_BUILD
    assert pres["tool"] == "hammer"


def test_enrich_lite_agent():
    sim = Simulation(SimConfig(name="hp2", seed=2, founders=4, max_agents=8))
    sim.bootstrap()
    ag = {"row": 0, "x": 0.0, "y": 0.0, "c": 0, "a": int(ActionKind.WALK_TO), "g": 0}
    sim.agents.vel[0, 0] = 1.2
    enrich_lite_agent(sim, ag)
    assert "posture" in ag
    assert ag["posture"] in ("walk", "run", "idle")
