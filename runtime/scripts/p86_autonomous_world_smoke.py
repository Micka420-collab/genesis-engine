"""P86 — Monde autonome : dynamo, plaques, transform matériaux."""
from __future__ import annotations

import io
import json
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


def _row(label: str, ok: bool, detail: str = "") -> str:
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}"


def _get(conn, path):
    conn.request("GET", path)
    r = conn.getresponse()
    return r.status, json.loads(r.read().decode() or "{}")


def main() -> int:
    print("=" * 78)
    print("P86 — Autonomous world smoke")
    print("=" * 78)
    failures = 0

    from engine.dashboard import SimController, start_god_server
    from engine.emergence_stack import wire_emergence_v2
    from engine.genesis_bootstrap import bootstrap_genesis_sim
    from engine.sim import Simulation, SimConfig
    from engine.world_genesis import GenesisParams

    with tempfile.TemporaryDirectory() as td:
        cfg = SimConfig(
            name="p86",
            seed=0xA870_0000,
            founders=30,
            max_agents=80,
            bounds_km=(0.5, 0.5),
            emergence_subsystems=True,
            autonomous_world=True,
        )
        sim = Simulation(cfg, journal_path=str(Path(td) / "p86.jsonl"))
        bootstrap_genesis_sim(sim, seed=cfg.seed, genesis_params=GenesisParams(seed=cfg.seed, resolution=48))
        sim.bootstrap()
        wire_emergence_v2(sim, autonomous_world=True)
        for _ in range(50):
            sim.step()

        ctl = SimController()
        srv, _, _ = start_god_server(sim, ctl, host="127.0.0.1", port=0)
        port = srv.server_port
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=8)
            checks = [
                ("/api/autonomous_world", lambda b: b.get("autonomous") is True),
                ("/api/earth_dynamo", lambda b: b.get("installed")),
                ("/api/plate_tectonics", lambda b: "installed" in b),
                ("/api/emergent_construction", lambda b: b.get("installed")),
                ("/api/material_transform", lambda b: b.get("installed")),
                ("/api/world_physics", lambda b: b.get("n_materials", 0) >= 10),
            ]
            for path, pred in checks:
                st, body = _get(conn, path)
                ok = st == 200 and pred(body)
                print(_row(path, ok, str(body)[:50]))
                failures += 0 if ok else 1
        finally:
            ctl.stop = True
            sim.annalist.close()
            srv.shutdown()

    print("=" * 78)
    print(f"P86 verdict: {'PASS' if failures == 0 else f'{failures} FAIL'}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
