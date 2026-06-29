#!/usr/bin/env python3
"""P164 — The agent loop FIRES clay into pottery (D12 wire, 2026-06-29, consumes C9).

**Not a new capability — the 9th agent BEHAVIOUR that consumes the arc**, and the FIRST whose inputs
are **two prior wires' products**: it FIREs carried clay (``inv_clay``, dug by DIG/C5) in a fire the
agent knows how to make (``has_made_fire``, from IGNITE/C7) into irreversible ceramic
(``inv_ceramic``). The founding neolithic transformation — the arc closing on itself: clay→fire→pot.

A curious agent that KNOWS FIRE and CARRIES clay, seeing a firing site (``ceramic_firing.best_firing_
site_near``), walks there and FIRE_CLAYs. Distinct from every prior wire: it CONSUMES a material
(``inv_clay``) that another wire (DIG) produces, and emits a new one (``inv_ceramic``). Each wire is
inert unless its capability is installed; this smoke installs ONLY C9 (which composes C5 clay + C7
fire), proving FIRE_CLAY in isolation.

LE MENSONGE RENDU VISIBLE #14 (the refractory inversion): "the prettiest clay makes the best pot" —
FALSE in an open fire. A bare fire never reaches kiln heat, so the humble earthenware SHALE fires
SOUND (a usable vessel) while the fine PLASTIC kaolin stays UNDER-FIRED — chalky, re-slakes — and the
clay is spent for NO vessel. ``best_firing_site_near(require_sound=True)`` routes to the sound ware;
firing an under-fired site teaches the lie by acting (clay gone, no pot). An open fire never
vitrifies (``watertight`` always False) — that needs a real kiln (a later bite).

Discipline: COMPOSES C5 × C7, the WIRE introduces NO new tell (``PY_TO_RUST`` stays 15 — D8), and
does NOT call ``geo.mine_at`` — firing is non-mutating (D10 frozen). ``inv_ceramic`` is a real
inventory field (added in mirror of ``inv_clay`` / ``inv_pigment``: dataclass + init + the two
persistence lists, defensive load → old saves compatible). Determinism: pure cues + memoised; no RNG.

Seed: 0xBEEF (clay + makeable fire co-located; plenty of SOUND shale firings + under-fired plastic).

Checks
------
 1.  LIVE loop: a ready agent (knows fire, carries clay) on a sound firing site ⇒ FIRE_CLAY: clay is
     spent, pottery is produced, the skill + site remembered (the milestone — inputs from two wires).
 2.  Both dependencies: no fire ⇒ no pot ; no clay in hand ⇒ no pot ; both ⇒ pot.
 3.  Refractory inversion #14: a sound shale site yields ceramic; an under-fired site spends the clay
     for NO vessel (learned by acting).
 4.  « Le monde ne ment jamais » : firing where no clay+fire is underfoot yields nothing (clay kept).
 5.  Survival outranks firing: a critically thirsty agent with water in sight DRINKS.
 6.  Same path as the real tick: a full ``sim.step()`` runs clean and decide() on the ready agent
     yields FIRE_CLAY.
 7.  Gate + determinism: no C9 ⇒ inert; same seed ⇒ bit-identical firing outcome.
 8.  D8/D10 discipline: FIRE_CLAY in ActionKind, memory field present, PY_TO_RUST==15, no mine_at.
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
import engine.ceramic_firing as cf                                 # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_FIRING = 0xBEEF
GRID = 12
OUT = os.path.join(ROOT, "journals", "p164_ceramic_firing_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:66s} {detail}")


def _build(seed: int = SEED_FIRING, *, with_c9: bool = True):
    cfg = SimConfig(name="p164", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c9:
        cf.install_ceramic_firing(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def _best_sound(sim, coords):
    best = None
    for coord in coords:
        cue = cf.firing_cue_for_chunk(sim, coord)
        if cue is None or not cue.fireable or not cue.is_sound:
            continue
        key = (cue.ware_quality, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _nonsound(sim, coords):
    for coord in coords:
        cue = cf.firing_cue_for_chunk(sim, coord)
        if cue is not None and cue.fireable and not cue.is_sound:
            return coord
    return None


def _ready(sim, row, *, knows_fire=True, clay_kg=None, warm=True):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal", "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone",
                "inv_metal", "inv_tools", "inv_pigment", "inv_clay", "inv_ceramic"):
        getattr(sim.agents, inv)[row] = 0.0
    # Sate the clay store so _seek_clay yields to _seek_kiln (unless overridden), warm so no IGNITE.
    sim.agents.inv_clay[row] = cog.CLAY_SATED_KG if clay_kg is None else float(clay_kg)
    if warm:
        sim.agents.thermal[row] = 0.05
    mem = sim.agents.memory[row]
    mem.known_kiln_locations.clear()
    mem.has_fired_pottery = False
    mem.last_ware_quality = None
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
    print("P164 — pottery firing: the agent loop CONSUMES C9 (closes a bite of D12/R0; the arc closes "
          "on itself — clay→fire→pot, the first wire fed by two others)")
    print("=" * 80)

    sim, coords = _build()
    n_sound = sum(1 for c in coords
                  if (cu := cf.firing_cue_for_chunk(sim, c)) is not None and cu.fireable and cu.is_sound)
    n_fire = sum(1 for c in coords
                 if (cu := cf.firing_cue_for_chunk(sim, c)) is not None and cu.fireable)
    print(f"  seed {hex(SEED_FIRING)}: streamed chunks={len(coords)} ; fireable={n_fire} sound={n_sound}")

    best = _best_sound(sim, coords)
    if best is None:
        print("RESULT: FAIL — seed produced no sound firing site (cannot exercise the wire).")
        return 1

    # 1 — LIVE loop: ready agent fires a pot (the milestone — inputs from DIG/C5 + IGNITE/C7)
    _ready(sim, 0)
    _stand(sim, 0, best)
    cue0 = cf.firing_cue_for_chunk(sim, best)
    clay_before = float(sim.agents.inv_clay[0])
    acts = _drive_loop(sim, 0, n_ticks=4)
    fired = ActionKind.FIRE_CLAY in acts
    clay_spent = float(sim.agents.inv_clay[0]) < clay_before
    made_ware = float(sim.agents.inv_ceramic[0]) > 0.0
    learned = bool(sim.agents.memory[0].has_fired_pottery)
    remembered = len(sim.agents.memory[0].known_kiln_locations)
    print(f"        agent#0 on {cue0.clay_class} sound site (ware={cue0.ware_quality}): "
          f"actions={[ActionKind(a).name for a in acts]}")
    print(f"        → inv_clay {clay_before:.3f}→{float(sim.agents.inv_clay[0]):.3f} "
          f"inv_ceramic={float(sim.agents.inv_ceramic[0]):.3f} has_fired_pottery={learned} kilns={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent CUIT un pot (jalon : argile DIG + feu IGNITE)",
          fired and clay_spent and made_ware and learned and remembered >= 1,
          f"fired={fired} clay_spent={clay_spent} ware={made_ware} learned={learned} mem={remembered}")

    # 2 — both dependencies
    sa, _ca = _build()
    _ready(sa, 0, knows_fire=False)
    _stand(sa, 0, best)
    sa.agents.memory[0].has_made_fire = False
    no_fire_blocked = cog._seek_kiln(sa.agents, 0, _obs_of(sa, 0), sa) is None
    sb, _cb = _build()
    _ready(sb, 0, clay_kg=0.0)
    _stand(sb, 0, best)
    no_clay_blocked = cog._seek_kiln(sb.agents, 0, _obs_of(sb, 0), sb) is None
    sc, _cc = _build()
    _ready(sc, 0)
    _stand(sc, 0, best)
    both_fires = (cog._seek_kiln(sc.agents, 0, _obs_of(sc, 0), sc) is not None)
    check("2 — deux dépendances : sans feu ⇒ rien ; sans argile en main ⇒ rien ; les deux ⇒ cuit",
          no_fire_blocked and no_clay_blocked and both_fires,
          f"no_fire={no_fire_blocked} no_clay={no_clay_blocked} both={both_fires}")

    # 3 — refractory inversion #14: sound yields ware; under-fired spends clay for nothing
    ss, css = _build()
    _ready(ss, 0, clay_kg=2.0, warm=False)
    _stand(ss, 0, best)
    ev_sound = _ORIG_APPLY(ss.agents, 0, cog.Decision(int(ActionKind.FIRE_CLAY), *_stand(ss, 0, best), 0.5),
                           ss.streamer, ss.tick, sim=ss)
    sound_ware = bool(ev_sound and ev_sound[-1]["is_sound"] and float(ev_sound[-1]["ceramic_kg"]) > 0.0)
    bad = _nonsound(ss, css)
    inversion = False
    if bad is not None:
        sb2, _c = _build()
        _ready(sb2, 0, clay_kg=2.0, warm=False)
        px, py = _stand(sb2, 0, bad)
        cb = float(sb2.agents.inv_clay[0])
        ev_bad = _ORIG_APPLY(sb2.agents, 0, cog.Decision(int(ActionKind.FIRE_CLAY), px, py, 0.5),
                             sb2.streamer, sb2.tick, sim=sb2)
        inversion = bool(ev_bad and ev_bad[-1]["is_sound"] is False
                         and float(sb2.agents.inv_ceramic[0]) == 0.0
                         and float(sb2.agents.inv_clay[0]) < cb)
    else:
        inversion = True  # seed had only sound sites — inversion path not exercisable here
    check("3 — inversion réfractaire #14 : schiste sound → poterie ; sur-cuit raté → argile perdue, 0 pot",
          sound_ware and inversion, f"sound_ware={sound_ware} underfired_lie={inversion}")

    # 4 — world never lies: no clay+fire underfoot ⇒ nothing, clay kept
    sn, _cn = _build()
    _ready(sn, 0, clay_kg=2.0, warm=False)
    far = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sn.agents.pos[0, 0] = far
    sn.agents.pos[0, 1] = far
    no_site = cf.prospect_firing(sn, far, far) is None
    cb = float(sn.agents.inv_clay[0])
    _ORIG_APPLY(sn.agents, 0, cog.Decision(int(ActionKind.FIRE_CLAY), far, far, 0.5),
                sn.streamer, sn.tick, sim=sn)
    kept = float(sn.agents.inv_clay[0]) == cb and float(sn.agents.inv_ceramic[0]) == 0.0
    check("4 — le monde ne ment jamais : pas d'argile+feu sous les pieds ⇒ RIEN (argile conservée)",
          no_site and kept, f"no_site={no_site} clay_kept={kept}")

    # 5 — survival outranks firing
    sv, cv = _build()
    bv = _best_sound(sv, cv)
    _ready(sv, 0)
    px, py = _stand(sv, 0, bv)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    obs = Observation(row=0, pos=(px, py, 0.0), drives=drives, vitality=1.0,
                      nearest={"water": water}, near_agents=[],
                      dominant_drive=cog._dominant_drive(drives), tick=0,
                      reproduction_readiness=0.0)
    d_thirst = _ORIG_DECIDE(sv.agents, obs, sim=sv)
    check("5 — survie > cuisson : un agent assoiffé (eau en vue) BOIT, ne cuit pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 6 — same path as the real tick
    st, ct = _build()
    bt = _best_sound(st, ct)
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
    check("6 — même chemin que le tick réel : sim.step() OK + decide()→FIRE_CLAY sur l'agent prêt",
          step_ok and d_live.action == int(ActionKind.FIRE_CLAY),
          f"step_ok={step_ok} decide={ActionKind(d_live.action).name}")

    # 7 — gate + determinism
    sng, cng = _build()
    _ready(sng, 0)
    _stand(sng, 0, _best_sound(sng, cng))
    sng._firing_cue_cache = None
    gate_off = cog._seek_kiln(sng.agents, 0, _obs_of(sng, 0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    b1 = _best_sound(d1, c1)
    for s in (d1, d2):
        _ready(s, 0, clay_kg=2.0, warm=False)
        px, py = _stand(s, 0, b1)
        _ORIG_APPLY(s.agents, 0, cog.Decision(int(ActionKind.FIRE_CLAY), px, py, 0.5),
                    s.streamer, s.tick, sim=s)
    det = abs(float(d1.agents.inv_ceramic[0]) - float(d2.agents.inv_ceramic[0])) < 1e-12
    check("7 — gate (pas de C9 ⇒ inerte) + déterminisme même-seed (cuisson bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    fire_in_enum = hasattr(ActionKind, "FIRE_CLAY")
    mem_field = hasattr(sim.agents.memory[0], "known_kiln_locations")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)
    blk = (src.split("ActionKind.FIRE_CLAY)", 1)[1].split("ActionKind.SLEEP)", 1)[0]
           if "ActionKind.FIRE_CLAY)" in src else "")
    no_mine_at = bool(blk) and "mine_at(" not in blk
    d8_ok = (fire_in_enum and mem_field and len(contract.PY_TO_RUST) == 15 and no_mine_at)
    check("8 — discipline : FIRE_CLAY∈ActionKind, mémoire kiln, PY_TO_RUST==15 (wire sans tell), pas de mine_at (D10 gelé)",
          d8_ok, f"fire_clay={fire_in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p164_ceramic_firing_loop", "seed": SEED_FIRING,
                   "fireable": n_fire, "sound": n_sound,
                   "agent0_actions": [ActionKind(a).name for a in acts],
                   "agent0_ware": sim.agents.memory[0].last_ware_quality,
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
