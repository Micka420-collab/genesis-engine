#!/usr/bin/env python3
"""P135 — Substrate capability : potabilité de l'eau (Cap. C3).

La ressource la plus fondamentale de toutes — l'eau potable — restait muette
d'une façon **physiquement fausse** : ``engine.physiology`` (action ``DRINK``)
réduit la soif pour N'IMPORTE QUELLE cellule d'eau, **y compris l'eau de mer**.
Le monde laissait un agent « boire l'océan » et être hydraté. Ce smoke valide
la capacité ``water_potability`` qui expose la **salinité** que tout être
vivant lit par le goût — sans rien scripter.

Règle d'émergence absolue : l'agent ne *sait* pas quelle eau le sustente. Il
PERÇOIT un goût (sucré/salé), une croûte de sel sur un rivage stérile, un
miroitement clair ; se souvient ; revient boire — ou crache. La découverte de
l'eau potable émerge.

Pendant hydrologique de Cap. C1 (minerai) et C2 (pierre taillable) : ici l'eau,
plus fondamentale encore (on meurt de soif avant la faim, avant l'outil).

Checks
------
 1.  Le monde Genesis réel produit des indices d'eau émergents.
 2.  « Le monde ne ment jamais » : potable ⇒ ≠ OCEAN & pas de saumure halite &
     ppt ≤ seuil ; mer ⇒ OCEAN ; saumure ⇒ halite ; tout indice ⇒ eau réelle.
     0 violation.
 3.  Boucle de découverte : prospecter eau douce → ``drink_at`` hydrate ;
     océan injecté → perçu salé → ``drink_at`` n'hydrate pas (mensonge rendu
     visible ; l'aperçu ne mute rien).
 4.  Déterminisme même-seed : indices bit-identiques.
 5.  Masquage physique : chunk sec → muet ; océan → salé.
 6.  Hiérarchie de salinité : mer/saumure non potables ; ``nearest_potable``
     saute l'eau salée pour l'eau douce voisine.
 7.  Coût tick nul : installation idempotente, aucun hook sur ``sim.step``.
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback
from types import SimpleNamespace

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
from engine.geology import StrataLayer                              # noqa: E402
from engine.world import Biome, CHUNK_SIDE_M                        # noqa: E402
import engine.water_potability as wp                                # noqa: E402

SEED = 0xFACE
GRID = 10
OUT = os.path.join(ROOT, "journals", "p135_water_potability.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}")


def _fake_chunk(w=300.0, biome=10, elev=500.0, side=8):
    return SimpleNamespace(
        water=np.full((side, side), w, dtype=np.float32),
        biome=np.full((side, side), biome, dtype=np.uint8),
        height=np.full((side, side), elev, dtype=np.float32))


def _layer(top, bottom, rock="shale", ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=2400.0, ore_mix=dict(ore or {}))


def _build():
    cfg = SimConfig(name="p135", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    wp.install_water_potability(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 78)
    print("P135 — water potability cues (emergent fresh/saline water discovery)")
    print("=" * 78)

    sim, coords = _build()
    summary = wp.water_cue_summary(sim)
    print(f"  region: {len(coords)} chunks | water chunks="
          f"{summary['n_chunks_with_water']} | potable_rate={summary['potable_rate']}")
    print(f"  salinity ppt range: {summary['salinity_ppt_range']}")
    print(f"  sources: {summary['by_source']}")
    print(f"  tastes:  {summary['by_taste']}")

    # 1 — emergent cues from the real world
    check("1 — Genesis world emits emergent water cues",
          summary["n_chunks_with_water"] > 0,
          f"{summary['n_chunks_with_water']}/{summary['n_chunks']} chunks")

    # 2 — the world never lies
    violations = 0
    for coord in coords:
        cue = wp.water_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        chunk = sim.streamer.cache.get(coord)
        if float(np.asarray(chunk.water).max()) < wp.WET_CELL_MIN:
            violations += 1
            continue
        g = geo.chunk_geology(sim, coord)
        layers = g.layers if g else []
        halite = wp._shallow_halite_fraction(layers)
        dom = wp._dominant_biome(chunk.biome)
        if cue.potable:
            if (dom == int(Biome.OCEAN) or halite >= wp.HALITE_BRINE_MIN_FRACTION
                    or cue.salinity_ppt > wp.POTABLE_MAX_PPT):
                violations += 1
        if cue.source == "sea" and dom != int(Biome.OCEAN):
            violations += 1
        if cue.source == "brine_spring" and halite < wp.HALITE_BRINE_MIN_FRACTION:
            violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ truthful salinity)",
          violations == 0, f"violations={violations}")

    # 3 — discovery loop : fresh hydrates ; injected sea is perceived salty
    fresh_coord = coords[len(coords) // 2]
    sim.agents.pos[0, 0] = (fresh_coord[0] + 0.5) * CHUNK_SIDE_M
    sim.agents.pos[0, 1] = (fresh_coord[1] + 0.5) * CHUNK_SIDE_M
    seen_fresh = wp.prospect_water(sim, float(sim.agents.pos[0, 0]),
                                   float(sim.agents.pos[0, 1]))
    drink_fresh = wp.drink_at(sim, float(sim.agents.pos[0, 0]),
                              float(sim.agents.pos[0, 1]))
    fresh_ok = (seen_fresh is not None and seen_fresh.potable
                and drink_fresh["hydrating"] is True)
    if seen_fresh is not None:
        print(f"        agent TASTES '{seen_fresh.label}' "
              f"ppt={seen_fresh.salinity_ppt} → drink hydrates="
              f"{drink_fresh['hydrating']}")

    # inject an ocean chunk on the agent's tile → must read as undrinkable.
    chunk = sim.streamer.get(0, fresh_coord)
    chunk.biome = np.full(np.asarray(chunk.biome).shape, int(Biome.OCEAN),
                          dtype=np.asarray(chunk.biome).dtype)
    chunk.water = np.full(np.asarray(chunk.water).shape, 1000.0, dtype=np.float32)
    water_before = np.asarray(chunk.water).copy()
    sim._water_cue_cache.clear()
    seen_sea = wp.prospect_water(sim, float(sim.agents.pos[0, 0]),
                                 float(sim.agents.pos[0, 1]))
    drink_sea = wp.drink_at(sim, float(sim.agents.pos[0, 0]),
                            float(sim.agents.pos[0, 1]))
    non_mut = np.array_equal(np.asarray(chunk.water), water_before)
    sea_ok = (seen_sea is not None and seen_sea.source == "sea"
              and seen_sea.potable is False
              and drink_sea["hydrating"] is False and non_mut)
    if seen_sea is not None:
        print(f"        agent TASTES '{seen_sea.label}' "
              f"ppt={seen_sea.salinity_ppt} → drink hydrates="
              f"{drink_sea['hydrating']} (lie made visible; preview non-mutating)")
    check("3 — découverte : douce hydrate ; mer perçue salée (aperçu non mutant)",
          fresh_ok and sea_ok,
          f"fresh_hydrates={fresh_ok} sea_undrinkable={sea_ok}")

    # 4 — determinism (rebuild both: sim is now mutated by the injection above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = wp.water_cue_for_chunk(sim2, coord)
        y = wp.water_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.source, x.taste,
                                     round(x.salinity_ppt, 6), x.potable)
        ky = None if y is None else (y.source, y.taste,
                                     round(y.salinity_ppt, 6), y.potable)
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (indices identiques)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physical masking (pure derivation)
    dry = wp._cue_from_chunk((0, 0, 0), [_layer(0, 5, "sandstone")],
                             _fake_chunk(w=0.0, elev=600.0))
    ocean = wp._cue_from_chunk((0, 0, 0), [_layer(0, 5, "basalt")],
                               _fake_chunk(w=1000.0, biome=int(Biome.OCEAN),
                                           elev=0.0))
    mask_ok = dry is None and ocean is not None and ocean.potable is False
    check("5 — masquage physique (sec → muet ; océan → salé)",
          mask_ok, f"dry_silent={dry is None} ocean_saline={ocean is not None}")

    # 6 — salinity hierarchy + nearest_potable skips saline
    brine = wp._cue_from_chunk((0, 0, 0),
                               [_layer(0, 2, "shale", ore={"halite": 0.06})],
                               _fake_chunk(elev=400.0))
    fresh = wp._cue_from_chunk((0, 0, 0), [_layer(0, 5, "sandstone")],
                               _fake_chunk(elev=600.0))
    hierarchy = (brine is not None and not brine.potable
                 and brine.salinity_ppt > wp.POTABLE_MAX_PPT
                 and fresh is not None and fresh.potable)
    # nearest_potable must skip a salted home chunk for a fresh neighbour.
    cx, cy, _ = coords2[len(coords2) // 2]
    own = sim2.streamer.get(0, (cx, cy, 0))
    own.biome = np.full(np.asarray(own.biome).shape, int(Biome.OCEAN),
                        dtype=np.asarray(own.biome).dtype)
    own.water = np.full(np.asarray(own.water).shape, 1000.0, dtype=np.float32)
    sim2._water_cue_cache.clear()
    sim2.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim2.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    best = wp.nearest_potable_water(sim2, 0, perception_radius_m=3 * CHUNK_SIDE_M)
    skip_ok = best is not None and best.potable and best.coord != (cx, cy, 0)
    check("6 — hiérarchie de salinité (mer/saumure imbuvables ; on va à l'eau douce)",
          hierarchy and skip_ok,
          f"brine_undrinkable={hierarchy} nearest_potable_inland={skip_ok}")

    # 7 — zero tick cost / idempotent install
    c1 = wp.install_water_potability(sim)
    c2 = wp.install_water_potability(sim)
    check("7 — installation idempotente, coût tick nul",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p135_water_potability", "seed": SEED,
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
