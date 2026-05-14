"""P25 — Wave 5 marine smoke test.

Builds a Léman world (the OCEAN biome covers the lake surface) and
exercises :mod:`engine.marine`:

  1. OceanCurrentField is non-empty for OCEAN-bearing chunks.
  2. Tide phase has advanced after 500 ticks.
  3. Plankton biomass is positive in at least one OCEAN chunk.
  4. Fish biomass is positive in at least one OCEAN chunk.
  5. Determinism : two runs with the same seed produce identical
     ``marine_state`` hashes.

Exit 0 on full pass, 1 otherwise.
"""
from __future__ import annotations

import hashlib
import io
import json
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

from engine.sim import Simulation, SimConfig                # noqa: E402
from engine.sim_5cd_integration import install              # noqa: E402
from engine.earth_loader import EarthLoader                 # noqa: E402
from engine.earth_streamer import (attach_earth_loader,     # noqa: E402
                                   attach_land_filter)
from engine.sim_lift import install_lift                    # noqa: E402
from engine.photosynthesis import install_photosynthesis    # noqa: E402
from engine.marine import (install_marine, marine_state,    # noqa: E402
                            M2_PERIOD_S)
from engine.world import Biome                              # noqa: E402


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:55s} {detail}"


def _build(seed: int, n_ticks: int):
    cfg = SimConfig(
        name="p25_marine",
        seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=8, max_agents=20,
        bounds_km=(2.0, 2.0),
        spawn_radius_m=200.0,
        drive_accel=1500.0,
        cultures=1,
    )
    loader = EarthLoader(
        origin_lat=46.510, origin_lon=6.633, bounds_km=2.0,
        cache_dir=os.path.abspath(os.path.join(
            ROOT, "..", "cache", "earth_leman")),
    )
    sim = Simulation(cfg)
    attach_earth_loader(sim.streamer, loader, log_first_hit=False)
    attach_land_filter(sim)
    install(sim)
    install_lift(sim)
    install_photosynthesis(sim)
    state = install_marine(sim)
    for _ in range(n_ticks):
        sim.step()
    return sim, state


def _state_hash(s) -> str:
    return hashlib.sha256(
        json.dumps(s, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]


def main() -> int:
    print("=" * 78)
    print("P25 — Wave 5 marine smoke (currents / tides / Lotka-Volterra)")
    print("=" * 78)
    failures = 0

    # --------------------------------------------------------------
    # Build + run twice for determinism comparison.
    # --------------------------------------------------------------
    seed = 0xBEEF_C0FFEE_2026 & 0xFFFFFFFFFFFFFFFF
    sim_a, state_a = _build(seed, 500)
    sim_b, state_b = _build(seed, 500)
    snap_a = marine_state(sim_a)
    snap_b = marine_state(sim_b)

    # --------------------------------------------------------------
    # Step 1 — OceanCurrentField populated for OCEAN-bearing chunks.
    # --------------------------------------------------------------
    ocean_field_count = 0
    non_zero_field_count = 0
    for coord, cf in state_a.currents.items():
        if cf.ocean_mask.any():
            ocean_field_count += 1
            if (cf.u.any() or cf.v.any()):
                non_zero_field_count += 1
    ok = ocean_field_count > 0 and non_zero_field_count > 0
    print(_row("step 1 — OCEAN current fields are non-empty", ok,
               f"ocean_chunks={ocean_field_count} "
               f"non_zero_currents={non_zero_field_count}"))
    if not ok:
        failures += 1

    # --------------------------------------------------------------
    # Step 2 — Tide phase has advanced. 500 ticks × drive_accel = 7.5e5
    # sim-seconds ≈ 16.8 × M2 period → phase should be far from zero.
    # --------------------------------------------------------------
    tide_phase = float(snap_a["tide_phase_rad"])
    tide_height = float(snap_a["tide_height_m"])
    ok = abs(tide_phase) > 0.01 and abs(tide_height) <= state_a.tide_amplitude_m + 1e-6
    print(_row("step 2 — tide phase advanced", ok,
               f"phase={tide_phase:.4f} rad height={tide_height:.4f} m "
               f"period_s={M2_PERIOD_S:.0f}"))
    if not ok:
        failures += 1

    # --------------------------------------------------------------
    # Step 3 — Plankton biomass > 0 in some OCEAN chunks.
    # --------------------------------------------------------------
    plk_total = float(snap_a["plankton_total_kg"])
    ok = plk_total > 0.0 and snap_a["biology_chunks"] > 0
    print(_row("step 3 — plankton biomass positive", ok,
               f"plankton_total_kg={plk_total:.3f} "
               f"biology_chunks={snap_a['biology_chunks']}"))
    if not ok:
        failures += 1

    # --------------------------------------------------------------
    # Step 4 — Fish biomass > 0 in some OCEAN chunks.
    # --------------------------------------------------------------
    fish_total = float(snap_a["fish_total_kg"])
    ok = fish_total > 0.0
    print(_row("step 4 — fish biomass positive", ok,
               f"fish_total_kg={fish_total:.3f} "
               f"predator_total_kg={snap_a['predator_total_kg']:.3f}"))
    if not ok:
        failures += 1

    # --------------------------------------------------------------
    # Step 5 — Determinism : marine_state hashes match across two
    # runs with the same seed.
    # --------------------------------------------------------------
    h_a = _state_hash(snap_a)
    h_b = _state_hash(snap_b)
    ok = h_a == h_b
    print(_row("step 5 — determinism (same seed → same hash)", ok,
               f"a={h_a} b={h_b}"))
    if not ok:
        failures += 1

    # --------------------------------------------------------------
    # Step 6 — Capabilities lint still clean after adding marine.
    # --------------------------------------------------------------
    from engine.world_model_capabilities import audit_modules
    _, lint_fails = audit_modules(strict=False)
    ok = not lint_fails
    print(_row("step 6 — ADR-0005 audit clean", ok,
               f"failures={lint_fails}"))
    if not ok:
        failures += 1

    print()
    print(f"Snapshot:")
    print(f"  ocean_chunks   : {snap_a['ocean_chunks']}")
    print(f"  current_chunks : {snap_a['current_chunks']}")
    print(f"  mean_current_ms: {snap_a['mean_current_ms']:.4f}")
    print(f"  tide_height_m  : {snap_a['tide_height_m']:.4f}")
    print(f"  plankton_total : {snap_a['plankton_total_kg']:.3f} kg")
    print(f"  fish_total     : {snap_a['fish_total_kg']:.3f} kg")
    print(f"  predator_total : {snap_a['predator_total_kg']:.3f} kg")

    print()
    if failures == 0:
        print("RESULT: PASS — Wave 5 marine smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
