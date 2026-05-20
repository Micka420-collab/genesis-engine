"""P85 — Algorithm evolution lab smoke (generate → test → select → improve)."""
from __future__ import annotations

import io
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)


def _row(label: str, ok: bool, detail: str = "") -> str:
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P85 — Algorithm evolution lab smoke")
    print("=" * 78)
    failures = 0

    from engine.algorithm_evolution import (  # noqa: E402
        EvolutionConfig,
        evaluate_genome,
        evolve_operators,
        improve_until_plateau,
        random_genome,
    )
    from engine.novel_operators import OPERATOR_IDS, apply_operator, default_params
    from engine.world_genesis import GenesisParams, generate_world

    world = generate_world(GenesisParams(seed=42, resolution=32))
    ok_ops = len(OPERATOR_IDS) == 4
    print(_row("four novel operator families", ok_ops, str(OPERATOR_IDS)))
    failures += 0 if ok_ops else 1

    for op in OPERATOR_IDS:
        g = random_genome(99, 0, op)
        g.params = default_params(op)
        snap_u = world.wind_u.copy()
        apply_operator(g, world)
        changed = not (world.wind_u == snap_u).all() or op != "mycorrhizal_mesh"
        fit, m = evaluate_genome(g, world)
        ok = fit >= 0.0 and m.get("fitness", 0) >= 0.0
        print(_row(f"evaluate {op}", ok, f"fit={fit:.4f}"))
        failures += 0 if ok else 1

    cfg = EvolutionConfig(
        seed=0xB85_0000,
        generations=6,
        population_size=12,
        elite_count=2,
        genesis_resolution=28,
    )
    r1 = evolve_operators(cfg)
    ok = r1.best.fitness > 0 and len(r1.history_best_fitness) == cfg.generations
    print(_row("evolve_operators", ok,
                 f"best={r1.best.operator_id} fit={r1.best.fitness:.4f}"))
    failures += 0 if ok else 1

    ok_improve = r1.history_best_fitness[-1] >= r1.history_best_fitness[0] * 0.9
    r2 = improve_until_plateau(
        EvolutionConfig(seed=0xB85_0001, generations=4, population_size=10, genesis_resolution=24),
        max_rounds=3,
    )
    ok2 = r2.best.fitness >= 0.0 and len(r2.history_best_fitness) >= 1
    print(_row("improve_until_plateau", ok2,
                 f"fit={r2.best.fitness:.4f} rounds={len(r2.history_best_fitness)}"))
    failures += 0 if ok2 else 1

    from engine.algorithm_lab import install_best_operator, run_discovery_lab  # noqa: E402
    from engine.genesis_bootstrap import bootstrap_genesis_sim  # noqa: E402
    from engine.sim import Simulation, SimConfig  # noqa: E402

    scfg = SimConfig(
        name="p85_lab",
        seed=0xB85_0000,
        founders=12,
        max_agents=30,
        bounds_km=(0.3, 0.3),
    )
    sim = Simulation(scfg)
    bootstrap_genesis_sim(sim, seed=scfg.seed, genesis_params=GenesisParams(seed=scfg.seed, resolution=32))
    sim.bootstrap()
    run_discovery_lab(sim, cfg=EvolutionConfig(seed=0xB85_0000, generations=4, population_size=8, genesis_resolution=24))
    inst = install_best_operator(sim)
    ok3 = inst.get("installed") is True and inst.get("operator_id") in OPERATOR_IDS
    print(_row("install_best_operator on sim", ok3, str(inst.get("operator_id"))))
    failures += 0 if ok3 else 1

    for _ in range(5):
        sim.step()

    print("=" * 78)
    print(f"P85 verdict: {'PASS' if failures == 0 else f'{failures} FAIL'}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
