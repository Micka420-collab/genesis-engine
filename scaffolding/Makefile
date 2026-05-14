# Genesis Engine — top-level commands
SHELL := /bin/bash
.DEFAULT_GOAL := help

CARGO := cargo
TARGET := target/release

help:
	@echo "Genesis Engine — make targets"
	@echo "  make dev               # local Petri tier, 10 agents"
	@echo "  make test              # unit + integration tests"
	@echo "  make determinism       # determinism canary (10⁴ ticks)"
	@echo "  make replay SNAP=...   # replay a snapshot"
	@echo "  make sbom              # generate SBOM (SPDX + CycloneDX)"
	@echo "  make sign              # cosign sign container images"
	@echo "  make bench             # criterion benchmarks"
	@echo "  make fmt lint          # rustfmt + clippy + biome + ruff"
	@echo "  make docs              # mkdocs serve"

dev:
	$(CARGO) run --release --bin ge-sim -- --config scaffolding/config/sim-petri.yaml

test:
	$(CARGO) test --workspace --all-features

determinism:
	./scripts/determinism-canary.sh

replay:
	$(CARGO) run --release --bin ge-sim -- replay --snapshot $(SNAP)

sbom:
	syft . -o spdx-json=sbom.spdx.json -o cyclonedx-json=sbom.cdx.json

sign:
	cosign sign --yes ghcr.io/genesis-engine/ge-sim-node:$(VERSION)

bench:
	$(CARGO) bench --workspace

fmt:
	$(CARGO) fmt --all
	cd front && pnpm biome format --write .
	ruff format ./services-py

lint:
	$(CARGO) clippy --workspace --all-targets --all-features -- -D warnings
	cd front && pnpm biome lint .
	ruff check ./services-py

docs:
	mkdocs serve

.PHONY: help dev test determinism replay sbom sign bench fmt lint docs
