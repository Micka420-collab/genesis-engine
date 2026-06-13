"""Invariants — Substrate capability : affleurement de combustible (Cap. C4).

Couvre :
- Échelle de rang houiller (peat < oil_shale < coal) + seuils (grade min,
  smelting, moisture-of-extinction) cohérents ; tell charbon noir mat (20,20,20).
- Dérivation pure : charbon en lithologie / tourbe en ore_mix ; le plus haut
  grade gagne ; filon profond → muet ; océan → masqué ; colonne non-organique →
  muet.
- **Porte d'humidité** : tourbe en bog gorgé d'eau → ``dry_to_burn`` (pas
  ``burnable_now``) ; même tourbe en site sec → ``burnable_now``.
- **« Le monde ne ment jamais »** : tout indice ⇒ combustible réel peu profond
  dans la même colonne que ``mine_at`` ; ``burnable_now`` ⇒ grade ≥ seuil & sec ;
  ``smelting_grade`` ⇒ grade ≥ seuil de fusion — colonnes synthétiques ET monde
  Genesis réel (boreal forest, seed 0xB0).
- ``ignite_preview`` est un aperçu **non mutant** et ``sustains_fire`` n'est vrai
  que pour un combustible sec, de grade suffisant, réellement présent.
- ``best_fuel_near`` préfère le charbon et filtre (burnable / smelting).
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
import engine.combustible_outcrop as co                             # noqa: E402

_BOREAL = 3    # BOREAL_FOREST — wet (bog) ; both peat & coal affinity
_DESERT = 7    # HOT_DESERT — dry ; used to make a fuel burnable
_FOREST = 4    # TEMPERATE_FOREST — non-ocean


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Chunk:
    """Minimal stand-in carrying the fields the derivation reads."""
    def __init__(self, water, biome, height):
        self.water = water
        self.biome = biome
        self.height = height


def _chunk(w=10.0, biome=_BOREAL, elev=500.0, side=8):
    return _Chunk(np.full((side, side), w, dtype=np.float32),
                  np.full((side, side), biome, dtype=np.uint8),
                  np.full((side, side), elev, dtype=np.float32))


def _layer(top, bottom, rock="shale", density=2400.0, ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom,
                       rock_type=rock, density_kg_m3=density,
                       ore_mix=dict(ore or {}))


def _booted_sim(name: str, seed: int = 0xB0, *, resolution: int = 128):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    geo.install_geology(sim)
    co.install_combustible_outcrop(sim)
    return sim


def _populate(sim, grid: int = 10):
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

def test_fuel_grades_and_thresholds_ordered():
    g = {m: p.calorific_grade for m, p in co._PROFILE.items()}
    assert g["peat"] < g["oil_shale"] < g["coal"]
    assert 0.0 < co.MIN_FUEL_GRADE <= g["peat"]          # peat still sustains a fire
    assert g["peat"] < co.SMELTING_GRADE <= g["coal"]    # only coal smelts
    assert g["oil_shale"] < co.SMELTING_GRADE
    assert 0.0 < co.MOISTURE_EXTINCTION < 1.0


def test_profile_materials_exist_in_catalogue():
    for material in co._PROFILE:
        assert material in MINERAL_BY_NAME


def test_coal_tell_is_matte_black():
    # The byte-exact tell an agent learns to seek for a furnace; mirrors the
    # Rust Mineral::Coal::surface_color() = [20,20,20] (locked cross-language
    # in tests/test_geology_cross_language_contract.py).
    assert co._PROFILE["coal"].rgb == (20, 20, 20)


# ---------------------------------------------------------------------------
# Pure derivation
# ---------------------------------------------------------------------------

def test_coal_seam_as_lithology():
    layers = [_layer(0.0, 1.0, "shale"),
              _layer(1.0, 5.0, "coal")]            # a coal seam as bedrock/rock
    cue = co._cue_from_geology((0, 0, 0), layers, _DESERT, _chunk(biome=_DESERT))
    assert cue is not None and cue.material == "coal"
    assert cue.source == "lithology" and cue.fuel_class == co.FuelClass.COAL
    assert cue.smelting_grade is True and cue.burnable_now is True   # dry desert


def test_peat_in_wet_bog_is_seen_but_not_burnable():
    # Peat present shallow in a waterlogged boreal bog → visible, but too wet to
    # light now: the emergent "cut & dry first" loop.
    layers = [_layer(0.0, 4.0, "shale", ore={"peat": 0.05})]
    cue = co._cue_from_geology((0, 0, 0), layers, _BOREAL,
                               _chunk(biome=_BOREAL, w=10.0))
    assert cue is not None and cue.material == "peat"
    assert cue.source == "ore" and cue.fuel_class == co.FuelClass.PEAT
    assert cue.burnable_now is False and cue.dry_to_burn is True
    assert cue.smelting_grade is False
    assert cue.effective_moisture > co.MOISTURE_EXTINCTION


def test_same_peat_burns_when_site_is_dry():
    layers = [_layer(0.0, 4.0, "shale", ore={"peat": 0.05})]
    dry = co._cue_from_geology((0, 0, 0), layers, _DESERT,
                               _chunk(biome=_DESERT, w=0.0))
    assert dry is not None and dry.material == "peat"
    assert dry.effective_moisture <= co.MOISTURE_EXTINCTION
    assert dry.burnable_now is True and dry.dry_to_burn is False


def test_standing_water_raises_moisture():
    layers = [_layer(0.0, 4.0, "shale", ore={"oil_shale": 0.05})]
    drier = co._cue_from_geology((0, 0, 0), layers, _FOREST,
                                 _chunk(biome=_FOREST, w=0.0))
    wetter = co._cue_from_geology((0, 0, 0), layers, _FOREST,
                                  _chunk(biome=_FOREST, w=co.WATER_SATURATION_L))
    assert wetter.ambient_moisture > drier.ambient_moisture


def test_highest_grade_wins_over_shallower_peat():
    # Both peat (shallow) and coal (slightly deeper) reachable → coal wins.
    layers = [_layer(0.0, 2.0, "shale", ore={"peat": 0.05}),
              _layer(2.0, 5.0, "shale", ore={"coal": 0.04})]
    cue = co._cue_from_geology((0, 0, 0), layers, _DESERT, _chunk(biome=_DESERT))
    assert cue is not None and cue.material == "coal" and cue.smelting_grade


def test_deep_seam_is_silent():
    layers = [_layer(0.0, 5.0, "shale"),
              _layer(co.MAX_SEAM_DEPTH_M + 10.0, 200.0, "shale",
                     ore={"coal": 0.10})]
    assert co._cue_from_geology((0, 0, 0), layers, _FOREST, _chunk()) is None


def test_faint_fraction_is_silent():
    layers = [_layer(0.0, 4.0, "shale",
                     ore={"coal": co.MIN_VISIBLE_FRACTION / 2.0})]
    assert co._cue_from_geology((0, 0, 0), layers, _FOREST, _chunk()) is None


def test_ocean_is_masked():
    layers = [_layer(0.0, 4.0, "shale", ore={"coal": 0.10})]
    assert co._cue_from_geology((0, 0, 0), layers, int(Biome.OCEAN),
                                _chunk(biome=int(Biome.OCEAN))) is None


def test_non_fuel_column_is_silent():
    layers = [_layer(0.0, 5.0, "limestone", ore={"hematite": 0.05}),
              _layer(5.0, 50.0, "sandstone", ore={"native_copper": 0.02})]
    assert co._cue_from_geology((0, 0, 0), layers, _FOREST, _chunk()) is None


# ---------------------------------------------------------------------------
# "Le monde ne ment jamais" — synthetic + real Genesis world
# ---------------------------------------------------------------------------

def _assert_cue_truthful(cue, layers):
    if cue is None:
        return
    grounded = False
    for L in layers:
        if L.depth_top_m > co.MAX_SEAM_DEPTH_M:
            continue
        if cue.source == "lithology" and L.rock_type == cue.material:
            grounded = True
        if cue.source == "ore" and \
                L.ore_mix.get(cue.material, 0.0) >= co.MIN_VISIBLE_FRACTION:
            grounded = True
    assert grounded, f"cue {cue.material} not grounded in a shallow layer"
    if cue.burnable_now:
        assert cue.calorific_grade >= co.MIN_FUEL_GRADE
        assert cue.effective_moisture <= co.MOISTURE_EXTINCTION
    if cue.smelting_grade:
        assert cue.calorific_grade >= co.SMELTING_GRADE


def test_world_never_lies_on_real_world():
    sim = _booted_sim("c4_neverlies")
    coords = _populate(sim)
    assert len(coords) > 0
    n_cued = 0
    for coord in coords:
        cue = co.combustible_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_cued += 1
        g = geo.chunk_geology(sim, coord)
        _assert_cue_truthful(cue, g.layers if g else [])
    # the canonical boreal seed must actually surface fuel (peat + coal).
    assert n_cued > 0


def test_ignite_preview_non_mutating_and_truthful():
    sim = _booted_sim("c4_preview")
    coords = _populate(sim)
    # find a chunk that emits a cue.
    target = next((c for c in coords
                   if co.combustible_cue_for_chunk(sim, c) is not None), None)
    assert target is not None
    g = geo.chunk_geology(sim, target)
    layers_before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg)
                     for L in g.layers]
    sim.agents.pos[0, 0] = (target[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (target[1] + 0.5) * CHUNK_SIDE_M
    out = co.ignite_preview(sim, float(sim.agents.pos[0, 0]),
                            float(sim.agents.pos[0, 1]))
    cue = co.combustible_cue_for_chunk(sim, target)
    # non-mutating: geology untouched by the preview.
    layers_after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg)
                    for L in g.layers]
    assert layers_after == layers_before
    # the oracle agrees with the perception cue.
    assert out["sustains_fire"] == cue.burnable_now
    assert out["smelting_grade"] == cue.smelting_grade
    assert out["material"] == cue.material


def test_injected_coal_seam_through_live_sim():
    sim = _booted_sim("c4_inject")
    coords = _populate(sim)
    target = coords[len(coords) // 2]
    chunk = sim.streamer.get(0, target)
    # a dry exposed coal seam.
    chunk.biome = np.full(np.asarray(chunk.biome).shape, _DESERT,
                          dtype=np.asarray(chunk.biome).dtype)
    chunk.water = np.zeros(np.asarray(chunk.water).shape, dtype=np.float32)
    sim._geology_state.chunks[target] = ChunkGeology(coord=target, layers=[
        _layer(0.0, 1.0, "shale"),
        _layer(1.0, 5.0, "shale", ore={"coal": 0.08}),
    ])
    sim._combustible_cue_cache.clear()
    cue = co.combustible_cue_for_chunk(sim, target)
    assert cue is not None and cue.material == "coal"
    assert cue.burnable_now is True and cue.smelting_grade is True


# ---------------------------------------------------------------------------
# Actionable pick : best_fuel_near
# ---------------------------------------------------------------------------

def test_best_fuel_near_prefers_coal_and_filters():
    sim = _booted_sim("c4_best")
    coords = _populate(sim)
    # place a coal seam + a peat bog near the agent on two adjacent chunks.
    cx, cy, _ = coords[len(coords) // 2]
    coal_coord = (cx, cy, 0)
    peat_coord = (cx + 1, cy, 0)
    if sim.streamer.get(0, peat_coord) is None:
        peat_coord = (cx - 1, cy, 0)
    for cc, ore, biome, w in (
            (coal_coord, {"coal": 0.08}, _DESERT, 0.0),       # dry coal → burnable
            (peat_coord, {"peat": 0.06}, _BOREAL, 10.0)):     # wet peat → not burnable
        ch = sim.streamer.get(0, cc)
        ch.biome = np.full(np.asarray(ch.biome).shape, biome,
                           dtype=np.asarray(ch.biome).dtype)
        ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
        sim._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=[
            _layer(0.0, 1.0, "shale"), _layer(1.0, 5.0, "shale", ore=ore)])
    sim._combustible_cue_cache.clear()
    sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    r = 3 * CHUNK_SIDE_M
    best = co.best_fuel_near(sim, 0, perception_radius_m=r)
    assert best is not None and best.material == "coal"
    smelt = co.best_fuel_near(sim, 0, perception_radius_m=r, require_smelting=True)
    assert smelt is not None and smelt.smelting_grade
    burn = co.best_fuel_near(sim, 0, perception_radius_m=r, require_burnable=True)
    assert burn is not None and burn.burnable_now  # the wet peat is skipped


# ---------------------------------------------------------------------------
# Determinism + install hygiene
# ---------------------------------------------------------------------------

def _cue_key(c):
    return None if c is None else (c.material, c.source,
                                   round(c.calorific_grade, 6),
                                   c.burnable_now, c.smelting_grade)


def test_determinism_same_seed():
    a = _booted_sim("det_a", seed=0xB0)
    b = _booted_sim("det_b", seed=0xB0)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    for coord in ca:
        assert _cue_key(co.combustible_cue_for_chunk(a, coord)) == \
               _cue_key(co.combustible_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("idem")
    _populate(sim)
    c1 = co.install_combustible_outcrop(sim)
    c2 = co.install_combustible_outcrop(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = co.combustible_cue_summary(sim)
    assert set(s) >= {"n_chunks", "n_chunks_with_cue", "cue_rate",
                      "n_burnable_now", "n_smelting_grade",
                      "best_calorific_grade", "by_class", "by_material"}
    assert 0.0 <= s["cue_rate"] <= 1.0
    assert s["n_burnable_now"] <= s["n_chunks_with_cue"] <= s["n_chunks"]
    assert s["n_smelting_grade"] <= s["n_chunks_with_cue"]
