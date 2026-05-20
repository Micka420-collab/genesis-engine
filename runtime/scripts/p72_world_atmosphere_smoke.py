"""P72 — Wave 41 world atmosphere smoke.

  1. Public API surface.
  2. ``compute_solar_state`` at noon → altitude ~ max for latitude.
  3. ``compute_solar_state`` at midnight → altitude < 0 (night).
  4. Sky color : day ≠ sunset ≠ night.
  5. Seasonal tint : summer ≠ winter (R,G,B multipliers differ).
  6. ``compute_snow_field`` : returns bool array matching world resolution.
  7. ``enhance_render`` preserves RGB shape, modifies content at night.
  8. Determinism : same args → same output.
  9. ``render_macro_with_atmosphere`` writes PNG.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
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

from engine.world_genesis import GenesisParams, generate_world          # noqa: E402
from engine.world_atmosphere import (                                   # noqa: E402
    SolarState, AtmosphereOptions,
    compute_solar_state, sky_color_from_solar, light_intensity_from_solar,
    seasonal_tint, compute_snow_field, compute_cloud_field,
    enhance_render, render_macro_with_atmosphere, atmosphere_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P72 — Wave 41 world atmosphere smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API.
    ok = all(name in globals() for name in (
        "SolarState", "AtmosphereOptions",
        "compute_solar_state",
        "sky_color_from_solar", "light_intensity_from_solar",
        "seasonal_tint",
        "compute_snow_field", "compute_cloud_field",
        "enhance_render", "render_macro_with_atmosphere",
        "atmosphere_summary",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Step 2 — noon : solar altitude near max for latitude.
    # At equator (lat=0), summer solstice (day=172), noon → max ~ 90°.
    # Use sim_tick that maps to noon on day 172 :
    #   sim_seconds_target = (172 × 86400) + (12 × 3600) = 14_904_000
    #   sim_tick = sim_seconds_target / drive_accel
    sim_tick_noon = int((172 * 86400 + 12 * 3600) / 1500.0)
    solar_noon = compute_solar_state(sim_tick_noon, latitude_deg=0.0)
    ok = (solar_noon.altitude_deg > 60.0
          and solar_noon.is_day
          and abs(solar_noon.hour_of_day - 12.0) < 0.1)
    print(_row("step 2 - noon @ equator summer → altitude > 60°",
               ok, f"alt={solar_noon.altitude_deg:.1f}° hour={solar_noon.hour_of_day:.2f} day={solar_noon.day_of_year}"))
    if not ok:
        failures += 1

    # Step 3 — midnight : altitude < 0.
    sim_tick_midnight = int((172 * 86400) / 1500.0)  # hour=0
    solar_midnight = compute_solar_state(sim_tick_midnight, latitude_deg=0.0)
    ok = (solar_midnight.altitude_deg < 0.0
          and not solar_midnight.is_day)
    print(_row("step 3 - midnight → altitude < 0 (night)",
               ok, f"alt={solar_midnight.altitude_deg:.1f}° hour={solar_midnight.hour_of_day:.2f}"))
    if not ok:
        failures += 1

    # Step 4 — sky colors differ across day phases.
    sky_day = sky_color_from_solar(SolarState(altitude_deg=60.0))
    sky_sunset = sky_color_from_solar(SolarState(altitude_deg=2.0))
    sky_night = sky_color_from_solar(SolarState(altitude_deg=-30.0))
    ok = (sky_day != sky_sunset and sky_sunset != sky_night
          and sky_day[2] > sky_night[2])  # day sky is bluer than night
    print(_row("step 4 - sky day ≠ sunset ≠ night",
               ok, f"day={sky_day} sunset={sky_sunset} night={sky_night}"))
    if not ok:
        failures += 1

    # Step 5 — seasonal tint summer ≠ winter.
    summer = seasonal_tint(1.0)
    winter = seasonal_tint(-1.0)
    neutral = seasonal_tint(0.0)
    ok = (summer != winter
          and neutral == (1.0, 1.0, 1.0)
          and summer[1] > winter[1])  # greens stronger in summer
    print(_row("step 5 - seasonal tint summer ≠ winter",
               ok, f"summer={summer} winter={winter}"))
    if not ok:
        failures += 1

    # Step 6 — snow field on a cold/wet world.
    gp = GenesisParams(seed=0xC0FFEE_72 & 0xFFFFFFFFFFFFFFFF,
                        resolution=48, n_plates=8,
                        erosion_iters=10, rain_iters=3)
    world = generate_world(gp)
    snow = compute_snow_field(world)
    cloud = compute_cloud_field(world)
    ok = (snow.shape == (gp.resolution, gp.resolution)
          and snow.dtype == bool
          and cloud.shape == (gp.resolution, gp.resolution)
          and cloud.dtype == np.float32
          and cloud.min() >= 0.0 and cloud.max() <= 1.0)
    print(_row("step 6 - snow + cloud fields shape + ranges",
               ok, f"snow={snow.shape}/{snow.sum()} cloud={cloud.shape} max={float(cloud.max()):.3f}"))
    if not ok:
        failures += 1

    # Step 7 — enhance_render preserves shape, modifies values at night.
    base_rgb = np.full((64, 64, 3), 128, dtype=np.uint8)
    enhanced_day = enhance_render(
        base_rgb, solar=SolarState(altitude_deg=60.0, season_factor=0.0))
    enhanced_night = enhance_render(
        base_rgb, solar=SolarState(altitude_deg=-30.0, season_factor=0.0))
    night_mean = float(enhanced_night.astype(np.float32).mean())
    day_mean = float(enhanced_day.astype(np.float32).mean())
    ok = (enhanced_day.shape == base_rgb.shape
          and enhanced_night.shape == base_rgb.shape
          and night_mean < day_mean - 10.0)  # night darker
    print(_row("step 7 - enhance_render darkens night",
               ok, f"day_mean={day_mean:.1f} night_mean={night_mean:.1f}"))
    if not ok:
        failures += 1

    # Step 8 — determinism.
    e1 = enhance_render(base_rgb, solar=SolarState(altitude_deg=-2.0,
                                                       season_factor=0.5),
                         snow_field=snow, cloud_field=cloud)
    e2 = enhance_render(base_rgb, solar=SolarState(altitude_deg=-2.0,
                                                       season_factor=0.5),
                         snow_field=snow, cloud_field=cloud)
    ok = np.array_equal(e1, e2)
    print(_row("step 8 - determinism on enhance_render",
               ok, f"match={np.array_equal(e1, e2)}"))
    if not ok:
        failures += 1

    # Step 9 — render_macro_with_atmosphere writes PNG.
    with tempfile.TemporaryDirectory() as td:
        path_day = os.path.join(td, "atm_day.png")
        path_night = os.path.join(td, "atm_night.png")
        rgb_day = render_macro_with_atmosphere(
            world, sim_tick_noon, latitude_deg=0.0, path=path_day)
        rgb_night = render_macro_with_atmosphere(
            world, sim_tick_midnight, latitude_deg=0.0, path=path_night)
        ok = (os.path.exists(path_day) and os.path.exists(path_night)
              and os.path.getsize(path_day) > 100
              and os.path.getsize(path_night) > 100
              and not np.array_equal(rgb_day, rgb_night)
              and rgb_day.shape == rgb_night.shape)
        print(_row("step 9 - render_macro_with_atmosphere day≠night PNG",
                   ok, f"day_size={os.path.getsize(path_day)}B "
                       f"night_size={os.path.getsize(path_night)}B"))
        if not ok:
            failures += 1

    # Diagnostic dump.
    print(f"\nAtmosphere summary @ sim_tick=0  : {atmosphere_summary(0)}")
    print(f"Atmosphere summary @ noon midyear : {atmosphere_summary(sim_tick_noon, latitude_deg=46.5)}")

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
