#!/usr/bin/env python3
"""P169 — The agent loop RAISES a draught kiln (D12 wire, 2026-06-29, consumes C11).

The 14th agent BEHAVIOUR that consumes the arc — and the FIRST APPARATUS the agent builds (the
pendant of C7's fire). C11 ``kiln_draft`` made kiln-building *perceivable* (wall-clay around a
makeable fire reaching a higher peak); but no agent ever lined a hearth. An agent that KNOWS FIRE
(IGNITE/C7) AND CARRIES clay (DIG/C5) RAISE_KILNs — enclosing the fire in clay walls so it burns
hotter (``kiln_peak_c``), the heat that will (a later bite) redeem C9 vitrification and C10 mortar.
Appended to ``_ARC_SEEKS`` as one line; consumes inv_clay, adds NO new inventory. Installs ONLY C11.

LE MENSONGE RENDU VISIBLE #19 (inversion-of-the-inversion): COMMON clay walls SLUMP at high heat
(modest peak), while the refractory KAOLIN that *under-fires as a pot* in an open fire (C9) makes the
BEST kiln wall. ``best_kiln_site_near`` prefers the hottest (refractory) kiln; any kiln beats the bare
open fire (draft_gain > 0). Learned by building.

Discipline: COMPOSES C5 × C7, the WIRE introduces NO new tell (``PY_TO_RUST`` stays 15 — D8), and is
NON-MUTATING (consumes inv_clay as the wall lining; no ``geo.mine_at``; D10 frozen). Determinism: pure
cues + memoised; no RNG. Seed 0xBEEF (clay + fire; refractory + common walls).

Checks
------
 1.  LIVE perceive→decide→act→remember: a ready agent on the kiln it chooses ⇒ RAISE_KILN: clay spent,
     the apparatus skill learned (has_built_kiln), the peak + site remembered.
 2.  Both dependencies: no fire ⇒ no kiln ; no clay in hand ⇒ no kiln ; both ⇒ kiln.
 3.  Lie #19: a refractory-walled kiln reaches a higher peak than a common one, and any kiln beats
     the bare open fire (draft_gain > 0).
 4.  « Le monde ne ment jamais » : building where no kiln is feasible keeps the clay.
 5.  Survival outranks building.
 6.  Same path as the real tick: ``sim.step()`` runs clean and the kiln wire is live post-step.
 7.  Gate + determinism: no C11 ⇒ inert; same seed ⇒ bit-identical kiln peak.
 8.  D8/D10 discipline: RAISE_KILN in ActionKind, memory field present, PY_TO_RUST==15, no mine_at.
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
import engine.kiln_draft as kd                                     # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_KILN = 0xBEEF
GRID = 12
OUT = os.path.join(ROOT, "journals", "p169_kiln_draft_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:66s} {detail}")


def _build(seed: int = SEED_KILN, *, with_c11: bool = True):
    cfg = SimConfig(name="p169", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8))
    geo.install_geology(sim)
    if with_c11:
        kd.install_kiln_draft(sim)
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
        cue = kd.kiln_cue_for_chunk(sim, coord)
        if cue is None or not cue.buildable:
            continue
        key = (cue.kiln_peak_c, cue.fire_confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _site_refractory(sim, coords, want):
    for coord in coords:
        cue = kd.kiln_cue_for_chunk(sim, coord)
        if cue is not None and cue.buildable and bool(cue.wall_refractory) is want:
            return coord
    return None


def _ready(sim, row, *, knows_fire=True, clay_kg=None):
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
    sim.agents.inv_clay[row] = cog.CLAY_SATED_KG if clay_kg is None else float(clay_kg)
    sim.agents.thermal[row] = 0.05
    mem = sim.agents.memory[row]
    mem.known_kiln_site_locations.clear()
    mem.has_built_kiln = False
    mem.last_kiln_peak_c = None
    mem.has_made_fire = bool(knows_fire)
    mem.last_fire_method = "PERCUSSION" if knows_fire else None


def _stand(sim, row, coord):
    px = (coord[0] + 0.5) * CHUNK_SIDE_M
    py = (coord[1] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[row, 0] = px
    sim.agents.pos[row, 1] = py
    return px, py


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
    print("P169 — kiln building: the agent loop CONSUMES C11 (closes a bite of D12/R0; the FIRST "
          "apparatus the agent builds — the heat that will redeem C9/C10)")
    print("=" * 80)

    sim, coords = _build()
    n_build = sum(1 for c in coords
                  if (cu := kd.kiln_cue_for_chunk(sim, c)) is not None and cu.buildable)
    n_refr = sum(1 for c in coords
                 if (cu := kd.kiln_cue_for_chunk(sim, c)) is not None and cu.buildable and cu.wall_refractory)
    print(f"  seed {hex(SEED_KILN)}: streamed chunks={len(coords)} ; buildable kilns={n_build} refractory={n_refr}")

    best = _best(sim, coords)
    if best is None:
        print("RESULT: FAIL — seed produced no buildable kiln.")
        return 1

    # 1 — LIVE perceive→decide→act→remember (stand on the wire's own pick → RAISE_KILN → build)
    _ready(sim, 0)
    _stand(sim, 0, best)
    pick = kd.best_kiln_site_near(sim, 0, perception_radius_m=cog.KILN_BUILD_PERCEPT_M)
    _stand(sim, 0, pick.coord)
    cue0 = kd.kiln_cue_for_chunk(sim, pick.coord)
    clay_before = float(sim.agents.inv_clay[0])
    seek = cog._seek_kilnbuild(sim.agents, 0, _obs_of(sim, 0), sim)
    decided = seek.action if seek is not None else None
    ev = _ORIG_APPLY(sim.agents, 0, cog.Decision(int(ActionKind.RAISE_KILN), *_stand(sim, 0, pick.coord), 0.5),
                     sim.streamer, sim.tick, sim=sim)
    built = bool(sim.agents.memory[0].has_built_kiln)
    spent = float(sim.agents.inv_clay[0]) < clay_before
    remembered = len(sim.agents.memory[0].known_kiln_site_locations)
    print(f"        agent#0 on {cue0.wall_clay_class} kiln (peak={cue0.kiln_peak_c}C, refractory="
          f"{cue0.wall_refractory}, open_fire={cue0.open_fire_peak_c}C): decide={ActionKind(decided).name if decided is not None else None}")
    print(f"        → inv_clay {clay_before:.3f}→{float(sim.agents.inv_clay[0]):.3f} "
          f"has_built_kiln={built} last_peak={sim.agents.memory[0].last_kiln_peak_c}C kilns={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent CONSTRUIT un four (bouchée D12, 1ᵉʳ appareillage)",
          decided == int(ActionKind.RAISE_KILN) and ev and ev[-1]["kind"] == "kiln_build"
          and built and spent and remembered >= 1,
          f"decide={ActionKind(decided).name if decided is not None else None} built={built} spent={spent} mem={remembered}")

    # 2 — both dependencies
    sa, _ca = _build()
    _ready(sa, 0, knows_fire=False)
    _stand(sa, 0, best)
    sa.agents.memory[0].has_made_fire = False
    no_fire = cog._seek_kilnbuild(sa.agents, 0, _obs_of(sa, 0), sa) is None
    sb, _cb = _build()
    _ready(sb, 0, clay_kg=0.0)
    _stand(sb, 0, best)
    no_clay = cog._seek_kilnbuild(sb.agents, 0, _obs_of(sb, 0), sb) is None
    sc, cc = _build()
    _ready(sc, 0)
    pc = kd.best_kiln_site_near(sc, 0, perception_radius_m=cog.KILN_BUILD_PERCEPT_M) if _best(sc, cc) else None
    if pc is not None:
        _stand(sc, 0, pc.coord)
    both = cog._seek_kilnbuild(sc.agents, 0, _obs_of(sc, 0), sc) is not None
    check("2 — deux dépendances : sans feu ⇒ rien ; sans argile en main ⇒ rien ; les deux ⇒ construit",
          no_fire and no_clay and both, f"no_fire={no_fire} no_clay={no_clay} both={both}")

    # 3 — lie #19: refractory > common; any kiln > open fire
    cr = _site_refractory(sim, coords, True)
    ck = _site_refractory(sim, coords, False)
    inversion = False
    detail3 = []
    if cr is not None and ck is not None:
        cur = kd.kiln_cue_for_chunk(sim, cr)
        cuk = kd.kiln_cue_for_chunk(sim, ck)
        inversion = (cur.kiln_peak_c > cuk.kiln_peak_c
                     and cur.draft_gain_c > 0.0 and cuk.draft_gain_c > 0.0)
        detail3 = [f"refr_peak={cur.kiln_peak_c}", f"common_peak={cuk.kiln_peak_c}"]
    else:
        detail3 = ["one wall class absent"]
    check("3 — inversion-de-l'inversion #19 : parois réfractaires > communes ; tout four > feu nu",
          inversion, " ".join(detail3))

    # 4 — world never lies
    sn, _cn = _build()
    _ready(sn, 0, clay_kg=2.0)
    far = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sn.agents.pos[0, 0] = far
    sn.agents.pos[0, 1] = far
    no_site = kd.prospect_kiln(sn, far, far) is None
    cb = float(sn.agents.inv_clay[0])
    _ORIG_APPLY(sn.agents, 0, cog.Decision(int(ActionKind.RAISE_KILN), far, far, 0.5),
                sn.streamer, sn.tick, sim=sn)
    kept = float(sn.agents.inv_clay[0]) == cb and sn.agents.memory[0].has_built_kiln is False
    check("4 — le monde ne ment jamais : pas de four constructible ⇒ argile conservée",
          no_site and kept, f"no_site={no_site} clay_kept={kept}")

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
    check("5 — survie > construire : un agent assoiffé (eau en vue) BOIT, ne construit pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 6 — same path as the real tick (the wire is live post-step)
    st, ct = _build()
    step_ok = True
    try:
        st.step()
    except Exception as exc:               # pragma: no cover
        step_ok = False
        print(f"        sim.step() raised: {exc}")
    ct2 = [c for c in ct if st.streamer.cache.get(c) is not None]
    bt = _best(st, ct2)
    seek_act = None
    if bt is not None:
        _ready(st, 0)
        _stand(st, 0, bt)
        s = cog._seek_kilnbuild(st.agents, 0, _obs_of(st, 0), st)
        seek_act = int(s.action) if s is not None else None
    check("6 — même chemin que le tick réel : sim.step() OK + le wire four est vivant (RAISE_KILN/WALK_TO)",
          step_ok and seek_act in (int(ActionKind.RAISE_KILN), int(ActionKind.WALK_TO)),
          f"step_ok={step_ok} seek={ActionKind(seek_act).name if seek_act is not None else 'None'}")

    # 7 — gate + determinism
    sng, cng = _build()
    _ready(sng, 0)
    _stand(sng, 0, _best(sng, cng))
    sng._kiln_draft_cue_cache = None
    gate_off = cog._seek_kilnbuild(sng.agents, 0, _obs_of(sng, 0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    b1 = _best(d1, c1)
    peaks = []
    for s in (d1, d2):
        _ready(s, 0, clay_kg=2.0)
        px, py = _stand(s, 0, b1)
        e = _ORIG_APPLY(s.agents, 0, cog.Decision(int(ActionKind.RAISE_KILN), px, py, 0.5),
                        s.streamer, s.tick, sim=s)
        peaks.append(e[-1]["kiln_peak_c"] if e else None)
    det = peaks[0] is not None and peaks[0] == peaks[1]
    check("7 — gate (pas de C11 ⇒ inerte) + déterminisme même-seed (pic four bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    in_enum = hasattr(ActionKind, "RAISE_KILN")
    mem_field = hasattr(sim.agents.memory[0], "known_kiln_site_locations")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)
    blk = (src.split("ActionKind.RAISE_KILN)", 1)[1].split("ActionKind.SLEEP)", 1)[0]
           if "ActionKind.RAISE_KILN)" in src else "")
    no_mine_at = bool(blk) and "mine_at(" not in blk
    d8_ok = (in_enum and mem_field and len(contract.PY_TO_RUST) == 15 and no_mine_at)
    check("8 — discipline : RAISE_KILN∈ActionKind, mémoire kiln-site, PY_TO_RUST==15 (wire sans tell), pas de mine_at (D10 gelé)",
          d8_ok, f"raise_kiln={in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p169_kiln_draft_loop", "seed": SEED_KILN,
                   "buildable": n_build, "refractory": n_refr,
                   "agent0_last_kiln_peak_c": sim.agents.memory[0].last_kiln_peak_c,
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
