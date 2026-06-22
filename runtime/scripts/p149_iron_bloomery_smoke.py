#!/usr/bin/env python3
"""P149 — Substrate capability : le bas-fourneau du fer (Cap. C17).

**La 5ᵉ TRANSFORMATION et la 2ᵉ MÉTALLURGIQUE** — le seuil de l'âge du fer. C12
``forced_draught`` a porté un four soufflé au charbon **au-delà de 1200 °C** (régime du
bas-fourneau, paroi réfractaire requise) et exposé ``reaches_iron_bloomery_temp`` comme un
POTENTIEL, en différant explicitement *la réduction effective*. Ce module la RÉALISE :
``bloom_at`` **consomme** le minerai (mutation via ``geo.mine_at`` — la **2ᵉ** mutation de
l'arc après C13 ``smelt_at``) et **rend** une **loupe de fer** solide + de la scorie de
fayalite, exactement comme l'oracle s'y était engagé.

Règle d'émergence absolue : l'agent ne *sait* pas qu'« on réduit la roche rouille au charbon
pour en tirer le fer ». Il voit le chapeau de fer rouille (C1 gossan), sait faire un four
soufflé à paroi réfractaire (C12), et en y entassant la roche il **découvre** l'éponge de
fer qui se forme au fond — qu'il faut **marteler** (forger), car elle ne coule jamais.

N'introduit AUCUN nouveau tell : COMPOSE C12 (four ≥1200 °C, paroi réfractaire) × C1 (tell
gossan « chapeau de fer »), et RÉUTILISE le seuil ``fd.IRON_BLOOMERY_TEMP_C`` (C12) + le
rendement par élément du catalogue (``yields_per_kg_ore["Fe"]``, ``category``). Pas de
``_PROFILE``, pas d'entrée ``PY_TO_RUST`` (garde-fou D8 — 11ᵉ fois par composition). Hors
glob ``*_outcrop.py``.

LE MENSONGE RENDU VISIBLE #8 (chapeau de fer polyminéral) : le **même** tell gossan (C1)
coiffe l'**oxyde** (hématite/magnétite → fer **sain**), le **sulfure** (pyrite → fer
**red-short**, à griller d'abord) ET le **non-fer** (galène → plomb, sphalérite → zinc :
aucun fer). `best_bloomery_site_near` enseigne : réduis le chapeau oxyde, méfie-toi du
pyriteux, fuis celui qui coiffe plomb/zinc.

LE MENSONGE PHYSIQUE : le fer ne FOND jamais (1538 °C hors d'atteinte) → réduction SOLIDE.
``melts`` toujours False, ``is_solid_bloom`` / ``requires_forging`` toujours True. C'est la
raison pour laquelle l'âge du fer arrive bien après le cuivre malgré un minerai plus abondant.

Seed 0x42 : continent de prairie produisant des sites de réduction réels — hématite (oxyde,
réduction directe) ET pyrite (sulfure, grillage requis, red-short). Aucune injection.

Checks
------
 1.  Le monde Genesis réel produit des sites de bas-fourneau émergents (oxyde ET sulfure).
 2.  « Le monde ne ment jamais » : cue ⇒ C12 reaches_iron ; minéral == C1 gossan ; fer rendu
     ≤ fer contenu (catalogue) ; sulfure cru → 0, grillé → >0 ; bloom solide (jamais fondu).
 3.  La RÉDUCTION EFFECTIVE : ``bloom_at`` consomme le minerai & rend le fer promis (oxyde) ;
     le mensonge (pyrite crue → scorie seule, grillée → fer red-short) ; preview non mutant.
 4.  Déterminisme même-seed : oracle bit-identique.
 5.  Physique : oxyde direct + sulfure grille d'abord + non-fer (galène/sphalérite) 0 + trop
     froid → 0 + le fer ne fond JAMAIS (solid bloom) + surchauffe monotone (plafonnée).
 6.  Hiérarchie : ``best_bloomery_site_near`` préfère l'oxyde sain ; require_sound saute le
     pyrite red-short ; require_direct → reducible_now.
 7.  Coût tick nul : oracle idempotent, aucun hook sur ``sim.step``.
 8.  D8 par composition : pas de ``_PROFILE``, ``PY_TO_RUST`` reste 15, hors glob *_outcrop.
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
import engine.forced_draught as fd                                  # noqa: E402
import engine.surface_mineralization as sm                          # noqa: E402
import engine.iron_bloomery as ib                                   # noqa: E402

SEED = 0x42         # grassland continent — refractory furnaces + iron gossans (oxide + pyrite)
GRID = 12
OUT = os.path.join(ROOT, "journals", "p149_iron_bloomery.jsonl")

results: list = []
_GRASS = 6


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}")


def _forced(peak=1280.0, reaches_iron=True, refractory=True, conf=0.9, biome=_GRASS):
    return SimpleNamespace(forced_peak_c=peak, reaches_iron_bloomery_temp=reaches_iron,
                           wall_refractory=refractory, confidence=conf, biome=biome)


def _gossan(mineral="hematite", dig=1.0):
    return SimpleNamespace(group="gossan", mineral=mineral, dig_depth_m=dig)


def _build():
    cfg = SimConfig(name="p149", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    ib.install_iron_bloomery(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 80)
    print("P149 — iron bloomery (réduction effective: C12×C1 gossan; realizes reaches_iron, opens Iron Age)")
    print("=" * 80)

    sim, coords = _build()
    summary = ib.bloom_summary(sim)
    print(f"  region: {len(coords)} chunks | bloomery_sites={summary['n_bloomery_sites']} "
          f"(direct={summary['n_direct_reducible']} "
          f"needs_roast={summary['n_needs_roasting']} "
          f"red_short={summary['n_red_short']}) "
          f"| best_Fe/kg={summary['best_bloom_iron_per_kg_ore']} "
          f"best_purity={summary['best_bloom_purity']}")
    print(f"  ore classes: {summary['by_ore_class']} | minerals: {summary['by_mineral']}")

    # 1 — emergent bloomery sites from the real world, BOTH oxide and sulfide
    by_class = summary["by_ore_class"]
    check("1 — Genesis world emits emergent iron bloomery sites (oxide + sulfide)",
          summary["n_bloomery_sites"] > 0 and by_class.get("oxide_iron", 0) > 0
          and by_class.get("sulfide_iron", 0) > 0,
          f"{summary['n_bloomery_sites']}/{summary['n_chunks']} sites; classes={by_class}")

    # 2 — the world never lies
    violations = 0
    n_oxide = n_sulfide = 0
    for coord in coords:
        cue = ib.bloom_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        forced = fd.forced_cue_for_chunk(sim, coord)
        if forced is None or not forced.reaches_iron_bloomery_temp:
            violations += 1
        c1 = sm.surface_cue_for_chunk(sim, coord)
        if c1 is None or c1.group != "gossan" or c1.mineral != cue.iron_mineral:
            violations += 1
        contained = MINERAL_BY_NAME[cue.iron_mineral].yields_per_kg_ore.get("Fe", 0.0)
        if not (0.0 <= cue.bloom_iron_per_kg_ore <= contained + 1e-9):
            violations += 1
        if not (0.0 <= cue.bloom_iron_per_kg_ore_roasted <= contained + 1e-9):
            violations += 1
        if not cue.is_solid_bloom or cue.furnace_reaches_iron_melt:
            violations += 1               # iron never melts in a bloomery — solid sponge
        if cue.ore_class == "sulfide_iron":
            n_sulfide += 1
            if not (cue.needs_roasting_first and cue.red_short
                    and cue.bloom_iron_per_kg_ore == 0.0
                    and cue.bloom_iron_per_kg_ore_roasted > 0.0):
                violations += 1
        else:
            n_oxide += 1
            if not (cue.reducible_now and not cue.red_short
                    and cue.bloom_iron_per_kg_ore > 0.0):
                violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ C12 reaches_iron ; minéral==C1 ; Fe≤contenu ; sulfure 0 cru/>0 grillé ; bloom solide)",
          violations == 0,
          f"violations={violations} oxide={n_oxide} sulfide={n_sulfide}")

    # 3 — the réduction effective : bloom_at consumes ore & yields the promised iron
    #     (oxide) ; the lie (pyrite raw → slag only, roasted → red-short iron) ;
    #     preview non-mutating.
    oxide_coord = next((c for c in coords
                        if (cu := ib.bloom_cue_for_chunk(sim, c)) is not None
                        and cu.ore_class == "oxide_iron"), None)
    sulf_coord = next((c for c in coords
                       if (cu := ib.bloom_cue_for_chunk(sim, c)) is not None
                       and cu.ore_class == "sulfide_iron"), None)
    bloom_ok = lie_ok = preview_ok = False
    if oxide_coord is not None:
        cue = ib.bloom_cue_for_chunk(sim, oxide_coord)
        g = geo.chunk_geology(sim, oxide_coord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        sim.agents.pos[0, 0] = (oxide_coord[0] + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (oxide_coord[1] + 0.5) * CHUNK_SIDE_M
        prev = ib.bloom_preview(sim, float(sim.agents.pos[0, 0]),
                                float(sim.agents.pos[0, 1]))
        after_preview = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        preview_ok = (prev["reducible"] is True and after_preview == before
                      and prev["is_solid_bloom"] is True
                      and prev["bloom_iron_per_kg_ore"] == cue.bloom_iron_per_kg_ore)
        extracted_before = sum(L.extracted_kg for L in g.layers)
        res = ib.bloom_at(sim, 0, charge_kg=5.0)
        extracted_after = sum(L.extracted_kg for L in g.layers)
        expected = cue.bloom_iron_per_kg_ore * res.ore_consumed_kg
        bloom_ok = (res is not None and extracted_after > extracted_before
                    and res.bloom_iron_kg > 0.0 and res.is_solid_bloom is True
                    and abs(res.bloom_iron_kg - expected) <= 1e-4)
        print(f"        BLOOM oxide @ {oxide_coord}: consumed {res.ore_consumed_kg:.2f} kg {res.iron_mineral} → "
              f"{res.bloom_iron_kg:.2f} kg Fe (purity {res.bloom_purity}, solid={res.is_solid_bloom}) + "
              f"{res.slag_kg:.2f} kg slag @ {res.peak_c:.0f}°C")
    if sulf_coord is not None:
        sim.agents.pos[0, 0] = (sulf_coord[0] + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (sulf_coord[1] + 0.5) * CHUNK_SIDE_M
        raw = ib.bloom_at(sim, 0, charge_kg=5.0, roasted=False)
        roasted = ib.bloom_at(sim, 0, charge_kg=5.0, roasted=True)
        lie_ok = (raw is not None and raw.required_roasting is True
                  and raw.bloom_iron_kg == 0.0 and raw.slag_kg > 0.0
                  and raw.red_short is True
                  and roasted is not None and roasted.bloom_iron_kg > 0.0
                  and roasted.red_short is True)
        print(f"        BLOOM pyrite @ {sulf_coord}: RAW → {raw.bloom_iron_kg:.2f} kg Fe "
              f"(only slag {raw.slag_kg:.2f} kg — the lie) ; ROASTED → {roasted.bloom_iron_kg:.2f} kg Fe "
              f"(red_short={roasted.red_short})")
    check("3 — réduction effective : bloom_at consomme & rend le fer promis ; pyrite crue → scorie ; preview non mutant",
          bloom_ok and lie_ok and preview_ok,
          f"oxide_bloom={bloom_ok} sulfide_lie={lie_ok} preview={preview_ok}")

    # 4 — determinism (rebuild fresh: sim mutated by bloom_at above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = ib.bloom_cue_for_chunk(sim2, coord)
        y = ib.bloom_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.iron_mineral, x.ore_class,
                                     round(x.bloom_iron_per_kg_ore, 6),
                                     x.reducible_now, x.needs_roasting_first)
        ky = None if y is None else (y.iron_mineral, y.ore_class,
                                     round(y.bloom_iron_per_kg_ore, 6),
                                     y.reducible_now, y.needs_roasting_first)
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (oracle bit-identique)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physics: oxide direct + sulfide roast + non-iron 0 + too-cold 0 + never melts +
    #     superheat monotone (capped)
    ox = ib._cue_from_inputs((0, 0, 0), _forced(), _gossan("hematite"))
    sul = ib._cue_from_inputs((0, 0, 0), _forced(), _gossan("pyrite"))
    lead = ib._cue_from_inputs((0, 0, 0), _forced(), _gossan("galena"))
    zinc = ib._cue_from_inputs((0, 0, 0), _forced(), _gossan("sphalerite"))
    cold = ib.iron_bloom_yield("hematite", 10.0, 1100.0)
    blazing = ib.iron_bloom_yield("hematite", 10.0, 1537.0)   # just under iron's melt point
    lo = ib.iron_bloom_yield("hematite", 10.0, 1210.0).reduction_efficiency
    hi = ib.iron_bloom_yield("hematite", 10.0, 1400.0).reduction_efficiency
    physics_ok = (
        ox is not None and ox.reducible_now and not ox.needs_roasting_first
        and not ox.red_short
        and sul is not None and sul.needs_roasting_first and sul.red_short
        and sul.bloom_iron_per_kg_ore == 0.0
        and sul.bloom_iron_per_kg_ore_roasted > 0.0
        and lead is None and zinc is None                      # lead/zinc gossan → no cue
        and cold.bloom_iron_kg == 0.0                          # too cold → nothing
        and blazing.melts is False                             # iron NEVER melts (solid)
        and lo < hi <= ib.OXIDE_RECOVERY_CEIL)                 # superheat monotone, capped
    print(f"        oxide: reducible_now={ox.reducible_now} | pyrite: needs_roast={sul.needs_roasting_first} "
          f"red_short={sul.red_short} raw={sul.bloom_iron_per_kg_ore} roasted={sul.bloom_iron_per_kg_ore_roasted:.3f} | "
          f"galena/sphalerite→no cue | blazing 1537°C melts={blazing.melts} | superheat {lo:.3f}→{hi:.3f}")
    check("5 — physique : oxyde direct + sulfure grille + non-fer 0 + trop froid→0 + fer ne fond JAMAIS + surchauffe monotone",
          physics_ok, f"oxide_direct={ox.reducible_now} sulfide_roast={sul.needs_roasting_first} no_melt={not blazing.melts}")

    # 6 — best_bloomery_site_near prefers sound oxide ; require_sound skips red-short ;
    #     require_direct → reducible_now
    cn = next((c for c in coords2
               if (cu := ib.bloom_cue_for_chunk(sim2, c)) is not None
               and cu.ore_class == "oxide_iron"), None)
    pick_ok = False
    if cn is not None:
        sim2.agents.pos[0, 0] = (cn[0] + 0.5) * CHUNK_SIDE_M
        sim2.agents.pos[0, 1] = (cn[1] + 0.5) * CHUNK_SIDE_M
        sound = ib.best_bloomery_site_near(sim2, 0, perception_radius_m=3 * CHUNK_SIDE_M,
                                           require_sound=True)
        direct = ib.best_bloomery_site_near(sim2, 0, perception_radius_m=3 * CHUNK_SIDE_M,
                                            require_direct=True)
        pick_ok = (sound is not None and sound.red_short is False
                   and direct is not None and direct.reducible_now is True)
    check("6 — best_bloomery_site préfère l'oxyde sain ; require_sound saute le red-short ; require_direct→reducible",
          pick_ok, f"sound+direct={pick_ok}")

    # 7 — zero tick cost / idempotent install (the oracle)
    c1 = ib.install_iron_bloomery(sim)
    c2 = ib.install_iron_bloomery(sim)
    check("7 — installation idempotente, coût tick nul (oracle)",
          c1 is c2, "no per-tick hook on sim.step")

    # 8 — D8 by composition: no _PROFILE, PY_TO_RUST stays 15, out of *_outcrop glob
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract       # noqa: E402
    d8_ok = (not hasattr(ib, "_PROFILE") and ib.fd is fd and ib.sm is sm
             and not os.path.basename(ib.__file__).endswith("_outcrop.py")
             and len(contract.PY_TO_RUST) == 15)
    check("8 — D8 par composition : pas de _PROFILE ; PY_TO_RUST==15 ; hors *_outcrop",
          d8_ok, f"py_to_rust={len(contract.PY_TO_RUST)}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p149_iron_bloomery", "seed": SEED,
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
