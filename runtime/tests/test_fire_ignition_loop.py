"""Invariants — the agent loop CONSUMES C7 fire_ignition (D12 wire, 2026-06-28).

Context (AUDIT-DELTA-2026-06-23, risk **D12 / R0**): the C1→C20 capability arc was a
library with no player. DRINK/C3, KNAP/C2, GATHER/C14, GRIND/C18 and MARK/C20 took the first
five bites. This is the 6th bite and it wires **the VOÛTE** — fire. C7 ``fire_ignition`` made
fire-making *perceivable* (a brown spark-stone, a hard striker, dry grass); it is the keystone
that turns the inert C1→C6 matters (copper, fuel, clay, lime) into *actionable* ones (smelt,
burn, fire, calcine). But until now no agent ever struck one.

Emergent fire-making:
- ``cognition._seek_firesite`` lets a survival-satisfied, curious agent that is mildly chilly
  (or has never made fire) and SEES a site where a spark truly takes
  (``fire_ignition.best_firesite_near``) walk there and IGNITE instead of wandering —
  utility-based action selection, nothing scripted. Tried *after* ``_seek_toolstone`` (secure
  stone first) and *before* the symbolic ``_seek_ochre`` / ``_seek_canvas`` (warmth before art).
- ``cognition.apply_decision``'s new ``ActionKind.IGNITE`` branch strikes the fire underfoot,
  EASES the agent's own thermal drive (the honest physical effect of warmth), and records the
  world's truth (``fire_ignition.prospect_ignition``): PERCUSSION where the geology carries a
  pyrophoric firestone + a hard striker over dry tinder, FRICTION where bone-dry tinder lets a
  hand-drill ember take. A lush DAMP meadow looks like tinder but a spark won't catch (the fire
  lie — ``prospect_ignition`` returns None). The agent learns the firestone→flame link by acting.

What this file proves:
1. The loop is genuinely gated on C7 (no cue cache → inert; no scripted fallback).
2. A curious, mildly-chilly agent on the best perceived firesite chooses IGNITE; off-site it
   WALK_TOs toward it.
3. IGNITE warms the agent (thermal eased), records the skill (``has_made_fire`` /
   ``last_fire_method``) and remembers the site — the keystone is LIVED, not merely provable.
4. « le monde ne ment jamais » — striking where no firestone is underfoot yields nothing.
5. Self-limiting & honest: a warm agent that already knows fire does NOT re-strike; but a
   never-made-fire agent still seeks one (first discovery by curiosity).
6. Survival always outranks fire-making (a critically thirsty agent drinks, never ignites).
7. IGNITE is back-compat inert with the old ``sim=None`` signature, fills NO portable
   inventory, and is NON-MUTATING (no ``geo.mine_at``; the mutation frontier D10 stays frozen).

Determinism preserved (pure cue derivation + memoised cues; no new RNG).
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
import engine.fire_ignition as fi                                  # noqa: E402

# Several arc capabilities globally REASSIGN ``cog.decide`` / ``cog.apply_decision`` with
# monkey-patch wrappers and never restore them. The D12 wire under test lives in the
# ORIGINAL functions; we capture them at import (before any installer runs) and exercise
# those directly — the correct unit scope, immune to cross-test pollution.
_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_FIRE = 0xBEEF    # a temperate grassland continent → dry tinder + pyrite firestones
GRID = 12


# ---------------------------------------------------------------------------
# Fixtures — a real Genesis world whose firesites C7 exposes. No injection: the world
# really carries pyrite + strikers + dry grass; we just point the curious agent at one.
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = SEED_FIRE, *, with_c7: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c7:
        fi.install_fire_ignition(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_firesite_coord(sim, coords):
    """The coord ``best_firesite_near`` would globally prefer — max (method, confidence) among
    fire-makeable sites. Standing the agent here makes the underfoot site the in-window argmax,
    so the loop deterministically IGNITEs."""
    best = None
    for coord in coords:
        cue = fi.ignition_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        key = (int(cue.method), cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _calm_curious(sim, row, thermal: float = 0.20):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal",
                "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.thermal[row] = float(thermal)
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone",
                "inv_metal", "inv_tools", "inv_pigment"):
        getattr(sim.agents, inv)[row] = 0.0
    mem = sim.agents.memory[row]
    mem.known_firesite_locations.clear()
    mem.has_made_fire = False
    mem.last_fire_method = None


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


def _ignite_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.IGNITE), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


# ---------------------------------------------------------------------------
# 1. Gate — without C7 installed there is no firesite perception at all
# ---------------------------------------------------------------------------

def test_seek_firesite_inert_without_c7():
    sim, coords = _booted_sim("gate", with_c7=False)
    _calm_curious(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_ignition_cue_cache", None) is None
    assert cog._seek_firesite(sim.agents, 0, _obs(sim, 0), sim) is None


# ---------------------------------------------------------------------------
# 2. Choose — a curious, chilly agent on the best perceived firesite decides to IGNITE
# ---------------------------------------------------------------------------

def test_curious_agent_on_firesite_decides_to_ignite():
    sim, coords = _booted_sim("ignite")
    best = _best_firesite_coord(sim, coords)
    if best is None:
        pytest.skip("seed produced no firesite in the streamed grid")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.IGNITE)


def test_curious_agent_walks_toward_perceived_firesite():
    """A curious agent that perceives a firesite but is not on it walks toward it — WALK_TO
    toward the perceived site centre, not random EXPLORE."""
    sim, coords = _booted_sim("walk")
    best = _best_firesite_coord(sim, coords)
    if best is None:
        pytest.skip("no firesite for the walk fixture")
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0)
    sim.agents.pos[0, 0] = cx + 10.0          # off-centre but in-chunk (< CHUNK_SIDE_M/2)
    sim.agents.pos[0, 1] = cy
    pick = fi.best_firesite_near(sim, 0, perception_radius_m=cog.FIRESITE_PERCEPT_M)
    assert pick is not None
    tx = (pick.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (pick.coord[1] + 0.5) * CHUNK_SIDE_M
    if ((tx - (cx + 10.0)) ** 2 + (ty - cy) ** 2) ** 0.5 < cog.INTERACT_RADIUS_M:
        pytest.skip("best firesite is underfoot — no WALK_TO to assert")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)
    assert abs(dec.target_x - tx) < 1e-3
    assert abs(dec.target_y - ty) < 1e-3


# ---------------------------------------------------------------------------
# 3. Act — IGNITE warms the agent, records the skill, remembers the site
# ---------------------------------------------------------------------------

def test_igniting_warms_records_and_remembers():
    sim, coords = _booted_sim("warm")
    best = _best_firesite_coord(sim, coords)
    if best is None:
        pytest.skip("no firesite")
    cue = fi.ignition_cue_for_chunk(sim, best)
    _calm_curious(sim, 0, thermal=0.20)
    _stand(sim, 0, best)
    thermal_before = float(sim.agents.thermal[0])
    ev = _ignite_here(sim, 0)
    assert ev and ev[-1]["kind"] == "ignite"
    assert ev[-1]["method"] == cue.method.name
    assert float(sim.agents.thermal[0]) < thermal_before          # the fire warmed the agent
    assert sim.agents.memory[0].has_made_fire is True             # keystone skill learned
    assert sim.agents.memory[0].last_fire_method == cue.method.name
    assert len(sim.agents.memory[0].known_firesite_locations) == 1


# ---------------------------------------------------------------------------
# 4. « Le monde ne ment jamais » — no firestone underfoot yields nothing
# ---------------------------------------------------------------------------

def test_igniting_where_no_firestone_yields_nothing():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert fi.prospect_ignition(sim, fx, fy) is None
    thermal_before = float(sim.agents.thermal[0])
    _ORIG_APPLY(sim.agents, 0, cog.Decision(int(ActionKind.IGNITE), fx, fy, 0.5),
                sim.streamer, sim.tick, sim=sim)
    assert float(sim.agents.thermal[0]) == thermal_before         # no fire → no warmth
    assert sim.agents.memory[0].has_made_fire is False
    assert len(sim.agents.memory[0].known_firesite_locations) == 0


# ---------------------------------------------------------------------------
# 5. Self-limiting & honest — warm + already-knows ⇒ no re-strike; never-made ⇒ still seeks
# ---------------------------------------------------------------------------

def test_warm_agent_that_knows_fire_does_not_reseek():
    sim, coords = _booted_sim("sated")
    best = _best_firesite_coord(sim, coords)
    if best is None:
        pytest.skip("no firesite")
    _calm_curious(sim, 0, thermal=0.05)        # warm (below FIRE_SEEK_THERMAL_MIN)
    sim.agents.memory[0].has_made_fire = True   # already knows fire
    _stand(sim, 0, best)
    assert cog._seek_firesite(sim.agents, 0, _obs(sim, 0), sim) is None


def test_naive_agent_seeks_first_fire_even_when_warm():
    sim, coords = _booted_sim("discovery")
    best = _best_firesite_coord(sim, coords)
    if best is None:
        pytest.skip("no firesite")
    _calm_curious(sim, 0, thermal=0.05)        # warm, but…
    sim.agents.memory[0].has_made_fire = False  # …has never made fire → curiosity drives it
    _stand(sim, 0, best)
    dec = cog._seek_firesite(sim.agents, 0, _obs(sim, 0), sim)
    assert dec is not None and dec.action == int(ActionKind.IGNITE)


# ---------------------------------------------------------------------------
# 6. Survival always outranks fire-making
# ---------------------------------------------------------------------------

def test_critical_thirst_outranks_igniting():
    sim, coords = _booted_sim("priority")
    best = _best_firesite_coord(sim, coords)
    if best is None:
        pytest.skip("no firesite")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95                    # critical
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)              # never IGNITE


# ---------------------------------------------------------------------------
# 7. Back-compat + non-mutation — old signature inert; IGNITE fills no inventory, no mine_at
# ---------------------------------------------------------------------------

def test_ignite_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_firesite_coord(sim, coords)
    if best is None:
        pytest.skip("no firesite")
    _calm_curious(sim, 0, thermal=0.40)
    px, py = _stand(sim, 0, best)
    thermal_before = float(sim.agents.thermal[0])
    dec = cog.Decision(int(ActionKind.IGNITE), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.thermal[0]) == thermal_before   # nothing changed without sim
    assert sim.agents.memory[0].has_made_fire is False


def test_ignite_fills_no_inventory_and_is_non_mutating():
    sim, coords = _booted_sim("orthogonal")
    best = _best_firesite_coord(sim, coords)
    if best is None:
        pytest.skip("no firesite")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    # geology snapshot before — IGNITE must not mutate it (D10 frozen)
    g_before = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
                for layer in geo.chunk_geology(sim, best).layers]
    _ignite_here(sim, 0)
    g_after = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
               for layer in geo.chunk_geology(sim, best).layers]
    assert g_before == g_after                              # geology unchanged
    assert float(sim.agents.inv_stone[0]) == 0.0            # IGNITE is not GATHER / KNAP
    assert float(sim.agents.inv_tools[0]) == 0.0
    assert float(sim.agents.inv_pigment[0]) == 0.0          # nor GRIND


def test_ignite_outcome_is_deterministic():
    """Same seed + same site ⇒ identical ignition outcome (pure cue + memoised, no RNG)."""
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    best = _best_firesite_coord(a, ca)
    if best is None:
        pytest.skip("no firesite")
    evs = []
    for s in (a, b):
        _calm_curious(s, 0, thermal=0.30)
        _stand(s, 0, best)
        evs.append(_ignite_here(s, 0)[-1])
    assert evs[0]["method"] == evs[1]["method"]
    assert evs[0]["tinder_state"] == evs[1]["tinder_state"]
    assert evs[0]["confidence"] == evs[1]["confidence"]
    assert abs(float(a.agents.thermal[0]) - float(b.agents.thermal[0])) < 1e-12
