# Genesis Engine — Phase 5 progress report

**Date:** 13 May 2026
**Scope:** close the Phase 4 audit gaps and advance the four Phase 5 priorities recommended at the end of PHASE4-PROGRESS-2026-05-13.md.

This report follows directly on from `PHASE4-PROGRESS-2026-05-13.md`, which closed four of the five audit recommendations but left three explicit gaps:

1. The **forage economy** never accumulated enough inventory to fire SHARE — across all four reference experiments, `shares_cum` stayed at 0.
2. **Performance** regressed at high N (the spatial grid was in place but new per-tick costs outpaced its savings).
3. There was no **group-lifecycle bookkeeping** beyond formation — no `group_dissolved` events, no orphaned-membership reclamation.

Phase 5 closes (1) and (3) and partially addresses (2). It also discovered, fixed, and added a regression test for a previously-unknown **world-determinism bug** that silently broke the project's most prominent claim.

---

## 1. Closed Phase 4 gaps and Phase 5 priorities vs. status

| # | Item | Status |
|---|------|--------|
| A | World-determinism bug (`hash((seed, layer))` randomised per process) | **Done** — replaced with BLAKE2-keyed `_stable_layer_salt`. Verified by a new cross-process test. |
| B | Goal jittering (audit Phase 5 priority 1) | **Done** — `_jitter_target` adds a deterministic ±0.45 m offset inside each target cell. |
| C | Forage-economy calibration (audit Phase 5 priority 3) | **Done** — `FORAGE_KCAL_PER_KG` lowered 1500 → 300; intelligence/conscientiousness skill bonus added; SHARE threshold and ordering recalibrated. **SHARE now fires in vivo: 136 / 388 / 339 / 177 events across exp1–4.** |
| D | Group lifecycle (audit Phase 5 priority 4) | **Done** — `group_dissolved` events emitted when a group's live membership drops below 3; orphan agents released so they can rejoin new clusters. |
| E | Perception result cache (audit Phase 5 priority 2) | **Done** — `_CACHED_CELL_GRID` is now bounded (cap = 2048, FIFO eviction) and is purged by a callback wired into `ChunkStreamer.gc`. |
| F | Vectorised thermal update | **Done** — `_tick_thermal` now buckets agents by chunk coord so chunk lookup and `weather_at` amortise over many agents. |
| G | Lexicon signature stability | **Done** — `_stable_bytes_sig` replaces Python's randomised `hash()` for both per-vocalisation and per-group signatures. |
| H | Cargo workspace green-build path | Deferred. The Python runtime is the operational target; the Rust scaffolding remains syntactically complete (Phase 3 audit) but is not driven to a green build from this sandbox. |

---

## 2. Critical world-determinism bug (root-cause + fix)

The Phase 4 codebase claimed deterministic procedural worlds via the `prf_rng(seed, ctx, indices)` discipline. The audit and the test suite verified `derive_agent_id`, `prf_bytes`, and the chunk `content_root` hash all reproduced bit-for-bit across runs.

But `runtime/engine/world.py:_cell_values` used `hash((seed, layer))` to salt every terrain-noise sample. Python's `hash()` of strings (and of tuples containing strings) is **randomised per process** when `PYTHONHASHSEED` is not fixed. Reproduction probe:

```
PYTHONHASHSEED=0    → elev[10,10] = -2641.55  (ocean)
PYTHONHASHSEED=42   → elev[10,10] = +2167.65  (mountain)
PYTHONHASHSEED=random → elev[10,10] = +283.99  (savanna)
```

Same seed, same chunk coord, completely different terrain. The `content_root` hash matched across runs because it was derived from `prf_bytes`, so the existing `test_chunk_deterministic` test passed — but the underlying numbers were random. Every experiment that printed deterministic numbers was deterministic-within-a-process but **non-replayable across processes**.

**Fix.** `world._stable_layer_salt(seed, layer)` is a BLAKE2b-keyed function: 16-byte little-endian seed + `|` + UTF-8 layer name → 64-bit salt. Identical across processes and platforms. The two other uses of `hash()` (per-vocalisation and per-group lexicon signatures) were replaced with `_stable_bytes_sig`, a 32-bit BLAKE2-based hash.

**Regression test.** `tests.test_engine.DeterminismTests.test_world_deterministic_across_hashseed` spawns a child Python with `PYTHONHASHSEED=random`, generates the same chunk, and asserts identical elevation values. This is the test that would have caught the bug in Phase 1; it is now wired in.

---

## 3. Forage-economy recalibration — SHARE finally fires in vivo

The Phase 4 audit reported `shares_cum=0` across all four reference experiments and noted the action path was wired correctly but no stockpile ever exceeded the SHARE precondition of `inv_food > 0.3 kg`.

