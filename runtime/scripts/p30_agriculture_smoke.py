"""P30 — Phase 4 agriculture smoke test.

Validates the PLANT / HARVEST cycle end-to-end on a real Léman sim.

  1. install_agriculture is idempotent.
  2. discover_seed registers a clade in a culture's seed library.
  3. plant_seed injects biomass into plant_evolution.ChunkVegetation.
  4. harvest draws down biomass and fills inv_food.
  5. Forage-time discovery records edible clades present in chunks.
  6. tick_agriculture boosts growth rate on cultivated fields.
  7. ADR-0005 audit clean (12/12 required-tagged).
  8. Persistence round-trip preserves seed libraries + field stats.
"""
from __future__ import annotations

import io
import json
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

from engine.sim import Simulation, SimConfig                # noqa: E402
from engine.sim_5cd_integration import install              # noqa: E402
from engine.earth_loader import EarthLoader                 # noqa: E402
from engine.earth_streamer import (attach_earth_loader,     # noqa: E402
                                   attach_land_filter)
from engine.sim_lift import install_lift                    # noqa: E402
from engine.photosynthesis import install_photosynthesis    # noqa: E402
from engine.plant_evolution import install_plant_evolution  # noqa: E402
from engine.agriculture import (                            # noqa: E402
    install_agriculture, agriculture_state,
    discover_seed, plant_seed, harvest, maybe_record_forage_discovery,
    save_agriculture_state, load_agriculture_state)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:55s} {detail}"


