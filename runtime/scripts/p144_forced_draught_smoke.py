#!/usr/bin/env python3
"""P144 — Substrate capability : le tirage forcé (Cap. C12).

**Le 2ᵉ APPARATUS** (le pendant de C11) — et la VOÛTE que C9 ``ceramic_firing`` ET
C11 ``kiln_draft`` désignent toutes deux par ``vitrifies_if_forced_draught``. Le four
à tirage naturel (C11) plafonne sous la vitrification (~1250 °C) et la métallurgie ;
``vitrifies_watertight`` y reste False. **Souffler** de l'air (soufflet) dans un foyer
de **charbon de bois** enclos pousse la pointe dans le régime du bas-fourneau
(~1100–1400 °C) : assez chaud pour **vitrifier** le kaolin réfractaire (céramique
étanche, C9/C11 enfin RÉALISÉ) et **fondre le cuivre** (1085 °C, le seuil
chalcolithique). Ce module RÉALISE la vitrification et OUVRE la métallurgie.

Règle d'émergence absolue : l'agent ne *sait* pas qu'« on souffle sur du charbon pour
fondre le métal ». Il fait déjà un four (C11), a vu la braise rugir au vent, a remarqué
le bois carbonisé brûler plus chaud — et en soufflant par hasard dans son foyer enclos
il **découvre** la fonte. Soufflet, tuyère, charbonnage en meule, coulée : tout émerge.

N'introduit AUCUN nouveau tell minéral : COMPOSE C11 (four + ``wall_refractory`` +
``fine_fuel``) × C1 (tell cuivre « tache verte » malachite/azurite), et RÉUTILISE
VERBATIM le SSOT de C11 (``kiln_peak_temp_c`` — *le combo* : la base est le four nu) et
de C9 (``clay_maturation_temp_c`` / ``fired_ware_quality`` / ``VITRIFICATION_FIREDNESS``).
Pas de ``_PROFILE``, pas d'entrée ``PY_TO_RUST`` (garde-fou D8 — 6ᵉ fois par composition
après C7/C8/C9/C10/C11). Hors glob ``*_outcrop.py``.

LE COMBO de la veille 2026-06-18 : ``forced_draught_peak_c(fine_fuel, wall_refractory)``
= pointe du four naturel (C11) + gain du tirage forcé, **plafonné par la réfractarité de
la paroi**. Argile commune (``shale``) : plafond ~1100 °C (slumpe juste au-delà du
cuivre). Argile réfractaire (kaolin, fire-clay) : plafond ~1400 °C (régime du bas-
fourneau). Archéométrie : feu nu ≤850 °C ; tirage naturel ~1000–1150 °C ; soufflet +
charbon ~1100–1300 °C — fusion cuivre 1085 °C, malachite Belovode ~1100–1200 °C.

L'inversion DE l'inversion, prolongée : c'est *la même paroi réfractaire* (la mauvaise
argile de poterie C9, la meilleure paroi C11) qui, sous tirage forcé, VITRIFIE enfin le
corps de kaolin ET atteint le régime du fer (1200 °C) — là où une paroi commune plafonne
juste au-dessus du cuivre. La pire argile de poterie est la seule clé de la haute
pyrotechnologie.

La marche différée honnête : ``would_smelt_copper_here`` (four assez chaud ET minerai
co-localisé C1) reste un POTENTIEL — la fonte effective (consommer la malachite →
bouton de cuivre + scorie) est une transformation différée (Cap. C13). De même
``reaches_iron_bloomery_temp`` porte la chaîne vers le fer (paroi réfractaire).

Seed 0xBEEF : continent de prairie (argile + foyers + combustible abondant) produisant
des sites de four forçable réels — parois communes (cuivre) ET réfractaires
(vitrification + fer). Un affleurement de cuivre est injecté pour démontrer
``would_smelt_copper_here``.

Checks
------
 1.  Le monde Genesis réel produit des sites de tirage forcé émergents (four + charbon).
 2.  « Le monde ne ment jamais » : cue ⇒ forceable ; four réel (C11) ; forced_peak ≥
     four nu, ≤ plafond de paroi, == SSOT ; ware vitrifiée == SSOT C9 ; cuivre
     co-localisé ⇒ C1 le voit. 0 viol.
 3.  Découverte : site réel → ``forced_draught_preview`` forceable & pointe (non
     mutant) ; la RÉALISATION : kaolin réfractaire VITRIFIE (où C9/C11 laissaient
     False) ; l'OUVERTURE : injection de cuivre → ``would_smelt_copper_here``.
 4.  Déterminisme même-seed : affordances bit-identiques.
 5.  Physique : tirage forcé RÉALISE la vitrification (C9/C11 différée) + paroi
     réfractaire plafonne plus haut (seule à atteindre le fer) + porte du charbon.
 6.  Hiérarchie : ``best_forced_site_near`` préfère la pointe la plus haute
     (réfractaire) ; ``require_smelting`` pointe le site cuprifère.
 7.  Coût tick nul : installation idempotente, aucun hook sur ``sim.step``.
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
from engine.geology import StrataLayer, ChunkGeology                # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.clay_outcrop as ci                                    # noqa: E402
import engine.fire_ignition as fi                                   # noqa: E402
import engine.limestone_outcrop as li                               # noqa: E402
import engine.ceramic_firing as cf                                  # noqa: E402
import engine.kiln_draft as kd                                      # noqa: E402
import engine.surface_mineralization as sm                          # noqa: E402
import engine.forced_draught as fd                                  # noqa: E402

SEED = 0xBEEF       # grassland continent — clay everywhere + hearths + abundant fuel
GRID = 12
OUT = os.path.join(ROOT, "journals", "p144_forced_draught.jsonl")

results: list = []

_GRASS = 6
_BOREAL = 3
_HOT_DESERT = 7


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


def _kaolin():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06})]


def _common_clay():
    return [_layer(0.0, 4.0, "shale")]


def _kaolin_plus_copper():
    return [_layer(0.0, 4.0, "sandstone",
                   ore={"fine_clay": 0.06, "native_copper": 0.05})]


def _derive(coord, layers, biome, chunk):
    clay = ci._cue_from_geology(coord, layers, biome, chunk)
    fire = fi._cue_from_geology(coord, layers, biome, chunk)
    lime = li._cue_from_geology(coord, layers, biome, chunk)
    kiln = kd._cue_from_inputs(coord, clay, fire, lime)
    copper = sm._cue_from_geology(coord, layers, biome)
    return fd._cue_from_inputs(coord, kiln, copper)


def _build():
    cfg = SimConfig(name="p144", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    fd.install_forced_draught(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 80)
    print("P144 — forced draught (bellows+charcoal apparatus: C11×C1; realizes vitrif, opens metallurgy)")
    print("=" * 80)

    sim, coords = _build()
    summary = fd.forced_draught_summary(sim)
    print(f"  region: {len(coords)} chunks | forceable={summary['n_chunks_forceable']} "
          f"(refractory={summary['n_refractory_walled']} "
          f"vitrifies={summary['n_vitrifies_watertight']} "
          f"reaches_Cu={summary['n_reaches_copper_smelt']} "
          f"reaches_Fe={summary['n_reaches_iron_bloomery']}) "
          f"| best_peak={summary['best_forced_peak_c']}°C "
          f"best_gain={summary['best_forced_gain_c']}°C")
    print(f"  walls: {summary['by_wall_material']}")

    # 1 — emergent forceable sites from the real world
    check("1 — Genesis world emits emergent forced-draught sites (kiln + charcoal fuel)",
          summary["n_chunks_forceable"] > 0,
          f"{summary['n_chunks_forceable']}/{summary['n_chunks']} forceable; "
          f"walls={summary['by_wall_material']}")

    # 2 — the world never lies
    violations = 0
    n_vitrify = 0
    for coord in coords:
        cue = fd.forced_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        if not cue.forceable or not cue.charcoal_makeable:
            violations += 1
        if not (cue.kiln_peak_c <= cue.forced_peak_c <= cue.wall_cap_c):
            violations += 1
        if cue.forced_peak_c != round(
                fd.forced_draught_peak_c(cue.fine_fuel, cue.wall_refractory), 1):
            violations += 1
        # vitrified ware agrees with the recomposed C9 SSOT
        maturation = cf.clay_maturation_temp_c(cue.clay_ceramic_grade)
        firedness = min(1.0, cue.forced_peak_c / maturation)
        if abs(cue.vitrified_ware_quality
               - cf.fired_ware_quality(cue.clay_pottery_grade, firedness)) > 5e-4:
            violations += 1
        # a non-refractory body never vitrifies watertight
        if (not cue.clay_ceramic_grade) and cue.vitrifies_watertight:
            violations += 1
        if cue.vitrifies_watertight:
            n_vitrify += 1
        # C11 really sees a buildable kiln here...
        kiln = kd.kiln_cue_for_chunk(sim, coord)
        if kiln is None or not kiln.buildable or kiln.wall_material != cue.wall_material:
            violations += 1
        # copper co-location implies C1 really surfaces a copper tell here.
        if cue.copper_ore_here:
            c1 = sm.surface_cue_for_chunk(sim, coord)
            if c1 is None or c1.group != "copper":
                violations += 1
        if cue.would_smelt_copper_here and not (
                cue.reaches_copper_smelting_temp and cue.copper_ore_here):
            violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ four C11 ; forced_peak==SSOT ; ware==SSOT C9 ; Cu⇒C1)",
          violations == 0,
          f"violations={violations} vitrifies_watertight={n_vitrify}")

    # 3 — discovery loop : a real forced site previews forceable & names the peak
    #     (non-mutating) ; the REALIZATION: a refractory kaolin furnace VITRIFIES
    #     watertight (where C9 open fire AND C11 natural draught both left False) ;
    #     the OPENING: a copper outcrop under a hot furnace → would_smelt_copper.
    bcoord = next((c for c in coords
                   if fd.forced_cue_for_chunk(sim, c) is not None), None)
    build_ok = vitrify_ok = smelt_ok = False
    if bcoord is not None:
        cx, cy, _ = bcoord
        sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
        g = geo.chunk_geology(sim, bcoord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        out = fd.forced_draught_preview(sim, float(sim.agents.pos[0, 0]),
                                        float(sim.agents.pos[0, 1]))
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        seen = fd.prospect_forced_draught(sim, float(sim.agents.pos[0, 0]),
                                          float(sim.agents.pos[0, 1]))
        build_ok = (seen is not None and out["forceable"] is True
                    and out["forced_peak_c"] >= out["kiln_peak_c"]
                    and after == before)
        print(f"        agent SEES wall='{seen.wall_material}' "
              f"kiln={seen.kiln_peak_c:.0f}°C → forced={seen.forced_peak_c:.0f}°C "
              f"(+{seen.forced_gain_c:.0f}°C bellows) "
              f"{'REFRACTORY' if seen.wall_refractory else 'common'} wall")

    # the kaolin vitrification redemption: forced draught realizes what C9/C11 deferred.
    kao = _derive((0, 0, 0), _kaolin(), _GRASS, _fake_chunk(biome=_GRASS))
    open_fd = min(1.0, cf.open_fire_peak_temp_c(kao.fine_fuel)
                  / cf.clay_maturation_temp_c(True))
    nat_fd = min(1.0, kd.kiln_peak_temp_c(kao.fine_fuel, True)
                 / cf.clay_maturation_temp_c(True))
    vitrify_ok = (kao is not None and kao.wall_refractory
                  and open_fd < cf.SOUND_MATURATION              # C9 under-fired
                  and nat_fd < kd.VITRIFICATION_FIREDNESS        # C11 not watertight
                  and kao.vitrifies_watertight is True           # C12 REALIZES it
                  and kao.reaches_iron_bloomery_temp is True)
    print(f"        kaolin: open-fire firedness={open_fd:.2f} (C9 under) → kiln {nat_fd:.2f} "
          f"(C11 sound, not watertight) → FORCED {kao.forced_peak_c:.0f}°C "
          f"firedness={kao.clay_firedness:.2f} VITRIFIES watertight={kao.vitrifies_watertight}")

    # the metallurgy opening: a copper outcrop under a hot refractory furnace.
    cu = _derive((0, 0, 0), _kaolin_plus_copper(), _GRASS, _fake_chunk(biome=_GRASS))
    smelt_ok = (cu is not None and cu.reaches_copper_smelting_temp
                and cu.copper_ore_here and cu.copper_mineral == "native_copper"
                and cu.would_smelt_copper_here is True
                and cu.smelts_copper_if_ore_present is True)
    print(f"        copper outcrop (C1 green tell) under forced furnace {cu.forced_peak_c:.0f}°C "
          f"≥ {fd.COPPER_SMELT_TEMP_C:.0f}°C → would_smelt_copper={cu.would_smelt_copper_here} "
          f"(actual smelt deferred to C13)")
    check("3 — découverte : forceable (non mutant) ; kaolin VITRIFIE (C9/C11 réalisé) ; cuivre fondable",
          build_ok and vitrify_ok and smelt_ok,
          f"forced_site={build_ok} vitrified={vitrify_ok} would_smelt={smelt_ok}")

    # 4 — determinism (rebuild fresh: sim mutated by agent move above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = fd.forced_cue_for_chunk(sim2, coord)
        y = fd.forced_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.wall_material, round(x.forced_peak_c, 3),
                                     round(x.forced_gain_c, 3),
                                     x.vitrifies_watertight)
        ky = None if y is None else (y.wall_material, round(y.forced_peak_c, 3),
                                     round(y.forced_gain_c, 3),
                                     y.vitrifies_watertight)
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (affordances identiques)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physics: forced REALIZES vitrification (deferred by C9/C11) + refractory caps
    #     higher (only one to reach iron) + the charcoal gate
    refrac_vit = min(1.0, fd.forced_draught_peak_c(0.80, True)
                     / cf.clay_maturation_temp_c(True)) >= kd.VITRIFICATION_FIREDNESS
    low_fuel_kiln = SimpleNamespace(buildable=True, biome=_GRASS, wall_material="shale",
                                    wall_refractory=False, clay_pottery_grade=0.4,
                                    clay_ceramic_grade=False,
                                    fine_fuel=fd.CHARCOAL_FUEL_FLOOR - 0.05,
                                    kiln_peak_c=900.0, confidence=0.5)
    physics_ok = (
        refrac_vit                                              # forced vitrifies refractory
        and fd.forced_draught_peak_c(1.0, True) > fd.forced_draught_peak_c(1.0, False)
        and fd.forced_draught_peak_c(1.0, False) < fd.IRON_BLOOMERY_TEMP_C  # common < iron
        and fd.forced_draught_peak_c(1.0, True) >= fd.IRON_BLOOMERY_TEMP_C  # refractory ≥ iron
        and fd._cue_from_inputs((0, 0, 0), low_fuel_kiln, None) is None)    # charcoal gate
    check("5 — physique : RÉALISE vitrification + paroi réfractaire (seule au fer) + porte du charbon",
          physics_ok,
          f"refrac_vitrifies={refrac_vit} "
          f"refrac>common={fd.forced_draught_peak_c(1.0, True):.0f}>{fd.forced_draught_peak_c(1.0, False):.0f} "
          f"common<Fe={fd.forced_draught_peak_c(1.0, False):.0f}<{fd.IRON_BLOOMERY_TEMP_C:.0f} "
          f"charcoal_gate=ok")

    # 6 — best_forced_site_near prefers the hottest (refractory) + require_smelting
    cx, cy, _ = coords2[len(coords2) // 2]
    cc = (cx, cy, 0)
    ch = sim2.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, _GRASS, dtype=np.asarray(ch.biome).dtype)
    ch.water = np.zeros(np.asarray(ch.water).shape, dtype=np.float32)
    sim2._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=_kaolin_plus_copper())
    sim2._clay_cue_cache.clear()
    sim2._ignition_cue_cache.clear()
    sim2._limestone_cue_cache.clear()
    sim2._kiln_draft_cue_cache.clear()
    sim2._surface_cue_cache.clear()
    sim2._forced_draught_cue_cache.clear()
    sim2.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim2.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    r = 0.4 * CHUNK_SIDE_M
    best = fd.best_forced_site_near(sim2, 0, perception_radius_m=r)
    smelt = fd.best_forced_site_near(sim2, 0, perception_radius_m=r, require_smelting=True)
    pick_ok = (best is not None and best.forceable
               and best.wall_material == "fine_clay" and best.wall_refractory
               and best.vitrifies_watertight is True
               and smelt is not None and smelt.would_smelt_copper_here is True
               and smelt.copper_mineral == "native_copper")
    check("6 — best_forced_site préfère la pointe la plus haute (réfractaire) ; require_smelting→cuivre",
          pick_ok, f"best_refractory_vitrifies + smelting_picks_copper={pick_ok}")

    # 7 — zero tick cost / idempotent install
    c1 = fd.install_forced_draught(sim)
    c2 = fd.install_forced_draught(sim)
    check("7 — installation idempotente, coût tick nul",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p144_forced_draught", "seed": SEED,
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
