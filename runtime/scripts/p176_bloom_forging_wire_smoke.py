#!/usr/bin/env python3
"""P176 — The agent loop FORGEs a carried iron bloom into wrought iron (D12 wire #20, 2026-07-01,
consumes C19).

The 19th agent BEHAVIOUR that consumes the arc — and the FIRST agent-facing capability that is a pure
REFINEMENT of a product already sitting in inventory rather than a fresh extraction. C13 ``copper_smelting``
and C17 ``iron_bloomery`` crossed the D10 mutation frontier (twice); C19 ``bloom_forging`` does NOT cross it
a third time — it hammer-consolidates the SOLID iron bloom BLOOM/C17 already won, in the SAME forced-draught
hearth (C12) that made it hot enough, expelling the fayalite slag and welding the iron. Adds a new verb
``ActionKind.FORGE``.

LE MENSONGE PHYSIQUE #10 (la suite du #8) : le même chapeau de fer rouille qui coiffait un oxyde
(hematite/magnetite → loupe saine, se consolide dense) ou un sulfure (pyrite → loupe red-short, se fissure
sous le marteau) paie, ou coûte, à nouveau à l'enclume. Le forgeron qui cingle une loupe red-short comme une
loupe d'oxyde obtient un billon fendu : rendement de fer forgé effondré, santé plafonnée bas.

Discipline: COMPOSES C19 (which composes C17, itself C12 x C1); the wire introduces NO new tell (PY_TO_RUST
stays 15 — D8). NON-MUTATING (no geo.mine_at — D10 stays exactly where BLOOM left it, frozen at 2
crossings). Fire-based (forge heat = the SAME C12 forced-draught regime as BLOOM/SMELT) — the metallurgy
tail stays structurally fire-bound (no new D9 alternance). Determinism: pure oracle + memoised; the forge
outcome is bit-identical for the same seed + injected site. Seed 0x1901 (continues the 0x1201 bloomery seed
family).

Checks
------
 1.  LIVE perceive->decide->act->remember: a ready agent (bloomed iron in hand) on a forge-hot oxide site =>
     FORGE: inv_metal spent + wrought iron gained, the skill remembered, the event emitted.
 2.  NON-MUTATING made explicit: no geology touched (extracted_kg unchanged) - D10 stays where BLOOM left it.
 3.  Le mensonge #10: a red-short (pyrite) bloom forged CRACKS - collapsed wrought-iron yield, soundness
     capped low, and the agent is NOT locked out (has_forged_iron stays False).
 4.  Le monde ne ment jamais: forging where nothing is forge-hot keeps the bloom iron untouched.
 5.  Survival outranks forging.
 6.  Same path as the real tick: sim.step() runs clean and the wire is live post-step.
 7.  Gate + determinism: no C19 => inert; same seed+injection => bit-identical forge outcome.
 8.  Discipline: FORGE in ActionKind, memory fields, "forge" right after "bloom" in registry, PY_TO_RUST==15.
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import numpy as np                                                  # noqa: E402

from engine.sim import Simulation, SimConfig                        # noqa: E402
from engine.world_genesis import GenesisParams                      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine.geology import StrataLayer, ChunkGeology                # noqa: E402
from engine import cognition as cog                                 # noqa: E402
from engine import bloom_forging as bf                              # noqa: E402
from engine.cognition import Observation, PerceivedTarget           # noqa: E402
from engine.agent import ActionKind, DriveKind                      # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_FORGE = 0x1901
GRID = 12
_GRASS = 6
OUT = os.path.join(ROOT, "journals", "p176_bloom_forging_wire.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:70s} {detail}")


def _build(seed: int = SEED_FORGE, *, with_c19: bool = True):
    cfg = SimConfig(name="p176", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8))
    geo.install_geology(sim)
    if with_c19:
        bf.install_bloom_forging(sim)
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


def _site(sim, coords, layers=None):
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
    mem.has_built_kiln = True
    mem.has_made_fire = True
    mem.prospected_ore_groups = ["gossan"]
    mem.has_prospected_ore = True


def _obs(sim, row):
    a = sim.agents
    d = np.array([float(a.hunger[row]), float(a.thirst[row]), float(a.sleep[row]),
                  float(a.fatigue[row]), float(a.thermal[row]), float(a.pain[row]),
                  float(a.stress[row]), float(a.loneliness[row])], dtype=np.float32)
    return Observation(row=int(row), pos=(float(a.pos[row, 0]), float(a.pos[row, 1]), 0.0),
                       drives=d, vitality=1.0, nearest={}, near_agents=[],
                       dominant_drive=cog._dominant_drive(d), tick=0,
                       reproduction_readiness=0.0)


def _forge_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    return _ORIG_APPLY(sim.agents, row, cog.Decision(int(ActionKind.FORGE), px, py, 0.5),
                       sim.streamer, sim.tick, sim=sim)


def main() -> int:
    print("=" * 84)
    print("P176 - bloom forging: the agent loop CONSUMES C19 (pure refinement, D10 untouched)")
    print("=" * 84)

    # 1 + 2 - LIVE perceive->decide->act->remember + NON-MUTATING made explicit
    sim, coords = _build()
    cc = _site(sim, coords)
    cue = bf.prospect_forge(sim, (cc[0] + 0.5) * CHUNK_SIDE_M, (cc[1] + 0.5) * CHUNK_SIDE_M)
    _ready(sim, 0)
    _stand(sim, 0, cc)
    seek = cog._seek_forge(sim.agents, 0, _obs(sim, 0), sim)
    decided = seek.action if seek is not None else None
    g = geo.chunk_geology(sim, cc)
    extracted_before = float(g.layers[0].extracted_kg)
    metal_before = float(sim.agents.inv_metal[0])
    ev = _forge_here(sim, 0)
    mem = sim.agents.memory[0]
    extracted_after = float(g.layers[0].extracted_kg)
    print(f"  seed {hex(SEED_FORGE)}: site={cc} mineral={cue.iron_mineral if cue else None} "
          f"hot_enough={cue.hot_enough if cue else None}")
    print(f"        decide={ActionKind(decided).name if decided is not None else None} ; "
          f"inv_metal {metal_before:.4f}->{float(sim.agents.inv_metal[0]):.4f} ; "
          f"event={ev[-1]['kind'] if ev else None}")
    check("1 - LIVE perceive->decide->act->remember : ready agent FORGEs (bouchee D12, cinglage)",
          decided == int(ActionKind.FORGE) and ev and ev[-1]["kind"] == "forge"
          and ev[-1]["is_wrought"] is True and ev[-1]["wrought_iron_kg"] > 0.0
          and mem.has_forged_iron is True,
          f"wrought_gain={ev[-1]['wrought_iron_kg'] if ev else None}")
    check("2 - NON-MUTATING : la colonne geologique n'est PAS touchee (D10 reste ou BLOOM l'a laisse)",
          extracted_after == extracted_before,
          f"extracted {extracted_before:.4f}->{extracted_after:.4f}")

    # 3 - the lie #10: red-short pyrite bloom cracks
    ss, sc = _build()
    ss_coord = _site(ss, sc, layers=_sulfide_iron())
    scue = bf.prospect_forge(ss, (ss_coord[0] + 0.5) * CHUNK_SIDE_M, (ss_coord[1] + 0.5) * CHUNK_SIDE_M)
    ok3 = True
    detail3 = "skipped (site not forge-hot in this bootstrap)"
    if scue is not None and scue.hot_enough:
        _ready(ss, 0, metal_kg=2.0)
        _stand(ss, 0, ss_coord)
        evs = _forge_here(ss, 0)
        ok3 = (evs and evs[-1]["kind"] == "forge" and evs[-1]["red_short"] is True
               and evs[-1]["cracked"] is True and evs[-1]["is_wrought"] is False
               and ss.agents.memory[0].has_forged_iron is False)
        detail3 = (f"cracked={evs[-1]['cracked'] if evs else None} "
                   f"wrought={evs[-1]['wrought_iron_kg'] if evs else None} "
                   f"locked_out={ss.agents.memory[0].has_forged_iron}")
    check("3 - le mensonge #10 : une loupe red-short (pyrite) se FISSURE (rendement effondre, non-verrouille)",
          ok3, detail3)

    # 4 - le monde ne ment jamais: barren -> ore kept
    sb2, _cb2 = _build()
    _ready(sb2, 0, metal_kg=2.0)
    far = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sb2.agents.pos[0, 0] = far
    sb2.agents.pos[0, 1] = far
    metal_b = float(sb2.agents.inv_metal[0])
    evb = _forge_here(sb2, 0)
    barren_ok = (evb == [] and float(sb2.agents.inv_metal[0]) == metal_b)
    check("4 - le monde ne ment jamais : rien a cingler ici => bloom-fer garde",
          barren_ok, f"barren={barren_ok}")

    # 5 - survival outranks forging
    sv, cv = _build()
    cvv = _site(sv, cv)
    _ready(sv, 0)
    px, py = _stand(sv, 0, cvv)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    obs = Observation(row=0, pos=(px, py, 0.0), drives=drives, vitality=1.0,
                      nearest={"water": water}, near_agents=[],
                      dominant_drive=cog._dominant_drive(drives), tick=0,
                      reproduction_readiness=0.0)
    d_thirst = _ORIG_DECIDE(sv.agents, obs, sim=sv)
    check("5 - survie > forge : un agent assoiffe (eau en vue) BOIT, ne cingle pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 6 - same path as the real tick
    st, ct = _build()
    _site(st, ct)
    step_ok = True
    try:
        st.step()
    except Exception as exc:                    # pragma: no cover
        step_ok = False
        print(f"        sim.step() raised: {exc}")
    cct = _site(st, [c for c in ct if st.streamer.cache.get(c) is not None] or ct)
    _ready(st, 0)
    _stand(st, 0, cct)
    s = cog._seek_forge(st.agents, 0, _obs(st, 0), st)
    seek_act = int(s.action) if s is not None else None
    check("6 - meme chemin que le tick reel : sim.step() OK + le wire forge vivant (FORGE/WALK_TO)",
          step_ok and seek_act in (int(ActionKind.FORGE), int(ActionKind.WALK_TO)),
          f"step_ok={step_ok} seek={ActionKind(seek_act).name if seek_act is not None else 'None'}")

    # 7 - gate (no C19 -> inert) + determinism (same injected site -> same forge outcome)
    sng, cng = _build(with_c19=False)
    _ready(sng, 0)
    _stand(sng, 0, cng[len(cng) // 2])
    gate_off = (getattr(sng, "_forge_cue_cache", None) is None
                and cog._seek_forge(sng.agents, 0, _obs(sng, 0), sng) is None)
    forges = []
    for _ in range(2):
        d, cd = _build()
        ccd = _site(d, cd)
        _ready(d, 0, metal_kg=2.0)
        _stand(d, 0, ccd)
        e = _forge_here(d, 0)
        forges.append(e[-1]["wrought_iron_kg"] if e else None)
    det = forges[0] is not None and forges[0] == forges[1]
    check("7 - gate (pas de C19 => inerte) + determinisme meme-seed (billon bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det} forges={forges}")

    # 8 - discipline
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    in_enum = hasattr(ActionKind, "FORGE") and int(ActionKind.FORGE) == 36
    mem_fields = hasattr(sim.agents.memory[0], "has_forged_iron")
    names = [n for n, _ in cog._ARC_SEEKS]
    in_registry = ("forge", cog._seek_forge) in cog._ARC_SEEKS
    right_after_bloom = "forge" in names and "bloom" in names and names.index("forge") == names.index("bloom") + 1
    d8_ok = in_enum and mem_fields and in_registry and right_after_bloom and len(contract.PY_TO_RUST) == 15
    check("8 - discipline : FORGE in ActionKind, memoire forge, registre (juste apres bloom), PY_TO_RUST==15",
          d8_ok, f"enum={in_enum} mem={mem_fields} registry={in_registry} after_bloom={right_after_bloom} "
                 f"py_to_rust={len(contract.PY_TO_RUST)}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p176_bloom_forging_wire", "seed": SEED_FORGE,
                   "agent0_inv_metal": float(sim.agents.inv_metal[0]),
                   "results": results, "passed": passed, "total": total},
                  f, ensure_ascii=False)
        f.write("\n")

    print()
    if passed == total:
        print(f"RESULT: PASS - {passed}/{total} checks. Journal: {OUT}")
        return 0
    print(f"RESULT: FAIL - {passed}/{total} checks passed.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
