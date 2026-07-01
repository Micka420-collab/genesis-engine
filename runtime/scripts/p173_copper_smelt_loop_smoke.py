#!/usr/bin/env python3
"""P173 — The agent loop SMELTs copper (D12 wire #18, 2026-07-01, consumes C13).

The 17th agent BEHAVIOUR that consumes the arc — and **THE FIRST AGENT-DRIVEN MUTATION OF THE WORLD**.
Through 17 wires the loop only ever read / gathered / transformed things the agent CARRIED; the geology
column was never touched (the D10 mutation frontier stayed frozen). C13 ``copper_smelting`` exposed
``smelt_at`` — the one mutating entry point of the C1→C13 arc (it drains ore via ``geo.mine_at``). This
wire lets a curious, survival-satisfied agent that has (a) discovered the forced-draught furnace
(``has_forced_draught``, C12), (b) LEARNED green==copper (``"copper" in prospected_ore_groups``, C1 —
wire #17's payoff), and (c) carries a charcoal charge (``inv_fuel``, C4) SMELT the copper ore underfoot:
the ore truly disappears from the ground and a bead of metal fills ``inv_metal``. **D10 is CROSSED
here, by design (ADR-0010).** Reuses the legacy ``ActionKind.SMELT`` (made honest, as C3 did for DRINK).

LE MENSONGE RENDU VISIBLE #4 (le mensonge métallurgique, vécu): the SAME green tell (C1) covers native
copper (melts to a bead directly) AND chalcopyrite (a refractory sulfide — smelt it raw and it is
CONSUMED but yields only slag; you must roast it first). ``best_smelt_site_near`` prefers the copper
actually recoverable — the agent learns to smelt the native green directly.

Discipline: COMPOSES C13 (which composes C12 + C1); the WIRE introduces NO new tell (``PY_TO_RUST`` stays
15 — D8). **MUTATING** (``geo.mine_at`` — D10 crossed, the designed payoff of PROSPECT). Fire-based (the
furnace) → D9 alternance 0→1 after the non-fire PROSPECT. Determinism: pure oracle + memoised;
``smelt_at`` mutates deterministically. Seed 0xC13 + an injected native/sulfide column (no lucky-seed
dependency — the same recipe test_copper_smelting uses).

Checks
------
 1.  LIVE perceive→decide→act→remember: a ready agent on a native-copper site ⇒ SMELT: geology mutated,
     inv_metal filled, the skill remembered, the event emitted.
 2.  The D10 crossing made explicit: the ore column's ``extracted_kg`` rises — the FIRST agent mutation.
 3.  Le mensonge #4: a raw sulfide is CONSUMED (geology mutated) but yields only slag (0 copper).
 4.  « Le monde ne ment jamais » : smelting where nothing is smeltable keeps fuel + metal, mutates nothing.
 5.  Survival outranks smelting.
 6.  Same path as the real tick: ``sim.step()`` runs clean and the wire is live post-step.
 7.  Gate + determinism: no C13 ⇒ inert ; same seed+injection ⇒ bit-identical bead.
 8.  Discipline: SMELT∈ActionKind, memory fields, "smelt"∈registry, PY_TO_RUST==15, D10 crossed by design.
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
from engine import copper_smelting as cs                            # noqa: E402
from engine.cognition import Observation, PerceivedTarget           # noqa: E402
from engine.agent import ActionKind, DriveKind                      # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_SMELT = 0xC13
GRID = 12
_GRASS = 6
OUT = os.path.join(ROOT, "journals", "p173_copper_smelt_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:70s} {detail}")


def _build(seed: int = SEED_SMELT, *, with_c13: bool = True):
    cfg = SimConfig(name="p173", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8))
    geo.install_geology(sim)
    if with_c13:
        cs.install_copper_smelting(sim)
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


def _native_copper():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06, "native_copper": 0.05})]


def _chalcopyrite():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06, "chalcopyrite": 0.05})]


def _put_chunk(sim, cc, layers, biome=_GRASS, w=0.0):
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


def _site(sim, coords, layers=None):
    cc = coords[len(coords) // 2]
    _put_chunk(sim, cc, layers or _native_copper())
    return cc


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _ready(sim, row, *, forced=True, prospected=True, fuel_kg=2.0, metal_kg=0.0):
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
    mem.has_forced_draught = bool(forced)
    mem.has_built_kiln = True
    mem.has_made_fire = True
    mem.prospected_ore_groups = ["copper"] if prospected else []
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


def _smelt_here(sim, row):
    px, py = float(sim.agents.pos[row, 0]), float(sim.agents.pos[row, 1])
    return _ORIG_APPLY(sim.agents, row, cog.Decision(int(ActionKind.SMELT), px, py, 0.5),
                       sim.streamer, sim.tick, sim=sim)


def main() -> int:
    print("=" * 84)
    print("P173 — copper smelting: the agent loop CONSUMES C13 (the 1ᵉʳ agent-driven MUTATION — "
          "D10 crossed, ADR-0010)")
    print("=" * 84)

    # 1 + 2 — LIVE perceive→decide→act→remember + the D10 crossing (geology mutated)
    sim, coords = _build()
    cc = _site(sim, coords)
    cue = cs.smelt_cue_for_chunk(sim, cc)
    _ready(sim, 0)
    _stand(sim, 0, cc)
    seek = cog._seek_smelt(sim.agents, 0, _obs(sim, 0), sim)
    decided = seek.action if seek is not None else None
    g = geo.chunk_geology(sim, cc)
    extracted_before = float(g.layers[0].extracted_kg)
    metal_before = float(sim.agents.inv_metal[0])
    ev = _smelt_here(sim, 0)
    mem = sim.agents.memory[0]
    extracted_after = float(g.layers[0].extracted_kg)
    print(f"  seed {hex(SEED_SMELT)}: site={cc} mineral={cue.copper_mineral if cue else None} "
          f"smeltable_now={cue.smeltable_now if cue else None}")
    print(f"        decide={ActionKind(decided).name if decided is not None else None} ; "
          f"extracted {extracted_before:.4f}→{extracted_after:.4f} ; "
          f"inv_metal {metal_before:.4f}→{float(sim.agents.inv_metal[0]):.4f} ; "
          f"event={ev[-1]['kind'] if ev else None}")
    check("1 — LIVE perceive→decide→act→remember : ready agent SMELTs (bouchée D12 #18, 1ʳᵉ métallurgie)",
          decided == int(ActionKind.SMELT) and ev and ev[-1]["kind"] == "smelt"
          and float(sim.agents.inv_metal[0]) > metal_before and mem.has_smelted_copper is True
          and mem.last_smelt_mineral == "native_copper" and len(mem.known_smelt_locations) == 1,
          f"metal_gained={float(sim.agents.inv_metal[0]) - metal_before:.4f}")
    check("2 — le franchissement de D10 : la colonne géologique est MUTÉE (extracted_kg ↑) — 1ʳᵉ mutation agent",
          extracted_after > extracted_before and ev and ev[-1]["mutated_geology"] is True
          and ev[-1]["ore_consumed_kg"] > 0.0,
          f"Δextracted={extracted_after - extracted_before:.4f} ore_consumed={ev[-1]['ore_consumed_kg'] if ev else None}")

    # 3 — the lie #4: raw sulfide consumed → only slag, geology still mutated
    ss, sc = _build()
    cs_coord = _site(ss, sc, layers=_chalcopyrite())
    scue = cs.smelt_cue_for_chunk(ss, cs_coord)
    _ready(ss, 0)
    _stand(ss, 0, cs_coord)
    gs = geo.chunk_geology(ss, cs_coord)
    before_s = float(gs.layers[0].extracted_kg)
    metal_before_s = float(ss.agents.inv_metal[0])
    evs = _smelt_here(ss, 0)
    ok3 = (scue is not None and scue.needs_roasting_first is True and evs and evs[-1]["kind"] == "smelt"
           and evs[-1]["required_roasting"] is True and evs[-1]["recovered_cu_kg"] == 0.0
           and evs[-1]["slag_kg"] > 0.0 and float(gs.layers[0].extracted_kg) > before_s
           and float(ss.agents.inv_metal[0]) == metal_before_s)
    check("3 — le mensonge #4 : un sulfure cru est CONSOMMÉ (géologie mutée) mais ne rend que de la scorie",
          ok3, f"recovered={evs[-1]['recovered_cu_kg'] if evs else None} slag={evs[-1]['slag_kg'] if evs else None}")

    # 4 — le monde ne ment jamais (no site → nothing)
    sb, _cb = _build()
    _ready(sb, 0, fuel_kg=2.0)
    far = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sb.agents.pos[0, 0] = far
    sb.agents.pos[0, 1] = far
    no_site = cs.smelt_at(sb, 0) is None
    fuel_b = float(sb.agents.inv_fuel[0])
    metal_b = float(sb.agents.inv_metal[0])
    evb = _smelt_here(sb, 0)
    kept = (evb == [] and float(sb.agents.inv_fuel[0]) == fuel_b
            and float(sb.agents.inv_metal[0]) == metal_b
            and sb.agents.memory[0].has_smelted_copper is False)
    check("4 — le monde ne ment jamais : rien à fondre ⇒ combustible + métal gardés, rien muté",
          no_site and kept, f"no_site={no_site} kept={kept}")

    # 5 — survival outranks smelting
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
    check("5 — survie > fonte : un agent assoiffé (eau en vue) BOIT, ne fond pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 6 — same path as the real tick
    st, ct = _build()
    cct = _site(st, ct)
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
    s = cog._seek_smelt(st.agents, 0, _obs(st, 0), st)
    seek_act = int(s.action) if s is not None else None
    check("6 — même chemin que le tick réel : sim.step() OK + le wire smelt vivant (SMELT/WALK_TO)",
          step_ok and seek_act in (int(ActionKind.SMELT), int(ActionKind.WALK_TO)),
          f"step_ok={step_ok} seek={ActionKind(seek_act).name if seek_act is not None else 'None'}")

    # 7 — gate (no C13 → inert) + determinism (same injected site → same bead)
    sng, cng = _build(with_c13=False)
    _ready(sng, 0)
    _stand(sng, 0, cng[len(cng) // 2])
    gate_off = (getattr(sng, "_copper_smelt_cue_cache", None) is None
                and cog._seek_smelt(sng.agents, 0, _obs(sng, 0), sng) is None)
    beads = []
    for _ in range(2):
        d, cd = _build()
        ccd = _site(d, cd)
        _ready(d, 0, fuel_kg=2.0)
        _stand(d, 0, ccd)
        e = _smelt_here(d, 0)
        beads.append(e[-1]["recovered_cu_kg"] if e else None)
    det = beads[0] is not None and beads[0] == beads[1]
    check("7 — gate (pas de C13 ⇒ inerte) + déterminisme même-seed (bouton bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det} beads={beads}")

    # 8 — discipline
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    in_enum = hasattr(ActionKind, "SMELT")
    mem_fields = all(hasattr(sim.agents.memory[0], f) for f in
                     ("has_smelted_copper", "last_smelt_mineral", "last_smelt_cu_kg",
                      "known_smelt_locations"))
    in_registry = ("smelt", cog._seek_smelt) in cog._ARC_SEEKS
    d8_ok = in_enum and mem_fields and in_registry and len(contract.PY_TO_RUST) == 15
    check("8 — discipline : SMELT∈ActionKind, mémoire smelt, registre, PY_TO_RUST==15 (D8), D10 franchi par design",
          d8_ok, f"enum={in_enum} mem={mem_fields} registry={in_registry} py_to_rust={len(contract.PY_TO_RUST)}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p173_copper_smelt_loop", "seed": SEED_SMELT,
                   "agent0_last_smelt_mineral": sim.agents.memory[0].last_smelt_mineral,
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
