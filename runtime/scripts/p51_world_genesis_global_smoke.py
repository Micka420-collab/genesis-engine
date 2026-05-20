"""P51 — Wave 22 world genesis global smoke.

Valide :mod:`engine.world_genesis_global` — un seul
:class:`engine.world_genesis.GenesisWorld` continental partagé entre N
régions, chacune ancrée à une portion via
:class:`engine.world_genesis.GenesisAnchor`.

  1. API publique exposée.
  2. ``build_or_load_global_world`` : génère + écrit le cache si
     inexistant ; second appel charge depuis le cache (signature
     identique).
  3. ``register_region`` : accepte des régions valides ; raise
     ``ValueError`` sur out-of-bounds.
  4. 2 régions enregistrées + 2 sims différentes : chaque
     ``attach_region_to_sim`` attache un anchor distinct ;
     ``sim.streamer.genesis`` n'est pas None.
  5. Les deux sims voient des macro elevations DIFFÉRENTES à leur coord
     (0, 0) car elles pointent sur des régions différentes.
  6. Les deux sims partagent la MÊME GenesisWorld
     (``id(state.world) == id(anchor1.world) == id(anchor2.world)``).
  7. ``find_inter_region_rivers`` retourne une liste cohérente
     (chaque entrée a ``from_region != to_region``).
  8. Déterminisme : deux ``build_or_load_global_world`` avec même
     config produisent le même ``world_signature``.
  9. Reporter ``global_state_summary`` cohérent.
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

import numpy as np                                                  # noqa: E402

from engine.sim import Simulation, SimConfig                        # noqa: E402
from engine.world_genesis import (                                  # noqa: E402
    sample_macro, world_signature,
)
from engine.world_genesis_global import (                           # noqa: E402
    GlobalGenesisConfig, GlobalGenesisState, RegionAnchor,
    attach_region_to_sim, build_or_load_global_world,
    find_inter_region_rivers, global_state_summary,
    register_region,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xBEEF_1234):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=2, max_agents=4,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def main() -> int:
    print("=" * 78)
    print("P51 — Wave 22 world genesis global smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API surface present.
    expected = (
        "GlobalGenesisConfig", "GlobalGenesisState", "RegionAnchor",
        "build_or_load_global_world", "register_region",
        "attach_region_to_sim", "find_inter_region_rivers",
        "global_state_summary",
    )
    ok = all(name in globals() for name in expected)
    print(_row("step 1 - public API exposed", ok,
               f"{len(expected)} names"))
    if not ok:
        failures += 1

    # Build config with a compact resolution so the smoke stays fast.
    # The world is big (6000 km) so regions can be far apart.
    map_size = 6000.0
    base_config_kwargs = dict(
        seed=0xCAFE_BABE & 0xFFFFFFFFFFFFFFFF,
        map_size_km=map_size,
        resolution=64,
        n_plates=12,
    )

    # Step 2 — cache write+read round-trip.
    with tempfile.TemporaryDirectory() as td:
        cache_path = os.path.join(td, "global_world.npz")
        cfg_a = GlobalGenesisConfig(cache_path=cache_path, **base_config_kwargs)

        # First call: file doesn't exist -> generate + save.
        wrote_file_before = os.path.isfile(cache_path)
        state_a = build_or_load_global_world(cfg_a)
        wrote_file_after = os.path.isfile(cache_path)
        sig_a = world_signature(state_a.world)
        cache_size = os.path.getsize(cache_path) if wrote_file_after else 0

        # Second call: file exists -> should load (signature equal).
        cfg_b = GlobalGenesisConfig(cache_path=cache_path, **base_config_kwargs)
        state_b = build_or_load_global_world(cfg_b)
        sig_b = world_signature(state_b.world)

        ok = (not wrote_file_before
              and wrote_file_after
              and sig_a == sig_b
              and cache_size > 1024)  # an npz must weigh > 1 KB
        print(_row("step 2 - cache write+load round-trip",
                   ok,
                   f"sig={sig_a[:16]} size={cache_size} bytes "
                   f"reload_match={sig_a == sig_b}"))
        if not ok:
            failures += 1

    # From here use a generated (no cache) state for the rest of the smoke
    # so we don't depend on filesystem state.
    cfg_no_cache = GlobalGenesisConfig(**base_config_kwargs)
    state = build_or_load_global_world(cfg_no_cache)
    sig_main = world_signature(state.world)
    print(f"        world signature = {sig_main[:16]}...")
    print(f"        world diag: land={state.world.diagnostics['land_fraction']:.2f} "
          f"rivers={state.world.diagnostics['river_cells']} "
          f"basins={state.world.diagnostics['n_watersheds']}")

    # Step 3 — register_region: valid regions accepted, out-of-bounds raised.
    cell_km = map_size / cfg_no_cache.resolution
    # Place regions at well-separated, plausible coords.
    region_a_origin = (1000.0, 1500.0)
    region_b_origin = (4500.0, 3500.0)
    region_a = register_region(state, "alpha", region_a_origin,
                                size_km=4.0, blend=1.0)
    region_b = register_region(state, "beta", region_b_origin,
                                size_km=4.0, blend=1.0)
    ok_valid = (isinstance(region_a, RegionAnchor)
                and isinstance(region_b, RegionAnchor)
                and len(state.regions) == 2)

    raised_out_of_bounds = False
    try:
        register_region(state, "bad", (map_size + 100.0, 1000.0), size_km=4.0)
    except ValueError:
        raised_out_of_bounds = True

    raised_neg = False
    try:
        register_region(state, "bad2", (-50.0, 1000.0), size_km=4.0)
    except ValueError:
        raised_neg = True

    ok = ok_valid and raised_out_of_bounds and raised_neg
    print(_row("step 3 - register_region validates bounds",
               ok,
               f"valid={ok_valid} raise_oob={raised_out_of_bounds} "
               f"raise_neg={raised_neg}"))
    if not ok:
        failures += 1

    # Step 4 — attach 2 sims, each on a different region; anchors distinct.
    sim_a = _build_sim("sim_alpha", seed=0xAAAA_1111)
    sim_b = _build_sim("sim_beta", seed=0xBBBB_2222)
    anchor_a = attach_region_to_sim(state, sim_a, "alpha")
    anchor_b = attach_region_to_sim(state, sim_b, "beta")
    streamer_a_has_genesis = sim_a.streamer.genesis is not None
    streamer_b_has_genesis = sim_b.streamer.genesis is not None
    anchors_distinct = (anchor_a is not anchor_b
                        and anchor_a.sim_origin_macro_km
                            != anchor_b.sim_origin_macro_km)
    state_tracks_both = (
        "sim_alpha" in state.registered_sims
        and "sim_beta" in state.registered_sims
        and state.sim_to_region.get("sim_alpha") == "alpha"
        and state.sim_to_region.get("sim_beta") == "beta")
    ok = (streamer_a_has_genesis and streamer_b_has_genesis
          and anchors_distinct and state_tracks_both)
    print(_row("step 4 - attach 2 sims to 2 regions",
               ok,
               f"genesis_a={streamer_a_has_genesis} "
               f"genesis_b={streamer_b_has_genesis} "
               f"tracked={state_tracks_both}"))
    if not ok:
        failures += 1

    # Step 5 — sims see DIFFERENT macro elevations at (0, 0).
    # Both regions point to distinct macro origins, so the macro
    # elevation should typically differ. We allow up to a tolerance
    # but expect at least one of (elevation, plate_id) to differ.
    macro_a = sample_macro(state.world,
                            anchor_a.sim_origin_macro_km[0],
                            anchor_a.sim_origin_macro_km[1])
    macro_b = sample_macro(state.world,
                            anchor_b.sim_origin_macro_km[0],
                            anchor_b.sim_origin_macro_km[1])
    elev_diff = abs(macro_a["elevation_m"] - macro_b["elevation_m"])
    plate_diff = int(macro_a["plate_id"]) != int(macro_b["plate_id"])
    biome_diff = int(macro_a["biome"]) != int(macro_b["biome"])
    # The two macro samples should differ either by elevation
    # > 100 m OR by plate / biome id.
    ok = elev_diff > 100.0 or plate_diff or biome_diff
    print(_row("step 5 - regions see distinct macro fields",
               ok,
               f"elev_diff={elev_diff:.1f}m "
               f"plate_diff={plate_diff} biome_diff={biome_diff}"))
    if not ok:
        failures += 1

    # Step 6 — both anchors share the SAME GenesisWorld (same id).
    same_world = (id(state.world) == id(anchor_a.world) == id(anchor_b.world))
    same_sig = (world_signature(state.world)
                == world_signature(anchor_a.world)
                == world_signature(anchor_b.world))
    ok = same_world and same_sig
    print(_row("step 6 - all anchors share same GenesisWorld",
               ok,
               f"id_equal={same_world} sig_equal={same_sig}"))
    if not ok:
        failures += 1

    # Step 7 — find_inter_region_rivers returns a coherent list.
    # To exercise the crossing logic, we register TWO ADJACENT regions
    # covering neighbouring macro cells: any flowing cell at the boundary
    # whose D8 receiver sits in the other region creates a crossing.
    # We pick the highest-flow_acc flowing cell so the chance of finding
    # a crossing in its neighbourhood is maximised.
    fa = state.world.flow_acc
    fd = state.world.flow_dir
    elev = state.world.elevation_m
    flowing = (fd != 255) & (elev > 0.0)
    candidates = np.where(flowing, fa, -1.0)
    if candidates.max() > 0:
        riy, rix = np.unravel_index(np.argmax(candidates), candidates.shape)
        # Place two narrow adjacent regions: "delta_left" and
        # "delta_right" side-by-side covering ~2x2 macro cells each,
        # straddling the flowing cell (rix, riy).
        # We keep them clamped inside [0, map_size_km].
        half = 1.0 * cell_km  # half-extent of 1 cell wide
        center_x_left = float(np.clip((rix + 0.0) * cell_km,
                                       half + 1.0, map_size - half - 1.0))
        center_y = float(np.clip((riy + 0.5) * cell_km,
                                  half + 1.0, map_size - half - 1.0))
        center_x_right = float(np.clip((rix + 2.0) * cell_km,
                                        half + 1.0, map_size - half - 1.0))
        # Register both if not too close (they need to be different macro
        # cells; clamping above might collapse them at the edges).
        try:
            register_region(state, "delta_left", (center_x_left, center_y),
                            size_km=float(half), blend=1.0)
            register_region(state, "delta_right", (center_x_right, center_y),
                            size_km=float(half), blend=1.0)
        except ValueError:
            pass

    crossings = find_inter_region_rivers(state, flow_acc_threshold=1.0)
    ok_list = isinstance(crossings, list)
    ok_entries = True
    for entry in crossings:
        if not isinstance(entry, dict):
            ok_entries = False
            break
        required_keys = {"from_region", "to_region",
                          "macro_x_km", "macro_y_km", "flow_acc"}
        if not required_keys.issubset(set(entry.keys())):
            ok_entries = False
            break
        if entry["from_region"] == entry["to_region"]:
            ok_entries = False
            break
        # Coordinates must lie inside the global map.
        if not (0 <= entry["macro_x_km"] <= map_size):
            ok_entries = False
            break
        if not (0 <= entry["macro_y_km"] <= map_size):
            ok_entries = False
            break
    ok = ok_list and ok_entries
    print(_row("step 7 - find_inter_region_rivers shape valid",
               ok,
               f"n_crossings={len(crossings)} "
               f"shape_ok={ok_entries}"))
    if not ok:
        failures += 1

    # Step 8 — determinism on a fresh build (no cache, same config).
    cfg_det1 = GlobalGenesisConfig(**base_config_kwargs)
    cfg_det2 = GlobalGenesisConfig(**base_config_kwargs)
    state_det1 = build_or_load_global_world(cfg_det1)
    state_det2 = build_or_load_global_world(cfg_det2)
    sig_det1 = world_signature(state_det1.world)
    sig_det2 = world_signature(state_det2.world)
    ok = sig_det1 == sig_det2 == sig_main
    print(_row("step 8 - determinism: same config -> same signature",
               ok,
               f"sig1={sig_det1[:16]} sig2={sig_det2[:16]}"))
    if not ok:
        failures += 1

    # Step 9 — reporter coherence.
    summary = global_state_summary(state)
    n_regions = len(state.regions)
    expected_summary_keys = {
        "world_signature", "world_signature_short", "map_size_km",
        "resolution", "n_plates", "seed", "n_regions",
        "n_sims_registered", "regions", "sims_to_regions",
        "world_diagnostics", "cache_path",
    }
    ok_keys = expected_summary_keys.issubset(set(summary.keys()))
    ok_values = (
        summary.get("n_regions") == n_regions
        and summary.get("n_sims_registered") == len(state.registered_sims)
        and summary.get("map_size_km") == map_size
        and summary.get("resolution") == cfg_no_cache.resolution
        and summary.get("n_plates") == cfg_no_cache.n_plates
        and summary.get("world_signature") == sig_main
        and isinstance(summary.get("regions"), list)
        and len(summary["regions"]) == n_regions
        and isinstance(summary.get("world_diagnostics"), dict)
    )
    ok = ok_keys and ok_values
    print(_row("step 9 - global_state_summary coherent",
               ok,
               f"keys_ok={ok_keys} values_ok={ok_values} "
               f"n_regions={summary.get('n_regions')} "
               f"n_sims={summary.get('n_sims_registered')}"))
    if not ok:
        failures += 1

    # Display summary for visibility.
    print()
    print("global_state_summary excerpt:")
    print(f"  world_signature        {summary.get('world_signature_short')}")
    print(f"  map_size_km            {summary.get('map_size_km')}")
    print(f"  resolution             {summary.get('resolution')}")
    print(f"  n_plates               {summary.get('n_plates')}")
    print(f"  n_regions              {summary.get('n_regions')}")
    print(f"  n_sims_registered      {summary.get('n_sims_registered')}")
    print(f"  sims_to_regions        {summary.get('sims_to_regions')}")

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
