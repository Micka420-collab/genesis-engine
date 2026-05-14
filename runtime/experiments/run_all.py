"""Run all experiments in sequence and print a comparative summary."""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

EXPERIMENTS = ["exp1_scarcity", "exp2_food_pressure", "exp3_two_cultures",
               "exp4_catastrophe", "stress_100"]


def main():
    for name in EXPERIMENTS:
        print(f"\n=== {name} ===")
        os.system(f"{sys.executable} {os.path.join(HERE, name + '.py')}")
    # Aggregate
    A = os.path.abspath(os.path.join(HERE, "..", "artifacts"))
    rows = []
    for name in EXPERIMENTS:
        path = os.path.join(A, name + ".json")
        if os.path.exists(path):
            rows.append(json.load(open(path)))
    print("\n=== ALL EXPERIMENTS SUMMARY ===")
    print(f"{'experiment':<22} {'ticks':>6} {'wall(s)':>8} {'TPS':>6} {'alive':>6} {'births':>7} {'deaths':>7}")
    print("-" * 80)
    for r in rows:
        print(f"{r['experiment']:<22} {r['ticks_run']:>6} {r['wall_clock_s']:>8.1f} {r['tps']:>6.1f} {r['final_alive']:>6} {r['cum_births']:>7} {r['cum_deaths']:>7}")


if __name__ == "__main__":
    main()
