"""P84 — Earth Console lite APIs: wind_field, packed agents, circulation 3D."""
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
    try:
        return resp.status, json.loads(body) if body else {}
    except json.JSONDecodeError:
        return resp.status, {}


def main() -> int:
    print("=" * 78)
    print("P84 — Earth Console lite smoke (vent + packed + circulation)")
    print("=" * 78)
    failures = 0

    with tempfile.TemporaryDirectory() as td:
        jpath = str(Path(td) / "p84.jsonl")
        cfg = SimConfig(
            name="p84_lite",
            seed=0xE84,
            founders=80,
            max_agents=200,
            bounds_km=(0.5, 0.5),
            emergence_subsystems=True,
            emergent_cognition=False,
            hydrology_mode="sv1d",
            graphcast_lite_prior=True,
            wind_advect_agents=True,
        )
        sim = Simulation(cfg, journal_path=jpath)
        gp = GenesisParams(seed=int(cfg.seed) & 0xFFFFFFFFFFFFFFFF, resolution=48)
        bootstrap_genesis_sim(sim, seed=cfg.seed, genesis_params=gp)
        sim.bootstrap()
        wire_emergence_v2(
            sim,
            genome_brain=False,
            graphcast_lite=True,
        )
        for _ in range(20):
            sim.step()

        ctl = SimController()
        srv, _, _ = start_god_server(sim, ctl, host="127.0.0.1", port=0)
        port = srv.server_port
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=8)

            st, state = _get_json(conn, "/api/state")
            ok = st == 200 and state.get("tick", 0) >= 1
            print(_row("GET /api/state", ok, f"tick={state.get('tick')}"))
            failures += 0 if ok else 1

            st, packed = _get_json(conn, "/api/agents?packed=1")
            ok = st == 200 and packed.get("count", 0) >= 1 and packed.get("data_b64")
            print(_row("GET /api/agents?packed=1", ok, f"count={packed.get('count')}"))
            failures += 0 if ok else 1

            st, circ = _get_json(conn, "/api/circulation_state")
            ok = st == 200 and (
                circ.get("live") is not None or circ.get("column_3d", {}).get("installed")
            )
            col = circ.get("column_3d") or {}
            print(_row("GET /api/circulation_state", ok,
                         f"wind={circ.get('live', {}).get('mean_wind_speed_ms')} "
                         f"col3d={col.get('n_columns')}"))
            failures += 0 if ok else 1

            st, wind = _get_json(
                conn,
                "/api/wind_field?xmin=-200&ymin=-200&xmax=200&ymax=200&w=32&h=24",
            )
            ok = st == 200 and bool(wind.get("rgba_b64"))
            print(_row("GET /api/wind_field", ok, f"w={wind.get('w')} h={wind.get('h')}"))
            failures += 0 if ok else 1

            st, prior = _get_json(conn, "/api/world_prior")
            ok = st == 200 and prior.get("applied") is True
            print(_row("GET /api/world_prior", ok, f"rms={prior.get('wind_delta_rms')}"))
            failures += 0 if ok else 1

            conn.request("GET", "/earth_console_webgpu.js")
            js_resp = conn.getresponse()
            ok = js_resp.status == 200
            print(_row("GET /earth_console_webgpu.js", ok))
            failures += 0 if ok else 1

        finally:
            ctl.stop = True
            sim.annalist.close()
            srv.shutdown()

    print("=" * 78)
    print(f"P84 verdict: {'PASS' if failures == 0 else f'{failures} FAIL'}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
