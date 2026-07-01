#!/usr/bin/env python3
"""P175 — The agent loop BLOOMs iron (D12 wire #19, 2026-07-01, consumes C17).

The 18th agent BEHAVIOUR that consumes the arc — and **the 2nd AGENT-DRIVEN MUTATION OF THE WORLD**, after
SMELT/C13. C13 ``copper_smelting`` crossed the D10 mutation frontier for copper (``smelt_at`` →
``geo.mine_at``); C17 ``iron_bloomery`` extends the same metallurgical sub-arc (ADR-0010) to iron — le
seuil de l'âge du fer. This wire lets a curious, survival-satisfied agent that has (a) discovered the
forced-draught furnace (``has_forced_draught``, C12 — only a refractory forced furnace clears the 1200 °C
bloomery regime), (b) LEARNED that the rusty iron-hat means iron (``"gossan" in prospected_ore_groups``,
C1/PROSPECT), and (c) carries a charcoal charge (``inv_fuel``, C4) REDUCE the oxide iron-hat ore underfoot:
the ore truly disappears from the ground and a SOLID spongy iron bloom fills ``inv_metal``. **D10 is
CROSSED here (the metallurgical sub-arc, ADR-0010).** Adds a new verb ``ActionKind.BLOOM``.

LE MENSONGE PHYSIQUE (vs C13): copper runs to a POURED bead; iron NEVER melts (1538 °C, out of reach) — the
bloom is a SOLID sponge that must be forged (C19), never poured. LE MENSONGE #8: the same rusty gossan (C1)
caps an oxide (hematite → sound iron), a sulfide (pyrite — reduce it raw and it is CONSUMED but yields only
slag; you must roast it first), or lead/zinc (galena/sphalerite → NO iron at all).
``best_bloomery_site_near(require_direct=True)`` routes to the oxide the agent can reduce NOW.

Discipline: COMPOSES C17 (which composes C12 + C1); the WIRE introduces NO new tell (``PY_TO_RUST`` stays
15 — D8). **MUTATING** (``geo.mine_at`` — D10 crossed, the metallurgical sub-arc ADR-0010). Fire-based (the
furnace): SMELT and BLOOM are both fire — the iron-age tail of the arc is structurally fire-bound.
Determinism: pure oracle + memoised; ``bloom_at`` mutates deterministically. Seed 0x1201 (the 1200 °C
bloomery threshold / iron age) + an injected oxide/sulfide/lead column (no lucky-seed dependency).

Checks
------
 1.  LIVE perceive→decide→act→remember: a ready agent on an oxide iron-hat ⇒ BLOOM: geology mutated,
     inv_metal filled with a SOLID bloom, the skill remembered, the event emitted.
 2.  The D10 crossing made explicit: the ore column's ``extracted_kg`` rises — the 2nd agent mutation.
 3.  Le mensonge #8: a raw sulfide (pyrite) is CONSUMED (geology mutated) but yields only slag (0 iron),
     and the agent is NOT locked out (has_bloomed_iron stays False).
 4.  « Le monde ne ment jamais » : a lead/zinc gossan yields NO iron and mutates nothing; blooming where
     nothing is reducible keeps fuel + metal.
 5.  Survival outranks blooming.
 6.  Same path as the real tick: ``sim.step()`` runs clean and the wire is live post-step.
 7.  Gate + determinism: no C17 ⇒ inert ; same seed+injection ⇒ bit-identical bloom.
 8.  Discipline: BLOOM∈ActionKind, memory fields, "bloom"∈registry, PY_TO_RUST==15, D10 crossed by design.
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
from engine import iron_bloomery as ib                              # noqa: E402
from engine.cognition import Observation, PerceivedTarget           # noqa: E402
from engine.agent import ActionKind, DriveKind                      # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_BLOOM = 0x1201
GRID = 12
_GRASS = 6
OUT = os.path.join(ROOT, "journals", "p175_iron_bloom_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:70s} {detail}")


def _build(seed: int = SEED_BLOOM, *, with_c17: bool = True):
    cfg = SimConfig(name="p175", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8))
    geo.install_geology(sim)
    if with_c17:
        ib.install_iron_bloomery(sim)
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


def _non_iron():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06, "galena": 0.05})]


def _put_chunk(sim, cc, layers, biome=_GRASS, w=0.0):
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


def _ready(sim, row, *, forced=True, prospected=True, fuel_kg=2.0, bloomed=False):
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
    sim.agents.thermal[row] = 0.05
    mem = sim.agents.memory[row]
    mem.known_bloom_locations.clear()
    mem.has_bloomed_iron = bool(bloomed)
    mem.last_bloom_mineral = None
    mem.last_bloom_iron_kg = 0.0
    mem.has_forced_draught = bool(forced)
    mem.has_built_kiln = True
    mem.has_made_fire = True
    mem.prospected_ore_groups = ["gossan"] if prospected else []
    mem.has_prospected_ore = bool(prospected)


def _obs(sim, row):
    a = sim.agents
    d = np.array([float(a.hunger[row]), float(a.thirst[row]), float(a.sleep[row]),
                  float(a.fatigue[row]), float(a.thermal[row]), float(a.pain[row]),
                  float(a.stress[row]), float(a.loneliness[row])], dtype=np.float32)
    return Observation(row=int(row), pos=(float(a.pos[row, 0]), float(a.pos[row, 1]), 0.0),
                       drives=d, vitality=1.0, nearest={}, near_agents=[],
                       dominant_drive=cog._dominant_drive(d), tick=0,
                       reproduction_readiness=0.0)


def _bloom_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    return _ORIG_APPLY(sim.agents, row, cog.Decision(int(ActionKind.BLOOM), px, py, 0.5),
                       sim.streamer, sim.tick, sim=sim)


def main() -> int:
    print("=" * 84)
    print("P175 — iron bloomery: the agent loop CONSUMES C17 (the 2ᵉ agent-driven MUTATION — "
          "l'âge du fer, ADR-0010)")
    print("=" * 84)

    # 1 + 2 — LIVE perceive→decide→act→remember + the D10 crossing (geology mutated)
    sim, coords = _build()
    cc = _site(sim, coords)
    cue = ib.bloom_cue_for_chunk(sim, cc)
    _ready(sim, 0)
    _stand(sim, 0, cc)
    seek = cog._seek_bloom(sim.agents, 0, _obs(sim, 0), sim)
    decided = seek.action if seek is not None else None
    g = geo.chunk_geology(sim, cc)
    extracted_before = float(g.layers[0].extracted_kg)
    metal_before = float(sim.agents.inv_metal[0])
    ev = _bloom_here(sim, 0)
    mem = sim.agents.memory[0]
    extracted_after = float(g.layers[0].extracted_kg)
    print(f"  seed {hex(SEED_BLOOM)}: site={cc} mineral={cue.iron_mineral if cue else None} "
          f"reducible_now={cue.reducible_now if cue else None}")
    print(f"        decide={ActionKind(decided).name if decided is not None else None} ; "
          f"extracted {extracted_before:.4f}→{extracted_after:.4f} ; "
          f"inv_metal {metal_before:.4f}→{float(sim.agents.inv_metal[0]):.4f} ; "
          f"event={ev[-1]['kind'] if ev else None}")
    check("1 — LIVE perceive→decide→act→remember : ready agent BLOOMs (bouchée D12 #19, l'âge du fer)",
          decided == int(ActionKind.BLOOM) and ev and ev[-1]["kind"] == "bloom"
          and ev[-1]["is_solid_bloom"] is True
          and float(sim.agents.inv_metal[0]) > metal_before and mem.has_bloomed_iron is True
          and mem.last_bloom_mineral == "hematite" and len(mem.known_bloom_locations) == 1,
          f"iron_gained={float(sim.agents.inv_metal[0]) - metal_before:.4f} solid={ev[-1]['is_solid_bloom'] if ev else None}")
    check("2 — le franchissement de D10 (2ᵉ) : la colonne géologique est MUTÉE (extracted_kg ↑) — le fer",
          extracted_after > extracted_before and ev and ev[-1]["mutated_geology"] is True
          and ev[-1]["ore_consumed_kg"] > 0.0,
          f"Δextracted={extracted_after - extracted_before:.4f} ore_consumed={ev[-1]['ore_consumed_kg'] if ev else None}")

    # 3 — the lie #8: raw sulfide consumed → only slag, geology still mutated, NOT locked out
    ss, sc = _build()
    ss_coord = _site(ss, sc, layers=_sulfide_iron())
    scue = ib.bloom_cue_for_chunk(ss, ss_coord)
    _ready(ss, 0)
    _stand(ss, 0, ss_coord)
    gs = geo.chunk_geology(ss, ss_coord)
    before_s = float(gs.layers[0].extracted_kg)
    metal_before_s = float(ss.agents.inv_metal[0])
    evs = _bloom_here(ss, 0)
    ok3 = (scue is not None and scue.needs_roasting_first is True and evs and evs[-1]["kind"] == "bloom"
           and evs[-1]["required_roasting"] is True and evs[-1]["bloom_iron_kg"] == 0.0
           and evs[-1]["slag_kg"] > 0.0 and float(gs.layers[0].extracted_kg) > before_s
           and float(ss.agents.inv_metal[0]) == metal_before_s
           and ss.agents.memory[0].has_bloomed_iron is False)
    check("3 — le mensonge #8 : un sulfure cru est CONSOMMÉ (géologie mutée) mais ne rend que scorie (non-verrouillé)",
          ok3, f"iron={evs[-1]['bloom_iron_kg'] if evs else None} slag={evs[-1]['slag_kg'] if evs else None} "
               f"locked_out={ss.agents.memory[0].has_bloomed_iron}")

    # 4 — le monde ne ment jamais : lead/zinc gossan → no iron, no mutation ; barren → fuel/metal kept
    sb, scb = _build()
    nb_coord = _site(sb, scb, layers=_non_iron())
    _ready(sb, 0, fuel_kg=2.0)
    _stand(sb, 0, nb_coord)
    gnb = geo.chunk_geology(sb, nb_coord)
    nb_before = float(gnb.layers[0].extracted_kg)
    no_iron = ib.bloom_cue_for_chunk(sb, nb_coord) is None and ib.bloom_at(sb, 0) is None
    ev_nb = _bloom_here(sb, 0)
    non_iron_ok = (no_iron and ev_nb == [] and float(gnb.layers[0].extracted_kg) == nb_before)
    sb2, _cb2 = _build()
    _ready(sb2, 0, fuel_kg=2.0)
    far = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sb2.agents.pos[0, 0] = far
    sb2.agents.pos[0, 1] = far
    fuel_b = float(sb2.agents.inv_fuel[0])
    metal_b = float(sb2.agents.inv_metal[0])
    evb = _bloom_here(sb2, 0)
    barren_ok = (ib.bloom_at(sb2, 0) is None and evb == []
                 and float(sb2.agents.inv_fuel[0]) == fuel_b
                 and float(sb2.agents.inv_metal[0]) == metal_b)
    check("4 — le monde ne ment jamais : plomb/zinc ⇒ 0 fer + rien muté ; rien à réduire ⇒ fuel+métal gardés",
          non_iron_ok and barren_ok, f"non_iron={non_iron_ok} barren={barren_ok}")

    # 5 — survival outranks blooming
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
    check("5 — survie > fonte : un agent assoiffé (eau en vue) BOIT, ne réduit pas le fer",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 6 — same path as the real tick
    st, ct = _build()
    _site(st, ct)
    step_ok = True
    try:
        st.step()
    except Exception as exc:                    # pragma: no cover
        step_ok = False
        print(f"        sim.step() raised: {exc}")
    # after a real tick, re-inject (step may have streamed/cleared) and confirm the wire is live
    cct = _site(st, [c for c in ct if st.streamer.cache.get(c) is not None] or ct)
    _ready(st, 0)
    _stand(st, 0, cct)
    s = cog._seek_bloom(st.agents, 0, _obs(st, 0), st)
    seek_act = int(s.action) if s is not None else None
    check("6 — même chemin que le tick réel : sim.step() OK + le wire bloom vivant (BLOOM/WALK_TO)",
          step_ok and seek_act in (int(ActionKind.BLOOM), int(ActionKind.WALK_TO)),
          f"step_ok={step_ok} seek={ActionKind(seek_act).name if seek_act is not None else 'None'}")

    # 7 — gate (no C17 → inert) + determinism (same injected site → same bloom)
    sng, cng = _build(with_c17=False)
    _ready(sng, 0)
    _stand(sng, 0, cng[len(cng) // 2])
    gate_off = (getattr(sng, "_iron_bloom_cue_cache", None) is None
                and cog._seek_bloom(sng.agents, 0, _obs(sng, 0), sng) is None)
    blooms = []
    for _ in range(2):
        d, cd = _build()
        ccd = _site(d, cd)
        _ready(d, 0, fuel_kg=2.0)
        _stand(d, 0, ccd)
        e = _bloom_here(d, 0)
        blooms.append(e[-1]["bloom_iron_kg"] if e else None)
    det = blooms[0] is not None and blooms[0] == blooms[1]
    check("7 — gate (pas de C17 ⇒ inerte) + déterminisme même-seed (loupe bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det} blooms={blooms}")

    # 8 — discipline
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    in_enum = hasattr(ActionKind, "BLOOM") and int(ActionKind.BLOOM) == 35
    mem_fields = all(hasattr(sim.agents.memory[0], f) for f in
                     ("has_bloomed_iron", "last_bloom_mineral", "last_bloom_iron_kg",
                      "known_bloom_locations"))
    in_registry = ("bloom", cog._seek_bloom) in cog._ARC_SEEKS
    orthogonal = ("smelt", cog._seek_smelt) in cog._ARC_SEEKS
    d8_ok = in_enum and mem_fields and in_registry and orthogonal and len(contract.PY_TO_RUST) == 15
    check("8 — discipline : BLOOM∈ActionKind, mémoire bloom, registre (∥ smelt), PY_TO_RUST==15 (D8), D10 franchi",
          d8_ok, f"enum={in_enum} mem={mem_fields} registry={in_registry} orth={orthogonal} "
                 f"py_to_rust={len(contract.PY_TO_RUST)}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p175_iron_bloom_loop", "seed": SEED_BLOOM,
                   "agent0_last_bloom_mineral": sim.agents.memory[0].last_bloom_mineral,
                   "agent0_inv_metal": float(sim.agents.inv_metal[0]),
                   "results": results, "passed": passed, "total": total},
                  f, ensure_ascii=False)
        f.write("\n")

    print()
    if passed == total:
        print(f"RESULT: PASS — {passed}/{total} checks. Journal: {OUT}")
        return 0
    print(f"RESULT: FAIL — {passed}/{total} checks passed.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
