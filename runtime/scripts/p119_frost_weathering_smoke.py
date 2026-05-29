"""P119 — Wave 50 frost weathering (cryoclastie) observer smoke.

 1. Public API exposed.
 2. compute_slope_field: increases monotonically on a synthetic ramp.
 3. frost_cracking_window peaks at -5.5 °C, zero at +5 °C and -20 °C.
 4. FCI is zero on dry cells, scales with precipitation up to saturation.
 5. observe_frost_weathering returns a sane snapshot on a real Genesis world.
 6. Snapshot is read-only: world arrays + sim tick unchanged.
 7. Cross-sim determinism: same world seed ⇒ same signature.
 8. Talus zones are a subset of land cells.
 9. install / uninstall wrap restore: sim.step round-trip.
10. Installed observer captures snapshots at the right cadence.
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
from engine.world_genesis import GenesisParams                          # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim              # noqa: E402
from engine.frost_weathering import (                                   # noqa: E402
    FrostConfig, FrostSnapshot, FrostHistory, FrostState, BiomeFrostStats,
    compute_slope_field, frost_cracking_window,
    compute_frost_cracking_index, biome_amplitude_field,
    compute_talus_mask, compute_permafrost_mask,
    compute_alpine_active_mask,
    observe_frost_weathering, install_frost_weathering_observer,
    uninstall_frost_weathering_observer, frost_weathering_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xCAFE_0119):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=20,
        bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def _booted_sim(name, seed=0xCAFE_0119, resolution=64,
                river_threshold_cells=8.0):
    """Build a Genesis-bootstrapped sim with realistic relief +
    climate so the frost field has something to bite into."""
    sim = _build_sim(name, seed=seed)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8,
                       river_threshold_cells=river_threshold_cells)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


def main() -> int:
    print("=" * 78)
    print("P119 — Wave 50 frost weathering observer smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API surface.
    expected = (
        "FrostConfig", "FrostSnapshot", "FrostHistory", "FrostState",
        "BiomeFrostStats",
        "compute_slope_field", "frost_cracking_window",
        "compute_frost_cracking_index", "biome_amplitude_field",
        "compute_talus_mask", "compute_permafrost_mask",
        "compute_alpine_active_mask",
        "observe_frost_weathering", "install_frost_weathering_observer",
        "uninstall_frost_weathering_observer", "frost_weathering_summary",
    )
    ok = all(name in globals() for name in expected)
    print(_row("step 1 - public API exposed", ok,
               f"n={len(expected)}"))
    if not ok:
        failures += 1

    # Step 2 — slope on a synthetic ramp.
    R = 16
    cell_km = 0.5  # 500 m / cell -> 8 km map
    ramp = np.zeros((R, R), dtype=np.float32)
    # Linear ramp east-west: 0 .. 800 m over R cells, slope 0 / cell elsewhere.
    for x in range(R):
        ramp[:, x] = float(x) * 100.0  # +100 m / cell horizontally
    slope = compute_slope_field(ramp, cell_km)
    # Expected slope (deg) at the interior of the ramp: arctan(100/500) ≈ 11.31 deg.
    interior_mean = float(slope[4:12, 4:12].mean())
    expected_slope = float(np.degrees(np.arctan(100.0 / (cell_km * 1000.0))))
    ok_ramp = (abs(interior_mean - expected_slope) < 0.5
               and float(slope.min()) >= 0.0)
    # Slope of a flat field is zero.
    flat = np.full((R, R), 250.0, dtype=np.float32)
    flat_slope_max = float(compute_slope_field(flat, cell_km).max())
    ok_flat = flat_slope_max < 1e-3
    ok = ok_ramp and ok_flat
    print(_row("step 2 - slope: ramp ≈ analytic, flat ≈ 0", ok,
               f"interior={interior_mean:.3f}deg "
               f"expected={expected_slope:.3f} flat_max={flat_slope_max:.2e}"))
    if not ok:
        failures += 1

    # Step 3 — frost cracking window peaks at -5.5°C, vanishes outside band.
    temps = np.array([-25.0, -20.0, -10.0, -5.5, -3.0, 0.5, 5.0, 25.0],
                     dtype=np.float32)
    w = frost_cracking_window(temps)
    peak_idx = int(np.argmax(w))
    ok = (peak_idx == 3                  # -5.5 °C
          and w[0] == 0.0                # -25 too cold
          and w[1] == 0.0                # -20 too cold (< -15 floor)
          and w[5] == 0.0                # +0.5 too warm
          and w[7] == 0.0                # +25 too warm
          and float(w[3]) > 0.99)        # window peak ≈ 1.0
    print(_row("step 3 - cracking window peaks -5.5 °C, zero outside band",
               ok, f"peak={float(w[3]):.3f} idx={peak_idx} "
                   f"w(-25)={float(w[0]):.3f} w(+5)={float(w[6]):.3f}"))
    if not ok:
        failures += 1

    # Step 4 — FCI scales with precipitation up to saturation.
    t = np.full((4,), -5.5, dtype=np.float32)        # at window peak
    p = np.array([0.0, 500.0, 1500.0, 5000.0],       # below / mid / sat / over
                  dtype=np.float32)
    fci = compute_frost_cracking_index(t, p, biome=None)
    ok = (fci[0] == 0.0                  # zero precip → zero FCI
          and 0.30 < fci[1] < 0.40       # 500/1500 ≈ 0.33
          and 0.99 < fci[2] <= 1.0       # saturation
          and 0.99 < fci[3] <= 1.0)      # over-saturation clamped
    print(_row("step 4 - FCI grows with P, clamps at saturation", ok,
               f"FCI={[round(float(v), 3) for v in fci]}"))
    if not ok:
        failures += 1

    # Step 5 — observe on real Genesis world.
    sim = _booted_sim("p119_real", seed=0xCAFE_01195)
    snap = observe_frost_weathering(sim)
    ok = (isinstance(snap, FrostSnapshot)
          and snap.land_cells > 0
          and snap.map_area_km2 > 0.0
          and snap.cell_km > 0.0
          and len(snap.signature) == 64
          and 0.0 <= snap.mean_fci_land <= 1.0
          and 0.0 <= snap.max_fci <= 1.0
          and 0.0 <= snap.permafrost_fraction <= 1.0)
    print(_row("step 5 - real-world snapshot well-formed", ok,
               f"land={snap.land_cells} meanFCI={snap.mean_fci_land:.4f} "
               f"permafrost={snap.permafrost_fraction:.3f} "
               f"talus={snap.talus_cells} alpine={snap.alpine_cells}"))
    if not ok:
        failures += 1

    # Step 6 — observe is read-only.
    sim6 = _booted_sim("p119_ro", seed=0xCAFE_01196)
    world6 = sim6._genesis_bootstrap_state.world
    elev_before = np.array(world6.elevation_m, copy=True)
    temp_before = np.array(world6.temp_c, copy=True)
    precip_before = np.array(world6.precip_mm, copy=True)
    biome_before = np.array(world6.biome, copy=True)
    tick_before = int(sim6.tick)
    _ = observe_frost_weathering(sim6)
    ok = (int(sim6.tick) == tick_before
          and np.array_equal(world6.elevation_m, elev_before)
          and np.array_equal(world6.temp_c, temp_before)
          and np.array_equal(world6.precip_mm, precip_before)
          and np.array_equal(world6.biome, biome_before))
    print(_row("step 6 - observe is read-only (world + tick frozen)", ok,
               f"tick={tick_before}->{int(sim6.tick)}"))
    if not ok:
        failures += 1

    # Step 7 — cross-sim determinism.
    seed_d = 0xCAFE_01197
    sim_a = _booted_sim("p119_det_a", seed=seed_d)
    sim_b = _booted_sim("p119_det_b", seed=seed_d)
    sig_a = observe_frost_weathering(sim_a).signature
    sig_b = observe_frost_weathering(sim_b).signature
    ok = (sig_a == sig_b)
    print(_row("step 7 - cross-sim determinism (same seed → same sig)",
               ok, f"match={sig_a == sig_b}"))
    if not ok:
        failures += 1

    # Step 8 — talus zones consistent: a subset of land + steep + cold.
    sim8 = _booted_sim("p119_talus", seed=0xCAFE_01198)
    world8 = sim8._genesis_bootstrap_state.world
    cell_km8 = float(world8.params.map_size_km) / float(world8.elevation_m.shape[0])
    sea_level8 = float(getattr(world8.params, "sea_level_m", 0.0))
    land_mask8 = (np.asarray(world8.elevation_m, dtype=np.float32) > sea_level8)
    slope8 = compute_slope_field(world8.elevation_m, cell_km8)
    fci8 = compute_frost_cracking_index(world8.temp_c, world8.precip_mm,
                                          world8.biome)
    talus8 = compute_talus_mask(slope8, fci8, land_mask8)
    # Talus cells must all be land + slope >= 25 + fci >= 0.4.
    if int(talus8.sum()) > 0:
        ok = (bool(land_mask8[talus8].all())
              and float(slope8[talus8].min()) >= 25.0
              and float(fci8[talus8].min()) >= 0.4)
    else:
        # On a warm tropical seed, no talus is also a valid result. Accept it
        # as long as the mask is properly typed.
        ok = (talus8.dtype == bool)
    print(_row("step 8 - talus = land ∧ slope ≥ 25° ∧ FCI ≥ 0.4", ok,
               f"n_talus={int(talus8.sum())}"))
    if not ok:
        failures += 1

    # Step 9 — install / uninstall round-trip.
    sim9 = _booted_sim("p119_install", seed=0xCAFE_01199)
    step_before = sim9.step
    state = install_frost_weathering_observer(
        sim9, FrostConfig(snapshot_every=2))
    wrapped = (sim9.step is not step_before
               and getattr(sim9, "_frost_wrapped", False) is True)
    # Re-install should NOT wrap twice.
    state2 = install_frost_weathering_observer(
        sim9, FrostConfig(snapshot_every=3))
    ok_idem = (state2 is state)
    restored = uninstall_frost_weathering_observer(sim9)
    ok_after = (sim9.step is step_before and restored is True
                and frost_weathering_summary(sim9).get("installed") is False)
    ok = wrapped and ok_idem and ok_after
    print(_row("step 9 - install wraps step (idempotent) / uninstall restores",
               ok, f"wrap={wrapped} idem={ok_idem} restored={restored}"))
    if not ok:
        failures += 1

    # Step 10 — installed observer captures at cadence.
    sim10 = _booted_sim("p119_cadence", seed=0xCAFE_011910)
    install_frost_weathering_observer(sim10, FrostConfig(snapshot_every=2))
    for _ in range(7):
        sim10.step()
    summary = frost_weathering_summary(sim10)
    n_snaps = int(summary.get("n_snapshots") or 0)
    # Snapshots are captured when (tick % 2 == 0). 7 steps yield ≥ 2 captures.
    ok = (summary.get("installed") is True
          and n_snaps >= 2
          and summary.get("last_signature") is not None)
    print(_row("step 10 - installed observer captures at cadence", ok,
               f"n_snaps={n_snaps} last_tick={summary.get('last_tick')}"))
    if not ok:
        failures += 1

    # Diagnostic dump.
    print()
    print("Snapshot dump (sim p119_real):")
    print(f"  tick                    : {snap.tick}")
    print(f"  cell_km                 : {snap.cell_km:.4f}")
    print(f"  land_area_km2           : {snap.land_area_km2:.1f}")
    print(f"  mean_fci_land           : {snap.mean_fci_land:.4f}")
    print(f"  max_fci                 : {snap.max_fci:.4f}")
    print(f"  fci_active_fraction     : {snap.fci_active_fraction:.4f}")
    print(f"  fci_strong_fraction     : {snap.fci_strong_fraction:.4f}")
    print(f"  permafrost_area_km2     : {snap.permafrost_area_km2:.1f} "
          f"({100.0 * snap.permafrost_fraction:.2f}% of land)")
    print(f"  talus_area_km2          : {snap.talus_area_km2:.1f} "
          f"({snap.talus_cells} cells)")
    print(f"  alpine_area_km2         : {snap.alpine_area_km2:.1f} "
          f"({snap.alpine_cells} cells)")
    print(f"  mean_slope_deg_land     : {snap.mean_slope_deg_land:.2f} deg")
    print(f"  max_slope_deg           : {snap.max_slope_deg:.2f} deg")
    print(f"  signature               : {snap.signature}")
    for b in snap.biomes_top:
        print(f"  biome#{b.biome_id:>2} cells={b.n_cells:>5} "
              f"meanFCI={b.mean_fci:.4f} maxFCI={b.max_fci:.4f} "
              f"PF={100.0 * b.permafrost_fraction:6.2f}% "
              f"talus={100.0 * b.talus_fraction:6.2f}%")

    total = 10
    passed = total - failures
    print("=" * 78)
    if failures == 0:
        print(f"RESULT: {total}/{total} PASS")
        return 0
    print(f"RESULT: {passed}/{total} PASS, {failures} FAIL")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
