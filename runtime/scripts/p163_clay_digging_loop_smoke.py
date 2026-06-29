#!/usr/bin/env python3
"""P163 — The agent loop DIGS workable clay from a bank (D12 wire, 2026-06-29, consumes C5).

**Not a new capability — the 8th agent BEHAVIOUR that consumes the arc** (after DRINK/C3, KNAP/C2,
GATHER/C14, GRIND/C18, MARK/C20, IGNITE/C7, TEMPER/C8). A **non-fire precursor** that restores the
fire/non-fire alternation after IGNITE+TEMPER, and lays in **the matter of the future pot**: C5
``clay_outcrop`` made clay banks *perceivable* (smooth ochre exposures, a plastic window, a pottery
grade); but no agent ever dug one. ``inv_clay`` is the substrate C9 ``ceramic_firing`` will consume.

A survival-satisfied, curious agent that SEES a clay bank it could work (``clay_outcrop.best_clay_near``)
walks there and DIGs a handful into its clay store. Distinct from the stone / pigment wires: DIG fills
its OWN inventory (``inv_clay``) and is non-fire. Tried after the tool/fire/temper cluster and before
the symbolic GRIND / MARK (useful matter before art). Each wire is inert unless its capability is
installed (gate on the cue cache), so this smoke installs ONLY C5 (clay_outcrop), proving DIG in
isolation.

LE MENSONGE RENDU VISIBLE #13 (the clay window): "a conspicuous clay bank is always good clay" —
FALSE. A plastic kaolinite inside its plastic window digs into fine ceramic-grade clay; a silty
SHALE_CLAY looks similar but works poorly; a bank too dry to shape / too wet a slurry yields little
until conditioned (``workable_now`` False → only the damp fraction). The agent learns smooth→pot and
plastic→holds-shape by digging.

Discipline: COMPOSES C5 (reads clay_outcrop), the WIRE introduces NO new tell (``PY_TO_RUST`` stays
15 — D8), and does NOT call ``geo.mine_at`` — DIG is surface collection (non-mutating), so the
mutation frontier (D10) stays frozen. ``inv_clay`` is a real inventory field (added in mirror of
``inv_pigment``: dataclass field + init loop + the two persistence lists, defensive load → old saves
compatible). Determinism: pure cue derivation + memoised cues; no new RNG.

Seeds: 0x42 (plentiful WORKABLE clay, both classes) ; 0xF00D (high-grade clay but none workable now —
the lie). No injection — the world really is this.

Checks
------
 1.  LIVE loop: perceive→decide→apply on a real clay bank, curious agent ⇒ DIG, clay store fills +
     remembers + records the clay class (D12 bite — the matter is LIVED).
 2.  Outcome = world truth: a plastic (ceramic-grade) bank yields more clay than a silty shale bank.
 3.  « Le monde ne ment jamais » + lie #13: digging a bank outside the plastic window yields only the
     damp fraction; digging where no clay is underfoot yields nothing.
 4.  Survival outranks digging: a critically thirsty agent with water in sight DRINKS.
 5.  Self-limiting: a clay-rich agent (inv_clay ≥ sated) stops seeking to dig.
 6.  Same path as the real tick: a full ``sim.step()`` runs clean and decide() on the curious agent
     yields DIG (the wire is on the live tick path, not a side API).
 7.  Gate + determinism: no C5 ⇒ inert; same seed ⇒ bit-identical dig outcome.
 8.  D8/D10 discipline: DIG in ActionKind, memory field present, PY_TO_RUST==15, no mine_at.
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
import engine.clay_outcrop as clo                                  # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_CLAY = 0x42
SEED_CLAY_DRY = 0xF00D
GRID = 12
OUT = os.path.join(ROOT, "journals", "p163_clay_digging_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:66s} {detail}")


def _build(seed: int = SEED_CLAY, *, with_c5: bool = True):
    cfg = SimConfig(name="p163", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c5:
        clo.install_clay_outcrop(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def _best_claysite(sim, coords):
    best = None
    for coord in coords:
        cue = clo.clay_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        key = (cue.pottery_grade, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _site_of_class(sim, coords, class_name: str):
    for coord in coords:
        cue = clo.clay_cue_for_chunk(sim, coord)
        if cue is not None and cue.clay_class.name == class_name:
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
                "inv_metal", "inv_tools", "inv_pigment", "inv_clay"):
        getattr(sim.agents, inv)[row] = 0.0
    mem = sim.agents.memory[row]
    mem.known_clay_locations.clear()
    mem.last_clay_class = None


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _drive_loop(sim, row, n_ticks=10):
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
    print("P163 — clay digging: the agent loop CONSUMES C5 (closes a bite of D12/R0; the matter of "
          "the future pot is LIVED — a non-fire precursor)")
    print("=" * 80)

    sim, coords = _build()
    summary = clo.clay_cue_summary(sim)
    print(f"  seed {hex(SEED_CLAY)}: streamed chunks={len(coords)} ; clay cues="
          f"{summary.get('n_chunks_cued')} workable={summary.get('n_chunks_workable')} "
          f"ceramic={summary.get('n_chunks_ceramic')} best_grade={summary.get('best_pottery_grade')}")
    print(f"  by clay class: {summary.get('by_class')}")

    best = _best_claysite(sim, coords)
    if best is None:
        print("RESULT: FAIL — seed produced no clay (cannot exercise the wire).")
        return 1

    # 1 — LIVE loop closes a bite of D12 (the matter of the future pot is LIVED)
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    cue0 = clo.clay_cue_for_chunk(sim, best)
    clay_before = float(sim.agents.inv_clay[0])
    acts = _drive_loop(sim, 0, n_ticks=10)
    dug = ActionKind.DIG in acts
    filled = float(sim.agents.inv_clay[0]) > clay_before
    learned = sim.agents.memory[0].last_clay_class is not None
    remembered = len(sim.agents.memory[0].known_clay_locations)
    print(f"        agent#0 on {cue0.clay_class.name} bank (grade={cue0.pottery_grade}, "
          f"workable={cue0.workable_now}): actions={[ActionKind(a).name for a in acts]}")
    print(f"        → inv_clay {clay_before:.3f}→{float(sim.agents.inv_clay[0]):.3f} "
          f"last_clay_class={sim.agents.memory[0].last_clay_class} known_clay={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent CREUSE l'argile (bouchée D12, la matière vécue)",
          dug and filled and learned and remembered >= 1,
          f"dug={dug} filled={filled} learned={learned} mem={remembered}")

    # 2 — outcome tracks the world's truth: plastic (ceramic) yields more than silty shale
    cp = _site_of_class(sim, coords, "PLASTIC_CLAY")
    cs = _site_of_class(sim, coords, "SHALE_CLAY")
    yields = {}
    detail2 = []
    for label, coord in (("plastic", cp), ("shale", cs)):
        if coord is None:
            detail2.append(f"{label}=absent")
            continue
        s2, _c2 = _build()
        _calm_curious(s2, 0)
        px, py = _stand(s2, 0, coord)
        ev = _ORIG_APPLY(s2.agents, 0, cog.Decision(int(ActionKind.DIG), px, py, 0.5),
                         s2.streamer, s2.tick, sim=s2)
        yields[label] = float(ev[-1]["clay_kg"]) if ev else 0.0
        detail2.append(f"{label}={yields.get(label)}")
    truth_ok = ("plastic" in yields and "shale" in yields and yields["plastic"] > yields["shale"])
    check("2 — résultat = vérité du monde : argile plastique (céramique) rend plus que schiste silteux",
          truth_ok, " ".join(detail2))

    # 3 — world never lies + lie #13: damp bank yields only the reduced fraction; no clay ⇒ nothing
    sd, cd = _build(seed=SEED_CLAY_DRY)
    bd = _best_claysite(sd, cd)
    lie_ok = False
    if bd is not None:
        cue_d = clo.clay_cue_for_chunk(sd, bd)
        if not cue_d.workable_now:
            _calm_curious(sd, 0)
            px, py = _stand(sd, 0, bd)
            ev = _ORIG_APPLY(sd.agents, 0, cog.Decision(int(ActionKind.DIG), px, py, 0.5),
                             sd.streamer, sd.tick, sim=sd)
            expected = cog.CLAY_DIG_KG * float(cue_d.pottery_grade) * cog.DAMP_CLAY_FACTOR
            lie_ok = bool(ev and ev[-1]["workable_now"] is False
                          and abs(float(ev[-1]["clay_kg"]) - expected) < 1e-3)
    sb, _cb = _build()
    _calm_curious(sb, 0)
    far = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sb.agents.pos[0, 0] = far
    sb.agents.pos[0, 1] = far
    no_clay = clo.prospect_clay(sb, far, far) is None
    _ORIG_APPLY(sb.agents, 0, cog.Decision(int(ActionKind.DIG), far, far, 0.5),
                sb.streamer, sb.tick, sim=sb)
    barren_inert = float(sb.agents.inv_clay[0]) == 0.0
    check("3 — le monde ne ment jamais (+ mensonge #13) : hors fenêtre plastique ⇒ fraction humide ; pas d'argile ⇒ RIEN",
          lie_ok and no_clay and barren_inert,
          f"damp_lie={lie_ok} no_clay={no_clay} inert={barren_inert}")

    # 4 — survival outranks digging
    sv, cv = _build()
    bv = _best_claysite(sv, cv)
    _calm_curious(sv, 0)
    px, py = _stand(sv, 0, bv)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    obs = Observation(row=0, pos=(px, py, 0.0), drives=drives, vitality=1.0,
                      nearest={"water": water}, near_agents=[],
                      dominant_drive=cog._dominant_drive(drives), tick=0,
                      reproduction_readiness=0.0)
    d_thirst = _ORIG_DECIDE(sv.agents, obs, sim=sv)
    check("4 — survie > argile : un agent assoiffé (eau en vue) BOIT, ne creuse pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 5 — self-limiting: a clay-rich agent stops seeking
    ss, cs2 = _build()
    bs = _best_claysite(ss, cs2)
    _calm_curious(ss, 0)
    ss.agents.inv_clay[0] = cog.CLAY_SATED_KG + 0.1
    _stand(ss, 0, bs)
    sated = cog._seek_clay(ss.agents, 0, _obs_of(ss, 0), ss) is None
    check("5 — auto-limité : agent riche en argile (≥ sated) ne cherche plus à creuser",
          sated, f"sated_no_reseek={sated}")

    # 6 — same path as the real tick
    st, ct = _build()
    bt = _best_claysite(st, ct)
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
    check("6 — même chemin que le tick réel : sim.step() OK + decide()→DIG sur l'agent curieux",
          step_ok and d_live.action == int(ActionKind.DIG),
          f"step_ok={step_ok} decide={ActionKind(d_live.action).name}")

    # 7 — gate + determinism
    sng, cng = _build()
    _calm_curious(sng, 0)
    _stand(sng, 0, _best_claysite(sng, cng))
    sng._clay_cue_cache = None            # strip C5
    gate_off = cog._seek_clay(sng.agents, 0, _obs_of(sng, 0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    b1 = _best_claysite(d1, c1)
    for s in (d1, d2):
        _calm_curious(s, 0)
        px, py = _stand(s, 0, b1)
        _ORIG_APPLY(s.agents, 0, cog.Decision(int(ActionKind.DIG), px, py, 0.5),
                    s.streamer, s.tick, sim=s)
    det = abs(float(d1.agents.inv_clay[0]) - float(d2.agents.inv_clay[0])) < 1e-12
    check("7 — gate (pas de C5 ⇒ inerte) + déterminisme même-seed (dig bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline: D8 (no new tell from the wire) + D10 frozen
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    dig_in_enum = hasattr(ActionKind, "DIG")
    mem_field = hasattr(sim.agents.memory[0], "known_clay_locations")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)
    dig_block = (src.split("ActionKind.DIG)", 1)[1].split("ActionKind.SLEEP)", 1)[0]
                 if "ActionKind.DIG)" in src else "")
    no_mine_at = bool(dig_block) and "mine_at(" not in dig_block
    d8_ok = (dig_in_enum and mem_field and len(contract.PY_TO_RUST) == 15 and no_mine_at)
    check("8 — discipline : DIG∈ActionKind, mémoire clay, PY_TO_RUST==15 (wire sans nouveau tell), pas de mine_at (D10 gelé)",
          d8_ok, f"dig={dig_in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p163_clay_digging_loop", "seed": SEED_CLAY,
                   "clay_summary": summary,
                   "agent0_actions": [ActionKind(a).name for a in acts],
                   "agent0_last_clay_class": sim.agents.memory[0].last_clay_class,
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
