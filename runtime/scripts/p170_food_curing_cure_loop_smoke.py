#!/usr/bin/env python3
"""P170 — The agent loop CURES raw food with salt (D12 wire, 2026-06-29, consumes C16 × C15).

The 14ᵉ agent BEHAVIOUR that consumes the arc — and the **1ʳᵉ qui consomme le PRODUIT d'une cap.
précédente**: the salt the agent itself RAKEd (C15) is the intrant that turns fugace fresh meat
(``inv_food``) into months-keeping cured haunch (``inv_cured_food``). NON-FIRE / non-thermal — the
sun + osmose du sel font le travail (D9 alternance: pendant non-feu du RAISE_KILN). C16
``food_curing`` made the physics of préservation visible (FIPS a_w = 0.75 NaCl floor ; Q10 = 2.5 ;
shelf_life_days) ; but no agent ever USED it. Appended to ``_ARC_SEEKS`` between ``kilnbuild`` and
``ochre``. Installs C15 + C16.

LE MENSONGE RENDU VISIBLE #7 — vécu, plus seulement aperçu (pendant comportemental du smoke C16) :
fresh food (rouge, succulent, le plus appétissant) pourrit en jours ; salted food (terne, dur,
salé) tient des mois. L'agent apprend l'arbitrage attrait↔conservation **en l'agissant** : il
échange ``inv_food`` (frais) + ``inv_salt`` contre ``inv_cured_food`` (terne, réserve), et
``last_preservation_class`` enregistre ce que la classe du monde lui a donné.

Discipline: COMPOSES C15 (le sel) + C16 (les physiques de la cure), le WIRE introduces NO new tell
(``PY_TO_RUST`` stays 15 — D8, 11ᵉ composition), NON-MUTATING world (no ``geo.mine_at`` — only the
agent's own inventory mutates, exactly comme RAKE/C15 dont C16 dérive ; D10 frozen). ``inv_cured_food``
is a real field (added like inv_salt/inv_fuel). Determinism: pure formulas + memoised cues; no RNG.
Seed 0x5A17 (« SALT ») — même côte aride que C15, où le sel est abondant.

Checks
------
 1.  LIVE loop : un agent curieux portant viande+sel sur le meilleur marais ⇒ CURE :
     ``inv_cured_food`` se remplit + ``has_cured_food`` + ``last_preservation_class`` enregistré
     (bouchée D12 — la conservation est LIVED, pas seulement aperçue).
 2.  MENSONGE #7 vécu : après CURE, ``inv_food`` baisse (le frais part), ``inv_cured_food`` monte
     (la réserve naît) — l'arbitrage attrait↔conservation est agi, pas dit.
 3.  « Le monde ne ment jamais » : sans sel en main (inv_salt = 0), CURE ne consomme rien.
 4.  Survie > cure : un agent affamé (faim critique) mange (EAT) ou chasse, plutôt que de saler.
 5.  Auto-limité : un agent riche en cure (``inv_cured_food`` ≥ sated) ne cherche plus à saler.
 6.  Composition C15→C16 : sans inv_food en main, le wire ne décide pas CURE même au marais.
 7.  Gate + déterminisme : pas de C16 (``_food_curing_state``) ⇒ inerte ; même seed ⇒
     cure bit-identique entre deux runs.
 8.  Discipline D8/D10 : CURE∈ActionKind, mémoire ``has_cured_food`` présente,
     ``PY_TO_RUST`` == 15 (wire sans tell), pas de ``mine_at`` (D10 gelé).
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
from engine.world_genesis import GenesisParams, generate_world      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine import cognition as cog                                 # noqa: E402
from engine.cognition import Observation                            # noqa: E402
from engine.agent import ActionKind, DriveKind                      # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.salt_evaporation as se                                # noqa: E402
import engine.water_potability as wp                                # noqa: E402
import engine.food_curing as fc                                     # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_CURE = 0x5A17
GRID = 12
OUT = os.path.join(ROOT, "journals", "p170_food_curing_cure_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:66s} {detail}")


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


def _build(seed: int = SEED_CURE, *, with_c16: bool = True):
    world = generate_world(GenesisParams(seed=seed, resolution=128, n_plates=8))
    origin = _arid_saline_origin_km(world)
    cfg = SimConfig(name="p170", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8),
                          sim_origin_macro_km=origin)
    geo.install_geology(sim)
    se.install_salt_evaporation(sim)
    if with_c16:
        fc.install_food_curing(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def _best(sim, coords):
    best = None
    for coord in coords:
        cue = se.saltpan_cue_for_chunk(sim, coord)
        if cue is None or not cue.harvestable:
            continue
        key = (cue.salt_yield_kg_m2, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _calm_curious(sim, row, *, with_food=True, with_salt=True):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal", "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal", "inv_tools",
                "inv_pigment", "inv_clay", "inv_ceramic", "inv_limestone", "inv_lime",
                "inv_salt", "inv_fuel", "inv_cured_food"):
        getattr(sim.agents, inv)[row] = 0.0
    if with_food:
        sim.agents.inv_food[row] = 2.0       # plenty of raw food to cure (4 batches)
    if with_salt:
        sim.agents.inv_salt[row] = 1.0       # plenty of salt (≈7 batches' dose)
    mem = sim.agents.memory[row]
    mem.has_cured_food = False
    mem.last_preservation_class = None
    mem.known_saltpan_locations.clear()


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _drive_loop(sim, row, n_ticks=8):
    actions = []
    for _ in range(n_ticks):
        obs = cog.perceive(sim.agents, row, sim.streamer, tick=sim.tick)
        d = _ORIG_DECIDE(sim.agents, obs, sim=sim)
        _ORIG_APPLY(sim.agents, row, d, sim.streamer, sim.tick, sim=sim)
        actions.append(int(d.action))
    return actions


def _obs_of(sim, row):
    a = sim.agents
    d = np.array([float(a.hunger[row]), float(a.thirst[row]), float(a.sleep[row]),
                  float(a.fatigue[row]), float(a.thermal[row]), float(a.pain[row]),
                  float(a.stress[row]), float(a.loneliness[row])], dtype=np.float32)
    return Observation(row=int(row), pos=(float(a.pos[row, 0]), float(a.pos[row, 1]), 0.0),
                       drives=d, vitality=1.0, nearest={}, near_agents=[],
                       dominant_drive=cog._dominant_drive(d), tick=0,
                       reproduction_readiness=0.0)


def main() -> int:
    print("=" * 80)
    print("P170 — food curing: the agent loop CONSUMES C16 × C15 (1ʳᵉ consommation du PRODUIT d'une "
          "cap. précédente, bouchée D12/R0 ; le sel raté devient une réserve qui tient des mois)")
    print("=" * 80)

    sim, coords = _build()
    n_pan = sum(1 for c in coords
                if (cu := se.saltpan_cue_for_chunk(sim, c)) is not None and cu.harvestable)
    print(f"  seed {hex(SEED_CURE)} (arid saline coast): streamed chunks={len(coords)} ; harvestable pans={n_pan}")

    best = _best(sim, coords)
    if best is None:
        print("RESULT: FAIL — anchored arid coast produced no harvestable pan.")
        return 1

    # 1 — LIVE loop. Pre-saturate inv_salt above SALT_SATED_KG so the saltpan seek skips (auto-limited)
    # and CURE fires immediately — this exercises the CURE wire in isolation, exactly the path the agent
    # reaches once it has raked enough salt over its lifetime (the post-saltpan state).
    _calm_curious(sim, 0)
    sim.agents.inv_salt[0] = cog.SALT_SATED_KG + 1.0   # past raked plenty; saltpan skips → cure fires
    _stand(sim, 0, best)
    before_food = float(sim.agents.inv_food[0])
    before_salt = float(sim.agents.inv_salt[0])
    before_cure = float(sim.agents.inv_cured_food[0])
    acts = _drive_loop(sim, 0, n_ticks=8)
    cured = ActionKind.CURE in acts
    filled = float(sim.agents.inv_cured_food[0]) > before_cure
    food_dropped = float(sim.agents.inv_food[0]) < before_food
    salt_dropped = float(sim.agents.inv_salt[0]) < before_salt
    learned = sim.agents.memory[0].has_cured_food and sim.agents.memory[0].last_preservation_class is not None
    remembered = len(sim.agents.memory[0].known_saltpan_locations)
    print(f"        agent#0 on best pan: actions={[ActionKind(a).name for a in acts]}")
    print(f"        → inv_food  {before_food:.3f}→{float(sim.agents.inv_food[0]):.3f}")
    print(f"        → inv_salt  {before_salt:.3f}→{float(sim.agents.inv_salt[0]):.3f}")
    print(f"        → inv_cured {before_cure:.3f}→{float(sim.agents.inv_cured_food[0]):.3f}  "
          f"class={sim.agents.memory[0].last_preservation_class} known_pans={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent SALE et la réserve naît (bouchée D12)",
          cured and filled and learned and remembered >= 1,
          f"cured={cured} filled={filled} learned={learned} mem={remembered}")

    # 2 — the lie #7 lived: fresh shrinks (food↓), salt is spent (salt↓), cured grows (cured↑).
    # With salt past sated the saltpan seek skips, so the only inv_salt motion is CURE consuming it —
    # the arbitrage attrait↔conservation is AGI (the agent literally exchanges fresh+salt for kept).
    lie_ok = food_dropped and salt_dropped and filled
    check("2 — mensonge #7 vécu : ``inv_food`` (frais, appétissant) baisse, ``inv_cured_food`` "
          "(terne, garde) monte — l'arbitrage est AGI",
          lie_ok, f"food↓={food_dropped} salt↓={salt_dropped} cured↑={filled}")

    # 3 — world never lies: no salt in hand → CURE consumes nothing (the world doesn't preserve magic)
    sb, _cb = _build()
    _calm_curious(sb, 0, with_salt=False)         # food in hand, ZERO salt
    bx, by = _stand(sb, 0, best)
    before_food_b = float(sb.agents.inv_food[0])
    _ORIG_APPLY(sb.agents, 0, cog.Decision(int(ActionKind.CURE), bx, by, 0.5),
                sb.streamer, sb.tick, sim=sb)
    inert = (float(sb.agents.inv_food[0]) == before_food_b
             and float(sb.agents.inv_cured_food[0]) == 0.0
             and not sb.agents.memory[0].has_cured_food)
    check("3 — le monde ne ment jamais : pas de sel en main ⇒ CURE inerte (pas de cure magique)",
          inert, f"food_kept={float(sb.agents.inv_food[0])==before_food_b} "
                 f"cured_zero={float(sb.agents.inv_cured_food[0])==0.0} "
                 f"unlearned={not sb.agents.memory[0].has_cured_food}")

    # 4 — survival outranks cure: starving agent EATs (has food in hand), doesn't salt
    sv, cv = _build()
    bv = _best(sv, cv)
    _calm_curious(sv, 0)
    px, py = _stand(sv, 0, bv)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.HUNGER)] = 0.95
    obs = Observation(row=0, pos=(px, py, 0.0), drives=drives, vitality=1.0,
                      nearest={}, near_agents=[],
                      dominant_drive=cog._dominant_drive(drives), tick=0, reproduction_readiness=0.0)
    d_starve = _ORIG_DECIDE(sv.agents, obs, sim=sv)
    check("4 — survie > cure : un agent affamé MANGE (EAT), il ne sale pas",
          d_starve.action == int(ActionKind.EAT), f"action={ActionKind(d_starve.action).name}")

    # 5 — self-limiting
    ss, cs2 = _build()
    bs = _best(ss, cs2)
    _calm_curious(ss, 0)
    ss.agents.inv_cured_food[0] = cog.CURED_FOOD_SATED_KG + 0.1
    _stand(ss, 0, bs)
    sated = cog._seek_cure(ss.agents, 0, _obs_of(ss, 0), ss) is None
    check("5 — auto-limité : agent riche en réserve (≥ sated) ne cherche plus à saler",
          sated, f"sated_no_reseek={sated}")

    # 6 — composition: no raw food in hand → the wire doesn't decide CURE
    snf, cnf = _build()
    bnf = _best(snf, cnf)
    _calm_curious(snf, 0, with_food=False)        # ZERO food, plenty of salt
    _stand(snf, 0, bnf)
    no_food_seek = cog._seek_cure(snf.agents, 0, _obs_of(snf, 0), snf) is None
    check("6 — composition C15→C16 : sans viande en main, le wire NE décide PAS CURE (intrant manquant)",
          no_food_seek, f"no_food_inert={no_food_seek}")

    # 7 — gate (no C16) + determinism (same seed → bit-identical cure)
    sng, cng = _build(with_c16=False)
    _calm_curious(sng, 0)
    _stand(sng, 0, _best(sng, cng))
    gate_off = cog._seek_cure(sng.agents, 0, _obs_of(sng, 0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    b1 = _best(d1, c1)
    for s in (d1, d2):
        _calm_curious(s, 0)
        px, py = _stand(s, 0, b1)
        _ORIG_APPLY(s.agents, 0, cog.Decision(int(ActionKind.CURE), px, py, 0.5),
                    s.streamer, s.tick, sim=s)
    det = abs(float(d1.agents.inv_cured_food[0]) - float(d2.agents.inv_cured_food[0])) < 1e-12
    check("7 — gate (pas de C16 ⇒ inerte) + déterminisme même-seed (cure bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline D8 / D10
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    in_enum = hasattr(ActionKind, "CURE")
    mem_field = hasattr(sim.agents.memory[0], "has_cured_food")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)
    blk = (src.split("ActionKind.CURE)", 1)[1].split("ActionKind.SLEEP)", 1)[0]
           if "ActionKind.CURE)" in src else "")
    no_mine_at = bool(blk) and "mine_at(" not in blk
    d8_ok = (in_enum and mem_field and len(contract.PY_TO_RUST) == 15 and no_mine_at)
    check("8 — discipline : CURE∈ActionKind, mémoire has_cured_food, PY_TO_RUST==15 (wire sans tell), "
          "pas de mine_at (D10 gelé)",
          d8_ok, f"cure={in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p170_food_curing_cure_loop", "seed": SEED_CURE,
                   "harvestable_pans": n_pan,
                   "agent0_actions": [ActionKind(a).name for a in acts],
                   "agent0_last_preservation_class": sim.agents.memory[0].last_preservation_class,
                   "agent0_inv_cured_food_kg": float(sim.agents.inv_cured_food[0]),
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
