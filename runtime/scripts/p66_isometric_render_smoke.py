"""P66 - Wave 36 isometric 2.5D renderer smoke.

Verifies the new ``engine.world_render_isometric`` module:

  1. Public API surface is exposed (every documented function present).
  2. ``project_iso(0,0,0)`` -> (0, 0). Basic projection identity.
  3. ``render_chunk_isometric`` returns a non-trivial (H, W, 3) uint8.
  4. PNG file written via PIL is non-empty.
  5. Hillshade introduces luminance variance across the rendered RGB.
  6. ``render_sim_isometric`` paints visible agent pixels.
  7. ``render_sim_isometric`` paints visible wounded-agent pixels when the
     anatomy module is installed and at least one agent is wounded.
  8. Determinism: two identical renders share an identical SHA-256.
  9. ``render_macro_isometric`` produces a valid (H, W, 3) PNG.

Writes ``journals/p66_isometric_render.json`` with the test summary +
the SHA-256 of each generated render.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
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

import numpy as np                                              # noqa: E402

from engine.sim import Simulation, SimConfig                    # noqa: E402
from engine.world import (CHUNK_SIDE_M, Biome, TerrainParams,    # noqa: E402
                          generate_chunk)
from engine.world_render_isometric import (                      # noqa: E402
    IsometricRenderOptions,
    project_iso,
    render_chunk_isometric,
    render_macro_isometric,
    render_sim_isometric,
    signature,
)


JOURNAL = os.path.abspath(os.path.join(ROOT, "journals",
                                       "p66_isometric_render.json"))
PNG_DIR = os.path.abspath(os.path.join(ROOT, "..", "docs", "renders"))


def _row(label: str, ok: bool, detail: str = "") -> str:
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _bgcolour_mask(img: np.ndarray,
                   options: IsometricRenderOptions) -> np.ndarray:
    br, bg, bb = options.background_rgb
    return ((img[:, :, 0] == br)
            & (img[:, :, 1] == bg)
            & (img[:, :, 2] == bb))


def _build_sim(name: str,
               *, founders: int = 8,
               max_agents: int = 40,
               bounds_km: float = 0.5,
               seed: int = 0xC0FFEE_F0F0_BEEF) -> Simulation:
    cfg = SimConfig(name=name,
                    seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=founders,
                    max_agents=max_agents,
                    bounds_km=(bounds_km, bounds_km),
                    spawn_radius_m=30.0)
    sim = Simulation(cfg)
    sim.bootstrap()
    return sim


def _restrict_chunks(sim, n_keep: int = 4) -> None:
    """Keep at most ``n_keep`` cached chunks so the render canvas stays
    affordable for the smoke (the sim grabs all chunks around agents,
    which may total dozens with founders > 0 and bounds_km > 0.5).
    """
    cache = sim.streamer.cache
    if len(cache) <= n_keep:
        return
    keep_coords = sorted(cache.keys())[:n_keep]
    keep_set = set(keep_coords)
    drop = [c for c in cache.keys() if c not in keep_set]
    for c in drop:
        cache.pop(c, None)
        sim.streamer.last_touch.pop(c, None)


def _try_install_anatomy_wound(sim) -> bool:
    """Inflict a synthetic wound on agent #0 even if the anatomy module is
    missing. Returns True if a wound is now visible to the renderer.
    """
    n = int(getattr(sim.agents, "n_active", 0))
    if n <= 0:
        return False

    # Try to load the real anatomy module first.
    try:
        from engine import anatomy as anat_mod  # type: ignore
        installer = getattr(anat_mod, "install_anatomy", None) or \
            getattr(anat_mod, "install", None)
        wounder = getattr(anat_mod, "inflict_wound", None)
        if installer is not None:
            installer(sim)
        if wounder is not None:
            wounder(sim, row=0, severity=0.7)
            if getattr(sim, "_anatomy_fields", None) is not None:
                return True
    except Exception:
        pass

    # Synthetic fallback — attach an _anatomy_fields shim ourselves so the
    # renderer's defensive lookup can fire. Read-only sim invariants are
    # preserved (we only set a private attribute, never mutate agents).
    class _AnatomyShim:
        def __init__(self, n_):
            self.wound_severity = np.zeros((n_,), dtype=np.float32)
    shim = _AnatomyShim(n)
    shim.wound_severity[0] = 0.7
    sim._anatomy_fields = shim
    return True


def main() -> int:
    print("=" * 78)
    print("P66 - Wave 36 isometric 2.5D renderer smoke")
    print("=" * 78)
    failures = 0
    journal: dict = {"checks": [], "renders": {}}

    if os.path.exists(JOURNAL):
        os.remove(JOURNAL)
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    os.makedirs(PNG_DIR, exist_ok=True)

    options = IsometricRenderOptions()

    # ------------------------------------------------------------------
    # Step 1 - Public API exposed
    # ------------------------------------------------------------------
    expected = ("IsometricRenderOptions", "project_iso", "render_chunk_isometric",
                "render_sim_isometric", "render_macro_isometric", "signature",
                "BIOME_COLOURS")
    import engine.world_render_isometric as wri
    missing = [n for n in expected if not hasattr(wri, n)]
    ok1 = not missing
    print(_row("public API surface complete", ok1,
               f"missing={missing}" if missing else "all 7 symbols present"))
    failures += int(not ok1)
    journal["checks"].append({"id": 1, "ok": ok1, "missing": missing})

    # ------------------------------------------------------------------
    # Step 2 - Projection identity: (0,0,0) -> (0,0)
    # ------------------------------------------------------------------
    sx, sy = project_iso(0.0, 0.0, 0.0, options)
    sx_x, sy_x = project_iso(1.0, 0.0, 0.0, options)
    sx_y, sy_y = project_iso(0.0, 1.0, 0.0, options)
    ok2a = abs(sx) < 1e-9 and abs(sy) < 1e-9
    ok2b = math.isclose(sx_x, options.tile_w * 0.5)
    ok2c = math.isclose(sx_y, -options.tile_w * 0.5)
    ok2 = ok2a and ok2b and ok2c
    print(_row("project_iso(0,0,0) == (0,0); x/y axis sane", ok2,
               f"px(1,0)={sx_x:.1f},{sy_x:.1f} px(0,1)={sx_y:.1f},{sy_y:.1f}"))
    failures += int(not ok2)
    journal["checks"].append({"id": 2, "ok": ok2})

    # ------------------------------------------------------------------
    # Step 3 - Single chunk render is non-trivial
    # ------------------------------------------------------------------
    chunk = generate_chunk(0xC0FFEE_DEAD_BEEF, (0, 0, 0), TerrainParams())
    img_chunk = render_chunk_isometric(chunk, options=options)
    bg_mask = _bgcolour_mask(img_chunk, options)
    bg_frac = float(bg_mask.mean())
    ok3a = (img_chunk.ndim == 3 and img_chunk.shape[2] == 3
            and img_chunk.dtype == np.uint8)
    # At most 90% of pixels are background (the rest is biome / faces).
    ok3b = bg_frac < 0.90
    # And the canvas has actual variance (i.e. not a single flat colour).
    ok3c = float(img_chunk.std()) > 5.0
    ok3 = ok3a and ok3b and ok3c
    print(_row("render_chunk_isometric returns non-trivial RGB", ok3,
               f"shape={img_chunk.shape} bg_frac={bg_frac:.3f} std={img_chunk.std():.1f}"))
    failures += int(not ok3)
    journal["checks"].append({"id": 3, "ok": ok3,
                              "bg_frac": bg_frac,
                              "std": float(img_chunk.std())})

    # ------------------------------------------------------------------
    # Step 4 - PNG saved successfully via PIL
    # ------------------------------------------------------------------
    png_chunk = os.path.join(PNG_DIR, "wave36_iso_chunk.png")
    try:
        img_path = render_chunk_isometric(chunk, path=png_chunk, options=options)
        png_size = os.path.getsize(png_chunk) if os.path.exists(png_chunk) else 0
    except Exception as exc:
        png_size = 0
        print(f"  (png save exception: {exc})")
    ok4 = png_size > 1024
    print(_row("PIL PNG written (>1 KiB)", ok4,
               f"size={png_size}B path={png_chunk}"))
    failures += int(not ok4)
    journal["checks"].append({"id": 4, "ok": ok4, "size_bytes": png_size,
                              "path": png_chunk})
    journal["renders"]["chunk_png"] = png_chunk

    # ------------------------------------------------------------------
    # Step 5 - Hillshade introduces luminance variance
    # ------------------------------------------------------------------
    options_flat = IsometricRenderOptions(hillshade_strength=0.0,
                                          draw_water=options.draw_water,
                                          draw_agents=False,
                                          draw_buildings=False)
    options_lit = IsometricRenderOptions(hillshade_strength=0.85,
                                         draw_water=options.draw_water,
                                         draw_agents=False,
                                         draw_buildings=False)
    img_flat = render_chunk_isometric(chunk, options=options_flat)
    img_lit = render_chunk_isometric(chunk, options=options_lit)
    std_flat = float(img_flat.std())
    std_lit = float(img_lit.std())
    # Lit render should show MORE variance than flat (hill bands light up).
    ok5 = std_lit > std_flat + 0.1
    print(_row("hillshade increases canvas luminance variance", ok5,
               f"std_flat={std_flat:.2f} std_lit={std_lit:.2f}"))
    failures += int(not ok5)
    journal["checks"].append({"id": 5, "ok": ok5,
                              "std_flat": std_flat, "std_lit": std_lit})

    # ------------------------------------------------------------------
    # Step 6 - Sim render shows agent pixels
    # ------------------------------------------------------------------
    sim = _build_sim("p66_step6", founders=8, bounds_km=0.5,
                     seed=0xC0FF_2026_5A5A)
    for _ in range(2):
        sim.step()
    _restrict_chunks(sim, n_keep=4)
    chunk_coords = list(sim.streamer.cache.keys())
    cx_min = min(c[0] for c in chunk_coords)
    cy_min = min(c[1] for c in chunk_coords)
    cx_max = max(c[0] for c in chunk_coords)
    cy_max = max(c[1] for c in chunk_coords)
    png_sim = os.path.join(PNG_DIR, "wave36_iso_sim.png")
    img_sim = render_sim_isometric(sim,
                                   chunks_range=(cx_min, cy_min, cx_max, cy_max),
                                   path=png_sim, options=options)
    ar, ag, ab = options.agent_rgb
    agent_mask = ((img_sim[:, :, 0] == ar)
                  & (img_sim[:, :, 1] == ag)
                  & (img_sim[:, :, 2] == ab))
    n_agent_px = int(agent_mask.sum())
    # We may not see agents if they spawned outside the kept chunks. In that
    # case, fall back to drawing them inside the chunks anyway by using
    # a fresh sim that fits in 1 chunk.
    if n_agent_px == 0:
        sim_alt = _build_sim("p66_step6_alt", founders=8, bounds_km=0.03,
                             seed=0xC0FF_2026_5A5A)
        for _ in range(2):
            sim_alt.step()
        _restrict_chunks(sim_alt, n_keep=4)
        chunk_coords = list(sim_alt.streamer.cache.keys())
        cx_min = min(c[0] for c in chunk_coords)
        cy_min = min(c[1] for c in chunk_coords)
        cx_max = max(c[0] for c in chunk_coords)
        cy_max = max(c[1] for c in chunk_coords)
        img_sim = render_sim_isometric(sim_alt,
                                       chunks_range=(cx_min, cy_min,
                                                     cx_max, cy_max),
                                       path=png_sim, options=options)
        agent_mask = ((img_sim[:, :, 0] == ar)
                      & (img_sim[:, :, 1] == ag)
                      & (img_sim[:, :, 2] == ab))
        n_agent_px = int(agent_mask.sum())
        sim = sim_alt
    ok6 = n_agent_px > 0
    print(_row("render_sim_isometric draws visible agents", ok6,
               f"agent_pixels={n_agent_px}"))
    failures += int(not ok6)
    journal["checks"].append({"id": 6, "ok": ok6,
                              "agent_pixels": n_agent_px})
    journal["renders"]["sim_png"] = png_sim

    # ------------------------------------------------------------------
    # Step 7 - Wounded agent overlay
    # ------------------------------------------------------------------
    sim_w = _build_sim("p66_step7", founders=8, bounds_km=0.03,
                       seed=0xC0FF_2026_3D3D)
    for _ in range(2):
        sim_w.step()
    installed = _try_install_anatomy_wound(sim_w)

    # Pick the chunk that contains the wounded agent (row=0) so the
    # marker is guaranteed to be inside the rendered canvas, then
    # extend the region by one chunk in each direction.
    wx, wy = float(sim_w.agents.pos[0, 0]), float(sim_w.agents.pos[0, 1])
    from engine.world import world_to_chunk as _w2c
    cwx, cwy, _ = _w2c(wx, wy)
    chunks_range = (cwx - 1, cwy - 1, cwx + 1, cwy + 1)
    # Make sure those chunks are cached.
    for cx_ in range(chunks_range[0], chunks_range[2] + 1):
        for cy_ in range(chunks_range[1], chunks_range[3] + 1):
            sim_w.streamer.get(sim_w.tick, (cx_, cy_, 0))

    img_w = render_sim_isometric(sim_w,
                                 chunks_range=chunks_range,
                                 options=options)
    wr, wg, wb = options.wounded_agent_rgb
    wound_mask = ((img_w[:, :, 0] == wr)
                  & (img_w[:, :, 1] == wg)
                  & (img_w[:, :, 2] == wb))
    n_wound_px = int(wound_mask.sum())
    ok7 = installed and n_wound_px > 0
    print(_row("wounded agent painted in wounded_agent_rgb", ok7,
               f"wounded_px={n_wound_px} (installer_ok={installed})"))
    failures += int(not ok7)
    journal["checks"].append({"id": 7, "ok": ok7,
                              "wounded_pixels": n_wound_px})

    # ------------------------------------------------------------------
    # Step 8 - Determinism: two renders -> same SHA-256
    # ------------------------------------------------------------------
    sig_a = signature(render_chunk_isometric(chunk, options=options))
    sig_b = signature(render_chunk_isometric(chunk, options=options))
    ok8 = sig_a == sig_b
    print(_row("two identical renders share SHA-256", ok8,
               f"sig={sig_a[:24]}…"))
    failures += int(not ok8)
    journal["checks"].append({"id": 8, "ok": ok8, "sig": sig_a})

    # ------------------------------------------------------------------
    # Step 9 - render_macro_isometric produces a valid PNG
    # ------------------------------------------------------------------
    # Build a small synthetic macro elevation grid.
    macro = np.zeros((24, 24), dtype=np.float32)
    yy, xx = np.meshgrid(np.linspace(-1, 1, 24),
                         np.linspace(-1, 1, 24), indexing="ij")
    macro = (1.0 - np.sqrt(xx * xx + yy * yy)).clip(0.0, 1.0) * 1800.0
    png_macro = os.path.join(PNG_DIR, "wave36_iso_macro.png")
    img_macro = render_macro_isometric(macro, path=png_macro, options=options)
    macro_ok_shape = (img_macro.ndim == 3 and img_macro.shape[2] == 3
                      and img_macro.dtype == np.uint8)
    macro_ok_var = float(img_macro.std()) > 5.0
    macro_size = os.path.getsize(png_macro) if os.path.exists(png_macro) else 0
    macro_ok_file = macro_size > 1024
    ok9 = macro_ok_shape and macro_ok_var and macro_ok_file
    print(_row("render_macro_isometric writes a valid PNG", ok9,
               f"shape={img_macro.shape} std={img_macro.std():.1f} png={macro_size}B"))
    failures += int(not ok9)
    journal["checks"].append({"id": 9, "ok": ok9,
                              "shape": list(img_macro.shape),
                              "png_size": macro_size,
                              "std": float(img_macro.std())})
    journal["renders"]["macro_png"] = png_macro

    print("-" * 78)
    if failures == 0:
        print("P66 isometric-render smoke : 9/9 PASS")
    else:
        print(f"P66 isometric-render smoke : FAILURES={failures}")

    journal["summary"] = {
        "passed": 9 - failures,
        "failed": failures,
        "total": 9,
    }
    with open(JOURNAL, "w", encoding="utf-8") as f:
        json.dump(journal, f, indent=2, sort_keys=True)
    print(f"journal: {JOURNAL}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
