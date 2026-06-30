#!/usr/bin/env python3
"""P172 — The agent loop PROSPECTs a surface stain (D12 wire, 2026-06-30, consumes C1).

The 16th agent BEHAVIOUR that consumes the arc — and the 1ᵉʳ ACTE COGNITIF/VISUEL de la boucle.
C1 ``surface_mineralization`` made the surface weathering stains *perceivable* (a truthful colour
over a real buried ore body); but no agent ever LEARNED what those colours meant. An agent that
SEES a coloured outcrop within ``PROSPECT_PERCEPT_M`` and HAS NOT YET READ that colour-group walks
there and PROSPECTs — recording ``(group, x, y)`` into ``known_ore_sites``, marking the group as
discovered in ``prospected_ore_groups`` (auto-limit per group), and learning by ASSOCIATION what
lies below. Appended to ``_ARC_SEEKS`` as one line; CONSUMES NO INVENTORY (pure cognition), adds
NO new tell (D8 composition only). Installs ONLY C1 surface_mineralization.

LE MENSONGE RENDU VISIBLE #21 (le mensonge cognitif): a striking VERT outcrop *means* one ore (the
agent guesses MALACHITE = copper); a humble RUSTY stain *means* SEVERAL (a gossan caps pyrite,
hematite, magnetite, galena, sphalerite — five possible ores under one colour). Visual richness ≠
underground richness. Learned by acting: the agent reads each colour-group ONCE and records what
the world says lies under it.

Discipline: COMPOSES C1 only, the WIRE introduces NO new tell (``PY_TO_RUST`` stays 15 — D8), and
is NON-MUTATING per excellence (no inventory consumed; no ``geo.mine_at``; D10 frozen). NON-FIRE
(visual / cognitive) → D9 alternance 1→0 after the fire-based FORCE_DRAUGHT. Determinism: pure cues
+ memoised; no RNG. Seed 0xC1 (thematic + spawns 3 expression groups: gossan / salt / sulfur).

Checks
------
 1.  LIVE perceive→decide→act→remember: a curious agent on a stain ⇒ PROSPECT: the group + site are
     remembered, the discovery flag set, the event emitted.
 2.  Per-group self-limit: re-prospecting the same group does NOT duplicate the group entry
     (idempotent discovery), but the site memory grows (FIFO bounded).
 3.  Multi-group exploration: after discovering group X, an agent on a different-colour stain Y
     decides to PROSPECT Y (the discovery tree branches by sight, not by repetition).
 4.  « Le monde ne ment jamais » : prospecting where no stain exists writes no memory.
 5.  Survival outranks prospecting.
 6.  Same path as the real tick: ``sim.step()`` runs clean and the wire is live post-step.
 7.  Gate + determinism: no C1 ⇒ inert ; same seed ⇒ bit-identical first-prospect group.
 8.  D8/D10 discipline: PROSPECT in ActionKind, memory fields present, PY_TO_RUST==15, no mine_at.
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
from engine import surface_mineralization as sm                     # noqa: E402
from engine.cognition import Observation, PerceivedTarget           # noqa: E402
from engine.agent import ActionKind, DriveKind                      # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_PROSPECT = 0xC1   # thematic + 3 expression groups (gossan / salt / sulfur)
GRID = 12
OUT = os.path.join(ROOT, "journals", "p172_prospect_ore_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:66s} {detail}")


def _build(seed: int = SEED_PROSPECT, *, with_c1: bool = True):
    cfg = SimConfig(name="p172", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8))
    geo.install_geology(sim)
    if with_c1:
        sm.install_surface_mineralization(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def _cued(sim, coords):
    out = []
    for coord in coords:
        cue = sm.surface_cue_for_chunk(sim, coord)
        if cue is not None:
            out.append((coord, cue))
    return out


def _coord_for_group(sim, coords, group):
    for coord in coords:
        cue = sm.surface_cue_for_chunk(sim, coord)
        if cue is not None and cue.group == group:
            return coord, cue
    return None, None


def _ready(sim, row):
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
    sim.agents.thermal[row] = 0.05
    mem = sim.agents.memory[row]
    mem.known_ore_sites.clear()
    mem.prospected_ore_groups.clear()
    mem.has_prospected_ore = False
    mem.last_prospect_group = None


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
    print("P172 — surface mineralization prospect: the agent loop CONSUMES C1 (1ᵉʳ acte purement "
          "COGNITIF/VISUEL — la fondation du futur D10 sans franchir D10)")
    print("=" * 80)

    sim, coords = _build()
    cued = _cued(sim, coords)
    groups_present = sorted({cu.group for _, cu in cued})
    print(f"  seed {hex(SEED_PROSPECT)}: streamed chunks={len(coords)} ; cued={len(cued)} ; "
          f"groups={groups_present}")

    if not cued:
        print("RESULT: FAIL — seed produced no surface cues.")
        return 1

    # 1 — LIVE perceive→decide→act→remember
    coord1, cue1 = cued[0]
    _ready(sim, 0)
    _stand(sim, 0, coord1)
    seek = cog._seek_prospect(sim.agents, 0, _obs_of(sim, 0), sim)
    decided = seek.action if seek is not None else None
    ev = _ORIG_APPLY(sim.agents, 0, cog.Decision(int(ActionKind.PROSPECT),
                                                  *_stand(sim, 0, coord1), 0.5),
                     sim.streamer, sim.tick, sim=sim)
    mem = sim.agents.memory[0]
    print(f"        agent#0 on {cue1.group} stain ({cue1.label}, mineral={cue1.mineral}, "
          f"dig={cue1.dig_depth_m:.2f}m): decide={ActionKind(decided).name if decided is not None else None}")
    print(f"        → has_prospected_ore={mem.has_prospected_ore} last_group={mem.last_prospect_group} "
          f"known_groups={mem.prospected_ore_groups} sites={len(mem.known_ore_sites)}")
    check("1 — LIVE perceive→decide→act→remember : l'agent LIT la couleur (bouchée D12, 1ᵉʳ cognitif)",
          decided == int(ActionKind.PROSPECT) and ev and ev[-1]["kind"] == "prospect"
          and mem.has_prospected_ore is True and len(mem.known_ore_sites) == 1
          and ev[-1]["first_for_group"] is True,
          f"decide={ActionKind(decided).name if decided is not None else None} group={mem.last_prospect_group}")

    # 2 — per-group idempotent learning + bounded site memory
    sa, ca = _build()
    cued_a = _cued(sa, ca)
    if not cued_a:
        check("2 — per-group idempotent learning + bounded site memory", False, "no cues")
    else:
        co2, cu2 = cued_a[0]
        _ready(sa, 0)
        _stand(sa, 0, co2)
        _ORIG_APPLY(sa.agents, 0, cog.Decision(int(ActionKind.PROSPECT),
                                                *_stand(sa, 0, co2), 0.5),
                    sa.streamer, sa.tick, sim=sa)
        _ORIG_APPLY(sa.agents, 0, cog.Decision(int(ActionKind.PROSPECT),
                                                *_stand(sa, 0, co2), 0.5),
                    sa.streamer, sa.tick, sim=sa)
        mema = sa.agents.memory[0]
        idem = mema.prospected_ore_groups.count(cu2.group) == 1
        sites_grow = len(mema.known_ore_sites) == 2   # site list grows (FIFO bounded at 32)
        check("2 — auto-limite par groupe (découverte binaire ; sites FIFO bornés)",
              idem and sites_grow,
              f"groups={mema.prospected_ore_groups} sites={len(mema.known_ore_sites)}")

    # 3 — multi-group exploration: after group X, on group Y → PROSPECT Y
    sb, cb = _build()
    cuedb_groups = sorted({cu.group for _, cu in _cued(sb, cb)})
    if len(cuedb_groups) < 2:
        check("3 — exploration multi-groupes : un agent prospecte une 2ᵉ couleur après la 1ʳᵉ",
              False, "only one group present")
    else:
        g1, g2 = cuedb_groups[:2]
        c_g1, _ = _coord_for_group(sb, cb, g1)
        c_g2, cu_g2 = _coord_for_group(sb, cb, g2)
        _ready(sb, 0)
        _stand(sb, 0, c_g1)
        _ORIG_APPLY(sb.agents, 0, cog.Decision(int(ActionKind.PROSPECT),
                                                *_stand(sb, 0, c_g1), 0.5),
                    sb.streamer, sb.tick, sim=sb)
        _stand(sb, 0, c_g2)
        seek_b = cog._seek_prospect(sb.agents, 0, _obs_of(sb, 0), sb)
        ev2 = _ORIG_APPLY(sb.agents, 0, cog.Decision(int(ActionKind.PROSPECT),
                                                      *_stand(sb, 0, c_g2), 0.5),
                          sb.streamer, sb.tick, sim=sb)
        memb = sb.agents.memory[0]
        ok3 = (seek_b is not None and seek_b.action == int(ActionKind.PROSPECT)
               and ev2 and ev2[-1]["group"] == g2 and g2 in memb.prospected_ore_groups
               and g1 in memb.prospected_ore_groups)
        check("3 — exploration multi-groupes : après X, l'agent prospecte une 2ᵉ couleur (Y)",
              ok3, f"groups_learned={memb.prospected_ore_groups}")

    # 4 — le monde ne ment jamais (no stain → no memory)
    sc, _cc = _build()
    _ready(sc, 0)
    far = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sc.agents.pos[0, 0] = far
    sc.agents.pos[0, 1] = far
    no_stain = sm.prospect(sc, far, far) is None
    ev3 = _ORIG_APPLY(sc.agents, 0, cog.Decision(int(ActionKind.PROSPECT), far, far, 0.5),
                      sc.streamer, sc.tick, sim=sc)
    kept = (ev3 == [] and sc.agents.memory[0].has_prospected_ore is False
            and sc.agents.memory[0].known_ore_sites == [])
    check("4 — le monde ne ment jamais : pas de stain ⇒ rien appris, mémoire vide",
          no_stain and kept, f"no_stain={no_stain} kept={kept}")

    # 5 — survival outranks prospecting
    sv, cv = _build()
    cued_v = _cued(sv, cv)
    if not cued_v:
        check("5 — survie > prospect", False, "no cues")
    else:
        co5, _cue5 = cued_v[0]
        _ready(sv, 0)
        px, py = _stand(sv, 0, co5)
        drives = np.full(8, 0.2, dtype=np.float32)
        drives[int(DriveKind.THIRST)] = 0.95
        water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
        obs = Observation(row=0, pos=(px, py, 0.0), drives=drives, vitality=1.0,
                          nearest={"water": water}, near_agents=[],
                          dominant_drive=cog._dominant_drive(drives), tick=0,
                          reproduction_readiness=0.0)
        d_thirst = _ORIG_DECIDE(sv.agents, obs, sim=sv)
        check("5 — survie > prospect : un agent assoiffé (eau en vue) BOIT, ne prospecte pas",
              d_thirst.action == int(ActionKind.DRINK),
              f"action={ActionKind(d_thirst.action).name}")

    # 6 — same path as the real tick
    st, ct = _build()
    step_ok = True
    try:
        st.step()
    except Exception as exc:               # pragma: no cover
        step_ok = False
        print(f"        sim.step() raised: {exc}")
    ct2 = [c for c in ct if st.streamer.cache.get(c) is not None]
    cued_t = _cued(st, ct2)
    seek_act = None
    if cued_t:
        cot, _cu = cued_t[0]
        _ready(st, 0)
        _stand(st, 0, cot)
        s = cog._seek_prospect(st.agents, 0, _obs_of(st, 0), st)
        seek_act = int(s.action) if s is not None else None
    check("6 — même chemin que le tick réel : sim.step() OK + le wire prospect vivant (PROSPECT/WALK_TO)",
          step_ok and seek_act in (int(ActionKind.PROSPECT), int(ActionKind.WALK_TO)),
          f"step_ok={step_ok} seek={ActionKind(seek_act).name if seek_act is not None else 'None'}")

    # 7 — gate + determinism
    sng, cng = _build()
    cued_n = _cued(sng, cng)
    if cued_n:
        _ready(sng, 0)
        _stand(sng, 0, cued_n[0][0])
    sng._surface_cue_cache = None
    gate_off = cog._seek_prospect(sng.agents, 0, _obs_of(sng, 0), sng) is None
    d1, _c1 = _build()
    d2, _c2 = _build()
    cued_d = _cued(d1, _c1)
    if not cued_d:
        check("7 — gate (pas de C1 ⇒ inerte) + déterminisme même-seed", False, "no cues")
    else:
        cod, _cued_d = cued_d[0]
        groups = []
        for s in (d1, d2):
            _ready(s, 0)
            _stand(s, 0, cod)
            e = _ORIG_APPLY(s.agents, 0, cog.Decision(int(ActionKind.PROSPECT),
                                                       *_stand(s, 0, cod), 0.5),
                            s.streamer, s.tick, sim=s)
            groups.append(e[-1]["group"] if e else None)
        det = groups[0] is not None and groups[0] == groups[1]
        check("7 — gate (pas de C1 ⇒ inerte) + déterminisme même-seed (groupe lu bit-identique)",
              gate_off and det, f"gate_off={gate_off} deterministic={det} groups={groups}")

    # 8 — discipline
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    in_enum = hasattr(ActionKind, "PROSPECT")
    mem_fields = (hasattr(sim.agents.memory[0], "known_ore_sites")
                  and hasattr(sim.agents.memory[0], "prospected_ore_groups")
                  and hasattr(sim.agents.memory[0], "has_prospected_ore")
                  and hasattr(sim.agents.memory[0], "last_prospect_group"))
    import inspect
    src = inspect.getsource(_ORIG_APPLY)
    blk = (src.split("ActionKind.PROSPECT)", 1)[1].split("ActionKind.CURE)", 1)[0]
           if "ActionKind.PROSPECT)" in src else "")
    no_mine_at = bool(blk) and "mine_at(" not in blk
    d8_ok = (in_enum and mem_fields and len(contract.PY_TO_RUST) == 15 and no_mine_at)
    check("8 — discipline : PROSPECT∈ActionKind, mémoire prospect, PY_TO_RUST==15 (wire sans tell), pas de mine_at (D10 gelé)",
          d8_ok, f"prospect={in_enum} mem={mem_fields} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p172_prospect_ore_loop", "seed": SEED_PROSPECT,
                   "groups_present": groups_present,
                   "agent0_known_ore_sites": list(sim.agents.memory[0].known_ore_sites),
                   "agent0_prospected_groups": list(sim.agents.memory[0].prospected_ore_groups),
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
