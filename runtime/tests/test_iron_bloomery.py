"""Invariants — Substrate capability : le bas-fourneau du fer (Cap. C17).

La 5ᵉ TRANSFORMATION et la 2ᵉ MÉTALLURGIQUE — le seuil de l'âge du fer. C12
``forced_draught`` a exposé ``reaches_iron_bloomery_temp`` (~1200 °C, paroi réfractaire)
comme un POTENTIEL, en différant la réduction effective. C17 la RÉALISE : ``bloom_at``
**consomme** le minerai (mutation via ``geo.mine_at``, la 2ᵉ de l'arc après C13) et rend
une **loupe de fer** solide + scorie de fayalite. Couvre :

- **Composition C12×C1** : cue émis ssi C12 atteint le régime bas-fourneau (≥1200 °C) ET
  C1 surface un gossan **ferreux** (hématite/magnétite/pyrite). Cool four / gossan plomb-
  zinc ⇒ pas de cue.
- **MENSONGE #8** (chapeau de fer polyminéral) : le **même** tell gossan coiffe
  l'**oxyde** (hématite/magnétite → fer sain), le **sulfure** (pyrite → fer *red-short*,
  griller d'abord) et le **non-fer** (galène → plomb, sphalérite → zinc : aucun fer).
- **MENSONGE PHYSIQUE** : le fer ne FOND jamais (1538 °C hors d'atteinte) — réduction
  **solide** : ``melts`` toujours False, ``is_solid_bloom`` / ``requires_forging``
  toujours True, ``furnace_reaches_iron_melt`` toujours False.
- **Seuil = SSOT C12** : ``iron_bloom_yield`` gate sur ``fd.IRON_BLOOMERY_TEMP_C``.
- **« Le monde ne ment jamais »** : cue ⇒ C12 reaches_iron + minéral == C1 + fer rendu ≤
  fer contenu (catalogue) ; sulfure cru → 0, grillé → >0 ; non-fer → pas de cue.
- ``bloom_at`` **consomme** le minerai & rend le fer promis ; ``bloom_preview`` non mutant.
- **N'introduit AUCUN nouveau tell** (garde-fou D8 par composition, 11ᵉ fois) : pas de
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
import engine.forced_draught as fd                                  # noqa: E402
import engine.surface_mineralization as sm                          # noqa: E402
import engine.iron_bloomery as ib                                   # noqa: E402

SEED = 0x42         # grassland continent — refractory furnaces + iron gossans (oxide + pyrite)
GRID = 12


# ---------------------------------------------------------------------------
# Fakes for pure-derivation tests (no world — fast, trivially unit-testable)
# ---------------------------------------------------------------------------

def _forced(peak=1280.0, reaches_iron=True, refractory=True, conf=0.9, biome=6):
    return SimpleNamespace(forced_peak_c=peak, reaches_iron_bloomery_temp=reaches_iron,
                           wall_refractory=refractory, confidence=conf, biome=biome)


def _gossan(mineral="hematite", dig=1.0):
    return SimpleNamespace(group="gossan", mineral=mineral, dig_depth_m=dig)


# ---------------------------------------------------------------------------
# Pure SSOT invariants — iron_bloom_yield (synthetic ore + temperature)
# ---------------------------------------------------------------------------

def test_oxide_reduces_directly_to_sound_bloom():
    """Hematite (oxide) reduces directly to a SOUND solid bloom — no roast, not brittle."""
    y = ib.iron_bloom_yield("hematite", 10.0, 1280.0)
    assert y.ore_class == "oxide_iron"
    assert y.requires_roasting is False and y.red_short is False
    assert y.bloom_iron_kg > 0.0 and y.melts is False
    assert 0.0 < y.reduction_efficiency <= ib.OXIDE_RECOVERY_CEIL


def test_magnetite_is_oxide_iron():
    """Magnetite (Fe3O4, oxide) is also a directly-reducible sound iron ore."""
    y = ib.iron_bloom_yield("magnetite", 10.0, 1280.0)
    assert y.ore_class == "oxide_iron" and y.red_short is False and y.bloom_iron_kg > 0.0


def test_sulfide_pyrite_needs_roasting_and_is_red_short():
    """Pyrite (FeS2, sulfide): raw → 0 iron; roasted → iron, but ALWAYS red-short."""
    raw = ib.iron_bloom_yield("pyrite", 10.0, 1280.0, roasted=False)
    roasted = ib.iron_bloom_yield("pyrite", 10.0, 1280.0, roasted=True)
    assert raw.ore_class == "sulfide_iron" and raw.requires_roasting is True
    assert raw.bloom_iron_kg == 0.0          # un-roasted sulfide locks Fe in slag
    assert roasted.bloom_iron_kg > 0.0       # roasting frees some iron…
    assert roasted.red_short is True         # …but the bloom stays brittle (the lie)
    assert raw.red_short is True


def test_non_iron_gossan_yields_no_iron():
    """The deepest lie #8: a gossan over galena (lead) or sphalerite (zinc) — no iron."""
    for ore in ("galena", "sphalerite"):
        y = ib.iron_bloom_yield(ore, 10.0, 1280.0, roasted=True)
        assert y.ore_class == "non_iron"
        assert y.bloom_iron_kg == 0.0 and y.contained_fe_fraction == 0.0


