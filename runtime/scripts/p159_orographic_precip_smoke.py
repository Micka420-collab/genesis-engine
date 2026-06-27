"""P159 — Wave 65 orographic precipitation coupling smoke (live relief -> rain).

Closes the precipitation half of D11 backlog #7 (AUDIT-DELTA-2026-06-23). The
orographic *temperature* coupling already turns live ``elevation_m`` drift into
a per-chunk temperature anomaly at the lapse rate; its named partner —
``precip_mm`` — was frozen at the install snapshot. ``climate_biome`` now
recomputes the macro orographic rainfall field for the live relief (re-using
``world_genesis._orographic_precipitation`` verbatim, SSOT) and feeds each chunk
``baseline + (field(live_elev) - field(baseline_elev))`` as the effective
rainfall driving the warming dry/wet biome branch. A rising range wrings extra
rain from its windward flank and casts a rain shadow on its lee.

Steps (on a REAL warm Genesis world, anchored at the most precip-responsive
land cell — the saturated global peak rains out and is a poor probe):
  1. Public API surface + reporter fields present.
  2. SSOT : recompute at the baseline elevation reproduces world.precip_mm.
  3. Static world : effective precip == baseline everywhere (back-compat).
  4. A tapered uplift makes the windward side wetter AND the lee drier.
  5. Effective precip tracks the live relief (the proxy is no longer frozen).
  6. The warming biome ladder consumes the effective precip (the wire is real).
  7. Reversible : reverting the elevation restores the baseline precip exactly.
  8. Read-only contract : world.precip_mm is never written.
  9. Determinism : same seed + same relief -> identical effective precip.
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
from engine.world import Biome                                         # noqa: E402
from engine.world_genesis import (GenesisParams, generate_world,        # noqa: E402
                                   make_anchor, _base_precip_by_latitude,
                                   _orographic_precipitation)
from engine.climate_biome import (install_climate_biome,                # noqa: E402
                                  apply_climate_biome_step,
                                  climate_biome_state,
                                  _orographic_precip_field,
                                  _shift_biomes_array)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:60s} {detail}"


def _make_world(seed=0xD11_BEEF):
    gp = GenesisParams(seed=seed & 0xFFFFFFFFFFFFFFFF, resolution=64,
                       n_plates=10, erosion_iters=20, rain_iters=5,
                       lat_span_deg=30.0)
    return generate_world(gp)


def _oro_field(world, elev):
    belt = _base_precip_by_latitude(world.params, world.latitude_deg)
    return _orographic_precipitation(
        world.params, np.asarray(elev, dtype=np.float32), belt,
        world.wind_u, world.wind_v, world.params.sea_level_m)


def _steepen(elev, sea, factor):
    """Amplify (or relax) all land relief about sea level by ``factor`` — a
    relief change that perturbs every windward/lee slope at once."""
    out = np.asarray(elev, dtype=np.float32).copy()
    land = out > sea
    out[land] = (sea + (out[land] - sea) * factor).astype(np.float32)
    return out


def _high_land_cell(world):
    elev = world.elevation_m
    score = np.where(elev > 0.0, elev, -1e9)
    iy, ix = np.unravel_index(int(np.argmax(score)), score.shape)
    return int(ix), int(iy)


def _responsive_cell(world):
    """Land cell whose orographic rainfall responds most to a relief steepening
    (mirrors p156's responsive-river-cell probe — the global peak is rained out
    and a poor probe)."""
    sea = world.params.sea_level_m
    f0 = np.asarray(world.precip_mm, dtype=np.float64)
    f1 = _oro_field(world, _steepen(world.elevation_m, sea, 1.6)).astype(np.float64)
    land = np.asarray(world.elevation_m) > sea
    score = np.where(land, np.abs(f1 - f0), -1.0)
    iy, ix = np.unravel_index(int(np.argmax(score)), score.shape)
    return int(ix), int(iy)


def _anchor_at(world, ix, iy):
    cell_km = world.params.map_size_km / world.params.resolution
    return make_anchor(world, sim_origin_macro_km=((ix + 0.5) * cell_km,
                                                   (iy + 0.5) * cell_km))


def _build(world, *, sim_seed=0xABCD_5678, precip=True):
    ix, iy = _responsive_cell(world)
    anchor = _anchor_at(world, ix, iy)
    cfg = SimConfig(name="p159_oro_precip", seed=sim_seed & 0xFFFFFFFFFFFFFFFF,
                    founders=2, max_agents=4, bounds_km=(0.5, 0.5),
                    spawn_radius_m=50.0, drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    sim.streamer.set_genesis(anchor)
    sim.streamer.clear_cache()
    sim.bootstrap()
    state = install_climate_biome(sim, anchor, anomaly_source="macro",
                                  transition_speed=1.0,
                                  orographic_precip_coupling=precip)
    return sim, anchor, state


def main() -> int:
    print("=" * 78)
    print("P159 — Wave 65 orographic precipitation coupling (live relief -> rain)")
    print("=" * 78)
    failures = 0

    world = _make_world()
    print(f"        diag = land={world.diagnostics['land_fraction']:.2f} "
          f"precip[{world.diagnostics['min_precip_land_mm']:.0f}.."
          f"{world.diagnostics['max_precip_mm']:.0f}]mm")

    # ----- Step 1 — API surface + reporter -----------------------------
    sim, anchor, state = _build(world)
    rep = climate_biome_state(sim)
    ok = (rep["installed"] is True
          and rep["orographic_precip_coupling"] is True
          and "orographic_precip_anomaly_mm" in rep
          and state.base_elev_field is not None
          and len(sim.streamer.cache) > 0)
    print(_row("step 1 - API + reporter + elevation baseline", ok,
               f"chunks={len(sim.streamer.cache)}"))
    failures += 0 if ok else 1

    # ----- Step 2 — SSOT reproduction ----------------------------------
    f0 = _orographic_precip_field(state, state.base_elev_field)
    ok = np.array_equal(f0, anchor.world.precip_mm)
    print(_row("step 2 - recompute(baseline) == world.precip_mm (SSOT)", ok, ""))
    failures += 0 if ok else 1

    # ----- Step 3 — static world : no change ---------------------------
    res = apply_climate_biome_step(sim)
    static_ok = (res["orographic_precip_anomaly_mm"] == 0.0
                 and all(abs(state.current_precip_proxy[c]
                             - state.chunk_precip_proxy[c]) < 1e-9
                         for c in sim.streamer.cache))
    print(_row("step 3 - static world: effective precip == baseline", static_ok,
               f"anomaly_mm={res['orographic_precip_anomaly_mm']:.3f}"))
    failures += 0 if static_ok else 1

    # ----- Step 4 — windward gain + lee rain shadow (field level) -------
    # A localised mountain raised in a still-wet region: its windward foot
    # wrings out extra rain while its lee falls into a fresh rain shadow. (A
    # global steepening only shows the gain — the existing lee is already at the
    # precip floor and cannot dry further.)
    sea = world.params.sea_level_m
    ix4, iy4 = _high_land_cell(world)
    e2 = state.base_elev_field.copy()
    e2[max(0, iy4 - 5):iy4 + 6, max(0, ix4 - 5):ix4 + 6] += np.float32(1500.0)
    d = _orographic_precip_field(state, e2) - f0
    ok = float(d.max()) > 0.0 and float(d.min()) < 0.0
    print(_row("step 4 - uplift: windward wetter + lee rain shadow", ok,
               f"dP[{d.min():.0f}..{d.max():.0f}]mm"))
    failures += 0 if ok else 1

    # ----- Step 5 — effective precip tracks live relief ----------------
    sim5, anchor5, state5 = _build(_make_world())
    apply_climate_biome_step(sim5)               # baseline proxies
    frozen = dict(state5.chunk_precip_proxy)
    anchor5.world.elevation_m = _steepen(anchor5.world.elevation_m, sea, 1.6)
    res5 = apply_climate_biome_step(sim5)
    moved = any(abs(state5.current_precip_proxy[c] - frozen[c]) > 1.0
                for c in sim5.streamer.cache)
    ok = res5["orographic_precip_anomaly_mm"] != 0.0 and moved
    print(_row("step 5 - effective precip tracks live relief", ok,
               f"anomaly_mm={res5['orographic_precip_anomaly_mm']:.1f}"))
    failures += 0 if ok else 1

    # ----- Step 6 — warming ladder consumes effective precip -----------
    sim6, anchor6, state6 = _build(_make_world())
    coord6 = next(iter(sim6.streamer.cache))
    ch6 = sim6.streamer.cache[coord6]
    ch6.biome = np.full_like(ch6.biome, int(Biome.SAVANNA))
    anchor6.world.elevation_m = _steepen(anchor6.world.elevation_m, sea, 0.4)  # erode -> warm
    apply_climate_biome_step(sim6)
    eff6 = state6.current_precip_proxy[coord6]
    expected = int(_shift_biomes_array(
        np.array([int(Biome.SAVANNA)], dtype=np.uint8), True, eff6)[0])
    ok = bool((sim6.streamer.cache[coord6].biome == expected).all())
    print(_row("step 6 - warming ladder uses effective precip", ok,
               f"eff={eff6:.0f}mm -> biome {expected}"))
    failures += 0 if ok else 1

    # ----- Step 7 — reversible -----------------------------------------
    sim7, anchor7, state7 = _build(_make_world())
    base7e = anchor7.world.elevation_m.copy()
    anchor7.world.elevation_m = _steepen(anchor7.world.elevation_m, sea, 1.6)
    r_up = apply_climate_biome_step(sim7)
    anchor7.world.elevation_m = base7e
    r_rev = apply_climate_biome_step(sim7)
    restored = all(abs(state7.current_precip_proxy[c]
                       - state7.chunk_precip_proxy[c]) < 1e-6
                   for c in sim7.streamer.cache)
    ok = (r_up["orographic_precip_anomaly_mm"] != 0.0
          and r_rev["orographic_precip_anomaly_mm"] == 0.0 and restored)
    print(_row("step 7 - revert relief restores baseline precip", ok,
               f"up={r_up['orographic_precip_anomaly_mm']:.1f} rev={r_rev['orographic_precip_anomaly_mm']:.1f}"))
    failures += 0 if ok else 1

    # ----- Step 8 — read-only macro contract ---------------------------
    sim8, anchor8, state8 = _build(_make_world())
    p0 = anchor8.world.precip_mm.copy()
    anchor8.world.elevation_m = _steepen(anchor8.world.elevation_m, sea, 1.6)
    apply_climate_biome_step(sim8)
    ok = np.array_equal(anchor8.world.precip_mm, p0)
    print(_row("step 8 - read-only: world.precip_mm untouched", ok, ""))
    failures += 0 if ok else 1

    # ----- Step 9 — determinism ----------------------------------------
    proxies = []
    for _ in range(2):
        s, a, st = _build(_make_world(seed=0x5EED_0159), sim_seed=0x2468_ACE0)
        a.world.elevation_m = _steepen(a.world.elevation_m, sea, 1.6)
        apply_climate_biome_step(s)
        proxies.append(tuple(sorted(st.current_precip_proxy.items())))
    ok = proxies[0] == proxies[1]
    print(_row("step 9 - determinism: same seed+relief -> same precip", ok,
               f"chunks={len(proxies[0])}"))
    failures += 0 if ok else 1

    print("-" * 78)
    passed = 9 - failures
    print(f"  RESULT: {passed}/9 checks passed")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
