"""Invariants — Substrate capability : le four à tirage (Cap. C11).

Couvre :
- **L'apparatus qui élève la température** (le pendant de C7) : un feu enclos dans
  une argile de paroi (C5) atteint une pointe **plus haute** qu'un feu nu — la VOÛTE
  que C9 (``vitrifies_if_kiln_fired``) ET C10 (``would_mortar_if_kiln_fired``)
  désignent toutes deux. Le monde s'engage sur ``kiln_peak_temp_c`` (SSOT
  déterministe), RÉUTILISE VERBATIM la pointe du feu de C9 (``open_fire_peak_temp_c``,
  le combo) et la plafonne par la réfractarité de paroi.
- **Composition, pas nouveau tell (garde-fou D8)** : pas de ``_PROFILE``, aucune
  entrée ``PY_TO_RUST`` ; hors glob ``*_outcrop.py``. Lit C5 ``clay_outcrop`` (paroi +
  ``ceramic_grade``), C7 ``fire_ignition`` (``fine_fuel``) et C6 ``limestone_outcrop``
  (carbonate, pour réaliser le mortier). 5ᵉ capacité D8-par-composition.
- **Effet 1+1>2** : four possible QUE si argile-de-paroi (C5) ET feu (C7)
  coexistent ; il débloque DEUX transformations différées d'un coup (mortier C10,
  kaolin sain C9).
- **L'inversion DE l'inversion (le rachat du kaolin C9)** : le kaolin réfractaire (la
  *mauvaise* argile de poterie de C9) est la **meilleure argile de PAROI** — c'est lui
  qui bâtit le four assez chaud pour cuire le kaolin **à cœur**. Une paroi commune
  (plafond 1000 °C) ne cuit JAMAIS le kaolin sain ; une paroi réfractaire (1150 °C) si.
- **La marche différée honnête** : le tirage naturel ne vitrifie jamais la porcelaine
  (``vitrifies_watertight`` toujours False) — ``vitrifies_if_forced_draught`` porte le
  potentiel du soufflet + charbon (C12+), exactement comme C9/C10 différaient le four.
- **« Le monde ne ment jamais »** : tout cue ⇒ ``buildable`` ; argile (C5) ET feu (C7)
  réels ; ``kiln_peak_c`` ≥ pointe du feu nu, ≤ plafond de paroi ; mortier réalisé ⇒
  carbonate présent — colonnes synthétiques ET monde Genesis réel (seed 0xBEEF).
- ``kiln_preview`` non mutant nomme l'ingrédient manquant.
- ``best_kiln_site_near`` préfère la pointe la plus haute (paroi réfractaire).
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
import engine.clay_outcrop as ci                                    # noqa: E402
import engine.fire_ignition as fi                                   # noqa: E402
import engine.limestone_outcrop as li                               # noqa: E402
import engine.ceramic_firing as cf                                  # noqa: E402
import engine.lime_burning as lb                                    # noqa: E402
import engine.kiln_draft as kd                                      # noqa: E402

_GRASS = 6        # GRASSLAND — dry, fire-makeable, fine_fuel 0.80 (prime tinder)
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
    """Compose exactly as the capability does, from a raw geology column."""
    clay = ci._cue_from_geology(coord, layers, biome, chunk)
    fire = fi._cue_from_geology(coord, layers, biome, chunk)
    lime = li._cue_from_geology(coord, layers, biome, chunk)
    return kd._cue_from_inputs(coord, clay, fire, lime)


# Common earthenware clay = shale lithology (COMMON wall — caps low, slumps ~1000 C).
def _common_clay():
    return [_layer(0.0, 4.0, "shale")]


# Refractory clay = fine_clay (kaolin) in the ore-mix (PLASTIC, ceramic_grade wall).
def _kaolin():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06})]


# Refractory kaolin walls AND a pure mortar-grade carbonate in the same column.
def _kaolin_plus_pure_limestone():
    return [_layer(0.0, 4.0, "sandstone",
                   ore={"fine_clay": 0.06, "limestone_pure": 0.06})]


def _common_clay_plus_pure_limestone():
    return [_layer(0.0, 4.0, "shale", ore={"limestone_pure": 0.06})]


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
    kd.install_kiln_draft(sim)
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

def test_kiln_peak_enclosure_gain_over_open_fire():
    """The apparatus only encloses C9's fire: kiln peak >= open-fire peak, rising
    monotonically with fuel, never below the bare fire it is built around."""
    for f in (0.4, 0.6, 0.8, 1.0):
        open_peak = cf.open_fire_peak_temp_c(f)
        for refrac in (False, True):
            kp = kd.kiln_peak_temp_c(f, refrac)
            assert kp >= open_peak                    # enclosure never cools the fire
    # monotone in fuel for a fixed wall (until the cap bites)
    assert kd.kiln_peak_temp_c(0.4, True) < kd.kiln_peak_temp_c(0.8, True)


def test_refractory_walls_cap_higher_than_common():
    """A refractory (kaolin) wall survives a hotter kiln than a common clay wall
    that slumps near ~1000 C — so at rich fuel the refractory kiln runs hotter."""
    assert kd.KILN_REFRACTORY_WALL_CAP_C > kd.KILN_COMMON_WALL_CAP_C
    # at rich fuel the difference bites: refractory peak strictly above common peak.
    assert kd.kiln_peak_temp_c(1.0, True) > kd.kiln_peak_temp_c(1.0, False)
    assert kd.kiln_peak_temp_c(1.0, False) == kd.KILN_COMMON_WALL_CAP_C
    # both capped (never reach forced-draught bloomery temperatures)
    assert kd.kiln_peak_temp_c(1.0, True) <= kd.KILN_REFRACTORY_WALL_CAP_C


def test_reuses_c9_open_fire_peak_ssot():
    """The combo: C11 reuses C9's open-fire peak SSOT verbatim as its base — it does
    NOT re-model the fire's heat, it only encloses it."""
    import inspect
    src = inspect.getsource(kd)
    assert "import engine.ceramic_firing" in src
    assert "open_fire_peak_temp_c" in src
    cue = _derive((0, 0, 0), _common_clay(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None
    assert cue.open_fire_peak_c == round(cf.open_fire_peak_temp_c(cue.fine_fuel), 1)
    assert cue.kiln_peak_c >= cue.open_fire_peak_c


def test_reuses_c10_calcination_ssots_for_mortar():
    """Mortar realization recomposes C10's calcination SSOTs at the kiln peak — no
    re-modelling of the lime chemistry."""
    import inspect
    src = inspect.getsource(kd)
    assert "import engine.lime_burning" in src
    assert "calcination_extent" in src and "quicklime_quality" in src
    cue = _derive((0, 0, 0), _kaolin_plus_pure_limestone(), _GRASS,
                  _chunk(biome=_GRASS))
    assert cue is not None and cue.limestone_here is True
    onset = lb.calcination_onset_c(li.LimeClass.PURE_CARBONATE)
    extent = lb.calcination_extent(cue.kiln_peak_c, onset)
    assert cue.mortar_lime_yield == round(lb.quicklime_quality(0.95, extent), 4)


def test_introduces_no_new_tell():
    """C11 composes C5 clay + C7 fire (+ C6 carbonate); it surfaces no new
    buried-mineral cue — the D8-by-composition decision (5th time, after C7/C8/C9/C10).
    """
    assert not hasattr(kd, "_PROFILE")
    # it is NOT an *_outcrop.py capability (exempt from the cross-language guardrail).
    assert not Path(kd.__file__).name.endswith("_outcrop.py")
    # the materials it reasons about are real catalogue tells C5/C6 already surface.
    for mat in ("fine_clay", "limestone_pure"):
        assert mat in MINERAL_BY_NAME
    assert "fine_clay" in ci._PROFILE and "limestone_pure" in li._PROFILE
    # it strictly reads C5 + C7 + C6 — no independent geology derivation of its own.
    import inspect
    src = inspect.getsource(kd)
    assert "clay_cue_for_chunk" in src and "ignition_cue_for_chunk" in src
    assert "limestone_cue_for_chunk" in src


def test_vitrification_never_in_natural_draught():
    """A natural-draught kiln never fully vitrifies refractory kaolin (maturation
    ~1250 C) — ``vitrifies_watertight`` stays False for ALL fuel loads, and the
    unrealized potential moves to ``vitrifies_if_forced_draught`` (the C12+ tier)."""
    maturation = cf.clay_maturation_temp_c(True)  # refractory kaolin maturation
    for f in (0.5, 0.7, 0.85, 1.0):
        peak = kd.kiln_peak_temp_c(f, True)
        firedness = min(1.0, peak / maturation)
        assert firedness < kd.VITRIFICATION_FIREDNESS
    # and the derived cue agrees: watertight False, forced-draught potential True.
    cue = _derive((0, 0, 0), _kaolin(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.clay_ceramic_grade is True
    assert cue.vitrifies_watertight is False
    assert cue.vitrifies_if_forced_draught is True


# ---------------------------------------------------------------------------
# Pure derivation — the apparatus outcomes
# ---------------------------------------------------------------------------

def test_common_clay_builds_common_walled_kiln():
    cue = _derive((0, 0, 0), _common_clay(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.buildable is True
    assert cue.wall_material == "shale"
    assert cue.wall_refractory is False
    assert cue.wall_cap_c == kd.KILN_COMMON_WALL_CAP_C
    assert cue.kiln_peak_c <= kd.KILN_COMMON_WALL_CAP_C
    # common earthenware clay (maturation 700) fires fully sound in any kiln.
    assert cue.fires_clay_sound is True
    assert cue.kiln_ware_quality == cue.clay_pottery_grade
    # a non-ceramic clay carries no vitrification potential at all.
    assert cue.vitrifies_watertight is False
    assert cue.vitrifies_if_forced_draught is False


def test_kaolin_builds_hotter_refractory_kiln():
    cue = _derive((0, 0, 0), _kaolin(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.buildable is True
    assert cue.wall_material == "fine_clay"
    assert cue.wall_refractory is True
    assert cue.wall_cap_c == kd.KILN_REFRACTORY_WALL_CAP_C
    # the refractory kiln runs hotter than the common one would at the same fuel,
    # and that extra heat fires the kaolin body SOUND (C9 redeemed).
    common_peak = kd.kiln_peak_temp_c(cue.fine_fuel, False)
    assert cue.kiln_peak_c > common_peak
    assert cue.fires_clay_sound is True
    assert cue.draft_gain_c > 0.0


def test_inversion_of_inversion_only_refractory_walls_fire_kaolin_sound():
    """The rachat du kaolin: a common-clay wall (cap 1000 C) can NEVER fire a
    refractory kaolin body sound (maturation 1250 C → firedness 0.80 < SOUND); only
    the kaolin's OWN refractory wall builds a kiln hot enough to fire it sound."""
    maturation = cf.clay_maturation_temp_c(True)
    common_firedness = min(1.0, kd.kiln_peak_temp_c(0.80, False) / maturation)
    refrac_firedness = min(1.0, kd.kiln_peak_temp_c(0.80, True) / maturation)
    assert common_firedness < cf.SOUND_MATURATION       # common walls: never sound
    assert refrac_firedness >= cf.SOUND_MATURATION       # refractory walls: sound
    # the world shows it: the refractory kaolin site fires its own body sound.
    cue = _derive((0, 0, 0), _kaolin(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.wall_refractory and cue.fires_clay_sound


def test_kiln_realizes_binding_mortar_c10_deferred():
    """The kiln realizes C10's ``would_mortar_if_kiln_fired``: a pure mortar-grade
    limestone, under-burnt in C10's open fire, hard-burns to binding lime here."""
    for layers in (_common_clay_plus_pure_limestone(),
                   _kaolin_plus_pure_limestone()):
        cue = _derive((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
        assert cue is not None and cue.buildable is True
        assert cue.limestone_here is True
        assert cue.realizes_binding_mortar is True
        assert 0.0 < cue.mortar_lime_yield <= 1.0


def test_open_fire_would_not_mortar_but_kiln_does():
    """The kiln is the key: at C10's open-fire peak a pure carbonate stays below
    ``MORTAR_CALCINATION`` (C10 ``mortar_ready`` False) — at the kiln peak it
    crosses it. Same stone, the enclosure makes the difference."""
    onset = lb.calcination_onset_c(li.LimeClass.PURE_CARBONATE)
    open_peak = cf.OPEN_FIRE_MAX_C
    assert lb.calcination_extent(open_peak, onset) < lb.MORTAR_CALCINATION
    kiln_peak = kd.kiln_peak_temp_c(0.80, False)   # even a humble common-walled kiln
    assert lb.calcination_extent(kiln_peak, onset) >= lb.MORTAR_CALCINATION


def test_clay_without_fire_is_not_buildable():
    # Boreal forest (moisture 0.60): clay underfoot but too wet for ANY fire (C7
    # None) → no kiln. The 1+1>2 gate.
    cue = _derive((0, 0, 0), _common_clay(), _BOREAL, _chunk(biome=_BOREAL))
    assert cue is None
    assert ci._cue_from_geology((0, 0, 0), _common_clay(), _BOREAL,
                                _chunk(biome=_BOREAL)) is not None
    assert fi._cue_from_geology((0, 0, 0), _common_clay(), _BOREAL,
                                _chunk(biome=_BOREAL)) is None


def test_fire_without_clay_is_not_buildable():
    # Dry grassland with a fire makeable, but bare granite — no wall-clay to line it.
    layers = [_layer(0.0, 5.0, "granite")]
    cue = _derive((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is None
    assert ci._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS)) is None
    assert fi._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS)) is not None


def test_limestone_optional_no_mortar_without_carbonate():
    # Clay + fire but no carbonate: the kiln is buildable, it just realizes no mortar.
    cue = _derive((0, 0, 0), _common_clay(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.buildable is True
    assert cue.limestone_here is False
    assert cue.realizes_binding_mortar is False
    assert cue.mortar_lime_yield == 0.0


# ---------------------------------------------------------------------------
# "Le monde ne ment jamais" — real Genesis world
# ---------------------------------------------------------------------------

def _assert_cue_truthful(sim, coord, cue):
    if cue is None:
        return
    assert cue.buildable is True
    # the enclosure never cools the fire, and never exceeds the wall's slump ceiling.
    assert cue.kiln_peak_c >= cue.open_fire_peak_c
    assert cue.kiln_peak_c <= cue.wall_cap_c
    assert cue.kiln_peak_c == round(
        kd.kiln_peak_temp_c(cue.fine_fuel, cue.wall_refractory), 1)
    # C5 really sees this wall-clay here...
    clay = ci.clay_cue_for_chunk(sim, coord)
    assert clay is not None and clay.material == cue.wall_material
    # ...and C7 really can make a fire here.
    assert fi.ignition_cue_for_chunk(sim, coord) is not None
    # ware quality agrees with the recomposed C9 SSOT.
    maturation = cf.clay_maturation_temp_c(cue.clay_ceramic_grade)
    firedness = min(1.0, cue.kiln_peak_c / maturation)
    assert abs(cue.kiln_ware_quality
               - cf.fired_ware_quality(cue.clay_pottery_grade, firedness)) <= 5e-4
    # a realized mortar implies a real mortar-grade carbonate underfoot (C6).
    if cue.realizes_binding_mortar:
        assert cue.limestone_here is True
        lime = li.limestone_cue_for_chunk(sim, coord)
        assert lime is not None and lime.mortar_grade is True


def test_world_never_lies_on_real_world():
    sim = _booted_sim("c11_neverlies")
    coords = _populate(sim)
    assert len(coords) > 0
    n_buildable = n_refractory = n_mortar = 0
    for coord in coords:
        cue = kd.kiln_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_buildable += 1
        if cue.wall_refractory:
            n_refractory += 1
        if cue.realizes_binding_mortar:
            n_mortar += 1
        _assert_cue_truthful(sim, coord, cue)
    # the grassland seed surfaces real buildable kiln sites, and the kiln realizes
    # binding mortar somewhere (C10's deferred potential is met in the real world).
    assert n_buildable > 0
    assert n_mortar > 0


def test_kiln_preview_non_mutating_and_truthful():
    sim = _booted_sim("c11_preview")
    coords = _populate(sim)
    target = next((c for c in coords
                   if kd.kiln_cue_for_chunk(sim, c) is not None), None)
    assert target is not None
    g = geo.chunk_geology(sim, target)
    before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    sim.agents.pos[0, 0] = (target[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (target[1] + 0.5) * CHUNK_SIDE_M
    out = kd.kiln_preview(sim, float(sim.agents.pos[0, 0]),
                          float(sim.agents.pos[0, 1]))
    cue = kd.kiln_cue_for_chunk(sim, target)
    after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    assert after == before                       # preview mutated nothing
    assert out["buildable"] is True
    assert out["kiln_peak_c"] == cue.kiln_peak_c
    assert out["draft_gain_c"] == cue.draft_gain_c
    assert out["realizes_binding_mortar"] == cue.realizes_binding_mortar


def test_preview_names_missing_clay():
    # Dry grassland, fire makeable, but bare granite — no wall-clay to line a kiln.
    sim = Simulation(SimConfig(name="c11_noclay", seed=1, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_GRASS, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(
        coord=cc, layers=[_layer(0.0, 5.0, "granite")])}
    out = kd.kiln_preview(sim, 4.0, 4.0)
    assert out["buildable"] is False
    assert out["has_clay"] is False
    assert "clay" in out["reason"]


def test_preview_names_missing_fire():
    # Clay underfoot but a soaked boreal forest: no fire can be made to run a kiln.
    sim = Simulation(SimConfig(name="c11_nofire", seed=2, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_BOREAL, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(coord=cc, layers=_common_clay())}
    out = kd.kiln_preview(sim, 4.0, 4.0)
    assert out["buildable"] is False
    assert out["has_fire"] is False
    assert "fire" in out["reason"]


def test_preview_shows_forced_draught_potential_for_kaolin():
    # A kaolin (refractory) site with fire: the kiln runs hot and fires the body
    # sound, but the world shows full vitrification as an UNREALIZED forced-draught
    # potential — never a watertight body in natural draught.
    sim = Simulation(SimConfig(name="c11_kaolin", seed=3, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_GRASS, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(coord=cc, layers=_kaolin())}
    out = kd.kiln_preview(sim, 4.0, 4.0)
    assert out["buildable"] is True
    assert out["wall_refractory"] is True
    assert out["vitrifies_watertight"] is False
    assert out["vitrifies_if_forced_draught"] is True


# ---------------------------------------------------------------------------
# Actionable pick : best_kiln_site_near
# ---------------------------------------------------------------------------

def _put_chunk(sim, cc, layers, biome, w):
    ch = sim.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, biome,
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
    sim._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=layers)
    sim._clay_cue_cache.clear()
    sim._ignition_cue_cache.clear()
    sim._limestone_cue_cache.clear()
    sim._kiln_draft_cue_cache.clear()


def test_best_kiln_site_prefers_hottest_refractory():
    sim = _booted_sim("c11_best")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    # a refractory kaolin site on the agent's own chunk — the hottest kiln in sight.
    _put_chunk(sim, cc, _kaolin(), _GRASS, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    best = kd.best_kiln_site_near(sim, 0, perception_radius_m=0.4 * CHUNK_SIDE_M)
    assert best is not None and best.buildable
    assert best.wall_refractory is True
    assert best.wall_material == "fine_clay"


def test_no_kiln_site_returns_none():
    # Bare hot desert: granite + no fine fuel → no clay, no fire: 'nothing to build'.
    sim = _booted_sim("c11_none")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, [_layer(0.0, 5.0, "granite")], _HOT_DESERT, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    assert kd.best_kiln_site_near(sim, 0,
                                  perception_radius_m=0.4 * CHUNK_SIDE_M) is None


# ---------------------------------------------------------------------------
# Determinism + install hygiene
# ---------------------------------------------------------------------------

def _cue_key(c):
    return None if c is None else (c.wall_material, c.wall_refractory,
                                   round(c.kiln_peak_c, 3),
                                   round(c.draft_gain_c, 3),
                                   c.fires_clay_sound, c.realizes_binding_mortar,
                                   round(c.mortar_lime_yield, 6))


def test_determinism_same_seed():
    a = _booted_sim("c11_det_a", seed=0xBEEF)
    b = _booted_sim("c11_det_b", seed=0xBEEF)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    for coord in ca:
        assert _cue_key(kd.kiln_cue_for_chunk(a, coord)) == \
               _cue_key(kd.kiln_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("c11_idem")
    _populate(sim)
    c1 = kd.install_kiln_draft(sim)
    c2 = kd.install_kiln_draft(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = kd.kiln_draft_summary(sim)
    assert set(s) >= {"n_chunks", "n_chunks_buildable", "buildable_rate",
                      "n_refractory_walled", "n_realizes_binding_mortar",
                      "n_fires_clay_sound", "best_kiln_peak_c", "best_draft_gain_c",
                      "by_wall_material"}
    assert 0.0 <= s["buildable_rate"] <= 1.0
    assert s["n_chunks_buildable"] <= s["n_chunks"]
    assert s["n_realizes_binding_mortar"] <= s["n_chunks_buildable"]
    assert s["best_kiln_peak_c"] <= kd.KILN_REFRACTORY_WALL_CAP_C
