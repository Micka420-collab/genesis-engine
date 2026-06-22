"""Invariants — Substrate capability : salaison / conservation par le sel (Cap. C16).

La 1ʳᵉ capacité qui **CONSOMME le produit de C15** (le sel), réponse à la reco
``R-J9r2-3 (a)`` de l'audit J+9 run #2 (« le sel ouvre la conservation »). Couvre :
- **Physique de l'activité de l'eau** : plus de sel → ``a_w`` plus bas (monotone),
  plancher à la saumure saturée NaCl (``SAT_BRINE_AW`` = 0,75) ; sous
  ``A_W_NO_GROWTH`` → conservation indéfinie (``SHELF_STABLE``).
- **Q10 température** : plus froid → conserve plus longtemps ; plus chaud → pourrit.
- **MENSONGE #7** : la chair **fraîche** (la plus appétissante) est la **plus
  périssable** ; la chair **salée** (terne) **tient des mois**. « Frais = meilleur »
  est le mensonge.
- **Compromis** : ``palatability`` et ``nutrient_retention`` **baissent** avec la dose.
- **Composition C15** : sans marais salant à portée → dose 0 → l'aliment reste
  **frais/périssable** (réciproque honnête) ; SALAR riche → saturation possible.
- **« Le monde ne ment jamais »** : ``shelf_life_days`` = formule(a_w, T) ; ``a_w``
  = formule(dose) — sur entrées synthétiques ET monde Genesis réel (côte aride).
- ``cure_food_at`` / ``achievable_cure_near`` **non mutants** (D10 gelé).
- Déterminisme même-seed (bit-identique) + installation idempotente, coût tick nul.
- **N'introduit AUCUN nouveau tell** (garde-fou D8 par composition, 10ᵉ fois) :
  pas de ``_PROFILE``, ``PY_TO_RUST`` reste 15, hors glob ``*_outcrop.py`` ; réutilise
  la lecture climat de C15 (SSOT).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

import numpy as np                                                  # noqa: E402
import pytest                                                       # noqa: E402

from engine.sim import Simulation, SimConfig                        # noqa: E402
from engine.world_genesis import GenesisParams, generate_world      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine import water_potability as wp                           # noqa: E402
from engine import salt_evaporation as se                           # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.food_curing as fc                                     # noqa: E402

SEED = 0x5A17        # "SALT" — hottest, most arid saline coast (shared with C15)


# ---------------------------------------------------------------------------
# Helpers — anchor at the most evaporative saline cell (shared with C15's test).
# ---------------------------------------------------------------------------

def _arid_saline_origin_km(world):
    R = world.params.resolution
    cell_km = world.params.map_size_km / R
    t = world.temp_c.astype(np.float64)
    p_th = np.where(t >= 0, 20.0 * t + 280.0, 20.0 * t)
    net = np.maximum(0.0, p_th - world.precip_mm)
    ar = np.where(p_th > 0, np.minimum(1.0, net / np.maximum(p_th, 1e-6)), 0.0)
    sea = world.elevation_m <= world.params.sea_level_m
    saline = sea | (world.elevation_m <= wp.COASTAL_MARGIN_M)
    score = np.where(saline, ar, -1.0)
    iy, ix = np.unravel_index(int(np.argmax(score)), score.shape)
    return float((ix + 0.5) * cell_km), float((iy + 0.5) * cell_km)


def _booted_arid_sim(name: str, seed: int = SEED, grid: int = 12):
    world = generate_world(GenesisParams(seed=seed, resolution=128, n_plates=8))
    origin = _arid_saline_origin_km(world)
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8),
                          sim_origin_macro_km=origin)
    geo.install_geology(sim)
    fc.install_food_curing(sim)
    coords = []
    for cx in range(grid):
        for cy in range(grid):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


@pytest.fixture(scope="module")
def arid_sim():
    return _booted_arid_sim("test_food_curing")


# ---------------------------------------------------------------------------
# Pure water-activity / shelf-life physics (synthetic — fast, no world)
# ---------------------------------------------------------------------------

def test_fresh_lean_meat_is_perishable():
    """Fresh lean meat at 25 °C: appealing, a_w≈0.99, spoils in a couple of days."""
    cue = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, 0.0, 25.0)
    assert cue.is_fresh is True
    assert cue.preservation_class == fc.PreservationClass.PERISHABLE
    assert cue.water_activity == pytest.approx(0.99, abs=1e-9)
    assert cue.shelf_life_days < 7.0


def test_saturation_cure_keeps_far_longer():
    """Saturation-salted lean meat at 25 °C keeps vastly longer than fresh."""
    fresh = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, 0.0, 25.0)
    sat_dose = fc._saturation_dose(fc._FOOD[fc.FoodKind.LEAN_MEAT].water_frac)
    cured = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, sat_dose, 25.0)
    assert cured.water_activity == pytest.approx(fc.SAT_BRINE_AW, abs=1e-9)
    assert cured.shelf_life_days > fresh.shelf_life_days * 20.0
    assert cured.preservation_class >= fc.PreservationClass.CURED


def test_water_activity_floor_at_saturated_brine():
    """No salt dose can push a_w below the saturated-NaCl limit (0.75)."""
    food = fc._FOOD[fc.FoodKind.LEAN_MEAT]
    a_w = fc._water_activity(food, 10.0)        # absurd over-dose
    assert a_w == pytest.approx(fc.SAT_BRINE_AW, abs=1e-9)


def test_water_activity_monotone_decreasing_in_dose():
    """More salt → lower (or equal) water activity, never higher."""
    food = fc._FOOD[fc.FoodKind.FISH]
    doses = [0.0, 0.05, 0.1, 0.2, 0.4, 0.8]
    aws = [fc._water_activity(food, d) for d in doses]
    assert all(aws[i + 1] <= aws[i] + 1e-12 for i in range(len(aws) - 1))


def test_shelf_life_monotone_in_dose():
    """More salt → longer (or equal) shelf life (the whole point of salting)."""
    shelves = [fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, d, 25.0).shelf_life_days
               for d in (0.0, 0.05, 0.1, 0.2, 0.3)]
    assert all(shelves[i + 1] >= shelves[i] - 1e-9 for i in range(len(shelves) - 1))


def test_colder_keeps_longer_warmer_spoils_faster():
    """Q10: at a fixed dose, lower temperature → longer shelf life (monotone)."""
    dose = 0.05
    shelves = [fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, dose, t).shelf_life_days
               for t in (35.0, 25.0, 15.0, 5.0, -5.0)]
    assert all(shelves[i + 1] >= shelves[i] for i in range(len(shelves) - 1))


def test_no_growth_below_threshold_is_shelf_stable():
    """If a_w ≤ A_W_NO_GROWTH the spoilage halts → capped shelf-stable."""
    food = fc._FOOD[fc.FoodKind.LEAN_MEAT]
    assert fc._aw_growth_factor(fc.A_W_NO_GROWTH) == 0.0
    assert fc._shelf_life_days(food, fc.A_W_NO_GROWTH - 0.01, 25.0) == fc.SHELF_MAX_DAYS


def test_lie_7_fresh_is_appealing_but_perishable():
    """MENSONGE #7: fresh = most appealing + most perishable ; cured = drab + keeps."""
    fresh, cured = fc.fresh_vs_cured(fc.FoodKind.LEAN_MEAT, 28.0)
    assert fresh.is_fresh and not cured.is_fresh
    assert fresh.shelf_life_days < cured.shelf_life_days       # fresh betrays you
    assert fresh.palatability > cured.palatability             # but it tastes best
    assert fresh.appeal_rgb == fc._FOOD[fc.FoodKind.LEAN_MEAT].fresh_rgb
    assert cured.appeal_rgb == fc._CURED_RGB                   # cured looks drab


