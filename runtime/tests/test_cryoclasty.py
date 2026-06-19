"""Invariants — Substrate capability : pierre gélifractée (Cap. C14).

Le 7ᵉ opérateur ORTHOGONAL (ramasser), réponse au verrou P0 R-J8-1 de l'audit
J+8. Couvre :
- **Orthogonalité** : le gélifract gît en surface (``collect_depth_m == 0``),
  signature distincte du « casser un affleurement » de C2 (``> 0``).
- **Porte de gel** : pas de champ de gel actif (``fci < FROST_ACTIVE_MIN``) ⇒
  muet ; gel actif + roche taillable ⇒ indice.
- **MENSONGE #5** : un versant froid sur granite → arène (gruss) non taillable ;
  le même gel sur obsidienne/silex → éclats prêts à tailler.
- **Physique du tri** : ``frost_response`` monotone par fabric (conchoïdal ≥
  tabulaire ≥ mafique grenu fin > cristallin grenu / carbonate).
- ``clast_quality == base_quality(C2) × frost_response``.
- **Zones Wave 50** perçues : talus / alpin / permafrost / felsenmeer.
- **« Le monde ne ment jamais »** : tout indice ⇒ gel réellement actif + roche
  réelle taillable du catalogue — sur colonnes synthétiques ET monde Genesis réel.
- ``gather_at`` est un aperçu **non mutant** (géologie inchangée).
- ``best_frost_clast_near`` saute l'arène stérile.
- Déterminisme même-seed (bit-identique).
- Installation idempotente, coût tick nul (pas de hook sur sim.step).
- **N'introduit AUCUN nouveau tell** (garde-fou D8 par composition, 8ᵉ fois) :
  pas de ``_PROFILE`` propre, ``PY_TO_RUST`` inchangé, hors glob ``*_outcrop.py``.
- **Ferme R-J4-1** : la cap perçoit enfin l'observateur Wave 50 (``macro_frost``).
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
from engine.geology import StrataLayer                              # noqa: E402
from engine import frost_weathering as fw                           # noqa: E402
from engine import lithic_outcrop as lo                             # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.cryoclasty as cc                                      # noqa: E402

_TUNDRA = 2
SEED = 0xB0          # boreal/tundra continent — strongest periglacial cell on the map


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _layer(top, bottom, rock="granite", ore=None, density=2600.0):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=density, ore_mix=dict(ore or {}))


def _coldest_origin_km(world):
    """Deterministic argmax-FCI land cell → macro km. The sim window is anchored
    here so it explores a genuine periglacial region (no injection — the world
    really has this cold terrain; we just point the camera at it)."""
    R = world.params.resolution
    cell_km = world.params.map_size_km / R
    fci = fw.compute_frost_cracking_index(world.temp_c, world.precip_mm, world.biome)
    land = world.elevation_m > world.params.sea_level_m
    fci_land = np.where(land, fci, -1.0)
    iy, ix = np.unravel_index(int(np.argmax(fci_land)), fci_land.shape)
    return (float((ix + 0.5) * cell_km), float((iy + 0.5) * cell_km))


def _booted_cold_sim(name: str, seed: int = SEED, grid: int = 12):
    world = generate_world(GenesisParams(seed=seed, resolution=128, n_plates=8))
    origin = _coldest_origin_km(world)
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8),
                          sim_origin_macro_km=origin)
    geo.install_geology(sim)
    cc.install_cryoclasty(sim)
    coords = []
    for cx in range(grid):
        for cy in range(grid):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


@pytest.fixture(scope="module")
def cold_sim():
    return _booted_cold_sim("test_cryoclasty")


# ---------------------------------------------------------------------------
# Pure-derivation invariants (synthetic frost inputs — fast, no world)
# ---------------------------------------------------------------------------

def test_orthogonal_gather_surface_depth():
    """The gelifract lies ON the surface — collect_depth_m == 0 (the 7th verb)."""
    cue = cc._clast_from_inputs((0, 0, 0), [_layer(0, 4, "obsidian")], _TUNDRA,
                                fci=0.5, slope_deg=30, temp_c=-5.0,
                                elevation_m=1800)
    assert cue is not None
    assert cue.collect_depth_m == cc.SURFACE_COLLECT_DEPTH_M == 0.0


def test_frost_active_gating():
    """No active frost field → no clasts (truthful silence); active → cue."""
    silent = cc._clast_from_inputs((0, 0, 0), [_layer(0, 4, "obsidian")], 7,
                                   fci=0.05, slope_deg=10, temp_c=18.0,
                                   elevation_m=200)
    assert silent is None
    loud = cc._clast_from_inputs((0, 0, 0), [_layer(0, 4, "obsidian")], _TUNDRA,
                                 fci=cc.FROST_ACTIVE_MIN + 1e-3, slope_deg=10,
                                 temp_c=-3.0, elevation_m=300)
    assert loud is not None


def test_no_rock_no_cue():
    """Active frost but no profiled rock fabric shallow → silent (nothing to
    shatter into a clast). A dolomite-only column carries no C2 profile entry
    and no flaker ore, so there is no gelifract to perceive."""
    cue = cc._clast_from_inputs((0, 0, 0), [_layer(0, 4, "dolomite")], _TUNDRA,
                                fci=0.6, slope_deg=10, temp_c=-5.0,
                                elevation_m=400)
    assert "dolomite" not in lo._PROFILE          # precondition
    assert cue is None


def test_mensonge_granite_grus():
    """MENSONGE #5: same cold steep slope, granite → barren grus, obsidian → prime."""
    common = dict(biome=_TUNDRA, fci=0.6, slope_deg=30, temp_c=-5.0,
                  elevation_m=1800)
    granite = cc._clast_from_inputs((0, 0, 0), [_layer(0, 4, "granite")], **common)
    obsidian = cc._clast_from_inputs((0, 0, 0), [_layer(0, 4, "obsidian")], **common)
    assert granite is not None and obsidian is not None
    # the world shows a scree in BOTH cases (cue present)…
    assert granite.zone == obsidian.zone == "talus"
    # …but only obsidian yields a workable edge; granite is grus.
    assert obsidian.workable is True and obsidian.clast_quality > 0.9
    assert granite.workable is False and granite.clast_quality < cc.MIN_CLAST_QUALITY


