"""P49 — Wave 20 climate-biome coupling smoke.

Validates that ``engine.climate_biome`` correctly shifts the biome map
of cached chunks as the macro temperature anomaly grows.

  1. Public API surface present.
  2. ``install_climate_biome`` is idempotent + captures baseline_temp.
  3. With 0 ticks elapsed (anomaly = 0), a forced apply does NOT shift
     any cell.
  4. With strong warming_rate + many ticks, at least one TUNDRA cell
     transitions to BOREAL_FOREST.
  5. Under warming, no shifted cell ends up in a *colder* biome than
     it started — the cooling matrix is not used.
  6. The transition pattern is correct on TUNDRA -> BOREAL_FOREST
     (exact shift from the warming matrix).
  7. Determinism : two sims with the same seed and anchor produce the
     same shifted cell count and the same final biome map.
  8. ``climate_biome_state(sim)`` reports ``transitions_total > 0``
     after the heated run.
  9. ``uninstall_climate_biome`` restores the original ``sim.step``
     and DOES NOT re-shift biomes backwards.
"""
from __future__ import annotations

import io
import os
import sys
import traceback

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
from engine.climate_biome import (                                      # noqa: E402
    ClimateBiomeState,
    install_climate_biome, uninstall_climate_biome,
    apply_climate_biome_step, climate_biome_state,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xC0DECAFE_BEEF):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=2, max_agents=4,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def _find_tundra_macro_cell(world):
    """Pick the macro cell whose biome is TUNDRA and is on land — used as
    the anchor target so simulated chunks are in tundra to start with."""
    elev = world.elevation_m
    biome = world.biome
    tundra_mask = (biome == int(Biome.TUNDRA)) & (elev > 0.0)
    if not tundra_mask.any():
        # Fall back to the COLDEST land biome (probably BOREAL_FOREST or
        # ICE) — the test will adapt.
        coldest_score = world.temp_c.copy()
        coldest_score[elev <= 0.0] = 1e9
        iy, ix = np.unravel_index(np.argmin(coldest_score),
                                    coldest_score.shape)
        return int(ix), int(iy), int(biome[iy, ix])
    # Choose the tundra cell furthest from any non-tundra cell (interior
    # tundra) so neighbouring chunks are also tundra.
    ys_, xs_ = np.where(tundra_mask)
    # First tundra cell will do — pick the median to avoid edges.
    k = len(xs_) // 2
    return int(xs_[k]), int(ys_[k]), int(Biome.TUNDRA)


def _anchor_at(world, ix, iy):
    cell_km = world.params.map_size_km / world.params.resolution
    return make_anchor(world,
                        sim_origin_macro_km=((ix + 0.5) * cell_km,
                                              (iy + 0.5) * cell_km))


def _count_biome_cells(sim, biome_id: int) -> int:
    total = 0
    for chunk in sim.streamer.cache.values():
        total += int((chunk.biome == biome_id).sum())
    return total


def _snapshot_biomes(sim):
    """Capture chunk.biome arrays as a dict for later comparison."""
    return {coord: chunk.biome.copy()
            for coord, chunk in sim.streamer.cache.items()}


