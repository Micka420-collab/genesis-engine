#!/usr/bin/env python3
"""P158 — The agent loop GRINDS the rusty iron-hat earth into pigment (D12 wire, 2026-06-27).

**Not a new capability — the 4th agent BEHAVIOUR that consumes the arc** (after DRINK/C3,
KNAP/C2 and GATHER/C14). AUDIT-DELTA-2026-06-23 named the dominant hole **D12 / R0**: 20
truthful affordances, no agent loop ever invoked them. R-J15-2 asked for a 4th capability
wired through the canonical ADR-0009 loop — preferably one that begins to move a still
immobile emergence pillar. This is it: a survival-satisfied, curious agent that SEES a
usable rusty-earth ochre site (``ochre_grinding.best_ochre_site_near``) walks there and
GRINDS a handful into pigment. It is the FIRST agent behaviour to advance the **symbolic**
pillar (pigment = the substrate of the future mark / drawing).

Orthogonal to KNAP / GATHER: GRIND triturates a SURFACE earth (``collect_depth_m == 0``)
into its OWN inventory (``inv_pigment``), so it never competes with the raw tool-stone
pool — it is tried after ``_seek_toolstone`` (tool first, then symbol). Each wire is inert
unless its capability is installed (gate on the cue cache), so none perturbs the others'
scenarios — this smoke installs ONLY C18 (ochre_grinding), proving GRIND in isolation;
p153 installs only C2 (KNAP), p155 only C14 (GATHER).

LE MENSONGE RENDU VISIBLE (#9, the painter's lie): "a rusty earth always makes paint" —
FALSE. An OXIDE gossan (hematite → red ochre, magnetite → black) grinds to a stable,
lightfast pigment; a pyrite / lead / zinc gossan looks just as rusty but grinds to no
usable colour. The agent only learns the rust→colour correlation by grinding (rust ≠ red).

Discipline: COMPOSES C18 (reads ``ochre_grinding``, itself composing C1), introduces NO
new tell (``PY_TO_RUST`` stays 15 — D8 by composition), and does NOT call ``geo.mine_at``
— GRIND is surface collection, so the mutation frontier (D10) stays frozen. Non-fire (D9).
Determinism: pure cue derivation + memoised cues; no new RNG.

Seed 0x42 (a real grassland continent whose emergent iron-hats carry BOTH the oxide
pigment AND the rusty lie — no injection, the world really is this; verbatim from the C18
capability smoke p150).

Checks
------
 1.  LIVE loop: perceive→decide→apply on a real ochre site ⇒ agent GRINDS, gains pigment
     (inv_pigment) + a remembered ochre site (D12 bite).
 2.  Yield = world truth: an OXIDE gossan paints, a rusty SULFIDE gossan paints nothing
     (mensonge #9, pigment_quality read).
 3.  « Le monde ne ment jamais » : grinding where no gossan is perceived yields nothing.
 4.  Survival outranks grinding: a critically thirsty agent with water in sight DRINKS.
 5.  Bounded: once pigment-sated (inv_pigment ≥ PIGMENT_SATED_KG) the agent stops, explores.
 6.  Same path as the real tick: a full ``sim.step()`` runs clean and decide() on the
     prepared agent yields GRIND (the wire is on the live tick path, not a side API).
 7.  Gate + determinism: no C18 ⇒ inert; same seed ⇒ bit-identical grind outcome.
 8.  D8/D10 discipline: GRIND in ActionKind, memory list present, PY_TO_RUST==15, no mine_at.
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
import engine.ochre_grinding as og                                 # noqa: E402

# Capture the ORIGINAL decide/apply_decision before any installer (e.g. a later
# sim.step()) globally wraps them — the D12 wire lives in the originals.
_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED = 0x42
GRID = 12
OUT = os.path.join(ROOT, "journals", "p158_ochre_grinding_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:64s} {detail}")


def _build(seed: int = SEED, *, with_c18: bool = True):
    """A grassland Genesis sim with C18 (ochre_grinding) installed — and ONLY C18, so
    GRIND is exercised in isolation (KNAP / GATHER inert: C2 / C14 never installed)."""
    cfg = SimConfig(name="p158", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c18:
        og.install_ochre_grinding(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def _best_usable(sim, coords):
    """The coord ``best_ochre_site_near`` globally prefers — max (pigment_quality,
    confidence) among usable sites. Standing the agent here makes the underfoot site the
    in-window argmax, so the live loop deterministically GRINDS."""
    best = None
    for coord in coords:
        cue = og.ochre_cue_for_chunk(sim, coord)
        if cue is None or not cue.usable:
            continue
        key = (cue.pigment_quality, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _lie(sim, coords):
    """A perceivable-but-barren rusty gossan (pyrite / lead / zinc → no pigment)."""
    for coord in coords:
        cue = og.ochre_cue_for_chunk(sim, coord)
        if cue is not None and not cue.is_pigment:
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
    sim.agents.memory[row].known_ochre_locations.clear()


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
    print("P158 — ochre grinding: the agent loop CONSUMES C18 (closes a bite of D12/R0; opens the symbolic axis)")
    print("=" * 80)

    sim, coords = _build()
    summary = og.ochre_summary(sim)
    print(f"  seed {hex(SEED)}: streamed chunks={len(coords)} ; ochre_sites={summary['n_ochre_sites']} "
          f"(pigment={summary['n_pigment']} usable={summary['n_usable']} lie={summary['n_lie']}) "
          f"best_q={summary['best_pigment_quality']}")
    print(f"  pigment classes: {summary['by_pigment_class']} | minerals: {summary['by_mineral']}")

    best = _best_usable(sim, coords)
    lie = _lie(sim, coords)
    if best is None:
        print("RESULT: FAIL — seed produced no usable ochre site (cannot exercise the wire).")
        return 1

    # 1 — LIVE loop closes a bite of D12
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    cue0 = og.ochre_cue_for_chunk(sim, best)
    acts = _drive_loop(sim, 0, n_ticks=12)
    ground = ActionKind.GRIND in acts
    pig = float(sim.agents.inv_pigment[0])
    remembered = len(sim.agents.memory[0].known_ochre_locations)
    print(f"        agent#0 on {cue0.mineral} gossan → {cue0.pigment_class} hue={cue0.hue}: "
          f"actions={[ActionKind(a).name for a in acts]}")
    print(f"        → inv_pigment={pig:.3f} known_ochre={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent BROIE l'ocre (bouchée D12, axe symbolique)",
          ground and pig > 0.0 and remembered >= 1,
          f"ground={ground} pigment={pig:.3f} mem={remembered}")

    # 2 — yield tracks the world's truth (oxide gossan paints, rusty sulfide paints nothing)
    so, co = _build()
    bo = _best_usable(so, co)
    _calm_curious(so, 0)
    pxo, pyo = _stand(so, 0, bo)
    _ORIG_APPLY(so.agents, 0, cog.Decision(int(ActionKind.GRIND), pxo, pyo, 0.5),
                so.streamer, so.tick, sim=so)
    oxide_pig = float(so.agents.inv_pigment[0])
    lie_pig = None
    lie_ok = True
    if lie is not None:
        sl, cl = _build()
        ll = _lie(sl, cl)
        _calm_curious(sl, 0)
        pxl, pyl = _stand(sl, 0, ll)
        _ORIG_APPLY(sl.agents, 0, cog.Decision(int(ActionKind.GRIND), pxl, pyl, 0.5),
                    sl.streamer, sl.tick, sim=sl)
        lie_pig = float(sl.agents.inv_pigment[0])
        lie_cue = og.ochre_cue_for_chunk(sl, ll)
        lie_ok = (lie_pig == 0.0 and lie_cue is not None and lie_cue.is_pigment is False)
    print(f"        oxide gossan pigment={oxide_pig:.3f} > rusty-lie pigment={lie_pig} "
          f"(lie present={lie is not None})")
    check("2 — rendement = vérité du monde : gossan oxyde peint, gossan rouille-sulfure ne peint pas (mensonge #9)",
          oxide_pig > 0.0 and lie_ok,
          f"oxide={oxide_pig:.3f} lie_pig={lie_pig} lie_ok={lie_ok}")

    # 3 — world never lies: a spot with no perceived gossan yields nothing
    sb, _cb = _build()
    _calm_curious(sb, 0)
    far_x = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    far_y = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sb.agents.pos[0, 0] = far_x
    sb.agents.pos[0, 1] = far_y
    no_cue = og.prospect_ochre(sb, far_x, far_y) is None
    _ORIG_APPLY(sb.agents, 0, cog.Decision(int(ActionKind.GRIND), far_x, far_y, 0.5),
                sb.streamer, sb.tick, sim=sb)
    barren_inert = (float(sb.agents.inv_pigment[0]) == 0.0
                    and len(sb.agents.memory[0].known_ochre_locations) == 0)
    check("3 — le monde ne ment jamais : un site sans gossan perçu ne rend RIEN",
          no_cue and barren_inert, f"no_cue={no_cue} inert={barren_inert}")

    # 4 — survival outranks grinding
    sp, cp = _build()
    bp = _best_usable(sp, cp)
    _calm_curious(sp, 0)
    px, py = _stand(sp, 0, bp)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    obs = Observation(row=0, pos=(px, py, 0.0), drives=drives, vitality=1.0,
                      nearest={"water": water}, near_agents=[],
                      dominant_drive=cog._dominant_drive(drives), tick=0,
                      reproduction_readiness=0.0)
    d_thirst = _ORIG_DECIDE(sp.agents, obs, sim=sp)
    check("4 — survie > broyage : un agent assoiffé (eau en vue) BOIT, ne broie pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 5 — bounded: once pigment-sated, the ochre wire is gated off (no more GRIND-seek). Whatever
    # downstream fall-through fires (PROSPECT on the gossan underfoot since C1 is now a wire ;
    # otherwise EXPLORE) is acceptable — the contract under test is « not GRIND ».
    ss, cs = _build()
    bs = _best_usable(ss, cs)
    _calm_curious(ss, 0)
    _stand(ss, 0, bs)
    ss.agents.inv_pigment[0] = cog.PIGMENT_SATED_KG + 0.1   # already carrying enough
    obs_s = cog.perceive(ss.agents, 0, ss.streamer, tick=ss.tick)
    d_sated = _ORIG_DECIDE(ss.agents, obs_s, sim=ss)
    check("5 — borné : une fois rassasié (inv_pigment≥seuil) l'agent ne broie plus (fall-through PROSPECT/EXPLORE)",
          d_sated.action != int(ActionKind.GRIND),
          f"action={ActionKind(d_sated.action).name} sated_kg={cog.PIGMENT_SATED_KG}")

    # 6 — same path as the real tick
    st, ct = _build()
    bt = _best_usable(st, ct)
    _calm_curious(st, 0)
    _stand(st, 0, bt)
    step_ok = True
    try:
        st.step()
    except Exception as exc:               # pragma: no cover
        step_ok = False
        print(f"        sim.step() raised: {exc}")
    _calm_curious(st, 0)
    _stand(st, 0, bt)
    obs_t = cog.perceive(st.agents, 0, st.streamer, tick=st.tick)
    d_live = _ORIG_DECIDE(st.agents, obs_t, sim=st)
    check("6 — même chemin que le tick réel : sim.step() OK + decide()→GRIND sur l'agent préparé",
          step_ok and d_live.action == int(ActionKind.GRIND),
          f"step_ok={step_ok} decide={ActionKind(d_live.action).name}")

    # 7 — gate + determinism. Strip the C18 cue cache (querying og.* lazily re-installs
    # it, so we null it AFTER positioning) → the wire must go inert with no scripted fallback.
    sng, cng = _build()
    _calm_curious(sng, 0)
    _stand(sng, 0, _best_usable(sng, cng))
    sng._ochre_cue_cache = None          # strip the C18 capability
    gate_off = cog._seek_ochre(sng.agents, 0,
                               cog.perceive(sng.agents, 0, sng.streamer, tick=0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    b1 = _best_usable(d1, c1)
    for s in (d1, d2):
        _calm_curious(s, 0)
        _stand(s, 0, b1)
        _drive_loop(s, 0, n_ticks=8)
    det = (abs(float(d1.agents.inv_pigment[0]) - float(d2.agents.inv_pigment[0])) < 1e-12
           and len(d1.agents.memory[0].known_ochre_locations)
               == len(d2.agents.memory[0].known_ochre_locations))
    check("7 — gate (pas de C18 ⇒ inerte) + déterminisme même-seed (grind bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline: D8 by composition, D10 frozen
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    grind_in_enum = hasattr(ActionKind, "GRIND")
    mem_field = hasattr(sim.agents.memory[0], "known_ochre_locations")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)            # the real, unwrapped handler
    grind_block = (src.split("ActionKind.GRIND)", 1)[1].split("ActionKind.SLEEP)", 1)[0]
                   if "ActionKind.GRIND)" in src else "")
    no_mine_at = bool(grind_block) and "mine_at(" not in grind_block
    no_profile = not hasattr(og, "_PROFILE")
    d8_ok = (grind_in_enum and mem_field and len(contract.PY_TO_RUST) == 15
             and no_mine_at and no_profile)
    check("8 — discipline : GRIND∈ActionKind, mémoire ochre, PY_TO_RUST==15, pas de mine_at (D10 gelé), pas de _PROFILE",
          d8_ok, f"grind={grind_in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p158_ochre_grinding_loop", "seed": SEED,
                   "ochre_summary": summary,
                   "agent0_actions": [ActionKind(a).name for a in acts],
                   "agent0_inv_pigment": pig,
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
