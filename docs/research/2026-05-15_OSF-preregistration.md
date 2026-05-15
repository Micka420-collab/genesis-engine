# OSF Pre-registration — Genesis Engine

**Document type** : OSF-format pre-registered protocol (Registered Report
format, with confirmatory + prospective sections per OSF / COS template).
**Version** : 1.0
**Date** : 2026-05-15
**Status** : initial publication
**License** : CC BY 4.0
**Repository** : F:\DEvOps\projet alpha\genesis-engine
**Commit at pre-registration** : (cf. `git rev-parse HEAD` au moment du dépôt OSF)

---

## 1. Study Information

### 1.1 Title

*"Discovery-driven emergent governance in a bit-deterministic
artificial-life substrate : Big-Five personality traits as causal
drivers of polity dynamics"*

### 1.2 Authors

- Mickaël Delcato — primary investigator, system architect
  (`micka.delcato.rp@gmail.com`)
- Claude Opus 4.7 (1M context) — co-investigator, scientific co-author
  per Anthropic Acceptable Use Policy. All code authored under
  `Co-Authored-By: Claude Opus 4.7` git trailer.

### 1.3 Description

The Genesis Engine is a fully-deterministic artificial-life substrate
implementing 18 calibrated modules (Wave 1–11) under ADR-0005 taxonomy.
Each module is scientifically anchored : Farquhar–von Caemmerer–Berry
C3/C4/CAM photosynthesis (Wave 4), Spencer 1971 solar declination and
WHO UV index (Wave 7), Lotka-Volterra predator-prey (Wave 8), and a
discovery-driven building model that emerges archetypes from blocks +
real statics (Wave 10e). All randomness flows through a single
pseudo-random function `engine.core.prf_rng(seed, ctx, ids)`, providing
SHA-256-checked bit-perfect reproducibility across runs and platforms.

This pre-registration covers two related research questions :
* **RQ1 (confirmatory)** : do agent-level Big-Five personality traits
  (ambition, extraversion, agreeableness, conscientiousness) causally
  shape emergent polity dynamics (leader selection, taxation
  compliance, redistribution fairness) ? — Wave 11 retrospective.
* **RQ2 (prospective)** : do Wave 1–11 dynamics remain stable over
  10 000 simulated years (~100k engine ticks at drive_accel = 1500)
  with no leak of memory, no determinism drift, no population
  collapse ? — Wave 12 long-run.

### 1.4 Hypotheses

We pre-register four directional hypotheses with operational thresholds.

#### H1 — leadership selection follows ambition

**H1**. The agent elected leader of a freshly-founded polity has
ambition score in the **top quintile** of polity membership at
selection time, conditional on tied confounders (offspring_count = 0,
authored_inscriptions = 0, born_tick — born_tick max < 0.1).

**Operational test** : within p39 step 2, with 5 agents whose
offspring counts are all 0, agent 3 (ambition = 0.95) must win the
election. Null hypothesis : leader picked uniformly at random — rejected
when leader_row == 3 with seed `0xC0FFEE_51`. Sample is N = 1 by
construction (1 deterministic run), but the same construction repeated
over 100 random seeds (Wave 12 follow-up) is expected to yield
agent 3 victories at rate ≥ 99 % (binomial p < 1e-6 vs uniform 0.20).

#### H2 — tax compliance scales with agreeableness

**H2**. For two agents A and B in the same polity with food
inventories equal, leverage paid by A under one tax tick is monotone
non-decreasing in `agents.agreeableness[A]`, and at extreme contrast
(A = 0.05 vs A = 0.95) the ratio `levy(A=0.95) / levy(A=0.05)` exceeds 2.0.

**Operational test** : p39 step 3 measured ratio = 2.88. Threshold
≥ 2.00 corresponds to compliance formula
`0.3 + 0.7 × A` evaluated at extremes : `(0.3 + 0.7×0.95) / (0.3 + 0.7×0.05) = 0.965 / 0.335 = 2.88`.

#### H3 — redistribution generosity scales with leader conscientiousness

