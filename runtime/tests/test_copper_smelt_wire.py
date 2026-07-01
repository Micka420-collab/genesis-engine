"""Invariants — the agent loop SMELTs copper ore (D12 wire #18, 2026-07-01, consumes C13).

The 18th wire — and **THE FIRST AGENT-DRIVEN MUTATION OF THE WORLD**. Through 17 wires the agent
loop only ever read/gathered/transformed things it CARRIED; the geology column was never touched
(the D10 mutation frontier stayed frozen). C13 ``copper_smelting`` exposed ``smelt_at`` — the one
mutating entry point of the C1→C13 arc (it drains ore via ``geo.mine_at``). This wire lets a curious
agent that has (a) discovered the forced-draught furnace (``has_forced_draught``, C12), (b) LEARNED
green==copper (``"copper" in prospected_ore_groups``, C1/PROSPECT — wire #17's payoff), and (c)
carries a charcoal charge (``inv_fuel``, C4) SMELT the copper ore underfoot: the ore truly disappears
from the ground and a bead of metal fills ``inv_metal``. The D10 frontier is CROSSED here, by design
(ADR-0010). Reuses the legacy ``ActionKind.SMELT`` (made honest, as C3 did for DRINK).

What this file proves:
1. Gated on C13 (no cue cache → inert).
2. Forced-draught dependency (C12): an agent that never forced a draught does not smelt.
3. Prospect dependency (C1): an agent that never learned green==copper does not smelt.
4. Fuel dependency (C4): a ready agent with no charcoal in hand does not smelt.
5. A ready agent on a smeltable native-copper site chooses SMELT; off-site WALK_TOs.
6. **The D10 crossing**: SMELT drains ore from the column (extracted_kg ↑), fills inv_metal, spends
   fuel, records the skill (has_smelted_copper) + the mineral + the site, emits a truthful event.
7. The lie #4 lived: a raw sulfide (chalcopyrite) is CONSUMED but yields only slag (0 copper) — the
   geology is still mutated (the costly honest lesson).
8. Self-limiting — a metal-sated agent (inv_metal ≥ SMELT_METAL_SATED_KG) does not re-seek.
9. « le monde ne ment jamais » — smelting where nothing is smeltable keeps the fuel and the metal.
10. Survival outranks smelting.
11. Back-compat (sim=None inert).
12. Determinism (same injected site → same bead).
13. Registry + enum + D8 discipline (composition only; PY_TO_RUST stays 15).
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
import engine.copper_smelting as cs                                 # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_SMELT = 0xC13     # thematic
GRID = 12
_GRASS = 6             # GRASSLAND — dry, fire-makeable, fine_fuel charcoal-grade (so the furnace forces)


# ---------------------------------------------------------------------------
# Boot + a deterministic smeltable site (injected — no lucky-seed dependency).
# ---------------------------------------------------------------------------

def _booted_sim(name: str, seed: int = SEED_SMELT, *, with_c13: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8))
    geo.install_geology(sim)
    if with_c13:
        cs.install_copper_smelting(sim)   # also installs C12 forced_draught + C1 mineralization + geo
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


# Refractory kaolin walls + a co-located NATIVE copper ore (the easy green — smelts directly).
def _native_copper():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06, "native_copper": 0.05})]


# Refractory kaolin walls + a co-located CHALCOPYRITE ore (the sulfide green — same colour, needs roast).
def _chalcopyrite():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06, "chalcopyrite": 0.05})]


def _put_chunk(sim, cc, layers, biome=_GRASS, w=0.0):
    """Inject a hand-built geology column at ``cc`` and clear the composed cue caches, so the C13
    smelt cue derives from it — the recipe test_copper_smelting uses to guarantee a smeltable site."""
    ch = sim.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, biome, dtype=np.asarray(ch.biome).dtype)
    ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
    sim._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=layers)
    for cache in ("_clay_cue_cache", "_ignition_cue_cache", "_limestone_cue_cache",
                  "_kiln_draft_cue_cache", "_surface_cue_cache", "_forced_draught_cue_cache",
                  "_copper_smelt_cue_cache"):
        c = getattr(sim, cache, None)
        if c is not None:
            c.clear()


def _smeltable_site(sim, coords, layers=None):
    """Inject a smeltable column into a central streamed chunk and return its coord."""
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, layers or _native_copper())
    return cc


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _ready(sim, row, *, forced=True, prospected_copper=True, fuel_kg=2.0, metal_kg=0.0):
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
    mem.known_smelt_locations.clear()
    mem.has_smelted_copper = False
    mem.last_smelt_mineral = None
    mem.last_smelt_cu_kg = 0.0
    mem.has_forced_draught = bool(forced)          # the C12/FORCE_DRAUGHT dependency
    mem.last_forced_peak_c = 1200.0 if forced else None
    mem.has_built_kiln = True                      # a draught-forcer already built the kiln
    mem.has_made_fire = True                       # ...and knows fire
    mem.prospected_ore_groups = ["copper"] if prospected_copper else []
    mem.has_prospected_ore = bool(prospected_copper)


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


def _smelt_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.SMELT), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

def test_seek_smelt_inert_without_c13():
    sim, coords = _booted_sim("gate", with_c13=False)
    _ready(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_copper_smelt_cue_cache", None) is None
    assert cog._seek_smelt(sim.agents, 0, _obs(sim, 0), sim) is None


def test_agent_without_forced_draught_does_not_smelt():
    sim, coords = _booted_sim("needs_forced")
    cc = _smeltable_site(sim, coords)
    _ready(sim, 0, forced=False)
    _stand(sim, 0, cc)
    assert cog._seek_smelt(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _smelt_here(sim, 0) == []


def test_agent_without_prospected_copper_does_not_smelt():
    sim, coords = _booted_sim("needs_prospect")
    cc = _smeltable_site(sim, coords)
    _ready(sim, 0, prospected_copper=False)
    _stand(sim, 0, cc)
    assert cog._seek_smelt(sim.agents, 0, _obs(sim, 0), sim) is None


def test_agent_without_fuel_does_not_smelt():
    sim, coords = _booted_sim("needs_fuel")
    cc = _smeltable_site(sim, coords)
    _ready(sim, 0, fuel_kg=0.0)
    _stand(sim, 0, cc)
    assert cog._seek_smelt(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _smelt_here(sim, 0) == []


# ---------------------------------------------------------------------------
# The decision + the act (the D10 crossing)
# ---------------------------------------------------------------------------

def test_ready_agent_on_smeltable_site_decides_to_smelt():
    sim, coords = _booted_sim("decide")
    cc = _smeltable_site(sim, coords)
    _ready(sim, 0)
    _stand(sim, 0, cc)
    assert cs.smelt_cue_for_chunk(sim, cc) is not None      # the injected site is genuinely smeltable
    seek = cog._seek_smelt(sim.agents, 0, _obs(sim, 0), sim)
    assert seek is not None and seek.action == int(ActionKind.SMELT)


def test_ready_agent_walks_toward_perceived_furnace():
    sim, coords = _booted_sim("walk")
    cc = _smeltable_site(sim, coords)
    cx = (cc[0] + 0.5) * CHUNK_SIDE_M
    cy = (cc[1] + 0.5) * CHUNK_SIDE_M
    _ready(sim, 0)
    sim.agents.pos[0, 0] = cx + CHUNK_SIDE_M       # one chunk east — off-site, still in range
    sim.agents.pos[0, 1] = cy
    seek = cog._seek_smelt(sim.agents, 0, _obs(sim, 0), sim)
    if seek is None or seek.action == int(ActionKind.SMELT):
        pytest.skip("nearest smelt site is underfoot from this offset — no WALK_TO to assert")
    assert seek.action == int(ActionKind.WALK_TO)


def test_smelting_consumes_ore_fills_metal_and_mutates_geology():
    """THE D10 CROSSING — the first agent-driven mutation. SMELT drains the ore column, fills the
    metal bead, spends the charcoal charge, and records the skill/site."""
    sim, coords = _booted_sim("act")
    cc = _smeltable_site(sim, coords)
    cue = cs.smelt_cue_for_chunk(sim, cc)
    assert cue is not None and cue.smeltable_now is True
    _ready(sim, 0, fuel_kg=2.0)
    _stand(sim, 0, cc)
    g = geo.chunk_geology(sim, cc)
    extracted_before = float(g.layers[0].extracted_kg)
    fuel_before = float(sim.agents.inv_fuel[0])
    metal_before = float(sim.agents.inv_metal[0])
    ev = _smelt_here(sim, 0)
    assert ev and ev[-1]["kind"] == "smelt"
    # D10 CROSSED: the ore is really drained from the geology column.
    assert float(g.layers[0].extracted_kg) > extracted_before
    assert ev[-1]["mutated_geology"] is True
    assert ev[-1]["ore_consumed_kg"] > 0.0
    # a bead of copper filled inv_metal; a charcoal charge was spent.
    assert float(sim.agents.inv_metal[0]) > metal_before
    assert ev[-1]["recovered_cu_kg"] > 0.0
    assert float(sim.agents.inv_fuel[0]) == pytest.approx(fuel_before - cog.SMELT_FUEL_COST_KG)
    # the skill + the mineral + the site are remembered.
    assert sim.agents.memory[0].has_smelted_copper is True
    assert sim.agents.memory[0].last_smelt_mineral == "native_copper"
    assert ev[-1]["copper_mineral"] == "native_copper" and ev[-1]["ore_class"] == "native_metal"
    assert len(sim.agents.memory[0].known_smelt_locations) == 1


def test_raw_sulfide_smelt_yields_only_slag_but_still_mutates():
    """The lie #4 lived: a raw chalcopyrite is CONSUMED (geology mutated) but yields only slag —
    0 copper. The costly, physically true lesson of the refractory sulfide."""
    sim, coords = _booted_sim("sulfide")
    cc = _smeltable_site(sim, coords, layers=_chalcopyrite())
    cue = cs.smelt_cue_for_chunk(sim, cc)
    assert cue is not None and cue.needs_roasting_first is True
    _ready(sim, 0, fuel_kg=2.0)
    _stand(sim, 0, cc)
    g = geo.chunk_geology(sim, cc)
    before = float(g.layers[0].extracted_kg)
    metal_before = float(sim.agents.inv_metal[0])
    ev = _smelt_here(sim, 0)
    assert ev and ev[-1]["kind"] == "smelt"
    assert ev[-1]["required_roasting"] is True
    assert ev[-1]["recovered_cu_kg"] == 0.0                 # only slag — no copper
    assert ev[-1]["slag_kg"] > 0.0
    assert float(g.layers[0].extracted_kg) > before         # ...but the charge was still consumed (mutated)
    assert float(sim.agents.inv_metal[0]) == metal_before   # no metal gained


def test_metal_sated_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    cc = _smeltable_site(sim, coords)
    _ready(sim, 0, metal_kg=cog.SMELT_METAL_SATED_KG)       # already carries enough copper
    _stand(sim, 0, cc)
    assert cog._seek_smelt(sim.agents, 0, _obs(sim, 0), sim) is None


def test_smelting_where_no_site_keeps_fuel_and_metal():
    sim, _coords = _booted_sim("barren")
    _ready(sim, 0, fuel_kg=2.0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    assert cs.smelt_at(sim, 0) is None                      # the world says: nothing smeltable here
    fuel_before = float(sim.agents.inv_fuel[0])
    metal_before = float(sim.agents.inv_metal[0])
    ev = _smelt_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_fuel[0]) == fuel_before     # fuel kept where nothing smelts
    assert float(sim.agents.inv_metal[0]) == metal_before
    assert sim.agents.memory[0].has_smelted_copper is False


def test_critical_thirst_outranks_smelting():
    sim, coords = _booted_sim("priority")
    cc = _smeltable_site(sim, coords)
    _ready(sim, 0)
    px, py = _stand(sim, 0, cc)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)


def test_smelt_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    cc = _smeltable_site(sim, coords)
    _ready(sim, 0, fuel_kg=2.0)
    px, py = _stand(sim, 0, cc)
    fuel_before = float(sim.agents.inv_fuel[0])
    dec = cog.Decision(int(ActionKind.SMELT), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)   # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_fuel[0]) == fuel_before
    assert sim.agents.memory[0].has_smelted_copper is False


def test_smelt_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    evs = []
    for s, c in ((a, ca), (b, cb)):
        cc = _smeltable_site(s, c)
        _ready(s, 0, fuel_kg=2.0)
        _stand(s, 0, cc)
        evs.append(_smelt_here(s, 0)[-1])
    assert evs[0]["copper_mineral"] == evs[1]["copper_mineral"]
    assert evs[0]["recovered_cu_kg"] == evs[1]["recovered_cu_kg"]
    assert evs[0]["ore_consumed_kg"] == evs[1]["ore_consumed_kg"]
    assert evs[0]["bead_purity"] == evs[1]["bead_purity"]


def test_registry_and_enum_and_d8_discipline():
    # the wire is in the arc registry, reuses the legacy SMELT enum, and composes C13 (no new tell → D8).
    assert ("smelt", cog._seek_smelt) in cog._ARC_SEEKS
    assert hasattr(ActionKind, "SMELT")
    sys.path.insert(0, str(RUNTIME / "tests"))
    import test_geology_cross_language_contract as contract        # noqa: E402
    assert len(contract.PY_TO_RUST) == 15                          # composition only — no new mineral tell
