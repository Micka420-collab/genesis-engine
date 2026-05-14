"""P1 — God Avatar wiring smoke test.

Boots a tiny Phase 4 sim, starts `start_god_server`, then exercises the
three endpoints required by `NEXT-SPRINT.md` P1:

    GET  /api/god/state
    POST /api/god/teleport
    POST /api/god/visibility

Pass = all three return 2xx with the expected JSON shape, and the
in-process `GodInterventionLog` records the two POST interventions.

Bonus: also verifies the dashboard's pre-existing /api/state still works
(fall-through from god_endpoints monkey-patch did not break it).
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.dashboard import SimController, start_god_server
from engine.sim import Simulation, SimConfig


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _get(url: str, timeout=2.0):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def _post(url: str, body: dict, timeout=2.0):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def main() -> int:
    cfg = SimConfig(
        name="p1_god_smoke", seed=0xBEEF,
        founders=4, max_agents=20,
        bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
        cultures=1, drive_accel=200.0,
    )
    sim = Simulation(cfg)
    sim.bootstrap()
    ctl = SimController(target_tps=10.0)

    port = _free_port()
    srv, god, log = start_god_server(sim, ctl, host="127.0.0.1", port=port)
    base = f"http://127.0.0.1:{port}"
    print(f"[p1] god server listening on {base}")
    time.sleep(0.15)   # let the listener spin up

    results = {"pass": True, "checks": []}

    def check(name, ok, detail=""):
        results["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            results["pass"] = False
            print(f"  ❌ {name}: {detail}")
        else:
            print(f"  ✅ {name}")

    try:
        # 1) GET /api/god/state
        code, body = _get(f"{base}/api/god/state")
        check("GET /api/god/state -> 200", code == 200, f"status={code}")
        check("god state has pos field",
              isinstance(body, dict) and "pos" in body,
              f"body={list(body)[:6] if isinstance(body, dict) else type(body)}")
        check("god state has visible field",
              isinstance(body, dict) and ("visible" in body or "is_visible" in body),
              f"body keys={list(body)[:8] if isinstance(body, dict) else '-'}")

        # 2) POST /api/god/teleport
        code, body = _post(f"{base}/api/god/teleport",
                           {"x": 12.5, "y": -3.0, "z": 0.0})
        check("POST /api/god/teleport -> 2xx", 200 <= code < 300,
              f"status={code} body={body}")
        # in-process introspection
        check("god.pos updated to teleport target",
              abs(float(god.pos[0]) - 12.5) < 1e-3
              and abs(float(god.pos[1]) - (-3.0)) < 1e-3,
              f"god.pos={list(god.pos)}")

        # 3) POST /api/god/visibility
        code, body = _post(f"{base}/api/god/visibility", {"visible": True})
        check("POST /api/god/visibility -> 2xx", 200 <= code < 300,
              f"status={code} body={body}")
        check("god.visible flipped to True",
              bool(getattr(god, "visible", getattr(god, "is_visible", False))),
              f"god.visible={getattr(god, 'visible', '?')}")

        # 4) Interventions logged?
        log_n = len(log)
        check("GodInterventionLog recorded at least 2 entries",
              log_n >= 2, f"len(log)={log_n}")
        recent = log.recent(5)
        check("intervention log .recent() returns dicts",
              isinstance(recent, list) and recent and isinstance(recent[0], dict),
              f"recent={recent[:1]}")
        kinds = {e.get("kind") for e in recent}
        check("teleport+visibility logged",
              "teleport" in kinds and "visibility" in kinds,
              f"kinds_seen={kinds}")

        # 5) Fall-through: an existing dashboard route must still work.
        code, body = _get(f"{base}/api/events/recent?n=5")
        check("GET /api/events/recent (fall-through) -> 200", code == 200,
              f"status={code}")

    finally:
        srv.shutdown()
        srv.server_close()

    print()
    print(json.dumps(results, indent=2))

    if not results["pass"]:
        print("\n❌ P1 SMOKE FAILED")
        return 1
    print("\n✅ P1 SMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
