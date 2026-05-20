"""P68 — Wave 37 animation timelapse smoke.

  1. Public API surface.
  2. ``capture_timelapse`` returns expected count of frames.
  3. Each frame has valid (H, W, 3) uint8 RGB.
  4. Frames evolve : tick monotone + at least one signature change.
  5. Frame metadata fields populated (n_alive, n_clusters, etc.).
  6. Determinism : two captures same seed → identical frame signatures.
  7. ``frames_to_gif`` writes a valid GIF file (PIL can read back).
  8. ``frames_to_pngs`` writes N PNG files.
  9. ``history_to_manifest`` produces JSON-serializable summary.
"""
from __future__ import annotations

import io
import os
import sys
import json
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

from engine.sim import Simulation, SimConfig                            # noqa: E402
from engine.animation_timelapse import (                                # noqa: E402
    TimelapseConfig, TimelapseFrame, TimelapseHistory,
    capture_timelapse, frames_to_gif, frames_to_pngs,
    history_to_manifest, timelapse_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xC0FFEE_68):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=6, max_agents=15,
        bounds_km=(0.5, 0.5), spawn_radius_m=80.0,
        drive_accel=1500.0, cultures=2,
    )
    return Simulation(cfg)


def main() -> int:
    print("=" * 78)
    print("P68 — Wave 37 animation timelapse smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API surface.
    ok = all(name in globals() for name in (
        "TimelapseConfig", "TimelapseFrame", "TimelapseHistory",
        "capture_timelapse", "frames_to_gif", "frames_to_pngs",
        "history_to_manifest", "timelapse_summary",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Step 2 — capture_timelapse returns expected frames count.
    # Use a small custom renderer for fast smoke (iso is huge).
    def _tiny_render(s):
        n = s.agents.n_active
        alive = int(s.agents.alive[:n].sum())
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        # Encode alive count in red channel + tick in green channel.
        img[:, :, 0] = min(255, alive * 30)
        img[:, :, 1] = int(s.tick) % 256
        # Add a per-tick deterministic noise band so frames have unique sigs.
        for i in range(min(8, n)):
            row = int((s.agents.pos[i, 0] * 0.5 + 32) % 64)
            col = int((s.agents.pos[i, 1] * 0.5 + 32) % 64)
            img[row, col] = (255, 200, 100)
        return img

    sim = _build_sim("p68_capture")
    cfg = TimelapseConfig(n_ticks=30, capture_every=10,
                            use_isometric=False,
                            custom_renderer=_tiny_render)
    history = capture_timelapse(sim, cfg)
    # Expected frames : initial + at ticks 10, 20, 30.
    expected = 1 + (cfg.n_ticks // cfg.capture_every)
    ok = len(history.frames) == expected
    print(_row("step 2 - capture returns expected frame count",
               ok, f"frames={len(history.frames)} expected={expected}"))
    if not ok:
        failures += 1

    # Step 3 — each frame valid (H, W, 3) uint8.
    valid_frames = all(
        f.rgb is not None and f.rgb.dtype == np.uint8
        and len(f.rgb.shape) == 3 and f.rgb.shape[2] == 3
        and f.rgb.size > 0
        for f in history.frames
    )
    ok = valid_frames
    print(_row("step 3 - all frames are valid uint8 RGB",
               ok, f"shapes={[f.rgb.shape for f in history.frames[:3]]}"))
    if not ok:
        failures += 1

    # Step 4 — ticks monotone + at least one signature change.
    ticks = [f.tick for f in history.frames]
    monotone = all(ticks[i] <= ticks[i + 1] for i in range(len(ticks) - 1))
    sigs = {f.signature_hex for f in history.frames}
    ok = monotone and len(sigs) >= 2
    print(_row("step 4 - ticks monotone + frames evolve",
               ok, f"ticks={ticks} unique_sigs={len(sigs)}"))
    if not ok:
        failures += 1

    # Step 5 — metadata fields populated.
    f0 = history.frames[0]
    ok = (f0.n_alive >= 1
          and isinstance(f0.signature_hex, str) and len(f0.signature_hex) == 64
          and isinstance(f0.blood_min_l, float))
    print(_row("step 5 - frame metadata populated",
               ok, f"n_alive={f0.n_alive} sig_len={len(f0.signature_hex)} "
                   f"blood_min={f0.blood_min_l:.2f}"))
    if not ok:
        failures += 1

    # Step 6 — determinism.
    sim_a = _build_sim("p68_det_a")
    sim_b = _build_sim("p68_det_b")
    cfg_det = TimelapseConfig(n_ticks=30, capture_every=10,
                                use_isometric=False,
                                custom_renderer=_tiny_render)
    h_a = capture_timelapse(sim_a, cfg_det)
    h_b = capture_timelapse(sim_b, cfg_det)
    sigs_a = [f.signature_hex for f in h_a.frames]
    sigs_b = [f.signature_hex for f in h_b.frames]
    ok = sigs_a == sigs_b
    print(_row("step 6 - determinism (same seed → same signatures)",
               ok, f"match={sigs_a == sigs_b}"))
    if not ok:
        failures += 1

    # Step 7 — GIF export.
    with tempfile.TemporaryDirectory() as td:
        gif_path = os.path.join(td, "timelapse.gif")
        gif_ok = frames_to_gif(history, gif_path, duration_ms=200)
        gif_exists = os.path.exists(gif_path) and os.path.getsize(gif_path) > 100
        # Read back with PIL to confirm it's a valid animated GIF.
        try:
            from PIL import Image
            with Image.open(gif_path) as img:
                n_frames_in_gif = getattr(img, "n_frames", 1)
        except ImportError:
            n_frames_in_gif = -1
        except Exception:
            n_frames_in_gif = 0
        # Accept dedup : count distinct signatures.
        n_unique = len({f.signature_hex for f in history.frames})
        ok = (gif_ok and gif_exists
              and n_frames_in_gif >= max(1, n_unique - 1))
        print(_row("step 7 - GIF written + PIL reads it back",
                   ok, f"gif_ok={gif_ok} bytes="
                       f"{os.path.getsize(gif_path) if gif_exists else 0} "
                       f"n_frames_in_gif={n_frames_in_gif} n_unique={n_unique}"))
        if not ok:
            failures += 1

    # Step 8 — PNGs export.
    with tempfile.TemporaryDirectory() as td:
        n_written = frames_to_pngs(history, td, filename_prefix="evol")
        files = sorted(f for f in os.listdir(td) if f.endswith(".png"))
        ok = (n_written == len(history.frames)
              and len(files) == len(history.frames))
        print(_row("step 8 - PNG sequence written",
                   ok, f"n_written={n_written} files={len(files)}"))
        if not ok:
            failures += 1

    # Step 9 — manifest.
    with tempfile.TemporaryDirectory() as td:
        manifest_path = os.path.join(td, "manifest.json")
        manifest = history_to_manifest(history, path=manifest_path)
        ok = (manifest["n_frames"] == len(history.frames)
              and "config" in manifest
              and "frames" in manifest
              and len(manifest["frames"]) == len(history.frames)
              and os.path.exists(manifest_path))
        # Round-trip JSON validity.
        with open(manifest_path, encoding="utf-8") as fh:
            loaded = json.load(fh)
        ok = ok and loaded["n_frames"] == manifest["n_frames"]
        print(_row("step 9 - manifest JSON valid + round-trip",
                   ok, f"keys={sorted(manifest.keys())}"))
        if not ok:
            failures += 1

    # Diagnostic dump.
    summary = timelapse_summary(history)
    print(f"\nTimelapse summary: {summary}")

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
