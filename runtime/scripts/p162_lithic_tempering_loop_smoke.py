#!/usr/bin/env python3
"""P162 — The agent loop HEAT-TREATS a silica stone in the fire (D12 wire, 2026-06-29).

**Not a new capability — the 7th agent BEHAVIOUR that consumes the arc** (after DRINK/C3,
KNAP/C2, GATHER/C14, GRIND/C18, MARK/C20 and IGNITE/C7). AUDIT-DELTA-2026-06-23 named the
dominant hole **D12 / R0**: 20 truthful affordances, no agent loop ever invoked them. C7 wired
the VOÛTE — fire. This bite wires **fire's FIRST USE on a material**: C8 ``lithic_tempering``,
the oldest pyrotechnology after fire itself — roasting a cryptocrystalline silica nodule
(flint / chert) in the fire to win a keener cutting edge than cold percussion gives.

A survival-satisfied, curious agent that ALREADY KNOWS FIRE (``has_made_fire``) and SEES a
heat-responsive silica it could roast (``lithic_tempering.best_temper_site_near``) walks there
and TEMPERs. It is tried AFTER ``_seek_firesite`` (you must have made fire to heat-treat with
it) and BEFORE the symbolic ``_seek_ochre`` / ``_seek_canvas`` (tools before art). TEMPER fills
no NEW inventory — it reuses ``inv_tools`` (the cutting edge), raising it by the world-committed
``tempered_quality``. On a real chert+fire site the LIVE loop shows the whole stone-age arc
lived end to end: the agent KNAPs raw stone, IGNITEs a fire, then TEMPERs that stone sharper.

LE MENSONGE RENDU VISIBLE #12 (obsidian): "the best knapping stone must be the best to fire" —
FALSE. Obsidian is volcanic glass (base quality 1.0) and looks the prime candidate for the
hearth, yet heat yields it NO edge gain (already perfect, and it may shatter). The world returns
no temper cue on obsidian (``best_temper_site_near`` never routes there); standing on one and
tempering teaches it by acting (cue None → no edge). Cryptocrystalline chert responds strongly
(Δ≈0.20), macrocrystalline quartzite modestly (Δ≈0.12) — both emerge in the seed.

Discipline: COMPOSES C2 (the knappable silica) × C7 (the makeable fire), introduces NO new tell
(``PY_TO_RUST`` stays 15 — D8 by composition; lithic_tempering has no ``_PROFILE``), and does
NOT call ``geo.mine_at`` — TEMPER is non-mutating (roasting a nodule consumes no rock), so the
mutation frontier (D10) stays frozen. Determinism: pure cue derivation + memoised cues; no new
RNG.

Seed: 0xBEEF (a temperate grassland continent → chert/quartzite outcrops beside makeable fires;
the 1+1>2 gate of C8). No injection — the world really is this (the C7 wire p161 uses the same
seed).

Checks
------
 1.  LIVE loop: perceive→decide→apply on a real temper site, curious fire-ready agent ⇒ agent
     TEMPERs, its edge improves + it remembers + learns the skill (D12 bite — fire's first use).
 2.  Outcome = world truth: the edge gained tracks the site's ``tempered_quality``; chert gains
     more than quartzite (both silica responses emerge in the seed).
 3.  « Le monde ne ment jamais » + lie #12: roasting where nothing temperable is underfoot
     yields nothing; perception never routes the agent to a non-temperable (obsidian) site.
 4.  Survival outranks tempering: a critically thirsty agent with water in sight DRINKS.
 5.  Fire's first consumer: a never-made-fire agent does NOT temper even on a perfect site; a
     fire-knowing one does (the C7→C8 dependency, honoured not scripted).
 6.  Same path as the real tick: a full ``sim.step()`` runs clean and decide() on the prepared
     curious agent yields TEMPER (the wire is on the live tick path, not a side API).
 7.  Gate + determinism: no C8 ⇒ inert; same seed ⇒ bit-identical temper outcome.
 8.  D8/D10 discipline: TEMPER in ActionKind, memory field present, PY_TO_RUST==15, no mine_at,
     lithic_tempering has no _PROFILE.
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
import engine.lithic_tempering as lt                               # noqa: E402

# Capture the ORIGINAL decide/apply_decision before any installer (e.g. a later
# sim.step()) globally wraps them — the D12 wire lives in the originals.
_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_TEMPER = 0xBEEF
GRID = 12
OUT = os.path.join(ROOT, "journals", "p162_lithic_tempering_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:66s} {detail}")


def _build(seed: int = SEED_TEMPER, *, with_c8: bool = True):
    """A grassland Genesis sim with C8 (lithic_tempering) installed — which also installs the
    composed C2 (lithic) + C7 (fire) underneath, so the LIVE loop can KNAP raw stone, IGNITE a
    fire, then TEMPER that stone sharper — the whole stone-age arc lived end to end."""
    cfg = SimConfig(name="p162", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    if with_c8:
        lt.install_lithic_tempering(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def _best_tempersite(sim, coords):
    """The coord ``best_temper_site_near`` globally prefers — max (quality_gain, confidence)
    among temperable sites. Standing the agent here makes the underfoot site the in-window
    argmax, so the live loop deterministically TEMPERs."""
    best = None
    for coord in coords:
        cue = lt.temper_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        key = (cue.quality_gain, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _site_of_silica(sim, coords, kind: str):
    """A coord whose silica response is exactly ``kind`` (chert / quartzite)."""
    for coord in coords:
        cue = lt.temper_cue_for_chunk(sim, coord)
        if cue is not None and cue.silica_kind == kind:
            return coord
    return None


def _calm_curious(sim, row, *, knows_fire: bool = True, tool_secured: bool = False):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal", "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone",
                "inv_metal", "inv_tools", "inv_pigment"):
        getattr(sim.agents, inv)[row] = 0.0
    mem = sim.agents.memory[row]
    mem.known_temper_locations.clear()
    mem.has_tempered_stone = False
    mem.last_temper_gain = None
    mem.has_made_fire = bool(knows_fire)
    mem.last_fire_method = "PERCUSSION" if knows_fire else None
    if tool_secured:
        # Hand the agent an already-secured stone + warmth so the full decide() reaches TEMPER
        # directly (the emergent order KNAP → IGNITE → TEMPER otherwise plays out over ticks).
        sim.agents.inv_stone[row] = cog.TOOLSTONE_SATED_KG
        sim.agents.thermal[row] = 0.05


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


def _drive_loop(sim, row, n_ticks=16):
    """The canonical agent primitive — exactly what Simulation.step runs per agent."""
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
    print("P162 — heat treatment: the agent loop CONSUMES C8 (closes a bite of D12/R0; fire's "
          "FIRST use on matter is finally LIVED)")
    print("=" * 80)

    sim, coords = _build()
    summary = lt.tempering_summary(sim)
    print(f"  seed {hex(SEED_TEMPER)}: streamed chunks={len(coords)} ; temperable="
          f"{summary['n_chunks_temperable']} (rate={summary['temperable_rate']}) "
          f"best_gain={summary['best_quality_gain']} best_tempered={summary['best_tempered_quality']}")
    print(f"  by silica kind: {summary['by_silica_kind']}")

    best = _best_tempersite(sim, coords)
    if best is None:
        print("RESULT: FAIL — seed produced no temper site (cannot exercise the wire).")
        return 1

    # 1 — LIVE loop closes a bite of D12 (fire's first use on matter is LIVED). On a chert+fire
    # site a fresh curious agent naturally KNAPs raw stone, IGNITEs a fire, then TEMPERs it
    # sharper — the whole arc end to end. We prime it fire-ready + stone-secured so the loop
    # lands on TEMPER deterministically (the natural KNAP→IGNITE→TEMPER ramp is checked too).
    _calm_curious(sim, 0, tool_secured=True)
    _stand(sim, 0, best)
    cue0 = lt.temper_cue_for_chunk(sim, best)
    tools_before = float(sim.agents.inv_tools[0])
    acts = _drive_loop(sim, 0, n_ticks=16)
    tempered = ActionKind.TEMPER in acts
    sharpened = float(sim.agents.inv_tools[0]) > tools_before
    learned = bool(sim.agents.memory[0].has_tempered_stone)
    remembered = len(sim.agents.memory[0].known_temper_locations)
    print(f"        agent#0 on {cue0.silica_kind} temper site (gain={cue0.quality_gain}, "
          f"conf={cue0.confidence}): actions={[ActionKind(a).name for a in acts]}")
    print(f"        → inv_tools {tools_before:.3f}→{float(sim.agents.inv_tools[0]):.3f} "
          f"has_tempered_stone={learned} last_gain={sim.agents.memory[0].last_temper_gain} "
          f"known_temper_sites={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent TREMPE la pierre (bouchée D12, 1ʳᵉ pyrotechnologie vécue)",
          tempered and sharpened and learned and remembered >= 1,
          f"tempered={tempered} sharpened={sharpened} learned={learned} mem={remembered}")

    # 1b — the LIVED arc: from a naive empty-handed agent, the same site yields KNAP→IGNITE→TEMPER
    sa, ca = _build()
    ba = _best_tempersite(sa, ca)
    _calm_curious(sa, 0)                          # naive: no stone, no fire, mildly chilly
    _stand(sa, 0, ba)
    acts_arc = _drive_loop(sa, 0, n_ticks=20)
    names = [ActionKind(a).name for a in acts_arc]
    arc_lived = ("KNAP" in names and "IGNITE" in names and "TEMPER" in names
                 and names.index("IGNITE") < names.index("TEMPER"))
    check("1b — l'arc VÉCU : un agent nu enchaîne KNAP → IGNITE → TEMPER sur le même site (feu avant trempe)",
          arc_lived, f"actions={names}")

    # 2 — outcome tracks the world's truth: chert gains more than quartzite (both emerge)
    sp_chert = _site_of_silica(sim, coords, "chert")
    sp_qz = _site_of_silica(sim, coords, "quartzite")
    detail2 = []
    gains = {}
    for label, coord in (("chert", sp_chert), ("quartzite", sp_qz)):
        if coord is None:
            detail2.append(f"{label}=absent")
            continue
        s2, _c2 = _build()
        _calm_curious(s2, 0, tool_secured=True)
        px, py = _stand(s2, 0, coord)
        ev = _ORIG_APPLY(s2.agents, 0, cog.Decision(int(ActionKind.TEMPER), px, py, 0.5),
                         s2.streamer, s2.tick, sim=s2)
        gains[label] = float(ev[-1]["quality_gain"]) if ev else 0.0
        detail2.append(f"{label}Δ={gains.get(label)}")
    truth_ok = ("chert" in gains and gains["chert"] > 0.0
                and (("quartzite" not in gains) or gains["chert"] > gains["quartzite"]))
    check("2 — résultat = vérité du monde : Δqualité suit tempered_quality ; chert > quartzite",
          truth_ok, " ".join(detail2))

    # 3 — world never lies + lie #12: no temperable underfoot ⇒ nothing; never routed to obsidian
    sb, _cb = _build()
    _calm_curious(sb, 0)
    far_x = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    far_y = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sb.agents.pos[0, 0] = far_x
    sb.agents.pos[0, 1] = far_y
    no_temper = lt.prospect_tempering(sb, far_x, far_y) is None
    _ORIG_APPLY(sb.agents, 0, cog.Decision(int(ActionKind.TEMPER), far_x, far_y, 0.5),
                sb.streamer, sb.tick, sim=sb)
    barren_inert = (float(sb.agents.inv_tools[0]) == 0.0
                    and sb.agents.memory[0].has_tempered_stone is False)
    sr, cr = _build()
    _calm_curious(sr, 0, tool_secured=True)
    _stand(sr, 0, _best_tempersite(sr, cr))
    pick = lt.best_temper_site_near(sr, 0, perception_radius_m=cog.TEMPER_PERCEPT_M)
    routed_ok = pick is not None and pick.temperable and pick.silica_kind in ("chert", "quartzite")
    check("3 — le monde ne ment jamais (+ mensonge #12 obsidienne) : rien sous les pieds ⇒ RIEN ; jamais routé vers du non-trempable",
          no_temper and barren_inert and routed_ok,
          f"no_temper={no_temper} inert={barren_inert} routed_temperable={routed_ok}")

    # 4 — survival outranks tempering
    sv, cv = _build()
    bv = _best_tempersite(sv, cv)
    _calm_curious(sv, 0, tool_secured=True)
    px, py = _stand(sv, 0, bv)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    obs = Observation(row=0, pos=(px, py, 0.0), drives=drives, vitality=1.0,
                      nearest={"water": water}, near_agents=[],
                      dominant_drive=cog._dominant_drive(drives), tick=0,
                      reproduction_readiness=0.0)
    d_thirst = _ORIG_DECIDE(sv.agents, obs, sim=sv)
    check("4 — survie > trempe : un agent assoiffé (eau en vue) BOIT, ne trempe pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 5 — fire's first consumer: never-made-fire ⇒ no temper; fire-knowing ⇒ temper
    ss, cs = _build()
    bs = _best_tempersite(ss, cs)
    _calm_curious(ss, 0, knows_fire=False, tool_secured=True)
    ss.agents.memory[0].has_made_fire = False     # never made a fire → cannot heat-treat
    _stand(ss, 0, bs)
    naive_blocked = cog._seek_tempersite(ss.agents, 0, _obs_of(ss, 0), ss) is None
    _calm_curious(ss, 1, tool_secured=True)        # knows fire
    _stand(ss, 1, bs)
    fire_seeks = cog._seek_tempersite(ss.agents, 1, _obs_of(ss, 1), ss)
    fire_ok = fire_seeks is not None and fire_seeks.action == int(ActionKind.TEMPER)
    check("5 — 1ᵉʳ consommateur du feu : sans feu ⇒ pas de trempe ; sait faire le feu ⇒ trempe",
          naive_blocked and fire_ok, f"naive_blocked={naive_blocked} fire_tempers={fire_ok}")

    # 6 — same path as the real tick
    st, ct = _build()
    bt = _best_tempersite(st, ct)
    step_ok = True
    try:
        st.step()
    except Exception as exc:               # pragma: no cover
        step_ok = False
        print(f"        sim.step() raised: {exc}")
    _calm_curious(st, 0, tool_secured=True)
    _stand(st, 0, bt)
    obs_t = cog.perceive(st.agents, 0, st.streamer, tick=st.tick)
    d_live = _ORIG_DECIDE(st.agents, obs_t, sim=st)
    check("6 — même chemin que le tick réel : sim.step() OK + decide()→TEMPER sur l'agent curieux préparé",
          step_ok and d_live.action == int(ActionKind.TEMPER),
          f"step_ok={step_ok} decide={ActionKind(d_live.action).name}")

    # 7 — gate + determinism. Strip the C8 cue cache (querying lt.* lazily re-installs it, so we
    # null it AFTER positioning) → the wire must go inert with no scripted fallback.
    sng, cng = _build()
    _calm_curious(sng, 0, tool_secured=True)
    _stand(sng, 0, _best_tempersite(sng, cng))
    sng._temper_cue_cache = None          # strip the C8 capability
    gate_off = cog._seek_tempersite(sng.agents, 0, _obs_of(sng, 0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    b1 = _best_tempersite(d1, c1)
    for s in (d1, d2):
        _calm_curious(s, 0, tool_secured=True)
        _stand(s, 0, b1)
        _temper = cog.Decision(int(ActionKind.TEMPER), *_stand(s, 0, b1), 0.5)
        _ORIG_APPLY(s.agents, 0, _temper, s.streamer, s.tick, sim=s)
    det = (abs(float(d1.agents.inv_tools[0]) - float(d2.agents.inv_tools[0])) < 1e-12
           and abs((d1.agents.memory[0].last_temper_gain or 0.0)
                   - (d2.agents.memory[0].last_temper_gain or 0.0)) < 1e-12)
    check("7 — gate (pas de C8 ⇒ inerte) + déterminisme même-seed (trempe bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline: D8 by composition, D10 frozen
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    temper_in_enum = hasattr(ActionKind, "TEMPER")
    mem_field = hasattr(sim.agents.memory[0], "known_temper_locations")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)            # the real, unwrapped handler
    tmp_block = (src.split("ActionKind.TEMPER)", 1)[1].split("ActionKind.SLEEP)", 1)[0]
                 if "ActionKind.TEMPER)" in src else "")
    no_mine_at = bool(tmp_block) and "mine_at(" not in tmp_block
    no_profile = not hasattr(lt, "_PROFILE")
    d8_ok = (temper_in_enum and mem_field and len(contract.PY_TO_RUST) == 15
             and no_mine_at and no_profile)
    check("8 — discipline : TEMPER∈ActionKind, mémoire temper, PY_TO_RUST==15, pas de mine_at (D10 gelé), pas de _PROFILE",
          d8_ok, f"temper={temper_in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p162_lithic_tempering_loop", "seed": SEED_TEMPER,
                   "tempering_summary": summary,
                   "agent0_actions": [ActionKind(a).name for a in acts],
                   "agent0_last_gain": sim.agents.memory[0].last_temper_gain,
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