def test_curing_cost_palatability_and_nutrient_drop():
    """The trade-off: heavier salting lowers palatability and nutrient retention."""
    light = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, 0.05, 25.0)
    heavy = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, 0.3, 25.0)
    assert heavy.palatability < light.palatability < 1.0
    assert heavy.nutrient_retention < light.nutrient_retention <= 1.0


def test_fish_and_offal_more_perishable_than_lean_meat():
    """Fresh fish/offal spoil faster than fresh lean meat (higher perishability)."""
    lean = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, 0.0, 25.0).shelf_life_days
    fish = fc._cure_from_inputs(fc.FoodKind.FISH, 0.0, 25.0).shelf_life_days
    offal = fc._cure_from_inputs(fc.FoodKind.OFFAL, 0.0, 25.0).shelf_life_days
    assert fish < lean and offal < lean


def test_saturation_dose_is_realistic():
    """Lean-meat saturation dose ≈ real dry-cure dose (~0.2–0.35 kg salt/kg)."""
    dose = fc._saturation_dose(fc._FOOD[fc.FoodKind.LEAN_MEAT].water_frac)
    assert 0.2 <= dose <= 0.35


def test_classify_thresholds():
    """Preservation-class boundaries are the documented day thresholds."""
    assert fc._classify(1.0) == fc.PreservationClass.PERISHABLE
    assert fc._classify(fc.SEMI_CURED_DAYS) == fc.PreservationClass.SEMI_CURED
    assert fc._classify(fc.CURED_DAYS) == fc.PreservationClass.CURED
    assert fc._classify(fc.SHELF_MAX_DAYS) == fc.PreservationClass.SHELF_STABLE


