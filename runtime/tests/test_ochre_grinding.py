"""Invariants — Substrate capability : l'ocre broyée (Cap. C18).

Le 9ᵉ OPÉRATEUR ORTHOGONAL — *broyer* (grind) — et la 1ʳᵉ avancée de l'axe symbolique
(le pigment, substrat du dessin). C18 **rompt à nouveau vers le non-feu** après C17
(fire-based) — reco audit J+12 ``R-J12r3-1``. Elle compose le **même** chapeau de fer
gossan que C17 réduit à chaud, mais le broie **à froid** → un pigment terreux d'oxyde
de fer (ocre rouge hématite / noir magnétite). Couvre :

- **Composition C1** : cue émis ssi C1 surface un **gossan** ; ``is_pigment`` /
  ``pigment_quality`` disent la vérité (oxyde → pigment ; sulfure/non-fer → rien).
- **MENSONGE #9** (le chapeau de fer ment AUSSI au peintre) : le **même** tell rouille
  coiffe l'**oxyde** (hématite → rouge, magnétite → noir — un pigment **stable**), le
  **sulfure** (pyrite → aucun pigment terreux stable) et le **non-fer** (galène/
  sphalérite → pas d'ocre). Pendant orthogonal de l'inversion à 5 voies de C17.
- **« Le monde ne ment jamais »** : cue ⇒ minéral == C1 gossan ; ``is_pigment`` ⟺ oxyde
  de fer ; ``pigment_kg`` ≤ masse broyée ; chroma monotone en finesse, plafonné.
- ``grind_ochre_at`` **non mutant** (D10 gelé — aperçu, pas acte, comme C14/C15/C16).
- **N'introduit AUCUN nouveau tell** (garde-fou D8 par composition, 12ᵉ fois) : pas de
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
from engine.mineral_catalog import MINERAL_BY_NAME                  # noqa: E402
import engine.surface_mineralization as sm                          # noqa: E402
import engine.ochre_grinding as og                                  # noqa: E402

SEED = 0x42         # grassland continent — iron gossans (hematite oxide + pyrite sulfide)
GRID = 12


# ---------------------------------------------------------------------------
# Fakes for pure-derivation tests (no world — fast, trivially unit-testable)
# ---------------------------------------------------------------------------

def _gossan(mineral="hematite", frac=0.05, conf=0.9, biome=6, rgb=(150, 75, 40)):
    return SimpleNamespace(group="gossan", mineral=mineral, mass_fraction=frac,
                           confidence=conf, biome=biome, rgb=rgb, dig_depth_m=1.0)


# ---------------------------------------------------------------------------
# Pure SSOT invariants — ochre_grind_yield (synthetic ore + fineness)
# ---------------------------------------------------------------------------

def test_hematite_grinds_to_red_ochre():
    """Hematite (Fe2O3, oxide) is the classic red ochre — a stable, lightfast pigment."""
    y = og.ochre_grind_yield("hematite", 10.0)
    assert y.pigment_class == "red_ochre" and y.is_pigment is True
    assert y.lightfast is True and y.hue == og.RED_OCHRE_RGB
    assert y.tinting_strength > 0.0 and y.pigment_kg > 0.0


def test_magnetite_grinds_to_black_oxide():
    """Magnetite (Fe3O4, oxide) is a stable black iron-oxide pigment (lower chroma)."""
    y = og.ochre_grind_yield("magnetite", 10.0)
    assert y.pigment_class == "black_oxide" and y.is_pigment is True
    assert y.hue == og.BLACK_OXIDE_RGB
    assert y.base_chroma < og.ochre_grind_yield("hematite", 10.0).base_chroma


def test_pyrite_sulfide_grinds_to_no_pigment():
    """The painter's lie #9: pyrite (FeS2) is iron-RICH and rusty, but a sulfide grinds
    to NO stable earth pigment."""
    y = og.ochre_grind_yield("pyrite", 10.0)
    assert y.is_pigment is False and y.pigment_class == "none"
    assert y.pigment_kg == 0.0 and y.tinting_strength == 0.0


def test_non_iron_gossan_grinds_to_no_ochre():
    """A gossan over galena (lead) or sphalerite (zinc) — no iron oxide, so no ochre."""
    for ore in ("galena", "sphalerite"):
        y = og.ochre_grind_yield(ore, 10.0)
        assert y.is_pigment is False and y.pigment_class == "none"
        assert y.pigment_kg == 0.0


def test_unknown_mineral_is_barren():
    """An unknown / None ore name yields no pigment (defensive)."""
    assert og.ochre_grind_yield(None, 5.0).is_pigment is False
    assert og.ochre_grind_yield("not_a_mineral", 5.0).pigment_kg == 0.0


def test_tinting_monotone_in_fineness_and_capped():
    """Tinting strength rises with grind fineness and saturates at the oxide's chroma."""
    lo = og.ochre_grind_yield("hematite", 10.0, fineness=0.2).tinting_strength
    hi = og.ochre_grind_yield("hematite", 10.0, fineness=0.95).tinting_strength
    assert lo < hi <= 1.0
    # magnetite caps at its lower intrinsic chroma, never above it
    mag = og.ochre_grind_yield("magnetite", 10.0, fineness=1.0)
    assert mag.tinting_strength <= mag.base_chroma + 1e-9


