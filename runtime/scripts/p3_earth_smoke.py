"""P3 -- smoke-test the EarthLoader offline fallback path.

Goal: confirm that EarthLoader.chunk_data() either returns a clean dict of
Chunk-shaped numpy arrays OR ``None`` (graceful offline behavior) without
raising any unhandled exception. Three chunk coordinates are exercised:
(0,0,0), (1,0,0), (0,1,0). A per-call summary is written to
``runtime/journals/p3_earth_smoke.jsonl`` and a final aggregate verdict is
appended at the end.

Pass = no unhandled exception AND every call either returned None or a dict
whose ``height``/``biome``/... arrays share consistent shapes.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from engine.core import prf_rng  # noqa: E402
from engine.earth_loader import EarthLoader  # noqa: E402


EXPECTED_KEYS = {"height", "biome", "water", "food_capacity", "stone", "wood", "metal"}


def _describe(result):
    """Return a JSON-serializable description of a chunk_data() result."""
    if result is None:
        return {"kind": "none"}
    if isinstance(result, dict):
        if not result:
            return {"kind": "empty_dict"}
        out = {"kind": "dict", "keys": sorted(result.keys()), "shapes": {}, "dtypes": {}}
        for k, v in result.items():
            try:
                out["shapes"][k] = list(getattr(v, "shape", ()))
                out["dtypes"][k] = str(getattr(v, "dtype", type(v).__name__))
            except Exception as exc:  # pragma: no cover - defensive
                out["shapes"][k] = f"<err:{exc}>"
        return out
    return {"kind": "other", "type": type(result).__name__}


def _validate(call_records):
    """Apply the pass/fail rule across all call records.

    Rule:
      (a) all calls returned ``None`` / empty dict --> clean offline,
      (b) OR every dict result has consistent shapes across keys/calls.
    Any unhandled exception is a fail.
    """
    if any(r.get("raised") for r in call_records):
        return False, "unhandled_exception"

    kinds = [r["result"]["kind"] for r in call_records]
    if all(k in ("none", "empty_dict") for k in kinds):
        return True, "clean_offline"

    # At least one dict result -- require shape consistency
    ref_shape = None
    for r in call_records:
        if r["result"]["kind"] != "dict":
            continue
        keys = set(r["result"]["keys"])
        if keys != EXPECTED_KEYS:
            return False, f"unexpected_keys:{sorted(keys ^ EXPECTED_KEYS)}"
        for k, shape in r["result"]["shapes"].items():
            if ref_shape is None:
                ref_shape = tuple(shape)
            elif tuple(shape) != ref_shape:
                return False, f"shape_mismatch:{k}={shape}!={list(ref_shape)}"
    return True, "consistent_shapes"


def main() -> int:
    out_path = os.path.join(ROOT, "journals", "p3_earth_smoke.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Truncate any previous run.
    open(out_path, "w", encoding="utf-8").close()

    # Deterministic randomness slot just in case the smoke test grows --
    # we don't actually need to perturb anything in the loader call, but
    # we honour the constraint that any randomness uses prf_rng.
    rng = prf_rng(world_seed=0xEA27_1005_5C0DE & 0xFFFFFFFFFFFFFFFF,
                  ctx=("p3", "earth_smoke"),
                  indices=(0,))
    _jitter = float(rng.random())  # noqa: F841  (kept for determinism trace)

    cache_dir = os.path.join(tempfile.gettempdir(), "earth_cache")

    records = []
    t_setup = time.monotonic()
    try:
        loader = EarthLoader(
            origin_lat=46.40,
            origin_lon=6.45,
            bounds_km=2.0,
            cache_dir=cache_dir,
        )
        setup_elapsed = time.monotonic() - t_setup
    except Exception as exc:
        setup_elapsed = time.monotonic() - t_setup
        tb = traceback.format_exc()
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "event": "construct_failed",
                "error": repr(exc),
                "traceback": tb,
                "setup_s": setup_elapsed,
            }) + "\n")
        print(f"[P3] EarthLoader construction FAILED: {exc}")
        print(tb)
        return 2

    with open(out_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "event": "constructed",
            "origin_lat": 46.40,
            "origin_lon": 6.45,
            "bounds_km": 2.0,
            "cache_dir": cache_dir,
            "setup_s": setup_elapsed,
        }) + "\n")

    coords = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    for coord in coords:
        t0 = time.monotonic()
        rec = {"event": "chunk_data", "coord": list(coord)}
        try:
            result = loader.chunk_data(coord)
            rec["raised"] = False
            rec["result"] = _describe(result)
        except Exception as exc:
            rec["raised"] = True
            rec["error"] = repr(exc)
            rec["traceback"] = traceback.format_exc()
            rec["result"] = {"kind": "exception"}
        rec["elapsed_s"] = time.monotonic() - t0
        records.append(rec)
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"[P3] chunk_data{coord} -> {rec['result']['kind']} "
              f"(raised={rec['raised']}, {rec['elapsed_s']*1000:.1f} ms)")
        if rec["result"]["kind"] == "dict":
            print(f"      keys={rec['result']['keys']}")
            print(f"      shapes={rec['result']['shapes']}")

    ok, reason = _validate(records)
    verdict = {
        "event": "verdict",
        "ok": ok,
        "reason": reason,
        "n_calls": len(records),
        "n_none": sum(1 for r in records if r["result"]["kind"] == "none"),
        "n_dict": sum(1 for r in records if r["result"]["kind"] == "dict"),
        "n_raised": sum(1 for r in records if r.get("raised")),
    }
    with open(out_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(verdict) + "\n")
    print(f"[P3] verdict ok={ok} reason={reason} "
          f"(none={verdict['n_none']} dict={verdict['n_dict']} raised={verdict['n_raised']})")
    print(f"[P3] journal -> {out_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
