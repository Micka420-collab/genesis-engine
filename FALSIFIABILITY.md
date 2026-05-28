# Genesis Engine — Falsifiability Ledger

> **Status:** initial scaffold, 2026-05-27. Entries added as runs validate
> preregistered predictions. This file is the artifact that distinguishes
> Genesis Engine from a demo: every emergent claim we make is here, with
> the conditions under which we would consider it refuted.

---

## Why this exists

Karl Popper: a scientific claim must specify in advance what observation
would falsify it. Saying "civilizations emerge from the simulation" without
a refutation condition is unfalsifiable theatre. Saying "in run X, with
`state_fingerprint = abc…`, the per-agent trade count exceeded the
random-decision control by ≥ 3× across 10 seeds, and we would consider the
claim refuted if the difference fell below 1.5× on a future seed" is
testable — and testable claims are the only kind that count as evidence.

The mechanics:

1. Every entry below names a **claim** that the engine produces a specific
   observable.
2. Each claim cites a **refutation condition** — a numeric threshold on a
   summary metric. If a future run with the same code crosses that threshold
   in the wrong direction, the claim is refuted and must be downgraded or
   removed.
3. Each claim links to one or more **anchor runs** — committed
   preregistrations + their `state_fingerprint` from `manifest.json`. The
   fingerprint is the reproducibility handle: anyone with the same git commit
   can rerun and produce the same fingerprint.
4. Status flow: `pending` → `confirmed` → (rarely) `refuted` or
   `superseded`. A `confirmed` claim stays in the ledger; an `refuted` one
   moves to the bottom with the refuting run cited.

If you don't have an anchor run with a `state_fingerprint`, your claim is
not ready to be here. Use [`PREREGISTRATION_TEMPLATE.md`](runtime/experiments/PREREGISTRATION_TEMPLATE.md)
to set up a real test first.

---

## How to add an entry

1. Write a preregistration (`runtime/experiments/<run_id>/preregistration.md`)
   declaring the hypothesis, observable, threshold, and stop conditions.
2. Run with `experimental_run`. Note the `state_fingerprint` from `manifest.json`.
3. If the prediction held: add a row in the **Confirmed claims** table below
   with the fingerprint and the refutation condition. Commit both the
   preregistration and this update in the same PR.
4. If the prediction failed: add to **Null results** with what you observed
   instead. Null results are evidence too — keep them.
5. If a previously confirmed claim later fails: move it to **Refuted claims**
   with the refuting run's fingerprint, and downgrade or qualify any README
   text that cited it.

A confirmation requires **at least 3 distinct seeds** (per `docs/RUNTIME-LAYOUT.md`
methodology). One-seed runs go in **Pending** until corroborated.

---

## Active claims

### Confirmed

| ID  | Claim | Observable (summary key) | Refutation if… | Anchor runs (state_fingerprint) | Last verified |
|-----|-------|--------------------------|-----------------|----------------------------------|---------------|
| _none yet_ | _Move a claim here once 3+ seeds independently produce the predicted observable on the same git commit._ | | | | |

### Pending corroboration (1-2 seeds, awaiting more)

| ID  | Claim | Observable | Refutation if… | Anchor runs | Seeds tested |
|-----|-------|------------|-----------------|-------------|---------------|
| _none yet_ | | | | | |

### Null results (predictions that did not hold)

| ID  | Predicted | Observed | Anchor runs |
|-----|-----------|----------|-------------|
| _none yet_ | | | |

### Refuted (previously confirmed, later falsified)

| ID  | Claim | Was confirmed by | Refuted by | Date |
|-----|-------|-------------------|------------|------|
| _none yet_ | | | | |

### Superseded (replaced by a more specific claim)

| ID  | Old claim | New claim (ID) | Reason | Date |
|-----|-----------|----------------|--------|------|
| _none yet_ | | | | |

---

