"""Invariants — Substrate capability : la fonte du cuivre (Cap. C13).

Couvre :
- **La 4ᵉ transformation, la 1ʳᵉ métallurgique** : la **fonte effective** du cuivre —
  la promesse que C12 (`would_smelt_copper_here`) différait explicitement. Le monde
  s'engage sur `copper_smelt_yield` (SSOT déterministe), RÉUTILISE le seuil de fusion
  `fd.COPPER_SMELT_TEMP_C` (C12) et le rendement par élément du **catalogue minéral**
  (`yields_per_kg_ore["Cu"]`, `category`) — aucune teneur re-déclarée.
- **Composition, pas nouveau tell (garde-fou D8)** : pas de `_PROFILE`, aucune entrée
  `PY_TO_RUST` ; hors glob `*_outcrop.py`. Lit C12 `forced_draught` (four assez chaud)
  et C1 `surface_mineralization` (tell cuivre). 7ᵉ capacité D8-par-composition.
- **Le mensonge rendu visible #4** : le **même tell vert** (C1) couvre le cuivre natif
  (fonte directe, facile) ET la chalcopyrite (sulfure réfractaire — il faut **griller**
  avant de fondre, sinon ~0 métal). `best_smelt_site_near` enseigne la leçon.
- **La fonte effective (mutation)** : `smelt_at` **consomme** le minerai (via `geo.mine_at`)
  et **rend** un bouton + scorie. « Le monde ne ment jamais » au sens fort : le cuivre
  réellement rendu == celui que l'oracle avait promis. Un sulfure cru → consommé, **scorie
  seule** (la leçon coûteuse).
- **Effet 1+1>2** : un site smeltable QUE si un four forçable ≥1085 °C (C12) ET un minerai
  de cuivre (C1) coexistent.
- `smelt_preview` non mutant nomme l'ingrédient manquant.
- Déterminisme même-seed de l'oracle (bit-identique). Installation idempotente, coût
  tick nul (l'oracle ; `smelt_at` mute volontairement).
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
import engine.clay_outcrop as ci                                    # noqa: E402
import engine.fire_ignition as fi                                   # noqa: E402
import engine.limestone_outcrop as li                               # noqa: E402
import engine.kiln_draft as kd                                      # noqa: E402
import engine.surface_mineralization as sm                          # noqa: E402
import engine.forced_draught as fd                                  # noqa: E402
import engine.copper_smelting as cs                                 # noqa: E402

_GRASS = 6        # GRASSLAND — dry, fire-makeable, fine_fuel 0.80 (charcoal-grade)
_BOREAL = 3       # BOREAL_FOREST — clay-visible but too wet for any fire


# ---------------------------------------------------------------------------
# Helpers — compose exactly as the capability does, from a raw geology column.
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


def _forced(coord, layers, biome, chunk):
    clay = ci._cue_from_geology(coord, layers, biome, chunk)
    fire = fi._cue_from_geology(coord, layers, biome, chunk)
    lime = li._cue_from_geology(coord, layers, biome, chunk)
    kiln = kd._cue_from_inputs(coord, clay, fire, lime)
    copper = sm._cue_from_geology(coord, layers, biome)
    return fd._cue_from_inputs(coord, kiln, copper)


def _derive(coord, layers, biome, chunk):
    return cs._cue_from_inputs(coord, _forced(coord, layers, biome, chunk))


# Refractory kaolin walls + a co-located NATIVE copper ore (the easy green).
def _kaolin_native_copper():
    return [_layer(0.0, 4.0, "sandstone",
                   ore={"fine_clay": 0.06, "native_copper": 0.05})]


# Refractory kaolin walls + a co-located CHALCOPYRITE ore (the sulfide green — same colour).
def _kaolin_chalcopyrite():
    return [_layer(0.0, 4.0, "sandstone",
                   ore={"fine_clay": 0.06, "chalcopyrite": 0.05})]


# Common earthenware walls (shale) + native copper — still smelts copper (>=1085 C).
def _common_native_copper():
    return [_layer(0.0, 4.0, "shale", ore={"native_copper": 0.05})]


# Refractory kaolin walls but NO copper ore — a hot furnace, nothing to smelt.
def _kaolin_only():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06})]


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
    cs.install_copper_smelting(sim)
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

def test_native_copper_smelts_directly():
    """Native copper is already metal — just melt & coalesce above 1085 C, no roast.
    High recovery, high-purity bead, recovery rises with superheat (saturating)."""
    cold = cs.copper_smelt_yield("native_copper", 10.0, 1000.0)
    assert cold.hot_enough is False and cold.recovered_cu_kg == 0.0
    y = cs.copper_smelt_yield("native_copper", 10.0, 1200.0)
    assert y.ore_class == "native_metal" and y.requires_roasting is False
    assert y.contained_cu_fraction == 1.0 and y.contained_cu_kg == 10.0
    assert 0.0 < y.recovered_cu_kg < 10.0          # never recovers ALL contained Cu
    assert y.bead_purity == cs.NATIVE_BEAD_PURITY
    # superheat monotonicity + ceiling
    lo = cs.copper_smelt_yield("native_copper", 10.0, 1090.0).recovery_efficiency
    hi = cs.copper_smelt_yield("native_copper", 10.0, 1400.0).recovery_efficiency
    assert lo < hi <= cs.NATIVE_RECOVERY_CEIL


def test_sulfide_needs_roasting_first():
    """Chalcopyrite is a refractory sulfide — un-roasted it yields NOTHING (locked in
    matte/slag); only a roast (≈590 C) unlocks the lower, blister-purity recovery."""
    raw = cs.copper_smelt_yield("chalcopyrite", 10.0, 1300.0, roasted=False)
    assert raw.requires_roasting is True
    assert raw.recovered_cu_kg == 0.0 and raw.slag_kg == 10.0     # all charge → slag
    roasted = cs.copper_smelt_yield("chalcopyrite", 10.0, 1300.0, roasted=True)
    assert roasted.recovered_cu_kg > 0.0
    # the catalogue Cu fraction (0.35) caps it well below native copper
    assert roasted.contained_cu_fraction == MINERAL_BY_NAME["chalcopyrite"].yields_per_kg_ore["Cu"]
    assert roasted.recovered_cu_kg < cs.copper_smelt_yield("native_copper", 10.0, 1300.0).recovered_cu_kg
    assert roasted.bead_purity == cs.SULFIDE_BEAD_PURITY


def test_non_copper_ore_yields_nothing():
    """A non-copper material (or an unknown name) smelts to no copper — honest zero."""
    for name in ("shale", "fine_clay", "limestone_pure", "definitely_not_a_mineral"):
        y = cs.copper_smelt_yield(name, 10.0, 1300.0)
        assert y.ore_class == "non_copper"
        assert y.recovered_cu_kg == 0.0 and y.contained_cu_fraction == 0.0


def test_reuses_c12_threshold_and_catalogue_ssot():
    """The combo: C13 reuses C12's copper melting threshold verbatim and the mineral
    catalogue's per-element yield — it re-declares neither the threshold nor any teneur."""
    import inspect
    src = inspect.getsource(cs)
    assert "import engine.forced_draught" in src
    assert "fd.COPPER_SMELT_TEMP_C" in src
    assert "yields_per_kg_ore" in src and "MINERAL_BY_NAME" in src
    # the melt gate IS C12's threshold (not an independent magic number).
    just_below = cs.copper_smelt_yield("native_copper", 1.0, fd.COPPER_SMELT_TEMP_C - 0.1)
    just_at = cs.copper_smelt_yield("native_copper", 1.0, fd.COPPER_SMELT_TEMP_C)
    assert just_below.hot_enough is False and just_at.hot_enough is True


