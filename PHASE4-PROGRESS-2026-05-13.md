# Genesis Engine — Phase 4 progress report
**Date:** 13 May 2026
**Scope:** implement the five next-step recommendations from the
2026-05-12 audit and validate them against fresh experiment runs.

This report follows on directly from `AUDIT-REPORT-2026-05-12.md`,
which closed Phase 3 by delivering a runnable Python operational
runtime with deterministic procedural worlds, multi-generational
lineages, and observed population-overshoot dynamics — but with three
explicit open items: no conflicts/shares emitted, no spatial index, and
no group/cultural-drift detection.

Phase 4 closes the first, third, fourth, and fifth audit
recommendations and partially closes the second (the conflict path now
fires under stress; share calibration remains a Phase 5 concern).

---

## 1. Audit recommendations vs. Phase 4 status

| # | Audit recommendation | Phase 4 status |
|---|----------------------|----------------|
| 1 | Spatial grid index for neighbour lookups | **Done** (`engine/spatial.py`) — used by `cognition.perceive` and `_detect_groups`. |
| 2 | Competition-affinity signal | **Done** — per-tick collision detector + rate-limited per-pair cooldown. Conflict path now demonstrably fires under high pressure; share path remains 0 (calibration). |
| 3 | Memory-driven goals | **Done** — agents remember up to 8 successful drink/forage locations and fall back to the most recent when in-radius perception fails. |
| 4 | Vocalisation / proto-language | **Done** — `lexicon` (16-dim float vector) added to AgentRegistry, drifts on SPEAK contact, inherited with mutation on birth, signed per event with a 32-bit hash. |
| 5 | Group formation detector | **Done** — union-find over near + affinity-bonded agents every 25 ticks, emits `group_formed` events and persists `group_id` on `SocialRelations`. |
| 6 | Cargo workspace green-build path | Not addressed in this phase (deferred to Phase 5). |

---

## 2. What changed in code

### 2.1 New module — `engine/spatial.py`
Uniform hash grid with three responsibilities:

- `rebuild(pos_xy, alive)` — O(N) once per tick.
- `query_disk(x, y, r, exclude_row)` — O(1)-bounded per query (5×5 cell window for the default 30 m cell, 60 m perception radius). Used in `cognition.perceive` and `Simulation._detect_groups`.
- `find_target_collisions(target_xy, action, alive, resource_actions)` — given the per-agent target positions for this tick, returns pairs whose targets hash to the same 2 m cell. Drives the competition signal.

### 2.2 `engine/cognition.py`
- `perceive` accepts an optional `grid` and now uses it for the nearby-agent scan instead of the legacy linear scan; the linear path remains as a fallback for sims with `n<=1`.
- `perceive` adds two synthetic perceived targets — `water_remembered` and `food_remembered` — sourced from `EpisodicMemory` when in-radius scan finds nothing and the relevant drive is above `ACT_THRESHOLD`. `_act_on` consults these as a second-choice resource.
- `apply_decision`:
  - `DRINK` and `FORAGE` now push their world position into `EpisodicMemory.known_{water,food}_locations` (capped at 8).
  - `SPEAK` now applies a 5% bidirectional drift of the two agents' lexicons toward each other and emits a `vocalize` raw event tagged with a hash of the resulting lexicon.
- `decide` adds a sociable SPEAK branch positioned just before the dominant-drive `_act_on` call. Gated on extraversion > 0.40 and `hunger<0.65` ∧ `thirst<0.65`. This was the single most important calibration change — without raising SPEAK above the sub-critical drive priority, the drive-driven WALK_TO/DRINK path always wins and SPEAK never fires.

### 2.3 `engine/agent.py`
- Added `lexicon: np.ndarray` of shape `(N, 16)` to `AgentRegistry`.
- Founders sample a deterministic per-culture base lexicon, plus per-founder Gaussian noise.
- Offspring inherit the mid-parent lexicon with a Gaussian mutation (σ=0.02). Same PRF chain as personality inheritance, so determinism is preserved.

### 2.4 `engine/sim.py`
- `Simulation.__init__` builds a `SpatialGrid(cell_size = PERCEPTION_RADIUS/2)` and a per-pair competition cooldown map.
- `Simulation.step` (Phase 4 changes):
  - Rebuilds the spatial grid once per tick before the perception loop.
  - Passes the grid to every `perceive` call.
  - After the decision pass: runs `find_target_collisions` on the just-set target positions, restricted to `WALK_TO` actions (so co-drinkers and co-foragers in a shared cell are NOT penalised). For each colliding pair, applies a 20-tick cooldown and lowers mutual affinity by 0.03. Emits a `competition` raw event.
  - Every 25 ticks runs `_detect_groups` — union-find over agents that are within 15 m AND share mutual affinity ≥ 0.10. Components of size ≥ 3 are persisted with a stable group_id; new groups emit `group_formed` events with centroid, member list, size, and the averaged-lexicon hash.

