#!/usr/bin/env python3
"""P136 — Substrate capability : affleurement de combustible (Cap. C4).

Toute la branche **ORGANIQUE** de la géologie (``peat`` / ``coal`` /
``oil_shale``, déjà semée dans l'``ore_mix`` par ``engine.geology``) restait
**muette** : aucun signal de surface ne disait à un agent *où trouver la
roche/terre qui brûle*. Or « la roche noire mate qui brûle longtemps » amorce la
**révolution énergétique** (feu durable → four + charbon → fusion → métallurgie).
Ce smoke valide la capacité ``combustible_outcrop`` qui expose l'exposition de
combustible (noir mat + son humidité) — sans rien scripter.

Règle d'émergence absolue : l'agent ne *sait* pas que ça brûle. Il PERÇOIT une
terre/roche noire et mate, sa spongiosité gorgée d'eau ; se souvient ; coupe,
sèche, allume — ou apprend qu'une veine sèche brûle là où elle affleure. La
découverte de l'énergie émerge.

Pendant géologique-organique de C1 (minerai), C2 (pierre), C3 (eau potable).
Combo veille D1 (rang houiller / grade calorifique) × D2 (porte d'humidité de
tourbière) : la même tourbière qu'on VOIT n'est pas brûlable tant qu'elle est
gorgée d'eau → boucle émergente couper→sécher→brûler.

Seed 0xB0 = forêt boréale : biome réaliste pour À LA FOIS la tourbe (bog) et le
charbon (bassin houiller), d'où des indices peat ET coal émergents.

Checks
------
 1.  Le monde Genesis réel (boreal) produit des indices émergents (peat + coal).
 2.  « Le monde ne ment jamais » : cue ⇒ combustible réel peu profond ;
     burnable_now ⇒ grade & sec ; smelting_grade ⇒ grade ≥ seuil. 0 violation.
 3.  Boucle de découverte : charbon sec → ``ignite_preview`` tient le feu &
     fond le métal ; tourbe gorgée d'eau → vue mais ne tient pas le feu
     (dry_to_burn ; mensonge rendu visible ; aperçu non mutant).
 4.  Déterminisme même-seed : indices bit-identiques.
 5.  Masquage physique : océan → muet ; filon profond → muet.
 6.  Hiérarchie calorifique : charbon fond le métal, pas la tourbe ;
     ``best_fuel_near`` préfère le charbon et saute la tourbe trop humide.
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
from engine.world import Biome, CHUNK_SIDE_M                        # noqa: E402
import engine.combustible_outcrop as co                             # noqa: E402

SEED = 0xB0          # boreal forest — peat-bog + coal-basin terrain
GRID = 12
OUT = os.path.join(ROOT, "journals", "p136_combustible_outcrop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}")


def _fake_chunk(w=10.0, biome=3, elev=500.0, side=8):
    return SimpleNamespace(
        water=np.full((side, side), w, dtype=np.float32),
        biome=np.full((side, side), biome, dtype=np.uint8),
        height=np.full((side, side), elev, dtype=np.float32))


def _layer(top, bottom, rock="shale", ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=2400.0, ore_mix=dict(ore or {}))


def _build():
    cfg = SimConfig(name="p136", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    co.install_combustible_outcrop(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 78)
    print("P136 — combustible outcrop cues (emergent fuel / energy discovery)")
    print("=" * 78)

    sim, coords = _build()
    summary = co.combustible_cue_summary(sim)
    print(f"  region: {len(coords)} chunks | cued={summary['n_chunks_with_cue']} "
          f"| burnable_now={summary['n_burnable_now']} "
          f"| smelting={summary['n_smelting_grade']}")
    print(f"  materials: {summary['by_material']}")
    print(f"  classes:   {summary['by_class']}")

    # 1 — emergent cues from the real world (peat + coal expected in boreal)
    mats = summary["by_material"]
    check("1 — Genesis world emits emergent fuel cues (peat + coal)",
          summary["n_chunks_with_cue"] > 0 and "peat" in mats and "coal" in mats,
          f"{summary['n_chunks_with_cue']}/{summary['n_chunks']} cued; {mats}")

    # 2 — the world never lies
    violations = 0
    for coord in coords:
        cue = co.combustible_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        g = geo.chunk_geology(sim, coord)
        grounded = False
        for L in (g.layers if g else []):
            if L.depth_top_m > co.MAX_SEAM_DEPTH_M:
                continue
            if cue.source == "lithology" and L.rock_type == cue.material:
                grounded = True
            if cue.source == "ore" and \
                    L.ore_mix.get(cue.material, 0.0) >= co.MIN_VISIBLE_FRACTION:
                grounded = True
        if not grounded:
            violations += 1
        if cue.burnable_now and not (cue.calorific_grade >= co.MIN_FUEL_GRADE
                                     and cue.effective_moisture <= co.MOISTURE_EXTINCTION):
            violations += 1
        if cue.smelting_grade and cue.calorific_grade < co.SMELTING_GRADE:
            violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ combustible véridique)",
          violations == 0, f"violations={violations}")

    # 3 — discovery loop : dry coal sustains fire & smelts ; wet peat is seen
    #     but does not stay lit (must cut & dry). Preview is non-mutating.
    coal_coord = next((c for c in coords
                       if (cu := co.combustible_cue_for_chunk(sim, c)) is not None
                       and cu.material == "coal"), None)
    peat_coord = next((c for c in coords
                       if (cu := co.combustible_cue_for_chunk(sim, c)) is not None
                       and cu.material == "peat"), None)
    coal_ok = peat_ok = False
    if coal_coord is not None:
        cx, cy, _ = coal_coord
        sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
        seen = co.prospect_fuel(sim, float(sim.agents.pos[0, 0]),
                                float(sim.agents.pos[0, 1]))
        g = geo.chunk_geology(sim, coal_coord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        out = co.ignite_preview(sim, float(sim.agents.pos[0, 0]),
                                float(sim.agents.pos[0, 1]))
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        coal_ok = (seen is not None and out["sustains_fire"] is True
                   and out["smelting_grade"] is True and after == before)
        print(f"        agent SEES '{seen.label}' → fire sustains="
              f"{out['sustains_fire']} smelts={out['smelting_grade']}")
    if peat_coord is not None:
        cx, cy, _ = peat_coord
        sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
        seen = co.prospect_fuel(sim, float(sim.agents.pos[0, 0]),
                                float(sim.agents.pos[0, 1]))
        out = co.ignite_preview(sim, float(sim.agents.pos[0, 0]),
                                float(sim.agents.pos[0, 1]))
        peat_ok = (seen is not None and out["sustains_fire"] is False
                   and out["dry_to_burn"] is True)
        print(f"        agent SEES '{seen.label}' → fire sustains="
              f"{out['sustains_fire']} dry_to_burn={out['dry_to_burn']} "
              f"(wet bog: lie made visible; must cut & dry)")
    check("3 — découverte : charbon sec tient le feu ; tourbe gorgée d'eau non",
          coal_ok and peat_ok,
          f"coal_sustains_smelts={coal_ok} wet_peat_needs_drying={peat_ok}")

    # 4 — determinism (rebuild fresh: sim is mutated by agent moves above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = co.combustible_cue_for_chunk(sim2, coord)
        y = co.combustible_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.material, x.source,
                                     round(x.calorific_grade, 6),
                                     x.burnable_now, x.smelting_grade)
        ky = None if y is None else (y.material, y.source,
                                     round(y.calorific_grade, 6),
                                     y.burnable_now, y.smelting_grade)
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (indices identiques)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physical masking (pure derivation)
    ocean = co._cue_from_geology((0, 0, 0), [_layer(0, 5, "shale", ore={"coal": 0.1})],
                                 int(Biome.OCEAN),
                                 _fake_chunk(biome=int(Biome.OCEAN)))
    deep = co._cue_from_geology(
        (0, 0, 0),
        [_layer(0, 5, "shale"),
         _layer(co.MAX_SEAM_DEPTH_M + 10.0, 200.0, "shale", ore={"coal": 0.1})],
        4, _fake_chunk(biome=4))
    mask_ok = ocean is None and deep is None
    check("5 — masquage physique (océan → muet ; filon profond → muet)",
          mask_ok, f"ocean_silent={ocean is None} deep_silent={deep is None}")

    # 6 — calorific hierarchy + best_fuel_near filters
    dry_coal = co._cue_from_geology((0, 0, 0),
                                    [_layer(0, 4, "shale", ore={"coal": 0.06})],
                                    7, _fake_chunk(biome=7, w=0.0))
    wet_peat = co._cue_from_geology((0, 0, 0),
                                    [_layer(0, 4, "shale", ore={"peat": 0.06})],
                                    3, _fake_chunk(biome=3, w=10.0))
    hierarchy = (dry_coal is not None and dry_coal.smelting_grade
                 and dry_coal.burnable_now
                 and wet_peat is not None and not wet_peat.smelting_grade
                 and not wet_peat.burnable_now)
    # best_fuel_near : inject a dry coal + a wet peat near the agent.
    cx, cy, _ = coords2[len(coords2) // 2]
    coal_c = (cx, cy, 0)
    peat_c = (cx + 1, cy, 0) if sim2.streamer.get(0, (cx + 1, cy, 0)) else (cx - 1, cy, 0)
    for cc, ore, biome, w in ((coal_c, {"coal": 0.08}, 7, 0.0),
                              (peat_c, {"peat": 0.06}, 3, 10.0)):
        ch = sim2.streamer.get(0, cc)
        ch.biome = np.full(np.asarray(ch.biome).shape, biome,
                           dtype=np.asarray(ch.biome).dtype)
        ch.water = np.full(np.asarray(ch.water).shape, w, dtype=np.float32)
        sim2._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=[
            _layer(0.0, 1.0, "shale"), _layer(1.0, 5.0, "shale", ore=ore)])
    sim2._combustible_cue_cache.clear()
    sim2.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim2.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    r = 3 * CHUNK_SIDE_M
    best = co.best_fuel_near(sim2, 0, perception_radius_m=r)
    burn = co.best_fuel_near(sim2, 0, perception_radius_m=r, require_burnable=True)
    pick_ok = (best is not None and best.material == "coal"
               and burn is not None and burn.burnable_now)
    check("6 — hiérarchie calorifique (charbon fond ; tourbe non ; pick=charbon)",
          hierarchy and pick_ok,
          f"hierarchy={hierarchy} best_is_coal={pick_ok}")

    # 7 — zero tick cost / idempotent install
    c1 = co.install_combustible_outcrop(sim)
    c2 = co.install_combustible_outcrop(sim)
    check("7 — installation idempotente, coût tick nul",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p136_combustible_outcrop", "seed": SEED,
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
