"""P77 — Epidemic contact graph smoke."""
from __future__ import annotations

import io
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.sim import Simulation, SimConfig  # noqa: E402
from engine.epidemic_observer import (  # noqa: E402
    build_contact_graph, install_epidemic_observer, epidemic_state_summary,
)
from engine.physiology import install_physiology  # noqa: E402


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P77 — Epidemic contact graph smoke")
    print("=" * 78)
    failures = 0
    sim = Simulation(SimConfig(seed=7, founders=8, max_agents=30,
                               spawn_radius_m=8.0))
    sim.bootstrap()
    install_physiology(sim)
    install_epidemic_observer(sim)
    pf = sim._physio_fields
    n = sim.agents.n_active
    pf.flu_load[0] = 0.5
    cg = build_contact_graph(sim, contact_radius_m=5.0)
    ok = cg.tick == sim.tick
    print(_row("build_contact_graph tick", ok, f"edges={len(cg.edges)}"))
    if not ok:
        failures += 1
    for _ in range(20):
        sim.step()
    summ = epidemic_state_summary(sim)
    ok = summ.get("installed") and summ.get("contact_graph", {}).get("n_snapshots", 0) >= 1
    print(_row("contact graph snapshots", ok, str(summ.get("contact_graph"))))
    if not ok:
        failures += 1
    cg2 = build_contact_graph(sim)
    if cg2.edges:
        e0 = cg2.edges[0]
        ok = e0.agent_a < e0.agent_b
        print(_row("edges sorted (a<b)", ok))
        if not ok:
            failures += 1
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