# ---------------------------------------------------------------------------
# C15 composition — salt availability bounds the cure (none → fresh)
# ---------------------------------------------------------------------------

def test_dose_from_yield_no_salt_is_zero():
    """A barren pan (yield 0) supplies no salt → dose 0 (food stays fresh)."""
    assert fc._dose_from_yield(0.0, fc._FOOD[fc.FoodKind.LEAN_MEAT]) == 0.0


def test_dose_from_yield_salar_saturates():
    """A copious salar (yield ≥ ABUNDANT_KG_M2) reaches full saturation dose."""
    food = fc._FOOD[fc.FoodKind.LEAN_MEAT]
    dose = fc._dose_from_yield(se.ABUNDANT_KG_M2, food)
    assert dose == pytest.approx(fc._saturation_dose(food.water_frac), abs=1e-9)


def test_dose_from_yield_monotone():
    """Richer pan → at least as much achievable salt dose."""
    food = fc._FOOD[fc.FoodKind.FISH]
    doses = [fc._dose_from_yield(y, food) for y in (0.0, 2.0, 5.0, 10.0, 20.0, 40.0)]
    assert all(doses[i + 1] >= doses[i] for i in range(len(doses) - 1))


# ---------------------------------------------------------------------------
# Real Genesis world — salt genuinely enables preservation
# ---------------------------------------------------------------------------

def test_real_world_salt_enables_cure(arid_sim):
    """On a real arid saline coast, harvested salt lifts food past PERISHABLE."""
    sim, _coords = arid_sim
    s = fc.food_curing_summary(sim, fc.FoodKind.LEAN_MEAT)
    assert s["n_harvestable_pans"] > 0
    assert s["n_pans_enabling_cure"] > 0
    assert s["best_shelf_life_days"] > fc.CURED_DAYS


def test_achievable_cure_uses_real_salt_when_on_a_pan(arid_sim):
    """An agent standing on a harvestable pan can really cure (records C15 salt)."""
    sim, coords = arid_sim
    hc = next((c for c in coords
               if (cu := se.saltpan_cue_for_chunk(sim, c)) is not None
               and cu.harvestable), None)
    assert hc is not None
    sim.agents.pos[0, 0] = (hc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (hc[1] + 0.5) * CHUNK_SIDE_M
    cue = fc.achievable_cure_near(sim, 0, fc.FoodKind.LEAN_MEAT,
                                  perception_radius_m=2 * CHUNK_SIDE_M)
    assert cue.salt_source in ("sea", "coastal", "brine_spring")
    assert cue.salt_yield_kg_m2 >= se.MIN_HARVEST_KG_M2
    assert cue.salt_dose_frac > 0.0
    assert cue.preservation_class != fc.PreservationClass.PERISHABLE


def test_achievable_cure_without_salt_stays_fresh(arid_sim):
    """No harvestable pan in range → food stays fresh/perishable (honest floor)."""
    sim, _coords = arid_sim
    sim.agents.pos[1, 0] = 1.0e6        # far outside any cached/saline region
    sim.agents.pos[1, 1] = 1.0e6
    cue = fc.achievable_cure_near(sim, 1, fc.FoodKind.LEAN_MEAT,
                                  perception_radius_m=CHUNK_SIDE_M)
    assert cue.is_fresh is True
    assert cue.salt_dose_frac == 0.0
    assert cue.salt_limited is True
    assert cue.salt_source is None
    # Salt added nothing: a_w stays the fresh value and shelf == the unsalted
    # shelf at this climate (cold alone may still preserve — that's C14's domain,
    # not salt's). The honest floor: no salt ⇒ no salt benefit.
    assert cue.water_activity == pytest.approx(0.99, abs=1e-9)
    fresh_here = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, 0.0, cue.temp_c)
    assert cue.shelf_life_days == fresh_here.shelf_life_days


