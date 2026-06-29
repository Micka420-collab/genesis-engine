#!/usr/bin/env python3
"""P168 — The agent loop GLEANS combustible fuel (D12 wire, 2026-06-29, consumes C4).

The 13th agent BEHAVIOUR that consumes the arc — a NON-FIRE precursor (the fuel that will FEED fires
and kilns, not be one). C4 ``combustible_outcrop`` made dark fuel exposures *perceivable* (peat /
oil-shale / coal); but no agent ever gleaned one. ``inv_fuel`` is durable combustible — coal is the
only smelting-grade fuel, the future enabler of C13 metallurgy. Appended to ``_ARC_SEEKS`` as one line.
Installs ONLY C4.

LE MENSONGE RENDU VISIBLE #18 (dark ≠ ready fuel): a coal / oil-shale exposure gleaned dry burns long
(yield ∝ calorific_grade); a spongy PEAT bog looks like fuel but is too WET to burn now
(``burnable_now`` False → only a damp fraction until cut & dried). ``best_fuel_near(require_burnable)``
routes to a dry source; gleaning a wet bog teaches the lie by acting.

Discipline: COMPOSES C4, the WIRE introduces NO new tell (``PY_TO_RUST`` stays 15 — D8), and is a
NON-MUTATING surface collection (no ``geo.mine_at``; D10 frozen). ``inv_fuel`` is a real field (added
like inv_salt/inv_lime — NOT inv_wood, which is the building-timber store). Determinism: pure cues +
memoised; no RNG. Seed 0xBEEF (coal + oil-shale exposures, all burnable, some smelting-grade).

Checks
------
 1.  LIVE loop: a curious agent on the best exposure ⇒ GLEAN: the fuel store fills + remembers the
     site + records the fuel class (D12 bite — durable fuel is LIVED).
 2.  Outcome = world truth: a COAL exposure yields more than an OIL_SHALE one.
 3.  « Le monde ne ment jamais » : gleaning where no fuel is underfoot yields nothing.
 4.  Survival outranks gleaning: a critically thirsty agent with water in sight DRINKS.
 5.  Self-limiting: a fuel-rich agent (inv_fuel ≥ sated) stops seeking.
 6.  Same path as the real tick: ``sim.step()`` runs clean and decide() yields GLEAN.
 7.  Gate + determinism: no C4 ⇒ inert; same seed ⇒ bit-identical glean outcome.
 8.  D8/D10 discipline: GLEAN in ActionKind, memory field present, PY_TO_RUST==15, no mine_at.
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
import engine.combustible_outcrop as co                            # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_FUEL = 0xBEEF
GRID = 12
OUT = os.path.join(ROOT, "journals", "p168_combustible_glean_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:66s} {detail}")


def _build(seed: int = SEED_FUEL, *, with_c4: bool = True):
    cfg = SimConfig(name="p168", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c4:
        co.install_combustible_outcrop(sim)
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
        cue = co.combustible_cue_for_chunk(sim, coord)
        if cue is None or not cue.burnable_now:
            continue
        key = (cue.calorific_grade, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _site_of_class(sim, coords, class_name):
    for coord in coords:
        cue = co.combustible_cue_for_chunk(sim, coord)
        if cue is not None and cue.fuel_class.name == class_name and cue.burnable_now:
            return coord
    return None


def _calm_curious(sim, row):
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
    mem = sim.agents.memory[row]
    mem.known_fuel_locations.clear()
    mem.last_fuel_class = None


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
    print("P168 — fuel gleaning: the agent loop CONSUMES C4 (closes a bite of D12/R0; durable "
          "combustible, the non-fire precursor that will feed fires & kilns)")
    print("=" * 80)

    sim, coords = _build()
    n_fuel = sum(1 for c in coords
                 if (cu := co.combustible_cue_for_chunk(sim, c)) is not None and cu.burnable_now)
    n_smelt = sum(1 for c in coords
                  if (cu := co.combustible_cue_for_chunk(sim, c)) is not None and cu.smelting_grade)
    print(f"  seed {hex(SEED_FUEL)}: streamed chunks={len(coords)} ; burnable fuel={n_fuel} smelting-grade={n_smelt}")

    best = _best(sim, coords)
    if best is None:
        print("RESULT: FAIL — seed produced no burnable fuel.")
        return 1

    # 1 — LIVE loop
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    cue0 = co.combustible_cue_for_chunk(sim, best)
    before = float(sim.agents.inv_fuel[0])
    acts = _drive_loop(sim, 0, n_ticks=8)
    gleaned = ActionKind.GLEAN in acts
    filled = float(sim.agents.inv_fuel[0]) > before
    learned = sim.agents.memory[0].last_fuel_class is not None
    remembered = len(sim.agents.memory[0].known_fuel_locations)
    print(f"        agent#0 on {cue0.fuel_class.name} exposure (grade={cue0.calorific_grade}, "
          f"smelting={cue0.smelting_grade}): actions={[ActionKind(a).name for a in acts]}")
    print(f"        → inv_fuel {before:.3f}→{float(sim.agents.inv_fuel[0]):.3f} "
          f"last_fuel_class={sim.agents.memory[0].last_fuel_class} known={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent GLANE le combustible (bouchée D12, le fuel durable vécu)",
          gleaned and filled and learned and remembered >= 1,
          f"gleaned={gleaned} filled={filled} learned={learned} mem={remembered}")

    # 2 — world truth: coal > oil_shale
    cc = _site_of_class(sim, coords, "COAL")
    cs = _site_of_class(sim, coords, "OIL_SHALE")
    yields = {}
    detail2 = []
    for label, coord in (("coal", cc), ("oil_shale", cs)):
        if coord is None:
            detail2.append(f"{label}=absent")
            continue
        s2, _c2 = _build()
        _calm_curious(s2, 0)
        px, py = _stand(s2, 0, coord)
        ev = _ORIG_APPLY(s2.agents, 0, cog.Decision(int(ActionKind.GLEAN), px, py, 0.5),
                         s2.streamer, s2.tick, sim=s2)
        yields[label] = float(ev[-1]["fuel_kg"]) if ev else 0.0
        detail2.append(f"{label}={yields.get(label)}")
    truth_ok = ("coal" in yields and "oil_shale" in yields and yields["coal"] > yields["oil_shale"])
    check("2 — résultat = vérité du monde : le CHARBON rend plus que le SCHISTE bitumineux",
          truth_ok, " ".join(detail2))

    # 3 — world never lies
    sb, _cb = _build()
    _calm_curious(sb, 0)
    far = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sb.agents.pos[0, 0] = far
    sb.agents.pos[0, 1] = far
    no_fuel = co.prospect_fuel(sb, far, far) is None
    _ORIG_APPLY(sb.agents, 0, cog.Decision(int(ActionKind.GLEAN), far, far, 0.5),
                sb.streamer, sb.tick, sim=sb)
    barren = float(sb.agents.inv_fuel[0]) == 0.0
    check("3 — le monde ne ment jamais : pas de combustible sous les pieds ⇒ RIEN",
          no_fuel and barren, f"no_fuel={no_fuel} inert={barren}")

    # 4 — survival
    sv, cv = _build()
    bv = _best(sv, cv)
    _calm_curious(sv, 0)
    px, py = _stand(sv, 0, bv)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    obs = Observation(row=0, pos=(px, py, 0.0), drives=drives, vitality=1.0,
                      nearest={"water": water}, near_agents=[],
                      dominant_drive=cog._dominant_drive(drives), tick=0, reproduction_readiness=0.0)
    d_thirst = _ORIG_DECIDE(sv.agents, obs, sim=sv)
    check("4 — survie > combustible : un agent assoiffé (eau en vue) BOIT, ne glane pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 5 — self-limiting
    ss, cs2 = _build()
    bs = _best(ss, cs2)
    _calm_curious(ss, 0)
    ss.agents.inv_fuel[0] = cog.FUEL_SATED_KG + 0.1
    _stand(ss, 0, bs)
    sated = cog._seek_fuel(ss.agents, 0, _obs_of(ss, 0), ss) is None
    check("5 — auto-limité : agent riche en combustible (≥ sated) ne cherche plus à glaner",
          sated, f"sated_no_reseek={sated}")

    # 6 — same path as the real tick
    st, ct = _build()
    bt = _best(st, ct)
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
    check("6 — même chemin que le tick réel : sim.step() OK + decide()→GLEAN sur l'agent curieux",
          step_ok and d_live.action == int(ActionKind.GLEAN),
          f"step_ok={step_ok} decide={ActionKind(d_live.action).name}")

    # 7 — gate + determinism
    sng, cng = _build()
    _calm_curious(sng, 0)
    _stand(sng, 0, _best(sng, cng))
    sng._combustible_cue_cache = None
    gate_off = cog._seek_fuel(sng.agents, 0, _obs_of(sng, 0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    b1 = _best(d1, c1)
    for s in (d1, d2):
        _calm_curious(s, 0)
        px, py = _stand(s, 0, b1)
        _ORIG_APPLY(s.agents, 0, cog.Decision(int(ActionKind.GLEAN), px, py, 0.5),
                    s.streamer, s.tick, sim=s)
    det = abs(float(d1.agents.inv_fuel[0]) - float(d2.agents.inv_fuel[0])) < 1e-12
    check("7 — gate (pas de C4 ⇒ inerte) + déterminisme même-seed (glean bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    in_enum = hasattr(ActionKind, "GLEAN")
    mem_field = hasattr(sim.agents.memory[0], "known_fuel_locations")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)
    blk = (src.split("ActionKind.GLEAN)", 1)[1].split("ActionKind.SLEEP)", 1)[0]
           if "ActionKind.GLEAN)" in src else "")
    no_mine_at = bool(blk) and "mine_at(" not in blk
    d8_ok = (in_enum and mem_field and len(contract.PY_TO_RUST) == 15 and no_mine_at)
    check("8 — discipline : GLEAN∈ActionKind, mémoire fuel, PY_TO_RUST==15 (wire sans tell), pas de mine_at (D10 gelé)",
          d8_ok, f"glean={in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p168_combustible_glean_loop", "seed": SEED_FUEL,
                   "burnable_fuel": n_fuel, "smelting_grade": n_smelt,
                   "agent0_actions": [ActionKind(a).name for a in acts],
                   "agent0_last_fuel_class": sim.agents.memory[0].last_fuel_class,
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
