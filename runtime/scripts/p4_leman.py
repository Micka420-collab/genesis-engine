"""P4 — Earth-anchored simulation run over Lake Geneva (Léman).

Founders: 20.  Bounds: 2 km × 2 km centred on 46.40°N / 6.45°E.  Ticks: 1000.
Output: ``runtime/journals/phase5a_leman.jsonl``.

Even without rasterio (offline), the EarthLoader smoke-tests the wiring; the
chunk content falls back to procedural generation seeded by the geographic
origin.  The wider bounds and larger spawn radius let agents disperse so the
cognition layer reaches SPEAK/FORAGE/INVENT branches (in the 0.5 km × 0.5 km
P0 smoke they were stuck in MATE loops).
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.sim import Simulation, SimConfig
from engine.sim_5cd_integration import install
from engine.earth_loader import EarthLoader
from engine.earth_streamer import attach_earth_loader, attach_land_filter
from engine.sim_lift import install_lift, lift_state


def main() -> int:
    out_path = os.path.join(ROOT, "journals", "phase5a_leman.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w").close()

    # Earth-anchored: Lausanne-Ouchy area (46.510°N, 6.633°E) — north shore
    # of Léman. Lake to the south, hills/forest to the north. Mixed terrain
    # gives agents access to water + wood + stone in one 4 km box.
    origin_lat = 46.510
    origin_lon = 6.633
    cache_dir = os.path.join(ROOT, "..", "cache", "earth_leman")
    cache_dir = os.path.abspath(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    loader = EarthLoader(origin_lat=origin_lat, origin_lon=origin_lon,
                         bounds_km=2.0, cache_dir=cache_dir)

    # Probe — record whether real data is online.
    earth_probe = {
        "origin_lat": origin_lat, "origin_lon": origin_lon, "bounds_km": 2.0,
        "samples": {},
    }
    for coord in [(0, 0, 0), (1, 0, 0), (0, 1, 0)]:
        try:
            data = loader.chunk_data(coord)
            earth_probe["samples"][str(coord)] = (
                "online" if data is not None else "offline_fallback"
            )
        except Exception as exc:
            earth_probe["samples"][str(coord)] = f"error:{type(exc).__name__}"

    # Sim config: bigger arena, more dispersed spawn, configurable tick count.
    n_ticks_env = os.environ.get("LEMAN_TICKS", "")
    try:
        N_TICKS = int(n_ticks_env) if n_ticks_env else 1000
    except ValueError:
        N_TICKS = 1000
    cfg = SimConfig(
        name="phase5a_leman",
        seed=0xFADE_C0FFEE_5A & 0xFFFFFFFF_FFFFFFFF,
        founders=20,
        max_agents=1000,        # P-NEW.15 — was 200, hit the cap by tick ~500
        bounds_km=(2.0, 2.0),
        spawn_radius_m=200.0,
        cultures=2,
        drive_accel=1500.0,
    )

    t_setup = time.monotonic()
    sim = Simulation(cfg)
    sim.earth_loader = loader
    # L1 wiring: try to fetch real Copernicus DEM + ESA WorldCover for every
    # chunk; fall back to procedural if the loader returns None.
    attach_earth_loader(sim.streamer, loader, strict=False, log_first_hit=True)
    # Land-filter: refuse to spawn founders on lake water (OCEAN biome).
    attach_land_filter(sim)
    install(sim)
    # L2 — vegetation succession + foot-traffic erosion.
    install_lift(sim)
    setup_elapsed = time.monotonic() - t_setup
    earth_probe["streamer_attached"] = True
    earth_probe["streamer_hits"] = int(getattr(sim.streamer, "_earth_hits", 0))
    earth_probe["streamer_misses"] = int(getattr(sim.streamer, "_earth_misses", 0))

    original_record = sim.annalist.record_tick
    counts = {
        "innovation": 0, "build": 0, "invent": 0, "artifact_transmitted": 0,
        "tech_transmitted": 0, "birth": 0, "death": 0, "fight": 0, "share": 0,
        "mating": 0, "vocalization": 0, "competition": 0,
        "group_formed": 0, "group_dissolved": 0,
    }
    journal_fp = open(out_path, "a", encoding="utf-8")

    # Map of raw-event kind -> counter key (annalist may rename on emit).
    _raw_to_count = {
        "vocalize": "vocalization", "innovation": "innovation",
        "build": "build", "invent": "invent",
        "artifact_transmitted": "artifact_transmitted",
        "tech_transmitted": "tech_transmitted",
        "mating_success": "mating", "competition": "competition",
        "fight": "fight", "share": "share",
        "group_formed": "group_formed", "group_dissolved": "group_dissolved",
        "birth": "birth", "death": "death",
    }

    def mirror_record(tick, agents, *, births, deaths, raw_events):
        # Births / deaths come in as positional args, not raw events.
        if births:
            counts["birth"] += len(births)
        if deaths:
            counts["death"] += len(deaths)
        for e in raw_events:
            k = e.get("kind", "?")
            ck = _raw_to_count.get(k, k)
            if ck in counts:
                counts[ck] = counts[ck] + 1
        out = original_record(tick, agents, births=births, deaths=deaths,
                              raw_events=raw_events)
        try:
            for ev in out:
                journal_fp.write(json.dumps(ev.to_dict(),
                                            separators=(",", ":")) + "\n")
            if tick % 50 == 0:
                journal_fp.flush()
        except Exception:
            pass
        return out

    sim.annalist.record_tick = mirror_record

    # Run.
    errors = []
    sample_ticks = []
    t0 = time.monotonic()
    for t in range(N_TICKS):
        try:
            sim.step()
        except Exception as exc:
            errors.append({
                "tick": t, "exception": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc().splitlines()[-6:],
            })
            break
        # Periodic mid-run snapshot (every 200 ticks).
        if t % 200 == 199:
            sample_ticks.append({
                "tick": t + 1,
                "alive": int(sim.agents.alive[:sim.agents.n_active].sum()),
                "co2_ppm": round(float(sim.atmosphere.co2_ppm), 3),
                "structures_complete": len(sim.construction_registry.structures),
                "artifacts": len(sim.invention_registry.artifacts),
                "innovations_seen": counts["innovation"],
                "vocalizations_seen": counts["vocalization"],
                "matings_seen": counts["mating"],
            })
    elapsed = time.monotonic() - t0

    # Per-agent material inventory peek.
    import numpy as np
    n = sim.agents.n_active
    alive = sim.agents.alive[:n]
    mat_summary = {}
    for fld in ("inv_wood", "inv_stone", "inv_fiber", "inv_flint",
                "inv_clay", "inv_food"):
        if hasattr(sim.agents, fld):
            arr = getattr(sim.agents, fld)[:n]
            mat_summary[fld] = {
                "mean_alive": round(float(arr[alive].mean() if alive.any() else 0.0), 4),
                "max": round(float(arr.max() if n > 0 else 0.0), 4),
                "total": round(float(arr.sum() if n > 0 else 0.0), 4),
            }

    summary = {
        "_summary": True,
        "config": {
            "name": cfg.name, "seed": cfg.seed, "founders": cfg.founders,
            "max_agents": cfg.max_agents, "bounds_km": list(cfg.bounds_km),
            "spawn_radius_m": cfg.spawn_radius_m, "drive_accel": cfg.drive_accel,
            "cultures": cfg.cultures, "ticks_target": N_TICKS,
        },
        "earth_probe": earth_probe,
        "earth_streamer": {
            "hits": int(getattr(sim.streamer, "_earth_hits", 0)),
            "misses": int(getattr(sim.streamer, "_earth_misses", 0)),
        },
        "lift_state": lift_state(sim),
        "setup_elapsed_s": round(setup_elapsed, 3),
        "run_elapsed_s": round(elapsed, 3),
        "ticks_completed": sim.tick,
        "agents_alive": int(alive.sum()),
        "agents_total_spawned": int(n),
        "event_counts": counts,
        "samples": sample_ticks,
        "construction": {
            "active_projects": len(sim.construction_registry.projects),
            "completed_structures": len(sim.construction_registry.structures),
        },
        "invention": {
            "artifacts": len(sim.invention_registry.artifacts),
            "names": [a.name for a in
                      list(sim.invention_registry.artifacts.values())[:5]],
        },
        "atmosphere": {
            "co2_kg": round(float(sim.atmosphere.co2_kg), 4),
            "co2_ppm": round(float(sim.atmosphere.co2_ppm), 4),
            "temp_anomaly_k": round(float(sim.atmosphere.temp_anomaly_k), 4),
        },
        "materials_inventory": mat_summary,
        "errors": errors,
    }
    journal_fp.write(json.dumps(summary, separators=(",", ":")) + "\n")
    journal_fp.close()
    print(json.dumps(summary, indent=2))

    if errors:
        print("\n[X] P4 LEMAN FAILED — exception thrown.")
        return 2

    # Pass criteria: agents alive at the end, no exceptions, at least 1
    # innovation or 1 vocalization or 1 material picked up.
    any_signal = (counts["innovation"] + counts["vocalization"]
                  + counts["invent"] + counts["mating"])
    if any_signal < 1:
        print("\n[!] P4 LEMAN: no innovation/vocalization/invent/mating — weak run")
        return 3
    if int(alive.sum()) < 1:
        print("\n[X] P4 LEMAN: all agents dead — environment too harsh")
        return 4

    print("\n[OK] P4 LEMAN RUN COMPLETED")
    print(f"   alive: {int(alive.sum())}/{n}   innovations: {counts['innovation']}")
    print(f"   vocalizations: {counts['vocalization']}  matings: {counts['mating']}")
    print(f"   structures complete: {len(sim.construction_registry.structures)}")
    print(f"   artifacts: {len(sim.invention_registry.artifacts)}")
    print(f"   journal = {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
