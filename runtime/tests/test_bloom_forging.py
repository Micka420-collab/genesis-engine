"""Invariants — Substrate capability : le cinglage de la loupe (Cap. C19).

La 6ᵉ TRANSFORMATION et la 3ᵉ MÉTALLURGIQUE — elle **ferme la chaîne du fer** : marteler
à chaud la **loupe** spongieuse de C17 pour en **expulser la scorie** de fayalite et la
**consolider** en **fer forgé** (wrought iron). Exécute la reco ``R-J12r3-2`` de l'audit
J+12 (« la forge de consolidation ferme la chaîne du fer — sans nouveau tell, sans feu
nouveau »). Couvre :

- **Composition C17** : cue émis ssi C17 ``bloom_cue_for_chunk`` rend une loupe ferreuse ;
  forge ``per kg ore`` directement sur les chiffres de C17.
- **MENSONGE #10** (le fer du chapeau pyriteux se brise sous le marteau) : la loupe
  d'**oxyde** se consolide saine ; la loupe **red-short** (pyrite, FeS aux joints de
  grain) **se fissure** à chaud (*hot-shortness*) → rendement effondré, santé plafonnée.
  Pendant, à l'étape suivante, du ``red_short`` de C17.
- **Solid-state** : ``melted`` toujours False — fer forgé, jamais fonte (1538 °C hors
  d'atteinte) ; conservation Fe : ``wrought + scale + crack == bloom_iron``.
- **Chaleur de forge** : le cinglage n'expulse la scorie que ≥ ``SLAG_EXPULSION_TEMP_C``
  (= seuil C12, où la fayalite coule) — trop froid ⇒ rien ne consolide.
- ``consolidate_bloom`` **non mutant** (D10 gelé — transforme un produit tenu, pas la
  géologie ; comme C8/C9).
- **N'introduit AUCUN nouveau tell** (garde-fou D8 par composition, 13ᵉ fois) : pas de
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
import engine.iron_bloomery as ib                                   # noqa: E402
import engine.forced_draught as fd                                  # noqa: E402
import engine.bloom_forging as bf                                   # noqa: E402

SEED = 0x42         # grassland continent — iron gossans (hematite oxide + pyrite sulfide)
GRID = 12


# ---------------------------------------------------------------------------
# Fakes for pure-derivation tests (no world — fast, trivially unit-testable)
# ---------------------------------------------------------------------------

def _bloom_cue(mineral="hematite", ore_class="oxide_iron", red_short=False,
               bloom_iron=0.35, bloom_iron_roasted=None, purity=0.96,
               peak=1300.0, conf=0.9, biome=6):
    """A minimal duck-typed C17 BloomCue for pure derivation tests."""
    return SimpleNamespace(
        iron_mineral=mineral, ore_class=ore_class, red_short=red_short,
        bloom_iron_per_kg_ore=bloom_iron,
        bloom_iron_per_kg_ore_roasted=(bloom_iron if bloom_iron_roasted is None
                                       else bloom_iron_roasted),
        bloom_purity=purity, forced_peak_c=peak, confidence=conf, biome=biome)


# ---------------------------------------------------------------------------
# Pure SSOT invariants — wrought_yield (synthetic bloom numbers)
# ---------------------------------------------------------------------------

def test_oxide_bloom_consolidates_to_sound_wrought_iron():
    """An oxide bloom hammered hot welds into sound wrought iron (most of the iron kept)."""
    y = bf.wrought_yield(10.0, 0.96, red_short=False, forge_temp_c=1300.0)
    assert y.hot_enough is True and y.melted is False
    assert y.is_wrought is True and y.cracked is False
    assert y.wrought_iron_kg > 0.0 and y.soundness >= bf.SOUND_THRESHOLD
    assert y.slag_expelled_kg > 0.0          # fayalite driven out


def test_red_short_bloom_cracks_and_yields_little():
    """The smith's lie #10: a red-short (pyrite) bloom cracks under the hammer (hot-short)
    → collapsed wrought yield, soundness capped below the usable threshold."""
    sound = bf.wrought_yield(10.0, 0.96, red_short=False, forge_temp_c=1300.0)
    redsh = bf.wrought_yield(10.0, 0.80, red_short=True, forge_temp_c=1300.0)
    assert redsh.cracked is True and redsh.red_short is True
    assert redsh.is_wrought is False                       # never welds sound
    assert redsh.soundness <= bf.RED_SHORT_SOUNDNESS_CEIL + 1e-9
    assert redsh.crack_loss_kg > 0.0
    assert redsh.wrought_iron_kg < sound.wrought_iron_kg   # far less iron recovered


def test_too_cold_a_forge_consolidates_nothing():
    """Below the slag-expulsion heat the fayalite stays frozen in → no consolidation."""
    y = bf.wrought_yield(10.0, 0.96, red_short=False,
                         forge_temp_c=bf.SLAG_EXPULSION_TEMP_C - 1.0)
    assert y.hot_enough is False
    assert y.wrought_iron_kg == 0.0 and y.is_wrought is False
    assert y.slag_expelled_kg == 0.0 and y.soundness == 0.0


def test_iron_mass_is_conserved():
    """All the bloom's iron is accounted: consolidated + fire scale + cracked-off."""
    for red_short, purity in ((False, 0.96), (True, 0.80)):
        y = bf.wrought_yield(10.0, purity, red_short=red_short, forge_temp_c=1300.0)
        total = y.wrought_iron_kg + y.scale_loss_kg + y.crack_loss_kg
        assert abs(total - 10.0) < 1e-9
        assert y.wrought_iron_kg <= 10.0


