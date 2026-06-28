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
	@echo "  make lint           # ruff-check the capability arc (modules + tests + smokes)"
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

# Ruff-check ONLY the emergent-capability arc (C1→C20) + its tests/smokes — the
# ruff-clean set the per-sprint commits claim. The legacy engine tree carries
# accumulated style debt (mostly intentional E402/F401 across 178 modules +
# smokes); a full-tree cleanup is deferred (AUDIT-DELTA-2026-06-23 R-J13-3). New
# capabilities must keep this set clean and add themselves here.
lint:
	$(PYTHON) -m ruff check \
	  runtime/engine/surface_mineralization.py runtime/engine/lithic_outcrop.py \
	  runtime/engine/water_potability.py runtime/engine/combustible_outcrop.py \
	  runtime/engine/clay_outcrop.py runtime/engine/limestone_outcrop.py \
	  runtime/engine/fire_ignition.py runtime/engine/lithic_tempering.py \
	  runtime/engine/ceramic_firing.py runtime/engine/lime_burning.py \
	  runtime/engine/kiln_draft.py runtime/engine/forced_draught.py \
	  runtime/engine/copper_smelting.py runtime/engine/cryoclasty.py \
	  runtime/engine/salt_evaporation.py runtime/engine/food_curing.py \
	  runtime/engine/iron_bloomery.py runtime/engine/ochre_grinding.py \
	  runtime/engine/bloom_forging.py runtime/engine/rock_canvas.py \
	  runtime/engine/climate_biome.py \
	  runtime/engine/river_discharge.py \
	  runtime/tests/test_geology_cross_language_contract.py \
	  runtime/tests/test_drink_potability.py \
	  runtime/tests/test_lithic_knapping_loop.py \
	  runtime/tests/test_frost_clast_gather_loop.py \
	  runtime/tests/test_ochre_grinding_loop.py \
	  runtime/tests/test_climate_biome_orographic.py \
	  runtime/tests/test_river_discharge_coupling.py \
	  runtime/tests/test_rock_canvas_mark_loop.py \
	  runtime/tests/test_fire_ignition_loop.py \
	  runtime/scripts/p13[3-9]_*_smoke.py runtime/scripts/p14[0-9]_*_smoke.py \
	  runtime/scripts/p15[0-9]_*_smoke.py runtime/scripts/p16[0-9]_*_smoke.py

smoke:
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p0_smoke.py

# --- Genesis Network (module de don de calcul communautaire) --------------
# Module autonome (fastapi/uvicorn/pydantic) ; gardé indépendamment de l'arc.
test-network:
	$(PYTHON) -m pytest network/tests

lint-network:
	$(PYTHON) -m ruff check network/

smoke-network:
	$(PYTHON) network/scripts/network_smoke.py

network: lint-network test-network smoke-network

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
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p123_compaction_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p124_hydrograph_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p125_geotherm_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p126_sediment_exner_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p127_evolutionary_activity_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p128_isostasy_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p129_illumination_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p130_flexure_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p131_hypsometry_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p132_concavity_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p133_surface_mineralization_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p134_lithic_outcrop_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p135_water_potability_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p136_combustible_outcrop_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p137_clay_outcrop_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p138_limestone_outcrop_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p139_fire_ignition_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p140_lithic_tempering_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p141_ceramic_firing_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p142_lime_burning_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p143_kiln_draft_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p144_forced_draught_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p145_copper_smelting_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p146_cryoclasty_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p147_salt_evaporation_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p148_food_curing_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p149_iron_bloomery_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p150_ochre_grinding_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p151_bloom_forging_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p152_rock_canvas_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p153_lithic_knapping_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p154_orographic_climate_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p155_frost_clast_gather_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p156_river_discharge_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p157_llm_observer_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p158_ochre_grinding_loop_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p159_orographic_precip_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p160_rock_canvas_mark_loop_smoke.py
	PYTHONPATH=runtime $(PYTHON) runtime/scripts/p161_fire_ignition_loop_smoke.py

maturin-dev:
	cd native/world-engine && maturin develop -m crates/pybindings/Cargo.toml --release

.PHONY: help setup setup-earth setup-dev doctor compile-python test-python lint smoke smoke-realism civilization terre terre-long validate-fair earth-console observe validate-all maturin-dev rust-check rust-test rust-check-scaffolding rust-test-scaffolding test

