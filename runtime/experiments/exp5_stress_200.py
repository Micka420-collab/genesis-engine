"""Stress test: 200 founders, cap 1000, two cultures, ~300 ticks.

This is the "100+ agents minimum, long-run" requirement of the
2026-05-17 audit. It exercises the full tick pipeline (perceive →
decide → apply) plus the Phase-5cd extensions (construction,
atmosphere, invention, tech tree, speech) under crowded conditions.

Run via:
    python run.py exp5_stress_200 --ticks 300
or directly:
    python experiments/exp5_stress_200.py
"""
from _runner import run_experiment, SimConfig

if __name__ == "__main__":
    cfg = SimConfig(
        name="exp5_stress_200",
        seed=0xABCDEF00,
        founders=200, max_agents=1000,
        bounds_km=(1.5, 1.5),
        cultures=2,
        drive_accel=2000.0,
    )
    run_experiment("exp5_stress_200", cfg, ticks=300)
