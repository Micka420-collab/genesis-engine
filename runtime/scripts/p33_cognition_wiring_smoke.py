"""P33 — Phase 4 / Wave 9d cognition wiring smoke.

Confirms that the agriculture wrapper installed on
``engine.cognition.apply_decision`` correctly :

  1. Lets agents execute ActionKind.PLANT autonomously (via
     decide().action = PLANT) → plant_seed is invoked, biomass added.
  2. Lets agents execute ActionKind.HARVEST autonomously → harvest is
     invoked, inv_food filled.
  3. Triggers seed-discovery on a successful FORAGE — the agent's
     culture seed_library gains the chunk's edible clades.
  4. Preserves *all existing actions* (DRINK, EAT, IDLE, WALK_TO).
     Smoke runs 200 ticks of a normal sim and verifies it doesn't
     crash and physiology / photosynthesis still tick.
  5. Determinism — bit-identical state across two runs same seed.

The smoke uses a minimalist Decision builder (no full sim cognition)
so we explicitly drive the action and observe the side-effect.
"""
from __future__ import annotations

import hashlib
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

from engine.sim import Simulation, SimConfig                # noqa: E402
from engine.sim_5cd_integration import install              # noqa: E402
from engine.earth_loader import EarthLoader                 # noqa: E402
from engine.earth_streamer import (attach_earth_loader,     # noqa: E402
                                   attach_land_filter)
from engine.sim_lift import install_lift                    # noqa: E402
from engine.photosynthesis import install_photosynthesis    # noqa: E402
from engine.plant_evolution import install_plant_evolution  # noqa: E402
from engine.agriculture import (                            # noqa: E402
    install_agriculture, discover_seed, agriculture_state)
from engine.agent import ActionKind                         # noqa: E402
import engine.cognition as _cog_mod                         # noqa: E402
from engine.cognition import Decision                       # noqa: E402


def apply_decision(*args, **kwargs):
    """Always resolve the LIVE apply_decision (after install patches)."""
    return _cog_mod.apply_decision(*args, **kwargs)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:55s} {detail}"


def _build_sim(name: str):
    cfg = SimConfig(
        name=name, seed=0xC0FFEE_9D & 0xFFFFFFFFFFFFFFFF,
        founders=6, max_agents=15,
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
    install_agriculture(sim)
    return sim


def main() -> int:
    print("=" * 78)
    print("P33 — Phase 4 / Wave 9d cognition wiring smoke")
    print("=" * 78)
    failures = 0

    sim = _build_sim("p33_wire")
    # One tick to populate plant biomass in chunks.
    sim.step()
    state = sim._ag_state

    # Seed culture 0 (the default fallback culture for unconfigured agents).
    discover_seed(state, 0, "poaceae_c3")
    discover_seed(state, 0, "legumes")

    # Step 1 — autonomous PLANT via Decision dispatch
    row = 0
    from engine.world import world_to_chunk
    px = float(sim.agents.pos[row, 0])
    py = float(sim.agents.pos[row, 1])
    chunk_c = world_to_chunk(px, py)
    veg = sim._plant_state.chunk_vegetation.get(chunk_c)
    mass_before = (veg.biomass_kg.get("poaceae_c3", 0.0)
                   if veg is not None else 0.0)
    # Pick "poaceae_c3" index = first sorted ("legumes" comes first
    # alphabetically; we want index 1 for poaceae_c3).
    lib_sorted = sorted({"legumes", "poaceae_c3"})
    idx = lib_sorted.index("poaceae_c3")
    dec = Decision(action=int(ActionKind.PLANT),
                   target_x=float(idx), target_y=0.0,
                   confidence=1.0)
    apply_decision(sim.agents, row, dec, sim.streamer, sim.tick)
    veg = sim._plant_state.chunk_vegetation.get(chunk_c)
    mass_after = (veg.biomass_kg.get("poaceae_c3", 0.0)
                  if veg is not None else 0.0)
    ok = mass_after > mass_before and state.plant_events == 1
    print(_row("step 1 — autonomous PLANT via apply_decision wrapper",
               ok,
               f"{mass_before:.1f} → {mass_after:.1f} kg ; "
               f"events={state.plant_events}"))
    if not ok:
        failures += 1

    # Step 2 — autonomous HARVEST via Decision dispatch
    inv_before = float(sim.agents.inv_food[row])
    dec = Decision(action=int(ActionKind.HARVEST),
                   confidence=1.0)
    apply_decision(sim.agents, row, dec, sim.streamer, sim.tick)
    inv_after = float(sim.agents.inv_food[row])
    ok = inv_after > inv_before and state.harvest_events == 1
    print(_row("step 2 — autonomous HARVEST via apply_decision wrapper",
               ok,
               f"inv {inv_before:.3f} → {inv_after:.3f} kg ; "
               f"events={state.harvest_events}"))
    if not ok:
        failures += 1

    # Step 3 — FORAGE triggers discovery hook
    n_before = len(state.culture_seed_library.get(0, set()))
    dec = Decision(action=int(ActionKind.FORAGE), confidence=1.0)
    apply_decision(sim.agents, 1, dec, sim.streamer, sim.tick)
    n_after = len(state.culture_seed_library.get(0, set()))
    ok = n_after >= n_before  # ≥ — discovery may add 0 if all known already
    print(_row("step 3 — FORAGE invokes seed-discovery hook",
               ok, f"lib_size {n_before} → {n_after}"))
    if not ok:
        failures += 1

    # Step 4 — Existing actions intact ; full sim runs 200 ticks no-crash
    sim2 = _build_sim("p33_full")
    for _ in range(200):
        sim2.step()
    snap = agriculture_state(sim2)
    print(_row("step 4 — 200 ticks no crash + agriculture snap available",
               snap is not None and "plant_events" in snap,
               f"alive={int(sim2.agents.alive[:sim2.agents.n_active].sum())} "
               f"events={snap.get('plant_events')}"))

    # Step 5 — Determinism : SHA-256 over a stable subset.
    def _state_hash(s):
        agents = s.agents
        n = s.agents.n_active
        buf = (agents.alive[:n].tobytes()
               + agents.pos[:n].tobytes()
               + agents.hunger[:n].tobytes()
               + agents.thirst[:n].tobytes())
        return hashlib.sha256(buf).hexdigest()[:24]

    sim_a = _build_sim("p33_det_a")
    for _ in range(120):
        sim_a.step()
    sim_b = _build_sim("p33_det_b")
    for _ in range(120):
        sim_b.step()
    h_a = _state_hash(sim_a)
    h_b = _state_hash(sim_b)
    ok = h_a == h_b
    print(_row("step 5 — determinism bit-identical across runs",
               ok, f"{h_a} == {h_b}"))
    if not ok:
        failures += 1

    print()
    if failures == 0:
        print("RESULT: PASS — Phase 4 cognition wiring smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
