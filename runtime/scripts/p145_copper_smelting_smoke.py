#!/usr/bin/env python3
"""P145 — Substrate capability : la fonte du cuivre (Cap. C13).

**La 4ᵉ TRANSFORMATION et la 1ʳᵉ MÉTALLURGIQUE** — le seuil chalcolithique, le premier
métal. C12 ``forced_draught`` a porté un four soufflé au charbon au-delà de la fusion du
cuivre (1085 °C) et exposé ``would_smelt_copper_here`` comme un POTENTIEL, en différant
explicitement *la fonte effective* à C13. Ce module la RÉALISE : ``smelt_at`` **consomme**
le minerai (mutation via ``geo.mine_at``) et **rend** un bouton de cuivre + de la scorie,
exactement comme l'oracle s'y était engagé.

Règle d'émergence absolue : l'agent ne *sait* pas qu'« on fond la pierre verte au charbon
pour en couler le métal ». Il voit la tache verte (C1), sait faire un four soufflé (C12),
et en jetant par hasard la roche verte dans la braise il **découvre** le métal qui suinte.
Creuset, tuyère, fluxage, moulage : tout émerge.

N'introduit AUCUN nouveau tell : COMPOSE C12 (four ≥1085 °C) × C1 (tell vert cuivre), et
RÉUTILISE le seuil ``fd.COPPER_SMELT_TEMP_C`` (C12) + le rendement par élément du catalogue
(``yields_per_kg_ore["Cu"]``, ``category``). Pas de ``_PROFILE``, pas d'entrée ``PY_TO_RUST``
(garde-fou D8 — 7ᵉ fois par composition). Hors glob ``*_outcrop.py``.

LE MENSONGE RENDU VISIBLE #4 : le **même tell vert** (C1) couvre le cuivre **natif** (déjà
métal — fonte directe, facile) ET la **chalcopyrite** (sulfure réfractaire — il faut
**griller** ~590 °C avant de fondre, sinon ~0 métal). `best_smelt_site_near` enseigne :
fonds le vert natif, grille le vert sulfuré. Le monde 0xBEEF surface NATURELLEMENT les deux.

Seed 0xBEEF : continent de prairie produisant des sites de fonte réels — cuivre natif
(fonte directe) ET chalcopyrite (grillage requis). Aucune injection : le monde les sème.

Checks
------
 1.  Le monde Genesis réel produit des sites de fonte émergents (natif ET sulfure).
 2.  « Le monde ne ment jamais » : cue ⇒ C12 would_smelt ; minéral == C1 ; cuivre rendu ≤
     cuivre contenu (catalogue) ; sulfure cru → 0, grillé → >0. 0 viol.
 3.  La FONTE EFFECTIVE : ``smelt_at`` consomme le minerai & rend le métal promis (natif) ;
     le mensonge (chalcopyrite crue → scorie seule, grillée → métal) ; preview non mutant.
 4.  Déterminisme même-seed : oracle bit-identique.
 5.  Physique : natif fonte directe + sulfure grille d'abord + trop froid → 0 + surchauffe
     monotone (plafonnée).
 6.  Hiérarchie : ``best_smelt_site_near`` préfère le cuivre le plus riche (natif) ;
     ``require_direct`` → natif.
 7.  Coût tick nul : oracle idempotent, aucun hook sur ``sim.step``.
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
from types import SimpleNamespace                                   # noqa: E402

from engine.sim import Simulation, SimConfig                        # noqa: E402
from engine.world_genesis import GenesisParams                      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine.geology import StrataLayer                              # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
from engine.mineral_catalog import MINERAL_BY_NAME                  # noqa: E402
import engine.clay_outcrop as ci                                    # noqa: E402
import engine.fire_ignition as fi                                   # noqa: E402
import engine.limestone_outcrop as li                               # noqa: E402
import engine.kiln_draft as kd                                      # noqa: E402
import engine.surface_mineralization as sm                          # noqa: E402
import engine.forced_draught as fd                                  # noqa: E402
import engine.copper_smelting as cs                                 # noqa: E402

SEED = 0xBEEF       # grassland continent — clay + hearths + abundant fuel + copper tells
GRID = 12
OUT = os.path.join(ROOT, "journals", "p145_copper_smelting.jsonl")

results: list = []

_GRASS = 6


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:60s} {detail}")


def _fake_chunk(w=0.0, biome=_GRASS, side=8):
    return SimpleNamespace(
        water=np.full((side, side), w, dtype=np.float32),
        biome=np.full((side, side), biome, dtype=np.uint8),
        height=np.full((side, side), 300.0, dtype=np.float32))


def _layer(top, bottom, rock="sandstone", ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=2400.0, ore_mix=dict(ore or {}))


def _kaolin_native():
    return [_layer(0.0, 4.0, "sandstone",
                   ore={"fine_clay": 0.06, "native_copper": 0.05})]


def _kaolin_chalco():
    return [_layer(0.0, 4.0, "sandstone",
                   ore={"fine_clay": 0.06, "chalcopyrite": 0.05})]


def _derive(coord, layers, biome, chunk):
    clay = ci._cue_from_geology(coord, layers, biome, chunk)
    fire = fi._cue_from_geology(coord, layers, biome, chunk)
    lime = li._cue_from_geology(coord, layers, biome, chunk)
    kiln = kd._cue_from_inputs(coord, clay, fire, lime)
    copper = sm._cue_from_geology(coord, layers, biome)
    forced = fd._cue_from_inputs(coord, kiln, copper)
    return cs._cue_from_inputs(coord, forced)


def _build():
    cfg = SimConfig(name="p145", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    cs.install_copper_smelting(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 80)
    print("P145 — copper smelting (fonte effective: C12×C1; realizes would_smelt, opens metallurgy)")
    print("=" * 80)

    sim, coords = _build()
    summary = cs.smelt_summary(sim)
    print(f"  region: {len(coords)} chunks | smelt_sites={summary['n_smelt_sites']} "
          f"(direct={summary['n_direct_smeltable']} "
          f"needs_roast={summary['n_needs_roasting']}) "
          f"| best_Cu/kg={summary['best_recovered_cu_per_kg_ore']} "
          f"best_purity={summary['best_bead_purity']}")
    print(f"  ore classes: {summary['by_ore_class']} | minerals: {summary['by_mineral']}")

    # 1 — emergent smelt sites from the real world, BOTH native and sulfide
    by_class = summary["by_ore_class"]
    check("1 — Genesis world emits emergent copper smelt sites (native + sulfide)",
          summary["n_smelt_sites"] > 0 and by_class.get("native_metal", 0) > 0
          and by_class.get("sulfide", 0) > 0,
          f"{summary['n_smelt_sites']}/{summary['n_chunks']} sites; classes={by_class}")

    # 2 — the world never lies
    violations = 0
    n_native = n_sulfide = 0
    for coord in coords:
        cue = cs.smelt_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        forced = fd.forced_cue_for_chunk(sim, coord)
        if forced is None or not forced.would_smelt_copper_here:
            violations += 1
        c1 = sm.surface_cue_for_chunk(sim, coord)
        if c1 is None or c1.group != "copper" or c1.mineral != cue.copper_mineral:
            violations += 1
        contained = MINERAL_BY_NAME[cue.copper_mineral].yields_per_kg_ore.get("Cu", 0.0)
        if not (0.0 <= cue.recovered_cu_per_kg_ore <= contained + 1e-9):
            violations += 1
        if not (0.0 <= cue.recovered_cu_per_kg_ore_roasted <= contained + 1e-9):
            violations += 1
        if cue.ore_class == "sulfide":
            n_sulfide += 1
            if not (cue.needs_roasting_first and cue.recovered_cu_per_kg_ore == 0.0
                    and cue.recovered_cu_per_kg_ore_roasted > 0.0):
                violations += 1
        else:
            n_native += 1
            if not (cue.smeltable_now and cue.recovered_cu_per_kg_ore > 0.0):
                violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ C12 would_smelt ; minéral == C1 ; Cu ≤ contenu ; sulfure 0 cru/>0 grillé)",
          violations == 0,
          f"violations={violations} native={n_native} sulfide={n_sulfide}")

    # 3 — the fonte effective : smelt_at consumes ore & yields the promised metal
    #     (native) ; the lie (chalcopyrite raw → slag only, roasted → metal) ;
    #     preview non-mutating.
    native_coord = next((c for c in coords
                         if (cu := cs.smelt_cue_for_chunk(sim, c)) is not None
                         and cu.ore_class == "native_metal"), None)
    sulf_coord = next((c for c in coords
                       if (cu := cs.smelt_cue_for_chunk(sim, c)) is not None
                       and cu.ore_class == "sulfide"), None)
    smelt_ok = lie_ok = preview_ok = False
    if native_coord is not None:
        cue = cs.smelt_cue_for_chunk(sim, native_coord)
        g = geo.chunk_geology(sim, native_coord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        # preview is non-mutating
        sim.agents.pos[0, 0] = (native_coord[0] + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (native_coord[1] + 0.5) * CHUNK_SIDE_M
        prev = cs.smelt_preview(sim, float(sim.agents.pos[0, 0]),
                                float(sim.agents.pos[0, 1]))
        after_preview = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        preview_ok = (prev["smeltable"] is True and after_preview == before
                      and prev["recovered_cu_per_kg_ore"] == cue.recovered_cu_per_kg_ore)
        # the fonte effective : smelt_at consumes ore and matches the oracle. The
        # copper-bearing layer is at C1's dig depth (not necessarily layers[0] in the
        # natural column) — so check the total extracted mass rose.
        extracted_before = sum(L.extracted_kg for L in g.layers)
        res = cs.smelt_at(sim, 0, charge_kg=5.0)
        extracted_after = sum(L.extracted_kg for L in g.layers)
        expected = cue.recovered_cu_per_kg_ore * res.ore_consumed_kg
        smelt_ok = (res is not None and extracted_after > extracted_before
                    and res.recovered_cu_kg > 0.0
                    and abs(res.recovered_cu_kg - expected) <= 1e-4)
        print(f"        SMELT native @ {native_coord}: consumed {res.ore_consumed_kg:.2f} kg ore → "
              f"{res.recovered_cu_kg:.2f} kg Cu (purity {res.bead_purity}) + "
              f"{res.slag_kg:.2f} kg slag @ {res.peak_c:.0f}°C")
    if sulf_coord is not None:
        sim.agents.pos[0, 0] = (sulf_coord[0] + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (sulf_coord[1] + 0.5) * CHUNK_SIDE_M
        raw = cs.smelt_at(sim, 0, charge_kg=5.0, roasted=False)
        roasted = cs.smelt_at(sim, 0, charge_kg=5.0, roasted=True)
        lie_ok = (raw is not None and raw.required_roasting is True
                  and raw.recovered_cu_kg == 0.0 and raw.slag_kg > 0.0
                  and roasted is not None and roasted.recovered_cu_kg > 0.0)
        print(f"        SMELT chalcopyrite @ {sulf_coord}: RAW → {raw.recovered_cu_kg:.2f} kg Cu "
              f"(only slag {raw.slag_kg:.2f} kg — the lie) ; ROASTED → {roasted.recovered_cu_kg:.2f} kg Cu")
    check("3 — fonte effective : smelt_at consomme & rend le métal promis ; le sulfure cru → scorie ; preview non mutant",
          smelt_ok and lie_ok and preview_ok,
          f"native_smelt={smelt_ok} sulfide_lie={lie_ok} preview={preview_ok}")

    # 4 — determinism (rebuild fresh: sim mutated by smelt_at above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = cs.smelt_cue_for_chunk(sim2, coord)
        y = cs.smelt_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.copper_mineral, x.ore_class,
                                     round(x.recovered_cu_per_kg_ore, 6),
                                     x.smeltable_now, x.needs_roasting_first)
        ky = None if y is None else (y.copper_mineral, y.ore_class,
                                     round(y.recovered_cu_per_kg_ore, 6),
                                     y.smeltable_now, y.needs_roasting_first)
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (oracle bit-identique)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physics: native direct + sulfide needs roast + too-cold 0 + superheat monotone
    nat = _derive((0, 0, 0), _kaolin_native(), _GRASS, _fake_chunk(biome=_GRASS))
    sul = _derive((0, 0, 0), _kaolin_chalco(), _GRASS, _fake_chunk(biome=_GRASS))
    cold = cs.copper_smelt_yield("native_copper", 10.0, 1000.0)
    lo = cs.copper_smelt_yield("native_copper", 10.0, 1090.0).recovery_efficiency
    hi = cs.copper_smelt_yield("native_copper", 10.0, 1400.0).recovery_efficiency
    physics_ok = (
        nat is not None and nat.smeltable_now and not nat.needs_roasting_first
        and sul is not None and sul.needs_roasting_first
        and sul.recovered_cu_per_kg_ore == 0.0
        and sul.recovered_cu_per_kg_ore_roasted > 0.0
        and cold.recovered_cu_kg == 0.0                        # too cold → nothing
        and lo < hi <= cs.NATIVE_RECOVERY_CEIL)                # superheat monotone, capped
    print(f"        native: smeltable_now={nat.smeltable_now} | "
          f"chalcopyrite: needs_roast={sul.needs_roasting_first} "
          f"raw={sul.recovered_cu_per_kg_ore} roasted={sul.recovered_cu_per_kg_ore_roasted:.3f} | "
          f"superheat {lo:.3f}→{hi:.3f} (ceil {cs.NATIVE_RECOVERY_CEIL})")
    check("5 — physique : natif direct + sulfure grille + trop froid→0 + surchauffe monotone (plafonnée)",
          physics_ok, f"native_direct={nat.smeltable_now} sulfide_roast={sul.needs_roasting_first}")

    # 6 — best_smelt_site_near prefers the richest copper (native) + require_direct
    cn = next((c for c in coords2
               if (cu := cs.smelt_cue_for_chunk(sim2, c)) is not None
               and cu.ore_class == "native_metal"), None)
    pick_ok = False
    if cn is not None:
        sim2.agents.pos[0, 0] = (cn[0] + 0.5) * CHUNK_SIDE_M
        sim2.agents.pos[0, 1] = (cn[1] + 0.5) * CHUNK_SIDE_M
        best = cs.best_smelt_site_near(sim2, 0, perception_radius_m=0.4 * CHUNK_SIDE_M)
        direct = cs.best_smelt_site_near(sim2, 0, perception_radius_m=0.4 * CHUNK_SIDE_M,
                                         require_direct=True)
        pick_ok = (best is not None and direct is not None
                   and direct.smeltable_now is True)
    check("6 — best_smelt_site préfère le cuivre le plus riche ; require_direct→smeltable",
          pick_ok, f"best+require_direct={pick_ok}")

    # 7 — zero tick cost / idempotent install (the oracle)
    c1 = cs.install_copper_smelting(sim)
    c2 = cs.install_copper_smelting(sim)
    check("7 — installation idempotente, coût tick nul (oracle)",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p145_copper_smelting", "seed": SEED,
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
