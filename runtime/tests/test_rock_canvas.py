"""Invariants — Substrate capability : la paroi à peindre (Cap. C20).

La 2ᵉ brique de l'axe SYMBOLIQUE (le **support** de la marque, après le **pigment** C18).
Non-fire (D9 1→0 après C19) ; non mutant (D10 gelé). Couvre :

- **Composition C6** : cue émis ssi C6 ``limestone_cue_for_chunk`` surface une paroi
  carbonatée ; deux axes orthogonaux — adhérence (porosité du matériau) × persistance
  (stabilité du site = ``weather_state`` de C6).
- **MENSONGE #11** (la belle paroi qui ne tient pas la marque) : une paroi SAINE (voile
  de calcite) tient une marque durable ; une paroi KARST/FROST l'accepte (adhérence forte,
  c'est du calcaire) mais l'**écaille** (persistance effondrée → ``holds_lasting_mark``
  False). Climat-driven (comme C15) : même calcaire, sec→durable vs humide karst→s'écaille.
- **Pont L1↔L4** : ``CALCITE_ADHESION`` byte-égale à
  ``art_discovery.PAINTABLE_SURFACES["bedrock_calcite"]`` (fonde la chaîne abstraite L4).
- **Visibilité** : un pigment dont la couleur épouse le mur est invisible (la 2ᵉ moitié du
  mensonge) — ``mark_visibility``.
- ``canvas_preview``/``paint_outcome`` **non mutants** (géologie jamais touchée).
- **N'introduit AUCUN nouveau tell** (garde-fou D8 par composition, 14ᵉ fois) : pas de
  ``_PROFILE``, ``PY_TO_RUST`` reste 15, hors glob ``*_outcrop.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

import pytest                                                       # noqa: E402

from engine.sim import Simulation, SimConfig                        # noqa: E402
from engine.world_genesis import GenesisParams                      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.limestone_outcrop as li                              # noqa: E402
import engine.ochre_grinding as og                                 # noqa: E402
import engine.rock_canvas as rc                                    # noqa: E402

SOUND_SEED = 0xC1A7   # dry temperate carbonate continent — SOUND walls (durable canvases)
KARST_SEED = 0xFE11   # humid continent — the SAME carbonate, KARST (flaking) walls
GRID = 12


# ---------------------------------------------------------------------------
# Fakes for pure-derivation tests (no world — fast, trivially unit-testable)
# ---------------------------------------------------------------------------

def _lime_cue(material="limestone_pure", weather=li.WeatherState.SOUND,
              rgb=(245, 240, 225), conf=0.9, biome=6):
    return SimpleNamespace(material=material, weather_state=int(weather), rgb=rgb,
                           confidence=conf, biome=biome)


# ---------------------------------------------------------------------------
# Pure SSOT invariants — canvas_quality
# ---------------------------------------------------------------------------

def test_sound_carbonate_holds_a_lasting_mark():
    """A SOUND carbonate wall grows a calcite veil → a painted mark lasts."""
    q = rc.canvas_quality("limestone_pure", li.WeatherState.SOUND)
    assert q.surface_key == "bedrock_calcite"
    assert q.adhesion > 0.0 and q.persistence > 0.0
    assert q.durability == pytest.approx(q.adhesion * q.persistence)
    assert q.holds_lasting_mark is True


def test_karst_wall_takes_pigment_but_flakes():
    """The lie #11: a KARST wall has high adhesion (it IS calcite) but low persistence
    (active dissolution) → the mark does not last."""
    sound = rc.canvas_quality("limestone_pure", li.WeatherState.SOUND)
    karst = rc.canvas_quality("limestone_pure", li.WeatherState.KARST)
    assert karst.adhesion == sound.adhesion          # same material → same grip
    assert karst.persistence < sound.persistence     # but unstable → flakes
    assert karst.holds_lasting_mark is False
    assert karst.durability < sound.durability


def test_frost_wall_flakes():
    """A FROST (freeze-thaw) carbonate wall spalls → the mark does not last."""
    q = rc.canvas_quality("limestone_pure", li.WeatherState.FROST)
    assert q.holds_lasting_mark is False
    assert q.persistence < rc.canvas_quality("limestone_pure", li.WeatherState.KARST).persistence \
        or q.persistence <= rc.canvas_quality("limestone_pure", li.WeatherState.KARST).persistence


def test_adhesion_ranks_by_porosity():
    """Fine porous chalk/limestone grips pigment best; dense recrystallised marble least."""
    pure = rc.canvas_quality("limestone_pure", li.WeatherState.SOUND).adhesion
    common = rc.canvas_quality("limestone", li.WeatherState.SOUND).adhesion
    marble = rc.canvas_quality("marble", li.WeatherState.SOUND).adhesion
    assert pure >= common > marble


def test_durability_is_adhesion_times_persistence():
    """Durability is exactly the product of the two orthogonal physical axes."""
    for mat in ("limestone_pure", "limestone", "marble", "dolomite", "calcite"):
        for w in (li.WeatherState.SOUND, li.WeatherState.KARST, li.WeatherState.FROST):
            q = rc.canvas_quality(mat, w)
            assert q.durability == pytest.approx(q.adhesion * q.persistence)


def test_calcite_adhesion_bridges_art_discovery_l4():
    """The L1↔L4 bridge: the best carbonate adhesion equals the abstract art-layer value,
    grounding ``art_discovery.PAINTABLE_SURFACES['bedrock_calcite']`` in real geology."""
    import engine.art_discovery as art
    assert rc._CALCITE_SURFACE_KEY in art.PAINTABLE_SURFACES
    assert rc.CALCITE_ADHESION == art.PAINTABLE_SURFACES["bedrock_calcite"]
    # the best modelled carbonate adhesion is exactly the bridge value
    assert max(rc._ADHESION_BY_MATERIAL.values()) == rc.CALCITE_ADHESION


# ---------------------------------------------------------------------------
# Visibility (contrast) — composes C18 pigment hues
# ---------------------------------------------------------------------------

def test_dark_pigment_on_pale_wall_is_visible():
    """Red ochre / black oxide (C18) on a pale calcite wall → high contrast → visible."""
    wall = (245, 240, 225)
    for pig in (og.RED_OCHRE_RGB, og.BLACK_OXIDE_RGB):
        c, vis = rc.mark_visibility(wall, pig)
        assert vis is True and c >= rc.MIN_VISIBLE_CONTRAST


def test_pigment_matching_wall_is_invisible():
    """The visibility lie: a pigment whose colour matches the wall is real paint but
    invisible (near-zero contrast)."""
    wall = (245, 240, 225)
    c, vis = rc.mark_visibility(wall, (244, 241, 224))
    assert c < rc.MIN_VISIBLE_CONTRAST and vis is False


# ---------------------------------------------------------------------------
# Pure cue derivation — _cue_from_limestone (synthetic C6 cues)
# ---------------------------------------------------------------------------

def test_cue_requires_a_carbonate_wall():
    """No cue without a C6 carbonate wall."""
    assert rc._cue_from_limestone((0, 0, 0), None) is None


def test_cue_sound_holds_karst_flakes():
    """A SOUND wall cue holds a lasting mark; a KARST wall cue does not (lie made visible)."""
    sound = rc._cue_from_limestone((1, 1, 0), _lime_cue(weather=li.WeatherState.SOUND))
    karst = rc._cue_from_limestone((2, 2, 0), _lime_cue(weather=li.WeatherState.KARST))
    assert sound is not None and sound.holds_lasting_mark is True and sound.sound_wall is True
    assert karst is not None and karst.holds_lasting_mark is False and karst.karst_wall is True
    assert karst.material == "limestone_pure"          # same material, opposite outcome


# ---------------------------------------------------------------------------
# paint_outcome — composes wall (this cap) × pigment (C18)
# ---------------------------------------------------------------------------

def test_paint_outcome_lasting_and_visible():
    """Lightfast dark pigment on a sound pale wall → a mark that lasts AND is seen."""
    cue = rc._cue_from_limestone((0, 0, 0), _lime_cue(weather=li.WeatherState.SOUND))
    out = rc.paint_outcome(cue, og.RED_OCHRE_RGB, pigment_lightfast=True)
    assert out["lasts"] is True and out["visible"] is True
    assert out["lasting_and_visible"] is True


def test_paint_outcome_non_lightfast_pigment_does_not_last():
    """A non-lightfast pigment fades even on a perfect wall."""
    cue = rc._cue_from_limestone((0, 0, 0), _lime_cue(weather=li.WeatherState.SOUND))
    out = rc.paint_outcome(cue, og.RED_OCHRE_RGB, pigment_lightfast=False)
    assert out["lasts"] is False
    assert out["mark_durability"] < cue.durability


def test_paint_outcome_karst_wall_does_not_last():
    """Even a perfect lightfast pigment will not last on a flaking karst wall."""
    cue = rc._cue_from_limestone((0, 0, 0), _lime_cue(weather=li.WeatherState.KARST))
    out = rc.paint_outcome(cue, og.RED_OCHRE_RGB, pigment_lightfast=True)
    assert out["lasts"] is False and out["visible"] is True   # visible now, gone tomorrow


# ---------------------------------------------------------------------------
# D8 guardrail — introduces no new tell (composition only, 14th time)
# ---------------------------------------------------------------------------

def test_introduces_no_new_tell():
    """C20 surfaces NO new tell: no own ``_PROFILE``, composes C6 (li). It is a support
    (canvas), not an outcrop — the *_outcrop glob ignores it."""
    assert not hasattr(rc, "_PROFILE"), "rock_canvas must not declare a tell table"
    assert rc.li is li                                  # composes C6 (not a duplicate)
    assert not Path(rc.__file__).name.endswith("_outcrop.py")


def test_py_to_rust_unchanged_at_15():
    """The cross-language contract map is untouched by C20 (D8 by composition)."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import test_geology_cross_language_contract as contract
    assert len(contract.PY_TO_RUST) == 15


