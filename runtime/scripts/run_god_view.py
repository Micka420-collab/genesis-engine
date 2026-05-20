"""Genesis Engine — God-view launcher.

Lance une simulation Phase 4 et un serveur HTTP qui sert l'interface
god-view (pan/zoom/follow, contrôles play/pause/vitesse).

Usage :
    python scripts/run_god_view.py [--founders 60] [--port 8080] [--seed 0xBEEF]

Puis ouvre http://localhost:8080 dans ton navigateur.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.abspath(os.path.join(HERE, ".."))
if RUNTIME not in sys.path:
    sys.path.insert(0, RUNTIME)

from engine.sim import Simulation, SimConfig
from engine.dashboard import SimController, start_god_server


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--founders", type=int, default=60)
    p.add_argument("--max-agents", type=int, default=400)
    p.add_argument("--bounds-km", type=float, default=0.6)
    p.add_argument("--cultures", type=int, default=2)
    p.add_argument("--drive-accel", type=float, default=2000.0)
    p.add_argument("--seed", type=lambda s: int(s, 0), default=0xBEEF)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--target-tps", type=float, default=10.0,
                   help="Vitesse cible en ticks/seconde (1.0× = ce taux).")
    p.add_argument("--journal", default=None,
                   help="Chemin du journal JSONL (sinon, sans journal).")
    return p.parse_args()


def main():
    args = parse_args()
    cfg = SimConfig(
        name="god_view_live", seed=args.seed,
        founders=args.founders, max_agents=args.max_agents,
        bounds_km=(args.bounds_km, args.bounds_km),
        spawn_radius_m=max(60.0, args.bounds_km * 1000.0 * 0.15),
        cultures=args.cultures, drive_accel=args.drive_accel,
    )
    sim = Simulation(cfg, journal_path=args.journal)
    sim.bootstrap()
    ctl = SimController(target_tps=args.target_tps)

    srv, god, god_log = start_god_server(sim, ctl, host=args.host, port=args.port)
    print(f"[god-view] Genesis Engine running")
    print(f"[god-view] founders={cfg.founders}  cultures={cfg.cultures}  "
          f"bounds={cfg.bounds_km[0]:.2f}km  seed=0x{cfg.seed:X}")
    print(f"[god-view] open  http://localhost:{args.port}/  in a browser")
    print(f"[god-view] god avatar v2 at  http://localhost:{args.port}/god_view_v2.html")
    print(f"[god-view] god endpoints under  /api/god/*  (interventions={god.intervention_count})")
    print(f"[god-view] Ctrl-C to stop")
    print()

    # Sim loop with controller-driven pacing
    sim_start = time.monotonic()
    log_every = 50
    try:
        while not ctl.stop:
            with ctl.lock:
                paused = ctl.paused
                speed = ctl.speed
                step_req = ctl.single_step
                if step_req:
                    ctl.single_step = False
            if paused and not step_req:
                time.sleep(0.05); continue
            t0 = time.monotonic()
            stats = sim.step()
            from engine.dashboard import feed_event_tail
            feed_event_tail(ctl, sim.annalist)
            # Pace
            target_dt = 1.0 / max(0.01, ctl.target_tps * speed)
            actual_dt = time.monotonic() - t0
            if actual_dt < target_dt and not step_req:
                time.sleep(target_dt - actual_dt)
            if sim.tick % log_every == 0:
                elapsed = time.monotonic() - sim_start
                tps_avg = sim.tick / max(elapsed, 1e-6)
                print(f"[god-view] tick {sim.tick:5d}  alive={stats.alive:4d}  "
                      f"births={stats.cum_births:4d}  deaths={stats.cum_deaths:4d}  "
                      f"events={stats.cum_events:5d}  avg {tps_avg:.1f} TPS")
    except KeyboardInterrupt:
        print("\n[god-view] stopping…")
    finally:
        srv.shutdown()
        try:
            sim.annalist.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
