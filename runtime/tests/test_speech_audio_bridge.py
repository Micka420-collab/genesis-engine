"""Pont parole → SoundField."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.communication import SoundField
from engine.emergence_stack import wire_emergence_v2
from engine.sim import Simulation, SimConfig
from engine.speech_audio_bridge import (
    emit_vocalize,
    install_speech_audio,
    languages_snapshot,
)


def test_install_emits_vocalize_to_sound_field():
    cfg = SimConfig(name="sp", seed=11, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    wire_emergence_v2(sim, genome_brain=False, autonomous_world=False)
    assert getattr(sim, "_speech_audio_installed", False)
    agents = sim.agents
    raw = {"kind": "vocalize", "from": 0, "to": 1, "lex_sig": 4242}
    sim.annalist.record_tick(1, agents, births=[], deaths=[], raw_events=[raw])
    assert len(sim.sound_field.utterances) >= 1
    u = sim.sound_field.utterances[0]
    assert u.speaker_row == 0
    assert u.lex_sig == 4242


def test_languages_snapshot_cultures():
    cfg = SimConfig(name="sp2", seed=12, founders=6, max_agents=16, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    install_speech_audio(sim)
    snap = languages_snapshot(sim)
    assert snap["n_cultures"] >= 1
    assert snap["cultures"][0]["phonemes"]


def test_emit_vocalize_direct():
    cfg = SimConfig(name="sp3", seed=3, founders=2, max_agents=8, bounds_km=(0.1, 0.1))
    sim = Simulation(cfg)
    sim.bootstrap()
    sim.sound_field = SoundField()
    emit_vocalize(sim, 5, sim.agents, {"kind": "vocalize", "from": 0, "to": None, "lex_sig": 99})
    assert len(sim.sound_field.utterances) == 1
