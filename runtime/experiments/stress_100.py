"""Stress test: 100 founders, 500-agent capacity, long run."""
from _runner import run_experiment, SimConfig

if __name__ == "__main__":
    cfg = SimConfig(
        name="stress_100",
        seed=0xFEEDFACE,
        founders=100, max_agents=500,
        bounds_km=(1.0, 1.0),
        cultures=1,
        drive_accel=2500.0,
    )
    run_experiment("stress_100", cfg, ticks=150)
