"""Invariants — the agent loop CONSUMES C20 rock_canvas (D12 wire, 2026-06-28).

Context (AUDIT-DELTA-2026-06-23, risk **D12 / R0**): the C1→C20 capability arc was a
library with no player. DRINK/C3, KNAP/C2, GATHER/C14 and GRIND/C18 took the first four
bites; GRIND opened the **symbolic** pillar by filling ``inv_pigment``. This is the 5th
bite and the symbolic pillar's **second** consumer: emergent **marking** — a curious agent
that HOLDS ground pigment (C18) and SEES a pale carbonate wall (C20) leaves a MARK. The
WORLD decides whether the mark LASTS (wall durability) and is SEEN (pigment/wall contrast).

Emergent rock-wall marking:
- ``cognition._seek_canvas`` lets a survival-satisfied, curious agent that already holds a
  colour and SEES a paintable wall (``rock_canvas.best_canvas_near``) walk there and MARK
  it instead of wandering — utility-based action selection, nothing scripted. It is tried
  *after* ``_seek_ochre`` (grind the pigment, THEN paint with it).
- ``cognition.apply_decision``'s new ``ActionKind.MARK`` branch paints the held hue onto
  the carbonate wall underfoot, spends a little ``inv_pigment``, and records the world's
  truth (``rock_canvas.paint_outcome``): a SOUND limestone face keeps the mark (calcite
  veil); a KARST / FROST wall takes the pigment then flakes it off (mensonge #11 — looks
  markable ≠ holds a lasting mark). The agent learns the wall→permanence link by acting.

What this file proves:
1. The loop is genuinely gated on C20 (no cue cache → inert; no scripted fallback).
2. An armed agent (pigment + a carried hue) on the best perceived wall chooses MARK; off-site
   it WALK_TOs; with no pigment in hand it never marks.
3. The outcome is the world's truth: a SOUND wall holds the mark, a KARST wall flakes it.
4. « le monde ne ment jamais » — marking where no carbonate wall is underfoot yields nothing.
5. Survival always outranks marking (a critically thirsty agent drinks, never marks).
6. MARK is back-compat inert with the old ``sim=None`` signature, and NON-MUTATING (D10
   frozen): it spends pigment only, never inv_stone / inv_tools, never the geology.

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
import engine.rock_canvas as rc                                    # noqa: E402

# Several arc capabilities globally REASSIGN ``cog.decide`` / ``cog.apply_decision`` with
# monkey-patch wrappers and never restore them. The D12 wire under test lives in the
# ORIGINAL functions; we capture them at import (before any installer runs) and exercise
# those directly — the correct unit scope, immune to cross-test pollution.
_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_SOUND = 0xC1A7   # temperate-dry carbonate continent → SOUND walls, durable marks
SEED_KARST = 0xFE11   # same carbonate in a humid climate → KARST walls, marks flake off
HEMATITE = (132, 46, 28)   # a dark red ochre hue (contrasts a pale limestone wall)
GRID = 12


# ---------------------------------------------------------------------------
# Fixtures — a real Genesis world whose carbonate walls C20 exposes. No injection:
# the world really has limestone faces; we just point the armed agent at one.
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = SEED_SOUND, *, with_c20: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c20:
        rc.install_rock_canvas(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_canvas_coord(sim, coords):
    """The coord ``best_canvas_near`` would globally prefer — max (durability, adhesion)
    among carbonate walls. Standing the agent here makes the underfoot wall the in-window
    argmax, so the loop deterministically MARKs."""
    best = None
    for coord in coords:
        cue = rc.canvas_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        key = (cue.durability, cue.adhesion, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _flaking_coord(sim, coords):
    """A coord whose carbonate wall is perceivable but flakes — takes the pigment yet does
    NOT hold a lasting mark (KARST dissolution / FROST spalling): the lie #11."""
    for coord in coords:
        cue = rc.canvas_cue_for_chunk(sim, coord)
        if cue is not None and not cue.holds_lasting_mark:
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
    sim.agents.memory[row].known_canvas_locations.clear()
    sim.agents.memory[row].last_pigment_hue = None


