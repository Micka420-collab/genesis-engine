#!/usr/bin/env python3
"""P148 — Substrate capability : salaison / conservation par le sel (Cap. C16).

**La 1ʳᵉ capacité qui CONSOMME le produit de C15 — saler pour conserver.** Réponse
à la reco ``R-J9r2-3 (a)`` de l'audit J+9 run #2 (« le sel rendu perceptible ouvre
la conservation : salaison de la viande/poisson → autonomie alimentaire »). C15 a
rendu le sel récoltable ; C16 expose la **vérité physique** de ce qu'on en fait :
le sel **arrête la pourriture** → réserve → surplus → sédentarité → commerce.

Règle d'émergence absolue : l'agent ne *sait* pas que le sel conserve. Il VOIT que
la chair fraîche (la plus appétissante) pourrit en jours, et que la chair salée
(terne) tient des mois, et apprend par l'usage le compromis attrait↔conservation.

CONSOMME C15 (``salt_evaporation`` — le sel récolté) × le champ macro de température
(climat, comme C14/C15). Sans marais salant à portée → dose nulle → aliment frais
(réciproque honnête). Plus le marais est riche (SALAR) → plus de sel → conservation.

N'introduit AUCUN nouveau tell : pas de ``_PROFILE``, ``PY_TO_RUST`` reste 15
(garde-fou D8 — 10ᵉ fois par composition). Hors glob ``*_outcrop.py``. Réutilise la
lecture climat de C15 (``se._resolve_anchor`` / ``se._climate_at`` — SSOT, 0 dérive).

LE MENSONGE RENDU VISIBLE #7 (pendant de l'obsidienne C8, du kaolin C9, du cuivre
C13, de l'arène C14, de la lagune humide C15) : l'aliment **le plus appétissant** —
la chair fraîche, rouge vif — est le **plus périssable**. « Frais = meilleur » est
le mensonge ; la fraîcheur se paie en pourriture. Le monde montre l'attrait (vrai) ;
``shelf_life_days`` dit la vérité.

Physique : a_w (activité de l'eau) abaissée par le sel (osmose), plancher 0,75
(saumure NaCl saturée) ; croissance microbienne ∝ a_w^5 × Q10^((T−25)/10). Viande
maigre fraîche à 25 °C → ~2 jours ; salée à saturation → des mois (dynamique ~100×).

Seed 0x5A17 (« SALT ») : même côte aride que C15 (le sel y est abondant). Le sim est
ancré déterministe sur la cellule saline la plus évaporative (argmax aridité parmi
mer ∪ côtier) — AUCUNE injection.

Checks
------
 1.  Le sel récolté du monde réel rend des aliments émergemment conservables.
 2.  « Le monde ne ment jamais » : a_w == formule(dose) ; shelf == formule(a_w,T). 0 viol.
 3.  ORTHOGONALITÉ : non-fire (aucun module de feu) ; cure_at/achievable non mutants.
 4.  MENSONGE #7 : frais = appétissant + périssable ; salé = terne + tient des mois.
 5.  COMPOSITION C15 : agent sur un marais → sel réel (dose>0) ; sans sel → frais.
 6.  PHYSIQUE : monotone (plus de sel → shelf↑, a_w↓ ; plus froid → shelf↑).
 7.  Déterminisme même-seed (bit-identique) + coût tick nul (oracle idempotent).
 8.  COMPROMIS + aucun nouveau tell : palatabilité↓ avec le sel ; pas de _PROFILE.
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
from engine import water_potability as wp                           # noqa: E402
from engine import salt_evaporation as se                           # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.food_curing as fc                                     # noqa: E402

SEED = 0x5A17       # "SALT" — same hot/arid saline coast as C15
GRID = 12
OUT = os.path.join(ROOT, "journals", "p148_food_curing.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}")


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


def _build():
    world = generate_world(GenesisParams(seed=SEED, resolution=128, n_plates=8))
    origin = _arid_saline_origin_km(world)
    cfg = SimConfig(name="p148", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED, resolution=128,
                                                       n_plates=8),
                          sim_origin_macro_km=origin)
    geo.install_geology(sim)
    fc.install_food_curing(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords, origin


def main() -> int:
    print("=" * 80)
    print("P148 — food_curing (salaison: SALT C15 → shelf-life; lie #7 fresh-vs-cured)")
    print("=" * 80)

    sim, coords, origin = _build()
    summary = fc.food_curing_summary(sim, fc.FoodKind.LEAN_MEAT)
    print(f"  anchored @ macro ({origin[0]:.0f},{origin[1]:.0f}) km — {len(coords)} chunks")
    print(f"  harvestable salt pans={summary['n_harvestable_pans']} "
          f"(enable cure={summary['n_pans_enabling_cure']}) | "
          f"best_shelf={summary['best_shelf_life_days']} days | classes={summary['by_class']}")

    # 1 — real harvested salt makes emergent preservation possible
    check("1 — le sel récolté du monde réel rend des aliments conservables",
          summary["n_harvestable_pans"] > 0 and summary["n_pans_enabling_cure"] > 0
          and summary["best_shelf_life_days"] > fc.CURED_DAYS,
          f"{summary['n_pans_enabling_cure']}/{summary['n_harvestable_pans']} enable cure; "
          f"best_shelf={summary['best_shelf_life_days']}d")

    # 2 — the world never lies (a_w == formula(dose) ; shelf == formula(a_w,T))
    food = fc._FOOD[fc.FoodKind.LEAN_MEAT]
    violations = 0
    n_checked = 0
    for coord in list(sim.streamer.cache.keys()):
        pan = se.saltpan_cue_for_chunk(sim, coord)
        if pan is None or not pan.harvestable:
            continue
        dose = fc._dose_from_yield(pan.salt_yield_kg_m2, food)
        cue = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, dose, pan.temp_c,
                                   salt_source=pan.source,
                                   salt_yield_kg_m2=pan.salt_yield_kg_m2)
        exp_aw = fc._water_activity(food, dose)
        exp_shelf = fc._shelf_life_days(food, exp_aw, pan.temp_c)
        if abs(cue.water_activity - round(exp_aw, 6)) > 1e-6:
            violations += 1
        if abs(cue.shelf_life_days - round(exp_shelf, 4)) > 1e-3:
            violations += 1
        n_checked += 1
    check("2 — le monde ne ment jamais (a_w=formule(dose) ; shelf=formule(a_w,T))",
          violations == 0 and n_checked > 0,
          f"violations={violations} checked={n_checked}")

    # 3 — orthogonality: non-fire ; cure previews are non-mutating
    src = open(fc.__file__, encoding="utf-8").read()
    solar_ok = all(f"engine.{m}" not in src and f"import {m}" not in src
                   for m in ("fire_ignition", "kiln_draft", "forced_draught",
                             "ceramic_firing", "lime_burning", "metallurgy",
                             "copper_smelting"))
    coord = next((c for c in coords
                  if se.saltpan_cue_for_chunk(sim, c) is not None), None)
    mut_ok = False
    if coord is not None:
        chunk = sim.streamer.cache.get(coord)
        w_before = float(np.asarray(chunk.water).sum())
        x = (coord[0] + 0.5) * CHUNK_SIDE_M
        y = (coord[1] + 0.5) * CHUNK_SIDE_M
        fc.cure_food_at(sim, x, y, fc.FoodKind.LEAN_MEAT, 0.2)
        sim.agents.pos[0, 0] = x
        sim.agents.pos[0, 1] = y
        fc.achievable_cure_near(sim, 0, fc.FoodKind.FISH)
        mut_ok = float(np.asarray(chunk.water).sum()) == w_before
    check("3 — orthogonalité : non-fire (aucun module de feu) ; cure non mutant",
          solar_ok and mut_ok, f"non_fire={solar_ok} non_mutating={mut_ok}")

    # 4 — the lie #7: fresh appealing+perishable vs cured drab+keeps
    fresh, cured = fc.fresh_vs_cured(fc.FoodKind.LEAN_MEAT, 28.0)
    lie_ok = (fresh.is_fresh and not cured.is_fresh
              and fresh.shelf_life_days < cured.shelf_life_days
              and fresh.palatability > cured.palatability
              and cured.preservation_class >= fc.PreservationClass.CURED)
    print(f"        fresh: {fresh.shelf_life_days:.1f}d (palat {fresh.palatability:.2f}, "
          f"{fresh.preservation_class.name}) | cured: {cured.shelf_life_days:.0f}d "
          f"(palat {cured.palatability:.2f}, {cured.preservation_class.name}) — the lie")
    check("4 — mensonge #7 : frais = appétissant+périssable ; salé = terne+tient",
          lie_ok, f"fresh<{cured.shelf_life_days:.0f}d cured ; palat {fresh.palatability:.2f}>{cured.palatability:.2f}")

    # 5 — composition C15: agent on a pan cures with real salt ; no salt → fresh
    hc = next((c for c in coords
               if (cu := se.saltpan_cue_for_chunk(sim, c)) is not None
               and cu.harvestable), None)
    comp_ok = False
    if hc is not None:
        sim.agents.pos[0, 0] = (hc[0] + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (hc[1] + 0.5) * CHUNK_SIDE_M
        on_pan = fc.achievable_cure_near(sim, 0, fc.FoodKind.LEAN_MEAT,
                                         perception_radius_m=2 * CHUNK_SIDE_M)
        sim.agents.pos[1, 0] = 1.0e6     # far from any salt
        sim.agents.pos[1, 1] = 1.0e6
        no_salt = fc.achievable_cure_near(sim, 1, fc.FoodKind.LEAN_MEAT,
                                          perception_radius_m=CHUNK_SIDE_M)
        comp_ok = (on_pan.salt_source in ("sea", "coastal", "brine_spring")
                   and on_pan.salt_dose_frac > 0.0
                   and on_pan.preservation_class != fc.PreservationClass.PERISHABLE
                   and no_salt.is_fresh and no_salt.salt_dose_frac == 0.0
                   and no_salt.salt_source is None)
        print(f"        on pan: dose={on_pan.salt_dose_frac:.3f} kg/kg salt={on_pan.salt_source} "
              f"shelf={on_pan.shelf_life_days:.0f}d ({on_pan.preservation_class.name}) | "
              f"no salt: fresh={no_salt.is_fresh} dose={no_salt.salt_dose_frac}")
    check("5 — composition C15 : sur un marais → sel réel (dose>0) ; sans sel → frais",
          comp_ok, f"composes_C15={comp_ok}")

    # 6 — physics monotonicity
    aws = [fc._water_activity(food, d) for d in (0.0, 0.05, 0.1, 0.2, 0.4)]
    shelves_dose = [fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, d, 25.0).shelf_life_days
                    for d in (0.0, 0.05, 0.1, 0.2, 0.3)]
    shelves_temp = [fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, 0.05, t).shelf_life_days
                    for t in (35.0, 25.0, 15.0, 5.0, -5.0)]
    mono_ok = (all(aws[i + 1] <= aws[i] + 1e-12 for i in range(len(aws) - 1))
               and all(shelves_dose[i + 1] >= shelves_dose[i] - 1e-9
                       for i in range(len(shelves_dose) - 1))
               and all(shelves_temp[i + 1] >= shelves_temp[i]
                       for i in range(len(shelves_temp) - 1)))
    check("6 — physique : plus de sel → shelf↑/a_w↓ ; plus froid → shelf↑",
          mono_ok, f"a_w↓={aws[0]:.2f}→{aws[-1]:.2f} ; cold shelf {shelves_temp[0]:.0f}→{shelves_temp[-1]:.0f}d")

    # 7 — determinism + zero tick cost
    sim2, coords2, _ = _build()
    sim3, _, _ = _build()
    s2 = fc.food_curing_summary(sim2, fc.FoodKind.LEAN_MEAT)
    s3 = fc.food_curing_summary(sim3, fc.FoodKind.LEAN_MEAT)
    step_before = sim2.step
    m1 = fc.install_food_curing(sim2)
    m2 = fc.install_food_curing(sim2)
    det_ok = (coords2 == coords and s2 == s3 and m1 is m2
              and sim2.step is step_before)
    check("7 — déterminisme même-seed (bit-identique) + coût tick nul (idempotent)",
          det_ok, f"summary_match={s2 == s3} idempotent={m1 is m2} no_hook={sim2.step is step_before}")

    # 8 — the trade-off + introduces no new tell
    light = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, 0.05, 25.0)
    heavy = fc._cure_from_inputs(fc.FoodKind.LEAN_MEAT, 0.3, 25.0)
    trade_ok = (heavy.palatability < light.palatability < 1.0
                and heavy.nutrient_retention < light.nutrient_retention)
    no_tell = (not hasattr(fc, "_PROFILE")
               and not os.path.basename(fc.__file__).endswith("_outcrop.py")
               and fc.se is se)
    check("8 — compromis (palatabilité↓ avec sel) + aucun nouveau tell (D8 composition)",
          trade_ok and no_tell,
          f"palat {light.palatability:.2f}>{heavy.palatability:.2f} ; no_PROFILE={not hasattr(fc, '_PROFILE')}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p148_food_curing", "seed": SEED,
                   "anchor_macro_km": list(origin), "summary": summary,
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
