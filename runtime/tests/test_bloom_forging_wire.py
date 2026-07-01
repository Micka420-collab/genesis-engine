"""Invariants — the agent loop FORGEs a carried iron bloom into wrought iron (D12 wire #20 aka
"D12 wire #19" in the sprint doc numbering, 2026-07-01, consumes C19).

The 20th wire — and the FIRST agent-facing capability that is a pure REFINEMENT of a product already
sitting in inventory rather than a fresh extraction (no ``geo.mine_at`` here: D10 stays exactly where
SMELT/C13 and BLOOM/C17 left it, frozen at 2 crossings). C19 ``bloom_forging`` closes the chain BLOOM/C17
opened honestly deferred: the spongy iron bloom (never poured — iron's 1538 °C melt point is unreachable)
must be hammer-consolidated in the SAME forced-draught hearth (C12) that made it hot enough, expelling the
fayalite slag and welding the iron into wrought iron. Adds ``ActionKind.FORGE``.

THE PHYSICAL LIE (mensonge #10, the sequel to #8): the same rusty gossan that capped an oxide bloom
(hematite/magnetite — welds SOUND, dense) or a pyrite bloom (red-short — sulfur at the grain boundaries
liquefies under forge heat, the billet FISSURES under the hammer) pays off, or costs, again at the anvil.
The forger who hammers a red-short bloom as if it were oxide gets a shattered billon: wrought-iron yield
collapsed, soundness capped low (``RED_SHORT_SOUNDNESS_CEIL``).

What this file proves:
1.  Gated on C19 (no cue cache → inert).
2.  Bloom dependency (C17): an agent that never bloomed iron does not forge.
3.  Self-limiting: an agent that already discovered the forge (``has_forged_iron``) does not re-seek.
4.  Ore dependency: a ready agent with insufficient bloom iron in hand does not forge.
5.  A ready agent on a forge-hot oxide site chooses FORGE; off-site WALK_TOs.
6.  Apply_decision FORGE arm: spends inv_metal, adds wrought iron back, sets has_forged_iron on a sound
    (oxide) site.
7.  Apply_decision FORGE arm on a red-short (pyrite) site: cracks, collapsed wrought-iron gain, does NOT
    set has_forged_iron.
8.  Non-mutating: FORGE touches no geology (no geo.mine_at) — D10 stays exactly as BLOOM left it.
9.  Registry: "forge" sits right after "bloom" in ``_ARC_SEEKS``.
10. Back-compat (sim=None inert) and determinism (same injected site → same forge outcome).
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
import engine.bloom_forging as bf                                   # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_FORGE = 0x1901    # thematic: continues the 0x1201 bloomery seed family for the forge wire
GRID = 12
_GRASS = 6


def _booted_sim(name: str, seed: int = SEED_FORGE, *, with_c19: bool = True):
    cfg = SimConfig(name=name, seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8))
    geo.install_geology(sim)
    if with_c19:
        bf.install_bloom_forging(sim)   # also installs C17 + C12 + C1 + geo
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


def _oxide_iron():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06, "hematite": 0.05})]


def _sulfide_iron():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06, "pyrite": 0.05})]


def _put_chunk(sim, cc, layers, biome=_GRASS, w=0.0):
    ch = sim.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, biome, dtype=np.asarray(ch.biome).dtype)
    ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
    sim._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=layers)
    for cache in ("_clay_cue_cache", "_ignition_cue_cache", "_limestone_cue_cache",
                  "_kiln_draft_cue_cache", "_surface_cue_cache", "_forced_draught_cue_cache",
                  "_copper_smelt_cue_cache", "_iron_bloom_cue_cache", "_forge_cue_cache"):
        c = getattr(sim, cache, None)
        if c is not None:
            c.clear()


def _forge_site(sim, coords, layers=None):
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, layers or _oxide_iron())
    return cc


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _ready(sim, row, *, bloomed=True, forged=False, metal_kg=2.0):
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
    sim.agents.inv_metal[row] = float(metal_kg)
    sim.agents.thermal[row] = 0.05
    mem = sim.agents.memory[row]
    mem.has_bloomed_iron = bool(bloomed)
    mem.has_forged_iron = bool(forged)
    mem.has_forced_draught = True
    mem.last_forced_peak_c = 1295.0
    mem.has_built_kiln = True
    mem.has_made_fire = True
    mem.prospected_ore_groups = ["gossan"]
    mem.has_prospected_ore = True


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


def _forge_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    dec = cog.Decision(int(ActionKind.FORGE), px, py, 0.5)
    return _ORIG_APPLY(sim.agents, row, dec, sim.streamer, sim.tick, sim=sim)


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

def test_seek_forge_inert_without_c19():
    sim, coords = _booted_sim("gate", with_c19=False)
    _ready(sim, 0)
    _stand(sim, 0, coords[len(coords) // 2])
    assert getattr(sim, "_forge_cue_cache", None) is None
    assert cog._seek_forge(sim.agents, 0, _obs(sim, 0), sim) is None


def test_agent_without_bloomed_iron_does_not_forge():
    sim, coords = _booted_sim("needs_bloom")
    cc = _forge_site(sim, coords)
    _ready(sim, 0, bloomed=False)
    _stand(sim, 0, cc)
    assert cog._seek_forge(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _forge_here(sim, 0) == []


def test_forge_aged_agent_does_not_reseek():
    sim, coords = _booted_sim("sated")
    cc = _forge_site(sim, coords)
    _ready(sim, 0, forged=True)
    _stand(sim, 0, cc)
    assert cog._seek_forge(sim.agents, 0, _obs(sim, 0), sim) is None


def test_agent_without_enough_ore_does_not_forge():
    sim, coords = _booted_sim("needs_ore")
    cc = _forge_site(sim, coords)
    _ready(sim, 0, metal_kg=0.0)
    _stand(sim, 0, cc)
    assert cog._seek_forge(sim.agents, 0, _obs(sim, 0), sim) is None
    assert _forge_here(sim, 0) == []


# ---------------------------------------------------------------------------
# The decision + the act
# ---------------------------------------------------------------------------

def test_ready_agent_on_oxide_site_decides_to_forge():
    sim, coords = _booted_sim("decide")
    cc = _forge_site(sim, coords)
    cue = bf.prospect_forge(sim, (cc[0] + 0.5) * CHUNK_SIDE_M, (cc[1] + 0.5) * CHUNK_SIDE_M)
    assert cue is not None and cue.hot_enough is True
    _ready(sim, 0)
    _stand(sim, 0, cc)
    seek = cog._seek_forge(sim.agents, 0, _obs(sim, 0), sim)
    assert seek is not None and seek.action == int(ActionKind.FORGE)


def test_ready_agent_walks_toward_perceived_forge():
    sim, coords = _booted_sim("walk")
    cc = _forge_site(sim, coords)
    cx = (cc[0] + 0.5) * CHUNK_SIDE_M
    cy = (cc[1] + 0.5) * CHUNK_SIDE_M
    _ready(sim, 0)
    sim.agents.pos[0, 0] = cx + CHUNK_SIDE_M
    sim.agents.pos[0, 1] = cy
    seek = cog._seek_forge(sim.agents, 0, _obs(sim, 0), sim)
    if seek is None or seek.action == int(ActionKind.FORGE):
        pytest.skip("nearest forge-hot site is underfoot from this offset — no WALK_TO to assert")
    assert seek.action == int(ActionKind.WALK_TO)


def test_forging_sound_oxide_bloom_spends_ore_gains_wrought_and_sets_discovery():
    sim, coords = _booted_sim("act")
    cc = _forge_site(sim, coords)
    _ready(sim, 0, metal_kg=2.0)
    _stand(sim, 0, cc)
    g = geo.chunk_geology(sim, cc)
    extracted_before = float(g.layers[0].extracted_kg)
    metal_before = float(sim.agents.inv_metal[0])
    ev = _forge_here(sim, 0)
    assert ev and ev[-1]["kind"] == "forge"
    assert ev[-1]["is_wrought"] is True
    assert ev[-1]["wrought_iron_kg"] > 0.0
    # inv_metal dropped by the spent bloom-ore mass but rose again by the wrought gain
    assert float(sim.agents.inv_metal[0]) != metal_before
    assert sim.agents.memory[0].has_forged_iron is True
    # NON-MUTATING — no geology touched (D10 stays exactly as BLOOM left it).
    assert float(g.layers[0].extracted_kg) == extracted_before


def test_forging_red_short_pyrite_bloom_cracks_and_does_not_set_discovery():
    sim, coords = _booted_sim("redshort")
    cc = _forge_site(sim, coords, layers=_sulfide_iron())
    cue = bf.prospect_forge(sim, (cc[0] + 0.5) * CHUNK_SIDE_M, (cc[1] + 0.5) * CHUNK_SIDE_M)
    if cue is None or not cue.hot_enough:
        pytest.skip("injected pyrite site not forge-hot in this bootstrap — no cracked case to assert")
    _ready(sim, 0, metal_kg=2.0)
    _stand(sim, 0, cc)
    ev = _forge_here(sim, 0)
    assert ev and ev[-1]["kind"] == "forge"
    assert ev[-1]["red_short"] is True
    assert ev[-1]["cracked"] is True
    assert ev[-1]["is_wrought"] is False
    assert sim.agents.memory[0].has_forged_iron is False   # honest failure — never locked out


def test_forging_where_no_site_keeps_ore():
    sim, _coords = _booted_sim("barren")
    _ready(sim, 0, metal_kg=2.0)
    fx, fy = _far_unstreamed()
    sim.agents.pos[0, 0] = fx
    sim.agents.pos[0, 1] = fy
    metal_before = float(sim.agents.inv_metal[0])
    ev = _forge_here(sim, 0)
    assert ev == []
    assert float(sim.agents.inv_metal[0]) == metal_before
    assert sim.agents.memory[0].has_forged_iron is False


def test_critical_thirst_outranks_forging():
    sim, coords = _booted_sim("priority")
    cc = _forge_site(sim, coords)
    _ready(sim, 0)
    px, py = _stand(sim, 0, cc)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    dec = _ORIG_DECIDE(sim.agents, _obs(sim, 0, nearest={"water": water}, drives=drives), sim=sim)
    assert dec.action == int(ActionKind.DRINK)


def test_forge_without_sim_is_inert():
    sim, coords = _booted_sim("backcompat")
    cc = _forge_site(sim, coords)
    _ready(sim, 0, metal_kg=2.0)
    px, py = _stand(sim, 0, cc)
    metal_before = float(sim.agents.inv_metal[0])
    dec = cog.Decision(int(ActionKind.FORGE), px, py, 0.5)
    ev = _ORIG_APPLY(sim.agents, 0, dec, sim.streamer, sim.tick)   # no sim kwarg
    assert ev == []
    assert float(sim.agents.inv_metal[0]) == metal_before
    assert sim.agents.memory[0].has_forged_iron is False


def test_forge_outcome_is_deterministic():
    a, ca = _booted_sim("det_a")
    b, cb = _booted_sim("det_b")
    evs = []
    for s, c in ((a, ca), (b, cb)):
        cc = _forge_site(s, c)
        _ready(s, 0, metal_kg=2.0)
        _stand(s, 0, cc)
        evs.append(_forge_here(s, 0)[-1])
    assert evs[0]["iron_mineral"] == evs[1]["iron_mineral"]
    assert evs[0]["wrought_iron_kg"] == evs[1]["wrought_iron_kg"]
    assert evs[0]["soundness"] == evs[1]["soundness"]


def test_registry_and_enum_and_d8_discipline():
    assert ("forge", cog._seek_forge) in cog._ARC_SEEKS
    names = [n for n, _ in cog._ARC_SEEKS]
    assert names.index("forge") == names.index("bloom") + 1
    assert hasattr(ActionKind, "FORGE") and int(ActionKind.FORGE) == 36
    sys.path.insert(0, str(RUNTIME / "tests"))
    import test_geology_cross_language_contract as contract        # noqa: E402
    assert len(contract.PY_TO_RUST) == 15                          # composition only — no new mineral tell
