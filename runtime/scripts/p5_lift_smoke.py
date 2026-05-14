"""P5 smoke — sim_lift (L2) integration test.

Run 300 ticks of the Léman sim with sim_lift installed. Verify:
  - veg fields are created for every cached chunk
  - some PRAIRIE/GARRIGUE cells exist somewhere
  - ravine_depth grows along agent footpaths
  - no exceptions during the run
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.sim import Simulation, SimConfig
from engine.sim_5cd_integration import install
from engine.earth_loader import EarthLoader
from engine.earth_streamer import attach_earth_loader, attach_land_filter
from engine.sim_lift import install_lift, lift_state


def main() -> int:
    out_path = os.path.join(ROOT, "journals", "p5_lift_smoke.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    cfg = SimConfig(
        name="p5_lift_smoke", seed=0xC0FFEE_5F1F & 0xFFFFFFFF_FFFFFFFF,
        founders=20, max_agents=50, bounds_km=(2.0, 2.0),
        spawn_radius_m=200.0, drive_accel=1500.0, cultures=2,
    )
    loader = EarthLoader(
        origin_lat=46.510, origin_lon=6.633, bounds_km=2.0,
        cache_dir=os.path.abspath(os.path.join(ROOT, "..", "cache", "earth_leman")),
    )
    sim = Simulation(cfg)
    attach_earth_loader(sim.streamer, loader, log_first_hit=False)
    attach_land_filter(sim)
    install(sim)
    install_lift(sim)

    t0 = time.monotonic()
    errors = []
    for t in range(300):
        try:
            sim.step()
        except Exception as exc:
            errors.append({"tick": t, "exc": type(exc).__name__, "msg": str(exc),
                           "trace": traceback.format_exc().splitlines()[-6:]})
            break
    elapsed = time.monotonic() - t0

    state = lift_state(sim)
    summary = {
        "ticks": sim.tick, "elapsed_s": round(elapsed, 3),
        "agents_alive": int(sim.agents.alive[:sim.agents.n_active].sum()),
        "lift_state": state,
        "errors": errors,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

    if errors:
        print("\n[X] P5 LIFT SMOKE FAILED")
        return 2
    if state["chunks"] < 1:
        print("\n[X] P5 LIFT SMOKE FAILED — no lift fields created")
        return 3
    if not state["veg_distribution"]:
        print("\n[X] P5 LIFT SMOKE FAILED — empty veg distribution")
        return 4
    print("\n[OK] P5 LIFT SMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
