"""Invariants — the agent loop BURNS limestone into quicklime (D12 wire, 2026-06-29, consumes C10).

The 11th wire and the SECOND two-ingredient transformation — the exact mirror of C9 FIRE_CLAY
(clay→pot :: limestone→lime). An agent that KNOWS FIRE (``has_made_fire``, from IGNITE/C7) AND
CARRIES limestone (``inv_limestone``, from QUARRY/C6) CALCINEs it at a burning site into caustic
quicklime (``inv_lime``) — the oldest chemical industry. Appended to ``_ARC_SEEKS`` as one line.

What this file proves:
1. Gated on C10 (no cue cache → inert).
2. Fire dependency (C7): a never-made-fire agent does not burn lime.
3. Limestone dependency (C6): a fire-knowing agent with no limestone does not burn lime.
4. A ready agent (fire + limestone) on the best well-burnt site chooses CALCINE; off-site WALK_TOs.
5. CALCINE spends limestone and yields sound quicklime, records the skill + the site.
6. The refractory inversion lie #16: an under-burnt site spends limestone for NO lime; and an open
   fire is NEVER mortar-ready (``mortar_ready`` False — hard-burn needs a kiln).
7. « le monde ne ment jamais » — burning where no carbonate+fire is underfoot keeps the limestone.
8. Survival outranks burning.
9. Self-limiting: a lime-rich agent (inv_lime ≥ sated) stops seeking.
10. Back-compat (sim=None inert), orthogonality (only limestone↓/lime↑), non-mutation (no mine_at).
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
import engine.lime_burning as lb                                   # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_LIME = 0xBEEF     # limestone + makeable fire co-located; well-burnt + under-burnt sites both present
GRID = 12


def _booted_sim(name: str, seed: int = SEED_LIME, *, with_c10: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c10:
        lb.install_lime_burning(sim)   # also installs the composed C6 limestone + C7 fire
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_burnsite(sim, coords):
    best = None
    for coord in coords:
        cue = lb.lime_burning_cue_for_chunk(sim, coord)
        if cue is None or not cue.burnable or not cue.well_burnt:
            continue
        key = (cue.lime_yield, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _underburnt_site(sim, coords):
    for coord in coords:
        cue = lb.lime_burning_cue_for_chunk(sim, coord)
        if cue is not None and cue.burnable and not cue.well_burnt:
            return coord
    return None


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _calm_curious(sim, row, *, knows_fire=True, limestone_kg=2.0, ready=False):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal",
                "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal", "inv_tools",
                "inv_pigment", "inv_clay", "inv_ceramic", "inv_limestone", "inv_lime"):
        getattr(sim.agents, inv)[row] = 0.0
    sim.agents.inv_limestone[row] = float(limestone_kg)
    mem = sim.agents.memory[row]
    mem.known_limekiln_locations.clear()
    mem.has_burnt_lime = False
    mem.last_lime_yield = None
    mem.has_made_fire = bool(knows_fire)
    mem.last_fire_method = "PERCUSSION" if knows_fire else None
    if ready:
        # Drive the full decide() to CALCINE: sate the limestone store (no QUARRY) + warm (no IGNITE).
        sim.agents.inv_limestone[row] = cog.LIMESTONE_SATED_KG
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


def _calcine_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.CALCINE), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


def test_seek_limekiln_inert_without_c10():
    sim, coords = _booted_sim("gate", with_c10=False)
    _calm_curious(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_lime_burn_cue_cache", None) is None
    assert cog._seek_limekiln(sim.agents, 0, _obs(sim, 0), sim) is None


def test_agent_without_fire_does_not_burn_lime():
    sim, coords = _booted_sim("needs_fire")
    best = _best_burnsite(sim, coords)
    if best is None:
        pytest.skip("no well-burnt site")
    _calm_curious(sim, 0, knows_fire=False, ready=True)
    sim.agents.memory[0].has_made_fire = False
    _stand(sim, 0, best)
    assert cog._seek_limekiln(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _calcine_here(sim, 0) == []
    assert float(sim.agents.inv_lime[0]) == 0.0


def test_agent_without_limestone_does_not_burn_lime():
    sim, coords = _booted_sim("needs_stone")
    best = _best_burnsite(sim, coords)
    if best is None:
        pytest.skip("no well-burnt site")
    _calm_curious(sim, 0, limestone_kg=0.0, ready=True)
    sim.agents.inv_limestone[0] = 0.0
    _stand(sim, 0, best)
    assert cog._seek_limekiln(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _calcine_here(sim, 0) == []
    assert float(sim.agents.inv_lime[0]) == 0.0


def test_ready_agent_on_burnsite_decides_to_calcine():
    sim, coords = _booted_sim("calcine")
    best = _best_burnsite(sim, coords)
    if best is None:
        pytest.skip("no well-burnt site")
    _calm_curious(sim, 0, ready=True)
    _stand(sim, 0, best)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.CALCINE)


def test_ready_agent_walks_toward_perceived_burnsite():
    sim, coords = _booted_sim("walk")
    best = _best_burnsite(sim, coords)
    if best is None:
        pytest.skip("no well-burnt site")
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0, ready=True)
    sim.agents.pos[0, 0] = cx + 10.0
    sim.agents.pos[0, 1] = cy
    pick = lb.best_burning_site_near(sim, 0, perception_radius_m=cog.LIMEKILN_PERCEPT_M, require_well_burnt=True)
    assert pick is not None
    tx = (pick.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (pick.coord[1] + 0.5) * CHUNK_SIDE_M
    if ((tx - (cx + 10.0)) ** 2 + (ty - cy) ** 2) ** 0.5 < cog.INTERACT_RADIUS_M:
        pytest.skip("best burn site is underfoot — no WALK_TO to assert")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)
    assert abs(dec.target_x - tx) < 1e-3
    assert abs(dec.target_y - ty) < 1e-3


def test_burning_spends_limestone_yields_lime_and_remembers():
    sim, coords = _booted_sim("act")
    best = _best_burnsite(sim, coords)
    if best is None:
        pytest.skip("no well-burnt site")
    cue = lb.lime_burning_cue_for_chunk(sim, best)
    _calm_curious(sim, 0, limestone_kg=2.0)
    _stand(sim, 0, best)
    stone_before = float(sim.agents.inv_limestone[0])
    ev = _calcine_here(sim, 0)
    assert ev and ev[-1]["kind"] == "calcine"
    assert ev[-1]["well_burnt"] is True
    assert float(sim.agents.inv_limestone[0]) == pytest.approx(stone_before - cog.CALCINE_STONE_COST_KG)
    assert float(sim.agents.inv_lime[0]) > 0.0
    assert ev[-1]["lime_yield"] == round(float(cue.lime_yield), 4)
    assert sim.agents.memory[0].has_burnt_lime is True
    assert len(sim.agents.memory[0].known_limekiln_locations) == 1


def test_underburnt_site_spends_limestone_for_no_lime():
    sim, coords = _booted_sim("underburnt")
    bad = _underburnt_site(sim, coords)
    if bad is None:
        pytest.skip("seed produced no under-burnt site")
    _calm_curious(sim, 0, limestone_kg=2.0)
    _stand(sim, 0, bad)
    stone_before = float(sim.agents.inv_limestone[0])
    ev = _calcine_here(sim, 0)
    assert ev and ev[-1]["well_burnt"] is False
    assert ev[-1]["mortar_ready"] is False                       # an open fire never hard-burns
    assert float(sim.agents.inv_limestone[0]) == pytest.approx(stone_before - cog.CALCINE_STONE_COST_KG)
    assert float(sim.agents.inv_lime[0]) == 0.0
    assert sim.agents.memory[0].has_burnt_lime is False


def test_burning_where_nothing_burnable_keeps_limestone():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0, limestone_kg=2.0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert lb.prospect_lime_burning(sim, fx, fy) is None
    stone_before = float(sim.agents.inv_limestone[0])
    ev = _calcine_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_limestone[0]) == stone_before    # limestone kept where nothing burns
    assert float(sim.agents.inv_lime[0]) == 0.0


def test_critical_thirst_outranks_burning():
    sim, coords = _booted_sim("priority")
    best = _best_burnsite(sim, coords)
    if best is None:
        pytest.skip("no well-burnt site")
    _calm_curious(sim, 0, ready=True)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)


def test_lime_rich_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    best = _best_burnsite(sim, coords)
    if best is None:
        pytest.skip("no well-burnt site")
    _calm_curious(sim, 0, ready=True)
    sim.agents.inv_lime[0] = cog.LIME_SATED_KG + 0.1
    _stand(sim, 0, best)
    assert cog._seek_limekiln(sim.agents, 0, _obs(sim, 0), sim) is None


def test_calcine_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_burnsite(sim, coords)
    if best is None:
        pytest.skip("no well-burnt site")
    _calm_curious(sim, 0, limestone_kg=2.0)
    px, py = _stand(sim, 0, best)
    stone_before = float(sim.agents.inv_limestone[0])
    dec = cog.Decision(int(ActionKind.CALCINE), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_limestone[0]) == stone_before
    assert float(sim.agents.inv_lime[0]) == 0.0


def test_calcine_touches_only_limestone_and_lime_and_is_non_mutating():
    sim, coords = _booted_sim("orthogonal")
    best = _best_burnsite(sim, coords)
    if best is None:
        pytest.skip("no well-burnt site")
    _calm_curious(sim, 0, limestone_kg=2.0)
    _stand(sim, 0, best)
    g_before = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
                for layer in geo.chunk_geology(sim, best).layers]
    _calcine_here(sim, 0)
    g_after = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
               for layer in geo.chunk_geology(sim, best).layers]
    assert g_before == g_after                              # geology unchanged
    assert float(sim.agents.inv_lime[0]) > 0.0             # quicklime made…
    assert float(sim.agents.inv_stone[0]) == 0.0           # …only limestone→lime moved
    assert float(sim.agents.inv_clay[0]) == 0.0
    assert float(sim.agents.inv_ceramic[0]) == 0.0


def test_calcine_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    best = _best_burnsite(a, ca)
    if best is None:
        pytest.skip("no well-burnt site")
    evs = []
    for s in (a, b):
        _calm_curious(s, 0, limestone_kg=2.0)
        _stand(s, 0, best)
        evs.append(_calcine_here(s, 0)[-1])
    assert evs[0]["lime_yield"] == evs[1]["lime_yield"]
    assert evs[0]["well_burnt"] == evs[1]["well_burnt"]
    assert evs[0]["lime_kg"] == evs[1]["lime_kg"]
    assert abs(float(a.agents.inv_lime[0]) - float(b.agents.inv_lime[0])) < 1e-12
