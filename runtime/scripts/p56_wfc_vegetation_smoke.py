"""P56 — Wave 26 WFC vegetation distribution smoke.

Validates the Wave Function Collapse pass that replaces ``chunk.wood``'s
uniform-per-biome blob with an emergent textured tile layout.

  1. Public API surface present.
  2. Adjacency table is symmetric + reflexive.
  3. Determinism : two ``run_wfc_on_chunk`` calls on identical inputs
     produce bit-identical tile grids.
  4. Forest biome → majority forest/edge tiles in the output.
  5. Desert biome → majority bare/grass tiles in the output.
  6. **No adjacency violations** : the propagated tile grid respects
     the compatibility table (``count_adjacency_violations == 0``).
  7. chunk.wood is now patterned (variance > 0, not uniform).
  8. Install + streamer wrap : fresh cache miss triggers WFC pass.
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
from engine.world import (generate_chunk, TerrainParams, Biome,         # noqa: E402
                           CHUNK_SIZE)
from engine.wfc_vegetation import (                                     # noqa: E402
    WFCVegetationConfig, WFCVegetationState, WFCDecision,
    run_wfc_on_chunk, install_wfc_vegetation, uninstall_wfc_vegetation,
    apply_to_existing_chunks, wfc_vegetation_state,
    count_adjacency_violations,
    ADJ, BIOME_TILE_PRIORS, TILE_NAMES, WOOD_PER_TILE, N_TILES,
    T_OCEAN, T_BARE, T_GRASS, T_SHRUB, T_EDGE, T_FOREST, T_WATER_EDGE,
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


def _force_biome(chunk, biome_value: int) -> None:
    """Overwrite chunk.biome uniformly + zero water so the WFC water
    override doesn't dominate. Used to isolate biome→tile prior behaviour
    in the smoke tests below."""
    chunk.biome[:] = np.uint8(biome_value)
    chunk.water[:] = 0.0


def main() -> int:
    print("=" * 78)
    print("P56 — Wave 26 WFC vegetation smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API surface.
    ok = all(name in globals() for name in (
        "WFCVegetationConfig", "WFCVegetationState", "WFCDecision",
        "run_wfc_on_chunk", "install_wfc_vegetation",
        "uninstall_wfc_vegetation", "apply_to_existing_chunks",
        "wfc_vegetation_state", "count_adjacency_violations",
        "ADJ", "BIOME_TILE_PRIORS", "TILE_NAMES", "WOOD_PER_TILE",
    ))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Step 2 — adjacency table is symmetric + reflexive.
    sym = bool(np.array_equal(ADJ, ADJ.T))
    refl = bool(np.all(np.diag(ADJ)))
    ok = sym and refl
    print(_row("step 2 - adjacency table symmetric + reflexive",
               ok, f"sym={sym} refl={refl}"))
    if not ok:
        failures += 1

    seed = 0xC0FFEE_56 & 0xFFFFFFFFFFFFFFFF
    params = TerrainParams()

    # Step 3 — determinism : same chunk + same seed → identical tiles.
    base_chunk_a = generate_chunk(seed, (100, 100, 0), params)
    base_chunk_b = generate_chunk(seed, (100, 100, 0), params)
    cfg = WFCVegetationConfig(wfc_grid_size=16, mute_chunk_wood=True)
    dec_a = run_wfc_on_chunk(base_chunk_a, sim_seed=seed, cfg=cfg)
    dec_b = run_wfc_on_chunk(base_chunk_b, sim_seed=seed, cfg=cfg)
    ok = (np.array_equal(dec_a.tiles_grid, dec_b.tiles_grid)
          and np.array_equal(base_chunk_a.wood, base_chunk_b.wood))
    print(_row("step 3 - determinism on identical inputs",
               ok, f"max_tile_diff={int(np.abs(dec_a.tiles_grid.astype(int) - dec_b.tiles_grid.astype(int)).max())} "
                   f"wood_match={np.array_equal(base_chunk_a.wood, base_chunk_b.wood)}"))
    if not ok:
        failures += 1

    # Step 4 — forest biome → majority forest/edge tiles.
    forest_chunk = generate_chunk(seed, (100, 100, 0), params)
    _force_biome(forest_chunk, int(Biome.TEMPERATE_FOREST))
    dec_for = run_wfc_on_chunk(forest_chunk, sim_seed=seed, cfg=cfg)
    forest_tiles = dec_for.tile_counts.get(T_FOREST, 0)
    edge_tiles = dec_for.tile_counts.get(T_EDGE, 0)
    total = sum(dec_for.tile_counts.values())
    forest_frac = (forest_tiles + edge_tiles) / max(total, 1)
    ok = forest_frac >= 0.6
    print(_row("step 4 - TEMPERATE_FOREST → ≥ 60% forest/edge tiles",
               ok, f"forest+edge={forest_tiles + edge_tiles}/{total} ({forest_frac*100:.1f}%)"))
    if not ok:
        failures += 1

    # Step 5 — desert biome → majority bare/grass tiles.
    desert_chunk = generate_chunk(seed, (100, 100, 0), params)
    _force_biome(desert_chunk, int(Biome.HOT_DESERT))
    dec_des = run_wfc_on_chunk(desert_chunk, sim_seed=seed, cfg=cfg)
    bare_tiles = dec_des.tile_counts.get(T_BARE, 0)
    grass_tiles = dec_des.tile_counts.get(T_GRASS, 0)
    total_d = sum(dec_des.tile_counts.values())
    desert_frac = (bare_tiles + grass_tiles) / max(total_d, 1)
    ok = desert_frac >= 0.85
    print(_row("step 5 - HOT_DESERT → ≥ 85% bare/grass tiles",
               ok, f"bare+grass={bare_tiles + grass_tiles}/{total_d} ({desert_frac*100:.1f}%)"))
    if not ok:
        failures += 1

    # Step 6 — adjacency respected after WFC propagation.
    viol_for = count_adjacency_violations(dec_for.tiles_grid)
    viol_des = count_adjacency_violations(dec_des.tiles_grid)
    ok = viol_for == 0 and viol_des == 0
    print(_row("step 6 - 0 adjacency violations after WFC",
               ok, f"forest_violations={viol_for} desert_violations={viol_des}"))
    if not ok:
        failures += 1

    # Step 7 — chunk.wood is patterned (not uniform).
    wood_var = float(forest_chunk.wood.var())
    wood_min = float(forest_chunk.wood.min())
    wood_max = float(forest_chunk.wood.max())
    ok = wood_var > 5.0 and (wood_max - wood_min) > 10.0
    print(_row("step 7 - chunk.wood is patterned (not uniform)",
               ok, f"var={wood_var:.1f} range=[{wood_min:.1f}, {wood_max:.1f}]"))
    if not ok:
        failures += 1

    # Step 8 — install + streamer wrap.
    sim = _build_sim("p56_wfc")
    sim.step()
    state = install_wfc_vegetation(sim, cfg)
    state_again = install_wfc_vegetation(sim, cfg)
    idempotent = (state is state_again)
    # Force a fresh cache-miss to trigger the wrapper.
    sim.streamer.clear_cache()
    state.decisions.clear()
    state.chunks_processed = 0
    fresh_coord = (10, 10, 0)
    ch_fresh = sim.streamer.get(0, fresh_coord)
    ok = (idempotent and ch_fresh is not None
          and state.chunks_processed >= 1
          and fresh_coord in state.decisions)
    print(_row("step 8 - install idempotent + streamer wrap fires",
               ok, f"idemp={idempotent} chunks_processed={state.chunks_processed}"))
    if not ok:
        failures += 1

    # Step 9 — uninstall restores streamer.
    streamer = sim.streamer
    ok1 = uninstall_wfc_vegetation(sim)
    ok2 = (getattr(streamer, "_wfc_veg_orig_get", None) is None
           and getattr(sim, "_wfc_vegetation_state", None) is None)
    sim.streamer.clear_cache()
    ch_post = sim.streamer.get(0, (20, 20, 0))
    ok3 = ch_post is not None
    ok = ok1 and ok2 and ok3
    print(_row("step 9 - uninstall cleanly detaches",
               ok, f"uninst={ok1} hook_clear={ok2} fresh_ok={ok3}"))
    if not ok:
        failures += 1

    # Diagnostic dump.
    print("\nForest chunk tile counts:")
    for t, c in sorted(dec_for.tile_counts.items(), key=lambda kv: -kv[1]):
        if c > 0:
            print(f"  {TILE_NAMES[t]:14s} {c:4d}")
    print("\nDesert chunk tile counts:")
    for t, c in sorted(dec_des.tile_counts.items(), key=lambda kv: -kv[1]):
        if c > 0:
            print(f"  {TILE_NAMES[t]:14s} {c:4d}")

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