def test_iron_never_melts():
    """Forging stays solid-state at any reachable hearth heat — wrought iron, never cast."""
    for t in (1200.0, 1300.0, 1400.0, bf.IRON_MELT_TEMP_C - 1.0):
        assert bf.wrought_yield(10.0, 0.96, red_short=False, forge_temp_c=t).melted is False
    assert bf.IRON_MELT_TEMP_C > 1400.0      # above any bloomery/forge hearth (C12 ceiling)


def test_more_heats_expel_more_slag_and_consolidate_more():
    """Soundness and slag expulsion rise (saturating) with the number of heats."""
    one = bf.wrought_yield(10.0, 0.96, red_short=False, forge_temp_c=1300.0, n_heats=1)
    three = bf.wrought_yield(10.0, 0.96, red_short=False, forge_temp_c=1300.0, n_heats=3)
    assert three.soundness > one.soundness
    assert three.slag_expelled_fraction > one.slag_expelled_fraction
    assert three.slag_expelled_fraction <= 1.0
    # ...but more heats also burn more iron to scale (an honest cost).
    assert three.scale_loss_kg > one.scale_loss_kg


def test_purity_rises_toward_wrought_ceiling():
    """Expelling slag raises the billet's Fe fraction toward the wrought-iron ceiling;
    a red-short billet caps lower (residual sulfur stays)."""
    oxide = bf.wrought_yield(10.0, 0.96, red_short=False, forge_temp_c=1300.0)
    assert oxide.final_purity >= 0.96 and oxide.final_purity <= bf.WROUGHT_PURITY_CEIL + 1e-9
    redsh = bf.wrought_yield(10.0, 0.80, red_short=True, forge_temp_c=1300.0)
    assert redsh.final_purity <= bf.RED_SHORT_PURITY_CEIL + 1e-9


def test_zero_bloom_is_barren():
    """No iron in → nothing out (defensive)."""
    y = bf.wrought_yield(0.0, 0.96, red_short=False, forge_temp_c=1300.0)
    assert y.wrought_iron_kg == 0.0 and y.is_wrought is False


def test_slag_expulsion_threshold_reuses_c12_ssot():
    """The forge heat threshold is the C12 bloomery regime (where fayalite flows) — reused
    verbatim, not a new magic number (SSOT discipline)."""
    assert bf.SLAG_EXPULSION_TEMP_C == fd.IRON_BLOOMERY_TEMP_C


# ---------------------------------------------------------------------------
# Pure cue derivation — _cue_from_bloom (synthetic C17 bloom cues)
# ---------------------------------------------------------------------------

def test_cue_requires_a_bloom():
    """No cue without a C17 bloom (None or zero-iron bloom → None)."""
    assert bf._cue_from_bloom((0, 0, 0), None) is None
    assert bf._cue_from_bloom((0, 0, 0), _bloom_cue(bloom_iron=0.0,
                                                    bloom_iron_roasted=0.0)) is None