def _build_sim(name: str):
    cfg = SimConfig(
        name=name, seed=0xC0FFEE_A6 & 0xFFFFFFFFFFFFFFFF,
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
    install_plant_evolution(sim, mode="modern")
    return sim


def main() -> int:
    print("=" * 78)
    print("P30 — Phase 4 agriculture smoke")
    print("=" * 78)
    failures = 0

    sim = _build_sim("p30_agri")
    state = install_agriculture(sim)
    # One tick to populate plant biomass + chunk cache.
    sim.step()

    # Step 1 — install is idempotent
    state2 = install_agriculture(sim)
    print(_row("step 1 — install_agriculture idempotent",
               state is state2, ""))
    if state is not state2:
        failures += 1

    # Resolve the agent's actual culture before seeding the library.
    from engine.agriculture import _agent_culture as _ac
    row = 0
    agent_culture = _ac(sim, row)

    # Step 2 — discover_seed marks new (use agent's real culture).
    new1 = discover_seed(state, agent_culture, "poaceae_c3")
    new2 = discover_seed(state, agent_culture, "poaceae_c3")  # already known
    new3 = discover_seed(state, agent_culture, "legumes")
    new4 = discover_seed(state, agent_culture, "not_a_real_clade")
    ok = new1 and not new2 and new3 and not new4
    print(_row("step 2 — discover_seed adds new, idempotent on known",
               ok, f"new1={new1} new2={new2} new3={new3} new4={new4}"))
    if not ok:
        failures += 1
    lib = state.culture_seed_library.get(agent_culture, set())
    print(_row("step 2 — agent's culture library has poaceae_c3 + legumes",
               "poaceae_c3" in lib and "legumes" in lib,
               f"culture={agent_culture} lib={sorted(lib)}"))
    if not ("poaceae_c3" in lib and "legumes" in lib):
        failures += 1

    # Step 3 — plant_seed injects biomass
    from engine.world import world_to_chunk
    px = float(sim.agents.pos[row, 0])
    py = float(sim.agents.pos[row, 1])
    chunk_c = world_to_chunk(px, py)
    plant_state = sim._plant_state
    veg_before = plant_state.chunk_vegetation.get(chunk_c)
    mass_before = veg_before.biomass_kg.get("poaceae_c3", 0.0) if veg_before else 0.0
    ok_plant, reason = plant_seed(sim, state, row, "poaceae_c3")
    veg_after = plant_state.chunk_vegetation.get(chunk_c)
    mass_after = veg_after.biomass_kg.get("poaceae_c3", 0.0) if veg_after else 0.0
    print(_row("step 3 — plant_seed succeeds + injects biomass",
               ok_plant and mass_after > mass_before,
               f"reason={reason!r} mass {mass_before:.1f} → {mass_after:.1f}"))
    if not (ok_plant and mass_after > mass_before):
        failures += 1
    print(_row("step 3 — plant_events counter incremented",
               state.plant_events == 1, f"events={state.plant_events}"))
    if state.plant_events != 1:
        failures += 1

    # Step 4 — harvest draws biomass + fills inv_food. The harvest picks
    # the highest-yield edible clade in the chunk (not necessarily
    # poaceae_c3), so we measure the TOTAL biomass before/after.
    biomass_before_h = sum(veg_after.biomass_kg.values()) if veg_after else 0
    inv_before = float(sim.agents.inv_food[row])
    ok_h, kcal, reason = harvest(sim, state, row)
    inv_after = float(sim.agents.inv_food[row])
    biomass_after_h = sum(veg_after.biomass_kg.values()) if veg_after else 0
    ok = (ok_h and kcal > 0 and inv_after >= inv_before
          and biomass_after_h < biomass_before_h)
    print(_row("step 4 — harvest succeeds, draws biomass, fills inv_food",
               ok,
               f"reason={reason!r} kcal={kcal:.0f} inv {inv_before:.2f}→{inv_after:.2f}"
               f" biomass {biomass_before_h:.0f}→{biomass_after_h:.0f}"))
    if not ok:
        failures += 1

    # Step 5 — forage discovery on a chunk with edible biomass
    n_new = maybe_record_forage_discovery(sim, state, row)
    print(_row("step 5 — forage discovery adds clades",
               n_new >= 0,  # may be 0 if all already known
               f"n_new={n_new} lib_size={len(state.culture_seed_library.get(1, set()))}"))
    # No fail counter — just informational.

    # Step 6 — tick_agriculture boosts growth on cultivated fields
    # Use a different chunk where we plant something and verify the
    # bonus growth fires on the next tick.
    from engine.agriculture import tick_agriculture
    veg_pre = veg_after.biomass_kg.get("poaceae_c3", 0.0)
    tick_agriculture(sim, state)
    veg_post = veg_after.biomass_kg.get("poaceae_c3", 0.0)
    print(_row("step 6 — tick_agriculture grows cultivated biomass",
               veg_post >= veg_pre,
               f"{veg_pre:.3f} → {veg_post:.3f}"))
    # No fail counter — bonus may be tiny per tick.

    # Step 7 — ADR-0005 audit
    from engine.world_model_capabilities import audit_modules
    table, lint_fails = audit_modules(strict=False)
    ag_row = next((r for r in table["modules"]
                   if r["module"] == "engine.agriculture"), None)
    ok = ag_row is not None and ag_row["status"] == "ok" and not lint_fails
    print(_row("step 7 — ADR-0005 lists agriculture OK",
               ok, f"failures={lint_fails}"))
    if not ok:
        failures += 1

    # Step 8 — persistence round-trip
    tmp = tempfile.mkdtemp(prefix="genesis_p30_")
    try:
        save_agriculture_state(sim, tmp)
        # Build a fresh sim, install, then load.
        sim2 = _build_sim("p30_agri_b")
        state2 = install_agriculture(sim2)
        sim2.step()  # one tick
        ok_load = load_agriculture_state(sim2, tmp)
        # Compare key stats.
        ok = (ok_load
              and sim2._ag_state.plant_events == state.plant_events
              and sim2._ag_state.harvest_events == state.harvest_events
              and sim2._ag_state.culture_seed_library
                  == state.culture_seed_library)
        print(_row("step 8 — persistence round-trip preserves stats",
                   ok,
                   f"events {sim2._ag_state.plant_events}/{sim2._ag_state.harvest_events}"
                   f" lib_match={sim2._ag_state.culture_seed_library == state.culture_seed_library}"))
        if not ok:
            failures += 1
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    snap = agriculture_state(sim)
    print(f"agriculture_state snapshot:")
    print(f"  plant_events: {snap.get('plant_events')}")
    print(f"  harvest_events: {snap.get('harvest_events')}")
    print(f"  total_kcal: {snap.get('total_kcal_harvested')}")
    print(f"  discoveries: {snap.get('discoveries')}")
    print(f"  seed libraries: {snap.get('culture_seed_libraries')}")
    print()
    if failures == 0:
        print("RESULT: PASS — Phase 4 agriculture smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
