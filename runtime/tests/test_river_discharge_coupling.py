"""Invariants — the chunk *river depth* responds to the LIVE macro elevation
(river-discharge coupling, ``engine.river_discharge``, 2026-06-25).

Context (AUDIT-DELTA-2026-06-23, risk **D11 / R0**): the substrate is frozen on
the agent-visible *chunk* path. Two pieces already existed but never met —
``chunk_hydrology`` paints a river stripe with a hard-coded 800 L depth (blind
to real discharge), and ``discharge_observer`` computes the real mass-conserving
discharge field but only *observes* it. This wire closes the **hydrology half**
of D11: it is the exact partner of the orographic *temperature* coupling in
``climate_biome``. Both re-read the live macro ``elevation_m``; that one turns
its drift into a per-chunk temperature anomaly, this one turns the same drift
into a per-chunk *river discharge* response through the temperature/ET channel
(uplift cools → less ET → more runoff → the river swells; erosion warms → less
runoff → the river shrinks, and dries if ET reaches the precipitation ceiling).

What this file proves:
1. Static world (elevation unchanged) -> strict no-op: river water bit-identical,
   nothing scaled. Exact back-compat with the painted river.
2. Uplift swells the river (discharge ratio > 1 at a warm, ET-active basin).
3. Erosion shrinks the river (ratio < 1); strong warming dries it toward 0.
4. Reversible: returning the elevation to baseline restores the painted river
   exactly (the scaling is never compounded).
5. Read-only contract: the macro temp / precip / flow_dir arrays are never
   written; only our own elevation perturbation is visible.
6. The driving macro discharge is mass-conserving (Σ Q[sinks] == Σ runoff).
7. Determinism: same seed + same uplift -> identical chunk river water.
8. ``enabled=False`` opts out (river untouched under uplift).
9. Reporter exposes the diagnostic fields; uninstall restores ``sim.step``.

No new RNG (pure derivation), no new cross-language tell (PY_TO_RUST unchanged —
substrate physics, not an agent capability), no mutation of the macro world.
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
from engine.world_genesis import (GenesisParams, generate_world,   # noqa: E402
                                   make_anchor)
from engine.chunk_hydrology import (                               # noqa: E402
    install_chunk_hydrology, apply_to_existing_chunks, RIVER_WATER_LITRES)
from engine.discharge_observer import (                            # noqa: E402
    DischargeConfig, route_runoff, runoff_field_m3s)
from engine.earth_laws import LAPSE_K_PER_M                        # noqa: E402
from engine.river_discharge import (                               # noqa: E402
    install_river_discharge, apply_river_discharge_step,
    river_discharge_state, uninstall_river_discharge, _discharge_field)


# --------------------------------------------------------------------------
# Harness — a WARM (tropical) world so basins are ET-active and rivers respond
# to the temperature channel. lat_span_deg=30 => map within +/-15 deg.
# --------------------------------------------------------------------------

def _make_world(seed: int = 0xC0FFEE_1234):
    gp = GenesisParams(seed=seed & 0xFFFFFFFFFFFFFFFF, resolution=64,
                       n_plates=10, erosion_iters=20, rain_iters=5,
                       river_threshold_cells=30.0, lat_span_deg=30.0)
    return generate_world(gp)


def _responsive_river_cell(world):
    """Macro cell of the river whose discharge moves most under a +1 km uplift.

    Deterministic: argmax |Q(uplift) - Q(base)| over flowing land river cells.
    Picks a warm, ET-active basin so the coupling is exercised, not a cold
    (T<=0, ET already 0) headwater where the temperature channel is inert.
    """
    P = np.asarray(world.precip_mm, float)
    T = np.asarray(world.temp_c, float)
    E = np.asarray(world.elevation_m, float)
    cfg = DischargeConfig()
    cell_km = world.params.map_size_km / world.params.resolution
    q0 = route_runoff(world.flow_dir, runoff_field_m3s(P, T, cell_km, cfg))
    q1 = route_runoff(world.flow_dir,
                      runoff_field_m3s(P, T - LAPSE_K_PER_M * 1000.0,
                                       cell_km, cfg))
    rm = np.asarray(world.river_mask, bool) & (E > 0.0) & (world.flow_dir != 255)
    score = np.where(rm, np.abs(q1 - q0), -1.0)
    iy, ix = np.unravel_index(int(np.argmax(score)), score.shape)
    return int(ix), int(iy)


def _anchor_at(world, ix, iy):
    cell_km = world.params.map_size_km / world.params.resolution
    return make_anchor(world, sim_origin_macro_km=((ix + 0.5) * cell_km,
                                                   (iy + 0.5) * cell_km))


def _build(world, *, sim_seed: int = 0xABCD_1234, enabled: bool = True):
    """Anchor a sim at the most discharge-responsive river cell, paint the
    macro river into its chunks, then install the discharge coupling."""
    ix, iy = _responsive_river_cell(world)
    anchor = _anchor_at(world, ix, iy)
    cfg = SimConfig(name="river_disc_test", seed=sim_seed & 0xFFFFFFFFFFFFFFFF,
                    founders=2, max_agents=4, bounds_km=(0.5, 0.5),
                    spawn_radius_m=50.0, drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    sim.streamer.set_genesis(anchor)
    sim.streamer.clear_cache()
    sim.bootstrap()
    install_chunk_hydrology(sim, anchor)          # idempotent
    apply_to_existing_chunks(sim)                  # paint cached chunks
    state = install_river_discharge(sim, anchor, enabled=enabled)
    return sim, anchor, state


def _river_chunk(sim):
    """Return (coord, chunk, mask) of a cached chunk carrying a painted river."""
    for coord, chunk in sim.streamer.cache.items():
        mask = np.asarray(chunk.water) >= np.float32(RIVER_WATER_LITRES)
        if bool(mask.any()):
            return coord, chunk, mask.copy()
    raise AssertionError("no painted river chunk in cache")


def _river_water_sum(chunk, mask):
    return float(np.asarray(chunk.water)[mask].sum())


# --------------------------------------------------------------------------
# 1. Static world : strict no-op (back-compat with the painted river)
# --------------------------------------------------------------------------

def test_static_world_is_strict_noop():
    world = _make_world()
    sim, anchor, state = _build(world)
    coord, chunk, mask = _river_chunk(sim)
    before = np.asarray(chunk.water).copy()
    res = apply_river_discharge_step(sim)
    assert res["changed"] == 0.0
    assert res["chunks_scaled"] == 0.0
    assert state.last_changed is False
    assert len(state.scaled_coords) == 0
    # Not a single water cell moved.
    assert np.array_equal(np.asarray(chunk.water), before)


# --------------------------------------------------------------------------
# 2 & 3. Uplift swells, erosion shrinks
# --------------------------------------------------------------------------

def test_uplift_swells_the_river():
    world = _make_world()
    sim, anchor, state = _build(world)
    coord, chunk, mask = _river_chunk(sim)
    base = _river_water_sum(chunk, mask)
    anchor.world.elevation_m = (anchor.world.elevation_m
                                + np.float32(1000.0)).astype(np.float32)
    res = apply_river_discharge_step(sim)
    assert res["changed"] == 1.0
    assert res["max_ratio"] > 1.0
    assert _river_water_sum(chunk, mask) > base


def test_erosion_shrinks_the_river():
    world = _make_world()
    sim, anchor, state = _build(world)
    coord, chunk, mask = _river_chunk(sim)
    base = _river_water_sum(chunk, mask)
    anchor.world.elevation_m = (anchor.world.elevation_m
                                - np.float32(1500.0)).astype(np.float32)
    res = apply_river_discharge_step(sim)
    assert res["changed"] == 1.0
    assert res["min_ratio"] < 1.0
    assert _river_water_sum(chunk, mask) < base


def test_strong_warming_dries_the_river_toward_zero():
    """Enough erosion warms ET up to the precipitation ceiling -> runoff
    collapses -> the channel runs nearly dry (emergent wadi)."""
    world = _make_world()
    sim, anchor, state = _build(world)
    coord, chunk, mask = _river_chunk(sim)
    base = _river_water_sum(chunk, mask)
    anchor.world.elevation_m = (anchor.world.elevation_m
                                - np.float32(4000.0)).astype(np.float32)
    apply_river_discharge_step(sim)
    # Discharge falls hard; the painted river loses most of its water.
    assert _river_water_sum(chunk, mask) < base * 0.5


# --------------------------------------------------------------------------
# 4. Reversibility — return to baseline restores the painted river exactly
# --------------------------------------------------------------------------

def test_reverts_to_baseline_when_elevation_returns():
    world = _make_world()
    sim, anchor, state = _build(world)
    coord, chunk, mask = _river_chunk(sim)
    base_water = np.asarray(chunk.water).copy()
    base_elev = anchor.world.elevation_m.copy()
    # Uplift, then put the elevation back to the exact baseline array.
    anchor.world.elevation_m = (anchor.world.elevation_m
                                + np.float32(1000.0)).astype(np.float32)
    apply_river_discharge_step(sim)
    assert not np.array_equal(np.asarray(chunk.water), base_water)  # moved
    anchor.world.elevation_m = base_elev
    res = apply_river_discharge_step(sim)
    assert res["changed"] == 0.0
    # The restore path put the river back to its painted baseline, bit-exact.
    assert np.array_equal(np.asarray(chunk.water), base_water)
    assert len(state.scaled_coords) == 0


# --------------------------------------------------------------------------
# 5. Read-only macro contract
# --------------------------------------------------------------------------

def test_macro_arrays_read_only():
    world = _make_world()
    sim, anchor, state = _build(world)
    temp0 = anchor.world.temp_c.copy()
    precip0 = anchor.world.precip_mm.copy()
    flowdir0 = anchor.world.flow_dir.copy()
    elev0 = anchor.world.elevation_m.copy()
    anchor.world.elevation_m = (anchor.world.elevation_m
                                + np.float32(1000.0)).astype(np.float32)
    apply_river_discharge_step(sim)
    assert np.array_equal(anchor.world.temp_c, temp0)
    assert np.array_equal(anchor.world.precip_mm, precip0)
    assert np.array_equal(anchor.world.flow_dir, flowdir0)
    assert np.array_equal(anchor.world.elevation_m,
                          elev0 + np.float32(1000.0))


# --------------------------------------------------------------------------
# 6. The driving discharge is mass-conserving
# --------------------------------------------------------------------------

def test_driving_discharge_is_mass_conserving():
    """Σ discharge[sinks] == Σ runoff for the field that drives the scaling —
    the coupling rides a genuinely mass-conserving routing (route_runoff SSOT),
    not an ad-hoc painted depth."""
    world = _make_world()
    sim, anchor, state = _build(world)
    elev = np.asarray(anchor.world.elevation_m, dtype=np.float64)
    # Reconstruct the runoff that _discharge_field routes, then check the
    # routing's mass balance.
    d_elev = np.maximum(elev, 0.0) - np.maximum(state.base_elev_m, 0.0)
    temp_eff = state.base_temp_c - LAPSE_K_PER_M * d_elev
    runoff = runoff_field_m3s(state.base_precip_mm, temp_eff,
                              state.cell_km, state.runoff_cfg)
    discharge = _discharge_field(state, elev)
    fd = np.asarray(anchor.world.flow_dir, dtype=np.uint8)
    is_sink = (fd == 255) | (fd > 7)
    total_runoff = float(runoff.sum())
    total_outflow = float(discharge[is_sink].sum())
    resid = abs(total_runoff - total_outflow) / max(total_runoff, 1e-9)
    assert resid < 1e-6


# --------------------------------------------------------------------------
# 7. Determinism
# --------------------------------------------------------------------------

def test_determinism_same_seed_same_uplift():
    sums = []
    waters = []
    for _ in range(2):
        world = _make_world(seed=0x5EED_0001)
        sim, anchor, state = _build(world, sim_seed=0x1357_9BDF)
        coord, chunk, mask = _river_chunk(sim)
        anchor.world.elevation_m = (anchor.world.elevation_m
                                    + np.float32(1000.0)).astype(np.float32)
        apply_river_discharge_step(sim)
        sums.append(_river_water_sum(chunk, mask))
        waters.append(np.asarray(chunk.water)[mask].copy())
    assert sums[0] == sums[1]
    assert np.array_equal(waters[0], waters[1])


# --------------------------------------------------------------------------
# 8. Opt-out
# --------------------------------------------------------------------------

def test_opt_out_disables_coupling():
    world = _make_world()
    sim, anchor, state = _build(world, enabled=False)
    coord, chunk, mask = _river_chunk(sim)
    before = np.asarray(chunk.water).copy()
    anchor.world.elevation_m = (anchor.world.elevation_m
                                + np.float32(1000.0)).astype(np.float32)
    res = apply_river_discharge_step(sim)
    assert res["chunks_scaled"] == 0.0
    assert np.array_equal(np.asarray(chunk.water), before)


# --------------------------------------------------------------------------
# 9. Reporter + uninstall
# --------------------------------------------------------------------------

def test_reporter_exposes_fields_and_uninstall_restores_step():
    world = _make_world()
    sim, anchor, state = _build(world)
    rep = river_discharge_state(sim)
    assert rep["installed"] is True
    assert rep["enabled"] is True
    assert "river_chunks_tracked" in rep
    assert "max_ratio_seen" in rep

    patched_step = sim.step
    assert uninstall_river_discharge(sim) is True
    assert sim.step is not patched_step
    assert getattr(sim, "_river_discharge_state", None) is None
    assert river_discharge_state(sim) == {"installed": False}


# --------------------------------------------------------------------------
# 10. Bootstrap wiring — optional module, gated on hydrology, off by default
# --------------------------------------------------------------------------

def test_bootstrap_installs_only_when_selected():
    from engine.genesis_bootstrap import (bootstrap_genesis_sim, ALL_MODULES,
                                          MOD_RIVER_DISCHARGE)
    from engine.world_genesis import GenesisParams as _GP

    gp = _GP(seed=0xC0FFEE_1234 & 0xFFFFFFFFFFFFFFFF, resolution=48,
             n_plates=8, erosion_iters=8, rain_iters=3, lat_span_deg=30.0)

    def _sim(name):
        cfg = SimConfig(name=name, seed=0xBEEF & 0xFFFFFFFFFFFFFFFF,
                        founders=2, max_agents=4, bounds_km=(0.5, 0.5),
                        spawn_radius_m=50.0, drive_accel=1500.0, cultures=1)
        return Simulation(cfg)

    s_all = _sim("rd_all")
    st_all = bootstrap_genesis_sim(s_all, genesis_params=gp,
                                   modules=ALL_MODULES)
    assert MOD_RIVER_DISCHARGE in st_all.modules_installed
    assert getattr(s_all, "_river_discharge_state", None) is not None

    s_def = _sim("rd_def")
    st_def = bootstrap_genesis_sim(s_def, genesis_params=gp)
    assert MOD_RIVER_DISCHARGE not in st_def.modules_installed
    assert getattr(s_def, "_river_discharge_state", None) is None
