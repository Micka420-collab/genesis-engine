#!/usr/bin/env python3
"""P171 — The agent loop FORCES a draught on its kiln (D12 wire, 2026-06-30, consumes C12).

The 15th agent BEHAVIOUR that consumes the arc — and the 2nd APPARATUS the agent builds (the pendant
of C11's kiln: raise → force). C12 ``forced_draught`` made the forced furnace *perceivable* (a charcoal
-fed kiln blown by a bellows reaching past the natural-draught peak); but no agent ever worked the
bellows. An agent that has ALREADY BUILT A KILN (RAISE_KILN/C11) AND CARRIES fuel (GLEAN/C4) FORCE_
DRAUGHTs it — driving the furnace into the high-temp regime that finally VITRIFIES the refractory kaolin
(the step C9/C11 both deferred) and reaches the copper-smelting threshold. Appended to ``_ARC_SEEKS`` as
one line; consumes inv_fuel, adds NO new inventory. Installs ONLY C12 (which pulls in C11 + C1).

LE MENSONGE RENDU VISIBLE #20 (the wall the bellows cannot beat): a COMMON-clay kiln, blown ever harder,
SLUMPS — its wall caps just past copper (FORCED_COMMON_WALL_CAP_C) and NEVER vitrifies nor reaches the
iron regime; only the refractory KAOLIN furnace (the very clay that under-fires as a *pot* in C9) breaks
through to vitrification + iron. ``best_forced_site_near`` prefers the hottest. Learned by forcing.

Discipline: COMPOSES C11 × C4 (kiln skill × charcoal fuel), the WIRE introduces NO new tell
(``PY_TO_RUST`` stays 15 — D8), and is NON-MUTATING (consumes inv_fuel as the charcoal charge; no
``geo.mine_at``; D10 frozen). Fire-based (the furnace) → D9 alternance 0→1 after the non-fire CURE.
Determinism: pure cues + memoised; no RNG. Seed 0xBEEF (clay + fire; refractory + common walls).

Checks
------
 1.  LIVE perceive→decide→act→remember: a ready agent on the furnace it chooses ⇒ FORCE_DRAUGHT: fuel
     spent, the apparatus skill learned (has_forced_draught), the peak + site remembered.
 2.  Both dependencies: no kiln built ⇒ no force ; no fuel in hand ⇒ no force ; both ⇒ force.
 3.  Lie #20: a refractory furnace reaches a HIGHER forced peak than a common one AND vitrifies
     watertight ; a common-walled furnace caps just past copper and NEVER vitrifies.
 4.  « Le monde ne ment jamais » : forcing where no kiln is forceable keeps the fuel.
 5.  Survival outranks forcing.
 6.  Same path as the real tick: ``sim.step()`` runs clean and the forced wire is live post-step.
 7.  Gate + determinism: no C12 ⇒ inert ; same seed ⇒ bit-identical forced peak.
 8.  D8/D10 discipline: FORCE_DRAUGHT in ActionKind, memory field present, PY_TO_RUST==15, no mine_at.
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
import engine.forced_draught as fd                                 # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_FORCE = 0xBEEF
GRID = 12
OUT = os.path.join(ROOT, "journals", "p171_forced_draught_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:66s} {detail}")


def _build(seed: int = SEED_FORCE, *, with_c12: bool = True):
    cfg = SimConfig(name="p171", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8))
    geo.install_geology(sim)
    if with_c12:
        fd.install_forced_draught(sim)   # pulls in C11 kiln_draft + C1 surface_mineralization
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
        cue = fd.forced_cue_for_chunk(sim, coord)
        if cue is None or not cue.forceable:
            continue
        key = (cue.forced_peak_c, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _site_refractory(sim, coords, want):
    for coord in coords:
        cue = fd.forced_cue_for_chunk(sim, coord)
        if cue is not None and cue.forceable and bool(cue.wall_refractory) is want:
            return coord
    return None


def _ready(sim, row, *, built_kiln=True, fuel_kg=None):
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
    sim.agents.inv_fuel[row] = cog.FUEL_SATED_KG if fuel_kg is None else float(fuel_kg)
    sim.agents.thermal[row] = 0.05
    mem = sim.agents.memory[row]
    mem.known_forced_locations.clear()
    mem.has_forced_draught = False
    mem.last_forced_peak_c = None
    mem.has_built_kiln = bool(built_kiln)    # the C11 dependency (built the kiln we now force)
    mem.last_kiln_peak_c = 900.0 if built_kiln else None
    mem.has_made_fire = True                 # a kiln-builder already knows fire
    mem.last_fire_method = "PERCUSSION"


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
    print("P171 — forced draught: the agent loop CONSUMES C12 (closes a bite of D12/R0; the 2nd "
          "apparatus the agent builds — the bellows that vitrifies kaolin + opens copper)")
    print("=" * 80)

    sim, coords = _build()
    n_force = sum(1 for c in coords
                  if (cu := fd.forced_cue_for_chunk(sim, c)) is not None and cu.forceable)
    n_refr = sum(1 for c in coords
                 if (cu := fd.forced_cue_for_chunk(sim, c)) is not None and cu.forceable and cu.wall_refractory)
    print(f"  seed {hex(SEED_FORCE)}: streamed chunks={len(coords)} ; forceable={n_force} refractory={n_refr}")

    best = _best(sim, coords)
    if best is None:
        print("RESULT: FAIL — seed produced no forceable furnace.")
        return 1

    # 1 — LIVE perceive→decide→act→remember (stand on the wire's own pick → FORCE_DRAUGHT → force)
    _ready(sim, 0)
    _stand(sim, 0, best)
    pick = fd.best_forced_site_near(sim, 0, perception_radius_m=cog.FORCE_PERCEPT_M)
    _stand(sim, 0, pick.coord)
    cue0 = fd.forced_cue_for_chunk(sim, pick.coord)
    fuel_before = float(sim.agents.inv_fuel[0])
    seek = cog._seek_forcedraught(sim.agents, 0, _obs_of(sim, 0), sim)
    decided = seek.action if seek is not None else None
    ev = _ORIG_APPLY(sim.agents, 0, cog.Decision(int(ActionKind.FORCE_DRAUGHT), *_stand(sim, 0, pick.coord), 0.5),
                     sim.streamer, sim.tick, sim=sim)
    forced = bool(sim.agents.memory[0].has_forced_draught)
    spent = float(sim.agents.inv_fuel[0]) < fuel_before
    remembered = len(sim.agents.memory[0].known_forced_locations)
    print(f"        agent#0 on {cue0.wall_material} furnace (kiln={cue0.kiln_peak_c}C → forced="
          f"{cue0.forced_peak_c}C, refractory={cue0.wall_refractory}, vitrifies={cue0.vitrifies_watertight}): "
          f"decide={ActionKind(decided).name if decided is not None else None}")
    print(f"        → inv_fuel {fuel_before:.3f}→{float(sim.agents.inv_fuel[0]):.3f} "
          f"has_forced_draught={forced} last_peak={sim.agents.memory[0].last_forced_peak_c}C sites={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent FORCE le tirage (bouchée D12, 2ᵉ appareillage)",
          decided == int(ActionKind.FORCE_DRAUGHT) and ev and ev[-1]["kind"] == "force_draught"
          and forced and spent and remembered >= 1,
          f"decide={ActionKind(decided).name if decided is not None else None} forced={forced} spent={spent} mem={remembered}")

    # 2 — both dependencies (no kiln built / no fuel in hand / both)
    sa, _ca = _build()
    _ready(sa, 0, built_kiln=False)
    _stand(sa, 0, best)
    no_kiln = cog._seek_forcedraught(sa.agents, 0, _obs_of(sa, 0), sa) is None
    sb, _cb = _build()
    _ready(sb, 0, fuel_kg=0.0)
    _stand(sb, 0, best)
    no_fuel = cog._seek_forcedraught(sb.agents, 0, _obs_of(sb, 0), sb) is None
    sc, cc = _build()
    _ready(sc, 0)
    pc = fd.best_forced_site_near(sc, 0, perception_radius_m=cog.FORCE_PERCEPT_M) if _best(sc, cc) else None
    if pc is not None:
        _stand(sc, 0, pc.coord)
    both = cog._seek_forcedraught(sc.agents, 0, _obs_of(sc, 0), sc) is not None
    check("2 — deux dépendances : sans four bâti ⇒ rien ; sans combustible en main ⇒ rien ; les deux ⇒ force",
          no_kiln and no_fuel and both, f"no_kiln={no_kiln} no_fuel={no_fuel} both={both}")

    # 3 — lie #20: refractory furnace hotter + vitrifies; common caps just past copper, never vitrifies
    cr = _site_refractory(sim, coords, True)
    ck = _site_refractory(sim, coords, False)
    inversion = False
    detail3 = []
    if cr is not None and ck is not None:
        cur = fd.forced_cue_for_chunk(sim, cr)
        cuk = fd.forced_cue_for_chunk(sim, ck)
        inversion = (cur.forced_peak_c > cuk.forced_peak_c
                     and cur.vitrifies_watertight and not cuk.vitrifies_watertight)
        detail3 = [f"refr_peak={cur.forced_peak_c}/vitr={cur.vitrifies_watertight}",
                   f"common_peak={cuk.forced_peak_c}/vitr={cuk.vitrifies_watertight}"]
    else:
        detail3 = ["one wall class absent"]
    check("3 — le mur que le soufflet ne bat pas #20 : paroi réfractaire plus chaude + vitrifie ; commune jamais",
          inversion, " ".join(detail3))

    # 4 — world never lies (forcing where no kiln is forceable keeps the fuel)
    sn, _cn = _build()
    _ready(sn, 0, fuel_kg=2.0)
    far = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sn.agents.pos[0, 0] = far
    sn.agents.pos[0, 1] = far
    no_site = fd.prospect_forced_draught(sn, far, far) is None
    fb = float(sn.agents.inv_fuel[0])
    _ORIG_APPLY(sn.agents, 0, cog.Decision(int(ActionKind.FORCE_DRAUGHT), far, far, 0.5),
                sn.streamer, sn.tick, sim=sn)
    kept = float(sn.agents.inv_fuel[0]) == fb and sn.agents.memory[0].has_forced_draught is False
    check("4 — le monde ne ment jamais : pas de four forçable ⇒ combustible conservé",
          no_site and kept, f"no_site={no_site} fuel_kept={kept}")

    # 5 — survival outranks forcing
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
    check("5 — survie > forcer : un agent assoiffé (eau en vue) BOIT, ne force pas",
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
        s = cog._seek_forcedraught(st.agents, 0, _obs_of(st, 0), st)
        seek_act = int(s.action) if s is not None else None
    check("6 — même chemin que le tick réel : sim.step() OK + le wire forcé est vivant (FORCE_DRAUGHT/WALK_TO)",
          step_ok and seek_act in (int(ActionKind.FORCE_DRAUGHT), int(ActionKind.WALK_TO)),
          f"step_ok={step_ok} seek={ActionKind(seek_act).name if seek_act is not None else 'None'}")

    # 7 — gate + determinism
    sng, cng = _build()
    _ready(sng, 0)
    _stand(sng, 0, _best(sng, cng))
    sng._forced_draught_cue_cache = None
    gate_off = cog._seek_forcedraught(sng.agents, 0, _obs_of(sng, 0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    b1 = _best(d1, c1)
    peaks = []
    for s in (d1, d2):
        _ready(s, 0, fuel_kg=2.0)
        px, py = _stand(s, 0, b1)
        e = _ORIG_APPLY(s.agents, 0, cog.Decision(int(ActionKind.FORCE_DRAUGHT), px, py, 0.5),
                        s.streamer, s.tick, sim=s)
        peaks.append(e[-1]["forced_peak_c"] if e else None)
    det = peaks[0] is not None and peaks[0] == peaks[1]
    check("7 — gate (pas de C12 ⇒ inerte) + déterminisme même-seed (pic forcé bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    in_enum = hasattr(ActionKind, "FORCE_DRAUGHT")
    mem_field = hasattr(sim.agents.memory[0], "known_forced_locations")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)
    blk = (src.split("ActionKind.FORCE_DRAUGHT)", 1)[1].split("ActionKind.CURE)", 1)[0]
           if "ActionKind.FORCE_DRAUGHT)" in src else "")
    no_mine_at = bool(blk) and "mine_at(" not in blk
    d8_ok = (in_enum and mem_field and len(contract.PY_TO_RUST) == 15 and no_mine_at)
    check("8 — discipline : FORCE_DRAUGHT∈ActionKind, mémoire forced-site, PY_TO_RUST==15 (wire sans tell), pas de mine_at (D10 gelé)",
          d8_ok, f"force_draught={in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p171_forced_draught_loop", "seed": SEED_FORCE,
                   "forceable": n_force, "refractory": n_refr,
                   "agent0_last_forced_peak_c": sim.agents.memory[0].last_forced_peak_c,
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
