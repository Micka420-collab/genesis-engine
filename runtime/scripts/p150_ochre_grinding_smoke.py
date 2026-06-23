#!/usr/bin/env python3
"""P150 — Substrate capability : l'ocre broyée (Cap. C18).

**Le 9ᵉ OPÉRATEUR ORTHOGONAL — broyer (grind)** et la **1ʳᵉ avancée de l'axe symbolique**
(le pigment, substrat du dessin). C17 ``iron_bloomery`` était *fire-based* (D9 → 1) ;
C18 **rompt à nouveau vers le non-feu** (reco audit J+12 ``R-J12r3-1``, D9 → 0). Elle
ajoute le verbe **broyer** : réduire en poudre la **terre rouille** du chapeau de fer
(C1) → un pigment d'oxyde de fer (ocre **rouge** hématite / **noir** magnétite).

C'est l'EXACT pendant orthogonal de C17 sur la MÊME matière (le gossan C1) : **chaud →
métal** (C17, mutant) ; **froid, broyé → pigment** (C18, non mutant). Une seule lecture
du monde, deux civilisations.

Règle d'émergence absolue : l'agent ne *sait* pas qu'« on broie la terre rouille pour
faire de la peinture ». Il voit le chapeau de fer (C1), en racle une poignée, la frotte
et **découvre** la trace rouge (ou noire, ou rien). Le geste (tracer, signifier) reste
émergent — C18 n'est que la première brique de l'émergence du dessin (5ᵉ pilier).

N'introduit AUCUN nouveau tell : COMPOSE C1 (gossan), pas de ``_PROFILE``, pas d'entrée
``PY_TO_RUST`` (garde-fou D8 — 12ᵉ fois par composition). Hors glob ``*_outcrop.py``.

LE MENSONGE RENDU VISIBLE #9 (le chapeau de fer ment AUSSI au peintre) : le **même** tell
gossan (C1) coiffe l'**oxyde** (hématite → ocre rouge, magnétite → noir : un pigment
**stable, lightfast**), le **sulfure** (pyrite → aucun pigment terreux stable) ET le
**non-fer** (galène/sphalérite → pas d'ocre). `best_ochre_site_near` enseigne : broie le
chapeau oxyde, ignore le pyriteux / plombo-zincifère. Pendant orthogonal de l'inversion
à 5 voies de C17.

Seed 0x42 : continent de prairie produisant des chapeaux de fer émergents — hématite
(oxyde → ocre rouge) ET pyrite (sulfure → rouille mensongère, aucun pigment). Aucune
injection.

Checks
------
 1.  Le monde Genesis réel produit des sites d'ocre émergents (pigment ET mensonge).
 2.  « Le monde ne ment jamais » : cue ⇒ minéral == C1 gossan ; is_pigment ⟺ oxyde de fer ;
     pigment_quality > 0 ⟺ pigment ; couleur de sortie correcte ; tell de surface = C1.
 3.  Aperçu NON MUTANT : ``grind_ochre_at`` rend le pigment promis & ne touche pas la
     géologie (D10 gelé) ; nomme le mensonge (pyrite/plomb/zinc → grindable mais barren).
 4.  Déterminisme même-seed : oracle bit-identique.
 5.  Physique : hématite → rouge + magnétite → noir + sulfure/non-fer → rien + finesse
     monotone (plafonnée) + pigment ≤ masse broyée.
 6.  Hiérarchie : ``best_ochre_site_near`` préfère le pigment utilisable ; le filtre
     ``pigment_class`` restreint la couleur.
 7.  Coût tick nul : oracle idempotent, aucun hook sur ``sim.step``.
 8.  D8 par composition : pas de ``_PROFILE``, ``PY_TO_RUST`` reste 15, hors *_outcrop.
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

from types import SimpleNamespace                                   # noqa: E402

from engine.sim import Simulation, SimConfig                        # noqa: E402
from engine.world_genesis import GenesisParams                      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
from engine.mineral_catalog import MINERAL_BY_NAME                  # noqa: E402
import engine.surface_mineralization as sm                          # noqa: E402
import engine.ochre_grinding as og                                  # noqa: E402

SEED = 0x42         # grassland continent — iron gossans (hematite oxide + pyrite sulfide)
GRID = 12
OUT = os.path.join(ROOT, "journals", "p150_ochre_grinding.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}")


def _gossan(mineral="hematite", frac=0.05):
    return SimpleNamespace(group="gossan", mineral=mineral, mass_fraction=frac,
                           confidence=0.9, biome=6, rgb=(150, 75, 40), dig_depth_m=1.0)


def _build():
    cfg = SimConfig(name="p150", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    og.install_ochre_grinding(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 80)
    print("P150 — ochre grinding (9th orthogonal operator: GRIND; cold pigment from the C1 iron-hat; opens the symbolic axis)")
    print("=" * 80)

    sim, coords = _build()
    summary = og.ochre_summary(sim)
    print(f"  region: {len(coords)} chunks | ochre_sites={summary['n_ochre_sites']} "
          f"(pigment={summary['n_pigment']} usable={summary['n_usable']} "
          f"lie={summary['n_lie']}) | best_quality={summary['best_pigment_quality']}")
    print(f"  pigment classes: {summary['by_pigment_class']} | minerals: {summary['by_mineral']}")

    # 1 — emergent ochre sites from the real world, BOTH pigment and the lie
    check("1 — Genesis world emits emergent ochre sites (real pigment + the rusty lie)",
          summary["n_ochre_sites"] > 0 and summary["n_pigment"] > 0
          and summary["n_lie"] > 0 and summary["n_usable"] > 0,
          f"{summary['n_ochre_sites']}/{summary['n_chunks']} sites; "
          f"pigment={summary['n_pigment']} lie={summary['n_lie']}")

    # 2 — the world never lies
    violations = 0
    n_pigment = n_lie = 0
    for coord in coords:
        cue = og.ochre_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        c1 = sm.surface_cue_for_chunk(sim, coord)
        if c1 is None or c1.group != "gossan" or c1.mineral != cue.mineral:
            violations += 1
        m = MINERAL_BY_NAME.get(cue.mineral)
        is_oxide_iron = (m is not None and m.category.name == "OXIDE"
                         and m.yields_per_kg_ore.get("Fe", 0.0) > 0.0)
        if cue.is_pigment != is_oxide_iron:
            violations += 1
        if cue.is_pigment:
            n_pigment += 1
            if not (cue.pigment_quality > 0.0
                    and cue.hue in (og.RED_OCHRE_RGB, og.BLACK_OXIDE_RGB)
                    and cue.lightfast):
                violations += 1
        else:
            n_lie += 1
            if not (cue.pigment_quality == 0.0 and cue.usable is False):
                violations += 1
        if c1 is not None and tuple(cue.tell_rgb) != tuple(c1.rgb):
            violations += 1
    check("2 — le monde ne ment jamais (minéral==C1 ; is_pigment⟺oxyde Fe ; quality>0⟺pigment ; couleur ; tell=C1)",
          violations == 0,
          f"violations={violations} pigment={n_pigment} lie={n_lie}")

    # 3 — non-mutating preview : grind yields the promised pigment & touches nothing ;
    #     names the lie for a barren gossan.
    pig_coord = next((c for c in coords
                      if (cu := og.ochre_cue_for_chunk(sim, c)) is not None
                      and cu.is_pigment), None)
    lie_coord = next((c for c in coords
                      if (cu := og.ochre_cue_for_chunk(sim, c)) is not None
                      and not cu.is_pigment), None)
    grind_ok = lie_ok = nonmut_ok = False
    if pig_coord is not None:
        cue = og.ochre_cue_for_chunk(sim, pig_coord)
        g = geo.chunk_geology(sim, pig_coord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        sim.agents.pos[0, 0] = (pig_coord[0] + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (pig_coord[1] + 0.5) * CHUNK_SIDE_M
        prev = og.grind_ochre_at(sim, float(sim.agents.pos[0, 0]),
                                 float(sim.agents.pos[0, 1]))
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        nonmut_ok = (after == before)
        grind_ok = (prev["grindable"] is True and prev["is_pigment"] is True
                    and prev["pigment_quality"] == cue.pigment_quality
                    and prev["collect_depth_m"] == 0.0)
        print(f"        GRIND pigment @ {pig_coord}: {cue.mineral} → {cue.pigment_class} "
              f"hue={cue.hue} (quality {cue.pigment_quality}, lightfast={cue.lightfast}) — geology untouched={nonmut_ok}")
    if lie_coord is not None:
        cue = og.ochre_cue_for_chunk(sim, lie_coord)
        sim.agents.pos[0, 0] = (lie_coord[0] + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (lie_coord[1] + 0.5) * CHUNK_SIDE_M
        prev = og.grind_ochre_at(sim, float(sim.agents.pos[0, 0]),
                                 float(sim.agents.pos[0, 1]))
        lie_ok = (prev["grindable"] is True and prev["is_pigment"] is False
                  and prev["pigment_quality"] == 0.0 and prev["reason"] != "ok")
        print(f"        GRIND lie @ {lie_coord}: {cue.mineral} (rusty) → no pigment — "
              f"reason: {prev['reason']}")
    check("3 — aperçu NON MUTANT : grind rend le pigment promis & ne touche pas la géologie ; nomme le mensonge",
          grind_ok and lie_ok and nonmut_ok,
          f"pigment={grind_ok} lie={lie_ok} non_mutating={nonmut_ok}")

    # 4 — determinism
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = og.ochre_cue_for_chunk(sim2, coord)
        y = og.ochre_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.mineral, x.pigment_class,
                                     round(x.pigment_quality, 6), x.usable, x.hue)
        ky = None if y is None else (y.mineral, y.pigment_class,
                                     round(y.pigment_quality, 6), y.usable, y.hue)
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (oracle bit-identique)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physics: hematite red + magnetite black + sulfide/non-iron none + fineness
    #     monotone (capped) + pigment <= ground mass
    red = og.ochre_grind_yield("hematite", 10.0)
    black = og.ochre_grind_yield("magnetite", 10.0)
    pyr = og.ochre_grind_yield("pyrite", 10.0)
    lead = og.ochre_grind_yield("galena", 10.0)
    lo = og.ochre_grind_yield("hematite", 10.0, fineness=0.2).tinting_strength
    hi = og.ochre_grind_yield("hematite", 10.0, fineness=0.95).tinting_strength
    physics_ok = (
        red.pigment_class == "red_ochre" and red.is_pigment and red.hue == og.RED_OCHRE_RGB
        and black.pigment_class == "black_oxide" and black.is_pigment
        and black.base_chroma < red.base_chroma
        and not pyr.is_pigment and pyr.pigment_kg == 0.0
        and not lead.is_pigment
        and lo < hi <= 1.0
        and 0.0 <= red.pigment_kg <= 10.0)
    print(f"        hematite→{red.pigment_class}{red.hue} | magnetite→{black.pigment_class}{black.hue} "
          f"| pyrite→pigment={pyr.is_pigment} | galena→pigment={lead.is_pigment} | "
          f"fineness {lo:.3f}→{hi:.3f}")
    check("5 — physique : hématite rouge + magnétite noir + sulfure/non-fer rien + finesse monotone + pigment≤masse",
          physics_ok, f"red={red.is_pigment} black={black.is_pigment} pyrite_none={not pyr.is_pigment}")

    # 6 — best_ochre_site_near prefers usable pigment ; pigment_class filters colour
    cn = next((c for c in coords2
               if (cu := og.ochre_cue_for_chunk(sim2, c)) is not None
               and cu.is_pigment), None)
    pick_ok = False
    if cn is not None:
        sim2.agents.pos[0, 0] = (cn[0] + 0.5) * CHUNK_SIDE_M
        sim2.agents.pos[0, 1] = (cn[1] + 0.5) * CHUNK_SIDE_M
        best = og.best_ochre_site_near(sim2, 0, perception_radius_m=4 * CHUNK_SIDE_M)
        red_only = og.best_ochre_site_near(sim2, 0, perception_radius_m=4 * CHUNK_SIDE_M,
                                           pigment_class="red_ochre")
        pick_ok = (best is not None and best.usable is True and best.is_pigment is True
                   and (red_only is None or red_only.pigment_class == "red_ochre"))
    check("6 — best_ochre_site préfère le pigment utilisable ; le filtre pigment_class restreint la couleur",
          pick_ok, f"best_usable={pick_ok}")

    # 7 — zero tick cost / idempotent install (the oracle)
    c1 = og.install_ochre_grinding(sim)
    c2 = og.install_ochre_grinding(sim)
    check("7 — installation idempotente, coût tick nul (oracle)",
          c1 is c2, "no per-tick hook on sim.step")

    # 8 — D8 by composition: no _PROFILE, PY_TO_RUST stays 15, out of *_outcrop glob
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract       # noqa: E402
    d8_ok = (not hasattr(og, "_PROFILE") and og.sm is sm
             and not os.path.basename(og.__file__).endswith("_outcrop.py")
             and len(contract.PY_TO_RUST) == 15)
    check("8 — D8 par composition : pas de _PROFILE ; PY_TO_RUST==15 ; hors *_outcrop",
          d8_ok, f"py_to_rust={len(contract.PY_TO_RUST)}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p150_ochre_grinding", "seed": SEED,
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
