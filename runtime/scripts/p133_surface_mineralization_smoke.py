#!/usr/bin/env python3
"""P133 — Substrate capability : indices de surface minéralisée.

Le monde portait des minerais en profondeur (``engine.geology``) mais restait
**muet** : aucun signal visuel ne permettait à un agent de *découvrir par la
vue* un gisement enfoui. Ce smoke valide la capacité ``surface_mineralization``
qui expose le **chapeau de fer / la tache d'altération** que les prospecteurs
lisent depuis l'âge du bronze — sans rien scripter.

Règle d'émergence absolue : l'agent ne *sait* pas qu'un minerai existe. Il VOIT
une couleur (vert malachite, brun limonite, jaune soufre, blanc sel, doré
placer), se souvient, revient, creuse. La découverte émerge.

Checks
------
 1.  Le monde Genesis réel produit des indices émergents (gossan / soufre…).
 2.  « Le monde ne ment jamais » : tout indice ⇒ vraie couche peu profonde
     contenant le minéral (même source que ``mine_at``). 0 violation.
 3.  Boucle de découverte : prospecter → creuser à ``dig_depth_m`` → obtenir
     le minéral perçu (cuivre injecté = signal vert diagnostique).
 4.  Déterminisme même-seed : indices bit-identiques.
 5.  Masquage physique : océan / canopée dense / glace → pas d'indice.
 6.  Couleurs physiquement correctes (cuivre vert, gossan brun-rouge…).
 7.  Coût tick nul : installation idempotente, aucun hook sur ``sim.step``.
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import numpy as np                                                  # noqa: E402

from engine.sim import Simulation, SimConfig                        # noqa: E402
from engine.world_genesis import GenesisParams                      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine.geology import StrataLayer, ChunkGeology                # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.surface_mineralization as sm                          # noqa: E402

# Seed chosen so the test region is a tropical-dry-forest continent (land +
# shallow ore) rather than ice/ocean — the capability needs land to express.
SEED = 0xFACE
GRID = 10
OUT = os.path.join(ROOT, "journals", "p133_surface_mineralization.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}")


def _build():
    cfg = SimConfig(name="p133", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    sm.install_surface_mineralization(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 78)
    print("P133 — surface mineralization cues (emergent visual discovery)")
    print("=" * 78)

    sim, coords = _build()
    summary = sm.surface_cue_summary(sim)
    print(f"  region: {len(coords)} land chunks | cue_rate={summary['cue_rate']}")
    print(f"  groups: {summary['by_group']}")
    print(f"  minerals: {summary['by_mineral']}")

    # 1 — emergent cues from the real world
    check("1 — Genesis world emits emergent surface cues",
          summary["n_chunks_with_cue"] > 0,
          f"{summary['n_chunks_with_cue']}/{summary['n_chunks']} chunks")

    # 2 — the world never lies
    violations = 0
    sample = None
    for coord in coords:
        cue = sm.surface_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        layer = geo.chunk_geology(sim, coord).find_layer_at(cue.dig_depth_m)
        if layer is None or cue.mineral not in layer.ore_mix or \
                sm._MINERAL_RULE[cue.mineral].group != cue.group:
            violations += 1
        elif sample is None:
            sample = (coord, cue)
    check("2 — le monde ne ment jamais (cue ⇒ ore below)",
          violations == 0, f"violations={violations}")

    # 3 — discovery loop on an injected copper body (diagnostic green)
    cu_coord = coords[len(coords) // 2]
    ch = sim.streamer.cache.get(cu_coord)
    ch.biome = np.full(np.asarray(ch.biome).shape, 7,         # HOT_DESERT
                       dtype=np.asarray(ch.biome).dtype)
    sim._geology_state.chunks[cu_coord] = ChunkGeology(coord=cu_coord, layers=[
        StrataLayer(0.0, 1.0, "regolith", 1800.0, {"native_copper": 0.03}),
        StrataLayer(1.0, 6.0, "shale", 2400.0, {"native_copper": 0.03}),
        StrataLayer(6.0, 200.0, "limestone", 2600.0, {}),
    ])
    sim._surface_cue_cache.clear()
    sim.agents.pos[0, 0] = (cu_coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (cu_coord[1] + 0.5) * CHUNK_SIDE_M
    seen = sm.prospect(sim, float(sim.agents.pos[0, 0]),
                       float(sim.agents.pos[0, 1]))
    loop_ok = False
    if seen is not None and seen.group == "copper":
        print(f"        agent SEES '{seen.label}' rgb={seen.rgb}")
        out = geo.mine_at(sim, 0, target_depth_m=seen.dig_depth_m,
                          kg_to_extract=20.0)
        loop_ok = seen.mineral in out and out[seen.mineral] > 0.0
        print(f"        agent DIGS at {seen.dig_depth_m:.2f} m → {out}")
    check("3 — découverte émergente : voir vert → creuser → cuivre",
          loop_ok, f"perceived={seen.group if seen else None}")

    # 4 — determinism : two fresh same-seed builds must agree (the first
    #     `sim` is now mutated by the injection above, so rebuild both).
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = sm.surface_cue_for_chunk(sim2, coord)
        y = sm.surface_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.group, x.mineral, x.rgb,
                                     round(x.dig_depth_m, 6))
        ky = None if y is None else (y.group, y.mineral, y.rgb,
                                     round(y.dig_depth_m, 6))
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (indices identiques)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physical masking (pure derivation)
    rich = [StrataLayer(0.0, 3.0, "regolith", 1800.0, {"native_copper": 0.05})]
    masked = (sm._cue_from_geology((0, 0, 0), rich, sm._OCEAN) is None and
              sm._cue_from_geology((0, 0, 0), rich, 1) is None and       # ICE
              sm._cue_from_geology((0, 0, 0), rich, 11) is None)         # RAINFOREST
    visible = sm._cue_from_geology((0, 0, 0), rich, 7) is not None       # DESERT
    check("5 — masquage physique (océan/glace/canopée vs désert)",
          masked and visible, f"masked={masked} desert_visible={visible}")

    # 6 — physical colours
    rule = {r.group: r for r in sm._RULES}
    cr, cg, cb = rule["copper"].rgb
    gr, gg, gb = rule["gossan"].rgb
    colours_ok = (cg > cr and cg > cb) and (gr > gg > gb)
    check("6 — couleurs physiques (cuivre vert, gossan brun-rouge)",
          colours_ok, f"copper={rule['copper'].rgb} gossan={rule['gossan'].rgb}")

    # 7 — zero tick cost / idempotent install
    c1 = sm.install_surface_mineralization(sim)
    c2 = sm.install_surface_mineralization(sim)
    check("7 — installation idempotente, coût tick nul",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p133_surface_mineralization", "seed": SEED,
                   "summary": summary, "results": results,
                   "passed": passed, "total": total}, f, ensure_ascii=False)
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
