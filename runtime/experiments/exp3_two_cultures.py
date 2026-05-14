"""Experiment 3: two founder groups in distinct clusters.

Hypothesis: distinct cultures will either (a) interbreed (fusion), (b) fight
when they meet (war), or (c) selectively trade. The personality distribution
of culture A vs B is randomised by seed.
"""
from _runner import run_experiment, SimConfig

if __name__ == "__main__":
    cfg = SimConfig(
        name="exp3_two_cultures",
        seed=0x1234_ABCD_5678,
        founders=24,
        cultures=2,                # 12 per culture
        max_agents=200,
        bounds_km=(0.9, 0.9),
        drive_accel=3500.0,
    )
    run_experiment("exp3_two_cultures", cfg, ticks=250)
