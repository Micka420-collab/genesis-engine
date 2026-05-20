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
from engine.dashboard import SimController, feed_event_tail, start_god_server
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
    p.add_argument("--genesis-resolution", type=int, default=192,
                   help="Macro grid resolution (higher = more Earth-like detail).")
    p.add_argument("--port", type=int, default=8090)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--target-tps", type=float, default=8.0)
    p.add_argument("--ticks", type=int, default=0,
                   help="0 = run until Ctrl+C")
    p.add_argument("--journal", default=None,
                   help="JSONL event journal (default: artifacts/earth_console.jsonl)")
    p.add_argument("--no-graphcast-lite", action="store_true",
                   help="Disable GraphCast-lite macro climate prior.")
    return p.parse_args()


def main():
    args = parse_args()
    if args.journal is None:
        art = os.path.abspath(os.path.join(RUNTIME, "..", "artifacts"))
        os.makedirs(art, exist_ok=True)
        args.journal = os.path.join(art, "earth_console.jsonl")
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
        emergent_cognition=True,
        hydrology_mode="sv1d",
        hydrology_cross_chunk=True,
        observable_every=15,
        graphcast_lite_prior=not args.no_graphcast_lite,
        autonomous_world=True,
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
    try:
        from engine.meteorology import install_meteorology

        install_meteorology(sim)
    except Exception as exc:
        print(f"[earth-console] meteorology skipped: {exc}")
    sim._observable_jsonl_path = os.path.join(
        os.path.dirname(args.journal), "earth_console_observable.jsonl")
    sim.bootstrap()
    from engine.emergence_stack import wire_emergence_v2
    ev2 = wire_emergence_v2(
        sim,
        genome_brain=bool(cfg.emergent_cognition),
        graphcast_lite=bool(cfg.graphcast_lite_prior),
        autonomous_world=bool(cfg.autonomous_world),
    )
    print(f"[earth-console] emergence_v2  {ev2}")

    ctl = SimController(target_tps=args.target_tps)
    srv, god, _ = start_god_server(sim, ctl, host=args.host, port=args.port)

    url = f"http://{args.host}:{args.port}/"
    print("[earth-console] Terre virtuelle — Genesis macro + sim live")
    print(f"[earth-console] seed=0x{cfg.seed:X}  bounds={cfg.bounds_km[0]:.2f} km  "
          f"genesis={args.genesis_resolution}px")
    print(f"[earth-console] open  {url}")
    print(f"[earth-console] journal  {args.journal}")
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
            feed_event_tail(ctl, sim.annalist)
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
