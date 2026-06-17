#!/usr/bin/env python3
"""P143 — Substrate capability : le four à tirage (Cap. C11).

**L'apparatus qui élève la température** — la VOÛTE que C9 ``ceramic_firing`` ET C10
``lime_burning`` désignent *toutes deux*. Un feu nu plafonne (~850 °C, SSOT C9)
parce qu'il perd sa chaleur à l'air libre. **Enfermer** ce feu dans une enceinte
d'argile (parois, C5) et lui donner un **tirage** le rend plus chaud, plus longtemps :
un **four à tirage** (updraft kiln), ~1000–1100 °C — le régime qui cuit le calcaire
pur **à cœur** (mortier liant, C10 réalisé) et fritte le kaolin en **corps sain** (C9
racheté).

Règle d'émergence absolue : l'agent ne *sait* pas qu'« on construit un four pour
cuire plus chaud ». Il sait faire du feu ici (C7), il voit l'argile collante du sol
(C5) — et en chemisant par hasard son foyer de cette argile il **découvre** que le feu
enclos rugit plus fort. La forme du four, la cheminée, le tirage — toute la chaîne
émerge.

N'introduit AUCUN nouveau tell minéral : COMPOSE C5 (paroi + ``ceramic_grade``) × C7
(feu + ``fine_fuel``) × C6 (carbonate, pour le mortier), et RÉUTILISE VERBATIM les
SSOT de C9 (``open_fire_peak_temp_c`` — *le combo* : la base est le feu nu) et de C10
(``calcination_extent`` / ``quicklime_quality``). Pas de ``_PROFILE``, pas d'entrée
``PY_TO_RUST`` (garde-fou D8 — 5ᵉ fois par composition après C7/C8/C9/C10). Hors glob
``*_outcrop.py``.

LE COMBO de la veille 2026-06-17 (run #2) : ``kiln_peak_temp_c(fine_fuel,
wall_refractory)`` = pointe du feu nu (C9) + gain d'enceinte, **plafonné par la
réfractarité de la paroi**. Argile commune (``shale``) : plafond ~1000 °C (elle flue
au-delà). Argile réfractaire (kaolin, ``fine_clay``) : plafond ~1150 °C (la fire-clay
tient 1515–1775 °C). Physique de l'enceinte (archéométrie de la pyrotechnologie) :
four à tirage ~1000–1100 °C vs feu nu ≤850 °C.

L'inversion DE l'inversion (le rachat du kaolin C9) : le kaolin réfractaire — la
*mauvaise* argile de poterie de C9 (sous-cuite au feu ouvert) — est la **meilleure
argile de PAROI** ; c'est lui qui bâtit le four assez chaud pour, enfin, cuire le
kaolin **à cœur**. Une paroi commune (plafond 1000 °C) ne cuit JAMAIS le kaolin sain
(maturation 1250 °C → firedness 0,80) ; une paroi réfractaire (1070 °C en prairie) si.

La marche différée honnête : le tirage naturel ne vitrifie jamais la porcelaine
(``vitrifies_watertight`` toujours False) — ``vitrifies_if_forced_draught`` porte le
potentiel du **soufflet + charbon** (1100–1300 °C, bas-fourneau ; C12+), exactement
comme C9/C10 différaient *vers* le four.

Effet 1+1>2 : four possible QUE si argile-de-paroi (C5) ET feu (C7) coexistent ; il
débloque DEUX transformations différées (mortier C10, kaolin sain C9).

Seed 0xBEEF : continent de prairie (argile partout + foyers + calcaires variés)
produisant des sites de four réels — parois communes (mortier réalisé) ET réfractaires
(kaolin sain), avec le mortier liant enfin atteint dans le monde réel.

Checks
------
 1.  Le monde Genesis réel produit des sites de four émergents (argile + feu).
 2.  « Le monde ne ment jamais » : cue ⇒ buildable ; argile réelle (C5) + feu (C7) ;
     kiln_peak ≥ feu nu, ≤ plafond de paroi, == SSOT ; ware == SSOT C9 ; mortier
     réalisé ⇒ carbonate mortar-grade présent (C6). 0 viol.
 3.  Boucle de découverte : site réel → ``kiln_preview`` buildable & pointe (non
     mutant) ; inversion DE l'inversion : kaolin → paroi réfractaire, four plus
     chaud, kaolin cuit sain (que l'open fire sous-cuisait).
 4.  Déterminisme même-seed : affordances bit-identiques.
 5.  Physique : le four RÉALISE le mortier (C10 différé) qu'un feu nu ne peut pas +
     paroi réfractaire plafonne plus haut + porte du feu (argile sans feu = non
     constructible).
 6.  Hiérarchie : ``best_kiln_site_near`` préfère la pointe la plus haute (réfractaire).
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
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.clay_outcrop as ci                                    # noqa: E402
import engine.fire_ignition as fi                                   # noqa: E402
import engine.limestone_outcrop as li                               # noqa: E402
import engine.ceramic_firing as cf                                  # noqa: E402
import engine.lime_burning as lb                                    # noqa: E402
import engine.kiln_draft as kd                                      # noqa: E402

SEED = 0xBEEF       # grassland continent — clay everywhere + hearths + varied carbonate
GRID = 12
OUT = os.path.join(ROOT, "journals", "p143_kiln_draft.jsonl")

results: list = []

_GRASS = 6
_BOREAL = 3
_HOT_DESERT = 7


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}")


def _fake_chunk(w=0.0, biome=_GRASS, side=8):
    return SimpleNamespace(
        water=np.full((side, side), w, dtype=np.float32),
        biome=np.full((side, side), biome, dtype=np.uint8),
        height=np.full((side, side), 300.0, dtype=np.float32))


def _layer(top, bottom, rock="sandstone", ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=2400.0, ore_mix=dict(ore or {}))


def _common_clay():
    return [_layer(0.0, 4.0, "shale")]


def _kaolin():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06})]


def _common_clay_pure_ls():
    return [_layer(0.0, 4.0, "shale", ore={"limestone_pure": 0.06})]


def _derive(coord, layers, biome, chunk):
    clay = ci._cue_from_geology(coord, layers, biome, chunk)
    fire = fi._cue_from_geology(coord, layers, biome, chunk)
    lime = li._cue_from_geology(coord, layers, biome, chunk)
    return kd._cue_from_inputs(coord, clay, fire, lime)


def _build():
    cfg = SimConfig(name="p143", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    kd.install_kiln_draft(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 78)
    print("P143 — kiln draft (emergent enclosed-fire apparatus: C5×C7, realizes C9/C10)")
    print("=" * 78)

    sim, coords = _build()
    summary = kd.kiln_draft_summary(sim)
    print(f"  region: {len(coords)} chunks | buildable={summary['n_chunks_buildable']} "
          f"(refractory={summary['n_refractory_walled']} "
          f"realizes_mortar={summary['n_realizes_binding_mortar']} "
          f"fires_sound={summary['n_fires_clay_sound']}) "
          f"| best_peak={summary['best_kiln_peak_c']}°C "
          f"best_gain={summary['best_draft_gain_c']}°C")
    print(f"  walls: {summary['by_wall_material']}")

    # 1 — emergent buildable kiln sites from the real world
    check("1 — Genesis world emits emergent kiln sites (wall-clay + fire)",
          summary["n_chunks_buildable"] > 0,
          f"{summary['n_chunks_buildable']}/{summary['n_chunks']} buildable; "
          f"walls={summary['by_wall_material']}")

    # 2 — the world never lies
    violations = 0
    n_mortar = 0
    for coord in coords:
        cue = kd.kiln_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        if not cue.buildable:
            violations += 1
        if not (cue.open_fire_peak_c <= cue.kiln_peak_c <= cue.wall_cap_c):
            violations += 1
        if cue.kiln_peak_c != round(
                kd.kiln_peak_temp_c(cue.fine_fuel, cue.wall_refractory), 1):
            violations += 1
        # ware quality agrees with the recomposed C9 SSOT
        maturation = cf.clay_maturation_temp_c(cue.clay_ceramic_grade)
        firedness = min(1.0, cue.kiln_peak_c / maturation)
        if abs(cue.kiln_ware_quality
               - cf.fired_ware_quality(cue.clay_pottery_grade, firedness)) > 5e-4:
            violations += 1
        # natural draught never vitrifies watertight
        if cue.vitrifies_watertight:
            violations += 1
        # C5 really sees this wall-clay here...
        clay = ci.clay_cue_for_chunk(sim, coord)
        if clay is None or clay.material != cue.wall_material:
            violations += 1
        # ...and C7 really can make a fire here.
        if fi.ignition_cue_for_chunk(sim, coord) is None:
            violations += 1
        # a realized mortar implies a real mortar-grade carbonate (C6).
        if cue.realizes_binding_mortar:
            n_mortar += 1
            lime = li.limestone_cue_for_chunk(sim, coord)
            if lime is None or not lime.mortar_grade:
                violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ argile C5 + feu C7 ; peak==SSOT ; mortier⇒carbonate)",
          violations == 0 and n_mortar > 0,
          f"violations={violations} realizes_mortar={n_mortar}")

    # 3 — discovery loop : a real kiln site previews buildable & names the peak ;
    #     the inversion-of-the-inversion: a kaolin site walls a hotter, refractory
    #     kiln that fires the kaolin SOUND (which the open fire under-fired). Preview
    #     is non-mutating.
    bcoord = next((c for c in coords
                   if kd.kiln_cue_for_chunk(sim, c) is not None), None)
    build_ok = redeem_ok = False
    if bcoord is not None:
        cx, cy, _ = bcoord
        sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
        g = geo.chunk_geology(sim, bcoord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        out = kd.kiln_preview(sim, float(sim.agents.pos[0, 0]),
                              float(sim.agents.pos[0, 1]))
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        seen = kd.prospect_kiln(sim, float(sim.agents.pos[0, 0]),
                                float(sim.agents.pos[0, 1]))
        build_ok = (seen is not None and out["buildable"] is True
                    and out["kiln_peak_c"] >= out["open_fire_peak_c"]
                    and after == before)
        print(f"        agent SEES wall='{seen.wall_material}' "
              f"open_fire={seen.open_fire_peak_c:.0f}°C → kiln={seen.kiln_peak_c:.0f}°C "
              f"(+{seen.draft_gain_c:.0f}°C draft) "
              f"{'REFRACTORY' if seen.wall_refractory else 'common'} wall")
    # the kaolin redemption: refractory wall → hotter kiln → kaolin fired sound,
    # where the open fire (C9) under-fired the very same kaolin body.
    kao_cue = _derive((0, 0, 0), _kaolin(), _GRASS, _fake_chunk(biome=_GRASS))
    kao_firedness_open = min(1.0, cf.open_fire_peak_temp_c(kao_cue.fine_fuel)
                             / cf.clay_maturation_temp_c(True))
    redeem_ok = (kao_cue is not None and kao_cue.wall_refractory
                 and kao_cue.fires_clay_sound is True
                 and kao_firedness_open < cf.SOUND_MATURATION   # open fire under-fired it
                 and kao_cue.vitrifies_watertight is False
                 and kao_cue.vitrifies_if_forced_draught is True)
    print(f"        kaolin wall: open-fire firedness={kao_firedness_open:.2f} (UNDER-fired) "
          f"→ kiln {kao_cue.kiln_peak_c:.0f}°C firedness={kao_cue.clay_firedness:.2f} "
          f"({'SOUND' if kao_cue.fires_clay_sound else 'under'}); "
          f"watertight only if forced draught (bellows+charcoal)")
    check("3 — découverte : four buildable (non mutant) ; kaolin réfractaire racheté",
          build_ok and redeem_ok,
          f"build_site={build_ok} kaolin_redeemed={redeem_ok}")

    # 4 — determinism (rebuild fresh: sim mutated by agent move above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = kd.kiln_cue_for_chunk(sim2, coord)
        y = kd.kiln_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.wall_material, round(x.kiln_peak_c, 3),
                                     round(x.draft_gain_c, 3),
                                     round(x.mortar_lime_yield, 6))
        ky = None if y is None else (y.wall_material, round(y.kiln_peak_c, 3),
                                     round(y.draft_gain_c, 3),
                                     round(y.mortar_lime_yield, 6))
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (affordances identiques)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physics: the kiln REALIZES mortar an open fire can't + refractory caps
    #     higher + the fire gate
    mortar_cue = _derive((0, 0, 0), _common_clay_pure_ls(), _GRASS,
                         _fake_chunk(biome=_GRASS))
    onset = lb.calcination_onset_c(li.LimeClass.PURE_CARBONATE)
    open_extent = lb.calcination_extent(cf.OPEN_FIRE_MAX_C, onset)   # C10: under-burnt
    clay_nofire = _derive((0, 0, 0), _common_clay(), _BOREAL,
                          _fake_chunk(biome=_BOREAL))
    physics_ok = (
        mortar_cue is not None and mortar_cue.realizes_binding_mortar is True
        and open_extent < lb.MORTAR_CALCINATION                     # open fire couldn't
        and kd.KILN_REFRACTORY_WALL_CAP_C > kd.KILN_COMMON_WALL_CAP_C
        and kd.kiln_peak_temp_c(1.0, True) > kd.kiln_peak_temp_c(1.0, False)
        and clay_nofire is None)                                    # the 1+1>2 gate
    check("5 — physique : four RÉALISE le mortier (C10 différé) + paroi réfractaire + porte du feu",
          physics_ok,
          f"realizes_mortar={mortar_cue.realizes_binding_mortar if mortar_cue else None} "
          f"open_fire_extent={open_extent:.2f}<{lb.MORTAR_CALCINATION} "
          f"refrac>common={kd.kiln_peak_temp_c(1.0, True):.0f}>{kd.kiln_peak_temp_c(1.0, False):.0f} "
          f"clay_nofire=None")

    # 6 — best_kiln_site_near prefers the hottest (refractory) kiln
    cx, cy, _ = coords2[len(coords2) // 2]
    cc = (cx, cy, 0)
    ch = sim2.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, _GRASS,
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.zeros(np.asarray(ch.water).shape, dtype=np.float32)
    sim2._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=_kaolin())
    sim2._clay_cue_cache.clear()
    sim2._ignition_cue_cache.clear()
    sim2._limestone_cue_cache.clear()
    sim2._kiln_draft_cue_cache.clear()
    sim2.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim2.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    r = 0.4 * CHUNK_SIDE_M
    best = kd.best_kiln_site_near(sim2, 0, perception_radius_m=r)
    pick_ok = (best is not None and best.buildable
               and best.wall_material == "fine_clay" and best.wall_refractory)
    check("6 — best_kiln_site préfère la pointe la plus haute (paroi réfractaire)",
          pick_ok, f"best_is_refractory_kaolin={pick_ok}")

    # 7 — zero tick cost / idempotent install
    c1 = kd.install_kiln_draft(sim)
    c2 = kd.install_kiln_draft(sim)
    check("7 — installation idempotente, coût tick nul",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p143_kiln_draft", "seed": SEED,
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
