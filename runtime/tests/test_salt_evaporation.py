"""Invariants — Substrate capability : sel d'évaporation solaire (Cap. C15).

Le 8ᵉ opérateur ORTHOGONAL (**sécher au soleil**), réponse à la reco ``R-J9-1``
de l'audit J+9 (« choisir le 8ᵉ opérateur avant de revenir au feu »). Couvre :
- **Orthogonalité** : la transformation est **solaire** (passive), pas
  *fire-based* — le module n'importe AUCUN module de feu (C7/C11/C12).
- **Porte de saumure** : eau douce/potable (``salinity < MIN_BRINE_PPT``) ⇒
  muet (rien à cristalliser) ; eau saline ⇒ indice.
- **Inversion de C3** : ``MIN_BRINE_PPT`` est *exactement* le plafond de
  potabilité de C3 (``POTABLE_MAX_PPT``) — « trop salée pour boire » = « assez
  salée pour récolter ».
- **MENSONGE #6** : une saumure identique en climat **humide** → aucune croûte
  (``harvestable=False``) ; la même en climat **aride** → sel abondant.
- **Aridité = SSOT Köppen** : ``_aridity`` réutilise ``koeppen_grid._p_thresh``
  (le critère « B aride » du moteur) — les deux ne divergent jamais.
- ``salt_yield_kg_m2 == net_evap_mm × 1e-3 × salinity_ppt`` (physique explicite).
- **« Le monde ne ment jamais »** : tout indice ⇒ eau réellement saline (C3) +
  rendement = formule + harvestable = seuil — sur entrées synthétiques ET monde
  Genesis réel (côte aride, seed ``0x5A17``).
- ``harvest_salt_at`` est un aperçu **non mutant** (eau inchangée — D10 gelé).
- ``best_saltpan_near`` saute la lagune salée stérile.
- Déterminisme même-seed (bit-identique) + installation idempotente, coût tick nul.
- **N'introduit AUCUN nouveau tell** (garde-fou D8 par composition, 9ᵉ fois) :
  pas de ``_PROFILE``, ``PY_TO_RUST`` reste 15, hors glob ``*_outcrop.py``.
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
from engine import koeppen_grid as kp                               # noqa: E402
from engine import water_potability as wp                           # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.salt_evaporation as se                                # noqa: E402

SEED = 0x5A17        # "SALT" — hottest, most arid saline coast on this map
_OCEAN = 0


# ---------------------------------------------------------------------------
# Helpers — anchor the sim at the most evaporative saline-water cell (no
# injection: the world genuinely has this arid coast; we point the camera at it).
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
    return (float((ix + 0.5) * cell_km), float((iy + 0.5) * cell_km))


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
    se.install_salt_evaporation(sim)
    coords = []
    for cx in range(grid):
        for cy in range(grid):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


@pytest.fixture(scope="module")
def arid_sim():
    return _booted_arid_sim("test_salt_evaporation")


# ---------------------------------------------------------------------------
# Pure-derivation invariants (synthetic salinity + climate — fast, no world)
# ---------------------------------------------------------------------------

def test_brine_gating_fresh_is_silent():
    """Fresh / potable water (< MIN_BRINE_PPT) → no salt to crystallise (None)."""
    assert se._saltpan_from_inputs((0, 0, 0), 0.4, "fresh", 100.0,
                                   temp_c=28.0, precip_mm=40.0, biome=7) is None
    cue = se._saltpan_from_inputs((0, 0, 0), 35.0, "sea", 100.0,
                                  temp_c=28.0, precip_mm=40.0, biome=_OCEAN)
    assert cue is not None


def test_min_brine_is_c3_potability_ceiling():
    """The salt gate is exactly C3's potability ceiling — one shared boundary."""
    assert se.MIN_BRINE_PPT == wp.POTABLE_MAX_PPT


