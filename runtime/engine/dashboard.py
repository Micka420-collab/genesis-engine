"""HTTP god-view dashboard server (stdlib only).

Endpoints
---------
GET  /                       → god-view HTML
GET  /index_classic.html     → legacy compact dashboard
GET  /api/state              → simulation snapshot
GET  /api/agents             → live agent positions, drives, traits
GET  /api/metrics            → full time-series for charts
GET  /api/lift_state         → L2 lift layer state (chunks, veg distribution, max ravine depth)
GET  /api/realism_state      → Reality Engine: hydrology, wildlife, trails, seasons, disease
GET  /api/world_model_capabilities → taxonomy table per ADR-0005 (Genesis L1-L5 × paper-L1/L2/L3)
GET  /api/physiology_state   → Wave 3 physiology: excretion, hygiene, skin, disease loads
GET  /api/photosynthesis_state → Wave 4 GPP: global + per-biome kcal/tick, Ca, PAR, T
GET  /api/material_aging_state → Wave 4 material aging: alive/destroyed counts, integrity
GET  /api/marine_state       → Wave 5 marine: tides, currents, plankton/fish/predator totals
GET  /api/global_world_state → Phase 15 inter-region: attached sims, shared atmosphere, clock, migration count
GET  /api/plant_evolution_state → Wave 6 plant evolution: 40-clade phylogeny, biomass, speciation, O2
GET  /api/meteorology_state  → Wave 7 weather: clouds, rain, wind, UV, storms, solar zenith
GET  /api/animal_evolution_state → Wave 8 fauna: 50 species populations, predation, trophic stats
GET  /api/agriculture_state  → Phase 4 agriculture: cultivated fields, harvests, seed libraries
GET  /api/writing_state      → Phase 4 writing: inscriptions, legibility, culture knowledge banks
GET  /api/polity_state       → Phase 4 polity: emergent proto-governments, taxation, redistribution
GET  /api/geology_state      → Wave 10 geology: strata columns, mineral extraction stats
GET  /api/demography         → lineage tree size, generations, cultures, top progenitors
GET  /api/agent?row=N        → one-agent detail
GET  /api/world?cx=&cy=      → one-chunk PNG (legacy)
GET  /api/render?xmin&ymin&xmax&ymax&w&h&overlay=  → bbox PNG with terrain
GET  /api/groups             → list of formed groups with centroids
GET  /api/events/recent?n=   → recent events tail
GET  /api/control?status=1   → control state (paused / speed)
POST /api/control            → {"action":"pause"|"play"|"step"|"speed","speed":1.0}
POST /api/timewarp           → {"mode":"realtime"|"x10"|"x100"|"x1000"|"milestone"}
"""
from __future__ import annotations

import io
import json
import math
import os
import struct
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.sim import Simulation
from engine.sim_lift import lift_state
try:
    from engine.realism import realism_state
except Exception:  # pragma: no cover
    realism_state = None  # type: ignore[assignment]
try:
    from engine.world_model_capabilities import world_model_capabilities
except Exception:  # pragma: no cover
    world_model_capabilities = None  # type: ignore[assignment]
try:
    from engine.physiology import physiology_state
except Exception:  # pragma: no cover
    physiology_state = None  # type: ignore[assignment]
try:
    from engine.photosynthesis import photosynthesis_state
except Exception:  # pragma: no cover
    photosynthesis_state = None  # type: ignore[assignment]
try:
    from engine.material_aging import material_aging_state
except Exception:  # pragma: no cover
    material_aging_state = None  # type: ignore[assignment]
try:
    from engine.marine import marine_state
except Exception:  # pragma: no cover
    marine_state = None  # type: ignore[assignment]
try:
    from engine.global_world import GlobalWorld
except Exception:  # pragma: no cover
    GlobalWorld = None  # type: ignore[assignment]
try:
    from engine.plant_evolution import plant_evolution_state
except Exception:  # pragma: no cover
    plant_evolution_state = None  # type: ignore[assignment]
try:
    from engine.meteorology import meteorology_state
except Exception:  # pragma: no cover
    meteorology_state = None  # type: ignore[assignment]
try:
    from engine.animal_evolution import animal_evolution_state
except Exception:  # pragma: no cover
    animal_evolution_state = None  # type: ignore[assignment]
try:
    from engine.agriculture import agriculture_state
except Exception:  # pragma: no cover
    agriculture_state = None  # type: ignore[assignment]
try:
    from engine.writing import writing_state
except Exception:  # pragma: no cover
    writing_state = None  # type: ignore[assignment]
try:
    from engine.polity import polity_state
except Exception:  # pragma: no cover
    polity_state = None  # type: ignore[assignment]
