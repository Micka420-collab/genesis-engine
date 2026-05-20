"""HTTP integration — audio, observer_feed, algorithm_lab."""
from __future__ import annotations

import json
import sys
from http.client import HTTPConnection
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.dashboard import SimController, start_god_server
from engine.emergence_stack import wire_emergence_v2
from engine.sim import Simulation, SimConfig
from engine.speech_audio_bridge import install_speech_audio


def _server(sim, ctl):
    return start_god_server(sim, ctl, host="127.0.0.1", port=0)


def _get(port: int, path: str) -> tuple:
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read().decode()
    conn.close()
    return resp.status, json.loads(body) if body else {}


def test_http_audio_endpoint():
    cfg = SimConfig(name="http_aud", seed=20, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    install_speech_audio(sim)
    ctl = SimController()
    srv, _, _ = _server(sim, ctl)
    port = srv.server_port
    try:
        status, body = _get(port, "/api/audio?listener_row=0")
        assert status == 200
        assert "utterances" in body
        assert body.get("listener") is not None
    finally:
        ctl.stop = True
        sim.annalist.close()
        srv.shutdown()


def test_http_observer_feed():
    cfg = SimConfig(
        name="http_obs",
        seed=21,
        founders=6,
        max_agents=20,
        bounds_km=(0.25, 0.25),
        emergence_subsystems=True,
    )
    sim = Simulation(cfg)
    sim.bootstrap()
    wire_emergence_v2(sim, genome_brain=False, autonomous_world=True)
    for _ in range(3):
        sim.step()
    ctl = SimController()
    srv, _, _ = _server(sim, ctl)
    port = srv.server_port
    try:
        status, body = _get(port, "/api/observer_feed?xmin=-200&ymin=-200&xmax=200&ymax=200")
        assert status == 200
        assert "agents" in body or "sites" in body or "counts" in body
    finally:
        ctl.stop = True
        sim.annalist.close()
        srv.shutdown()


def test_http_algorithm_lab_snapshot():
    cfg = SimConfig(
        name="http_lab",
        seed=22,
        founders=4,
        max_agents=12,
        bounds_km=(0.2, 0.2),
        algorithm_lab=True,
    )
    sim = Simulation(cfg)
    sim.bootstrap()
    ctl = SimController()
    srv, _, _ = _server(sim, ctl)
    port = srv.server_port
    try:
        status, body = _get(port, "/api/algorithm_lab")
        assert status == 200
        assert isinstance(body, dict)
    finally:
        ctl.stop = True
        sim.annalist.close()
        srv.shutdown()
