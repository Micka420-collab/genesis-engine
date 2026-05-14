"""Multi-region Genesis demo — proves the engine is location-agnostic.

Builds 4 worlds on different continents, runs each for 400 ticks, exports
PNG cartographic maps + GeoTIFF heightmaps + JSON snapshots, and saves
everything via :mod:`engine.world_library`.

Regions chosen for biome diversity:
  * Lausanne (Léman shore)       — temperate, mountains, lake
  * Eastern Sahara (Egypt)        — hot desert, ergs
  * Western Amazon (Manaus)       — tropical rainforest
  * Reykjavík (Iceland)           — subarctic, glaciers, coastline

Output : ``runtime/exports/multi_region_<region>/`` per region.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.world_builder import WorldBuilder
from engine.world_export import (export_geotiff, export_png_map,
                                  export_json_snapshot)
from engine.world_library import save_world

REGIONS = [
    {"name": "lausanne",  "lat": 46.510,  "lon":   6.633, "founders": 20,
     "blurb": "Léman north shore — temperate, mixed forest + lake"},
    {"name": "sahara",    "lat": 25.700,  "lon":  29.000, "founders": 12,
     "blurb": "Eastern Sahara (Egypt) — hot desert"},
    {"name": "amazon",    "lat": -3.110,  "lon": -60.020, "founders": 18,
     "blurb": "Manaus area — tropical rainforest"},
    {"name": "reykjavik", "lat": 64.140,  "lon": -21.940, "founders": 14,
     "blurb": "Reykjavík — subarctic, oceanic, glacial"},
]


def run_region(region: dict) -> dict:
    print(f"\n=== {region['name']} — {region['blurb']} ===")
    t0 = time.monotonic()
    world = (WorldBuilder(region["name"])
             .anchor(region["lat"], region["lon"])
             .size_km(2.0)
             .founders(region["founders"])
             .cultures(2)
             .max_agents(400)
             .spawn_radius_m(200.0)
             .build())
    setup_s = time.monotonic() - t0

    print(f"  built in {setup_s:.1f}s — anchor {region['lat']:.3f}, {region['lon']:.3f}")
    print(f"  spawned {world.n_spawned} agents")

    # Short run (400 ticks) — enough for veg + a few inventions.
    t1 = time.monotonic()
    for _ in range(400):
        world.step()
    run_s = time.monotonic() - t1

    summary = world.summary()
    print(f"  ran 400 ticks in {run_s:.1f}s — alive {world.n_alive}/{world.n_spawned}")
    if "l1" in summary:
        print(f"  L1 hits/misses: {summary['l1']}")
    if "l2" in summary:
        l2 = summary["l2"]
        print(f"  L2 chunks={l2.get('chunks')}, "
              f"mean slope {l2.get('mean_slope_deg')}°, "
              f"lake {l2.get('lake_cells_pct'):.1%}, "
              f"impassable {l2.get('impassable_pct'):.1%}")
        veg = l2.get("veg_distribution") or {}
        if veg:
            dominant = max(veg.items(), key=lambda kv: kv[1])
            print(f"  L2 dominant vegetation: {dominant[0]} ({dominant[1]:.1%})")

    # Exports
    export_dir = os.path.join(ROOT, "exports", f"multi_region_{region['name']}")
    os.makedirs(export_dir, exist_ok=True)

    export_png_map(world, os.path.join(export_dir, "map.png"))
    print(f"  wrote {os.path.join(export_dir, 'map.png')}")

    try:
        export_geotiff(world, "height", os.path.join(export_dir, "height.tif"))
        print(f"  wrote {os.path.join(export_dir, 'height.tif')}")
        export_geotiff(world, "biome", os.path.join(export_dir, "biome.tif"))
        print(f"  wrote {os.path.join(export_dir, 'biome.tif')}")
        export_geotiff(world, "slope_deg", os.path.join(export_dir, "slope.tif"))
        print(f"  wrote {os.path.join(export_dir, 'slope.tif')}")
    except Exception as e:
        print(f"  geotiff export skipped: {type(e).__name__}: {e}")

    export_json_snapshot(world, os.path.join(export_dir, "snapshot.json"))
    print(f"  wrote {os.path.join(export_dir, 'snapshot.json')}")

    # Library save (no chunks — too big × 4)
    save_path = save_world(world, name=f"demo_{region['name']}",
                           save_chunks=False)
    print(f"  saved library entry: {save_path}")

    return {"region": region["name"], "summary": summary,
            "setup_s": round(setup_s, 1), "run_s": round(run_s, 1)}


def main() -> int:
    results = []
    for region in REGIONS:
        try:
            results.append(run_region(region))
        except Exception as exc:
            import traceback
            print(f"  REGION FAILED: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            results.append({"region": region["name"], "error": str(exc)})

    out_path = os.path.join(ROOT, "exports", "multi_region_summary.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n→ wrote summary: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
