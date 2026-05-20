"""HTTP integration — God Observer endpoints."""
from __future__ import annotations

import json
import sys
from http.client import HTTPConnection
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.dashboard import SimController, start_god_server
from engine.sim import Simulation, SimConfig


def _server(sim, ctl):
    return start_god_server(sim, ctl, host="127.0.0.1", port=0)


def test_http_god_state():
    cfg = SimConfig(name="god_http", seed=40, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    ctl = SimController()
    srv, god, log = _server(sim, ctl)
    port = srv.server_port
    try:
        conn = HTTPConnection("127.0.0.1", port, timeout=8)
        conn.request("GET", "/api/god/state")
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        assert resp.status == 200
        assert body.get("visible") is False
        assert "log_size" in body
        assert body["log_size"] == len(log)
        assert god.intervention_count == body.get("intervention_count", 0)
    finally:
        ctl.stop = True
        sim.annalist.close()
        srv.shutdown()


def test_http_god_teleport_post():
    cfg = SimConfig(name="god_tp", seed=41, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    ctl = SimController()
    srv, god, log = _server(sim, ctl)
    port = srv.server_port
    try:
        payload = json.dumps({"x": 12.5, "y": -3.0, "z": 100.0}).encode()
        conn = HTTPConnection("127.0.0.1", port, timeout=8)
        conn.request(
            "POST", "/api/god/teleport",
            body=payload,
            headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
        )
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        assert resp.status == 200
        assert body.get("ok") is True
        assert float(god.pos[0]) == 12.5
        assert float(god.pos[1]) == -3.0
        assert god.intervention_count >= 1
        assert len(log) >= 1
    finally:
        ctl.stop = True
        sim.annalist.close()
        srv.shutdown()
