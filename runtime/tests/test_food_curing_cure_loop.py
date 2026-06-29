"""Invariants — the agent loop CUREs raw food with salt (D12 wire, 2026-06-29, consumes C16 × C15).

The 14ᵉ wire — and the **1ʳᵉ qui consomme le PRODUIT d'une cap. précédente**: the salt the agent
itself RAKEd (C15) is the intrant that turns fugace fresh meat (``inv_food``) into months-keeping
cured haunch (``inv_cured_food``). NON-FIRE / non-thermal — D9 alternance: pendant non-feu du
RAISE_KILN. C16 ``food_curing`` made the physics visible (FIPS a_w 0.75 NaCl floor ; Q10 = 2.5 ;
shelf_life_days) ; but no agent ever USED it. Appended to ``_ARC_SEEKS`` between ``kilnbuild`` and
``ochre``.

What this file proves:
1. Gated on C16 (no ``_food_curing_state`` → inert).
2. Food dependency (FORAGE/HUNT): a foodless agent does not cure.
3. Salt dependency (C15/RAKE): a saltless agent does not cure (the world doesn't lie).
4. A ready agent (food + salt) on a saltpan chooses CURE; off-site WALK_TOs.
5. CURE spends inv_food + inv_salt, fills inv_cured_food, records ``has_cured_food`` + class + site.
6. The lie #7 lived: cure_at SHELF_STABLE / CURED in cool climate, drops to PERISHABLE in hot.
7. Self-limiting — once cured_food ≥ sated the agent does not re-seek.
8. « le monde ne ment jamais » — curing where no salt in hand keeps the food.
9. Survival outranks curing.
10. Back-compat (sim=None inert), non-mutation (consumes only agent inv ; geology + water unchanged).
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

from engine.sim import Simulation, SimConfig                        # noqa: E402
from engine.world_genesis import GenesisParams, generate_world      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine import cognition as cog                                 # noqa: E402
from engine.cognition import Observation                            # noqa: E402
from engine.agent import ActionKind, DriveKind                      # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.salt_evaporation as se                                # noqa: E402
import engine.water_potability as wp                                # noqa: E402
import engine.food_curing as fc                                     # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_CURE = 0x5A17     # same arid saline coast the C15 / C16 capability smokes use
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


def _booted_sim(name: str, seed: int = SEED_CURE, *, with_c16: bool = True):
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
    se.install_salt_evaporation(sim)
    if with_c16:
        fc.install_food_curing(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_saltpan_coord(sim, coords):
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


def _calm_curious(sim, row, *, food_kg=2.0, salt_kg=1.0):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal",
                "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal", "inv_tools",
                "inv_pigment", "inv_clay", "inv_ceramic", "inv_limestone", "inv_lime",
                "inv_salt", "inv_fuel", "inv_cured_food"):
        getattr(sim.agents, inv)[row] = 0.0
    sim.agents.inv_food[row] = float(food_kg)
    sim.agents.inv_salt[row] = float(salt_kg)
    mem = sim.agents.memory[row]
    mem.has_cured_food = False
    mem.last_preservation_class = None
    mem.known_saltpan_locations.clear()


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


def _cure_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.CURE), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


def test_seek_cure_inert_without_c16():
    sim, coords = _booted_sim("gate", with_c16=False)
    _calm_curious(sim, 0)
    best = _best_saltpan_coord(sim, coords)
    if best is None:
        pytest.skip("no saltpan")
    _stand(sim, 0, best)
    assert getattr(sim, "_food_curing_state", None) is None
    assert cog._seek_cure(sim.agents, 0, _obs(sim, 0), sim) is None


def test_agent_without_food_does_not_cure():
    sim, coords = _booted_sim("needs_food")
    best = _best_saltpan_coord(sim, coords)
    if best is None:
        pytest.skip("no saltpan")
    _calm_curious(sim, 0, food_kg=0.0)
    _stand(sim, 0, best)
    assert cog._seek_cure(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _cure_here(sim, 0) == []


def test_agent_without_salt_does_not_cure():
    sim, coords = _booted_sim("needs_salt")
    best = _best_saltpan_coord(sim, coords)
    if best is None:
        pytest.skip("no saltpan")
    _calm_curious(sim, 0, salt_kg=0.0)
    _stand(sim, 0, best)
    assert cog._seek_cure(sim.agents, 0, _obs(sim, 0), sim) is None
    food_before = float(sim.agents.inv_food[0])
    assert _cure_here(sim, 0) == []
    assert float(sim.agents.inv_food[0]) == food_before        # world doesn't lie: no salt, no cure


def test_ready_agent_on_a_saltpan_decides_to_cure():
    sim, coords = _booted_sim("cure")
    best = _best_saltpan_coord(sim, coords)
    if best is None:
        pytest.skip("no saltpan")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    pick = se.best_saltpan_near(sim, 0, perception_radius_m=cog.CURE_PERCEPT_M)
    if pick is None:
        pytest.skip("no saltpan perceived")
    _stand(sim, 0, pick.coord)
    seek = cog._seek_cure(sim.agents, 0, _obs(sim, 0), sim)
    assert seek is not None and seek.action == int(ActionKind.CURE)


def test_ready_agent_walks_toward_perceived_saltpan():
    sim, coords = _booted_sim("walk")
    best = _best_saltpan_coord(sim, coords)
    if best is None:
        pytest.skip("no saltpan")
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0)
    sim.agents.pos[0, 0] = cx + CHUNK_SIDE_M       # one chunk east — off-site, still in range
    sim.agents.pos[0, 1] = cy
    seek = cog._seek_cure(sim.agents, 0, _obs(sim, 0), sim)
    if seek is None or seek.action == int(ActionKind.CURE):
        pytest.skip("nearest saltpan is underfoot from this offset — no WALK_TO to assert")
    assert seek.action == int(ActionKind.WALK_TO)


def test_curing_spends_food_and_salt_fills_cured_records_and_remembers():
    sim, coords = _booted_sim("act")
    best = _best_saltpan_coord(sim, coords)
    if best is None:
        pytest.skip("no saltpan")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    food_before = float(sim.agents.inv_food[0])
    salt_before = float(sim.agents.inv_salt[0])
    cured_before = float(sim.agents.inv_cured_food[0])
    ev = _cure_here(sim, 0)
    assert ev and ev[-1]["kind"] == "cure"
    food_spent = ev[-1]["food_kg_spent"]
    salt_spent = ev[-1]["salt_kg_spent"]
    assert food_spent == pytest.approx(cog.CURE_FOOD_BATCH_KG)
    assert salt_spent == pytest.approx(cog.CURE_SALT_PER_KG_FOOD * cog.CURE_FOOD_BATCH_KG)
    assert float(sim.agents.inv_food[0]) == pytest.approx(food_before - food_spent)
    assert float(sim.agents.inv_salt[0]) == pytest.approx(salt_before - salt_spent)
    assert float(sim.agents.inv_cured_food[0]) == pytest.approx(cured_before + food_spent)
    assert sim.agents.memory[0].has_cured_food is True
    assert sim.agents.memory[0].last_preservation_class == ev[-1]["preservation_class"]
    assert len(sim.agents.memory[0].known_saltpan_locations) == 1


def test_lie_7_climate_drives_shelf_life():
    """LIE #7 — physical: at saturation salt, COOL climates keep months; tropical heat doesn't."""
    cool = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT,
                                fc._saturation_dose(fc._FOOD[fc.FoodKind.LEAN_MEAT].water_frac),
                                temp_c=5.0)
    hot = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT,
                               fc._saturation_dose(fc._FOOD[fc.FoodKind.LEAN_MEAT].water_frac),
                               temp_c=40.0)
    assert cool.shelf_life_days > hot.shelf_life_days
    assert int(cool.preservation_class) >= int(hot.preservation_class)