def test_pigment_never_exceeds_ground_mass():
    """Usable pigment powder can never exceed the earth mass ground (recovery < 1)."""
    y = og.ochre_grind_yield("hematite", 10.0, fineness=1.0)
    assert 0.0 <= y.pigment_kg <= 10.0


# ---------------------------------------------------------------------------
# Pure cue derivation — _cue_from_gossan (synthetic gossan cues)
# ---------------------------------------------------------------------------

def test_cue_requires_a_gossan():
    """No cue without a gossan tell (a copper/None group → None)."""
    assert og._cue_from_gossan((0, 0, 0), None) is None
    assert og._cue_from_gossan((0, 0, 0),
                               SimpleNamespace(group="copper", mineral="native_copper",
                                               mass_fraction=0.05, rgb=(80, 140, 70),
                                               confidence=0.9, biome=6)) is None


def test_cue_oxide_is_usable_pigment():
    """A hematite gossan → a usable red-ochre cue at the surface (collect_depth 0)."""
    cue = og._cue_from_gossan((1, 2, 0), _gossan("hematite", frac=0.05))
    assert cue is not None
    assert cue.pigment_class == "red_ochre" and cue.is_pigment is True
    assert cue.usable is True and cue.lightfast is True
    assert cue.collect_depth_m == 0.0 and cue.pigment_quality > 0.0
    assert cue.hue == og.RED_OCHRE_RGB


def test_cue_pyrite_emits_but_is_not_pigment():
    """A pyrite gossan still emits a cue (the rusty tell looks identical) but it truthfully
    reports no pigment — the lie made visible, not hidden."""
    cue = og._cue_from_gossan((0, 0, 0), _gossan("pyrite", frac=0.05))
    assert cue is not None and cue.mineral == "pyrite"
    assert cue.is_pigment is False and cue.usable is False
    assert cue.pigment_quality == 0.0 and cue.pigment_class == "none"


def test_cue_richer_cap_tints_stronger():
    """A richer oxide cap (higher C1 mass_fraction) yields a higher pigment quality."""
    lean = og._cue_from_gossan((0, 0, 0), _gossan("hematite", frac=0.005))
    rich = og._cue_from_gossan((0, 0, 0), _gossan("hematite", frac=0.06))
    assert lean.pigment_quality < rich.pigment_quality


def test_cue_keeps_c1_surface_tell_rgb():
    """The perceived SURFACE colour stays C1's rusty tell (the same for all gossans);
    only the OUTPUT powder colour differs by mineral."""
    cue = og._cue_from_gossan((0, 0, 0), _gossan("hematite", rgb=(150, 75, 40)))
    assert cue.tell_rgb == (150, 75, 40) and cue.hue == og.RED_OCHRE_RGB


# ---------------------------------------------------------------------------
# D8 guardrail — introduces no new tell (composition only, 12th time)
# ---------------------------------------------------------------------------

def test_introduces_no_new_tell():
    """C18 surfaces NO new tell: no own ``_PROFILE``, composes C1 (sm). It is a verb
    (grind), not an outcrop — the *_outcrop glob ignores it."""
    assert not hasattr(og, "_PROFILE"), "ochre_grinding must not declare a tell table"
    assert og.sm is sm                                  # composes C1 (not a duplicate)
    assert not Path(og.__file__).name.endswith("_outcrop.py")


