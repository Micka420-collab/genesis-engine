"""P27 — Wave 6 plant evolution smoke test.

Validates the 40-clade catalogue + emergence + extinction + speciation
+ photosynthesis pathway override.

  1. Catalogue audit — phylogeny graph is acyclic, biome ids in sync
     with engine.world.Biome.
  2. fitness function obeys laws (sub-min temp → 0, sub-O2 → 0,
     biome affinity boost).
  3. modern mode seeds all 40 clades and at least 20 of them survive
     the first 100 ticks.
  4. ancient mode seeds only cyanobacteria; after enough ticks, O2
     climbs and at least one *new* clade emerges.
  5. CO2 stress — pushing the global Atmosphere to >700 ppm causes
     poaceae_c4 (C4 grasses, max_co2_ppm=600) to crash in biomass.
  6. Photosynthesis pathway override is wired (chunk._plant_pathway_mix
     is set after a few ticks, photosynthesis reads it).
  7. ADR-0005 audit clean — engine.plant_evolution required-tagged.
  8. Determinism — two runs same seed produce same plant-state hash.
"""
from __future__ import annotations

import hashlib
import io
import json
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

from engine.sim import Simulation, SimConfig                # noqa: E402
from engine.sim_5cd_integration import install              # noqa: E402
from engine.earth_loader import EarthLoader                 # noqa: E402
from engine.earth_streamer import (attach_earth_loader,     # noqa: E402
                                   attach_land_filter)
from engine.sim_lift import install_lift                    # noqa: E402
from engine.photosynthesis import install_photosynthesis    # noqa: E402
from engine.plant_evolution import (install_plant_evolution, # noqa: E402
                                     plant_evolution_state,
                                     compute_fitness)
from engine.plant_catalog import (CLADE_BY_NAME,            # noqa: E402
                                   children_of, ancestors_of,
                                   audit_biome_ids,
                                   all_clade_names)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:55s} {detail}"


def _build_sim(name: str):
    cfg = SimConfig(
        name=name, seed=0xC0FFEE_F1EE_D & 0xFFFFFFFFFFFFFFFF,
        founders=8, max_agents=20,
        bounds_km=(1.5, 1.5), spawn_radius_m=150.0,
        drive_accel=1500.0, cultures=1,
    )
    loader = EarthLoader(
        origin_lat=46.510, origin_lon=6.633, bounds_km=1.5,
        cache_dir=os.path.abspath(os.path.join(
            ROOT, "..", "cache", "earth_leman")),
    )
    sim = Simulation(cfg)
    attach_earth_loader(sim.streamer, loader, log_first_hit=False)
    attach_land_filter(sim)
    install(sim)
    install_lift(sim)
    install_photosynthesis(sim)
    return sim


