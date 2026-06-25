"""Invariants — the agent loop CONSUMES C14 cryoclasty (D12 wire, 2026-06-25).

Context (AUDIT-DELTA-2026-06-23, risk **D12 / R0**): the C1→C20 capability arc was
a library with no player. DRINK/C3 (R-J13-4) and KNAP/C2 (R-J13-1) took the first two
bites. R-J14-1 (P0) of the J+14 delta asked for a 3rd capability wired through the
canonical ADR-0009 ``perceive→decide→act→remember`` loop. This is it: emergent
gathering of frost-shattered surface clasts.

Emergent gelifract gathering:
- ``cognition._seek_frost_clast`` lets a survival-satisfied, curious agent that SEES a
  workable frost scree (``cryoclasty.best_frost_clast_near``) walk there and GATHER a
  ready clast instead of wandering — utility-based action selection, nothing scripted.
  It is tried *before* ``_seek_toolstone``: where the cold has already broken sound
  clasts loose, stooping to gather beats knapping an in-situ outcrop (less effort).
- ``cognition.apply_decision``'s new ``ActionKind.GATHER`` branch picks up the surface
  clasts the agent stands on into raw ``inv_stone`` + a cutting edge (``inv_tools``)
  whose size scales with the clast's TRUE ``clast_quality`` (C2 base × frost fabric
  response) — cold obsidian gives razor flakes, a cold granite slope gives edgeless
  grus. The agent learns the cold+rock→edge link by acting (mensonge #5).

What this file proves:
1. The loop is genuinely gated on C14 (no cue cache → inert; no scripted fallback).
2. A curious agent on / near a perceived scree chooses GATHER / WALK_TO, not random EXPLORE.
3. The yield is the world's truth: cold obsidian out-yields cold granite grus.
4. « le monde ne ment jamais » — gathering where no clasts are perceived yields nothing.
5. Survival always outranks gathering (a critically thirsty agent drinks, never gathers).
6. GATHER is surface only — back-compat inert with the old ``sim=None`` signature.
7. Coexistence: with BOTH C2 and C14 installed, the agent prefers GATHER over KNAP.

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
from engine.world_genesis import GenesisParams, generate_world     # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim         # noqa: E402
from engine import geology as geo                                  # noqa: E402
from engine.geology import StrataLayer, ChunkGeology               # noqa: E402
from engine import frost_weathering as fw                          # noqa: E402
from engine import lithic_outcrop as lo                            # noqa: E402
from engine import cognition as cog                                # noqa: E402
from engine.cognition import Observation, PerceivedTarget          # noqa: E402
from engine.agent import ActionKind, DriveKind                     # noqa: E402
from engine.world import CHUNK_SIDE_M                              # noqa: E402
import engine.cryoclasty as cc                                     # noqa: E402

# Several arc capabilities globally REASSIGN ``cog.decide`` / ``cog.apply_decision``
# with monkey-patch wrappers and never restore them. The D12 wire under test lives in
# the ORIGINAL functions; we capture them at import (before any installer runs) and
# exercise those directly — the correct unit scope, immune to cross-test pollution.
_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

_TUNDRA = 2
SEED = 0xB0          # boreal/tundra continent — strongest periglacial cell on the map


# ---------------------------------------------------------------------------
# Fixtures — a real cold-anchored Genesis world (reuses the exact frost-region
# anchoring of test_cryoclasty) with a controlled scree column injected.
# ---------------------------------------------------------------------------

def _layer(top, bottom, rock="granite", density=2600.0, ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=density, ore_mix=dict(ore or {}))


_OBSIDIAN = [_layer(0.0, 6.0, rock="obsidian", density=2400.0)]
_GRANITE = [_layer(0.0, 800.0, rock="granite")]


def _coldest_origin_km(world):
    """Deterministic argmax-FCI land cell → macro km (verbatim from test_cryoclasty)."""
    R = world.params.resolution
    cell_km = world.params.map_size_km / R
    fci = fw.compute_frost_cracking_index(world.temp_c, world.precip_mm, world.biome)
    land = world.elevation_m > world.params.sea_level_m
    fci_land = np.where(land, fci, -1.0)
    iy, ix = np.unravel_index(int(np.argmax(fci_land)), fci_land.shape)
    return (float((ix + 0.5) * cell_km), float((iy + 0.5) * cell_km))


def _booted_cold_sim(name: str, seed: int = SEED, *, with_c2: bool = False):
    world = generate_world(GenesisParams(seed=seed, resolution=128, n_plates=8))
    origin = _coldest_origin_km(world)
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8),
                          sim_origin_macro_km=origin)
    geo.install_geology(sim)
    cc.install_cryoclasty(sim)
    if with_c2:
        lo.install_lithic_outcrop(sim)
    sim._life_emergence = None
    return sim


def _streamed_coords(sim, grid: int = 12):
    coords = []
    for cx in range(grid):
        for cy in range(grid):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return coords


def _inject_scree(sim, coord, layers, biome=_TUNDRA):
    """Plant a controlled shallow column at ``coord`` and bust the cue cache so
    C14 re-derives the gelifract from the fixture."""
    ch = sim.streamer.get(0, coord)
    assert ch is not None
    ch.biome = np.full(np.asarray(ch.biome).shape, biome, dtype=np.asarray(ch.biome).dtype)
    g = ChunkGeology(coord=tuple(int(c) for c in coord), layers=list(layers))
    sim._geology_state.chunks[tuple(int(c) for c in coord)] = g
    sim._cryoclasty_cue_cache.clear()
    if getattr(sim, "_lithic_cue_cache", None) is not None:
        sim._lithic_cue_cache.clear()
    return ch


def _stand_agent_on(sim, row, coord):
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
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal", "inv_tools"):
        getattr(sim.agents, inv)[row] = 0.0
    sim.agents.memory[row].known_frost_clast_locations.clear()


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


# An off-map, un-streamed position: no chunk is cached here, so no scree is
# perceivable — the deterministic "the world shows nothing here" location.
def _far_unstreamed(grid: int = 12):
    return ((grid + 50 + 0.5) * CHUNK_SIDE_M, (grid + 50 + 0.5) * CHUNK_SIDE_M)


# ---------------------------------------------------------------------------
# 1. Gate — without C14 installed there is no frost-clast perception at all
# ---------------------------------------------------------------------------

def test_seek_frost_clast_inert_without_c14():
    sim = _booted_cold_sim("gate")
    coords = _streamed_coords(sim)
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, coords[len(coords) // 2])
    sim._cryoclasty_cue_cache = None          # strip the C14 capability
    assert cog._seek_frost_clast(sim.agents, 0, _obs(sim, 0), sim) is None


# ---------------------------------------------------------------------------
# 2. Choose — a curious agent perceiving a scree heads to it / gathers it
# ---------------------------------------------------------------------------

def test_curious_agent_on_scree_decides_to_gather():
    sim = _booted_cold_sim("gather")
    coords = _streamed_coords(sim)
    target = coords[len(coords) // 2]
    _inject_scree(sim, target, _OBSIDIAN)
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, target)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.GATHER)


def test_curious_agent_walks_toward_perceived_scree():
    """Agent standing on barren grus (own chunk skipped) walks toward a workable
    scree it perceives nearby — WALK_TO, not random EXPLORE."""
    sim = _booted_cold_sim("walk")
    coords = _streamed_coords(sim)
    cx, cy, _ = coords[len(coords) // 2]
    here = (cx, cy, 0)
    _inject_scree(sim, here, _GRANITE)        # own chunk → barren grus (skipped)
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, here)
    best = cc.best_frost_clast_near(sim, 0, perception_radius_m=cog.FROST_CLAST_PERCEPT_M)
    if best is None:                          # no workable neighbour in sight: skip
        pytest.skip("no perceivable workable scree near the grus fixture")
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)
    assert abs(dec.target_x - (best.coord[0] + 0.5) * CHUNK_SIDE_M) < 1e-3
    assert abs(dec.target_y - (best.coord[1] + 0.5) * CHUNK_SIDE_M) < 1e-3


def test_curious_agent_without_scree_falls_back_to_explore():
    sim = _booted_cold_sim("explore")
    _calm_curious(sim, 0)
    fx, fy = _far_unstreamed()                # nothing streamed → nothing perceived
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.EXPLORE)


# ---------------------------------------------------------------------------
# 3. Act — GATHER picks up the scree into stone + a quality-scaled cutting edge
# ---------------------------------------------------------------------------

def _gather_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.GATHER), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


def test_gathering_obsidian_yields_stone_tool_and_memory():
    sim = _booted_cold_sim("yield")
    target = _streamed_coords(sim)[len(_streamed_coords(sim)) // 2]
    _inject_scree(sim, target, _OBSIDIAN)
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, target)
    ev = _gather_here(sim, 0)
    assert float(sim.agents.inv_stone[0]) > 0.0          # raw clasts gathered
    assert float(sim.agents.inv_tools[0]) > 0.0          # a real cutting edge
    assert len(sim.agents.memory[0].known_frost_clast_locations) == 1
    assert ev and ev[-1]["kind"] == "gather" and ev[-1]["tool_gain"] > 0.0


def test_tool_yield_scales_with_true_quality_obsidian_beats_grus():
    """D12 bite: identical GATHER action, two cold screes. The cutting edge tracks
    the cue's TRUE clast_quality — cold obsidian (workable) must out-yield cold
    granite grus (barren). A flat yield would mean the loop ignores C14."""
    sim = _booted_cold_sim("scale")
    target = _streamed_coords(sim)[len(_streamed_coords(sim)) // 2]

    _inject_scree(sim, target, _OBSIDIAN)
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, target)
    _gather_here(sim, 0)
    obs_tool, obs_stone = float(sim.agents.inv_tools[0]), float(sim.agents.inv_stone[0])

    _inject_scree(sim, target, _GRANITE)
    _calm_curious(sim, 1)
    px, py = _stand_agent_on(sim, 1, target)
    _gather_here(sim, 1)
    gra_tool, gra_stone = float(sim.agents.inv_tools[1]), float(sim.agents.inv_stone[1])

    assert obs_stone == gra_stone > 0.0          # same raw mass gathered
    assert obs_tool > gra_tool >= 0.0            # but obsidian's edge is far better
    grus = cc.prospect_frost_clasts(sim, px, py)
    assert grus is not None and grus.workable is False   # granite scree is barren


# ---------------------------------------------------------------------------
# 4. « Le monde ne ment jamais » — no perceived scree yields nothing, unremembered
# ---------------------------------------------------------------------------

def test_gathering_where_no_scree_yields_nothing():
    sim = _booted_cold_sim("barren")
    _calm_curious(sim, 0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert cc.prospect_frost_clasts(sim, fx, fy) is None
    dec = cog.Decision(int(ActionKind.GATHER), fx, fy, 0.5)
    _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick, sim=sim)
    assert float(sim.agents.inv_stone[0]) == 0.0
    assert float(sim.agents.inv_tools[0]) == 0.0
    assert len(sim.agents.memory[0].known_frost_clast_locations) == 0


# ---------------------------------------------------------------------------
# 5. Survival always outranks gathering
# ---------------------------------------------------------------------------

def test_critical_thirst_outranks_gathering():
    sim = _booted_cold_sim("priority")
    target = _streamed_coords(sim)[len(_streamed_coords(sim)) // 2]
    _inject_scree(sim, target, _OBSIDIAN)
    _calm_curious(sim, 0)
    px, py = _stand_agent_on(sim, 0, target)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95                     # critical
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)              # never GATHER


# ---------------------------------------------------------------------------
# 6. Back-compat — GATHER with the old 5-arg signature is inert, never crashes
# ---------------------------------------------------------------------------

def test_gather_without_sim_is_inert():
    sim = _booted_cold_sim("backcompat")
    target = _streamed_coords(sim)[len(_streamed_coords(sim)) // 2]
    _inject_scree(sim, target, _OBSIDIAN)
    _calm_curious(sim, 0)
    px, py = _stand_agent_on(sim, 0, target)
    dec = cog.Decision(int(ActionKind.GATHER), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_stone[0]) == 0.0
    assert float(sim.agents.inv_tools[0]) == 0.0


# ---------------------------------------------------------------------------
# 7. Coexistence — with BOTH C2 and C14 installed, the agent prefers GATHER
# ---------------------------------------------------------------------------

def test_gather_preferred_over_knap_when_both_installed():
    """Frost did the breaking: where a cold scree of workable clasts lies at the
    agent's feet, gathering (C14) is tried before knapping the outcrop (C2)."""
    sim = _booted_cold_sim("coexist", with_c2=True)
    target = _streamed_coords(sim)[len(_streamed_coords(sim)) // 2]
    _inject_scree(sim, target, _OBSIDIAN)
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, target)
    # both capabilities perceive the same obsidian; the loop must choose GATHER.
    assert cc.best_frost_clast_near(sim, 0, cog.FROST_CLAST_PERCEPT_M) is not None
    assert lo.best_toolstone_near(sim, 0, perception_radius_m=cog.TOOLSTONE_PERCEPT_M) is not None
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.GATHER)
