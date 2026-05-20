"""P60 — Wave 30 trade flow gravity smoke.

  1. Public API surface.
  2. ``compute_settlement_weights`` returns (N,) float32 > 0.
  3. Weights respect biome NPP bias (rainforest > desert).
  4. ``compute_trade_flows`` returns symmetric matrix.
  5. Gravity behaviour : flow ∝ w_i × w_j / dist^β.
  6. Only MST-connected pairs have nonzero flow.
  7. Determinism : same inputs → identical flow matrix.
  8. ``render_trade_flows`` paints edges with magnitude-coloured RGB.
  9. ``trade_summary`` returns plausible aggregates.
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
from engine.settlement_emergence import (find_settlement_candidates,    # noqa: E402
                                           SettlementCandidate)
from engine.road_network import build_road_network                      # noqa: E402
from engine.trade_flow import (                                         # noqa: E402
    TradeConfig, TradeNetwork,
    compute_settlement_weights, compute_trade_flows,
    render_trade_flows, trade_summary, _flow_to_rgb,
)
from engine.world import Biome                                          # noqa: E402


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _mk_candidate(rank, x_km, y_km, score, biome):
    return SettlementCandidate(
        rank=rank, macro_ix=int(x_km / 50), macro_iy=int(y_km / 50),
        macro_x_km=float(x_km), macro_y_km=float(y_km),
        score=float(score), biome=int(biome),
    )


def main() -> int:
    print("=" * 78)
    print("P60 — Wave 30 trade flow gravity smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API.
    ok = all(name in globals() for name in (
        "TradeConfig", "TradeNetwork",
        "compute_settlement_weights", "compute_trade_flows",
        "render_trade_flows", "trade_summary",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    gp = GenesisParams(seed=0xC0FFEE_60 & 0xFFFFFFFFFFFFFFFF,
                        resolution=64, n_plates=10,
                        erosion_iters=15, rain_iters=4)
    world = generate_world(gp)
    print(f"        world: land_frac="
          f"{world.diagnostics['land_fraction']:.2f}")

    candidates = find_settlement_candidates(
        world, n_candidates=6, min_spacing_km=400.0, seed=0xCAFE)
    network = build_road_network(world, candidates)
    print(f"        settlements={len(candidates)} edges={len(network.edges)}")

    # Step 2 — weights shape + dtype.
    cfg = TradeConfig()
    weights = compute_settlement_weights(candidates, world, cfg)
    ok = (weights.shape == (len(candidates),)
          and weights.dtype == np.float32
          and (weights > 0.0).all())
    print(_row("step 2 - weights shape + all positive",
               ok, f"shape={weights.shape} dtype={weights.dtype} "
                   f"min={float(weights.min()):.4f}"))
    if not ok:
        failures += 1

    # Step 3 — biome NPP bias : synthetic test with rainforest vs desert.
    synth = [
        _mk_candidate(0, 100.0, 100.0, 0.5, int(Biome.TROPICAL_RAINFOREST)),
        _mk_candidate(1, 100.0, 200.0, 0.5, int(Biome.HOT_DESERT)),
    ]
    w_synth = compute_settlement_weights(synth, world, cfg)
    ok = w_synth[0] > w_synth[1]
    print(_row("step 3 - rainforest weight > desert weight (NPP bias)",
               ok, f"rainforest={float(w_synth[0]):.4f} "
                   f"desert={float(w_synth[1]):.4f}"))
    if not ok:
        failures += 1

    # Step 4 — flow matrix symmetric.
    trade = compute_trade_flows(candidates, world, network, cfg)
    flows = trade.flows
    ok = (flows.shape == (len(candidates), len(candidates))
          and np.allclose(flows, flows.T))
    print(_row("step 4 - flow matrix symmetric",
               ok, f"shape={flows.shape} "
                   f"diff_norm={float(np.abs(flows - flows.T).max()):.6f}"))
    if not ok:
        failures += 1

    # Step 5 — gravity sanity : a larger weight pair should give larger
    # flow when distances are similar.
    # Find two edges with similar lengths and check that the one with
    # higher product of weights has higher flow.
    if len(network.edges) >= 2:
        edges_by_len = sorted(network.edges, key=lambda e: e.length_km)
        # Two edges with very different weight products.
        rank_to_idx = {c.rank: i for i, c in enumerate(candidates)}

        def edge_weight_product(e):
            i = rank_to_idx.get(e.from_rank, -1)
            j = rank_to_idx.get(e.to_rank, -1)
            if i < 0 or j < 0:
                return 0.0
            return float(weights[i] * weights[j])

        # Sort edges by w_i*w_j / dist^beta — that's exactly the flow.
        # So if we sort by raw flow and find the strongest, it should
        # also have one of the highest weight products.
        ranked = sorted(
            network.edges,
            key=lambda e: trade.edge_flow.get(
                tuple(sorted((e.from_rank, e.to_rank))), 0.0),
            reverse=True,
        )
        if len(ranked) >= 2:
            top = ranked[0]
            bottom = ranked[-1]
            top_wp = edge_weight_product(top)
            bot_wp = edge_weight_product(bottom)
            top_dist = max(top.length_km, 1.0)
            bot_dist = max(bottom.length_km, 1.0)
            beta = cfg.beta_distance
            top_predict = top_wp / (top_dist ** beta)
            bot_predict = bot_wp / (bot_dist ** beta)
            ok = top_predict >= bot_predict - 1e-6
            print(_row("step 5 - top-flow edge has highest w_i*w_j/d^beta",
                       ok, f"top={top_predict:.6e} bot={bot_predict:.6e}"))
            if not ok:
                failures += 1
        else:
            print(_row("step 5 - too few edges to compare (skipped)",
                       True, ""))
    else:
        print(_row("step 5 - too few edges to compare (skipped)",
                   True, ""))

    # Step 6 — only MST-connected pairs have nonzero flow.
    rank_to_idx = {c.rank: i for i, c in enumerate(candidates)}
    mst_pairs = set()
    for e in network.edges:
        i = rank_to_idx[e.from_rank]
        j = rank_to_idx[e.to_rank]
        mst_pairs.add((min(i, j), max(i, j)))
    extraneous = 0
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            if flows[i, j] > 0 and (i, j) not in mst_pairs:
                extraneous += 1
    ok = extraneous == 0
    print(_row("step 6 - only MST pairs have nonzero flow",
               ok, f"extraneous_pairs={extraneous}"))
    if not ok:
        failures += 1

    # Step 7 — determinism.
    trade2 = compute_trade_flows(candidates, world, network, cfg)
    ok = (np.array_equal(trade.flows, trade2.flows)
          and np.array_equal(trade.weights, trade2.weights)
          and trade.edge_flow == trade2.edge_flow)
    print(_row("step 7 - determinism (same inputs → same flows)",
               ok, f"flows_match={np.array_equal(trade.flows, trade2.flows)}"))
    if not ok:
        failures += 1

    # Step 8 — render paints magnitude-coloured edges.
    with tempfile.TemporaryDirectory() as td:
        png_path = os.path.join(td, "trade.png")
        rgb = render_trade_flows(world, network, candidates, trade,
                                   path=png_path, max_radius_px=2)
        # Find an MST cell : its colour should be in the yellow-red range
        # (R high, G mid, B low) — different from the default macro
        # palette.
        any_yellow = False
        for edge in network.edges:
            for (py, px) in edge.path[:3]:
                if 0 <= py < rgb.shape[0] and 0 <= px < rgb.shape[1]:
                    r, g, b = rgb[py, px]
                    if r >= 180 and g <= 250 and b <= 120:
                        any_yellow = True
                        break
            if any_yellow:
                break
        ok = (rgb.shape == (gp.resolution, gp.resolution, 3)
              and os.path.exists(png_path)
              and os.path.getsize(png_path) > 100
              and any_yellow)
        print(_row("step 8 - render paints flow-coloured roads",
                   ok, f"any_warm_pixel={any_yellow} "
                       f"png_bytes={os.path.getsize(png_path)}"))
        if not ok:
            failures += 1

    # Step 9 — summary.
    summary = trade_summary(candidates, trade)
    ok = (summary["n_settlements"] == len(candidates)
          and summary["total_volume"] >= 0.0
          and summary["weight_min"] > 0.0
          and "top_routes" in summary)
    print(_row("step 9 - trade summary plausible",
               ok, f"n={summary['n_settlements']} "
                   f"total={summary['total_volume']} "
                   f"dominant_rank={summary['dominant_city_rank']}"))
    if not ok:
        failures += 1

    # Dump.
    print(f"\nTrade summary: {summary}")
    print(f"_flow_to_rgb(0.0)={_flow_to_rgb(0.0)} "
          f"(0.5)={_flow_to_rgb(0.5)} (1.0)={_flow_to_rgb(1.0)}")

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