def test_frost_response_monotone_by_fabric():
    """Fragmentation factor: conchoidal ≥ tabular ≥ fine mafic > coarse/soft."""
    r = cc._frost_response
    assert r("obsidian") == r("quartz") == 1.0
    assert r("slate") >= r("basalt") > r("granite")
    assert r("granite") == r("gneiss") and r("sandstone") <= r("granite")
    assert r("limestone") <= r("basalt")


def test_clast_quality_is_base_times_response():
    """clast_quality == C2 base_quality × frost_response (no hidden term)."""
    cue = cc._clast_from_inputs((0, 0, 0), [_layer(0, 4, "basalt")], _TUNDRA,
                                fci=0.5, slope_deg=10, temp_c=-4.0,
                                elevation_m=500)
    assert cue is not None
    expected = cue.base_quality * cue.frost_response
    assert abs(cue.clast_quality - round(expected, 6)) <= 1e-6


def test_zone_classification_mirrors_wave50():
    """The four zones reproduce the Wave 50 masks the agent now perceives."""
    base = dict(coord=(0, 0, 0), layers=[_layer(0, 4, "obsidian")], biome=_TUNDRA)
    talus = cc._clast_from_inputs(**base, fci=0.5, slope_deg=30, temp_c=2.0,
                                  elevation_m=800)
    alpine = cc._clast_from_inputs(**base, fci=0.3, slope_deg=5, temp_c=2.0,
                                   elevation_m=2000)
    perma = cc._clast_from_inputs(**base, fci=0.3, slope_deg=5, temp_c=-5.0,
                                  elevation_m=300)
    field = cc._clast_from_inputs(**base, fci=0.2, slope_deg=5, temp_c=1.0,
                                  elevation_m=300)
    assert talus.zone == "talus"
    assert alpine.zone == "alpine"
    assert perma.zone == "permafrost"
    assert field.zone == "frost_field"


def test_chert_bonus_makes_periglacial_flint_workable():
    """Quartz in a carbonate host upgrades to flint (C2 chert bonus) → a frost
    field of flint nodules is the archetypal periglacial raw material."""
    plain = cc._clast_from_inputs(
        (0, 0, 0), [_layer(0, 4, "sandstone", ore={"quartz": 0.02})], _TUNDRA,
        fci=0.5, slope_deg=10, temp_c=-4.0, elevation_m=400)
    in_chalk = cc._clast_from_inputs(
        (0, 0, 0),
        [_layer(0, 2, "sandstone", ore={"quartz": 0.02}), _layer(2, 6, "limestone")],
        _TUNDRA, fci=0.5, slope_deg=10, temp_c=-4.0, elevation_m=400)
    assert plain is not None and in_chalk is not None
    assert in_chalk.material == "quartz" and plain.material == "quartz"
    assert in_chalk.clast_quality > plain.clast_quality  # chert upgrade flows through


# ---------------------------------------------------------------------------
# Real Genesis world invariants
# ---------------------------------------------------------------------------

def test_real_world_emits_emergent_frost_clasts(cold_sim):
    """A genuine periglacial region produces frost-clast fields, incl. workable."""
    sim, coords = cold_sim
    s = cc.cryoclasty_summary(sim)
    assert s["n_chunks_with_clasts"] > 0
    assert s["n_workable"] > 0
    assert s["best_clast_quality"] >= cc.MIN_CLAST_QUALITY
    # the agent perceives at least one Wave 50 zone.
    assert set(s["by_zone"]) & {"talus", "alpine", "permafrost", "frost_field"}