def _arm_pigment(sim, row, hue=HEMATITE, kg: float = 1.0):
    """Give the agent a colour in hand — as if it had just ground ochre (C18)."""
    sim.agents.inv_pigment[row] = float(kg)
    sim.agents.memory[row].last_pigment_hue = tuple(int(c) for c in hue)


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


def _mark_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.MARK), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


# ---------------------------------------------------------------------------
# 1. Gate — without C20 installed there is no canvas perception at all
# ---------------------------------------------------------------------------

def test_seek_canvas_inert_without_c20():
    sim, coords = _booted_sim("gate", with_c20=False)
    _calm_curious(sim, 0)
    _arm_pigment(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_canvas_cue_cache", None) is None
    assert cog._seek_canvas(sim.agents, 0, _obs(sim, 0), sim) is None


# ---------------------------------------------------------------------------
# 2. Choose — an armed agent on the best perceived wall decides to MARK
# ---------------------------------------------------------------------------

def test_armed_agent_on_canvas_decides_to_mark():
    sim, coords = _booted_sim("mark")
    best = _best_canvas_coord(sim, coords)
    if best is None:
        pytest.skip("seed produced no carbonate wall in the streamed grid")
    _calm_curious(sim, 0)
    _arm_pigment(sim, 0)
    _stand(sim, 0, best)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.MARK)


def test_armed_agent_walks_toward_perceived_canvas():
    """An armed agent that perceives a wall but is not on it walks toward it — WALK_TO toward
    the perceived wall centre, not random EXPLORE."""
    sim, coords = _booted_sim("walk")
    best = _best_canvas_coord(sim, coords)
    if best is None:
        pytest.skip("no carbonate wall for the walk fixture")
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0)
    _arm_pigment(sim, 0)
    sim.agents.pos[0, 0] = cx + 10.0          # off-centre but in-chunk (< CHUNK_SIDE_M/2)
    sim.agents.pos[0, 1] = cy
    pick = rc.best_canvas_near(sim, 0, perception_radius_m=cog.CANVAS_PERCEPT_M)
    assert pick is not None
    tx = (pick.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (pick.coord[1] + 0.5) * CHUNK_SIDE_M
    if ((tx - (cx + 10.0)) ** 2 + (ty - cy) ** 2) ** 0.5 < cog.INTERACT_RADIUS_M:
        pytest.skip("best wall is underfoot — no WALK_TO to assert")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)
    assert abs(dec.target_x - tx) < 1e-3
    assert abs(dec.target_y - ty) < 1e-3


def test_unarmed_agent_does_not_mark():
    """No colour in hand → no MARK. With only C20 installed and no pigment, a curious agent
    standing on a wall falls through to ordinary EXPLORE (it has nothing to paint with)."""
    sim, coords = _booted_sim("unarmed")
    best = _best_canvas_coord(sim, coords)
    if best is None:
        pytest.skip("no carbonate wall")
    _calm_curious(sim, 0)                      # leaves inv_pigment == 0, hue None
    _stand(sim, 0, best)
    assert cog._seek_canvas(sim.agents, 0, _obs(sim, 0), sim) is None
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.EXPLORE)


# ---------------------------------------------------------------------------
# 3. Act — MARK records the world's truth: SOUND lasts, KARST flakes (lie #11)
# ---------------------------------------------------------------------------

def test_marking_sound_wall_lasts_and_debits():
    sim, coords = _booted_sim("sound", seed=SEED_SOUND)
    best = _best_canvas_coord(sim, coords)
    if best is None:
        pytest.skip("no carbonate wall")
    cue = rc.canvas_cue_for_chunk(sim, best)
    _calm_curious(sim, 0)
    _arm_pigment(sim, 0, kg=1.0)
    _stand(sim, 0, best)
    ev = _mark_here(sim, 0)
    assert ev and ev[-1]["kind"] == "mark"
    assert ev[-1]["material"] == cue.material
    assert ev[-1]["pigment_kg"] > 0.0
    assert float(sim.agents.inv_pigment[0]) < 1.0           # pigment spent
    assert len(sim.agents.memory[0].known_canvas_locations) == 1
    if cue.holds_lasting_mark:                              # 0xC1A7 walls are SOUND
        assert ev[-1]["lasts"] is True