# ---------------------------------------------------------------------------
# Real Genesis world invariants
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int, grid: int = GRID):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    rc.install_rock_canvas(sim)
    coords = []
    for cx in range(grid):
        for cy in range(grid):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


@pytest.fixture(scope="module")
def sound_sim():
    return _booted_sim("test_rock_canvas_sound", SOUND_SEED)


def test_real_world_emits_durable_canvases(sound_sim):
    """A dry temperate carbonate continent produces emergent paintable walls that hold a
    lasting mark — the Lascaux-like sound calcite face, with no injection."""
    sim, _coords = sound_sim
    s = rc.canvas_summary(sim)
    assert s["n_canvas_walls"] > 0
    assert s["n_lasting"] > 0
    assert s["best_durability"] >= rc.MIN_DURABLE


def test_world_never_lies_real(sound_sim):
    """Every real cue matches C6's carbonate (same material); holds_lasting_mark ⟺
    durability ≥ threshold; durability == adhesion × persistence."""
    sim, coords = sound_sim
    violations = 0
    n = 0
    for coord in coords:
        cue = rc.canvas_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n += 1
        lime = li.limestone_cue_for_chunk(sim, coord)
        if lime is None or lime.material != cue.material:
            violations += 1
        if cue.holds_lasting_mark != (cue.durability >= rc.MIN_DURABLE):
            violations += 1
        if abs(cue.durability - cue.adhesion * cue.persistence) > 1e-9:
            violations += 1
        if cue.surface_key != "bedrock_calcite":
            violations += 1
    assert violations == 0, f"{violations} world-lies among real canvas cues"
    assert n > 0


