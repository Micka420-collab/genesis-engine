#!/usr/bin/env python3
"""P160 — The agent loop MARKS a pigment onto a carbonate wall (D12 wire, 2026-06-28).

**Not a new capability — the 5th agent BEHAVIOUR that consumes the arc** (after DRINK/C3,
KNAP/C2, GATHER/C14 and GRIND/C18). AUDIT-DELTA-2026-06-23 named the dominant hole **D12 /
R0**: 20 truthful affordances, no agent loop ever invoked them. GRIND/C18 (p158) opened the
SYMBOLIC pillar by filling ``inv_pigment`` — the *matter* of the mark. This is its pendant
and the symbolic pillar's **second** agent consumer: a survival-satisfied, curious agent
that HOLDS a ground colour and SEES a pale carbonate wall (``rock_canvas.best_canvas_near``)
walks there and leaves a MARK — the *mark* itself, after its matter.

Orthogonal to GRIND: MARK consumes from ``inv_pigment`` (it does not fill an inventory) and
deposits colour on a wall; it is tried AFTER ``_seek_ochre`` (grind the colour, THEN paint
with it). Each wire is inert unless its capability is installed (gate on the cue cache), so
none perturbs the others' scenarios — this smoke installs ONLY C20 (rock_canvas) and ARMS
the agent with pigment by hand (as if C18 had just run), proving MARK in isolation.

LE MENSONGE RENDU VISIBLE (#11, the painter's lie): "a conspicuous pale cliff always holds a
mark" — FALSE. A SOUND limestone face grows a protective calcite veil and keeps the mark for
millennia (Lascaux); the SAME carbonate wall in a humid (KARST, dissolution) or freezing
(FROST, spalling) climate takes the pigment then flakes it off. The mark IS made (pigment is
spent) but it does NOT last. The agent learns the wall→permanence link by marking.

Discipline: COMPOSES C20 (reads ``rock_canvas``, itself composing C6), introduces NO new
tell (``PY_TO_RUST`` stays 15 — D8 by composition), and does NOT call ``geo.mine_at`` — MARK
is non-mutating (painting does not consume the rock), so the mutation frontier (D10) stays
frozen. Non-fire (D9). Determinism: pure cue derivation + memoised cues; no new RNG.

Seeds: 0xC1A7 (a temperate-dry carbonate continent → SOUND walls, durable marks) and 0xFE11
(the same carbonate in a humid climate → KARST walls, marks that flake off). No injection —
the world really is this (verbatim from the C20 capability smoke p152).

Checks
------
 1.  LIVE loop: perceive→decide→apply on a real wall, agent armed with pigment ⇒ agent MARKS,
     spends pigment + remembers the wall (D12 bite, the symbolic pillar's 2nd consumer).
 2.  Outcome = world truth: a SOUND wall holds the mark (lasts), a KARST wall flakes it
     (mark made — pigment spent — but lasts False). Mensonge #11.
 3.  « Le monde ne ment jamais » : marking where no carbonate wall is underfoot yields nothing.
 4.  Survival outranks marking: a critically thirsty agent with water in sight DRINKS.
 5.  Requires a colour in hand: with no pigment / no carried hue the agent never marks, explores.
 6.  Same path as the real tick: a full ``sim.step()`` runs clean and decide() on the armed
     agent yields MARK (the wire is on the live tick path, not a side API).
 7.  Gate + determinism: no C20 ⇒ inert; same seed ⇒ bit-identical mark outcome.
 8.  D8/D10 discipline: MARK in ActionKind, memory list present, PY_TO_RUST==15, no mine_at.
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
import engine.rock_canvas as rc                                    # noqa: E402

# Capture the ORIGINAL decide/apply_decision before any installer (e.g. a later
# sim.step()) globally wraps them — the D12 wire lives in the originals.
_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_SOUND = 0xC1A7
SEED_KARST = 0xFE11
HEMATITE = (132, 46, 28)     # a dark red ochre hue (contrasts a pale limestone wall)
GRID = 12
OUT = os.path.join(ROOT, "journals", "p160_rock_canvas_mark_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:66s} {detail}")


def _build(seed: int = SEED_SOUND, *, with_c20: bool = True):
    """A carbonate Genesis sim with C20 (rock_canvas) installed — and ONLY C20, so MARK is
    exercised in isolation (KNAP / GATHER / GRIND inert: C2 / C14 / C18 never installed)."""
    cfg = SimConfig(name="p160", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c20:
        rc.install_rock_canvas(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def _best_canvas(sim, coords):
    """The coord ``best_canvas_near`` globally prefers — max (durability, adhesion) among
    carbonate walls. Standing the agent here makes the underfoot wall the in-window argmax,
    so the live loop deterministically MARKs."""
    best = None
    for coord in coords:
        cue = rc.canvas_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        key = (cue.durability, cue.adhesion, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _flaking(sim, coords):
    """A perceivable carbonate wall that flakes — takes the pigment yet does NOT hold a
    lasting mark (KARST dissolution / FROST spalling): the lie #11."""
    for coord in coords:
        cue = rc.canvas_cue_for_chunk(sim, coord)
        if cue is not None and not cue.holds_lasting_mark:
            return coord
    return None


