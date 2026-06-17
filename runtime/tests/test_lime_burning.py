"""Invariants — Substrate capability : cuisson de la chaux (Cap. C10).

Couvre :
- **Troisième TRANSFORMATION** (après C8/C9) et **pendant exact de C9** : calcaire
  cru → chaux. Le monde s'engage sur le résultat (SSOT ``quicklime_quality`` /
  ``calcination_extent``), gouverné par deux températures physiques : pointe du feu
  ouvert (``cf.open_fire_peak_temp_c`` — RÉEMPLOYÉE de C9, le combo) × seuil de
  décarbonatation du carbonate (``calcination_onset_c``, réfractaire pur vs commun).
- **Composition, pas nouveau tell (garde-fou D8)** : pas de ``_PROFILE``, aucune
  entrée ``PY_TO_RUST`` ; lit C6 ``limestone_outcrop`` (carbonate + ``lime_grade`` +
  ``lime_class`` + ``mortar_grade``) et C7 ``fire_ignition`` (feu + ``fine_fuel``).
- **Effet 1+1>2** : calcination possible QUE si calcaire (C6) ET feu (C7)
  coexistent — calcaire + foyer = cuisible ; calcaire sans feu (boréal humide) =
  non cuisible.
- **L'inversion réfractaire (le mensonge rendu visible)** : ``limestone_pure`` (le
  *meilleur* calcaire, ``mortar_grade`` True) **sous-cuit** au feu ouvert et donne
  une chaux **pire** qu'un humble calcaire commun calciné à cœur — le pendant
  symétrique du kaolin de C9 et de l'obsidienne de C8.
- **« Le monde ne ment jamais »** : tout cue ⇒ ``burnable`` ; le carbonate existe
  (C6, même colonne que ``mine_at``) et le feu est faisable (C7) — colonnes
  synthétiques ET monde Genesis réel (seed 0xBEEF). ``mortar_ready`` toujours False
  en feu ouvert (pas de mortier liant sans four à chaux).
- ``burn_preview`` non mutant nomme l'ingrédient manquant.
- ``best_burning_site_near`` préfère la plus haute ``lime_yield`` (calcaire commun
  bien cuit > calcaire pur sous-cuit).
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
import engine.limestone_outcrop as li                               # noqa: E402
import engine.fire_ignition as fi                                   # noqa: E402
import engine.ceramic_firing as cf                                  # noqa: E402
import engine.lime_burning as lb                                    # noqa: E402

_GRASS = 6        # GRASSLAND — dry, fire-makeable (friction), peak ~800 C
_BOREAL = 3       # BOREAL_FOREST — carbonate-visible but too wet for any fire
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
    lime = li._cue_from_geology(coord, layers, biome, chunk)
    fire = fi._cue_from_geology(coord, layers, biome, chunk)
    return lb._cue_from_inputs(coord, lime, fire)


# Common building carbonate = limestone lithology (COMMON, low-onset, well-burns).
def _common_limestone():
    return [_layer(0.0, 4.0, "limestone")]


# Refractory pure carbonate = limestone_pure in the ore-mix (PURE, kiln-grade).
def _pure_limestone():
    return [_layer(0.0, 4.0, "limestone", ore={"limestone_pure": 0.06})]


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
    lb.install_lime_burning(sim)
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

def test_calcination_onset_ssot():
    # pure calcite is the most stable carbonate — needs far more heat than a
    # common / dolomitic (fluxed) one to begin decarbonating.
    assert lb.calcination_onset_c(li.LimeClass.PURE_CARBONATE) == \
        lb.CALCINATION_ONSET_PURE_C
    assert lb.calcination_onset_c(li.LimeClass.COMMON_CARBONATE) == \
        lb.CALCINATION_ONSET_FLUXED_C
    assert lb.CALCINATION_ONSET_PURE_C > lb.CALCINATION_ONSET_FLUXED_C


def test_calcination_extent_ssot():
    # nothing below the onset; monotone above it; bounded by 1.
    assert lb.calcination_extent(lb.CALCINATION_ONSET_FLUXED_C - 50, 680.0) == 0.0
    assert lb.calcination_extent(lb.CALCINATION_ONSET_FLUXED_C, 680.0) == 0.0
    e1 = lb.calcination_extent(780.0, 680.0)
    e2 = lb.calcination_extent(840.0, 680.0)
    assert 0.0 < e1 < e2 <= 1.0
    assert lb.calcination_extent(2000.0, 680.0) == 1.0


def test_reuses_c9_open_fire_peak_ssot():
    """The combo: C10 reuses C9's open-fire peak-temperature SSOT verbatim — it
    does NOT re-model the fire's heat. One fire, two pyrotransformations."""
    import inspect
    src = inspect.getsource(lb)
    assert "import engine.ceramic_firing" in src
    assert "open_fire_peak_temp_c" in src
    # functional: a derived cue's peak is exactly C9's open-fire peak from fuel.
    cue = _derive((0, 0, 0), _common_limestone(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None
    assert cue.peak_temp_c == round(cf.open_fire_peak_temp_c(cue.fine_fuel), 1)
    assert cf.OPEN_FIRE_MIN_C <= cue.peak_temp_c <= cf.OPEN_FIRE_MAX_C


def test_quicklime_quality_ssot_wellburnt_vs_underburnt():
    # Well-burnt (extent >= SOUND): lime takes the stone's intrinsic grade.
    assert lb.quicklime_quality(0.72, 1.0) == 0.72
    assert lb.quicklime_quality(0.72, lb.SOUND_CALCINATION) == 0.72
    # Under-burnt: capped hard by UNDERBURNT_CEILING, scaled by burn progress.
    ce = 0.30
    expected = 0.95 * lb.UNDERBURNT_CEILING * (ce / lb.SOUND_CALCINATION)
    assert lb.quicklime_quality(0.95, ce) == expected
    # The inversion at the SSOT level: a pure stone under-burnt scores BELOW a
    # humble common stone burnt to soundness.
    assert lb.quicklime_quality(0.95, 0.23) < lb.quicklime_quality(0.72, 1.0)


def test_mortar_ready_impossible_in_open_fire():
    """An open fire never hard-burns: even at its hottest, the decarbonation
    stays below ``MORTAR_CALCINATION`` for any modelled onset → ``mortar_ready``
    is always False (the unrealized kiln potential)."""
    hottest = cf.OPEN_FIRE_MAX_C
    for onset in (lb.CALCINATION_ONSET_FLUXED_C, lb.CALCINATION_ONSET_PURE_C):
        assert lb.calcination_extent(hottest, onset) < lb.MORTAR_CALCINATION


def test_introduces_no_new_tell():
    """C10 composes C6 carbonate + C7 fire; it surfaces no new buried-mineral cue.

    Documents (and asserts) the D8 decision: ``lime_burning`` is NOT an
    ``*_outcrop.py`` with a ``_PROFILE`` table, so the cross-language guardrail
    neither classifies it nor needs to. The carbonates it transforms are already
    classified tells / catalogue minerals from C6.
    """
    assert not hasattr(lb, "_PROFILE")
    # The carbonates it burns are real catalogue minerals C6 already surfaces.
    for rock in ("limestone_pure", "limestone", "dolomite"):
        assert rock in MINERAL_BY_NAME
        assert rock in li._PROFILE
    # It strictly reads C6 + C7 — no independent geology derivation of its own.
    import inspect
    src = inspect.getsource(lb)
    assert "limestone_cue_for_chunk" in src and "ignition_cue_for_chunk" in src


# ---------------------------------------------------------------------------
# Pure derivation — the calcination outcomes
# ---------------------------------------------------------------------------

def test_common_limestone_burns_well():
    cue = _derive((0, 0, 0), _common_limestone(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.burnable is True
    assert cue.carbonate_material == "limestone"
    assert cue.lime_class == "COMMON_CARBONATE"
    assert cue.well_burnt is True and cue.underburnt is False
    # lime quality is the stone's intrinsic grade (no hard burn beyond it).
    assert cue.lime_yield == cue.lime_grade
    assert cue.mortar_ready is False
    assert cue.fire_method in ("PERCUSSION", "FRICTION")


def test_pure_limestone_underburns_in_open_fire_the_lie():
    # limestone_pure is the BEST carbonate (mortar_grade True, lime_grade 0.95) and
    # a fire is makeable — yet a bare open fire under-burns refractory pure calcite.
    # The world must not lie: it shows the unrealized mortar potential, not a binder.
    cue = _derive((0, 0, 0), _pure_limestone(), _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.burnable is True
    assert cue.carbonate_material == "limestone_pure"
    assert cue.lime_class == "PURE_CARBONATE"
    assert cue.mortar_grade is True
    assert cue.underburnt is True and cue.well_burnt is False
    assert cue.mortar_ready is False                 # open fire never hard-burns
    assert cue.would_mortar_if_kiln_fired is True    # the unrealized kiln potential


def test_refractory_inversion_common_beats_pure():
    """The C10 inversion (pendant of C9's kaolin, C8's obsidian): in an open fire
    the humble common limestone out-performs the prettier pure white stone."""
    common = _derive((0, 0, 0), _common_limestone(), _GRASS, _chunk(biome=_GRASS))
    pure = _derive((0, 0, 0), _pure_limestone(), _GRASS, _chunk(biome=_GRASS))
    assert common is not None and pure is not None
    assert common.well_burnt and pure.underburnt
    assert common.lime_yield > pure.lime_yield


def test_carbonate_without_fire_is_not_burnable():
    # Boreal forest (moisture 0.60) is carbonate-visible but too wet for ANY fire
    # (C7 returns None). Limestone underfoot, but you cannot burn it here.
    cue = _derive((0, 0, 0), _common_limestone(), _BOREAL, _chunk(biome=_BOREAL))
    assert cue is None
    # ...and C6 still sees the carbonate, C7 still refuses the fire — the 1+1>2 gate.
    assert li._cue_from_geology((0, 0, 0), _common_limestone(), _BOREAL,
                                _chunk(biome=_BOREAL)) is not None
    assert fi._cue_from_geology((0, 0, 0), _common_limestone(), _BOREAL,
                                _chunk(biome=_BOREAL)) is None


def test_fire_without_carbonate_is_not_burnable():
    # Dry grassland with a fire makeable, but bare granite — no carbonate to burn.
    layers = [_layer(0.0, 5.0, "granite")]
    cue = _derive((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is None
    assert li._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS)) is None
    assert fi._cue_from_geology((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS)) is not None


# ---------------------------------------------------------------------------
# "Le monde ne ment jamais" — real Genesis world
# ---------------------------------------------------------------------------

def _assert_cue_truthful(sim, coord, cue):
    if cue is None:
        return
    assert cue.burnable is True
    assert 0.0 <= cue.lime_yield <= 1.0
    assert cf.OPEN_FIRE_MIN_C <= cue.peak_temp_c <= cf.OPEN_FIRE_MAX_C
    assert cue.mortar_ready is False
    # lime quality agrees with the SSOT outcome (rounding-tolerant)
    expected = lb.quicklime_quality(cue.lime_grade, cue.calcination_extent)
    assert abs(cue.lime_yield - expected) <= 5e-4
    # C6 really sees this carbonate here...
    lime = li.limestone_cue_for_chunk(sim, coord)
    assert lime is not None and lime.material == cue.carbonate_material
    # ...and C7 really can make a fire here.
    assert fi.ignition_cue_for_chunk(sim, coord) is not None


def test_world_never_lies_on_real_world():
    sim = _booted_sim("c10_neverlies")
    coords = _populate(sim)
    assert len(coords) > 0
    n_burnable = n_well = n_under = 0
    for coord in coords:
        cue = lb.lime_burning_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_burnable += 1
        if cue.well_burnt:
            n_well += 1
        else:
            n_under += 1
        _assert_cue_truthful(sim, coord, cue)
    # the grassland seed must surface real burnable (carbonate + fire) sites,
    # AND both burn outcomes (the inversion exists in the real world).
    assert n_burnable > 0
    assert n_well > 0 and n_under > 0


def test_burn_preview_non_mutating_and_truthful():
    sim = _booted_sim("c10_preview")
    coords = _populate(sim)
    target = next((c for c in coords
                   if lb.lime_burning_cue_for_chunk(sim, c) is not None), None)
    assert target is not None
    g = geo.chunk_geology(sim, target)
    before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    sim.agents.pos[0, 0] = (target[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (target[1] + 0.5) * CHUNK_SIDE_M
    out = lb.burn_preview(sim, float(sim.agents.pos[0, 0]),
                          float(sim.agents.pos[0, 1]))
    cue = lb.lime_burning_cue_for_chunk(sim, target)
    after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    assert after == before                       # preview mutated nothing
    assert out["burnable"] is True
    assert out["lime_yield"] == cue.lime_yield
    assert out["calcination_extent"] == cue.calcination_extent
    assert out["peak_temp_c"] == cue.peak_temp_c


def test_preview_names_missing_limestone():
    # Dry grassland, fire makeable, but bare granite — no carbonate to burn.
    sim = Simulation(SimConfig(name="c10_norock", seed=1, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_GRASS, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(
        coord=cc, layers=[_layer(0.0, 5.0, "granite")])}
    out = lb.burn_preview(sim, 4.0, 4.0)
    assert out["burnable"] is False
    assert out["has_limestone"] is False
    assert "limestone" in out["reason"]


def test_preview_names_missing_fire():
    # Carbonate underfoot but a soaked boreal forest: no fire can be made.
    sim = Simulation(SimConfig(name="c10_nofire", seed=2, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_BOREAL, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(coord=cc,
                                                  layers=_common_limestone())}
    out = lb.burn_preview(sim, 4.0, 4.0)
    assert out["burnable"] is False
    assert out["has_fire"] is False
    assert "fire" in out["reason"]


def test_preview_pure_limestone_lie_is_visible():
    # A pure white limestone outcrop with fire: burnable, but the open fire
    # under-burns it — the preview shows the unrealized mortar potential, not a binder.
    sim = Simulation(SimConfig(name="c10_pure", seed=3, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_GRASS, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(coord=cc, layers=_pure_limestone())}
    out = lb.burn_preview(sim, 4.0, 4.0)
    assert out["burnable"] is True
    assert out["carbonate_material"] == "limestone_pure"
    assert out["underburnt"] is True
    assert out["mortar_ready"] is False
    assert out["would_mortar_if_kiln_fired"] is True


# ---------------------------------------------------------------------------
# Actionable pick : best_burning_site_near
# ---------------------------------------------------------------------------

def _put_chunk(sim, cc, layers, biome, w):
    ch = sim.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, biome,
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
    sim._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=layers)
    sim._limestone_cue_cache.clear()
    sim._ignition_cue_cache.clear()
    sim._lime_burn_cue_cache.clear()


def test_best_burning_site_prefers_well_burnt_common_over_pure():
    sim = _booted_sim("c10_best")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    # a common-limestone site on the agent's own chunk — well-burnt, the best lime.
    _put_chunk(sim, cc, _common_limestone(), _GRASS, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    best = lb.best_burning_site_near(sim, 0, perception_radius_m=0.4 * CHUNK_SIDE_M)
    assert best is not None and best.burnable
    assert best.carbonate_material == "limestone"
    assert best.well_burnt is True


def test_no_burning_site_returns_none():
    # Bare hot desert: granite + no fine fuel → no carbonate, no fire: an honest
    # 'nothing to burn here'.
    sim = _booted_sim("c10_none")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, [_layer(0.0, 5.0, "granite")], _HOT_DESERT, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    assert lb.best_burning_site_near(sim, 0,
                                     perception_radius_m=0.4 * CHUNK_SIDE_M) is None


# ---------------------------------------------------------------------------
# Determinism + install hygiene
# ---------------------------------------------------------------------------

def _cue_key(c):
    return None if c is None else (c.carbonate_material, round(c.peak_temp_c, 3),
                                   round(c.calcination_extent, 6),
                                   round(c.lime_yield, 6), c.well_burnt,
                                   c.fire_method)


def test_determinism_same_seed():
    a = _booted_sim("c10_det_a", seed=0xBEEF)
    b = _booted_sim("c10_det_b", seed=0xBEEF)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    for coord in ca:
        assert _cue_key(lb.lime_burning_cue_for_chunk(a, coord)) == \
               _cue_key(lb.lime_burning_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("c10_idem")
    _populate(sim)
    c1 = lb.install_lime_burning(sim)
    c2 = lb.install_lime_burning(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = lb.lime_burning_summary(sim)
    assert set(s) >= {"n_chunks", "n_chunks_burnable", "burnable_rate",
                      "n_well_burnt", "n_underburnt", "best_lime_yield",
                      "best_peak_temp_c", "by_carbonate_material"}
    assert 0.0 <= s["burnable_rate"] <= 1.0
    assert s["n_chunks_burnable"] <= s["n_chunks"]
    assert s["n_well_burnt"] + s["n_underburnt"] == s["n_chunks_burnable"]
    assert s["best_peak_temp_c"] <= cf.OPEN_FIRE_MAX_C
