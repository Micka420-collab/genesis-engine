"""HTTP dashboard server (stdlib only — no Flask/FastAPI dep).

GET /                 → dashboard HTML
GET /api/state        → snapshot
GET /api/agents       → live agent positions, drives, traits
GET /api/metrics      → full time-series for charts
GET /api/world?cx=&cy=  → height/biome PNG-encoded for god-view
"""
from __future__ import annotations

import io
import json
import os
import struct
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional

import numpy as np

from engine.sim import Simulation


BIOME_COLORS = {
    0: (0, 80, 180),       # OCEAN
    1: (235, 250, 255),    # ICE
    2: (200, 215, 200),    # TUNDRA
    3: (60, 100, 70),      # BOREAL_FOREST
    4: (80, 145, 70),      # TEMPERATE_FOREST
    5: (50, 110, 60),      # TEMPERATE_RAINFOREST
    6: (200, 200, 100),    # GRASSLAND
    7: (240, 215, 145),    # HOT_DESERT
    8: (210, 200, 175),    # COLD_DESERT
    9: (220, 195, 110),    # SAVANNA
    10: (140, 175, 90),    # TROPICAL_DRY_FOREST
    11: (40, 140, 80),     # TROPICAL_RAINFOREST
}


def render_world_png(sim: Simulation, cx: int, cy: int) -> bytes:
    """Render a chunk's biome+height as a PNG (RGBA)."""
    from engine.world import CHUNK_SIZE
    chunk = sim.streamer.get(sim.tick, (cx, cy, 0))
    h, w = CHUNK_SIZE, CHUNK_SIZE
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 3] = 255
    for y in range(h):
        for x in range(w):
            b = int(chunk.biome[y, x])
            r, g, bl = BIOME_COLORS.get(b, (128, 128, 128))
            # shade by elevation
            shade = np.clip(0.5 + chunk.height[y, x] / 4000.0, 0.3, 1.0)
            img[y, x, 0] = int(r * shade)
            img[y, x, 1] = int(g * shade)
            img[y, x, 2] = int(bl * shade)
    return _encode_png(img)


def _encode_png(img: np.ndarray) -> bytes:
    h, w = img.shape[:2]
    raw = b""
    for y in range(h):
        raw += b"\x00" + img[y].tobytes()

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    sim_ref: Simulation = None
    static_dir: str = ""

    def log_message(self, *args, **kwargs):
        pass

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            with open(os.path.join(self.static_dir, "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/state":
            self._json(200, self.sim_ref.snapshot())
            return
        if path == "/api/agents":
            self._json(200, {"agents": self.sim_ref.snapshot_agents()})
            return
        if path == "/api/metrics":
            self._json(200, self.sim_ref.annalist.metrics_to_dict())
            return
        if path == "/api/world":
            qs = dict(p.split("=") for p in self.path.split("?", 1)[1].split("&")) if "?" in self.path else {}
            cx = int(qs.get("cx", 0)); cy = int(qs.get("cy", 0))
            png = render_world_png(self.sim_ref, cx, cy)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(png)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(png)
            return
        if path == "/api/agent":
            qs = dict(p.split("=") for p in self.path.split("?", 1)[1].split("&")) if "?" in self.path else {}
            row = int(qs.get("row", 0))
            self._json(200, self._agent_detail(row))
            return
        self.send_response(404); self.end_headers()

    def _agent_detail(self, row: int) -> dict:
        a = self.sim_ref.agents
        if row < 0 or row >= a.n_active:
            return {"error": "out of range"}
        return {
            "row": row,
            "uuid": str(a.uuid[row]),
            "alive": bool(a.alive[row]),
            "generation": int(a.generation[row]),
            "born_tick": int(a.born_tick[row]),
            "pos": a.pos[row].tolist(),
            "drives": {
                "hunger": float(a.hunger[row]), "thirst": float(a.thirst[row]),
                "sleep": float(a.sleep[row]), "fatigue": float(a.fatigue[row]),
                "thermal": float(a.thermal[row]), "stress": float(a.stress[row]),
                "pain": float(a.pain[row]), "loneliness": float(a.loneliness[row])
            },
            "personality": {
                "openness": float(a.openness[row]), "conscientiousness": float(a.conscientiousness[row]),
                "extraversion": float(a.extraversion[row]), "agreeableness": float(a.agreeableness[row]),
                "neuroticism": float(a.neuroticism[row]), "ambition": float(a.ambition[row]),
                "risk_tolerance": float(a.risk_tolerance[row]), "aggression": float(a.aggression[row]),
                "curiosity": float(a.curiosity[row]), "empathy": float(a.empathy[row]),
                "intelligence": float(a.intelligence[row]),
            },
            "vitality": float(a.vitality[row]), "injuries": float(a.injuries[row]),
            "inventory": {
                "water": float(a.inv_water[row]), "food": float(a.inv_food[row]),
                "wood": float(a.inv_wood[row]), "stone": float(a.inv_stone[row]),
                "metal": float(a.inv_metal[row]), "tools": float(a.inv_tools[row]),
            },
            "offspring": int(a.offspring_count[row]),
            "culture": int(a.relations[row].culture_id),
            "relations_count": len(a.relations[row].affinity),
            "parents": [int(p) if p is not None else None for p in a.parents[row]],
        }


def start_server(sim: Simulation, host: str = "0.0.0.0", port: int = 8080, static_dir: str = "") -> ThreadingHTTPServer:
    _Handler.sim_ref = sim
    _Handler.static_dir = static_dir or os.path.dirname(os.path.abspath(__file__))
    srv = ThreadingHTTPServer((host, port), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv
