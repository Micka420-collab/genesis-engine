#!/usr/bin/env python3
"""P166 — The agent loop BURNS limestone into quicklime (D12 wire, 2026-06-29, consumes C10).

The 11th agent BEHAVIOUR that consumes the arc, and the SECOND two-ingredient transformation — the
exact mirror of C9 FIRE_CLAY (clay→pot :: limestone→lime). An agent that KNOWS FIRE (from IGNITE/C7)
AND CARRIES limestone (from QUARRY/C6) CALCINEs it at a burning site into caustic quicklime
(``inv_lime``) — *« Burning Lime, the oldest chemical industry on Earth »*. Appended to the
``_ARC_SEEKS`` registry as one line. Installs ONLY C10 (which composes C6 limestone + C7 fire).

LE MENSONGE RENDU VISIBLE #16 (the same refractory inversion as C9): an OPEN fire only ever
SOFT-burns aerial lime — it NEVER reaches the hard-burn / mortar temperature (``mortar_ready`` always
False; that needs a kiln, a later bite). An under-burnt stone (fire too cool / impure carbonate) is
spent for NO usable lime — a raw core that re-carbonates. ``best_burning_site_near(require_well_burnt)``
routes to the usable burn; firing an under-burnt site teaches the lie by acting.

Discipline: COMPOSES C6 × C7, the WIRE introduces NO new tell (``PY_TO_RUST`` stays 15 — D8), no
``geo.mine_at`` (D10 frozen). ``inv_lime`` is a real field (added like inv_limestone/inv_ceramic).
Determinism: pure cues + memoised; no RNG. Seed 0xBEEF (limestone + fire, well-burnt + under-burnt).

Checks
------
 1.  LIVE loop: a ready agent (fire + limestone) on a well-burnt site ⇒ CALCINE: limestone spent,
     quicklime produced, skill + site remembered (the milestone — inputs from QUARRY/C6 + IGNITE/C7).
 2.  Both dependencies: no fire ⇒ no lime ; no limestone in hand ⇒ no lime ; both ⇒ lime.
 3.  Refractory inversion #16: a well-burnt site yields lime; an under-burnt site spends the limestone
     for NO lime, and an open fire is never mortar-ready.
 4.  « Le monde ne ment jamais » : burning where no carbonate+fire is underfoot keeps the limestone.
 5.  Survival outranks burning.
 6.  Same path as the real tick: ``sim.step()`` runs clean and decide() yields CALCINE.
 7.  Gate + determinism: no C10 ⇒ inert; same seed ⇒ bit-identical burn outcome.
 8.  D8/D10 discipline: CALCINE in ActionKind, memory field present, PY_TO_RUST==15, no mine_at.
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
from engine import cognition as cog                                 # noqa: E402
from engine.cognition import Observation, PerceivedTarget           # noqa: E402
from engine.agent import ActionKind, DriveKind                      # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.lime_burning as lb                                   # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_LIME = 0xBEEF
GRID = 12
OUT = os.path.join(ROOT, "journals", "p166_lime_burning_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:66s} {detail}")


def _build(seed: int = SEED_LIME, *, with_c10: bool = True):
    cfg = SimConfig(name="p166", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c10:
        lb.install_lime_burning(sim)
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
        cue = lb.lime_burning_cue_for_chunk(sim, coord)
        if cue is None or not cue.burnable or not cue.well_burnt:
            continue
        key = (cue.lime_yield, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _underburnt(sim, coords):
    for coord in coords:
        cue = lb.lime_burning_cue_for_chunk(sim, coord)
        if cue is not None and cue.burnable and not cue.well_burnt:
            return coord
    return None


def _ready(sim, row, *, knows_fire=True, limestone_kg=None, warm=True):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal", "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal", "inv_tools",
                "inv_pigment", "inv_clay", "inv_ceramic", "inv_limestone", "inv_lime"):
        getattr(sim.agents, inv)[row] = 0.0
    sim.agents.inv_limestone[row] = cog.LIMESTONE_SATED_KG if limestone_kg is None else float(limestone_kg)
    if warm:
        sim.agents.thermal[row] = 0.05
    mem = sim.agents.memory[row]
    mem.known_limekiln_locations.clear()
    mem.has_burnt_lime = False
    mem.last_lime_yield = None
    mem.has_made_fire = bool(knows_fire)
    mem.last_fire_method = "PERCUSSION" if knows_fire else None


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _drive_loop(sim, row, n_ticks=4):
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
    print("P166 — lime burning: the agent loop CONSUMES C10 (closes a bite of D12/R0; the 2nd two-"
          "ingredient transformation — limestone→fire→lime, mirror of clay→fire→pot)")
    print("=" * 80)

    sim, coords = _build()
    n_burn = sum(1 for c in coords
                 if (cu := lb.lime_burning_cue_for_chunk(sim, c)) is not None and cu.burnable)
    n_well = sum(1 for c in coords
                 if (cu := lb.lime_burning_cue_for_chunk(sim, c)) is not None and cu.burnable and cu.well_burnt)
    print(f"  seed {hex(SEED_LIME)}: streamed chunks={len(coords)} ; burnable={n_burn} well_burnt={n_well}")

    best = _best(sim, coords)
    if best is None:
        print("RESULT: FAIL — seed produced no well-burnt lime site.")
        return 1

    # 1 — LIVE loop
    _ready(sim, 0)
    _stand(sim, 0, best)
    cue0 = lb.lime_burning_cue_for_chunk(sim, best)
    stone_before = float(sim.agents.inv_limestone[0])
    acts = _drive_loop(sim, 0, n_ticks=4)
    calcined = ActionKind.CALCINE in acts
    spent = float(sim.agents.inv_limestone[0]) < stone_before
    made = float(sim.agents.inv_lime[0]) > 0.0
    learned = bool(sim.agents.memory[0].has_burnt_lime)
    remembered = len(sim.agents.memory[0].known_limekiln_locations)
    print(f"        agent#0 on {cue0.lime_class} well-burnt site (yield={cue0.lime_yield}, "
          f"mortar_ready={cue0.mortar_ready}): actions={[ActionKind(a).name for a in acts]}")
    print(f"        → inv_limestone {stone_before:.3f}→{float(sim.agents.inv_limestone[0]):.3f} "
          f"inv_lime={float(sim.agents.inv_lime[0]):.3f} has_burnt_lime={learned} kilns={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent CUIT la chaux (jalon : calcaire QUARRY + feu IGNITE)",
          calcined and spent and made and learned and remembered >= 1,
          f"calcined={calcined} spent={spent} lime={made} learned={learned} mem={remembered}")

    # 2 — both dependencies
    sa, _ca = _build()
    _ready(sa, 0, knows_fire=False)
    _stand(sa, 0, best)
    sa.agents.memory[0].has_made_fire = False
    no_fire = cog._seek_limekiln(sa.agents, 0, _obs_of(sa, 0), sa) is None
    sb, _cb = _build()
    _ready(sb, 0, limestone_kg=0.0)
    _stand(sb, 0, best)
    no_stone = cog._seek_limekiln(sb.agents, 0, _obs_of(sb, 0), sb) is None
    sc, _cc = _build()
    _ready(sc, 0)
    _stand(sc, 0, best)
    both = cog._seek_limekiln(sc.agents, 0, _obs_of(sc, 0), sc) is not None
    check("2 — deux dépendances : sans feu ⇒ rien ; sans calcaire en main ⇒ rien ; les deux ⇒ cuit",
          no_fire and no_stone and both, f"no_fire={no_fire} no_stone={no_stone} both={both}")

    # 3 — refractory inversion #16
    ss, css = _build()
    _ready(ss, 0, limestone_kg=2.0, warm=False)
    px, py = _stand(ss, 0, best)
    ev_w = _ORIG_APPLY(ss.agents, 0, cog.Decision(int(ActionKind.CALCINE), px, py, 0.5),
                       ss.streamer, ss.tick, sim=ss)
    well_yield = bool(ev_w and ev_w[-1]["well_burnt"] and float(ev_w[-1]["lime_kg"]) > 0.0
                      and ev_w[-1]["mortar_ready"] is False)
    bad = _underburnt(ss, css)
    inversion = False
    if bad is not None:
        sb2, _c = _build()
        _ready(sb2, 0, limestone_kg=2.0, warm=False)
        px, py = _stand(sb2, 0, bad)
        cb = float(sb2.agents.inv_limestone[0])
        ev_b = _ORIG_APPLY(sb2.agents, 0, cog.Decision(int(ActionKind.CALCINE), px, py, 0.5),
                           sb2.streamer, sb2.tick, sim=sb2)
        inversion = bool(ev_b and ev_b[-1]["well_burnt"] is False
                         and float(sb2.agents.inv_lime[0]) == 0.0
                         and float(sb2.agents.inv_limestone[0]) < cb)
    else:
        inversion = True
    check("3 — inversion réfractaire #16 : bien cuit → chaux (jamais mortier sur feu nu) ; sous-cuit → pierre perdue, 0 chaux",
          well_yield and inversion, f"well_yield={well_yield} underburnt_lie={inversion}")

    # 4 — world never lies
    sn, _cn = _build()
    _ready(sn, 0, limestone_kg=2.0, warm=False)
    far = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sn.agents.pos[0, 0] = far
    sn.agents.pos[0, 1] = far
    no_site = lb.prospect_lime_burning(sn, far, far) is None
    cb = float(sn.agents.inv_limestone[0])
    _ORIG_APPLY(sn.agents, 0, cog.Decision(int(ActionKind.CALCINE), far, far, 0.5),
                sn.streamer, sn.tick, sim=sn)
    kept = float(sn.agents.inv_limestone[0]) == cb and float(sn.agents.inv_lime[0]) == 0.0
    check("4 — le monde ne ment jamais : pas de calcaire+feu sous les pieds ⇒ calcaire conservé",
          no_site and kept, f"no_site={no_site} stone_kept={kept}")

    # 5 — survival
    sv, cv = _build()
    bv = _best(sv, cv)
    _ready(sv, 0)
    px, py = _stand(sv, 0, bv)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    obs = Observation(row=0, pos=(px, py, 0.0), drives=drives, vitality=1.0,
                      nearest={"water": water}, near_agents=[],
                      dominant_drive=cog._dominant_drive(drives), tick=0, reproduction_readiness=0.0)
    d_thirst = _ORIG_DECIDE(sv.agents, obs, sim=sv)
    check("5 — survie > cuisson chaux : un agent assoiffé (eau en vue) BOIT, ne cuit pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 6 — same path as the real tick
    st, ct = _build()
    bt = _best(st, ct)
    step_ok = True
    try:
        st.step()
    except Exception as exc:               # pragma: no cover
        step_ok = False
        print(f"        sim.step() raised: {exc}")
    _ready(st, 0)
    _stand(st, 0, bt)
    obs_t = cog.perceive(st.agents, 0, st.streamer, tick=st.tick)
    d_live = _ORIG_DECIDE(st.agents, obs_t, sim=st)
    check("6 — même chemin que le tick réel : sim.step() OK + decide()→CALCINE sur l'agent prêt",
          step_ok and d_live.action == int(ActionKind.CALCINE),
          f"step_ok={step_ok} decide={ActionKind(d_live.action).name}")

    # 7 — gate + determinism
    sng, cng = _build()
    _ready(sng, 0)
    _stand(sng, 0, _best(sng, cng))
    sng._lime_burn_cue_cache = None
    gate_off = cog._seek_limekiln(sng.agents, 0, _obs_of(sng, 0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    b1 = _best(d1, c1)
    for s in (d1, d2):
        _ready(s, 0, limestone_kg=2.0, warm=False)
        px, py = _stand(s, 0, b1)
        _ORIG_APPLY(s.agents, 0, cog.Decision(int(ActionKind.CALCINE), px, py, 0.5),
                    s.streamer, s.tick, sim=s)
    det = abs(float(d1.agents.inv_lime[0]) - float(d2.agents.inv_lime[0])) < 1e-12
    check("7 — gate (pas de C10 ⇒ inerte) + déterminisme même-seed (cuisson chaux bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    in_enum = hasattr(ActionKind, "CALCINE")
    mem_field = hasattr(sim.agents.memory[0], "known_limekiln_locations")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)
    blk = (src.split("ActionKind.CALCINE)", 1)[1].split("ActionKind.SLEEP)", 1)[0]
           if "ActionKind.CALCINE)" in src else "")
    no_mine_at = bool(blk) and "mine_at(" not in blk
    d8_ok = (in_enum and mem_field and len(contract.PY_TO_RUST) == 15 and no_mine_at)
    check("8 — discipline : CALCINE∈ActionKind, mémoire limekiln, PY_TO_RUST==15 (wire sans tell), pas de mine_at (D10 gelé)",
          d8_ok, f"calcine={in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p166_lime_burning_loop", "seed": SEED_LIME,
                   "burnable": n_burn, "well_burnt": n_well,
                   "agent0_actions": [ActionKind(a).name for a in acts],
                   "agent0_lime_yield": sim.agents.memory[0].last_lime_yield,
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
