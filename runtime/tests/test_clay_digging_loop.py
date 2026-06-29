"""Invariants — the agent loop DIGS workable clay (D12 wire, 2026-06-29, consumes C5).

Context (AUDIT-DELTA-2026-06-23, risk **D12 / R0**): the C1→C20 capability arc was a library
with no player. DRINK/C3, KNAP/C2, GATHER/C14, GRIND/C18, MARK/C20, IGNITE/C7 and TEMPER/C8 took
the first seven bites. This is the 8th — a **non-fire precursor** that restores the fire/non-fire
alternation after IGNITE+TEMPER, and lays in **the matter of the future pot**: C5 ``clay_outcrop``
made clay banks *perceivable* (smooth ochre exposures, plastic window, pottery grade); but no agent
ever dug one. ``inv_clay`` is the substrate C9 ``ceramic_firing`` will one day consume.

Emergent clay digging:
- ``cognition._seek_clay`` lets a survival-satisfied, curious agent that SEES a clay bank it could
  work (``clay_outcrop.best_clay_near``) walk there and DIG into its clay store instead of wandering
  — utility-based action selection, nothing scripted. Tried after the tool/fire/temper cluster and
  before the symbolic ``_seek_ochre`` / ``_seek_canvas`` (useful matter before art). It runs on its
  OWN inventory (``inv_clay``), so it never competes with the stone / pigment pools.
- ``cognition.apply_decision``'s new ``ActionKind.DIG`` branch digs the bank underfoot, fills
  ``inv_clay`` by the world's committed ``pottery_grade`` × workability (``clay_outcrop.prospect_clay``),
  and records WHICH clay (``last_clay_class``) + the site. A plastic kaolinite digs into fine
  ceramic-grade clay; a silty SHALE_CLAY works poorly; a bank outside the plastic window (too dry /
  too wet) yields little until conditioned (the lie #13). The agent learns smooth→pot by acting.

What this file proves:
1. The loop is genuinely gated on C5 (no cue cache → inert; no scripted fallback).
2. A curious agent on the best perceived clay bank chooses DIG; off-site it WALK_TOs toward it.
3. DIG fills the clay store, records the clay class + the site — the matter is LIVED.
4. Outcome = world truth: a plastic (ceramic-grade) bank yields more than a silty shale bank.
5. The workability lie #13: a bank outside the plastic window yields the reduced (damp) amount.
6. « le monde ne ment jamais » — digging where no clay is underfoot yields nothing.
7. Self-limiting — a clay-rich agent (inv_clay ≥ sated) does not seek to dig more.
8. Survival always outranks digging (a critically thirsty agent drinks, never digs).
9. DIG is back-compat inert with the old ``sim=None`` signature, fills only ``inv_clay`` (stone /
   tools / pigment untouched), and is NON-MUTATING (no ``geo.mine_at``; the mutation frontier D10
   stays frozen).

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
import engine.clay_outcrop as clo                                  # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_CLAY = 0x42        # plentiful WORKABLE clay, both classes (plastic ceramic + silty shale)
SEED_CLAY_DRY = 0xF00D  # high-grade clay but NONE workable now (outside the plastic window) — the lie
GRID = 12


def _booted_sim(name: str, seed: int = SEED_CLAY, *, with_c5: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c5:
        clo.install_clay_outcrop(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_claysite_coord(sim, coords):
    """The coord ``best_clay_near`` would globally prefer — max (pottery_grade, confidence).
    Standing the agent here makes the underfoot bank the in-window argmax, so the loop DIGs."""
    best = None
    for coord in coords:
        cue = clo.clay_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        key = (cue.pottery_grade, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _site_of_class(sim, coords, class_name: str):
    for coord in coords:
        cue = clo.clay_cue_for_chunk(sim, coord)
        if cue is not None and cue.clay_class.name == class_name:
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
                "inv_metal", "inv_tools", "inv_pigment", "inv_clay"):
        getattr(sim.agents, inv)[row] = 0.0
    mem = sim.agents.memory[row]
    mem.known_clay_locations.clear()
    mem.last_clay_class = None


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


def _dig_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.DIG), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


# 1. Gate — without C5 there is no clay perception at all
def test_seek_clay_inert_without_c5():
    sim, coords = _booted_sim("gate", with_c5=False)
    _calm_curious(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_clay_cue_cache", None) is None
    assert cog._seek_clay(sim.agents, 0, _obs(sim, 0), sim) is None


# 2. Choose — a curious agent on the best clay bank decides to DIG; off-site walks toward it
def test_curious_agent_on_claysite_decides_to_dig():
    sim, coords = _booted_sim("dig")
    best = _best_claysite_coord(sim, coords)
    if best is None:
        pytest.skip("seed produced no clay in the streamed grid")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.DIG)


def test_curious_agent_walks_toward_perceived_claysite():
    sim, coords = _booted_sim("walk")
    best = _best_claysite_coord(sim, coords)
    if best is None:
        pytest.skip("no clay for the walk fixture")
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0)
    sim.agents.pos[0, 0] = cx + 10.0          # off-centre but in-chunk (< CHUNK_SIDE_M/2)
    sim.agents.pos[0, 1] = cy
    pick = clo.best_clay_near(sim, 0, perception_radius_m=cog.CLAY_PERCEPT_M)
    assert pick is not None
    tx = (pick.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (pick.coord[1] + 0.5) * CHUNK_SIDE_M
    if ((tx - (cx + 10.0)) ** 2 + (ty - cy) ** 2) ** 0.5 < cog.INTERACT_RADIUS_M:
        pytest.skip("best clay bank is underfoot — no WALK_TO to assert")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)
    assert abs(dec.target_x - tx) < 1e-3
    assert abs(dec.target_y - ty) < 1e-3


# 3. Act — DIG fills the clay store, records the class + the site
def test_digging_fills_clay_records_and_remembers():
    sim, coords = _booted_sim("fill")
    best = _best_claysite_coord(sim, coords)
    if best is None:
        pytest.skip("no clay")
    cue = clo.clay_cue_for_chunk(sim, best)
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    clay_before = float(sim.agents.inv_clay[0])
    ev = _dig_here(sim, 0)
    assert ev and ev[-1]["kind"] == "dig"
    assert ev[-1]["clay_class"] == cue.clay_class.name
    assert float(sim.agents.inv_clay[0]) > clay_before            # the bank yielded clay
    assert sim.agents.memory[0].last_clay_class == cue.clay_class.name
    assert len(sim.agents.memory[0].known_clay_locations) == 1


# 4. Outcome tracks world truth — plastic (ceramic) clay yields more than silty shale
def test_plastic_clay_yields_more_than_shale():
    sim, coords = _booted_sim("grade")
    cp = _site_of_class(sim, coords, "PLASTIC_CLAY")
    cs = _site_of_class(sim, coords, "SHALE_CLAY")
    if cp is None or cs is None:
        pytest.skip("seed lacks both clay classes")
    yields = {}
    for label, coord in (("plastic", cp), ("shale", cs)):
        s, _c = _booted_sim(f"grade_{label}")
        _calm_curious(s, 0)
        _stand(s, 0, coord)
        ev = _dig_here(s, 0)
        yields[label] = float(ev[-1]["clay_kg"])
    assert yields["plastic"] > yields["shale"]                    # higher pottery_grade → more clay


# 5. The workability lie #13 — clay outside the plastic window yields the reduced (damp) amount
def test_unworkable_clay_yields_reduced_amount():
    sim, coords = _booted_sim("dry", seed=SEED_CLAY_DRY)
    best = _best_claysite_coord(sim, coords)
    if best is None:
        pytest.skip("dry seed produced no clay")
    cue = clo.clay_cue_for_chunk(sim, best)
    if cue.workable_now:
        pytest.skip("expected a non-workable bank on this seed")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    ev = _dig_here(sim, 0)
    assert ev[-1]["workable_now"] is False
    # damp clay yields the reduced fraction of the grade-scaled nominal (the lie, learned by acting).
    # The event rounds clay_kg to 4 decimals, so compare with a matching tolerance.
    expected = cog.CLAY_DIG_KG * float(cue.pottery_grade) * cog.DAMP_CLAY_FACTOR
    assert abs(float(ev[-1]["clay_kg"]) - expected) < 1e-3


# 6. « Le monde ne ment jamais » — no clay underfoot yields nothing
def test_digging_where_no_clay_yields_nothing():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert clo.prospect_clay(sim, fx, fy) is None
    ev = _dig_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_clay[0]) == 0.0
    assert len(sim.agents.memory[0].known_clay_locations) == 0


# 7. Self-limiting — a clay-rich agent does not seek to dig more
def test_clay_rich_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    best = _best_claysite_coord(sim, coords)
    if best is None:
        pytest.skip("no clay")
    _calm_curious(sim, 0)
    sim.agents.inv_clay[0] = cog.CLAY_SATED_KG + 0.1
    _stand(sim, 0, best)
    assert cog._seek_clay(sim.agents, 0, _obs(sim, 0), sim) is None


# 8. Survival outranks digging
def test_critical_thirst_outranks_digging():
    sim, coords = _booted_sim("priority")
    best = _best_claysite_coord(sim, coords)
    if best is None:
        pytest.skip("no clay")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)


# 9. Back-compat + orthogonality + non-mutation
def test_dig_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_claysite_coord(sim, coords)
    if best is None:
        pytest.skip("no clay")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    dec = cog.Decision(int(ActionKind.DIG), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_clay[0]) == 0.0


def test_dig_fills_only_clay_and_is_non_mutating():
    sim, coords = _booted_sim("orthogonal")
    best = _best_claysite_coord(sim, coords)
    if best is None:
        pytest.skip("no clay")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    g_before = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
                for layer in geo.chunk_geology(sim, best).layers]
    _dig_here(sim, 0)
    g_after = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
               for layer in geo.chunk_geology(sim, best).layers]
    assert g_before == g_after                              # geology unchanged
    assert float(sim.agents.inv_clay[0]) > 0.0             # clay filled…
    assert float(sim.agents.inv_stone[0]) == 0.0           # …but DIG is not KNAP / GATHER
    assert float(sim.agents.inv_tools[0]) == 0.0           # nor TEMPER
    assert float(sim.agents.inv_pigment[0]) == 0.0         # nor GRIND


def test_dig_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    best = _best_claysite_coord(a, ca)
    if best is None:
        pytest.skip("no clay")
    evs = []
    for s in (a, b):
        _calm_curious(s, 0)
        _stand(s, 0, best)
        evs.append(_dig_here(s, 0)[-1])
    assert evs[0]["clay_class"] == evs[1]["clay_class"]
    assert evs[0]["pottery_grade"] == evs[1]["pottery_grade"]
    assert evs[0]["clay_kg"] == evs[1]["clay_kg"]
    assert abs(float(a.agents.inv_clay[0]) - float(b.agents.inv_clay[0])) < 1e-12
