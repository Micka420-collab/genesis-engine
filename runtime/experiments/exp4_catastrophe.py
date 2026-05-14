"""Experiment 4: environmental catastrophe.

A "shockwave" hits the world at tick 80, damaging agents within 250 m and
wiping food/water there. Hypothesis: survivors emigrate, lineages bottleneck,
and recovery dynamics emerge.
"""
from _runner import run_experiment, SimConfig

if __name__ == "__main__":
    cfg = SimConfig(
        name="exp4_catastrophe",
        seed=0xD15A57E2,
        founders=30, max_agents=200,
        bounds_km=(0.8, 0.8),
        cultures=1,
        drive_accel=4000.0,
        catastrophe_at_tick=80,
        catastrophe_radius_m=250.0,
        catastrophe_damage=0.6,
    )
    run_experiment("exp4_catastrophe", cfg, ticks=200)
