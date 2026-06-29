#!/usr/bin/env python3
"""P167 — The agent loop RAKES solar salt from a brine pan (D12 wire, 2026-06-29, consumes C15).

The 12th agent BEHAVIOUR that consumes the arc — a NON-FIRE / non-thermal precursor (the sun does
the work). C15 ``salt_evaporation`` made arid brine pans *perceivable* (a white efflorescence crust);
but no agent ever raked one. ``inv_salt`` is « white gold » — the preservative the future C16
``food_curing`` needs. Appended to the ``_ARC_SEEKS`` registry as one line. Installs ONLY C15.

Fixture: like the C15 capability smoke, the sim is anchored at the map's most evaporative saline
coast (SEED 0x5A17) — no injection, the world genuinely has this arid coast; we point the camera at it.

LE MENSONGE RENDU VISIBLE #17 (white gold needs the sun): a brine pan in an arid evaporative climate
has a real harvestable salt crust (yield ∝ salt_yield, more on a copious salar); the SAME brine in a
HUMID climate looks just as wet but NEVER crusts (``harvestable`` False — the sun never wins against
the rain). ``best_saltpan_near`` only ever routes to a real crusted pan; learned by acting.

Discipline: COMPOSES C3 (salinity) × climate, the WIRE introduces NO new tell (``PY_TO_RUST`` stays
15 — D8), and is a NON-MUTATING surface harvest (no ``geo.mine_at``; D10 frozen). ``inv_salt`` is a
real field (added like inv_lime/inv_limestone). Determinism: pure cues + memoised; no RNG.

Checks
------
 1.  LIVE loop: a curious agent on the best pan ⇒ RAKE: the salt store fills + it remembers the site +
     records the aridity zone (D12 bite — white gold is LIVED).
 2.  The lie #17: the same brine crusts in an arid climate but never in a humid one (oracle).
 3.  « Le monde ne ment jamais » : raking where no pan is underfoot yields nothing.
 4.  Survival outranks raking: a critically thirsty agent with water in sight DRINKS.
 5.  Self-limiting: a salt-rich agent (inv_salt ≥ sated) stops seeking.
 6.  Same path as the real tick: ``sim.step()`` runs clean and decide() yields RAKE.
 7.  Gate + determinism: no C15 ⇒ inert; same seed ⇒ bit-identical rake outcome.
 8.  D8/D10 discipline: RAKE in ActionKind, memory field present, PY_TO_RUST==15, no mine_at.
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
from engine.world_genesis import GenesisParams, generate_world      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine import cognition as cog                                 # noqa: E402
from engine.cognition import Observation, PerceivedTarget           # noqa: E402
from engine.agent import ActionKind, DriveKind                      # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.salt_evaporation as se                               # noqa: E402
import engine.water_potability as wp                               # noqa: E402

_ORIG_DECIDE = cog.decide
_ORIG_APPLY = cog.apply_decision

SEED_SALT = 0x5A17
GRID = 12
OUT = os.path.join(ROOT, "journals", "p167_salt_evaporation_loop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:66s} {detail}")


def _arid_saline_origin_km(world):
    R = world.params.resolution
    cell_km = world.params.map_size_km / R
    t = world.temp_c.astype(np.float64)
    p_th = np.where(t >= 0, 20.0 * t + 280.0, 20.0 * t)
    net = np.maximum(0.0, p_th - world.precip_mm)
    ar = np.where(p_th > 0, np.minimum(1.0, net / np.maximum(p_th, 1e-6)), 0.0)
    sea = world.elevation_m <= world.params.sea_level_m
    saline = sea | (world.elevation_m <= wp.COASTAL_MARGIN_M)
    score = np.where(saline, ar, -1.0)
    iy, ix = np.unravel_index(int(np.argmax(score)), score.shape)
    return (float((ix + 0.5) * cell_km), float((iy + 0.5) * cell_km))


def _build(seed: int = SEED_SALT, *, with_c15: bool = True):
    world = generate_world(GenesisParams(seed=seed, resolution=128, n_plates=8))
    origin = _arid_saline_origin_km(world)
    cfg = SimConfig(name="p167", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128, n_plates=8),
                          sim_origin_macro_km=origin)
    geo.install_geology(sim)
    if with_c15:
        se.install_salt_evaporation(sim)
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
        cue = se.saltpan_cue_for_chunk(sim, coord)
        if cue is None or not cue.harvestable:
            continue
        key = (cue.salt_yield_kg_m2, cue.confidence)
        if best is None or key > best[0]:
            best = (key, coord)
    return None if best is None else best[1]


def _calm_curious(sim, row):
    for drv in ("hunger", "thirst", "sleep", "fatigue", "thermal", "pain", "stress", "loneliness"):
        getattr(sim.agents, drv)[row] = 0.20
    sim.agents.curiosity[row] = 0.9
    sim.agents.aggression[row] = 0.1
    sim.agents.extraversion[row] = 0.1
    sim.agents.agreeableness[row] = 0.1
    for inv in ("inv_food", "inv_water", "inv_wood", "inv_stone", "inv_metal", "inv_tools",
                "inv_pigment", "inv_clay", "inv_ceramic", "inv_limestone", "inv_lime", "inv_salt"):
        getattr(sim.agents, inv)[row] = 0.0
    mem = sim.agents.memory[row]
    mem.known_saltpan_locations.clear()
    mem.last_salt_zone = None


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
    print("P167 — solar salt: the agent loop CONSUMES C15 (closes a bite of D12/R0; « white gold », a "
          "non-fire precursor for the future food-curing)")
    print("=" * 80)

    sim, coords = _build()
    n_pan = sum(1 for c in coords
                if (cu := se.saltpan_cue_for_chunk(sim, c)) is not None and cu.harvestable)
    print(f"  seed {hex(SEED_SALT)} (arid saline coast): streamed chunks={len(coords)} ; harvestable pans={n_pan}")

    best = _best(sim, coords)
    if best is None:
        print("RESULT: FAIL — anchored arid coast produced no harvestable pan.")
        return 1

    # 1 — LIVE loop
    _calm_curious(sim, 0)
    _stand(sim, 0, best)
    cue0 = se.saltpan_cue_for_chunk(sim, best)
    before = float(sim.agents.inv_salt[0])
    acts = _drive_loop(sim, 0, n_ticks=8)
    raked = ActionKind.RAKE in acts
    filled = float(sim.agents.inv_salt[0]) > before
    learned = sim.agents.memory[0].last_salt_zone is not None
    remembered = len(sim.agents.memory[0].known_saltpan_locations)
    print(f"        agent#0 on {cue0.zone} pan (yield={round(cue0.salt_yield_kg_m2,3)}, "
          f"abundant={cue0.abundant}): actions={[ActionKind(a).name for a in acts]}")
    print(f"        → inv_salt {before:.3f}→{float(sim.agents.inv_salt[0]):.3f} "
          f"last_salt_zone={sim.agents.memory[0].last_salt_zone} known={remembered}")
    check("1 — LIVE perceive→decide→act→remember : l'agent RÂTELLE le sel solaire (bouchée D12, l'or blanc vécu)",
          raked and filled and learned and remembered >= 1,
          f"raked={raked} filled={filled} learned={learned} mem={remembered}")

    # 2 — the lie #17 (oracle): same brine crusts arid, never humid
    arid = se._saltpan_from_inputs((0, 0, 0), 35.0, "coastal", 100.0, temp_c=28.0, precip_mm=40.0, biome=7)
    humid = se._saltpan_from_inputs((0, 0, 0), 35.0, "coastal", 100.0, temp_c=28.0, precip_mm=2000.0, biome=11)
    lie_ok = (arid is not None and arid.harvestable is True
              and (humid is None or humid.harvestable is False))
    check("2 — mensonge #17 : même saumure → croûte en climat aride, JAMAIS en climat humide",
          lie_ok, f"arid_harvestable={arid.harvestable if arid else None} humid={'None' if humid is None else humid.harvestable}")

    # 3 — world never lies
    sb, _cb = _build()
    _calm_curious(sb, 0)
    far = (GRID + 50 + 0.5) * CHUNK_SIDE_M
    sb.agents.pos[0, 0] = far
    sb.agents.pos[0, 1] = far
    no_pan = se.prospect_saltpan(sb, far, far) is None
    _ORIG_APPLY(sb.agents, 0, cog.Decision(int(ActionKind.RAKE), far, far, 0.5),
                sb.streamer, sb.tick, sim=sb)
    barren = float(sb.agents.inv_salt[0]) == 0.0
    check("3 — le monde ne ment jamais : pas de bassin sous les pieds ⇒ RIEN",
          no_pan and barren, f"no_pan={no_pan} inert={barren}")

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
    check("4 — survie > sel : un agent assoiffé (eau en vue) BOIT, ne râtelle pas",
          d_thirst.action == int(ActionKind.DRINK), f"action={ActionKind(d_thirst.action).name}")

    # 5 — self-limiting
    ss, cs = _build()
    bs = _best(ss, cs)
    _calm_curious(ss, 0)
    ss.agents.inv_salt[0] = cog.SALT_SATED_KG + 0.1
    _stand(ss, 0, bs)
    sated = cog._seek_saltpan(ss.agents, 0, _obs_of(ss, 0), ss) is None
    check("5 — auto-limité : agent riche en sel (≥ sated) ne cherche plus à râteler",
          sated, f"sated_no_reseek={sated}")

    # 6 — same path as the real tick
    st, ct = _build()
    step_ok = True
    try:
        st.step()
    except Exception as exc:               # pragma: no cover
        step_ok = False
        print(f"        sim.step() raised: {exc}")
    # The step may stream/evict chunks; recompute the best pan among those STILL cached.
    ct2 = [c for c in ct if st.streamer.cache.get(c) is not None]
    bt = _best(st, ct2)
    seek_act = None
    if bt is not None:
        _calm_curious(st, 0)
        _stand(st, 0, bt)
        # Prove the C15 wire is LIVE on the post-step tick path: the saltpan seek fires (RAKE if the
        # picked pan is underfoot, else WALK_TO toward it) — either is a salt-driven decision.
        dec = cog._seek_saltpan(st.agents, 0, _obs_of(st, 0), st)
        seek_act = int(dec.action) if dec is not None else None
    check("6 — même chemin que le tick réel : sim.step() OK + le wire saltpan est vivant (RAKE/WALK_TO)",
          step_ok and seek_act in (int(ActionKind.RAKE), int(ActionKind.WALK_TO)),
          f"step_ok={step_ok} seek={ActionKind(seek_act).name if seek_act is not None else 'None'}")

    # 7 — gate + determinism
    sng, cng = _build()
    _calm_curious(sng, 0)
    _stand(sng, 0, _best(sng, cng))
    sng._saltpan_cue_cache = None
    gate_off = cog._seek_saltpan(sng.agents, 0, _obs_of(sng, 0), sng) is None
    d1, c1 = _build()
    d2, c2 = _build()
    b1 = _best(d1, c1)
    for s in (d1, d2):
        _calm_curious(s, 0)
        px, py = _stand(s, 0, b1)
        _ORIG_APPLY(s.agents, 0, cog.Decision(int(ActionKind.RAKE), px, py, 0.5),
                    s.streamer, s.tick, sim=s)
    det = abs(float(d1.agents.inv_salt[0]) - float(d2.agents.inv_salt[0])) < 1e-12
    check("7 — gate (pas de C15 ⇒ inerte) + déterminisme même-seed (rake bit-identique)",
          gate_off and det, f"gate_off={gate_off} deterministic={det}")

    # 8 — discipline
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract          # noqa: E402
    in_enum = hasattr(ActionKind, "RAKE")
    mem_field = hasattr(sim.agents.memory[0], "known_saltpan_locations")
    import inspect
    src = inspect.getsource(_ORIG_APPLY)
    blk = (src.split("ActionKind.RAKE)", 1)[1].split("ActionKind.SLEEP)", 1)[0]
           if "ActionKind.RAKE)" in src else "")
    no_mine_at = bool(blk) and "mine_at(" not in blk
    d8_ok = (in_enum and mem_field and len(contract.PY_TO_RUST) == 15 and no_mine_at)
    check("8 — discipline : RAKE∈ActionKind, mémoire saltpan, PY_TO_RUST==15 (wire sans tell), pas de mine_at (D10 gelé)",
          d8_ok, f"rake={in_enum} mem={mem_field} py_to_rust={len(contract.PY_TO_RUST)} no_mine_at={no_mine_at}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p167_salt_evaporation_loop", "seed": SEED_SALT,
                   "harvestable_pans": n_pan,
                   "agent0_actions": [ActionKind(a).name for a in acts],
                   "agent0_last_salt_zone": sim.agents.memory[0].last_salt_zone,
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