def _calm_curious(sim, row):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal", "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone",
                "inv_metal", "inv_tools", "inv_pigment"):
        getattr(sim.agents, inv)[row] = 0.0
    # Pre-saturate ``inv_limestone`` past sated: rock_canvas (C20) transitively installs C6
    # limestone_outcrop, so the limestone seek would otherwise prefer QUARRY over MARK on a
    # paintable carbonate wall (limestone precedes canvas in the registry). Mirrors a real
    # agent that has already gathered limestone — its NEXT step is the mark.
    sim.agents.inv_limestone[row] = cog.LIMESTONE_SATED_KG + 0.1
    sim.agents.memory[row].known_canvas_locations.clear()
    sim.agents.memory[row].last_pigment_hue = None


def _arm(sim, row, hue=HEMATITE, kg: float = 1.0):
    """Give the agent a colour in hand — as if it had just ground ochre (C18)."""
    sim.agents.inv_pigment[row] = float(kg)
    sim.agents.memory[row].last_pigment_hue = tuple(int(c) for c in hue)


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _drive_loop(sim, row, n_ticks=12):
    """The canonical agent primitive — exactly what Simulation.step runs per agent."""
    actions = []
    for _ in range(n_ticks):
        obs = cog.perceive(sim.agents, row, sim.streamer, tick=sim.tick)
        d = _ORIG_DECIDE(sim.agents, obs, sim=sim)
        _ORIG_APPLY(sim.agents, row, d, sim.streamer, sim.tick, sim=sim)
        actions.append(int(d.action))
    return actions


