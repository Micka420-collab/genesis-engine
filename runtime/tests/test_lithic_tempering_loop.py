"""Invariants — the agent loop CONSUMES C8 lithic_tempering (D12 wire, 2026-06-29).

Context (AUDIT-DELTA-2026-06-23, risk **D12 / R0**): the C1→C20 capability arc was a
library with no player. DRINK/C3, KNAP/C2, GATHER/C14, GRIND/C18, MARK/C20 and IGNITE/C7 took
the first six bites. This is the 7th — and it is **fire's first use ON a material**. C7 made
fire-making *livable* (the VOÛTE). C8 ``lithic_tempering`` is the oldest pyrotechnology after
fire itself: heating a cryptocrystalline silica nodule (flint / chert) in that fire to win a
**keener cutting edge** than cold percussion gives. Until now no agent ever roasted a stone.

Emergent heat treatment:
- ``cognition._seek_tempersite`` lets a survival-satisfied, curious agent that ALREADY KNOWS
  FIRE (``has_made_fire``) and SEES a heat-responsive silica it could roast
  (``lithic_tempering.best_temper_site_near``) walk there and TEMPER instead of wandering —
  utility-based action selection, nothing scripted. Tried *after* ``_seek_firesite`` (you must
  have made fire to heat-treat with it) and *before* the symbolic ``_seek_ochre`` /
  ``_seek_canvas`` (tools before art).
- ``cognition.apply_decision``'s new ``ActionKind.TEMPER`` branch roasts the silica underfoot,
  raises the agent's cutting edge (``inv_tools``) by the world's committed ``tempered_quality``
  (``lithic_tempering.prospect_tempering``), and records the skill (``has_tempered_stone`` /
  ``last_temper_gain``). Cryptocrystalline chert responds strongly, quartzite modestly; OBSIDIAN
  — the best raw knapping stone, the obvious-looking candidate — gains NOTHING (already glass):
  the world returns no cue there (the lie #12). The agent learns fire+silex→edge by acting.

What this file proves:
1. The loop is genuinely gated on C8 (no cue cache → inert; no scripted fallback).
2. Fire's FIRST consumer — an agent that has never made fire does NOT seek to temper, even on a
   perfectly temperable site (the C7→C8 dependency is honoured, not scripted around).
3. A curious, fire-knowing agent on the best perceived temper site chooses TEMPER; off-site it
   WALK_TOs toward it.
4. TEMPER raises the cutting edge by the world-committed gain, records the skill and the site —
   the pyrotechnology is LIVED, not merely provable.
5. « le monde ne ment jamais » — roasting where no temperable silica+fire is underfoot yields
   nothing; ``best_temper_site_near`` never routes the agent to a non-temperable (e.g. obsidian)
   site, so the lie #12 is only ever learned by acting on one.
6. Self-limiting — a tool-rich agent (``inv_tools`` ≥ sated) does not seek to temper more.
7. Survival always outranks tempering (a critically thirsty agent drinks, never tempers).
8. TEMPER is back-compat inert with the old ``sim=None`` signature, fills NO new inventory
   (reuses ``inv_tools``; ``inv_stone`` / ``inv_pigment`` untouched), and is NON-MUTATING (no
   ``geo.mine_at``; the mutation frontier D10 stays frozen).

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
import engine.lithic_tempering as lt                               # noqa: E402

# Several arc capabilities globally REASSIGN ``cog.decide`` / ``cog.apply_decision`` with
# monkey-patch wrappers and never restore them. The D12 wire under test lives in the
# ORIGINAL functions; we capture them at import (before any installer runs) and exercise
# those directly — the correct unit scope, immune to cross-test pollution.
_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_TEMPER = 0xBEEF   # a temperate grassland continent → chert/quartzite outcrops AND makeable
                       # fire coexist (the 1+1>2 gate of C8); same world the C7 fire wire uses.
GRID = 12


# ---------------------------------------------------------------------------
# Fixtures — a real Genesis world whose temper sites C8 exposes. No injection: the world
# really carries heat-responsive silica beside a fire-makeable spot; we just point the
# fire-knowing curious agent at the best one.
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = SEED_TEMPER, *, with_c8: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c8:
        lt.install_lithic_tempering(sim)   # also installs the composed C2 lithic + C7 fire
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_tempersite_coord(sim, coords):
    """The coord ``best_temper_site_near`` would globally prefer — max (quality_gain,
    confidence) among temperable sites. Standing the agent here makes the underfoot site the
    in-window argmax, so the loop deterministically TEMPERs."""
    best = None
    for coord in coords:
        cue = lt.temper_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        key = (cue.quality_gain, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _calm_curious(sim, row, *, knows_fire: bool = True, tool_secured: bool = False):
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
    mem = sim.agents.memory[row]
    mem.known_temper_locations.clear()
    mem.has_tempered_stone = False
    mem.last_temper_gain = None
    # C8 is fire's first downstream use: the agent must already know how to make a fire.
    mem.has_made_fire = bool(knows_fire)
    mem.last_fire_method = "PERCUSSION" if knows_fire else None
    if tool_secured:
        # The emergent order is GATHER → KNAP → IGNITE → TEMPER → GRIND → MARK: a fresh agent
        # on a chert outcrop secures raw stone (KNAP) and warmth (IGNITE) *before* it invests in
        # heat-treating. To isolate the TEMPER decision through the full ``decide()`` we hand it
        # an agent that has already done both — stone secured and warm — so the earlier seeks
        # yield and tempering is the next useful act.
        sim.agents.inv_stone[row] = cog.TOOLSTONE_SATED_KG   # _seek_toolstone → None (sated)
        sim.agents.thermal[row] = 0.05                       # warm + knows fire → _seek_firesite None


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


def _temper_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.TEMPER), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


# ---------------------------------------------------------------------------
# 1. Gate — without C8 installed there is no temper-site perception at all
# ---------------------------------------------------------------------------

def test_seek_tempersite_inert_without_c8():
    sim, coords = _booted_sim("gate", with_c8=False)
    _calm_curious(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_temper_cue_cache", None) is None
    assert cog._seek_tempersite(sim.agents, 0, _obs(sim, 0), sim) is None


# ---------------------------------------------------------------------------
# 2. Fire's first consumer — never-made-fire ⇒ no tempering, even on a perfect site
# ---------------------------------------------------------------------------

def test_agent_without_fire_does_not_seek_to_temper():
    sim, coords = _booted_sim("needs_fire")
    best = _best_tempersite_coord(sim, coords)
    if best is None:
        pytest.skip("seed produced no temper site in the streamed grid")
    _calm_curious(sim, 0, knows_fire=False)     # has never made a fire → cannot heat-treat
    _stand(sim, 0, best)
    assert cog._seek_tempersite(sim.agents, 0, _obs(sim, 0), sim) is None


def test_tempering_without_fire_skill_yields_nothing():
    """Even forced to act, an agent that never made fire roasts no stone (the C7→C8 gate)."""
    sim, coords = _booted_sim("needs_fire_act")
    best = _best_tempersite_coord(sim, coords)
    if best is None:
        pytest.skip("no temper site")
    _calm_curious(sim, 0, knows_fire=False)
    _stand(sim, 0, best)
    ev = _temper_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_tools[0]) == 0.0
    assert sim.agents.memory[0].has_tempered_stone is False


# ---------------------------------------------------------------------------
# 3. Choose — a curious, fire-knowing agent on the best temper site decides to TEMPER
# ---------------------------------------------------------------------------

def test_curious_fire_agent_on_site_decides_to_temper():
    sim, coords = _booted_sim("temper")
    best = _best_tempersite_coord(sim, coords)
    if best is None:
        pytest.skip("no temper site")
    _calm_curious(sim, 0, tool_secured=True)
    _stand(sim, 0, best)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.TEMPER)


def test_curious_agent_walks_toward_perceived_tempersite():
    """A fire-knowing agent that perceives a temper site but is not on it walks toward it —
    WALK_TO toward the perceived site centre, not random EXPLORE."""
    sim, coords = _booted_sim("walk")
    best = _best_tempersite_coord(sim, coords)
    if best is None:
        pytest.skip("no temper site for the walk fixture")
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0, tool_secured=True)
    sim.agents.pos[0, 0] = cx + 10.0          # off-centre but in-chunk (< CHUNK_SIDE_M/2)
    sim.agents.pos[0, 1] = cy
    pick = lt.best_temper_site_near(sim, 0, perception_radius_m=cog.TEMPER_PERCEPT_M)
    assert pick is not None
    tx = (pick.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (pick.coord[1] + 0.5) * CHUNK_SIDE_M
    if ((tx - (cx + 10.0)) ** 2 + (ty - cy) ** 2) ** 0.5 < cog.INTERACT_RADIUS_M:
        pytest.skip("best temper site is underfoot — no WALK_TO to assert")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)
    assert abs(dec.target_x - tx) < 1e-3
    assert abs(dec.target_y - ty) < 1e-3


# ---------------------------------------------------------------------------
# 4. Act — TEMPER raises the cutting edge, records the skill, remembers the site
# ---------------------------------------------------------------------------

def test_tempering_sharpens_records_and_remembers():
    sim, coords = _booted_sim("sharpen")
    best = _best_tempersite_coord(sim, coords)
    if best is None:
        pytest.skip("no temper site")
    cue = lt.temper_cue_for_chunk(sim, best)
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    tools_before = float(sim.agents.inv_tools[0])
    ev = _temper_here(sim, 0)
    assert ev and ev[-1]["kind"] == "temper"
    assert ev[-1]["silica_kind"] == cue.silica_kind
    assert float(sim.agents.inv_tools[0]) > tools_before          # the heat won a keener edge
    assert ev[-1]["tempered_quality"] == round(float(cue.tempered_quality), 4)
    assert ev[-1]["quality_gain"] > 0.0                           # a real pyrotechnology premium
    assert sim.agents.memory[0].has_tempered_stone is True        # skill learned by acting
    assert abs(sim.agents.memory[0].last_temper_gain - cue.quality_gain) < 1e-9
    assert len(sim.agents.memory[0].known_temper_locations) == 1


def test_tempered_edge_beats_cold_knap_on_the_same_stone():
    """The world commits to a premium: heat-treated quality ≥ the raw base, so the edge a
    TEMPER yields is ≥ what cold KNAP would give on that very stone (responsive silica)."""
    sim, coords = _booted_sim("premium")
    best = _best_tempersite_coord(sim, coords)
    if best is None:
        pytest.skip("no temper site")
    cue = lt.temper_cue_for_chunk(sim, best)
    # cold-knap edge ~ KNAP_TOOL_YIELD * base; tempered edge ~ TEMPER_TOOL_YIELD * tempered.
    cold = cog.KNAP_TOOL_YIELD * float(cue.base_quality)
    hot = cog.TEMPER_TOOL_YIELD * float(cue.tempered_quality)
    assert cue.tempered_quality >= cue.base_quality
    assert hot >= cold


# ---------------------------------------------------------------------------
# 5. « Le monde ne ment jamais » — no temperable silica+fire underfoot yields nothing;
#    the agent is never routed to a non-temperable (obsidian) site.
# ---------------------------------------------------------------------------

def test_tempering_where_nothing_temperable_yields_nothing():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert lt.prospect_tempering(sim, fx, fy) is None
    ev = _temper_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_tools[0]) == 0.0
    assert sim.agents.memory[0].has_tempered_stone is False
    assert len(sim.agents.memory[0].known_temper_locations) == 0


def test_best_site_is_always_temperable():
    """The lie #12 (obsidian looks prime but gains nothing) is only ever learned by ACTING on
    one: perception never routes the agent to a non-temperable site."""
    sim, coords = _booted_sim("routing")
    best = _best_tempersite_coord(sim, coords)
    if best is None:
        pytest.skip("no temper site")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    pick = lt.best_temper_site_near(sim, 0, perception_radius_m=cog.TEMPER_PERCEPT_M)
    assert pick is not None
    assert pick.temperable is True
    assert pick.silica_kind in ("chert", "quartzite")    # never obsidian / none
    assert pick.quality_gain > 0.0


# ---------------------------------------------------------------------------
# 6. Self-limiting — a tool-rich agent does not seek to temper more
# ---------------------------------------------------------------------------

def test_tool_rich_agent_does_not_reseek_to_temper():
    sim, coords = _booted_sim("sated")
    best = _best_tempersite_coord(sim, coords)
    if best is None:
        pytest.skip("no temper site")
    _calm_curious(sim, 0)
    sim.agents.inv_tools[0] = cog.TEMPER_TOOLS_SATED + 0.1   # already tool-rich
    _stand(sim, 0, best)
    assert cog._seek_tempersite(sim.agents, 0, _obs(sim, 0), sim) is None


# ---------------------------------------------------------------------------
# 7. Survival always outranks tempering
# ---------------------------------------------------------------------------

def test_critical_thirst_outranks_tempering():
    sim, coords = _booted_sim("priority")
    best = _best_tempersite_coord(sim, coords)
    if best is None:
        pytest.skip("no temper site")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95                    # critical
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)              # never TEMPER


# ---------------------------------------------------------------------------
# 8. Back-compat + orthogonality + non-mutation
# ---------------------------------------------------------------------------

def test_temper_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_tempersite_coord(sim, coords)
    if best is None:
        pytest.skip("no temper site")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    dec = cog.Decision(int(ActionKind.TEMPER), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_tools[0]) == 0.0            # nothing changed without sim
    assert sim.agents.memory[0].has_tempered_stone is False


def test_temper_fills_only_tools_and_is_non_mutating():
    sim, coords = _booted_sim("orthogonal")
    best = _best_tempersite_coord(sim, coords)
    if best is None:
        pytest.skip("no temper site")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    # geology snapshot before — TEMPER must not mutate it (D10 frozen)
    g_before = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
                for layer in geo.chunk_geology(sim, best).layers]
    _temper_here(sim, 0)
    g_after = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
               for layer in geo.chunk_geology(sim, best).layers]
    assert g_before == g_after                              # geology unchanged
    assert float(sim.agents.inv_tools[0]) > 0.0             # the edge improved…
    assert float(sim.agents.inv_stone[0]) == 0.0            # …but TEMPER is not KNAP / GATHER
    assert float(sim.agents.inv_pigment[0]) == 0.0          # nor GRIND


def test_temper_outcome_is_deterministic():
    """Same seed + same site ⇒ identical heat-treatment outcome (pure cue + memoised, no RNG)."""
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    best = _best_tempersite_coord(a, ca)
    if best is None:
        pytest.skip("no temper site")
    evs = []
    for s in (a, b):
        _calm_curious(s, 0)
        _stand(s, 0, best)
        evs.append(_temper_here(s, 0)[-1])
    assert evs[0]["silica_kind"] == evs[1]["silica_kind"]
    assert evs[0]["tempered_quality"] == evs[1]["tempered_quality"]
    assert evs[0]["quality_gain"] == evs[1]["quality_gain"]
    assert abs(float(a.agents.inv_tools[0]) - float(b.agents.inv_tools[0])) < 1e-12