def test_mensonge_6_humid_vs_arid_same_brine():
    """MENSONGE #6: identical 35 ppt brine — arid crusts to salt, humid does not."""
    arid = se._saltpan_from_inputs((0, 0, 0), 35.0, "coastal", 100.0,
                                   temp_c=28.0, precip_mm=40.0, biome=7)
    humid = se._saltpan_from_inputs((0, 0, 0), 35.0, "coastal", 100.0,
                                    temp_c=28.0, precip_mm=2000.0, biome=11)
    assert arid is not None and humid is not None
    assert arid.salinity_ppt == humid.salinity_ppt == 35.0   # same saltiness…
    assert arid.harvestable is True and arid.salt_yield_kg_m2 > se.MIN_HARVEST_KG_M2
    assert humid.harvestable is False and humid.salt_yield_kg_m2 == 0.0
    assert humid.pan_class == se.SaltPanClass.SALINE_LAGOON   # salty, no crust


def test_salt_yield_is_netevap_times_salinity():
    """salt_yield == net_evap_mm × 1e-3 × salinity_ppt (no hidden term)."""
    cue = se._saltpan_from_inputs((0, 0, 0), 35.0, "sea", 100.0,
                                  temp_c=25.0, precip_mm=100.0, biome=_OCEAN)
    assert cue is not None
    expected = cue.net_evap_mm * 1e-3 * cue.salinity_ppt
    assert abs(cue.salt_yield_kg_m2 - round(expected, 6)) <= 1e-6


def test_aridity_uses_koeppen_ssot():
    """_aridity reuses the Köppen dryness threshold verbatim (single source)."""
    for t in (-5.0, 0.0, 12.0, 25.0, 30.0):
        p_th, _net, _surf = se._aridity(t, 0.0)
        assert p_th == float(kp._p_thresh(t))


def test_aridity_zones_monotone():
    """Drier climate → higher zone tier (humid → semiarid → arid → hyperarid)."""
    assert se._aridity_zone(0.0) == "humid"
    assert se._aridity_zone(0.1) == "semiarid"
    assert se._aridity_zone(0.5) == "arid"
    assert se._aridity_zone(0.9) == "hyperarid"


def test_cold_climate_no_solar_salt():
    """A very cold saline cell yields no solar salt (that domain is frost, C14)."""
    cue = se._saltpan_from_inputs((0, 0, 0), 35.0, "sea", 100.0,
                                  temp_c=-20.0, precip_mm=50.0, biome=1)
    assert cue is not None
    assert cue.aridity_surplus == 0.0 and cue.harvestable is False


def test_brine_spring_is_eligible():
    """An inland evaporitic brine spring (C3 source) can crust salt when arid."""
    cue = se._saltpan_from_inputs((0, 0, 0), 120.0, "brine_spring", 50.0,
                                  temp_c=26.0, precip_mm=60.0, biome=7)
    assert cue is not None and cue.harvestable is True
    assert cue.source == "brine_spring"


# ---------------------------------------------------------------------------
# Orthogonality — solar, NOT fire-based (the point of R-J9-1)
# ---------------------------------------------------------------------------

def test_orthogonal_solar_not_fire():
    """The capability is non-thermal: its source imports no fire/kiln/forge
    module (C7/C11/C12). The heat is the sun's, not a hearth's."""
    src = Path(se.__file__).read_text(encoding="utf-8")
    for fire_mod in ("fire_ignition", "kiln_draft", "forced_draught",
                     "ceramic_firing", "lime_burning", "metallurgy"):
        assert f"import {fire_mod}" not in src and f"engine.{fire_mod}" not in src


# ---------------------------------------------------------------------------
# Real Genesis world invariants
# ---------------------------------------------------------------------------

def test_real_world_emits_emergent_salt_pans(arid_sim):
    """A genuine arid saline coast produces harvestable solar salt pans."""
    sim, _coords = arid_sim
    s = se.salt_evaporation_summary(sim)
    assert s["n_chunks_with_brine"] > 0
    assert s["n_harvestable"] > 0
    assert s["best_salt_yield_kg_m2"] >= se.MIN_HARVEST_KG_M2
    assert set(s["by_zone"]) & {"hyperarid", "arid", "semiarid"}


def test_world_never_lies_real(arid_sim):
    """Every real cue: water genuinely saline (C3) + yield == formula +
    harvestable == threshold + a real C3 source."""
    sim, coords = arid_sim
    violations = 0
    for coord in coords:
        cue = se.saltpan_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        if cue.salinity_ppt < se.MIN_BRINE_PPT:
            violations += 1
        if cue.source not in ("sea", "coastal", "brine_spring"):
            violations += 1
        expected = max(0.0, cue.p_thresh_mm - cue.precip_mm) * 1e-3 * cue.salinity_ppt
        if abs(cue.salt_yield_kg_m2 - round(expected, 6)) > 1e-5:
            violations += 1
        if cue.harvestable != (cue.salt_yield_kg_m2 >= se.MIN_HARVEST_KG_M2):
            violations += 1
    assert violations == 0, f"{violations} world-lies among real cues"


