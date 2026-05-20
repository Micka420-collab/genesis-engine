"""Audio API helpers — snapshot sans serveur HTTP."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.audio_endpoints import audio_history, audio_snapshot
from engine.communication import SoundField
from engine.sim import Simulation, SimConfig
from engine.speech_audio_bridge import emit_vocalize


def test_audio_snapshot_missing_listener():
    cfg = SimConfig(name="aud", seed=5, founders=2, max_agents=8, bounds_km=(0.1, 0.1))
    sim = Simulation(cfg)
    sim.bootstrap()
    sim.sound_field = SoundField()
    out = audio_snapshot(sim, sim.sound_field, {})
    assert out["utterances"] == []
    assert "error" in out


def test_audio_snapshot_by_agent_row():
    cfg = SimConfig(name="aud2", seed=6, founders=2, max_agents=8, bounds_km=(0.1, 0.1))
    sim = Simulation(cfg)
    sim.bootstrap()
    sim.sound_field = SoundField()
    emit_vocalize(sim, 1, sim.agents, {"kind": "vocalize", "from": 0, "to": None, "lex_sig": 42})
    row = 0
    x = float(sim.agents.pos[row, 0])
    y = float(sim.agents.pos[row, 1])
    out = audio_snapshot(sim, sim.sound_field, {"listener_row": str(row)})
    assert out.get("listener") is not None
    assert out["listener"]["x"] == x
    assert out["listener"]["y"] == y


def test_audio_history_invalid_row():
    cfg = SimConfig(name="aud3", seed=7, founders=2, max_agents=8, bounds_km=(0.1, 0.1))
    sim = Simulation(cfg)
    sim.bootstrap()
    sim.sound_field = SoundField()
    out = audio_history(sim, sim.sound_field, {"row": "999", "n": "5"})
    assert out["utterances"] == []
    assert "error" in out
