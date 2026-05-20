"""Common helpers for experiment scripts."""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Optional

# Make the runtime importable when run from anywhere
HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DIR = os.path.abspath(os.path.join(HERE, ".."))
if RUNTIME_DIR not in sys.path:
    sys.path.insert(0, RUNTIME_DIR)

from engine.sim import Simulation, SimConfig  # noqa: E402


def run_experiment(name: str, cfg: SimConfig, ticks: int,
                   journal: Optional[str] = None,
                   verbose: bool = True) -> dict:
    """Run a simulation and return summary stats + write metrics JSON."""
    if journal is None:
        journal = os.path.join(RUNTIME_DIR, "journals", f"{name}.jsonl")
    os.makedirs(os.path.dirname(journal), exist_ok=True)
    # Truncate any existing journal so each run is fresh.
    open(journal, "w").close()
    sim = Simulation(cfg, journal_path=journal)
    t0 = time.monotonic()
    last_report = 0
    for i in range(ticks):
        s = sim.step()
        if verbose and (i + 1) % max(1, ticks // 10) == 0:
            elapsed = time.monotonic() - t0
            tps = (i + 1) / max(elapsed, 1e-6)
            print(f"  [{name}] tick {i+1}/{ticks} alive={s.alive:>4} "
                  f"births={s.cum_births:>4} deaths={s.cum_deaths:>4} "
                  f"events={s.cum_events:>5} {tps:.1f}TPS")
    elapsed = time.monotonic() - t0
    summary = {
        "experiment": name,
        "config": {
            "seed": cfg.seed, "founders": cfg.founders, "max_agents": cfg.max_agents,
            "bounds_km": cfg.bounds_km, "cultures": cfg.cultures,
            "drive_accel": cfg.drive_accel,
            "catastrophe_at_tick": cfg.catastrophe_at_tick,
        },
        "ticks_run": ticks,
        "wall_clock_s": elapsed,
        "tps": ticks / max(elapsed, 1e-6),
        "final_alive": int(sim.stats.alive),
        "cum_births": int(sim.stats.cum_births),
        "cum_deaths": int(sim.stats.cum_deaths),
        "cum_events": int(sim.stats.cum_events),
        "metrics": sim.annalist.metrics_to_dict(),
        "journal": journal,
        "multi_rate_coupler": bool(getattr(sim, "_coupler_wrapped", False)),
        "emergence_subsystems": bool(cfg.emergence_subsystems),
    }
    emergence = (sim.snapshot().get("emergence") or {})
    if emergence.get("epidemic"):
        summary["epidemic"] = emergence["epidemic"]
    if emergence.get("koeppen"):
        summary["koeppen"] = emergence["koeppen"]
    sim.annalist.close()
    out = os.path.join(RUNTIME_DIR, "artifacts", f"{name}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    if verbose:
        print(f"  [{name}] DONE: {elapsed:.1f}s, {summary['tps']:.1f} TPS, journal={journal}")
        print(f"  [{name}] summary → {out}")
    return summary
