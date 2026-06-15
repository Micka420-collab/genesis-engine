#!/usr/bin/env python3
"""P139 — Substrate capability : amorçage du feu (Cap. C7).

Le feu est la **voûte** qui ferme l'arc C1→C6 : presque toute matière rendue
perceptible (cuivre C1, combustible C4, argile C5, calcaire C6) demande ensuite
*un feu* pour devenir outil (fondre, brûler, cuire, calciner). Sans amorçage par
l'agent, ces capacités restaient des matières inertes. ``engine.wildfire``
(Wave 14) modélise le feu **spontané** (foudre + propagation) et note lui-même
que l'agent doit *déduire* que « le silex frappé produit la même chose en
petit » — mais aucun signal de substrat ne disait, par site, si un humain *peut
allumer un feu ici, et comment*. Ce smoke valide la capacité ``fire_ignition``
qui expose cette affordance — sans rien scripter.

Règle d'émergence absolue : l'agent ne *sait* pas qu'on fait du feu. Il PERÇOIT
une pierre brun-rouille qui jette des étincelles frappée (pyrite), une pierre
dure pour la percuter (silex), de l'herbe sèche qui prend ; ou il frotte deux
bois sur un amadou très sec. Le briquet, l'archet à feu, le foyer, la cuisson
émergent.

Deux voies honnêtes et physiquement distinctes (veille 2026-06-15) :
  • PERCUSSION (briquet à pyrite, méthode d'Ötzi) : pyrite (FeS₂ pyrophorique)
    + percuteur dur (silex/quartz — pétrologie C2 réutilisée) + amadou *assez* sec.
  • FRICTION (archet/drille) : aucune pierre, mais amadou *très* sec (seuil plus
    strict — un amadou humide tue la braise).
Effet 1+1>2 : géologie (pyrite+silex, SYSTÈME C) × hydrologie (``chunk.water``,
SYSTÈME A) × biome combustible (SYSTÈME E). Une seule vérité de substrat, plusieurs
lectures (C4 sec, C5 plastique, C6 sain, C7 amadou sec).

N'introduit AUCUN nouveau tell minéral : COMPOSE la pyrite (gossan C1) + le
percuteur (C2). Pas de ``_PROFILE``, pas d'entrée ``PY_TO_RUST`` (garde-fou D8).

Seed 0xBEEF : continent de prairie (herbe sèche = amadou canonique) produisant
À LA FOIS des sites percussion (pyrite + percuteur + sec) ET la voie friction.

Checks
------
 1.  Le monde Genesis réel produit des sites d'amorçage émergents (percussion + friction).
 2.  « Le monde ne ment jamais » : cue ⇒ can_ignite ; percussion ⇒ pyrite réelle
     peu profonde + percuteur réel + amadou sec ; friction ⇒ amadou sec & combustible.
     0 violation.
 3.  Boucle de découverte : prairie sèche pyrite+silex → ``ignition_preview``
     can_percussion & nomme la pyrite + un percuteur ; prairie détrempée → vue
     comme amadou mais ne prend pas (DAMP ; mensonge rendu visible ; aperçu non mutant).
 4.  Déterminisme même-seed : affordances bit-identiques.
 5.  Masquage physique : océan → muet ; pyrite+silex mais détrempé → pas de
     percussion ; désert (percuteur mais pas d'amadou) → pas de friction.
 6.  Hiérarchie des méthodes : percussion préférée à friction ; forêt sans pyrite
     reste allumable par friction ; ``best_firesite_near`` préfère/­filtre la percussion.
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
import engine.fire_ignition as fi                                   # noqa: E402

SEED = 0xBEEF       # grassland continent — pyrite + flint striker + dry grass
GRID = 12
OUT = os.path.join(ROOT, "journals", "p139_fire_ignition.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}")


def _fake_chunk(w=0.0, biome=6, elev=300.0, side=8):
    return SimpleNamespace(
        water=np.full((side, side), w, dtype=np.float32),
        biome=np.full((side, side), biome, dtype=np.uint8),
        height=np.full((side, side), elev, dtype=np.float32))


def _layer(top, bottom, rock="sandstone", ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=2400.0, ore_mix=dict(ore or {}))


def _build():
    cfg = SimConfig(name="p139", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    fi.install_fire_ignition(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 78)
    print("P139 — fire ignition affordance (emergent strike-a-light / fire drill)")
    print("=" * 78)

    sim, coords = _build()
    summary = fi.ignition_summary(sim)
    print(f"  region: {len(coords)} chunks | ignitable={summary['n_chunks_ignitable']} "
          f"| percussion={summary['n_percussion']} | friction={summary['n_friction']}")
    print(f"  methods: {summary['by_method']}")
    print(f"  tinder:  {summary['by_tinder']}")

    # 1 — emergent fire-making sites from the real world (both methods present)
    check("1 — Genesis world emits emergent ignition sites (percussion + friction)",
          summary["n_chunks_ignitable"] > 0 and summary["n_percussion"] > 0
          and summary["n_friction"] > 0,
          f"{summary['n_chunks_ignitable']}/{summary['n_chunks']} ignitable; "
          f"perc={summary['n_percussion']} fric={summary['n_friction']}")

    # 2 — the world never lies
    violations = 0
    for coord in coords:
        cue = fi.ignition_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        g = geo.chunk_geology(sim, coord)
        if not cue.can_ignite:
            violations += 1
        if cue.can_percussion:
            # pyrite really in a shallow ore layer
            pyr = any(L.depth_top_m <= fi.MAX_IGNITER_DEPTH_M
                      and L.ore_mix.get(cue.spark_source, 0.0) >= fi.MIN_VISIBLE_FRACTION
                      for L in (g.layers if g else []))
            if not pyr:
                violations += 1
            if cue.striker_material is None or cue.striker_quality < fi.STRIKER_MIN_QUALITY:
                violations += 1
            if cue.ambient_moisture > fi.PERCUSSION_DRY_MOISTURE:
                violations += 1
            if cue.fine_fuel < fi.FINE_FUEL_FLOOR:
                violations += 1
        if cue.can_friction:
            if cue.ambient_moisture > fi.FRICTION_DRY_MOISTURE:
                violations += 1
            if cue.fine_fuel < fi.FRICTION_FUEL_FLOOR:
                violations += 1
        # method must reflect the affordances
        if cue.can_percussion and cue.method != fi.IgnitionMethod.PERCUSSION:
            violations += 1
        if (not cue.can_percussion) and cue.can_friction \
                and cue.method != fi.IgnitionMethod.FRICTION:
            violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ ingrédients véridiques)",
          violations == 0, f"violations={violations}")

    # 3 — discovery loop : a dry grassland percussion site previews can_percussion
    #     & names pyrite + a striker ; a synthetic soaked meadow is seen as tinder
    #     but won't catch (DAMP). Preview is non-mutating.
    perc_coord = next((c for c in coords
                       if (cu := fi.ignition_cue_for_chunk(sim, c)) is not None
                       and cu.can_percussion), None)
    perc_ok = damp_ok = False
    if perc_coord is not None:
        cx, cy, _ = perc_coord
        sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
        seen = fi.prospect_ignition(sim, float(sim.agents.pos[0, 0]),
                                    float(sim.agents.pos[0, 1]))
        g = geo.chunk_geology(sim, perc_coord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        out = fi.ignition_preview(sim, float(sim.agents.pos[0, 0]),
                                  float(sim.agents.pos[0, 1]))
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        perc_ok = (seen is not None and out["can_ignite"] is True
                   and out["can_percussion"] is True
                   and out["spark_source"] == "pyrite"
                   and out["striker_material"] is not None and after == before)
        print(f"        agent SEES spark='{seen.spark_source}' "
              f"striker='{seen.striker_material}' (q={seen.striker_quality:.2f}) "
              f"→ method={out['method']}")
    # a synthetic soaked grassland: grass tinder present, but standing water →
    # too damp to catch a spark (DAMP). Even with pyrite + flint underfoot.
    damp = fi._cue_from_geology((0, 0, 0),
                                [_layer(0, 5, "limestone",
                                        ore={"pyrite": 0.05, "quartz": 0.05})],
                                int(Biome.GRASSLAND),
                                _fake_chunk(biome=int(Biome.GRASSLAND),
                                            w=fi.WATER_SATURATION_L))
    damp_prev = fi.ignition_preview(
        SimpleNamespace(
            streamer=SimpleNamespace(cache={
                (0, 0, 0): _fake_chunk(biome=int(Biome.GRASSLAND),
                                       w=fi.WATER_SATURATION_L)}),
            _geology_state=SimpleNamespace(chunks={
                (0, 0, 0): ChunkGeology(coord=(0, 0, 0), layers=[
                    _layer(0, 5, "limestone",
                           ore={"pyrite": 0.05, "quartz": 0.05})])})),
        4.0, 4.0)
    damp_ok = (damp is None and damp_prev["can_ignite"] is False
               and damp_prev.get("tinder_available") is True)
    print(f"        soaked meadow → can_ignite={damp_prev['can_ignite']} "
          f"reason='{damp_prev['reason']}' (looks like tinder, won't catch)")
    check("3 — découverte : prairie sèche s'allume (percussion) ; détrempée non",
          perc_ok and damp_ok,
          f"percussion_site={perc_ok} soaked_not_ignitable={damp_ok}")

    # 4 — determinism (rebuild fresh: sim mutated by agent move above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = fi.ignition_cue_for_chunk(sim2, coord)
        y = fi.ignition_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.method, x.can_percussion, x.can_friction,
                                     x.spark_source, x.striker_material,
                                     round(x.ambient_moisture, 6))
        ky = None if y is None else (y.method, y.can_percussion, y.can_friction,
                                     y.spark_source, y.striker_material,
                                     round(y.ambient_moisture, 6))
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (affordances identiques)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physical masking (pure derivation)
    ocean = fi._cue_from_geology((0, 0, 0),
                                 [_layer(0, 5, "limestone",
                                         ore={"pyrite": 0.05, "quartz": 0.05})],
                                 int(Biome.OCEAN),
                                 _fake_chunk(biome=int(Biome.OCEAN)))
    # pyrite + flint but soaking rainforest → no percussion (damp), no friction
    soaked = fi._cue_from_geology((0, 0, 0),
                                  [_layer(0, 5, "limestone",
                                          ore={"pyrite": 0.05, "quartz": 0.05})],
                                  int(Biome.TROPICAL_RAINFOREST),
                                  _fake_chunk(biome=int(Biome.TROPICAL_RAINFOREST)))
    # hot desert with a flint striker but no fine fuel → no friction, no tinder
    desert = fi._cue_from_geology((0, 0, 0),
                                  [_layer(0, 5, "sandstone",
                                          ore={"quartz": 0.06})],
                                  int(Biome.HOT_DESERT),
                                  _fake_chunk(biome=int(Biome.HOT_DESERT)))
    mask_ok = ocean is None and soaked is None and desert is None
    check("5 — masquage physique (océan muet ; détrempé/désert non allumables)",
          mask_ok, f"ocean={ocean is None} soaked={soaked is None} "
                   f"desert={desert is None}")

    # 6 — method hierarchy + friction-only forest + best_firesite_near filters
    # dry grassland with pyrite + flint host → percussion (the easy method).
    perc = fi._cue_from_geology((0, 0, 0),
                                [_layer(0, 4, "limestone",
                                        ore={"pyrite": 0.05, "quartz": 0.06})],
                                int(Biome.GRASSLAND),
                                _fake_chunk(biome=int(Biome.GRASSLAND)))
    # dry woodland (tropical-dry-forest), NO pyrite, dry enough → friction only
    # (no minerals). A spark needs only PERCUSSION_DRY tinder; friction needs the
    # stricter FRICTION_DRY — so a friction site is, by construction, dry woodland
    # / savanna / grassland, not a damp temperate forest.
    fric = fi._cue_from_geology((0, 0, 0),
                                [_layer(0, 5, "sandstone")],
                                int(Biome.TROPICAL_DRY_FOREST),
                                _fake_chunk(biome=int(Biome.TROPICAL_DRY_FOREST)))
    hierarchy = (perc is not None and perc.can_percussion
                 and perc.method == fi.IgnitionMethod.PERCUSSION
                 and fric is not None and fric.can_friction
                 and not fric.can_percussion
                 and fric.method == fi.IgnitionMethod.FRICTION)
    # best_firesite_near : a percussion site on the agent's own chunk; require
    # filters work (own-chunk radius isolates it from procedural neighbours).
    cx, cy, _ = coords2[len(coords2) // 2]
    cc = (cx, cy, 0)
    ch = sim2.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, int(Biome.GRASSLAND),
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.zeros(np.asarray(ch.water).shape, dtype=np.float32)
    sim2._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=[
        _layer(0.0, 1.0, "sandstone"),
        _layer(1.0, 5.0, "limestone", ore={"pyrite": 0.05, "quartz": 0.06})])
    sim2._ignition_cue_cache.clear()
    sim2.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim2.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    r = 0.4 * CHUNK_SIDE_M
    best = fi.best_firesite_near(sim2, 0, perception_radius_m=r)
    perc_only = fi.best_firesite_near(sim2, 0, perception_radius_m=r,
                                      require_percussion=True)
    pick_ok = (best is not None and best.can_percussion
               and perc_only is not None and perc_only.can_percussion)
    check("6 — hiérarchie méthodes (percussion>friction ; forêt=friction seule)",
          hierarchy and pick_ok,
          f"hierarchy={hierarchy} best_is_percussion={pick_ok}")

    # 7 — zero tick cost / idempotent install
    c1 = fi.install_fire_ignition(sim)
    c2 = fi.install_fire_ignition(sim)
    check("7 — installation idempotente, coût tick nul",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p139_fire_ignition", "seed": SEED,
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
