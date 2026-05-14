"""P2 — Audio endpoints + overlay smoke test.

Boots a tiny Phase 4 sim and starts `start_full_observation_server`. Then:

  1. emits one fake utterance into `sim.sound_field` (so the audio endpoint
     has something to report);
  2. GETs /api/audio?listener_x=0&listener_y=0 → must return 200 + a JSON
     dict listing the audible utterance(s);
  3. GETs /static/audio_overlay.js → must return 200 with the actual JS
     content (so the <script src=…> tag in god_view.html will work);
  4. GETs /api/god/state (fall-through past audio) → must still work;
  5. Verifies god_view.html now references audio_overlay.js.
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

from engine.communication import SpeechVolume, UtteranceKind
from engine.dashboard import SimController, start_full_observation_server
from engine.sim import Simulation, SimConfig


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _get(url, timeout=2.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read(), r.headers.get("Content-Type", "")


def main() -> int:
    cfg = SimConfig(
        name="p2_audio_smoke", seed=0xA0D10,
        founders=4, max_agents=12, bounds_km=(0.3, 0.3),
        spawn_radius_m=15.0, cultures=1, drive_accel=100.0,
    )
    sim = Simulation(cfg)
    sim.bootstrap()
    ctl = SimController(target_tps=10.0)

    port = _free_port()
    srv, god, log, sound_field, knowledge = start_full_observation_server(
        sim, ctl, host="127.0.0.1", port=port,
        static_dir=os.path.join(ROOT, "engine"),
    )
    base = f"http://127.0.0.1:{port}"
    print(f"[p2] full observation server listening on {base}")
    time.sleep(0.15)

    # Seed: emit one utterance close to (0,0) so the audio endpoint has
    # something to listen to.
    u = sound_field.emit(
        speaker_row=0,
        pos=(1.0, 1.0, 1.0),
        tick=int(getattr(sim, "tick", 0)),
        kind=UtteranceKind.GREETING,
        volume=SpeechVolume.SPEAK,
        lex_sig=0xC0FFEE,
        payload={"phonemes": "ka-ta-ni"},
        ttl_ticks=999,
    )
    print(f"[p2] emitted utterance id={u.utterance_id}")

    results = {"pass": True, "checks": []}
    def check(name, ok, detail=""):
        results["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            results["pass"] = False
            print(f"  ❌ {name}: {detail}")
        else:
            print(f"  ✅ {name}")

    try:
        # 1) /api/audio
        code, body, ct = _get(f"{base}/api/audio?listener_x=0&listener_y=0")
        check("GET /api/audio -> 200", code == 200, f"status={code}")
        check("/api/audio returns JSON", "json" in ct, f"ct={ct}")
        payload = json.loads(body.decode("utf-8"))
        check("/api/audio payload is a dict", isinstance(payload, dict),
              f"type={type(payload).__name__}")
        # Common shape: utterances list
        utters = (payload.get("utterances") or payload.get("audible")
                  or payload.get("hearing") or [])
        check("/api/audio reports >=1 utterance",
              isinstance(utters, list) and len(utters) >= 1,
              f"keys={list(payload)[:8]} utters={len(utters)}")

        # 2) /static/audio_overlay.js
        code, body, ct = _get(f"{base}/static/audio_overlay.js")
        check("GET /static/audio_overlay.js -> 200", code == 200,
              f"status={code}")
        check("audio_overlay.js content-type is JS",
              "javascript" in ct, f"ct={ct}")
        check("audio_overlay.js body looks like JS",
              b"audio_overlay" in body or b"(function" in body,
              f"len={len(body)} head={body[:40]!r}")

        # 3) /api/god/state (fall-through past audio + dashboard chain)
        code, body, ct = _get(f"{base}/api/god/state")
        check("GET /api/god/state (fall-through) -> 200",
              code == 200, f"status={code}")

        # 4) god_view.html references the overlay
        with open(os.path.join(ROOT, "engine", "god_view.html"),
                  encoding="utf-8") as f:
            html = f.read()
        check("god_view.html references audio_overlay.js",
              "audio_overlay.js" in html,
              "string not found in HTML")

    finally:
        srv.shutdown()
        srv.server_close()

    print()
    print(json.dumps(results, indent=2))

    if not results["pass"]:
        print("\n❌ P2 SMOKE FAILED")
        return 1
    print("\n✅ P2 SMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
