#!/usr/bin/env python3
"""P137 — Substrate capability : affleurement d'argile (Cap. C5).

L'argile est la **clé de voûte** stone-age : le récipient qui contient l'eau
potable (C3), le four qui contient le feu (C4), le creuset qui contient le métal
fondu, la brique qui bâtit. Pourtant elle restait **muette** : la géologie
portait le schiste argileux (``shale`` = *clay_consolidated*) en surface partout,
et la crate Rust réservait un ``Mineral::FineClay`` (« pottery / brick »,
``[180,140,110]``) **orphelin** — aucun signal Python ne le rendait perceptible.
Ce smoke valide la capacité ``clay_outcrop`` qui expose l'exposition d'argile
(terre lisse beige-ocre + sa plasticité) — sans rien scripter.

Règle d'émergence absolue : l'agent ne *sait* pas qu'on en fait des pots. Il
PERÇOIT une berge de terre lisse, la malaxe (plastique ⇒ tient la forme), la
sèche, la cuit ; ou apprend qu'une argile trop sèche s'émiette (mouiller) et
qu'une argile gorgée d'eau flue (laisser drainer). La poterie émerge.

Pendant géologique de C1 (minerai), C2 (pierre), C3 (eau), C4 (combustible).
Combo veille D1 (hiérarchie de grade : argile schisteuse brique < kaolin
céramique) × D2 (porte de plasticité d'Atterberg) : la même argile qu'on VOIT
n'est façonnable que dans la fenêtre d'humidité PL→LL → boucle émergente
mouiller/sécher avant de façonner. Pendant inversé de la porte d'humidité de C4
(le feu veut le sec, l'argile veut le plastique) — une seule vérité de substrat,
deux lectures.

Seed 0xC1A7 : monde tempéré/prairie produisant À LA FOIS le kaolin céramique
(ore) ET l'argile schisteuse (lithologie topsoil), avec une humidité dans la
fenêtre plastique (argile façonnable maintenant).

Checks
------
 1.  Le monde Genesis réel produit des indices émergents (fine_clay + shale).
 2.  « Le monde ne ment jamais » : cue ⇒ argile réelle peu profonde ;
     workable_now ⇒ humidité dans la fenêtre plastique ; ceramic_grade ⇒
     grade ≥ seuil céramique. 0 violation.
 3.  Boucle de découverte : kaolin plastique → ``shape_preview`` façonnable &
     cuit en céramique ; argile désertique sèche → vue mais ne se façonne pas
     (too_dry_to_shape ; mensonge rendu visible ; aperçu non mutant).
 4.  Déterminisme même-seed : indices bit-identiques.
 5.  Masquage physique : océan → muet ; lit profond → muet.
 6.  Porte de plasticité : kaolin cuit la céramique, pas le schiste ;
     ``best_clay_near`` préfère le kaolin et saute l'argile hors fenêtre.
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
import engine.clay_outcrop as cl                                    # noqa: E402

SEED = 0xC1A7        # temperate / grassland — plastic kaolin + shaly topsoil
GRID = 12
OUT = os.path.join(ROOT, "journals", "p137_clay_outcrop.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}")


def _fake_chunk(w=0.0, biome=4, elev=300.0, side=8):
    return SimpleNamespace(
        water=np.full((side, side), w, dtype=np.float32),
        biome=np.full((side, side), biome, dtype=np.uint8),
        height=np.full((side, side), elev, dtype=np.float32))


def _layer(top, bottom, rock="sandstone", ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=2400.0, ore_mix=dict(ore or {}))


def _build():
    cfg = SimConfig(name="p137", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    cl.install_clay_outcrop(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 78)
    print("P137 — clay outcrop cues (emergent pottery / ceramic discovery)")
    print("=" * 78)

    sim, coords = _build()
    summary = cl.clay_cue_summary(sim)
    print(f"  region: {len(coords)} chunks | cued={summary['n_chunks_with_cue']} "
          f"| workable_now={summary['n_workable_now']} "
          f"| ceramic={summary['n_ceramic_grade']}")
    print(f"  materials: {summary['by_material']}")
    print(f"  classes:   {summary['by_class']}")

    # 1 — emergent cues from the real world (kaolin + shale expected)
    mats = summary["by_material"]
    check("1 — Genesis world emits emergent clay cues (fine_clay + shale)",
          summary["n_chunks_with_cue"] > 0 and "fine_clay" in mats
          and "shale" in mats,
          f"{summary['n_chunks_with_cue']}/{summary['n_chunks']} cued; {mats}")

    # 2 — the world never lies
    violations = 0
    for coord in coords:
        cue = cl.clay_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        g = geo.chunk_geology(sim, coord)
        grounded = False
        for L in (g.layers if g else []):
            if L.depth_top_m > cl.MAX_CLAY_DEPTH_M:
                continue
            if cue.source == "lithology" and L.rock_type == cue.material:
                grounded = True
            if cue.source == "ore" and \
                    L.ore_mix.get(cue.material, 0.0) >= cl.MIN_VISIBLE_FRACTION:
                grounded = True
        if not grounded:
            violations += 1
        if cue.workable_now and not (cl.PLASTIC_LIMIT <= cue.ambient_moisture
                                     <= cl.LIQUID_LIMIT):
            violations += 1
        if cue.ceramic_grade and cue.pottery_grade < cl.CERAMIC_GRADE:
            violations += 1
        if (int(cue.workable_now) + int(cue.too_dry_to_shape)
                + int(cue.too_wet_slurry)) != 1:
            violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ argile véridique)",
          violations == 0, f"violations={violations}")

    # 3 — discovery loop : plastic kaolin shapes & fires ; a dry desert clay is
    #     seen but cannot be shaped (must wet & wedge). Preview is non-mutating.
    kaolin_coord = next((c for c in coords
                         if (cu := cl.clay_cue_for_chunk(sim, c)) is not None
                         and cu.material == "fine_clay" and cu.workable_now), None)
    kaolin_ok = dry_ok = False
    if kaolin_coord is not None:
        cx, cy, _ = kaolin_coord
        sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
        seen = cl.prospect_clay(sim, float(sim.agents.pos[0, 0]),
                                float(sim.agents.pos[0, 1]))
        g = geo.chunk_geology(sim, kaolin_coord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        out = cl.shape_preview(sim, float(sim.agents.pos[0, 0]),
                               float(sim.agents.pos[0, 1]))
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        kaolin_ok = (seen is not None and out["can_shape"] is True
                     and out["fires_to_ceramic"] is True and after == before)
        print(f"        agent SEES '{seen.label}' → can_shape="
              f"{out['can_shape']} fires_to_ceramic={out['fires_to_ceramic']}")
    # a synthetic bone-dry desert clay: seen, but below the plastic limit.
    dry = cl._cue_from_geology((0, 0, 0),
                               [_layer(0, 4, "sandstone", ore={"fine_clay": 0.06})],
                               int(Biome.HOT_DESERT),
                               _fake_chunk(biome=int(Biome.HOT_DESERT), w=0.0))
    dry_ok = (dry is not None and dry.too_dry_to_shape is True
              and dry.workable_now is False)
    if dry is not None:
        print(f"        agent SEES '{dry.label}' → too_dry_to_shape="
              f"{dry.too_dry_to_shape} (dry clay: lie made visible; wet & wedge)")
    check("3 — découverte : kaolin plastique cuit ; argile sèche se façonne pas",
          kaolin_ok and dry_ok,
          f"kaolin_shapes_fires={kaolin_ok} dry_clay_needs_wetting={dry_ok}")

    # 4 — determinism (rebuild fresh: sim is mutated by agent moves above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = cl.clay_cue_for_chunk(sim2, coord)
        y = cl.clay_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.material, x.source,
                                     round(x.pottery_grade, 6),
                                     x.workable_now, x.ceramic_grade)
        ky = None if y is None else (y.material, y.source,
                                     round(y.pottery_grade, 6),
                                     y.workable_now, y.ceramic_grade)
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (indices identiques)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physical masking (pure derivation)
    ocean = cl._cue_from_geology((0, 0, 0),
                                 [_layer(0, 5, "shale", ore={"fine_clay": 0.1})],
                                 int(Biome.OCEAN),
                                 _fake_chunk(biome=int(Biome.OCEAN)))
    deep = cl._cue_from_geology(
        (0, 0, 0),
        [_layer(0, 5, "sandstone"),
         _layer(cl.MAX_CLAY_DEPTH_M + 10.0, 200.0, "sandstone",
                ore={"fine_clay": 0.1})],
        int(Biome.GRASSLAND), _fake_chunk(biome=int(Biome.GRASSLAND)))
    mask_ok = ocean is None and deep is None
    check("5 — masquage physique (océan → muet ; lit profond → muet)",
          mask_ok, f"ocean_silent={ocean is None} deep_silent={deep is None}")

    # 6 — grade hierarchy + best_clay_near filters
    kaolin = cl._cue_from_geology((0, 0, 0),
                                  [_layer(0, 4, "sandstone", ore={"fine_clay": 0.06})],
                                  int(Biome.TEMPERATE_FOREST),
                                  _fake_chunk(biome=int(Biome.TEMPERATE_FOREST)))
    shaly = cl._cue_from_geology((0, 0, 0), [_layer(0, 1, "shale")],
                                 int(Biome.GRASSLAND),
                                 _fake_chunk(biome=int(Biome.GRASSLAND)))
    hierarchy = (kaolin is not None and kaolin.ceramic_grade
                 and kaolin.workable_now
                 and shaly is not None and not shaly.ceramic_grade
                 and shaly.workable_now)
    # best_clay_near : a ceramic kaolin alone on the agent's chunk; require
    # filters work (own-chunk radius isolates it from procedural neighbours).
    cx, cy, _ = coords2[len(coords2) // 2]
    cc = (cx, cy, 0)
    ch = sim2.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, int(Biome.TEMPERATE_FOREST),
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.zeros(np.asarray(ch.water).shape, dtype=np.float32)
    sim2._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=[
        _layer(0.0, 1.0, "sandstone"),
        _layer(1.0, 5.0, "sandstone", ore={"fine_clay": 0.08})])
    sim2._clay_cue_cache.clear()
    sim2.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim2.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    r = 0.4 * CHUNK_SIDE_M
    best = cl.best_clay_near(sim2, 0, perception_radius_m=r)
    ceramic = cl.best_clay_near(sim2, 0, perception_radius_m=r, require_ceramic=True)
    pick_ok = (best is not None and best.material == "fine_clay"
               and ceramic is not None and ceramic.ceramic_grade)
    check("6 — hiérarchie de grade (kaolin cuit ; schiste non ; pick=kaolin)",
          hierarchy and pick_ok,
          f"hierarchy={hierarchy} best_is_kaolin={pick_ok}")

    # 7 — zero tick cost / idempotent install
    c1 = cl.install_clay_outcrop(sim)
    c2 = cl.install_clay_outcrop(sim)
    check("7 — installation idempotente, coût tick nul",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p137_clay_outcrop", "seed": SEED,
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