def test_too_cold_no_bloom():
    """Below the bloomery threshold (1200 °C) nothing reduces — no bloom."""
    y = ib.iron_bloom_yield("hematite", 10.0, 1100.0)
    assert y.hot_enough is False and y.bloom_iron_kg == 0.0


def test_iron_never_melts_solid_state_reduction():
    """The deep physics lie: even a maximal bloomery never melts iron (1538 °C). The
    yield is ALWAYS a solid bloom, regardless of how hot the furnace gets."""
    for peak in (1200.0, 1300.0, 1400.0, 1537.0):
        y = ib.iron_bloom_yield("hematite", 10.0, peak)
        assert y.melts is False


def test_superheat_monotone_and_capped():
    """Reduction efficiency rises with superheat above 1200 °C and saturates < ceiling."""
    lo = ib.iron_bloom_yield("hematite", 10.0, 1210.0).reduction_efficiency
    hi = ib.iron_bloom_yield("hematite", 10.0, 1400.0).reduction_efficiency
    assert lo < hi <= ib.OXIDE_RECOVERY_CEIL


def test_bloom_never_exceeds_contained_iron():
    """A bloom can never contain more iron than the ore held (catalogue Fe fraction)."""
    contained = MINERAL_BY_NAME["hematite"].yields_per_kg_ore["Fe"] * 10.0
    y = ib.iron_bloom_yield("hematite", 10.0, 1400.0)
    assert 0.0 <= y.bloom_iron_kg <= contained + 1e-9


def test_unknown_mineral_is_non_iron():
    """An unknown / None ore name yields no iron (defensive)."""
    assert ib.iron_bloom_yield(None, 5.0, 1300.0).ore_class == "non_iron"
    assert ib.iron_bloom_yield("not_a_mineral", 5.0, 1300.0).bloom_iron_kg == 0.0


def test_threshold_reuses_c12_ssot():
    """The bloomery temperature gate is C12's SSOT (no re-declared threshold)."""
    just_under = ib.iron_bloom_yield("hematite", 10.0, fd.IRON_BLOOMERY_TEMP_C - 1.0)
    just_over = ib.iron_bloom_yield("hematite", 10.0, fd.IRON_BLOOMERY_TEMP_C)
    assert just_under.hot_enough is False and just_over.hot_enough is True


# ---------------------------------------------------------------------------
# Pure cue derivation — _cue_from_inputs (synthetic forced + gossan cues)
# ---------------------------------------------------------------------------

def test_cue_requires_bloomery_temp():
    """A furnace that does not reach the bloomery regime → no cue (1+1>2 gate)."""
    assert ib._cue_from_inputs((0, 0, 0), _forced(reaches_iron=False), _gossan()) is None


def test_cue_requires_iron_gossan():
    """No gossan, a non-gossan group, or a gossan over lead/zinc → no cue (no iron)."""
    assert ib._cue_from_inputs((0, 0, 0), _forced(), None) is None
    assert ib._cue_from_inputs((0, 0, 0), _forced(),
                               SimpleNamespace(group="copper", mineral="native_copper",
                                               dig_depth_m=1.0)) is None
    assert ib._cue_from_inputs((0, 0, 0), _forced(), _gossan("galena")) is None
    assert ib._cue_from_inputs((0, 0, 0), _forced(), _gossan("sphalerite")) is None


def test_cue_oxide_reducible_now_solid_bloom():
    """A hot refractory furnace + hematite gossan → a directly-reducible cue; the bloom
    is solid (never melts), must be forged, and the furnace never reaches iron's melt."""
    cue = ib._cue_from_inputs((1, 2, 0), _forced(peak=1280.0), _gossan("hematite", dig=1.4))
    assert cue is not None
    assert cue.ore_class == "oxide_iron" and cue.reducible_now is True
    assert cue.needs_roasting_first is False and cue.red_short is False
    assert cue.is_solid_bloom is True and cue.requires_forging is True
    assert cue.furnace_reaches_iron_melt is False
    assert cue.dig_depth_m == 1.4 and cue.bloom_iron_per_kg_ore > 0.0


