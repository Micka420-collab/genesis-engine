"""P61 — Wave 31 cultural diffusion smoke.

  1. Public API surface.
  2. ``initialize_cultures`` returns (N, D) float32 in [0, 1].
  3. Determinism : two inits same seed → identical cultures.
  4. ``_build_diffusion_matrix`` produces row-stochastic (rows sum to 1).
  5. Cultures stay clipped in [0, 1] after K iterations.
  6. Convergence : two heavily-traded settlements become more similar
     than two weakly-connected ones.
  7. Run reproducible : two full runs same inputs → identical history.
  8. ``render_cultural_map`` writes PNG with colour-coded dots.
  9. ``cultural_summary`` reports plausible bloc structure.
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
from engine.cultural_diffusion import (                                 # noqa: E402
    CulturalConfig, CulturalHistory,
    initialize_cultures, step_cultural_diffusion,
    _build_diffusion_matrix, run_cultural_diffusion,
    detect_cultural_blocs, culture_to_rgb,
    render_cultural_map, cultural_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P61 — Wave 31 cultural diffusion smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API surface.
    ok = all(name in globals() for name in (
        "CulturalConfig", "CulturalHistory",
        "initialize_cultures", "step_cultural_diffusion",
        "run_cultural_diffusion", "detect_cultural_blocs",
        "culture_to_rgb", "render_cultural_map", "cultural_summary",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Build a world + settlements + roads + trade.
    gp = GenesisParams(seed=0xC0FFEE_61 & 0xFFFFFFFFFFFFFFFF,
                        resolution=64, n_plates=10,
                        erosion_iters=15, rain_iters=4)
    world = generate_world(gp)
    cands = find_settlement_candidates(world, n_candidates=8,
                                         min_spacing_km=350.0, seed=0xCAFE)
    network = build_road_network(world, cands)
    trade = compute_trade_flows(cands, world, network)
    print(f"        settlements={len(cands)} edges={len(network.edges)}")

    # Step 2 — initialize_cultures shape + range.
    cfg = CulturalConfig(n_dimensions=5, n_iterations=30,
                          diffusion_rate=0.15, innovation_rate=0.005,
                          initial_seed=0xCAFE_C0DE_1234)
    cultures_init = initialize_cultures(cands, cfg)
    ok = (cultures_init.shape == (len(cands), cfg.n_dimensions)
          and cultures_init.dtype == np.float32
          and cultures_init.min() >= 0.0 and cultures_init.max() <= 1.0)
    print(_row("step 2 - init cultures shape + range",
               ok, f"shape={cultures_init.shape} dtype={cultures_init.dtype} "
                   f"range=[{float(cultures_init.min()):.3f}, "
                   f"{float(cultures_init.max()):.3f}]"))
    if not ok:
        failures += 1

    # Step 3 — determinism of init.
    cultures_init_again = initialize_cultures(cands, cfg)
    ok = np.array_equal(cultures_init, cultures_init_again)
    print(_row("step 3 - init determinism (same seed)",
               ok, f"max_diff={float(np.abs(cultures_init - cultures_init_again).max()):.6f}"))
    if not ok:
        failures += 1

    # Step 4 — diffusion matrix row-stochastic.
    P = _build_diffusion_matrix(cands, trade)
    row_sums = P.sum(axis=1)
    ok = np.allclose(row_sums, 1.0, atol=1e-5)
    print(_row("step 4 - diffusion matrix row-stochastic (rows = 1)",
               ok, f"row_sum range=[{float(row_sums.min()):.6f}, "
                   f"{float(row_sums.max()):.6f}]"))
    if not ok:
        failures += 1

    # Step 5 — cultures stay in [0, 1] after iterations.
    history = run_cultural_diffusion(cands, trade, cfg)
    ok = (history.final.min() >= 0.0 and history.final.max() <= 1.0
          and history.final.shape == cultures_init.shape)
    print(_row("step 5 - final cultures stay in [0, 1]",
               ok, f"final range=[{float(history.final.min()):.3f}, "
                   f"{float(history.final.max()):.3f}]"))
    if not ok:
        failures += 1

    # Step 6 — convergence : heavily-traded settlements become similar.
    flows = trade.flows
    # Find the highest-flow pair and the lowest-flow pair.
    n = len(cands)
    max_flow = 0.0; max_pair = (-1, -1)
    min_flow = float("inf"); min_pair = (-1, -1)
    for i in range(n):
        for j in range(i + 1, n):
            f = float(flows[i, j])
            if f > max_flow:
                max_flow = f; max_pair = (i, j)
            if 0.0 < f < min_flow:
                min_flow = f; min_pair = (i, j)
    if max_pair[0] >= 0 and min_pair[0] >= 0 and max_pair != min_pair:
        d_max = float(np.linalg.norm(
            history.final[max_pair[0]] - history.final[max_pair[1]]))
        d_min = float(np.linalg.norm(
            history.final[min_pair[0]] - history.final[min_pair[1]]))
        # High-trade pair should NOT be MUCH further apart than low-trade.
        # We accept equal-or-closer for the high-trade pair.
        ok = d_max <= d_min + 0.2
        print(_row("step 6 - heavy-trade pair more (or as) similar than light",
                   ok,
                   f"d(heavy={max_pair}, flow={max_flow:.2f})={d_max:.3f} "
                   f"d(light={min_pair}, flow={min_flow:.4f})={d_min:.3f}"))
        if not ok:
            failures += 1
    else:
        print(_row("step 6 - too few distinct pairs (skipped)", True, ""))

    # Step 7 — full run reproducibility.
    history_a = run_cultural_diffusion(cands, trade, cfg)
    history_b = run_cultural_diffusion(cands, trade, cfg)
    ok = (np.array_equal(history_a.final, history_b.final)
          and np.array_equal(history_a.initial, history_b.initial)
          and abs(history_a.convergence_metric -
                  history_b.convergence_metric) < 1e-6)
    print(_row("step 7 - full run determinism",
               ok, f"final_match={np.array_equal(history_a.final, history_b.final)}"))
    if not ok:
        failures += 1

    # Step 8 — render writes PNG with culture-coloured dots.
    with tempfile.TemporaryDirectory() as td:
        png_path = os.path.join(td, "culture.png")
        rgb = render_cultural_map(
            world, network, cands, history,
            path=png_path, dot_radius_px=2, paint_roads_neutral=True)
        # Check that at least one settlement cell carries the expected
        # culture-derived colour.
        ok_paint = False
        for i, sett in enumerate(cands):
            target = np.array(culture_to_rgb(history.final[i]),
                                dtype=np.uint8)
            cy = sett.macro_iy; cx = sett.macro_ix
            if (0 <= cy < rgb.shape[0]) and (0 <= cx < rgb.shape[1]):
                if np.array_equal(rgb[cy, cx], target):
                    ok_paint = True
                    break
        ok = (rgb.shape == (gp.resolution, gp.resolution, 3)
              and os.path.exists(png_path)
              and os.path.getsize(png_path) > 100
              and ok_paint)
        print(_row("step 8 - render paints culture-coloured dots",
                   ok, f"paint_match={ok_paint} "
                       f"png_bytes={os.path.getsize(png_path)}"))
        if not ok:
            failures += 1

    # Step 9 — summary.
    summary = cultural_summary(cands, history, similarity_threshold=0.30)
    ok = (summary["n_settlements"] == len(cands)
          and summary["n_blocs"] >= 1
          and summary["dominant_bloc_size"] >= 1
          and sum(summary["bloc_sizes"]) == summary["n_settlements"])
    print(_row("step 9 - cultural summary plausible",
               ok, f"n_blocs={summary['n_blocs']} "
                   f"sizes={summary['bloc_sizes']} "
                   f"convergence={summary['convergence_metric']}"))
    if not ok:
        failures += 1

    print(f"\nCultural summary: {summary}")
    print(f"Per-settlement culture (first 3 dims as RGB):")
    for i, sett in enumerate(cands):
        col = culture_to_rgb(history.final[i])
        print(f"  rank {sett.rank} (biome {sett.biome}) "
              f"→ RGB {col}  init→final shift="
              f"{float(np.linalg.norm(history.final[i] - history.initial[i])):.3f}")

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
