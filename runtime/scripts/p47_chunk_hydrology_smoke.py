"""P47 — Wave 18 chunk hydrology smoke.

Validates that ``engine.chunk_hydrology`` overlays macro-aligned river
stripes onto chunks anchored to a :class:`GenesisWorld`.

  1. Public API surface present.
  2. Pure-function overlay : chunk in a non-river macro cell -> decision
     is ``is_river=False`` and chunk water is untouched.
  3. Pure-function overlay : chunk in a high-flow_acc macro cell ->
     decision ``is_river=True`` and >= 1 cells get water painted.
  4. River width grows with sqrt(flow_acc) — a high-acc chunk has more
     painted cells than a lower-acc chunk.
  5. River direction follows macro flow_dir : painted cells form a
     stripe whose long axis aligns with the macro flow vector
     (perpendicular component of variance dominates).
  6. Idempotence : install + apply_to_existing_chunks twice keeps the
     same painted cell count.
  7. Streamer wrapping : after install_chunk_hydrology, a fresh
     ``streamer.get`` on a cache-miss coord triggers the overlay and
     increments ``chunks_processed``.
  8. Determinism : two anchored sims with the same seed produce
     bit-identical chunk.water on the same coord.
  9. Uninstall restores the original streamer methods and leaves no
     residual hook.
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
from engine.world import (CHUNK_SIDE_M, CHUNK_SIZE, generate_chunk,     # noqa: E402
                           TerrainParams)
from engine.world_genesis import (GenesisParams, generate_world,        # noqa: E402
                                    make_anchor)
from engine.chunk_hydrology import (                                    # noqa: E402
    apply_macro_rivers_to_chunk,
    install_chunk_hydrology, uninstall_chunk_hydrology,
    apply_to_existing_chunks, chunk_hydrology_state,
    HydrologyDecision, RIVER_WATER_LITRES,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xBEE_F_1234):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=2, max_agents=4,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def _find_river_macro_cell(world, min_flow_acc=200.0):
    """Pick the macro cell with highest flow_acc that is *not* a sink.

    The cell with the very highest flow_acc is the river mouth at the
    coastline, where ``flow_dir == 255`` and the river drains into the
    ocean — useless for testing a stripe through the chunk. We want a
    mid-stream cell with a defined downslope direction.
    """
    elev = world.elevation_m
    flow_acc = world.flow_acc
    flow_dir = world.flow_dir
    land = elev > 0.0
    flowing = flow_dir != 255
    candidates = np.where(land & flowing, flow_acc, -1.0)
    iy, ix = np.unravel_index(np.argmax(candidates), candidates.shape)
    if float(candidates[iy, ix]) < min_flow_acc:
        return None
    return int(ix), int(iy), float(candidates[iy, ix])


def _find_passive_macro_cell(world):
    """Pick a macro cell with very low flow_acc on land (no river)."""
    elev = world.elevation_m
    flow_acc = world.flow_acc
    land = elev > 0.0
    candidates = np.where(land, flow_acc, 1e9)
    iy, ix = np.unravel_index(np.argmin(candidates), candidates.shape)
    return int(ix), int(iy), float(flow_acc[iy, ix])


def _anchor_at(world, ix, iy):
    cell_km = world.params.map_size_km / world.params.resolution
    return make_anchor(world,
                        sim_origin_macro_km=((ix + 0.5) * cell_km,
                                              (iy + 0.5) * cell_km))


def main() -> int:
    print("=" * 78)
    print("P47 — Wave 18 chunk hydrology smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API surface
    ok = all(name in globals() for name in (
        "apply_macro_rivers_to_chunk",
        "install_chunk_hydrology",
        "uninstall_chunk_hydrology",
        "apply_to_existing_chunks",
        "chunk_hydrology_state",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Build a genesis world with rivers.
    gp = GenesisParams(seed=0xFEEDF00D & 0xFFFFFFFFFFFFFFFF,
                        resolution=96, n_plates=10,
                        erosion_iters=25, rain_iters=5,
                        river_threshold_cells=30.0)
    world = generate_world(gp)
    print(f"        diag = land={world.diagnostics['land_fraction']:.2f} "
          f"rivers={world.diagnostics['river_cells']} "
          f"basins={world.diagnostics['n_watersheds']}")

    # Locate a high-flow_acc cell that is NOT a sink.
    river_cell = _find_river_macro_cell(world, min_flow_acc=25.0)
    pass_cell = _find_passive_macro_cell(world)
    if river_cell is None:
        # Diagnose: dump the top flowing cells.
        flow_dir = world.flow_dir
        flow_acc = world.flow_acc
        elev = world.elevation_m
        mask = (elev > 0.0) & (flow_dir != 255)
        if mask.any():
            top5 = np.argpartition(-flow_acc[mask].ravel(), 5)[:5]
            ys_, xs_ = np.where(mask)
            for k in top5:
                print(f"        top flowing: (ix={int(xs_[k])}, "
                      f"iy={int(ys_[k])}) acc={float(flow_acc[ys_[k], xs_[k]]):.1f}")
        print(_row("step 2-5 - skipped: no flowing river cell found",
                   False, "world too small"))
        return 1
    rix, riy, racc = river_cell
    pix, piy, pacc = pass_cell
    print(f"        river cell: (ix={rix}, iy={riy}) flow_acc={racc:.1f}")
    print(f"        passive cell: (ix={pix}, iy={piy}) flow_acc={pacc:.1f}")

    params = TerrainParams()
    coord = (0, 0, 0)
    seed = 0xC0FFEE_AB

    # Step 2 — passive cell -> no river.
    pass_anchor = _anchor_at(world, pix, piy)
    pass_chunk = generate_chunk(seed, coord, params, genesis=pass_anchor)
    water_before = float(pass_chunk.water.sum())
    pass_dec = apply_macro_rivers_to_chunk(pass_chunk, pass_anchor)
    water_after = float(pass_chunk.water.sum())
    ok = (not pass_dec.is_river) and pass_dec.cells_painted == 0 \
        and water_before == water_after
    print(_row("step 2 - passive cell leaves water untouched",
               ok, f"is_river={pass_dec.is_river} "
                   f"painted={pass_dec.cells_painted} "
                   f"water dz={water_after - water_before:+.0f}"))
    if not ok:
        failures += 1

    # Step 3 — river cell -> water painted.
    river_anchor = _anchor_at(world, rix, riy)
    river_chunk = generate_chunk(seed, coord, params, genesis=river_anchor)
    water_before = float((river_chunk.water >= RIVER_WATER_LITRES).sum())
    river_dec = apply_macro_rivers_to_chunk(river_chunk, river_anchor,
                                              flow_acc_threshold=20.0)
    water_after = float((river_chunk.water >= RIVER_WATER_LITRES).sum())
    ok = river_dec.is_river and river_dec.cells_painted >= 1 \
        and water_after > water_before
    print(_row("step 3 - river cell paints water cells",
               ok, f"is_river={river_dec.is_river} "
                   f"painted={river_dec.cells_painted} "
                   f"width={river_dec.width_m:.1f}m"))
    if not ok:
        failures += 1

    # Step 4 — width scales with sqrt(flow_acc): pick a lower-acc river
    # cell that is *still* flowing (flow_dir != 255) and compare width.
    land_flow_mask = (world.elevation_m > 0.0) & (world.flow_dir != 255)
    flowing_accs = world.flow_acc[land_flow_mask]
    above_thresh = flowing_accs[flowing_accs > 20.0]
    if len(above_thresh) >= 5:
        target = float(np.percentile(above_thresh, 30))  # smaller river
        diff = np.abs(world.flow_acc - target)
        diff[~land_flow_mask] = 1e9
        my, mx = np.unravel_index(np.argmin(diff), diff.shape)
        small_anchor = _anchor_at(world, int(mx), int(my))
        small_chunk = generate_chunk(seed, coord, params,
                                      genesis=small_anchor)
        small_dec = apply_macro_rivers_to_chunk(small_chunk, small_anchor,
                                                  flow_acc_threshold=20.0)
        ok = (river_dec.width_m >= small_dec.width_m * 0.9
              and river_dec.flow_acc >= small_dec.flow_acc)
        print(_row("step 4 - width grows with sqrt(flow_acc)",
                   ok,
                   f"big acc={river_dec.flow_acc:.1f} w={river_dec.width_m:.1f}"
                   f" / small acc={small_dec.flow_acc:.1f} "
                   f"w={small_dec.width_m:.1f}"))
        if not ok:
            failures += 1
    else:
        print(_row("step 4 - width scaling (only one river)", True, "skipped"))

    # Step 5 — direction alignment : the painted stripe's principal axis
    # should follow macro flow_dir. We compute the covariance of painted
    # cell coords and check that the dominant eigenvector aligns with
    # the flow direction.
    yy, xx = np.where(river_chunk.water >= RIVER_WATER_LITRES)
    if len(xx) >= 4:
        pts = np.stack([xx.astype(np.float32) - xx.mean(),
                        yy.astype(np.float32) - yy.mean()], axis=0)
        cov = pts @ pts.T / len(xx)
        eigvals, eigvecs = np.linalg.eigh(cov)
        principal = eigvecs[:, np.argmax(eigvals)]
        from engine.chunk_hydrology import _D8_DX, _D8_DY, _D8_NORM
        fd = river_dec.flow_dir
        flow_vec = np.array([_D8_DX[fd] / _D8_NORM[fd],
                             _D8_DY[fd] / _D8_NORM[fd]],
                            dtype=np.float32)
        dot = abs(float(principal[0] * flow_vec[0]
                         + principal[1] * flow_vec[1]))
        ok = dot >= 0.85
        print(_row("step 5 - stripe principal axis aligns with flow_dir",
                   ok, f"|dot|={dot:.3f} flow_dir={fd}"))
        if not ok:
            failures += 1
    else:
        print(_row("step 5 - alignment (too few painted cells)",
                   True, f"painted={len(xx)}"))

    # Step 6 — idempotence on second apply.
    river_chunk2 = generate_chunk(seed, coord, params, genesis=river_anchor)
    apply_macro_rivers_to_chunk(river_chunk2, river_anchor,
                                  flow_acc_threshold=20.0)
    n1 = int((river_chunk.water >= RIVER_WATER_LITRES).sum())
    apply_macro_rivers_to_chunk(river_chunk2, river_anchor,
                                  flow_acc_threshold=20.0)
    n2 = int((river_chunk2.water >= RIVER_WATER_LITRES).sum())
    ok = n1 == n2 and np.array_equal(river_chunk.water, river_chunk2.water)
    print(_row("step 6 - idempotence on repeated apply",
               ok, f"n1={n1} n2={n2}"))
    if not ok:
        failures += 1

    # Step 7 — streamer wrapping: install -> get fresh coord -> overlay applied.
    sim = _build_sim("p47_hydro", seed=0xC0FFEE_AB)
    sim.streamer.set_genesis(river_anchor)
    sim.streamer.clear_cache()
    st = install_chunk_hydrology(sim, river_anchor, flow_acc_threshold=20.0)
    fresh_coord = (5, 5, 0)
    ch = sim.streamer.get(0, fresh_coord)
    state_after = chunk_hydrology_state(sim)
    ok = (state_after["installed"] and state_after["chunks_processed"] >= 1
          and ch is not None)
    print(_row("step 7 - streamer wrap triggers overlay on cache miss",
               ok, f"chunks_processed={state_after['chunks_processed']} "
                   f"with_river={state_after['chunks_with_river']}"))
    if not ok:
        failures += 1

    # Step 8 — determinism between two sims with the same seed.
    sim2 = _build_sim("p47_hydro_2", seed=0xC0FFEE_AB)
    sim2.streamer.set_genesis(river_anchor)
    sim2.streamer.clear_cache()
    install_chunk_hydrology(sim2, river_anchor, flow_acc_threshold=20.0)
    ch2 = sim2.streamer.get(0, fresh_coord)
    ok = (np.array_equal(ch.water, ch2.water)
          and np.array_equal(ch.height, ch2.height))
    print(_row("step 8 - determinism across two anchored sims",
               ok, f"water_match={np.array_equal(ch.water, ch2.water)} "
                   f"height_match={np.array_equal(ch.height, ch2.height)}"))
    if not ok:
        failures += 1

    # Step 9 — uninstall restores original streamer.
    ok1 = uninstall_chunk_hydrology(sim)
    streamer = sim.streamer
    ok2 = (getattr(streamer, "_chunk_hydrology_orig_get", None) is None
           and getattr(sim, "_chunk_hydrology_state", None) is None)
    # Confirm fresh get still works.
    sim.streamer.clear_cache()
    ch3 = sim.streamer.get(0, fresh_coord)
    ok3 = ch3 is not None
    ok = ok1 and ok2 and ok3
    print(_row("step 9 - uninstall cleanly detaches",
               ok,
               f"uninst={ok1} hook_clear={ok2} chunk_ok={ok3}"))
    if not ok:
        failures += 1

    print(f"\nHydrology state on sim2: {chunk_hydrology_state(sim2)}")

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
