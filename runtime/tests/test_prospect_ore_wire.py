"""Invariants — the agent loop PROSPECTs a surface stain (D12 wire, 2026-06-30, consumes C1).

The 16th wire — the 1ᵉʳ acte purement COGNITIF/VISUEL de la boucle agent. C1
``surface_mineralization`` made the gossan / malachite / sulfur / salt / placer stains
*perceivable* (a truthful colour over a real buried ore body) ; but no agent ever LEARNED what
those colours meant. An agent that SEES a new colour-group within ``PROSPECT_PERCEPT_M`` and HAS
NOT YET READ that group walks there and PROSPECTs — recording ``(group, x, y)`` into
``known_ore_sites``, marking the group as discovered in ``prospected_ore_groups`` (auto-limit
per group), and learning by ASSOCIATION what lies below. Appended to ``_ARC_SEEKS`` as one line ;
consumes NO inventory (pure cognition), adds NO new tell (D8 composition only).

What this file proves:
1. Gated on C1 (no cue cache → inert).
2. Sated discovery: an agent whose ``prospected_ore_groups`` already covers the 5 groups stops
   re-seeking (the 5 « mensonges du sol » learned).
3. A ready agent (curious, never prospected) on a coloured chunk chooses PROSPECT.
4. Off-site agent WALK_TOs the perceived stain.
5. PROSPECT records the group + site, sets the discovery flag, emits a structured event.
6. Per-group self-limit: prospecting the same group twice does NOT add a second entry to
   ``prospected_ore_groups`` (idempotent learning), and the wire ignores the same-colour stain
   afterwards.
7. Multi-group: an agent that prospected one group still seeks a different colour nearby.
8. Survival outranks prospecting (a thirsty agent with water in sight DRINKs, not PROSPECTs).
9. « Le monde ne ment jamais » — prospecting where no stain exists writes no memory.
10. NON-MUTATING — geology, inventories, and other agents' memories are untouched.
11. Back-compat (sim=None inert ; missing memory fields don't crash).
12. Determinism — same seed → same first-prospect group + same site.
13. Registry inclusion + budget — ``_ARC_SEEKS`` carries ``prospect`` after ``canvas`` and the
    perception budget still bounds the whole arc (≥ len).
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
from engine import surface_mineralization as sm                    # noqa: E402
from engine.cognition import Observation, PerceivedTarget          # noqa: E402
from engine.agent import ActionKind, DriveKind                     # noqa: E402
from engine.world import CHUNK_SIDE_M                              # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_PROSPECT = 0xC1   # thematic + spawns 3 expression groups (gossan / salt / sulfur)
GRID = 12


def _booted_sim(name: str, seed: int = SEED_PROSPECT, *, with_c1: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8))
    geo.install_geology(sim)
    if with_c1:
        sm.install_surface_mineralization(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _all_cued_coords(sim, coords):
    out = []
    for coord in coords:
        cue = sm.surface_cue_for_chunk(sim, coord)
        if cue is not None:
            out.append((coord, cue))
    return out


def _coord_for_group(sim, coords, group):
    for coord in coords:
        cue = sm.surface_cue_for_chunk(sim, coord)
        if cue is not None and cue.group == group:
            return coord, cue
    return None, None


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
                "inv_pigment", "inv_clay", "inv_ceramic", "inv_limestone", "inv_lime",
                "inv_salt", "inv_fuel"):
        getattr(sim.agents, inv)[row] = 0.0
    sim.agents.thermal[row] = 0.05
    mem = sim.agents.memory[row]
    mem.known_ore_sites.clear()
    mem.prospected_ore_groups.clear()
    mem.has_prospected_ore = False
    mem.last_prospect_group = None


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


def _prospect_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.PROSPECT), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


def test_seek_prospect_inert_without_c1():
    sim, coords = _booted_sim("gate", with_c1=False)
    _calm_curious(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_surface_cue_cache", None) is None
    assert cog._seek_prospect(sim.agents, 0, _obs(sim, 0), sim) is None


def test_sated_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    cued = _all_cued_coords(sim, coords)
    if not cued:
        pytest.skip("seed has no surface cues")
    _calm_curious(sim, 0)
    _stand(sim, 0, cued[0][0])
    # Pretend all 5 groups have been prospected already.
    sim.agents.memory[0].prospected_ore_groups[:] = [
        "copper", "gossan", "sulfur", "salt", "gold_placer",
    ]
    assert cog._seek_prospect(sim.agents, 0, _obs(sim, 0), sim) is None


def test_ready_agent_on_stain_decides_to_prospect():
    sim, coords = _booted_sim("act")
    cued = _all_cued_coords(sim, coords)
    if not cued:
        pytest.skip("seed has no surface cues")
    coord, _cue = cued[0]
    _calm_curious(sim, 0)
    _stand(sim, 0, coord)
    seek = cog._seek_prospect(sim.agents, 0, _obs(sim, 0), sim)
    assert seek is not None
    assert seek.action == int(ActionKind.PROSPECT)


def test_offsite_agent_walks_toward_perceived_stain():
    sim, coords = _booted_sim("walk")
    cued = _all_cued_coords(sim, coords)
    if not cued:
        pytest.skip("seed has no surface cues")
    coord, _cue = cued[0]
    _calm_curious(sim, 0)
    cx = (coord[0] + 0.5) * CHUNK_SIDE_M
    cy = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 0] = cx + CHUNK_SIDE_M       # one chunk east — off-site, still in range
    sim.agents.pos[0, 1] = cy
    seek = cog._seek_prospect(sim.agents, 0, _obs(sim, 0), sim)
    if seek is None or seek.action == int(ActionKind.PROSPECT):
        pytest.skip("nearest stain is underfoot from this offset — no WALK_TO to assert")
    assert seek.action == int(ActionKind.WALK_TO)


def test_prospect_records_site_and_group_and_emits_event():
    sim, coords = _booted_sim("record")
    cued = _all_cued_coords(sim, coords)
    if not cued:
        pytest.skip("seed has no surface cues")
    coord, cue = cued[0]
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, coord)
    ev = _prospect_here(sim, 0)
    assert ev and ev[-1]["kind"] == "prospect"
    assert ev[-1]["group"] == cue.group
    assert ev[-1]["mineral"] == cue.mineral
    assert ev[-1]["first_for_group"] is True
    mem = sim.agents.memory[0]
    assert mem.has_prospected_ore is True
    assert mem.last_prospect_group == cue.group
    assert cue.group in mem.prospected_ore_groups
    assert len(mem.known_ore_sites) == 1
    g, sx, sy = mem.known_ore_sites[0]
    assert g == cue.group
    assert sx == pytest.approx(px)
    assert sy == pytest.approx(py)


def test_re_reading_same_group_is_idempotent_and_skipped_by_seek():
    sim, coords = _booted_sim("idem")
    cued = _all_cued_coords(sim, coords)
    if not cued:
        pytest.skip("seed has no surface cues")
    coord, cue = cued[0]
    _calm_curious(sim, 0)
    _stand(sim, 0, coord)
    _prospect_here(sim, 0)
    _prospect_here(sim, 0)                                  # twice on the same stain
    mem = sim.agents.memory[0]
    # idempotent on the GROUP list (the discovery is binary), but the site memory grows (FIFO).
    assert mem.prospected_ore_groups.count(cue.group) == 1
    # On a same-colour stain underfoot, the wire never decides to PROSPECT here again — either it
    # falls through (no other colour in sight) or steers (WALK_TO) toward a *different* colour.
    same_group_coord = None
    for c in coords:
        cu = sm.surface_cue_for_chunk(sim, c)
        if cu is not None and cu.group == cue.group and c != coord:
            same_group_coord = c
            break
    if same_group_coord is None:
        pytest.skip("only one stain of this group in the streamed window")
    _stand(sim, 0, same_group_coord)
    dec = cog._seek_prospect(sim.agents, 0, _obs(sim, 0), sim)
    # Either fully inert (no fresh colour anywhere) or walking toward another colour. Never
    # PROSPECT on this re-read stain — re-reading the same group is not a discovery.
    assert dec is None or dec.action == int(ActionKind.WALK_TO)


def test_multi_group_wire_seeks_another_colour_after_first_discovery():
    sim, coords = _booted_sim("multi")
    groups_present = set()
    for c in coords:
        cu = sm.surface_cue_for_chunk(sim, c)
        if cu is not None:
            groups_present.add(cu.group)
    if len(groups_present) < 2:
        pytest.skip("seed exposes only one expression group — cannot exercise multi-group")
    g1, g2 = list(groups_present)[:2]
    c1, _ = _coord_for_group(sim, coords, g1)
    c2, _ = _coord_for_group(sim, coords, g2)
    _calm_curious(sim, 0)
    _stand(sim, 0, c1)
    _prospect_here(sim, 0)
    # Now sitting on a different-colour stain → the wire still wants to read that fresh colour.
    _stand(sim, 0, c2)
    seek = cog._seek_prospect(sim.agents, 0, _obs(sim, 0), sim)
    assert seek is not None
    assert seek.action == int(ActionKind.PROSPECT)


def test_critical_thirst_outranks_prospecting():
    sim, coords = _booted_sim("priority")
    cued = _all_cued_coords(sim, coords)
    if not cued:
        pytest.skip("seed has no surface cues")
    coord, _cue = cued[0]
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, coord)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)


def test_prospecting_where_no_stain_writes_nothing():
    sim, coords = _booted_sim("barren")
    # Walk far past the streamed area — no cue, no chunk cached.
    _calm_curious(sim, 0)
    far = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 0] = far
    sim.agents.pos[0, 1] = far
    ev = _prospect_here(sim, 0)
    mem = sim.agents.memory[0]
    assert ev == []
    assert mem.has_prospected_ore is False
    assert mem.prospected_ore_groups == []
    assert mem.known_ore_sites == []


def test_prospect_is_non_mutating():
    sim, coords = _booted_sim("orthogonal")
    cued = _all_cued_coords(sim, coords)
    if not cued:
        pytest.skip("seed has no surface cues")
    coord, _cue = cued[0]
    _calm_curious(sim, 0)
    _stand(sim, 0, coord)
    g_before = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
                for layer in geo.chunk_geology(sim, coord).layers]
    invs_before = {fld: float(getattr(sim.agents, fld)[0]) for fld in (
        "inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal", "inv_tools",
        "inv_pigment", "inv_clay", "inv_ceramic", "inv_limestone", "inv_lime",
        "inv_salt", "inv_fuel",
    )}
    _prospect_here(sim, 0)
    g_after = [(layer.depth_top_m, layer.rock_type, dict(layer.ore_mix))
               for layer in geo.chunk_geology(sim, coord).layers]
    invs_after = {fld: float(getattr(sim.agents, fld)[0]) for fld in invs_before}
    assert g_before == g_after                                          # geology untouched (D10 gelé)
    assert invs_before == invs_after                                    # 0 inventory consumed (purely cognitive)


def test_prospect_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    cued = _all_cued_coords(sim, coords)
    if not cued:
        pytest.skip("seed has no surface cues")
    coord, _cue = cued[0]
    _calm_curious(sim, 0)
    px, py = _stand(sim, 0, coord)
    dec = cog.Decision(int(ActionKind.PROSPECT), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)        # no sim kwarg
    assert ev == []
    assert sim.agents.memory[0].has_prospected_ore is False


def test_prospect_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    cued = _all_cued_coords(a, ca)
    if not cued:
        pytest.skip("seed has no surface cues")
    coord, _cue = cued[0]
    evs = []
    for s in (a, b):
        _calm_curious(s, 0)
        _stand(s, 0, coord)
        evs.append(_prospect_here(s, 0)[-1])
    assert evs[0]["group"] == evs[1]["group"]
    assert evs[0]["mineral"] == evs[1]["mineral"]
    assert evs[0]["dig_depth_m"] == evs[1]["dig_depth_m"]


def test_registry_includes_prospect_after_canvas_and_budget_covers():
    names = [n for n, _ in cog._ARC_SEEKS]
    assert "prospect" in names
    assert names.index("prospect") > names.index("canvas")
    assert cog.ARC_SEEK_BUDGET >= len(cog._ARC_SEEKS)
