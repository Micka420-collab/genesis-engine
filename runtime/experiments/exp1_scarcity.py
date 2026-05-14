"""Experiment 1: 10 agents in a small bounded world.

Hypothesis: limited resources will produce a mix of foraging competition,
opportunistic sharing (high-agreeableness agents), and dominance via
high-aggression agents.
Observation targets: shares vs fights cumulative ratio, offspring distribution.
"""
from _runner import run_experiment, SimConfig

if __name__ == "__main__":
    cfg = SimConfig(
        name="exp1_scarcity",
        seed=0xC0FFEE_DEADBEEF,
        founders=10, max_agents=80,
        bounds_km=(0.4, 0.4),     # ~160 000 m² ≈ small dense world
        cultures=1,
        drive_accel=4000.0,
    )
    run_experiment("exp1_scarcity", cfg, ticks=250)
