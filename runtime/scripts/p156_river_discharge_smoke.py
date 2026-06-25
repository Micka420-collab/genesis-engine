"""P156 — Wave 64 live river-discharge coupling smoke (live elevation -> river).

Closes the hydrology half of D11 (AUDIT-DELTA-2026-06-23). ``chunk_hydrology``
paints a river stripe at a hard-coded 800 L depth — blind to how much water the
basin actually carries — and ``discharge_observer`` computes the real
mass-conserving discharge but only observes it. ``river_discharge`` is the wire:
the exact hydrological partner of the orographic temperature coupling. It
re-reads the live macro ``elevation_m`` and turns its drift into a river
discharge response through the temperature/ET channel (uplift cools -> less ET
-> more runoff -> the river swells; erosion warms -> less runoff -> the river
shrinks, and dries when ET hits the precipitation ceiling).

Steps (on a REAL warm Genesis world so basins are ET-active):
  1. Public API surface + diagnostics present.
  2. Static world : a full apply leaves every river cell untouched (back-compat).
  3. Uplift (+1 km) : painted river water rises (discharge ratio > 1).
  4. Erosion (-1.5 km) : painted river water falls (ratio < 1).
  5. Strong warming (-4 km) : the channel runs nearly dry (emergent wadi).
  6. Reversible : returning the elevation to baseline restores the river exactly.
  7. Read-only contract : macro temp / precip / flow_dir untouched.
  8. The driving discharge is mass-conserving (Sum Q[sinks] == Sum runoff).
  9. Determinism : same seed + same uplift -> identical river water.
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

from engine.sim import Simulation, SimConfig                           # noqa: E402
from engine.world_genesis import (GenesisParams, generate_world,        # noqa: E402
                                   make_anchor)
from engine.chunk_hydrology import (install_chunk_hydrology,            # noqa: E402
                                    apply_to_existing_chunks,
                                    RIVER_WATER_LITRES)
from engine.discharge_observer import (DischargeConfig, route_runoff,   # noqa: E402
                                       runoff_field_m3s)
from engine.earth_laws import LAPSE_K_PER_M                             # noqa: E402
from engine.river_discharge import (install_river_discharge,            # noqa: E402
                                    apply_river_discharge_step,
                                    river_discharge_state, _discharge_field)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:60s} {detail}"


def _make_world(seed=0xC0FFEE_1234):
    gp = GenesisParams(seed=seed & 0xFFFFFFFFFFFFFFFF, resolution=64,
                       n_plates=10, erosion_iters=20, rain_iters=5,
                       river_threshold_cells=30.0, lat_span_deg=30.0)
    return generate_world(gp)


def _responsive_river_cell(world):
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


def _build(world, *, sim_seed=0xABCD_1234, enabled=True):
    ix, iy = _responsive_river_cell(world)
    anchor = _anchor_at(world, ix, iy)
    cfg = SimConfig(name="p156_river", seed=sim_seed & 0xFFFFFFFFFFFFFFFF,
                    founders=2, max_agents=4, bounds_km=(0.5, 0.5),
                    spawn_radius_m=50.0, drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    sim.streamer.set_genesis(anchor)
    sim.streamer.clear_cache()
    sim.bootstrap()
    install_chunk_hydrology(sim, anchor)
    apply_to_existing_chunks(sim)
    state = install_river_discharge(sim, anchor, enabled=enabled)
    return sim, anchor, state


def _river_chunk(sim):
    for coord, chunk in sim.streamer.cache.items():
        mask = np.asarray(chunk.water) >= np.float32(RIVER_WATER_LITRES)
        if bool(mask.any()):
            return coord, chunk, mask.copy()
    return None, None, None


def _wsum(chunk, mask):
    return float(np.asarray(chunk.water)[mask].sum())


def main() -> int:
    print("=" * 78)
    print("P156 — Wave 64 live river-discharge coupling (live elevation -> river)")
    print("=" * 78)
    failures = 0

    world = _make_world()
    print(f"        diag = land={world.diagnostics['land_fraction']:.2f} "
          f"rivers={world.diagnostics['river_cells']} "
          f"Tmean={float(np.asarray(world.temp_c)[world.elevation_m > 0].mean()):.1f}C")

    # ----- Step 1 — API surface ----------------------------------------
    sim, anchor, state = _build(world)
    coord, chunk, mask = _river_chunk(sim)
    rep = river_discharge_state(sim)
    ok = (coord is not None and rep["installed"] is True
          and rep["enabled"] is True and "max_ratio_seen" in rep
          and state.base_discharge is not None)
    print(_row("step 1 - API + diagnostics + painted river chunk", ok,
               f"river_cells_in_chunk={int(mask.sum()) if mask is not None else 0}"))
    failures += 0 if ok else 1
    if coord is None:
        print("RESULT: 0/9 PASS (no river chunk)")
        return 1

    base_water = np.asarray(chunk.water).copy()
    base = _wsum(chunk, mask)

    # ----- Step 2 — static world : strict no-op ------------------------
    res = apply_river_discharge_step(sim)
    ok = (res["changed"] == 0.0 and res["chunks_scaled"] == 0.0
          and np.array_equal(np.asarray(chunk.water), base_water))
    print(_row("step 2 - static world: river untouched (back-compat)", ok,
               f"changed={res['changed']}"))
    failures += 0 if ok else 1

    # ----- Step 3 — uplift swells the river ----------------------------
    anchor.world.elevation_m = (anchor.world.elevation_m
                                + np.float32(1000.0)).astype(np.float32)
    res = apply_river_discharge_step(sim)
    up = _wsum(chunk, mask)
    ok = (res["changed"] == 1.0 and res["max_ratio"] > 1.0 and up > base)
    print(_row("step 3 - uplift +1km swells river (ratio > 1)", ok,
               f"base={base:.0f} uplift={up:.0f} ratio={res.get('max_ratio', 0):.3f}"))
    failures += 0 if ok else 1

    # ----- Step 4 — erosion shrinks the river --------------------------
    # Fresh build to keep this check independent of step 3's uplift.
    sim4, anchor4, state4 = _build(_make_world())
    coord4, chunk4, mask4 = _river_chunk(sim4)
    base4 = _wsum(chunk4, mask4)
    anchor4.world.elevation_m = (anchor4.world.elevation_m
                                 - np.float32(1500.0)).astype(np.float32)
    res = apply_river_discharge_step(sim4)
    dn = _wsum(chunk4, mask4)
    ok = (res["changed"] == 1.0 and res["min_ratio"] < 1.0 and dn < base4)
    print(_row("step 4 - erosion -1.5km shrinks river (ratio < 1)", ok,
               f"base={base4:.0f} erosion={dn:.0f} ratio={res.get('min_ratio', 1):.3f}"))
    failures += 0 if ok else 1

    # ----- Step 5 — strong warming dries the channel -------------------
    sim5, anchor5, state5 = _build(_make_world())
    coord5, chunk5, mask5 = _river_chunk(sim5)
    base5 = _wsum(chunk5, mask5)
    anchor5.world.elevation_m = (anchor5.world.elevation_m
                                 - np.float32(4000.0)).astype(np.float32)
    apply_river_discharge_step(sim5)
    dry = _wsum(chunk5, mask5)
    ok = dry < base5 * 0.5
    print(_row("step 5 - strong warming dries channel (< 0.5x)", ok,
               f"base={base5:.0f} dry={dry:.0f}"))
    failures += 0 if ok else 1

    # ----- Step 6 — reversible -----------------------------------------
    sim6, anchor6, state6 = _build(_make_world())
    coord6, chunk6, mask6 = _river_chunk(sim6)
    base6w = np.asarray(chunk6.water).copy()
    base6e = anchor6.world.elevation_m.copy()
    anchor6.world.elevation_m = (anchor6.world.elevation_m
                                 + np.float32(1000.0)).astype(np.float32)
    apply_river_discharge_step(sim6)
    moved = not np.array_equal(np.asarray(chunk6.water), base6w)
    anchor6.world.elevation_m = base6e
    res = apply_river_discharge_step(sim6)
    restored = np.array_equal(np.asarray(chunk6.water), base6w)
    ok = moved and res["changed"] == 0.0 and restored
    print(_row("step 6 - revert to baseline restores river exactly", ok,
               f"moved={moved} restored={restored}"))
    failures += 0 if ok else 1

    # ----- Step 7 — read-only macro contract ---------------------------
    sim7, anchor7, state7 = _build(_make_world())
    t0 = anchor7.world.temp_c.copy()
    p0 = anchor7.world.precip_mm.copy()
    fd0 = anchor7.world.flow_dir.copy()
    anchor7.world.elevation_m = (anchor7.world.elevation_m
                                 + np.float32(1000.0)).astype(np.float32)
    apply_river_discharge_step(sim7)
    ok = (np.array_equal(anchor7.world.temp_c, t0)
          and np.array_equal(anchor7.world.precip_mm, p0)
          and np.array_equal(anchor7.world.flow_dir, fd0))
    print(_row("step 7 - read-only: macro temp/precip/flow_dir untouched", ok, ""))
    failures += 0 if ok else 1

    # ----- Step 8 — mass conservation of the driving discharge ---------
    elev = np.asarray(anchor7.world.elevation_m, dtype=np.float64)
    d_elev = np.maximum(elev, 0.0) - np.maximum(state7.base_elev_m, 0.0)
    temp_eff = state7.base_temp_c - LAPSE_K_PER_M * d_elev
    runoff = runoff_field_m3s(state7.base_precip_mm, temp_eff,
                              state7.cell_km, state7.runoff_cfg)
    disc = _discharge_field(state7, elev)
    fd = np.asarray(anchor7.world.flow_dir, dtype=np.uint8)
    is_sink = (fd == 255) | (fd > 7)
    resid = abs(float(runoff.sum()) - float(disc[is_sink].sum())) \
        / max(float(runoff.sum()), 1e-9)
    ok = resid < 1e-6
    print(_row("step 8 - driving discharge mass-conserving", ok,
               f"residual={resid:.2e}"))
    failures += 0 if ok else 1

    # ----- Step 9 — determinism ----------------------------------------
    sums = []
    for _ in range(2):
        s, a, stt = _build(_make_world(seed=0x5EED_0001), sim_seed=0x2468_ACE0)
        c, ch, m = _river_chunk(s)
        a.world.elevation_m = (a.world.elevation_m
                               + np.float32(1000.0)).astype(np.float32)
        apply_river_discharge_step(s)
        sums.append(_wsum(ch, m))
    ok = sums[0] == sums[1]
    print(_row("step 9 - determinism: same seed+uplift -> same river", ok,
               f"sums={sums}"))
    failures += 0 if ok else 1

    print("-" * 78)
    passed = 9 - failures
    print(f"  RESULT: {passed}/9 checks passed")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
