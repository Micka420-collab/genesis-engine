"""Journal replay API and annalist event tail."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

RUNTIME = Path(__file__).resolve().parents[1]
import sys

if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.annalist import Annalist, Event
from engine.dashboard import (
    SimController,
    enrich_event_for_replay,
    feed_event_tail,
    live_observable_payload,
    live_stream_payload,
    merge_journal_events,
    session_info,
    start_god_server,
)
from engine.sim import Simulation, SimConfig


def test_annalist_last_batch_and_jsonl_tail():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "t.jsonl")
        j = Annalist("sim-test", journal_path=path)
        ev = Event("e1", "sim-test", 1, "birth", ["u1"], (10.0, 20.0, 0.0), {})
        j.journal.append([ev])
        j._last_batch = [ev.to_dict()]
        assert j._last_batch[0]["kind"] == "birth"
        j.close()
        tail = Annalist.read_jsonl_tail(path, 10)
        assert len(tail) == 1
        assert tail[0]["tick"] == 1


def test_enrich_event_for_replay():
    raw = {"participants": ["a"], "location": [1.0, 2.0, 0.0]}
    out = enrich_event_for_replay(raw)
    assert out["positions"]["a"] == [1.0, 2.0]


def test_feed_event_tail_caps():
    ctl = SimController()
    class FakeAnnalist:
        _last_batch = [{"tick": i, "kind": "birth"} for i in range(10)]
    for _ in range(60):
        feed_event_tail(ctl, FakeAnnalist())
    assert len(ctl.last_event_tail) <= 500


def test_merge_journal_events_dedupes():
    live = [{"event_id": "a", "tick": 2, "participants": ["x"], "location": [0, 0, 0]}]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({"event_id": "a", "tick": 2, "participants": ["x"], "location": [0, 0, 0]}) + "\n")
        f.write(json.dumps({"event_id": "b", "tick": 5, "participants": ["y"], "location": [1, 1, 0]}) + "\n")
        path = f.name
    merged = merge_journal_events(live, path, 100)
    os.unlink(path)
    ids = [e["event_id"] for e in merged]
    assert ids.count("a") == 1
    assert "b" in ids


def test_live_stream_payload_shape():
    cfg = SimConfig(name="stream", seed=2, founders=4, max_agents=16, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    p = live_stream_payload(sim)
    assert "tick" in p and "observable" in p
    obs = live_observable_payload(sim)
    assert "tick" in obs


def test_observable_http_endpoint():
    cfg = SimConfig(name="obs_api", seed=3, founders=4, max_agents=16, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    ctl = SimController()
    srv, _, _ = start_god_server(sim, ctl, host="127.0.0.1", port=0)
    port = srv.server_port
    try:
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/observable")
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        assert resp.status == 200
        assert "tick" in body
    finally:
        ctl.stop = True
        sim.annalist.close()
        srv.shutdown()


def test_journal_events_http_endpoint():
    cfg = SimConfig(name="journal_api", seed=1, founders=4, max_agents=20, bounds_km=(0.3, 0.3))
    with tempfile.TemporaryDirectory() as td:
        jpath = os.path.join(td, "live.jsonl")
        sim = Simulation(cfg, journal_path=jpath)
        sim.bootstrap()
        ctl = SimController()
        srv, _, _ = start_god_server(sim, ctl, host="127.0.0.1", port=0)
        port = srv.server_port
        try:
            sim.step()
            feed_event_tail(ctl, sim.annalist)
            conn = HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/api/journal/events?n=50")
            resp = conn.getresponse()
            body = json.loads(resp.read().decode())
            assert resp.status == 200
            assert "events" in body
            conn.request("GET", "/api/session")
            sess = json.loads(conn.getresponse().read().decode())
            assert sess["journal_path"] == jpath
            assert session_info(sim)["sim_id"] == sim.sim_id
        finally:
            ctl.stop = True
            sim.annalist.close()
            srv.shutdown()
