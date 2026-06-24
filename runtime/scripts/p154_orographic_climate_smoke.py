"""P154 — orographic climate coupling smoke (live elevation -> chunk biome).

Closes the chunk-path half of D11 (AUDIT-DELTA-2026-06-23): the macro
``elevation_m`` field is mutated live by ``plate_tectonics_live`` /
``novel_operators`` but inside a loop disjoint from the agent-visible chunk
path. ``climate_biome`` now re-reads that live elevation each tick and turns
its drift into a per-chunk temperature anomaly at the environmental lapse
rate (``earth_laws.LAPSE_K_PER_M`` = 6.5 K/km). Uplift cools, erosion warms,
biomes migrate accordingly — on the path the agents actually see.

Steps (all on a REAL Genesis world, driven through the patched ``sim.step``):
  1. Public API + new diagnostic fields present.
  2. Static world : a full tick leaves the orographic term at 0 (back-compat).
  3. Uplift (+1 km) through sim.step() : anomaly == -LAPSE_K_PER_M·1000 (cool).
  4. Erosion (-1 km) through sim.step() : anomaly == +LAPSE_K_PER_M·1000 (warm).
  5. Uplift actually migrates biomes down the COOLING ladder.
  6. ``anomaly_source='macro'`` : 0 transitions frozen, > 0 once elevation moves.
  7. Read-only contract : macro temp/precip arrays untouched.
  8. Determinism : same seed + same uplift -> identical biome maps.
"""
from __future__ import annotations

import io
import os
import sys

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import numpy as np                                                      # noqa: E402

from engine.sim import Simulation, SimConfig                            # noqa: E402
from engine.world import Biome                                          # noqa: E402
from engine.world_genesis import (GenesisParams, generate_world,        # noqa: E402
                                    make_anchor)
from engine.earth_laws import LAPSE_K_PER_M                             # noqa: E402
from engine.climate_biome import (                                      # noqa: E402
    install_climate_biome, apply_climate_biome_step, climate_biome_state,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:60s} {detail}"


def _make_world(seed=0xCAFE_BEEF):
    gp = GenesisParams(seed=seed & 0xFFFFFFFFFFFFFFFF, resolution=48,
                       n_plates=9, erosion_iters=8, rain_iters=4)
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