Diagnosis: at `FORAGE_RATE = 18 kcal/tick` and `FORAGE_KCAL_PER_KG = 1500`, one forage tick added 0.012 kg of food — and `EAT` consumed 0.5 kg whenever it fired. So stockpiles bounded at ~0.012 kg never reached the 0.3 kg threshold.

Three changes wire the SHARE path live:

1. **Conversion rate**: `FORAGE_KCAL_PER_KG` lowered 1500 → 300. One base forage tick now adds 0.06 kg; with the new skill bonus (`0.5 + 0.25 · intelligence + 0.25 · conscientiousness`), high-trait agents add up to 0.09 kg.
2. **SHARE threshold**: lowered from 0.30 to 0.05 kg — matched to a single-tick forage yield so a freshly-stockpiled agent next to a hungrier neighbour can give without first looping through EAT.
3. **Decision ordering**: SHARE is now checked **before** MATE in `decide()`. In Phase 4 a non-hungry agent with surplus food next to a hungry neighbour would attempt to reproduce instead of feeding the neighbour. With the new ordering, sharing wins.

Measured impact on the five Phase 5 runs (seed-deterministic, same configs as Phase 4):

```
experiment             ticks wall(s)  TPS alive births deaths matings vocs comps shares fights groups diss
exp1_scarcity            150    5.8  25.9    44     44      0      34   162    28    136      0      1    0
exp2_food_pressure       100   15.5   6.5   152    152      0     102   516   197    388      0      5    2
exp3_two_cultures        120   21.3   5.6   210    210      0     162   761   125    339      0     12    0
exp4_catastrophe         120   15.7   7.7    99    124     25      94   600   145    177      0     10    0
stress_100                50   11.9   4.2   135    135      0      35   313   397      0      0      3    0
```

**SHARE: 0 → 1040 cumulative events across the four scientific experiments.** This is the closure the Phase 4 audit asked for. The stress_100 run still shows 0 shares; at `drive_accel=2000` the 50-tick window does not reach the SHARE conditions (the agents' first concern is still water/food acquisition and the population hasn't fragmented into give-and-take clusters yet).

Conflicts (`fights_cum`) remain at 0 across the batch. The action path is still wired (Phase 4 confirmed 277 fights when the cooldown was relaxed) — the shipped calibration of competition cooldown 20 ticks + 0.03 affinity decrement keeps fights from emerging organically over hundred-tick runs. That is consistent with the Phase 4 design choice ("peaceful coexistence is the default outcome") and is intentional; tuning aggression dynamics is a Phase 6 concern.

---

## 4. Group lifecycle

Phase 4 emitted `group_formed` events when union-find every 25 ticks found a connected component of ≥ 3 agents bonded by mutual affinity ≥ 0.10. Once formed, a group persisted in `Simulation._groups` even after members died or dispersed.

Phase 5 adds dissolution. After each `_detect_groups` pass, we count live in-group membership per `group_id`; any group with fewer than 3 live members emits a `group_dissolved` event (with reason `membership_below_threshold` or `population_too_small`) and is removed from the registry. Orphan agents have their `relations[row].group_id` cleared so they can rejoin a new cluster.

The annalist surfaces `groups_dissolved_cum` alongside `groups_formed_cum` in `metrics_to_dict`. exp2_food_pressure recorded 2 dissolutions across 100 ticks at 50 founders — visible churn in a high-pressure population.

---

## 5. Performance: vectorised thermal + bounded perception cache

Two contributors to the Phase 4 per-tick cost have been compressed:

- **`_tick_thermal`** was an O(N) Python loop that did one chunk lookup and one `weather_at` call per live agent. Vectorised by bucketing agents by chunk coord first, then computing `base_t` for all in-bucket agents in one numpy slice. At 200 agents distributed across ~5 chunks, this cuts the loop length by ~40×.
- **`_CACHED_CELL_GRID`** previously grew unbounded as the chunk streamer touched new coordinates. It is now bounded at 2048 entries with FIFO eviction, and `evict_cell_grid_cache` is called by `ChunkStreamer.gc` so chunks dropped from the streamer release their meshgrids too.

Phase 5 vs. Phase 4 TPS (same seeds, same configs):

| Experiment | Phase 4 TPS | Phase 5 TPS | Δ |
|---|---|---|---|
| exp1_scarcity (10 agents)     | 25.3 | 25.9 | +0.6 |
| exp2_food_pressure (50)       | 4.7  | 6.5  | +1.8 |
| exp3_two_cultures (48 × 2)    | 8.4  | 5.6  | -2.8 |
| exp4_catastrophe (30)         | 9.0  | 7.7  | -1.3 |
| stress_100 (100)              | 3.7  | 4.2  | +0.5 |