def test_marking_karst_wall_made_but_flakes():
    """The painter's lie #11: identical MARK, two carbonate walls. A SOUND wall holds the
    mark; a KARST / FROST wall takes the pigment (a mark IS made — pigment is spent) but it
    does NOT last. A flat outcome would mean the loop ignores C20's truth."""
    sim, coords = _booted_sim("karst", seed=SEED_KARST)
    flaking = _flaking_coord(sim, coords)
    if flaking is None:
        pytest.skip("seed produced no flaking (karst/frost) carbonate wall")
    _calm_curious(sim, 0)
    _arm_pigment(sim, 0, kg=1.0)
    _stand(sim, 0, flaking)
    ev = _mark_here(sim, 0)
    assert ev and ev[-1]["kind"] == "mark"
    assert ev[-1]["pigment_kg"] > 0.0                       # the mark IS made (pigment spent)
    assert ev[-1]["lasts"] is False                         # …but it flakes off (the lie)


# ---------------------------------------------------------------------------
# 4. « Le monde ne ment jamais » — no carbonate wall underfoot yields nothing
# ---------------------------------------------------------------------------

def test_marking_where_no_wall_yields_nothing():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0)
    _arm_pigment(sim, 0, kg=1.0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert rc.prospect_canvas(sim, fx, fy) is None
    before = float(sim.agents.inv_pigment[0])
    _ORIG_APPLY(sim.agents, 0, cog.Decision(int(ActionKind.MARK), fx, fy, 0.5),
                sim.streamer, sim.tick, sim=sim)
    assert float(sim.agents.inv_pigment[0]) == before       # no wall → no pigment spent
    assert len(sim.agents.memory[0].known_canvas_locations) == 0


# ---------------------------------------------------------------------------
# 5. Survival always outranks marking
# ---------------------------------------------------------------------------

def test_critical_thirst_outranks_marking():
    sim, coords = _booted_sim("priority")
    best = _best_canvas_coord(sim, coords)
    if best is None:
        pytest.skip("no carbonate wall")
    _calm_curious(sim, 0)
    _arm_pigment(sim, 0)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95                    # critical
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)              # never MARK


# ---------------------------------------------------------------------------
# 6. Back-compat + non-mutation — old signature inert; MARK spends pigment only
# ---------------------------------------------------------------------------

def test_mark_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_canvas_coord(sim, coords)
    if best is None:
        pytest.skip("no carbonate wall")
    _calm_curious(sim, 0)
    _arm_pigment(sim, 0, kg=1.0)
    px, py = _stand(sim, 0, best)
    dec = cog.Decision(int(ActionKind.MARK), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_pigment[0]) == 1.0          # nothing spent without sim


def test_mark_spends_pigment_only_not_stone_or_tools():
    sim, coords = _booted_sim("orthogonal")
    best = _best_canvas_coord(sim, coords)
    if best is None:
        pytest.skip("no carbonate wall")
    _calm_curious(sim, 0)
    _arm_pigment(sim, 0, kg=1.0)
    _stand(sim, 0, best)
    _mark_here(sim, 0)
    assert float(sim.agents.inv_pigment[0]) < 1.0           # pigment spent
    assert float(sim.agents.inv_stone[0]) == 0.0            # MARK is not GATHER / KNAP
    assert float(sim.agents.inv_tools[0]) == 0.0


def test_mark_outcome_is_deterministic():
    """Same seed + same hue + same wall ⇒ bit-identical mark outcome (pure cue + memoised)."""
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    best = _best_canvas_coord(a, ca)
    if best is None:
        pytest.skip("no carbonate wall")
    evs = []
    for s in (a, b):
        _calm_curious(s, 0)
        _arm_pigment(s, 0, kg=1.0)
        _stand(s, 0, best)
        evs.append(_mark_here(s, 0)[-1])
    assert evs[0]["mark_durability"] == evs[1]["mark_durability"]
    assert evs[0]["contrast"] == evs[1]["contrast"]
    assert evs[0]["lasts"] == evs[1]["lasts"]
    assert abs(float(a.agents.inv_pigment[0]) - float(b.agents.inv_pigment[0])) < 1e-12
