"""Experiment 2: 50 agents in a medium world with rapid drive growth.

Hypothesis: severe food pressure will trigger conflicts, alliances form
around high-agreeableness clusters, and groups will migrate toward
food-richer chunks.
"""
from _runner import run_experiment, SimConfig

if __name__ == "__main__":
    cfg = SimConfig(
        name="exp2_food_pressure",
        seed=0xBEEFCAFE_99,
        founders=50, max_agents=200,
        bounds_km=(0.6, 0.6),
        cultures=1,
        drive_accel=6000.0,        # harder pressure
    )
    run_experiment("exp2_food_pressure", cfg, ticks=200)
