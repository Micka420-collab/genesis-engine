"""P75 — Köppen full macro grid + FAIR metrics smoke."""
from __future__ import annotations

import io
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.world_genesis import GenesisParams, generate_world  # noqa: E402
from engine.koeppen_grid import (  # noqa: E402
    classify_koeppen_grid, fair_koeppen_manifest, harness_pass_rate,
    koeppen_metrics_from_world,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P75 — Köppen macro grid smoke")
    print("=" * 78)
    failures = 0
    world = generate_world(GenesisParams(seed=0xC055E001, resolution=64))
    kg = classify_koeppen_grid(
        world.temp_c, world.precip_mm, world.latitude_deg)
    ok = kg.shape == world.temp_c.shape and kg.dtype.kind == "U"
    print(_row("classify_koeppen_grid shape", ok, str(kg.shape)))
    if not ok:
        failures += 1
    m = koeppen_metrics_from_world(world)
    ok = m.harness_pass_rate >= 0.99 and m.land_cells > 100
    print(_row("harness + land cells", ok,
               f"pass={m.harness_pass_rate:.0%} land={m.land_cells}"))
    if not ok:
        failures += 1
    ok = 0.15 <= m.biome_coherence_rate <= 1.0
    print(_row("biome coherence", ok, f"{m.biome_coherence_rate:.2%}"))
    if not ok:
        failures += 1
    fair = fair_koeppen_manifest(world)
    ok = "koeppen_harness_pass_rate" in fair and fair["koeppen_land_cells"] > 0
    print(_row("fair_koeppen_manifest", ok, str(list(fair.keys())[:4])))
    if not ok:
        failures += 1
    ok = harness_pass_rate() >= 0.99
    print(_row("reference harness", ok))
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