def test_cue_oxide_is_sound_wrought():
    """A hematite bloom cue → a sound wrought-iron forge cue."""
    cue = bf._cue_from_bloom((1, 2, 0), _bloom_cue("hematite"))
    assert cue is not None
    assert cue.ore_class == "oxide_iron" and cue.is_wrought is True
    assert cue.cracked is False and cue.melted is False
    assert cue.wrought_iron_per_kg_ore > 0.0 and cue.soundness >= bf.SOUND_THRESHOLD


def test_cue_red_short_emits_but_cracks():
    """A pyrite bloom still emits a cue (iron IS won by C17) but it truthfully reports
    cracking — the lie made visible, not hidden."""
    cue = bf._cue_from_bloom((0, 0, 0), _bloom_cue(
        "pyrite", ore_class="sulfide_iron", red_short=True, purity=0.80,
        bloom_iron=0.0, bloom_iron_roasted=0.135))   # direct 0, roasted wins
    assert cue is not None and cue.iron_mineral == "pyrite"
    assert cue.cracked is True and cue.is_wrought is False
    assert cue.crack_loss_per_kg_ore > 0.0


def test_cue_uses_achievable_bloom_iron():
    """A sulfide whose iron is only winnable after a roast forges the roasted bloom."""
    cue = bf._cue_from_bloom((0, 0, 0), _bloom_cue(
        "pyrite", ore_class="sulfide_iron", red_short=True,
        bloom_iron=0.0, bloom_iron_roasted=0.2))
    assert cue is not None and cue.bloom_iron_per_kg_ore == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# consolidate_bloom on a held product — NON-MUTATING transform (D10 frozen)
# ---------------------------------------------------------------------------

def test_consolidate_bloom_from_bloom_result():
    """Consolidating a held C17 BloomResult yields wrought iron equal to the SSOT."""
    bloom = SimpleNamespace(iron_mineral="hematite", ore_class="oxide_iron",
                            bloom_iron_kg=4.0, bloom_purity=0.96, red_short=False,
                            peak_c=1300.0)
    res = bf.consolidate_bloom(bloom)
    y = bf.wrought_yield(4.0, 0.96, red_short=False, forge_temp_c=1300.0)
    assert res.wrought_iron_kg == pytest.approx(round(y.wrought_iron_kg, 6))
    assert res.is_wrought is True and res.melted is False
    # conservation passes through the realized result too
    assert abs((res.wrought_iron_kg + res.scale_loss_kg + res.crack_loss_kg) - 4.0) < 1e-6


def test_consolidate_red_short_bloom_cracks():
    """A held red-short bloom consolidates to a cracked, low-yield billet."""
    bloom = SimpleNamespace(iron_mineral="pyrite", ore_class="sulfide_iron",
                            bloom_iron_kg=4.0, bloom_purity=0.80, red_short=True,
                            peak_c=1300.0)
    res = bf.consolidate_bloom(bloom)
    assert res.cracked is True and res.is_wrought is False
    assert res.crack_loss_kg > 0.0


# ---------------------------------------------------------------------------
# D8 guardrail — introduces no new tell (composition only, 13th time)
# ---------------------------------------------------------------------------

def test_introduces_no_new_tell():
    """C19 surfaces NO new tell: no own ``_PROFILE``, composes C17 (ib). It is a verb
    (forge), not an outcrop — the *_outcrop glob ignores it."""
    assert not hasattr(bf, "_PROFILE"), "bloom_forging must not declare a tell table"
    assert bf.ib is ib                                  # composes C17 (not a duplicate)
    assert not Path(bf.__file__).name.endswith("_outcrop.py")


def test_py_to_rust_unchanged_at_15():
    """The cross-language contract map is untouched by C19 (D8 by composition)."""
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
    bf.install_bloom_forging(sim)
    coords = []
    for cx in range(grid):
        for cy in range(grid):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


@pytest.fixture(scope="module")
def forge_sim():
    return _booted_sim("test_bloom_forging")


