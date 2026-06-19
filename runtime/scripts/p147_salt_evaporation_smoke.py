#!/usr/bin/env python3
"""P147 — Substrate capability : sel d'évaporation solaire (Cap. C15).

**Le 8ᵉ opérateur ORTHOGONAL — SÉCHER AU SOLEIL (solar evaporation).** Réponse à
la reco ``R-J9-1`` de l'audit J+9 (« choisir le 8ᵉ opérateur AVANT de revenir au
feu »). C14 (ramasser) avait rompu la chaîne de 7 capacités *fire-based* ; celle-ci
ajoute un 8ᵉ verbe **non thermique** : laisser la saumure s'évaporer au soleil. Le
soleil fait le travail — aucun feu, aucune fonte. Le sel solaire (marais salants,
sabkhas, salars) conserve la nourriture et structure le commerce néolithique.

Règle d'émergence absolue : l'agent ne *sait* pas qu'une lagune salée séchera en
sel. Il VOIT une croûte blanche sur un bas-fond aride, va la RÉCOLTER, et découvre
par l'usage que le sel conserve la viande — mais qu'une lagune tout aussi salée
sous la pluie ne croûte jamais.

CONSOMME C3 (``water_potability`` — la salinité véridique) × le critère d'aridité
de ``koeppen_grid`` (``20·T+280``, SSOT « B aride » du moteur). INVERSION EXACTE de
C3 : le **même** seuil ``POTABLE_MAX_PPT`` sépare « trop salée pour boire » (C3) de
« assez salée pour récolter » (C15).

N'introduit AUCUN nouveau tell : pas de ``_PROFILE``, ``PY_TO_RUST`` reste 15
(garde-fou D8 — 9ᵉ fois par composition). Hors glob ``*_outcrop.py``.

LE MENSONGE RENDU VISIBLE #6 (pendant de l'obsidienne C8, du kaolin C9, du cuivre
C13, de l'arène C14) : une saumure **identique** (35 ppt) en climat **humide** →
``net_evap = 0`` → AUCUNE croûte (la pluie redilue) ; la même en climat **aride** →
sel abondant. « Eau salée » ≠ sel : c'est le **bilan évaporatif** qui décide. Le
monde montre l'eau salée (vrai, via C3) ; ``harvestable`` dit la vérité.

Seed 0x5A17 (« SALT ») : côte la plus chaude et la plus aride de la carte. Le sim
est ancré déterministe sur la cellule d'eau saline la plus évaporative (argmax
aridité parmi mer ∪ côtier) — AUCUNE injection : le monde a réellement cette côte
aride, on y pose seulement la fenêtre de simulation.

Checks
------
 1.  Le monde Genesis réel produit des marais salants émergents (+ récoltables).
 2.  « Le monde ne ment jamais » : cue ⇒ eau saline C3 ; yield == net_evap×ppt ;
     harvestable == seuil ; source C3 réelle. 0 viol.
 3.  ORTHOGONALITÉ : solaire (n'importe aucun module de feu) ; harvest_at non mutant.
 4.  MENSONGE #6 : même saumure — humide → pas de croûte ; aride → sel.
 5.  Aridité = SSOT Köппen (``_p_thresh`` réutilisé verbatim).
 6.  best_saltpan_near retourne du récoltable (saute la lagune stérile).
 7.  Déterminisme même-seed (bit-identique) + coût tick nul (oracle idempotent).
 8.  Inversion de C3 (MIN_BRINE_PPT == POTABLE_MAX_PPT) + compose C3 (salinité/source).
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
from engine import koeppen_grid as kp                               # noqa: E402
from engine import water_potability as wp                           # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.salt_evaporation as se                                # noqa: E402

SEED = 0x5A17       # "SALT" — hottest, most arid saline coast on this map
GRID = 12
OUT = os.path.join(ROOT, "journals", "p147_salt_evaporation.jsonl")

results: list = []
_OCEAN = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}")


def _arid_saline_origin_km(world):
    """Deterministic argmax-aridity saline-water cell → macro km (no injection:
    point the sim window at a region that genuinely is an arid saline coast)."""
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
    return (float((ix + 0.5) * cell_km), float((iy + 0.5) * cell_km)), \
        float(ar[iy, ix]), float(world.temp_c[iy, ix]), float(world.precip_mm[iy, ix])


def _build():
    world = generate_world(GenesisParams(seed=SEED, resolution=128, n_plates=8))
    origin, ar0, t0, p0 = _arid_saline_origin_km(world)
    cfg = SimConfig(name="p147", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED, resolution=128,
                                                       n_plates=8),
                          sim_origin_macro_km=origin)
    geo.install_geology(sim)
    se.install_salt_evaporation(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords, origin, ar0, t0, p0


def main() -> int:
    print("=" * 80)
    print("P147 — salt_evaporation (solar salt-pan: 8th orthogonal verb SOLAR-DRY; alternates off fire)")
    print("=" * 80)

    sim, coords, origin, ar0, t0, p0 = _build()
    summary = se.salt_evaporation_summary(sim)
    print(f"  anchored @ macro ({origin[0]:.0f},{origin[1]:.0f}) km — cell aridity={ar0:.3f} "
          f"T={t0:.1f}°C P={p0:.0f}mm")
    print(f"  region: {len(coords)} chunks | brine bodies={summary['n_chunks_with_brine']} "
          f"(harvestable={summary['n_harvestable']}) | best_yield={summary['best_salt_yield_kg_m2']} kg/m²/yr")
    print(f"  zones: {summary['by_zone']} | classes: {summary['by_class']}")

    # 1 — emergent salt pans from the real world, including harvestable
    check("1 — Genesis world emits emergent solar salt pans (incl. harvestable)",
          summary["n_chunks_with_brine"] > 0 and summary["n_harvestable"] > 0
          and summary["best_salt_yield_kg_m2"] >= se.MIN_HARVEST_KG_M2,
          f"{summary['n_harvestable']}/{summary['n_chunks_with_brine']} harvestable; "
          f"best_yield={summary['best_salt_yield_kg_m2']}")

    # 2 — the world never lies
    violations = 0
    n_harv = n_lagoon = 0
    for coord in coords:
        cue = se.saltpan_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        if cue.salinity_ppt < se.MIN_BRINE_PPT:
            violations += 1
        if cue.source not in ("sea", "coastal", "brine_spring"):
            violations += 1
        expected = max(0.0, cue.p_thresh_mm - cue.precip_mm) * 1e-3 * cue.salinity_ppt
        if abs(cue.salt_yield_kg_m2 - round(expected, 6)) > 1e-5:
            violations += 1
        if cue.harvestable != (cue.salt_yield_kg_m2 >= se.MIN_HARVEST_KG_M2):
            violations += 1
        if cue.harvestable:
            n_harv += 1
        else:
            n_lagoon += 1
    check("2 — le monde ne ment jamais (cue ⇒ saline C3 ; yield=net_evap×ppt ; harvestable=seuil ; source C3)",
          violations == 0,
          f"violations={violations} harvestable={n_harv} barren_lagoon={n_lagoon}")

    # 3 — orthogonality: solar (no fire module imported) ; harvest_at non-mutating
    src = open(se.__file__, encoding="utf-8").read()
    solar_ok = all(f"engine.{m}" not in src and f"import {m}" not in src
                   for m in ("fire_ignition", "kiln_draft", "forced_draught",
                             "ceramic_firing", "lime_burning", "metallurgy"))
    coord = next((c for c in coords
                  if se.saltpan_cue_for_chunk(sim, c) is not None), None)
    mut_ok = False
    if coord is not None:
        cue = se.saltpan_cue_for_chunk(sim, coord)
        chunk = sim.streamer.cache.get(coord)
        w_before = float(np.asarray(chunk.water).sum())
        x = (coord[0] + 0.5) * CHUNK_SIDE_M
        y = (coord[1] + 0.5) * CHUNK_SIDE_M
        out = se.harvest_salt_at(sim, x, y)
        w_after = float(np.asarray(chunk.water).sum())
        mut_ok = (w_after == w_before and out["material"] == "halite"
                  and out["harvestable"] == cue.harvestable)
        print(f"        HARVEST @ {coord}: {out['material']} yield={out['salt_yield_kg_m2']:.2f} "
              f"kg/m²/yr harvestable={out['harvestable']} zone={out['zone']} class={out['pan_class']}")
    check("3 — orthogonalité : solaire (n'importe aucun module de feu) ; harvest_at non mutant",
          solar_ok and mut_ok, f"solar={solar_ok} non_mutating={mut_ok}")

    # 4 — the lie #6: same brine, humid → no crust ; arid → salt
    arid = se._saltpan_from_inputs((0, 0, 0), 35.0, "coastal", 100.0,
                                   temp_c=28.0, precip_mm=40.0, biome=7)
    humid = se._saltpan_from_inputs((0, 0, 0), 35.0, "coastal", 100.0,
                                    temp_c=28.0, precip_mm=2000.0, biome=11)
    lie_ok = (arid is not None and humid is not None
              and arid.salinity_ppt == humid.salinity_ppt == 35.0
              and arid.harvestable and not humid.harvestable
              and humid.salt_yield_kg_m2 == 0.0
              and humid.pan_class == se.SaltPanClass.SALINE_LAGOON)
    print(f"        arid brine: yield={arid.salt_yield_kg_m2:.1f} harvestable={arid.harvestable} "
          f"({arid.pan_class.name}) | humid brine: yield={humid.salt_yield_kg_m2:.1f} "
          f"harvestable={humid.harvestable} ({humid.pan_class.name} — the lie)")
    check("4 — mensonge #6 : même saumure — humide → pas de croûte ; aride → sel",
          lie_ok, f"arid_salt={arid.harvestable} humid_barren={not humid.harvestable}")

    # 5 — aridity uses the Köppen SSOT threshold verbatim
    ssot_ok = all(se._aridity(t, 0.0)[0] == float(kp._p_thresh(t))
                  for t in (-5.0, 0.0, 12.0, 25.0, 30.0))
    print(f"        p_thresh(25°C)={se._aridity(25.0, 0.0)[0]:.0f} mm (Köppen 20·T+280) — SSOT shared")
    check("5 — aridité = SSOT Köppen (_p_thresh réutilisé verbatim)",
          ssot_ok, "no drift from koeppen_grid")

    # 6 — best_saltpan_near returns a harvestable pan (skips barren lagoon)
    hc = next((c for c in coords
               if (cu := se.saltpan_cue_for_chunk(sim, c)) is not None
               and cu.harvestable), None)
    pick_ok = False
    if hc is not None:
        sim.agents.pos[0, 0] = (hc[0] + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (hc[1] + 0.5) * CHUNK_SIDE_M
        best = se.best_saltpan_near(sim, 0, perception_radius_m=2 * CHUNK_SIDE_M)
        pick_ok = best is not None and best.harvestable is True
    check("6 — best_saltpan_near retourne du récoltable (saute la lagune stérile)",
          pick_ok, f"harvestable_pick={pick_ok}")

    # 7 — determinism + zero tick cost
    sim2, coords2, *_ = _build()
    sim3, _, *_ = _build()
    det_ok = coords2 == coords
    mism = 0
    for coord in coords2:
        x = se.saltpan_cue_for_chunk(sim2, coord)
        y = se.saltpan_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.salinity_ppt, round(x.salt_yield_kg_m2, 6),
                                     x.harvestable, x.zone)
        ky = None if y is None else (y.salinity_ppt, round(y.salt_yield_kg_m2, 6),
                                     y.harvestable, y.zone)
        if kx != ky:
            mism += 1
    step_before = sim2.step
    c1 = se.install_salt_evaporation(sim2)
    c2 = se.install_salt_evaporation(sim2)
    check("7 — déterminisme même-seed (bit-identique) + coût tick nul (oracle idempotent)",
          det_ok and mism == 0 and c1 is c2 and sim2.step is step_before,
          f"mismatches={mism} idempotent={c1 is c2} no_hook={sim2.step is step_before}")

    # 8 — inversion of C3 (shared boundary) + composes C3 (salinity/source)
    inv_ok = se.MIN_BRINE_PPT == wp.POTABLE_MAX_PPT
    comp_ok = True
    n_comp = 0
    for coord in coords:
        cue = se.saltpan_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        water = wp.water_cue_for_chunk(sim, coord)
        if water is None or cue.salinity_ppt != water.salinity_ppt or cue.source != water.source:
            comp_ok = False
            break
        n_comp += 1
    check("8 — inversion de C3 (MIN_BRINE_PPT==POTABLE_MAX_PPT) + compose C3 (salinité/source)",
          inv_ok and comp_ok and n_comp > 0,
          f"shared_boundary={inv_ok} composes_C3={comp_ok} (n={n_comp})")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p147_salt_evaporation", "seed": SEED,
                   "anchor_macro_km": list(origin), "anchor_aridity": ar0,
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
