#!/usr/bin/env python3
"""P161 — The agent loop STRIKES a fire at a firestone site (D12 wire, 2026-06-28).

**Not a new capability — the 6th agent BEHAVIOUR that consumes the arc** (after DRINK/C3,
KNAP/C2, GATHER/C14, GRIND/C18 and MARK/C20). AUDIT-DELTA-2026-06-23 named the dominant hole
**D12 / R0**: 20 truthful affordances, no agent loop ever invoked them. This bite wires **the
VOÛTE** — fire. C7 ``fire_ignition`` made fire-making *perceivable* (a brown spark-stone, a
hard striker, dry grass); it is the keystone that turns the inert C1→C6 matters (copper, fuel,
clay, lime) into *actionable* ones (smelt, burn, fire, calcine). Until now no agent struck one.

A survival-satisfied, curious agent that is mildly chilly (or has never made fire) and SEES a
site where a spark truly takes (``fire_ignition.best_firesite_near``) walks there and IGNITEs.
Distinct from the other wires: IGNITE fills NO portable inventory — the product is WARMTH (the
agent's own thermal drive eases) and the learned skill (``has_made_fire``). It is tried AFTER
``_seek_toolstone`` (secure stone first) and BEFORE the symbolic ``_seek_ochre`` /
``_seek_canvas`` (warmth before art). Each wire is inert unless its capability is installed
(gate on the cue cache), so this smoke installs ONLY C7 (fire_ignition), proving IGNITE in
isolation.

LE MENSONGE RENDU VISIBLE (the fire lie): "a lush green meadow always makes good tinder" —
FALSE. A spark takes only over DRY tinder; a DAMP meadow looks like fuel but a strike won't
catch (``prospect_ignition`` returns None — the world names the missing ingredient). Two
physically distinct methods emerge: PERCUSSION (pyrite firestone + hard striker over dry-enough
tinder) and FRICTION (bone-dry tinder, no minerals). The agent learns the firestone→flame link
by acting.

Discipline: COMPOSES C7 (reads ``fire_ignition``, itself composing C1 pyrite + C2 striker),
introduces NO new tell (``PY_TO_RUST`` stays 15 — D8 by composition; C7 has no ``_PROFILE``),
and does NOT call ``geo.mine_at`` — IGNITE is non-mutating (striking a spark consumes no rock),
so the mutation frontier (D10) stays frozen. Determinism: pure cue derivation + memoised cues;
no new RNG.

Seed: 0xBEEF (a temperate grassland continent → dry tinder + pyrite firestones). No injection —
the world really is this (the C7 capability smoke p139 uses the same seed).

Checks
------
 1.  LIVE loop: perceive→decide→apply on a real firesite, curious chilly agent ⇒ agent IGNITES,
     warms + remembers + learns the skill (D12 bite, the VOÛTE is finally LIVED).
 2.  Outcome = world truth: the struck method matches the site's cue (PERCUSSION over a real
     pyrite firestone + striker, FRICTION over bone-dry tinder) — both emerge in the seed.
 3.  « Le monde ne ment jamais » : igniting where no firestone is underfoot yields nothing.
 4.  Survival outranks fire-making: a critically thirsty agent with water in sight DRINKS.
 5.  Self-limiting & honest: a warm agent that already knows fire does NOT re-strike; a
     never-made-fire agent still seeks one (first discovery by curiosity).
 6.  Same path as the real tick: a full ``sim.step()`` runs clean and decide() on the chilly
     curious agent yields IGNITE (the wire is on the live tick path, not a side API).
 7.  Gate + determinism: no C7 ⇒ inert; same seed ⇒ bit-identical ignition outcome.
 8.  D8/D10 discipline: IGNITE in ActionKind, memory field present, PY_TO_RUST==15, no mine_at,
     fire_ignition has no _PROFILE.
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
import engine.fire_ignition as fi                                  # noqa: E402

# Capture the ORIGINAL decide/apply_decision before any installer (e.g. a later
# sim.step()) globally wraps them — the D12 wire lives in the originals.
_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_FIRE = 0xBEEF
GRID = 12
OUT = os.path.join(ROOT, "journals", "p161_fire_ignition_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:66s} {detail}")


def _build(seed: int = SEED_FIRE, *, with_c7: bool = True):
    """A grassland Genesis sim with C7 (fire_ignition) installed — and ONLY C7, so IGNITE is
    exercised in isolation (KNAP / GATHER / GRIND / MARK inert: C2 / C14 / C18 / C20 never
    installed)."""
    cfg = SimConfig(name="p161", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c7:
        fi.install_fire_ignition(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def _best_firesite(sim, coords):
    """The coord ``best_firesite_near`` globally prefers — max (method, confidence) among
    fire-makeable sites. Standing the agent here makes the underfoot site the in-window argmax,
    so the live loop deterministically IGNITEs."""
    best = None
    for coord in coords:
        cue = fi.ignition_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        key = (int(cue.method), cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _site_of_method(sim, coords, method_name: str):
    """A coord whose easiest method is exactly ``method_name`` (PERCUSSION / FRICTION)."""
    for coord in coords:
        cue = fi.ignition_cue_for_chunk(sim, coord)
        if cue is not None and cue.method.name == method_name:
            return coord
    return None


def _calm_curious(sim, row, thermal: float = 0.20):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal", "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.thermal[row] = float(thermal)
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone",
                "inv_metal", "inv_tools", "inv_pigment"):
        getattr(sim.agents, inv)[row] = 0.0
    mem = sim.agents.memory[row]
    mem.known_firesite_locations.clear()
    mem.has_made_fire = False
    mem.last_fire_method = None


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
    print("P161 — fire-making: the agent loop CONSUMES C7 (closes a bite of D12/R0; the VOÛTE "
          "of the stone-age arc is finally LIVED)")
    print("=" * 80)

    sim, coords = _build()
    summary = fi.ignition_summary(sim)
    print(f"  seed {hex(SEED_FIRE)}: streamed chunks={len(coords)} ; ignitable="
          f"{summary['n_chunks_ignitable']} (rate={summary['ignitable_rate']}) "
          f"percussion={summary['n_percussion']} friction={summary['n_friction']} "
          f"best_conf={summary['best_confidence']}")
    print(f"  by method: {summary['by_method']} | by tinder: {summary['by_tinder']}")

    best = _best_firesite(sim, coords)
    if best is None:
        print("RESULT: FAIL — seed produced no firesite (cannot exercise the wire).")
        return 1

    # 1 — LIVE loop closes a bite of D12 (the VOÛTE is finally LIVED)
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    cue0 = fi.ignition_cue_for_chunk(sim, best)
    thermal_before = float(sim.agents.thermal[0])
    acts = _drive_loop(sim, 0, n_ticks=12)
    ignited = ActionKind.IGNITE in acts
    warmed = float(sim.agents.thermal[0]) < thermal_before
    learned = bool(sim.agents.memory[0].has_made_fire)
    remembered = len(sim.agents.memory[0].known_firesite_locations)
    print(f"        agent#0 on {cue0.method.name} firesite (conf={cue0.confidence}): "
          f"actions={[ActionKind(a).name for a in acts]}")
    print(f"        → thermal {thermal_before:.3f}→{float(sim.agents.thermal[0]):.3f} "
          f"has_made_fire={learned} method={sim.agents.memory[0].last_fire_method} "
          f"known_firesites={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent ALLUME un feu (bouchée D12, la VOÛTE vécue)",
          ignited and warmed and learned and remembered >= 1,
          f"ignited={ignited} warmed={warmed} learned={learned} mem={remembered}")

    # 2 — outcome tracks the world's truth: the struck method matches the site (both emerge)
    sp_perc = _site_of_method(sim, coords, "PERCUSSION")
    sp_fric = _site_of_method(sim, coords, "FRICTION")
    method_truth = True
    detail2 = []
    for label, coord in (("PERCUSSION", sp_perc), ("FRICTION", sp_fric)):
        if coord is None:
            detail2.append(f"{label}=absent")
            continue
        s2, c2 = _build()
        _calm_curious(s2, 0, thermal=0.30)
        px, py = _stand(s2, 0, coord)
        ev = _ORIG_APPLY(s2.agents, 0, cog.Decision(int(ActionKind.IGNITE), px, py, 0.5),
                         s2.streamer, s2.tick, sim=s2)
        cue = fi.ignition_cue_for_chunk(s2, coord)
        ok = bool(ev and ev[-1]["kind"] == "ignite" and ev[-1]["method"] == cue.method.name)
        method_truth = method_truth and ok
        detail2.append(f"{label}={ev[-1]['method'] if ev else None}")
    check("2 — résultat = vérité du monde : la méthode allumée = celle du site (percussion/friction émergent)",
          method_truth and sp_perc is not None, " ".join(detail2))

    # 3 — world never lies: a spot with no firestone yields nothing
    sb, _cb = _build()
    _calm_curious(sb, 0)
    far_x = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    far_y = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sb.agents.pos[0, 0] = far_x
    sb.agents.pos[0, 1] = far_y
    no_fire = fi.prospect_ignition(sb, far_x, far_y) is None
    th_before = float(sb.agents.thermal[0])
    _ORIG_APPLY(sb.agents, 0, cog.Decision(int(ActionKind.IGNITE), far_x, far_y, 0.5),
                sb.streamer, sb.tick, sim=sb)
    barren_inert = (float(sb.agents.thermal[0]) == th_before
                    and sb.agents.memory[0].has_made_fire is False
                    and len(sb.agents.memory[0].known_firesite_locations) == 0)
    check("3 — le monde ne ment jamais : aucun firestone sous les pieds ⇒ RIEN",
          no_fire and barren_inert, f"no_fire={no_fire} inert={barren_inert}")

    # 4 — survival outranks fire-making
    sv, cv = _build()
    bv = _best_firesite(sv, cv)
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
    check("4 — survie > feu : un agent assoiffé (eau en vue) BOIT, n'allume pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 5 — self-limiting & honest: warm+knows ⇒ no re-seek; warm+naive ⇒ first discovery
    ss, cs = _build()
    bs = _best_firesite(ss, cs)

    def _obs_of(sim, row):
        a = sim.agents
        d = np.array([float(a.hunger[row]), float(a.thirst[row]), float(a.sleep[row]),
                      float(a.fatigue[row]), float(a.thermal[row]), float(a.pain[row]),
                      float(a.stress[row]), float(a.loneliness[row])], dtype=np.float32)
        return Observation(row=int(row), pos=(float(a.pos[row, 0]), float(a.pos[row, 1]), 0.0),
                           drives=d, vitality=1.0, nearest={}, near_agents=[],
                           dominant_drive=cog._dominant_drive(d), tick=0,
                           reproduction_readiness=0.0)

    _calm_curious(ss, 0, thermal=0.05)        # warm
    ss.agents.memory[0].has_made_fire = True   # already knows fire
    _stand(ss, 0, bs)
    sated = cog._seek_firesite(ss.agents, 0, _obs_of(ss, 0), ss) is None
    _calm_curious(ss, 1, thermal=0.05)        # warm, but…
    ss.agents.memory[1].has_made_fire = False  # …never made fire → curiosity drives it
    _stand(ss, 1, bs)
    naive = cog._seek_firesite(ss.agents, 1, _obs_of(ss, 1), ss)
    naive_seeks = naive is not None and naive.action == int(ActionKind.IGNITE)
    check("5 — auto-limité & honnête : chaud+sait ⇒ ne ré-allume pas ; chaud+naïf ⇒ 1ʳᵉ découverte",
          sated and naive_seeks, f"sated_no_reseek={sated} naive_first_discovery={naive_seeks}")

    # 6 — same path as the real tick
    st, ct = _build()
    bt = _best_firesite(st, ct)
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
    check("6 — même chemin que le tick réel : sim.step() OK + decide()→IGNITE sur l'agent curieux frileux",
          step_ok and d_live.action == int(ActionKind.IGNITE),
          f"step_ok={step_ok} decide={ActionKind(d_live.action).name}")

    # 7 — gate + determinism. Strip the C7 cue cache (querying fi.* lazily re-installs it, so
    # we null it AFTER positioning) → the wire must go inert with no scripted fallback.
    sng, cng = _build()
    _calm_curious(sng, 0)
    _stand(sng, 0, _best_firesite(sng, cng))
    sng._ignition_cue_cache = None        # strip the C7 capability
    gate_off = cog._seek_firesite(sng.agents, 0,
                                  cog.perceive(sng.agents, 0, sng.streamer, tick=0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    b1 = _best_firesite(d1, c1)
    for s in (d1, d2):
        _calm_curious(s, 0, thermal=0.30)
        _stand(s, 0, b1)
        _drive_loop(s, 0, n_ticks=8)
    det = (abs(float(d1.agents.thermal[0]) - float(d2.agents.thermal[0])) < 1e-12
           and d1.agents.memory[0].last_fire_method == d2.agents.memory[0].last_fire_method
           and len(d1.agents.memory[0].known_firesite_locations)
               == len(d2.agents.memory[0].known_firesite_locations))
    check("7 — gate (pas de C7 ⇒ inerte) + déterminisme même-seed (ignition bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline: D8 by composition, D10 frozen
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    ignite_in_enum = hasattr(ActionKind, "IGNITE")
    mem_field = hasattr(sim.agents.memory[0], "known_firesite_locations")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)            # the real, unwrapped handler
    ign_block = (src.split("ActionKind.IGNITE)", 1)[1].split("ActionKind.SLEEP)", 1)[0]
                 if "ActionKind.IGNITE)" in src else "")
    no_mine_at = bool(ign_block) and "mine_at(" not in ign_block
    no_profile = not hasattr(fi, "_PROFILE")
    d8_ok = (ignite_in_enum and mem_field and len(contract.PY_TO_RUST) == 15
             and no_mine_at and no_profile)
    check("8 — discipline : IGNITE∈ActionKind, mémoire firesite, PY_TO_RUST==15, pas de mine_at (D10 gelé), pas de _PROFILE",
          d8_ok, f"ignite={ignite_in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p161_fire_ignition_loop", "seed": SEED_FIRE,
                   "ignition_summary": summary,
                   "agent0_actions": [ActionKind(a).name for a in acts],
                   "agent0_method": sim.agents.memory[0].last_fire_method,
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