def test_real_world_emits_emergent_forge_sites(forge_sim):
    """An iron-rich continent produces emergent forge sites wherever C17 yields a bloom —
    both sound (oxide) and the cracking red-short lie — with no injection."""
    sim, _coords = forge_sim
    s = bf.forge_summary(sim)
    assert s["n_forge_sites"] > 0
    assert s["best_wrought_iron_per_kg_ore"] > 0.0
    assert s["best_soundness"] >= bf.SOUND_THRESHOLD


def test_forge_sites_track_bloom_sites(forge_sim):
    """Every forge cue corresponds to a real C17 bloom cue (same mineral); cracked ⟺ the
    bloom is red-short. No bloom ⇒ no forge cue ('the world never lies')."""
    sim, coords = forge_sim
    violations = 0
    n_forge = 0
    for coord in coords:
        cue = bf.forge_cue_for_chunk(sim, coord)
        bloom = ib.bloom_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_forge += 1
        if bloom is None or bloom.iron_mineral != cue.iron_mineral:
            violations += 1
        if cue.cracked != bool(bloom.red_short):
            violations += 1
        if cue.melted is not False:
            violations += 1
        # conservation per kg ore (per-kg figures are each rounded to 6 dp, so the
        # summed rounding error can reach ~2e-6 — the SSOT itself conserves exactly).
        total = (cue.wrought_iron_per_kg_ore + cue.scale_loss_per_kg_ore
                 + cue.crack_loss_per_kg_ore)
        if abs(total - cue.bloom_iron_per_kg_ore) > 1e-5:
            violations += 1
    assert violations == 0, f"{violations} world-lies among real forge cues"
    assert n_forge > 0


def test_forge_preview_is_non_mutating(forge_sim):
    """forge_preview on a real site reports a billet AND mutates nothing (geology
    untouched — D10 frozen, unlike C17 bloom_at)."""
    sim, coords = forge_sim
    coord = next((c for c in coords
                  if bf.forge_cue_for_chunk(sim, c) is not None), None)
    assert coord is not None
    cue = bf.forge_cue_for_chunk(sim, coord)
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    g = geo.chunk_geology(sim, coord)
    before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    prev = bf.forge_preview(sim, float(sim.agents.pos[0, 0]),
                            float(sim.agents.pos[0, 1]))
    after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    assert after == before                              # non-mutating
    assert prev["forgeable"] is True
    assert prev["wrought_iron_per_kg_ore"] == cue.wrought_iron_per_kg_ore


def test_best_site_prefers_sound_iron(forge_sim):
    """best_forge_site_near returns the most wrought iron; require_sound rejects red-short."""
    sim, coords = forge_sim
    coord = next((c for c in coords
                  if bf.forge_cue_for_chunk(sim, c) is not None), None)
    assert coord is not None
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    best = bf.best_forge_site_near(sim, 0, perception_radius_m=6 * CHUNK_SIDE_M)
    assert best is not None and best.wrought_iron_per_kg_ore > 0.0
    sound = bf.best_forge_site_near(sim, 0, perception_radius_m=6 * CHUNK_SIDE_M,
                                    require_sound=True)
    assert sound is None or (sound.is_wrought is True and sound.cracked is False)


def test_determinism_same_seed():
    """Two builds at the same seed give bit-identical oracle cues."""
    sim_a, coords_a = _booted_sim("det_a")
    sim_b, coords_b = _booted_sim("det_b")
    assert coords_a == coords_b
    mismatches = 0
    for coord in coords_a:
        a = bf.forge_cue_for_chunk(sim_a, coord)
        b = bf.forge_cue_for_chunk(sim_b, coord)
        ka = None if a is None else (a.iron_mineral, round(a.wrought_iron_per_kg_ore, 6),
                                     a.is_wrought, a.cracked, round(a.soundness, 6))
        kb = None if b is None else (b.iron_mineral, round(b.wrought_iron_per_kg_ore, 6),
                                     b.is_wrought, b.cracked, round(b.soundness, 6))
        if ka != kb:
            mismatches += 1
    assert mismatches == 0


def test_idempotent_zero_tick_cost(forge_sim):
    """Install is idempotent and adds NO per-tick hook (zero tick cost — it is an oracle)."""
    sim, _ = forge_sim
    step_before = sim.step
    c1 = bf.install_bloom_forging(sim)
    c2 = bf.install_bloom_forging(sim)
    assert c1 is c2
    assert sim.step is step_before              # no sim.step wrapping