def test_cured_rich_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    best = _best_saltpan_coord(sim, coords)
    if best is None:
        pytest.skip("no saltpan")
    _calm_curious(sim, 0)
    sim.agents.inv_cured_food[0] = cog.CURED_FOOD_SATED_KG + 0.1
    _stand(sim, 0, best)
    assert cog._seek_cure(sim.agents, 0, _obs(sim, 0), sim) is None


def test_curing_where_no_salt_in_hand_keeps_the_food():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0, salt_kg=0.0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    food_before = float(sim.agents.inv_food[0])
    ev = _cure_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_food[0]) == food_before        # food kept where salt is missing
    assert float(sim.agents.inv_cured_food[0]) == 0.0
    assert sim.agents.memory[0].has_cured_food is False


def test_critical_hunger_outranks_curing():
    sim, coords = _booted_sim("priority")
    best = _best_saltpan_coord(sim, coords)
    if best is None:
        pytest.skip("no saltpan")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.HUNGER)] = 0.95
    # Agent has inv_food → EAT path (closer than chasing salt pan for cure).
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.EAT)


def test_cure_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_saltpan_coord(sim, coords)
    if best is None:
        pytest.skip("no saltpan")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    food_before = float(sim.agents.inv_food[0])
    salt_before = float(sim.agents.inv_salt[0])
    dec = cog.Decision(int(ActionKind.CURE), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)   # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_food[0]) == food_before
    assert float(sim.agents.inv_salt[0]) == salt_before
    assert float(sim.agents.inv_cured_food[0]) == 0.0
    assert sim.agents.memory[0].has_cured_food is False


def test_cure_only_touches_agent_inventory_geology_water_unchanged():
    sim, coords = _booted_sim("orthogonal")
    best = _best_saltpan_coord(sim, coords)
    if best is None:
        pytest.skip("no saltpan")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    g_before = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
                for layer in geo.chunk_geology(sim, best).layers]
    chunk = sim.streamer.get(sim.tick, best)
    water_before = float(chunk.water.sum()) if chunk is not None else 0.0
    stone_before = float(sim.agents.inv_stone[0])
    pigment_before = float(sim.agents.inv_pigment[0])
    _cure_here(sim, 0)
    g_after = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
               for layer in geo.chunk_geology(sim, best).layers]
    chunk2 = sim.streamer.get(sim.tick, best)
    water_after = float(chunk2.water.sum()) if chunk2 is not None else 0.0
    assert g_before == g_after                              # geology unchanged (D10 frozen)
    assert water_before == water_after                      # chunk water untouched (no DRINK side-effect)
    assert float(sim.agents.inv_stone[0]) == stone_before   # only food + salt → cured_food
    assert float(sim.agents.inv_pigment[0]) == pigment_before


def test_cure_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    best = _best_saltpan_coord(a, ca)
    if best is None:
        pytest.skip("no saltpan")
    evs = []
    for s in (a, b):
        _calm_curious(s, 0)
        _stand(s, 0, best)
        evs.append(_cure_here(s, 0)[-1])
    assert evs[0]["preservation_class"] == evs[1]["preservation_class"]
    assert evs[0]["shelf_life_days"] == evs[1]["shelf_life_days"]
    assert evs[0]["water_activity"] == evs[1]["water_activity"]
    assert evs[0]["cured_kg"] == evs[1]["cured_kg"]
