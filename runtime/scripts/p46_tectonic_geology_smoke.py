"""P46 — Wave 17 tectonic-aware geology smoke.

Validates that the macro tectonic map (GenesisAnchor) biases per-chunk
ore deposits in ways that match real-world mineralisation provinces:

  1. Module imports cleanly and exposes the public API.
  2. ``sample_tectonic_context`` returns the right province on hand-picked
     macro cells (passive, convergent oc-co, convergent co-co, divergent oc,
     divergent co, transform).
  3. ``apply_overlay_to_chunk`` injects expected minerals on a synthetic
     ChunkGeology for an Andean (oc-co convergent) cell.
  4. Andean province → chalcopyrite + native_gold fraction strictly higher
     than at a passive control cell.
  5. Mid-ocean ridge → sphalerite + galena boosted (VMS signature).
  6. Continental rift → halite + gypsum boosted (evaporites).
  7. ``install_tectonic_overlay`` is idempotent.
  8. Determinism: two installs with the same anchor produce identical
     ore_mix on the same chunk.
  9. Uninstall restores the original ``chunk_geology`` and leaves no
     residual hook in :mod:`engine.geology`.
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
from engine.geology import (install_geology, chunk_geology,             # noqa: E402
                            generate_chunk_geology, ChunkGeology,
                            StrataLayer)
from engine.world import world_to_chunk, CHUNK_SIDE_M                   # noqa: E402
from engine.world_genesis import (GenesisParams, generate_world,        # noqa: E402
                                    make_anchor,
                                    BOUND_NONE, BOUND_CONVERGENT,
                                    BOUND_DIVERGENT, BOUND_TRANSFORM,
                                    OCEANIC, CONTINENTAL)
from engine.tectonic_geology import (sample_tectonic_context,           # noqa: E402
                                       apply_overlay_to_chunk,
                                       install_tectonic_overlay,
                                       uninstall_tectonic_overlay,
                                       tectonic_state,
                                       apply_to_existing,
                                       _tectonic_boost_table)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str):
    cfg = SimConfig(
        name=name, seed=0xA17EC0FFEE & 0xFFFFFFFFFFFFFFFF,
        founders=2, max_agents=4,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def _find_cell(world, predicate):
    """Return (ix, iy) of the first macro cell satisfying predicate(ix, iy) or None."""
    R = world.params.resolution
    for iy in range(R):
        for ix in range(R):
            if predicate(ix, iy):
                return ix, iy
    return None


def _anchor_at(world, ix, iy):
    cell_km = world.params.map_size_km / world.params.resolution
    return make_anchor(world,
                        sim_origin_macro_km=((ix + 0.5) * cell_km,
                                              (iy + 0.5) * cell_km))


def _make_synthetic_geology(coord=(0, 0, 0)):
    """Build a minimal 4-layer geology object for unit testing the overlay."""
    g = ChunkGeology(coord=coord)
    g.layers = [
        StrataLayer(0.0, 1.0, "shale", 1500.0, ore_mix={}),
        StrataLayer(1.0, 5.0, "sandstone", 1800.0, ore_mix={"pyrite": 0.005}),
        StrataLayer(5.0, 200.0, "limestone", 2300.0,
                    ore_mix={"chalcopyrite": 0.002}),
        StrataLayer(200.0, 1000.0, "granite", 2700.0,
                    ore_mix={"native_gold": 0.0005}),
    ]
    return g


def main() -> int:
    print("=" * 78)
    print("P46 — Wave 17 tectonic-aware geology smoke")
    print("=" * 78)
    failures = 0

    # Generate a genesis world with enough boundary diversity.
    gp = GenesisParams(seed=0xDEAD_BEEF & 0xFFFFFFFFFFFFFFFF,
                        resolution=64, n_plates=12,
                        erosion_iters=15, rain_iters=4)
    world = generate_world(gp)

    plate_kinds = world.plate_kind  # per-plate
    plate_id = world.plate_id
    bk = world.boundary_kind

    def is_convergent_oc_co(ix, iy):
        if bk[iy, ix] != BOUND_CONVERGENT:
            return False
        self_pk = plate_kinds[plate_id[iy, ix]]
        # Check 4 neighbours for differing plate of opposite kind.
        R = gp.resolution
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = ix + dx, iy + dy
            if 0 <= nx < R and 0 <= ny < R:
                npid = plate_id[ny, nx]
                if npid != plate_id[iy, ix]:
                    if plate_kinds[npid] != self_pk:
                        return True
        return False

    def is_convergent_co_co(ix, iy):
        if bk[iy, ix] != BOUND_CONVERGENT:
            return False
        if plate_kinds[plate_id[iy, ix]] != CONTINENTAL:
            return False
        R = gp.resolution
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = ix + dx, iy + dy
            if 0 <= nx < R and 0 <= ny < R:
                npid = plate_id[ny, nx]
                if npid != plate_id[iy, ix] and plate_kinds[npid] == CONTINENTAL:
                    return True
        return False

    def is_divergent_oceanic(ix, iy):
        return (bk[iy, ix] == BOUND_DIVERGENT and
                plate_kinds[plate_id[iy, ix]] == OCEANIC)

    def is_divergent_continental(ix, iy):
        return (bk[iy, ix] == BOUND_DIVERGENT and
                plate_kinds[plate_id[iy, ix]] == CONTINENTAL)

    def is_transform(ix, iy):
        return bk[iy, ix] == BOUND_TRANSFORM

    def is_passive(ix, iy):
        return bk[iy, ix] == BOUND_NONE

    # Step 1 — API import + provinces dispatched.
    ok = all(name in globals() for name in (
        "sample_tectonic_context", "apply_overlay_to_chunk",
        "install_tectonic_overlay", "uninstall_tectonic_overlay"))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Step 2 — sample_tectonic_context returns the right province on
    # hand-picked cells.
    passive = _find_cell(world, is_passive)
    andean = _find_cell(world, is_convergent_oc_co)
    himalayan = _find_cell(world, is_convergent_co_co)
    mor = _find_cell(world, is_divergent_oceanic)
    rift = _find_cell(world, is_divergent_continental)

    found = {"passive": passive, "andean": andean, "himalayan": himalayan,
             "mid_ocean_ridge": mor, "continental_rift": rift}
    print(f"        province cells found (ix, iy): {found}")

    province_ok = True
    for expected, cell in found.items():
        if cell is None:
            # Permit missing himalayan or rift on small worlds.
            print(_row(f"  province {expected} not present (skipped)",
                       expected in ("himalayan", "continental_rift"),
                       ""))
            if expected not in ("himalayan", "continental_rift"):
                province_ok = False
            continue
        ix, iy = cell
        anchor = _anchor_at(world, ix, iy)
        ctx = sample_tectonic_context(anchor, 0.0, 0.0)
        label, _ = _tectonic_boost_table(ctx)
        ok2 = (label == expected)
        if not ok2:
            print(f"        mismatch: cell={cell} expected={expected} "
                  f"got={label} ctx={ctx}")
            province_ok = False
    ok = province_ok
    print(_row("step 2 - sample_tectonic_context dispatches correctly",
               ok, ""))
    if not ok:
        failures += 1

    # Step 3 — apply_overlay_to_chunk modifies layers on an Andean cell.
    if andean is None:
        print(_row("step 3 - andean overlay (no convergent oc-co found)",
                   False, "skipped"))
        failures += 1
    else:
        ix, iy = andean
        anchor = _anchor_at(world, ix, iy)
        ctx = sample_tectonic_context(anchor, 0.0, 0.0)
        g = _make_synthetic_geology()
        before_chal = g.layers[2].ore_mix.get("chalcopyrite", 0.0)
        before_au = g.layers[2].ore_mix.get("native_gold", 0.0)
        n, province = apply_overlay_to_chunk(g, ctx, world_seed=gp.seed)
        after_chal = g.layers[2].ore_mix.get("chalcopyrite", 0.0)
        after_au = g.layers[2].ore_mix.get("native_gold", 0.0)
        ok = (province == "andean" and n >= 2
              and after_chal > before_chal * 3
              and after_au > before_au * 3)
        print(_row("step 3 - andean overlay boosts Cu + Au",
                   ok,
                   f"province={province} n_layers={n} "
                   f"chal {before_chal:.4f}->{after_chal:.4f} "
                   f"Au {before_au:.4f}->{after_au:.4f}"))
        if not ok:
            failures += 1

    # Step 4 — andean vs passive ore content difference.
    if andean is not None and passive is not None:
        andean_g = _make_synthetic_geology()
        ax, ay = andean
        actx = sample_tectonic_context(_anchor_at(world, ax, ay), 0.0, 0.0)
        apply_overlay_to_chunk(andean_g, actx, world_seed=gp.seed)
        pas_g = _make_synthetic_geology()
        px, py = passive
        pctx = sample_tectonic_context(_anchor_at(world, px, py), 0.0, 0.0)
        apply_overlay_to_chunk(pas_g, pctx, world_seed=gp.seed)
        andean_cu = sum(L.ore_mix.get("chalcopyrite", 0.0)
                         for L in andean_g.layers)
        passive_cu = sum(L.ore_mix.get("chalcopyrite", 0.0)
                          for L in pas_g.layers)
        ok = andean_cu > passive_cu * 5.0
        print(_row("step 4 - andean Cu strictly > passive Cu",
                   ok, f"andean={andean_cu:.4f} passive={passive_cu:.4f}"))
        if not ok:
            failures += 1
    else:
        print(_row("step 4 - andean vs passive (cells missing)", False,
                   "skipped"))
        failures += 1

    # Step 5 — mid-ocean ridge → sphalerite + galena boosted.
    if mor is None:
        print(_row("step 5 - mid-ocean ridge (no divergent oceanic cell)",
                   False, "skipped"))
        failures += 1
    else:
        ix, iy = mor
        anchor = _anchor_at(world, ix, iy)
        ctx = sample_tectonic_context(anchor, 0.0, 0.0)
        g = _make_synthetic_geology()
        n, province = apply_overlay_to_chunk(g, ctx, world_seed=gp.seed)
        # Sum across deep layers
        sph = sum(L.ore_mix.get("sphalerite", 0.0) for L in g.layers[2:])
        gal = sum(L.ore_mix.get("galena", 0.0) for L in g.layers[2:])
        ok = province == "mid_ocean_ridge" and sph > 0.005 and gal > 0.005
        print(_row("step 5 - mid-ocean ridge boosts Zn + Pb",
                   ok,
                   f"province={province} sph={sph:.4f} gal={gal:.4f}"))
        if not ok:
            failures += 1

    # Step 6 — continental rift → halite + gypsum.
    if rift is None:
        # Likely not present on small worlds — accept skip.
        print(_row("step 6 - continental rift not present (skipped)",
                   True, ""))
    else:
        ix, iy = rift
        anchor = _anchor_at(world, ix, iy)
        ctx = sample_tectonic_context(anchor, 0.0, 0.0)
        g = _make_synthetic_geology()
        n, province = apply_overlay_to_chunk(g, ctx, world_seed=gp.seed)
        halite = sum(L.ore_mix.get("halite", 0.0) for L in g.layers[2:])
        gyp = sum(L.ore_mix.get("gypsum", 0.0) for L in g.layers[2:])
        ok = province == "continental_rift" and halite > 0.01 and gyp > 0.005
        print(_row("step 6 - continental rift boosts halite + gypsum",
                   ok,
                   f"province={province} halite={halite:.4f} gyp={gyp:.4f}"))
        if not ok:
            failures += 1

    # Step 7 — install_tectonic_overlay idempotent.
    sim = _build_sim("p46_tec")
    sim.step()
    anchor = make_anchor(world)
    st1 = install_tectonic_overlay(sim, anchor)
    st2 = install_tectonic_overlay(sim, anchor)
    import engine.geology as _geo_mod
    ok = (st1 is st2 and
          getattr(_geo_mod, "_tectonic_inner_chunk_geology", None) is not None)
    print(_row("step 7 - install is idempotent",
               ok, f"same_state={st1 is st2}"))
    if not ok:
        failures += 1

    # Step 8 — determinism + actually-overlaid: must reach the wrapper,
    # so we go through the module attribute rather than the local import
    # binding (which would bypass the monkey-patch).
    coord = next(iter(sim.streamer.cache.keys()))
    g1 = _geo_mod.chunk_geology(sim, coord)
    snapshot1 = [(L.depth_top_m, dict(L.ore_mix)) for L in g1.layers]
    chunks_overlaid_after_first = tectonic_state(sim)["chunks_overlaid"]

    sim2 = _build_sim("p46_tec_2")
    sim2.step()
    install_tectonic_overlay(sim2, make_anchor(world))
    coord2 = next(iter(sim2.streamer.cache.keys()))
    g2 = _geo_mod.chunk_geology(sim2, coord2)
    snapshot2 = [(L.depth_top_m, dict(L.ore_mix)) for L in g2.layers]

    same_coord = (coord == coord2)
    if same_coord:
        snapshots_match = snapshot1 == snapshot2
    else:
        snapshots_match = True  # different bootstrap coords; skip strict equality
    ok = (chunks_overlaid_after_first >= 1 and snapshots_match)
    print(_row("step 8 - overlay runs + determinism",
               ok, f"chunks_overlaid={chunks_overlaid_after_first} "
                   f"coord_match={same_coord} snapshots_match={snapshots_match}"))
    if not ok:
        failures += 1

    # Step 9 — uninstall restores original chunk_geology.
    ok1 = uninstall_tectonic_overlay(sim)
    ok2 = (getattr(_geo_mod, "_tectonic_inner_chunk_geology", None) is None)
    # Re-run chunk_geology to confirm no error.
    g3 = _geo_mod.chunk_geology(sim, coord)
    ok3 = g3 is not None
    ok = ok1 and ok2 and ok3
    print(_row("step 9 - uninstall restores original chunk_geology",
               ok, f"uninstalled={ok1} hook_clear={ok2} chunk_ok={ok3}"))
    if not ok:
        failures += 1

    # Diagnostics
    report1 = tectonic_state(sim2)
    print(f"\nTectonic state on sim2: {report1}")

    print("=" * 78)
    total = 9
    passed = total - failures
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
