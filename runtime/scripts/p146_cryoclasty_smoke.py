#!/usr/bin/env python3
"""P146 — Substrate capability : pierre gélifractée (Cap. C14).

**Le 7ᵉ opérateur ORTHOGONAL — RAMASSER (gather).** Réponse directe au verrou P0
``R-J8-1`` de l'audit J+8 : sept capacités (C7→C13) empilaient toutes sur le foyer
(allumer). Celle-ci **rompt le treadmill** — elle n'allume rien, ne chauffe rien,
ne casse rien : elle collecte une pierre que **le gel a déjà détachée** (gélifract,
éboulis périglaciaire, felsenmeer). ``collect_depth_m == 0`` (surface) vs C2 (>0).

Règle d'émergence absolue : l'agent ne *sait* pas qu'un éboulis froid recèle des
éclats. Il VOIT le champ de gélifracts, va RAMASSER, et découvre par l'usage que
l'obsidienne/silex y donne des lames — mais que le granite n'y donne que de l'arène.

PREMIÈRE CONSOMMATION AGENT de l'observateur Wave 50 (``frost_weathering``) : la
cryoclastie passe d'instrument de mesure (FCI, talus/permafrost/alpin, jamais vu)
à **fait du monde perçu** (ferme la dette transparence R-J4-1).

N'introduit AUCUN nouveau tell : COMPOSE Wave 50 (champ de gel) × C2
(``lithic_outcrop._PROFILE``). Pas de ``_PROFILE``, pas d'entrée ``PY_TO_RUST``
(garde-fou D8 — 8ᵉ fois par composition). Hors glob ``*_outcrop.py``.

LE MENSONGE RENDU VISIBLE #5 (pendant de l'obsidienne C8, du kaolin C9, du cuivre
C13) : un versant froid et raide sur **granite/gneiss** offre un éboulis
spectaculaire d'**arène stérile** (désagrégation granulaire → gruss) ; le même gel
sur **obsidienne/silex** livre des éclats-rasoir. « Froid + raide » ≠ bonne pierre :
c'est le **fabric** de la roche qui décide. Le monde montre l'éboulis (vrai) ;
``clast_quality`` dit la vérité sur son utilité.

Seed 0xB0 (continent boréal/toundra) : porte la cellule périglaciaire la plus
intense de la carte. Le sim est ancré déterministe sur cette cellule (argmax FCI
sur terre) — AUCUNE injection : le monde a réellement cette région froide, on y
pose seulement la fenêtre de simulation (comme une expédition qui marche vers les
montagnes).

Checks
------
 1.  Le monde Genesis réel produit des champs de gélifracts émergents (+ taillables).
 2.  « Le monde ne ment jamais » : cue ⇒ FCI ≥ seuil ; matériau réel du catalogue C2 ;
     clast_quality == base×frost_response ; surface (depth 0). 0 viol.
 3.  ORTHOGONALITÉ : ramasser (depth 0) ≠ casser C2 (depth > 0) ; gather_at non mutant.
 4.  MENSONGE #5 : granite → arène non taillable ; obsidienne → éclat prêt — même gel.
 5.  Physique du tri : frost_response monotone (conchoïdal ≥ tabulaire ≥ mafique > grenu).
 6.  best_frost_clast_near préfère/retourne du taillable, saute l'arène.
 7.  Déterminisme même-seed (bit-identique) + coût tick nul (oracle idempotent).
 8.  Perçoit l'observateur Wave 50 (macro_frost) — ferme R-J4-1.
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
from engine.world_genesis import (GenesisParams, generate_world)    # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine.geology import StrataLayer                              # noqa: E402
from engine import frost_weathering as fw                           # noqa: E402
from engine import lithic_outcrop as lo                             # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.cryoclasty as cc                                      # noqa: E402

SEED = 0xB0       # boreal/tundra continent — strongest periglacial cell on the map
GRID = 12
OUT = os.path.join(ROOT, "journals", "p146_cryoclasty.jsonl")

results: list = []
_TUNDRA = 2


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}")


def _layer(top, bottom, rock="granite", ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=2600.0, ore_mix=dict(ore or {}))


def _coldest_origin_km(world):
    """Deterministic argmax-FCI land cell → macro km (no injection: point the
    sim window at a region that genuinely is periglacial)."""
    R = world.params.resolution
    cell_km = world.params.map_size_km / R
    fci = fw.compute_frost_cracking_index(world.temp_c, world.precip_mm, world.biome)
    land = world.elevation_m > world.params.sea_level_m
    fci_land = np.where(land, fci, -1.0)
    iy, ix = np.unravel_index(int(np.argmax(fci_land)), fci_land.shape)
    return (float((ix + 0.5) * cell_km), float((iy + 0.5) * cell_km)), \
        float(fci_land[iy, ix]), float(world.temp_c[iy, ix])


def _build():
    world = generate_world(GenesisParams(seed=SEED, resolution=128, n_plates=8))
    origin, fci0, t0 = _coldest_origin_km(world)
    cfg = SimConfig(name="p146", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED, resolution=128,
                                                       n_plates=8),
                          sim_origin_macro_km=origin)
    geo.install_geology(sim)
    cc.install_cryoclasty(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords, origin, fci0, t0


def main() -> int:
    print("=" * 80)
    print("P146 — cryoclasty (frost-shattered tool-stone: 7th orthogonal verb GATHER; breaks the fire treadmill)")
    print("=" * 80)

    sim, coords, origin, fci0, t0 = _build()
    summary = cc.cryoclasty_summary(sim)
    mf = summary["macro_frost"]
    print(f"  anchored @ macro ({origin[0]:.0f},{origin[1]:.0f}) km — cell FCI={fci0:.3f} T={t0:.1f}°C")
    print(f"  region: {len(coords)} chunks | clast fields={summary['n_chunks_with_clasts']} "
          f"(workable={summary['n_workable']}) | best_clast_q={summary['best_clast_quality']}")
    print(f"  zones: {summary['by_zone']} | materials: {summary['by_material']}")
    print(f"  macro Wave 50 perceived: mean_fci={mf['mean_fci_land']} max_fci={mf['max_fci']} "
          f"talus={mf['talus_cells']} permafrost={mf['permafrost_cells']} alpine={mf['alpine_cells']}")

    # 1 — emergent frost-clast fields from the real world, including workable
    check("1 — Genesis world emits emergent frost-clast fields (incl. workable tool-stone)",
          summary["n_chunks_with_clasts"] > 0 and summary["n_workable"] > 0
          and summary["best_clast_quality"] >= cc.MIN_CLAST_QUALITY,
          f"{summary['n_chunks_with_clasts']}/{summary['n_chunks']} fields; "
          f"workable={summary['n_workable']}; best_q={summary['best_clast_quality']}")

    # 2 — the world never lies
    violations = 0
    n_work = n_barren = 0
    for coord in coords:
        cue = cc.frost_clast_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        if cue.fci < cc.FROST_ACTIVE_MIN:
            violations += 1
        if cue.material not in lo._PROFILE:
            violations += 1
        if cue.collect_depth_m != 0.0:
            violations += 1
        if abs(cue.clast_quality - round(cue.base_quality * cue.frost_response, 6)) > 1e-6:
            violations += 1
        if cue.workable != (cue.clast_quality >= cc.MIN_CLAST_QUALITY):
            violations += 1
        if cue.workable:
            n_work += 1
        else:
            n_barren += 1
    check("2 — le monde ne ment jamais (cue ⇒ FCI≥seuil ; matériau C2 réel ; q=base×response ; surface)",
          violations == 0,
          f"violations={violations} workable={n_work} barren={n_barren}")

    # 3 — orthogonality: gather (surface) vs C2 break (buried) ; gather non-mutating
    coord = next((c for c in coords
                  if cc.frost_clast_cue_for_chunk(sim, c) is not None), None)
    ortho_ok = mut_ok = False
    if coord is not None:
        cue = cc.frost_clast_cue_for_chunk(sim, coord)
        # C2 outcrop at the same chunk (if any) digs below surface; C14 gathers @0
        lc = lo.lithic_cue_for_chunk(sim, coord)
        ortho_ok = (cue.collect_depth_m == 0.0
                    and (lc is None or lc.collect_depth_m > 0.0))
        g = geo.chunk_geology(sim, coord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        x = (coord[0] + 0.5) * CHUNK_SIDE_M
        y = (coord[1] + 0.5) * CHUNK_SIDE_M
        out = cc.gather_at(sim, x, y)
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        mut_ok = (after == before and out["material"] == cue.material
                  and out["collect_depth_m"] == 0.0)
        print(f"        GATHER @ {coord}: {out['material']} clast_q={out['clast_quality']:.3f} "
              f"workable={out['workable']} zone={out['zone']} (C2 outcrop depth="
              f"{None if lc is None else round(lc.collect_depth_m, 2)})")
    check("3 — orthogonalité : ramasser (depth 0) ≠ casser C2 (>0) ; gather_at non mutant",
          ortho_ok and mut_ok, f"orthogonal={ortho_ok} non_mutating={mut_ok}")

    # 4 — the lie #5: granite → grus barren ; obsidian → prime (same cold steep slope)
    common = dict(biome=_TUNDRA, fci=0.6, slope_deg=30, temp_c=-5.0, elevation_m=1800)
    gra = cc._clast_from_inputs((0, 0, 0), [_layer(0, 4, "granite")], **common)
    obs = cc._clast_from_inputs((0, 0, 0), [_layer(0, 4, "obsidian")], **common)
    lie_ok = (gra is not None and obs is not None
              and gra.zone == obs.zone == "talus"
              and not gra.workable and gra.clast_quality < cc.MIN_CLAST_QUALITY
              and obs.workable and obs.clast_quality > 0.9)
    print(f"        granite scree: q={gra.clast_quality:.3f} workable={gra.workable} (grus — the lie) | "
          f"obsidian scree: q={obs.clast_quality:.3f} workable={obs.workable}")
    check("4 — mensonge #5 : granite → arène stérile ; obsidienne → éclat prêt (même gel)",
          lie_ok, f"granite_barren={not gra.workable} obsidian_prime={obs.workable}")

    # 5 — frost-sorting physics: response monotone by fabric
    r = cc._frost_response
    phys_ok = (r("obsidian") == r("quartz") == 1.0
               and r("slate") >= r("basalt") > r("granite")
               and r("sandstone") <= r("granite") and r("limestone") <= r("basalt"))
    print(f"        frost_response: obsidian={r('obsidian'):.2f} slate={r('slate'):.2f} "
          f"basalt={r('basalt'):.2f} granite={r('granite'):.2f} sandstone={r('sandstone'):.2f}")
    check("5 — physique du tri : frost_response monotone par fabric (conchoïdal≥tabulaire≥mafique>grenu)",
          phys_ok, "monotone by fracture class")

    # 6 — best_frost_clast_near returns a workable clast (skips grus)
    wc = next((c for c in coords
               if (cu := cc.frost_clast_cue_for_chunk(sim, c)) is not None
               and cu.workable), None)
    pick_ok = False
    if wc is not None:
        sim.agents.pos[0, 0] = (wc[0] + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (wc[1] + 0.5) * CHUNK_SIDE_M
        best = cc.best_frost_clast_near(sim, 0, perception_radius_m=2 * CHUNK_SIDE_M)
        pick_ok = best is not None and best.workable is True
    check("6 — best_frost_clast_near retourne du taillable (saute l'arène)",
          pick_ok, f"workable_pick={pick_ok}")

    # 7 — determinism + zero tick cost
    sim2, coords2, *_ = _build()
    sim3, _, *_ = _build()
    det_ok = coords2 == coords
    mism = 0
    for coord in coords2:
        x = cc.frost_clast_cue_for_chunk(sim2, coord)
        y = cc.frost_clast_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.material, round(x.clast_quality, 6),
                                     x.workable, x.zone, round(x.fci, 6))
        ky = None if y is None else (y.material, round(y.clast_quality, 6),
                                     y.workable, y.zone, round(y.fci, 6))
        if kx != ky:
            mism += 1
    step_before = sim2.step
    c1 = cc.install_cryoclasty(sim2)
    c2 = cc.install_cryoclasty(sim2)
    check("7 — déterminisme même-seed (bit-identique) + coût tick nul (oracle idempotent)",
          det_ok and mism == 0 and c1 is c2 and sim2.step is step_before,
          f"mismatches={mism} idempotent={c1 is c2} no_hook={sim2.step is step_before}")

    # 8 — perceives the Wave 50 observer (closes R-J4-1)
    obs_ok = (mf is not None and mf["max_fci"] > 0.0
              and {"talus_cells", "permafrost_cells", "alpine_cells"} <= set(mf))
    check("8 — perçoit l'observateur Wave 50 (macro_frost) — ferme R-J4-1",
          obs_ok, f"max_fci={mf['max_fci']} permafrost={mf['permafrost_cells']}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p146_cryoclasty", "seed": SEED,
                   "anchor_macro_km": list(origin), "anchor_fci": fci0,
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
