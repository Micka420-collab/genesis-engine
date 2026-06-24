"""Invariants — the chunk biome map responds to the LIVE macro elevation
(orographic coupling, climate_biome, 2026-06-24).

Context (AUDIT-DELTA-2026-06-23, risk **D11 / R0**): the substrate is frozen
on the agent-visible *chunk* path. The macro ``elevation_m`` field IS mutated
live — by ``plate_tectonics_live`` and ``novel_operators`` — but inside the
``autonomous_world`` loop that is **disjoint** from the chunk path the agents
read. The ``climate_biome`` ``macro`` anomaly source was a literal ``return
0.0`` placeholder, so tectonics/erosion never reached the biomes a chunk sees.

This wire closes the chunk-path half of D11. ``climate_biome`` now adds a
per-chunk *orographic* term: it re-reads the live macro elevation at each
chunk centre and converts the drift from the install-time baseline into a
temperature anomaly at the environmental lapse rate (``earth_laws.
LAPSE_K_PER_M`` = 6.5 K/km — the same value world_genesis bakes into the
baseline temperature, so the coupling is self-consistent). Uplift cools and
migrates biomes down the cooling ladder ; erosion/subsidence warms and
migrates them up.

What this file proves:
1. Static world (elevation unchanged) -> orographic term is identically 0 :
   exact back-compat, the old behaviour is preserved.
2. Uplift cools : a uniform +Δ elevation yields ``-LAPSE_K_PER_M·Δ`` (sign +
   magnitude exact).
3. Erosion warms : a uniform -Δ elevation yields ``+LAPSE_K_PER_M·Δ``.
4. The biome shift follows the COOLING ladder under uplift and the WARMING
   ladder under erosion (the anomaly really drives the existing migration).
5. ``anomaly_source='macro'`` is no longer a dead placeholder : 0 transitions
   on a static world, but real migration once the elevation moves.
6. The term composes additively with the ``linear_warming`` global trend.
7. ``orographic_coupling=False`` opts out (term forced to 0).
8. Read-only contract preserved : the macro arrays are never written.
9. Determinism : same seed + same elevation delta -> identical biome maps.

No new RNG (pure derivation). No new cross-language tell (PY_TO_RUST unchanged
— this is substrate physics, not an agent capability).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

import numpy as np                                                  # noqa: E402

from engine.sim import Simulation, SimConfig                       # noqa: E402
from engine.world import Biome                                     # noqa: E402
from engine.world_genesis import (GenesisParams, generate_world,   # noqa: E402
                                   make_anchor)
from engine.earth_laws import LAPSE_K_PER_M                        # noqa: E402
from engine.climate_biome import (                                 # noqa: E402
    install_climate_biome, apply_climate_biome_step,
    climate_biome_state, _orographic_anomaly_for_chunk,
)


# --------------------------------------------------------------------------
# Harness
# --------------------------------------------------------------------------

def _make_world(seed: int = 0xCAFE_1234):
    gp = GenesisParams(seed=seed & 0xFFFFFFFFFFFFFFFF, resolution=32,
                       n_plates=8, erosion_iters=6, rain_iters=3)
    return generate_world(gp)


def _high_land_cell(world):
    """Macro cell of the highest land point — keeps cached chunks safely
    above sea level so a ±1 km test perturbation never crosses the coast."""
    elev = world.elevation_m
    score = np.where(elev > 0.0, elev, -1e9)
    iy, ix = np.unravel_index(int(np.argmax(score)), score.shape)
    return int(ix), int(iy)


def _anchor_at(world, ix, iy):
    cell_km = world.params.map_size_km / world.params.resolution
    return make_anchor(world, sim_origin_macro_km=((ix + 0.5) * cell_km,
                                                    (iy + 0.5) * cell_km))


def _build(world, *, sim_seed: int = 0xC0FFEE_F00D,
           source: str = "macro", transition_speed: float = 1.0,
           orographic: bool = True):
    ix, iy = _high_land_cell(world)
    anchor = _anchor_at(world, ix, iy)
    cfg = SimConfig(name="oro_test", seed=sim_seed & 0xFFFFFFFFFFFFFFFF,
                    founders=2, max_agents=4, bounds_km=(0.5, 0.5),
                    spawn_radius_m=50.0, drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    sim.streamer.set_genesis(anchor)
    sim.streamer.clear_cache()
    sim.bootstrap()
    state = install_climate_biome(sim, anchor, anomaly_source=source,
                                  transition_speed=transition_speed,
                                  orographic_coupling=orographic)
    assert len(sim.streamer.cache) > 0, "bootstrap cached no chunks"
    return sim, anchor, state


def _snapshot_biomes(sim):
    return {coord: chunk.biome.copy()
            for coord, chunk in sim.streamer.cache.items()}


# --------------------------------------------------------------------------
# 1. Static world : term is identically 0 (back-compat)
# --------------------------------------------------------------------------

def test_static_world_orographic_is_zero():
    world = _make_world()
    sim, anchor, state = _build(world, source="macro")
    res = apply_climate_biome_step(sim)
    assert res["orographic_anomaly_c"] == 0.0
    assert state.orographic_anomaly_c == 0.0
    # macro source => global trend 0 ; with no elevation change the per-chunk
    # anomaly is exactly 0 everywhere -> nothing shifts.
    assert all(abs(v) < 1e-9 for v in state.current_anomaly_c.values())
    assert state.transitions_total == 0


def test_static_world_macro_source_no_transitions():
    """`macro` source on a frozen world keeps the old `return 0.0` behaviour."""
    world = _make_world()
    sim, _, state = _build(world, source="macro", transition_speed=1.0)
    for _ in range(5):
        apply_climate_biome_step(sim)
    assert state.transitions_total == 0


# --------------------------------------------------------------------------
# 2 & 3. Sign + magnitude exactly track the lapse rate
# --------------------------------------------------------------------------

def test_uplift_cools_at_lapse_rate():
    world = _make_world()
    sim, anchor, state = _build(world, source="macro")
    anchor.world.elevation_m += np.float32(1000.0)   # uniform +1 km uplift
    res = apply_climate_biome_step(sim)
    # -6.5 K/km : negative (cooling), magnitude == LAPSE_K_PER_M * 1000.
    assert res["orographic_anomaly_c"] < 0.0
    assert abs(res["orographic_anomaly_c"] - (-LAPSE_K_PER_M * 1000.0)) < 1e-3


def test_erosion_warms_at_lapse_rate():
    world = _make_world()
    sim, anchor, state = _build(world, source="macro")
    anchor.world.elevation_m -= np.float32(1000.0)   # uniform -1 km erosion
    res = apply_climate_biome_step(sim)
    assert res["orographic_anomaly_c"] > 0.0
    assert abs(res["orographic_anomaly_c"] - (LAPSE_K_PER_M * 1000.0)) < 1e-3


def test_orographic_helper_exact_magnitude():
    world = _make_world()
    sim, anchor, state = _build(world, source="macro")
    coord = next(iter(sim.streamer.cache))
    base = state.baseline_elev_m[coord]
    assert base > 0.0  # high-land anchor keeps the baseline above sea level
    anchor.world.elevation_m += np.float32(500.0)
    oro = _orographic_anomaly_for_chunk(state, coord)
    assert abs(oro - (-LAPSE_K_PER_M * 500.0)) < 1e-4


def test_submerged_excursion_carries_no_lapse_anomaly():
    """Below sea level the lapse term is clamped to 0 (consistent with the
    macro baseline temp, which uses max(elev, 0))."""
    world = _make_world()
    sim, anchor, state = _build(world, source="macro")
    coord = next(iter(sim.streamer.cache))
    base = state.baseline_elev_m[coord]
    # Drop the whole world far below sea level : both baseline and current
    # clamp to 0 -> no anomaly.
    anchor.world.elevation_m[:] = -5000.0
    oro = _orographic_anomaly_for_chunk(state, coord)
    expected = -LAPSE_K_PER_M * (max(-5000.0, 0.0) - max(base, 0.0))
    assert abs(oro - expected) < 1e-4
    assert oro >= 0.0  # losing positive elevation can only warm


# --------------------------------------------------------------------------
# 4. The anomaly drives the existing biome migration ladders
# --------------------------------------------------------------------------

def test_uplift_drives_cooling_ladder():
    world = _make_world()
    sim, anchor, state = _build(world, source="macro", transition_speed=1.0)
    coord = next(iter(sim.streamer.cache))
    chunk = sim.streamer.cache[coord]
    chunk.biome = np.full_like(chunk.biome, int(Biome.TEMPERATE_FOREST))
    state.chunk_precip_proxy[coord] = 800.0
    anchor.world.elevation_m += np.float32(1000.0)   # strong uplift -> cooling
    apply_climate_biome_step(sim)
    # _COOLING[TEMPERATE_FOREST] == BOREAL_FOREST.
    assert (sim.streamer.cache[coord].biome == int(Biome.BOREAL_FOREST)).all()


def test_erosion_drives_warming_ladder():
    world = _make_world()
    sim, anchor, state = _build(world, source="macro", transition_speed=1.0)
    coord = next(iter(sim.streamer.cache))
    chunk = sim.streamer.cache[coord]
    chunk.biome = np.full_like(chunk.biome, int(Biome.BOREAL_FOREST))
    state.chunk_precip_proxy[coord] = 800.0
    anchor.world.elevation_m -= np.float32(1000.0)   # strong erosion -> warming
    apply_climate_biome_step(sim)
    # _WARMING_TO_DRY[BOREAL_FOREST] == TEMPERATE_FOREST.
    assert (sim.streamer.cache[coord].biome == int(Biome.TEMPERATE_FOREST)).all()


def test_macro_source_migrates_once_elevation_moves():
    world = _make_world()
    sim, anchor, state = _build(world, source="macro", transition_speed=1.0)
    # Force a shiftable, non-terminal biome everywhere so a shift is visible.
    for coord, chunk in sim.streamer.cache.items():
        chunk.biome = np.full_like(chunk.biome, int(Biome.TEMPERATE_FOREST))
        state.chunk_precip_proxy[coord] = 800.0
    anchor.world.elevation_m += np.float32(1000.0)
    res = apply_climate_biome_step(sim)
    assert res["cells_shifted_this_step"] > 0
    assert state.transitions_total > 0


# --------------------------------------------------------------------------
# 5. Composition with the global trend
# --------------------------------------------------------------------------

def test_orographic_composes_with_linear_warming():
    world = _make_world()
    sim, anchor, state = _build(world, source="linear_warming",
                                transition_speed=0.0)  # freeze biome shifts
    # Run a few ticks so the linear trend is non-zero, then uplift.
    for _ in range(3):
        sim.step()
    anchor.world.elevation_m += np.float32(1000.0)
    apply_climate_biome_step(sim)
    coord = next(iter(sim.streamer.cache))
    expected = state.global_anomaly_c + (-LAPSE_K_PER_M * 1000.0)
    assert abs(state.current_anomaly_c[coord] - expected) < 1e-3


# --------------------------------------------------------------------------
# 6. Opt-out
# --------------------------------------------------------------------------

def test_opt_out_disables_orographic():
    world = _make_world()
    sim, anchor, state = _build(world, source="macro", orographic=False)
    anchor.world.elevation_m += np.float32(1000.0)
    res = apply_climate_biome_step(sim)
    assert res["orographic_anomaly_c"] == 0.0
    assert all(abs(v) < 1e-9 for v in state.current_anomaly_c.values())
    assert state.transitions_total == 0


# --------------------------------------------------------------------------
# 7. Read-only contract
# --------------------------------------------------------------------------

def test_macro_arrays_read_only():
    world = _make_world()
    sim, anchor, state = _build(world, source="macro")
    temp0 = anchor.world.temp_c.copy()
    precip0 = anchor.world.precip_mm.copy()
    elev0 = anchor.world.elevation_m.copy()
    anchor.world.elevation_m += np.float32(1000.0)
    apply_climate_biome_step(sim)
    # The module reads elevation but never writes any macro array. temp/precip
    # untouched ; elevation equals exactly our own perturbation (no module write).
    assert np.array_equal(anchor.world.temp_c, temp0)
    assert np.array_equal(anchor.world.precip_mm, precip0)
    assert np.array_equal(anchor.world.elevation_m, elev0 + np.float32(1000.0))


# --------------------------------------------------------------------------
# 8. Determinism
# --------------------------------------------------------------------------

def test_determinism_same_seed_same_uplift():
    snaps = []
    counts = []
    for _ in range(2):
        world = _make_world(seed=0xABCD_0001)          # identical worlds
        sim, anchor, state = _build(world, sim_seed=0x1357_9BDF,
                                    source="macro", transition_speed=0.4)
        for coord, chunk in sim.streamer.cache.items():
            chunk.biome = np.full_like(chunk.biome, int(Biome.TEMPERATE_FOREST))
            state.chunk_precip_proxy[coord] = 800.0
        anchor.world.elevation_m += np.float32(1000.0)
        res = apply_climate_biome_step(sim)
        counts.append(res["cells_shifted_this_step"])
        snaps.append(_snapshot_biomes(sim))
    assert counts[0] == counts[1]
    assert counts[0] > 0  # the perturbation actually moved cells
    assert snaps[0].keys() == snaps[1].keys()
    for coord in snaps[0]:
        assert np.array_equal(snaps[0][coord], snaps[1][coord])


# --------------------------------------------------------------------------
# 9. Diagnostic reporter exposes the new fields
# --------------------------------------------------------------------------

def test_state_reporter_exposes_orographic_fields():
    world = _make_world()
    sim, anchor, state = _build(world, source="macro", orographic=True)
    rep = climate_biome_state(sim)
    assert rep["installed"] is True
    assert rep["orographic_coupling"] is True
    assert "orographic_anomaly_c" in rep

    world2 = _make_world(seed=0xBEEF_0007)
    sim2, _, _ = _build(world2, source="macro", orographic=False)
    rep2 = climate_biome_state(sim2)
    assert rep2["orographic_coupling"] is False
