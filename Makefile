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
	@echo "  make civilization   # Genesis bootstrap + agents + FAIR exports"
	@echo "  make terre          # preset terre (400 ticks, live observe JSONL)"
	@echo "  make terre-long     # preset terre 2000 ticks + enriched artifact"
	@echo "  make validate-fair  # Köppen FAIR + checksums (p80)"
	@echo "  make observe        # SSE observation server + dashboard URL"
	@echo "  make earth-console  # live Terre UI (Genesis macro + god view)"
	@echo "  make validate-all   # pytest + smokes p72–p87"
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
	cd native/world-engine && cargo test -p genesis-core -p genesis-biome -p genesis-worldgraph --no-run

rust-test:
	cd native/world-engine && cargo test -p genesis-core -p genesis-biome -p genesis-worldgraph

rust-check-scaffolding:
	cd scaffolding && cargo check --workspace

rust-test-scaffolding:
	cd scaffolding && cargo test --workspace --all-features

test: compile-python test-python
	@if command -v cargo >/dev/null 2>&1; then \
		$(MAKE) rust-check; \
	else \
		echo "cargo not found; skipped rust-check"; \
	fi

smoke-realism:
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p72_world_atmosphere_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p73_rust_worldgraph_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p75_koeppen_grid_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p80_koeppen_genesis_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p84_earth_console_lite_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p87_observer_sky_smoke.py

civilization:
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/civilization_pipeline.py --seed 0xC1A71CE0 --ticks 100

terre:
	PYTHONPATH=runtime $(PYTHON) runtime/run.py terre --ticks 400

terre-long:
	PYTHONPATH=runtime $(PYTHON) runtime/run.py terre --ticks 2000

validate-fair:
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p80_koeppen_genesis_smoke.py

earth-console:
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/run_earth_console.py

observe:
	@echo "Dashboard (open in browser):"
	@echo "  file://$$(pwd)/runtime/dashboard.html"
	@echo "SSE stream (set URL in dashboard):"
	@echo "  http://127.0.0.1:8765/events"
	@echo "Run civilization first to refresh observable.json, or use an experiment artifact."
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/observation_server.py \
		--observable runtime/artifacts/observable.json \
		--artifacts runtime/artifacts/civilization_run_manifest.json \
		--port 8765

validate-all: test-python
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p72_world_atmosphere_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p73_rust_worldgraph_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p73_agent_observation_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p74_koeppen_harness_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p75_koeppen_grid_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p76_multi_rate_coupler_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p77_epidemic_contact_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p78_pbr_render_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p79_vision_observation_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p80_koeppen_genesis_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p81_hydrology_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p82_civilization_pipeline_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p82_observation_sse_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p83_terre_report_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p84_earth_console_lite_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p85_algorithm_evolution_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p86_autonomous_world_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p87_observer_sky_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p119_frost_weathering_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p122_discharge_routing_smoke.py

maturin-dev:
	cd native/world-engine && maturin develop -m crates/pybindings/Cargo.toml --release

.PHONY: help setup setup-earth setup-dev doctor compile-python test-python smoke smoke-realism civilization terre terre-long validate-fair earth-console observe validate-all maturin-dev rust-check rust-test rust-check-scaffolding rust-test-scaffolding test

