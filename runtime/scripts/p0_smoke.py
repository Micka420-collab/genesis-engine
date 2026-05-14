"""P0 — smoke test of the 5c+5d integration on a Phase 4 sim.

Goal: 30 agents × 200 ticks. Capture errors. Produce
``runtime/journals/p0_smoke.jsonl`` containing every event emitted by the
annalist, plus a per-tick metrics line. Pass = at least 1 INNOVATION (or
INVENT) OR 1 BUILD event was emitted in the run.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.sim import Simulation, SimConfig
from engine.sim_5cd_integration import install


def main() -> int:
    out_path = os.path.join(ROOT, "journals", "p0_smoke.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Truncate any previous run.
    open(out_path, "w").close()

    cfg = SimConfig(
        name="p0_smoke",
        seed=0xC0FFEE_5CD,
        founders=30,
        max_agents=120,
        bounds_km=(0.5, 0.5),
        spawn_radius_m=20.0,
        cultures=1,
        drive_accel=1500.0,
    )

    t_setup = time.monotonic()
    sim = Simulation(cfg)
    install(sim)
    setup_elapsed = time.monotonic() - t_setup

    # Hook the annalist to mirror every event into the journal file.
    original_record = sim.annalist.record_tick
    counts = {
        "innovation": 0, "build": 0, "invent": 0,
        "birth": 0, "death": 0, "fight": 0, "share": 0,
        "mating": 0, "vocalization": 0, "competition": 0,
        "group_formed": 0, "group_dissolved": 0,
    }

    _raw_to_count = {
        "vocalize": "vocalization", "mating_success": "mating",
    }

    def mirror_record(tick, agents, *, births, deaths, raw_events):
        for e in raw_events:
            k = e.get("kind", "?")
            ck = _raw_to_count.get(k, k)
            if ck in counts:
                counts[ck] = counts[ck] + 1
        out = original_record(tick, agents, births=births, deaths=deaths,
                              raw_events=raw_events)
        # Persist each emitted Event object.
        try:
            with open(out_path, "a") as f:
                for ev in out:
                    f.write(json.dumps(ev.to_dict(), separators=(",", ":")) + "\n")
        except Exception:
            pass
        return out

    sim.annalist.record_tick = mirror_record

    # Run.
    errors = []
    t0 = time.monotonic()
    for t in range(200):
        try:
            sim.step()
        except Exception as exc:
            errors.append({
                "tick": t,
                "exception": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc().splitlines()[-6:],
            })
            break
    elapsed = time.monotonic() - t0

    # Final summary line, also dumped as a JSONL record.
    summary = {
        "_summary": True,
        "config": {
            "name": cfg.name, "seed": cfg.seed, "founders": cfg.founders,
            "max_agents": cfg.max_agents, "drive_accel": cfg.drive_accel,
        },
        "setup_elapsed_s": round(setup_elapsed, 3),
        "run_elapsed_s": round(elapsed, 3),
        "ticks_completed": sim.tick,
        "agents_alive": int((sim.agents.alive[:sim.agents.n_active]).sum()),
        "agents_total_spawned": int(sim.agents.n_active),
        "event_counts": counts,
        "construction": {
            "active_projects": len(sim.construction_registry.projects),
            "completed_structures": len(sim.construction_registry.structures),
        },
        "invention": {
            "artifacts": len(sim.invention_registry.artifacts),
        },
        "atmosphere": {
            "co2_kg": round(float(sim.atmosphere.co2_kg), 4),
            "co2_ppm": round(float(sim.atmosphere.co2_ppm), 4),
            "temp_anomaly_k": round(float(sim.atmosphere.temp_anomaly_k), 4),
        },
        "errors": errors,
    }
    with open(out_path, "a") as f:
        f.write(json.dumps(summary, separators=(",", ":")) + "\n")

    print(json.dumps(summary, indent=2))

    if errors:
        print("\n❌ P0 SMOKE FAILED — exception thrown during step()")
        return 2

    innovation_or_invent = (counts["innovation"] + counts["invent"]
                            + len(sim.invention_registry.artifacts))
    build_or_project = (counts["build"]
                        + len(sim.construction_registry.projects)
                        + len(sim.construction_registry.structures))

    if innovation_or_invent < 1:
        print("\n❌ P0 SMOKE FAILED — no INNOVATION or INVENT event.")
        return 3
    if build_or_project < 1:
        print("\n❌ P0 SMOKE FAILED — no BUILD event nor active project.")
        return 4

    print("\n✅ P0 SMOKE PASSED")
    print(f"   innovation+invent+artifacts = {innovation_or_invent}")
    print(f"   build+projects+structures   = {build_or_project}")
    print(f"   journal = {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
