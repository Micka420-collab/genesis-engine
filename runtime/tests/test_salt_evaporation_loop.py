"""Invariants — the agent loop RAKES solar salt from a brine pan (D12 wire, 2026-06-29, consumes C15).

The 12th wire — a NON-FIRE / non-thermal precursor (the sun does the work). C15 ``salt_evaporation``
made arid brine pans *perceivable* (a white efflorescence crust); but no agent ever raked one.
``inv_salt`` is « white gold » — the preservative the future C16 ``food_curing`` needs, and a
structurer of neolithic trade. Appended to ``_ARC_SEEKS`` as one line.

Fixture: like the C15 capability test, the sim is anchored at the map's most evaporative saline
coast (SEED 0x5A17) — no injection, the world genuinely has this arid coast; we point the camera at it.

What this file proves:
1. Gated on C15 (no cue cache → inert).
2. A curious agent on the best pan chooses RAKE; off-site it WALK_TOs toward it.
3. RAKE fills the salt store, records the aridity zone + the site.
4. Outcome tracks the world: an abundant salar yields the abundant-scaled amount.
5. « le monde ne ment jamais » + the lie #17: raking where no pan is underfoot yields nothing; a
   humid saline lagoon never crusts (``harvestable`` False) — proven on the pure-derivation oracle.
6. Self-limiting — a salt-rich agent (inv_salt ≥ sated) stops seeking.
7. Survival outranks raking.
8. Back-compat (sim=None inert), orthogonality (only inv_salt moves), non-mutation (no mine_at).
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
from engine.world_genesis import GenesisParams, generate_world     # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim         # noqa: E402
from engine import geology as geo                                  # noqa: E402
from engine import cognition as cog                                # noqa: E402
from engine.cognition import Observation, PerceivedTarget          # noqa: E402
from engine.agent import ActionKind, DriveKind                     # noqa: E402
from engine.world import CHUNK_SIDE_M                              # noqa: E402
import engine.salt_evaporation as se                               # noqa: E402
import engine.water_potability as wp                               # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_SALT = 0x5A17     # "SALT" — the hottest, most arid saline coast on this map
GRID = 12


def _arid_saline_origin_km(world):
    R = world.params.resolution
    cell_km = world.params.map_size_km / R
    t = world.temp_c.astype(np.float64)
    p_th = np.where(t >= 0, 20.0 * t + 280.0, 20.0 * t)
    net = np.maximum(0.0, p_th - world.precip_mm)
    ar = np.where(p_th > 0, np.minimum(1.0, net / np.maximum(p_th, 1e-6)), 0.0)
    sea = world.elevation_m <= world.params.sea_level_m
    saline = sea | (world.elevation_m <= wp.COASTAL_MARGIN_M)
    score = np.where(saline, ar, -1.0)
    iy, ix = np.unravel_index(int(np.argmax(score)), score.shape)
    return (float((ix + 0.5) * cell_km), float((iy + 0.5) * cell_km))


def _booted_sim(name: str, seed: int = SEED_SALT, *, with_c15: bool = True):
    world = generate_world(GenesisParams(seed=seed, resolution=128, n_plates=8))
    origin = _arid_saline_origin_km(world)
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8),
                          sim_origin_macro_km=origin)
    geo.install_geology(sim)
    if with_c15:
        se.install_salt_evaporation(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_pan_coord(sim, coords):
    best = None
    for coord in coords:
        cue = se.saltpan_cue_for_chunk(sim, coord)
        if cue is None or not cue.harvestable:
            continue
        key = (cue.salt_yield_kg_m2, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


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
                "inv_pigment", "inv_clay", "inv_ceramic", "inv_limestone", "inv_lime", "inv_salt"):
        getattr(sim.agents, inv)[row] = 0.0
    mem = sim.agents.memory[row]
    mem.known_saltpan_locations.clear()
    mem.last_salt_zone = None


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


def _rake_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.RAKE), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


def test_seek_saltpan_inert_without_c15():
    sim, coords = _booted_sim("gate", with_c15=False)
    _calm_curious(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_saltpan_cue_cache", None) is None
    assert cog._seek_saltpan(sim.agents, 0, _obs(sim, 0), sim) is None


def test_curious_agent_on_pan_decides_to_rake():
    sim, coords = _booted_sim("rake")
    best = _best_pan_coord(sim, coords)
    if best is None:
        pytest.skip("no harvestable pan")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.RAKE)


def test_curious_agent_walks_toward_perceived_pan():
    sim, coords = _booted_sim("walk")
    best = _best_pan_coord(sim, coords)
    if best is None:
        pytest.skip("no harvestable pan")
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0)
    sim.agents.pos[0, 0] = cx + 10.0
    sim.agents.pos[0, 1] = cy
    pick = se.best_saltpan_near(sim, 0, perception_radius_m=cog.SALTPAN_PERCEPT_M)
    assert pick is not None
    tx = (pick.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (pick.coord[1] + 0.5) * CHUNK_SIDE_M
    if ((tx - (cx + 10.0)) ** 2 + (ty - cy) ** 2) ** 0.5 < cog.INTERACT_RADIUS_M:
        pytest.skip("best pan is underfoot — no WALK_TO to assert")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)
    assert abs(dec.target_x - tx) < 1e-3
    assert abs(dec.target_y - ty) < 1e-3


def test_raking_fills_salt_records_and_remembers():
    sim, coords = _booted_sim("fill")
    best = _best_pan_coord(sim, coords)
    if best is None:
        pytest.skip("no harvestable pan")
    cue = se.saltpan_cue_for_chunk(sim, best)
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    before = float(sim.agents.inv_salt[0])
    ev = _rake_here(sim, 0)
    assert ev and ev[-1]["kind"] == "rake"
    assert ev[-1]["zone"] == cue.zone
    assert float(sim.agents.inv_salt[0]) > before
    assert sim.agents.memory[0].last_salt_zone == cue.zone
    assert len(sim.agents.memory[0].known_saltpan_locations) == 1


def test_abundant_pan_yields_the_abundant_scaled_amount():
    sim, coords = _booted_sim("yield")
    best = _best_pan_coord(sim, coords)
    if best is None:
        pytest.skip("no harvestable pan")
    cue = se.saltpan_cue_for_chunk(sim, best)
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    ev = _rake_here(sim, 0)
    expected = cog.SALT_HARVEST_KG * (cog.SALT_ABUNDANT_MULT if cue.abundant else 1.0)
    assert abs(float(ev[-1]["salt_kg"]) - expected) < 1e-3
    assert ev[-1]["abundant"] is bool(cue.abundant)


def test_lie_17_humid_saline_lagoon_never_crusts():
    """The harvestability gate the wire relies on: the SAME brine in an arid vs a humid climate —
    arid crusts (harvestable), humid never does (the sun never wins against the rain)."""
    arid = se._saltpan_from_inputs((0, 0, 0), 35.0, "coastal", 100.0,
                                   temp_c=28.0, precip_mm=40.0, biome=7)
    humid = se._saltpan_from_inputs((0, 0, 0), 35.0, "coastal", 100.0,
                                    temp_c=28.0, precip_mm=2000.0, biome=11)
    assert arid is not None and arid.harvestable is True
    assert humid is None or humid.harvestable is False


def test_raking_where_no_pan_yields_nothing():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert se.prospect_saltpan(sim, fx, fy) is None
    ev = _rake_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_salt[0]) == 0.0
    assert len(sim.agents.memory[0].known_saltpan_locations) == 0


def test_salt_rich_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    best = _best_pan_coord(sim, coords)
    if best is None:
        pytest.skip("no harvestable pan")
    _calm_curious(sim, 0)
    sim.agents.inv_salt[0] = cog.SALT_SATED_KG + 0.1
    _stand(sim, 0, best)
    assert cog._seek_saltpan(sim.agents, 0, _obs(sim, 0), sim) is None


def test_critical_thirst_outranks_raking():
    sim, coords = _booted_sim("priority")
    best = _best_pan_coord(sim, coords)
    if best is None:
        pytest.skip("no harvestable pan")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)


def test_rake_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_pan_coord(sim, coords)
    if best is None:
        pytest.skip("no harvestable pan")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    dec = cog.Decision(int(ActionKind.RAKE), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_salt[0]) == 0.0


def test_rake_fills_only_salt_and_is_non_mutating():
    sim, coords = _booted_sim("orthogonal")
    best = _best_pan_coord(sim, coords)
    if best is None:
        pytest.skip("no harvestable pan")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    g_before = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
                for layer in geo.chunk_geology(sim, best).layers]
    _rake_here(sim, 0)
    g_after = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
               for layer in geo.chunk_geology(sim, best).layers]
    assert g_before == g_after                              # geology unchanged
    assert float(sim.agents.inv_salt[0]) > 0.0             # salt filled…
    assert float(sim.agents.inv_stone[0]) == 0.0           # …only the salt store moved
    assert float(sim.agents.inv_limestone[0]) == 0.0
    assert float(sim.agents.inv_clay[0]) == 0.0


def test_rake_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    best = _best_pan_coord(a, ca)
    if best is None:
        pytest.skip("no harvestable pan")
    evs = []
    for s in (a, b):
        _calm_curious(s, 0)
        _stand(s, 0, best)
        evs.append(_rake_here(s, 0)[-1])
    assert evs[0]["zone"] == evs[1]["zone"]
    assert evs[0]["salt_kg"] == evs[1]["salt_kg"]
    assert evs[0]["abundant"] == evs[1]["abundant"]
    assert abs(float(a.agents.inv_salt[0]) - float(b.agents.inv_salt[0])) < 1e-12
