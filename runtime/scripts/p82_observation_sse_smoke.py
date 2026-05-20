"""P82 — observation SSE server smoke (stdlib HTTP)."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P82 — observation SSE smoke")
    print("=" * 78)
    failures = 0
    with tempfile.TemporaryDirectory() as td:
        art = Path(td) / "obs_test.json"
        art.write_text(json.dumps({"experiment": "p82", "tick": 0}),
                       encoding="utf-8")
        from scripts.observation_server import ObservationHandler  # noqa: E402

        ObservationHandler.artifact_path = art
        ObservationHandler.observable_path = None
        payload = ObservationHandler._load_payload(ObservationHandler)
        ok = payload.get("experiment") == "p82"
        print(_row("load_payload", ok, str(payload)[:60]))
        if not ok:
            failures += 1
        ok = hasattr(ObservationHandler, "do_GET")
        print(_row("ObservationHandler API", ok))
        if not ok:
            failures += 1
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
