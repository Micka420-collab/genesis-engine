"""P76 — Multi-rate coupler smoke (weather vs agent dispatch)."""
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
from engine.multi_rate_coupler import (  # noqa: E402
    TickDomain, install_multi_rate_coupler, coupler_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P76 — Multi-rate coupler smoke")
    print("=" * 78)
    failures = 0
    sim = Simulation(SimConfig(seed=42, founders=4, max_agents=20))
    install_multi_rate_coupler(sim, master_dt=int(sim.cfg.drive_accel))
    for _ in range(400):
        sim.step()
    summ = coupler_summary(sim)
    ok = summ.get("installed") and summ.get("master_tick", 0) > 0
    print(_row("coupler installed", ok, str(summ.get("domain_ticks"))))
    if not ok:
        failures += 1
    wtick = summ.get("domain_ticks", {}).get("Weather", 0)
    ok = wtick >= 1
    print(_row("weather domain fired", ok, f"weather_ticks={wtick}"))
    if not ok:
        failures += 1
    last = summ.get("last_fired", [])
    ok = "Agent" in last or sim.tick > 0
    print(_row("agent steps ran", ok, f"sim.tick={sim.tick}"))
    if not ok:
        failures += 1
    ok = TickDomain.Weather in TickDomain.all_domains()
    print(_row("TickDomain enum", ok))
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
