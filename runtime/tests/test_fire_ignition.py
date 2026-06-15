"""Invariants — Substrate capability : amorçage du feu (Cap. C7).

Couvre :
- Deux voies d'amorçage physiquement distinctes : PERCUSSION (pyrite pyrophorique
  + percuteur dur + amadou *assez* sec) et FRICTION (combustible fin + amadou
  *très* sec, aucune pierre) — seuil friction plus strict que percussion.
- **Composition, pas nouveau tell (garde-fou D8)** : ce module n'a pas de
  ``_PROFILE`` et ne crée aucune entrée ``PY_TO_RUST`` ; il réutilise la pyrite
  (gossan C1) + le percuteur (pétrologie C2, source unique de vérité).
- Dérivation pure : pyrite en ``ore_mix`` peu profond ; percuteur via
  ``lithic_outcrop`` (incl. amélioration silex/chert en hôte carbonaté) ; pyrite
  profonde / fraction faible → pas de percussion ; océan masqué ; biome trop
  humide → ni l'un ni l'autre ; désert sans amadou → pas de friction.
- **Porte des deux seuils** : forêt tempérée (humidité 0.50) prend une étincelle
  (percussion) mais pas une braise de friction (0.50 > seuil friction 0.45).
- **« Le monde ne ment jamais »** : tout site ⇒ ``can_ignite`` ; percussion ⇒
  pyrite réelle peu profonde + percuteur réel + amadou sec ; friction ⇒ amadou
  sec & combustible — colonnes synthétiques ET monde Genesis réel (seed 0xBEEF).
- ``ignition_preview`` est un aperçu **non mutant** qui nomme l'ingrédient
  manquant (mensonge rendu visible : prairie détrempée = amadou apparent mais
  ne prend pas).
- ``best_firesite_near`` préfère la percussion et filtre (``require_percussion``).
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
import engine.lithic_outcrop as lo                                  # noqa: E402
import engine.fire_ignition as fi                                   # noqa: E402

_TEMPERATE = 4   # TEMPERATE_FOREST — moisture 0.50 (spark yes, friction no)
_GRASS = 6       # GRASSLAND — dry grass, the canonical tinder
_DESERT = 7      # HOT_DESERT — bone dry but almost fuel-less
_SAVANNA = 9     # SAVANNA — tall dry grass
_DRYFOREST = 10  # TROPICAL_DRY_FOREST — dry woodland (friction works)
_BOREAL = 3      # BOREAL_FOREST — moisture 0.60 (too wet for either)
_RAINFOREST = 11  # TROPICAL_RAINFOREST — soaked


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


# Pyrite firestone + a flint striker (quartz upgraded by a carbonate host).
def _firestone_layers(top=0.0, bottom=4.0):
    return [_layer(top, bottom, "limestone", ore={"pyrite": 0.05, "quartz": 0.06})]


def _booted_sim(name: str, seed: int = 0xBEEF, *, resolution: int = 128):
    cfg = SimConfig(name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
                    founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    geo.install_geology(sim)
    fi.install_fire_ignition(sim)
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
# Constants + composition contract (D8)
# ---------------------------------------------------------------------------

def test_constants_ordered():
    # Friction needs a drier tinder than a hot spark (the physical core).
    assert fi.FRICTION_DRY_MOISTURE < fi.PERCUSSION_DRY_MOISTURE
    # Friction needs at least as much fuel as merely having tinder.
    assert fi.FINE_FUEL_FLOOR <= fi.FRICTION_FUEL_FLOOR
    assert 0.0 < fi.STRIKER_MIN_QUALITY < 1.0
    assert fi.MIN_VISIBLE_FRACTION > 0.0
    assert fi.MAX_IGNITER_DEPTH_M > 0.0
    assert 0.0 < fi.PERCUSSION_DRY_MOISTURE < 1.0


def test_introduces_no_new_tell():
    """C7 composes existing tells; it surfaces no new buried-mineral cue.

    Documents (and asserts) the D8 decision: ``fire_ignition`` is NOT an
    ``*_outcrop.py`` with a ``_PROFILE`` table, so the cross-language guardrail
    neither classifies it nor needs to. The spark source and striker it reads are
    already classified tells from C1 and C2.
    """
    assert not hasattr(fi, "_PROFILE")
    # spark source = pyrite: a real catalogue mineral that C1 already surfaces as
    # the gossan / iron-cap cue (so no new PY_TO_RUST entry is created).
    from engine import surface_mineralization as sm
    gossan = next(r for r in sm._RULES if r.group == "gossan")
    for m in fi._SPARK_MINERALS:
        assert m in MINERAL_BY_NAME, f"spark mineral '{m}' absent from catalogue"
        assert m in gossan.minerals, f"spark mineral '{m}' not a C1 gossan tell"
    # striker = C2 lithic petrology, reused verbatim (single source of truth).
    s = fi._best_striker([_layer(0.0, 4.0, "limestone", ore={"quartz": 0.06})],
                         _GRASS)
    assert s is not None and s[0] in lo._PROFILE


# ---------------------------------------------------------------------------
# Pure derivation — percussion
# ---------------------------------------------------------------------------

def test_dry_grassland_with_pyrite_and_flint_is_percussion():
    cue = fi._cue_from_geology((0, 0, 0), _firestone_layers(), _GRASS,
                               _chunk(biome=_GRASS))
    assert cue is not None
    assert cue.can_percussion is True
    assert cue.method == fi.IgnitionMethod.PERCUSSION
    assert cue.spark_source == "pyrite"
    assert cue.striker_material is not None
    assert cue.striker_quality >= fi.STRIKER_MIN_QUALITY
    assert cue.tinder_state == fi.TinderState.DRY


def test_pyrite_without_striker_is_friction_only():
    # Grassland with pyrite but no hard striker (sandstone is too soft) → the
    # spark source is found, but you cannot strike it; fall back to friction.
    layers = [_layer(0.0, 4.0, "sandstone", ore={"pyrite": 0.05})]
    cue = fi._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is not None
    assert cue.spark_source == "pyrite"      # firestone is really there...
    assert cue.striker_material is None       # ...but nothing hard to strike it
    assert cue.can_percussion is False
    assert cue.can_friction is True
    assert cue.method == fi.IgnitionMethod.FRICTION


def test_deep_pyrite_denies_percussion_but_friction_remains():
    # Pyrite below the reachable depth → no spark source to pick up; dry grassland
    # still ignites by friction.
    layers = [_layer(0.0, 5.0, "sandstone", ore={"quartz": 0.06}),
              _layer(fi.MAX_IGNITER_DEPTH_M + 10.0, 200.0, "shale",
                     ore={"pyrite": 0.10})]
    cue = fi._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is not None
    assert cue.spark_source is None and cue.can_percussion is False
    assert cue.can_friction is True


def test_faint_pyrite_fraction_denies_percussion():
    layers = [_layer(0.0, 4.0, "limestone",
                     ore={"pyrite": fi.MIN_VISIBLE_FRACTION / 2.0,
                          "quartz": 0.06})]
    cue = fi._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is not None
    assert cue.spark_source is None and cue.can_percussion is False


# ---------------------------------------------------------------------------
# Pure derivation — friction + the two-threshold gate
# ---------------------------------------------------------------------------

def test_dry_woodland_without_minerals_is_friction():
    cue = fi._cue_from_geology((0, 0, 0), [_layer(0.0, 5.0, "sandstone")],
                               _DRYFOREST, _chunk(biome=_DRYFOREST))
    assert cue is not None
    assert cue.can_friction is True and cue.can_percussion is False
    assert cue.method == fi.IgnitionMethod.FRICTION


def test_temperate_forest_spark_yes_friction_no():
    # Moisture 0.50: a hot spark catches (≤ 0.58) but a friction ember does not
    # (> 0.45). With pyrite + flint present → percussion only.
    cue = fi._cue_from_geology((0, 0, 0), _firestone_layers(), _TEMPERATE,
                               _chunk(biome=_TEMPERATE))
    assert cue is not None
    assert cue.can_percussion is True
    assert cue.can_friction is False
    assert cue.method == fi.IgnitionMethod.PERCUSSION


def test_standing_water_can_quench_a_percussion_site():
    dry = fi._cue_from_geology((0, 0, 0), _firestone_layers(), _GRASS,
                               _chunk(biome=_GRASS, w=0.0))
    wet = fi._cue_from_geology((0, 0, 0), _firestone_layers(), _GRASS,
                               _chunk(biome=_GRASS, w=fi.WATER_SATURATION_L))
    assert dry is not None and dry.can_percussion is True
    assert wet is None  # soaked: tinder too damp to catch — no viable method


# ---------------------------------------------------------------------------
# Physical masking
# ---------------------------------------------------------------------------

def test_ocean_is_masked():
    assert fi._cue_from_geology((0, 0, 0), _firestone_layers(), int(Biome.OCEAN),
                                _chunk(biome=int(Biome.OCEAN))) is None


def test_soaked_rainforest_is_not_ignitable():
    # Pyrite + flint underfoot, but a soaked rainforest: no spark catches, no
    # friction ember survives.
    assert fi._cue_from_geology((0, 0, 0), _firestone_layers(), _RAINFOREST,
                                _chunk(biome=_RAINFOREST)) is None


def test_desert_striker_but_no_tinder_is_not_ignitable():
    # Bone-dry desert with a flint striker but almost no fine fuel → nothing to
    # catch (no tinder), and no pyrite → neither method.
    cue = fi._cue_from_geology((0, 0, 0), [_layer(0.0, 5.0, "sandstone",
                                                  ore={"quartz": 0.06})],
                               _DESERT, _chunk(biome=_DESERT))
    assert cue is None


def test_wet_boreal_is_not_ignitable():
    # Moisture 0.60 > both thresholds → neither method, even with firestone.
    assert fi._cue_from_geology((0, 0, 0), _firestone_layers(), _BOREAL,
                                _chunk(biome=_BOREAL)) is None


# ---------------------------------------------------------------------------
# "Le monde ne ment jamais" — synthetic + real Genesis world
# ---------------------------------------------------------------------------

def _assert_cue_truthful(cue, layers):
    if cue is None:
        return
    assert cue.can_ignite is True
    if cue.can_percussion:
        grounded = any(
            L.depth_top_m <= fi.MAX_IGNITER_DEPTH_M
            and L.ore_mix.get(cue.spark_source, 0.0) >= fi.MIN_VISIBLE_FRACTION
            for L in layers)
        assert grounded, "percussion claimed but no shallow pyrite present"
        assert cue.striker_material is not None
        assert cue.striker_quality >= fi.STRIKER_MIN_QUALITY
        assert cue.ambient_moisture <= fi.PERCUSSION_DRY_MOISTURE
        assert cue.fine_fuel >= fi.FINE_FUEL_FLOOR
        assert cue.method == fi.IgnitionMethod.PERCUSSION
    if cue.can_friction:
        assert cue.ambient_moisture <= fi.FRICTION_DRY_MOISTURE
        assert cue.fine_fuel >= fi.FRICTION_FUEL_FLOOR


def test_world_never_lies_on_real_world():
    sim = _booted_sim("c7_neverlies")
    coords = _populate(sim)
    assert len(coords) > 0
    n_ignitable = 0
    n_percussion = 0
    for coord in coords:
        cue = fi.ignition_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_ignitable += 1
        if cue.can_percussion:
            n_percussion += 1
        g = geo.chunk_geology(sim, coord)
        _assert_cue_truthful(cue, g.layers if g else [])
    # the grassland seed must surface both real percussion and friction sites.
    assert n_ignitable > 0 and n_percussion > 0


def test_ignition_preview_non_mutating_and_truthful():
    sim = _booted_sim("c7_preview")
    coords = _populate(sim)
    target = next((c for c in coords
                   if (cu := fi.ignition_cue_for_chunk(sim, c)) is not None
                   and cu.can_percussion), None)
    assert target is not None
    g = geo.chunk_geology(sim, target)
    before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    sim.agents.pos[0, 0] = (target[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (target[1] + 0.5) * CHUNK_SIDE_M
    out = fi.ignition_preview(sim, float(sim.agents.pos[0, 0]),
                              float(sim.agents.pos[0, 1]))
    cue = fi.ignition_cue_for_chunk(sim, target)
    after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    assert after == before                       # preview mutated nothing
    assert out["can_ignite"] is True
    assert out["can_percussion"] == cue.can_percussion
    assert out["spark_source"] == cue.spark_source == "pyrite"
    assert out["method"] == cue.method.name


def test_preview_names_missing_ingredient_when_damp():
    # A soaked grassland: looks like grass tinder, but a spark won't take.
    sim = Simulation(SimConfig(name="c7_damp", seed=1, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_GRASS, w=fi.WATER_SATURATION_L)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(coord=cc,
                                                  layers=_firestone_layers())}
    out = fi.ignition_preview(sim, 4.0, 4.0)
    assert out["can_ignite"] is False
    assert out["tinder_available"] is True       # grass IS there...
    assert "damp" in out["reason"]               # ...but too wet to catch


# ---------------------------------------------------------------------------
# Actionable pick : best_firesite_near
# ---------------------------------------------------------------------------

def _put_chunk(sim, cc, layers, biome, w):
    ch = sim.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, biome,
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
    sim._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=layers)
    sim._ignition_cue_cache.clear()


def _stand_on(sim, cc):
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M


_OWN_CHUNK_R = 0.4 * CHUNK_SIDE_M


def test_best_firesite_prefers_percussion():
    sim = _booted_sim("c7_best")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc,
               [_layer(0.0, 1.0, "sandstone"),
                _layer(1.0, 5.0, "limestone", ore={"pyrite": 0.05, "quartz": 0.06})],
               _GRASS, 0.0)
    _stand_on(sim, cc)
    best = fi.best_firesite_near(sim, 0, perception_radius_m=_OWN_CHUNK_R)
    assert best is not None and best.can_percussion
    assert best.method == fi.IgnitionMethod.PERCUSSION
    perc = fi.best_firesite_near(sim, 0, perception_radius_m=_OWN_CHUNK_R,
                                 require_percussion=True)
    assert perc is not None and perc.can_percussion


def test_require_percussion_skips_friction_only_site():
    sim = _booted_sim("c7_best2")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    # dry savanna, no pyrite → friction only.
    _put_chunk(sim, cc, [_layer(0.0, 5.0, "sandstone")], _SAVANNA, 0.0)
    _stand_on(sim, cc)
    # a viable site exists (friction)...
    assert fi.best_firesite_near(sim, 0, perception_radius_m=_OWN_CHUNK_R) is not None
    # ...but require_percussion finds nothing (honest 'no firestone here').
    assert fi.best_firesite_near(sim, 0, perception_radius_m=_OWN_CHUNK_R,
                                 require_percussion=True) is None


# ---------------------------------------------------------------------------
# Determinism + install hygiene
# ---------------------------------------------------------------------------

def _cue_key(c):
    return None if c is None else (int(c.method), c.can_percussion,
                                   c.can_friction, c.spark_source,
                                   c.striker_material,
                                   round(c.ambient_moisture, 6))


def test_determinism_same_seed():
    a = _booted_sim("det_a", seed=0xBEEF)
    b = _booted_sim("det_b", seed=0xBEEF)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    for coord in ca:
        assert _cue_key(fi.ignition_cue_for_chunk(a, coord)) == \
               _cue_key(fi.ignition_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("idem")
    _populate(sim)
    c1 = fi.install_fire_ignition(sim)
    c2 = fi.install_fire_ignition(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = fi.ignition_summary(sim)
    assert set(s) >= {"n_chunks", "n_chunks_ignitable", "ignitable_rate",
                      "n_percussion", "n_friction", "best_confidence",
                      "by_method", "by_tinder"}
    assert 0.0 <= s["ignitable_rate"] <= 1.0
    assert s["n_percussion"] <= s["n_chunks_ignitable"] <= s["n_chunks"]
    assert s["n_friction"] <= s["n_chunks_ignitable"]
