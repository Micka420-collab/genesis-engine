#!/usr/bin/env python3
"""P153 — The agent loop KNAPS tool-stone (D12 wire, 2026-06-24).

**Not a new capability — the first new agent BEHAVIOUR that consumes the arc.**
AUDIT-DELTA-2026-06-23 named the dominant hole **D12 / R0**: the C1→C20 arc was a
library with no player — 20 truthful affordances no agent ever invoked in a loop.
The DRINK / C3 fix (R-J13-4) took the first bite by making an existing action honest.
This wire (R-J13-1) takes the next: it gives the agent loop a *new behaviour* driven
by PERCEIVING an arc capability.

The canonical perceive → decide → act → remember loop (``cognition.perceive`` /
``decide`` / ``apply_decision`` — the exact three calls ``Simulation.step`` makes per
agent) now: a survival-satisfied, curious agent that SEES a knappable outcrop
(``lithic_outcrop.best_toolstone_near``) walks to it and KNAPS a flake instead of
wandering at random. The world decides the edge: ``inv_tools`` grows in proportion to
the cue's TRUE ``knap_quality``.

LE MENSONGE RENDU VISIBLE (#12, the deceptive boulder): "a hard, sharp-looking stone
always makes a good tool" — FALSE. Obsidian (conchoidal glass) yields a razor edge;
a quern-grade granite boulder looks just as stony but yields a poor edge; a barren
soft-carbonate spot yields no tool at all. The agent only learns this by acting.

Discipline: COMPOSES C2 (reads ``lithic_outcrop``), introduces NO new tell
(``PY_TO_RUST`` stays 15 — D8 by composition), and does NOT call ``geo.mine_at`` —
KNAP is surface gather, so the mutation frontier (D10) stays frozen. Non-fire (D9).
Determinism: pure cue derivation + memoised cues; no new RNG.

Seeds: 0xC0DE_C2A6 (a real bootstrapped continent; a controlled obsidian outcrop is
planted on a streamed chunk to exercise the LIVE perceive→decide→apply plumbing, as in
test_lithic_outcrop). Barren / granite fixtures prove the world-never-lies yield curve.

Checks
------
 1.  LIVE loop: perceive→decide→apply on a real outcrop ⇒ agent KNAPS, gains a cutting
     edge (inv_tools) + raw stone + a remembered tool-stone location (the D12 closure).
 2.  Yield = world truth: obsidian out-yields granite for the same raw mass (cue read).
 3.  « Le monde ne ment jamais » : knapping a barren spot yields nothing, unremembered.
 4.  Survival outranks foraging: a critically thirsty agent with water in sight DRINKS.
 5.  Bounded: once sated (inv_stone ≥ TOOLSTONE_SATED_KG) the agent stops seeking, explores.
 6.  Same path as the real tick: a full ``sim.step()`` runs clean and decide() on the
     prepared agent yields KNAP (the wire is on the live tick path, not a side API).
 7.  Gate + determinism: no C2 ⇒ inert; same seed ⇒ bit-identical knap outcome.
 8.  D8/D10 discipline: KNAP in ActionKind, memory list present, PY_TO_RUST==15, no mine_at.
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
from engine.geology import StrataLayer, ChunkGeology                # noqa: E402
from engine import cognition as cog                                 # noqa: E402
from engine.cognition import Observation, PerceivedTarget           # noqa: E402
from engine.agent import ActionKind, DriveKind                      # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.lithic_outcrop as lo                                 # noqa: E402

# Capture the ORIGINAL decide/apply_decision before any installer (e.g. a
# later sim.step()) globally wraps them — the D12 wire lives in the originals.
_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED = 0xC0DE_C2A6
GRID = 12
OUT = os.path.join(ROOT, "journals", "p153_lithic_knapping.jsonl")
_ARID = 7

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:64s} {detail}")


def _layer(top, bottom, rock="shale", ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=2400.0, ore_mix=dict(ore or {}))


_OBSIDIAN = [_layer(0.0, 1.0, rock="sandstone", ore={"obsidian": 0.05}),
             _layer(1.0, 6.0, rock="shale", ore={"obsidian": 0.05}),
             _layer(6.0, 200.0, rock="limestone")]
_GRANITE = [_layer(0.0, 1.0, rock="shale"), _layer(1.0, 5.0, rock="sandstone"),
            _layer(5.0, 800.0, rock="granite")]
_BARREN = [_layer(0.0, 1.0, rock="shale"), _layer(1.0, 5.0, rock="sandstone"),
           _layer(5.0, 200.0, rock="limestone")]


def _build(seed: int = SEED):
    cfg = SimConfig(name="p153", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    lo.install_lithic_outcrop(sim)
    sim._life_emergence = None
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def _inject(sim, coord, layers, biome=_ARID):
    ch = sim.streamer.get(0, coord)
    ch.biome = np.full(np.asarray(ch.biome).shape, biome, dtype=np.asarray(ch.biome).dtype)
    sim._geology_state.chunks[tuple(int(c) for c in coord)] = ChunkGeology(
        coord=tuple(int(c) for c in coord), layers=list(layers))
    sim._lithic_cue_cache.clear()
    return ch


def _calm_curious(sim, row):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal", "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal", "inv_tools"):
        getattr(sim.agents, inv)[row] = 0.0
    sim.agents.memory[row].known_toolstone_locations.clear()


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
    print("P153 — lithic knapping: the agent loop CONSUMES C2 (closes a bite of D12/R0)")
    print("=" * 80)

    sim, coords = _build()
    target = coords[len(coords) // 2]

    # Report the natural cue rate of the real world before we plant a fixture.
    summ = lo.lithic_cue_summary(sim)
    print(f"  seed {hex(SEED)}: streamed chunks={len(coords)} ; natural tool-stone cue_rate={summ['cue_rate']} "
          f"best_q={summ['best_knap_quality']} by_class={summ['by_class']}")

    # 1 — LIVE loop closes a bite of D12
    _inject(sim, target, _OBSIDIAN)
    _calm_curious(sim, 0)
    _stand(sim, 0, target)
    acts = _drive_loop(sim, 0, n_ticks=12)
    knapped = ActionKind.KNAP in acts
    tool = float(sim.agents.inv_tools[0])
    stone = float(sim.agents.inv_stone[0])
    remembered = len(sim.agents.memory[0].known_toolstone_locations)
    print(f"        agent#0 on obsidian outcrop: actions={[ActionKind(a).name for a in acts]}")
    print(f"        → inv_tools={tool:.3f} inv_stone={stone:.3f} known_toolstone={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent TAILLE la pierre (bouchée D12)",
          knapped and tool > 0.0 and stone > 0.0 and remembered >= 1,
          f"knapped={knapped} tools={tool:.3f} stone={stone:.3f} mem={remembered}")

    # 2 — yield tracks the world's truth (obsidian > granite, same raw mass)
    so, _co = _build()
    _inject(so, target, _OBSIDIAN)
    _calm_curious(so, 0)
    _stand(so, 0, target)
    _ORIG_APPLY(so.agents, 0, cog.Decision(int(ActionKind.KNAP),
                       float(so.agents.pos[0, 0]), float(so.agents.pos[0, 1]), 0.5),
                       so.streamer, so.tick, sim=so)
    sg, _cg = _build()
    _inject(sg, target, _GRANITE)
    _calm_curious(sg, 0)
    _stand(sg, 0, target)
    _ORIG_APPLY(sg.agents, 0, cog.Decision(int(ActionKind.KNAP),
                       float(sg.agents.pos[0, 0]), float(sg.agents.pos[0, 1]), 0.5),
                       sg.streamer, sg.tick, sim=sg)
    obs_tool, gra_tool = float(so.agents.inv_tools[0]), float(sg.agents.inv_tools[0])
    same_mass = abs(float(so.agents.inv_stone[0]) - float(sg.agents.inv_stone[0])) < 1e-9
    print(f"        obsidian edge={obs_tool:.3f} > granite edge={gra_tool:.3f} (same stone mass={same_mass})")
    check("2 — rendement = vérité du monde : obsidienne > granite (cue.knap_quality lu)",
          obs_tool > gra_tool > 0.0 and same_mass, f"obs={obs_tool:.3f} gra={gra_tool:.3f}")

    # 3 — world never lies: barren spot yields nothing
    sb, _cb = _build()
    _inject(sb, target, _BARREN)
    _calm_curious(sb, 0)
    px, py = _stand(sb, 0, target)
    no_cue = lo.prospect_toolstone(sb, px, py) is None
    _ORIG_APPLY(sb.agents, 0, cog.Decision(int(ActionKind.KNAP), px, py, 0.5),
                       sb.streamer, sb.tick, sim=sb)
    barren_inert = (float(sb.agents.inv_stone[0]) == 0.0 and float(sb.agents.inv_tools[0]) == 0.0
                    and len(sb.agents.memory[0].known_toolstone_locations) == 0)
    check("3 — le monde ne ment jamais : un site stérile (pas d'indice) ne rend RIEN",
          no_cue and barren_inert, f"no_cue={no_cue} inert={barren_inert}")

    # 4 — survival outranks foraging
    sp, _cp = _build()
    _inject(sp, target, _OBSIDIAN)
    _calm_curious(sp, 0)
    px, py = _stand(sp, 0, target)
    drives = np.full(8, 0.2, dtype=np.float32)
    drives[int(DriveKind.THIRST)] = 0.95
    water = PerceivedTarget(kind="water", x=px, y=py, distance=0.5, qty=50.0)
    obs = Observation(row=0, pos=(px, py, 0.0), drives=drives, vitality=1.0,
                      nearest={"water": water}, near_agents=[],
                      dominant_drive=cog._dominant_drive(drives), tick=0,
                      reproduction_readiness=0.0)
    d_thirst = _ORIG_DECIDE(sp.agents, obs, sim=sp)
    check("4 — survie > taille : un agent assoiffé (eau en vue) BOIT, ne taille pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 5 — bounded: once sated, the agent stops seeking and explores
    ss, _cs = _build()
    _inject(ss, target, _OBSIDIAN)
    _calm_curious(ss, 0)
    _stand(ss, 0, target)
    ss.agents.inv_stone[0] = cog.TOOLSTONE_SATED_KG + 0.1   # already carrying enough
    obs_s = cog.perceive(ss.agents, 0, ss.streamer, tick=ss.tick)
    d_sated = _ORIG_DECIDE(ss.agents, obs_s, sim=ss)
    check("5 — borné : une fois rassasié (inv_stone≥seuil) l'agent cesse de chercher, explore",
          d_sated.action == int(ActionKind.EXPLORE),
          f"action={ActionKind(d_sated.action).name} sated_kg={cog.TOOLSTONE_SATED_KG}")

    # 6 — same path as the real tick
    st, ct = _build()
    tt = ct[len(ct) // 2]
    _inject(st, tt, _OBSIDIAN)
    _calm_curious(st, 0)
    _stand(st, 0, tt)
    step_ok = True
    try:
        st.step()
    except Exception as exc:               # pragma: no cover
        step_ok = False
        print(f"        sim.step() raised: {exc}")
    obs_t = cog.perceive(st.agents, 0, st.streamer, tick=st.tick)
    # re-pin (step may have moved the agent); decide on the prepared outcrop
    _calm_curious(st, 0)
    _stand(st, 0, tt)
    obs_t = cog.perceive(st.agents, 0, st.streamer, tick=st.tick)
    d_live = _ORIG_DECIDE(st.agents, obs_t, sim=st)
    check("6 — même chemin que le tick réel : sim.step() OK + decide()→KNAP sur l'agent préparé",
          step_ok and d_live.action == int(ActionKind.KNAP),
          f"step_ok={step_ok} decide={ActionKind(d_live.action).name}")

    # 7 — gate + determinism
    sng, cng = _build()
    tg = cng[len(cng) // 2]
    _inject(sng, tg, _OBSIDIAN)
    _calm_curious(sng, 0)
    _stand(sng, 0, tg)
    sng._lithic_cue_cache = None
    gate_off = cog._seek_toolstone(sng.agents, 0, cog.perceive(sng.agents, 0, sng.streamer, tick=0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    td = c1[len(c1) // 2]
    for s in (d1, d2):
        _inject(s, td, _OBSIDIAN)
        _calm_curious(s, 0)
        _stand(s, 0, td)
        _drive_loop(s, 0, n_ticks=8)
    det = (abs(float(d1.agents.inv_tools[0]) - float(d2.agents.inv_tools[0])) < 1e-12
           and abs(float(d1.agents.inv_stone[0]) - float(d2.agents.inv_stone[0])) < 1e-12
           and len(d1.agents.memory[0].known_toolstone_locations)
               == len(d2.agents.memory[0].known_toolstone_locations))
    check("7 — gate (pas de C2 ⇒ inerte) + déterminisme même-seed (knap bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline: D8 by composition, D10 frozen
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    knap_in_enum = hasattr(ActionKind, "KNAP")
    mem_field = hasattr(sim.agents.memory[0], "known_toolstone_locations")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)            # the real, unwrapped handler
    # isolate the KNAP branch only — MINE (a different branch) legitimately mutates
    # geology via geo.mine_at; KNAP must NOT (surface gather, D10 frozen).
    knap_block = (src.split("ActionKind.KNAP)", 1)[1].split("ActionKind.SLEEP)", 1)[0]
                  if "ActionKind.KNAP)" in src else "")
    no_mine_at = bool(knap_block) and "mine_at(" not in knap_block  # an actual call, not a comment
    d8_ok = (knap_in_enum and mem_field and len(contract.PY_TO_RUST) == 15 and no_mine_at)
    check("8 — discipline : KNAP∈ActionKind, mémoire tool-stone, PY_TO_RUST==15, pas de mine_at (D10 gelé)",
          d8_ok, f"knap={knap_in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p153_lithic_knapping", "seed": SEED,
                   "natural_cue_rate": summ["cue_rate"],
                   "agent0_actions": [ActionKind(a).name for a in acts],
                   "agent0_inv_tools": tool, "agent0_inv_stone": stone,
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
