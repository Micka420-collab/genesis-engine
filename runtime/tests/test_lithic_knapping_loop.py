"""Invariants — the agent loop CONSUMES C2 lithic_outcrop (D12 wire, 2026-06-24).

Context (AUDIT-DELTA-2026-06-23, risk **D12 / R0**): the C1→C20 capability arc was
a library with no player — 20 truthful affordances that *no agent ever invoked* in a
simulation loop. The DRINK / C3 fix (R-J13-4) took the first bite by making an existing
action (drinking) honest. This wire takes the next: it gives the agent loop a *new
behaviour* driven by perceiving an arc capability.

Emergent stone-age knapping (R-J13-1):
- ``cognition._seek_toolstone`` lets a survival-satisfied, curious agent that SEES a
  knappable outcrop (``lithic_outcrop.best_toolstone_near``) walk to it and knap a flake
  instead of wandering at random — utility-based action selection, nothing scripted.
- ``cognition.apply_decision``'s new ``ActionKind.KNAP`` branch debits the outcrop the
  agent stands on into raw ``inv_stone`` + a cutting edge (``inv_tools``) whose size
  scales with the stone's TRUE ``knap_quality`` — obsidian gives razor tools, a
  quern-grade boulder barely any. The agent learns the stone→edge link by acting.

What this file proves:
1. The loop is genuinely gated on C2 (no cue cache → inert; no scripted fallback).
2. A curious agent on / near a perceived outcrop chooses KNAP / WALK_TO, not random EXPLORE.
3. The yield is the world's truth: obsidian out-yields granite (the cue is really read).
4. « le monde ne ment jamais » — knapping a barren spot (no cue) yields nothing, unremembered.
5. Survival always outranks tool-stone (a critically thirsty agent drinks, never knaps).
6. Back-compat: KNAP with the old ``sim=None`` signature is inert, never crashes.

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

from engine.sim import Simulation, SimConfig                       # noqa: E402
from engine.world_genesis import GenesisParams                     # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim         # noqa: E402
from engine import geology as geo                                  # noqa: E402
from engine.geology import StrataLayer, ChunkGeology               # noqa: E402
from engine import cognition as cog                                # noqa: E402
from engine.cognition import Observation, PerceivedTarget          # noqa: E402
from engine.agent import ActionKind, DriveKind                     # noqa: E402
from engine.world import CHUNK_SIDE_M                              # noqa: E402
import engine.lithic_outcrop as lo                                 # noqa: E402

# Several arc capabilities (knowledge_wiring, geology, metallurgy, …) globally
# REASSIGN ``cog.decide`` / ``cog.apply_decision`` with monkey-patch wrappers and
# never restore them, so a sibling test can leak a wrapper into this shared
# process. The D12 wire under test lives in the ORIGINAL functions; we capture
# them at import (collection time, before any installer runs) and exercise those
# directly — the correct unit scope, immune to cross-test pollution.
_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

_ARID = 7  # HOT_DESERT — max outcrop visibility, never masks


# ---------------------------------------------------------------------------
# Fixtures — a real booted Genesis world with a controlled outcrop (reuses the
# exact injection plumbing of test_lithic_outcrop).
# ---------------------------------------------------------------------------

def _layer(top, bottom, rock="shale", density=2400.0, ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=density, ore_mix=dict(ore or {}))


def _booted_sim(name: str, seed: int = 0xC0DE_C2A6):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF, founders=4,
                    max_agents=20, bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=64,
                                                       n_plates=8))
    geo.install_geology(sim)
    lo.install_lithic_outcrop(sim)
    # Disable the optional life-emergence appraisal injection so decide() ordering
    # is exercised in isolation (deterministic, no mate hijack).
    sim._life_emergence = None
    return sim


def _streamed_coords(sim, grid: int = 6):
    coords = []
    for cx in range(grid):
        for cy in range(grid):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return coords


def _inject_outcrop(sim, coord, layers, biome=_ARID):
    """Plant a controlled shallow column + visible biome at ``coord``, then bust
    the cue cache so C2 re-derives from the fixture."""
    geo.install_geology(sim)
    lo.install_lithic_outcrop(sim)
    ch = sim.streamer.get(0, coord)
    assert ch is not None
    ch.biome = np.full(np.asarray(ch.biome).shape, biome, dtype=np.asarray(ch.biome).dtype)
    g = ChunkGeology(coord=tuple(int(c) for c in coord), layers=list(layers))
    sim._geology_state.chunks[tuple(int(c) for c in coord)] = g
    sim._lithic_cue_cache.clear()
    return ch


def _stand_agent_on(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _calm_curious(sim, row):
    """Make ``row`` survival-satisfied and curious so decide() reaches the
    exploration fall-through (where tool-stone foraging lives)."""
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal",
                "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal", "inv_tools"):
        getattr(sim.agents, inv)[row] = 0.0
    sim.agents.memory[row].known_toolstone_locations.clear()


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


_OBSIDIAN_FLOAT = [_layer(0.0, 1.0, rock="sandstone", ore={"obsidian": 0.05}),
                   _layer(1.0, 6.0, rock="shale", ore={"obsidian": 0.05}),
                   _layer(6.0, 200.0, rock="limestone")]
_GRANITE_CROP = [_layer(0.0, 1.0, rock="shale"),
                 _layer(1.0, 5.0, rock="sandstone"),
                 _layer(5.0, 800.0, rock="granite")]
_BARREN = [_layer(0.0, 1.0, rock="shale"),
           _layer(1.0, 5.0, rock="sandstone"),
           _layer(5.0, 200.0, rock="limestone")]  # only soft/regolith → no cue


# ---------------------------------------------------------------------------
# 1. Gate — without C2 installed there is no tool-stone perception at all
# ---------------------------------------------------------------------------

def test_seek_toolstone_inert_without_c2():
    sim = _booted_sim("gate")
    coords = _streamed_coords(sim)
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, coords[len(coords) // 2])
    # strip the C2 capability from the world
    sim._lithic_cue_cache = None
    assert cog._seek_toolstone(sim.agents, 0, _obs(sim, 0), sim) is None


# ---------------------------------------------------------------------------
# 2. Choose — a curious agent perceiving an outcrop heads to it / knaps it
# ---------------------------------------------------------------------------

def test_curious_agent_on_outcrop_decides_to_knap():
    sim = _booted_sim("knap")
    target = _streamed_coords(sim)[len(_streamed_coords(sim)) // 2]
    _inject_outcrop(sim, target, _OBSIDIAN_FLOAT)
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, target)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.KNAP)


def test_curious_agent_walks_toward_perceived_outcrop():
    sim = _booted_sim("walk")
    coords = _streamed_coords(sim)
    # outcrop on one chunk, agent on an adjacent streamed chunk within sight
    cx, cy, _ = coords[len(coords) // 2]
    target = (cx, cy, 0)
    neigh = next(((nx, ny, 0) for nx, ny, _ in coords if (nx, ny) != (cx, cy)
                  and abs(nx - cx) <= 1 and abs(ny - cy) <= 1), None)
    if neigh is None:                       # tiny worlds: skip rather than lie
        import pytest
        pytest.skip("no adjacent streamed chunk for the walk fixture")
    _inject_outcrop(sim, target, _OBSIDIAN_FLOAT)
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, neigh)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.WALK_TO)
    # heads toward the outcrop's chunk centre, not a random heading
    assert abs(dec.target_x - (cx + 0.5) * CHUNK_SIDE_M) < 1e-3
    assert abs(dec.target_y - (cy + 0.5) * CHUNK_SIDE_M) < 1e-3


def test_curious_agent_without_outcrop_falls_back_to_explore():
    sim = _booted_sim("explore")
    target = _streamed_coords(sim)[len(_streamed_coords(sim)) // 2]
    _inject_outcrop(sim, target, _BARREN)         # no perceivable tool-stone
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, target)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0), sim=sim)
    assert dec.action == int(ActionKind.EXPLORE)  # plain wander, unchanged


# ---------------------------------------------------------------------------
# 3. Act — KNAP debits the outcrop into stone + a quality-scaled cutting edge
# ---------------------------------------------------------------------------

def _knap_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.KNAP), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


def test_knapping_obsidian_yields_stone_tool_and_memory():
    sim = _booted_sim("yield")
    target = _streamed_coords(sim)[len(_streamed_coords(sim)) // 2]
    _inject_outcrop(sim, target, _OBSIDIAN_FLOAT)
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, target)
    ev = _knap_here(sim, 0)
    assert float(sim.agents.inv_stone[0]) > 0.0          # raw stone gathered
    assert float(sim.agents.inv_tools[0]) > 0.0          # a real cutting edge
    assert len(sim.agents.memory[0].known_toolstone_locations) == 1
    assert ev and ev[-1]["kind"] == "knap" and ev[-1]["tool_gain"] > 0.0


def test_tool_yield_scales_with_true_quality_obsidian_beats_granite():
    """D12 bite: identical KNAP action, two stones. The cutting edge tracks the
    cue's TRUE knap_quality — obsidian (1.0) must out-yield granite (~0.40). A
    flat yield would mean the loop ignores C2; this proves it consults it."""
    sim = _booted_sim("scale")
    target = _streamed_coords(sim)[len(_streamed_coords(sim)) // 2]

    _inject_outcrop(sim, target, _OBSIDIAN_FLOAT)
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, target)
    _knap_here(sim, 0)
    obs_tool, obs_stone = float(sim.agents.inv_tools[0]), float(sim.agents.inv_stone[0])

    _inject_outcrop(sim, target, _GRANITE_CROP)
    _calm_curious(sim, 1)
    _stand_agent_on(sim, 1, target)
    _knap_here(sim, 1)
    gra_tool, gra_stone = float(sim.agents.inv_tools[1]), float(sim.agents.inv_stone[1])

    assert obs_stone == gra_stone > 0.0      # same raw mass gathered
    assert obs_tool > gra_tool > 0.0         # but obsidian's edge is far better


# ---------------------------------------------------------------------------
# 4. « Le monde ne ment jamais » — a barren spot yields nothing, unremembered
# ---------------------------------------------------------------------------

def test_knapping_barren_spot_yields_nothing():
    sim = _booted_sim("barren")
    target = _streamed_coords(sim)[len(_streamed_coords(sim)) // 2]
    _inject_outcrop(sim, target, _BARREN)            # soft/regolith only → no cue
    _calm_curious(sim, 0)
    _stand_agent_on(sim, 0, target)
    assert lo.prospect_toolstone(sim, *_stand_agent_on(sim, 0, target)) is None
    _knap_here(sim, 0)
    assert float(sim.agents.inv_stone[0]) == 0.0
    assert float(sim.agents.inv_tools[0]) == 0.0
    assert len(sim.agents.memory[0].known_toolstone_locations) == 0


# ---------------------------------------------------------------------------
# 5. Survival always outranks tool-stone foraging
# ---------------------------------------------------------------------------

def test_critical_thirst_outranks_knapping():
    """Standing on razor obsidian but dying of thirst with water in sight: the
    agent drinks. Tool-stone foraging lives strictly below survival drives."""
    sim = _booted_sim("priority")
    target = _streamed_coords(sim)[len(_streamed_coords(sim)) // 2]
    _inject_outcrop(sim, target, _OBSIDIAN_FLOAT)
    _calm_curious(sim, 0)
    px, py = _stand_agent_on(sim, 0, target)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95                     # critical
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)              # never KNAP


# ---------------------------------------------------------------------------
# 6. Back-compat — KNAP with the old 5-arg signature is inert, never crashes
# ---------------------------------------------------------------------------

def test_knap_without_sim_is_inert():
    sim = _booted_sim("backcompat")
    target = _streamed_coords(sim)[len(_streamed_coords(sim)) // 2]
    _inject_outcrop(sim, target, _OBSIDIAN_FLOAT)
    _calm_curious(sim, 0)
    px, py = _stand_agent_on(sim, 0, target)
    dec = cog.Decision(int(ActionKind.KNAP), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)  # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_stone[0]) == 0.0
    assert float(sim.agents.inv_tools[0]) == 0.0
