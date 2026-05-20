"""P57 — Wave 27 world render smoke.

Validates :mod:`engine.world_render` : hillshade, biome colours,
macro/chunk/pipeline renderers, PNG output.

  1. Public API surface.
  2. Hillshade returns (H, W) float32 in [0, 1].
  3. Biome colour map covers all 12 Whittaker classes.
  4. render_macro_world returns (R, R, 3) uint8 + writes PNG.
  5. River overlay actually paints river_mask cells in blue.
  6. render_chunk returns upsampled image + writes PNG.
  7. render_pipeline_demo returns 2×2 grid + writes PNG.
  8. Deterministic : two renders of the same input → identical signature.
  9. PNG file on disk is non-empty + readable back.
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

from engine.world import generate_chunk, TerrainParams, Biome           # noqa: E402
from engine.world_genesis import (GenesisParams, generate_world,        # noqa: E402
                                    make_anchor)
from engine.world_render import (                                       # noqa: E402
    BIOME_COLOURS, biome_color_map, hillshade, hypsometric_tint,
    render_macro_world, render_chunk, render_pipeline_demo,
    MacroRenderOptions, ChunkRenderOptions, signature, _save_png,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P57 — Wave 27 world render smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API.
    ok = all(name in globals() for name in (
        "BIOME_COLOURS", "biome_color_map", "hillshade",
        "hypsometric_tint", "render_macro_world", "render_chunk",
        "render_pipeline_demo", "signature",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Build a small genesis world.
    gp = GenesisParams(seed=0xC0FFEE_57 & 0xFFFFFFFFFFFFFFFF,
                        resolution=64, n_plates=10,
                        erosion_iters=15, rain_iters=4)
    world = generate_world(gp)

    # Step 2 — hillshade in [0, 1] of correct shape.
    h = hillshade(world.elevation_m, cell_size_m=30.0)
    ok = (h.shape == world.elevation_m.shape
          and h.dtype == np.float32
          and h.min() >= 0.0 and h.max() <= 1.0)
    print(_row("step 2 - hillshade shape + range",
               ok, f"shape={h.shape} dtype={h.dtype} "
                   f"min={float(h.min()):.3f} max={float(h.max()):.3f}"))
    if not ok:
        failures += 1

    # Step 3 — biome palette covers 12 Whittaker classes.
    ok = (all(int(b) in BIOME_COLOURS for b in Biome)
          and all(BIOME_COLOURS[int(b)].dtype == np.uint8 for b in Biome))
    print(_row("step 3 - palette covers 12 biomes (uint8 RGB)",
               ok, f"len(palette)={len(BIOME_COLOURS)}"))
    if not ok:
        failures += 1

    # Step 4 — render_macro_world returns (R, R, 3) uint8.
    with tempfile.TemporaryDirectory() as td:
        macro_path = os.path.join(td, "macro.png")
        macro_rgb = render_macro_world(world, path=macro_path)
        ok = (macro_rgb.shape == (gp.resolution, gp.resolution, 3)
              and macro_rgb.dtype == np.uint8
              and os.path.exists(macro_path)
              and os.path.getsize(macro_path) > 100)
        print(_row("step 4 - macro render shape + PNG written",
                   ok, f"shape={macro_rgb.shape} "
                       f"png_bytes={os.path.getsize(macro_path) if os.path.exists(macro_path) else 0}"))
        if not ok:
            failures += 1

        # Step 5 — river overlay paints river_mask cells.
        # Find a known river cell.
        ys, xs = np.where(world.river_mask)
        if len(ys) > 0:
            ry, rx = int(ys[0]), int(xs[0])
            opts = MacroRenderOptions(draw_rivers=True)
            with_river = render_macro_world(world, options=opts)
            opts_no_river = MacroRenderOptions(draw_rivers=False)
            no_river = render_macro_world(world, options=opts_no_river)
            r_pixel = with_river[ry, rx]
            n_pixel = no_river[ry, rx]
            ok = (not np.array_equal(r_pixel, n_pixel)
                  and tuple(r_pixel) == opts.river_rgb)
            print(_row("step 5 - river overlay paints river cells",
                       ok, f"river_rgb={tuple(int(v) for v in r_pixel)} "
                           f"expect={opts.river_rgb}"))
            if not ok:
                failures += 1
        else:
            print(_row("step 5 - river overlay (no rivers in world)",
                       True, "skipped"))

        # Step 6 — render_chunk works (uses arbitrary anchored chunk).
        anchor = make_anchor(world)
        chunk = generate_chunk(int(gp.seed), (100, 100, 0),
                                TerrainParams(), genesis=anchor)
        chunk_path = os.path.join(td, "chunk.png")
        chunk_opts = ChunkRenderOptions(upsample=2)
        chunk_rgb = render_chunk(chunk, path=chunk_path, options=chunk_opts)
        expected = (chunk.height.shape[0] * 2, chunk.height.shape[1] * 2, 3)
        ok = (chunk_rgb.shape == expected
              and chunk_rgb.dtype == np.uint8
              and os.path.exists(chunk_path)
              and os.path.getsize(chunk_path) > 100)
        print(_row("step 6 - chunk render upsampled + PNG written",
                   ok, f"shape={chunk_rgb.shape} "
                       f"png_bytes={os.path.getsize(chunk_path) if os.path.exists(chunk_path) else 0}"))
        if not ok:
            failures += 1

        # Step 7 — pipeline demo 2x2.
        demo_path = os.path.join(td, "demo.png")
        demo_rgb = render_pipeline_demo(world, chunk_coord=(100, 100, 0),
                                          path=demo_path)
        # Expected shape: 2x chunk_rgb default upsample 4.
        ok = (demo_rgb.dtype == np.uint8 and demo_rgb.shape[2] == 3
              and demo_rgb.shape[0] == demo_rgb.shape[1]  # square
              and os.path.exists(demo_path))
        print(_row("step 7 - pipeline 2x2 demo + PNG written",
                   ok, f"shape={demo_rgb.shape} "
                       f"png_bytes={os.path.getsize(demo_path) if os.path.exists(demo_path) else 0}"))
        if not ok:
            failures += 1

        # Step 8 — determinism : two renders match bit-for-bit.
        macro_a = render_macro_world(world)
        macro_b = render_macro_world(world)
        sig_a = signature(macro_a)
        sig_b = signature(macro_b)
        ok = (sig_a == sig_b and np.array_equal(macro_a, macro_b))
        print(_row("step 8 - determinism (same input → identical PNG)",
                   ok, f"sig={sig_a[:16]}..."))
        if not ok:
            failures += 1

        # Step 9 — PNG round-trip readable via PIL.
        try:
            from PIL import Image
            with Image.open(macro_path) as im:
                im_arr = np.array(im)
            ok = (im_arr.shape == macro_rgb.shape
                  and np.array_equal(im_arr, macro_rgb))
            print(_row("step 9 - PNG round-trips byte-identical",
                       ok, f"loaded_shape={im_arr.shape}"))
            if not ok:
                failures += 1
        except ImportError:
            print(_row("step 9 - PIL not available (skipped)", True, ""))

    print(f"\nFinal renders dropped to a temp dir — already cleaned up.")
    print(f"Run interactively for persistent PNGs :")
    print(f"  from engine.world_render import render_macro_world")
    print(f"  render_macro_world(world, path='macro.png')")

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
