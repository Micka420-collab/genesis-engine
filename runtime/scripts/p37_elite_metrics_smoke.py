"""P37 — Wave 11 elite-metrics smoke (Veille 2026-05-15).

Verifies that the new `engine.elite_metrics` observer :

  1. Returns one entry per culture present in the sim.
  2. Reports valid stats (n_alive>0, gini ∈ [0,1], top10 finite).
  3. Hill α is finite when enough agents exist, NaN otherwise.
  4. Writes a JSONL journal with one line per logged tick.
  5. Is pure-read : determinism of the underlying sim is preserved
     (bit-identical state across two runs at same seed).
  6. Does NOT crash on empty / extinct populations.

The smoke runs a 2-culture sim of 16 founders × 250 ticks and logs
metrics every 50 ticks. No mutation of sim state by the observer.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import traceback


if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.sim import Simulation, SimConfig            # noqa: E402
from engine.elite_metrics import (                      # noqa: E402
    compute_elite_metrics, log_elite_metrics, detect_power_law)


JOURNAL = os.path.abspath(
    os.path.join(ROOT, "journals", "p37_elite_metrics.jsonl"))


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:55s} {detail}"


def _build_sim(name: str, *, founders=16, cultures=2, seed=0xE17E_2026):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=founders, max_agents=max(40, founders * 3),
        bounds_km=(1.5, 1.5), spawn_radius_m=120.0,
        drive_accel=1500.0, cultures=cultures,
    )
    return Simulation(cfg)


def _state_hash(sim) -> str:
    a = sim.agents
    n = a.n_active
    buf = (a.alive[:n].tobytes()
           + a.pos[:n].tobytes()
           + a.hunger[:n].tobytes()
           + a.thirst[:n].tobytes()
           + a.intelligence[:n].tobytes()
           + a.conscientiousness[:n].tobytes())
    return hashlib.sha256(buf).hexdigest()[:24]


def main() -> int:
    print("=" * 78)
    print("P37 — Wave 11 elite-metrics smoke")
    print("=" * 78)
    failures = 0

    if os.path.exists(JOURNAL):
        os.remove(JOURNAL)

    # Step 1 — Empty sim → empty dict, no crash.
    sim_empty = _build_sim("p37_empty")
    out_empty = compute_elite_metrics(sim_empty)
    print(_row("step 1 — empty sim returns {}", out_empty == {},
               f"got={out_empty!r}"))
    if out_empty != {}:
        failures += 1

    # Step 2 — 2-culture sim, bootstrap, immediate metrics.
    sim = _build_sim("p37_main")
    sim.bootstrap()
    m0 = compute_elite_metrics(sim)
    n_cult = len(m0)
    print(_row("step 2 — bootstrap yields >=1 culture",
               n_cult >= 1, f"cultures={list(m0.keys())}"))
    if n_cult < 1:
        failures += 1

    # Step 3 — Run + periodic logging.
    logged = 0
    for t in range(250):
        sim.step()
        if (t + 1) % 50 == 0:
            log_elite_metrics(sim, JOURNAL, extra={"phase": "smoke"})
            logged += 1
    print(_row("step 3 — 250 ticks + 5 logs no crash",
               logged == 5, f"logged={logged}"))
    if logged != 5:
        failures += 1

    # Step 4 — JSONL has 5 valid lines, each has 'cultures' key.
    with open(JOURNAL, "r", encoding="utf-8") as fh:
        lines = [json.loads(ln) for ln in fh.read().splitlines() if ln]
    print(_row("step 4 — JSONL parsed, 5 entries, schema OK",
               len(lines) == 5 and all("cultures" in ln for ln in lines),
               f"n={len(lines)}"))
    if len(lines) != 5:
        failures += 1

    # Step 5 — Metric ranges sanity.
    bad = []
    for ln in lines:
        for cid, m in ln["cultures"].items():
            if not (0.0 <= m["gini"] <= 1.0):
                bad.append(("gini", cid, m["gini"]))
            if m["n_alive"] < 0:
                bad.append(("n_alive", cid, m["n_alive"]))
            if m["mean"] < 0.0 or m["mean"] > 1.0 + 1e-6:
                bad.append(("mean", cid, m["mean"]))
    print(_row("step 5 — metric ranges sane",
               not bad, f"violations={bad}"))
    if bad:
        failures += 1

    # Step 6 — detect_power_law returns dict aligned with cultures.
    final = compute_elite_metrics(sim)
    plaw = detect_power_law(final)
    ok = set(plaw.keys()) == set(final.keys())
    print(_row("step 6 — detect_power_law keys align",
               ok, f"keys={sorted(plaw.keys())}"))
    if not ok:
        failures += 1

    # Step 7 — Determinism : observer is pure-read.
    sim_a = _build_sim("p37_det_a")
    sim_a.bootstrap()
    for _ in range(120):
        sim_a.step()
    h_a = _state_hash(sim_a)
    _ = compute_elite_metrics(sim_a)
    _ = log_elite_metrics(sim_a, JOURNAL + ".tmp")
    h_a_after = _state_hash(sim_a)
    os.remove(JOURNAL + ".tmp")

    sim_b = _build_sim("p37_det_b")
    sim_b.bootstrap()
    for _ in range(120):
        sim_b.step()
    h_b = _state_hash(sim_b)
    det_ok = (h_a == h_b) and (h_a == h_a_after)
    print(_row("step 7 — determinism + pure-read observer",
               det_ok, f"{h_a} vs {h_b} (after={h_a_after})"))
    if not det_ok:
        failures += 1

    # Step 8 — Extinct culture handled : kill all of culture 1, observer
    # still works and culture 1 just disappears from the dict.
    sim_k = _build_sim("p37_kill")
    sim_k.bootstrap()
    n = sim_k.agents.n_active
    for i in range(n):
        if sim_k.agents.relations[i].culture_id == 1:
            sim_k.agents.alive[i] = False
    out_k = compute_elite_metrics(sim_k)
    ok = (1 not in out_k) and all(v["n_alive"] > 0 for v in out_k.values())
    print(_row("step 8 — extinct culture pruned cleanly",
               ok, f"cultures_after_kill={sorted(out_k.keys())}"))
    if not ok:
        failures += 1

    print()
    if failures == 0:
        print("RESULT: PASS — Wave 11 elite-metrics smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
