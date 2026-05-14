"""Phase 5 validation: re-run the four scientific experiments + stress
test with the Phase 5 engine and write a comparative summary.

Each experiment uses a fixed seed (replayable).  Outputs:
  - runtime/journals/phase5_<name>.jsonl  — per-tick event journal
  - runtime/artifacts/phase5_<name>.json  — summary stats + metrics
  - runtime/artifacts/phase5_summary.json — aggregated table
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.abspath(os.path.join(HERE, ".."))
if RUNTIME not in sys.path:
    sys.path.insert(0, RUNTIME)

from engine.sim import Simulation, SimConfig
from engine.cognition import FORAGE_KCAL_PER_KG


EXPERIMENTS = [
    # name, hypothesis, SimConfig kwargs, ticks
    ("exp1_scarcity",
     "10 agents in a small bounded world -> mix of competition + cooperation",
     dict(seed=0xC0FFEE_DEADBEEF, founders=10, max_agents=80,
          bounds_km=(0.4, 0.4), cultures=1, drive_accel=4000.0,
          spawn_radius_m=60.0),
     150),
    ("exp2_food_pressure",
     "50 agents under harsh drive growth -> mass mortality, overshoot",
     dict(seed=0xC0FFEE_DEADBEEF, founders=50, max_agents=250,
          bounds_km=(0.6, 0.6), cultures=1, drive_accel=6000.0,
          spawn_radius_m=80.0),
     100),
    ("exp3_two_cultures",
     "2 founder clusters -> meeting dynamics, interbreeding, multi-cluster lineages",
     dict(seed=0xC0FFEE_DEADBEEF, founders=48, max_agents=250,
          bounds_km=(0.9, 0.9), cultures=2, drive_accel=4000.0,
          spawn_radius_m=80.0),
     120),
    ("exp4_catastrophe",
     "Environmental disaster at tick 60 -> adaptation + recovery",
     dict(seed=0xD15A57E2, founders=30, max_agents=200,
          bounds_km=(0.8, 0.8), cultures=1, drive_accel=4000.0,
          spawn_radius_m=80.0,
          catastrophe_at_tick=60, catastrophe_radius_m=250.0,
          catastrophe_damage=0.6),
     120),
    ("stress_100",
     "100-founder sustained run (capacity proof)",
     dict(seed=0xBEEF, founders=100, max_agents=500,
          bounds_km=(0.7, 0.7), cultures=1, drive_accel=2000.0,
          spawn_radius_m=80.0),
     50),
]


def run_one(name: str, hypothesis: str, cfg_kw: dict, ticks: int) -> dict:
    journal = os.path.join(RUNTIME, "journals", f"phase5_{name}.jsonl")
    os.makedirs(os.path.dirname(journal), exist_ok=True)
    open(journal, "w").close()
    cfg = SimConfig(name=name, **cfg_kw)
    sim = Simulation(cfg, journal_path=journal)
    t0 = time.monotonic()
    last_report = 0
    for i in range(ticks):
        s = sim.step()
        if (i + 1) % max(1, ticks // 5) == 0:
            elapsed = time.monotonic() - t0
            tps = (i + 1) / max(elapsed, 1e-6)
            print(f"  [{name}] {i+1}/{ticks} alive={s.alive} "
                  f"births={s.cum_births} deaths={s.cum_deaths} "
                  f"events={s.cum_events} {tps:.1f}TPS")
    elapsed = time.monotonic() - t0
    m = sim.annalist.metrics_to_dict()
    summary = {
        "experiment": name,
        "hypothesis": hypothesis,
        "config": {k: (list(v) if isinstance(v, tuple) else v) for k, v in cfg_kw.items()},
        "ticks_run": ticks,
        "wall_clock_s": elapsed,
        "tps": ticks / max(elapsed, 1e-6),
        "final_alive": int(sim.stats.alive),
        "cum_births": int(sim.stats.cum_births),
        "cum_deaths": int(sim.stats.cum_deaths),
        "cum_events": int(sim.stats.cum_events),
        "vocalizations": int(m["vocalizations_cum"]),
        "competitions": int(m["competitions_cum"]),
        "groups_formed": int(m["groups_formed_cum"]),
        "groups_dissolved": int(m["groups_dissolved_cum"]),
        "distinct_lex_signatures": int(m["distinct_lex_signatures"]),
        "fights_cum": int(m["fights_cum"][-1]) if m["fights_cum"] else 0,
        "shares_cum": int(m["shares_cum"][-1]) if m["shares_cum"] else 0,
        "matings_cum": int(m["matings_cum"][-1]) if m["matings_cum"] else 0,
        "max_generation": int(max(m["avg_generation"]) if m["avg_generation"] else 0),
        "avg_affinity_final": float(m["avg_affinity"][-1]) if m["avg_affinity"] else 0.0,
        "journal": journal,
        "metrics": m,
    }
    sim.annalist.close()
    out = os.path.join(RUNTIME, "artifacts", f"phase5_{name}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  [{name}] DONE: {elapsed:.1f}s, {summary['tps']:.1f} TPS")
    print(f"           shares={summary['shares_cum']} fights={summary['fights_cum']} "
          f"vocs={summary['vocalizations']} groups={summary['groups_formed']}/"
          f"{summary['groups_dissolved']}")
    return summary


def main():
    print(f"Phase 5 validation run — FORAGE_KCAL_PER_KG={FORAGE_KCAL_PER_KG}")
    print("=" * 76)
    rows = []
    for name, hyp, kw, ticks in EXPERIMENTS:
        print(f"\n=== {name} ===")
        print(f"  hypothesis: {hyp}")
        rows.append(run_one(name, hyp, kw, ticks))
    agg = {
        "phase": 5,
        "experiments": [
            {k: r[k] for k in ("experiment", "ticks_run", "wall_clock_s", "tps",
                               "final_alive", "cum_births", "cum_deaths",
                               "vocalizations", "competitions", "groups_formed",
                               "groups_dissolved", "fights_cum", "shares_cum",
                               "matings_cum", "max_generation",
                               "avg_affinity_final", "distinct_lex_signatures")}
            for r in rows
        ],
    }
    out = os.path.join(RUNTIME, "artifacts", "phase5_summary.json")
    with open(out, "w") as f:
        json.dump(agg, f, indent=2)
    print("\n" + "=" * 76)
    print("PHASE 5 SUMMARY")
    print("=" * 76)
    header = (f"{'experiment':<22} {'ticks':>5} {'wall(s)':>7} {'TPS':>5} "
              f"{'alive':>5} {'births':>6} {'deaths':>6} {'matings':>7} "
              f"{'vocs':>5} {'comps':>5} {'shares':>6} {'fights':>6} "
              f"{'groups':>6} {'diss':>4}")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['experiment']:<22} {r['ticks_run']:>5} {r['wall_clock_s']:>7.1f} "
              f"{r['tps']:>5.1f} {r['final_alive']:>5} {r['cum_births']:>6} "
              f"{r['cum_deaths']:>6} {r['matings_cum']:>7} {r['vocalizations']:>5} "
              f"{r['competitions']:>5} {r['shares_cum']:>6} {r['fights_cum']:>6} "
              f"{r['groups_formed']:>6} {r['groups_dissolved']:>4}")
    print(f"\nAggregate -> {out}")


if __name__ == "__main__":
    main()