def test_canvas_preview_is_non_mutating(sound_sim):
    """canvas_preview reports a wall AND mutates nothing (geology untouched — D10 frozen)."""
    sim, coords = sound_sim
    coord = next((c for c in coords if rc.canvas_cue_for_chunk(sim, c) is not None), None)
    assert coord is not None
    cue = rc.canvas_cue_for_chunk(sim, coord)
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    g = geo.chunk_geology(sim, coord)
    before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    prev = rc.canvas_preview(sim, float(sim.agents.pos[0, 0]),
                             float(sim.agents.pos[0, 1]))
    after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    assert after == before                              # non-mutating
    assert prev["markable"] is True
    assert prev["holds_lasting_mark"] == cue.holds_lasting_mark


def test_best_canvas_prefers_durable(sound_sim):
    """best_canvas_near returns the most durable wall; require_lasting keeps only walls
    that hold a lasting mark."""
    sim, coords = sound_sim
    coord = next((c for c in coords if rc.canvas_cue_for_chunk(sim, c) is not None), None)
    assert coord is not None
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    best = rc.best_canvas_near(sim, 0, perception_radius_m=6 * CHUNK_SIDE_M)
    assert best is not None and best.durability > 0.0
    lasting = rc.best_canvas_near(sim, 0, perception_radius_m=6 * CHUNK_SIDE_M,
                                  require_lasting=True)
    assert lasting is None or lasting.holds_lasting_mark is True


def test_karst_climate_makes_the_mark_flake():
    """The lie #11 emergent on the real world: a HUMID continent exposes the SAME carbonate
    walls, but they are KARST → the mark flakes (holds_lasting_mark False). Climate-driven,
    no injection — the exact pendant of C15's humid-vs-arid salt lie."""
    sim, coords = _booted_sim("test_rock_canvas_karst", KARST_SEED)
    s = rc.canvas_summary(sim)
    assert s["n_canvas_walls"] > 0
    assert s["n_flaking"] > 0          # carbonate walls that do NOT hold a mark
    # every flaking wall is real carbonate (same material C6 surfaces) but unstable
    flaking = [rc.canvas_cue_for_chunk(sim, c) for c in coords]
    flaking = [c for c in flaking if c is not None and not c.holds_lasting_mark]
    assert flaking, "expected emergent flaking (karst/frost) carbonate walls"
    for c in flaking:
        assert c.adhesion > 0.0         # it IS calcite (takes the pigment)
        assert c.karst_wall or c.frost_wall   # ...but unstable → flakes


def test_determinism_same_seed():
    """Two builds at the same seed give bit-identical oracle cues."""
    sim_a, coords_a = _booted_sim("det_a", SOUND_SEED)
    sim_b, coords_b = _booted_sim("det_b", SOUND_SEED)
    assert coords_a == coords_b
    mism = 0
    for coord in coords_a:
        a = rc.canvas_cue_for_chunk(sim_a, coord)
        b = rc.canvas_cue_for_chunk(sim_b, coord)
        ka = None if a is None else (a.material, round(a.durability, 6),
                                     a.holds_lasting_mark, a.weather_state)
        kb = None if b is None else (b.material, round(b.durability, 6),
                                     b.holds_lasting_mark, b.weather_state)
        if ka != kb:
            mism += 1
    assert mism == 0


def test_idempotent_zero_tick_cost(sound_sim):
    """Install is idempotent and adds NO per-tick hook (zero tick cost — it is an oracle)."""
    sim, _ = sound_sim
    step_before = sim.step
    c1 = rc.install_rock_canvas(sim)
    c2 = rc.install_rock_canvas(sim)
    assert c1 is c2
    assert sim.step is step_before              # no sim.step wrapping
