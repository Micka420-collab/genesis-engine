"""Invariants — the agent loop RAISES a draught kiln (D12 wire, 2026-06-29, consumes C11).

The 14th wire — and the FIRST APPARATUS the agent builds (the pendant of C7's fire). C11
``kiln_draft`` made kiln-building *perceivable* (wall-clay around a makeable fire reaching a higher
peak temperature); but no agent ever lined a hearth. An agent that KNOWS FIRE (``has_made_fire``,
IGNITE/C7) AND CARRIES clay (``inv_clay``, DIG/C5) RAISE_KILNs — enclosing the fire in clay walls so
it burns hotter (``kiln_peak_c``), the heat that will (a later bite) redeem C9 vitrification and C10
hard-burnt mortar. Appended to ``_ARC_SEEKS`` as one line; consumes inv_clay, adds NO new inventory.

What this file proves:
1. Gated on C11 (no cue cache → inert).
2. Fire dependency (C7): a never-made-fire agent does not build a kiln.
3. Clay dependency (C5): a fire-knowing agent with no clay does not build a kiln.
4. A ready agent (fire + clay) on the best site chooses RAISE_KILN; off-site WALK_TOs.
5. RAISE_KILN spends clay, records the apparatus skill (has_built_kiln) + the peak + the site.
6. The lie #19 (inversion-of-the-inversion): a refractory-walled kiln reaches a higher peak than a
   common-clay one, and any kiln beats the bare open fire (draft_gain > 0).
7. Self-limiting — once built (has_built_kiln) the agent does not re-seek to build another.
8. « le monde ne ment jamais » — building where no kiln is feasible keeps the clay.
9. Survival outranks building.
10. Back-compat (sim=None inert), non-mutation (consumes inv_clay only, geology unchanged).
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
import engine.kiln_draft as kd                                     # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_KILN = 0xBEEF     # clay + makeable fire co-located; refractory + common-clay walls both present
GRID = 12


def _booted_sim(name: str, seed: int = SEED_KILN, *, with_c11: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c11:
        kd.install_kiln_draft(sim)   # also installs the composed C5 clay + C7 fire
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_kiln_coord(sim, coords):
    best = None
    for coord in coords:
        cue = kd.kiln_cue_for_chunk(sim, coord)
        if cue is None or not cue.buildable:
            continue
        key = (cue.kiln_peak_c, cue.fire_confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _site_refractory(sim, coords, want: bool):
    for coord in coords:
        cue = kd.kiln_cue_for_chunk(sim, coord)
        if cue is not None and cue.buildable and bool(cue.wall_refractory) is want:
            return coord
    return None


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _calm_curious(sim, row, *, knows_fire=True, clay_kg=2.0, ready=False):
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
    sim.agents.inv_clay[row] = float(clay_kg)
    mem = sim.agents.memory[row]
    mem.known_kiln_site_locations.clear()
    mem.has_built_kiln = False
    mem.last_kiln_peak_c = None
    mem.has_made_fire = bool(knows_fire)
    mem.last_fire_method = "PERCUSSION" if knows_fire else None
    if ready:
        # Drive the full decide() to RAISE_KILN: sate the clay store (no DIG) + warm (no IGNITE).
        sim.agents.inv_clay[row] = cog.CLAY_SATED_KG
        sim.agents.thermal[row] = 0.05


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


def _kiln_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.RAISE_KILN), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


def test_seek_kilnbuild_inert_without_c11():
    sim, coords = _booted_sim("gate", with_c11=False)
    _calm_curious(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_kiln_draft_cue_cache", None) is None
    assert cog._seek_kilnbuild(sim.agents, 0, _obs(sim, 0), sim) is None


def test_agent_without_fire_does_not_build_kiln():
    sim, coords = _booted_sim("needs_fire")
    best = _best_kiln_coord(sim, coords)
    if best is None:
        pytest.skip("no buildable kiln")
    _calm_curious(sim, 0, knows_fire=False, ready=True)
    sim.agents.memory[0].has_made_fire = False
    _stand(sim, 0, best)
    assert cog._seek_kilnbuild(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _kiln_here(sim, 0) == []


def test_agent_without_clay_does_not_build_kiln():
    sim, coords = _booted_sim("needs_clay")
    best = _best_kiln_coord(sim, coords)
    if best is None:
        pytest.skip("no buildable kiln")
    _calm_curious(sim, 0, clay_kg=0.0, ready=True)
    sim.agents.inv_clay[0] = 0.0
    _stand(sim, 0, best)
    assert cog._seek_kilnbuild(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _kiln_here(sim, 0) == []


def test_ready_agent_on_its_chosen_kiln_decides_to_raise_it():
    sim, coords = _booted_sim("build")
    best = _best_kiln_coord(sim, coords)
    if best is None:
        pytest.skip("no buildable kiln")
    _calm_curious(sim, 0, ready=True)
    _stand(sim, 0, best)
    # best_kiln_site_near is deterministic but may prefer a different (equal-peak, higher-confidence)
    # kiln than our helper; stand the agent on the WIRE's own pick so it is underfoot at distance 0.
    pick = kd.best_kiln_site_near(sim, 0, perception_radius_m=cog.KILN_BUILD_PERCEPT_M)
    if pick is None:
        pytest.skip("no kiln perceived")
    _stand(sim, 0, pick.coord)
    seek = cog._seek_kilnbuild(sim.agents, 0, _obs(sim, 0), sim)
    assert seek is not None and seek.action == int(ActionKind.RAISE_KILN)


def test_ready_agent_walks_toward_perceived_kiln_site():
    sim, coords = _booted_sim("walk")
    best = _best_kiln_coord(sim, coords)
    if best is None:
        pytest.skip("no buildable kiln")
    # Place the agent one chunk away from a buildable kiln (off-site but in perception) and assert the
    # kiln wire STEERS it (WALK_TO, not random EXPLORE). Exact target is not asserted: among many
    # equal-peak kilns the argmax pick is tie-break-sensitive — what matters is the agent walks to a kiln.
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0, ready=True)
    sim.agents.pos[0, 0] = cx + CHUNK_SIDE_M       # one chunk east — off-site, still in range
    sim.agents.pos[0, 1] = cy
    seek = cog._seek_kilnbuild(sim.agents, 0, _obs(sim, 0), sim)
    if seek is None or seek.action == int(ActionKind.RAISE_KILN):
        pytest.skip("nearest kiln is underfoot from this offset — no WALK_TO to assert")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)               # the wire steers toward a kiln


def test_raising_kiln_spends_clay_records_and_remembers():
    sim, coords = _booted_sim("act")
    best = _best_kiln_coord(sim, coords)
    if best is None:
        pytest.skip("no buildable kiln")
    cue = kd.kiln_cue_for_chunk(sim, best)
    _calm_curious(sim, 0, clay_kg=2.0)
    _stand(sim, 0, best)
    clay_before = float(sim.agents.inv_clay[0])
    ev = _kiln_here(sim, 0)
    assert ev and ev[-1]["kind"] == "kiln_build"
    assert float(sim.agents.inv_clay[0]) == pytest.approx(clay_before - cog.KILN_CLAY_COST_KG)
    assert ev[-1]["kiln_peak_c"] == round(float(cue.kiln_peak_c), 2)
    assert sim.agents.memory[0].has_built_kiln is True
    assert abs(sim.agents.memory[0].last_kiln_peak_c - cue.kiln_peak_c) < 1e-6
    assert len(sim.agents.memory[0].known_kiln_site_locations) == 1


def test_refractory_kiln_beats_common_and_open_fire():
    sim, coords = _booted_sim("inversion")
    cr = _site_refractory(sim, coords, True)
    cc = _site_refractory(sim, coords, False)
    if cr is None or cc is None:
        pytest.skip("seed lacks both wall classes")
    peaks = {}
    for label, coord in (("refractory", cr), ("common", cc)):
        cue = kd.kiln_cue_for_chunk(sim, coord)
        peaks[label] = float(cue.kiln_peak_c)
        assert cue.kiln_peak_c > cue.open_fire_peak_c          # any kiln beats the bare fire
        assert cue.draft_gain_c > 0.0
    assert peaks["refractory"] > peaks["common"]               # refractory walls reach a higher peak


def test_kiln_rich_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    best = _best_kiln_coord(sim, coords)
    if best is None:
        pytest.skip("no buildable kiln")
    _calm_curious(sim, 0, ready=True)
    sim.agents.memory[0].has_built_kiln = True                 # already discovered the apparatus
    _stand(sim, 0, best)
    assert cog._seek_kilnbuild(sim.agents, 0, _obs(sim, 0), sim) is None


def test_building_where_no_kiln_feasible_keeps_clay():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0, clay_kg=2.0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert kd.prospect_kiln(sim, fx, fy) is None
    clay_before = float(sim.agents.inv_clay[0])
    ev = _kiln_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_clay[0]) == clay_before        # clay kept where nothing builds
    assert sim.agents.memory[0].has_built_kiln is False


def test_critical_thirst_outranks_building():
    sim, coords = _booted_sim("priority")
    best = _best_kiln_coord(sim, coords)
    if best is None:
        pytest.skip("no buildable kiln")
    _calm_curious(sim, 0, ready=True)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)


def test_raise_kiln_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_kiln_coord(sim, coords)
    if best is None:
        pytest.skip("no buildable kiln")
    _calm_curious(sim, 0, clay_kg=2.0)
    px, py = _stand(sim, 0, best)
    clay_before = float(sim.agents.inv_clay[0])
    dec = cog.Decision(int(ActionKind.RAISE_KILN), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_clay[0]) == clay_before
    assert sim.agents.memory[0].has_built_kiln is False


def test_raise_kiln_consumes_only_clay_and_is_non_mutating():
    sim, coords = _booted_sim("orthogonal")
    best = _best_kiln_coord(sim, coords)
    if best is None:
        pytest.skip("no buildable kiln")
    _calm_curious(sim, 0, clay_kg=2.0)
    _stand(sim, 0, best)
    g_before = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
                for layer in geo.chunk_geology(sim, best).layers]
    stone_before = float(sim.agents.inv_stone[0])
    fuel_before = float(sim.agents.inv_fuel[0])
    _kiln_here(sim, 0)
    g_after = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
               for layer in geo.chunk_geology(sim, best).layers]
    assert g_before == g_after                              # geology unchanged
    assert float(sim.agents.inv_stone[0]) == stone_before   # only inv_clay moved (the lining)
    assert float(sim.agents.inv_fuel[0]) == fuel_before


def test_raise_kiln_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    best = _best_kiln_coord(a, ca)
    if best is None:
        pytest.skip("no buildable kiln")
    evs = []
    for s in (a, b):
        _calm_curious(s, 0, clay_kg=2.0)
        _stand(s, 0, best)
        evs.append(_kiln_here(s, 0)[-1])
    assert evs[0]["kiln_peak_c"] == evs[1]["kiln_peak_c"]
    assert evs[0]["wall_refractory"] == evs[1]["wall_refractory"]
    assert evs[0]["draft_gain_c"] == evs[1]["draft_gain_c"]
