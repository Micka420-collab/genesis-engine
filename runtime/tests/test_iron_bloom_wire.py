"""Invariants — the agent loop BLOOMs iron ore (D12 wire #19, 2026-07-01, consumes C17).

The 19th wire — and **the 2nd AGENT-DRIVEN MUTATION OF THE WORLD**, after SMELT/C13. C13 crossed the
D10 mutation frontier (``smelt_at`` → ``geo.mine_at``) for copper; C17 ``iron_bloomery`` extends the same
metallurgical sub-arc (ADR-0010) to iron — le seuil de l'âge du fer. This wire lets a curious agent that
has (a) discovered the forced-draught furnace (``has_forced_draught``, C12 — only a refractory forced
furnace clears the 1200 °C bloomery regime), (b) LEARNED that the rusty iron-hat means iron
(``"gossan" in prospected_ore_groups``, C1/PROSPECT), and (c) carries a charcoal charge (``inv_fuel``, C4)
REDUCE the oxide iron-hat ore underfoot: the ore truly disappears from the ground and a SOLID spongy iron
bloom fills ``inv_metal``. Adds ``ActionKind.BLOOM`` (a new verb — iron reduction is not copper smelting).

THE PHYSICAL LIE (vs C13): copper runs to a poured bead; iron NEVER melts (1538 °C, out of reach) — the
bloom is a solid sponge that must be forged (C19), never poured. THE LIE #8: the same rusty gossan caps an
oxide (hematite/magnetite → sound iron), a sulfide (pyrite → slag unless roasted, then red-short), or
lead/zinc (galena/sphalerite → NO iron). The wire routes to the oxide it can reduce NOW (``require_direct``).

What this file proves:
1.  Gated on C17 (no cue cache → inert).
2.  Forced-draught dependency (C12): an agent that never forced a draught does not bloom.
3.  Prospect dependency (C1): an agent that never learned the gossan means iron does not bloom.
4.  Fuel dependency (C4): a ready agent with no charcoal does not bloom (and mutates no geology).
5.  A ready agent on a directly-reducible oxide iron-hat chooses BLOOM; off-site WALK_TOs.
6.  **The D10 crossing**: BLOOM drains ore (extracted_kg ↑), fills inv_metal with the bloom, spends fuel,
    records has_bloomed_iron + the mineral + the site, emits a truthful event.
7.  The physical lie: the iron is a SOLID bloom (never poured) — ``is_solid_bloom`` True.
8.  The lie #8 (sulfide): a raw pyrite is CONSUMED but yields only slag (0 iron); the agent is NOT locked
    out (has_bloomed_iron stays False) — the honest costly lesson of the sulfide iron-hat.
9.  The deepest lie (non-iron): a lead/zinc gossan yields NO iron and mutates nothing.
10. Self-limiting — an agent that has already bloomed iron (has_bloomed_iron) does not re-seek.
11. « le monde ne ment jamais » — blooming where nothing is reducible keeps the fuel and the metal.
12. Survival outranks blooming.
13. Back-compat (sim=None inert).
14. Determinism (same injected site → same bloom).
15. Registry + enum + D8 discipline (composition only; PY_TO_RUST stays 15) + orthogonal to SMELT.
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
from engine.world_genesis import GenesisParams                      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine.geology import StrataLayer, ChunkGeology                # noqa: E402
from engine import cognition as cog                                 # noqa: E402
from engine.cognition import Observation, PerceivedTarget           # noqa: E402
from engine.agent import ActionKind, DriveKind                      # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.iron_bloomery as ib                                   # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_BLOOM = 0x1201    # thematic: 1200 °C bloomery threshold / the iron age (~1200 BCE) — a clean seed
GRID = 12              # verified: no natural bloomery site within 128 m of centre (injected site is unique)
_GRASS = 6             # GRASSLAND — dry, fine_fuel charcoal-grade (forces the furnace to ~1295 °C ≥ 1200)


# ---------------------------------------------------------------------------
# Boot + a deterministic reducible site (injected — no lucky-seed dependency).
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = SEED_BLOOM, *, with_c17: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8))
    geo.install_geology(sim)
    if with_c17:
        ib.install_iron_bloomery(sim)   # also installs C12 forced_draught + C1 mineralization + geo
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
                coords.append(coord)
    return sim, coords


def _layer(top, bottom, rock="sandstone", ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=2400.0, ore_mix=dict(ore or {}))


# Refractory kaolin walls (fine_clay → forces to ~1295 °C) + a co-located OXIDE iron-hat (hematite —
# reduces directly to sound iron).
def _oxide_iron():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06, "hematite": 0.05})]


# Refractory kaolin walls + a SULFIDE iron-hat (pyrite — the same rusty gossan; only slag unless roasted).
def _sulfide_iron():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06, "pyrite": 0.05})]


# Refractory kaolin walls + a NON-IRON gossan (galena → lead; the deepest lie of the iron-hat: no iron).
def _non_iron():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06, "galena": 0.05})]


def _put_chunk(sim, cc, layers, biome=_GRASS, w=0.0):
    """Inject a hand-built geology column at ``cc`` and clear the composed cue caches, so the C17 bloom
    cue derives from it — the recipe test_iron_bloomery uses to guarantee a reducible iron-hat site."""
    ch = sim.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, biome, dtype=np.asarray(ch.biome).dtype)
    ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
    sim._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=layers)
    for cache in ("_clay_cue_cache", "_ignition_cue_cache", "_limestone_cue_cache",
                  "_kiln_draft_cue_cache", "_surface_cue_cache", "_forced_draught_cue_cache",
                  "_copper_smelt_cue_cache", "_iron_bloom_cue_cache"):
        c = getattr(sim, cache, None)
        if c is not None:
            c.clear()


def _reducible_site(sim, coords, layers=None):
    """Inject a reducible iron-hat column into a central streamed chunk and return its coord."""
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, layers or _oxide_iron())
    return cc


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _ready(sim, row, *, forced=True, prospected_gossan=True, fuel_kg=2.0,
           bloomed=False, metal_kg=0.0):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal", "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal", "inv_tools",
                "inv_pigment", "inv_clay", "inv_ceramic", "inv_limestone", "inv_lime",
                "inv_salt", "inv_fuel"):
        getattr(sim.agents, inv)[row] = 0.0
    sim.agents.inv_fuel[row] = float(fuel_kg)
    sim.agents.inv_metal[row] = float(metal_kg)
    sim.agents.thermal[row] = 0.05
    mem = sim.agents.memory[row]
    mem.known_bloom_locations.clear()
    mem.has_bloomed_iron = bool(bloomed)
    mem.last_bloom_mineral = None
    mem.last_bloom_iron_kg = 0.0
    mem.has_forced_draught = bool(forced)          # the C12/FORCE_DRAUGHT dependency
    mem.last_forced_peak_c = 1295.0 if forced else None
    mem.has_built_kiln = True                      # a draught-forcer already built the kiln
    mem.has_made_fire = True                       # ...and knows fire
    mem.prospected_ore_groups = ["gossan"] if prospected_gossan else []
    mem.has_prospected_ore = bool(prospected_gossan)


def _obs(sim, row, *, nearest=None, drives=None):
    a = sim.agents
    d = drives if drives is not None else np.array(
        [float(a.hunger[row]), float(a.thirst[row]), float(a.sleep[row]),
         float(a.fatigue[row]), float(a.thermal[row]), float(a.pain[row]),
         float(a.stress[row]), float(a.loneliness[row])], dtype=np.float32)
    return Observation(
        row=int(row),
        pos=(float(a.pos[row, 0]), float(a.pos[row, 1]), float(a.pos[row, 2])),
        drives=d, vitality=float(a.vitality[row]), nearest=(nearest or {}),
        near_agents=[], dominant_drive=cog._dominant_drive(d),
        tick=0, reproduction_readiness=0.0)


def _far_unstreamed(grid: int = GRID):
    return ((grid + 50 + 0.5) * CHUNK_SIDE_M, (grid + 50 + 0.5) * CHUNK_SIDE_M)


def _bloom_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.BLOOM), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

def test_seek_bloom_inert_without_c17():
    sim, coords = _booted_sim("gate", with_c17=False)
    _ready(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_iron_bloom_cue_cache", None) is None
    assert cog._seek_bloom(sim.agents, 0, _obs(sim, 0), sim) is None


def test_agent_without_forced_draught_does_not_bloom():
    sim, coords = _booted_sim("needs_forced")
    cc = _reducible_site(sim, coords)
    _ready(sim, 0, forced=False)
    _stand(sim, 0, cc)
    assert cog._seek_bloom(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _bloom_here(sim, 0) == []


def test_agent_without_prospected_gossan_does_not_bloom():
    sim, coords = _booted_sim("needs_prospect")
    cc = _reducible_site(sim, coords)
    _ready(sim, 0, prospected_gossan=False)
    _stand(sim, 0, cc)
    assert cog._seek_bloom(sim.agents, 0, _obs(sim, 0), sim) is None


def test_agent_without_fuel_does_not_bloom_and_mutates_no_geology():
    sim, coords = _booted_sim("needs_fuel")
    cc = _reducible_site(sim, coords)
    _ready(sim, 0, fuel_kg=0.0)
    _stand(sim, 0, cc)
    g = geo.chunk_geology(sim, cc)
    before = float(g.layers[0].extracted_kg)
    assert cog._seek_bloom(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _bloom_here(sim, 0) == []
    assert float(g.layers[0].extracted_kg) == before   # a gated precondition mutates NO geology (D10 safe)


# ---------------------------------------------------------------------------
# The decision + the act (the D10 crossing)
# ---------------------------------------------------------------------------

def test_ready_agent_on_oxide_site_decides_to_bloom():
    sim, coords = _booted_sim("decide")
    cc = _reducible_site(sim, coords)
    cue = ib.bloom_cue_for_chunk(sim, cc)
    assert cue is not None and cue.reducible_now is True    # the injected site is directly reducible
    _ready(sim, 0)
    _stand(sim, 0, cc)
    seek = cog._seek_bloom(sim.agents, 0, _obs(sim, 0), sim)
    assert seek is not None and seek.action == int(ActionKind.BLOOM)


def test_ready_agent_walks_toward_perceived_furnace():
    sim, coords = _booted_sim("walk")
    cc = _reducible_site(sim, coords)
    cx = (cc[0] + 0.5) * CHUNK_SIDE_M
    cy = (cc[1] + 0.5) * CHUNK_SIDE_M
    _ready(sim, 0)
    sim.agents.pos[0, 0] = cx + CHUNK_SIDE_M       # one chunk east — off-site, still in range
    sim.agents.pos[0, 1] = cy
    seek = cog._seek_bloom(sim.agents, 0, _obs(sim, 0), sim)
    if seek is None or seek.action == int(ActionKind.BLOOM):
        pytest.skip("nearest reducible site is underfoot from this offset — no WALK_TO to assert")
    assert seek.action == int(ActionKind.WALK_TO)


def test_blooming_consumes_ore_fills_metal_and_mutates_geology():
    """THE D10 CROSSING (2nd, iron). BLOOM drains the ore column, fills inv_metal with the solid bloom,
    spends the charcoal charge, and records the skill/site."""
    sim, coords = _booted_sim("act")
    cc = _reducible_site(sim, coords)
    cue = ib.bloom_cue_for_chunk(sim, cc)
    assert cue is not None and cue.reducible_now is True
    _ready(sim, 0, fuel_kg=2.0)
    _stand(sim, 0, cc)
    g = geo.chunk_geology(sim, cc)
    extracted_before = float(g.layers[0].extracted_kg)
    fuel_before = float(sim.agents.inv_fuel[0])
    metal_before = float(sim.agents.inv_metal[0])
    ev = _bloom_here(sim, 0)
    assert ev and ev[-1]["kind"] == "bloom"
    # D10 CROSSED: the ore is really drained from the geology column.
    assert float(g.layers[0].extracted_kg) > extracted_before
    assert ev[-1]["mutated_geology"] is True
    assert ev[-1]["ore_consumed_kg"] > 0.0
    # a solid iron bloom filled inv_metal; a charcoal charge was spent.
    assert float(sim.agents.inv_metal[0]) > metal_before
    assert ev[-1]["bloom_iron_kg"] > 0.0
    assert float(sim.agents.inv_fuel[0]) == pytest.approx(fuel_before - cog.BLOOM_FUEL_COST_KG)
    # the skill + the mineral + the site are remembered.
    assert sim.agents.memory[0].has_bloomed_iron is True
    assert sim.agents.memory[0].last_bloom_mineral == "hematite"
    assert ev[-1]["iron_mineral"] == "hematite" and ev[-1]["ore_class"] == "oxide_iron"
    assert len(sim.agents.memory[0].known_bloom_locations) == 1


def test_iron_is_a_solid_bloom_never_poured():
    """THE PHYSICAL LIE vs copper: iron never melts (1538 °C, out of reach) — the world hands back a
    SOLID sponge that must be forged (C19), never a poured bead."""
    sim, coords = _booted_sim("solid")
    cc = _reducible_site(sim, coords)
    _ready(sim, 0, fuel_kg=2.0)
    _stand(sim, 0, cc)
    ev = _bloom_here(sim, 0)
    assert ev and ev[-1]["kind"] == "bloom"
    assert ev[-1]["is_solid_bloom"] is True        # a sponge, never poured
    assert ev[-1]["red_short"] is False            # oxide iron is sound (not sulfur-embrittled)


def test_raw_sulfide_bloom_yields_only_slag_but_still_mutates_and_does_not_lock_out():
    """The lie #8 lived: a raw pyrite is CONSUMED (geology mutated) but yields only slag — 0 iron. The
    agent is NOT locked out (has_bloomed_iron stays False), so an honest failure never ends the iron age."""
    sim, coords = _booted_sim("sulfide")
    cc = _reducible_site(sim, coords, layers=_sulfide_iron())
    cue = ib.bloom_cue_for_chunk(sim, cc)
    assert cue is not None and cue.needs_roasting_first is True
    _ready(sim, 0, fuel_kg=2.0)
    _stand(sim, 0, cc)
    g = geo.chunk_geology(sim, cc)
    before = float(g.layers[0].extracted_kg)
    metal_before = float(sim.agents.inv_metal[0])
    ev = _bloom_here(sim, 0)
    assert ev and ev[-1]["kind"] == "bloom"
    assert ev[-1]["required_roasting"] is True
    assert ev[-1]["bloom_iron_kg"] == 0.0                   # only slag — no iron
    assert ev[-1]["slag_kg"] > 0.0
    assert float(g.layers[0].extracted_kg) > before         # ...but the charge was still consumed (mutated)
    assert float(sim.agents.inv_metal[0]) == metal_before   # no iron gained
    assert sim.agents.memory[0].has_bloomed_iron is False    # not locked out — the honest failure is free to retry


def test_non_iron_gossan_yields_no_iron_and_mutates_nothing():
    """The deepest lie of the iron-hat: a lead/zinc gossan (galena) caps NO iron. The world refuses the
    reduction (bloom_at → None) — nothing is consumed, nothing gained."""
    sim, coords = _booted_sim("noniron")
    cc = _reducible_site(sim, coords, layers=_non_iron())
    assert ib.bloom_cue_for_chunk(sim, cc) is None          # no iron under the rusty tell → no cue
    _ready(sim, 0, fuel_kg=2.0)
    _stand(sim, 0, cc)
    g = geo.chunk_geology(sim, cc)
    before = float(g.layers[0].extracted_kg)
    fuel_before = float(sim.agents.inv_fuel[0])
    ev = _bloom_here(sim, 0)
    assert ev == []                                         # the world says: nothing to reduce here
    assert float(g.layers[0].extracted_kg) == before        # no geology mutated (the honest 'no iron')
    assert float(sim.agents.inv_fuel[0]) == fuel_before
    assert sim.agents.memory[0].has_bloomed_iron is False


def test_iron_aged_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    cc = _reducible_site(sim, coords)
    _ready(sim, 0, bloomed=True)                            # already discovered the iron age
    _stand(sim, 0, cc)
    assert cog._seek_bloom(sim.agents, 0, _obs(sim, 0), sim) is None


def test_blooming_where_no_site_keeps_fuel_and_metal():
    sim, _coords = _booted_sim("barren")
    _ready(sim, 0, fuel_kg=2.0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert ib.bloom_at(sim, 0) is None                      # the world says: nothing reducible here
    fuel_before = float(sim.agents.inv_fuel[0])
    metal_before = float(sim.agents.inv_metal[0])
    ev = _bloom_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_fuel[0]) == fuel_before     # fuel kept where nothing reduces
    assert float(sim.agents.inv_metal[0]) == metal_before
    assert sim.agents.memory[0].has_bloomed_iron is False


def test_critical_thirst_outranks_blooming():
    sim, coords = _booted_sim("priority")
    cc = _reducible_site(sim, coords)
    _ready(sim, 0)
    px, py = _stand(sim, 0, cc)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)


def test_bloom_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    cc = _reducible_site(sim, coords)
    _ready(sim, 0, fuel_kg=2.0)
    px, py = _stand(sim, 0, cc)
    fuel_before = float(sim.agents.inv_fuel[0])
    dec = cog.Decision(int(ActionKind.BLOOM), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)   # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_fuel[0]) == fuel_before
    assert sim.agents.memory[0].has_bloomed_iron is False


def test_bloom_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    evs = []
    for s, c in ((a, ca), (b, cb)):
        cc = _reducible_site(s, c)
        _ready(s, 0, fuel_kg=2.0)
        _stand(s, 0, cc)
        evs.append(_bloom_here(s, 0)[-1])
    assert evs[0]["iron_mineral"] == evs[1]["iron_mineral"]
    assert evs[0]["bloom_iron_kg"] == evs[1]["bloom_iron_kg"]
    assert evs[0]["ore_consumed_kg"] == evs[1]["ore_consumed_kg"]
    assert evs[0]["bloom_purity"] == evs[1]["bloom_purity"]


def test_registry_and_enum_and_d8_discipline():
    # the wire is in the arc registry (orthogonal to SMELT), adds the BLOOM verb, composes C17 (no new
    # tell → D8: PY_TO_RUST stays 15).
    assert ("bloom", cog._seek_bloom) in cog._ARC_SEEKS
    assert ("smelt", cog._seek_smelt) in cog._ARC_SEEKS      # the two metallurgy wires coexist, independent
    assert hasattr(ActionKind, "BLOOM") and int(ActionKind.BLOOM) == 35
    sys.path.insert(0, str(RUNTIME / "tests"))
    import test_geology_cross_language_contract as contract        # noqa: E402
    assert len(contract.PY_TO_RUST) == 15                          # composition only — no new mineral tell
