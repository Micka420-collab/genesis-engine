"""Invariants — Substrate capability : affleurement calcaire (Cap. C6).

Couvre :
- Hiérarchie de grade (calcaire commun < carbonate pur) + seuils (grade min,
  mortier) cohérents ; tell calcaire pur blanc-crayeux (245,240,225) byte-exact
  ⇔ Rust ``Mineral::LimestonePure``.
- Dérivation pure : limestone en lithologie / limestone_pure (calcite, dolomite,
  marble) en ore_mix ; le plus haut grade gagne ; lit profond → muet ; océan →
  masqué ; colonne non-carbonatée → muet.
- **Porte de pureté (chaux/mortier)** : carbonate pur → ``mortar_grade`` (chaux
  vive → mortier) ; calcaire commun / dolomie → pierre à bâtir, pas de mortier.
- **Porte d'altération (karstification / cryoclastie)** : exposition sèche/tempérée
  → ``sound_quarry`` (dressable) ; humide → ``karst_fissured`` ; gel → ``frost_
  shattered`` — les trois mutuellement exclusifs et exhaustifs. mortar_grade
  (chaux) et dressable_now (blocs) sont **orthogonaux**.
- **« Le monde ne ment jamais »** : tout indice ⇒ carbonate réel peu profond dans
  la même colonne que ``mine_at`` ; ``mortar_grade`` ⇒ grade ≥ seuil ;
  ``dressable_now`` ⇒ sain & pierre de taille — colonnes synthétiques ET monde
  Genesis réel (seed 0xC1A7).
- ``work_preview`` est un aperçu **non mutant** et ``can_dress`` n'est vrai que
  pour un carbonate réel, sain, pierre de taille, réellement présent.
- ``best_limestone_near`` préfère le carbonate pur et filtre (mortar / dressable).
- Déterminisme même-seed (bit-identique). Installation idempotente, coût tick nul.
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
from engine.mineral_catalog import MINERAL_BY_NAME                  # noqa: E402
import engine.limestone_outcrop as li                               # noqa: E402

_TEMPERATE = 4   # TEMPERATE_FOREST — sound (below karst threshold)
_GRASS = 6       # GRASSLAND — sound, non-ocean
_DESERT = 7      # HOT_DESERT — sound (dry massive limestone = good stone)
_RAINFOREST = 11  # TROPICAL_RAINFOREST — karst (wet)
_TUNDRA = 2      # TUNDRA — frost (cryoclasty)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Chunk:
    """Minimal stand-in carrying the fields the derivation reads."""
    def __init__(self, water, biome, height):
        self.water = water
        self.biome = biome
        self.height = height


def _chunk(w=0.0, biome=_GRASS, elev=300.0, side=8):
    return _Chunk(np.full((side, side), w, dtype=np.float32),
                  np.full((side, side), biome, dtype=np.uint8),
                  np.full((side, side), elev, dtype=np.float32))


def _layer(top, bottom, rock="sandstone", density=2400.0, ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom,
                       rock_type=rock, density_kg_m3=density,
                       ore_mix=dict(ore or {}))


def _booted_sim(name: str, seed: int = 0xC1A7, *, resolution: int = 128):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    geo.install_geology(sim)
    li.install_limestone_outcrop(sim)
    return sim


def _populate(sim, grid: int = 12):
    coords = []
    for cx in range(grid):
        for cy in range(grid):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return coords


# ---------------------------------------------------------------------------
# Constants + profile table
# ---------------------------------------------------------------------------

def test_lime_grades_and_thresholds_ordered():
    g = {m: p.lime_grade for m, p in li._PROFILE.items()}
    assert g["limestone"] < g["limestone_pure"]
    assert g["dolomite"] < g["limestone"]              # dolomitic = weaker lime
    assert 0.0 < li.MIN_LIME_GRADE <= g["dolomite"]    # still burns to some lime
    assert g["limestone"] < li.MORTAR_GRADE <= g["limestone_pure"]  # only pure
    assert 0.0 < li.KARST_MOISTURE < 1.0


def test_profile_materials_exist_in_catalogue():
    for material in li._PROFILE:
        assert material in MINERAL_BY_NAME


def test_limestone_pure_tell_is_chalk_white():
    # The byte-exact tell an agent learns to seek for lime; mirrors the Rust
    # Mineral::LimestonePure::surface_color() = [245,240,225] (locked
    # cross-language in tests/test_geology_cross_language_contract.py).
    assert li._PROFILE["limestone_pure"].rgb == (245, 240, 225)


def test_only_dimension_stones_dress_into_blocks():
    # Calcite is a vein (lime source), not a masonry block; the rock carbonates
    # are dimension stones.
    assert li._PROFILE["calcite"].dimension_stone is False
    assert li._PROFILE["limestone"].dimension_stone is True
    assert li._PROFILE["limestone_pure"].dimension_stone is True
    assert li._PROFILE["marble"].dimension_stone is True


# ---------------------------------------------------------------------------
# Pure derivation
# ---------------------------------------------------------------------------

def test_pure_carbonate_in_ore_is_mortar_grade():
    layers = [_layer(0.0, 1.0, "shale"),
              _layer(1.0, 5.0, "sandstone", ore={"limestone_pure": 0.05})]
    cue = li._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.material == "limestone_pure"
    assert cue.source == "ore" and cue.lime_class == li.LimeClass.PURE_CARBONATE
    assert cue.mortar_grade is True and cue.dressable_now is True


def test_common_limestone_lithology_is_building_grade():
    layers = [_layer(0.0, 5.0, "limestone")]   # the carbonate platform cover
    cue = li._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.material == "limestone"
    assert cue.source == "lithology"
    assert cue.lime_class == li.LimeClass.COMMON_CARBONATE
    assert cue.mortar_grade is False          # common limestone → weak lime only
    assert cue.dressable_now is True          # grassland is sound (dry enough)


def test_wet_carbonate_is_karst_fissured_not_dressable():
    # Carbonate present shallow in a waterlogged rainforest → visible, but the
    # surface is dissolution-fissured: the emergent "quarry the sound rock below"
    # loop. Still burns to lime (mortar_grade independent of weathering).
    layers = [_layer(0.0, 4.0, "limestone", ore={"limestone_pure": 0.05})]
    cue = li._cue_from_geology((0, 0, 0), layers, _RAINFOREST,
                               _chunk(biome=_RAINFOREST, w=li.WATER_SATURATION_L))
    assert cue is not None
    assert cue.karst_fissured is True and cue.dressable_now is False
    assert cue.sound_quarry is False and cue.frost_shattered is False
    assert cue.ambient_moisture > li.KARST_MOISTURE
    assert cue.mortar_grade is True           # fissured rubble still burns to lime


def test_freezing_carbonate_is_frost_shattered():
    layers = [_layer(0.0, 5.0, "limestone")]
    cue = li._cue_from_geology((0, 0, 0), layers, _TUNDRA, _chunk(biome=_TUNDRA))
    assert cue is not None and cue.frost_shattered is True
    assert cue.dressable_now is False
    assert cue.sound_quarry is False and cue.karst_fissured is False


def test_dry_desert_limestone_is_sound():
    # Dry massive limestone (the great quarried building stones) → sound.
    layers = [_layer(0.0, 5.0, "limestone")]
    cue = li._cue_from_geology((0, 0, 0), layers, _DESERT,
                               _chunk(biome=_DESERT, w=0.0))
    assert cue is not None and cue.sound_quarry is True
    assert cue.dressable_now is True


def test_standing_water_can_push_sound_to_karst():
    layers = [_layer(0.0, 4.0, "limestone")]
    dry = li._cue_from_geology((0, 0, 0), layers, _TEMPERATE,
                               _chunk(biome=_TEMPERATE, w=0.0))
    wet = li._cue_from_geology((0, 0, 0), layers, _TEMPERATE,
                               _chunk(biome=_TEMPERATE, w=li.WATER_SATURATION_L))
    assert dry.sound_quarry is True
    assert wet.ambient_moisture > dry.ambient_moisture
    assert wet.karst_fissured is True


def test_highest_grade_wins_over_common_limestone():
    # Both limestone (lithology) and limestone_pure (ore) reachable → pure wins.
    layers = [_layer(0.0, 2.0, "limestone", ore={"limestone_pure": 0.04})]
    cue = li._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.material == "limestone_pure" and cue.mortar_grade


def test_deep_bed_is_silent():
    layers = [_layer(0.0, 5.0, "sandstone"),
              _layer(li.MAX_CARBONATE_DEPTH_M + 10.0, 200.0, "limestone",
                     ore={"limestone_pure": 0.10})]
    assert li._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk()) is None


def test_faint_fraction_is_silent():
    layers = [_layer(0.0, 4.0, "sandstone",
                     ore={"limestone_pure": li.MIN_VISIBLE_FRACTION / 2.0})]
    assert li._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk()) is None


def test_ocean_is_masked():
    layers = [_layer(0.0, 4.0, "limestone", ore={"limestone_pure": 0.10})]
    assert li._cue_from_geology((0, 0, 0), layers, int(Biome.OCEAN),
                                _chunk(biome=int(Biome.OCEAN))) is None


def test_non_carbonate_column_is_silent():
    layers = [_layer(0.0, 5.0, "sandstone", ore={"hematite": 0.05}),
              _layer(5.0, 50.0, "granite", ore={"native_copper": 0.02})]
    assert li._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk()) is None


# ---------------------------------------------------------------------------
# "Le monde ne ment jamais" — synthetic + real Genesis world
# ---------------------------------------------------------------------------

def _assert_cue_truthful(cue, layers):
    if cue is None:
        return
    grounded = False
    for L in layers:
        if L.depth_top_m > li.MAX_CARBONATE_DEPTH_M:
            continue
        if cue.source == "lithology" and L.rock_type == cue.material:
            grounded = True
        if cue.source == "ore" and \
                L.ore_mix.get(cue.material, 0.0) >= li.MIN_VISIBLE_FRACTION:
            grounded = True
    assert grounded, f"cue {cue.material} not grounded in a shallow layer"
    if cue.mortar_grade:
        assert cue.lime_grade >= li.MORTAR_GRADE
    if cue.dressable_now:
        assert cue.sound_quarry and cue.dimension_stone
    # the three weathering states are mutually exclusive and exhaustive.
    assert (int(cue.sound_quarry) + int(cue.karst_fissured)
            + int(cue.frost_shattered)) == 1


def test_world_never_lies_on_real_world():
    sim = _booted_sim("c6_neverlies")
    coords = _populate(sim)
    assert len(coords) > 0
    n_cued = 0
    for coord in coords:
        cue = li.limestone_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_cued += 1
        g = geo.chunk_geology(sim, coord)
        _assert_cue_truthful(cue, g.layers if g else [])
    # the canonical carbonate seed must actually surface carbonate.
    assert n_cued > 0


def test_work_preview_non_mutating_and_truthful():
    sim = _booted_sim("c6_preview")
    coords = _populate(sim)
    target = next((c for c in coords
                   if li.limestone_cue_for_chunk(sim, c) is not None), None)
    assert target is not None
    g = geo.chunk_geology(sim, target)
    layers_before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg)
                     for L in g.layers]
    sim.agents.pos[0, 0] = (target[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (target[1] + 0.5) * CHUNK_SIDE_M
    out = li.work_preview(sim, float(sim.agents.pos[0, 0]),
                          float(sim.agents.pos[0, 1]))
    cue = li.limestone_cue_for_chunk(sim, target)
    # non-mutating: geology untouched by the preview.
    layers_after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg)
                    for L in g.layers]
    assert layers_after == layers_before
    # the oracle agrees with the perception cue.
    assert out["can_dress"] == cue.dressable_now
    assert out["burns_to_quicklime"] == cue.mortar_grade
    assert out["material"] == cue.material


def test_injected_pure_carbonate_through_live_sim():
    sim = _booted_sim("c6_inject")
    coords = _populate(sim)
    target = coords[len(coords) // 2]
    chunk = sim.streamer.get(0, target)
    # a pure carbonate bed in a sound grassland.
    chunk.biome = np.full(np.asarray(chunk.biome).shape, _GRASS,
                          dtype=np.asarray(chunk.biome).dtype)
    chunk.water = np.zeros(np.asarray(chunk.water).shape, dtype=np.float32)
    sim._geology_state.chunks[target] = ChunkGeology(coord=target, layers=[
        _layer(0.0, 1.0, "shale"),
        _layer(1.0, 5.0, "sandstone", ore={"limestone_pure": 0.08}),
    ])
    sim._limestone_cue_cache.clear()
    cue = li.limestone_cue_for_chunk(sim, target)
    assert cue is not None and cue.material == "limestone_pure"
    assert cue.mortar_grade is True and cue.dressable_now is True


def test_mortar_and_dressable_are_orthogonal():
    # A pure carbonate (mortar grade) that is karst-fissured (not dressable):
    # the two properties are independent — burns to lime, but no sound blocks.
    layers = [_layer(0.0, 4.0, "sandstone", ore={"limestone_pure": 0.06})]
    cue = li._cue_from_geology((0, 0, 0), layers, _RAINFOREST,
                               _chunk(biome=_RAINFOREST, w=li.WATER_SATURATION_L))
    assert cue is not None
    assert cue.mortar_grade is True and cue.dressable_now is False


# ---------------------------------------------------------------------------
# Actionable pick : best_limestone_near
# ---------------------------------------------------------------------------

def _put_chunk(sim, cc, layers, biome, w):
    ch = sim.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, biome,
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
    sim._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=layers)
    sim._limestone_cue_cache.clear()


def _stand_on(sim, cc):
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M


# Perception radius small enough that only the agent's own chunk is in range
# (neighbour chunk centres sit a full CHUNK_SIDE_M away). Keeps the filter test
# isolated from whatever the procedural neighbours happen to carry.
_OWN_CHUNK_R = 0.4 * CHUNK_SIDE_M


def test_best_limestone_near_prefers_mortar_grade():
    sim = _booted_sim("c6_best")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    # a pure carbonate, sound grassland → mortar grade AND dressable.
    _put_chunk(sim, cc,
               [_layer(0.0, 1.0, "sandstone"),
                _layer(1.0, 5.0, "sandstone", ore={"limestone_pure": 0.08})],
               _GRASS, 0.0)
    _stand_on(sim, cc)
    best = li.best_limestone_near(sim, 0, perception_radius_m=_OWN_CHUNK_R)
    assert best is not None and best.material == "limestone_pure" and best.mortar_grade
    mortar = li.best_limestone_near(sim, 0, perception_radius_m=_OWN_CHUNK_R,
                                    require_mortar=True)
    assert mortar is not None and mortar.mortar_grade


def test_best_limestone_near_require_dressable_skips_karst():
    sim = _booted_sim("c6_best2")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    # a pure carbonate in a waterlogged rainforest → mortar grade but karst
    # fissured (not dressable).
    _put_chunk(sim, cc,
               [_layer(0.0, 5.0, "limestone", ore={"limestone_pure": 0.08})],
               _RAINFOREST, li.WATER_SATURATION_L)
    _stand_on(sim, cc)
    # mortar pick still works (burns to lime regardless of weathering)...
    mortar = li.best_limestone_near(sim, 0, perception_radius_m=_OWN_CHUNK_R,
                                    require_mortar=True)
    assert mortar is not None and mortar.mortar_grade
    # ...but the karst-fissured cliff is not dressable → require_dressable skips it
    # and, with nothing else in range, honestly reports 'no sound stone here'.
    assert li.best_limestone_near(sim, 0, perception_radius_m=_OWN_CHUNK_R,
                                  require_dressable=True) is None


def test_common_limestone_is_dressable_but_not_mortar():
    sim = _booted_sim("c6_best3")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    # common limestone cliff in a sound grassland → dressable, but weak lime.
    _put_chunk(sim, cc, [_layer(0.0, 5.0, "limestone")], _GRASS, 0.0)
    _stand_on(sim, cc)
    dressable = li.best_limestone_near(sim, 0, perception_radius_m=_OWN_CHUNK_R,
                                       require_dressable=True)
    assert dressable is not None and dressable.dressable_now
    assert dressable.material == "limestone"
    # common limestone never reaches plaster-grade quicklime → require_mortar
    # finds nothing.
    assert li.best_limestone_near(sim, 0, perception_radius_m=_OWN_CHUNK_R,
                                  require_mortar=True) is None


# ---------------------------------------------------------------------------
# Determinism + install hygiene
# ---------------------------------------------------------------------------

def _cue_key(c):
    return None if c is None else (c.material, c.source,
                                   round(c.lime_grade, 6),
                                   int(c.weather_state), c.mortar_grade)


def test_determinism_same_seed():
    a = _booted_sim("det_a", seed=0xC1A7)
    b = _booted_sim("det_b", seed=0xC1A7)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    for coord in ca:
        assert _cue_key(li.limestone_cue_for_chunk(a, coord)) == \
               _cue_key(li.limestone_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("idem")
    _populate(sim)
    c1 = li.install_limestone_outcrop(sim)
    c2 = li.install_limestone_outcrop(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = li.limestone_cue_summary(sim)
    assert set(s) >= {"n_chunks", "n_chunks_with_cue", "cue_rate",
                      "n_dressable_now", "n_mortar_grade",
                      "best_lime_grade", "by_class", "by_material", "by_weather"}
    assert 0.0 <= s["cue_rate"] <= 1.0
    assert s["n_dressable_now"] <= s["n_chunks_with_cue"] <= s["n_chunks"]
    assert s["n_mortar_grade"] <= s["n_chunks_with_cue"]