def test_introduces_no_new_tell():
    """C13 composes C12 furnace + C1 copper tell; it surfaces no new buried-mineral cue
    — the D8-by-composition decision (7th time, after C7/C8/C9/C10/C11/C12)."""
    assert not hasattr(cs, "_PROFILE")
    assert not Path(cs.__file__).name.endswith("_outcrop.py")
    for mat in ("native_copper", "chalcopyrite"):
        assert mat in MINERAL_BY_NAME
    import inspect
    src = inspect.getsource(cs)
    assert "forced_cue_for_chunk" in src and "surface_cue_for_chunk" in src


# ---------------------------------------------------------------------------
# The lie made visible #4 — native (easy) vs chalcopyrite (sulfide) same green tell
# ---------------------------------------------------------------------------

def test_same_green_tell_opposite_metallurgy():
    """C1 surfaces native copper AND chalcopyrite as the SAME green tell (same rgb,
    same group) — but C13 reveals opposite metallurgy: native smelts directly, the
    sulfide must be roasted first. The inversion (after obsidian C8, kaolin C9)."""
    c1_native = sm._cue_from_geology((0, 0, 0), _kaolin_native_copper(), _GRASS)
    c1_sulf = sm._cue_from_geology((0, 0, 0), _kaolin_chalcopyrite(), _GRASS)
    assert c1_native.group == "copper" and c1_sulf.group == "copper"
    assert c1_native.rgb == c1_sulf.rgb            # the identical green sign
    assert c1_native.mineral == "native_copper"
    assert c1_sulf.mineral == "chalcopyrite"

    native = _derive((0, 0, 0), _kaolin_native_copper(), _GRASS, _chunk(biome=_GRASS))
    sulf = _derive((0, 0, 0), _kaolin_chalcopyrite(), _GRASS, _chunk(biome=_GRASS))
    assert native is not None and sulf is not None
    # native: directly smeltable, no roast.
    assert native.ore_class == "native_metal"
    assert native.smeltable_now is True and native.needs_roasting_first is False
    assert native.recovered_cu_per_kg_ore > 0.0
    # chalcopyrite (same green!): NOT smeltable now — needs roasting first.
    assert sulf.ore_class == "sulfide"
    assert sulf.smeltable_now is False and sulf.needs_roasting_first is True
    assert sulf.recovered_cu_per_kg_ore == 0.0              # the lie: green but no metal now
    assert sulf.recovered_cu_per_kg_ore_roasted > 0.0       # a roast unlocks it
    assert sulf.roast_temp_c == cs.ROAST_TEMP_C