def test_cue_composes_c3(arid_sim):
    """Every salt cue's salinity/source matches the C3 water cue it composes."""
    sim, coords = arid_sim
    checked = 0
    for coord in coords:
        cue = se.saltpan_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        water = wp.water_cue_for_chunk(sim, coord)
        assert water is not None
        assert cue.salinity_ppt == water.salinity_ppt
        assert cue.source == water.source
        checked += 1
    assert checked > 0


def test_harvest_at_is_non_mutating(arid_sim):
    """harvest_salt_at is a preview: it consumes no water (D10 stays frozen)."""
    sim, coords = arid_sim
    coord = next((c for c in coords
                  if se.saltpan_cue_for_chunk(sim, c) is not None), None)
    assert coord is not None
    chunk = sim.streamer.cache.get(coord)
    w_before = float(np.asarray(chunk.water).sum())
    x = (coord[0] + 0.5) * CHUNK_SIDE_M
    y = (coord[1] + 0.5) * CHUNK_SIDE_M
    out = se.harvest_salt_at(sim, x, y)
    w_after = float(np.asarray(chunk.water).sum())
    assert w_after == w_before                    # nothing consumed
    cue = se.saltpan_cue_for_chunk(sim, coord)
    assert out["material"] == "halite"
    assert out["harvestable"] == cue.harvestable
    assert out["salt_yield_kg_m2"] == cue.salt_yield_kg_m2


def test_best_saltpan_skips_barren_lagoon(arid_sim):
    """best_saltpan_near returns only a harvestable pan (never a barren lagoon)."""
    sim, coords = arid_sim
    coord = next((c for c in coords
                  if (cu := se.saltpan_cue_for_chunk(sim, c)) is not None
                  and cu.harvestable), None)
    assert coord is not None
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    best = se.best_saltpan_near(sim, 0, perception_radius_m=2 * CHUNK_SIDE_M)
    assert best is not None and best.harvestable is True


def test_determinism_same_seed():
    """Two arid-anchored builds at the same seed give bit-identical cues."""
    sim_a, coords_a = _booted_arid_sim("det_a")
    sim_b, coords_b = _booted_arid_sim("det_b")
    assert coords_a == coords_b
    mismatches = 0
    for coord in coords_a:
        a = se.saltpan_cue_for_chunk(sim_a, coord)
        b = se.saltpan_cue_for_chunk(sim_b, coord)
        ka = None if a is None else (a.salinity_ppt, a.salt_yield_kg_m2,
                                     a.harvestable, a.zone)
        kb = None if b is None else (b.salinity_ppt, b.salt_yield_kg_m2,
                                     b.harvestable, b.zone)
        if ka != kb:
            mismatches += 1
    assert mismatches == 0


def test_idempotent_zero_tick_cost(arid_sim):
    """Install is idempotent and adds NO per-tick hook (zero tick cost)."""
    sim, _ = arid_sim
    step_before = sim.step
    c1 = se.install_salt_evaporation(sim)
    c2 = se.install_salt_evaporation(sim)
    assert c1 is c2
    assert sim.step is step_before              # no sim.step wrapping


# ---------------------------------------------------------------------------
# D8 guardrail — introduces no new tell (composition only, 9th time)
# ---------------------------------------------------------------------------

def test_introduces_no_new_tell():
    """C15 surfaces NO new tell: no own ``_PROFILE``, reuses C3. So PY_TO_RUST
    stays 15 and the *_outcrop glob ignores it."""
    assert not hasattr(se, "_PROFILE"), "salt_evaporation must not declare a tell table"
    assert se.wp is wp                                  # composes C3 (not duplicates)
    assert not Path(se.__file__).name.endswith("_outcrop.py")


def test_py_to_rust_unchanged_at_15():
    """The cross-language contract map is untouched by C15 (D8 by composition)."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import test_geology_cross_language_contract as contract
    assert len(contract.PY_TO_RUST) == 15
