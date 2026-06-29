"""Invariants — the agent loop GLEANS combustible fuel (D12 wire, 2026-06-29, consumes C4).

The 13th wire — a NON-FIRE precursor (the fuel that will FEED fires and kilns, not be one). C4
``combustible_outcrop`` made dark fuel exposures *perceivable* (peat / oil-shale / coal); but no
agent ever gleaned one. ``inv_fuel`` is durable combustible — coal is the only smelting-grade fuel,
the future enabler of C13 metallurgy. Appended to ``_ARC_SEEKS`` as one line.

What this file proves:
1. Gated on C4 (no cue cache → inert).
2. A curious agent on the best burnable exposure chooses GLEAN; off-site it WALK_TOs toward it.
3. GLEAN fills the fuel store, records the fuel class + the site.
4. Outcome = world truth: a COAL exposure (smelting-grade, higher calorific) yields more than OIL_SHALE.
5. « le monde ne ment jamais » — gleaning where no fuel is underfoot yields nothing.
6. Self-limiting — a fuel-rich agent (inv_fuel ≥ sated) stops seeking.
7. Survival outranks gleaning.
8. Back-compat (sim=None inert), orthogonality (only inv_fuel moves), non-mutation (no mine_at).
9. Determinism.
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
import engine.combustible_outcrop as co                            # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_FUEL = 0xBEEF     # coal + oil-shale exposures, all burnable, some smelting-grade
GRID = 12


def _booted_sim(name: str, seed: int = SEED_FUEL, *, with_c4: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c4:
        co.install_combustible_outcrop(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_fuel_coord(sim, coords):
    best = None
    for coord in coords:
        cue = co.combustible_cue_for_chunk(sim, coord)
        if cue is None or not cue.burnable_now:
            continue
        key = (cue.calorific_grade, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _site_of_class(sim, coords, class_name: str):
    for coord in coords:
        cue = co.combustible_cue_for_chunk(sim, coord)
        if cue is not None and cue.fuel_class.name == class_name and cue.burnable_now:
            return coord
    return None


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _calm_curious(sim, row):
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
    mem = sim.agents.memory[row]
    mem.known_fuel_locations.clear()
    mem.last_fuel_class = None


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


def _glean_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.GLEAN), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


def test_seek_fuel_inert_without_c4():
    sim, coords = _booted_sim("gate", with_c4=False)
    _calm_curious(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_combustible_cue_cache", None) is None
    assert cog._seek_fuel(sim.agents, 0, _obs(sim, 0), sim) is None


def test_curious_agent_on_exposure_decides_to_glean():
    sim, coords = _booted_sim("glean")
    best = _best_fuel_coord(sim, coords)
    if best is None:
        pytest.skip("no burnable fuel")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.GLEAN)


def test_curious_agent_walks_toward_perceived_exposure():
    sim, coords = _booted_sim("walk")
    best = _best_fuel_coord(sim, coords)
    if best is None:
        pytest.skip("no fuel")
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0)
    sim.agents.pos[0, 0] = cx + 10.0
    sim.agents.pos[0, 1] = cy
    pick = co.best_fuel_near(sim, 0, perception_radius_m=cog.FUEL_PERCEPT_M, require_burnable=True)
    assert pick is not None
    tx = (pick.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (pick.coord[1] + 0.5) * CHUNK_SIDE_M
    if ((tx - (cx + 10.0)) ** 2 + (ty - cy) ** 2) ** 0.5 < cog.INTERACT_RADIUS_M:
        pytest.skip("best fuel is underfoot — no WALK_TO to assert")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)
    assert abs(dec.target_x - tx) < 1e-3
    assert abs(dec.target_y - ty) < 1e-3


def test_gleaning_fills_fuel_records_and_remembers():
    sim, coords = _booted_sim("fill")
    best = _best_fuel_coord(sim, coords)
    if best is None:
        pytest.skip("no fuel")
    cue = co.combustible_cue_for_chunk(sim, best)
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    before = float(sim.agents.inv_fuel[0])
    ev = _glean_here(sim, 0)
    assert ev and ev[-1]["kind"] == "glean"
    assert ev[-1]["fuel_class"] == cue.fuel_class.name
    assert float(sim.agents.inv_fuel[0]) > before
    assert sim.agents.memory[0].last_fuel_class == cue.fuel_class.name
    assert len(sim.agents.memory[0].known_fuel_locations) == 1


def test_coal_yields_more_than_oil_shale():
    sim, coords = _booted_sim("grade")
    cc = _site_of_class(sim, coords, "COAL")
    cs = _site_of_class(sim, coords, "OIL_SHALE")
    if cc is None or cs is None:
        pytest.skip("seed lacks both fuel classes")
    yields = {}
    for label, coord in (("coal", cc), ("oil_shale", cs)):
        s, _c = _booted_sim(f"grade_{label}")
        _calm_curious(s, 0)
        _stand(s, 0, coord)
        ev = _glean_here(s, 0)
        yields[label] = float(ev[-1]["fuel_kg"])
    assert yields["coal"] > yields["oil_shale"]            # higher calorific_grade → more fuel


def test_gleaning_where_no_fuel_yields_nothing():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert co.prospect_fuel(sim, fx, fy) is None
    ev = _glean_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_fuel[0]) == 0.0
    assert len(sim.agents.memory[0].known_fuel_locations) == 0


def test_fuel_rich_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    best = _best_fuel_coord(sim, coords)
    if best is None:
        pytest.skip("no fuel")
    _calm_curious(sim, 0)
    sim.agents.inv_fuel[0] = cog.FUEL_SATED_KG + 0.1
    _stand(sim, 0, best)
    assert cog._seek_fuel(sim.agents, 0, _obs(sim, 0), sim) is None


def test_critical_thirst_outranks_gleaning():
    sim, coords = _booted_sim("priority")
    best = _best_fuel_coord(sim, coords)
    if best is None:
        pytest.skip("no fuel")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)


def test_glean_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_fuel_coord(sim, coords)
    if best is None:
        pytest.skip("no fuel")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    dec = cog.Decision(int(ActionKind.GLEAN), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_fuel[0]) == 0.0


def test_glean_fills_only_fuel_and_is_non_mutating():
    sim, coords = _booted_sim("orthogonal")
    best = _best_fuel_coord(sim, coords)
    if best is None:
        pytest.skip("no fuel")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    g_before = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
                for layer in geo.chunk_geology(sim, best).layers]
    _glean_here(sim, 0)
    g_after = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
               for layer in geo.chunk_geology(sim, best).layers]
    assert g_before == g_after                              # geology unchanged
    assert float(sim.agents.inv_fuel[0]) > 0.0             # fuel filled…
    assert float(sim.agents.inv_stone[0]) == 0.0           # …only the fuel store moved
    assert float(sim.agents.inv_wood[0]) == 0.0            # NOT the building-wood store
    assert float(sim.agents.inv_limestone[0]) == 0.0


def test_glean_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    best = _best_fuel_coord(a, ca)
    if best is None:
        pytest.skip("no fuel")
    evs = []
    for s in (a, b):
        _calm_curious(s, 0)
        _stand(s, 0, best)
        evs.append(_glean_here(s, 0)[-1])
    assert evs[0]["fuel_class"] == evs[1]["fuel_class"]
    assert evs[0]["calorific_grade"] == evs[1]["calorific_grade"]
    assert evs[0]["fuel_kg"] == evs[1]["fuel_kg"]
    assert abs(float(a.agents.inv_fuel[0]) - float(b.agents.inv_fuel[0])) < 1e-12
