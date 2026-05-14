"""P11 — Observatory HUD widget smoke test (Sprint A5).

Builds a world via :class:`WorldBuilder` with the Reality Engine enabled,
ticks the sim for 100 steps, starts the god-view dashboard on port 8770,
then GETs ``/god_view_v2.html`` and verifies the unified Observatory HUD
widget (Sprint A5) is present in the served HTML:

    - HTML must contain  id="observatory-panel"
    - JS  must contain  refreshObservatory  (or equivalent driver fn)

Also verifies the 4 endpoints the widget polls every 3s are alive:
    /api/state, /api/realism_state, /api/lift_state, /api/demography

Architecture ref: Genesis Engine §23 Mode 'God' & Observatoire.
"""
from __future__ import annotations

import io
import json
import os
import socket
import sys
import time
import urllib.request

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.dashboard import SimController, start_god_server
from engine.world_builder import WorldBuilder


def _free_port_or(default: int) -> int:
    """Return ``default`` if free, else any ephemeral port."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", default))
        s.close()
        return default
    except OSError:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port


def _get_text(url: str, timeout: float = 3.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def _get_json(url: str, timeout: float = 3.0):
    code, txt = _get_text(url, timeout=timeout)
    try:
        return code, json.loads(txt)
    except json.JSONDecodeError:
        return code, None


def main() -> int:
    results = {"pass": True, "checks": []}

    def check(name: str, ok: bool, detail: str = "") -> None:
        results["checks"].append({"name": name, "ok": bool(ok),
                                  "detail": detail})
        if not ok:
            results["pass"] = False
            print(f"  [X] {name}: {detail}")
        else:
            print(f"  [OK] {name}")

    # --- Build world with realism layer --------------------------------------
    print("[p11] building world (WorldBuilder + with_realism)...")
    world = (WorldBuilder("p11_observatory_smoke")
             .founders(8).max_agents(40)
             .size_km(0.4).cultures(2)
             .drive_accel(1500.0).seed(0xA50B5)
             .with_5cd(True)
             .with_l2_lift(True)
             .with_realism()
             .build())
    sim = world.sim
    sim.bootstrap()

    # --- Run 100 ticks --------------------------------------------------------
    print("[p11] running 100 ticks...")
    t0 = time.monotonic()
    for _ in range(100):
        sim.step()
    elapsed = time.monotonic() - t0
    print(f"[p11] 100 ticks in {elapsed:.2f}s, alive={world.n_alive}")

    # --- Start god server on 8770 (or fallback) ------------------------------
    port = _free_port_or(8770)
    ctl = SimController(target_tps=10.0)
    srv, god, log = start_god_server(sim, ctl, host="127.0.0.1", port=port)
    base = f"http://127.0.0.1:{port}"
    print(f"[p11] god server listening on {base}")
    time.sleep(0.2)

    try:
        # 1) Fetch the v2 page
        code, html = _get_text(f"{base}/god_view_v2.html")
        check("GET /god_view_v2.html -> 200", code == 200,
              f"status={code}")
        check("html contains id=\"observatory-panel\"",
              'id="observatory-panel"' in html,
              "marker not found")
        check("html contains refreshObservatory driver",
              "refreshObservatory" in html,
              "driver fn missing")
        check("html still contains lift-panel (non-regression)",
              'id="lift-panel"' in html,
              "lift-panel was removed!")
        check("html still contains demo-panel (non-regression)",
              'id="demo-panel"' in html,
              "demo-panel was removed!")

        # 2) Endpoints the widget polls
        code, body = _get_json(f"{base}/api/state")
        check("/api/state -> 200 dict with tick",
              code == 200 and isinstance(body, dict) and "tick" in body,
              f"status={code}")
        code, body = _get_json(f"{base}/api/realism_state")
        check("/api/realism_state -> 200 dict",
              code == 200 and isinstance(body, dict),
              f"status={code}")
        check("/api/realism_state has seasons block",
              isinstance(body, dict) and "seasons" in body,
              f"keys={list(body) if isinstance(body, dict) else '-'}")
        code, body = _get_json(f"{base}/api/lift_state")
        check("/api/lift_state -> 200 dict with veg_distribution",
              code == 200 and isinstance(body, dict)
              and "veg_distribution" in body,
              f"status={code}")
        code, body = _get_json(f"{base}/api/demography")
        check("/api/demography -> 200 dict",
              code == 200 and isinstance(body, dict),
              f"status={code}")

    finally:
        try:
            srv.shutdown()
            srv.server_close()
        except Exception:
            pass

    print()
    print(json.dumps(results, indent=2))
    if not results["pass"]:
        print("\n[X] P11 OBSERVATORY SMOKE FAILED")
        return 1
    print("\n[OK] P11 OBSERVATORY SMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
