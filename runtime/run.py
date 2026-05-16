"""DEPRECATED entry point.

The supported entry points are the per-experiment scripts under
`experiments/` and the smoke tests under `scripts/`:

    python experiments/exp1_scarcity.py
    python experiments/exp2_food_pressure.py
    python experiments/exp3_two_cultures.py
    python experiments/exp4_catastrophe.py
    python experiments/stress_100.py
    python experiments/run_all.py
    python scripts/p0_smoke.py
    ...
"""
import sys
sys.stderr.write(__doc__)
sys.exit(2)