try:
    from engine.geology import geology_state
except Exception:  # pragma: no cover
    geology_state = None  # type: ignore[assignment]
try:
    from engine.metallurgy import metallurgy_state
except Exception:  # pragma: no cover
    metallurgy_state = None  # type: ignore[assignment]
try:
    from engine.realistic_construction import realistic_construction_state
except Exception:  # pragma: no cover
    realistic_construction_state = None  # type: ignore[assignment]
from engine.world import CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M


def _json_default(obj):
    """Fallback encoder so numpy scalars / arrays / bytes don't break json.dumps.

    Used by ``_Handler._json`` to keep dashboard responses robust when a
    snapshot accidentally leaks a numpy type. Returns a plain-Python value.
    """
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.hex()
        except Exception:
            return repr(obj)
    if isinstance(obj, set):
        return list(obj)
    return str(obj)


# ---------------------------------------------------------------------------
# Biome palette
# ---------------------------------------------------------------------------

BIOME_COLORS = {
    0: (0, 80, 180),
    1: (235, 250, 255),
    2: (200, 215, 200),
    3: (60, 100, 70),
    4: (80, 145, 70),
    5: (50, 110, 60),
    6: (200, 200, 100),
    7: (240, 215, 145),
    8: (210, 200, 175),
    9: (220, 195, 110),
    10: (140, 175, 90),
    11: (40, 140, 80),
}


def _encode_png(img: np.ndarray) -> bytes:
    h, w = img.shape[:2]
    # Flatten with row filter bytes prepended
    rows = np.zeros((h, w * 4 + 1), dtype=np.uint8)
    rows[:, 1:] = img.reshape(h, w * 4)
    raw = rows.tobytes()

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


def render_chunk_png(sim: Simulation, cx: int, cy: int) -> bytes:
    """Legacy: render a single chunk's biome+height as PNG."""
    chunk = sim.streamer.get(sim.tick, (cx, cy, 0))
    h, w = CHUNK_SIZE, CHUNK_SIZE
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 3] = 255
    palette = np.array([BIOME_COLORS.get(i, (128, 128, 128)) for i in range(12)], dtype=np.float32)
    biome_int = chunk.biome.astype(np.int32)
    biome_int = np.clip(biome_int, 0, 11)
    cols = palette[biome_int]
    shade = np.clip(0.5 + chunk.height / 4000.0, 0.3, 1.0)
    img[..., 0] = (cols[..., 0] * shade).astype(np.uint8)
    img[..., 1] = (cols[..., 1] * shade).astype(np.uint8)
    img[..., 2] = (cols[..., 2] * shade).astype(np.uint8)
    return _encode_png(img)