def test_world_never_lies_real(arid_sim):
    """Every pan-enabled cure: a_w == formula(dose) and shelf == formula(a_w, T)."""
    sim, _coords = arid_sim
    food = fc._FOOD[fc.FoodKind.LEAN_MEAT]
    violations = 0
    checked = 0
    for coord in list(sim.streamer.cache.keys()):
        pan = se.saltpan_cue_for_chunk(sim, coord)
        if pan is None or not pan.harvestable:
            continue
        dose = fc._dose_from_yield(pan.salt_yield_kg_m2, food)
        cue = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, dose, pan.temp_c,
                                   salt_source=pan.source,
                                   salt_yield_kg_m2=pan.salt_yield_kg_m2)
        exp_aw = fc._water_activity(food, dose)
        exp_shelf = fc._shelf_life_days(food, exp_aw, pan.temp_c)
        if abs(cue.water_activity - round(exp_aw, 6)) > 1e-6:
            violations += 1
        if abs(cue.shelf_life_days - round(exp_shelf, 4)) > 1e-3:
            violations += 1
        checked += 1
    assert checked > 0
    assert violations == 0, f"{violations} world-lies among real cures"


def test_cure_is_non_mutating(arid_sim):
    """cure_food_at / achievable_cure_near consume no water (D10 stays frozen)."""
    sim, coords = arid_sim
    coord = next((c for c in coords
                  if se.saltpan_cue_for_chunk(sim, c) is not None), None)
    assert coord is not None
    chunk = sim.streamer.cache.get(coord)
    w_before = float(np.asarray(chunk.water).sum())
    x = (coord[0] + 0.5) * CHUNK_SIDE_M
    y = (coord[1] + 0.5) * CHUNK_SIDE_M
    fc.cure_food_at(sim, x, y, fc.FoodKind.LEAN_MEAT, 0.2)
    sim.agents.pos[0, 0] = x
    sim.agents.pos[0, 1] = y
    fc.achievable_cure_near(sim, 0, fc.FoodKind.FISH)
    assert float(np.asarray(chunk.water).sum()) == w_before


def test_determinism_same_seed():
    """Two arid-anchored builds give bit-identical curing summaries."""
    sim_a, _ = _booted_arid_sim("det_fc_a")
    sim_b, _ = _booted_arid_sim("det_fc_b")
    a = fc.food_curing_summary(sim_a, fc.FoodKind.LEAN_MEAT)
    b = fc.food_curing_summary(sim_b, fc.FoodKind.LEAN_MEAT)
    assert a == b


def test_idempotent_zero_tick_cost(arid_sim):
    """Install is idempotent and adds NO per-tick hook (zero tick cost)."""
    sim, _ = arid_sim
    step_before = sim.step
    c1 = fc.install_food_curing(sim)
    c2 = fc.install_food_curing(sim)
    assert c1 is c2
    assert sim.step is step_before


# ---------------------------------------------------------------------------
# Orthogonality + D8 guardrail
# ---------------------------------------------------------------------------

def test_orthogonal_not_fire():
    """Salaison is non-thermal: its source imports no fire/kiln/forge module."""
    src = Path(fc.__file__).read_text(encoding="utf-8")
    for fire_mod in ("fire_ignition", "kiln_draft", "forced_draught",
                     "ceramic_firing", "lime_burning", "metallurgy",
                     "copper_smelting"):
        assert f"import {fire_mod}" not in src and f"engine.{fire_mod}" not in src


def test_composes_c15_salt():
    """C16 consumes C15: it imports salt_evaporation and reuses its climate SSOT."""
    assert fc.se is se
    assert fc.se.ABUNDANT_KG_M2 == se.ABUNDANT_KG_M2


def test_introduces_no_new_tell():
    """C16 surfaces NO new tell: no own ``_PROFILE``, composes C15. PY_TO_RUST
    stays 15 and the *_outcrop glob ignores it."""
    assert not hasattr(fc, "_PROFILE"), "food_curing must not declare a tell table"
    assert not Path(fc.__file__).name.endswith("_outcrop.py")


def test_py_to_rust_unchanged_at_15():
    """The cross-language contract map is untouched by C16 (D8 by composition)."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import test_geology_cross_language_contract as contract
    assert len(contract.PY_TO_RUST) == 15
