"""P35 — Wave 10c full chain smoke (MINE → SMELT → SYNTHESIZE).

Demonstrates the complete materials pipeline now operational :

  Earth strata (Wave 10 geology)
       ↓ ActionKind.MINE → ore in inv_metal
  Smelt with charcoal in bloomery (Wave 10c metallurgy)
       ↓ pure Fe, Cu, Sn etc. in agent pure-element bag
  Wave 1/2 material_synthesis.synthesize
       ↓ SynthesizedMaterial (bronze, steel, etc.)
  Wave 4 material_aging tracks decay
"""
from __future__ import annotations

import io
import os
import random
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
from engine.geology import (                                # noqa: E402
    install_geology, chunk_geology, mine_at)
from engine.metallurgy import (                             # noqa: E402
    install_metallurgy, smelt, teach_practice,
    metallurgy_state, FURNACE_YIELD)
from engine.material_synthesis import (                     # noqa: E402
    synthesize, SynthesisConditions, MaterialRegistry)
from engine.agent import ActionKind                         # noqa: E402
import engine.cognition as _cog_mod                         # noqa: E402
from engine.cognition import Decision                       # noqa: E402


def apply_decision(*args, **kwargs):
    return _cog_mod.apply_decision(*args, **kwargs)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:55s} {detail}"


def _build_sim(name: str):
    cfg = SimConfig(
        name=name, seed=0xC0FFEE_FE & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=10,
        bounds_km=(1.0, 1.0), spawn_radius_m=100.0,
        drive_accel=1500.0, cultures=1,
    )
    loader = EarthLoader(
        origin_lat=46.510, origin_lon=6.633, bounds_km=1.0,
        cache_dir=os.path.abspath(os.path.join(
            ROOT, "..", "cache", "earth_leman")),
    )
    sim = Simulation(cfg)
    attach_earth_loader(sim.streamer, loader, log_first_hit=False)
    attach_land_filter(sim)
    install(sim)
    install_geology(sim)
    install_metallurgy(sim)
    return sim


def main() -> int:
    print("=" * 78)
    print("P35 — Wave 10c full chain: MINE → SMELT → SYNTHESIZE")
    print("=" * 78)
    failures = 0

    sim = _build_sim("p35_chain")
    sim.step()  # populate chunks

    row = 0

    # Step 1 — MINE action via cognition wrapper, deep enough to hit
    # any ore-rich layer.
    inv_metal_before = float(sim.agents.inv_metal[row])
    dec = Decision(action=int(ActionKind.MINE),
                   target_x=50.0,    # depth 50 m
                   target_y=15.0,    # 15 kg of ore
                   confidence=1.0)
    apply_decision(sim.agents, row, dec, sim.streamer, sim.tick)
    inv_metal_after = float(sim.agents.inv_metal[row])
    geo = sim._geology_state
    chunks_visited = len(geo.chunks)
    ok = inv_metal_after > inv_metal_before and chunks_visited >= 1
    print(_row("step 1 — MINE via cognition wrapper credits inv_metal",
               ok,
               f"inv_metal {inv_metal_before:.3f} → {inv_metal_after:.3f} ; "
               f"chunks={chunks_visited}"))
    if not ok:
        failures += 1

    # Step 2 — Smelt hematite with charcoal in bloomery → Fe.
    ok_s, elements, reason = smelt(sim, row,
                                    ore_name="hematite",
                                    ore_kg=5.0,
                                    fuel_name="charcoal",
                                    furnace="bloomery")
    fe_yield = elements.get("Fe", 0.0)
    print(_row("step 2 — smelt 5 kg hematite + charcoal → Fe",
               ok_s and fe_yield > 1.0,
               f"reason={reason!r} elements={ {k: round(v,3) for k,v in elements.items()} }"))
    if not (ok_s and fe_yield > 1.0):
        failures += 1

    # Step 3 — Furnace tier matters : pit_kiln yields less than bloomery.
    _, elem_pit, _ = smelt(sim, row, "hematite", 5.0,
                            fuel_name="charcoal", furnace="pit_kiln")
    fe_pit = elem_pit.get("Fe", 0.0)
    ok = fe_pit < fe_yield
    print(_row("step 3 — pit_kiln Fe yield < bloomery Fe yield",
               ok, f"pit={fe_pit:.3f} bloomery={fe_yield:.3f}"))
    if not ok:
        failures += 1

    # Step 4 — Smelt cassiterite SnO2 + charcoal → Sn (for bronze).
    _, sn_elem, _ = smelt(sim, row, "cassiterite", 3.0,
                          fuel_name="charcoal", furnace="bloomery")
    sn_yield = sn_elem.get("Sn", 0.0)
    print(_row("step 4 — smelt cassiterite → Sn",
               sn_yield > 0.5, f"Sn={sn_yield:.3f} kg"))
    if not (sn_yield > 0.5):
        failures += 1

    # Step 5 — Smelt native_copper → Cu (already pure).
    _, cu_elem, _ = smelt(sim, row, "native_copper", 4.0,
                          fuel_name="charcoal", furnace="pit_kiln")
    cu_yield = cu_elem.get("Cu", 0.0)
    print(_row("step 5 — smelt native_copper → Cu",
               cu_yield > 0.5, f"Cu={cu_yield:.3f} kg"))
    if not (cu_yield > 0.5):
        failures += 1

    # Step 6 — Use the smelted Cu + Sn to synthesize bronze via Wave 1/2.
    cond = SynthesisConditions(temperature_K=1200.0, atmosphere="reducing")
    mat = synthesize(
        composition={"Cu": 0.70, "Sn": 0.30},
        conditions=cond,
        tools_available=("forge",),
        culture_id=0,
        tick=sim.tick,
        rng=random.Random(0xDEADBEEF),
    )
    ok = mat is not None and mat.name.startswith("alloy_")
    print(_row("step 6 — synthesize bronze from smelted Cu + Sn",
               ok, f"material={mat.name if mat else None}"))
    if not ok:
        failures += 1

    # Step 7 — Practice : teach bellows to culture 0, get higher yield.
    state = sim._metal_state
    teach_practice(state, 0, "bellows")
    _, elem_bellows, _ = smelt(sim, row, "hematite", 5.0,
                                fuel_name="charcoal", furnace="bloomery")
    fe_bellows = elem_bellows.get("Fe", 0.0)
    ok = fe_bellows > fe_yield  # bellows × 1.15
    print(_row("step 7 — bellows practice raises Fe yield ~15 %",
               ok, f"baseline={fe_yield:.3f} bellows={fe_bellows:.3f}"))
    if not ok:
        failures += 1

    # Step 8 — ADR-0005 audit
    from engine.world_model_capabilities import audit_modules
    table, lint_fails = audit_modules(strict=False)
    m_row = next((r for r in table["modules"]
                  if r["module"] == "engine.metallurgy"), None)
    ok = m_row is not None and m_row["status"] == "ok" and not lint_fails
    print(_row("step 8 — ADR-0005 lists metallurgy OK",
               ok, f"failures={lint_fails}"))
    if not ok:
        failures += 1

    print()
    snap = metallurgy_state(sim)
    print(f"metallurgy snapshot:")
    print(f"  total_smelt_events: {snap.get('total_smelt_events')}")
    print(f"  total_ore_kg: {snap.get('total_ore_kg')}")
    print(f"  top_pure_elements: {snap.get('top_pure_elements')}")
    print()
    if failures == 0:
        print("RESULT: PASS — Wave 10c full chain smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
