"""P78 — PBR-lite macro render (normals + specular) smoke."""
from __future__ import annotations

import io
import os
import sys
import traceback

import numpy as np

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.world_genesis import GenesisParams, generate_world  # noqa: E402
from engine.world_render import (  # noqa: E402
    surface_normals, specular_sun, render_macro_pbr_lite, signature,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P78 — PBR-lite render smoke")
    print("=" * 78)
    failures = 0
    world = generate_world(GenesisParams(seed=0xEB000001, resolution=32))
    cell_km = world.params.map_size_km / world.params.resolution
    cell_m = cell_km * 1000.0
    n = surface_normals(world.elevation_m, cell_size_m=cell_m)
    ok = n.shape == (*world.elevation_m.shape, 3)
    norm_len = float(np.sqrt((n ** 2).sum(axis=-1)).mean())
    ok = ok and norm_len > 0.99
    print(_row("surface_normals", ok, f"|n|_mean={norm_len:.3f}"))
    if not ok:
        failures += 1
    rgb = render_macro_pbr_lite(world)
    ok = rgb.shape == (*world.elevation_m.shape, 3) and rgb.dtype == "uint8"
    sig1 = signature(rgb)
    sig2 = signature(render_macro_pbr_lite(world))
    ok = ok and sig1 == sig2
    print(_row("render_macro_pbr_lite deterministic", ok, sig1[:16]))
    if not ok:
        failures += 1
    base = render_macro_pbr_lite(world)
    spec = specular_sun(base, n, specular_strength=0.5)
    ok = int(spec.mean()) >= int(base.mean())
    print(_row("specular brightens", ok))
    if not ok:
        failures += 1
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
