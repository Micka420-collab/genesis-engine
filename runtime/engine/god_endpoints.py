"""HTTP endpoints for the God Observer — monkey-patched onto a dashboard handler.

This module is intentionally self-contained: it does not touch dashboard.py.
Call `register_god_endpoints(handler_class, god, log)` once after building
your dashboard handler class. It splices new GET/POST routes into `do_GET`
and `do_POST`, preserving the originals via delegation.

Endpoints
---------
GET  /api/god/state                -> GodObserver snapshot
POST /api/god/teleport             -> {x, y, z?}
POST /api/god/visibility           -> {visible: bool}
POST /api/god/spawn_agent          -> {x, y, culture_id?}
POST /api/god/spawn_resource       -> {material, kg, x, y}
POST /api/god/freeze_time          -> {frozen: bool}
POST /api/god/grant_tech           -> {row, tech_id}

Every POST emits a GodIntervention entry to the log.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional


def _read_json_body(handler) -> Dict[str, Any]:
    try:
        ln = int(handler.headers.get("Content-Length", "0"))
    except Exception:
        ln = 0
    if ln <= 0:
        return {}
    try:
        raw = handler.rfile.read(ln).decode("utf-8")
        return json.loads(raw or "{}")
    except Exception:
        return {}


def _json_response(handler, code: int, payload: Dict[str, Any]) -> None:
    # Prefer the handler's existing JSON helper if it exposes one.
    fn = getattr(handler, "_json", None)
    if callable(fn):
        fn(code, payload)
        return
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def _current_tick(handler) -> Optional[int]:
    sim = getattr(handler, "sim_ref", None)
    if sim is None:
        return None
    return getattr(sim, "tick", None)


# ---------------------------------------------------------------------------
# Endpoint implementations
# ---------------------------------------------------------------------------

def _handle_get_state(handler, god, log) -> None:
    snap = god.to_dict()
    snap["log_size"] = len(log)
    snap["recent_interventions"] = log.recent(10)
    _json_response(handler, 200, snap)


def _handle_teleport(handler, god, log) -> None:
    req = _read_json_body(handler)
    try:
        x = float(req["x"]); y = float(req["y"])
    except (KeyError, TypeError, ValueError):
        _json_response(handler, 400, {"error": "x and y required"})
        return
    z = req.get("z")
    z = None if z is None else float(z)
    god.teleport(x, y, z)
    god.increment_intervention()
    entry = log.append(
        "teleport", {"x": x, "y": y, "z": z}, tick=_current_tick(handler)
    )
    _json_response(handler, 200, {"ok": True, "god": god.to_dict(), "entry": entry.to_dict()})


def _handle_visibility(handler, god, log) -> None:
    req = _read_json_body(handler)
    visible = bool(req.get("visible", False))
    god.set_visible(visible)
    god.increment_intervention()
    entry = log.append(
        "visibility", {"visible": visible}, tick=_current_tick(handler)
    )
    _json_response(handler, 200, {"ok": True, "god": god.to_dict(), "entry": entry.to_dict()})


def _handle_spawn_agent(handler, god, log) -> None:
    req = _read_json_body(handler)
    try:
        x = float(req["x"]); y = float(req["y"])
    except (KeyError, TypeError, ValueError):
        _json_response(handler, 400, {"error": "x and y required"})
        return
    culture_id = int(req.get("culture_id", 0))
    sim = getattr(handler, "sim_ref", None)
    if sim is None:
        _json_response(handler, 500, {"error": "no sim attached to handler"})
        return
    agents = getattr(sim, "agents", None)
    if agents is None or not hasattr(agents, "spawn_founder"):
        _json_response(handler, 500, {"error": "agent registry not available"})
        return
    try:
        world_seed = getattr(sim, "world_seed", None) or getattr(
            getattr(sim, "config", None), "world_seed", 0
        ) or 0
        founder_idx = int(getattr(agents, "n_active", 0))
        born_tick = int(getattr(sim, "tick", 0))
        z = float(req.get("z", 0.0))
        row = agents.spawn_founder(
            world_seed, founder_idx, (float(x), float(y), z), born_tick, culture_id=culture_id
        )
    except Exception as exc:
        _json_response(handler, 500, {"error": f"spawn failed: {exc!r}"})
        return
    god.increment_intervention()
    entry = log.append(
        "spawn_agent",
        {"x": x, "y": y, "culture_id": culture_id, "row": int(row)},
        tick=_current_tick(handler),
    )
    _json_response(handler, 200, {"ok": True, "row": int(row), "entry": entry.to_dict()})


def _handle_spawn_resource(handler, god, log) -> None:
    req = _read_json_body(handler)
    try:
        material = str(req["material"])
        kg = float(req["kg"])
        x = float(req["x"]); y = float(req["y"])
    except (KeyError, TypeError, ValueError):
        _json_response(handler, 400, {"error": "material, kg, x, y required"})
        return
    sim = getattr(handler, "sim_ref", None)
    placed = False
    # Try a few plausible sim-side hooks, in order, without hard-requiring them.
    for fn_name in ("spawn_resource", "drop_resource", "add_resource"):
        fn = getattr(sim, fn_name, None) if sim is not None else None
        if callable(fn):
            try:
                fn(material, kg, x, y)
                placed = True
                break
            except Exception:
                continue
    god.increment_intervention()
    entry = log.append(
        "spawn_resource",
        {"material": material, "kg": kg, "x": x, "y": y, "placed": placed},
        tick=_current_tick(handler),
    )
    _json_response(handler, 200, {"ok": True, "placed": placed, "entry": entry.to_dict()})


def _handle_freeze_time(handler, god, log) -> None:
    req = _read_json_body(handler)
    frozen = bool(req.get("frozen", False))
    ctl = getattr(handler, "ctl_ref", None)
    applied = False
    if ctl is not None:
        if hasattr(ctl, "apply"):
            try:
                ctl.apply("pause" if frozen else "play")
                applied = True
            except Exception:
                applied = False
        if not applied:
            try:
                setattr(ctl, "frozen", frozen)
                setattr(ctl, "paused", frozen)
                applied = True
            except Exception:
                applied = False
    god.increment_intervention()
    entry = log.append(
        "freeze_time", {"frozen": frozen, "applied": applied}, tick=_current_tick(handler)
    )
    _json_response(handler, 200, {"ok": True, "frozen": frozen, "entry": entry.to_dict()})


def _handle_grant_tech(handler, god, log) -> None:
    req = _read_json_body(handler)
    try:
        row = int(req["row"])
        tech_id = req["tech_id"]
    except (KeyError, TypeError, ValueError):
        _json_response(handler, 400, {"error": "row and tech_id required"})
        return
    sim = getattr(handler, "sim_ref", None)
    granted = False
    if sim is not None:
        # Try sim-level grant hook first, then a known_tech set on the agent.
        fn = getattr(sim, "grant_tech", None)
        if callable(fn):
            try:
                fn(row, tech_id)
                granted = True
            except Exception:
                granted = False
        if not granted:
            agents = getattr(sim, "agents", None)
            store = getattr(agents, "known_tech", None) if agents is not None else None
            if isinstance(store, dict):
                store.setdefault(int(row), set()).add(tech_id)
                granted = True
            elif isinstance(store, list) and 0 <= int(row) < len(store):
                bucket = store[int(row)]
                if isinstance(bucket, set):
                    bucket.add(tech_id)
                    granted = True
    god.increment_intervention()
    entry = log.append(
        "grant_tech",
        {"row": row, "tech_id": tech_id, "granted": granted},
        tick=_current_tick(handler),
    )
    _json_response(handler, 200, {"ok": True, "granted": granted, "entry": entry.to_dict()})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_GET_ROUTES: Dict[str, Callable] = {
    "/api/god/state": _handle_get_state,
}

_POST_ROUTES: Dict[str, Callable] = {
    "/api/god/teleport": _handle_teleport,
    "/api/god/visibility": _handle_visibility,
    "/api/god/spawn_agent": _handle_spawn_agent,
    "/api/god/spawn_resource": _handle_spawn_resource,
    "/api/god/freeze_time": _handle_freeze_time,
    "/api/god/grant_tech": _handle_grant_tech,
}


def register_god_endpoints(handler_class, god, log):
    """Monkey-patch `handler_class` to expose the god routes.

    The handler keeps responding to its existing routes; god routes are
    handled first and fall through to the original `do_GET` / `do_POST` on
    no match. Also attaches `god_ref` and `god_log_ref` class attributes so
    other handlers / tests can introspect them.
    """
    handler_class.god_ref = god
    handler_class.god_log_ref = log

    orig_get = handler_class.do_GET
    orig_post = handler_class.do_POST

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        fn = _GET_ROUTES.get(path)
        if fn is not None:
            from engine.api_lock import handler_sim_lock
            with handler_sim_lock(self):
                return fn(self, self.god_ref, self.god_log_ref)
        return orig_get(self)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        fn = _POST_ROUTES.get(path)
        if fn is not None:
            from engine.api_lock import handler_sim_lock
            with handler_sim_lock(self):
                return fn(self, self.god_ref, self.god_log_ref)
        return orig_post(self)

    handler_class.do_GET = do_GET
    handler_class.do_POST = do_POST
    return handler_class
