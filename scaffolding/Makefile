# Genesis Engine — top-level commands
SHELL := /bin/bash
.DEFAULT_GOAL := help

CARGO := cargo
TARGET := target/release

help:
	@echo "Genesis Engine — make targets"
	@echo "  make dev                    # local Petri tier (2 founders)"
	@echo "  make stress                 # stress test (100 founders)"
	@echo "  make experiment-scarcity    # experiment 1: 10 agents, scarce resources"
	@echo "  make experiment-two-cultures# experiment 2: 2 cultural groups"
	@echo "  make experiment-catastrophe # experiment 3: catastrophe at tick T"
	@echo "  make check                  # cargo check workspace"
	@echo "  make test                   # unit + integration tests"
	@echo "  make determinism            # determinism canary (cargo test)"
	@echo "  make bench                  # criterion benchmarks"
	@echo "  make fmt lint               # rustfmt + clippy"

dev:
	$(CARGO) run --release --bin ge-api -- --config config/sim-petri.yaml

stress:
	$(CARGO) run --release --bin ge-api -- --config config/sim-stress.yaml

experiment-scarcity:
	$(CARGO) run --release --bin ge-api -- --config config/exp-scarcity.yaml --scenario scarcity

experiment-two-cultures:
	$(CARGO) run --release --bin ge-api -- --config config/exp-two-cultures.yaml --scenario two_cultures

experiment-catastrophe:
	$(CARGO) run --release --bin ge-api -- --config config/exp-catastrophe.yaml --scenario catastrophe

check:
	$(CARGO) check --workspace

test:
	$(CARGO) test --workspace --all-features

determinism:
	$(CARGO) test --release -p ge-api determinism_

replay:
	@echo "Replay binary not yet implemented; for now re-run with the same seed/config."

sbom:
	syft . -o spdx-json=sbom.spdx.json -o cyclonedx-json=sbom.cdx.json

sign:
	cosign sign --yes ghcr.io/genesis-engine/ge-sim-node:$(VERSION)

bench:
	$(CARGO) bench --workspace

fmt:
	$(CARGO) fmt --all

lint:
	$(CARGO) clippy --workspace --all-targets --all-features -- -D warnings

docs:
	mkdocs serve

.PHONY: help dev stress check test determinism replay sbom sign bench fmt lint docs experiment-scarcity experiment-two-cultures experiment-catastrophe
