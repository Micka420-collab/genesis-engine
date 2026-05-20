"""Run algorithm evolution lab — generate, test, select, improve.

Usage::

    python scripts/run_algorithm_evolution.py
    python scripts/run_algorithm_evolution.py --generations 15 --population 32
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, RUNTIME)

from engine.algorithm_evolution import EvolutionConfig, evolve_operators, improve_until_plateau  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=lambda s: int(s, 0), default=0xA1B0_BEEE)
    p.add_argument("--generations", type=int, default=12)
    p.add_argument("--population", type=int, default=24)
    p.add_argument("--resolution", type=int, default=48)
    p.add_argument("--plateau", action="store_true", help="Repeat until fitness plateaus")
    p.add_argument("--out", default=None, help="JSON artifact path")
    args = p.parse_args()

    cfg = EvolutionConfig(
        seed=args.seed,
        generations=args.generations,
        population_size=args.population,
        genesis_resolution=args.resolution,
    )
    result = improve_until_plateau(cfg) if args.plateau else evolve_operators(cfg)
    best = result.best
    payload = {
        "operator_id": best.operator_id,
        "params": best.params,
        "fitness": round(best.fitness, 6),
        "generation": best.generation,
        "history_best_fitness": [round(x, 6) for x in result.history_best_fitness],
        "generations_run": result.generations_run,
    }
    print(json.dumps(payload, indent=2))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"[algo-evo] wrote {args.out}")


if __name__ == "__main__":
    main()
