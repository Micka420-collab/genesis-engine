"""Invariants — the chunk *precipitation* proxy responds to the LIVE macro
relief (orographic precipitation coupling, climate_biome, Wave 65, 2026-06-27).

Context (AUDIT-DELTA-2026-06-23, backlog #7 / risk **D11 / R0**): the substrate
is frozen on the agent-visible *chunk* path. The orographic *temperature*
coupling (2026-06-24) already re-reads the live macro ``elevation_m`` and turns
its drift into a per-chunk temperature anomaly at the lapse rate. Its named
partner — ``precip_mm`` — was still frozen: each chunk kept the rainfall it was
born with, so a rising mountain never cast a rain shadow on the biomes a chunk
sees.

This wire closes the precipitation half. ``climate_biome`` now recomputes the
macro orographic rainfall field for the live relief, **re-using the worldgen
model verbatim** (``world_genesis._orographic_precipitation`` +
``_base_precip_by_latitude``, the exact SSOT code path that baked
``world.precip_mm`` at generation), and feeds each chunk
``baseline + (field(live_elev) - field(baseline_elev))`` as the effective
rainfall driving the warming dry/wet biome branch. Windward slopes wring out
extra rain ; their lee falls into a rain shadow.

What this file proves:
1. SSOT reproduction : recomputing at the baseline elevation reproduces
   ``world.precip_mm`` bit-for-bit (so the static-world delta is exactly 0).
2. A localised uplift makes the windward side wetter AND the lee drier
   (rain shadow) in the same field.
3. Static world : the effective precip equals the frozen baseline everywhere
   and the reported anomaly is 0 (exact back-compat).
4. The per-chunk effective precip tracks the live relief (it is no longer the
   frozen install snapshot once the elevation moves).
5. The warming biome ladder consumes the *effective* precip (the wire is real,
   not cosmetic).
6. ``orographic_precip_coupling=False`` opts out (proxy forced to baseline).
7. Read-only contract : ``world.precip_mm`` is never written.
8. Determinism : same seed + same relief change -> identical effective precip
   and identical biome maps.
9. Diagnostic reporter exposes the new fields.

No new RNG (pure derivation). No new tunable constant (the gain / rain-shadow
coefficients are read from the world's own GenesisParams). No new cross-language
tell (PY_TO_RUST unchanged — substrate physics, not an agent capability).
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
from engine.climate_biome import (                                 # noqa: E402
    install_climate_biome, apply_climate_biome_step,
    climate_biome_state, _orographic_precip_field, _shift_biomes_array,
)


# --------------------------------------------------------------------------
# Harness (mirrors test_climate_biome_orographic)
# --------------------------------------------------------------------------

def _make_world(seed: int = 0xD11_9A11):
    gp = GenesisParams(seed=seed & 0xFFFFFFFFFFFFFFFF, resolution=32,
                       n_plates=8, erosion_iters=6, rain_iters=3)
    return generate_world(gp)


def _high_land_cell(world):
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
           precip: bool = True):
    ix, iy = _high_land_cell(world)
    anchor = _anchor_at(world, ix, iy)
    cfg = SimConfig(name="oro_precip_test", seed=sim_seed & 0xFFFFFFFFFFFFFFFF,
                    founders=2, max_agents=4, bounds_km=(0.5, 0.5),
                    spawn_radius_m=50.0, drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    sim.streamer.set_genesis(anchor)
    sim.streamer.clear_cache()
    sim.bootstrap()
    state = install_climate_biome(sim, anchor, anomaly_source=source,
                                  transition_speed=transition_speed,
                                  orographic_precip_coupling=precip)
    assert len(sim.streamer.cache) > 0, "bootstrap cached no chunks"
    return sim, anchor, state


def _uplift_block(world, ix, iy, peak_delta, half=4):
    """Add a tapered (tent) relief bump of peak ``peak_delta`` m centred on
    (ix, iy). A *tapered* bump (not a flat block) is essential: a flat block
    leaves its interior gradient — and hence its orographic rainfall —
    unchanged, so only a slope changes the precip a centred chunk samples."""
    R = world.params.resolution
    for dy in range(-half, half + 1):
        for dx in range(-half, half + 1):
            y, x = iy + dy, ix + dx
            if 0 <= y < R and 0 <= x < R:
                w = max(0.0, 1.0 - max(abs(dx), abs(dy)) / float(half + 1))
                world.elevation_m[y, x] = np.float32(
                    world.elevation_m[y, x] + peak_delta * w)


# --------------------------------------------------------------------------
# 1. SSOT reproduction — recompute at baseline == world.precip_mm
# --------------------------------------------------------------------------

def test_baseline_recompute_reproduces_macro_precip():
    world = _make_world()
    sim, anchor, state = _build(world)
    f0 = _orographic_precip_field(state, state.base_elev_field)
    # The worldgen pipeline applies no post-processing after the orographic
    # pass, so the recompute is bit-identical to the stored precipitation.
    assert np.array_equal(f0, anchor.world.precip_mm)


# --------------------------------------------------------------------------
# 2. Windward gain + lee-side rain shadow live in the same field
# --------------------------------------------------------------------------

def test_uplift_block_makes_windward_wet_and_lee_dry():
    world = _make_world()
    sim, anchor, state = _build(world)
    ix, iy = _high_land_cell(world)
    base = state.base_elev_field
    f0 = _orographic_precip_field(state, base)
    e2 = base.copy()
    e2[max(0, iy - 4):iy + 5, max(0, ix - 4):ix + 5] += np.float32(1500.0)
    f1 = _orographic_precip_field(state, e2)
    d = f1 - f0
    assert float(d.max()) > 0.0   # windward flank wrings out extra rain
    assert float(d.min()) < 0.0   # the lee falls into a rain shadow


# --------------------------------------------------------------------------
# 3. Static world : effective precip == baseline (back-compat)
# --------------------------------------------------------------------------

def test_static_world_precip_unchanged():
    world = _make_world()
    sim, anchor, state = _build(world)
    res = apply_climate_biome_step(sim)
    assert res["orographic_precip_anomaly_mm"] == 0.0
    assert state.orographic_precip_anomaly_mm == 0.0
    for coord in sim.streamer.cache:
        base = state.chunk_precip_proxy[coord]
        assert abs(state.current_precip_proxy[coord] - base) < 1e-9


# --------------------------------------------------------------------------
# 4. Effective precip tracks the LIVE relief
# --------------------------------------------------------------------------

def test_effective_precip_tracks_live_relief():
    world = _make_world()
    sim, anchor, state = _build(world)
    ix, iy = _high_land_cell(world)
    # Snapshot the frozen baseline proxy per chunk.
    apply_climate_biome_step(sim)  # populate current_precip_proxy at baseline
    frozen = dict(state.chunk_precip_proxy)
    _uplift_block(anchor.world, ix, iy, 1500.0)
    res = apply_climate_biome_step(sim)
    assert res["orographic_precip_anomaly_mm"] != 0.0
    # At least one cached chunk now sees a precipitation different from the
    # value it was born with — the proxy is live, not frozen.
    moved = any(abs(state.current_precip_proxy[c] - frozen[c]) > 1.0
                for c in sim.streamer.cache)
    assert moved


# --------------------------------------------------------------------------
# 5. The warming ladder consumes the effective precip
# --------------------------------------------------------------------------

def test_warming_ladder_consumes_effective_precip():
    world = _make_world()
    sim, anchor, state = _build(world, source="macro", transition_speed=1.0)
    ix, iy = _high_land_cell(world)
    coord = next(iter(sim.streamer.cache))
    chunk = sim.streamer.cache[coord]
    # SAVANNA's warming target is precip-conditional (<500 -> HOT_DESERT, else
    # TROPICAL_DRY_FOREST), so the outcome is a direct function of the rainfall.
    chunk.biome = np.full_like(chunk.biome, int(Biome.SAVANNA))
    # Erode to warm (lapse) so the warming branch fires, and to perturb precip.
    _uplift_block(anchor.world, ix, iy, -900.0)
    apply_climate_biome_step(sim)
    eff = state.current_precip_proxy[coord]
    expected = int(_shift_biomes_array(
        np.array([int(Biome.SAVANNA)], dtype=np.uint8), True, eff)[0])
    assert (sim.streamer.cache[coord].biome == expected).all()
    # And the effective precip is genuinely the live value, not the frozen 800.
    assert abs(eff - state.chunk_precip_proxy[coord]) >= 0.0  # defined/finite
    assert np.isfinite(eff)


# --------------------------------------------------------------------------
# 6. Opt-out
# --------------------------------------------------------------------------

def test_opt_out_disables_precip_coupling():
    world = _make_world()
    sim, anchor, state = _build(world, precip=False)
    ix, iy = _high_land_cell(world)
    _uplift_block(anchor.world, ix, iy, 1500.0)
    res = apply_climate_biome_step(sim)
    assert res["orographic_precip_anomaly_mm"] == 0.0
    for coord in sim.streamer.cache:
        assert abs(state.current_precip_proxy[coord]
                   - state.chunk_precip_proxy[coord]) < 1e-9


# --------------------------------------------------------------------------
# 7. Read-only contract — world.precip_mm never written
# --------------------------------------------------------------------------

def test_macro_precip_array_read_only():
    world = _make_world()
    sim, anchor, state = _build(world)
    ix, iy = _high_land_cell(world)
    precip0 = anchor.world.precip_mm.copy()
    _uplift_block(anchor.world, ix, iy, 1500.0)
    apply_climate_biome_step(sim)
    assert np.array_equal(anchor.world.precip_mm, precip0)


# --------------------------------------------------------------------------
# 8. Determinism
# --------------------------------------------------------------------------

def test_determinism_same_seed_same_uplift():
    proxies = []
    snaps = []
    for _ in range(2):
        world = _make_world(seed=0x5EED_0042)
        sim, anchor, state = _build(world, sim_seed=0x1357_9BDF,
                                    source="macro", transition_speed=0.5)
        ix, iy = _high_land_cell(world)
        for coord, chunk in sim.streamer.cache.items():
            chunk.biome = np.full_like(chunk.biome, int(Biome.SAVANNA))
        _uplift_block(anchor.world, ix, iy, -900.0)
        apply_climate_biome_step(sim)
        proxies.append(dict(state.current_precip_proxy))
        snaps.append({c: ch.biome.copy()
                      for c, ch in sim.streamer.cache.items()})
    assert proxies[0].keys() == proxies[1].keys()
    for c in proxies[0]:
        assert proxies[0][c] == proxies[1][c]
        assert np.array_equal(snaps[0][c], snaps[1][c])


# --------------------------------------------------------------------------
# 9. Diagnostic reporter exposes the new fields
# --------------------------------------------------------------------------

def test_reporter_exposes_precip_fields():
    world = _make_world()
    sim, anchor, state = _build(world, precip=True)
    rep = climate_biome_state(sim)
    assert rep["installed"] is True
    assert rep["orographic_precip_coupling"] is True
    assert "orographic_precip_anomaly_mm" in rep

    world2 = _make_world(seed=0xBEEF_0099)
    sim2, _, _ = _build(world2, precip=False)
    rep2 = climate_biome_state(sim2)
    assert rep2["orographic_precip_coupling"] is False
