#!/usr/bin/env python3
"""P151 — Substrate capability : le cinglage de la loupe (Cap. C19).

**La 6ᵉ TRANSFORMATION et la 3ᵉ MÉTALLURGIQUE — elle FERME la chaîne du fer.** C17
``iron_bloomery`` a réduit le minerai en **loupe** spongieuse (``requires_forging`` True,
``is_solid_bloom`` True) en différant *« le martelage de consolidation reste émergent »*.
C19 la **réalise** (reco audit J+12 ``R-J12r3-2``) : marteler la loupe **à chaud** →
expulser la scorie de fayalite → **fer forgé** (wrought iron). Fire-based (D9 0 → 1 après
le non-feu C18 — alternance, pas treadmill : la forge à chaud est physiquement
obligatoire).

Règle d'émergence absolue : l'agent ne *sait* pas qu'« on martèle la loupe au rouge ». Il
obtient une éponge récalcitrante (C17), s'attend peut-être au bouton coulé du cuivre
(C13), et **découvre** qu'au rouge elle se compacte et qu'un liquide noir (la scorie) en
sort sous le marteau. Le geste (enclume, cadence, corroyage) reste émergent.

N'introduit AUCUN nouveau tell : COMPOSE C17 (la loupe, elle-même C12×C1), pas de
``_PROFILE``, ``PY_TO_RUST`` reste 15 (garde-fou D8 — 13ᵉ fois par composition). Hors glob
``*_outcrop.py``.

LE MENSONGE RENDU VISIBLE #10 (le fer du chapeau pyriteux se brise sous le marteau) : la
loupe d'**oxyde** se consolide **saine** ; la loupe **red-short** (pyrite — FeS aux joints
de grain, fondu sous la chaleur de forge) **se fissure** à chaud (*hot-shortness*) →
rendement de fer forgé effondré, santé plafonnée. Pendant, à l'étape suivante, du
``red_short`` de C17.

Le fer ne FOND toujours pas : ``melted`` toujours False — fer forgé, jamais fonte
(1538 °C hors d'atteinte). Conservation Fe : ``wrought + scale + crack == bloom_iron``.

Seed 0x42 : continent de prairie (le MÊME que C17/C18) produisant des loupes émergentes —
oxyde (hématite, fer sain) ET pyrite (sulfure, fer red-short). Aucune injection.

Checks
------
 1.  Le monde Genesis réel produit des sites de forge émergents (1:1 avec les loupes C17).
 2.  « Le monde ne ment jamais » : cue ⇒ loupe C17 (même minéral) ; cracked ⟺ red-short ;
     melted toujours False ; conservation Fe (wrought+scale+crack == bloom_iron).
 3.  Aperçu NON MUTANT : ``forge_preview`` rend le billon promis & ne touche pas la
     géologie (D10 gelé) ; ``consolidate_bloom`` transforme une loupe tenue (pas le monde).
 4.  Déterminisme même-seed : oracle bit-identique.
 5.  Physique : oxyde sain + pyrite red-short se fissure + trop froid → rien + plus de
     chaudes consolident plus + conservation Fe + jamais fondu.
 6.  Hiérarchie : ``best_forge_site_near`` préfère le plus de fer forgé ; ``require_sound``
     rejette la loupe red-short.
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

from engine.sim import Simulation, SimConfig                        # noqa: E402
from engine.world_genesis import GenesisParams                      # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim          # noqa: E402
from engine import geology as geo                                   # noqa: E402
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.iron_bloomery as ib                                   # noqa: E402
import engine.bloom_forging as bf                                   # noqa: E402

SEED = 0x42         # grassland continent — iron gossans (hematite oxide + pyrite sulfide)
GRID = 12
OUT = os.path.join(ROOT, "journals", "p151_bloom_forging.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}")


def _build():
    cfg = SimConfig(name="p151", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    bf.install_bloom_forging(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 80)
    print("P151 — bloom forging (6th transformation: hammer the spongy bloom → wrought iron; closes the iron chain)")
    print("=" * 80)

    sim, coords = _build()
    summary = bf.forge_summary(sim)
    print(f"  region: {len(coords)} chunks | forge_sites={summary['n_forge_sites']} "
          f"(sound={summary['n_sound_wrought']} cracked_red_short={summary['n_cracked_red_short']}) "
          f"| best_wrought={summary['best_wrought_iron_per_kg_ore']} best_soundness={summary['best_soundness']}")
    print(f"  ore classes: {summary['by_ore_class']} | minerals: {summary['by_mineral']}")

    # 1 — emergent forge sites, 1:1 with C17 bloom sites
    n_bloom = sum(1 for c in coords if ib.bloom_cue_for_chunk(sim, c) is not None)
    check("1 — Genesis world emits emergent forge sites (1:1 with the C17 blooms)",
          summary["n_forge_sites"] > 0
          and summary["best_wrought_iron_per_kg_ore"] > 0.0
          and summary["best_soundness"] >= bf.SOUND_THRESHOLD
          and summary["n_forge_sites"] == n_bloom,
          f"{summary['n_forge_sites']} forge sites == {n_bloom} bloom sites; "
          f"sound={summary['n_sound_wrought']} cracked={summary['n_cracked_red_short']}")

    # 2 — the world never lies
    violations = 0
    n_sound = n_cracked = 0
    for coord in coords:
        cue = bf.forge_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        bloom = ib.bloom_cue_for_chunk(sim, coord)
        if bloom is None or bloom.iron_mineral != cue.iron_mineral:
            violations += 1
        if cue.cracked != bool(bloom.red_short):
            violations += 1
        if cue.melted is not False:
            violations += 1
        total = (cue.wrought_iron_per_kg_ore + cue.scale_loss_per_kg_ore
                 + cue.crack_loss_per_kg_ore)
        if abs(total - cue.bloom_iron_per_kg_ore) > 1e-5:
            violations += 1
        if cue.is_wrought:
            n_sound += 1
        if cue.cracked:
            n_cracked += 1
    check("2 — le monde ne ment jamais (loupe C17 ; cracked⟺red-short ; melted False ; conservation Fe)",
          violations == 0,
          f"violations={violations} sound={n_sound} cracked={n_cracked}")

    # 3 — non-mutating preview / consolidate on a held bloom (geology untouched)
    coord = next((c for c in coords if bf.forge_cue_for_chunk(sim, c) is not None), None)
    prev_ok = nonmut_ok = consol_ok = False
    if coord is not None:
        cue = bf.forge_cue_for_chunk(sim, coord)
        sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
        g = geo.chunk_geology(sim, coord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        prev = bf.forge_preview(sim, float(sim.agents.pos[0, 0]),
                                float(sim.agents.pos[0, 1]))
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        nonmut_ok = (after == before)
        prev_ok = (prev["forgeable"] is True
                   and prev["wrought_iron_per_kg_ore"] == cue.wrought_iron_per_kg_ore
                   and prev["melted"] is False)
        # consolidate a held bloom (no geology touched — it's a product transform)
        held = ib.BloomResult(
            coord=coord, iron_mineral=cue.iron_mineral, ore_class=cue.ore_class,
            ore_consumed_kg=5.0, bloom_iron_kg=cue.bloom_iron_per_kg_ore * 5.0,
            slag_kg=0.0, bloom_purity=0.96, red_short=cue.red_short, roasted=False,
            required_roasting=False, is_solid_bloom=True, peak_c=cue.forge_temp_c)
        res = bf.consolidate_bloom(held)
        consol_ok = (res.melted is False
                     and abs((res.wrought_iron_kg + res.scale_loss_kg + res.crack_loss_kg)
                             - held.bloom_iron_kg) < 1e-6)
        print(f"        FORGE @ {coord}: {cue.iron_mineral} ({cue.ore_class}) → wrought "
              f"{cue.wrought_iron_per_kg_ore}/kg ore, soundness {cue.soundness}, "
              f"cracked={cue.cracked} — geology untouched={nonmut_ok}")
    check("3 — aperçu NON MUTANT : forge_preview & consolidate_bloom ne touchent pas la géologie (D10 gelé)",
          prev_ok and nonmut_ok and consol_ok,
          f"preview={prev_ok} non_mutating={nonmut_ok} consolidate={consol_ok}")

    # 4 — determinism
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = bf.forge_cue_for_chunk(sim2, coord)
        y = bf.forge_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.iron_mineral, round(x.wrought_iron_per_kg_ore, 6),
                                     x.is_wrought, x.cracked, round(x.soundness, 6))
        ky = None if y is None else (y.iron_mineral, round(y.wrought_iron_per_kg_ore, 6),
                                     y.is_wrought, y.cracked, round(y.soundness, 6))
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (oracle bit-identique)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physics
    oxide = bf.wrought_yield(10.0, 0.96, red_short=False, forge_temp_c=1300.0)
    redsh = bf.wrought_yield(10.0, 0.80, red_short=True, forge_temp_c=1300.0)
    cold = bf.wrought_yield(10.0, 0.96, red_short=False,
                            forge_temp_c=bf.SLAG_EXPULSION_TEMP_C - 1.0)
    one = bf.wrought_yield(10.0, 0.96, red_short=False, forge_temp_c=1300.0, n_heats=1)
    three = bf.wrought_yield(10.0, 0.96, red_short=False, forge_temp_c=1300.0, n_heats=3)
    cons_ok = all(abs((y.wrought_iron_kg + y.scale_loss_kg + y.crack_loss_kg) - 10.0) < 1e-9
                  for y in (oxide, redsh, three))
    physics_ok = (
        oxide.is_wrought and not oxide.cracked and oxide.melted is False
        and redsh.cracked and not redsh.is_wrought
        and redsh.wrought_iron_kg < oxide.wrought_iron_kg
        and redsh.soundness <= bf.RED_SHORT_SOUNDNESS_CEIL + 1e-9
        and cold.wrought_iron_kg == 0.0 and cold.hot_enough is False
        and three.soundness > one.soundness
        and three.slag_expelled_fraction > one.slag_expelled_fraction
        and cons_ok and bf.IRON_MELT_TEMP_C > 1400.0)
    print(f"        oxide→wrought {oxide.wrought_iron_kg:.3f}kg (sound {oxide.soundness:.3f}) | "
          f"pyrite→wrought {redsh.wrought_iron_kg:.3f}kg cracked (sound {redsh.soundness:.3f}) | "
          f"cold→{cold.wrought_iron_kg:.3f}kg | heats 1→3 sound {one.soundness:.3f}→{three.soundness:.3f}")
    check("5 — physique : oxyde sain + pyrite red-short fissure + trop froid rien + chaudes consolident + conservation + jamais fondu",
          physics_ok, f"oxide_sound={oxide.is_wrought} pyrite_cracked={redsh.cracked} conservation={cons_ok}")

    # 6 — best_forge_site_near prefers most wrought iron ; require_sound rejects red-short
    cn = next((c for c in coords2 if bf.forge_cue_for_chunk(sim2, c) is not None), None)
    pick_ok = False
    if cn is not None:
        sim2.agents.pos[0, 0] = (cn[0] + 0.5) * CHUNK_SIDE_M
        sim2.agents.pos[0, 1] = (cn[1] + 0.5) * CHUNK_SIDE_M
        best = bf.best_forge_site_near(sim2, 0, perception_radius_m=6 * CHUNK_SIDE_M)
        sound = bf.best_forge_site_near(sim2, 0, perception_radius_m=6 * CHUNK_SIDE_M,
                                        require_sound=True)
        pick_ok = (best is not None and best.wrought_iron_per_kg_ore > 0.0
                   and (sound is None or (sound.is_wrought and not sound.cracked)))
    check("6 — best_forge_site préfère le plus de fer forgé ; require_sound rejette la loupe red-short",
          pick_ok, f"best_pick={pick_ok}")

    # 7 — zero tick cost / idempotent install (the oracle)
    c1 = bf.install_bloom_forging(sim)
    c2 = bf.install_bloom_forging(sim)
    check("7 — installation idempotente, coût tick nul (oracle)",
          c1 is c2, "no per-tick hook on sim.step")

    # 8 — D8 by composition: no _PROFILE, PY_TO_RUST stays 15, out of *_outcrop glob
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract       # noqa: E402
    d8_ok = (not hasattr(bf, "_PROFILE") and bf.ib is ib
             and not os.path.basename(bf.__file__).endswith("_outcrop.py")
             and len(contract.PY_TO_RUST) == 15)
    check("8 — D8 par composition : pas de _PROFILE ; PY_TO_RUST==15 ; hors *_outcrop",
          d8_ok, f"py_to_rust={len(contract.PY_TO_RUST)}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p151_bloom_forging", "seed": SEED,
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