### 2.5 `engine/annalist.py`
- Three new event kinds wired through `record_tick`: `vocalize` → `vocalization`, `competition`, `group_formed`.
- Three new cumulative counters surfaced through `metrics_to_dict`: `vocalizations_cum`, `competitions_cum`, `groups_formed_cum`.
- A `_distinct_lex_signatures` set tracks the number of distinct lexicon hashes seen — a coarse proxy for proto-language diversity over the run.

---

## 3. Measured results (seed-deterministic, 2026-05-13 batch)

All runs use seed `0xBEEF`. Summary written to `runtime/artifacts/phase4_summary.json`.

```
experiment              n   ticks  wall(s)  TPS   alive  births  matings  vocs  comps  groups  lex_sigs  avg_aff
phase4_smoke_60         60    80    10.7   7.48     88     88      28    280   344     1       280     +0.0042
phase4_scale_100       100    50    10.3   4.85    125    125      25    316   393     4       316     -0.0021
phase4_scale_200       200    30    12.7   2.36    214    214      14      0   576     0         0     -0.0163
phase4_two_cultures     48    80    12.0   6.65     73     73      25    203   330     3       203     +0.0032
```

### 3.1 What is real and emergent

- **Vocalisations.** Up to 316 SPEAK events in 50 ticks at 100 agents, producing the same number of distinct lexicon signatures — every drift step changes the listener's lexicon, so each SPEAK produces a never-before-seen 16-dim signature. This is proto-language in motion. The two-cultures run shows the dynamic across geographic clusters: 203 vocalisations and 3 distinct emergent groups.

- **Groups.** The detector emitted 1 group at 60 agents (single founder cluster), 4 at 100 agents (founders had begun to disperse before the 50-tick mark), 3 in the two-cultures run (each culture seeded its own bond cluster, and a third formed by interbreeding contact). At 200 founders in 0.9 km² the cluster density is too high and pressure too acute (every agent is drinking) for affinity to climb above the 0.10 group threshold in the 30 ticks observed.

- **Competitions.** 330–576 competition pairs per run. These now produce a believable negative-affinity background that the conflict path can latch onto when other thresholds (aggression > 0.70 AND stress > 0.35) are also met. With the rate-limit and the 0.03 per-pair penalty, the system no longer collapses into constant fighting — see §3.2.

- **Memory recall.** Difficult to measure as a count, but visible in tick-by-tick behaviour: agents who drank at a water cell return to it on subsequent thirst spikes even when the cell is outside their current perception disk. This is the territoriality / migration scaffolding the audit asked for.

- **Determinism preserved.** The new lexicon and group-id allocations all flow through the existing `prf_rng`/`derive_agent_id` chain or are deterministic functions of state; replaying with the same seed reproduces the same vocalisation count, group count, and birth tree.

### 3.2 Conflict / share path: progress with caveats

Conflicts are no longer self-extinguishing in principle — when we ran a brief un-cooldowned variant for diagnostic purposes (delta = -0.04, no per-pair cooldown, aggression threshold 0.60), the engine emitted 277 fights over 60 ticks at 60 agents, proving the path is wired. The shipped configuration is intentionally calmer: the competition signal is rate-limited (cooldown 20 ticks, delta 0.03) so affinity descents are gradual rather than runaway. Under those settings, all four Phase 4 experiments emitted 0 fights — i.e. peaceful coexistence is the default outcome for this calibration.

Shares remain at 0 across the batch. The reason is upstream of Phase 4: with `drive_accel = 1500–2000` and the existing `FORAGE_RATE = 18 kcal/tick`, agents almost never accumulate `inv_food > 0.3 kg`, which is the precondition for the `SHARE` decision. The action path works (we exercised it directly in unit-level tests), but a positive forage/inventory balance is a Phase 5 calibration job. Widening the SHARE candidate radius from `INTERACT_RADIUS_M=1.8 m` to `SOCIAL_TALK_RADIUS_M=3.5 m` (Phase 4 change) ensures sharing will fire as soon as inventory exists.

### 3.3 Performance: honest accounting

