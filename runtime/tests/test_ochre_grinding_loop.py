"""Invariants — the agent loop CONSUMES C18 ochre_grinding (D12 wire, 2026-06-27).

Context (AUDIT-DELTA-2026-06-23, risk **D12 / R0**): the C1→C20 capability arc was a
library with no player. DRINK/C3 (R-J13-4), KNAP/C2 (R-J13-1) and GATHER/C14 (R-J14-1)
took the first three bites. R-J15-2 asked for a 4th capability wired through the
canonical ADR-0009 ``perceive→decide→act→remember`` loop — preferably one that begins to
move a still-immobile emergence pillar. This is it: emergent **grinding** of the rusty
iron-hat earth into **pigment** — the first agent behaviour to advance the **symbolic**
pillar (pigment = the substrate of the future mark / drawing).

Emergent ochre grinding:
- ``cognition._seek_ochre`` lets a survival-satisfied, curious agent that SEES a usable
  rusty-earth ochre site (``ochre_grinding.best_ochre_site_near``) walk there and GRIND a
  handful into pigment instead of wandering — utility-based action selection, nothing
  scripted. It is tried *after* ``_seek_toolstone`` (survival tools first, then symbol)
  and runs on its OWN inventory (``inv_pigment``), so it never competes with tool-stone.
- ``cognition.apply_decision``'s new ``ActionKind.GRIND`` branch grinds the gossan earth
  the agent stands on into ``inv_pigment`` scaled by the cue's TRUE ``pigment_quality``
  (oxide chroma × cap richness) — an OXIDE gossan (hematite → red, magnetite → black)
  gives lightfast pigment; a pyrite / lead / zinc gossan looks just as rusty but grinds
  to nothing. The agent learns the rust→colour link by acting (mensonge #9: rust ≠ red).

What this file proves:
1. The loop is genuinely gated on C18 (no cue cache → inert; no scripted fallback).
2. A curious agent on the best perceived ochre site chooses GRIND; off-site it WALK_TOs / EXPLOREs.
3. The yield is the world's truth: an oxide gossan yields pigment, a rusty sulfide yields none.
4. « le monde ne ment jamais » — grinding where no gossan is perceived yields nothing.
5. Survival always outranks grinding (a critically thirsty agent drinks, never grinds).
6. GRIND is surface only — back-compat inert with the old ``sim=None`` signature.
7. Orthogonal inventory — GRIND fills inv_pigment, never inv_stone / inv_tools.
8. Bounded — once pigment-sated the agent stops seeking and explores.

Determinism preserved (pure derivation + memoised cues; no new RNG).
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
import engine.ochre_grinding as og                                 # noqa: E402

# Several arc capabilities globally REASSIGN ``cog.decide`` / ``cog.apply_decision`` with
# monkey-patch wrappers and never restore them. The D12 wire under test lives in the
# ORIGINAL functions; we capture them at import (before any installer runs) and exercise
# those directly — the correct unit scope, immune to cross-test pollution.
_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED = 0x42          # grassland continent — iron gossans (hematite oxide + pyrite sulfide)
GRID = 12


# ---------------------------------------------------------------------------
# Fixtures — a real Genesis world whose gossans emit BOTH pigment and the rusty lie
# (verbatim seed / streaming of test-side p150). No injection: the world really has
# emergent iron-hats; we just point the agent at one.
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = SEED, *, with_c18: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c18:
        og.install_ochre_grinding(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_usable_coord(sim, coords):
    """The coord whose cue ``best_ochre_site_near`` would globally prefer — max
    (pigment_quality, confidence) among usable sites. Standing the agent here makes the
    underfoot site the in-window argmax, so the loop deterministically GRINDS."""
    best = None
    for coord in coords:
        cue = og.ochre_cue_for_chunk(sim, coord)
        if cue is None or not cue.usable:
            continue
        key = (cue.pigment_quality, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _lie_coord(sim, coords):
    """A coord whose gossan is perceivable but barren — a rusty-but-no-pigment lie
    (pyrite / lead / zinc gossan: cue exists, ``is_pigment`` False)."""
    for coord in coords:
        cue = og.ochre_cue_for_chunk(sim, coord)
        if cue is not None and not cue.is_pigment:
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
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone",
                "inv_metal", "inv_tools", "inv_pigment"):
        getattr(sim.agents, inv)[row] = 0.0
    sim.agents.memory[row].known_ochre_locations.clear()


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


def _grind_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.GRIND), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


# ---------------------------------------------------------------------------
# 1. Gate — without C18 installed there is no ochre perception at all
# ---------------------------------------------------------------------------

def test_seek_ochre_inert_without_c18():
    sim, coords = _booted_sim("gate", with_c18=False)
    _calm_curious(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_ochre_cue_cache", None) is None
    assert cog._seek_ochre(sim.agents, 0, _obs(sim, 0), sim) is None


# ---------------------------------------------------------------------------
# 2. Choose — a curious agent on the best perceived ochre site decides to GRIND
# ---------------------------------------------------------------------------

def test_curious_agent_on_ochre_decides_to_grind():
    sim, coords = _booted_sim("grind")
    best = _best_usable_coord(sim, coords)
    if best is None:
        pytest.skip("seed produced no usable ochre site in the streamed grid")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.GRIND)


def test_curious_agent_walks_toward_perceived_ochre():
    """Agent that perceives an ochre site but is not standing on it walks toward it —
    WALK_TO toward the perceived site centre, not random EXPLORE. Stand off-centre in
    the best chunk (offset > INTERACT_RADIUS_M) so the site is in sight but not underfoot."""
    sim, coords = _booted_sim("walk")
    best = _best_usable_coord(sim, coords)
    if best is None:
        pytest.skip("no usable ochre site for the walk fixture")
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0)
    sim.agents.pos[0, 0] = cx + 10.0          # off-centre but in-chunk (< CHUNK_SIDE_M/2)
    sim.agents.pos[0, 1] = cy
    pick = og.best_ochre_site_near(sim, 0, perception_radius_m=cog.OCHRE_PERCEPT_M)
    assert pick is not None
    tx = (pick.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (pick.coord[1] + 0.5) * CHUNK_SIDE_M
    if ((tx - (cx + 10.0)) ** 2 + (ty - cy) ** 2) ** 0.5 < cog.INTERACT_RADIUS_M:
        pytest.skip("best site is underfoot — no WALK_TO to assert")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)
    assert abs(dec.target_x - tx) < 1e-3
    assert abs(dec.target_y - ty) < 1e-3


def test_curious_agent_without_ochre_falls_back_to_explore():
    sim, _coords = _booted_sim("explore")
    _calm_curious(sim, 0)
    fx, fy = _far_unstreamed()                # nothing streamed → nothing perceived
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.EXPLORE)


# ---------------------------------------------------------------------------
# 3. Act — GRIND wins pigment scaled by the world's true pigment_quality
# ---------------------------------------------------------------------------

def test_grinding_oxide_yields_pigment_and_memory():
    sim, coords = _booted_sim("yield")
    best = _best_usable_coord(sim, coords)
    if best is None:
        pytest.skip("no usable ochre site")
    cue = og.ochre_cue_for_chunk(sim, best)
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    ev = _grind_here(sim, 0)
    assert float(sim.agents.inv_pigment[0]) > 0.0           # real pigment won
    assert len(sim.agents.memory[0].known_ochre_locations) == 1
    assert ev and ev[-1]["kind"] == "grind"
    assert ev[-1]["pigment_class"] == cue.pigment_class
    assert ev[-1]["pigment_kg"] > 0.0


def test_pigment_tracks_true_quality_oxide_beats_rusty_sulfide():
    """The painter's lie #9: identical GRIND action, two rusty gossans. An OXIDE gossan
    yields pigment; a rusty SULFIDE / non-iron gossan yields none. A flat yield would mean
    the loop ignores C18's truth."""
    sim, coords = _booted_sim("scale")
    best = _best_usable_coord(sim, coords)
    lie = _lie_coord(sim, coords)
    if best is None or lie is None:
        pytest.skip("seed lacks both an oxide site and a rusty lie")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    _grind_here(sim, 0)
    oxide_pig = float(sim.agents.inv_pigment[0])

    _calm_curious(sim, 1)
    _stand(sim, 1, lie)
    _grind_here(sim, 1)
    lie_pig = float(sim.agents.inv_pigment[1])

    assert oxide_pig > 0.0                                   # oxide gossan paints
    assert lie_pig == 0.0                                    # rusty sulfide paints nothing
    lie_cue = og.ochre_cue_for_chunk(sim, lie)
    assert lie_cue is not None and lie_cue.is_pigment is False


