"""P48 — Wave 19 macro climate propagation smoke.

Validates that the macro wind field (``GenesisWorld.wind_u/v``) replaces
the synthetic wind sources of meteorology, marine and wildfire.

  1. Public API surface present.
  2. ``sample_macro_wind_at`` returns bilinear-interpolated wind matching
     the macro grid at known cells.
  3. After ``install_macro_climate(sim, anchor)``, ``marine._wind_for_chunk(sim, coord)``
     returns macro values (not legacy synthetic).
  4. ``meteorology.tick_meteorology`` post-pass overwrites each cell's
     ``wind_u_ms / wind_v_ms`` with macro values; verified by matching
     against ``sample_macro_wind_at`` at chunk centres.
  5. ``wildfire.tick_wildfire`` receives a non-zero injected wind from
     macro when called without an explicit ``wind=`` argument
     (verified by capturing the inner call's ``wind`` parameter).
  6. ``blend = 0.5`` lerps linearly between macro and legacy.
  7. ``install_macro_climate`` is idempotent : second install returns the
     same state object and only patches each module once.
  8. Determinism : two sims with the same seed and anchor produce the
     same wind values at the same coord.
  9. ``uninstall_macro_climate`` restores the originals on all three
     modules.
"""
from __future__ import annotations

import io
import os
import sys
import traceback
import math

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
from engine.world import CHUNK_SIDE_M                                   # noqa: E402
from engine.world_genesis import (GenesisParams, generate_world,        # noqa: E402
                                    make_anchor)
