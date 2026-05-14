"""P4 LIVE — Léman simulation served live via the god-view dashboard.

Runs the same Léman recipe as ``scripts/p4_leman.py`` (Lausanne-Ouchy,
46.510°N / 6.633°E, 2 km × 2 km box, 20 founders) BUT instead of just
ticking the sim and dumping a journal, this script:

* boots the dashboard HTTP server on ``localhost:<port>`` (default 8765),
* runs the sim in a background thread at ~20 ticks/sec,
* serves ``god_view_v2.html`` and all ``/api/*`` endpoints live, so the
  user can open the URL in a browser and watch agents evolve.

Stops after ``--ticks`` ticks (default: run forever, Ctrl+C to stop).
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import threading
import time

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.sim import Simulation, SimConfig
from engine.sim_5cd_integration import install
from engine.earth_loader import EarthLoader
from engine.earth_streamer import attach_earth_loader, attach_land_filter
from engine.sim_lift import install_lift
from engine.dashboard import SimController, start_god_server


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ticks", type=int, default=0,
                   help="Number of ticks to run (0 = run forever, until Ctrl+C).")
    p.add_argument("--port", type=int, default=8765,
                   help="HTTP port to bind the dashboard on (default 8765).")
    p.add_argument("--host", default="127.0.0.1",
                   help="HTTP host to bind on (default 127.0.0.1).")
    p.add_argument("--tick-sleep", type=float, default=0.05,
                   help="Sleep between ticks in seconds (default 0.05 = ~20 TPS).")
    return p.parse_args()


def build_leman_sim() -> Simulation:
    """Build the Léman sim exactly like ``scripts/p4_leman.py`` does."""
    origin_lat = 46.510
    origin_lon = 6.633
    cache_dir = os.path.abspath(os.path.join(ROOT, "..", "cache", "earth_leman"))
    os.makedirs(cache_dir, exist_ok=True)
    loader = EarthLoader(origin_lat=origin_lat, origin_lon=origin_lon,
                         bounds_km=2.0, cache_dir=cache_dir)

    cfg = SimConfig(
        name="phase5a_leman_live",
        seed=0xFADE_C0FFEE_5A & 0xFFFFFFFF_FFFFFFFF,
        founders=20,
        max_agents=1000,                # synced with p4_leman.py (P-NEW.15)
        bounds_km=(2.0, 2.0),
        spawn_radius_m=200.0,
        cultures=2,
        drive_accel=1500.0,
    )
    sim = Simulation(cfg)
    sim.earth_loader = loader
    attach_earth_loader(sim.streamer, loader, strict=False, log_first_hit=True)
    attach_land_filter(sim)
    install(sim)
    install_lift(sim)                   # L2 vegetation + erosion (P-NEW.5)
    return sim


def main() -> int:
    args = parse_args()

    print("[p4-leman-live] building Léman simulation…")
    sim = build_leman_sim()
    ctl = SimController(target_tps=20.0)

    # Stand up the dashboard FIRST. start_god_server stashes the sim on
    # _Handler.sim_ref as a class attribute and spins up a daemon thread
    # serving HTTP. Static dir defaults to engine/, which holds
    # god_view_v2.html.
    srv, god, god_log = start_god_server(
        sim, ctl, host=args.host, port=args.port,
    )

    banner = (
        f"\n[p4-leman-live] Léman simulation is live.\n"
        f"[p4-leman-live] Open  http://localhost:{args.port}/god_view_v2.html  "
        f"to watch the simulation.\n"
        f"[p4-leman-live] API   http://localhost:{args.port}/api/god/state\n"
        f"[p4-leman-live] tick budget: "
        f"{'infinite' if args.ticks <= 0 else args.ticks}    "
        f"sleep/tick: {args.tick_sleep:.3f}s\n"
        f"[p4-leman-live] Press Ctrl+C to stop.\n"
    )
    print(banner, flush=True)

    # Background sim-loop. The HTTP server is already on a daemon thread;
    # we put the sim on its own daemon thread so the main thread is free
    # to handle KeyboardInterrupt cleanly.
    stop_evt = threading.Event()
    done_evt = threading.Event()
    target_ticks = args.ticks if args.ticks > 0 else None

    def sim_loop():
        try:
            while not stop_evt.is_set():
                if ctl.stop:
                    break
                with ctl.lock:
                    paused = ctl.paused
                    step_req = ctl.single_step
                    if step_req:
                        ctl.single_step = False
                if paused and not step_req:
                    time.sleep(0.05)
                    continue
                try:
                    sim.step()
                except Exception as exc:
                    print(f"[p4-leman-live] sim.step() raised "
                          f"{type(exc).__name__}: {exc}", flush=True)
                    break
                if sim.tick % 50 == 0:
                    n_alive = int(sim.agents.alive[:sim.agents.n_active].sum())
                    print(f"[p4-leman-live] tick {sim.tick:5d}  "
                          f"alive={n_alive:3d}", flush=True)
                if target_ticks is not None and sim.tick >= target_ticks:
                    print(f"[p4-leman-live] reached target {target_ticks} ticks.",
                          flush=True)
                    break
                if args.tick_sleep > 0:
                    time.sleep(args.tick_sleep)
        finally:
            done_evt.set()

    sim_thread = threading.Thread(target=sim_loop, name="leman-sim-loop",
                                  daemon=True)
    sim_thread.start()

    exit_code = 0
    try:
        # Block main thread until sim loop is done or user hits Ctrl+C.
        while not done_evt.is_set():
            done_evt.wait(timeout=0.5)
    except KeyboardInterrupt:
        print("\n[p4-leman-live] Ctrl+C — stopping…", flush=True)
    finally:
        stop_evt.set()
        sim_thread.join(timeout=2.0)
        try:
            srv.shutdown()
        except Exception:
            pass
        try:
            sim.annalist.close()
        except Exception:
            pass

    print(f"[p4-leman-live] final tick = {sim.tick}", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
