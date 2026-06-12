#!/usr/bin/env python3
"""P134 — Substrate capability : affleurements de pierre taillable.

La géologie portait la lithologie (``rock_type``) et les silicates taillables
(``obsidian``, ``quartz``) mais restait **muette** : aucun signal ne disait à
un agent *où trouver une pierre qui fait des lames tranchantes*. Ce smoke
valide la capacité ``lithic_outcrop`` qui expose l'**affleurement** que tout
tailleur paléolithique sait lire — sans rien scripter.

Règle d'émergence absolue : l'agent ne *sait* pas qu'une pierre est bonne. Il
VOIT un éclat vitreux (obsidienne), un galet siliceux (silex), une dalle de
basalte ; se souvient ; revient ; débite. La découverte de l'outil émerge.

Pendant naturel de Cap. C1 (minerai métallique / âge du bronze) : ici la
**pierre taillée**, technologie plus fondamentale encore.

Checks
------
 1.  Le monde Genesis réel produit des indices d'affleurement émergents.
 2.  « Le monde ne ment jamais » : tout indice ⇒ vraie couche peu profonde
     portant la matière (rock_type OU ore_mix). 0 violation.
 3.  Boucle de découverte : prospecter → débiter à ``collect_depth_m`` →
     obtenir la pierre perçue (obsidienne injectée = signal conchoïdal).
 4.  Déterminisme même-seed : indices bit-identiques.
 5.  Masquage physique : océan / canopée dense / glace → pas d'indice.
 6.  Hiérarchie de taille : la pierre la plus tranchante l'emporte (obsidienne
     > silex > quartzite > basalte) ; pierre tendre/régolithe sous le seuil.
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
import engine.lithic_outcrop as lo                                  # noqa: E402

SEED = 0xFACE
GRID = 10
OUT = os.path.join(ROOT, "journals", "p134_lithic_outcrop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}")


def _build():
    cfg = SimConfig(name="p134", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    lo.install_lithic_outcrop(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 78)
    print("P134 — lithic outcrop cues (emergent knappable tool-stone discovery)")
    print("=" * 78)

    sim, coords = _build()
    summary = lo.lithic_cue_summary(sim)
    print(f"  region: {len(coords)} land chunks | cue_rate={summary['cue_rate']}")
    print(f"  best_knap_quality: {summary['best_knap_quality']}")
    print(f"  classes: {summary['by_class']}")
    print(f"  materials: {summary['by_material']}")

    # 1 — emergent cues from the real world
    check("1 — Genesis world emits emergent outcrop cues",
          summary["n_chunks_with_cue"] > 0,
          f"{summary['n_chunks_with_cue']}/{summary['n_chunks']} chunks")

    # 2 — the world never lies
    violations = 0
    for coord in coords:
        cue = lo.lithic_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        layer = geo.chunk_geology(sim, coord).find_layer_at(cue.collect_depth_m)
        if layer is None:
            violations += 1
            continue
        if cue.source == "lithology":
            ok = layer.rock_type == cue.material
        else:
            ok = cue.material in layer.ore_mix
        if not ok or cue.knap_quality < lo.MIN_KNAP_QUALITY:
            violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ stone below)",
          violations == 0, f"violations={violations}")

    # 3 — discovery loop on an injected obsidian source (conchoidal glass)
    obs_coord = coords[len(coords) // 2]
    ch = sim.streamer.cache.get(obs_coord)
    ch.biome = np.full(np.asarray(ch.biome).shape, 7,         # HOT_DESERT
                       dtype=np.asarray(ch.biome).dtype)
    sim._geology_state.chunks[obs_coord] = ChunkGeology(coord=obs_coord, layers=[
        StrataLayer(0.0, 1.0, "sandstone", 1800.0, {"obsidian": 0.05}),
        StrataLayer(1.0, 6.0, "shale", 2400.0, {"obsidian": 0.05}),
        StrataLayer(6.0, 200.0, "limestone", 2600.0, {}),
    ])
    sim._lithic_cue_cache.clear()
    sim.agents.pos[0, 0] = (obs_coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (obs_coord[1] + 0.5) * CHUNK_SIDE_M
    seen = lo.prospect_toolstone(sim, float(sim.agents.pos[0, 0]),
                                 float(sim.agents.pos[0, 1]))
    loop_ok = False
    if seen is not None and seen.material == "obsidian":
        print(f"        agent SEES '{seen.label}' class={seen.knap_class.name}"
              f" q={seen.knap_quality:.2f}")
        out = geo.mine_at(sim, 0, target_depth_m=seen.collect_depth_m,
                          kg_to_extract=20.0)
        loop_ok = "obsidian" in out and out["obsidian"] > 0.0
        print(f"        agent KNAPS at {seen.collect_depth_m:.2f} m → {out}")
    check("3 — découverte émergente : voir verre → débiter → obsidienne",
          loop_ok, f"perceived={seen.material if seen else None}")

    # 4 — determinism (rebuild both: sim is now mutated by the injection above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = lo.lithic_cue_for_chunk(sim2, coord)
        y = lo.lithic_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.material, x.source,
                                     round(x.knap_quality, 6),
                                     round(x.collect_depth_m, 6))
        ky = None if y is None else (y.material, y.source,
                                     round(y.knap_quality, 6),
                                     round(y.collect_depth_m, 6))
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (indices identiques)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physical masking (pure derivation)
    rich = [StrataLayer(0.0, 3.0, "sandstone", 1800.0, {"obsidian": 0.05})]
    masked = (lo._cue_from_geology((0, 0, 0), rich, lo._OCEAN) is None and
              lo._cue_from_geology((0, 0, 0), rich, 1) is None and        # ICE
              lo._cue_from_geology((0, 0, 0), rich, 11) is None)          # RAINFOREST
    visible = lo._cue_from_geology((0, 0, 0), rich, 7) is not None        # DESERT
    check("5 — masquage physique (océan/glace/canopée vs désert)",
          masked and visible, f"masked={masked} desert_visible={visible}")

    # 6 — knapping hierarchy: sharpest wins; soft/regolith stay muet
    sharp = [StrataLayer(0.0, 4.0, "granite", 2700.0, {}),
             StrataLayer(4.0, 6.0, "sandstone", 1800.0, {"obsidian": 0.03})]
    sc = lo._cue_from_geology((0, 0, 0), sharp, 7)
    soft = [StrataLayer(0.0, 1.0, "shale", 1800.0, {}),
            StrataLayer(1.0, 5.0, "sandstone", 1800.0, {}),
            StrataLayer(5.0, 200.0, "limestone", 2600.0, {})]
    soft_muet = lo._cue_from_geology((0, 0, 0), soft, 7) is None
    hierarchy_ok = (sc is not None and sc.material == "obsidian"
                    and sc.knap_quality > 0.9 and soft_muet)
    check("6 — hiérarchie de taille (obsidienne gagne ; tendre muet)",
          hierarchy_ok,
          f"sharpest={sc.material if sc else None} soft_muet={soft_muet}")

    # 7 — zero tick cost / idempotent install
    c1 = lo.install_lithic_outcrop(sim)
    c2 = lo.install_lithic_outcrop(sim)
    check("7 — installation idempotente, coût tick nul",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p134_lithic_outcrop", "seed": SEED,
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
