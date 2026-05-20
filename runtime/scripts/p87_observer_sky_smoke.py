#!/usr/bin/env python3
"""Smoke — observer feed API (vue du ciel)."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

BASE = "http://127.0.0.1:8090"
TIMEOUT = 90


def get(path: str) -> dict:
    req = urllib.request.Request(BASE + path)
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        try:
            feed = get("/api/observer_feed?xmin=-500&ymin=-500&xmax=500&ymax=500")
            assert "sites" in feed and "workers" in feed
            html = urllib.request.urlopen(
                urllib.request.Request(BASE + "/earth_console_observer.js"), timeout=8,
            ).read().decode()
            assert "EarthConsoleObserver" in html
            print("PASS p87 observer sky smoke", feed.get("counts"))
            return 0
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(1.5)
    print("FAIL p87 — Earth Console not ready", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
