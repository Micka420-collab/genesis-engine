"""Run all experiments in sequence and print a comparative summary.

2026-05-18 audit refresh: switched from ``os.system`` subprocess calls to
in-process imports so configurations stay coherent and we can collect
the post-audit metrics that were silently zero before (cum_fights,
cum_shares, cum_vocalizations, groups_formed_cum, …). A single
consolidated ``all_experiments_summary.json`` is written at the end.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DIR = os.path.abspath(os.path.join(HERE, ".."))
if RUNTIME_DIR not in sys.path:
    sys.path.insert(0, RUNTIME_DIR)
# The experiments dir holds ``_runner.py``; make it importable here too.
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from _runner import run_experiment, SimConfig  # noqa: E402


# (name, ticks, SimConfig kwargs) — mirrors each experiment's own script
# so editing one place is enough. Names match the per-file scripts so
# downstream tooling that looks up artifacts/<name>.json keeps working.
EXPERIMENTS = [
    ("exp1_scarcity", 250, dict(
        seed=0xC0FFEE_DEADBEEF, founders=10, max_agents=80,
        bounds_km=(0.4, 0.4), cultures=1, drive_accel=4000.0)),
    ("exp2_food_pressure", 200, dict(
        seed=0xBEEFCAFE_99, founders=50, max_agents=200,
        bounds_km=(0.6, 0.6), cultures=1, drive_accel=6000.0)),
    ("exp3_two_cultures", 250, dict(
        seed=0x1234_ABCD_5678, founders=24, max_agents=200,
        bounds_km=(0.9, 0.9), cultures=2, drive_accel=3500.0)),
    ("exp4_catastrophe", 200, dict(
        seed=0xD15A57E2, founders=30, max_agents=200,
        bounds_km=(0.8, 0.8), cultures=1, drive_accel=4000.0,
        catastrophe_at_tick=80, catastrophe_radius_m=250.0,
        catastrophe_damage=0.6)),
    ("stress_100", 150, dict(
        seed=0xFEEDFACE, founders=100, max_agents=500,
        bounds_km=(1.0, 1.0), cultures=1, drive_accel=2500.0)),
    ("exp5_stress_200", 300, dict(
        seed=0xABCDEF00, founders=200, max_agents=1000,
        bounds_km=(1.5, 1.5), cultures=2, drive_accel=2000.0)),
]


def _row_from_summary(summary: dict) -> dict:
    """Pull a compact, comparable row out of the per-experiment metrics."""
    m = summary.get("metrics", {})
    last = lambda key: int((m.get(key) or [0])[-1])  # noqa: E731
    return {
        "name": summary["experiment"],
        "ticks": int(summary["ticks_run"]),
        "wall_s": round(float(summary.get("wall_clock_s", 0.0)), 2),
        "tps": round(float(summary.get("tps", 0.0)), 2),
        "final_alive": int(summary["final_alive"]),
        "cum_births": int(summary["cum_births"]),
        "cum_deaths": int(summary["cum_deaths"]),
        # Post-audit metrics (were 0 prior to 2026-05-17 SHARE/FIGHT fix):
        "cum_fights": last("fights_cum"),
        "cum_shares": last("shares_cum"),
        "cum_matings": last("matings_cum"),
        "vocalizations_cum": int(m.get("vocalizations_cum", 0)),
        "competitions_cum": int(m.get("competitions_cum", 0)),
        "groups_formed_cum": int(m.get("groups_formed_cum", 0)),
        "groups_dissolved_cum": int(m.get("groups_dissolved_cum", 0)),
        "distinct_lex_signatures": int(m.get("distinct_lex_signatures", 0)),
        "events_emitted": int(m.get("events_emitted", 0)),
    }


def main() -> int:
    rows = []
    for name, ticks, kwargs in EXPERIMENTS:
        cfg = SimConfig(name=name, **kwargs)
        print(f"\n=== {name} ({ticks} ticks, founders={cfg.founders}, "
              f"max_agents={cfg.max_agents}) ===")
        summary = run_experiment(name, cfg, ticks=ticks)
        rows.append(_row_from_summary(summary))

    artifacts = os.path.abspath(os.path.join(HERE, "..", "artifacts"))
    out = os.path.join(artifacts, "all_experiments_summary.json")
    os.makedirs(artifacts, exist_ok=True)
    with open(out, "w") as f:
        json.dump(rows, f, indent=2)

    print("\n=== ALL EXPERIMENTS SUMMARY ===")
    header = (f"{'experiment':<20} {'ticks':>6} {'wall(s)':>8} {'TPS':>6} "
              f"{'alive':>6} {'births':>7} {'deaths':>7} "
              f"{'shares':>7} {'fights':>7} {'voc':>5} {'grps':>5}")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['name']:<20} {r['ticks']:>6} {r['wall_s']:>8.1f} "
              f"{r['tps']:>6.1f} {r['final_alive']:>6} "
              f"{r['cum_births']:>7} {r['cum_deaths']:>7} "
              f"{r['cum_shares']:>7} {r['cum_fights']:>7} "
              f"{r['vocalizations_cum']:>5} {r['groups_formed_cum']:>5}")

    print(f"\nConsolidated summary -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
