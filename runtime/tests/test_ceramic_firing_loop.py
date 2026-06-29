"""Invariants — the agent loop FIRES clay into pottery (D12 wire, 2026-06-29, consumes C9).

Context (AUDIT-DELTA-2026-06-23, risk **D12 / R0**): the C1→C20 arc was a library with no player.
Wires #1–#8 (DRINK/C3, KNAP/C2, GATHER/C14, GRIND/C18, MARK/C20, IGNITE/C7, TEMPER/C8, DIG/C5) each
consumed ONE capability. This is the 9th — and the FIRST whose inputs are **two prior wires'
products**: it FIRES carried clay (``inv_clay``, from DIG/C5) in a fire the agent knows how to make
(``has_made_fire``, from IGNITE/C7) into irreversible ceramic. The founding neolithic transformation,
the arc closing on itself: clay→fire→pot.

Emergent pottery firing:
- ``cognition._seek_kiln`` lets a curious agent that KNOWS FIRE and CARRIES clay, seeing a firing site
  (``ceramic_firing.best_firing_site_near``, require_sound), walk there and FIRE_CLAY instead of
  wandering. Tried after ``_seek_clay`` (you must have dug clay first). Utility-based, nothing scripted.
- ``cognition.apply_decision``'s new ``ActionKind.FIRE_CLAY`` branch spends ``inv_clay`` and, if the
  firing is SOUND (``ceramic_firing.prospect_firing``), yields ``inv_ceramic`` ∝ ``ware_quality``. An
  open fire never reaches kiln heat: the humble earthenware shale fires sound while the pretty kaolin
  stays UNDER-FIRED — clay spent, no vessel (the refractory inversion, lie #14). Learned by acting.

What this file proves:
1. The loop is gated on C9 (no cue cache → inert).
2. Fire dependency (C7): a never-made-fire agent does NOT fire pottery, even with clay + a site.
3. Clay dependency (C5): a fire-knowing agent with NO clay in hand does NOT fire — the milestone.
4. A ready agent (fire + clay) on the best site chooses FIRE_CLAY; off-site WALK_TOs toward it.
5. FIRE_CLAY spends clay and yields sound ceramic, records the skill + the site — the pot is LIVED.
6. The refractory inversion lie #14: firing an under-fired site spends the clay for NO vessel.
7. « le monde ne ment jamais » — firing where no clay+fire is underfoot yields nothing (clay kept).
8. Survival outranks firing.
9. Self-limiting: a pottery-rich agent (inv_ceramic ≥ sated) stops seeking to fire.
10. Back-compat (sim=None inert), orthogonality (only inv_clay↓ / inv_ceramic↑), non-mutation (no mine_at).
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
import engine.ceramic_firing as cf                                 # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_FIRING = 0xBEEF   # clay + makeable fire co-located; plenty of SOUND firings (humble shale) + some
                       # under-fired plastic kaolin (the refractory inversion).
GRID = 12


def _booted_sim(name: str, seed: int = SEED_FIRING, *, with_c9: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c9:
        cf.install_ceramic_firing(sim)   # also installs the composed C5 clay + C7 fire
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_firingsite_coord(sim, coords, *, sound=True):
    """The coord ``best_firing_site_near(require_sound)`` would globally prefer — max
    (ware_quality, confidence) among (sound) fireable sites."""
    best = None
    for coord in coords:
        cue = cf.firing_cue_for_chunk(sim, coord)
        if cue is None or not cue.fireable:
            continue
        if sound and not cue.is_sound:
            continue
        key = (cue.ware_quality, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _nonsound_firingsite_coord(sim, coords):
    """A fireable site whose firing is NOT sound (under-fired — the refractory inversion)."""
    for coord in coords:
        cue = cf.firing_cue_for_chunk(sim, coord)
        if cue is not None and cue.fireable and not cue.is_sound:
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
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone",
                "inv_metal", "inv_tools", "inv_pigment", "inv_clay", "inv_ceramic"):
        getattr(sim.agents, inv)[row] = 0.0
    sim.agents.inv_clay[row] = float(clay_kg)
    mem = sim.agents.memory[row]
    mem.known_kiln_locations.clear()
    mem.has_fired_pottery = False
    mem.last_ware_quality = None
    mem.has_made_fire = bool(knows_fire)
    mem.last_fire_method = "PERCUSSION" if knows_fire else None
    if ready:
        # Drive the full decide() to FIRE_CLAY: sate the clay store (no DIG) and stay warm (no
        # IGNITE), so the earlier _seek_clay / _seek_firesite yield and firing is the next act.
        sim.agents.inv_clay[row] = cog.CLAY_SATED_KG     # _seek_clay → None (sated)
        sim.agents.thermal[row] = 0.05                   # warm + knows fire → _seek_firesite None


def _obs(sim, row, *, nearest=None, drives=None, near_agents=None):
    a = sim.agents
    d = drives if drives is not None else np.array(
        [float(a.hunger[row]), float(a.thirst[row]), float(a.sleep[row]),
         float(a.fatigue[row]), float(a.thermal[row]), float(a.pain[row]),
         float(a.stress[row]), float(a.loneliness[row])], dtype=np.float32)
    return Observation(
        row=int(row),
        pos=(float(a.pos[row, 0]), float(a.pos[row, 1]), float(a.pos[row, 2])),
        drives=d, vitality=float(a.vitality[row]), nearest=(nearest or {}),
        near_agents=(near_agents or []), dominant_drive=cog._dominant_drive(d),
        tick=0, reproduction_readiness=0.0)


def _far_unstreamed(grid: int = GRID):
    return ((grid + 50 + 0.5) * CHUNK_SIDE_M, (grid + 50 + 0.5) * CHUNK_SIDE_M)


def _fire_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.FIRE_CLAY), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


# 1. Gate
def test_seek_kiln_inert_without_c9():
    sim, coords = _booted_sim("gate", with_c9=False)
    _calm_curious(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_firing_cue_cache", None) is None
    assert cog._seek_kiln(sim.agents, 0, _obs(sim, 0), sim) is None


# 2. Fire dependency (C7)
def test_agent_without_fire_does_not_fire_pottery():
    sim, coords = _booted_sim("needs_fire")
    best = _best_firingsite_coord(sim, coords)
    if best is None:
        pytest.skip("no sound firing site")
    _calm_curious(sim, 0, knows_fire=False, ready=True)
    sim.agents.memory[0].has_made_fire = False
    _stand(sim, 0, best)
    assert cog._seek_kiln(sim.agents, 0, _obs(sim, 0), sim) is None
    ev = _fire_here(sim, 0)
    assert ev == []                                       # forced act also yields nothing
    assert float(sim.agents.inv_ceramic[0]) == 0.0


# 3. Clay dependency (C5) — the milestone: no dug clay in hand ⇒ no pot
def test_agent_without_clay_does_not_fire_pottery():
    sim, coords = _booted_sim("needs_clay")
    best = _best_firingsite_coord(sim, coords)
    if best is None:
        pytest.skip("no sound firing site")
    _calm_curious(sim, 0, clay_kg=0.0, ready=True)
    sim.agents.inv_clay[0] = 0.0                          # knows fire, warm, but carries no clay
    _stand(sim, 0, best)
    assert cog._seek_kiln(sim.agents, 0, _obs(sim, 0), sim) is None
    ev = _fire_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_ceramic[0]) == 0.0


# 4. Choose / walk
def test_ready_agent_on_firingsite_decides_to_fire():
    sim, coords = _booted_sim("fire")
    best = _best_firingsite_coord(sim, coords)
    if best is None:
        pytest.skip("no sound firing site")
    _calm_curious(sim, 0, ready=True)
    _stand(sim, 0, best)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.FIRE_CLAY)


def test_ready_agent_walks_toward_perceived_firingsite():
    sim, coords = _booted_sim("walk")
    best = _best_firingsite_coord(sim, coords)
    if best is None:
        pytest.skip("no sound firing site")
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0, ready=True)
    sim.agents.pos[0, 0] = cx + 10.0
    sim.agents.pos[0, 1] = cy
    pick = cf.best_firing_site_near(sim, 0, perception_radius_m=cog.KILN_PERCEPT_M, require_sound=True)
    assert pick is not None
    tx = (pick.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (pick.coord[1] + 0.5) * CHUNK_SIDE_M
    if ((tx - (cx + 10.0)) ** 2 + (ty - cy) ** 2) ** 0.5 < cog.INTERACT_RADIUS_M:
        pytest.skip("best firing site is underfoot — no WALK_TO to assert")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)
    assert abs(dec.target_x - tx) < 1e-3
    assert abs(dec.target_y - ty) < 1e-3


# 5. Act — spends clay, yields sound ceramic, records + remembers
def test_firing_spends_clay_yields_pottery_and_remembers():
    sim, coords = _booted_sim("act")
    best = _best_firingsite_coord(sim, coords)
    if best is None:
        pytest.skip("no sound firing site")
    cue = cf.firing_cue_for_chunk(sim, best)
    _calm_curious(sim, 0, clay_kg=2.0)
    _stand(sim, 0, best)
    clay_before = float(sim.agents.inv_clay[0])
    ev = _fire_here(sim, 0)
    assert ev and ev[-1]["kind"] == "fire_clay"
    assert ev[-1]["is_sound"] is True
    assert float(sim.agents.inv_clay[0]) == pytest.approx(clay_before - cog.FIRE_CLAY_COST_KG)
    assert float(sim.agents.inv_ceramic[0]) > 0.0
    assert ev[-1]["ware_quality"] == round(float(cue.ware_quality), 4)
    assert sim.agents.memory[0].has_fired_pottery is True
    assert len(sim.agents.memory[0].known_kiln_locations) == 1


# 6. The refractory inversion lie #14 — under-fired site spends clay for NO vessel
def test_underfired_site_spends_clay_for_no_pottery():
    sim, coords = _booted_sim("underfired")
    bad = _nonsound_firingsite_coord(sim, coords)
    if bad is None:
        pytest.skip("seed produced no under-fired site")
    _calm_curious(sim, 0, clay_kg=2.0)
    _stand(sim, 0, bad)
    clay_before = float(sim.agents.inv_clay[0])
    ev = _fire_here(sim, 0)
    assert ev and ev[-1]["is_sound"] is False
    assert float(sim.agents.inv_clay[0]) == pytest.approx(clay_before - cog.FIRE_CLAY_COST_KG)  # clay spent
    assert float(sim.agents.inv_ceramic[0]) == 0.0          # …but no usable vessel
    assert sim.agents.memory[0].has_fired_pottery is False


# 7. World never lies — no clay+fire underfoot yields nothing (clay kept)
def test_firing_where_nothing_fireable_yields_nothing():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0, clay_kg=2.0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert cf.prospect_firing(sim, fx, fy) is None
    clay_before = float(sim.agents.inv_clay[0])
    ev = _fire_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_clay[0]) == clay_before     # clay NOT spent where nothing fires
    assert float(sim.agents.inv_ceramic[0]) == 0.0


# 8. Survival outranks firing
def test_critical_thirst_outranks_firing():
    sim, coords = _booted_sim("priority")
    best = _best_firingsite_coord(sim, coords)
    if best is None:
        pytest.skip("no firing site")
    _calm_curious(sim, 0, ready=True)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)


# 9. Self-limiting — pottery-rich agent stops seeking
def test_pottery_rich_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    best = _best_firingsite_coord(sim, coords)
    if best is None:
        pytest.skip("no firing site")
    _calm_curious(sim, 0, ready=True)
    sim.agents.inv_ceramic[0] = cog.CERAMIC_SATED_KG + 0.1
    _stand(sim, 0, best)
    assert cog._seek_kiln(sim.agents, 0, _obs(sim, 0), sim) is None


# 10. Back-compat + orthogonality + non-mutation
def test_fire_clay_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_firingsite_coord(sim, coords)
    if best is None:
        pytest.skip("no firing site")
    _calm_curious(sim, 0, clay_kg=2.0)
    px, py = _stand(sim, 0, best)
    clay_before = float(sim.agents.inv_clay[0])
    dec = cog.Decision(int(ActionKind.FIRE_CLAY), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_clay[0]) == clay_before
    assert float(sim.agents.inv_ceramic[0]) == 0.0


def test_fire_clay_touches_only_clay_and_ceramic_and_is_non_mutating():
    sim, coords = _booted_sim("orthogonal")
    best = _best_firingsite_coord(sim, coords)
    if best is None:
        pytest.skip("no firing site")
    _calm_curious(sim, 0, clay_kg=2.0)
    _stand(sim, 0, best)
    g_before = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
                for layer in geo.chunk_geology(sim, best).layers]
    _fire_here(sim, 0)
    g_after = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
               for layer in geo.chunk_geology(sim, best).layers]
    assert g_before == g_after                              # geology unchanged
    assert float(sim.agents.inv_ceramic[0]) > 0.0          # pottery made…
    assert float(sim.agents.inv_stone[0]) == 0.0           # …only clay→ceramic moved
    assert float(sim.agents.inv_tools[0]) == 0.0
    assert float(sim.agents.inv_pigment[0]) == 0.0


def test_fire_clay_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    best = _best_firingsite_coord(a, ca)
    if best is None:
        pytest.skip("no firing site")
    evs = []
    for s in (a, b):
        _calm_curious(s, 0, clay_kg=2.0)
        _stand(s, 0, best)
        evs.append(_fire_here(s, 0)[-1])
    assert evs[0]["ware_quality"] == evs[1]["ware_quality"]
    assert evs[0]["is_sound"] == evs[1]["is_sound"]
    assert evs[0]["ceramic_kg"] == evs[1]["ceramic_kg"]
    assert abs(float(a.agents.inv_ceramic[0]) - float(b.agents.inv_ceramic[0])) < 1e-12
