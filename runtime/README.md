# Genesis Engine — Operational Runtime

A real, runnable multi-agent autonomous-world simulation laboratory.

This directory contains the Python operational implementation that
mirrors the architecture described in `../docs/` and matches the
domain boundaries of the Rust crates under `../scaffolding/crates/`.

## What it does

Runs a persistent simulated world populated by autonomous AI agents
with cognition (perception → decision → action), memory, drives,
personality, fertility, and social relations. Agents reproduce and
form multi-generational lineages, the world has biomes / weather /
resource regeneration, and an annalist records every salient event
to a JSONL journal for offline analysis.

This is **not a fake demo**: every agent runs the same policy
deterministically, every drive is computed each tick, every chunk
is procedurally generated from a deterministic PRF, and the journal
is the actual ground truth.

## Architecture

```
runtime/
├── engine/
│   ├── core.py           Deterministic primitives (PRF, IDs, hashing, ticks)
│   ├── world.py          Terrain, biomes, resources, chunks, weather, streaming
│   ├── agent.py          SoA registry (numpy) + memory + relations + personality
│   ├── cognition.py      Perception → R0 utility policy → action application
│   ├── annalist.py       Event detectors, JSONL journal, lineage map, metrics
│   ├── sim.py            Tick loop (the main entry point)
│   ├── dashboard.py      Stdlib HTTP server exposing live state & visualisation
│   └── index.html        Browser dashboard (god-mode, agent inspector, charts)
├── experiments/          The four scientific experiments + stress test
├── journals/             Per-experiment JSONL event journals
├── artifacts/            Per-experiment metric summaries (JSON)
└── configs/              YAML configs (referenced by the Rust scaffolding too)
```

## Running

```bash
cd runtime/experiments
python3 exp1_scarcity.py        # 10 agents, scarcity → cooperation/competition
python3 exp2_food_pressure.py   # 50 agents, harsh drive growth
python3 exp3_two_cultures.py    # 2 cultures, contact dynamics
python3 exp4_catastrophe.py     # environmental disaster at tick 80
python3 stress_100.py           # 100+ founders / 500-agent capacity
```

To open the live dashboard against a running simulation:

```python
from engine.sim import Simulation, SimConfig
from engine.dashboard import start_server

sim = Simulation(SimConfig(founders=50, max_agents=300, drive_accel=3000.0))
srv = start_server(sim, port=8080)
while True:
    sim.step()
```

Then open http://localhost:8080/ — biome view, culture view, hunger heatmap,
agent inspector, population/conflict/mating charts.

## Determinism

Every random number in the simulation derives from `prf_rng(seed, ctx, indices)`
in `engine/core.py`. A run with `seed=X` produces identical chunks, identical
founder personalities, identical offspring IDs and identical mutation samples.
Use a fixed seed for reproducibility, or pass a random seed for fresh runs.

## Performance

Baseline measured on this sandbox (single CPU, vectorised numpy):

| Experiment           | agents (peak) | TPS  | wall-clock |
|----------------------|--------------:|-----:|-----------:|
| exp1_scarcity        | 49            | 25.3 |  9.9 s     |
| exp2_food_pressure   | 200           |  4.7 | 42.6 s     |
| exp3_two_cultures    | 200           |  8.4 | 29.6 s     |
| exp4_catastrophe     | 200           |  9.0 | 22.1 s     |
| stress_100           | 255 (cap 500) |  3.7 | 40.7 s     |

The hot path is the per-agent perception scan; it's already vectorised
on numpy at the chunk level. For 1000+ agents, the next steps are
(1) a spatial grid index over agents, (2) cython/numba for the
decision loop, and (3) ECS-style parallelism via the Rust crates.

## Configuration knobs

Edit `SimConfig` fields in any experiment to tune:

- `founders`, `max_agents`, `bounds_km`, `cultures`
- `drive_accel`: how many simulated seconds elapse per tick
  (higher = harsher; calibrate around 1000–6000 for healthy populations)
- `catastrophe_at_tick` / `catastrophe_radius_m` / `catastrophe_damage`

## Journals

Each experiment writes `journals/<name>.jsonl`. Lines are
self-contained JSON events with schema:

```json
{"event_id":"…","sim_id":"…","tick":42,"kind":"birth",
 "participants":["uuid",…],"location":[x,y,z],"metadata":{…}}
```

Kinds emitted: `birth`, `death`, `conflict`, `share`, `mating`,
`catastrophe`. The annalist updates `LineageMap` (parent→children
graph) and time-series metrics in memory too.
