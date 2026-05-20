"""Shared simulation API lock and safe optional snapshots."""
from __future__ import annotations

import contextlib
from typing import Any, Callable, Dict, Optional, Tuple


def sim_api_lock(sim) -> contextlib.AbstractContextManager:
    lock = getattr(sim, "api_lock", None)
    if lock is None:
        return contextlib.nullcontext()
    return lock


def handler_sim_lock(handler) -> contextlib.AbstractContextManager:
    return sim_api_lock(getattr(handler, "sim_ref", None))


def safe_optional(label: str, fn: Callable[[], Any],
                  *, default: Any = None) -> Tuple[Any, Optional[str]]:
    try:
        return fn(), None
    except Exception as exc:
        return default, f"{label}: {type(exc).__name__}: {exc}"


def safe_dict(label: str, fn: Callable[[], Dict[str, Any]],
              *, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(default or {})
    result, err = safe_optional(label, fn, default=None)
    if err:
        out["error"] = err
        return out
    if isinstance(result, dict):
        return result
    if result is not None:
        out["value"] = result
    return out
