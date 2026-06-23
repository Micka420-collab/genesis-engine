"""Invariants — Substrate capability : trempe thermique de la pierre (Cap. C8).

Couvre :
- **Première TRANSFORMATION** (pas perception) : ``base_quality`` →
  ``tempered_quality``. Le monde s'engage sur le résultat (SSOT
  ``tempered_quality``), borné par ``TEMPER_CEILING``, additif par caractère de
  silice (chert > quartzite > 0 ; obsidienne / non-silice = 0).
- **Composition, pas nouveau tell (garde-fou D8)** : ce module n'a pas de
  ``_PROFILE`` et ne crée aucune entrée ``PY_TO_RUST`` ; il lit C2
  ``lithic_outcrop`` (pierre + ``knap_quality``, incl. silex/chert) et C7
  ``fire_ignition`` (feu faisable).
- **Effet 1+1>2** : trempe possible QUE si une silice réactive (C2) ET un feu
  (C7) coexistent — chert + foyer = trempable ; chert sans feu (boréal détrempé)
  ou obsidienne (déjà verre) = non trempable.
- **« Le monde ne ment jamais »** : tout cue ⇒ ``temperable`` ; la pierre existe
  (C2, même colonne que ``mine_at``) et le feu est faisable (C7) — colonnes
  synthétiques ET monde Genesis réel (seed 0xBEEF).
- ``temper_preview`` non mutant nomme l'ingrédient manquant (mensonge rendu
  visible : l'obsidienne semble la pierre idéale mais le feu ne l'améliore pas).
- ``best_temper_site_near`` préfère le plus grand gain.
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
from engine.world import CHUNK_SIDE_M                        # noqa: E402
from engine.mineral_catalog import MINERAL_BY_NAME                  # noqa: E402
import engine.lithic_outcrop as lo                                  # noqa: E402
import engine.fire_ignition as fi                                   # noqa: E402
import engine.lithic_tempering as lt                                # noqa: E402

_GRASS = 6        # GRASSLAND — dry, lithic-visible, fire-makeable
_SAVANNA = 9      # SAVANNA — dry woodland, friction fire
_BOREAL = 3       # BOREAL_FOREST — lithic-visible but too wet for any fire
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
    lithic = lo._cue_from_geology(coord, layers, biome)
    fire = fi._cue_from_geology(coord, layers, biome, chunk)
    carb = lo._has_carbonate_host(layers)
    return lt._cue_from_inputs(coord, lithic, fire, carb)


# Flint/chert striker (quartz upgraded by a carbonate host) + pyrite firestone.
def _chert_firestone():
    return [_layer(0.0, 4.0, "limestone", ore={"quartz": 0.06, "pyrite": 0.05})]


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
    lt.install_lithic_tempering(sim)
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
# Constants + SSOT outcome + composition contract (D8)
# ---------------------------------------------------------------------------

def test_constants_and_gain_ordering():
    assert 0.0 < lt.TEMPER_CEILING <= 1.0
    # Cryptocrystalline chert must out-respond macrocrystalline quartzite.
    assert lt._TEMPER_GAIN["chert"] > lt._TEMPER_GAIN["quartzite"] > 0.0
    # Obsidian / non-silica are not in the gain table (gain 0).
    assert "obsidian" not in lt._TEMPER_GAIN
    assert "none" not in lt._TEMPER_GAIN


def test_tempered_quality_ssot_monotone_capped():
    # Responsive silica gains exactly its keyed Δ, capped at the ceiling.
    assert lt.tempered_quality(0.42, "quartzite") == \
        min(lt.TEMPER_CEILING, 0.42 + lt._TEMPER_GAIN["quartzite"])
    assert lt.tempered_quality(0.72, "chert") == \
        min(lt.TEMPER_CEILING, 0.72 + lt._TEMPER_GAIN["chert"])
    # Ceiling actually bites for an already-excellent chert.
    assert lt.tempered_quality(0.90, "chert") == lt.TEMPER_CEILING
    # Non-responsive stone is returned unchanged (no lie of improvement).
    assert lt.tempered_quality(1.00, "obsidian") == 1.00
    assert lt.tempered_quality(0.45, "none") == 0.45


def test_introduces_no_new_tell():
    """C8 composes C2 stone + C7 fire; it surfaces no new buried-mineral cue.

    Documents (and asserts) the D8 decision: ``lithic_tempering`` is NOT an
    ``*_outcrop.py`` with a ``_PROFILE`` table, so the cross-language guardrail
    neither classifies it nor needs to. The stones it transforms are already
    classified tells / catalogue minerals from C2.
    """
    assert not hasattr(lt, "_PROFILE")
    # The silica it can temper are real catalogue minerals C2 already surfaces.
    for stone in ("quartz", "obsidian"):
        assert stone in MINERAL_BY_NAME
        assert stone in lo._PROFILE
    # It strictly reads C2 + C7 — no independent geology derivation of its own.
    import inspect
    src = inspect.getsource(lt)
    assert "lithic_cue_for_chunk" in src and "ignition_cue_for_chunk" in src


# ---------------------------------------------------------------------------
# Pure derivation — the four silica responses
# ---------------------------------------------------------------------------

def test_chert_with_fire_is_temperable():
    cue = _derive((0, 0, 0), _chert_firestone(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None
    assert cue.temperable is True
    assert cue.silica_kind == "chert"
    assert cue.stone_material == "quartz"        # chert = quartz + carbonate host
    assert cue.quality_gain == lt._TEMPER_GAIN["chert"]
    assert cue.tempered_quality > cue.base_quality
    assert cue.fire_method in ("PERCUSSION", "FRICTION")


def test_raw_quartzite_has_modest_gain():
    # Dry savanna, quartz float but NO carbonate host → macrocrystalline quartzite;
    # no pyrite → friction fire. Temperable, but a smaller gain than chert.
    layers = [_layer(0.0, 5.0, "sandstone", ore={"quartz": 0.06})]
    cue = _derive((0, 0, 0), layers, _SAVANNA, _chunk(biome=_SAVANNA))
    assert cue is not None and cue.temperable is True
    assert cue.silica_kind == "quartzite"
    assert cue.quality_gain == lt._TEMPER_GAIN["quartzite"]
    assert cue.quality_gain < lt._TEMPER_GAIN["chert"]


def test_obsidian_is_not_temperable_the_lie():
    # Obsidian is the BEST knapping stone (base 1.0) and a fire is makeable — yet
    # heat-treating volcanic glass yields no edge gain. The world must not lie.
    layers = [_layer(0.0, 5.0, "sandstone", ore={"obsidian": 0.06, "pyrite": 0.05})]
    cue = _derive((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is None
    # And the perceived stone really was the prime obsidian (C2 would surface it).
    lithic = lo._cue_from_geology((0, 0, 0), layers, _GRASS)
    assert lithic is not None and lithic.material == "obsidian"


def test_non_silica_stone_is_not_temperable():
    # Basalt (ground-stone, conchoidal=False) cannot be tempered for an edge.
    layers = [_layer(0.0, 5.0, "basalt", ore={"pyrite": 0.05})]
    cue = _derive((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is None


def test_chert_without_fire_is_not_temperable():
    # Boreal forest (moisture 0.60) is lithic-visible but too wet for ANY fire
    # (C7 returns None). Chert underfoot, but you cannot heat-treat it here.
    cue = _derive((0, 0, 0), _chert_firestone(), _BOREAL, _chunk(biome=_BOREAL))
    assert cue is None
    # ...and C2 still sees the stone, C7 still refuses the fire — the 1+1>2 gate.
    assert lo._cue_from_geology((0, 0, 0), _chert_firestone(), _BOREAL) is not None
    assert fi._cue_from_geology((0, 0, 0), _chert_firestone(), _BOREAL,
                                _chunk(biome=_BOREAL)) is None


# ---------------------------------------------------------------------------
# "Le monde ne ment jamais" — real Genesis world
# ---------------------------------------------------------------------------

def _assert_cue_truthful(sim, coord, cue):
    if cue is None:
        return
    assert cue.temperable is True
    assert cue.quality_gain > 0.0
    assert cue.tempered_quality > cue.base_quality
    assert cue.tempered_quality <= lt.TEMPER_CEILING
    # C2 really sees a heat-responsive silica stone here...
    lithic = lo.lithic_cue_for_chunk(sim, coord)
    assert lithic is not None and lithic.material == cue.stone_material
    assert lithic.knap_class == lo.KnapClass.CONCHOIDAL
    # ...and C7 really can make a fire here.
    assert fi.ignition_cue_for_chunk(sim, coord) is not None


def test_world_never_lies_on_real_world():
    sim = _booted_sim("c8_neverlies")
    coords = _populate(sim)
    assert len(coords) > 0
    n_temperable = 0
    for coord in coords:
        cue = lt.temper_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_temperable += 1
        _assert_cue_truthful(sim, coord, cue)
    # the grassland seed must surface real temperable (chert + fire) sites.
    assert n_temperable > 0


def test_temper_preview_non_mutating_and_truthful():
    sim = _booted_sim("c8_preview")
    coords = _populate(sim)
    target = next((c for c in coords
                   if lt.temper_cue_for_chunk(sim, c) is not None), None)
    assert target is not None
    g = geo.chunk_geology(sim, target)
    before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    sim.agents.pos[0, 0] = (target[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (target[1] + 0.5) * CHUNK_SIDE_M
    out = lt.temper_preview(sim, float(sim.agents.pos[0, 0]),
                            float(sim.agents.pos[0, 1]))
    cue = lt.temper_cue_for_chunk(sim, target)
    after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    assert after == before                       # preview mutated nothing
    assert out["temperable"] is True
    assert out["tempered_quality"] == cue.tempered_quality
    assert out["quality_gain"] == cue.quality_gain
    assert out["base_quality"] == cue.base_quality


def test_preview_names_missing_ingredient_obsidian():
    # Synthetic: an obsidian outcrop with fire underfoot — temperable False, and
    # the reason names the "already glass" lie.
    sim = Simulation(SimConfig(name="c8_obs", seed=1, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_GRASS, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(
        coord=cc, layers=[_layer(0.0, 5.0, "sandstone",
                                 ore={"obsidian": 0.06, "pyrite": 0.05})])}
    out = lt.temper_preview(sim, 4.0, 4.0)
    assert out["temperable"] is False
    assert out["silica_kind"] == "obsidian"
    assert "obsidian" in out["reason"] or "glass" in out["reason"]


def test_preview_names_missing_fire():
    # Chert underfoot but a soaked boreal forest: no fire can be made.
    sim = Simulation(SimConfig(name="c8_nofire", seed=2, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_BOREAL, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(coord=cc,
                                                  layers=_chert_firestone())}
    out = lt.temper_preview(sim, 4.0, 4.0)
    assert out["temperable"] is False
    assert "fire" in out["reason"]
    assert out["silica_kind"] == "chert"


# ---------------------------------------------------------------------------
# Actionable pick : best_temper_site_near
# ---------------------------------------------------------------------------

def _put_chunk(sim, cc, layers, biome, w):
    ch = sim.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, biome,
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
    sim._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=layers)
    sim._lithic_cue_cache.clear()
    sim._ignition_cue_cache.clear()
    sim._temper_cue_cache.clear()


def test_best_temper_site_prefers_largest_gain():
    sim = _booted_sim("c8_best")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    # a chert firestone site on the agent's own chunk (the biggest-gain option).
    _put_chunk(sim, cc, _chert_firestone(), _GRASS, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    best = lt.best_temper_site_near(sim, 0, perception_radius_m=0.4 * CHUNK_SIDE_M)
    assert best is not None and best.temperable
    assert best.silica_kind == "chert"
    assert best.quality_gain == lt._TEMPER_GAIN["chert"]


def test_no_temper_site_returns_none():
    # Bare hot desert with only soft/ground stone and no fine fuel → no fire, and
    # the basalt is not temperable anyway: an honest 'nothing to roast here'.
    sim = _booted_sim("c8_none")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, [_layer(0.0, 5.0, "basalt")], _HOT_DESERT, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    assert lt.best_temper_site_near(sim, 0,
                                    perception_radius_m=0.4 * CHUNK_SIDE_M) is None


# ---------------------------------------------------------------------------
# Determinism + install hygiene
# ---------------------------------------------------------------------------

def _cue_key(c):
    return None if c is None else (c.stone_material, c.silica_kind,
                                   round(c.base_quality, 6),
                                   round(c.tempered_quality, 6),
                                   round(c.quality_gain, 6), c.fire_method)


def test_determinism_same_seed():
    a = _booted_sim("c8_det_a", seed=0xBEEF)
    b = _booted_sim("c8_det_b", seed=0xBEEF)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    for coord in ca:
        assert _cue_key(lt.temper_cue_for_chunk(a, coord)) == \
               _cue_key(lt.temper_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("c8_idem")
    _populate(sim)
    c1 = lt.install_lithic_tempering(sim)
    c2 = lt.install_lithic_tempering(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = lt.tempering_summary(sim)
    assert set(s) >= {"n_chunks", "n_chunks_temperable", "temperable_rate",
                      "best_quality_gain", "best_tempered_quality",
                      "by_silica_kind"}
    assert 0.0 <= s["temperable_rate"] <= 1.0
    assert s["n_chunks_temperable"] <= s["n_chunks"]
    assert s["best_tempered_quality"] <= lt.TEMPER_CEILING
