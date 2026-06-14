"""Invariants — Substrate capability : affleurement d'argile (Cap. C5).

Couvre :
- Hiérarchie de grade (argile schisteuse brique < kaolin céramique) + seuils
  (grade min, céramique) cohérents ; tell kaolin beige-ocre (180,140,110)
  byte-exact ⇔ Rust ``Mineral::FineClay``.
- Dérivation pure : shale en lithologie (topsoil) / fine_clay en ore_mix ; le
  plus haut grade gagne ; lit profond → muet ; océan → masqué ; colonne
  non-argileuse → muet.
- **Porte de plasticité (limites d'Atterberg)** : argile en désert sec →
  ``too_dry_to_shape`` ; en marécage gorgé d'eau → ``too_wet_slurry`` ; entre
  les deux → ``workable_now``.
- **« Le monde ne ment jamais »** : tout indice ⇒ argile réelle peu profonde
  dans la même colonne que ``mine_at`` ; ``workable_now`` ⇒ humidité dans la
  fenêtre plastique ; ``ceramic_grade`` ⇒ grade ≥ seuil céramique — colonnes
  synthétiques ET monde Genesis réel (seed 0xC1A7).
- ``shape_preview`` est un aperçu **non mutant** et ``can_shape`` n'est vrai que
  pour une argile réelle, dans la fenêtre plastique, réellement présente.
- ``best_clay_near`` préfère le kaolin et filtre (workable / ceramic).
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
import engine.clay_outcrop as cl                                    # noqa: E402

_TEMPERATE = 4   # TEMPERATE_FOREST — squarely in the plastic window (workable)
_DESERT = 7      # HOT_DESERT — too dry to shape
_RAINFOREST = 11  # TROPICAL_RAINFOREST — too wet (slurry)
_GRASS = 6       # GRASSLAND — workable, non-ocean


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Chunk:
    """Minimal stand-in carrying the fields the derivation reads."""
    def __init__(self, water, biome, height):
        self.water = water
        self.biome = biome
        self.height = height


def _chunk(w=0.0, biome=_TEMPERATE, elev=300.0, side=8):
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
    cl.install_clay_outcrop(sim)
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

def test_clay_grades_and_thresholds_ordered():
    g = {m: p.pottery_grade for m, p in cl._PROFILE.items()}
    assert g["shale"] < g["fine_clay"]
    assert 0.0 < cl.MIN_POTTERY_GRADE <= g["shale"]        # shale still shapeable
    assert g["shale"] < cl.CERAMIC_GRADE <= g["fine_clay"]  # only kaolin fires
    assert 0.0 < cl.PLASTIC_LIMIT < cl.LIQUID_LIMIT < 1.0


def test_profile_materials_exist_in_catalogue():
    for material in cl._PROFILE:
        assert material in MINERAL_BY_NAME


def test_fine_clay_tell_is_smooth_ochre():
    # The byte-exact tell an agent learns to seek for a pot; mirrors the Rust
    # Mineral::FineClay::surface_color() = [180,140,110] (locked cross-language
    # in tests/test_geology_cross_language_contract.py).
    assert cl._PROFILE["fine_clay"].rgb == (180, 140, 110)


# ---------------------------------------------------------------------------
# Pure derivation
# ---------------------------------------------------------------------------

def test_fine_clay_in_ore_is_ceramic_grade():
    layers = [_layer(0.0, 1.0, "shale"),
              _layer(1.0, 5.0, "sandstone", ore={"fine_clay": 0.05})]
    cue = cl._cue_from_geology((0, 0, 0), layers, _TEMPERATE,
                               _chunk(biome=_TEMPERATE))
    assert cue is not None and cue.material == "fine_clay"
    assert cue.source == "ore" and cue.clay_class == cl.ClayClass.PLASTIC_CLAY
    assert cue.ceramic_grade is True and cue.workable_now is True


def test_shale_topsoil_is_brick_grade_lithology():
    layers = [_layer(0.0, 1.0, "shale")]   # the ubiquitous clay-shale topsoil
    cue = cl._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.material == "shale"
    assert cue.source == "lithology" and cue.clay_class == cl.ClayClass.SHALE_CLAY
    assert cue.ceramic_grade is False         # shale only fires to porous brick
    assert cue.workable_now is True           # grassland is in the plastic window


def test_clay_in_dry_desert_is_seen_but_not_shapeable():
    # Clay present shallow in a bone-dry desert → visible, but below the plastic
    # limit: the emergent "wet & wedge first" loop.
    layers = [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.05})]
    cue = cl._cue_from_geology((0, 0, 0), layers, _DESERT,
                               _chunk(biome=_DESERT, w=0.0))
    assert cue is not None and cue.material == "fine_clay"
    assert cue.workable_now is False and cue.too_dry_to_shape is True
    assert cue.too_wet_slurry is False
    assert cue.ambient_moisture < cl.PLASTIC_LIMIT


def test_clay_in_waterlogged_swamp_is_slurry():
    layers = [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.05})]
    cue = cl._cue_from_geology((0, 0, 0), layers, _RAINFOREST,
                               _chunk(biome=_RAINFOREST, w=cl.WATER_SATURATION_L))
    assert cue is not None and cue.too_wet_slurry is True
    assert cue.workable_now is False and cue.too_dry_to_shape is False
    assert cue.ambient_moisture > cl.LIQUID_LIMIT


def test_standing_water_raises_moisture():
    layers = [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.05})]
    drier = cl._cue_from_geology((0, 0, 0), layers, _GRASS,
                                 _chunk(biome=_GRASS, w=0.0))
    wetter = cl._cue_from_geology((0, 0, 0), layers, _GRASS,
                                  _chunk(biome=_GRASS, w=cl.WATER_SATURATION_L))
    assert wetter.ambient_moisture > drier.ambient_moisture


def test_highest_grade_wins_over_shale():
    # Both shale (lithology) and fine_clay (ore) reachable → kaolin wins.
    layers = [_layer(0.0, 2.0, "shale", ore={"fine_clay": 0.04})]
    cue = cl._cue_from_geology((0, 0, 0), layers, _TEMPERATE,
                               _chunk(biome=_TEMPERATE))
    assert cue is not None and cue.material == "fine_clay" and cue.ceramic_grade


def test_deep_bed_is_silent():
    layers = [_layer(0.0, 5.0, "sandstone"),
              _layer(cl.MAX_CLAY_DEPTH_M + 10.0, 200.0, "sandstone",
                     ore={"fine_clay": 0.10})]
    assert cl._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk()) is None


def test_faint_fraction_is_silent():
    layers = [_layer(0.0, 4.0, "sandstone",
                     ore={"fine_clay": cl.MIN_VISIBLE_FRACTION / 2.0})]
    assert cl._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk()) is None


def test_ocean_is_masked():
    layers = [_layer(0.0, 4.0, "shale", ore={"fine_clay": 0.10})]
    assert cl._cue_from_geology((0, 0, 0), layers, int(Biome.OCEAN),
                                _chunk(biome=int(Biome.OCEAN))) is None


def test_non_clay_column_is_silent():
    layers = [_layer(0.0, 5.0, "limestone", ore={"hematite": 0.05}),
              _layer(5.0, 50.0, "granite", ore={"native_copper": 0.02})]
    assert cl._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk()) is None


# ---------------------------------------------------------------------------
# "Le monde ne ment jamais" — synthetic + real Genesis world
# ---------------------------------------------------------------------------

def _assert_cue_truthful(cue, layers):
    if cue is None:
        return
    grounded = False
    for L in layers:
        if L.depth_top_m > cl.MAX_CLAY_DEPTH_M:
            continue
        if cue.source == "lithology" and L.rock_type == cue.material:
            grounded = True
        if cue.source == "ore" and \
                L.ore_mix.get(cue.material, 0.0) >= cl.MIN_VISIBLE_FRACTION:
            grounded = True
    assert grounded, f"cue {cue.material} not grounded in a shallow layer"
    if cue.workable_now:
        assert cl.PLASTIC_LIMIT <= cue.ambient_moisture <= cl.LIQUID_LIMIT
    if cue.ceramic_grade:
        assert cue.pottery_grade >= cl.CERAMIC_GRADE
    # the three moisture states are mutually exclusive and exhaustive.
    assert (int(cue.workable_now) + int(cue.too_dry_to_shape)
            + int(cue.too_wet_slurry)) == 1


def test_world_never_lies_on_real_world():
    sim = _booted_sim("c5_neverlies")
    coords = _populate(sim)
    assert len(coords) > 0
    n_cued = 0
    for coord in coords:
        cue = cl.clay_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_cued += 1
        g = geo.chunk_geology(sim, coord)
        _assert_cue_truthful(cue, g.layers if g else [])
    # the canonical clay seed must actually surface clay.
    assert n_cued > 0


def test_shape_preview_non_mutating_and_truthful():
    sim = _booted_sim("c5_preview")
    coords = _populate(sim)
    target = next((c for c in coords
                   if cl.clay_cue_for_chunk(sim, c) is not None), None)
    assert target is not None
    g = geo.chunk_geology(sim, target)
    layers_before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg)
                     for L in g.layers]
    sim.agents.pos[0, 0] = (target[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (target[1] + 0.5) * CHUNK_SIDE_M
    out = cl.shape_preview(sim, float(sim.agents.pos[0, 0]),
                           float(sim.agents.pos[0, 1]))
    cue = cl.clay_cue_for_chunk(sim, target)
    # non-mutating: geology untouched by the preview.
    layers_after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg)
                    for L in g.layers]
    assert layers_after == layers_before
    # the oracle agrees with the perception cue.
    assert out["can_shape"] == cue.workable_now
    assert out["fires_to_ceramic"] == cue.ceramic_grade
    assert out["material"] == cue.material


def test_injected_ceramic_clay_through_live_sim():
    sim = _booted_sim("c5_inject")
    coords = _populate(sim)
    target = coords[len(coords) // 2]
    chunk = sim.streamer.get(0, target)
    # a plastic potter's clay bank in a temperate floodplain.
    chunk.biome = np.full(np.asarray(chunk.biome).shape, _TEMPERATE,
                          dtype=np.asarray(chunk.biome).dtype)
    chunk.water = np.zeros(np.asarray(chunk.water).shape, dtype=np.float32)
    sim._geology_state.chunks[target] = ChunkGeology(coord=target, layers=[
        _layer(0.0, 1.0, "shale"),
        _layer(1.0, 5.0, "sandstone", ore={"fine_clay": 0.08}),
    ])
    sim._clay_cue_cache.clear()
    cue = cl.clay_cue_for_chunk(sim, target)
    assert cue is not None and cue.material == "fine_clay"
    assert cue.ceramic_grade is True and cue.workable_now is True


# ---------------------------------------------------------------------------
# Actionable pick : best_clay_near
# ---------------------------------------------------------------------------

def _put_chunk(sim, cc, layers, biome, w):
    ch = sim.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, biome,
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
    sim._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=layers)
    sim._clay_cue_cache.clear()


def _stand_on(sim, cc):
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M


# Perception radius small enough that only the agent's own chunk is in range
# (neighbour chunk centres sit a full CHUNK_SIDE_M away). Keeps the filter test
# isolated from whatever the procedural neighbours happen to carry.
_OWN_CHUNK_R = 0.4 * CHUNK_SIDE_M


def test_best_clay_near_prefers_ceramic_grade():
    sim = _booted_sim("c5_best")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    # a ceramic kaolin bank, but desert-dry → ceramic_grade yet NOT workable.
    _put_chunk(sim, cc,
               [_layer(0.0, 1.0, "sandstone"),
                _layer(1.0, 5.0, "sandstone", ore={"fine_clay": 0.08})],
               _DESERT, 0.0)
    _stand_on(sim, cc)
    best = cl.best_clay_near(sim, 0, perception_radius_m=_OWN_CHUNK_R)
    assert best is not None and best.material == "fine_clay" and best.ceramic_grade
    ceramic = cl.best_clay_near(sim, 0, perception_radius_m=_OWN_CHUNK_R,
                                require_ceramic=True)
    assert ceramic is not None and ceramic.ceramic_grade
    # the bone-dry kaolin is below the plastic limit → require_workable skips it
    # and, with nothing else in range, honestly reports 'no workable clay here'.
    assert cl.best_clay_near(sim, 0, perception_radius_m=_OWN_CHUNK_R,
                             require_workable=True) is None


def test_best_clay_near_require_workable_picks_plastic_clay():
    sim = _booted_sim("c5_best2")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    # shale topsoil in a grassland floodplain → brick-grade but workable now.
    _put_chunk(sim, cc, [_layer(0.0, 1.0, "shale")], _GRASS, 0.0)
    _stand_on(sim, cc)
    workable = cl.best_clay_near(sim, 0, perception_radius_m=_OWN_CHUNK_R,
                                 require_workable=True)
    assert workable is not None and workable.workable_now
    assert workable.material == "shale"
    # shale never fires to a watertight ceramic → require_ceramic finds nothing.
    assert cl.best_clay_near(sim, 0, perception_radius_m=_OWN_CHUNK_R,
                             require_ceramic=True) is None


# ---------------------------------------------------------------------------
# Determinism + install hygiene
# ---------------------------------------------------------------------------

def _cue_key(c):
    return None if c is None else (c.material, c.source,
                                   round(c.pottery_grade, 6),
                                   c.workable_now, c.ceramic_grade)


def test_determinism_same_seed():
    a = _booted_sim("det_a", seed=0xC1A7)
    b = _booted_sim("det_b", seed=0xC1A7)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    for coord in ca:
        assert _cue_key(cl.clay_cue_for_chunk(a, coord)) == \
               _cue_key(cl.clay_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("idem")
    _populate(sim)
    c1 = cl.install_clay_outcrop(sim)
    c2 = cl.install_clay_outcrop(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = cl.clay_cue_summary(sim)
    assert set(s) >= {"n_chunks", "n_chunks_with_cue", "cue_rate",
                      "n_workable_now", "n_ceramic_grade",
                      "best_pottery_grade", "by_class", "by_material"}
    assert 0.0 <= s["cue_rate"] <= 1.0
    assert s["n_workable_now"] <= s["n_chunks_with_cue"] <= s["n_chunks"]
    assert s["n_ceramic_grade"] <= s["n_chunks_with_cue"]