def test_py_to_rust_unchanged_at_15():
    """The cross-language contract map is untouched by C18 (D8 by composition)."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import test_geology_cross_language_contract as contract
    assert len(contract.PY_TO_RUST) == 15


# ---------------------------------------------------------------------------
# Real Genesis world invariants (seed 0x42 — iron gossans, oxide + sulfide)
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = SEED, grid: int = GRID):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    og.install_ochre_grinding(sim)
    coords = []
    for cx in range(grid):
        for cy in range(grid):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


@pytest.fixture(scope="module")
def ochre_sim():
    return _booted_sim("test_ochre_grinding")


def test_real_world_emits_emergent_ochre_sites(ochre_sim):
    """An iron-rich continent produces emergent ochre sites — BOTH usable oxide pigment
    AND the rusty-but-barren lie (pyrite / lead / zinc) — with no injection."""
    sim, _coords = ochre_sim
    s = og.ochre_summary(sim)
    assert s["n_ochre_sites"] > 0
    assert s["n_pigment"] > 0          # at least one oxide gossan → real pigment
    assert s["n_lie"] > 0              # at least one rusty-but-barren gossan (the lie)
    assert s["n_usable"] > 0
    assert s["best_pigment_quality"] > 0.0


def test_world_never_lies_real(ochre_sim):
    """Every real cue: the mineral matches C1's gossan + is_pigment ⟺ iron oxide +
    pigment colour is the right output hue + barren sites carry quality 0."""
    sim, coords = ochre_sim
    violations = 0
    n_pigment = n_lie = 0
    for coord in coords:
        cue = og.ochre_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        c1 = sm.surface_cue_for_chunk(sim, coord)
        if c1 is None or c1.group != "gossan" or c1.mineral != cue.mineral:
            violations += 1
        m = MINERAL_BY_NAME.get(cue.mineral)
        is_oxide_iron = (m is not None
                         and m.category.name == "OXIDE"
                         and m.yields_per_kg_ore.get("Fe", 0.0) > 0.0)
        if cue.is_pigment != is_oxide_iron:
            violations += 1
        if cue.is_pigment:
            n_pigment += 1
            if not (cue.pigment_quality > 0.0
                    and cue.hue in (og.RED_OCHRE_RGB, og.BLACK_OXIDE_RGB)
                    and cue.lightfast):
                violations += 1
        else:
            n_lie += 1
            if not (cue.pigment_quality == 0.0 and cue.usable is False):
                violations += 1
        # the surface tell stays C1's rusty colour for every gossan
        if c1 is not None and tuple(cue.tell_rgb) != tuple(c1.rgb):
            violations += 1
    assert violations == 0, f"{violations} world-lies among real ochre cues"
    assert n_pigment > 0 and n_lie > 0


def test_grind_preview_is_non_mutating(ochre_sim):
    """grind_ochre_at on a real oxide site reports a pigment AND mutates nothing
    (geology untouched — D10 frozen, unlike C17 bloom_at)."""
    sim, coords = ochre_sim
    coord = next((c for c in coords
                  if (cu := og.ochre_cue_for_chunk(sim, c)) is not None
                  and cu.is_pigment), None)
    assert coord is not None
    cue = og.ochre_cue_for_chunk(sim, coord)
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    g = geo.chunk_geology(sim, coord)
    before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    prev = og.grind_ochre_at(sim, float(sim.agents.pos[0, 0]),
                             float(sim.agents.pos[0, 1]))
    after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    assert after == before                              # non-mutating
    assert prev["grindable"] is True and prev["is_pigment"] is True
    assert prev["pigment_quality"] == cue.pigment_quality
    assert prev["collect_depth_m"] == 0.0


def test_grind_preview_names_the_lie(ochre_sim):
    """A pyrite/lead/zinc gossan previews as grindable-but-barren, naming the why-not."""
    sim, coords = ochre_sim
    coord = next((c for c in coords
                  if (cu := og.ochre_cue_for_chunk(sim, c)) is not None
                  and not cu.is_pigment), None)
    assert coord is not None
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    prev = og.grind_ochre_at(sim, float(sim.agents.pos[0, 0]),
                             float(sim.agents.pos[0, 1]))
    assert prev["grindable"] is True and prev["is_pigment"] is False
    assert prev["pigment_quality"] == 0.0 and prev["reason"] != "ok"


def test_best_site_prefers_usable_pigment(ochre_sim):
    """best_ochre_site_near returns a usable oxide pigment; pigment_class filters colour."""
    sim, coords = ochre_sim
    coord = next((c for c in coords
                  if (cu := og.ochre_cue_for_chunk(sim, c)) is not None
                  and cu.is_pigment), None)
    assert coord is not None
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    best = og.best_ochre_site_near(sim, 0, perception_radius_m=4 * CHUNK_SIDE_M)
    assert best is not None and best.usable is True and best.is_pigment is True
    red = og.best_ochre_site_near(sim, 0, perception_radius_m=4 * CHUNK_SIDE_M,
                                  pigment_class="red_ochre")
    assert red is None or red.pigment_class == "red_ochre"


def test_determinism_same_seed():
    """Two builds at the same seed give bit-identical oracle cues."""
    sim_a, coords_a = _booted_sim("det_a")
    sim_b, coords_b = _booted_sim("det_b")
    assert coords_a == coords_b
    mismatches = 0
    for coord in coords_a:
        a = og.ochre_cue_for_chunk(sim_a, coord)
        b = og.ochre_cue_for_chunk(sim_b, coord)
        ka = None if a is None else (a.mineral, a.pigment_class,
                                     round(a.pigment_quality, 6), a.usable, a.hue)
        kb = None if b is None else (b.mineral, b.pigment_class,
                                     round(b.pigment_quality, 6), b.usable, b.hue)
        if ka != kb:
            mismatches += 1
    assert mismatches == 0


def test_idempotent_zero_tick_cost(ochre_sim):
    """Install is idempotent and adds NO per-tick hook (zero tick cost — it is an oracle)."""
    sim, _ = ochre_sim
    step_before = sim.step
    c1 = og.install_ochre_grinding(sim)
    c2 = og.install_ochre_grinding(sim)
    assert c1 is c2
    assert sim.step is step_before              # no sim.step wrapping
