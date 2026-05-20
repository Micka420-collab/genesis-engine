#!/usr/bin/env python3
"""Smoke — observer feed API + Earth Console observer JS (in-process server)."""
from __future__ import annotations

import io
import sys
import tempfile
import traceback
from http.client import HTTPConnection
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from engine.dashboard import SimController, start_god_server  # noqa: E402
from engine.emergence_stack import wire_emergence_v2  # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim  # noqa: E402
from engine.sim import Simulation, SimConfig  # noqa: E402
from engine.world_genesis import GenesisParams  # noqa: E402


def _row(label: str, ok: bool, detail: str = "") -> str:
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}"


def _get_json(conn: HTTPConnection, path: str) -> tuple[int, dict]:
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8", errors="replace")
    import json
    try:
        return resp.status, json.loads(body) if body else {}
    except json.JSONDecodeError:
        return resp.status, {}


def main() -> int:
    print("=" * 78)
    print("P87 — Observer sky smoke (observer_feed + earth_console_observer.js)")
    print("=" * 78)
    failures = 0

    with tempfile.TemporaryDirectory() as td:
        jpath = str(Path(td) / "p87.jsonl")
        cfg = SimConfig(
            name="p87_obs",
            seed=0x087,
            founders=24,
            max_agents=80,
            bounds_km=(0.4, 0.4),
            emergence_subsystems=True,
            autonomous_world=True,
            graphcast_lite_prior=True,
        )
        sim = Simulation(cfg, journal_path=jpath)
        gp = GenesisParams(seed=int(cfg.seed) & 0xFFFFFFFFFFFFFFFF, resolution=40)
        bootstrap_genesis_sim(sim, seed=cfg.seed, genesis_params=gp)
        sim.bootstrap()
        wire_emergence_v2(sim, genome_brain=False, graphcast_lite=True, autonomous_world=True)
        for _ in range(12):
            sim.step()

        ctl = SimController()
        srv, _, _ = start_god_server(sim, ctl, host="127.0.0.1", port=0)
        port = srv.server_port
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=8)

            st, feed = _get_json(
                conn, "/api/observer_feed?xmin=-300&ymin=-300&xmax=300&ymax=300",
            )
            ok = (
                st == 200
                and "sites" in feed
                and "workers" in feed
                and "counts" in feed
            )
            print(_row("GET /api/observer_feed", ok, str(feed.get("counts"))))
            failures += 0 if ok else 1

            conn.request("GET", "/earth_console_observer.js")
            js_resp = conn.getresponse()
            js_body = js_resp.read().decode("utf-8", errors="replace")
            ok = js_resp.status == 200 and "EarthConsoleObserver" in js_body
            print(_row("GET /earth_console_observer.js", ok))
            failures += 0 if ok else 1

            st, audio = _get_json(conn, "/api/audio?listener_row=0")
            ok = st == 200 and "utterances" in audio
            print(_row("GET /api/audio", ok))
            failures += 0 if ok else 1

        finally:
            ctl.stop = True
            sim.annalist.close()
            srv.shutdown()

    print("=" * 78)
    print(f"P87 verdict: {'PASS' if failures == 0 else f'{failures} FAIL'}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
