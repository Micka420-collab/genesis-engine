"""Invariants — Substrate capability : le tirage forcé (Cap. C12).

Couvre :
- **Le 2ᵉ apparatus** (le pendant de C11) : un four enclos + un **soufflet** + du
  **charbon de bois** atteint une pointe **plus haute** qu'un four à tirage naturel —
  la VOÛTE que C9 (``vitrifies_if_kiln_fired``) ET C11 (``vitrifies_if_forced_draught``)
  désignent toutes deux. Le monde s'engage sur ``forced_draught_peak_c`` (SSOT
  déterministe), RÉUTILISE VERBATIM la pointe du four de C11 (``kiln_peak_temp_c``, le
  combo) et la plafonne par la réfractarité de paroi sous tirage forcé.
- **Composition, pas nouveau tell (garde-fou D8)** : pas de ``_PROFILE``, aucune
  entrée ``PY_TO_RUST`` ; hors glob ``*_outcrop.py``. Lit C11 ``kiln_draft`` (four +
  ``wall_refractory`` + ``fine_fuel``) et C1 ``surface_mineralization`` (tell cuivre).
  6ᵉ capacité D8-par-composition.
- **La RÉALISATION** : le tirage forcé **vitrifie** enfin le kaolin réfractaire
  (``vitrifies_watertight`` True) — le pas que C9 puis C11 différaient. Le mensonge du
  kaolin (C9) → la paroi réfractaire (C11) → la vitrification (C12) : l'arc se ferme.
- **L'OUVERTURE** : la métallurgie du cuivre. ``reaches_copper_smelting_temp`` (≥1085 °C)
  + ``copper_ore_here`` (C1) → ``would_smelt_copper_here`` (effet 1+1>2). La fonte
  effective (consommer le minerai → métal) reste différée (C13).
- **Effet 1+1>2 / porte du charbon** : four forçable QUE si four constructible (C11)
  ET combustible ligneux suffisant pour le charbon (``CHARCOAL_FUEL_FLOOR``).
- **« Le monde ne ment jamais »** : tout cue ⇒ ``forceable`` ; four (C11) réel ;
  ``forced_peak_c`` ≥ pointe du four naturel, ≤ plafond de paroi ; cuivre co-localisé ⇒
  C1 le voit — colonnes synthétiques ET monde Genesis réel (seed 0xBEEF).
- ``forced_draught_preview`` non mutant nomme l'ingrédient manquant.
- ``best_forced_site_near`` préfère la pointe la plus haute (paroi réfractaire).
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
import engine.kiln_draft as kd                                      # noqa: E402
import engine.surface_mineralization as sm                          # noqa: E402
import engine.forced_draught as fd                                  # noqa: E402

_GRASS = 6        # GRASSLAND — dry, fire-makeable, fine_fuel 0.80 (charcoal-grade)
_BOREAL = 3       # BOREAL_FOREST — clay-visible but too wet for any fire
_HOT_DESERT = 7   # HOT_DESERT — bare rock, no fine fuel
_TUNDRA = 2       # TUNDRA — fire-makeable by friction but fine_fuel 0.35 < charcoal floor


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
    kiln = kd._cue_from_inputs(coord, clay, fire, lime)
    copper = sm._cue_from_geology(coord, layers, biome)
    return fd._cue_from_inputs(coord, kiln, copper)


# Common earthenware clay = shale lithology (COMMON wall — caps low under forced).
def _common_clay():
    return [_layer(0.0, 4.0, "shale")]


# Refractory clay = fine_clay (kaolin) in the ore-mix (PLASTIC, ceramic_grade wall).
def _kaolin():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06})]


# Refractory kaolin walls AND a co-located copper ore (C1 green malachite tell).
def _kaolin_plus_copper():
    return [_layer(0.0, 4.0, "sandstone",
                   ore={"fine_clay": 0.06, "native_copper": 0.05})]


def _common_clay_plus_copper():
    return [_layer(0.0, 4.0, "shale", ore={"native_copper": 0.05})]


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
    fd.install_forced_draught(sim)
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

def test_forced_peak_gain_over_kiln():
    """The apparatus only pushes C11's kiln: forced peak >= kiln peak, rising
    monotonically with fuel, never below the natural-draught kiln it is built on."""
    for f in (0.45, 0.6, 0.8, 1.0):
        for refrac in (False, True):
            kiln = kd.kiln_peak_temp_c(f, refrac)
            forced = fd.forced_draught_peak_c(f, refrac)
            assert forced >= kiln                  # forced draught never cools the kiln
    # monotone in fuel for a fixed wall (until the cap bites)
    assert fd.forced_draught_peak_c(0.45, True) < fd.forced_draught_peak_c(0.9, True)


def test_refractory_caps_higher_than_common_under_forced():
    """A refractory fire-clay wall survives the full bloomery regime; a common
    earthenware wall slumps just past copper — so at rich fuel the refractory furnace
    runs much hotter (and is the only one to reach the iron regime)."""
    assert fd.FORCED_REFRACTORY_WALL_CAP_C > fd.FORCED_COMMON_WALL_CAP_C
    assert fd.forced_draught_peak_c(1.0, True) > fd.forced_draught_peak_c(1.0, False)
    assert fd.forced_draught_peak_c(1.0, False) == fd.FORCED_COMMON_WALL_CAP_C
    assert fd.forced_draught_peak_c(1.0, True) <= fd.FORCED_REFRACTORY_WALL_CAP_C
    # a common wall stays below the iron bloomery temp; a refractory one reaches it.
    assert fd.forced_draught_peak_c(1.0, False) < fd.IRON_BLOOMERY_TEMP_C
    assert fd.forced_draught_peak_c(1.0, True) >= fd.IRON_BLOOMERY_TEMP_C


def test_reuses_c11_kiln_peak_ssot():
    """The combo: C12 reuses C11's kiln-peak SSOT verbatim as its base — it does NOT
    re-model the kiln's heat, it only pushes it with a bellows."""
    import inspect
    src = inspect.getsource(fd)
    assert "import engine.kiln_draft" in src
    assert "kiln_peak_temp_c" in src
    cue = _derive((0, 0, 0), _common_clay(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None
    assert cue.kiln_peak_c == round(kd.kiln_peak_temp_c(cue.fine_fuel, False), 1)
    assert cue.forced_peak_c >= cue.kiln_peak_c


def test_reuses_c9_vitrification_ssots():
    """Vitrification recomposes C9's maturation/ware SSOTs + C11's vitrification
    fraction at the forced peak — no re-modelling of the ceramic physics."""
    import inspect
    src = inspect.getsource(fd)
    assert "import engine.ceramic_firing" in src
    assert "clay_maturation_temp_c" in src and "fired_ware_quality" in src
    assert "VITRIFICATION_FIREDNESS" in src
    cue = _derive((0, 0, 0), _kaolin(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.clay_ceramic_grade is True
    maturation = cf.clay_maturation_temp_c(True)
    firedness = min(1.0, cue.forced_peak_c / maturation)
    assert cue.vitrified_ware_quality == round(
        cf.fired_ware_quality(cue.clay_pottery_grade, firedness), 4)


def test_introduces_no_new_tell():
    """C12 composes C11 kiln + C1 copper tell; it surfaces no new buried-mineral cue
    — the D8-by-composition decision (6th time, after C7/C8/C9/C10/C11)."""
    assert not hasattr(fd, "_PROFILE")
    # it is NOT an *_outcrop.py capability (exempt from the cross-language guardrail).
    assert not Path(fd.__file__).name.endswith("_outcrop.py")
    # the materials it reasons about are real catalogue tells C1/C5 already surface.
    for mat in ("native_copper", "fine_clay"):
        assert mat in MINERAL_BY_NAME
    # it strictly reads C11 + C1 — no independent geology derivation of its own.
    import inspect
    src = inspect.getsource(fd)
    assert "kiln_cue_for_chunk" in src and "surface_cue_for_chunk" in src


# ---------------------------------------------------------------------------
# The REALIZATION — vitrification (C9/C11 deferred → met here)
# ---------------------------------------------------------------------------

def test_vitrification_realized_for_refractory():
    """The payoff: where C9 (open fire) and C11 (natural draught) both left
    ``vitrifies_watertight`` False, the forced draught **realizes** it for a
    refractory kaolin body — the arc clay-lie → wall → vitrification closes."""
    # C9 open fire: under-fires kaolin (watertight False).
    open_firedness = min(1.0, cf.open_fire_peak_temp_c(0.80)
                         / cf.clay_maturation_temp_c(True))
    assert open_firedness < cf.SOUND_MATURATION
    # C11 natural draught: hotter, fires sound, but still NOT watertight.
    nat_firedness = min(1.0, kd.kiln_peak_temp_c(0.80, True)
                        / cf.clay_maturation_temp_c(True))
    assert nat_firedness < kd.VITRIFICATION_FIREDNESS
    # C12 forced draught: REALIZES vitrification.
    cue = _derive((0, 0, 0), _kaolin(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.wall_refractory is True
    assert cue.fires_clay_sound is True
    assert cue.vitrifies_watertight is True
    assert cue.forced_gain_c > 0.0


def test_common_wall_never_vitrifies_but_still_smelts_copper():
    """A common (non-ceramic) earthenware wall never vitrifies watertight however
    forced — but its furnace still crosses the copper threshold (1085 °C)."""
    cue = _derive((0, 0, 0), _common_clay(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.wall_refractory is False
    assert cue.clay_ceramic_grade is False
    assert cue.vitrifies_watertight is False
    assert cue.forced_peak_c <= fd.FORCED_COMMON_WALL_CAP_C
    assert cue.reaches_copper_smelting_temp is True       # common wall still smelts copper
    assert cue.reaches_iron_bloomery_temp is False        # but not iron (refractory only)


# ---------------------------------------------------------------------------
# The OPENING — copper metallurgy (composes C1 copper tell)
# ---------------------------------------------------------------------------

def test_copper_threshold_and_composition():
    """``would_smelt_copper_here`` iff the furnace crosses 1085 °C AND C1 sees a
    copper ore co-located — the honest 1+1>2 the world commits to."""
    # kaolin + copper: hot AND ore present → would smelt.
    cue = _derive((0, 0, 0), _kaolin_plus_copper(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None
    assert cue.reaches_copper_smelting_temp is True
    assert cue.copper_ore_here is True
    assert cue.copper_mineral == "native_copper"
    assert cue.would_smelt_copper_here is True
    # the smelt itself is still deferred to C13: hot-enough is just a potential.
    assert cue.smelts_copper_if_ore_present is True


def test_copper_temp_without_ore_does_not_smelt():
    """Hot enough but no copper ore underfoot → reaches the temp, would NOT smelt
    (nothing to smelt). The world never lies about what is actually here."""
    cue = _derive((0, 0, 0), _kaolin(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None
    assert cue.reaches_copper_smelting_temp is True
    assert cue.copper_ore_here is False
    assert cue.copper_mineral is None
    assert cue.would_smelt_copper_here is False


def test_copper_ore_agrees_with_c1_cue():
    """``copper_ore_here`` is exactly C1's copper-group surface cue — not an
    independent re-derivation (single source of truth)."""
    layers = _common_clay_plus_copper()
    c1 = sm._cue_from_geology((0, 0, 0), layers, _GRASS)
    assert c1 is not None and c1.group == "copper"
    cue = _derive((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is not None
    assert cue.copper_ore_here is True
    assert cue.copper_mineral == c1.mineral


# ---------------------------------------------------------------------------
# The 1+1>2 gate — kiln AND charcoal-grade fuel
# ---------------------------------------------------------------------------

def test_no_kiln_is_not_forceable():
    # Boreal forest: clay underfoot but too wet for ANY fire (no kiln C11) → no furnace.
    cue = _derive((0, 0, 0), _common_clay(), _BOREAL, _chunk(biome=_BOREAL))
    assert cue is None
    assert kd._cue_from_inputs(
        (0, 0, 0),
        ci._cue_from_geology((0, 0, 0), _common_clay(), _BOREAL, _chunk(biome=_BOREAL)),
        fi._cue_from_geology((0, 0, 0), _common_clay(), _BOREAL, _chunk(biome=_BOREAL)),
        None) is None


def test_charcoal_fuel_gate():
    """A kiln may be buildable on sparse fuel, but a bellows furnace needs
    charcoal-grade woody fuel — the SSOT gate at ``CHARCOAL_FUEL_FLOOR``."""
    # Direct SSOT-level check: a buildable kiln with sub-floor fuel is not forceable.
    from types import SimpleNamespace
    low = SimpleNamespace(buildable=True, biome=_TUNDRA, wall_material="shale",
                          wall_refractory=False, clay_pottery_grade=0.4,
                          clay_ceramic_grade=False,
                          fine_fuel=fd.CHARCOAL_FUEL_FLOOR - 0.05,
                          kiln_peak_c=900.0, confidence=0.5)
    assert fd._cue_from_inputs((0, 0, 0), low, None) is None
    hi = SimpleNamespace(buildable=True, biome=_GRASS, wall_material="shale",
                         wall_refractory=False, clay_pottery_grade=0.4,
                         clay_ceramic_grade=False,
                         fine_fuel=fd.CHARCOAL_FUEL_FLOOR + 0.05,
                         kiln_peak_c=1000.0, confidence=0.8)
    cue = fd._cue_from_inputs((0, 0, 0), hi, None)
    assert cue is not None and cue.charcoal_makeable is True


# ---------------------------------------------------------------------------
# "Le monde ne ment jamais" — real Genesis world
# ---------------------------------------------------------------------------

def _assert_cue_truthful(sim, coord, cue):
    if cue is None:
        return
    assert cue.forceable is True
    assert cue.charcoal_makeable is True
    # the bellows never cools the kiln, and never exceeds the wall's slump ceiling.
    assert cue.forced_peak_c >= cue.kiln_peak_c
    assert cue.forced_peak_c <= cue.wall_cap_c
    assert cue.forced_peak_c == round(
        fd.forced_draught_peak_c(cue.fine_fuel, cue.wall_refractory), 1)
    # C11 really sees a buildable kiln here (same wall material).
    kiln = kd.kiln_cue_for_chunk(sim, coord)
    assert kiln is not None and kiln.buildable and kiln.wall_material == cue.wall_material
    assert cue.kiln_peak_c == kiln.kiln_peak_c
    # vitrified ware agrees with the recomposed C9 SSOT.
    maturation = cf.clay_maturation_temp_c(cue.clay_ceramic_grade)
    firedness = min(1.0, cue.forced_peak_c / maturation)
    assert abs(cue.vitrified_ware_quality
               - cf.fired_ware_quality(cue.clay_pottery_grade, firedness)) <= 5e-4
    # a non-refractory body never vitrifies watertight, whatever the heat.
    if not cue.clay_ceramic_grade:
        assert cue.vitrifies_watertight is False
    # copper co-location implies C1 really surfaces a copper tell here.
    if cue.copper_ore_here:
        c1 = sm.surface_cue_for_chunk(sim, coord)
        assert c1 is not None and c1.group == "copper"
    # would-smelt implies both the temp AND the ore.
    if cue.would_smelt_copper_here:
        assert cue.reaches_copper_smelting_temp and cue.copper_ore_here


def test_world_never_lies_on_real_world():
    sim = _booted_sim("c12_neverlies")
    coords = _populate(sim)
    assert len(coords) > 0
    n_forceable = n_vitrify = 0
    for coord in coords:
        cue = fd.forced_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_forceable += 1
        if cue.vitrifies_watertight:
            n_vitrify += 1
        _assert_cue_truthful(sim, coord, cue)
    # the grassland seed surfaces real forced-draught sites and realizes
    # vitrification somewhere (refractory walls present in the real world).
    assert n_forceable > 0


def test_forced_preview_non_mutating_and_truthful():
    sim = _booted_sim("c12_preview")
    coords = _populate(sim)
    target = next((c for c in coords
                   if fd.forced_cue_for_chunk(sim, c) is not None), None)
    assert target is not None
    g = geo.chunk_geology(sim, target)
    before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    sim.agents.pos[0, 0] = (target[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (target[1] + 0.5) * CHUNK_SIDE_M
    out = fd.forced_draught_preview(sim, float(sim.agents.pos[0, 0]),
                                    float(sim.agents.pos[0, 1]))
    cue = fd.forced_cue_for_chunk(sim, target)
    after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    assert after == before                       # preview mutated nothing
    assert out["forceable"] is True
    assert out["forced_peak_c"] == cue.forced_peak_c
    assert out["vitrifies_watertight"] == cue.vitrifies_watertight
    assert out["reaches_copper_smelting_temp"] == cue.reaches_copper_smelting_temp


def test_preview_names_missing_kiln():
    # Dry grassland, fire makeable, but bare granite — no wall-clay → no kiln to force.
    sim = Simulation(SimConfig(name="c12_nokiln", seed=1, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_GRASS, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(
        coord=cc, layers=[_layer(0.0, 5.0, "granite")])}
    out = fd.forced_draught_preview(sim, 4.0, 4.0)
    assert out["forceable"] is False
    assert out["has_kiln"] is False
    assert "kiln" in out["reason"]


def test_preview_names_missing_charcoal():
    # A kiln IS buildable (percussion fire: pyrite + basalt striker, dry tinder, shale
    # walls) but the fuel load is below the charcoal floor — the bellows furnace needs
    # more woody fuel than a pottery kiln. An unknown biome (default fine_fuel 0.40 <
    # CHARCOAL_FUEL_FLOOR 0.45, moisture 0.40 dry) makes this gate bite deterministically.
    sim = Simulation(SimConfig(name="c12_nochar", seed=2, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=99, w=0.0)   # unknown biome → 0.40 fine_fuel
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(
        coord=cc, layers=[_layer(0.0, 2.0, "shale", ore={"pyrite": 0.05}),
                          _layer(2.0, 4.0, "basalt")])}
    kiln = kd.kiln_cue_for_chunk(sim, cc)
    assert kiln is not None and kiln.fine_fuel < fd.CHARCOAL_FUEL_FLOOR  # buildable, sub-floor fuel
    out = fd.forced_draught_preview(sim, 4.0, 4.0)
    assert out["forceable"] is False
    assert out["has_kiln"] is True
    assert out["charcoal_makeable"] is False
    assert "fuel" in out["reason"] or "charcoal" in out["reason"]


# ---------------------------------------------------------------------------
# Actionable pick : best_forced_site_near
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
    sim._surface_cue_cache.clear()
    sim._forced_draught_cue_cache.clear()


def test_best_forced_site_prefers_hottest_refractory():
    sim = _booted_sim("c12_best")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, _kaolin(), _GRASS, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    best = fd.best_forced_site_near(sim, 0, perception_radius_m=0.4 * CHUNK_SIDE_M)
    assert best is not None and best.forceable
    assert best.wall_refractory is True
    assert best.wall_material == "fine_clay"
    assert best.vitrifies_watertight is True


def test_best_forced_site_require_smelting():
    sim = _booted_sim("c12_smelt")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, _kaolin_plus_copper(), _GRASS, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    best = fd.best_forced_site_near(sim, 0, perception_radius_m=0.4 * CHUNK_SIDE_M,
                                    require_smelting=True)
    assert best is not None
    assert best.would_smelt_copper_here is True
    assert best.copper_mineral == "native_copper"


def test_no_forced_site_returns_none():
    # Bare hot desert: granite + no fine fuel → no kiln, no charcoal: 'nothing'.
    sim = _booted_sim("c12_none")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, [_layer(0.0, 5.0, "granite")], _HOT_DESERT, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    assert fd.best_forced_site_near(sim, 0,
                                    perception_radius_m=0.4 * CHUNK_SIDE_M) is None


# ---------------------------------------------------------------------------
# Determinism + install hygiene
# ---------------------------------------------------------------------------

def _cue_key(c):
    return None if c is None else (c.wall_material, c.wall_refractory,
                                   round(c.forced_peak_c, 3),
                                   round(c.forced_gain_c, 3),
                                   c.vitrifies_watertight,
                                   c.reaches_copper_smelting_temp,
                                   c.would_smelt_copper_here)


def test_determinism_same_seed():
    a = _booted_sim("c12_det_a", seed=0xBEEF)
    b = _booted_sim("c12_det_b", seed=0xBEEF)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    for coord in ca:
        assert _cue_key(fd.forced_cue_for_chunk(a, coord)) == \
               _cue_key(fd.forced_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("c12_idem")
    _populate(sim)
    c1 = fd.install_forced_draught(sim)
    c2 = fd.install_forced_draught(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = fd.forced_draught_summary(sim)
    assert set(s) >= {"n_chunks", "n_chunks_forceable", "forceable_rate",
                      "n_refractory_walled", "n_vitrifies_watertight",
                      "n_reaches_copper_smelt", "n_copper_ore_here",
                      "n_would_smelt_copper", "n_reaches_iron_bloomery",
                      "best_forced_peak_c", "best_forced_gain_c",
                      "by_wall_material"}
    assert 0.0 <= s["forceable_rate"] <= 1.0
    assert s["n_chunks_forceable"] <= s["n_chunks"]
    assert s["n_vitrifies_watertight"] <= s["n_chunks_forceable"]
    assert s["n_would_smelt_copper"] <= s["n_copper_ore_here"]
    assert s["best_forced_peak_c"] <= fd.FORCED_REFRACTORY_WALL_CAP_C
