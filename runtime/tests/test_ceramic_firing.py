"""Invariants — Substrate capability : cuisson de la céramique (Cap. C9).

Couvre :
- **Deuxième TRANSFORMATION** (après C8) : argile crue → tesson cuit. Le monde
  s'engage sur le résultat (SSOT ``fired_ware_quality`` / ``firedness``), gouverné
  par deux températures physiques : pointe du feu ouvert (``open_fire_peak_temp_c``,
  charge en combustible) × maturation de l'argile (``clay_maturation_temp_c``,
  réfractaire kaolin vs terre commune).
- **Composition, pas nouveau tell (garde-fou D8)** : pas de ``_PROFILE``, aucune
  entrée ``PY_TO_RUST`` ; lit C5 ``clay_outcrop`` (argile + ``pottery_grade`` +
  ``ceramic_grade``) et C7 ``fire_ignition`` (feu + ``fine_fuel``).
- **Effet 1+1>2** : cuisson possible QUE si argile (C5) ET feu (C7) coexistent —
  argile + foyer = cuisible ; argile sans feu (boréal détrempé) = non cuisible.
- **L'inversion réfractaire (le mensonge rendu visible)** : le kaolin (la
  *meilleure* argile, ``ceramic_grade`` True) **sous-cuit** au feu ouvert et donne
  un objet **pire** qu'une humble terre schisteuse cuite à cœur — le pendant
  symétrique de l'obsidienne de C8.
- **« Le monde ne ment jamais »** : tout cue ⇒ ``fireable`` ; l'argile existe
  (C5, même colonne que ``mine_at``) et le feu est faisable (C7) — colonnes
  synthétiques ET monde Genesis réel (seed 0xBEEF). ``watertight`` toujours False
  en feu ouvert (pas de vitrification sans four).
- ``firing_preview`` non mutant nomme l'ingrédient manquant.
- ``best_firing_site_near`` préfère la plus haute ``ware_quality`` (terre saine
  > kaolin sous-cuit).
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
from engine.world import CHUNK_SIDE_M                               # noqa: E402
from engine.mineral_catalog import MINERAL_BY_NAME                  # noqa: E402
import engine.clay_outcrop as cl                                    # noqa: E402
import engine.fire_ignition as fi                                   # noqa: E402
import engine.ceramic_firing as cf                                  # noqa: E402

_GRASS = 6        # GRASSLAND — dry, clay-workable, fire-makeable
_SAVANNA = 9      # SAVANNA — dry woodland, friction fire
_BOREAL = 3       # BOREAL_FOREST — clay-visible but too wet for any fire
_HOT_DESERT = 7   # HOT_DESERT — bare rock, no fine fuel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk(w=0.0, biome=_GRASS, side=8):
    from types import SimpleNamespace
    return SimpleNamespace(
        water=np.full((side, side), w, dtype=np.float32),
        biome=np.full((side, side), biome, dtype=np.uint8),
        height=np.full((side, side), 300.0, dtype=np.float32))


def _layer(top, bottom, rock="sandstone", ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=2400.0, ore_mix=dict(ore or {}))


def _derive(coord, layers, biome, chunk):
    """Compose the same way the capability does, from raw geology columns."""
    clay = cl._cue_from_geology(coord, layers, biome, chunk)
    fire = fi._cue_from_geology(coord, layers, biome, chunk)
    return cf._cue_from_inputs(coord, clay, fire)


# Common earthenware clay = shale lithology (brick/earthenware grade, low-firing).
def _earthenware():
    return [_layer(0.0, 4.0, "shale")]


# Refractory kaolin = fine_clay in the ore-mix (ceramic grade, kiln-grade).
def _kaolin():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06})]


def _booted_sim(name, seed=0xBEEF, resolution=128):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF, founders=4,
                    max_agents=20, bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed,
                                                       resolution=resolution,
                                                       n_plates=8))
    geo.install_geology(sim)
    cf.install_ceramic_firing(sim)
    return sim


def _populate(sim, grid=12):
    coords = []
    for cx in range(grid):
        for cy in range(grid):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return coords


# ---------------------------------------------------------------------------
# SSOT physics + composition contract (D8)
# ---------------------------------------------------------------------------

def test_open_fire_peak_temp_ssot():
    assert cf.open_fire_peak_temp_c(0.0) == cf.OPEN_FIRE_MIN_C
    assert cf.open_fire_peak_temp_c(1.0) == cf.OPEN_FIRE_MAX_C
    # monotone in fuel; a fuel-rich grassland fire is hotter than a sparse one.
    assert cf.open_fire_peak_temp_c(0.8) > cf.open_fire_peak_temp_c(0.35)
    # a bare open fire never reaches a refractory kiln temperature.
    assert cf.open_fire_peak_temp_c(1.0) < cf.REFRACTORY_MATURATION_C


def test_clay_maturation_ssot():
    # refractory kaolin needs far more heat than common earthenware clay.
    assert cf.clay_maturation_temp_c(True) == cf.REFRACTORY_MATURATION_C
    assert cf.clay_maturation_temp_c(False) == cf.EARTHENWARE_MATURATION_C
    assert cf.clay_maturation_temp_c(True) > cf.clay_maturation_temp_c(False)


def test_fired_ware_quality_ssot_sound_vs_underfired():
    # Sound firing (firedness >= SOUND): vessel takes the clay's intrinsic grade.
    assert cf.fired_ware_quality(0.45, 1.0) == 0.45
    assert cf.fired_ware_quality(0.45, cf.SOUND_MATURATION) == 0.45
    # Under-fired: capped hard by UNDERFIRED_CEILING, scaled by maturation.
    fd = 0.64
    expected = 0.85 * cf.UNDERFIRED_CEILING * (fd / cf.SOUND_MATURATION)
    assert cf.fired_ware_quality(0.85, fd) == expected
    # The inversion at the SSOT level: a fine kaolin under-fired scores BELOW a
    # humble earthenware fired sound.
    assert cf.fired_ware_quality(0.85, 0.64) < cf.fired_ware_quality(0.45, 1.0)


def test_introduces_no_new_tell():
    """C9 composes C5 clay + C7 fire; it surfaces no new buried-mineral cue.

    Documents (and asserts) the D8 decision: ``ceramic_firing`` is NOT an
    ``*_outcrop.py`` with a ``_PROFILE`` table, so the cross-language guardrail
    neither classifies it nor needs to. The clays it transforms are already
    classified tells / catalogue minerals from C5.
    """
    assert not hasattr(cf, "_PROFILE")
    # The clays it fires are real catalogue minerals C5 already surfaces.
    for clay in ("fine_clay", "shale"):
        assert clay in MINERAL_BY_NAME
        assert clay in cl._PROFILE
    # It strictly reads C5 + C7 — no independent geology derivation of its own.
    import inspect
    src = inspect.getsource(cf)
    assert "clay_cue_for_chunk" in src and "ignition_cue_for_chunk" in src


# ---------------------------------------------------------------------------
# Pure derivation — the firing outcomes
# ---------------------------------------------------------------------------

def test_earthenware_fires_sound():
    cue = _derive((0, 0, 0), _earthenware(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.fireable is True
    assert cue.clay_material == "shale"
    assert cue.ceramic_grade is False
    assert cue.is_sound is True and cue.underfired is False
    # ware quality is the clay's intrinsic earthenware grade (no vitrification).
    assert cue.ware_quality == cue.pottery_grade
    assert cue.watertight is False
    assert cue.fire_method in ("PERCUSSION", "FRICTION")


def test_kaolin_underfires_in_open_fire_the_lie():
    # Kaolin is the BEST clay (ceramic_grade True, pottery_grade 0.85) and a fire
    # is makeable — yet a bare open fire under-fires refractory kaolin. The world
    # must not lie: it shows the unrealized watertight potential, not a finished pot.
    cue = _derive((0, 0, 0), _kaolin(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.fireable is True
    assert cue.clay_material == "fine_clay"
    assert cue.ceramic_grade is True
    assert cue.underfired is True and cue.is_sound is False
    assert cue.watertight is False              # open fire never vitrifies
    assert cue.vitrifies_if_kiln_fired is True  # the unrealized kiln potential


def test_refractory_inversion_earthenware_beats_kaolin():
    """The C9 inversion (pendant of C8's obsidian): in an open fire the humble
    earthenware out-performs the prettier kaolin."""
    earth = _derive((0, 0, 0), _earthenware(), _GRASS, _chunk(biome=_GRASS))
    kaolin = _derive((0, 0, 0), _kaolin(), _GRASS, _chunk(biome=_GRASS))
    assert earth is not None and kaolin is not None
    assert earth.is_sound and kaolin.underfired
    assert earth.ware_quality > kaolin.ware_quality


def test_clay_without_fire_is_not_fireable():
    # Boreal forest (moisture 0.60) is clay-visible but too wet for ANY fire
    # (C7 returns None). Clay underfoot, but you cannot fire it here.
    cue = _derive((0, 0, 0), _earthenware(), _BOREAL, _chunk(biome=_BOREAL))
    assert cue is None
    # ...and C5 still sees the clay, C7 still refuses the fire — the 1+1>2 gate.
    assert cl._cue_from_geology((0, 0, 0), _earthenware(), _BOREAL,
                                _chunk(biome=_BOREAL)) is not None
    assert fi._cue_from_geology((0, 0, 0), _earthenware(), _BOREAL,
                                _chunk(biome=_BOREAL)) is None


def test_fire_without_clay_is_not_fireable():
    # Dry grassland with a fire makeable, but bare granite — no clay to fire.
    layers = [_layer(0.0, 5.0, "granite")]
    cue = _derive((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is None
    assert cl._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS)) is None
    assert fi._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS)) is not None


# ---------------------------------------------------------------------------
# "Le monde ne ment jamais" — real Genesis world
# ---------------------------------------------------------------------------

def _assert_cue_truthful(sim, coord, cue):
    if cue is None:
        return
    assert cue.fireable is True
    assert 0.0 <= cue.ware_quality <= 1.0
    assert cf.OPEN_FIRE_MIN_C <= cue.peak_temp_c <= cf.OPEN_FIRE_MAX_C
    assert cue.watertight is False
    # ware quality agrees with the SSOT outcome
    assert cue.ware_quality == cf.fired_ware_quality(cue.pottery_grade, cue.firedness)
    # C5 really sees this clay here...
    clay = cl.clay_cue_for_chunk(sim, coord)
    assert clay is not None and clay.material == cue.clay_material
    # ...and C7 really can make a fire here.
    assert fi.ignition_cue_for_chunk(sim, coord) is not None


def test_world_never_lies_on_real_world():
    sim = _booted_sim("c9_neverlies")
    coords = _populate(sim)
    assert len(coords) > 0
    n_fireable = 0
    for coord in coords:
        cue = cf.firing_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_fireable += 1
        _assert_cue_truthful(sim, coord, cue)
    # the grassland seed must surface real fireable (clay + fire) sites.
    assert n_fireable > 0


def test_firing_preview_non_mutating_and_truthful():
    sim = _booted_sim("c9_preview")
    coords = _populate(sim)
    target = next((c for c in coords
                   if cf.firing_cue_for_chunk(sim, c) is not None), None)
    assert target is not None
    g = geo.chunk_geology(sim, target)
    before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    sim.agents.pos[0, 0] = (target[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (target[1] + 0.5) * CHUNK_SIDE_M
    out = cf.firing_preview(sim, float(sim.agents.pos[0, 0]),
                            float(sim.agents.pos[0, 1]))
    cue = cf.firing_cue_for_chunk(sim, target)
    after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    assert after == before                       # preview mutated nothing
    assert out["fireable"] is True
    assert out["ware_quality"] == cue.ware_quality
    assert out["firedness"] == cue.firedness
    assert out["peak_temp_c"] == cue.peak_temp_c


def test_preview_names_missing_clay():
    # Dry grassland, fire makeable, but bare granite — no clay to fire.
    sim = Simulation(SimConfig(name="c9_noclay", seed=1, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_GRASS, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(
        coord=cc, layers=[_layer(0.0, 5.0, "granite")])}
    out = cf.firing_preview(sim, 4.0, 4.0)
    assert out["fireable"] is False
    assert out["has_clay"] is False
    assert "clay" in out["reason"]


def test_preview_names_missing_fire():
    # Clay underfoot but a soaked boreal forest: no fire can be made.
    sim = Simulation(SimConfig(name="c9_nofire", seed=2, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_BOREAL, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(coord=cc, layers=_earthenware())}
    out = cf.firing_preview(sim, 4.0, 4.0)
    assert out["fireable"] is False
    assert out["has_fire"] is False
    assert "fire" in out["reason"]


def test_preview_kaolin_lie_is_visible():
    # A fine kaolin outcrop with fire: fireable, but the open fire under-fires it —
    # the preview shows the unrealized watertight potential, not a finished pot.
    sim = Simulation(SimConfig(name="c9_kaolin", seed=3, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_GRASS, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(coord=cc, layers=_kaolin())}
    out = cf.firing_preview(sim, 4.0, 4.0)
    assert out["fireable"] is True
    assert out["clay_material"] == "fine_clay"
    assert out["underfired"] is True
    assert out["watertight"] is False
    assert out["vitrifies_if_kiln_fired"] is True


# ---------------------------------------------------------------------------
# Actionable pick : best_firing_site_near
# ---------------------------------------------------------------------------

def _put_chunk(sim, cc, layers, biome, w):
    ch = sim.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, biome,
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
    sim._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=layers)
    sim._clay_cue_cache.clear()
    sim._ignition_cue_cache.clear()
    sim._firing_cue_cache.clear()


def test_best_firing_site_prefers_sound_earthenware_over_kaolin():
    sim = _booted_sim("c9_best")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    # an earthenware site on the agent's own chunk — sound, the best ware here.
    _put_chunk(sim, cc, _earthenware(), _GRASS, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    best = cf.best_firing_site_near(sim, 0, perception_radius_m=0.4 * CHUNK_SIDE_M)
    assert best is not None and best.fireable
    assert best.clay_material == "shale"
    assert best.is_sound is True


def test_no_firing_site_returns_none():
    # Bare hot desert: granite + no fine fuel → no clay, no fire: an honest
    # 'nothing to fire here'.
    sim = _booted_sim("c9_none")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, [_layer(0.0, 5.0, "granite")], _HOT_DESERT, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    assert cf.best_firing_site_near(sim, 0,
                                    perception_radius_m=0.4 * CHUNK_SIDE_M) is None


# ---------------------------------------------------------------------------
# Determinism + install hygiene
# ---------------------------------------------------------------------------

def _cue_key(c):
    return None if c is None else (c.clay_material, round(c.peak_temp_c, 3),
                                   round(c.firedness, 6),
                                   round(c.ware_quality, 6), c.is_sound,
                                   c.fire_method)


def test_determinism_same_seed():
    a = _booted_sim("c9_det_a", seed=0xBEEF)
    b = _booted_sim("c9_det_b", seed=0xBEEF)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    for coord in ca:
        assert _cue_key(cf.firing_cue_for_chunk(a, coord)) == \
               _cue_key(cf.firing_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("c9_idem")
    _populate(sim)
    c1 = cf.install_ceramic_firing(sim)
    c2 = cf.install_ceramic_firing(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = cf.firing_summary(sim)
    assert set(s) >= {"n_chunks", "n_chunks_fireable", "fireable_rate",
                      "n_sound", "n_underfired", "best_ware_quality",
                      "best_peak_temp_c", "by_clay_material"}
    assert 0.0 <= s["fireable_rate"] <= 1.0
    assert s["n_chunks_fireable"] <= s["n_chunks"]
    assert s["n_sound"] + s["n_underfired"] == s["n_chunks_fireable"]
    assert s["best_peak_temp_c"] <= cf.OPEN_FIRE_MAX_C