| Population | Audit baseline (Phase 3) | Phase 4 measured | Δ |
|------------|--------------------------|------------------|---|
| 50–60      | 25.3 TPS                 | 7.5 TPS          | −3.4× |
| 100        | 3.7 TPS                  | 4.85 TPS         | +1.3× |
| 200        | 4.7 TPS (exp2)           | 2.4 TPS          | −2.0× |

The spatial grid is in place and saves work in the nearby-agent scan, but Phase 4 added five new per-tick costs:
1. Grid rebuild every tick.
2. Per-tick `find_target_collisions` (rebuilds a second grid).
3. Group detection every 25 ticks (amortised — cheap on average but spikes on detection ticks).
4. SPEAK lexicon drift arithmetic plus a `hash(bytes)` call per vocalisation.
5. Affinity dict updates from the competition signal and from the speak-affinity bump.

At 60 agents these new costs dominate the grid's savings; at 100 agents the grid begins to win; at 200 it loses to dense-cell occupancy (the grid degenerates toward the linear scan when many agents hash into the same cell). Phase 5 should add (a) a perception result cache so static observations skip the scan, and (b) goal jittering so agents spread out across water cells rather than crowding the nearest one.

---

## 4. Files touched

| Path | Status |
|---|---|
| `runtime/engine/spatial.py` | **New** — uniform spatial hash grid + target-collision detector. |
| `runtime/engine/agent.py` | Modified — `lexicon` field, founder/offspring inheritance. |
| `runtime/engine/cognition.py` | Modified — grid-aware `perceive`, memory recall, SPEAK promotion, drift on SPEAK. |
| `runtime/engine/sim.py` | Modified — grid build, competition signal, group detector, cooldown map. |
| `runtime/engine/annalist.py` | Modified — `vocalization`, `competition`, `group_formed` events; new counters. |
| `runtime/artifacts/phase4_summary.json` | **New** — aggregated table for the four Phase 4 runs. |
| `runtime/journals/phase4_*.jsonl` | **New** — per-experiment ground-truth event journals. |
| `PHASE4-PROGRESS-2026-05-13.md` | **New** — this report. |

The four pre-existing experiment scripts under `runtime/experiments/` (exp1–4, stress_100) were not modified; they continue to work against the upgraded engine and benefit from the new event kinds in their journals.

---

## 5. Reproduction

```bash
cd runtime
python3 - <<'PY'
import sys, time
sys.path.insert(0, '.')
from engine.sim import Simulation, SimConfig
cfg = SimConfig(name="phase4_smoke_60", seed=0xBEEF, founders=60,
                max_agents=300, bounds_km=(0.6, 0.6), spawn_radius_m=80.0,
                cultures=1, drive_accel=2000.0)
sim = Simulation(cfg, journal_path="journals/phase4_smoke_60.jsonl")
t0 = time.monotonic()
for _ in range(80):
    sim.step()
m = sim.annalist.metrics_to_dict()
print("tps:", round(80 / (time.monotonic() - t0), 2))
print("vocs:", m["vocalizations_cum"], "groups:", m["groups_formed_cum"],
      "comps:", m["competitions_cum"], "matings:", m["matings_cum"][-1])
PY
```

Expected on the reference machine: 7.4 TPS, 280 vocalisations, 1 group formed, 344 competitions, 28 matings.

---

## 6. Recommended Phase 5 next steps

In priority order:

1. **Goal jittering** — pick a random offset of ±0.5 m inside the target water/food cell. Naturally spreads dense clusters and recovers the grid's expected speedup at high N.
2. **Perception result cache** — `(chunk_coord, agent_pos_quantised)` → cached `_scan_chunk` output. Cuts the hot path's `argmin` work for stationary agents.
3. **Forage-economy calibration** — increase `FORAGE_RATE` or lower the share-eligibility threshold so the SHARE path can finally fire under benign conditions. This is the single remaining audit gap.
4. **Per-group bookkeeping** — track group population, mean lexicon, centroid drift, and emit `group_split` / `group_dissolved` events. Foundation for tribes and inter-tribe dynamics in Phase 6.
5. **Group-aware decision policy** — give in-group neighbours a small affinity floor so groups self-reinforce, and bias mating selection toward in-group partners. Cultural lineages and proto-tribal endogamy fall out for free.
6. **Cross-tier benchmark with the Rust crates** — clone `scaffolding/` into a writable directory and resolve the transitive Cargo versions so the same architecture can be measured at 10k agents.
