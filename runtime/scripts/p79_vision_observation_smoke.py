"""P79 — Vision cone + JSONL observation smoke."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.sim import Simulation, SimConfig  # noqa: E402
from engine.agent_observation import (  # noqa: E402
    export_observable_snapshot, export_vision_cone,
    append_observable_jsonl,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P79 — Vision observation smoke")
    print("=" * 78)
    failures = 0
    sim = Simulation(SimConfig(seed=99, founders=6, max_agents=20,
                               spawn_radius_m=15.0))
    sim.bootstrap()
    vc = export_vision_cone(sim, 0)
    ok = vc.radius_m > 0 and isinstance(vc.visible_agent_rows, list)
    print(_row("export_vision_cone", ok, f"see={len(vc.visible_agent_rows)}"))
    if not ok:
        failures += 1
    with tempfile.TemporaryDirectory() as td:
        snap_path = os.path.join(td, "obs.json")
        snap = export_observable_snapshot(sim, snap_path, include_vision_cones=True)
        ok = os.path.isfile(snap_path) and len(snap.vision_cones) > 0
        with open(snap_path, encoding="utf-8") as f:
            raw = json.load(f)
        ok = ok and "vision_cones" in raw
        print(_row("snapshot vision_cones", ok, f"n={len(snap.vision_cones)}"))
        if not ok:
            failures += 1
        jl = os.path.join(td, "stream.jsonl")
        line = append_observable_jsonl(sim, jl)
        ok = os.path.isfile(jl) and line.get("tick") == sim.tick
        print(_row("append_observable_jsonl", ok))
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