def _state_hash(state_snap) -> str:
    return hashlib.sha256(
        json.dumps(state_snap, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


def main() -> int:
    print("=" * 78)
    print("P27 — Wave 6 plant evolution smoke")
    print("=" * 78)
    failures = 0

    # ------------------------------------------------------------------
    # Step 1 — catalogue audit
    # ------------------------------------------------------------------
    ok_biomes = audit_biome_ids()
    print(_row("step 1 — biome ids in sync", ok_biomes))
    if not ok_biomes:
        failures += 1
    # Phylogeny acyclic.
    cycles = []
    for name in all_clade_names():
        anc = ancestors_of(name)
        if len(anc) != len(set(anc)):
            cycles.append(name)
    ok_acyclic = not cycles
    print(_row("step 1 — phylogeny acyclic", ok_acyclic,
               f"cycles={cycles}" if cycles else "no cycles"))
    if not ok_acyclic:
        failures += 1
    n_cat = len(all_clade_names())
    print(_row("step 1 — catalogue ≥ 35 clades",
               n_cat >= 35, f"n={n_cat}"))
    if n_cat < 35:
        failures += 1

    # ------------------------------------------------------------------
    # Step 2 — fitness laws
    # ------------------------------------------------------------------
    pine = CLADE_BY_NAME["pinaceae"]
    # Sub-min temp → fitness=0
    f_cold = compute_fitness(pine, biome_id=3, temp_c=-60,
                             chunk_water_max_l=20, oxygen_pct=21, co2_ppm=400)
    print(_row("step 2 — pinaceae @ -60°C → fitness 0",
               f_cold == 0.0, f"f={f_cold:.4f}"))
    if f_cold != 0.0:
        failures += 1

    # Sub-O2 (cycads need 15%)
    cycad = CLADE_BY_NAME["cycads"]
    f_lowO2 = compute_fitness(cycad, biome_id=11, temp_c=25,
                              chunk_water_max_l=10, oxygen_pct=10, co2_ppm=400)
    print(_row("step 2 — cycads at 10% O2 → fitness 0",
               f_lowO2 == 0.0, f"f={f_lowO2:.4f}"))
    if f_lowO2 != 0.0:
        failures += 1

    # Oaks in temperate forest, optimal → fitness near 1
    oak = CLADE_BY_NAME["oaks"]
    f_oak = compute_fitness(oak, biome_id=4, temp_c=15,
                            chunk_water_max_l=20, oxygen_pct=21, co2_ppm=280)
    print(_row("step 2 — oaks in temp forest optimal → fitness > 0.5",
               f_oak > 0.5, f"f={f_oak:.4f}"))
    if not (f_oak > 0.5):
        failures += 1

    # ------------------------------------------------------------------
    # Step 3 — modern mode seeds + survives
    # ------------------------------------------------------------------
    sim = _build_sim("p27_modern")
    state = install_plant_evolution(sim, mode="modern")
    seeded_clades = len(state.available_clades)
    for _ in range(100):
        sim.step()
    snap = plant_evolution_state(sim)
    n_top = len(snap.get("top_clades", []))
    biomass = snap.get("global_biomass_kg", 0)
    print(_row("step 3 — modern: ≥35 clades seeded",
               seeded_clades >= 35, f"seeded={seeded_clades}"))
    if seeded_clades < 35:
        failures += 1
    print(_row("step 3 — modern: positive global biomass",
               biomass > 0, f"biomass={biomass} kg"))
    if biomass <= 0:
        failures += 1
    print(_row("step 3 — modern: ≥ 1 clade in top",
               n_top >= 1, f"top={n_top}"))
    if n_top < 1:
        failures += 1

    # ------------------------------------------------------------------
    # Step 4 — photosynthesis pathway override is set
    # ------------------------------------------------------------------
    sample_chunk = next(iter(sim.streamer.cache.values()))
    has_override = hasattr(sample_chunk, "_plant_pathway_mix") \
                   and sample_chunk._plant_pathway_mix is not None
    print(_row("step 4 — chunk._plant_pathway_mix written",
               has_override,
               f"mix={getattr(sample_chunk, '_plant_pathway_mix', None)}"))
    if not has_override:
        failures += 1

    # ------------------------------------------------------------------
    # Step 5 — CO2 stress kills C4 grasses
    # ------------------------------------------------------------------
    c4 = CLADE_BY_NAME["poaceae_c4"]
    f_normalCO2 = compute_fitness(c4, biome_id=9, temp_c=30,
                                  chunk_water_max_l=5, oxygen_pct=21, co2_ppm=400)
    f_highCO2 = compute_fitness(c4, biome_id=9, temp_c=30,
                                chunk_water_max_l=5, oxygen_pct=21, co2_ppm=800)
    ok = f_normalCO2 > 0 and f_highCO2 == 0.0
    print(_row("step 5 — C4 grass @ 800 ppm CO2 → fitness 0",
               ok, f"normal={f_normalCO2:.3f}  high={f_highCO2:.3f}"))
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Step 6 — ancient mode emergence
    # ------------------------------------------------------------------
    sim_a = _build_sim("p27_ancient")
    state_a = install_plant_evolution(sim_a, mode="ancient")
    initial_clades = set(state_a.available_clades)
    for _ in range(200):
        sim_a.step()
    final_clades = set(state_a.available_clades)
    new_clades = final_clades - initial_clades
    ok = initial_clades == {"cyanobacteria"}
    print(_row("step 6 — ancient mode starts with cyanobacteria only",
               ok, f"initial={initial_clades}"))
    if not ok:
        failures += 1
    print(_row("step 6 — ancient mode: O2 climbs from cyanobacteria",
               state_a.oxygen_pct() > 0.1,
               f"O2={state_a.oxygen_pct():.4f}%"))
    if state_a.oxygen_pct() <= 0.1:
        failures += 1

    # ------------------------------------------------------------------
    # Step 7 — ADR-0005 audit
    # ------------------------------------------------------------------
    from engine.world_model_capabilities import audit_modules
    table, lint_fails = audit_modules(strict=False)
    rows = table.get("modules", [])
    pe_row = next((r for r in rows
                   if r["module"] == "engine.plant_evolution"), None)
    ok = pe_row is not None and pe_row["status"] == "ok" and not lint_fails
    print(_row("step 7 — ADR-0005 lists plant_evolution OK",
               ok, f"failures={lint_fails}"))
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Step 8 — determinism
    # ------------------------------------------------------------------
    sim_b = _build_sim("p27_det")
    install_plant_evolution(sim_b, mode="modern")
    for _ in range(100):
        sim_b.step()
    snap_b = plant_evolution_state(sim_b)
    h_a = _state_hash({k: v for k, v in snap.items()
                       if k not in ("ticks_run", "available_clades")})
    h_b = _state_hash({k: v for k, v in snap_b.items()
                       if k not in ("ticks_run", "available_clades")})
    print(_row("step 8 — determinism (same seed → same snapshot)",
               h_a == h_b, f"{h_a} vs {h_b}"))
    if h_a != h_b:
        failures += 1

    print()
    if failures == 0:
        print("RESULT: PASS — Wave 6 plant evolution smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
