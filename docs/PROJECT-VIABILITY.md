# Genesis Engine — Viability Contract

**Date:** 2026-05-16

Genesis Engine is viable when a contributor can install it, run a baseline
simulation, verify determinism, and understand which runtime is authoritative.
New features should wait behind this contract when they would add ambiguity.

## Authoritative Entry Points

> Source of truth: [`RUNTIME-LAYOUT.md`](./RUNTIME-LAYOUT.md). Decisions changed
> between 2026-05-16 (initial draft of this doc) and 2026-05-27 (Rust workspace
> migration). The summary below is reconciled to current `Makefile` + CI.

- Python operational runtime: `runtime/engine`
- Python smoke tests: `runtime/scripts/p*_*.py`
- Python unit tests: `runtime/tests`
- Rust workspace (CANONICAL, builds the `genesis_world` wheel): `native/world-engine/`
- Rust workspace (LEGACY, to be absorbed): `scaffolding/crates/` — see RUNTIME-LAYOUT.md §3
- Deprecated, slated for deletion: `runtime/genesis/` (raises `ImportError`), `runtime-phase5/` (excluded from pytest)

## Required Local Checks

```bash
python -m pip install -e ".[dev]"
make doctor
make compile-python
make test-python
```

For Earth-anchored runs:

```bash
python -m pip install -e ".[earth,dev]"
python runtime/scripts/p3_earth_smoke.py
```

For the canonical Rust workspace (`native/world-engine/`):

```bash
cd native/world-engine
cargo check --workspace
cargo test --workspace
```

For the legacy `scaffolding/` workspace (still required for smokes p89-p111
until migration B lands — see [`RUNTIME-LAYOUT.md`](./RUNTIME-LAYOUT.md) §2):

```bash
cd scaffolding
cargo check --workspace
cargo test --workspace --all-features
```

## Priority Gates

1. **Installability before features.** Any module that requires a new Python
   dependency must add it to `pyproject.toml` or an optional extra.
2. **One supported runtime.** Public docs should point to `runtime/engine`.
   `runtime/genesis` stays deprecated until removed.
3. **Evidence before claims.** README claims should link to a smoke test,
   artifact, audit report, or sprint note.
4. **Generated data out of source control.** Journals, exports, local JSONL
   streams, and profile logs should be ignored or regenerated.
5. **Rust must compile continuously.** Both `native/world-engine/` (canonical)
   and `scaffolding/` (legacy) must pass `cargo check`. `scaffolding/` is
   allowed to lag in features behind the canonical workspace, but must not
   regress its current API surface until the smoke suite has been migrated.

## Current Known Risks

- Python dependencies are now declared, but local environments still need
  `python -m pip install -e ".[dev]"` before tests can run.
- Rust validation depends on having Cargo/Rust 1.85+ available.
- Some experiment artifacts are modified in the current worktree; treat them
  as generated outputs unless deliberately refreshing benchmark baselines.
- `runtime-phase5` and `runtime/genesis` should be consolidated or archived to
  reduce contributor confusion.

