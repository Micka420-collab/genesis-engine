"""P52 — Genesis integration end-to-end smoke.

Validates that :func:`engine.genesis_bootstrap.bootstrap_genesis_sim`
correctly chains Waves 16-19 (and any optional Waves 20+ if present),
producing a fully-anchored sim ready to tick.

  1. Public API surface present.
  2. ``bootstrap_genesis_sim`` with default modules installs all
     mandatory subsystems (genesis + geology + hydrology + meteo + marine
     + wildfire + climate).
  3. Idempotent — second call returns the same state.
  4. ``modules={'genesis'}`` only wires the macro anchor, skips the rest.
  5. ``modules=MINIMAL_MODULES`` wires substrate only (geology + hydro).
  6. Macro propagation : chunk at sim origin has elevation ≈ macro elev.
  7. After a few ticks, climate state shows queries > 0 (macro wind
     consumed by meteo + marine).
  8. Determinism : two sims same seed → same world signature + same
     bootstrap state shape.
  9. Optional Wave 20/21 modules : if present, listed in
     ``modules_installed``; if absent, listed in ``modules_skipped``
     with a "not yet implemented" reason.
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

from engine.sim import Simulation, SimConfig                            # noqa: E402
from engine.genesis_bootstrap import (                                  # noqa: E402
    bootstrap_genesis_sim, bootstrap_state, BootstrapState,
    ALL_MODULES, MINIMAL_MODULES, CLIMATE_MODULES,
    MOD_GENESIS, MOD_GEOLOGY, MOD_HYDROLOGY, MOD_METEOROLOGY,
    MOD_MARINE, MOD_WILDFIRE, MOD_CLIMATE,
    MOD_CLIMATE_BIOME, MOD_MARINE_BATHYMETRY,
)
from engine.world_genesis import (GenesisParams,                        # noqa: E402
                                    world_signature, sample_macro)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xC0FFEE_0011):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=2, max_agents=4,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def main() -> int:
    print("=" * 78)
    print("P52 — Genesis integration end-to-end smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API
    ok = all(name in globals() for name in (
        "bootstrap_genesis_sim", "bootstrap_state",
        "ALL_MODULES", "MINIMAL_MODULES", "CLIMATE_MODULES",
        "MOD_GENESIS", "MOD_GEOLOGY", "MOD_HYDROLOGY"))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Step 2 — default bootstrap wires the mandatory stack.
    sim = _build_sim("p52_full")
    params = GenesisParams(seed=0xC0FFEE_0011 & 0xFFFFFFFFFFFFFFFF,
                            resolution=64, n_plates=10,
                            erosion_iters=15, rain_iters=4)
    state = bootstrap_genesis_sim(sim, genesis_params=params)
    expected = {MOD_GENESIS, MOD_GEOLOGY, MOD_HYDROLOGY,
                MOD_METEOROLOGY, MOD_MARINE, MOD_WILDFIRE, MOD_CLIMATE}
    ok = expected.issubset(state.modules_installed)
    print(_row("step 2 - default bootstrap installs mandatory stack",
               ok, f"installed={sorted(state.modules_installed)}"))
    if not ok:
        failures += 1

    # Step 3 — idempotent
    state2 = bootstrap_genesis_sim(sim)
    ok = (state is state2 and bootstrap_state(sim) is state)
    print(_row("step 3 - idempotent (same state object)", ok, ""))
    if not ok:
        failures += 1

    # Step 4 — modules={'genesis'} only.
    sim_min1 = _build_sim("p52_min1")
    s_min1 = bootstrap_genesis_sim(sim_min1, genesis_params=params,
                                     modules={MOD_GENESIS})
    ok = (s_min1.modules_installed == {MOD_GENESIS}
          and sim_min1.streamer.genesis is not None)
    print(_row("step 4 - modules={'genesis'} wires only anchor",
               ok, f"installed={sorted(s_min1.modules_installed)}"))
    if not ok:
        failures += 1

    # Step 5 — MINIMAL_MODULES = substrate only.
    sim_min2 = _build_sim("p52_min2")
    s_min2 = bootstrap_genesis_sim(sim_min2, genesis_params=params,
                                     modules=MINIMAL_MODULES)
    ok = (s_min2.modules_installed == set(MINIMAL_MODULES))
    print(_row("step 5 - MINIMAL_MODULES wires substrate only",
               ok, f"installed={sorted(s_min2.modules_installed)}"))
    if not ok:
        failures += 1

    # Step 6 — macro propagation : chunk at sim origin ≈ macro elev.
    sim.step()  # populate streamer cache
    coord = (0, 0, 0)
    chunk = sim.streamer.get(0, coord)
    chunk_mean = float(chunk.height.mean())
    # Macro at sim origin (which is at the macro centre by default).
    center_x_km = state.anchor.sim_origin_macro_km[0]
    center_y_km = state.anchor.sim_origin_macro_km[1]
    macro_elev = float(sample_macro(state.world, center_x_km, center_y_km)
                        ["elevation_m"])
    delta = abs(chunk_mean - macro_elev)
    ok = delta <= state.anchor.micro_amp_m * 2.0 + 50.0
    print(_row("step 6 - chunk at origin matches macro elev",
               ok, f"chunk={chunk_mean:.1f} macro={macro_elev:.1f} "
                   f"delta={delta:.1f}"))
    if not ok:
        failures += 1

    # Step 7 — climate state shows macro wind queries after ticks.
    for _ in range(3):
        sim.step()
    clim_st = state.sub_states.get("macro_climate")
    queries = int(getattr(clim_st, "queries_total", 0)) if clim_st else 0
    ok = queries > 0
    print(_row("step 7 - macro climate consumed (queries>0)",
               ok, f"queries_total={queries}"))
    if not ok:
        failures += 1

    # Step 8 — determinism : two sims same seed produce same world signature.
    sim_a = _build_sim("p52_det_a")
    sim_b = _build_sim("p52_det_b")
    sa = bootstrap_genesis_sim(sim_a, genesis_params=params)
    sb = bootstrap_genesis_sim(sim_b, genesis_params=params)
    sig_a = world_signature(sa.world)
    sig_b = world_signature(sb.world)
    ok = (sig_a == sig_b
          and sa.modules_installed == sb.modules_installed)
    print(_row("step 8 - determinism (world signature + modules)",
               ok, f"sig={sig_a[:16]}..."))
    if not ok:
        failures += 1

    # Step 9 — Optional Wave 20/21 reporting.
    # If modules implemented and requested, they appear in installed.
    # Otherwise they appear in skipped with reason "not yet implemented".
    sim_opt = _build_sim("p52_opt")
    requested = ALL_MODULES
    s_opt = bootstrap_genesis_sim(sim_opt, genesis_params=params,
                                    modules=requested)
    cb_installed = MOD_CLIMATE_BIOME in s_opt.modules_installed
    cb_skipped = MOD_CLIMATE_BIOME in s_opt.modules_skipped
    mb_installed = MOD_MARINE_BATHYMETRY in s_opt.modules_installed
    mb_skipped = MOD_MARINE_BATHYMETRY in s_opt.modules_skipped
    # Each optional module must be either installed OR skipped — never neither.
    ok = (cb_installed ^ cb_skipped) and (mb_installed ^ mb_skipped)
    print(_row("step 9 - optional Wave 20/21 reported (installed or skipped)",
               ok,
               f"climate_biome={'OK' if cb_installed else 'skip'} "
               f"bathymetry={'OK' if mb_installed else 'skip'}"))
    if not ok:
        failures += 1
    # Dump for visibility.
    if s_opt.modules_skipped:
        for name, reason in s_opt.modules_skipped.items():
            print(f"        skipped {name}: {reason[:60]}")

    print(f"\nFinal state: {state}")

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
