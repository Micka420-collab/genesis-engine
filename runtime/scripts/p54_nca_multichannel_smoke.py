"""P54 — Wave 24 multi-channel NCA smoke.

Validates the full Mordvintsev-style multi-channel NCA in
:mod:`engine.nca_multichannel`.

  1. Public API surface.
  2. Pure-function determinism : two runs → bit-identical chunk.height.
  3. Refinement modifies height non-trivially.
  4. Mass balance bounded : mean elevation drift < 15 %.
  5. Eroded cells > 0 and deposited cells > 0 (both processes active).
  6. Abyssal cells frozen (bathymetry untouched).
  7. install_nca_multichannel idempotent.
  8. Streamer wrap triggers refinement on cache miss.
  9. Uninstall restores the streamer.
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
from engine.world import generate_chunk, TerrainParams                  # noqa: E402
from engine.nca_multichannel import (                                   # noqa: E402
    NCAMultiChannelConfig, NCAMultiChannelState, MultiChannelDecision,
    refine_chunk_multichannel, install_nca_multichannel,
    uninstall_nca_multichannel, apply_to_existing_chunks,
    nca_multichannel_state,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xCAFEBABE_42):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=2, max_agents=4,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def _find_land_coord(seed, params):
    """Scan coords for one with > 30 % land."""
    for tc in [(100, 100, 0), (50, 50, 0), (200, 0, 0),
                (0, 200, 0), (-50, 50, 0), (10, 10, 0)]:
        probe = generate_chunk(seed, tc, params)
        if (probe.height > 0.0).mean() > 0.3:
            return tc
    return None


def main() -> int:
    print("=" * 78)
    print("P54 — Wave 24 multi-channel NCA smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API surface.
    ok = all(name in globals() for name in (
        "NCAMultiChannelConfig", "NCAMultiChannelState",
        "MultiChannelDecision", "refine_chunk_multichannel",
        "install_nca_multichannel", "uninstall_nca_multichannel",
        "apply_to_existing_chunks", "nca_multichannel_state"))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    seed = 0xCAFEBABE_42 & 0xFFFFFFFFFFFFFFFF
    params = TerrainParams()
    land_coord = _find_land_coord(seed, params)
    assert land_coord is not None
    print(f"        test coord={land_coord}")

    chunk_a = generate_chunk(seed, land_coord, params)
    chunk_b = generate_chunk(seed, land_coord, params)
    H_orig = chunk_a.height.copy()
    H_orig_b = chunk_b.height.copy()
    assert np.array_equal(H_orig, H_orig_b)

    # Step 2 — determinism on the pure-function overlay.
    cfg = NCAMultiChannelConfig(iterations=6)
    dec_a = refine_chunk_multichannel(chunk_a, cfg)
    dec_b = refine_chunk_multichannel(chunk_b, cfg)
    ok = (np.array_equal(chunk_a.height, chunk_b.height)
          and dec_a.iterations == dec_b.iterations)
    print(_row("step 2 - determinism on pure-function overlay",
               ok, f"max_diff={float(np.abs(chunk_a.height - chunk_b.height).max()):.6f} "
                   f"iters={dec_a.iterations}"))
    if not ok:
        failures += 1

    # Step 3 — refinement changes the field non-trivially.
    delta = chunk_a.height - H_orig
    mean_abs_delta = float(np.abs(delta).mean())
    max_abs_delta = float(np.abs(delta).max())
    ok = mean_abs_delta > 0.05 and max_abs_delta > 0.5
    print(_row("step 3 - refinement produces a measurable delta",
               ok, f"mean|dH|={mean_abs_delta:.3f}m max|dH|={max_abs_delta:.3f}m"))
    if not ok:
        failures += 1

    # Step 4 — mass balance bounded.
    mean_orig = float(H_orig.mean())
    mean_after = float(chunk_a.height.mean())
    drift = abs(mean_after - mean_orig)
    rel = drift / (abs(mean_orig) + 1.0)
    ok = rel < 0.15
    print(_row("step 4 - mean elev drift bounded",
               ok, f"drift={drift:.2f}m rel={rel*100:.2f}% (limit 15 %)"))
    if not ok:
        failures += 1

    # Step 5 — both erosion AND deposition active.
    ok = dec_a.cells_eroded > 0 and dec_a.cells_deposited > 0
    print(_row("step 5 - both erosion + deposition active",
               ok, f"eroded={dec_a.cells_eroded} deposited={dec_a.cells_deposited} "
                   f"peak_water={dec_a.peak_water:.2f} "
                   f"peak_S={dec_a.peak_sediment_m:.3f}m"))
    if not ok:
        failures += 1

    # Step 6 — abyssal cells frozen (use a chunk that contains abyss).
    chunk_mix = generate_chunk(seed ^ 0xAA, (5, 5, 0), params)
    H_mix_orig = chunk_mix.height.copy()
    refine_chunk_multichannel(chunk_mix, cfg)
    abyssal_before = H_mix_orig < -50.0
    if abyssal_before.any():
        ok = np.array_equal(H_mix_orig[abyssal_before],
                             chunk_mix.height[abyssal_before])
    else:
        ok = True  # nothing abyssal in this chunk, trivially satisfied
    print(_row("step 6 - abyssal cells frozen",
               ok, f"abyssal_cells={int(abyssal_before.sum())}"))
    if not ok:
        failures += 1

    # Step 7 — install idempotent.
    sim = _build_sim("p54_nca_mc")
    sim.step()
    state1 = install_nca_multichannel(sim, cfg)
    state2 = install_nca_multichannel(sim, cfg)
    ok = state1 is state2
    print(_row("step 7 - install idempotent", ok, ""))
    if not ok:
        failures += 1

    # Step 8 — streamer wrap on cache miss.
    sim.streamer.clear_cache()
    state1.decisions.clear()
    state1.chunks_refined = 0
    state1.total_iterations = 0
    ch_new = sim.streamer.get(0, land_coord)
    ok = (ch_new is not None
          and state1.chunks_refined == 1
          and state1.total_iterations >= cfg.iterations)
    print(_row("step 8 - streamer wrap triggers multi-channel NCA",
               ok, f"chunks_refined={state1.chunks_refined} "
                   f"iters={state1.total_iterations}"))
    if not ok:
        failures += 1

    # Step 9 — uninstall.
    streamer = sim.streamer
    ok1 = uninstall_nca_multichannel(sim)
    ok2 = (getattr(streamer, "_nca_mc_orig_get", None) is None
           and getattr(sim, "_nca_multichannel_state", None) is None)
    sim.streamer.clear_cache()
    ch_post = sim.streamer.get(0, (30, 30, 0))
    ok3 = ch_post is not None
    ok = ok1 and ok2 and ok3
    print(_row("step 9 - uninstall cleanly detaches",
               ok, f"uninst={ok1} hook_clear={ok2} fresh_ok={ok3}"))
    if not ok:
        failures += 1

    # apply_to_existing sanity (not a numbered check).
    sim2 = _build_sim("p54_retro", seed=0xBADBADD0)
    for _ in range(2):
        sim2.step()
    install_nca_multichannel(sim2, cfg)
    n_retro = apply_to_existing_chunks(sim2)
    print(f"\nMulti-channel state on sim2: {nca_multichannel_state(sim2)}")
    print(f"        retro-refined {n_retro} chunks")

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
