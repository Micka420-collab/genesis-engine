#!/usr/bin/env python
"""Unified Genesis Engine launcher.

Usage:
    python run.py <experiment> [--ticks N] [--no-5cd] [--realism] [--hydrology-mode MODE] ...

Where <experiment> is one of:
    realism - full_biosphere + knowledge_layers + sv1d cross-chunk hydrology;
        runs engine.genesis_bootstrap.bootstrap_genesis_sim on startup
        (continental genesis substrate). Defaults: founders=8, max_agents=200,
        bounds_km=(2,2), drive_accel=8000, ticks=500.
    terre - origins + realism merged: emergent sapients, genesis, layers,
        rust WorldGraph tick, 5cd, sv1d hydrology (2000 ticks default).
    exp1_scarcity, exp2_food_pressure, exp3_two_cultures, exp4_catastrophe,
    stress_100, exp5_stress_200, origins
or a custom name + --founders N --max-agents M --bounds-km K to roll your own.
Use ``--realism`` to merge the realism preset into any experiment (preset keys
override the named preset for overlapping fields).

Writes:
    artifacts/<experiment>.json          - dashboard-ready summary + metrics
    journals/<experiment>.jsonl          - full event journal
    artifacts/<experiment>_snapshot.json - final agent positions (god-view)

Open dashboard.html (sibling file) in a browser to visualise.

Civilization subsystems (coupler, epidemic, Koeppen, observable) wire in
``Simulation.__init__`` via ``engine/sim_emergence.py`` - this script only
runs ``sim.step()`` in a loop.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from engine.sim import Simulation, SimConfig  # noqa: E402


_PRESET_REALISM_SEED = 0xEA11_5CAF_DEAD_BEEF

PRESETS = {
    "realism": dict(
        seed=_PRESET_REALISM_SEED,
        founders=8,
        max_agents=200,
        bounds_km=(2.0, 2.0),
        cultures=1,
        drive_accel=8000.0,
        ticks=500,
        knowledge_layers=True,
        full_biosphere=True,
        hydrology_mode="sv1d",
        macro_commerce=True,
        rust_worldgraph_prod=True,
    ),
    "terre": dict(
        seed=0x7E112E_DE000000,
        founders=0,
        emergent_origins=True,
        full_biosphere=True,
        max_emergent_founders=2,
        knowledge_layers=True,
        hydrology_mode="sv1d",
        macro_commerce=True,
        rust_worldgraph_prod=True,
        max_agents=200,
        bounds_km=(2.5, 2.5),
        cultures=1,
        drive_accel=10000.0,
        ticks=2000,
    ),
    "exp1_scarcity": dict(
        seed=0xC0FFEE_DEADBEEF, founders=10, max_agents=80,
        bounds_km=(0.4, 0.4), cultures=1, drive_accel=4000.0, ticks=250),
    "exp2_food_pressure": dict(
        seed=0xBADF00D, founders=50, max_agents=200,
        bounds_km=(0.6, 0.6), cultures=1, drive_accel=3500.0, ticks=300),
    "exp3_two_cultures": dict(
        seed=0x1234_ABCD_5678, founders=24, max_agents=200,
        bounds_km=(0.9, 0.9), cultures=2, drive_accel=3500.0, ticks=250),
    "exp4_catastrophe": dict(
        seed=0xD15A57E2, founders=30, max_agents=200,
        bounds_km=(0.8, 0.8), cultures=1, drive_accel=4000.0,
        catastrophe_at_tick=80, catastrophe_radius_m=250.0,
        catastrophe_damage=0.6, ticks=200),
    "stress_100": dict(
        seed=0xFEEDFACE, founders=100, max_agents=500,
        bounds_km=(1.0, 1.0), cultures=1, drive_accel=2500.0, ticks=150),
    "exp5_stress_200": dict(
        seed=0xABCDEF00, founders=200, max_agents=1000,
        bounds_km=(1.5, 1.5), cultures=2, drive_accel=2000.0, ticks=300),
    "origins": dict(
        seed=0x0B1601FE, founders=0, emergent_origins=True,
        full_biosphere=True, max_emergent_founders=2, max_agents=120,
        bounds_km=(2.0, 2.0), cultures=1, drive_accel=12000.0, ticks=8000),
}


def _resolve_config(args) -> Tuple[SimConfig, int]:
    name = args.experiment
    base = dict(PRESETS.get(name, {}))
    if getattr(args, "realism", False):
        r = dict(PRESETS["realism"])
        base = {**base, **r}
    ticks = int(args.ticks or base.pop("ticks", 200))
    base.pop("ticks", None)
    if args.seed is not None:
        base["seed"] = int(args.seed, 0)
    if args.founders is not None:
        base["founders"] = int(args.founders)
    if args.max_agents is not None:
        base["max_agents"] = int(args.max_agents)
    if args.bounds_km is not None:
        base["bounds_km"] = (float(args.bounds_km), float(args.bounds_km))
    if args.cultures is not None:
        base["cultures"] = int(args.cultures)
    if args.drive_accel is not None:
        base["drive_accel"] = float(args.drive_accel)
    if args.emergent_origins:
        base["emergent_origins"] = True
        base["full_biosphere"] = True
        base["founders"] = 0
        base.setdefault("max_emergent_founders", 2)
    if getattr(args, "full_biosphere", False):
        base["full_biosphere"] = True
    if getattr(args, "knowledge_layers", False):
        base["knowledge_layers"] = True
    if args.hydrology_mode is not None:
        base["hydrology_mode"] = str(args.hydrology_mode)
    if not base:
        raise SystemExit(
            f"Unknown experiment '{name}'. Either pick a preset "
            f"({', '.join(PRESETS)}) or pass --founders/--max-agents/--bounds-km.")
    base.setdefault("name", name)
    cfg = SimConfig(**base)
    return cfg, ticks


def _snapshot(sim: Simulation) -> dict:
    agents = sim.agents
    rows = []
    for row in range(agents.n_active):
        if not bool(agents.alive[row]):
            continue
        try:
            culture = int(agents.relations[row].culture_id)
        except Exception:
            culture = 0
        try:
            group_id = agents.relations[row].group_id
        except Exception:
            group_id = None
        rows.append({
            "row": int(row),
            "uuid": str(agents.uuid[row]),
            "gen": int(agents.generation[row]),
            "x": float(agents.pos[row, 0]),
            "y": float(agents.pos[row, 1]),
            "h": float(agents.hunger[row]),
            "t": float(agents.thirst[row]),
            "v": float(agents.vitality[row]),
            "a": int(agents.action[row]),
            "c": culture,
            "g": (int(group_id) if group_id is not None else -1),
            "agg": float(agents.aggression[row]),
            "agr": float(agents.agreeableness[row]),
            "cur": float(agents.curiosity[row]),
        })
    bx_m = sim.cfg.bounds_km[0] * 500.0
    by_m = sim.cfg.bounds_km[1] * 500.0
    return {"bounds_m": [bx_m, by_m], "hydrology_mode": str(sim.cfg.hydrology_mode),
            "agents": rows}


def _collapse_metrics(raw: dict) -> dict:
    """Collapse per-tick metric arrays so each tick value appears once.

    5cd sub-ticks emit additional `record_tick` calls per tick, which
    appends an extra row to every metrics array. We keep the last
    observation per tick.
    """
    ticks = raw.get("tick") or []
    keys = ("population", "births_cum", "deaths_cum", "avg_hunger",
            "avg_thirst", "avg_vitality", "fights_cum", "shares_cum",
            "matings_cum", "avg_generation", "avg_affinity")
    if not ticks:
        return raw
    keep_index: dict = {}
    for idx, t in enumerate(ticks):
        keep_index[int(t)] = idx
    sorted_ticks = sorted(keep_index.keys())
    out = {"tick": list(sorted_ticks)}
    for k in keys:
        arr = raw.get(k)
        if not arr or len(arr) != len(ticks):
            out[k] = arr
            continue
        out[k] = [arr[keep_index[t]] for t in sorted_ticks]
    for k, v in raw.items():
        if k not in out and k != "tick":
            out[k] = v
    return out


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("experiment", help="Preset name or custom label.")
    p.add_argument("--ticks", type=int, default=None,
                   help="Number of simulation ticks (default: preset value or 200).")
    p.add_argument("--no-5cd", action="store_true",
                   help="Skip the Phase-5cd extensions (faster, fewer event kinds).")
    p.add_argument("--seed", default=None, help="World seed (int, 0x... ok).")
    p.add_argument("--founders", type=int, default=None)
    p.add_argument("--max-agents", type=int, default=None)
    p.add_argument("--bounds-km", type=float, default=None,
                   help="Square bounds, in km (e.g. 1.0).")
    p.add_argument("--cultures", type=int, default=None)
    p.add_argument("--drive-accel", type=float, default=None)
    p.add_argument("--emergent-origins", action="store_true",
                   help="100%% emergent biosphere: protocells -> microbes -> fauna -> "
                        "sapients (max 2 by default). No scripted founders.")
    p.add_argument("--full-biosphere", action="store_true",
                   help="Install photosynthesis + ancient plant/animal evolution.")
    p.add_argument("--knowledge-layers", action="store_true",
                   help="Physics + Materials Project + voxel architecture + social topology.")
    p.add_argument("--realism", action="store_true",
                   help="Merge realism preset (biosphere, knowledge_layers, sv1d hydrology, "
                        "defaults); triggers genesis bootstrap after Simulation(). "
                        "Same as experiment name 'realism' when used alone.")
    p.add_argument("--hydrology-mode", choices=("stub", "sv1d", "lbm"), default=None,
                   help="Cross-chunk hydrology model (default: stub, or from preset).")
    p.add_argument("--journal", default=None,
                   help="Override journal path (default: journals/<exp>.jsonl).")
    p.add_argument("--observe-jsonl", default=None,
                   help="Append live observable JSONL each emergence tick "
                        "(default for realism/terre: artifacts/<exp>_observe.jsonl).")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress per-tick progress reports.")
    args = p.parse_args()

    cfg, ticks = _resolve_config(args)
    name = cfg.name
    use_full_stack = (
        getattr(args, "realism", False)
        or args.experiment in ("realism", "terre")
    )
    journal_path = args.journal or os.path.join(
        HERE, "journals", f"{name}.jsonl")
    os.makedirs(os.path.dirname(journal_path), exist_ok=True)
    open(journal_path, "w").close()  # truncate

    sim = Simulation(cfg, journal_path=journal_path)

    observe_jsonl = args.observe_jsonl
    if observe_jsonl is None and use_full_stack:
        observe_jsonl = os.path.join(HERE, "artifacts", f"{name}_observe.jsonl")
    if observe_jsonl:
        os.makedirs(os.path.dirname(observe_jsonl) or ".", exist_ok=True)
        open(observe_jsonl, "w").close()
        sim._observable_jsonl_path = observe_jsonl

    stack_status: dict = {}
    if use_full_stack:
        try:
            from engine.full_stack import wire_full_stack

            stack_status = wire_full_stack(
                sim,
                genesis=True,
                rust_worldgraph=True,
                mp_api=bool(cfg.knowledge_layers),
                five_cd=not args.no_5cd,
                macro_commerce=bool(getattr(cfg, "macro_commerce", False)),
            )
        except Exception as exc:
            print(f"[run] full stack wiring failed (continuing): {exc}",
                  file=sys.stderr)

    genesis_bootstrapped = bool(stack_status.get("genesis_bootstrapped"))
    five_cd_installed = bool(stack_status.get("five_cd"))
    if not use_full_stack and not args.no_5cd:
        try:
            from engine.sim_5cd_integration import install
            install(sim)
            five_cd_installed = True
        except Exception as exc:
            print(f"[run] 5cd install failed (continuing without): {exc}",
                  file=sys.stderr)

    coupler_installed = bool(getattr(sim, "_coupler_wrapped", False))

    if not args.quiet:
        print(f"[run] {name}: founders={cfg.founders} emergent={cfg.emergent_origins} "
              f"cap={cfg.max_agents} bounds_km={cfg.bounds_km} cultures={cfg.cultures} "
              f"drive_accel={cfg.drive_accel} hydrology_mode={cfg.hydrology_mode} "
              f"genesis={genesis_bootstrapped} rust={stack_status.get('rust_worldgraph')} "
              f"5cd={five_cd_installed} "
              f"ticks={ticks} journal={journal_path}")

    t0 = time.monotonic()
    report_every = max(1, ticks // 10)
    last_population = 0
    for i in range(ticks):
        stats = sim.step()
        last_population = int(stats.alive)
        if not args.quiet and (i + 1) % report_every == 0:
            elapsed = time.monotonic() - t0
            tps = (i + 1) / max(elapsed, 1e-6)
            print(f"  tick {i+1}/{ticks} alive={last_population:>4} "
                  f"births={stats.cum_births:>5} deaths={stats.cum_deaths:>5} "
                  f"events={stats.cum_events:>6} {tps:.1f}TPS "
                  f"chunks={stats.chunks_in_mem}")
        if (i + 1) % 50 == 0:
            from engine.cognition import promote_memories
            n = sim.agents.n_active
            for row in range(n):
                if bool(sim.agents.alive[row]):
                    promote_memories(sim.agents, row)
    elapsed = time.monotonic() - t0

    metrics_raw = sim.annalist.metrics_to_dict()
    metrics = _collapse_metrics(metrics_raw)

    emergence = (sim.snapshot().get("emergence") or {})
    epidemic_summary = emergence.get("epidemic")

    summary = {
        "experiment": name,
        "config": {
            "seed": int(cfg.seed),
            "founders": int(cfg.founders),
            "max_agents": int(cfg.max_agents),
            "bounds_km": list(cfg.bounds_km),
            "cultures": int(cfg.cultures),
            "drive_accel": float(cfg.drive_accel),
            "hydrology_mode": str(cfg.hydrology_mode),
            "genesis_bootstrapped": bool(genesis_bootstrapped),
            "rust_worldgraph": bool(stack_status.get("rust_worldgraph")),
            "macro_commerce": bool(stack_status.get("macro_commerce")),
            "mp_api_records": int(stack_status.get("mp_api_records", 0)),
            "catastrophe_at_tick": int(cfg.catastrophe_at_tick),
            "5cd_installed": bool(five_cd_installed),
            "multi_rate_coupler": bool(coupler_installed),
            "emergence_subsystems": bool(cfg.emergence_subsystems),
        },
        "ticks_run": int(ticks),
        "wall_clock_s": float(elapsed),
        "tps": float(ticks / max(elapsed, 1e-6)),
        "final_alive": int(last_population),
        "cum_births": int(sim.stats.cum_births),
        "cum_deaths": int(sim.stats.cum_deaths),
        "cum_events": int(sim.stats.cum_events),
        "cum_trades": int(getattr(sim.annalist, "cum_trades", 0)),
        "metrics": metrics,
        "journal": journal_path,
    }
    if observe_jsonl:
        summary["observe_jsonl"] = observe_jsonl
    if epidemic_summary:
        summary["epidemic"] = epidemic_summary
    if emergence.get("koeppen"):
        summary["koeppen"] = emergence["koeppen"]
    if emergence.get("rust_worldgraph"):
        summary["rust_worldgraph"] = emergence["rust_worldgraph"]
    if emergence.get("commerce"):
        summary["commerce"] = emergence["commerce"]
    live = getattr(getattr(sim, "_emergence", None), "live_observable", None)
    if live:
        summary["observable"] = live

    artifact_dir = os.path.join(HERE, "artifacts")
    os.makedirs(artifact_dir, exist_ok=True)
    artifact_path = os.path.join(artifact_dir, f"{name}.json")
    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    snapshot_path = os.path.join(artifact_dir, f"{name}_snapshot.json")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(_snapshot(sim), f, indent=2)

    sim.annalist.close()

    if not args.quiet:
        print(f"[run] DONE {elapsed:.1f}s, {summary['tps']:.1f} TPS, "
              f"alive={last_population}, journal={journal_path}")
        print(f"[run] summary  -> {artifact_path}")
        print(f"[run] snapshot -> {snapshot_path}")
        print(f"[run] open dashboard.html, pick "
              f"{os.path.basename(artifact_path)} + the journal file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
