"""P58 — Wave 28 settlement emergence smoke.

Validates :mod:`engine.settlement_emergence` : per-cell viability
scoring + Poisson-disk site picking + overlay render.

  1. Public API surface.
  2. ``score_settlement_viability`` returns a dict with 7 keys (6
     components + "score"), all (R, R) float32.
  3. Ocean cells get score = 0 (not viable).
  4. ``find_settlement_candidates`` respects ``min_spacing_km``.
  5. Convergent-boundary neighbours are penalised (lower score).
  6. River-adjacent cells have higher water_score than far-from-river.
  7. Determinism : two runs same inputs → identical candidates.
  8. ``render_settlements_overlay`` paints dots at candidate cells.
  9. ``candidates_summary`` returns plausible aggregates.
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

from engine.world_genesis import (GenesisParams, generate_world,        # noqa: E402
                                    BOUND_CONVERGENT)
from engine.settlement_emergence import (                               # noqa: E402
    SettlementConfig, SettlementCandidate,
    score_settlement_viability, find_settlement_candidates,
    render_settlements_overlay, candidates_summary,
    BIOME_FOOD_POTENTIAL,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P58 — Wave 28 settlement emergence smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API.
    ok = all(name in globals() for name in (
        "SettlementConfig", "SettlementCandidate",
        "score_settlement_viability", "find_settlement_candidates",
        "render_settlements_overlay", "candidates_summary",
        "BIOME_FOOD_POTENTIAL",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    gp = GenesisParams(seed=0xC0FFEE_58 & 0xFFFFFFFFFFFFFFFF,
                        resolution=64, n_plates=10,
                        erosion_iters=15, rain_iters=4)
    world = generate_world(gp)
    print(f"        world: land_frac="
          f"{world.diagnostics['land_fraction']:.2f} "
          f"rivers={world.diagnostics['river_cells']}")

    # Step 2 — score function returns 7-key dict.
    cfg = SettlementConfig()
    components = score_settlement_viability(world, cfg)
    keys_expected = {"flatness", "water", "food", "safety", "climate",
                     "coast", "score"}
    ok = (set(components.keys()) == keys_expected
          and all(v.shape == (gp.resolution, gp.resolution)
                  for v in components.values())
          and all(v.dtype == np.float32 for v in components.values()))
    print(_row("step 2 - score components shape + dtype",
               ok, f"keys={sorted(components.keys())}"))
    if not ok:
        failures += 1

    # Step 3 — ocean cells score = 0.
    ocean_mask = world.elevation_m <= world.params.sea_level_m
    if ocean_mask.any():
        ocean_max = float(components["score"][ocean_mask].max())
        ok = ocean_max < 1e-3
        print(_row("step 3 - ocean cells score ≈ 0",
                   ok, f"max_ocean_score={ocean_max:.6f}"))
        if not ok:
            failures += 1
    else:
        print(_row("step 3 - no ocean cells (skipped)", True, ""))

    # Step 4 — candidates respect min_spacing.
    n_target = 8
    min_spacing_km = 300.0
    candidates = find_settlement_candidates(
        world, n_candidates=n_target, min_spacing_km=min_spacing_km,
        cfg=cfg, seed=0xCAFEBABE,
    )
    # Pairwise distances.
    min_dist_observed = float("inf")
    if len(candidates) >= 2:
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                dx = candidates[i].macro_x_km - candidates[j].macro_x_km
                dy = candidates[i].macro_y_km - candidates[j].macro_y_km
                d = (dx * dx + dy * dy) ** 0.5
                if d < min_dist_observed:
                    min_dist_observed = d
    ok = (len(candidates) > 0
          and (len(candidates) < 2 or min_dist_observed >= min_spacing_km * 0.9))
    print(_row("step 4 - candidates respect min_spacing",
               ok, f"n={len(candidates)} min_dist={min_dist_observed:.1f} km "
                   f"(target ≥ {min_spacing_km:.0f})"))
    if not ok:
        failures += 1

    # Step 5 — convergent boundary cells penalised.
    safety_arr = components["safety"]
    conv_cells = world.boundary_kind == BOUND_CONVERGENT
    if conv_cells.any():
        safety_at_conv = float(safety_arr[conv_cells].mean())
        safety_at_else = float(safety_arr[~conv_cells].mean())
        ok = safety_at_conv < safety_at_else
        print(_row("step 5 - convergent cells get lower safety",
                   ok, f"safety_conv={safety_at_conv:.3f} "
                       f"vs_other={safety_at_else:.3f}"))
        if not ok:
            failures += 1
    else:
        print(_row("step 5 - no convergent cells (skipped)", True, ""))

    # Step 6 — water score : river-adjacent > far cells.
    water_arr = components["water"]
    river_mask = world.river_mask
    if river_mask.any():
        # Cells immediately neighbour to a river.
        near_river = river_mask | np.roll(river_mask, 1, 0) | np.roll(river_mask, -1, 0) \
                     | np.roll(river_mask, 1, 1) | np.roll(river_mask, -1, 1)
        far_river = ~near_river
        water_near = float(water_arr[near_river].mean())
        water_far = float(water_arr[far_river].mean()) if far_river.any() else 0.0
        ok = water_near > water_far
        print(_row("step 6 - water score: near-river > far-river",
                   ok, f"near={water_near:.3f} far={water_far:.3f}"))
        if not ok:
            failures += 1
    else:
        print(_row("step 6 - no rivers (skipped)", True, ""))

    # Step 7 — determinism.
    c1 = find_settlement_candidates(world, n_candidates=5,
                                      min_spacing_km=300.0, seed=0xCAFE)
    c2 = find_settlement_candidates(world, n_candidates=5,
                                      min_spacing_km=300.0, seed=0xCAFE)
    ok = (len(c1) == len(c2)
          and all(c1[i].macro_ix == c2[i].macro_ix
                  and c1[i].macro_iy == c2[i].macro_iy
                  and abs(c1[i].score - c2[i].score) < 1e-6
                  for i in range(len(c1))))
    print(_row("step 7 - determinism on candidate list",
               ok, f"n1={len(c1)} n2={len(c2)} match=all"))
    if not ok:
        failures += 1

    # Step 8 — render overlay paints dots.
    with tempfile.TemporaryDirectory() as td:
        png_path = os.path.join(td, "settlements.png")
        rgb = render_settlements_overlay(
            world, candidates, path=png_path,
            dot_rgb=(255, 80, 200), dot_radius_px=2)
        ok = (rgb.shape == (gp.resolution, gp.resolution, 3)
              and rgb.dtype == np.uint8
              and os.path.exists(png_path)
              and os.path.getsize(png_path) > 100)
        # Check at least one candidate cell is painted with the dot color.
        if candidates:
            c0 = candidates[0]
            pixel = rgb[c0.macro_iy, c0.macro_ix]
            ok = ok and tuple(int(v) for v in pixel) == (255, 80, 200)
        print(_row("step 8 - render overlay paints settlement dots",
                   ok, f"png_bytes={os.path.getsize(png_path)}"))
        if not ok:
            failures += 1

    # Step 9 — summary returns plausible dict.
    summary = candidates_summary(candidates)
    ok = (summary["n"] == len(candidates)
          and 0.0 <= summary["score_min"] <= summary["score_max"] <= 1.0
          and isinstance(summary["biomes_distinct"], list)
          and len(summary["top_3_xy_km"]) == min(3, len(candidates)))
    print(_row("step 9 - candidates_summary plausible",
               ok, f"n={summary['n']} score range "
                   f"[{summary['score_min']:.3f}, {summary['score_max']:.3f}] "
                   f"biomes={summary['biomes_distinct']}"))
    if not ok:
        failures += 1

    # Diagnostic dump.
    print(f"\nTop {min(5, len(candidates))} settlement candidates:")
    for c in candidates[:5]:
        biome_name = ""
        try:
            from engine.world import Biome as B
            biome_name = B(c.biome).name
        except Exception:
            biome_name = str(c.biome)
        print(f"  rank {c.rank}: ({c.macro_x_km:6.1f}, {c.macro_y_km:6.1f}) km  "
              f"score={c.score:.4f}  biome={biome_name}")

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