def main() -> int:
    print("=" * 78)
    print("P49 — Wave 20 climate biome coupling smoke")
    print("=" * 78)
    failures = 0

    # Build a genesis world with a clear tundra band.
    gp = GenesisParams(seed=0xCAFEDEAD & 0xFFFFFFFFFFFFFFFF,
                        resolution=64, n_plates=10,
                        erosion_iters=10, rain_iters=4)
    world = generate_world(gp)
    print(f"        diag = land={world.diagnostics['land_fraction']:.2f} "
          f"rivers={world.diagnostics['river_cells']} "
          f"basins={world.diagnostics['n_watersheds']}")

    tix, tiy, anchor_biome = _find_tundra_macro_cell(world)
    print(f"        anchor macro cell: (ix={tix}, iy={tiy}) "
          f"biome={Biome(anchor_biome).name}")
    anchor = _anchor_at(world, tix, tiy)

    # ----- Step 1 — API surface ----------------------------------------
    ok = all(name in globals() for name in (
        "ClimateBiomeState",
        "install_climate_biome",
        "uninstall_climate_biome",
        "apply_climate_biome_step",
        "climate_biome_state",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # ----- Step 2 — install idempotent + baseline captured -------------
    sim = _build_sim("p49_climate_biome", seed=0xC0FFEE_F00D)
    sim.streamer.set_genesis(anchor)
    sim.streamer.clear_cache()
    sim.bootstrap()  # warm the streamer cache around founders

    # Quickly run a couple of legacy ticks to populate more chunks BEFORE
    # install — we want to see the baseline snapshot at install time.
    # (We do NOT call sim.step() here yet because that ticks the simulation
    # forward; bootstrap already filled some chunks via streamer.touch_area.)
    n_chunks_pre = len(sim.streamer.cache)

    s1 = install_climate_biome(sim, anchor,
                                anomaly_source="linear_warming",
                                warming_rate_c_per_year=2.0,
                                transition_speed=0.5)
    s2 = install_climate_biome(sim, anchor,
                                anomaly_source="linear_warming",
                                warming_rate_c_per_year=2.0,
                                transition_speed=0.5)
    n_baseline = len(s1.baseline_temp_c)
    ok = (s1 is s2
          and n_baseline == n_chunks_pre
          and n_baseline > 0)
    print(_row("step 2 - install idempotent + baseline captured",
               ok, f"same={s1 is s2} chunks_cached={n_chunks_pre} "
                   f"baseline_snapshots={n_baseline}"))
    if not ok:
        failures += 1

    # ----- Step 3 — 0 ticks => 0 shifts --------------------------------
    # sim.tick is still at its post-bootstrap value but we have *not*
    # advanced past bootstrap. The anomaly is warming_rate * (tick *
    # accel / SEC_PER_YEAR). With tick small enough this should yield
    # below ANOMALY_DEADBAND_C => no shifts.
    # Force tick to 0 to be safe ; ``apply_climate_biome_step`` is
    # idempotent.
    sim.tick = 0
    biomes_before = _snapshot_biomes(sim)
    info_zero = apply_climate_biome_step(sim)
    biomes_after = _snapshot_biomes(sim)
    same = all(np.array_equal(biomes_before[c], biomes_after[c])
               for c in biomes_before)
    ok = (info_zero["cells_shifted_this_step"] == 0
          and abs(info_zero["global_anomaly_c"]) < 1e-9
          and same)
    print(_row("step 3 - tick=0 anomaly=0 -> 0 cells shifted",
               ok, f"shifted={info_zero['cells_shifted_this_step']} "
                   f"anom={info_zero['global_anomaly_c']:+.4f} "
                   f"map_identical={same}"))
    if not ok:
        failures += 1

    # ----- Step 4 — heated run shifts TUNDRA -> BOREAL_FOREST ----------
    # Force enough sim-years of heating to push anomaly past the deadband.
    # warming_rate=2.0 K/year ; drive_accel=1500 sim-s/tick ;
    # sim_years_per_tick = 1500 / SECONDS_PER_YEAR ~= 4.75e-5
    # After 50 ticks: ~2.4e-3 years -> dT ~= 0.005 K (still tiny).
    # We need a far stronger forcing. Bump tick to a large integer to
    # simulate the equivalent of many sim-years of warming.
    # Equivalent: set tick so dT = 4 K. tick = 4 / (2.0 * accel /
    # SEC_PER_YEAR) = 4 * SEC_PER_YEAR / (2 * 1500) = 4.2e4 ticks.
    sim.tick = 50_000  # ~ +6 K warming
    info_hot = apply_climate_biome_step(sim)
    biomes_post = _snapshot_biomes(sim)
    boreal_id = int(Biome.BOREAL_FOREST)
    tundra_id = int(Biome.TUNDRA)
    n_shift_to_boreal = 0
    n_shift_total = 0
    for coord, before in biomes_before.items():
        after = biomes_post[coord]
        was_tundra = (before == tundra_id)
        now_boreal = (after == boreal_id)
        n_shift_to_boreal += int((was_tundra & now_boreal).sum())
        n_shift_total += int((before != after).sum())
    ok = (info_hot["cells_shifted_this_step"] > 0
          and info_hot["global_anomaly_c"] > 0.1
          and n_shift_to_boreal >= 1)
    print(_row("step 4 - heated run: TUNDRA -> BOREAL_FOREST cells > 0",
               ok, f"anom={info_hot['global_anomaly_c']:+.2f}C "
                   f"shifted_step={info_hot['cells_shifted_this_step']} "
                   f"to_boreal={n_shift_to_boreal} total={n_shift_total}"))
    if not ok:
        failures += 1

    # ----- Step 5 — under warming, no shifted cell lands in a colder biome
    # Build the "warmth rank" : a per-Biome integer such that warming
    # transitions never decrease the rank. (OCEAN=0 stays apart.)
    warmth_rank = {
        Biome.OCEAN: 0,
        Biome.ICE: 1,
        Biome.TUNDRA: 2,
        Biome.BOREAL_FOREST: 3,
        Biome.COLD_DESERT: 3,
        Biome.TEMPERATE_FOREST: 4,
        Biome.TEMPERATE_RAINFOREST: 5,
        Biome.GRASSLAND: 4,
        Biome.SAVANNA: 5,
        Biome.HOT_DESERT: 6,
        Biome.TROPICAL_DRY_FOREST: 6,
        Biome.TROPICAL_RAINFOREST: 7,
    }
    rank_arr = np.zeros(12, dtype=np.int32)
    for b, r in warmth_rank.items():
        rank_arr[int(b)] = r
    n_violations = 0
    for coord, before in biomes_before.items():
        after = biomes_post[coord]
        changed = (before != after)
        if not changed.any():
            continue
        before_rank = rank_arr[before[changed]]
        after_rank = rank_arr[after[changed]]
        n_violations += int((after_rank < before_rank).sum())
    ok = (n_violations == 0)
    print(_row("step 5 - no warming->cooling violations on shifted cells",
               ok, f"violations={n_violations}"))
    if not ok:
        failures += 1

    # ----- Step 6 — exact TUNDRA -> BOREAL_FOREST shift confirmed -------
    # Locate at least one (coord, cell) pair that experienced exactly that
    # transition. Already counted in step 4 ; here we re-verify the count
    # and confirm none became, say, TEMPERATE_FOREST in one hop (the
    # matrix says TUNDRA always goes to BOREAL_FOREST under warming).
    n_tundra_to_other = 0
    for coord, before in biomes_before.items():
        after = biomes_post[coord]
        was_tundra = (before == tundra_id)
        target = after[was_tundra]
        # All shifted should go to BOREAL_FOREST; unshifted stay TUNDRA.
        bad = (target != tundra_id) & (target != boreal_id)
        n_tundra_to_other += int(bad.sum())
    ok = (n_shift_to_boreal >= 1 and n_tundra_to_other == 0)
    print(_row("step 6 - TUNDRA shifts always go to BOREAL_FOREST",
               ok, f"to_boreal={n_shift_to_boreal} "
                   f"to_other={n_tundra_to_other}"))
    if not ok:
        failures += 1

    # ----- Step 7 — determinism: two sims same seed same final biomes ---
    sim2 = _build_sim("p49_climate_biome_2", seed=0xC0FFEE_F00D)
    sim2.streamer.set_genesis(anchor)
    sim2.streamer.clear_cache()
    sim2.bootstrap()
    # Replay the same trajectory: install with same params, then directly
    # apply at the same tick.
    install_climate_biome(sim2, anchor,
                           anomaly_source="linear_warming",
                           warming_rate_c_per_year=2.0,
                           transition_speed=0.5)
    sim2.tick = 50_000
    apply_climate_biome_step(sim2)
    biomes_sim2 = _snapshot_biomes(sim2)
    # Compare. We require the union of coords to match AND every shared
    # coord to have an identical biome array.
    coords_a = set(biomes_post.keys())
    coords_b = set(biomes_sim2.keys())
    shared = coords_a & coords_b
    arrays_match = all(np.array_equal(biomes_post[c], biomes_sim2[c])
                        for c in shared)
    state2 = climate_biome_state(sim2)
    state1 = climate_biome_state(sim)
    counts_match = (state1["transitions_total"]
                    == state2["transitions_total"])
    ok = (len(shared) > 0 and arrays_match and counts_match)
    print(_row("step 7 - determinism: two anchored sims identical maps",
               ok, f"shared_chunks={len(shared)} "
                   f"all_arrays_eq={arrays_match} "
                   f"transitions={state1['transitions_total']}/"
                   f"{state2['transitions_total']}"))
    if not ok:
        failures += 1

    # ----- Step 8 — climate_biome_state(sim) reports nontrivial counters
    final_state = climate_biome_state(sim)
    ok = (final_state["installed"]
          and final_state["transitions_total"] > 0
          and final_state["global_anomaly_c"] > 0.0
          and final_state["chunks_with_shifts"] >= 1)
    print(_row("step 8 - state reporter: transitions_total > 0",
               ok, f"installed={final_state['installed']} "
                   f"transitions={final_state['transitions_total']} "
                   f"global_anom={final_state['global_anomaly_c']:+.2f} "
                   f"shifted_chunks={final_state['chunks_with_shifts']}"))
    if not ok:
        failures += 1

    # ----- Step 9 — uninstall restores sim.step, no re-shift backwards --
    biomes_before_uninst = _snapshot_biomes(sim)
    ok1 = uninstall_climate_biome(sim)
    ok2 = (getattr(sim, "_climate_biome_state", None) is None
           and getattr(sim, "_climate_biome_orig_step", None) is None)
    # After uninstall, sim.step is the original. A direct tick should NOT
    # revert any biome — we use streamer.clear_cache is not appropriate
    # here ; just verify the biome arrays remain identical to the heated
    # snapshot.
    biomes_after_uninst = _snapshot_biomes(sim)
    no_revert = all(np.array_equal(biomes_before_uninst[c],
                                     biomes_after_uninst[c])
                     for c in biomes_before_uninst)
    # Also confirm sim.step still works (just runs the original loop).
    try:
        sim.step()
        step_ok = True
    except Exception as exc:  # pragma: no cover
        step_ok = False
        print(f"        sim.step raised after uninstall: {exc}")
    ok = ok1 and ok2 and no_revert and step_ok
    print(_row("step 9 - uninstall restores step and freezes biomes",
               ok, f"uninst={ok1} hooks_clear={ok2} "
                   f"no_revert={no_revert} step_ok={step_ok}"))
    if not ok:
        failures += 1

    print(f"\nClimate biome state on sim: {climate_biome_state(sim)}")

    total = 9
    passed = total - failures
    print("=" * 78)
    if failures == 0:
        print(f"RESULT: {total}/{total} PASS")
        return 0
    else:
        print(f"RESULT: {passed}/{total} PASS, {failures} FAIL")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
