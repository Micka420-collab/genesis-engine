"""Genesis Earth Console — live Terre virtuelle avec contrôle UI.

Bootstrap Genesis (macro continent) + stack réalisme, puis serveur HTTP
``earth_console.html`` (pan/zoom, couches, carte macro, agents).

Usage::

    python scripts/run_earth_console.py
    python scripts/run_earth_console.py --port 8090 --ticks 0

Ouvre http://127.0.0.1:8090/ dans le navigateur.
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
from engine.genesis_bootstrap import bootstrap_genesis_sim
from engine.full_stack import wire_full_stack
from engine.world_genesis import GenesisParams


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=lambda s: int(s, 0), default=0x7E4E_7E00)
    p.add_argument("--founders", type=int, default=40)
    p.add_argument("--max-agents", type=int, default=500)
    p.add_argument("--bounds-km", type=float, default=1.2,
                   help="Simulation footprint (km) anchored on macro centre.")
    p.add_argument("--genesis-resolution", type=int, default=128)
    p.add_argument("--port", type=int, default=8090)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--target-tps", type=float, default=8.0)
    p.add_argument("--ticks", type=int, default=0,
                   help="0 = run until Ctrl+C")
    p.add_argument("--journal", default=None)
    return p.parse_args()


def main():
    args = parse_args()
    cfg = SimConfig(
        name="earth_console",
        seed=args.seed,
        founders=args.founders,
        max_agents=args.max_agents,
        bounds_km=(args.bounds_km, args.bounds_km),
        spawn_radius_m=max(80.0, args.bounds_km * 1000.0 * 0.2),
        cultures=3,
        drive_accel=1800.0,
        macro_commerce=True,
        rust_worldgraph_prod=False,
        life_emergence=True,
        emergence_subsystems=True,
    )
    sim = Simulation(cfg, journal_path=args.journal)
    gp = GenesisParams(
        seed=int(cfg.seed) & 0xFFFFFFFFFFFFFFFF,
        resolution=args.genesis_resolution,
        n_plates=8,
        erosion_iters=12,
        rain_iters=4,
    )
    bootstrap_genesis_sim(sim, seed=cfg.seed, genesis_params=gp)
    wire_full_stack(
        sim,
        genesis=False,
        rust_worldgraph=True,
        five_cd=True,
        macro_commerce=bool(cfg.macro_commerce),
    )
    sim.bootstrap()

    ctl = SimController(target_tps=args.target_tps)
    srv, god, _ = start_god_server(sim, ctl, host=args.host, port=args.port)

    url = f"http://{args.host}:{args.port}/"
    print("[earth-console] Terre virtuelle — Genesis macro + sim live")
    print(f"[earth-console] seed=0x{cfg.seed:X}  bounds={cfg.bounds_km[0]:.2f} km  "
          f"genesis={args.genesis_resolution}px")
    print(f"[earth-console] open  {url}")
    print(f"[earth-console] legacy god view: {url}god_view_v2.html")
    print("[earth-console] Ctrl+C to stop")

    sim_start = time.monotonic()
    log_every = 100
    try:
        tick_limit = args.ticks if args.ticks > 0 else None
        while not ctl.stop:
            with ctl.lock:
                paused = ctl.paused
                speed = ctl.speed
                step_req = ctl.single_step
                if step_req:
                    ctl.single_step = False
            if paused and not step_req:
                time.sleep(0.05)
                continue
            t0 = time.monotonic()
            stats = sim.step()
            target_dt = 1.0 / max(0.01, ctl.target_tps * speed)
            elapsed = time.monotonic() - t0
            if elapsed < target_dt and not step_req:
                time.sleep(target_dt - elapsed)
            if sim.tick % log_every == 0:
                wall = time.monotonic() - sim_start
                print(f"[earth-console] tick {sim.tick:5d}  alive={stats.alive:4d}  "
                      f"births={stats.cum_births:4d}  TPS={sim.tick / max(wall, 1e-6):.1f}")
            if tick_limit is not None and sim.tick >= tick_limit:
                ctl.stop = True
    except KeyboardInterrupt:
        print("\n[earth-console] stopping…")
    finally:
        srv.shutdown()
        try:
            sim.annalist.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