def render_bbox_png(sim: Simulation, xmin: float, ymin: float, xmax: float, ymax: float,
                    out_w: int, out_h: int, overlay: str = "") -> bytes:
    """Render an arbitrary world bbox at requested image resolution.

    Composes every chunk that intersects the bbox into a single image.
    Biome color × elevation shading; water cells get a blue tint overlay.
    """
    out_w = max(8, min(out_w, 2048))
    out_h = max(8, min(out_h, 2048))
    img = np.zeros((out_h, out_w, 4), dtype=np.uint8)
    img[..., 3] = 255

    span_x = max(xmax - xmin, 1e-3)
    span_y = max(ymax - ymin, 1e-3)
    # For each output pixel, compute world-coord, then chunk + cell.
    # Vectorise: build XX, YY world arrays.
    px = (np.arange(out_w, dtype=np.float32) + 0.5) / out_w * span_x + xmin
    py = (np.arange(out_h, dtype=np.float32) + 0.5) / out_h * span_y + ymin
    XX, YY = np.meshgrid(px, py, indexing="xy")
    # YY is image row → world Y; flip so that Y_up convention matches canvas.
    # We render with image row 0 at YY[0]==ymin; caller should pass ymax/ymin
    # consistent with the canvas convention.

    cx_arr = np.floor(XX / CHUNK_SIDE_M).astype(np.int32)
    cy_arr = np.floor(YY / CHUNK_SIDE_M).astype(np.int32)

    biome_out = np.zeros((out_h, out_w), dtype=np.int32)
    height_out = np.zeros((out_h, out_w), dtype=np.float32)
    water_out = np.zeros((out_h, out_w), dtype=np.float32)
    # Overlays that sample per-cell live state when requested.
    gpp_out = np.zeros((out_h, out_w), dtype=np.float32)
    food_out = np.zeros((out_h, out_w), dtype=np.float32)
    food_cap_out = np.zeros((out_h, out_w), dtype=np.float32)
    wood_out = np.zeros((out_h, out_w), dtype=np.float32)

    photo_state = getattr(sim, "_photo_state", None)
    photo_caches = (photo_state.chunk_caches
                    if photo_state is not None else {})
    marine_state_obj = getattr(sim, "_marine_state", None)
    marine_currents = (marine_state_obj.currents
                       if marine_state_obj is not None else {})

    # Marine-overlay scratch fields, only populated when the overlay is
    # requested. Allocated unconditionally so the indexing below stays
    # straightforward (cheap : two float arrays the size of the image).
    current_speed_out = np.zeros((out_h, out_w), dtype=np.float32)
    ocean_mask_out = np.zeros((out_h, out_w), dtype=bool)

    # Wave 7 meteorology overlays — per-chunk single values broadcast over
    # the chunk's pixels.
    meteo_state_obj = getattr(sim, "_meteo_state", None)
    meteo_chunks = (meteo_state_obj.chunk_meteo
                    if meteo_state_obj is not None else {})
    cloud_out = np.zeros((out_h, out_w), dtype=np.float32)
    precip_out = np.zeros((out_h, out_w), dtype=np.float32)
    uv_out = np.zeros((out_h, out_w), dtype=np.float32)
    wind_speed_out = np.zeros((out_h, out_w), dtype=np.float32)
    temp_out = np.zeros((out_h, out_w), dtype=np.float32)

    # Determine unique chunks
    pairs = np.stack([cx_arr.ravel(), cy_arr.ravel()], axis=1)
    uniq = np.unique(pairs, axis=0)
    for ccx, ccy in uniq:
        coord = (int(ccx), int(ccy), 0)
        try:
            ch = sim.streamer.get(sim.tick, coord)
        except Exception:
            continue
        # Mask of output pixels that map into this chunk
        mask = (cx_arr == ccx) & (cy_arr == ccy)
        # Local cell index inside the chunk
        lx_w = XX[mask] - ccx * CHUNK_SIDE_M
        ly_w = YY[mask] - ccy * CHUNK_SIDE_M
        ix = np.clip((lx_w / VOXEL_SIZE_M).astype(np.int32), 0, CHUNK_SIZE - 1)
        iy = np.clip((ly_w / VOXEL_SIZE_M).astype(np.int32), 0, CHUNK_SIZE - 1)
        biome_out[mask] = ch.biome[iy, ix].astype(np.int32)
        height_out[mask] = ch.height[iy, ix]
        water_out[mask] = ch.water[iy, ix]
        food_out[mask] = ch.food_kcal[iy, ix]
        food_cap_out[mask] = ch.food_capacity[iy, ix]
        wood_out[mask] = ch.wood[iy, ix]
        # GPP overlay : look up the photo cache for this chunk if available.
        gpp_cache = photo_caches.get(coord)
        if gpp_cache is not None and gpp_cache.last_gpp_umol is not None:
            gpp_out[mask] = gpp_cache.last_gpp_umol[iy, ix]
        # Marine overlay : per-cell current speed magnitude on OCEAN cells.
        cf = marine_currents.get(coord)
        if cf is not None:
            speed = np.sqrt(cf.u * cf.u + cf.v * cf.v).astype(np.float32)
            current_speed_out[mask] = speed[iy, ix]
            ocean_mask_out[mask] = cf.ocean_mask[iy, ix]
        # Wave 7 meteorology — single value per chunk broadcast.
        mc = meteo_chunks.get(coord)
        if mc is not None:
            cloud_out[mask] = mc.cloud_cover
            precip_out[mask] = mc.precip_mm_h
            uv_out[mask] = mc.uv_index
            wind_speed_out[mask] = mc.wind_speed_ms
            temp_out[mask] = mc.temp_c

    palette = np.array([BIOME_COLORS.get(i, (128, 128, 128)) for i in range(12)],
                       dtype=np.float32)
    biome_clipped = np.clip(biome_out, 0, 11)
    cols = palette[biome_clipped]
    # Elevation shading
    shade = np.clip(0.45 + height_out / 4000.0, 0.30, 1.05)[..., None]
    cols = cols * shade
    # Water overlay (blue tint where water > 5 L/cell)
    water_mask = water_out > 5.0
    cols[water_mask] = cols[water_mask] * 0.4 + np.array([20, 80, 180], np.float32) * 0.6

    # ---- Overlay modes ----------------------------------------------------
    # Comma-separated; e.g. ``overlay=ndvi,water``. Stacked in order.
    overlay_set = set(o.strip() for o in (overlay or "").split(",") if o.strip())

    if "ndvi" in overlay_set:
        # NDVI proxy: forest-style green intensity from food_capacity / wood.
        ndvi = np.clip(
            (food_cap_out / 200.0) * 0.5 + (wood_out / 80.0) * 0.5,
            0.0, 1.0)[..., None]
        green = np.array([30, 175, 70], np.float32)
        brown = np.array([135, 95, 55], np.float32)
        veg_col = green * ndvi + brown * (1.0 - ndvi)
        cols = cols * 0.35 + veg_col * 0.65

    if "gpp" in overlay_set:
        # Live primary production intensity. Hot yellow-green for high GPP,
        # neutral brown when zero.
        gpp_norm = np.clip(gpp_out / 30.0, 0.0, 1.0)[..., None]
        hi = np.array([235, 240, 80], np.float32)
        lo = np.array([90, 75, 50], np.float32)
        cols = cols * (1.0 - gpp_norm) + (hi * gpp_norm + lo * (1.0 - gpp_norm)) * gpp_norm

    if "food" in overlay_set:
        # Current standing food (after consumption + regen).
        food_norm = np.clip(food_out / 200.0, 0.0, 1.0)[..., None]
        warm = np.array([255, 180, 80], np.float32)
        cols = cols * (1.0 - food_norm * 0.7) + warm * (food_norm * 0.7)

    if "marine" in overlay_set:
        # Wave 5 marine overlay : colour OCEAN cells by current speed.
        # Deep blue at 0 m/s, bright cyan at the CURRENT_MAX_MS cap. We
        # import locally to avoid a hard module dependency on import.
        try:
            from engine.marine import CURRENT_MAX_MS as _CMAX
        except Exception:
            _CMAX = 1.5
        speed_norm = np.clip(current_speed_out / max(_CMAX, 1e-3),
                             0.0, 1.0)[..., None]
        deep_blue = np.array([10, 35, 110], np.float32)
        bright_cyan = np.array([40, 220, 240], np.float32)
        marine_col = deep_blue * (1.0 - speed_norm) + bright_cyan * speed_norm
        m3 = ocean_mask_out[..., None]
        cols = np.where(m3, marine_col, cols)

    if "elev" in overlay_set:
        # Greyscale elevation, sharp contrast.
        elev = np.clip(height_out / 3000.0, 0.0, 1.0)[..., None]
        grey = np.array([240, 240, 240], np.float32)
        dark = np.array([40, 40, 40], np.float32)
        cols = cols * 0.30 + (grey * elev + dark * (1.0 - elev)) * 0.70

    if "clouds" in overlay_set:
        # Wave 7 — white veil for cloud cover, darker where dense.
        cc = np.clip(cloud_out, 0.0, 1.0)[..., None]
        white = np.array([240, 240, 240], np.float32)
        cols = cols * (1.0 - 0.55 * cc) + white * (0.55 * cc)

    if "precip" in overlay_set:
        # Wave 7 — blue stripes for rain/snow intensity.
        p = np.clip(precip_out / 20.0, 0.0, 1.0)[..., None]
        blue = np.array([80, 130, 240], np.float32)
        cols = cols * (1.0 - 0.6 * p) + blue * (0.6 * p)

    if "uv" in overlay_set:
        # Wave 7 — purple intensity for UV index 0..11+.
        uv = np.clip(uv_out / 11.0, 0.0, 1.0)[..., None]
        purple = np.array([200, 60, 220], np.float32)
        cols = cols * (1.0 - 0.5 * uv) + purple * (0.5 * uv)

    if "wind" in overlay_set:
        # Wave 7 — green to red gradient by wind speed (m/s).
        ws = np.clip(wind_speed_out / 25.0, 0.0, 1.0)[..., None]
        calm = np.array([60, 140, 80], np.float32)
        gust = np.array([220, 50, 30], np.float32)
        wind_col = calm * (1.0 - ws) + gust * ws
        cols = cols * 0.45 + wind_col * 0.55

    if "temperature" in overlay_set or "temp" in overlay_set:
        # Wave 7 — blue (cold) → red (hot) gradient. Centred ~15 °C.
        t = np.clip((temp_out - (-10.0)) / 50.0, 0.0, 1.0)[..., None]
        cold = np.array([60, 100, 220], np.float32)
        hot = np.array([240, 60, 40], np.float32)
        temp_col = cold * (1.0 - t) + hot * t
        cols = cols * 0.40 + temp_col * 0.60

    img[..., 0] = np.clip(cols[..., 0], 0, 255).astype(np.uint8)
    img[..., 1] = np.clip(cols[..., 1], 0, 255).astype(np.uint8)
    img[..., 2] = np.clip(cols[..., 2], 0, 255).astype(np.uint8)

    return _encode_png(img)


