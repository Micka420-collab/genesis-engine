"""Invariants — DRINK consults water potability (R-J13-4, the live emergence-breach fix).

Before this fix, the DRINK action relieved thirst **unconditionally** from `chunk.water`,
so an agent drinking the OCEAN hydrated exactly like a freshwater spring — the world told
the truth in *perception* (C3 `water_potability`: seawater tastes briny/undrinkable) but
**lied in behaviour**. This is the single place the sacred rule « le monde ne ment jamais »
was actively violated in conduct, flagged P1 in AUDIT-DELTA-2026-06-23.

The fix composes C3 in `cognition.apply_decision`'s DRINK branch:
- fresh water  → full hydration (factor +1.0);
- brackish-but-drinkable → partial (down to +0.4 at the potability ceiling);
- sea / brine  → **net dehydration** (factor < 0, thirst RISES) — the osmotic load.

It is also the **first real consumption of a substrate capability (C3) by the agent
loop** — a concrete bite out of risk D12 (the C1→C20 arc had no agent consumer). This
file proves both: the physiology is now honest, AND C3 is genuinely consulted (a result
the biome-only fallback could not produce).

Nothing is scripted: the agent still *chooses* to drink; it discovers by acting that
brine harms. Determinism preserved (pure functions, no RNG).
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

import pytest                                                       # noqa: E402

from engine.sim import Simulation, SimConfig                        # noqa: E402
from engine.world_genesis import GenesisParams                      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine import water_potability as wp                           # noqa: E402
from engine import cognition as cog                                 # noqa: E402
from engine.agent import ActionKind                                 # noqa: E402
from engine.world import Biome, CHUNK_SIDE_M, world_to_cell  # noqa: E402

SEED = 0x6EA   # any seed — the test forces the cell's biome/water/height itself


# ---------------------------------------------------------------------------
# Pure SSOT — the hydration curve (composes C3 thresholds)
# ---------------------------------------------------------------------------

def test_fresh_water_fully_hydrates():
    assert cog._hydration_factor(0.0, True) == 1.0
    assert cog._hydration_factor(wp.FRESH_MAX_PPT, True) == 1.0


def test_brackish_drinkable_partially_hydrates():
    f = cog._hydration_factor(wp.POTABLE_MAX_PPT, True)   # marginal, still potable
    assert 0.3 < f < 1.0                                  # helps, but less than fresh


def test_seawater_net_dehydrates():
    """Drinking seawater costs the body more water than it gives — factor strongly < 0."""
    assert cog._hydration_factor(wp.SEAWATER_PPT, False) == pytest.approx(-1.0)
    mid = cog._hydration_factor((wp.POTABLE_MAX_PPT + wp.SEAWATER_PPT) / 2.0, False)
    assert -1.0 < mid < 0.0                               # less salt → less harm, still harm


def test_factor_is_monotone_in_salinity():
    fresh = cog._hydration_factor(0.0, True)
    brack = cog._hydration_factor(wp.POTABLE_MAX_PPT, True)
    sea = cog._hydration_factor(wp.SEAWATER_PPT, False)
    assert fresh > brack > 0.0 > sea


# ---------------------------------------------------------------------------
# Scoping — without the C3 salinity capability, drinking is legacy full hydration
# ---------------------------------------------------------------------------

def _fake_chunk(biome_id):
    return SimpleNamespace(biome=np.full((4, 4), int(biome_id), dtype=np.uint8))


def test_no_salinity_capability_means_legacy_full_hydration():
    """When C3 is not installed there is no salinity truth in the world, so the fix is
    inert (factor 1.0) for ANY biome — deliberately: ``Biome.OCEAN == 0`` cannot be told
    apart from an unpopulated all-zero biome array, so a biome-only fallback would
    falsely dehydrate inland drinkers in lightweight sims. The breach is fixed where
    salinity is actually modelled (C3 installed)."""
    assert cog._drink_factor(None, _fake_chunk(Biome.OCEAN), (0, 0, 0)) == 1.0
    assert cog._drink_factor(None, _fake_chunk(Biome.GRASSLAND), (0, 0, 0)) == 1.0


# ---------------------------------------------------------------------------
# Integration — apply_decision DRINK plumbing on a real bootstrapped chunk
# ---------------------------------------------------------------------------

def _sim():
    cfg = SimConfig(name="drink", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    wp.install_water_potability(sim)   # install C3 at SETUP (never mid-loop)
    coord = None
    for cx in range(8):
        for cy in range(8):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                coord = (cx, cy, 0)
                break
        if coord is not None:
            break
    assert coord is not None, "no chunk streamed for the test region"
    geo.chunk_geology(sim, coord)
    return sim, coord


def _place_agent_on_cell(sim, coord, *, biome_id, height_m, thirst=0.5):
    """Force the chunk's biome/height, flood one cell, and stand agent 0 on it."""
    chunk = sim.streamer.get(0, coord)
    chunk.biome[:] = int(biome_id)
    if hasattr(chunk, "height"):
        np.asarray(chunk.height)[:] = float(height_m)
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    cx, cy = world_to_cell(px, py, coord)
    chunk.water[cy, cx] = 50.0
    sim.agents.pos[0, 0] = px
    sim.agents.pos[0, 1] = py
    sim.agents.thirst[0] = float(thirst)
    sim.agents.inv_water[0] = 0.0
    if hasattr(sim.agents, "memory") and sim.agents.memory[0] is not None:
        sim.agents.memory[0].known_water_locations.clear()
    # ensure C3 recomputes against the forced biome
    cache = getattr(sim, "_water_cue_cache", None)
    if isinstance(cache, dict):
        cache.pop(tuple(int(c) for c in coord), None)
    return chunk


