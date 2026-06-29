"""Invariants — the agent loop QUARRIES carbonate stone (D12 wire, 2026-06-29, consumes C6).

Context (AUDIT-DELTA-2026-06-23, risk **D12 / R0**): the C1→C20 arc was a library with no player.
This is the 10th wire — the first appended through the new ``_ARC_SEEKS`` registry (the refactor).
A **non-fire precursor**: C6 ``limestone_outcrop`` made carbonate banks *perceivable* (white cliffs,
purity, dressability); but no agent ever quarried one. ``inv_limestone`` is the matter the future
C10 ``lime_burning`` will calcine to quicklime — the binder of the neolithic.

Emergent quarrying:
- ``cognition._seek_limestone`` lets a survival-satisfied, curious agent that SEES a mortar-grade
  carbonate bank (``limestone_outcrop.best_limestone_near``, require_mortar) walk there and QUARRY a
  block into its limestone store. It runs on its OWN inventory (``inv_limestone``).
- ``cognition.apply_decision``'s new ``ActionKind.QUARRY`` branch fills ``inv_limestone`` by the
  world's committed ``lime_grade`` (``limestone_outcrop.prospect_limestone``) and records WHICH
  carbonate (``last_lime_class``). A pure carbonate quarries rich; a karst/frost-weathered or
  dolomitic bank looks white but yields poorer stone (the lie #15). Learned by acting.

What this file proves:
1. The loop is gated on C6 (no cue cache → inert).
2. A curious agent on the best carbonate bank chooses QUARRY; off-site it WALK_TOs toward it.
3. QUARRY fills the limestone store, records the lime class + the site.
4. Outcome = world truth: a PURE_CARBONATE bank yields more than a COMMON_CARBONATE one.
5. « le monde ne ment jamais » — quarrying where no carbonate is underfoot yields nothing.
6. Self-limiting — a limestone-rich agent (inv_limestone ≥ sated) stops seeking.
7. Survival outranks quarrying.
8. Back-compat (sim=None inert), orthogonality (only inv_limestone moves), non-mutation (no mine_at).
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
import engine.limestone_outcrop as lso                             # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_LIMESTONE = 0xBEEF   # plentiful mortar-grade carbonate, both classes (pure + common)
GRID = 12


def _booted_sim(name: str, seed: int = SEED_LIMESTONE, *, with_c6: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c6:
        lso.install_limestone_outcrop(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _best_limestonesite_coord(sim, coords):
    """Max (lime_grade, confidence) among MORTAR-grade banks — matches best_limestone_near
    (require_mortar)."""
    best = None
    for coord in coords:
        cue = lso.limestone_cue_for_chunk(sim, coord)
        if cue is None or not cue.mortar_grade:
            continue
        key = (cue.lime_grade, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _site_of_class(sim, coords, class_name: str):
    for coord in coords:
        cue = lso.limestone_cue_for_chunk(sim, coord)
        if cue is not None and cue.lime_class.name == class_name:
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
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal",
                "inv_tools", "inv_pigment", "inv_clay", "inv_ceramic", "inv_limestone"):
        getattr(sim.agents, inv)[row] = 0.0
    mem = sim.agents.memory[row]
    mem.known_limestone_locations.clear()
    mem.last_lime_class = None


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


def _quarry_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.QUARRY), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


def test_seek_limestone_inert_without_c6():
    sim, coords = _booted_sim("gate", with_c6=False)
    _calm_curious(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_limestone_cue_cache", None) is None
    assert cog._seek_limestone(sim.agents, 0, _obs(sim, 0), sim) is None


def test_curious_agent_on_carbonate_decides_to_quarry():
    sim, coords = _booted_sim("quarry")
    best = _best_limestonesite_coord(sim, coords)
    if best is None:
        pytest.skip("no mortar-grade carbonate")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.QUARRY)


def test_curious_agent_walks_toward_perceived_carbonate():
    sim, coords = _booted_sim("walk")
    best = _best_limestonesite_coord(sim, coords)
    if best is None:
        pytest.skip("no carbonate")
    cx = (best[0] + 0.5) * CHUNK_SIDE_M
    cy = (best[1] + 0.5) * CHUNK_SIDE_M
    _calm_curious(sim, 0)
    sim.agents.pos[0, 0] = cx + 10.0
    sim.agents.pos[0, 1] = cy
    pick = lso.best_limestone_near(sim, 0, perception_radius_m=cog.QUARRY_PERCEPT_M, require_mortar=True)
    assert pick is not None
    tx = (pick.coord[0] + 0.5) * CHUNK_SIDE_M
    ty = (pick.coord[1] + 0.5) * CHUNK_SIDE_M
    if ((tx - (cx + 10.0)) ** 2 + (ty - cy) ** 2) ** 0.5 < cog.INTERACT_RADIUS_M:
        pytest.skip("best carbonate is underfoot — no WALK_TO to assert")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)
    assert abs(dec.target_x - tx) < 1e-3
    assert abs(dec.target_y - ty) < 1e-3


def test_quarrying_fills_limestone_records_and_remembers():
    sim, coords = _booted_sim("fill")
    best = _best_limestonesite_coord(sim, coords)
    if best is None:
        pytest.skip("no carbonate")
    cue = lso.limestone_cue_for_chunk(sim, best)
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    before = float(sim.agents.inv_limestone[0])
    ev = _quarry_here(sim, 0)
    assert ev and ev[-1]["kind"] == "quarry"
    assert ev[-1]["lime_class"] == cue.lime_class.name
    assert float(sim.agents.inv_limestone[0]) > before
    assert sim.agents.memory[0].last_lime_class == cue.lime_class.name
    assert len(sim.agents.memory[0].known_limestone_locations) == 1


def test_pure_carbonate_yields_more_than_common():
    sim, coords = _booted_sim("grade")
    cp = _site_of_class(sim, coords, "PURE_CARBONATE")
    cc = _site_of_class(sim, coords, "COMMON_CARBONATE")
    if cp is None or cc is None:
        pytest.skip("seed lacks both carbonate classes")
    yields = {}
    for label, coord in (("pure", cp), ("common", cc)):
        s, _c = _booted_sim(f"grade_{label}")
        _calm_curious(s, 0)
        _stand(s, 0, coord)
        ev = _quarry_here(s, 0)
        yields[label] = float(ev[-1]["limestone_kg"])
    assert yields["pure"] > yields["common"]


def test_quarrying_where_no_carbonate_yields_nothing():
    sim, _coords = _booted_sim("barren")
    _calm_curious(sim, 0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert lso.prospect_limestone(sim, fx, fy) is None
    ev = _quarry_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_limestone[0]) == 0.0
    assert len(sim.agents.memory[0].known_limestone_locations) == 0


def test_limestone_rich_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    best = _best_limestonesite_coord(sim, coords)
    if best is None:
        pytest.skip("no carbonate")
    _calm_curious(sim, 0)
    sim.agents.inv_limestone[0] = cog.LIMESTONE_SATED_KG + 0.1
    _stand(sim, 0, best)
    assert cog._seek_limestone(sim.agents, 0, _obs(sim, 0), sim) is None


def test_critical_thirst_outranks_quarrying():
    sim, coords = _booted_sim("priority")
    best = _best_limestonesite_coord(sim, coords)
    if best is None:
        pytest.skip("no carbonate")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)


def test_quarry_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    best = _best_limestonesite_coord(sim, coords)
    if best is None:
        pytest.skip("no carbonate")
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, best)
    dec = cog.Decision(int(ActionKind.QUARRY), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_limestone[0]) == 0.0


def test_quarry_fills_only_limestone_and_is_non_mutating():
    sim, coords = _booted_sim("orthogonal")
    best = _best_limestonesite_coord(sim, coords)
    if best is None:
        pytest.skip("no carbonate")
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    g_before = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
                for layer in geo.chunk_geology(sim, best).layers]
    _quarry_here(sim, 0)
    g_after = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
               for layer in geo.chunk_geology(sim, best).layers]
    assert g_before == g_after                              # geology unchanged
    assert float(sim.agents.inv_limestone[0]) > 0.0        # limestone filled…
    assert float(sim.agents.inv_stone[0]) == 0.0           # …only the carbonate store moved
    assert float(sim.agents.inv_clay[0]) == 0.0
    assert float(sim.agents.inv_ceramic[0]) == 0.0
    assert float(sim.agents.inv_pigment[0]) == 0.0


def test_quarry_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    best = _best_limestonesite_coord(a, ca)
    if best is None:
        pytest.skip("no carbonate")
    evs = []
    for s in (a, b):
        _calm_curious(s, 0)
        _stand(s, 0, best)
        evs.append(_quarry_here(s, 0)[-1])
    assert evs[0]["lime_class"] == evs[1]["lime_class"]
    assert evs[0]["lime_grade"] == evs[1]["lime_grade"]
    assert evs[0]["limestone_kg"] == evs[1]["limestone_kg"]
    assert abs(float(a.agents.inv_limestone[0]) - float(b.agents.inv_limestone[0])) < 1e-12
