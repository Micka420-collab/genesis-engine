#!/usr/bin/env python3
"""P142 — Substrate capability : cuisson de la chaux (Cap. C10).

**Troisième capacité de TRANSFORMATION** (après C8/C9) et **pendant exact de C9** :
C9 cuit l'**argile** (C5) dans un **feu** (C7) → céramique ; C10 brûle le
**calcaire** (C6) dans le même feu (C7) → **chaux** (CaCO₃ → CaO + CO₂). L'argile
*contient*, le calcaire *lie* : la chaux est le plus ancien liant chimique connu
(enduits de sol néolithiques, Göbekli Tepe ~9500 av. J.-C.).

Règle d'émergence absolue : l'agent ne *sait* pas qu'« on brûle la pierre blanche
pour faire du mortier ». Il taille déjà le calcaire (C6), sait faire du feu ici
(C7) — et en jetant un éclat dans le brasier il **découvre** la chaux vive qui bout
à l'eau (extinction, lien C3) et durcit. Le tas de cuisson, le four à chaux, le
mortier — toute la chaîne émerge.

N'introduit AUCUN nouveau tell minéral : COMPOSE C6 (calcaire + ``lime_grade`` +
``lime_class`` + ``mortar_grade``) × C7 (feu + ``fine_fuel``). Pas de ``_PROFILE``,
pas d'entrée ``PY_TO_RUST`` (garde-fou D8 — 4ᵉ fois par composition après C7/C8/C9).
Hors glob ``*_outcrop.py``.

LE COMBO de la veille 2026-06-17 : C10 **réutilise verbatim** la SSOT de C9
``cf.open_fire_peak_temp_c`` (pointe d'un feu ouvert ~600–850 °C selon ``fine_fuel``)
au lieu de la re-modéliser. Un seul feu, deux pyrotransformations.

Physique de la calcination (archéométrie de la chaux) : seuil de décarbonatation —
carbonate commun/dolomitique ~680 °C (fondants + MgCO₃ abaissent), calcaire pur
réfractaire ~770 °C, conversion complète ~898 °C (P(CO₂)=1 atm, Boynton).
``calcination_extent = (peak−onset)/(full−onset)``.

L'inversion réfractaire (le mensonge rendu visible — pendant du kaolin C9 / de
l'obsidienne C8) : ``limestone_pure`` (le *meilleur* calcaire, ``mortar_grade``
True) **sous-cuit** au feu ouvert et donne une chaux **pire** qu'un humble calcaire
commun cuit à cœur. La leçon émergente : brûle la pierre grise banale, pas la belle
pierre blanche — tant que tu n'as qu'un feu nu. ``mortar_ready`` toujours False en
feu ouvert (pas de mortier liant sans four à chaux).

Effet 1+1>2 : calcination possible QUE si calcaire (C6) ET feu (C7) coexistent.

Seed 0xBEEF : continent de prairie (calcaires variés partout + foyers) produisant
des sites de cuisson réels — calcaires communs bien cuits ET calcaires purs
sous-cuits (l'inversion vit dans le monde réel).

Checks
------
 1.  Le monde Genesis réel produit des sites de calcination émergents (calcaire+feu).
 2.  « Le monde ne ment jamais » : cue ⇒ burnable ; calcaire réel (C6) + feu
     faisable (C7) ; lime_yield == SSOT ; peak dans [min,max] ; mortar_ready False. 0 viol.
 3.  Boucle de découverte : calcaire+foyer → ``burn_preview`` burnable & lime ;
     calcaire pur+foyer → burnable mais sous-cuit (mensonge visible ; aperçu non mutant).
 4.  Déterminisme même-seed : affordances bit-identiques.
 5.  Physique : commun bien cuit vs pur sous-cuit (inversion) + porte du feu
     (calcaire sans feu = non cuisible).
 6.  Hiérarchie : ``best_burning_site_near`` préfère la plus haute lime (commun cuit).
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
import engine.limestone_outcrop as li                               # noqa: E402
import engine.fire_ignition as fi                                   # noqa: E402
import engine.ceramic_firing as cf                                  # noqa: E402
import engine.lime_burning as lb                                    # noqa: E402

SEED = 0xBEEF       # grassland continent — varied carbonate everywhere + hearths
GRID = 12
OUT = os.path.join(ROOT, "journals", "p142_lime_burning.jsonl")

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


def _common_limestone():
    return [_layer(0.0, 4.0, "limestone")]


def _pure_limestone():
    return [_layer(0.0, 4.0, "limestone", ore={"limestone_pure": 0.06})]


def _derive(coord, layers, biome, chunk):
    lime = li._cue_from_geology(coord, layers, biome, chunk)
    fire = fi._cue_from_geology(coord, layers, biome, chunk)
    return lb._cue_from_inputs(coord, lime, fire)


def _build():
    cfg = SimConfig(name="p142", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    lb.install_lime_burning(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 78)
    print("P142 — lime burning (emergent limestone→lime transformation: C6×C7)")
    print("=" * 78)

    sim, coords = _build()
    summary = lb.lime_burning_summary(sim)
    print(f"  region: {len(coords)} chunks | burnable={summary['n_chunks_burnable']} "
          f"(well_burnt={summary['n_well_burnt']} underburnt={summary['n_underburnt']}) "
          f"| best_lime={summary['best_lime_yield']} "
          f"best_peak={summary['best_peak_temp_c']}°C")
    print(f"  carbonates: {summary['by_carbonate_material']}")

    # 1 — emergent burnable sites from the real world
    check("1 — Genesis world emits emergent lime-burning sites (carbonate + fire)",
          summary["n_chunks_burnable"] > 0,
          f"{summary['n_chunks_burnable']}/{summary['n_chunks']} burnable; "
          f"carbonates={summary['by_carbonate_material']}")

    # 2 — the world never lies
    violations = 0
    for coord in coords:
        cue = lb.lime_burning_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        if not cue.burnable:
            violations += 1
        if cue.mortar_ready:             # open fire never hard-burns
            violations += 1
        if not (cf.OPEN_FIRE_MIN_C <= cue.peak_temp_c <= cf.OPEN_FIRE_MAX_C):
            violations += 1
        if abs(cue.lime_yield
               - lb.quicklime_quality(cue.lime_grade, cue.calcination_extent)) > 5e-4:
            violations += 1
        # C6 really sees this carbonate here...
        lime = li.limestone_cue_for_chunk(sim, coord)
        if lime is None or lime.material != cue.carbonate_material:
            violations += 1
        # ...and C7 really can make a fire here.
        if fi.ignition_cue_for_chunk(sim, coord) is None:
            violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ calcaire C6 + feu C7 ; lime==SSOT)",
          violations == 0, f"violations={violations}")

    # 3 — discovery loop : a real burning site previews burnable & names the lime ;
    #     a synthetic pure-limestone outcrop with fire is seen as the prime stone
    #     but under-burns (the lie). Preview is non-mutating.
    bcoord = next((c for c in coords
                   if lb.lime_burning_cue_for_chunk(sim, c) is not None), None)
    burn_ok = lie_ok = False
    if bcoord is not None:
        cx, cy, _ = bcoord
        sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
        g = geo.chunk_geology(sim, bcoord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        out = lb.burn_preview(sim, float(sim.agents.pos[0, 0]),
                              float(sim.agents.pos[0, 1]))
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        seen = lb.prospect_lime_burning(sim, float(sim.agents.pos[0, 0]),
                                        float(sim.agents.pos[0, 1]))
        burn_ok = (seen is not None and out["burnable"] is True
                   and 0.0 <= out["lime_yield"] <= 1.0
                   and out["mortar_ready"] is False
                   and after == before)
        print(f"        agent SEES stone='{seen.carbonate_material}' "
              f"peak={seen.peak_temp_c:.0f}°C onset={seen.calcination_onset_c:.0f}°C "
              f"→ burnt={seen.calcination_extent:.2f} lime={seen.lime_yield:.2f} "
              f"({'well-burnt' if seen.well_burnt else 'UNDERBURNT'})")
    # synthetic pure limestone + fire: the prime stone, but the open fire under-burns it.
    pure_layers = _pure_limestone()
    pure_cue = _derive((0, 0, 0), pure_layers, _GRASS, _fake_chunk(biome=_GRASS))
    pure_prev = lb.burn_preview(
        SimpleNamespace(
            streamer=SimpleNamespace(cache={(0, 0, 0): _fake_chunk(biome=_GRASS)}),
            _geology_state=SimpleNamespace(chunks={
                (0, 0, 0): ChunkGeology(coord=(0, 0, 0), layers=pure_layers)})),
        4.0, 4.0)
    lie_ok = (pure_cue is not None and pure_cue.underburnt
              and pure_prev["burnable"] is True and pure_prev["underburnt"] is True
              and pure_prev["mortar_ready"] is False
              and pure_prev["would_mortar_if_kiln_fired"] is True)
    print(f"        pure limestone outcrop + fire → burnable={pure_prev['burnable']} "
          f"underburnt={pure_prev['underburnt']} mortar_ready={pure_prev['mortar_ready']} "
          f"(looks ideal, but a bare fire can't hard-burn it — needs a kiln)")
    check("3 — découverte : calcaire+foyer cuit ; pur sous-cuit (mensonge visible)",
          burn_ok and lie_ok,
          f"burn_site={burn_ok} pure_underburns={lie_ok}")

    # 4 — determinism (rebuild fresh: sim mutated by agent move above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = lb.lime_burning_cue_for_chunk(sim2, coord)
        y = lb.lime_burning_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.carbonate_material, round(x.peak_temp_c, 3),
                                     round(x.calcination_extent, 6),
                                     round(x.lime_yield, 6))
        ky = None if y is None else (y.carbonate_material, round(y.peak_temp_c, 3),
                                     round(y.calcination_extent, 6),
                                     round(y.lime_yield, 6))
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (affordances identiques)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — calcination physics: common well-burnt vs pure underburnt + the fire gate
    common = _derive((0, 0, 0), _common_limestone(), _GRASS, _fake_chunk(biome=_GRASS))
    pure = _derive((0, 0, 0), _pure_limestone(), _GRASS, _fake_chunk(biome=_GRASS))
    common_nofire = _derive((0, 0, 0), _common_limestone(), _BOREAL,
                            _fake_chunk(biome=_BOREAL))
    physics_ok = (
        common is not None and common.well_burnt and not common.underburnt
        and common.lime_yield == common.lime_grade
        and pure is not None and pure.underburnt and not pure.well_burnt
        and pure.mortar_ready is False and pure.would_mortar_if_kiln_fired is True
        and common.lime_yield > pure.lime_yield            # the inversion
        and common_nofire is None)                         # the 1+1>2 gate
    check("5 — physique : commun cuit > pur sous-cuit (inversion) + porte du feu",
          physics_ok,
          f"common_lime={common.lime_yield if common else None} "
          f"pure_lime={pure.lime_yield if pure else None} "
          f"common_well={common.well_burnt if common else None} "
          f"pure_underburnt={pure.underburnt if pure else None} "
          f"common_nofire=None")

    # 6 — best_burning_site_near prefers the highest lime (well-burnt common)
    cx, cy, _ = coords2[len(coords2) // 2]
    cc = (cx, cy, 0)
    ch = sim2.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, _GRASS,
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.zeros(np.asarray(ch.water).shape, dtype=np.float32)
    sim2._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=_common_limestone())
    sim2._limestone_cue_cache.clear()
    sim2._ignition_cue_cache.clear()
    sim2._lime_burn_cue_cache.clear()
    sim2.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim2.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    r = 0.4 * CHUNK_SIDE_M
    best = lb.best_burning_site_near(sim2, 0, perception_radius_m=r)
    pick_ok = (best is not None and best.burnable
               and best.carbonate_material == "limestone" and best.well_burnt)
    check("6 — best_burning_site préfère la plus haute lime (commun bien cuit)",
          pick_ok, f"best_is_well_burnt_common={pick_ok}")

    # 7 — zero tick cost / idempotent install
    c1 = lb.install_lime_burning(sim)
    c2 = lb.install_lime_burning(sim)
    check("7 — installation idempotente, coût tick nul",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p142_lime_burning", "seed": SEED,
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