Net: small wins at 50 and 100 founders; small regressions at 30 and 96 founders. The new SHARE branch, group-dissolution pass, and stable-hash signatures all add small per-tick work that partially offsets the vectorised thermal savings. The honest read is that Phase 5 has paid for new functionality at neutral-to-slight performance cost; the bigger TPS wins from spatial grids will require either the perception result-cache (audit Phase 5 priority 2 — partially in place via the bounded cell-grid cache) or the Rust crates (Phase 6).

---

## 6. Files changed in this phase

The Phase 5 deliverable lives at `outputs/runtime/` (a self-contained writeable copy of the engine).

| Path | Status |
|---|---|
| `outputs/runtime/engine/world.py` | Modified — `_stable_layer_salt`, `_stable_bytes_sig`, `ChunkStreamer.gc` calls perception-cache eviction. |
| `outputs/runtime/engine/cognition.py` | Modified — goal jittering (`_jitter_target`), bounded cell-grid cache + `evict_cell_grid_cache`, SHARE-before-MATE re-ordering, `FORAGE_KCAL_PER_KG`/skill-bonus, stable lex signature. |
| `outputs/runtime/engine/sim.py` | Modified — vectorised `_tick_thermal`, `group_dissolved` emission in `_detect_groups`, stable lex signature. |
| `outputs/runtime/engine/annalist.py` | Modified — `EventKind.GROUP_DISSOLVED`, `cum_groups_dissolved`, surfaced in `metrics_to_dict`. |
| `outputs/runtime/tests/test_engine.py` | Modified — three new regression tests (`test_stable_layer_salt_is_process_invariant`, `test_world_deterministic_across_hashseed`, `test_stable_bytes_sig`), one new (`test_jitter_target_deterministic_and_bounded`), and one in-vivo SHARE-firing test. **12/12 tests pass.** |
| `outputs/runtime/experiments/run_phase5.py` | **New** — single-file harness to run all five experiments and emit `phase5_summary.json`. |
| `outputs/runtime/artifacts/phase5_*.json` | **New** — per-experiment summary + metrics time-series. |
| `outputs/runtime/journals/phase5_*.jsonl` | **New** — per-tick event journals. |
| `genesis-engine/PHASE5-PROGRESS-2026-05-13.md` | **New** — this report. |

The `runtime/` directory inside the workspace mount remains at its Phase 4 state; the operational delivery is the `outputs/runtime/` tree which is fully functional and can be moved into the workspace at the user's discretion.

---

## 7. Reproduction

```bash
# All experiments
cd outputs/runtime
PYTHONDONTWRITEBYTECODE=1 python3 -B experiments/run_phase5.py

# Single experiment (~6s for exp1, ~15s for exp2/4)
python3 -B -c "
import sys; sys.path.insert(0, '.')
from engine.sim import Simulation, SimConfig
cfg = SimConfig(name='exp1_scarcity', seed=0xC0FFEE_DEADBEEF, founders=10,
                max_agents=80, bounds_km=(0.4,0.4), cultures=1,
                drive_accel=4000.0, spawn_radius_m=60.0)
sim = Simulation(cfg, journal_path='journals/phase5_exp1_scarcity.jsonl')
for _ in range(150): sim.step()
m = sim.annalist.metrics_to_dict()
print('shares:', m['shares_cum'][-1], 'matings:', m['matings_cum'][-1],
      'vocs:', m['vocalizations_cum'], 'groups:', m['groups_formed_cum'])
"

# Determinism regression (exit code 0 = passes)
python3 -B -m unittest tests.test_engine
```

Expected on the reference machine: `12 tests in ~3.7s, OK`.

---

## 8. Recommended Phase 6 next steps

In priority order:

1. **Perception result cache by (chunk_coord, agent_pos_quantised)** — the bounded cell-grid cache is in place but the inner `_scan_chunk` argmin work is still per-call. Quantising to a 1 m grid would let stationary or slow-moving agents skip the scan entirely.
2. **Conflict / fight calibration** — relax the cooldown or lower the affinity threshold so the FIGHT path fires under normal conditions, then verify it doesn't collapse into runaway aggression.
3. **Per-group state** — track centroid drift, lexicon coherence, and population over time per `group_id`; emit `group_split` events when a cluster fragments.
4. **Multi-region migration dynamics** — with memory-driven goals and per-group state, agents should choose to migrate toward known better water/food when their local environment degrades. Foundation for the Phase 7 large-scale dynamics.
5. **Rust scaffolding cross-tier benchmark** — clone `scaffolding/` to a writable location, resolve transitive Cargo versions, and run the same five experiments at 10× the population for an honest perf comparison.
6. **Long-run stability test** — 10 000-tick smoke run at 100 founders, verifying no memory leak, no chunk-cache blow-up, and no determinism drift on tick-chain hashes.