def _build(world, *, sim_seed=0xC0FFEE_D00D, source="macro",
           transition_speed=1.0, orographic=True):
    ix, iy = _high_land_cell(world)
    anchor = _anchor_at(world, ix, iy)
    cfg = SimConfig(name="p154_oro", seed=sim_seed & 0xFFFFFFFFFFFFFFFF,
                    founders=2, max_agents=4, bounds_km=(0.5, 0.5),
                    spawn_radius_m=50.0, drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    sim.streamer.set_genesis(anchor)
    sim.streamer.clear_cache()
    sim.bootstrap()
    state = install_climate_biome(sim, anchor, anomaly_source=source,
                                  transition_speed=transition_speed,
                                  orographic_coupling=orographic)
    return sim, anchor, state


def _snapshot(sim):
    return {c: ch.biome.copy() for c, ch in sim.streamer.cache.items()}


def main() -> int:
    print("=" * 78)
    print("P154 — orographic climate coupling (live elevation -> biome)")
    print("=" * 78)
    failures = 0

    world = _make_world()
    print(f"        diag = land={world.diagnostics['land_fraction']:.2f} "
          f"rivers={world.diagnostics['river_cells']}")

    # ----- Step 1 — API surface ----------------------------------------
    sim, anchor, state = _build(world, source="macro")
    n_chunks = len(sim.streamer.cache)
    rep = climate_biome_state(sim)
    ok = (n_chunks > 0
          and rep.get("orographic_coupling") is True
          and "orographic_anomaly_c" in rep
          and len(state.baseline_elev_m) == n_chunks)
    print(_row("step 1 - API + diagnostics + elevation baseline", ok,
               f"chunks={n_chunks}"))
    failures += 0 if ok else 1

    # ----- Step 2 — static world, full tick, term stays 0 --------------
    sim2, anchor2, st2 = _build(world, source="macro")
    sim2.step()  # patched step runs apply_climate_biome_step
    ok = (st2.orographic_anomaly_c == 0.0 and st2.transitions_total == 0)
    print(_row("step 2 - static world: orographic term == 0 (back-compat)",
               ok, f"oro={st2.orographic_anomaly_c:.4f}"))
    failures += 0 if ok else 1

    # ----- Step 3 — uplift cools through sim.step() --------------------
    sim3, anchor3, st3 = _build(world, source="macro")
    anchor3.world.elevation_m += np.float32(1000.0)
    sim3.step()
    expect_cool = -LAPSE_K_PER_M * 1000.0
    ok = (st3.orographic_anomaly_c < 0.0
          and abs(st3.orographic_anomaly_c - expect_cool) < 1e-3)
    print(_row("step 3 - uplift +1km -> anomaly == -6.5 C (cooling)", ok,
               f"oro={st3.orographic_anomaly_c:.3f} expect={expect_cool:.3f}"))
    failures += 0 if ok else 1

    # ----- Step 4 — erosion warms through sim.step() ------------------
    sim4, anchor4, st4 = _build(world, source="macro")
    anchor4.world.elevation_m -= np.float32(1000.0)
    sim4.step()
    expect_warm = LAPSE_K_PER_M * 1000.0
    ok = (st4.orographic_anomaly_c > 0.0
          and abs(st4.orographic_anomaly_c - expect_warm) < 1e-3)
    print(_row("step 4 - erosion -1km -> anomaly == +6.5 C (warming)", ok,
               f"oro={st4.orographic_anomaly_c:.3f} expect={expect_warm:.3f}"))
    failures += 0 if ok else 1

    # ----- Step 5 — uplift migrates biomes down the cooling ladder ----
    sim5, anchor5, st5 = _build(world, source="macro", transition_speed=1.0)
    coord = next(iter(sim5.streamer.cache))
    ch = sim5.streamer.cache[coord]
    ch.biome = np.full_like(ch.biome, int(Biome.TEMPERATE_FOREST))
    st5.chunk_precip_proxy[coord] = 800.0
    anchor5.world.elevation_m += np.float32(1000.0)
    apply_climate_biome_step(sim5)
    ok = bool((sim5.streamer.cache[coord].biome
               == int(Biome.BOREAL_FOREST)).all())
    print(_row("step 5 - cooling ladder: TEMPERATE_FOREST -> BOREAL_FOREST",
               ok, ""))
    failures += 0 if ok else 1

    # ----- Step 6 — macro source: dead when frozen, alive on change ---
    sim6, anchor6, st6 = _build(world, source="macro", transition_speed=1.0)
    for c, chk in sim6.streamer.cache.items():
        chk.biome = np.full_like(chk.biome, int(Biome.TEMPERATE_FOREST))
        st6.chunk_precip_proxy[c] = 800.0
    apply_climate_biome_step(sim6)            # frozen: must not move
    frozen_ok = (st6.transitions_total == 0)
    anchor6.world.elevation_m += np.float32(1000.0)
    res6 = apply_climate_biome_step(sim6)      # elevation moved: must migrate
    ok = frozen_ok and res6["cells_shifted_this_step"] > 0
    print(_row("step 6 - macro source: 0 frozen, >0 once elevation moves", ok,
               f"frozen={frozen_ok} shifted={res6['cells_shifted_this_step']}"))
    failures += 0 if ok else 1

    # ----- Step 7 — read-only macro contract --------------------------
    sim7, anchor7, st7 = _build(world, source="macro")
    t0 = anchor7.world.temp_c.copy()
    p0 = anchor7.world.precip_mm.copy()
    anchor7.world.elevation_m += np.float32(1000.0)
    sim7.step()
    ok = (np.array_equal(anchor7.world.temp_c, t0)
          and np.array_equal(anchor7.world.precip_mm, p0))
    print(_row("step 7 - read-only: macro temp/precip untouched", ok, ""))
    failures += 0 if ok else 1

    # ----- Step 8 — determinism ---------------------------------------
    snaps = []
    counts = []
    for _ in range(2):
        w = _make_world(seed=0xD00D_1111)
        s, a, stt = _build(w, sim_seed=0x2468_ACE0, source="macro",
                           transition_speed=0.4)
        for c, chk in s.streamer.cache.items():
            chk.biome = np.full_like(chk.biome, int(Biome.TEMPERATE_FOREST))
            stt.chunk_precip_proxy[c] = 800.0
        a.world.elevation_m += np.float32(1000.0)
        r = apply_climate_biome_step(s)
        counts.append(r["cells_shifted_this_step"])
        snaps.append(_snapshot(s))
    same = (counts[0] == counts[1] and counts[0] > 0
            and snaps[0].keys() == snaps[1].keys()
            and all(np.array_equal(snaps[0][c], snaps[1][c])
                    for c in snaps[0]))
    print(_row("step 8 - determinism: same seed+uplift -> same biomes", same,
               f"shifted={counts}"))
    failures += 0 if same else 1

    print("-" * 78)
    passed = 8 - failures
    print(f"  RESULT: {passed}/8 checks passed")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