def test_best_site_prefers_richer_copper_and_require_direct():
    """`best_smelt_site_near` prefers the most copper actually gotten (native > roasted
    sulfide), and `require_direct` keeps only no-roast sites — teaching the lesson."""
    sim = _booted_sim("c13_best")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    nb = coords[len(coords) // 2 + 1]
    _put_chunk(sim, cc, _kaolin_native_copper(), _GRASS, 0.0)
    _put_chunk(sim, nb, _kaolin_chalcopyrite(), _GRASS, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    r = 2.0 * CHUNK_SIDE_M
    best = cs.best_smelt_site_near(sim, 0, perception_radius_m=r)
    assert best is not None and best.copper_mineral == "native_copper"
    direct = cs.best_smelt_site_near(sim, 0, perception_radius_m=r, require_direct=True)
    assert direct is not None and direct.smeltable_now is True
    assert direct.ore_class == "native_metal"


# ---------------------------------------------------------------------------
# Composition / cue gating
# ---------------------------------------------------------------------------

def test_no_copper_no_smelt_cue():
    """A hot furnace with no copper ore underfoot → no smelt affordance (nothing to
    smelt). The 1+1>2 gate, mirroring C12's would_smelt = temp AND ore."""
    cue = _derive((0, 0, 0), _kaolin_only(), _GRASS, _chunk(biome=_GRASS))
    assert cue is None
    forced = _forced((0, 0, 0), _kaolin_only(), _GRASS, _chunk(biome=_GRASS))
    assert forced is not None and forced.reaches_copper_smelting_temp is True
    assert forced.copper_ore_here is False


def test_no_furnace_no_smelt_cue():
    """Copper ore but no buildable hot furnace (boreal: too wet for any fire → no kiln,
    no forced draught) → no smelt affordance."""
    cue = _derive((0, 0, 0), _common_native_copper(), _BOREAL, _chunk(biome=_BOREAL))
    assert cue is None


def test_cue_mineral_agrees_with_c1():
    """`copper_mineral` is exactly C1's copper-group surface cue — single source of truth."""
    layers = _common_native_copper()
    c1 = sm._cue_from_geology((0, 0, 0), layers, _GRASS)
    cue = _derive((0, 0, 0), layers, _GRASS, _chunk(biome=_GRASS))
    assert cue is not None and cue.copper_mineral == c1.mineral == "native_copper"


# ---------------------------------------------------------------------------
# "Le monde ne ment jamais" — real Genesis world (seed 0xBEEF surfaces copper)
# ---------------------------------------------------------------------------

def _assert_cue_truthful(sim, coord, cue):
    if cue is None:
        return
    forced = fd.forced_cue_for_chunk(sim, coord)
    assert forced is not None and forced.would_smelt_copper_here is True
    assert forced.forced_peak_c >= fd.COPPER_SMELT_TEMP_C
    # the ore the smelt reasons about is exactly C1's copper-group tell here.
    c1 = sm.surface_cue_for_chunk(sim, coord)
    assert c1 is not None and c1.group == "copper" and c1.mineral == cue.copper_mineral
    # recovered copper never exceeds the copper contained in the ore (catalogue).
    contained = MINERAL_BY_NAME[cue.copper_mineral].yields_per_kg_ore.get("Cu", 0.0)
    assert cue.contained_cu_fraction == round(contained, 4)
    assert 0.0 <= cue.recovered_cu_per_kg_ore <= contained + 1e-9
    assert 0.0 <= cue.recovered_cu_per_kg_ore_roasted <= contained + 1e-9
    # a sulfide gives nothing un-roasted, but a positive roasted potential (the lie).
    if cue.ore_class == "sulfide":
        assert cue.needs_roasting_first is True
        assert cue.recovered_cu_per_kg_ore == 0.0
        assert cue.recovered_cu_per_kg_ore_roasted > 0.0
    else:
        assert cue.smeltable_now is True and cue.recovered_cu_per_kg_ore > 0.0


def test_world_never_lies_on_real_world():
    sim = _booted_sim("c13_neverlies")
    coords = _populate(sim)
    assert len(coords) > 0
    n_sites = n_native = n_sulfide = 0
    for coord in coords:
        cue = cs.smelt_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n_sites += 1
        n_native += int(cue.ore_class == "native_metal")
        n_sulfide += int(cue.ore_class == "sulfide")
        _assert_cue_truthful(sim, coord, cue)
    # the grassland seed surfaces real copper smelt sites — BOTH native and sulfide.
    assert n_sites > 0 and n_native > 0 and n_sulfide > 0


def test_smelt_at_consumes_ore_and_matches_oracle():
    """The fonte effective: smelt_at DRAINS the ore from the column and yields the metal
    the oracle promised. The world never lies at the strong (mutating) level."""
    sim = _booted_sim("c13_smelt_native")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, _kaolin_native_copper(), _GRASS, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    cue = cs.smelt_cue_for_chunk(sim, cc)
    assert cue is not None and cue.smeltable_now is True
    g = geo.chunk_geology(sim, cc)
    extracted_before = g.layers[0].extracted_kg
    res = cs.smelt_at(sim, 0, charge_kg=5.0)
    assert res is not None
    assert g.layers[0].extracted_kg > extracted_before          # ore really consumed
    assert res.ore_consumed_kg > 0.0 and res.recovered_cu_kg > 0.0
    assert res.copper_mineral == "native_copper" and res.ore_class == "native_metal"
    # realized recovery == the oracle's committed per-kg yield × ore consumed.
    expected = cue.recovered_cu_per_kg_ore * res.ore_consumed_kg
    assert abs(res.recovered_cu_kg - expected) <= 1e-4
    assert res.bead_purity == cs.NATIVE_BEAD_PURITY


def test_smelt_at_raw_sulfide_yields_only_slag():
    """The costly honest lesson: smelting a sulfide un-roasted CONSUMES the charge and
    yields only slag (0 copper). The agent must discover roasting first."""
    sim = _booted_sim("c13_smelt_sulfide")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, _kaolin_chalcopyrite(), _GRASS, 0.0)
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    g = geo.chunk_geology(sim, cc)
    before = g.layers[0].extracted_kg
    raw = cs.smelt_at(sim, 0, charge_kg=5.0, roasted=False)
    assert raw is not None and raw.required_roasting is True
    assert raw.ore_consumed_kg > 0.0                            # charge consumed (lost)
    assert raw.recovered_cu_kg == 0.0 and raw.slag_kg > 0.0     # only slag
    assert g.layers[0].extracted_kg > before
    # roasting the next charge DOES yield metal.
    roasted = cs.smelt_at(sim, 0, charge_kg=5.0, roasted=True)
    assert roasted is not None and roasted.recovered_cu_kg > 0.0


def test_smelt_at_returns_none_without_site():
    """No smeltable site under the agent → smelt_at is a no-op (None), mutates nothing."""
    sim = _booted_sim("c13_nosite")
    coords = _populate(sim)
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, _kaolin_only(), _GRASS, 0.0)   # hot furnace, no copper
    sim.agents.pos[0, 0] = (cc[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cc[1] + 0.5) * CHUNK_SIDE_M
    assert cs.smelt_cue_for_chunk(sim, cc) is None
    assert cs.smelt_at(sim, 0) is None


# ---------------------------------------------------------------------------
# Non-mutating preview
# ---------------------------------------------------------------------------

def _put_chunk(sim, cc, layers, biome, w):
    ch = sim.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, biome,
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
    sim._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=layers)
    sim._clay_cue_cache.clear()
    sim._ignition_cue_cache.clear()
    sim._limestone_cue_cache.clear()
    sim._kiln_draft_cue_cache.clear()
    sim._surface_cue_cache.clear()
    sim._forced_draught_cue_cache.clear()
    sim._copper_smelt_cue_cache.clear()