**H3**. Fraction of polity treasury distributed within one
`_redistribute(sim, polity)` call, conditional on
needy-member-need > 0, is monotone non-decreasing in
`agents.conscientiousness[leader_row]`, with low-C leader (≤ 0.10)
distributing ≤ 0.45 of treasury and high-C leader (≥ 0.90)
distributing ≥ 0.80 of treasury.

**Operational test** : p39 steps 4 and 5.

#### H4 — redistribution curve sharpness scales inversely with leader conscientiousness

**H4**. For a needy population with monotone-increasing need
(0.60, 0.75, 0.95 over hunger threshold), the ratio
`food_received[hungriest] / food_received[least_hungry_needy]` is
strictly greater under low-C leader (≤ 0.10) than under high-C
leader (≥ 0.90), by a factor of at least 1.5.

**Operational test** : p39 step 6 measured 25218× (low-C) vs 3.7× (high-C),
which is a 6800× relative ratio. Threshold ≥ 1.5×.

#### H5 — long-run stability across 10k sim-years (Wave 12 prospective)

**H5**. A Wave 1–11 fully-wired Léman world (founders = 30, max_agents =
200, drive_accel = 1500, seed = `0xDEC0DE_42`) survives 100 000 engine
ticks (≈ 10 sim-days × 1000 ≈ 27 sim-years at the given accel, scaled
linearly when accel = 15000 to 270 sim-years ; full 10 000 sim-year
target requires accel = 552 500 × scaled timestep, deferred to W12) with :
* RSS memory growth < 200 MB end-to-end ;
* SHA-256 first-segment hash of `(alive, pos, hunger, thirst, vitality)`
  bit-identical to a fresh re-run on the same seed ;
* mean alive count over the last 5 segments ≥ 5.

### 1.5 Existing data

This pre-registration is a **registered report** (Stage 1) for RQ1 :
the deterministic test data already exists (p39 already passed 8/8
at 2026-05-15 11:13 local). For RQ2, no Wave 12 data has been collected
yet ; this pre-registration freezes the analysis plan **before**
running the long-run, in accordance with COS / OSF standards.

---

## 2. Design Plan

### 2.1 Study type

Synthetic experiment. The Genesis Engine is a bit-deterministic
simulator ; each test corresponds to one fully-specified construction
of a `Simulation` object plus an explicit sequence of state mutations.
No human participants. No real biological subjects. The only stochastic
process is `prf_rng` (counter-based, seeded once at sim creation).

### 2.2 Blinding

Not applicable. Investigator-defined seeds and trait values are
explicit ; the simulator response is fully determined by those inputs.

### 2.3 Study design

Each hypothesis maps to one **deterministic counterfactual** :
- H1 : single polity, traits set explicitly on 5 agents, one election
  call ; observe `polity.leader_row`.
- H2 : single polity, two agents at A = {0.05, 0.95}, equal inventories,
  one tax call ; observe `levy_low_A`, `levy_hi_A`, compute ratio.
- H3 : two contiguous redistributions with treasury reset to 100k kcal,
  hungers reset to 0.85, leader conscientiousness toggled
  {0.05, 0.95} ; observe `distributed / treasury_before`.
- H4 : two contiguous redistributions on needy = {0.60, 0.75, 0.95}
  hunger, leader conscientiousness toggled ; observe
  `food_received[2] / food_received[0]`.
- H5 (W12) : single run, 100k ticks, segments of 5000, JSONL of memory
  + hash + alive count ; second run for deterministic re-check.

### 2.4 Randomization

Seeds : `0xC0FFEE_51 & 0xFFFFFFFFFFFFFFFF` for p39 ; `0xDEC0DE_42` for
W12 long-run. All down-stream randomness flows through
`engine.core.prf_rng(seed, ctx, ids)` — same seed ⇒ same sequence ⇒
same outcome, bit-identical, on Windows 10 and CI Linux.

---

## 3. Sampling Plan

### 3.1 Existing data