from engine.macro_climate import (                                      # noqa: E402
    sample_macro_wind_at, chunk_wind_at,
    install_macro_climate, uninstall_macro_climate, macro_climate_state,
    MacroClimateState,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xC0FFEE_F00D):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=2, max_agents=4,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def main() -> int:
    print("=" * 78)
    print("P48 — Wave 19 macro climate propagation smoke")
    print("=" * 78)
    failures = 0

    # Build world + anchor.
    gp = GenesisParams(seed=0xDECAFBAD & 0xFFFFFFFFFFFFFFFF,
                        resolution=64, n_plates=10,
                        erosion_iters=12, rain_iters=4)
    world = generate_world(gp)
    anchor = make_anchor(world)

    # Step 1 — API surface.
    ok = all(name in globals() for name in (
        "sample_macro_wind_at", "chunk_wind_at",
        "install_macro_climate", "uninstall_macro_climate",
        "macro_climate_state"))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Step 2 — sample_macro_wind_at at known macro cells.
    # Pick a high-|wind_u| cell and verify bilinear sampler returns
    # something close to it at the cell's centre.
    abs_wu = np.abs(world.wind_u)
    iy, ix = np.unravel_index(np.argmax(abs_wu), abs_wu.shape)
    cell_km = gp.map_size_km / gp.resolution
    # Place sim origin so that sim (0,0) maps to (ix+0.5, iy+0.5) macro cell.
    test_anchor = make_anchor(
        world, sim_origin_macro_km=((ix + 0.5) * cell_km,
                                      (iy + 0.5) * cell_km))
    u_sample, v_sample = sample_macro_wind_at(test_anchor, 0.0, 0.0)
    u_expected = float(world.wind_u[iy, ix])
    v_expected = float(world.wind_v[iy, ix])
    err = max(abs(u_sample - u_expected), abs(v_sample - v_expected))
    ok = err < 0.01
    print(_row("step 2 - sample_macro_wind_at matches macro at cell centre",
               ok, f"u={u_sample:.2f} (expect {u_expected:.2f}) "
                   f"v={v_sample:.2f} (expect {v_expected:.2f}) err={err:.3f}"))
    if not ok:
        failures += 1

    # Step 3 — marine._wind_for_chunk reads macro after install.
    sim = _build_sim("p48_climate")
    sim.streamer.set_genesis(anchor)
    sim.streamer.clear_cache()
    sim.step()  # populate streamer.cache

    import engine.marine as _marine
    legacy_wind = _marine._wind_for_chunk(sim, (0, 0, 0))
    install_macro_climate(sim, anchor)
    macro_wind = _marine._wind_for_chunk(sim, (0, 0, 0))
    expected = chunk_wind_at(anchor, (0, 0, 0))
    diff_macro = max(abs(macro_wind[0] - expected[0]),
                      abs(macro_wind[1] - expected[1]))
    diff_legacy = max(abs(legacy_wind[0] - expected[0]),
                       abs(legacy_wind[1] - expected[1]))
    ok = diff_macro < 1e-4 and diff_legacy > 0.1
    print(_row("step 3 - marine._wind_for_chunk reads macro after install",
               ok,
               f"legacy=({legacy_wind[0]:+.2f},{legacy_wind[1]:+.2f}) "
               f"macro=({macro_wind[0]:+.2f},{macro_wind[1]:+.2f}) "
               f"expect=({expected[0]:+.2f},{expected[1]:+.2f})"))
    if not ok:
        failures += 1

    # Step 4 — meteorology post-pass overwrites cell winds with macro.
    import engine.meteorology as _meteo
    _meteo.install_meteorology(sim)
    meteo_state = sim._meteo_state if hasattr(sim, "_meteo_state") else None
    # Find the meteo state attribute name via getattr.
    for attr in dir(sim):
        v = getattr(sim, attr, None)
        if isinstance(v, _meteo.MeteorologyState):
            meteo_state = v
            break
    assert meteo_state is not None, "meteorology state not attached to sim"
    _meteo.tick_meteorology(sim, meteo_state)
    # Now compare each cell wind to chunk_wind_at(anchor, coord).
    max_err = 0.0
    n_checked = 0
    for coord, cell in meteo_state.chunk_meteo.items():
        u_macro, v_macro = chunk_wind_at(anchor, coord)
        err = max(abs(cell.wind_u_ms - u_macro),
                  abs(cell.wind_v_ms - v_macro))
        max_err = max(max_err, err)
        n_checked += 1
    ok = (max_err < 1e-4 and n_checked > 0)
    print(_row("step 4 - meteorology cell winds match macro",
               ok, f"n_checked={n_checked} max_err={max_err:.4f}"))
    if not ok:
        failures += 1

    # Step 5 — wildfire receives injected macro wind.
    import engine.wildfire as _wf

    # Capture wind via probe wrapper around the patched function.
    captured = {}
    orig_fire = _wf._macro_orig_tick_wildfire

    def _probe(sim_inner, *, storm_factor=1.0, wind=None):
        captured["wind"] = wind
        return orig_fire(sim_inner, storm_factor=storm_factor, wind=wind)

    # Patch the *outer* tick_wildfire so it still calls our injector,
    # but the inner call lands in _probe so we can intercept the wind.
    _wf._macro_orig_tick_wildfire = _probe
    _wf.install_wildfire(sim)
    try:
        _wf.tick_wildfire(sim)
    finally:
        _wf._macro_orig_tick_wildfire = orig_fire

    wind_passed = captured.get("wind")
    ok = (wind_passed is not None
          and isinstance(wind_passed, tuple)
          and len(wind_passed) == 2
          and (abs(wind_passed[0]) + abs(wind_passed[1])) > 0.01)
    print(_row("step 5 - wildfire receives non-trivial macro wind",
               ok, f"wind={wind_passed}"))
    if not ok:
        failures += 1

    # Step 6 — blend = 0.5 lerps.
    uninstall_macro_climate(sim)
    blended_state = install_macro_climate(sim, anchor, blend=0.5)
    legacy_u = legacy_wind[0]
    macro_u = expected[0]
    blended_u, blended_v = _marine._wind_for_chunk(sim, (0, 0, 0))
    expected_blend_u = 0.5 * macro_u + 0.5 * legacy_u
    ok = abs(blended_u - expected_blend_u) < 0.05
    print(_row("step 6 - blend=0.5 lerps macro vs legacy",
               ok,
               f"legacy_u={legacy_u:.2f} macro_u={macro_u:.2f} "
               f"blended_u={blended_u:.2f} expect={expected_blend_u:.2f}"))
    if not ok:
        failures += 1

    # Step 7 — install idempotent.
    s1 = install_macro_climate(sim, anchor, blend=1.0)
    s2 = install_macro_climate(sim, anchor, blend=1.0)
    ok = (s1 is s2 and s1.modules_patched == 3)
    print(_row("step 7 - install idempotent + patched 3 modules",
               ok, f"same={s1 is s2} patched={s1.modules_patched}"))
    if not ok:
        failures += 1

    # Step 8 — determinism: two sims same seed -> same wind.
    sim2 = _build_sim("p48_climate_2")
    sim2.streamer.set_genesis(anchor)
    sim2.streamer.clear_cache()
    sim2.step()
    install_macro_climate(sim2, anchor)
    w1 = _marine._wind_for_chunk(sim, (3, 3, 0))
    w2 = _marine._wind_for_chunk(sim2, (3, 3, 0))
    ok = abs(w1[0] - w2[0]) < 1e-6 and abs(w1[1] - w2[1]) < 1e-6
    print(_row("step 8 - determinism: two anchored sims give same wind",
               ok, f"w1=({w1[0]:+.3f},{w1[1]:+.3f}) "
                   f"w2=({w2[0]:+.3f},{w2[1]:+.3f})"))
    if not ok:
        failures += 1

    # Step 9 — uninstall restores originals.
    ok1 = uninstall_macro_climate(sim)
    ok2 = (getattr(_marine, "_macro_orig_wind_for_chunk", None) is None
           and getattr(_meteo, "_macro_orig_tick_meteorology", None) is None
           and getattr(_wf, "_macro_orig_tick_wildfire", None) is None)
    legacy_again = _marine._wind_for_chunk(sim, (0, 0, 0))
    # Should match the original (synthetic) wind (within FP precision).
    ok3 = abs(legacy_again[0] - legacy_wind[0]) < 1e-6 \
        and abs(legacy_again[1] - legacy_wind[1]) < 1e-6
    ok = ok1 and ok2 and ok3
    print(_row("step 9 - uninstall restores originals on all 3 modules",
               ok,
               f"uninst={ok1} hooks_clear={ok2} "
               f"legacy_match={ok3}"))
    if not ok:
        failures += 1

    print(f"\nMacro climate state on sim2: {macro_climate_state(sim2)}")

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