def test_world_never_lies_real(cold_sim):
    """Every real cue: frost genuinely active + material is a real knappable rock
    + clast_quality is exactly base×response + surface (depth 0)."""
    sim, coords = cold_sim
    violations = 0
    for coord in coords:
        cue = cc.frost_clast_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        if cue.fci < cc.FROST_ACTIVE_MIN:
            violations += 1
        if cue.material not in lo._PROFILE:
            violations += 1
        if cue.collect_depth_m != 0.0:
            violations += 1
        if abs(cue.clast_quality - round(cue.base_quality * cue.frost_response, 6)) > 1e-6:
            violations += 1
        if cue.workable != (cue.clast_quality >= cc.MIN_CLAST_QUALITY):
            violations += 1
    assert violations == 0, f"{violations} world-lies among real cues"


def test_gather_at_is_non_mutating(cold_sim):
    """gather_at is a preview: it consumes no geology (unlike C13 smelt_at)."""
    sim, coords = cold_sim
    coord = next((c for c in coords
                  if cc.frost_clast_cue_for_chunk(sim, c) is not None), None)
    assert coord is not None
    g = geo.chunk_geology(sim, coord)
    before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    x = (coord[0] + 0.5) * CHUNK_SIDE_M
    y = (coord[1] + 0.5) * CHUNK_SIDE_M
    out = cc.gather_at(sim, x, y)
    after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    assert after == before                       # nothing consumed
    cue = cc.frost_clast_cue_for_chunk(sim, coord)
    assert out["material"] == cue.material and out["workable"] == cue.workable
    assert out["collect_depth_m"] == 0.0


def test_best_frost_clast_skips_grus(cold_sim):
    """best_frost_clast_near returns only a workable clast (never barren grus)."""
    sim, coords = cold_sim
    coord = next((c for c in coords
                  if (cu := cc.frost_clast_cue_for_chunk(sim, c)) is not None
                  and cu.workable), None)
    assert coord is not None
    sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
    best = cc.best_frost_clast_near(sim, 0, perception_radius_m=2 * CHUNK_SIDE_M)
    assert best is not None and best.workable is True


def test_determinism_same_seed():
    """Two cold-anchored builds at the same seed give bit-identical cues."""
    sim_a, coords_a = _booted_cold_sim("det_a")
    sim_b, coords_b = _booted_cold_sim("det_b")
    assert coords_a == coords_b
    mismatches = 0
    for coord in coords_a:
        a = cc.frost_clast_cue_for_chunk(sim_a, coord)
        b = cc.frost_clast_cue_for_chunk(sim_b, coord)
        ka = None if a is None else (a.material, a.clast_quality, a.workable,
                                     a.zone, round(a.fci, 6))
        kb = None if b is None else (b.material, b.clast_quality, b.workable,
                                     b.zone, round(b.fci, 6))
        if ka != kb:
            mismatches += 1
    assert mismatches == 0


def test_idempotent_zero_tick_cost(cold_sim):
    """Install is idempotent and adds NO per-tick hook (zero tick cost)."""
    sim, _ = cold_sim
    step_before = sim.step
    c1 = cc.install_cryoclasty(sim)
    c2 = cc.install_cryoclasty(sim)
    assert c1 is c2
    assert sim.step is step_before              # no sim.step wrapping


# ---------------------------------------------------------------------------
# D8 guardrail — introduces no new tell (composition only, 8th time)
# ---------------------------------------------------------------------------

def test_introduces_no_new_tell():
    """C14 surfaces NO new tell: it has no own ``_PROFILE`` and reuses C2's
    profiles. So PY_TO_RUST stays 15 and the *_outcrop glob ignores it."""
    assert not hasattr(cc, "_PROFILE"), "cryoclasty must not declare its own tell table"
    # it composes C2's profiles (proves reuse, not duplication).
    assert cc.lo._PROFILE is lo._PROFILE
    # the file is deliberately NOT named *_outcrop.py (stays out of the D8 glob).
    assert not Path(cc.__file__).name.endswith("_outcrop.py")


def test_py_to_rust_unchanged_at_15():
    """The cross-language contract map is untouched by C14 (D8 by composition)."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import test_geology_cross_language_contract as contract
    assert len(contract.PY_TO_RUST) == 15


def test_perceives_wave50_observer(cold_sim):
    """Closes R-J4-1: the capability surfaces the macro Wave 50 frost field —
    the first time an agent-facing cap consumes the observer's output."""
    sim, _ = cold_sim
    s = cc.cryoclasty_summary(sim)
    mf = s["macro_frost"]
    assert mf is not None
    assert mf["max_fci"] > 0.0
    assert {"talus_cells", "permafrost_cells", "alpine_cells"} <= set(mf)
