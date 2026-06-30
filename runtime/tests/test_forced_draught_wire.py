"""Invariants — the agent loop FORCES a draught on its kiln (D12 wire, 2026-06-30, consumes C12).

The 15th wire — and the 2nd APPARATUS the agent builds (the pendant of C11's kiln: raise → force).
C12 ``forced_draught`` made the forced furnace *perceivable* (a charcoal-fed kiln blown by a bellows
reaching past the natural-draught peak); but no agent ever worked the bellows. An agent that has
ALREADY BUILT A KILN (``has_built_kiln``, RAISE_KILN/C11) AND CARRIES fuel (``inv_fuel``, GLEAN/C4)
FORCE_DRAUGHTs it — driving the furnace into the high-temp regime that finally VITRIFIES the refractory
kaolin (the step C9/C11 both deferred) and reaches the copper-smelting threshold. Appended to
``_ARC_SEEKS`` as one line; consumes inv_fuel, adds NO new inventory.

What this file proves:
1. Gated on C12 (no cue cache → inert).
2. Kiln dependency (C11): an agent that never built a kiln does not force a draught.
3. Fuel dependency (C4): a kiln-builder with no fuel in hand does not force a draught.
4. A ready agent (kiln + fuel) on the best furnace chooses FORCE_DRAUGHT; off-site WALK_TOs.
5. FORCE_DRAUGHT spends fuel, records the apparatus skill (has_forced_draught) + the peak + the site.
6. The lie #20 (the wall the bellows cannot beat): a refractory furnace reaches a higher forced peak
   than a common one AND vitrifies watertight; a common-walled furnace caps just past copper and never
   vitrifies.
7. Self-limiting — once forced (has_forced_draught) the agent does not re-seek.
8. « le monde ne ment jamais » — forcing where no kiln is forceable keeps the fuel.
9. Survival outranks forcing.
10. Back-compat (sim=None inert), non-mutation (consumes inv_fuel only, geology unchanged).
11. Determinism.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

import numpy as np                                                  # noqa: E402
import pytest                                                       # noqa: E402

from engine.sim import Simulation, SimConfig                       # noqa: E402
from engine.world_genesis import GenesisParams                     # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim         # noqa: E402
from engine import geology as geo                                  # noqa: E402
from engine import cognition as cog                                # noqa: E402
from engine.cognition import Observation, PerceivedTarget          # noqa: E402
from engine.agent import ActionKind, DriveKind                     # noqa: E402
from engine.world import CHUNK_SIDE_M                              # noqa: E402
import engine.forced_draught as fd                                 # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_FORCE = 0xBEEF    # clay + makeable fire co-located; refractory + common-clay walls both present
GRID = 12


def _booted_sim(name: str, seed: int = SEED_FORCE, *, with_c12: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c12:
        fd.install_forced_draught(sim)   # also installs the composed C11 kiln + C1 mineralization
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_force_coord(sim, coords):
    best = None
    for coord in coords:
        cue = fd.forced_cue_for_chunk(sim, coord)
        if cue is None or not cue.forceable:
            continue
        key = (cue.forced_peak_c, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _site_refractory(sim, coords, want: bool):
    for coord in coords:
        cue = fd.forced_cue_for_chunk(sim, coord)
        if cue is not None and cue.forceable and bool(cue.wall_refractory) is want:
            return coord
    return None


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _calm_curious(sim, row, *, built_kiln=True, fuel_kg=2.0):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal",
                "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal", "inv_tools",
                "inv_pigment", "inv_clay", "inv_ceramic", "inv_limestone", "inv_lime",
                "inv_salt", "inv_fuel"):
        getattr(sim.agents, inv)[row] = 0.0
    sim.agents.inv_fuel[row] = float(fuel_kg)
    sim.agents.thermal[row] = 0.05
    mem = sim.agents.memory[row]
    mem.known_forced_locations.clear()
    mem.has_forced_draught = False
    mem.last_forced_peak_c = None
    mem.has_built_kiln = bool(built_kiln)        # the C11 dependency (built the kiln we now force)
    mem.last_kiln_peak_c = 900.0 if built_kiln else None
    mem.has_made_fire = True                     # a kiln-builder already knows fire
    mem.last_fire_method = "PERCUSSION"


def _obs(sim, row, *, nearest=None, drives=None):
    a = sim.agents
    d = drives if drives is not None else np.array(
        [float(a.hunger[row]), float(a.thirst[row]), float(a.sleep[row]),
         float(a.fatigue[row]), float(a.thermal[row]), float(a.pain[row]),
         float(a.stress[row]), float(a.loneliness[row])], dtype=np.float32)
    return Observation(
        row=int(row),
        pos=(float(a.pos[row, 0]), float(a.pos[row, 1]), float(a.pos[row, 2])),
        drives=d, vitality=float(a.vitality[row]), nearest=(nearest or {}),
        near_agents=[], dominant_drive=cog._dominant_drive(d),
        tick=0, reproduction_readiness=0.0)


def _far_unstreamed(grid: int = GRID):
    return ((grid + 50 + 0.5) * CHUNK_SIDE_M, (grid + 50 + 0.5) * CHUNK_SIDE_M)


def _force_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.FORCE_DRAUGHT), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


def test_seek_forcedraught_inert_without_c12():
    sim, coords = _booted_sim("gate", with_c12=False)
    _calm_curious(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_forced_draught_cue_cache", None) is None
    assert cog._seek_forcedraught(sim.agents, 0, _obs(sim, 0), sim) is None


def test_agent_without_built_kiln_does_not_force():
    sim, coords = _booted_sim("needs_kiln")
    best = _best_force_coord(sim, coords)
    if best is None:
        pytest.skip("no forceable furnace")
    _calm_curious(sim, 0, built_kiln=False)
    _stand(sim, 0, best)
    assert cog._seek_forcedraught(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _force_here(sim, 0) == []


def test_agent_without_fuel_does_not_force():
    sim, coords = _booted_sim("needs_fuel")
    best = _best_force_coord(sim, coords)
    if best is None:
        pytest.skip("no forceable furnace")
    _calm_curious(sim, 0, fuel_kg=0.0)
    _stand(sim, 0, best)
    assert cog._seek_forcedraught(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _force_here(sim, 0) == []


def test_ready_agent_on_its_chosen_furnace_decides_to_force():
    sim, coords = _booted_sim("force")
    best = _best_force_coord(sim, coords)
    if best is None:
        pytest.skip("no forceable furnace")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    pick = fd.best_forced_site_near(sim, 0, perception_radius_m=cog.FORCE_PERCEPT_M)
    if pick is None:
        pytest.skip("no furnace perceived")
    _stand(sim, 0, pick.coord)
    seek = cog._seek_forcedraught(sim.agents, 0, _obs(sim, 0), sim)
    assert seek is not None and seek.action == int(ActionKind.FORCE_DRAUGHT)


def test_ready_agent_walks_toward_perceived_furnace():
    sim, coords = _booted_sim("walk")
    best = _best_force_coord(sim, coords)
    if best is None:
        pytest.skip("no forceable furnace")
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0)
    sim.agents.pos[0, 0] = cx + CHUNK_SIDE_M       # one chunk east — off-site, still in range
    sim.agents.pos[0, 1] = cy
    seek = cog._seek_forcedraught(sim.agents, 0, _obs(sim, 0), sim)
    if seek is None or seek.action == int(ActionKind.FORCE_DRAUGHT):
        pytest.skip("nearest furnace is underfoot from this offset — no WALK_TO to assert")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)               # the wire steers toward a furnace


def test_forcing_spends_fuel_records_and_remembers():
    sim, coords = _booted_sim("act")
    best = _best_force_coord(sim, coords)
    if best is None:
        pytest.skip("no forceable furnace")
    cue = fd.forced_cue_for_chunk(sim, best)
    _calm_curious(sim, 0, fuel_kg=2.0)
    _stand(sim, 0, best)
    fuel_before = float(sim.agents.inv_fuel[0])
    ev = _force_here(sim, 0)
    assert ev and ev[-1]["kind"] == "force_draught"
    assert float(sim.agents.inv_fuel[0]) == pytest.approx(fuel_before - cog.FORCE_FUEL_COST_KG)
    assert ev[-1]["forced_peak_c"] == round(float(cue.forced_peak_c), 2)
    assert sim.agents.memory[0].has_forced_draught is True
    assert abs(sim.agents.memory[0].last_forced_peak_c - cue.forced_peak_c) < 1e-6
    assert len(sim.agents.memory[0].known_forced_locations) == 1


def test_refractory_furnace_beats_common_and_vitrifies():
    sim, coords = _booted_sim("inversion")
    cr = _site_refractory(sim, coords, True)
    cc = _site_refractory(sim, coords, False)
    if cr is None or cc is None:
        pytest.skip("seed lacks both wall classes")
    cur = fd.forced_cue_for_chunk(sim, cr)
    cuk = fd.forced_cue_for_chunk(sim, cc)
    assert cur.forced_peak_c > cur.kiln_peak_c                  # the bellows wins over natural draught
    assert cur.forced_peak_c > cuk.forced_peak_c                # refractory walls reach a higher peak
    assert cur.vitrifies_watertight                            # refractory body finally vitrifies (lie #20)
    assert not cuk.vitrifies_watertight                        # common wall caps just past copper, never


def test_forced_rich_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    best = _best_force_coord(sim, coords)
    if best is None:
        pytest.skip("no forceable furnace")
    _calm_curious(sim, 0)
    sim.agents.memory[0].has_forced_draught = True             # already discovered the apparatus
    _stand(sim, 0, best)
    assert cog._seek_forcedraught(sim.agents, 0, _obs(sim, 0), sim) is None


def test_forcing_where_no_kiln_feasible_keeps_fuel():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0, fuel_kg=2.0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert fd.prospect_forced_draught(sim, fx, fy) is None
    fuel_before = float(sim.agents.inv_fuel[0])
    ev = _force_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_fuel[0]) == fuel_before        # fuel kept where nothing forces
    assert sim.agents.memory[0].has_forced_draught is False


def test_critical_thirst_outranks_forcing():
    sim, coords = _booted_sim("priority")
    best = _best_force_coord(sim, coords)
    if best is None:
        pytest.skip("no forceable furnace")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)


def test_force_draught_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_force_coord(sim, coords)
    if best is None:
        pytest.skip("no forceable furnace")
    _calm_curious(sim, 0, fuel_kg=2.0)
    px, py = _stand(sim, 0, best)
    fuel_before = float(sim.agents.inv_fuel[0])
    dec = cog.Decision(int(ActionKind.FORCE_DRAUGHT), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_fuel[0]) == fuel_before
    assert sim.agents.memory[0].has_forced_draught is False


def test_force_consumes_only_fuel_and_is_non_mutating():
    sim, coords = _booted_sim("orthogonal")
    best = _best_force_coord(sim, coords)
    if best is None:
        pytest.skip("no forceable furnace")
    _calm_curious(sim, 0, fuel_kg=2.0)
    _stand(sim, 0, best)
    g_before = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
                for layer in geo.chunk_geology(sim, best).layers]
    clay_before = float(sim.agents.inv_clay[0])
    stone_before = float(sim.agents.inv_stone[0])
    _force_here(sim, 0)
    g_after = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
               for layer in geo.chunk_geology(sim, best).layers]
    assert g_before == g_after                              # geology unchanged (D10 frozen)
    assert float(sim.agents.inv_clay[0]) == clay_before     # only inv_fuel moved (the charcoal charge)
    assert float(sim.agents.inv_stone[0]) == stone_before


def test_force_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    best = _best_force_coord(a, ca)
    if best is None:
        pytest.skip("no forceable furnace")
    evs = []
    for s in (a, b):
        _calm_curious(s, 0, fuel_kg=2.0)
        _stand(s, 0, best)
        evs.append(_force_here(s, 0)[-1])
    assert evs[0]["forced_peak_c"] == evs[1]["forced_peak_c"]
    assert evs[0]["wall_refractory"] == evs[1]["wall_refractory"]
    assert evs[0]["vitrifies_watertight"] == evs[1]["vitrifies_watertight"]
