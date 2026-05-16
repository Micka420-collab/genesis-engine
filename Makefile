SHELL := /bin/bash
PYTHON ?= python3

.DEFAULT_GOAL := help

help:
	@echo "Genesis Engine — project commands"
	@echo "  make setup          # install Python runtime in editable mode"
	@echo "  make setup-earth    # install runtime + Earth-data dependencies"
	@echo "  make setup-dev      # install runtime + pytest"
	@echo "  make doctor         # check local tooling and dependency imports"
	@echo "  make compile-python # syntax-check Python sources"
	@echo "  make test-python    # run Python unit tests"
	@echo "  make smoke          # run baseline p0 smoke"
	@echo "  make rust-check     # cargo check Rust workspace"
	@echo "  make rust-test      # cargo test Rust workspace"
	@echo "  make test           # compile + Python tests + Rust check if cargo exists"

setup:
	$(PYTHON) -m pip install -e .

setup-earth:
	$(PYTHON) -m pip install -e ".[earth]"

setup-dev:
	$(PYTHON) -m pip install -e ".[dev]"

doctor:
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/doctor.py

compile-python:
	$(PYTHON) -m compileall -q runtime/engine runtime/scripts runtime/tests runtime-phase5/engine runtime-phase5/tests

test-python:
	PYTHONPATH=runtime $(PYTHON) -m pytest runtime/tests

smoke:
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p0_smoke.py

rust-check:
	cd scaffolding && cargo check --workspace

rust-test:
	cd scaffolding && cargo test --workspace --all-features

test: compile-python test-python
	@if command -v cargo >/dev/null 2>&1; then \
		$(MAKE) rust-check; \
	else \
		echo "cargo not found; skipped rust-check"; \
	fi

.PHONY: help setup setup-earth setup-dev doctor compile-python test-python smoke rust-check rust-test test