def test_cue_pyrite_needs_roasting_first():
    """A pyrite gossan cue: not reducible now (raw → 0), needs roasting first, red-short;
    the roasted potential is positive."""
    cue = ib._cue_from_inputs((0, 0, 0), _forced(peak=1280.0), _gossan("pyrite"))
    assert cue is not None
    assert cue.ore_class == "sulfide_iron" and cue.reducible_now is False
    assert cue.needs_roasting_first is True and cue.red_short is True
    assert cue.bloom_iron_per_kg_ore == 0.0
    assert cue.bloom_iron_per_kg_ore_roasted > 0.0


# ---------------------------------------------------------------------------
# D8 guardrail — introduces no new tell (composition only, 11th time)
# ---------------------------------------------------------------------------

def test_introduces_no_new_tell():
    """C17 surfaces NO new tell: no own ``_PROFILE``, composes C12 (fd) + C1 (sm). So
    PY_TO_RUST stays 15 and the *_outcrop glob ignores it (it is a transformation)."""
    assert not hasattr(ib, "_PROFILE"), "iron_bloomery must not declare a tell table"
    assert ib.fd is fd and ib.sm is sm                  # composes C12 + C1 (not duplicates)
    assert not Path(ib.__file__).name.endswith("_outcrop.py")


def test_py_to_rust_unchanged_at_15():
    """The cross-language contract map is untouched by C17 (D8 by composition)."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import test_geology_cross_language_contract as contract
    assert len(contract.PY_TO_RUST) == 15


# ---------------------------------------------------------------------------
# Real Genesis world invariants (seed 0x42 — refractory furnaces + iron gossans)
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
    ib.install_iron_bloomery(sim)
    coords = []
    for cx in range(grid):
        for cy in range(grid):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


@pytest.fixture(scope="module")
def iron_sim():
    return _booted_sim("test_iron_bloomery")


def test_real_world_emits_emergent_bloomery_sites(iron_sim):
    """A genuine iron-rich continent produces emergent bloomery sites — BOTH the oxide
    iron prize AND the pyrite (sulfide, red-short) lie — with no injection."""
    sim, _coords = iron_sim
    s = ib.bloom_summary(sim)
    assert s["n_bloomery_sites"] > 0
    assert s["by_ore_class"].get("oxide_iron", 0) > 0
    assert s["by_ore_class"].get("sulfide_iron", 0) > 0
    assert s["best_bloom_iron_per_kg_ore"] > 0.0


def test_world_never_lies_real(iron_sim):
    """Every real cue: C12 reaches the bloomery regime + the mineral matches C1's gossan
    + iron won ≤ iron contained + the bloom is solid (never melts, never reaches iron melt)."""
    sim, coords = iron_sim
    violations = 0
    n_oxide = n_sulfide = 0
    for coord in coords:
        cue = ib.bloom_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        forced = fd.forced_cue_for_chunk(sim, coord)
        if forced is None or not forced.reaches_iron_bloomery_temp:
            violations += 1
        c1 = sm.surface_cue_for_chunk(sim, coord)
        if c1 is None or c1.group != "gossan" or c1.mineral != cue.iron_mineral:
            violations += 1
        contained = MINERAL_BY_NAME[cue.iron_mineral].yields_per_kg_ore.get("Fe", 0.0)
        if not (0.0 <= cue.bloom_iron_per_kg_ore <= contained + 1e-9):
            violations += 1
        if not (0.0 <= cue.bloom_iron_per_kg_ore_roasted <= contained + 1e-9):
            violations += 1
        if not cue.is_solid_bloom or cue.furnace_reaches_iron_melt:
            violations += 1
        if cue.ore_class == "sulfide_iron":
            n_sulfide += 1
            if not (cue.needs_roasting_first and cue.red_short
                    and cue.bloom_iron_per_kg_ore == 0.0
                    and cue.bloom_iron_per_kg_ore_roasted > 0.0):
                violations += 1
        else:
            n_oxide += 1
            if not (cue.reducible_now and not cue.red_short
                    and cue.bloom_iron_per_kg_ore > 0.0):
                violations += 1
    assert violations == 0, f"{violations} world-lies among real cues"
    assert n_oxide > 0 and n_sulfide > 0


def test_bloom_at_consumes_and_matches_oracle(iron_sim):
    """The réduction effective: bloom_at on an oxide site consumes ore (mutation) and
    yields exactly the iron the oracle promised; bloom_preview is non-mutating."""
    sim, coords = iron_sim
    coord = next((c for c in coords
                  if (cu := ib.bloom_cue_for_chunk(sim, c)) is not None
                  and cu.ore_class == "oxide_iron"), None)
    assert coord is not None
    cue = ib.bloom_cue_for_chunk(sim, coord)
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    g = geo.chunk_geology(sim, coord)
    before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    prev = ib.bloom_preview(sim, float(sim.agents.pos[0, 0]), float(sim.agents.pos[0, 1]))
    after_preview = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    assert prev["reducible"] is True and after_preview == before     # preview non-mutating
    assert prev["is_solid_bloom"] is True and prev["requires_forging"] is True
    extracted_before = sum(L.extracted_kg for L in g.layers)
    res = ib.bloom_at(sim, 0, charge_kg=5.0)
    extracted_after = sum(L.extracted_kg for L in g.layers)
    assert res is not None and extracted_after > extracted_before
    assert res.bloom_iron_kg > 0.0 and res.is_solid_bloom is True
    expected = cue.bloom_iron_per_kg_ore * res.ore_consumed_kg
    assert abs(res.bloom_iron_kg - expected) <= 1e-4


def test_pyrite_raw_is_only_slag_roasted_yields_brittle(iron_sim):
    """The lie #8 on the real world: a pyrite gossan reduced raw → only slag (0 iron);
    roasted → some iron, but always red-short (brittle)."""
    sim, coords = iron_sim
    coord = next((c for c in coords
                  if (cu := ib.bloom_cue_for_chunk(sim, c)) is not None
                  and cu.ore_class == "sulfide_iron"), None)
    assert coord is not None
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    raw = ib.bloom_at(sim, 0, charge_kg=5.0, roasted=False)
    roasted = ib.bloom_at(sim, 0, charge_kg=5.0, roasted=True)
    assert raw is not None and raw.required_roasting is True
    assert raw.bloom_iron_kg == 0.0 and raw.slag_kg > 0.0 and raw.red_short is True
    assert roasted is not None and roasted.bloom_iron_kg > 0.0 and roasted.red_short is True


def test_best_site_prefers_sound_oxide(iron_sim):
    """best_bloomery_site_near with require_sound skips red-short pyrite; require_direct
    keeps only directly-reducible (oxide) sites."""
    sim, coords = iron_sim
    coord = next((c for c in coords
                  if (cu := ib.bloom_cue_for_chunk(sim, c)) is not None
                  and cu.ore_class == "oxide_iron"), None)
    assert coord is not None
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    sound = ib.best_bloomery_site_near(sim, 0, perception_radius_m=3 * CHUNK_SIDE_M,
                                       require_sound=True)
    direct = ib.best_bloomery_site_near(sim, 0, perception_radius_m=3 * CHUNK_SIDE_M,
                                        require_direct=True)
    assert sound is not None and sound.red_short is False
    assert direct is not None and direct.reducible_now is True


def test_determinism_same_seed():
    """Two builds at the same seed give bit-identical oracle cues."""
    sim_a, coords_a = _booted_sim("det_a")
    sim_b, coords_b = _booted_sim("det_b")
    assert coords_a == coords_b
    mismatches = 0
    for coord in coords_a:
        a = ib.bloom_cue_for_chunk(sim_a, coord)
        b = ib.bloom_cue_for_chunk(sim_b, coord)
        ka = None if a is None else (a.iron_mineral, a.ore_class,
                                     round(a.bloom_iron_per_kg_ore, 6),
                                     a.reducible_now, a.needs_roasting_first)
        kb = None if b is None else (b.iron_mineral, b.ore_class,
                                     round(b.bloom_iron_per_kg_ore, 6),
                                     b.reducible_now, b.needs_roasting_first)
        if ka != kb:
            mismatches += 1
    assert mismatches == 0


def test_idempotent_zero_tick_cost(iron_sim):
    """Install is idempotent and adds NO per-tick hook (zero tick cost — it is an oracle)."""
    sim, _ = iron_sim
    step_before = sim.step
    c1 = ib.install_iron_bloomery(sim)
    c2 = ib.install_iron_bloomery(sim)
    assert c1 is c2
    assert sim.step is step_before              # no sim.step wrapping