# ---------------------------------------------------------------------------
# Sim control shared state
# ---------------------------------------------------------------------------

class SimController:
    """Shared between the HTTP handler thread and the sim-loop thread."""
    def __init__(self, target_tps: float = 10.0):
        self.lock = threading.Lock()
        self.paused = False
        self.speed = 1.0       # multiplier on target_tps
        self.target_tps = target_tps
        self.single_step = False  # consumed by sim-loop
        self.stop = False
        self.last_event_tail: List[dict] = []  # capped journal tail

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "paused": self.paused, "speed": float(self.speed),
                "target_tps": float(self.target_tps),
                "effective_tps": 0.0 if self.paused else float(self.target_tps * self.speed),
            }

    def apply(self, action: str, value: Optional[float] = None) -> dict:
        with self.lock:
            if action == "pause":
                self.paused = True
            elif action == "play":
                self.paused = False
            elif action == "step":
                self.single_step = True
                self.paused = True
            elif action == "speed":
                if value is not None:
                    self.speed = float(max(0.1, min(100.0, value)))
            elif action == "stop":
                self.stop = True
            return self.snapshot()


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    sim_ref: Simulation = None
    ctl_ref: SimController = None
    static_dir: str = ""

    def log_message(self, *args, **kwargs):
        pass

    def _json(self, code: int, payload: dict) -> None:
        try:
            body = json.dumps(payload, default=_json_default).encode("utf-8")
        except Exception as exc:
            # Surface serialisation failures as a 500 with a parseable body
            # instead of half-sending a 200 (which manifests as "empty body").
            err = json.dumps({"error": "serialisation_failed",
                              "type": type(exc).__name__,
                              "detail": str(exc)[:200]}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(err)
            return
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _qs(self) -> Dict[str, str]:
        if "?" not in self.path:
            return {}
        try:
            return dict(p.split("=", 1) for p in self.path.split("?", 1)[1].split("&") if "=" in p)
        except Exception:
            return {}

    def _serve_file(self, name: str, content_type: str = "text/html; charset=utf-8") -> None:
        path = os.path.join(self.static_dir, name)
        if not os.path.isfile(path):
            self.send_response(404); self.end_headers(); return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            self._serve_file("god_view.html")
            return
        if path == "/index_classic.html":
            self._serve_file("index.html")
            return
        if path == "/god_view_v2.html" or path == "/god_view_v2":
            self._serve_file("god_view_v2.html")
            return
        if path == "/audio_overlay.js" or path == "/static/audio_overlay.js":
            self._serve_file("audio_overlay.js", content_type="application/javascript; charset=utf-8")
            return
        if path == "/api/state":
            self._json(200, self.sim_ref.snapshot()); return
        if path == "/api/agents":
            self._json(200, {"agents": self.sim_ref.snapshot_agents()}); return
        if path == "/api/metrics":
            self._json(200, self.sim_ref.annalist.metrics_to_dict()); return
        if path == "/api/lift_state":
            self._json(200, lift_state(self.sim_ref)); return
        if path == "/api/realism_state":
            payload = (realism_state(self.sim_ref)
                       if realism_state is not None else {})
            self._json(200, payload); return
        if path == "/api/world_model_capabilities":
            payload = (world_model_capabilities()
                       if world_model_capabilities is not None else {})
            self._json(200, payload); return
        if path == "/api/physiology_state":
            payload = (physiology_state(self.sim_ref)
                       if physiology_state is not None else {})
            self._json(200, payload); return
        if path == "/api/photosynthesis_state":
            payload = (photosynthesis_state(self.sim_ref)
                       if photosynthesis_state is not None else {})
            self._json(200, payload); return
        if path == "/api/material_aging_state":
            payload = (material_aging_state(self.sim_ref)
                       if material_aging_state is not None else {})
            self._json(200, payload); return
        if path == "/api/marine_state":
            payload = (marine_state(self.sim_ref)
                       if marine_state is not None else {})
            self._json(200, payload); return
        if path == "/api/global_world_state":
            gw = getattr(self.sim_ref, "_global_world", None)
            payload = gw.state() if gw is not None else {
                "sims": [], "atmosphere": {}, "clock": {},
                "migration_count": 0, "migration_fail_count": 0,
            }
            self._json(200, payload); return
        if path == "/api/plant_evolution_state":
            payload = (plant_evolution_state(self.sim_ref)
                       if plant_evolution_state is not None else {})
            self._json(200, payload); return
        if path == "/api/meteorology_state":
            payload = (meteorology_state(self.sim_ref)
                       if meteorology_state is not None else {})
            self._json(200, payload); return
        if path == "/api/animal_evolution_state":
            payload = (animal_evolution_state(self.sim_ref)
                       if animal_evolution_state is not None else {})
            self._json(200, payload); return
        if path == "/api/agriculture_state":
            payload = (agriculture_state(self.sim_ref)
                       if agriculture_state is not None else {})
            self._json(200, payload); return
        if path == "/api/writing_state":
            payload = (writing_state(self.sim_ref)
                       if writing_state is not None else {})
            self._json(200, payload); return
        if path == "/api/polity_state":
            payload = (polity_state(self.sim_ref)
                       if polity_state is not None else {})
            self._json(200, payload); return
        if path == "/api/geology_state":
            payload = (geology_state(self.sim_ref)
                       if geology_state is not None else {})
            self._json(200, payload); return
        if path == "/api/metallurgy_state":
            payload = (metallurgy_state(self.sim_ref)
                       if metallurgy_state is not None else {})
            self._json(200, payload); return
        if path == "/api/realistic_construction_state":
            payload = (realistic_construction_state(self.sim_ref)
                       if realistic_construction_state is not None else {})
            self._json(200, payload); return
        if path == "/api/demography":
            self._json(200, self._demography()); return
        if path == "/api/agent":
            qs = self._qs()
            row = int(qs.get("row", 0))
            self._json(200, self._agent_detail(row)); return
        if path == "/api/groups":
            self._json(200, {"groups": self._groups()}); return
        if path == "/api/events/recent":
            qs = self._qs()
            n = int(qs.get("n", 50))
            self._json(200, {"events": (self.ctl_ref.last_event_tail or [])[-n:]}); return
        if path == "/api/world":
            qs = self._qs()
            cx = int(qs.get("cx", 0)); cy = int(qs.get("cy", 0))
            png = render_chunk_png(self.sim_ref, cx, cy)
            self._png(png); return
        if path == "/api/render":
            qs = self._qs()
            xmin = float(qs.get("xmin", -100)); ymin = float(qs.get("ymin", -100))
            xmax = float(qs.get("xmax", 100));  ymax = float(qs.get("ymax", 100))
            w = int(qs.get("w", 600)); h = int(qs.get("h", 400))
            overlay = qs.get("overlay", "")
            png = render_bbox_png(self.sim_ref, xmin, ymin, xmax, ymax, w, h, overlay)
            self._png(png); return
        if path == "/api/control":
            qs = self._qs()
            if "action" in qs:
                val = float(qs["speed"]) if "speed" in qs else None
                snap = self.ctl_ref.apply(qs["action"], val)
                self._json(200, snap); return
            self._json(200, self.ctl_ref.snapshot()); return
        self.send_response(404); self.end_headers()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/control":
            ln = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(ln).decode("utf-8") if ln else "{}"
            try:
                req = json.loads(body or "{}")
            except json.JSONDecodeError:
                req = {}
            action = req.get("action", "play")
            value = req.get("speed")
            snap = self.ctl_ref.apply(action, value)
            self._json(200, snap); return
        if path == "/api/timewarp":
            ln = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(ln).decode("utf-8") if ln else "{}"
            try:
                req = json.loads(body or "{}")
            except json.JSONDecodeError:
                req = {}
            mode = str(req.get("mode", "realtime"))
            try:
                from engine.timewarp import install_timewarp
                tw = install_timewarp(self.sim_ref)
                snap = tw.set_mode(mode)
                self._json(200, snap); return
            except Exception as exc:
                self._json(400, {"error": type(exc).__name__,
                                 "detail": str(exc)[:200]}); return
        self.send_response(404); self.end_headers()

    def _png(self, png: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(png)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(png)

    def _agent_detail(self, row: int) -> dict:
        a = self.sim_ref.agents
        if row < 0 or row >= a.n_active:
            return {"error": "out of range"}
        return {
            "row": row, "uuid": str(a.uuid[row]),
            "alive": bool(a.alive[row]),
            "generation": int(a.generation[row]),
            "born_tick": int(a.born_tick[row]),
            "pos": a.pos[row].tolist(),
            "drives": {"hunger": float(a.hunger[row]), "thirst": float(a.thirst[row]),
                       "sleep": float(a.sleep[row]), "fatigue": float(a.fatigue[row]),
                       "thermal": float(a.thermal[row]), "stress": float(a.stress[row]),
                       "pain": float(a.pain[row]), "loneliness": float(a.loneliness[row])},
            "personality": {"openness": float(a.openness[row]),
                            "conscientiousness": float(a.conscientiousness[row]),
                            "extraversion": float(a.extraversion[row]),
                            "agreeableness": float(a.agreeableness[row]),
                            "neuroticism": float(a.neuroticism[row]),
                            "ambition": float(a.ambition[row]),
                            "risk_tolerance": float(a.risk_tolerance[row]),
                            "aggression": float(a.aggression[row]),
                            "curiosity": float(a.curiosity[row]),
                            "empathy": float(a.empathy[row]),
                            "intelligence": float(a.intelligence[row])},
            "vitality": float(a.vitality[row]), "injuries": float(a.injuries[row]),
            "inventory": {"water": float(a.inv_water[row]), "food": float(a.inv_food[row]),
                          "wood": float(a.inv_wood[row]), "stone": float(a.inv_stone[row]),
                          "metal": float(a.inv_metal[row]), "tools": float(a.inv_tools[row])},
            "offspring": int(a.offspring_count[row]),
            "culture": int(a.relations[row].culture_id),
            "group_id": a.relations[row].group_id,
            "relations_count": len(a.relations[row].affinity),
            "parents": [int(p) if p is not None else None for p in a.parents[row]],
        }

    def _demography(self) -> Dict:
        """Snapshot of lineage + generations + culture distribution."""
        sim = self.sim_ref
        agents = sim.agents
        n = agents.n_active
        if n == 0:
            return {"tick": int(sim.tick), "alive": 0, "spawned": 0,
                    "generations": {}, "cultures": {}, "top_progenitors": [],
                    "lineage_size": 0, "births_cum": 0, "deaths_cum": 0}
        alive_mask = agents.alive[:n]
        gens = agents.generation[:n][alive_mask]
        gen_dist: Dict[int, int] = {}
        for g in gens:
            g_i = int(g)
            gen_dist[g_i] = gen_dist.get(g_i, 0) + 1
        cult_dist: Dict[int, int] = {}
        for row in range(n):
            if not alive_mask[row]:
                continue
            try:
                cid = int(agents.relations[row].culture_id)
            except Exception:
                cid = 0
            cult_dist[cid] = cult_dist.get(cid, 0) + 1
        # Top progenitors by descendant count (LineageMap stores row ids).
        lineage = getattr(sim.annalist, "lineage", None)
        top = []
        lineage_size = 0
        if lineage is not None:
            try:
                lineage_size = len(lineage.parents) + len(lineage.children)
                desc = []
                for root in list(lineage.children.keys())[:200]:
                    desc.append((int(root), int(lineage.descendant_count(int(root)))))
                desc.sort(key=lambda x: -x[1])
                for row, count in desc[:10]:
                    if 0 <= row < n:
                        top.append({
                            "row": int(row),
                            "descendants": int(count),
                            "generation": int(agents.generation[row]),
                            "alive": bool(agents.alive[row]),
                        })
            except Exception:
                pass
        return {
            "tick": int(sim.tick),
            "alive": int(alive_mask.sum()),
            "spawned": int(n),
            "generations": gen_dist,
            "cultures": cult_dist,
            "top_progenitors": top,
            "lineage_size": int(lineage_size),
            "births_cum": int(getattr(sim.annalist, "cum_births", 0)),
            "deaths_cum": int(getattr(sim.annalist, "cum_deaths", 0)),
            "matings_cum": int(getattr(sim.annalist, "cum_matings", 0)),
        }

    def _groups(self) -> List[dict]:
        groups = getattr(self.sim_ref, "_groups", {})
        out = []
        for gid, info in groups.items():
            out.append({
                "group_id": int(gid),
                "formed_tick": int(info.get("formed_tick", 0)),
                "size": int(info.get("size", 0)),
                "centroid": list(info.get("centroid", (0.0, 0.0))),
                "lex_sig": int(info.get("lex_sig", 0)),
            })
        return out


def start_server(sim: Simulation, ctl: SimController, host: str = "0.0.0.0",
                 port: int = 8080, static_dir: str = "") -> ThreadingHTTPServer:
    _Handler.sim_ref = sim
    _Handler.ctl_ref = ctl
    _Handler.static_dir = static_dir or os.path.dirname(os.path.abspath(__file__))
    # P2 — audio endpoints (best-effort wiring; safe if modules missing).
    try:
        from engine.audio_endpoints import register_audio_endpoints
        from engine.communication import SoundField
        from engine.knowledge_artifacts import KnowledgeRegistry
        _sf = getattr(sim, "sound_field", None) or SoundField()
        _kr = getattr(sim, "knowledge_registry", None) or KnowledgeRegistry()
        try:
            if not hasattr(sim, "sound_field"):
                sim.sound_field = _sf
            if not hasattr(sim, "knowledge_registry"):
                sim.knowledge_registry = _kr
        except Exception:
            pass
        register_audio_endpoints(_Handler, sim, _sf, _kr)
    except Exception:
        pass
    srv = ThreadingHTTPServer((host, port), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv



# ---------------------------------------------------------------------------
# P1 — God Avatar wiring (append-only extension, 2026-05-13).
# ---------------------------------------------------------------------------
#
# `start_god_server` is identical to `start_server` but additionally creates
# a `GodObserver` + `GodInterventionLog` and registers the god HTTP routes
# on the `_Handler` class before the server starts serving.
#
# Returned tuple is (server, god, log) so callers (and tests) can introspect
# the in-process god state.
#
# Idempotent: registering god endpoints twice on the same handler class is
# safe because `register_god_endpoints` only patches do_GET/do_POST with a
# fall-through closure that calls the *previous* method, so wrappers stack
# without double-handling routes.

def start_god_server(sim: "Simulation", ctl: "SimController",
                     host: str = "0.0.0.0", port: int = 8080,
                     static_dir: str = ""):
    """Start the dashboard HTTP server with God Avatar endpoints attached.

    Routes added (handled BEFORE the regular dashboard routes):
        GET  /api/god/state          - current god observer state
        POST /api/god/teleport       - move the god camera
        POST /api/god/visibility     - toggle visible / invisible
        POST /api/god/spawn_agent    - intervention: spawn an agent
        POST /api/god/spawn_resource - intervention: place a resource
        POST /api/god/freeze_time    - intervention: freeze the sim
        POST /api/god/grant_tech     - intervention: grant a tech to an agent

    All non-god routes fall through to the existing `_Handler` implementation.
    """
    from engine.god_avatar import GodObserver, GodInterventionLog
    from engine.god_endpoints import register_god_endpoints

    god = GodObserver()
    log = GodInterventionLog()

    # Attach a tick-getter shim if needed — god_endpoints may try to read
    # the current tick off the handler's sim_ref for intervention metadata.
    register_god_endpoints(_Handler, god, log)

    srv = start_server(sim, ctl, host=host, port=port, static_dir=static_dir)
    return srv, god, log



# ---------------------------------------------------------------------------
# P2 — Audio wiring (append-only extension, 2026-05-13).
# ---------------------------------------------------------------------------
#
# `start_full_observation_server` boots the dashboard with BOTH the God
# Avatar endpoints AND the audio endpoints attached. Returns
# (srv, god, log, sound_field, knowledge_registry) so callers can introspect
# every observation channel.
#
# Idempotent on the audio side: register_audio_endpoints itself only patches
# do_GET once thanks to its `_audio_patched` sentinel.

def start_full_observation_server(sim: "Simulation", ctl: "SimController",
                                  host: str = "0.0.0.0", port: int = 8080,
                                  static_dir: str = "",
                                  sound_field=None,
                                  knowledge_registry=None):
    """Dashboard + God Avatar + Audio overlay endpoints.

    Routes added on top of `start_god_server`:
        GET /api/audio?listener_x=…&listener_y=…   - audible utterances
        GET /api/audio/history?row=N&n=K           - recent vocalizations near agent N
        GET /api/artifacts                         - knowledge artifacts in bbox
        GET /static/audio_overlay.js               - the JS HUD client
    """
    from engine.audio_endpoints import register_audio_endpoints
    from engine.communication import SoundField
    from engine.knowledge_artifacts import KnowledgeRegistry

    if sound_field is None:
        sound_field = getattr(sim, "sound_field", None) or SoundField()
        # Attach back to sim so the tick loop can call sound_field.emit(...).
        if not hasattr(sim, "sound_field"):
            try:
                sim.sound_field = sound_field
            except Exception:
                pass
    if knowledge_registry is None:
        knowledge_registry = (getattr(sim, "knowledge_registry", None)
                              or KnowledgeRegistry())
        if not hasattr(sim, "knowledge_registry"):
            try:
                sim.knowledge_registry = knowledge_registry
            except Exception:
                pass

    # First wire god (also calls start_server inside; we need to start
    # the server *after* both monkey-patches are installed, so we don't
    # use start_god_server's auto-start here — register audio FIRST and
    # then start_server once).
    from engine.god_avatar import GodObserver, GodInterventionLog
    from engine.god_endpoints import register_god_endpoints

    god = GodObserver()
    log = GodInterventionLog()
    register_god_endpoints(_Handler, god, log)
    register_audio_endpoints(_Handler, sim, sound_field, knowledge_registry)

    srv = start_server(sim, ctl, host=host, port=port, static_dir=static_dir)
    return srv, god, log, sound_field, knowledge_registry
