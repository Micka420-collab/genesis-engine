#!/usr/bin/env python
"""Lightweight SSE observation server for Genesis Engine artifacts.

Streams ``observable.json`` or experiment summary updates to the dashboard.

Usage::

    PYTHONPATH=runtime python runtime/scripts/observation_server.py \\
        --artifacts runtime/artifacts/exp4_catastrophe.json \\
        --port 8765

Then open ``runtime/dashboard.html`` and set SSE URL to
``http://127.0.0.1:8765/events``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class ObservationHandler(BaseHTTPRequestHandler):
    artifact_path: Optional[Path] = None
    observable_path: Optional[Path] = None
    jsonl_path: Optional[Path] = None
    poll_interval_s: float = 1.0

    def log_message(self, fmt: str, *args) -> None:
        pass

    def _read_jsonl_tail(self) -> dict:
        path = self.jsonl_path
        if not path or not path.is_file():
            return {"error": "no jsonl", "ts": time.time()}
        try:
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            if not lines:
                return {"error": "empty jsonl", "ts": time.time()}
            return json.loads(lines[-1])
        except Exception as exc:
            return {"error": repr(exc), "ts": time.time()}

    def _send_json(self, obj: object, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _load_payload(self) -> dict:
        if self.jsonl_path and self.jsonl_path.is_file():
            return self._read_jsonl_tail()
        if self.observable_path and self.observable_path.is_file():
            return json.loads(self.observable_path.read_text(encoding="utf-8"))
        if self.artifact_path and self.artifact_path.is_file():
            return json.loads(self.artifact_path.read_text(encoding="utf-8"))
        return {"error": "no artifact", "ts": time.time()}

    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            self._send_json({"ok": True, "service": "genesis-observation-sse"})
            return
        if self.path == "/snapshot":
            self._send_json(self._load_payload())
            return
        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            last_mtime = -1.0
            while True:
                path = self.jsonl_path or self.observable_path or self.artifact_path
                mtime = path.stat().st_mtime if path and path.is_file() else 0.0
                if mtime != last_mtime:
                    payload = self._load_payload()
                    data = json.dumps(payload)
                    self.wfile.write(f"event: tick\ndata: {data}\n\n".encode())
                    self.wfile.flush()
                    last_mtime = mtime
                time.sleep(self.poll_interval_s)
            return
        self._send_json({"error": "not found"}, status=404)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--artifacts", default=None,
                   help="Path to summary JSON (e.g. artifacts/exp4.json)")
    p.add_argument("--observable", default=None,
                   help="Path to observable.json (live sim)")
    p.add_argument("--jsonl", default=None,
                   help="Tail last line of observable JSONL (live run.py --observe-jsonl)")
    p.add_argument("--interval", type=float, default=1.0,
                   help="SSE poll interval seconds")
    args = p.parse_args()

    ObservationHandler.artifact_path = (
        Path(args.artifacts) if args.artifacts else None)
    ObservationHandler.observable_path = (
        Path(args.observable) if args.observable else None)
    ObservationHandler.jsonl_path = (
        Path(args.jsonl) if args.jsonl else None)
    ObservationHandler.poll_interval_s = float(args.interval)

    if (not ObservationHandler.artifact_path
            and not ObservationHandler.observable_path
            and not ObservationHandler.jsonl_path):
        default = Path(ROOT) / "artifacts" / "exp1_scarcity.json"
        if default.is_file():
            ObservationHandler.artifact_path = default

    httpd = ThreadingHTTPServer(
        (args.host, args.port), ObservationHandler)
    print(f"[observation_server] http://{args.host}:{args.port}/events")
    print(f"[observation_server] snapshot http://{args.host}:{args.port}/snapshot")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[observation_server] stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