## Engine-level invariants (not emergent claims — bit-level guarantees)

These are not falsifiable hypotheses about emergence; they are
properties of the substrate that must hold or the engine is broken. They
live here because their failure also forces a re-evaluation of every
emergent claim above (a broken substrate means even confirmed claims need
re-checking).

| ID   | Invariant | Refutation if… | Test |
|------|-----------|-----------------|------|
| I-1  | Same `(seed, config)` produces identical chunks bit-for-bit | Two runs on the same git commit produce different `state_fingerprint` values | `runtime/scripts/p0_smoke.py` + `genesis_streaming::tests::determinism::same_seed_same_chunk_single_thread` and `_across_threads` |
| I-2  | NaN payloads in float-hashed `ContentAddressable` outputs hash identically across platforms | Linux vs Windows produce different `content_hash` for the same chunk | `genesis_worldgraph::pass::hash_helper_tests::all_f32_nan_payloads_hash_identically` |
| I-3  | Concurrent `get_or_generate` for the same coord results in exactly one generation call | `mgr.generate_call_count()` > 1 after N parallel `get_or_generate(coord)` | `genesis_streaming::manager::tests::concurrent_get_or_generate_coalesces_to_one_generation` |
| I-4  | Mutated chunks (`mutation_version > 0`) survive eviction pressure until snapshot | Snapshot bytes lose mutations when cache_capacity is small | `genesis_agent_api::tests::mutated_chunks_survive_eviction_pressure` |

Failure of any I-* item is a **stop the world** event for the falsifiability
ledger: every claim that relied on the substrate gets a `pending re-verification`
note added until I-* passes again.

**CI enforcement status (2026-05-28).** Not all four invariants are equally
guarded yet. Only **I-2** runs in a blocking CI job (`cargo test -p genesis-core
-p genesis-biome -p genesis-worldgraph`): a failure there fails the build.
**I-1, I-3 and I-4** live in the `streaming` / `agent-api` crates, exercised by the
`cargo test (extended workspace)` job, which is presently marked
`continue-on-error: true` in [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
— a failure there is reported but does **not** fail the build. Until that flag is
removed (after a green local `cargo test` on the streaming + agent-api crates),
treat **I-1/I-3/I-4 as advisory, not CI-guaranteed**, and do not cite them in
public claims as enforced by CI. This is itself a falsifiability obligation: the
fix is to make the extended-workspace job blocking, not to soften the wording
permanently.

---

## Process notes

- **No retro-fitted claims.** A claim cannot be added here unless a
  preregistration *predating* the supporting run is committed in the same
  history. The git commit graph is the audit trail.
- **No floor thresholds.** Refutation conditions must be specific numbers
  with directions. "The claim is refuted if cooperation decreases" is not
  acceptable — "if `summary.cooperation_index < 0.4` over 1000 ticks at
  the same seed" is.
- **The fingerprint is the handle.** Two readers must be able to rerun the
  anchor and produce the same `state_fingerprint`. If a run cannot be
  reproduced (e.g. depended on a stale Earth tile that's now offline), its
  claim should be marked `superseded` or `refuted-by-unreproducibility`,
  not silently kept.
- **Cite this file from public claims.** Any README/preprint statement of
  the form "Genesis Engine produces X" must cite an entry in **Confirmed
  claims** by ID. If no entry exists, the statement is a hypothesis at
  best — phrase it as one.

---

**See also:**
- [`runtime/experiments/PREREGISTRATION_TEMPLATE.md`](runtime/experiments/PREREGISTRATION_TEMPLATE.md) — template for new runs
- [`runtime/engine/experiment_manifest.py`](runtime/engine/experiment_manifest.py) — provenance + fingerprint capture
- [`docs/RUNTIME-LAYOUT.md`](docs/RUNTIME-LAYOUT.md) — canonical source-tree decisions
- [`ETHICS.md`](ETHICS.md) — broader research-ethics framework