def main() -> int:
    print("=" * 80)
    print("P160 — rock-wall marking: the agent loop CONSUMES C20 (closes a bite of D12/R0; "
          "the symbolic axis' 2nd consumer)")
    print("=" * 80)

    sim, coords = _build()
    summary = rc.canvas_summary(sim)
    print(f"  seed {hex(SEED_SOUND)}: streamed chunks={len(coords)} ; canvas_walls="
          f"{summary['n_canvas_walls']} (lasting={summary['n_lasting']} flaking={summary['n_flaking']}) "
          f"best_durability={summary['best_durability']}")
    print(f"  by material: {summary['by_material']} | by weather: {summary['by_weather']}")

    best = _best_canvas(sim, coords)
    if best is None:
        print("RESULT: FAIL — seed produced no carbonate wall (cannot exercise the wire).")
        return 1

    # 1 — LIVE loop closes a bite of D12 (the symbolic pillar's 2nd consumer)
    _calm_curious(sim, 0)
    _arm(sim, 0)
    _stand(sim, 0, best)
    cue0 = rc.canvas_cue_for_chunk(sim, best)
    acts = _drive_loop(sim, 0, n_ticks=12)
    marked = ActionKind.MARK in acts
    spent = 1.0 - float(sim.agents.inv_pigment[0])
    remembered = len(sim.agents.memory[0].known_canvas_locations)
    print(f"        agent#0 on {cue0.material} wall (durability={cue0.durability} "
          f"sound={cue0.sound_wall}): actions={[ActionKind(a).name for a in acts]}")
    print(f"        → pigment spent={spent:.3f} known_canvas={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent MARQUE la paroi (bouchée D12, 2e conso symbolique)",
          marked and spent > 0.0 and remembered >= 1,
          f"marked={marked} spent={spent:.3f} mem={remembered}")

    # 2 — outcome tracks the world's truth: SOUND wall lasts, KARST wall flakes (mensonge #11)
    ss, cs = _build(SEED_SOUND)
    bsnd = _best_canvas(ss, cs)
    _calm_curious(ss, 0)
    _arm(ss, 0)
    pxs, pys = _stand(ss, 0, bsnd)
    ev_s = _ORIG_APPLY(ss.agents, 0, cog.Decision(int(ActionKind.MARK), pxs, pys, 0.5),
                       ss.streamer, ss.tick, sim=ss)
    sound_lasts = bool(ev_s and ev_s[-1]["kind"] == "mark" and ev_s[-1]["lasts"])

    sk, ck = _build(SEED_KARST)
    flak = _flaking(sk, ck)
    karst_made_not_last = None
    karst_ok = True
    if flak is not None:
        _calm_curious(sk, 0)
        _arm(sk, 0)
        pxk, pyk = _stand(sk, 0, flak)
        ev_k = _ORIG_APPLY(sk.agents, 0, cog.Decision(int(ActionKind.MARK), pxk, pyk, 0.5),
                           sk.streamer, sk.tick, sim=sk)
        made = bool(ev_k and ev_k[-1]["kind"] == "mark" and ev_k[-1]["pigment_kg"] > 0.0)
        karst_made_not_last = made and (ev_k[-1]["lasts"] is False)
        karst_ok = karst_made_not_last
    print(f"        SOUND wall lasts={sound_lasts} | KARST mark-made-but-flakes="
          f"{karst_made_not_last} (flaking wall present={flak is not None})")
    check("2 — résultat = vérité du monde : paroi SAINE tient, paroi KARST écaille (mensonge #11)",
          sound_lasts and karst_ok,
          f"sound_lasts={sound_lasts} karst_made_not_last={karst_made_not_last}")

    # 3 — world never lies: a spot with no carbonate wall yields nothing
    sb, _cb = _build()
    _calm_curious(sb, 0)
    _arm(sb, 0)
    far_x = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    far_y = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sb.agents.pos[0, 0] = far_x
    sb.agents.pos[0, 1] = far_y
    no_wall = rc.prospect_canvas(sb, far_x, far_y) is None
    before = float(sb.agents.inv_pigment[0])
    _ORIG_APPLY(sb.agents, 0, cog.Decision(int(ActionKind.MARK), far_x, far_y, 0.5),
                sb.streamer, sb.tick, sim=sb)
    barren_inert = (float(sb.agents.inv_pigment[0]) == before
                    and len(sb.agents.memory[0].known_canvas_locations) == 0)
    check("3 — le monde ne ment jamais : aucune paroi carbonatée sous les pieds ⇒ RIEN",
          no_wall and barren_inert, f"no_wall={no_wall} inert={barren_inert}")

    # 4 — survival outranks marking
    sp, cp = _build()
    bp = _best_canvas(sp, cp)
    _calm_curious(sp, 0)
    _arm(sp, 0)
    px, py = _stand(sp, 0, bp)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    obs = Observation(row=0, pos=(px, py, 0.0), drives=drives, vitality=1.0,
                      nearest={"water": water}, near_agents=[],
                      dominant_drive=cog._dominant_drive(drives), tick=0,
                      reproduction_readiness=0.0)
    d_thirst = _ORIG_DECIDE(sp.agents, obs, sim=sp)
    check("4 — survie > marquage : un agent assoiffé (eau en vue) BOIT, ne marque pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 5 — requires a colour in hand: no pigment / no hue ⇒ never marks, explores
    su, cu = _build()
    bu = _best_canvas(su, cu)
    _calm_curious(su, 0)                       # leaves inv_pigment == 0, hue None
    _stand(su, 0, bu)
    seek_none = cog._seek_canvas(su.agents, 0,
                                 cog.perceive(su.agents, 0, su.streamer, tick=su.tick), su) is None
    d_unarmed = _ORIG_DECIDE(su.agents, cog.perceive(su.agents, 0, su.streamer, tick=su.tick), sim=su)
    check("5 — il faut une couleur en main : sans pigment/teinte l'agent ne marque pas, explore",
          seek_none and d_unarmed.action == int(ActionKind.EXPLORE),
          f"seek_none={seek_none} action={ActionKind(d_unarmed.action).name}")

    # 6 — same path as the real tick
    st, ct = _build()
    bt = _best_canvas(st, ct)
    step_ok = True
    try:
        st.step()
    except Exception as exc:               # pragma: no cover
        step_ok = False
        print(f"        sim.step() raised: {exc}")
    _calm_curious(st, 0)
    _arm(st, 0)
    _stand(st, 0, bt)
    obs_t = cog.perceive(st.agents, 0, st.streamer, tick=st.tick)
    d_live = _ORIG_DECIDE(st.agents, obs_t, sim=st)
    check("6 — même chemin que le tick réel : sim.step() OK + decide()→MARK sur l'agent armé",
          step_ok and d_live.action == int(ActionKind.MARK),
          f"step_ok={step_ok} decide={ActionKind(d_live.action).name}")

    # 7 — gate + determinism. Strip the C20 cue cache (querying rc.* lazily re-installs it,
    # so we null it AFTER positioning) → the wire must go inert with no scripted fallback.
    sng, cng = _build()
    _calm_curious(sng, 0)
    _arm(sng, 0)
    _stand(sng, 0, _best_canvas(sng, cng))
    sng._canvas_cue_cache = None          # strip the C20 capability
    gate_off = cog._seek_canvas(sng.agents, 0,
                                cog.perceive(sng.agents, 0, sng.streamer, tick=0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    b1 = _best_canvas(d1, c1)
    for s in (d1, d2):
        _calm_curious(s, 0)
        _arm(s, 0)
        _stand(s, 0, b1)
        _drive_loop(s, 0, n_ticks=8)
    det = (abs(float(d1.agents.inv_pigment[0]) - float(d2.agents.inv_pigment[0])) < 1e-12
           and len(d1.agents.memory[0].known_canvas_locations)
               == len(d2.agents.memory[0].known_canvas_locations))
    check("7 — gate (pas de C20 ⇒ inerte) + déterminisme même-seed (mark bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline: D8 by composition, D10 frozen
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    mark_in_enum = hasattr(ActionKind, "MARK")
    mem_field = hasattr(sim.agents.memory[0], "known_canvas_locations")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)            # the real, unwrapped handler
    mark_block = (src.split("ActionKind.MARK)", 1)[1].split("ActionKind.SLEEP)", 1)[0]
                  if "ActionKind.MARK)" in src else "")
    no_mine_at = bool(mark_block) and "mine_at(" not in mark_block
    no_profile = not hasattr(rc, "_PROFILE")
    d8_ok = (mark_in_enum and mem_field and len(contract.PY_TO_RUST) == 15
             and no_mine_at and no_profile)
    check("8 — discipline : MARK∈ActionKind, mémoire canvas, PY_TO_RUST==15, pas de mine_at (D10 gelé), pas de _PROFILE",
          d8_ok, f"mark={mark_in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p160_rock_canvas_mark_loop", "seed_sound": SEED_SOUND,
                   "seed_karst": SEED_KARST, "canvas_summary": summary,
                   "agent0_actions": [ActionKind(a).name for a in acts],
                   "agent0_pigment_spent": spent,
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
