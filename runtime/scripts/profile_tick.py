"""P-NEW.11 — Profile a saturated-population tick.

Bootstraps a 200-agent Léman sim, runs to steady state (~1000 ticks), then
cProfiles 300 ticks. Prints the top 20 most expensive functions by cumulative
time. Output: ``journals/profile_tick.txt``.
"""
from __future__ import annotations

import cProfile
import io
import os
import pstats
import sys

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
from engine.sim_lift import install_lift


def main() -> int:
    cfg = SimConfig(
        name="profile_tick",
        seed=0xFADE_C0FFEE_5A & 0xFFFFFFFF_FFFFFFFF,
        founders=20, max_agents=200,
        bounds_km=(2.0, 2.0), spawn_radius_m=200.0,
        drive_accel=1500.0, cultures=2,
    )
    loader = EarthLoader(origin_lat=46.510, origin_lon=6.633, bounds_km=2.0,
                         cache_dir=os.path.abspath(
                             os.path.join(ROOT, "..", "cache", "earth_leman")))
    sim = Simulation(cfg)
    attach_earth_loader(sim.streamer, loader, log_first_hit=False)
    attach_land_filter(sim)
    install(sim)
    install_lift(sim)

    # Warm up to saturation (population grows fast in first ~500 ticks).
    print("Warming up to tick 800...")
    for _ in range(800):
        sim.step()
    alive = int(sim.agents.alive[:sim.agents.n_active].sum())
    print(f"  warm-up done. alive={alive}/{sim.agents.n_active}, tick={sim.tick}")

    # Profile 300 steady-state ticks.
    print("Profiling 300 ticks...")
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(300):
        sim.step()
    pr.disable()

    # Save + print top 25 by cumulative time.
    out_path = os.path.join(ROOT, "journals", "profile_tick.txt")
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(25)
    text = s.getvalue()
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(text[:5000])
    print(f"\n  full report -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