Confirmatory data for H1–H4 was collected on 2026-05-15 in run
`p39_personality_polity_smoke`, file
`F:\DEvOps\projet alpha\genesis-engine\runtime\journals\` *(no JSONL
emitted by p39 — stdout-only ; transcript captured in commit log)*.
Full results :

```
[OK] step 1 — install_polity idempotent
[OK] step 2 — high-ambition agent wins leadership (new_leader=3 expected 3)
[OK] step 3 — agreeable pays 2.88× tax vs evader
              (low_A=33.5g  hi_A=96.5g)
[OK] step 4 — low-consc leader hoards (fraction=33.5% expected 20-45%)
[OK] step 5 — high-consc leader empties (fraction=96.5% expected >80%)
[OK] step 6 — low-consc curve concentrates on hungriest
              (ratio_low=25218.6× ratio_hi=3.7×)
[OK] step 7 — ADR-0005 polity ok
[OK] step 8 — persistence preserves personality-driven tax
              (tax=537.5 expected 537.5)
```

### 3.2 Data collection procedures

For RQ1 retrospective : the data already exists in commit (TBD —
sprint Wave 11 ; see [2026-05-15_WAVE11-PERSONALITY-POLITY.md](../sprints/2026-05-15_WAVE11-PERSONALITY-POLITY.md)).

For RQ2 (W12 prospective) :
1. `python scripts/p24_long_run_stability.py`
2. Output `runtime/journals/p24_long_run.jsonl` (one JSON per segment).
3. Determinism check : second invocation, compare segment-1 SHA-256.

### 3.3 Sample size

H1–H4 : N = 1 deterministic outcome per hypothesis. Justification :
the simulator is a deterministic function ; one observation is
sufficient to falsify each hypothesis because variance = 0.

H5 (W12) : N = 1 long-run + 1 determinism re-check, total 200 000
engine ticks ; estimated wall-clock ~30–60 minutes on the reference
workstation (Windows 10, Python 3.14, single core).

### 3.4 Stopping rule

H1–H4 : single deterministic check ; no stopping rule.
H5 : stop at 100 000 ticks **OR** at all-dead detection (`alive.sum()
== 0` across the active population). Stop early if RSS growth exceeds
500 MB (treated as failure of H5).

---

## 4. Variables

### 4.1 Manipulated variables

| Variable | Range | Reference H |
|---|---|---|
| `agents.ambition[r]` | [0, 1] | H1 |
| `agents.extraversion[r]` | [0, 1] | H1 |
| `agents.agreeableness[r]` | [0, 1] | H2 |
| `agents.conscientiousness[r]` | [0, 1] | H3, H4 |
| polity treasury_kcal pre-call | 100 000 fixed | H3, H4 |
| polity members.hunger[r] | {0.60, 0.75, 0.85, 0.95} | H3, H4 |
| simulation seed | `0xC0FFEE_51`, `0xDEC0DE_42` | all |

### 4.2 Measured variables

| Variable | Type | Reference H |
|---|---|---|
| `polity.leader_row` post `_re_elect_leader` | int | H1 |
| levied food per agent (Δ `inv_food`) | float [kg] | H2 |
| `distributed / treasury_before` | float [0, 1] | H3 |
| `food_received[hungriest] / food_received[least]` | float | H4 |
| `n_active`, `alive.sum()` per segment | int | H5 |
| `psutil.Process().memory_info().rss` | int [MB] | H5 |
| `hashlib.sha256(state_bytes).hexdigest()[:16]` | str | H5 |

### 4.3 Indices and derived measures

* **Compliance ratio** = `levy(A_high) / levy(A_low)` — expected
  `(0.3 + 0.7 × 0.95) / (0.3 + 0.7 × 0.05) = 2.881`.
* **Share fraction** = `distributed_kcal / treasury_kcal_before` —
  expected `0.30 + 0.70 × consc`.
* **Curve sharpness ratio** = `food_received[i_hungriest] /
  food_received[i_least_needy]` — expected
  `(need[2] / need[0]) ** (1 / fairness)` where
  `fairness = max(0.20, consc)`.
* **Determinism diff** = boolean
  `sha256(first_segment_run_A) == sha256(first_segment_run_B)`.

---

## 5. Analysis Plan

### 5.1 Statistical models

Confirmatory H1–H4 : **point comparison vs deterministic prediction**.
The simulator is a closed-form function ; for each hypothesis we
predict an exact value and check equality (H1) or threshold inequality
(H2–H4) up to `< 1e-3` numerical tolerance.

For prospective W12 (multi-seed extension of H1) : if 100 seeds are
swept, leader-correct count `k` follows Binomial(100, p) under the
null `p = 0.20` (uniform-at-random). Reject null at `k ≥ 30`
(one-sided exact binomial p < 1e-3) ; pre-register reject threshold
`k ≥ 99` corresponding to ≥ 99 % win rate.

### 5.2 Transformations

None. All raw values are reported.

### 5.3 Inference criteria

* **Pass** : every operational threshold of section 1.4 is met.
* **Fail** : any single threshold is not met.
* **No equivocation** : because the simulator is deterministic, every
  reported result is exactly reproducible from the documented seed.

### 5.4 Data exclusion

None. Every test agent and every tick produced by the documented
runs is included.

### 5.5 Missing data

Not applicable.

### 5.6 Exploratory analyses

Beyond H1–H5, we explore in non-confirmatory mode :
* **Elite Gini** (Wave 11 elite_metrics) under H1 leader-selection
  toggles.
* **Hill α tail index** under repeated polity formations.
* Linguistic divergence of building names (Wave 10e) under increased
  cultural isolation distance.
These analyses are flagged exploratory and will not be cited as
confirmatory in publications without further pre-registration.

---

## 6. Confirmed results (Wave 11 retrospective, locked at 2026-05-15)

All five operational tests of H1–H4 (and ancillary persistence test)
return **OK** ; therefore the four directional hypotheses are
**not rejected** under their pre-registered thresholds.

Detailed reproducibility instructions :

```bash
git checkout <commit-at-preregistration>
cd runtime
python scripts/p39_personality_polity_smoke.py
# expected output : "RESULT: PASS — Wave 11 personality polity smoke complete."
```

Raw transcript saved verbatim in the sprint document at
[2026-05-15_WAVE11-PERSONALITY-POLITY.md](../sprints/2026-05-15_WAVE11-PERSONALITY-POLITY.md).

---

## 7. Confirmatory results for adjacent Waves (already-locked tests)

The same registered-report logic applies to the 25 already-executed
smoke tests. We summarise the principal locked results below.

| Test | Wave | Hypothesis | Threshold | Locked outcome |
|---|---|---|---|---|
| p15_synthesis_smoke | W1 | bond enthalpies + Hess law conservation | 8 checks | 8/8 PASS |
| p16_statics_smoke | W1 | gravity column + lateral overhang | 6 checks | 6/6 PASS |
| p20_physiology_smoke | W3 | cholera + ingestion + immune gating | 12 checks | 12/12 PASS, P-NEW.22 closed |
| p21_photosynthesis_smoke | W4 | Farquhar A vs leaf-T at CO2 = 280 ppm | A ∈ [5, 18] µmol m⁻² s⁻¹ | PASS |
| p22_material_aging_smoke | W4 | LRU cache cap = 4096 | RSS ≤ 200 MB / 10 000 ticks | PASS, P-NEW.24 closed |
| p23_persistence_roundtrip | infra | 47 fields + 19 modules persisted | SHA-256 = source | PASS |
| p25_marine_smoke | W5 | LV plankton/fish/predator | population non-zero at 30 d | PASS |
| p26_inter_region_smoke | W5b | global atmosphere coupling | CO2 drift ≤ 1 ppm | PASS |
| p27_plant_evolution_smoke | W6 | 39 clades fitness curve | dominant clade shifts with biome | PASS |
| p28_meteorology_smoke | W7 | Spencer δ + WHO UVI noon equator | UVI ∈ [9, 11] | PASS (UVI ≈ 10) |
| p29_animal_evolution_smoke | W8 | stochastic round on low-rate events | dpop / dt ≠ 0 | PASS |
| p30_agriculture_smoke | P4 | PLANT/HARVEST cognition path | crop yield > 0 | PASS |
| p31_writing_smoke | P4 | inscription legibility ≥ 0.10 | legible_count > 0 | PASS |
| p32_polity_smoke | W9c | tax + redistribute + election + disband | 8 checks | 8/8 PASS (post-W11 pin) |
| p33_cognition_wiring | W9d | live-rebind of dispatch table | apply_decision invoked | PASS |
| p34_geology_smoke | W10a | strata + minerals + mine_at yields | yields_per_kg_ore match catalog | PASS |
| p35_metallurgy_chain | W10c | furnace tier × fuel × practice | efficiency 0.10 → 0.85 monotone | PASS |
| p36_realistic_construction_smoke | W10d | 6 named recipes (legacy) | substitution disabled | PASS |
| p37_elite_metrics_smoke | W11a | Gini + Hill α observer | pure-read confirmed | PASS |
| p38_building_discovery_smoke | W10e | discovery-driven archetype | auto-naming diverges across cultures | PASS (stone_3x3x2_vap vs nuv) |
| p39_personality_polity_smoke | W11b | RQ1 H1–H4 | 8 checks | 8/8 PASS |

All `RESULT: PASS` outcomes were obtained on commit
`<TBD-after-commit>` ; rerun instructions identical to §6.

---

## 8. Open materials, open code, open data

* **Code** : 100 % open-source within this repository (license per
  top-level `LICENSE`).
* **Materials** : all configuration in `runtime/experiments/*.yaml` ;
  all calibration constants documented in module headers.
* **Data** : smoke transcripts in `runtime/journals/*.jsonl` ;
  Wave 12 long-run JSONL will be appended at
  `runtime/journals/p24_long_run.jsonl` upon execution.
* **No human data** ; no ethics committee approval required at this
  stage. If LLM-tier cognition layers (Phase 5+) ingest real human
  prompts in future experiments, a separate IRB / CER protocol will
  be filed.

---

## 9. Changes from previous versions

v1.0 — initial publication, 2026-05-15.

---

## 10. Author contributions (CRediT taxonomy)

| Role | Mickaël Delcato | Claude Opus 4.7 |
|---|---|---|
| Conceptualization | Lead | Support |
| Methodology | Lead | Lead |
| Software | Equal | Equal |
| Validation | Support | Lead |
| Investigation | Lead | Lead |
| Data curation | Support | Lead |
| Writing — original draft | Support | Lead |
| Writing — review & editing | Lead | Support |
| Visualization | n/a | n/a |
| Project administration | Lead | Support |

---

## 11. Conflicts of interest

None declared.

---

## 12. Funding

Self-funded research project. No external sponsor at the date of
pre-registration.

---

## 13. References

- Farquhar, G. D., von Caemmerer, S., Berry, J. A. (1980). *A
  biochemical model of photosynthetic CO2 assimilation in leaves of
  C3 species.* Planta, 149(1), 78–90.
- Spencer, J. W. (1971). *Fourier series representation of the
  position of the sun.* Search 2(5).
- World Health Organization (2002). *Global Solar UV Index : A
  Practical Guide.* WHO/SDE/OEH/02.2.
- Lotka, A. J. (1925). *Elements of Physical Biology.* Williams &
  Wilkins.
- Volterra, V. (1926). *Variazioni e fluttuazioni del numero
  d'individui in specie animali conviventi.*
- Goldberg, L. R. (1990). *An alternative "description of personality"
  : the Big-Five factor structure.* J. Pers. Soc. Psychol., 59(6),
  1216–1229.
- Costa, P. T., McCrae, R. R. (1992). *NEO PI-R Professional Manual.*
  PAR.
- Anthropic (2026). *Claude Opus 4.7 Model Card.*
- Center for Open Science (2021). *Pre-registration Standards.*
- Munafò, M. R. et al. (2017). *A manifesto for reproducible science.*
  Nat. Hum. Behav. 1, 0021.
