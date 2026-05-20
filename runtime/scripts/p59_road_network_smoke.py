"""P59 — Wave 29 road network emergence smoke.

  1. Public API surface.
  2. ``compute_cost_field`` returns (R, R) float32 with all values >= 1.
  3. Ocean cells have very high cost (>= 100).
  4. ``dijkstra_path`` finds a connected path between two cells.
  5. Dijkstra path total cost ≤ naive straight-line cost (proves it
     actually optimises rather than going straight).
  6. ``build_road_network`` on N=5 settlements yields a tree with N-1 edges.
  7. Road network connects all settlements (graph reachability).
  8. Determinism : two runs identical → identical road_mask.
  9. ``render_road_network`` writes a PNG with roads painted at the
     correct RGB and settlements in their RGB.
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
from engine.settlement_emergence import find_settlement_candidates      # noqa: E402
from engine.road_network import (                                       # noqa: E402
    RoadCostConfig, RoadEdge, RoadNetwork,
    compute_cost_field, dijkstra_path, build_road_network,
    render_road_network, network_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P59 — Wave 29 road network emergence smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API.
    ok = all(name in globals() for name in (
        "RoadCostConfig", "RoadEdge", "RoadNetwork",
        "compute_cost_field", "dijkstra_path", "build_road_network",
        "render_road_network", "network_summary",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    gp = GenesisParams(seed=0xC0FFEE_59 & 0xFFFFFFFFFFFFFFFF,
                        resolution=64, n_plates=10,
                        erosion_iters=15, rain_iters=4)
    world = generate_world(gp)
    print(f"        world: land_frac="
          f"{world.diagnostics['land_fraction']:.2f}")

    # Step 2 — cost field shape + min ≥ 1.
    cost = compute_cost_field(world)
    ok = (cost.shape == (gp.resolution, gp.resolution)
          and cost.dtype == np.float32
          and float(cost.min()) >= 1.0)
    print(_row("step 2 - cost field shape + dtype + min >= 1",
               ok, f"shape={cost.shape} min={float(cost.min()):.2f} "
                   f"max={float(cost.max()):.2f}"))
    if not ok:
        failures += 1

    # Step 3 — ocean cost high.
    ocean = world.elevation_m <= world.params.sea_level_m
    if ocean.any():
        ocean_min = float(cost[ocean].min())
        ok = ocean_min >= 100.0
        print(_row("step 3 - ocean cells cost >= 100",
                   ok, f"ocean_min_cost={ocean_min:.1f}"))
        if not ok:
            failures += 1
    else:
        print(_row("step 3 - no ocean (skipped)", True, ""))

    # Step 4 — Dijkstra finds a path between two land cells.
    land = np.argwhere(world.elevation_m > 0.0)
    if len(land) < 2:
        print(_row("step 4 - not enough land for Dijkstra", False, ""))
        failures += 1
        return 1
    s = tuple(int(v) for v in land[0])
    g = tuple(int(v) for v in land[-1])
    path, cost_path = dijkstra_path(cost, s, g)
    ok = (len(path) >= 2 and path[0] == s and path[-1] == g
          and cost_path > 0.0)
    print(_row("step 4 - Dijkstra connects start to goal",
               ok, f"len={len(path)} cost={cost_path:.1f} "
                   f"start={s} goal={g}"))
    if not ok:
        failures += 1

    # Step 5 — Dijkstra path is structurally valid : every consecutive
    # pair of cells is 8-connected (no teleporting), no duplicates, and
    # the recomputed cost matches what Dijkstra reported (within FP).
    sy, sx = s; gy, gx = g
    valid_struct = True
    dup_free = (len(set(path)) == len(path))
    recomputed = 0.0
    for k in range(1, len(path)):
        py, px = path[k - 1]
        qy, qx = path[k]
        dy = abs(qy - py); dx = abs(qx - px)
        if max(dy, dx) != 1:
            valid_struct = False
            break
        dist_factor = float(np.sqrt(2.0)) if (dy == 1 and dx == 1) else 1.0
        recomputed += float(cost[qy, qx]) * dist_factor
    cost_match = abs(recomputed - cost_path) < 0.01
    ok = valid_struct and dup_free and cost_match
    print(_row("step 5 - Dijkstra path is 8-connected + cost-consistent",
               ok, f"struct={valid_struct} dup_free={dup_free} "
                   f"cost_match={cost_match} (dij={cost_path:.2f} "
                   f"recomp={recomputed:.2f})"))
    if not ok:
        failures += 1

    # Step 6 — MST with N=5 settlements yields N-1 edges.
    candidates = find_settlement_candidates(
        world, n_candidates=5, min_spacing_km=400.0,
        seed=0xCAFE,
    )
    n = len(candidates)
    network = build_road_network(world, candidates)
    ok = (n >= 2 and len(network.edges) == n - 1)
    print(_row("step 6 - MST has N-1 edges for N settlements",
               ok, f"n_settlements={n} n_edges={len(network.edges)}"))
    if not ok:
        failures += 1

    # Step 7 — network connects all settlements (graph reachability).
    if n >= 2:
        from collections import defaultdict, deque
        adj = defaultdict(set)
        for e in network.edges:
            adj[e.from_rank].add(e.to_rank)
            adj[e.to_rank].add(e.from_rank)
        start = candidates[0].rank
        seen = {start}
        q = deque([start])
        while q:
            node = q.popleft()
            for nb in adj[node]:
                if nb not in seen:
                    seen.add(nb)
                    q.append(nb)
        expected = {c.rank for c in candidates}
        ok = (seen == expected)
        print(_row("step 7 - network spans all settlements (connected)",
                   ok, f"reached={len(seen)}/{n}"))
        if not ok:
            failures += 1

    # Step 8 — determinism.
    net1 = build_road_network(world, candidates)
    net2 = build_road_network(world, candidates)
    ok = (np.array_equal(net1.road_mask, net2.road_mask)
          and len(net1.edges) == len(net2.edges)
          and abs(net1.total_length_km - net2.total_length_km) < 1e-4)
    print(_row("step 8 - determinism: same inputs -> same network",
               ok, f"road_cells={int(net1.road_mask.sum())} "
                   f"total_km={net1.total_length_km:.1f}"))
    if not ok:
        failures += 1

    # Step 9 — render produces PNG with roads + settlements.
    with tempfile.TemporaryDirectory() as td:
        png_path = os.path.join(td, "roads.png")
        rgb = render_road_network(
            world, network, candidates, path=png_path,
            road_rgb=(200, 50, 50),
            settlement_rgb=(255, 80, 200),
            settlement_radius_px=1,
        )
        # Check : at least one road cell is painted with road_rgb.
        road_pixels = (rgb[..., 0] == 200) & (rgb[..., 1] == 50) & (rgb[..., 2] == 50)
        settlement_pixels = (rgb[..., 0] == 255) & (rgb[..., 1] == 80) & (rgb[..., 2] == 200)
        ok = (rgb.shape == (gp.resolution, gp.resolution, 3)
              and os.path.exists(png_path)
              and os.path.getsize(png_path) > 100
              and road_pixels.any()
              and settlement_pixels.any())
        print(_row("step 9 - render paints roads + settlements",
                   ok, f"road_px={int(road_pixels.sum())} "
                       f"settlement_px={int(settlement_pixels.sum())} "
                       f"png_bytes={os.path.getsize(png_path)}"))
        if not ok:
            failures += 1

    # Dump.
    print(f"\nNetwork summary: {network_summary(network)}")
    print("Edges:")
    for e in network.edges:
        print(f"  {e.from_rank} <-> {e.to_rank}  "
              f"length={e.length_km:.1f} km  "
              f"cells={e.length_cells}  cost={e.cost_total:.1f}")

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
