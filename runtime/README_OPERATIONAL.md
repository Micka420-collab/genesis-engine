# Genesis Engine — Operational Guide

> Companion to `AUDIT.md`. This file tells you exactly how to run the
> simulation and look at the results after the 2026-05-17 audit pass.

## What this is

A real, deterministic multi-agent simulation — not a demo. Each tick the
engine perceives the world for every living agent, lets them choose an
action via a utility-based decision policy that consults personality
(Big-5 + ambition/risk/aggression/curiosity/empathy/intelligence),
needs (hunger, thirst, sleep, fatigue, thermal, pain, stress, loneliness),
relationships (per-agent affinity map + cultural lexicon), and the local
chunk's resources (water, food, wood, stone, metal). Real procedural
terrain (fBm noise → Whittaker biomes) drives biome-aware resource
distribution; a chunk streamer keeps memory bounded by LRU GC.

The Phase-5cd extension layer adds construction projects, atmospheric
CO₂ tracking, an invention/artifact registry, a tech tree with
probabilistic discovery + peer transmission, chronic-fatigue dynamics,
material foraging, and free-will value overrides.

## Prerequisites

- Python ≥ 3.10
- numpy (no other runtime deps required for the core sim)

## Run a single experiment

```
cd F:\DEvOps\projet alpha\genesis-engine\runtime
python run.py exp1_scarcity                 # 250 ticks, 10 founders, scarcity
python run.py exp4_catastrophe              # catastrophe shockwave at tick 80
python run.py exp5_stress_200 --ticks 300   # 200 founders, cap 1000, 5cd on
python run.py exp3_two_cultures --no-5cd    # core sim only, no extensions
```

Outputs land in:

- `journals/<experiment>.jsonl` — full event journal (one JSON per line).
- `artifacts/<experiment>.json` — summary + collapsed per-tick metrics.
- `artifacts/<experiment>_snapshot.json` — final agent positions.

## Open the dashboard

Open `runtime/dashboard.html` in any modern browser. No build, no
server, no external deps. Then:

1. Click **summary.json** and pick `artifacts/<experiment>.json`.
2. Click **journal.jsonl** and pick the matching `journals/<experiment>.jsonl`.
3. *(optional)* Click **snapshot.json** for the god-view scatter map.

You'll see:

- **Population panel:** alive, cumulative births, cumulative deaths.
- **Drives panel:** average hunger / thirst / vitality over time.
- **Society panel:** cumulative shares / fights / matings.
- **Event mix:** histogram of event kinds from the journal.
- **God view:** last snapshot, colored by culture / action / vitality / hunger.
- **Event log:** the last 300 journaled events, color-coded by kind.

## Roll your own experiment

```
python run.py my_run \
    --seed 0xDEADBEEF \
    --founders 80 --max-agents 400 \
    --bounds-km 1.0 --cultures 3 \
    --drive-accel 2500 --ticks 500
```

Tip: the seed and config fully determine the trajectory. Re-run with the
same arguments and you'll get bit-identical agent UUIDs.

## Reproducibility

The determinism contract is enforced in `engine/core.py` via
BLAKE2b-keyed PRF + numpy PCG64, and in `engine/world.py` via a stable
BLAKE2b layer salt that doesn't depend on `PYTHONHASHSEED`. There's a
regression test (`tests/test_engine.py::test_world_deterministic_across_hashseed`)
that spawns a child Python with a random `PYTHONHASHSEED` and verifies
the terrain matches the parent.

## Running the test suite

```
python -m unittest discover -s tests -v
```

After the 2026-05-17 patch, `test_share_fires_under_stockpile_conditions`
will *pass* — go remove its `@unittest.expectedFailure` decorator once
you've confirmed it.

## What changed in the 2026-05-17 audit pass

See `AUDIT.md` for the full report. Headline fixes:

1. `engine/cognition.apply_decision` now actually executes SHARE, FIGHT,
   SPEAK, and FLEE (they used to be silently dropped after the decide
   step).
2. `engine/sim_5cd_integration.patched_apply` cooperates with the new
   SPEAK branch via a per-call flag so vocalize events aren't double-emitted.
3. `engine/cognition.remember_short` + `promote_memories` actually use
   the `EpisodicMemory.short_term` / `long_term` slots that existed but
   were never written.
4. New `run.py` unified CLI that bootstraps a sim, installs 5cd, runs
   it, and writes dashboard-ready artifacts.
5. New `dashboard.html` self-contained observation tool.
6. New `experiments/exp5_stress_200.py` for the 200-agent stress test.

## Performance ballpark

Measured on a single CPU at the configured drive_accel:

- `exp1_scarcity` (10 founders, 250 ticks) — sub-second.
- `exp4_catastrophe` (30 founders, 200 ticks) — a few seconds.
- `exp5_stress_200` (200 founders, 300 ticks, 5cd installed) — single-digit
  to low double-digit minutes depending on hardware; chunk count
  stabilises around 25-100 thanks to the LRU GC.

If you need to scale beyond 500 agents, the bottleneck is the Python
per-agent loop in `Simulation.step`. The codebase has Rust scaffolding
under `scaffolding/crates/` for a future port; that work is intentionally
out of scope for the operational audit.
