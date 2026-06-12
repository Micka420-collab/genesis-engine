"""Invariants — Substrate capability : affleurements de pierre taillable.

Couvre :
- Intégrité de la table de taille (matières réelles, classes assignées).
- Hiérarchie archéologique de qualité (obsidienne > silex > quartzite >
  basalte > granite ; tendre/régolithe sous le seuil → muet).
- Bonus silex/chert dans un hôte carbonaté.
- Affleurement vs enfouissement (socle peu profond → indice ; enfoui → muet).
- Sélection par qualité (le plus tranchant gagne, même s'il est moins haut).
- Masquage par biome (océan / glace / canopée).
- **« Le monde ne ment jamais »** : tout indice ⇒ vraie couche peu profonde
  portant la matière (rock_type OU ore_mix) — colonnes synthétiques ET monde
  Genesis réel ; boucle prospecter → débiter → obtenir la pierre.
- Déterminisme même-seed (bit-identique).
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
import engine.lithic_outcrop as lo                                 # noqa: E402

_ARID = 7  # HOT_DESERT — max visibility, never masks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _layer(top, bottom, rock="shale", density=2400.0, ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom,
                       rock_type=rock, density_kg_m3=density,
                       ore_mix=dict(ore or {}))


def _booted_sim(name: str, seed: int = 0xC0DE_C002, *, resolution: int = 64):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=4, max_agents=20,
                    bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    geo.install_geology(sim)
    lo.install_lithic_outcrop(sim)
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


def _inject_outcrop(sim, coord, layers, biome=_ARID):
    """Plant a controlled shallow column + visible biome at ``coord`` in a real
    booted sim, then invalidate the cue cache. The procedural world is
    region-dependent, so we control the fixture to exercise live plumbing."""
    geo.install_geology(sim)
    lo.install_lithic_outcrop(sim)
    ch = sim.streamer.get(0, coord)
    assert ch is not None
    ch.biome = np.full(np.asarray(ch.biome).shape, biome,
                       dtype=np.asarray(ch.biome).dtype)
    g = ChunkGeology(coord=tuple(int(c) for c in coord), layers=list(layers))
    sim._geology_state.chunks[tuple(int(c) for c in coord)] = g
    sim._lithic_cue_cache.clear()
    return ch


# ---------------------------------------------------------------------------
# Table integrity + archaeological quality ranking
# ---------------------------------------------------------------------------

def test_table_integrity_real_materials():
    for prof in lo._PROFILES:
        assert prof.material in MINERAL_BY_NAME, f"unknown {prof.material}"
        assert 0.0 <= prof.base_quality <= 1.0
    # obsidian + quartz are the conchoidal flakers that can come up as float
    assert set(lo._FLAKER_MINERALS) == {"obsidian", "quartz"}


def test_quality_ranking_is_archaeological():
    q = {p.material: p.base_quality for p in lo._PROFILES}
    # obsidian (razor glass) > raw quartzite > sandstone abrasive ;
    # basalt axe-stone > granite > soft carbonate.
    assert q["obsidian"] > q["quartz"] > q["sandstone"]
    assert q["basalt"] > q["granite"] >= q["limestone"]
    assert q["limestone"] < lo.MIN_KNAP_QUALITY  # soft stone never cues
    assert q["sandstone"] < lo.MIN_KNAP_QUALITY   # ubiquitous regolith: muet
    assert q["obsidian"] >= lo.MIN_KNAP_QUALITY


def test_chert_boost_only_in_carbonate_host():
    bare = [_layer(0.0, 3.0, rock="granite", ore={"quartz": 0.05})]
    cue_bare = lo._cue_from_geology((0, 0, 0), bare, _ARID)
    # granite (0.40) vs quartzite (0.42) → quartzite wins, no chert boost
    assert cue_bare is not None and cue_bare.material == "quartz"
    assert abs(cue_bare.knap_quality - 0.42) < 1e-9
    # add a carbonate host → quartz upgrades to flint/chert (+CHERT_BONUS)
    hosted = [_layer(0.0, 3.0, rock="granite", ore={"quartz": 0.05}),
              _layer(3.0, 60.0, rock="limestone", ore={})]
    cue_host = lo._cue_from_geology((0, 0, 0), hosted, _ARID)
    assert cue_host is not None and cue_host.material == "quartz"
    assert abs(cue_host.knap_quality - (0.42 + lo.CHERT_BONUS)) < 1e-9
    assert cue_host.knap_class == lo.KnapClass.CONCHOIDAL


# ---------------------------------------------------------------------------
# Pure derivation : exposure / threshold / masking / selection
# ---------------------------------------------------------------------------

def test_obsidian_float_expresses_conchoidal():
    layers = [_layer(0.0, 2.0, rock="sandstone", ore={"obsidian": 0.02})]
    cue = lo._cue_from_geology((0, 0, 0), layers, _ARID)
    assert cue is not None and cue.material == "obsidian"
    assert cue.source == "ore" and cue.knap_class == lo.KnapClass.CONCHOIDAL
    assert abs(cue.knap_quality - 1.0) < 1e-9
    assert 0.0 <= cue.collect_depth_m < 2.0  # lands inside the float layer


def test_bedrock_outcrop_vs_buried():
    # granite cropping out near surface → GROUND lithology cue
    shallow = [_layer(0.0, 1.0, rock="shale"),
               _layer(1.0, 5.0, rock="sandstone"),
               _layer(5.0, 800.0, rock="granite")]
    cue = lo._cue_from_geology((0, 0, 0), shallow, _ARID)
    assert cue is not None and cue.material == "granite"
    assert cue.source == "lithology"
    # same granite buried under 200 m of sediment → no lithology cue
    buried = [_layer(0.0, 1.0, rock="shale"),
              _layer(1.0, 5.0, rock="sandstone"),
              _layer(5.0, 200.0, rock="limestone"),
              _layer(200.0, 1000.0, rock="granite")]
    assert lo._cue_from_geology((0, 0, 0), buried, _ARID) is None


def test_soft_and_regolith_are_muet():
    # only soft / abrasive ubiquitous stone present → below threshold → no cue
    layers = [_layer(0.0, 1.0, rock="shale"),
              _layer(1.0, 5.0, rock="sandstone"),
              _layer(5.0, 200.0, rock="limestone")]
    assert lo._cue_from_geology((0, 0, 0), layers, _ARID) is None


def test_faint_float_below_fraction_no_cue():
    frac = lo.MIN_VISIBLE_FRACTION / 2.0
    layers = [_layer(0.0, 3.0, rock="shale", ore={"obsidian": frac})]
    assert lo._cue_from_geology((0, 0, 0), layers, _ARID) is None


def test_ocean_ice_rainforest_mask_cue():
    layers = [_layer(0.0, 3.0, rock="basalt", ore={"obsidian": 0.05})]
    assert lo._cue_from_geology((0, 0, 0), layers, lo._OCEAN) is None
    assert lo._cue_from_geology((0, 0, 0), layers, 1) is None   # ICE
    assert lo._cue_from_geology((0, 0, 0), layers, 11) is None  # RAINFOREST
    assert lo._cue_from_geology((0, 0, 0), layers, _ARID) is not None


def test_sharpest_stone_wins_selection():
    # a granite outcrop (0.40) on top of obsidian float (1.0) just below:
    # the razor stone must win even though granite is shallower.
    layers = [_layer(0.0, 4.0, rock="granite"),
              _layer(4.0, 6.0, rock="sandstone", ore={"obsidian": 0.03})]
    cue = lo._cue_from_geology((0, 0, 0), layers, _ARID)
    assert cue is not None and cue.material == "obsidian"
    assert cue.knap_quality > 0.9


def test_synthetic_cue_never_lies():
    cases = [
        [_layer(0.0, 3.0, rock="sandstone", ore={"obsidian": 0.02})],   # ore
        [_layer(0.0, 1.0, rock="shale"),
         _layer(1.0, 5.0, rock="sandstone"),
         _layer(5.0, 800.0, rock="basalt")],                            # litho
        [_layer(0.0, 4.0, rock="gneiss")],                              # litho
        [_layer(0.0, 3.0, rock="shale", ore={"quartz": 0.05}),
         _layer(3.0, 80.0, rock="limestone")],                         # chert
    ]
    for layers in cases:
        cue = lo._cue_from_geology((0, 0, 0), layers, _ARID)
        assert cue is not None
        # find the proving layer at the collect depth and verify the material.
        L = next(L for L in layers
                 if L.depth_top_m <= cue.collect_depth_m < L.depth_bottom_m)
        if cue.source == "lithology":
            assert L.rock_type == cue.material
        else:
            assert cue.material in L.ore_mix
        assert L.depth_top_m <= lo.MAX_OUTCROP_DEPTH_M


# ---------------------------------------------------------------------------
# Sim-level invariants on a real Genesis world
# ---------------------------------------------------------------------------

def test_world_never_lies_on_real_world():
    sim = _booted_sim("c2_neverlies")
    coords = _populate(sim)
    # (a) one-directional invariant on whatever the procedural world emits.
    for coord in coords:
        cue = lo.lithic_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        layer = geo.chunk_geology(sim, coord).find_layer_at(cue.collect_depth_m)
        assert layer is not None
        if cue.source == "lithology":
            assert layer.rock_type == cue.material
        else:
            assert cue.material in layer.ore_mix
        assert cue.knap_quality >= lo.MIN_KNAP_QUALITY
    # (b) exercise an obsidian source through the live sim plumbing + dig loop.
    target = coords[len(coords) // 2]
    _inject_outcrop(sim, target, [
        _layer(0.0, 1.0, rock="sandstone", ore={"obsidian": 0.05}),
        _layer(1.0, 6.0, rock="shale", ore={"obsidian": 0.05}),
        _layer(6.0, 200.0, rock="limestone", ore={}),
    ])
    cue = lo.lithic_cue_for_chunk(sim, target)
    assert cue is not None and cue.material == "obsidian"
    # the world never lies: knapping where the glassy outcrop is yields obsidian
    sim.agents.pos[0, 0] = (target[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (target[1] + 0.5) * CHUNK_SIDE_M
    out = geo.mine_at(sim, 0, target_depth_m=cue.collect_depth_m,
                      kg_to_extract=20.0)
    assert "obsidian" in out and out["obsidian"] > 0.0


def _cue_key(c):
    return None if c is None else (c.material, c.source, c.knap_class,
                                   round(c.knap_quality, 6),
                                   round(c.collect_depth_m, 6))


def test_determinism_same_seed():
    a = _booted_sim("det_a", seed=0xBC_2345)
    b = _booted_sim("det_b", seed=0xBC_2345)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    for coord in ca:
        assert _cue_key(lo.lithic_cue_for_chunk(a, coord)) == \
               _cue_key(lo.lithic_cue_for_chunk(b, coord))
    coord = ca[len(ca) // 2]
    layers = [_layer(0.0, 2.0, rock="sandstone", ore={"obsidian": 0.04})]
    _inject_outcrop(a, coord, layers)
    _inject_outcrop(b, coord, layers)
    ka = _cue_key(lo.lithic_cue_for_chunk(a, coord))
    assert ka is not None and ka == _cue_key(lo.lithic_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("idem")
    _populate(sim)
    c1 = lo.install_lithic_outcrop(sim)
    c2 = lo.install_lithic_outcrop(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = lo.lithic_cue_summary(sim)
    assert set(s) >= {"n_chunks", "n_chunks_with_cue", "cue_rate",
                      "best_knap_quality", "by_class", "by_material"}
    assert 0.0 <= s["cue_rate"] <= 1.0
    assert s["n_chunks_with_cue"] <= s["n_chunks"]


def test_best_toolstone_near_picks_sharpest():
    sim = _booted_sim("best")
    coords = _populate(sim)
    cx, cy, _ = coords[len(coords) // 2]
    # plant obsidian on the agent's own chunk; it must be the sharpest pick.
    _inject_outcrop(sim, (cx, cy, 0),
                    [_layer(0.0, 2.0, rock="sandstone", ore={"obsidian": 0.05})])
    sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    best = lo.best_toolstone_near(sim, 0, perception_radius_m=2 * CHUNK_SIDE_M)
    assert best is not None and best.material == "obsidian"
    assert best.knap_quality >= 1.0 - 1e-9


def test_discover_by_sight_returns_sorted_nearby_cues():
    sim = _booted_sim("sight")
    coords = _populate(sim)
    cx, cy, _ = coords[len(coords) // 2]
    _inject_outcrop(sim, (cx, cy, 0),
                    [_layer(0.0, 2.0, rock="sandstone", ore={"obsidian": 0.03})])
    sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    res = lo.discover_toolstone_by_sight(sim, [0],
                                         perception_radius_m=3 * CHUNK_SIDE_M)
    assert 0 in res
    cues = res[0]
    assert len(cues) >= 1
    assert cues[0].coord == (cx, cy, 0)  # own chunk first (distance 0)
