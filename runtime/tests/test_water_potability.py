"""Invariants — Substrate capability : potabilité de l'eau (Cap. C3).

Couvre :
- Cohérence des bandes de salinité (fresh < potable < brackish < seawater).
- Dérivation pure : mer (biome OCEAN) → 35 ppt ; saumure (halite peu profonde)
  → non potable ; côtier (basse élévation) → mélange estuarien ; douce
  intérieure (douce/dure) → potable ; pas d'eau → muet.
- Mapping goût ↔ ppt (FRESH/MINERAL/BRACKISH/SALINE/BRINE).
- **« Le monde ne ment jamais »** : potable ⇒ ≠ OCEAN & pas de saumure halite &
  ppt ≤ seuil ; mer ⇒ OCEAN ; saumure ⇒ halite — colonnes synthétiques ET
  monde Genesis réel.
- ``drink_at`` est un aperçu **non mutant** (eau & soif inchangées) et
  ``hydrating`` n'est vrai que pour une eau potable réellement présente.
- ``nearest_potable_water`` saute l'eau salée.
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

import numpy as np                                                  # noqa: E402

from engine.sim import Simulation, SimConfig                        # noqa: E402
from engine.world_genesis import GenesisParams                      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine.geology import StrataLayer, ChunkGeology                # noqa: E402
from engine.world import Biome, CHUNK_SIDE_M                        # noqa: E402
import engine.water_potability as wp                                # noqa: E402

_FOREST = 10   # TROPICAL_DRY_FOREST — non-ocean, never marine
_GRASS = 6     # GRASSLAND — used for coastal cases (non-ocean)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Chunk:
    """Minimal stand-in carrying the three fields ``_cue_from_chunk`` reads."""
    def __init__(self, water, biome, height):
        self.water = water
        self.biome = biome
        self.height = height


def _chunk(w=200.0, biome=_FOREST, elev=500.0, side=8):
    return _Chunk(np.full((side, side), w, dtype=np.float32),
                  np.full((side, side), biome, dtype=np.uint8),
                  np.full((side, side), elev, dtype=np.float32))


def _layer(top, bottom, rock="shale", density=2400.0, ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom,
                       rock_type=rock, density_kg_m3=density,
                       ore_mix=dict(ore or {}))


def _booted_sim(name: str, seed: int = 0xC0DE_C003, *, resolution: int = 64):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=4, max_agents=20,
                    bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    geo.install_geology(sim)
    wp.install_water_potability(sim)
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


# ---------------------------------------------------------------------------
# Band constants + taste mapping
# ---------------------------------------------------------------------------

def test_salinity_bands_are_ordered():
    assert wp.FRESH_MAX_PPT < wp.POTABLE_MAX_PPT < wp.BRACKISH_MAX_PPT \
        < wp.SEAWATER_PPT <= wp.BRINE_SAT_PPT
    assert wp.FRESH_SOFT_PPT < wp.FRESH_HARD_PPT <= wp.FRESH_MAX_PPT


def test_taste_mapping_thresholds():
    assert wp._taste_for_ppt(0.05) == wp.WaterTaste.FRESH
    assert wp._taste_for_ppt(0.40) == wp.WaterTaste.MINERAL
    assert wp._taste_for_ppt(2.0) == wp.WaterTaste.BRACKISH
    assert wp._taste_for_ppt(10.0) == wp.WaterTaste.SALINE
    assert wp._taste_for_ppt(35.0) == wp.WaterTaste.BRINE


# ---------------------------------------------------------------------------
# Pure derivation : sea / brine / coastal / fresh / silent
# ---------------------------------------------------------------------------

def test_ocean_is_seawater_not_potable():
    cue = wp._cue_from_chunk((0, 0, 0), [_layer(0, 5, "basalt")],
                             _chunk(w=1000.0, biome=int(Biome.OCEAN), elev=0.0))
    assert cue is not None and cue.source == "sea"
    assert abs(cue.salinity_ppt - wp.SEAWATER_PPT) < 1e-6
    assert cue.potable is False and cue.taste == wp.WaterTaste.BRINE


def test_shallow_halite_makes_brine_spring():
    layers = [_layer(0.0, 2.0, "shale", ore={"halite": 0.05}),
              _layer(2.0, 60.0, "sandstone")]
    cue = wp._cue_from_chunk((0, 0, 0), layers, _chunk(elev=400.0))
    assert cue is not None and cue.source == "brine_spring"
    assert cue.salinity_ppt > wp.POTABLE_MAX_PPT and cue.potable is False
    # rock_type halite (a solid salt bed) → near-saturation brine
    bed = [_layer(0.0, 3.0, "halite")]
    cue2 = wp._cue_from_chunk((0, 0, 0), bed, _chunk(elev=400.0))
    assert cue2 is not None and cue2.salinity_ppt >= wp.SEAWATER_PPT


def test_deep_halite_does_not_salt_surface_water():
    # halite below the leach depth → spring stays fresh & potable.
    layers = [_layer(0.0, 2.0, "shale"),
              _layer(wp.BRINE_LEACH_DEPTH_M + 5.0, 80.0, "sandstone",
                     ore={"halite": 0.20})]
    cue = wp._cue_from_chunk((0, 0, 0), layers, _chunk(elev=400.0))
    assert cue is not None and cue.source == "fresh" and cue.potable is True


def test_coastal_estuary_mixing_gradient():
    layers = [_layer(0.0, 5.0, "sandstone")]
    at_sea = wp._cue_from_chunk((0, 0, 0), layers,
                                _chunk(biome=_GRASS, elev=0.0))
    half = wp._cue_from_chunk((0, 0, 0), layers,
                              _chunk(biome=_GRASS, elev=wp.COASTAL_MARGIN_M / 2))
    head = wp._cue_from_chunk((0, 0, 0), layers,
                              _chunk(biome=_GRASS, elev=wp.COASTAL_MARGIN_M))
    assert at_sea.source == "coastal" and at_sea.salinity_ppt > half.salinity_ppt
    assert half.salinity_ppt > head.salinity_ppt
    assert at_sea.potable is False                # near sea level = saline
    assert head.potable is True                   # estuary head = fresh


def test_fresh_inland_soft_vs_hard():
    soft = wp._cue_from_chunk((0, 0, 0), [_layer(0, 5, "sandstone")],
                              _chunk(elev=600.0))
    hard = wp._cue_from_chunk((0, 0, 0), [_layer(0, 5, "limestone")],
                              _chunk(elev=600.0))
    assert soft.source == "fresh" and soft.potable and hard.potable
    assert soft.salinity_ppt == wp.FRESH_SOFT_PPT
    assert hard.salinity_ppt == wp.FRESH_HARD_PPT     # carbonate hardness
    assert soft.taste == wp.WaterTaste.FRESH
    assert hard.taste == wp.WaterTaste.MINERAL


def test_dry_chunk_is_silent():
    dry = wp._cue_from_chunk((0, 0, 0), [_layer(0, 5, "sandstone")],
                             _chunk(w=0.0, elev=600.0))
    assert dry is None
    faint = wp._cue_from_chunk((0, 0, 0), [_layer(0, 5, "sandstone")],
                               _chunk(w=wp.WET_CELL_MIN / 2.0, elev=600.0))
    assert faint is None


# ---------------------------------------------------------------------------
# "Le monde ne ment jamais" — synthetic + ground-truth coupling
# ---------------------------------------------------------------------------

def _assert_cue_truthful(cue, layers, dom_biome):
    if cue is None:
        return
    halite = wp._shallow_halite_fraction(layers)
    if cue.potable:
        assert dom_biome != int(Biome.OCEAN)
        assert halite < wp.HALITE_BRINE_MIN_FRACTION
        assert cue.salinity_ppt <= wp.POTABLE_MAX_PPT
    if cue.source == "sea":
        assert dom_biome == int(Biome.OCEAN)
    if cue.source == "brine_spring":
        assert halite >= wp.HALITE_BRINE_MIN_FRACTION


def test_synthetic_cue_never_lies():
    cases = [
        ([_layer(0, 5, "basalt")], int(Biome.OCEAN), 0.0),               # sea
        ([_layer(0, 2, "shale", ore={"halite": 0.08})], _FOREST, 400.0),  # brine
        ([_layer(0, 5, "sandstone")], _GRASS, 0.0),                       # coastal
        ([_layer(0, 5, "limestone")], _FOREST, 700.0),                    # fresh
    ]
    for layers, biome, elev in cases:
        cue = wp._cue_from_chunk((0, 0, 0), layers,
                                 _chunk(w=300.0, biome=biome, elev=elev))
        _assert_cue_truthful(cue, layers, biome)


def test_world_never_lies_on_real_world():
    sim = _booted_sim("c3_neverlies")
    coords = _populate(sim)
    assert len(coords) > 0
    for coord in coords:
        cue = wp.water_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        chunk = sim.streamer.cache.get(coord)
        # (1) a cue ⇒ real water present.
        assert float(np.asarray(chunk.water).max()) >= wp.WET_CELL_MIN
        g = geo.chunk_geology(sim, coord)
        _assert_cue_truthful(cue, g.layers if g else [],
                             wp._dominant_biome(chunk.biome))


def test_injected_sea_and_brine_through_live_sim():
    sim = _booted_sim("c3_inject")
    coords = _populate(sim)
    target = coords[len(coords) // 2]
    chunk = sim.streamer.get(0, target)

    # Inject an ocean chunk: biome OCEAN + deep water → saline, not potable.
    chunk.biome = np.full(np.asarray(chunk.biome).shape, int(Biome.OCEAN),
                          dtype=np.asarray(chunk.biome).dtype)
    chunk.water = np.full(np.asarray(chunk.water).shape, 1000.0,
                          dtype=np.float32)
    sim._water_cue_cache.clear()
    sea = wp.water_cue_for_chunk(sim, target)
    assert sea is not None and sea.source == "sea" and sea.potable is False
    # the truth oracle agrees: drinking the sea does NOT hydrate.
    sim.agents.pos[0, 0] = (target[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (target[1] + 0.5) * CHUNK_SIDE_M
    out = wp.drink_at(sim, float(sim.agents.pos[0, 0]),
                      float(sim.agents.pos[0, 1]))
    assert out["water_litres"] >= wp.WET_CELL_MIN and out["hydrating"] is False

    # Inject a brine spring: shallow halite + fresh-water elevation.
    chunk.biome = np.full(np.asarray(chunk.biome).shape, _FOREST,
                          dtype=np.asarray(chunk.biome).dtype)
    chunk.height = np.full(np.asarray(chunk.height).shape, 300.0,
                           dtype=np.float32)
    chunk.water = np.full(np.asarray(chunk.water).shape, 200.0, dtype=np.float32)
    sim._geology_state.chunks[target] = ChunkGeology(coord=target, layers=[
        _layer(0.0, 2.0, "shale", ore={"halite": 0.06}),
        _layer(2.0, 80.0, "sandstone"),
    ])
    sim._water_cue_cache.clear()
    brine = wp.water_cue_for_chunk(sim, target)
    assert brine is not None and brine.source == "brine_spring"
    assert brine.potable is False


# ---------------------------------------------------------------------------
# Discovery loop : drink_at preview + nearest potable
# ---------------------------------------------------------------------------

def test_drink_at_is_non_mutating_and_hydrates_only_fresh():
    sim = _booted_sim("c3_drink")
    coords = _populate(sim)
    coord = coords[0]
    chunk = sim.streamer.get(0, coord)
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    water_before = np.asarray(chunk.water).copy()
    thirst_before = float(sim.agents.thirst[0])
    out = wp.drink_at(sim, float(sim.agents.pos[0, 0]),
                      float(sim.agents.pos[0, 1]))
    # non-mutating: neither the water field nor thirst moved.
    assert np.array_equal(np.asarray(chunk.water), water_before)
    assert float(sim.agents.thirst[0]) == thirst_before
    # the booted region is fresh highland → potable & hydrating.
    cue = wp.water_cue_for_chunk(sim, coord)
    assert cue is not None and cue.potable
    assert out["hydrating"] is True and out["source"] == "fresh"


def test_nearest_potable_skips_saline():
    sim = _booted_sim("c3_nearest")
    coords = _populate(sim)
    cx, cy, _ = coords[len(coords) // 2]
    # Salt the agent's own chunk (nearest) ; leave neighbours fresh.
    own = sim.streamer.get(0, (cx, cy, 0))
    own.biome = np.full(np.asarray(own.biome).shape, int(Biome.OCEAN),
                        dtype=np.asarray(own.biome).dtype)
    own.water = np.full(np.asarray(own.water).shape, 1000.0, dtype=np.float32)
    sim._water_cue_cache.clear()
    sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    best = wp.nearest_potable_water(sim, 0, perception_radius_m=3 * CHUNK_SIDE_M)
    # nearest body is the salt chunk, but it must be skipped for a potable one.
    assert best is not None and best.potable
    assert best.coord != (cx, cy, 0)


# ---------------------------------------------------------------------------
# Determinism + install hygiene
# ---------------------------------------------------------------------------

def _cue_key(c):
    return None if c is None else (c.source, c.taste,
                                   round(c.salinity_ppt, 6), c.potable)


def test_determinism_same_seed():
    a = _booted_sim("det_a", seed=0xBE_3456)
    b = _booted_sim("det_b", seed=0xBE_3456)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    for coord in ca:
        assert _cue_key(wp.water_cue_for_chunk(a, coord)) == \
               _cue_key(wp.water_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("idem")
    _populate(sim)
    c1 = wp.install_water_potability(sim)
    c2 = wp.install_water_potability(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = wp.water_cue_summary(sim)
    assert set(s) >= {"n_chunks", "n_chunks_with_water", "n_potable",
                      "potable_rate", "salinity_ppt_range", "by_source",
                      "by_taste"}
    assert 0.0 <= s["potable_rate"] <= 1.0
    assert s["n_potable"] <= s["n_chunks_with_water"] <= s["n_chunks"]
