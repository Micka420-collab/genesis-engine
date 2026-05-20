"""P73 — observable agent snapshot export smoke."""
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
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.sim import Simulation, SimConfig  # noqa: E402
from engine.agent_observation import (  # noqa: E402
    export_observable_snapshot, observable_summary, DEFAULT_PERCEPTION_RADIUS_M,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P73 — agent observation smoke")
    print("=" * 78)
    failures = 0

    cfg = SimConfig(
        seed=0x0B53E2A_B1E, founders=12, max_agents=40,
        bounds_km=(0.3, 0.3), cultures=2, drive_accel=2000.0,
        name="p73_obs",
    )
    sim = Simulation(cfg)
    for _ in range(30):
        sim.step()

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "observable.json")
        snap = export_observable_snapshot(sim, path)
        ok = os.path.isfile(path) and snap.n_alive > 0
        print(_row("step 1 - export JSON", ok, f"n_alive={snap.n_alive}"))
        if not ok:
            failures += 1

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        compact = data.get("agents_compact") or []
        ok = len(compact) == snap.n_alive and "vision_m" in compact[0]
        print(_row("step 2 - agents_compact + vision_m", ok,
                   f"keys={list(compact[0].keys())[:6]}..."))
        if not ok:
            failures += 1

    summary = observable_summary(snap)
    ok = summary["n_alive"] > 0 and summary.get("mean_vitality", 0) > 0
    print(_row("step 3 - summary stats", ok, str(summary)))
    if not ok:
        failures += 1

    ok = abs(DEFAULT_PERCEPTION_RADIUS_M - 60.0) < 1e-3
    print(_row("step 4 - perception radius 60m", ok,
               f"radius={DEFAULT_PERCEPTION_RADIUS_M}"))
    if not ok:
        failures += 1

    # determinism
    sim2 = Simulation(cfg)
    for _ in range(30):
        sim2.step()
    with tempfile.TemporaryDirectory() as td:
        p1 = os.path.join(td, "a.json")
        p2 = os.path.join(td, "b.json")
        export_observable_snapshot(sim, p1)
        export_observable_snapshot(sim2, p2)
        with open(p1, encoding="utf-8") as f:
            d1 = json.load(f)
        with open(p2, encoding="utf-8") as f:
            d2 = json.load(f)
        ok = d1["tick"] == d2["tick"] and d1["n_alive"] == d2["n_alive"]
        print(_row("step 5 - determinism same seed", ok,
                   f"tick={d1['tick']} alive={d1['n_alive']}"))
        if not ok:
            failures += 1

    print("=" * 78)
    if failures:
        print(f"P73 FAIL — {failures} step(s)")
        return 1
    print("P73 PASS — all steps OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
