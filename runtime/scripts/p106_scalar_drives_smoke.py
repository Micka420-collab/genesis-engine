#!/usr/bin/env python3
"""Smoke -- Wave 56 : Scalar drives loop.

Checks:
  1. Drives increment correctly (hunger, thirst increase)
  2. Drives stay clamped [0, 1.5]
  3. Pain decays toward 0
  4. Vitality recovers when calm
  5. drives_ms < 0.05ms (scalar: ~0.023ms vs numpy 0.067ms)
  6. Total sim tick < 1.2ms
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

results: list[str] = []
passed = failed = 0


def _row(label: str, ok: bool, detail: str = "") -> str:
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    results.append(_row(label, ok, detail))
    if ok:
        passed += 1
    else:
        failed += 1


SEED = 42

# ---------------------------------------------------------------------------
# 1. Drives increment correctly
# ---------------------------------------------------------------------------
try:
    from engine.sim import Simulation, SimConfig

    cfg = SimConfig(
        seed=SEED,
        founders=6,
        bounds_km=(0.5, 0.5),
        emergence_subsystems=False,
        life_emergence=False,
        knowledge_layers=False,
        wind_advect_agents=False,
    )
    sim = Simulation(cfg)
    sim.step()

    h0 = float(sim.agents.hunger[0])
    t0 = float(sim.agents.thirst[0])
    sim.step()
    h1 = float(sim.agents.hunger[0])
    t1 = float(sim.agents.thirst[0])

    hunger_inc = h1 > h0
    thirst_inc = t1 > t0

    check("Drives increment (hunger/thirst increase per tick)",
          hunger_inc and thirst_inc,
          f"hunger {h0:.6f}->{h1:.6f} thirst {t0:.6f}->{t1:.6f}")
except Exception as e:
    check("Drives increment", False, str(e))

# ---------------------------------------------------------------------------
# 2. Drives stay clamped [0, 1.5]
# ---------------------------------------------------------------------------
try:
    sim2 = Simulation(cfg)
    for _ in range(100):
        sim2.step()
    n = sim2.agents.n_active
    alive = np.flatnonzero(sim2.agents.alive[:n])
    all_ok = True
    for arr_name in ["hunger", "thirst", "fatigue", "sleep", "pain", "stress"]:
        arr = getattr(sim2.agents, arr_name)[alive]
        if arr.min() < 0.0 or arr.max() > 1.5:
            all_ok = False

    check("Drives clamped [0, 1.5] after 100 ticks",
          all_ok,
          f"alive={alive.size}")
except Exception as e:
    check("Drives clamped", False, str(e))

# ---------------------------------------------------------------------------
# 3. Pain decays toward 0
# ---------------------------------------------------------------------------
try:
    sim3 = Simulation(cfg)
    # Set initial pain
    sim3.agents.pain[0] = 0.5
    sim3.step()
    pain_after = float(sim3.agents.pain[0])
    decayed = pain_after < 0.5

    check("Pain decays toward 0",
          decayed,
          f"0.5 -> {pain_after:.6f}")
except Exception as e:
    check("Pain decays", False, str(e))

# ---------------------------------------------------------------------------
# 4. Vitality recovers when calm
# ---------------------------------------------------------------------------
try:
    sim4 = Simulation(cfg)
    # Set low drives (calm) and reduced vitality
    sim4.agents.hunger[0] = 0.1
    sim4.agents.thirst[0] = 0.1
    sim4.agents.injuries[0] = 0.0
    sim4.agents.vitality[0] = 0.8
    sim4.step()
    vit_after = float(sim4.agents.vitality[0])
    recovered = vit_after > 0.8

    check("Vitality recovers when calm",
          recovered,
          f"0.8 -> {vit_after:.6f}")
except Exception as e:
    check("Vitality recovers", False, str(e))

# ---------------------------------------------------------------------------
# 5. drives_ms < 0.05ms
# ---------------------------------------------------------------------------
try:
    sim5 = Simulation(cfg)
    for _ in range(5):
        sim5.step()
    drives_times = []
    for _ in range(20):
        stats = sim5.step()
        drives_times.append(stats.drives_ms)
    avg_drives = sum(drives_times) / len(drives_times)

    check(f"drives_ms < 0.05ms ({avg_drives:.3f}ms)",
          avg_drives < 0.05,
          f"avg={avg_drives:.3f}ms (scalar, was 0.067ms numpy)")
except Exception as e:
    check("drives_ms < 0.05ms", False, str(e))

# ---------------------------------------------------------------------------
# 6. Total sim tick < 1.2ms
# ---------------------------------------------------------------------------
try:
    tick_times = []
    for _ in range(20):
        stats = sim5.step()
        tick_times.append(stats.last_tick_ms)
    avg_tick = sum(tick_times) / len(tick_times)

    check(f"Sim tick < 1.2ms ({avg_tick:.2f}ms)",
          avg_tick < 1.2,
          f"drives={stats.drives_ms:.3f} perceive={stats.perceive_ms:.3f} regen={stats.regen_ms:.3f}")
except Exception as e:
    check("Sim tick < 1.2ms", False, str(e))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p106 -- Wave 56 Scalar Drives ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) rate(s).")
    sys.exit(1)
print("OK -- Wave 56 scalar drives validation complet.")