def _drink(sim, coord, *, with_sim):
    dec = cog.Decision(int(ActionKind.DRINK),
                       float(sim.agents.pos[0, 0]), float(sim.agents.pos[0, 1]), 0.95)
    cog.apply_decision(sim.agents, 0, dec, sim.streamer, sim.tick,
                       sim=(sim if with_sim else None))


def test_drinking_fresh_inland_water_relieves_thirst():
    """Land, above the coastal margin, drunk via the sim=None fallback → hydrates."""
    sim, coord = _sim()
    _place_agent_on_cell(sim, coord, biome_id=Biome.GRASSLAND, height_m=400.0, thirst=0.5)
    _drink(sim, coord, with_sim=False)
    assert sim.agents.thirst[0] < 0.5                     # thirst relieved
    assert sim.agents.inv_water[0] > 0.0                  # canteen filled
    if hasattr(sim.agents, "memory") and sim.agents.memory[0] is not None:
        assert len(sim.agents.memory[0].known_water_locations) == 1   # remembered


def test_drinking_ocean_water_does_not_relieve_thirst():
    """Drinking the OCEAN must NOT hydrate — it net-dehydrates (the breach, fixed)."""
    sim, coord = _sim()
    _place_agent_on_cell(sim, coord, biome_id=Biome.OCEAN, height_m=0.0, thirst=0.5)
    _drink(sim, coord, with_sim=True)
    assert sim.agents.thirst[0] > 0.5                     # thirst WORSE, not better
    assert sim.agents.inv_water[0] == 0.0                 # no drinkable water stored
    if hasattr(sim.agents, "memory") and sim.agents.memory[0] is not None:
        assert len(sim.agents.memory[0].known_water_locations) == 0   # brine not remembered


def test_c3_is_actually_consulted_by_the_agent_loop():
    """Definitive D12 bite: a sea-level LAND chunk (estuary) hydrates under the biome-only
    fallback (+1.0) but DEHYDRATES once C3 is consulted (coastal → ~35 ppt, unpotable).
    The opposite outcomes on identical cell state prove the agent loop genuinely consumes
    the C3 capability — not just the cheap ocean fallback."""
    # (a) with sim → C3 coastal salinity makes it unpotable → thirst rises
    sim_a, coord_a = _sim()
    _place_agent_on_cell(sim_a, coord_a, biome_id=Biome.GRASSLAND, height_m=0.0, thirst=0.5)
    cue = wp.water_cue_for_chunk(sim_a, coord_a)
    assert cue is not None and cue.potable is False       # C3 says: not drinkable here
    _drink(sim_a, coord_a, with_sim=True)
    assert sim_a.agents.thirst[0] > 0.5                   # C3 path: net dehydration

    # (b) identical cell, sim=None fallback → biome is land → hydrates (would be the lie)
    sim_b, coord_b = _sim()
    _place_agent_on_cell(sim_b, coord_b, biome_id=Biome.GRASSLAND, height_m=0.0, thirst=0.5)
    _drink(sim_b, coord_b, with_sim=False)
    assert sim_b.agents.thirst[0] < 0.5                   # fallback hydrates — proves (a)≠(b)


def test_apply_decision_backcompat_without_sim():
    """apply_decision still works with the old 5-arg signature (sim defaults to None)."""
    sim, coord = _sim()
    _place_agent_on_cell(sim, coord, biome_id=Biome.GRASSLAND, height_m=400.0, thirst=0.5)
    dec = cog.Decision(int(ActionKind.DRINK),
                       float(sim.agents.pos[0, 0]), float(sim.agents.pos[0, 1]), 0.95)
    cog.apply_decision(sim.agents, 0, dec, sim.streamer, sim.tick)   # no sim kwarg
    assert sim.agents.thirst[0] < 0.5
