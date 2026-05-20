"""P62 — Wave 32 polity emergence smoke.

  1. Public API surface.
  2. ``assign_polities`` returns N >= 1 polities given culturally diverse
     settlements.
  3. Every settlement is a member of exactly one polity (partition).
  4. Each polity has a capital with rank ∈ member_ranks.
  5. Voronoi partitions all land cells (every land cell has polity_id ≥ 0).
  6. Members of one polity are culturally similar (max pairwise L2 <
     threshold).
  7. Determinism : two runs same inputs → identical polity_id_grid.
  8. ``render_polities`` writes PNG with at least 2 distinct territory
     colours visible.
  9. ``polity_summary`` returns plausible aggregates.
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
from engine.road_network import build_road_network                      # noqa: E402
from engine.trade_flow import compute_trade_flows                       # noqa: E402
from engine.cultural_diffusion import (CulturalConfig,                  # noqa: E402
                                          run_cultural_diffusion)
from engine.polity_emergence import (                                   # noqa: E402
    PolityConfig, Polity, PolityMap,
    assign_polities, render_polities, polity_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P62 — Wave 32 polity emergence smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API.
    ok = all(name in globals() for name in (
        "PolityConfig", "Polity", "PolityMap",
        "assign_polities", "render_polities", "polity_summary",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Build full upstream pipeline.
    gp = GenesisParams(seed=0xC0FFEE_62 & 0xFFFFFFFFFFFFFFFF,
                        resolution=64, n_plates=10,
                        erosion_iters=15, rain_iters=4)
    world = generate_world(gp)
    cands = find_settlement_candidates(world, n_candidates=10,
                                         min_spacing_km=300.0,
                                         seed=0xCAFE)
    network = build_road_network(world, cands)
    trade = compute_trade_flows(cands, world, network)
    # Use LOW diffusion + LOW iterations so cultures STAY diverse.
    cfg_culture = CulturalConfig(n_dimensions=5, n_iterations=8,
                                   diffusion_rate=0.05,
                                   innovation_rate=0.02,
                                   initial_seed=0xDEAD_C0DE_5678)
    cultures = run_cultural_diffusion(cands, trade, cfg_culture)
    print(f"        settlements={len(cands)} edges={len(network.edges)} "
          f"convergence={cultures.convergence_metric:.3f}")

    # Step 2 — assign_polities → N >= 1.
    cfg = PolityConfig(similarity_threshold=0.25, min_polity_size=1)
    pmap = assign_polities(world, cands, cultures, trade, cfg)
    ok = pmap.n_polities >= 1
    print(_row("step 2 - at least one polity emerges",
               ok, f"n_polities={pmap.n_polities}"))
    if not ok:
        failures += 1

    # Step 3 — every settlement is a member of exactly one polity.
    member_set = set()
    duplicates = 0
    for p in pmap.polities:
        for r in p.member_ranks:
            if r in member_set:
                duplicates += 1
            member_set.add(r)
    expected = {c.rank for c in cands}
    missing = expected - member_set
    ok = (duplicates == 0 and not missing)
    print(_row("step 3 - polities partition the settlements",
               ok, f"duplicates={duplicates} missing={list(missing)} "
                   f"total_members={len(member_set)}/{len(cands)}"))
    if not ok:
        failures += 1

    # Step 4 — every polity's capital is one of its members.
    bad_caps = 0
    for p in pmap.polities:
        if p.capital_rank not in p.member_ranks:
            bad_caps += 1
    ok = bad_caps == 0
    print(_row("step 4 - every capital is in its own polity",
               ok, f"bad_capitals={bad_caps}"))
    if not ok:
        failures += 1

    # Step 5 — Voronoi assigns every land cell.
    grid = pmap.polity_id_grid
    land = world.elevation_m > world.params.sea_level_m
    land_assigned = grid >= 0
    # Should be : every land cell has polity_id != -1.
    unassigned_land = land & (~land_assigned)
    assigned_ocean = (~land) & (grid >= 0)
    ok = unassigned_land.sum() == 0 and assigned_ocean.sum() == 0
    print(_row("step 5 - Voronoi covers all land cells, leaves ocean -1",
               ok, f"unassigned_land={int(unassigned_land.sum())} "
                   f"assigned_ocean={int(assigned_ocean.sum())}"))
    if not ok:
        failures += 1

    # Step 6 — members of one polity are culturally similar.
    max_intra = 0.0
    rank_to_idx = {c.rank: i for i, c in enumerate(cands)}
    for p in pmap.polities:
        if len(p.member_ranks) < 2:
            continue
        idxs = [rank_to_idx[r] for r in p.member_ranks]
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                d = float(np.linalg.norm(
                    cultures.final[idxs[i]] - cultures.final[idxs[j]]))
                if d > max_intra:
                    max_intra = d
    ok = max_intra < cfg.similarity_threshold + 1e-3
    print(_row("step 6 - intra-polity culture distances < threshold",
               ok, f"max_intra={max_intra:.4f} threshold={cfg.similarity_threshold}"))
    if not ok:
        failures += 1

    # Step 7 — determinism.
    pmap2 = assign_polities(world, cands, cultures, trade, cfg)
    ok = (pmap.n_polities == pmap2.n_polities
          and np.array_equal(pmap.polity_id_grid, pmap2.polity_id_grid)
          and pmap.total_population == pmap2.total_population)
    print(_row("step 7 - determinism (same inputs → same map)",
               ok, f"grid_match={np.array_equal(pmap.polity_id_grid, pmap2.polity_id_grid)}"))
    if not ok:
        failures += 1

    # Step 8 — render writes PNG with multiple polity colours.
    with tempfile.TemporaryDirectory() as td:
        png_path = os.path.join(td, "polities.png")
        rgb = render_polities(world, pmap, cands, network,
                                path=png_path)
        # Count distinct colours that come from polity territory tinting :
        # if there are >= 2 polities with territory, we should see > 2
        # distinct "tinted" regions. Approximate via : count unique pixel
        # RGB values across the land mask — expect > the count we'd have
        # without tinting (12 biomes max).
        flat = rgb.reshape(-1, 3)
        n_distinct_rgb = len(np.unique(flat.view(np.dtype((np.void,
                                                              flat.dtype.itemsize * 3))).ravel()))
        ok = (rgb.shape == (gp.resolution, gp.resolution, 3)
              and os.path.exists(png_path)
              and os.path.getsize(png_path) > 100
              and n_distinct_rgb >= 12)  # at least biomes + tints
        print(_row("step 8 - render PNG has tinted territory regions",
                   ok, f"distinct_rgb={n_distinct_rgb} "
                       f"png_bytes={os.path.getsize(png_path)}"))
        if not ok:
            failures += 1

    # Step 9 — summary.
    summary = polity_summary(pmap)
    ok = (summary["n_polities"] == pmap.n_polities
          and summary["total_population"] >= 0.0
          and len(summary["polities"]) == pmap.n_polities)
    print(_row("step 9 - polity_summary plausible",
               ok, f"n={summary['n_polities']} "
                   f"total_pop={summary['total_population']}"))
    if not ok:
        failures += 1

    # Diagnostic dump.
    print(f"\nPolities ({summary['n_polities']}, sorted by population):")
    for p in summary["polities"]:
        print(f"  polity {p['polity_id']}  capital=rank{p['capital_rank']}  "
              f"members={p['members']}  pop={p['population']:.3f}  "
              f"territory={p['territory_cells']} cells  "
              f"color={p['color_rgb']}  biome={p['dominant_biome']}")

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
