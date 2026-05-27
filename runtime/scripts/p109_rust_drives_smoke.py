#!/usr/bin/env python3
"""Smoke -- Wave 59 : Rust drives update.

Tests that the Rust py_tick_drives function:
  1. Is importable from genesis_world
  2. Produces identical results to Python scalar path
  3. sim.step() stable at 6 agents (20 ticks)
  4. Drives time < 0.05ms at 6 agents
  5. sim.step() stable at 50 agents (20 ticks)
  6. Drives time < 0.10ms at 50 agents
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
from engine.sim import Simulation, SimConfig, HUNGER_PER_S, THIRST_PER_S, FATIGUE_PER_S, SLEEP_PER_S

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


# ---------------------------------------------------------------------------
# 1. Import check
# ---------------------------------------------------------------------------
try:
    from genesis_world import py_tick_drives
    has_drives = True
except ImportError:
    has_drives = False
check("py_tick_drives importable", has_drives)

if not has_drives:
    print("ECHEC: py_tick_drives not available — skipping all checks")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 2. Correctness: Rust vs Python scalar match
# ---------------------------------------------------------------------------
N = 10
accel = 1500.0
alive = np.array([1,1,0,1,1,1,0,1,1,1], dtype=np.uint8)

# Setup arrays with known values
def make_arrays():
    return (
        np.full(N, 0.3, dtype=np.float32),   # hunger
        np.full(N, 0.25, dtype=np.float32),  # thirst
        np.full(N, 0.1, dtype=np.float32),   # fatigue
        np.full(N, 0.15, dtype=np.float32),  # sleep
        np.full(N, 0.05, dtype=np.float32),  # pain
        np.full(N, 0.2, dtype=np.float32),   # stress
        np.full(N, 0.1, dtype=np.float32),   # injuries
        np.full(N, 0.9, dtype=np.float32),   # vitality
    )

h_rate = float(HUNGER_PER_S * accel)
t_rate = float(THIRST_PER_S * accel)
f_rate = float(FATIGUE_PER_S * accel)
s_rate = float(SLEEP_PER_S * accel)
pain_dec = float(0.001 * accel)
stress_rate = float(0.001 * accel)
stress_dec = float(0.0005 * accel)
inj_dec = float(0.00005 * accel)
vit_inc = float(0.0001 * accel)

# Rust path
r_h, r_t, r_f, r_s, r_p, r_st, r_inj, r_vit = make_arrays()
py_tick_drives(alive, r_h, r_t, r_f, r_s, r_p, r_st, r_inj, r_vit,
               h_rate, t_rate, f_rate, s_rate,
               pain_dec, stress_rate, stress_dec, inj_dec, vit_inc)

# Python scalar path
p_h, p_t, p_f, p_s, p_p, p_st, p_inj, p_vit = make_arrays()
for i in range(N):
    if alive[i] == 0:
        continue
    p_h[i] = min(float(p_h[i]) + h_rate, 1.5)
    p_t[i] = min(float(p_t[i]) + t_rate, 1.5)
    p_f[i] = min(float(p_f[i]) + f_rate, 1.5)
    p_s[i] = min(float(p_s[i]) + s_rate, 1.5)
    p_p[i] = max(float(p_p[i]) - pain_dec, 0.0)
    _sv = float(p_st[i]) + (float(p_h[i]) + float(p_t[i])) * stress_rate - stress_dec
    p_st[i] = max(0.0, min(_sv, 1.5))
    p_inj[i] = max(float(p_inj[i]) - inj_dec, 0.0)
    if float(p_h[i]) < 0.4 and float(p_t[i]) < 0.4 and float(p_inj[i]) < 0.3:
        p_vit[i] = min(float(p_vit[i]) + vit_inc, 1.0)

# Compare
max_diff = 0.0
for name, ra, pa in [("hunger",r_h,p_h), ("thirst",r_t,p_t), ("fatigue",r_f,p_f),
                      ("sleep",r_s,p_s), ("pain",r_p,p_p), ("stress",r_st,p_st),
                      ("injuries",r_inj,p_inj), ("vitality",r_vit,p_vit)]:
    diff = float(np.max(np.abs(ra - pa)))
    max_diff = max(max_diff, diff)

# Dead agents (idx 2,6) should be unchanged
dead_ok = (r_h[2] == 0.3 and r_h[6] == 0.3 and
           r_vit[2] == 0.9 and r_vit[6] == 0.9)

check("Rust drives matches Python scalar path",
      max_diff < 1e-6 and dead_ok,
      f"max_diff={max_diff:.2e} dead_ok={dead_ok}")

# ---------------------------------------------------------------------------
# 3. sim.step() stable at 6 agents
# ---------------------------------------------------------------------------
cfg6 = SimConfig(seed=42, founders=6, bounds_km=(0.5, 0.5),
                 emergence_subsystems=False, life_emergence=False,
                 knowledge_layers=False, wind_advect_agents=False)
sim6 = Simulation(cfg6)
try:
    for _ in range(20):
        sim6.step()
    step6_ok = True
    detail6 = f"tick={sim6.tick} alive={int(sim6.agents.alive[:sim6.agents.n_active].sum())}"
except Exception as e:
    step6_ok = False
    detail6 = str(e)
check("sim.step() stable 6 agents 20 ticks", step6_ok, detail6)

# ---------------------------------------------------------------------------
# 4. Drives time < 0.05ms at 6 agents
# ---------------------------------------------------------------------------
drives_times = []
for _ in range(20):
    stats = sim6.step()
    drives_times.append(stats.drives_ms)
avg_drives6 = sum(drives_times) / len(drives_times)
check(f"Drives < 0.05ms at 6 agents (avg={avg_drives6:.4f}ms)",
      avg_drives6 < 0.05,
      f"min={min(drives_times):.4f}ms max={max(drives_times):.4f}ms")

# ---------------------------------------------------------------------------
# 5. sim.step() stable at 50 agents
# ---------------------------------------------------------------------------
cfg50 = SimConfig(seed=42, founders=50, bounds_km=(0.5, 0.5),
                  emergence_subsystems=False, life_emergence=False,
                  knowledge_layers=False, wind_advect_agents=False)
sim50 = Simulation(cfg50)
try:
    for _ in range(20):
        sim50.step()
    step50_ok = True
    detail50 = f"tick={sim50.tick} alive={int(sim50.agents.alive[:sim50.agents.n_active].sum())}"
except Exception as e:
    step50_ok = False
    detail50 = str(e)
check("sim.step() stable 50 agents 20 ticks", step50_ok, detail50)

# ---------------------------------------------------------------------------
# 6. Drives time < 0.10ms at 50 agents
# ---------------------------------------------------------------------------
drives_times50 = []
for _ in range(20):
    stats = sim50.step()
    drives_times50.append(stats.drives_ms)
avg_drives50 = sum(drives_times50) / len(drives_times50)
check(f"Drives < 0.10ms at 50 agents (avg={avg_drives50:.4f}ms)",
      avg_drives50 < 0.10,
      f"min={min(drives_times50):.4f}ms max={max(drives_times50):.4f}ms")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = passed + failed
print(f"\nSmoke p109 -- Wave 59 Rust Drives ({passed}/{total})\n")
for r in results:
    print(r)
print()
if failed:
    print(f"ECHEC : {failed} check(s) raté(s).")
    sys.exit(1)
print("OK -- Wave 59 Rust drives validation complet.")
