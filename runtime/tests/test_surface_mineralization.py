"""Invariants — Substrate capability : indices de surface minéralisée.

Couvre :
- Intégrité de la table d'expression (minéraux réels, groupes disjoints).
- Couleurs physiquement correctes (cuivre vert, gossan brun-rouge, etc.).
- Règles de profondeur / seuil de visibilité / masquage par biome.
- Priorité (signal diagnostique rare > chapeau de fer commun) et couche la
  plus haute qui domine la surface.
- **« Le monde ne ment jamais »** : tout indice émis correspond à une vraie
  couche peu profonde contenant le minéral — sur colonnes synthétiques ET
  sur monde Genesis réel.
- Déterminisme même-seed (bit-identique).
- Boucle de découverte émergente : prospecter → creuser → obtenir le minéral.
- Installation idempotente, coût tick nul (pas de hook sur sim.step).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

import numpy as np                                                 # noqa: E402

from engine.sim import Simulation, SimConfig                       # noqa: E402
from engine.world_genesis import GenesisParams                     # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim         # noqa: E402
from engine import geology as geo                                  # noqa: E402
from engine.geology import StrataLayer, ChunkGeology               # noqa: E402
from engine.mineral_catalog import MINERAL_BY_NAME                 # noqa: E402
from engine.world import CHUNK_SIDE_M                              # noqa: E402
import engine.surface_mineralization as sm                         # noqa: E402

_ARID = 7  # HOT_DESERT — max visibility, never masks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _layer(top, bottom, rock="shale", density=2400.0, ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom,
                       rock_type=rock, density_kg_m3=density,
                       ore_mix=dict(ore or {}))


def _booted_sim(name: str, seed: int = 0xC0DE_C001, *, resolution: int = 64):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=4, max_agents=20,
                    bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    geo.install_geology(sim)
    sm.install_surface_mineralization(sim)
    return sim


def _populate(sim, grid: int = 6):
    coords = []
    for cx in range(grid):
        for cy in range(grid):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return coords


def _inject_deposit(sim, coord, ore, biome=_ARID):
    """Plant a controlled shallow ore body + visible biome at ``coord`` in a
    real booted sim, then invalidate the cue cache. The procedural world is
    region-dependent (the test region may be ice/ocean/barren), so we control
    the fixture to exercise the live plumbing deterministically. Returns the
    chunk object so callers can inspect it."""
    geo.install_geology(sim)
    sm.install_surface_mineralization(sim)
    ch = sim.streamer.get(0, coord)
    assert ch is not None
    ch.biome = np.full(np.asarray(ch.biome).shape, biome,
                       dtype=np.asarray(ch.biome).dtype)
    g = ChunkGeology(coord=tuple(int(c) for c in coord), layers=[
        StrataLayer(0.0, 1.0, "regolith", 1800.0, dict(ore)),
        StrataLayer(1.0, 5.0, "shale", 2400.0, dict(ore)),
        StrataLayer(5.0, 200.0, "limestone", 2600.0, {}),
    ])
    sim._geology_state.chunks[tuple(int(c) for c in coord)] = g
    sim._surface_cue_cache.clear()
    return ch


# ---------------------------------------------------------------------------
# Table integrity + physical colours
# ---------------------------------------------------------------------------

def test_table_integrity_real_minerals_disjoint_groups():
    seen = set()
    for rule in sm._RULES:
        for m in rule.minerals:
            assert m in MINERAL_BY_NAME, f"unknown mineral {m}"
            assert m not in seen, f"{m} in two groups"
            seen.add(m)
    groups = {r.group for r in sm._RULES}
    assert {"copper", "gossan", "sulfur", "salt", "gold_placer"} <= groups


def test_colours_are_physically_correct():
    rule = {r.group: r for r in sm._RULES}
    cr, cg, cb = rule["copper"].rgb            # malachite green dominant
    assert cg > cr and cg > cb
    gr, gg, gb = rule["gossan"].rgb            # iron cap : red/brown, low blue
    assert gr > gg > gb
    sr, sg, sb = rule["sulfur"].rgb            # yellow : r,g high, b low
    assert sr > sb and sg > sb
    wr, wg, wb = rule["salt"].rgb              # white efflorescence
    assert min(wr, wg, wb) >= 200
    yr, yg, yb = rule["gold_placer"].rgb       # golden : r>g>b, elevated
    assert yr > yg > yb and yr > 150


# ---------------------------------------------------------------------------
# Pure derivation : depth / threshold / masking / priority
# ---------------------------------------------------------------------------

def test_shallow_copper_expresses_green():
    layers = [_layer(0.0, 2.0, ore={"native_copper": 0.01})]
    cue = sm._cue_from_geology((0, 0, 0), layers, _ARID)
    assert cue is not None and cue.group == "copper"
    assert cue.rgb == (80, 140, 70)
    assert 0.0 <= cue.dig_depth_m < 2.0  # lands inside the ore layer


def test_deep_only_ore_gives_no_surface_cue():
    # copper body top at 100 m >> 40 m expression depth → no surface stain
    layers = [_layer(0.0, 90.0, ore={}), _layer(90.0, 200.0,
              ore={"native_copper": 0.05})]
    assert sm._cue_from_geology((0, 0, 0), layers, _ARID) is None


def test_faint_ore_below_threshold_no_cue():
    frac = sm.MIN_VISIBLE_FRACTION / 2.0
    layers = [_layer(0.0, 3.0, ore={"native_copper": frac})]
    assert sm._cue_from_geology((0, 0, 0), layers, _ARID) is None


def test_ocean_masks_cue():
    layers = [_layer(0.0, 3.0, ore={"native_copper": 0.05})]
    assert sm._cue_from_geology((0, 0, 0), layers, sm._OCEAN) is None


def test_rainforest_canopy_masks_cue():
    layers = [_layer(0.0, 3.0, ore={"pyrite": 0.05})]
    assert sm._cue_from_geology((0, 0, 0), layers, 11) is None  # TROPICAL_RAINFOREST


def test_priority_diagnostic_copper_beats_common_gossan():
    # same shallow layer carries both → green copper signal dominates
    layers = [_layer(0.0, 4.0, ore={"native_copper": 0.01, "pyrite": 0.08})]
    cue = sm._cue_from_geology((0, 0, 0), layers, _ARID)
    assert cue is not None and cue.group == "copper"


def test_shallowest_layer_dominates_surface():
    layers = [
        _layer(0.0, 3.0, ore={"hematite": 0.05}),        # iron cap on top
        _layer(3.0, 30.0, ore={"native_copper": 0.05}),  # copper just below
    ]
    cue = sm._cue_from_geology((0, 0, 0), layers, _ARID)
    assert cue is not None and cue.group == "gossan"  # topmost weathering wins


def test_synthetic_cue_never_lies():
    # any cue derived must point at a real shallow layer holding the mineral
    cases = [
        {"native_copper": 0.02}, {"pyrite": 0.04}, {"native_sulfur": 0.03},
        {"halite": 0.05}, {"native_gold": 0.01}, {"hematite": 0.06},
    ]
    for ore in cases:
        layers = [_layer(0.0, 5.0, ore=ore)]
        cue = sm._cue_from_geology((0, 0, 0), layers, _ARID)
        assert cue is not None
        L = layers[0]
        assert L.depth_top_m <= cue.dig_depth_m < L.depth_bottom_m
        assert cue.mineral in L.ore_mix
        rule = sm._MINERAL_RULE[cue.mineral]
        assert rule.group == cue.group
        assert L.depth_top_m <= rule.max_expression_depth_m


# ---------------------------------------------------------------------------
# Sim-level invariants on a real Genesis world
# ---------------------------------------------------------------------------

def test_world_never_lies_on_real_world():
    sim = _booted_sim("c1_neverlies")
    coords = _populate(sim)
    # (a) one-directional invariant on whatever the procedural world emits:
    #     any cue present must point at a real shallow layer with the mineral.
    for coord in coords:
        cue = sm.surface_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        layer = geo.chunk_geology(sim, coord).find_layer_at(cue.dig_depth_m)
        assert layer is not None and cue.mineral in layer.ore_mix
        assert sm._MINERAL_RULE[cue.mineral].group == cue.group
    # (b) guarantee at least one cue is exercised through the live sim plumbing
    target = coords[len(coords) // 2]
    _inject_deposit(sim, target, {"native_copper": 0.02})
    cue = sm.surface_cue_for_chunk(sim, target)
    assert cue is not None and cue.group == "copper"
    layer = geo.chunk_geology(sim, target).find_layer_at(cue.dig_depth_m)
    assert layer is not None and cue.mineral in layer.ore_mix


def _cue_key(c):
    return None if c is None else (c.group, c.mineral, c.rgb,
                                   round(c.dig_depth_m, 6),
                                   round(c.confidence, 6))


def test_determinism_same_seed():
    a = _booted_sim("det_a", seed=0xAB_1234)
    b = _booted_sim("det_b", seed=0xAB_1234)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    # same seed → identical per-chunk cue decision (including None)
    for coord in ca:
        assert _cue_key(sm.surface_cue_for_chunk(a, coord)) == \
               _cue_key(sm.surface_cue_for_chunk(b, coord))
    # and an identical injected deposit yields a bit-identical cue
    coord = ca[len(ca) // 2]
    _inject_deposit(a, coord, {"native_copper": 0.02})
    _inject_deposit(b, coord, {"native_copper": 0.02})
    ka = _cue_key(sm.surface_cue_for_chunk(a, coord))
    assert ka is not None
    assert ka == _cue_key(sm.surface_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("idem")
    _populate(sim)
    c1 = sm.install_surface_mineralization(sim)
    c2 = sm.install_surface_mineralization(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = sm.surface_cue_summary(sim)
    assert set(s) >= {"n_chunks", "n_chunks_with_cue", "cue_rate",
                      "by_group", "by_mineral"}
    assert 0.0 <= s["cue_rate"] <= 1.0
    assert s["n_chunks_with_cue"] <= s["n_chunks"]


def test_prospect_to_mine_discovery_loop():
    sim = _booted_sim("loop")
    coords = _populate(sim)
    coord = coords[len(coords) // 2]
    _inject_deposit(sim, coord, {"native_copper": 0.03})
    # agent walks to the green stain it perceived, then digs there
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    seen = sm.prospect(sim, float(sim.agents.pos[0, 0]),
                       float(sim.agents.pos[0, 1]))
    assert seen is not None and seen.group == "copper"
    # the world never lies: digging where the green stain is yields copper
    out = geo.mine_at(sim, 0, target_depth_m=seen.dig_depth_m,
                      kg_to_extract=20.0)
    assert seen.mineral in out and out[seen.mineral] > 0.0


def test_discover_by_sight_returns_sorted_nearby_cues():
    sim = _booted_sim("sight")
    coords = _populate(sim)
    cx, cy, _ = coords[len(coords) // 2]
    _inject_deposit(sim, (cx, cy, 0), {"native_copper": 0.02})
    sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    res = sm.discover_by_sight(sim, [0], perception_radius_m=3 * CHUNK_SIDE_M)
    assert 0 in res
    cues = res[0]
    assert len(cues) >= 1
    # the agent's own chunk cue must be first (distance 0)
    assert cues[0].coord == (cx, cy, 0)