def test_preview_non_mutating_and_truthful():
    sim = _booted_sim("c13_preview")
    coords = _populate(sim)
    target = next((c for c in coords
                   if cs.smelt_cue_for_chunk(sim, c) is not None), None)
    assert target is not None
    g = geo.chunk_geology(sim, target)
    before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    sim.agents.pos[0, 0] = (target[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (target[1] + 0.5) * CHUNK_SIDE_M
    out = cs.smelt_preview(sim, float(sim.agents.pos[0, 0]),
                           float(sim.agents.pos[0, 1]))
    cue = cs.smelt_cue_for_chunk(sim, target)
    after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
    assert after == before                       # preview mutated nothing
    assert out["smeltable"] is True
    assert out["copper_mineral"] == cue.copper_mineral
    assert out["recovered_cu_per_kg_ore"] == cue.recovered_cu_per_kg_ore
    assert out["needs_roasting_first"] == cue.needs_roasting_first


def test_preview_names_missing_copper():
    """A hot furnace, no copper ore → preview says smeltable False, reason names copper."""
    sim = Simulation(SimConfig(name="c13_nocu", seed=7, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_GRASS, w=0.0)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(
        coord=cc, layers=_kaolin_only())}
    out = cs.smelt_preview(sim, 4.0, 4.0)
    assert out["smeltable"] is False
    assert out["has_furnace"] is True and out["has_copper_ore"] is False
    assert "copper" in out["reason"]


def test_preview_names_missing_furnace():
    """Copper ore but bare granite + boreal wet → no furnace; preview names it."""
    sim = Simulation(SimConfig(name="c13_nofurnace", seed=8, founders=2, max_agents=4,
                               bounds_km=(0.3, 0.3), spawn_radius_m=20.0,
                               drive_accel=1500.0, cultures=1))
    cc = (0, 0, 0)
    sim.streamer.cache[cc] = _chunk(biome=_BOREAL, w=0.5)
    sim._geology_state = type("G", (), {})()
    sim._geology_state.chunks = {cc: ChunkGeology(
        coord=cc, layers=[_layer(0.0, 5.0, "granite", ore={"native_copper": 0.05})])}
    out = cs.smelt_preview(sim, 4.0, 4.0)
    assert out["smeltable"] is False
    assert out["has_furnace"] is False


# ---------------------------------------------------------------------------
# Determinism + install hygiene
# ---------------------------------------------------------------------------

def _cue_key(c):
    return None if c is None else (c.copper_mineral, c.ore_class,
                                   round(c.recovered_cu_per_kg_ore, 6),
                                   round(c.recovered_cu_per_kg_ore_roasted, 6),
                                   c.smeltable_now, c.needs_roasting_first)


def test_determinism_same_seed():
    a = _booted_sim("c13_det_a", seed=0xBEEF)
    b = _booted_sim("c13_det_b", seed=0xBEEF)
    ca, cb = _populate(a), _populate(b)
    assert ca == cb and len(ca) > 0
    for coord in ca:
        assert _cue_key(cs.smelt_cue_for_chunk(a, coord)) == \
               _cue_key(cs.smelt_cue_for_chunk(b, coord))


def test_install_idempotent_and_summary_shape():
    sim = _booted_sim("c13_idem")
    _populate(sim)
    c1 = cs.install_copper_smelting(sim)
    c2 = cs.install_copper_smelting(sim)
    assert c1 is c2  # same cache object, no duplicate state
    s = cs.smelt_summary(sim)
    assert set(s) >= {"n_chunks", "n_smelt_sites", "smelt_rate",
                      "n_direct_smeltable", "n_needs_roasting",
                      "best_recovered_cu_per_kg_ore", "best_bead_purity",
                      "by_ore_class", "by_mineral"}
    assert 0.0 <= s["smelt_rate"] <= 1.0
    assert s["n_smelt_sites"] <= s["n_chunks"]
    assert s["n_direct_smeltable"] + s["n_needs_roasting"] <= s["n_smelt_sites"]
    assert s["best_bead_purity"] <= cs.NATIVE_BEAD_PURITY