# ---------------------------------------------------------------------------
# 4. « Le monde ne ment jamais » — no perceived gossan yields nothing, unremembered
# ---------------------------------------------------------------------------

def test_grinding_where_no_gossan_yields_nothing():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert og.prospect_ochre(sim, fx, fy) is None
    dec = cog.Decision(int(ActionKind.GRIND), fx, fy, 0.5)
    _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick, sim=sim)
    assert float(sim.agents.inv_pigment[0]) == 0.0
    assert len(sim.agents.memory[0].known_ochre_locations) == 0


# ---------------------------------------------------------------------------
# 5. Survival always outranks grinding
# ---------------------------------------------------------------------------

def test_critical_thirst_outranks_grinding():
    sim, coords = _booted_sim("priority")
    best = _best_usable_coord(sim, coords)
    if best is None:
        pytest.skip("no usable ochre site")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95                     # critical
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)              # never GRIND


# ---------------------------------------------------------------------------
# 6. Back-compat — GRIND with the old 5-arg signature is inert, never crashes
# ---------------------------------------------------------------------------

def test_grind_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_usable_coord(sim, coords)
    if best is None:
        pytest.skip("no usable ochre site")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    dec = cog.Decision(int(ActionKind.GRIND), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_pigment[0]) == 0.0


# ---------------------------------------------------------------------------
# 7. Orthogonal inventory — GRIND fills pigment only, never the tool-stone pool
# ---------------------------------------------------------------------------

def test_grind_fills_pigment_not_stone_or_tools():
    sim, coords = _booted_sim("orthogonal")
    best = _best_usable_coord(sim, coords)
    if best is None:
        pytest.skip("no usable ochre site")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    _grind_here(sim, 0)
    assert float(sim.agents.inv_pigment[0]) > 0.0
    assert float(sim.agents.inv_stone[0]) == 0.0           # GRIND is not GATHER / KNAP
    assert float(sim.agents.inv_tools[0]) == 0.0


# ---------------------------------------------------------------------------
# 8. Bounded — once pigment-sated, the agent stops seeking and explores
# ---------------------------------------------------------------------------

def test_pigment_sated_agent_stops_seeking():
    sim, coords = _booted_sim("sated")
    best = _best_usable_coord(sim, coords)
    if best is None:
        pytest.skip("no usable ochre site")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    sim.agents.inv_pigment[0] = cog.PIGMENT_SATED_KG + 0.1   # already carrying enough
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.EXPLORE)
