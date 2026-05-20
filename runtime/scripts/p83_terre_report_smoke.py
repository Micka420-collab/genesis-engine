#!/usr/bin/env python
"""P83 — Terre preset short run + enriched artifact report smoke."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.full_stack import wire_full_stack  # noqa: E402
from engine.run_report import enrich_run_summary  # noqa: E402
from engine.sim import Simulation, SimConfig  # noqa: E402
from engine.social_topology import EdgeKind, add_edge, install_social_topology  # noqa: E402
from engine.trade_exchange import execute_bilateral_trade  # noqa: E402


def _row(label: str, ok: bool, detail: str = "") -> str:
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P83 — Terre report + multi-resource trade smoke")
    print("=" * 78)
    failures = 0

    with tempfile.TemporaryDirectory() as tmp:
        journal = os.path.join(tmp, "terre_smoke.jsonl")
        observe = os.path.join(tmp, "terre_observe.jsonl")
        open(journal, "w").close()
        open(observe, "w").close()

        cfg = SimConfig(
            name="p83_terre",
            seed=0x7833_0001,
            founders=0,
            emergent_origins=True,
            full_biosphere=True,
            max_emergent_founders=1,
            knowledge_layers=True,
            macro_commerce=True,
            rust_worldgraph_prod=False,
            hydrology_mode="sv1d",
            max_agents=24,
            bounds_km=(0.2, 0.2),
            drive_accel=2000.0,
            observable_every=5,
        )
        sim = Simulation(cfg, journal_path=journal)
        sim._observable_jsonl_path = observe

        try:
            wire_full_stack(sim, genesis=True, rust_worldgraph=True,
                            five_cd=False, macro_commerce=True)
        except Exception as exc:
            print(_row("wire_full_stack", False, repr(exc)))
            failures += 1

        sim.bootstrap()
        ticks = 40
        for _ in range(ticks):
            sim.step()

        sim.annalist.close()

        summary = {
            "experiment": cfg.name,
            "ticks_run": ticks,
            "journal": journal,
            "observe_jsonl": observe,
            "final_alive": int(sim.stats.alive),
        }
        summary = enrich_run_summary(sim, summary)

        ok = summary.get("report_schema") == "genesis.run_report/v1"
        print(_row("enrich_run_summary schema", ok, summary.get("report_schema", "")))
        if not ok:
            failures += 1

        ok = "stack_active" in summary and len(summary["stack_active"]) >= 2
        print(_row("stack_active present", ok, str(summary.get("stack_active"))))
        if not ok:
            failures += 1

        ok = summary.get("observe_stats", {}).get("jsonl_lines", 0) > 0
        print(_row("observe JSONL lines", ok,
                   str(summary.get("observe_stats"))))
        if not ok:
            failures += 1

    # Unit: water transfer
    sim2 = Simulation(
        SimConfig(founders=2, max_agents=4, life_emergence=False,
                  epidemic_observer=False, emergence_subsystems=False,
                  knowledge_layers=True))
    sim2.bootstrap()
    install_social_topology(sim2)
    sim2.agents.inv_water[0] = 1.0
    sim2.agents.inv_water[1] = 0.05
    sim2.agents.inv_food[0] = 0.5
    sim2.agents.inv_food[1] = 0.5
    add_edge(sim2._social_topology, 0, 1, EdgeKind.TRADE, 0.7)
    w1_before = float(sim2.agents.inv_water[1])
    xfer = execute_bilateral_trade(sim2, 0, 1, edge_weight=0.8, macro_flow=10.0)
    ok = xfer is not None and "water_a_to_b" in xfer
    print(_row("water bilateral transfer", ok, str(xfer)))
    if not ok:
        failures += 1
    elif float(sim2.agents.inv_water[1]) <= w1_before:
        print(_row("water received", False))
        failures += 1
    else:
        print(_row("water received", True))

    print("=" * 78)
    if failures:
        print(f"P83 FAIL — {failures}")
        return 1
    print("P83 PASS — terre report smoke")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
