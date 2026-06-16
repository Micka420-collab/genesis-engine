#!/usr/bin/env python3
"""P141 — Substrate capability : cuisson de la céramique (Cap. C9).

**Deuxième capacité de TRANSFORMATION** (après C8 ``lithic_tempering``). C1→C7
ont rendu *perceptibles* / *amorçables* les matières et le feu de l'âge de pierre ;
C8 a trempé une pierre. C9 est la transformation néolithique fondatrice : cuire
une **argile** (C5) dans un **feu** (C7) crée la **céramique** — le récipient qui
*contient* l'eau (C3), le grain, le métal, et rend le stockage (donc le surplus)
possible.

Règle d'émergence absolue : l'agent ne *sait* pas qu'« on cuit l'argile ». Il
malaxe déjà l'argile (C5), sait faire du feu ici (C7) — et en oubliant une
boulette séchée dans la braise il **découvre** qu'elle durcit pour toujours. La
boulette, le colombin, le four — toute la chaîne émerge.

N'introduit AUCUN nouveau tell minéral : COMPOSE C5 (argile + ``pottery_grade`` +
``ceramic_grade``) × C7 (feu + ``fine_fuel``). Pas de ``_PROFILE``, pas d'entrée
``PY_TO_RUST`` (garde-fou D8 — 3ᵉ fois par composition après C7/C8). Hors glob
``*_outcrop.py``.

Physique de la cuisson (veille 2026-06-16, archéométrie) : pointe d'un feu ouvert
~600–850 °C (selon ``fine_fuel``) × maturation de l'argile — terre commune
schisteuse ~700 °C (cuit au feu de camp), kaolin réfractaire ~1250 °C (sous-cuit
au feu ouvert : il faut un four). ``firedness = min(1, peak/maturation)``.

L'inversion réfractaire (le mensonge rendu visible — pendant de l'obsidienne C8) :
le **kaolin** (la *meilleure* argile, ``ceramic_grade`` True) **sous-cuit** au feu
ouvert et donne un objet **pire** qu'une humble terre cuite à cœur. La leçon
émergente : cuis la terre banale, pas la belle argile blanche — tant que tu n'as
qu'un feu nu. ``watertight`` toujours False en feu ouvert (pas de four).

Effet 1+1>2 : cuisson possible QUE si argile (C5) ET feu (C7) coexistent.

Seed 0xBEEF : continent de prairie (argile schisteuse partout + foyers) produisant
des sites cuisibles réels (terre saine).

Checks
------
 1.  Le monde Genesis réel produit des sites de cuisson émergents (argile + feu).
 2.  « Le monde ne ment jamais » : cue ⇒ fireable ; argile réelle (C5) + feu
     faisable (C7) ; ware == SSOT ; peak dans [min,max] ; watertight False. 0 viol.
 3.  Boucle de découverte : argile+foyer → ``firing_preview`` fireable & ware ;
     kaolin+foyer → fireable mais sous-cuit (mensonge visible ; aperçu non mutant).
 4.  Déterminisme même-seed : affordances bit-identiques.
 5.  Physique : terre saine vs kaolin sous-cuit (inversion) + porte du feu
     (argile sans feu = non cuisible).
 6.  Hiérarchie : ``best_firing_site_near`` préfère la plus haute ware (terre saine).
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
from engine.world import CHUNK_SIDE_M                               # noqa: E402
import engine.clay_outcrop as cl                                    # noqa: E402
import engine.fire_ignition as fi                                   # noqa: E402
import engine.ceramic_firing as cf                                  # noqa: E402

SEED = 0xBEEF       # grassland continent — shaly clay everywhere + hearths
GRID = 12
OUT = os.path.join(ROOT, "journals", "p141_ceramic_firing.jsonl")

results: list = []

_GRASS = 6
_SAVANNA = 9
_BOREAL = 3


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:58s} {detail}")


def _fake_chunk(w=0.0, biome=_GRASS, side=8):
    return SimpleNamespace(
        water=np.full((side, side), w, dtype=np.float32),
        biome=np.full((side, side), biome, dtype=np.uint8),
        height=np.full((side, side), 300.0, dtype=np.float32))


def _layer(top, bottom, rock="sandstone", ore=None):
    return StrataLayer(depth_top_m=top, depth_bottom_m=bottom, rock_type=rock,
                       density_kg_m3=2400.0, ore_mix=dict(ore or {}))


def _earthenware():
    return [_layer(0.0, 4.0, "shale")]


def _kaolin():
    return [_layer(0.0, 4.0, "sandstone", ore={"fine_clay": 0.06})]


def _derive(coord, layers, biome, chunk):
    clay = cl._cue_from_geology(coord, layers, biome, chunk)
    fire = fi._cue_from_geology(coord, layers, biome, chunk)
    return cf._cue_from_inputs(coord, clay, fire)


def _build():
    cfg = SimConfig(name="p141", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    cf.install_ceramic_firing(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 78)
    print("P141 — ceramic firing (emergent clay→pottery transformation: C5×C7)")
    print("=" * 78)

    sim, coords = _build()
    summary = cf.firing_summary(sim)
    print(f"  region: {len(coords)} chunks | fireable={summary['n_chunks_fireable']} "
          f"(sound={summary['n_sound']} underfired={summary['n_underfired']}) "
          f"| best_ware={summary['best_ware_quality']} "
          f"best_peak={summary['best_peak_temp_c']}°C")
    print(f"  clays: {summary['by_clay_material']}")

    # 1 — emergent fireable sites from the real world
    check("1 — Genesis world emits emergent firing sites (clay + fire)",
          summary["n_chunks_fireable"] > 0,
          f"{summary['n_chunks_fireable']}/{summary['n_chunks']} fireable; "
          f"clays={summary['by_clay_material']}")

    # 2 — the world never lies
    violations = 0
    for coord in coords:
        cue = cf.firing_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        if not cue.fireable:
            violations += 1
        if cue.watertight:               # open fire never vitrifies
            violations += 1
        if not (cf.OPEN_FIRE_MIN_C <= cue.peak_temp_c <= cf.OPEN_FIRE_MAX_C):
            violations += 1
        if cue.ware_quality != cf.fired_ware_quality(cue.pottery_grade, cue.firedness):
            violations += 1
        # C5 really sees this clay here...
        clay = cl.clay_cue_for_chunk(sim, coord)
        if clay is None or clay.material != cue.clay_material:
            violations += 1
        # ...and C7 really can make a fire here.
        if fi.ignition_cue_for_chunk(sim, coord) is None:
            violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ argile C5 + feu C7 ; ware==SSOT)",
          violations == 0, f"violations={violations}")

    # 3 — discovery loop : a real firing site previews fireable & names the ware ;
    #     a synthetic kaolin outcrop with fire is seen as the prime clay but
    #     under-fires (the lie). Preview is non-mutating.
    fcoord = next((c for c in coords
                   if cf.firing_cue_for_chunk(sim, c) is not None), None)
    fire_ok = lie_ok = False
    if fcoord is not None:
        cx, cy, _ = fcoord
        sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
        g = geo.chunk_geology(sim, fcoord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        out = cf.firing_preview(sim, float(sim.agents.pos[0, 0]),
                                float(sim.agents.pos[0, 1]))
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        seen = cf.prospect_firing(sim, float(sim.agents.pos[0, 0]),
                                  float(sim.agents.pos[0, 1]))
        fire_ok = (seen is not None and out["fireable"] is True
                   and 0.0 <= out["ware_quality"] <= 1.0
                   and out["watertight"] is False
                   and after == before)
        print(f"        agent SEES clay='{seen.clay_material}' "
              f"peak={seen.peak_temp_c:.0f}°C mat={seen.maturation_temp_c:.0f}°C "
              f"→ fired={seen.firedness:.2f} ware={seen.ware_quality:.2f} "
              f"({'sound' if seen.is_sound else 'UNDERFIRED'})")
    # synthetic kaolin + fire: the prime clay, but the open fire under-fires it.
    kao_layers = _kaolin()
    kao_cue = _derive((0, 0, 0), kao_layers, _GRASS, _fake_chunk(biome=_GRASS))
    kao_prev = cf.firing_preview(
        SimpleNamespace(
            streamer=SimpleNamespace(cache={(0, 0, 0): _fake_chunk(biome=_GRASS)}),
            _geology_state=SimpleNamespace(chunks={
                (0, 0, 0): ChunkGeology(coord=(0, 0, 0), layers=kao_layers)})),
        4.0, 4.0)
    lie_ok = (kao_cue is not None and kao_cue.underfired
              and kao_prev["fireable"] is True and kao_prev["underfired"] is True
              and kao_prev["watertight"] is False
              and kao_prev["vitrifies_if_kiln_fired"] is True)
    print(f"        kaolin outcrop + fire → fireable={kao_prev['fireable']} "
          f"underfired={kao_prev['underfired']} watertight={kao_prev['watertight']} "
          f"(looks ideal, but a bare fire can't vitrify it — needs a kiln)")
    check("3 — découverte : argile+foyer cuit ; kaolin sous-cuit (mensonge visible)",
          fire_ok and lie_ok,
          f"firing_site={fire_ok} kaolin_underfires={lie_ok}")

    # 4 — determinism (rebuild fresh: sim mutated by agent move above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = cf.firing_cue_for_chunk(sim2, coord)
        y = cf.firing_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.clay_material, round(x.peak_temp_c, 3),
                                     round(x.firedness, 6),
                                     round(x.ware_quality, 6))
        ky = None if y is None else (y.clay_material, round(y.peak_temp_c, 3),
                                     round(y.firedness, 6),
                                     round(y.ware_quality, 6))
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (affordances identiques)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — firing physics: earthenware sound vs kaolin underfired + the fire gate
    earth = _derive((0, 0, 0), _earthenware(), _GRASS, _fake_chunk(biome=_GRASS))
    kaolin = _derive((0, 0, 0), _kaolin(), _GRASS, _fake_chunk(biome=_GRASS))
    earth_nofire = _derive((0, 0, 0), _earthenware(), _BOREAL,
                           _fake_chunk(biome=_BOREAL))
    physics_ok = (
        earth is not None and earth.is_sound and not earth.underfired
        and earth.ware_quality == earth.pottery_grade
        and kaolin is not None and kaolin.underfired and not kaolin.is_sound
        and kaolin.watertight is False and kaolin.vitrifies_if_kiln_fired is True
        and earth.ware_quality > kaolin.ware_quality      # the inversion
        and earth_nofire is None)                         # the 1+1>2 gate
    check("5 — physique : terre saine > kaolin sous-cuit (inversion) + porte du feu",
          physics_ok,
          f"earth_ware={earth.ware_quality if earth else None} "
          f"kaolin_ware={kaolin.ware_quality if kaolin else None} "
          f"earth_sound={earth.is_sound if earth else None} "
          f"kaolin_underfired={kaolin.underfired if kaolin else None} "
          f"earth_nofire=None")

    # 6 — best_firing_site_near prefers the highest ware (sound earthenware)
    cx, cy, _ = coords2[len(coords2) // 2]
    cc = (cx, cy, 0)
    ch = sim2.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, _GRASS,
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.zeros(np.asarray(ch.water).shape, dtype=np.float32)
    sim2._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=_earthenware())
    sim2._clay_cue_cache.clear()
    sim2._ignition_cue_cache.clear()
    sim2._firing_cue_cache.clear()
    sim2.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim2.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    r = 0.4 * CHUNK_SIDE_M
    best = cf.best_firing_site_near(sim2, 0, perception_radius_m=r)
    pick_ok = (best is not None and best.fireable
               and best.clay_material == "shale" and best.is_sound)
    check("6 — best_firing_site préfère la plus haute ware (terre saine)",
          pick_ok, f"best_is_sound_earthenware={pick_ok}")

    # 7 — zero tick cost / idempotent install
    c1 = cf.install_ceramic_firing(sim)
    c2 = cf.install_ceramic_firing(sim)
    check("7 — installation idempotente, coût tick nul",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p141_ceramic_firing", "seed": SEED,
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
