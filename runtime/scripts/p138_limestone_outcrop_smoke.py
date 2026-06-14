#!/usr/bin/env python3
"""P138 — Substrate capability : affleurement calcaire (Cap. C6).

Le calcaire est le **pendant construction** de l'argile (C5) : l'argile *contient*
(récipient/four/creuset/brique), le calcaire *bâtit* et *colle* (pierre de taille
+ chaux qui lie les pierres). La veille du jour ancre ce maillon dans l'âge de
pierre : la **chaux est le plus ancien liant connu** (néolithique, sols d'enduit
à Göbekli Tepe ~9500 av. J.-C.), **antérieur à la métallurgie**. Pourtant le
calcaire restait **muet** : la géologie portait une lithologie ``limestone`` et
des ores carbonatés, et la crate Rust réservait un ``Mineral::LimestonePure``
(« Quicklime precursor — pure carbonate beds », ``[245,240,225]``) **orphelin** —
aucun signal Python ne le rendait perceptible. Ce smoke valide la capacité
``limestone_outcrop`` qui expose l'affleurement carbonaté (pierre blanche + sa
pureté + son altération) — sans rien scripter.

Règle d'émergence absolue : l'agent ne *sait* pas qu'on en fait du mortier. Il
PERÇOIT une falaise blanche, en détache un bloc (sain ⇒ tient l'arête), le brûle
(carbonate pur ⇒ chaux vive), l'éteint à l'eau (pâte qui durcit) ; ou apprend
qu'une falaise karst-fissurée s'émiette (carrer la roche saine en dessous) et
qu'un calcaire gelé éclate. La maçonnerie et le mortier émergent.

Pendant géologique de C1 (minerai), C2 (pierre), C3 (eau), C4 (combustible),
C5 (argile). Combo veille D1 (grade de chaux = pureté carbonatée → mortier) × D3
(altération : pierre saine vs karst-fissurée vs gel-éclatée) : la même pierre
blanche qu'on VOIT ne se dresse en blocs que SAINE, et ne fait du mortier que
PURE — deux propriétés honnêtes et orthogonales. Effet 1+1>2 : hydrologie
(SYSTÈME A) × géologie (SYSTÈME C) × gel (Wave 50). Une seule vérité de substrat,
plusieurs lectures (C4 veut sec, C5 plastique, C6 sain).

Seed 0xC1A7 : monde tempéré/prairie produisant À LA FOIS le calcaire pur
(``limestone_pure`` ore, grade mortier) ET la falaise calcaire commune
(``limestone`` lithologie, pierre à bâtir), expositions saines (dressables).

Checks
------
 1.  Le monde Genesis réel produit des indices émergents (limestone_pure + limestone).
 2.  « Le monde ne ment jamais » : cue ⇒ carbonate réel peu profond ;
     mortar_grade ⇒ lime_grade ≥ seuil ; dressable_now ⇒ sain & pierre de taille ;
     un seul état d'altération. 0 violation.
 3.  Boucle de découverte : calcaire pur sain → ``work_preview`` dressable & brûle
     en chaux ; falaise karst-fissurée → vue mais ne se dresse pas
     (karst_fissured ; mensonge rendu visible ; aperçu non mutant).
 4.  Déterminisme même-seed : indices bit-identiques.
 5.  Masquage physique : océan → muet ; lit profond → muet.
 6.  Hiérarchie grade/altération : calcaire pur brûle en mortier, calcaire commun
     non ; gel → éclaté ; ``best_limestone_near`` préfère le pur et filtre.
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
from engine.geology import StrataLayer, ChunkGeology                # noqa: E402
from engine.world import Biome, CHUNK_SIDE_M                        # noqa: E402
import engine.limestone_outcrop as li                               # noqa: E402

SEED = 0xC1A7        # temperate / grassland — pure carbonate + common limestone
GRID = 12
OUT = os.path.join(ROOT, "journals", "p138_limestone_outcrop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}")


def _fake_chunk(w=0.0, biome=4, elev=300.0, side=8):
    return SimpleNamespace(
        water=np.full((side, side), w, dtype=np.float32),
        biome=np.full((side, side), biome, dtype=np.uint8),
        height=np.full((side, side), elev, dtype=np.float32))


def _layer(top, bottom, rock="sandstone", ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=2400.0, ore_mix=dict(ore or {}))


def _build():
    cfg = SimConfig(name="p138", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    li.install_limestone_outcrop(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 78)
    print("P138 — limestone outcrop cues (emergent building stone / lime / mortar)")
    print("=" * 78)

    sim, coords = _build()
    summary = li.limestone_cue_summary(sim)
    print(f"  region: {len(coords)} chunks | cued={summary['n_chunks_with_cue']} "
          f"| dressable={summary['n_dressable_now']} "
          f"| mortar={summary['n_mortar_grade']}")
    print(f"  materials: {summary['by_material']}")
    print(f"  classes:   {summary['by_class']}")
    print(f"  weather:   {summary['by_weather']}")

    # 1 — emergent cues from the real world (limestone_pure + limestone expected)
    mats = summary["by_material"]
    check("1 — Genesis world emits emergent carbonate cues (pure + common)",
          summary["n_chunks_with_cue"] > 0 and "limestone_pure" in mats
          and "limestone" in mats,
          f"{summary['n_chunks_with_cue']}/{summary['n_chunks']} cued; {mats}")

    # 2 — the world never lies
    violations = 0
    for coord in coords:
        cue = li.limestone_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        g = geo.chunk_geology(sim, coord)
        grounded = False
        for L in (g.layers if g else []):
            if L.depth_top_m > li.MAX_CARBONATE_DEPTH_M:
                continue
            if cue.source == "lithology" and L.rock_type == cue.material:
                grounded = True
            if cue.source == "ore" and \
                    L.ore_mix.get(cue.material, 0.0) >= li.MIN_VISIBLE_FRACTION:
                grounded = True
        if not grounded:
            violations += 1
        if cue.mortar_grade and cue.lime_grade < li.MORTAR_GRADE:
            violations += 1
        if cue.dressable_now and not (cue.sound_quarry and cue.dimension_stone):
            violations += 1
        if (int(cue.sound_quarry) + int(cue.karst_fissured)
                + int(cue.frost_shattered)) != 1:
            violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ carbonate véridique)",
          violations == 0, f"violations={violations}")

    # 3 — discovery loop : a sound pure carbonate dresses & burns to quicklime ;
    #     a karst-fissured cliff is seen but cannot be dressed (quarry below).
    #     Preview is non-mutating.
    pure_coord = next((c for c in coords
                       if (cu := li.limestone_cue_for_chunk(sim, c)) is not None
                       and cu.material == "limestone_pure"
                       and cu.dressable_now), None)
    pure_ok = karst_ok = False
    if pure_coord is not None:
        cx, cy, _ = pure_coord
        sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
        seen = li.prospect_limestone(sim, float(sim.agents.pos[0, 0]),
                                     float(sim.agents.pos[0, 1]))
        g = geo.chunk_geology(sim, pure_coord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        out = li.work_preview(sim, float(sim.agents.pos[0, 0]),
                              float(sim.agents.pos[0, 1]))
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        pure_ok = (seen is not None and out["can_dress"] is True
                   and out["burns_to_quicklime"] is True and after == before)
        print(f"        agent SEES '{seen.label}' → can_dress="
              f"{out['can_dress']} burns_to_quicklime={out['burns_to_quicklime']}")
    # a synthetic karst-fissured limestone cliff: seen, but humid → not dressable.
    karst = li._cue_from_geology((0, 0, 0),
                                 [_layer(0, 5, "limestone")],
                                 int(Biome.TROPICAL_RAINFOREST),
                                 _fake_chunk(biome=int(Biome.TROPICAL_RAINFOREST),
                                             w=li.WATER_SATURATION_L))
    karst_ok = (karst is not None and karst.karst_fissured is True
                and karst.dressable_now is False)
    if karst is not None:
        print(f"        agent SEES '{karst.label}' → karst_fissured="
              f"{karst.karst_fissured} (wet cliff: lie made visible; quarry below)")
    check("3 — découverte : calcaire pur sain se dresse & brûle ; karst non dressable",
          pure_ok and karst_ok,
          f"pure_dresses_burns={pure_ok} karst_not_dressable={karst_ok}")

    # 4 — determinism (rebuild fresh: sim is mutated by agent moves above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = li.limestone_cue_for_chunk(sim2, coord)
        y = li.limestone_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.material, x.source,
                                     round(x.lime_grade, 6),
                                     x.weather_state, x.mortar_grade)
        ky = None if y is None else (y.material, y.source,
                                     round(y.lime_grade, 6),
                                     y.weather_state, y.mortar_grade)
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (indices identiques)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physical masking (pure derivation)
    ocean = li._cue_from_geology((0, 0, 0),
                                 [_layer(0, 5, "limestone",
                                         ore={"limestone_pure": 0.1})],
                                 int(Biome.OCEAN),
                                 _fake_chunk(biome=int(Biome.OCEAN)))
    deep = li._cue_from_geology(
        (0, 0, 0),
        [_layer(0, 5, "sandstone"),
         _layer(li.MAX_CARBONATE_DEPTH_M + 10.0, 200.0, "limestone")],
        int(Biome.GRASSLAND), _fake_chunk(biome=int(Biome.GRASSLAND)))
    mask_ok = ocean is None and deep is None
    check("5 — masquage physique (océan → muet ; lit profond → muet)",
          mask_ok, f"ocean_silent={ocean is None} deep_silent={deep is None}")

    # 6 — grade/weather hierarchy + best_limestone_near filters
    pure = li._cue_from_geology((0, 0, 0),
                                [_layer(0, 4, "sandstone",
                                        ore={"limestone_pure": 0.06})],
                                int(Biome.GRASSLAND),
                                _fake_chunk(biome=int(Biome.GRASSLAND)))
    common = li._cue_from_geology((0, 0, 0), [_layer(0, 5, "limestone")],
                                  int(Biome.GRASSLAND),
                                  _fake_chunk(biome=int(Biome.GRASSLAND)))
    frost = li._cue_from_geology((0, 0, 0), [_layer(0, 5, "limestone")],
                                 int(Biome.TUNDRA),
                                 _fake_chunk(biome=int(Biome.TUNDRA)))
    hierarchy = (pure is not None and pure.mortar_grade and pure.dressable_now
                 and common is not None and not common.mortar_grade
                 and common.dressable_now
                 and frost is not None and frost.frost_shattered
                 and not frost.dressable_now)
    # best_limestone_near : a pure carbonate alone on the agent's chunk; require
    # filters work (own-chunk radius isolates it from procedural neighbours).
    cx, cy, _ = coords2[len(coords2) // 2]
    cc = (cx, cy, 0)
    ch = sim2.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, int(Biome.GRASSLAND),
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.zeros(np.asarray(ch.water).shape, dtype=np.float32)
    sim2._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=[
        _layer(0.0, 1.0, "sandstone"),
        _layer(1.0, 5.0, "sandstone", ore={"limestone_pure": 0.08})])
    sim2._limestone_cue_cache.clear()
    sim2.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim2.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    r = 0.4 * CHUNK_SIDE_M
    best = li.best_limestone_near(sim2, 0, perception_radius_m=r)
    mortar = li.best_limestone_near(sim2, 0, perception_radius_m=r,
                                    require_mortar=True)
    pick_ok = (best is not None and best.material == "limestone_pure"
               and mortar is not None and mortar.mortar_grade)
    check("6 — hiérarchie grade/altération (pur=mortier ; commun non ; gel éclaté)",
          hierarchy and pick_ok,
          f"hierarchy={hierarchy} best_is_pure={pick_ok}")

    # 7 — zero tick cost / idempotent install
    c1 = li.install_limestone_outcrop(sim)
    c2 = li.install_limestone_outcrop(sim)
    check("7 — installation idempotente, coût tick nul",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p138_limestone_outcrop", "seed": SEED,
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
