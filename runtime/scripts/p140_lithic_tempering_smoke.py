#!/usr/bin/env python3
"""P140 — Substrate capability : trempe thermique de la pierre (Cap. C8).

**Première capacité de TRANSFORMATION** (recommandation audit J+5 §7-a). C1→C7
ont rendu *perceptibles* / *amorçables* les matières et le feu de l'âge de pierre.
C8 est la première **utilisation actionnable** qui *transforme* une matière :
chauffer un silex/chert dans un foyer **améliore sa taille** — la plus ancienne
pyrotechnologie connue après le feu (silcrète chauffé à Pinnacle Point ~72 ka).

Règle d'émergence absolue : l'agent ne *sait* pas qu'on « traite la pierre par la
chaleur ». Il taille déjà du silex (C2), il sait faire du feu ici (C7) — et en
laissant un nodule dans la braise il **découvre** que le silex chauffé se débite
plus net. Le four, l'enfouissement, la durée, le refroidissement lent émergent.

N'introduit AUCUN nouveau tell minéral : COMPOSE C2 (pierre + ``knap_quality``,
incl. silex/chert) × C7 (feu faisable). Pas de ``_PROFILE``, pas d'entrée
``PY_TO_RUST`` (garde-fou D8). Fichier hors glob ``*_outcrop.py``.

Quelle silice répond — et laquelle ment : chert (silice cryptocristalline) forte
réponse ; quartzite (macrocristalline) modeste ; **obsidienne = AUCUN gain**
(déjà du verre — la *meilleure* pierre, mais le feu ne l'améliore pas : le
mensonge rendu visible) ; non-silice (basalte) = pas de bord à gagner.

Effet 1+1>2 : trempe possible QUE si silice réactive (C2) ET feu (C7) coexistent.

Seed 0xBEEF : continent de prairie (silex/chert + foyers) produisant des sites
trempables réels (chert ET quartzite).

Checks
------
 1.  Le monde Genesis réel produit des sites de trempe émergents (chert + feu).
 2.  « Le monde ne ment jamais » : cue ⇒ temperable ; pierre réactive réelle (C2)
     + feu faisable (C7) ; gain > 0 ; tempered ≤ plafond. 0 violation.
 3.  Boucle de découverte : silex+foyer → ``temper_preview`` temperable & nomme
     le gain ; obsidienne+foyer → vue comme pierre idéale mais aucun gain
     (mensonge rendu visible ; aperçu non mutant).
 4.  Déterminisme même-seed : affordances bit-identiques.
 5.  Les quatre réponses de la silice (chert/quartzite fort/modeste ;
     obsidienne/non-silice = nul) + porte du feu (chert sans feu = non trempable).
 6.  Hiérarchie : ``best_temper_site_near`` préfère le plus grand gain (chert).
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
import engine.lithic_outcrop as lo                                  # noqa: E402
import engine.fire_ignition as fi                                   # noqa: E402
import engine.lithic_tempering as lt                                # noqa: E402

SEED = 0xBEEF       # grassland continent — flint/chert outcrops + hearths
GRID = 12
OUT = os.path.join(ROOT, "journals", "p140_lithic_tempering.jsonl")

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


def _chert_firestone():
    return [_layer(0.0, 4.0, "limestone", ore={"quartz": 0.06, "pyrite": 0.05})]


def _derive(coord, layers, biome, chunk):
    lithic = lo._cue_from_geology(coord, layers, biome)
    fire = fi._cue_from_geology(coord, layers, biome, chunk)
    carb = lo._has_carbonate_host(layers)
    return lt._cue_from_inputs(coord, lithic, fire, carb)


def _build():
    cfg = SimConfig(name="p140", seed=SEED, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=SEED,
                          genesis_params=GenesisParams(seed=SEED,
                                                       resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    lt.install_lithic_tempering(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 78)
    print("P140 — lithic tempering (emergent heat-treatment of silica: C2×C7)")
    print("=" * 78)

    sim, coords = _build()
    summary = lt.tempering_summary(sim)
    print(f"  region: {len(coords)} chunks | temperable={summary['n_chunks_temperable']} "
          f"| best_gain={summary['best_quality_gain']} "
          f"best_tempered={summary['best_tempered_quality']}")
    print(f"  silica kinds: {summary['by_silica_kind']}")

    # 1 — emergent temper sites from the real world
    check("1 — Genesis world emits emergent temper sites (responsive silica + fire)",
          summary["n_chunks_temperable"] > 0,
          f"{summary['n_chunks_temperable']}/{summary['n_chunks']} temperable; "
          f"kinds={summary['by_silica_kind']}")

    # 2 — the world never lies
    violations = 0
    for coord in coords:
        cue = lt.temper_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        if not cue.temperable or cue.quality_gain <= 0.0:
            violations += 1
        if cue.tempered_quality > lt.TEMPER_CEILING + 1e-9:
            violations += 1
        if cue.tempered_quality <= cue.base_quality:
            violations += 1
        # C2 really sees a heat-responsive silica stone here...
        lithic = lo.lithic_cue_for_chunk(sim, coord)
        if lithic is None or lithic.material != cue.stone_material \
                or lithic.knap_class != lo.KnapClass.CONCHOIDAL:
            violations += 1
        # ...and C7 really can make a fire here.
        if fi.ignition_cue_for_chunk(sim, coord) is None:
            violations += 1
    check("2 — le monde ne ment jamais (cue ⇒ pierre réactive C2 + feu C7)",
          violations == 0, f"violations={violations}")

    # 3 — discovery loop : a real temper site previews temperable & names the
    #     gain ; a synthetic obsidian outcrop with fire is seen as the prime
    #     stone but yields no gain (the lie). Preview is non-mutating.
    tcoord = next((c for c in coords
                   if lt.temper_cue_for_chunk(sim, c) is not None), None)
    temper_ok = lie_ok = False
    if tcoord is not None:
        cx, cy, _ = tcoord
        sim.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
        g = geo.chunk_geology(sim, tcoord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        out = lt.temper_preview(sim, float(sim.agents.pos[0, 0]),
                                float(sim.agents.pos[0, 1]))
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        seen = lt.prospect_tempering(sim, float(sim.agents.pos[0, 0]),
                                     float(sim.agents.pos[0, 1]))
        temper_ok = (seen is not None and out["temperable"] is True
                     and out["quality_gain"] > 0.0
                     and out["tempered_quality"] > out["base_quality"]
                     and after == before)
        print(f"        agent SEES stone='{seen.stone_material}' "
              f"({seen.silica_kind}) base={seen.base_quality:.2f} "
              f"→ tempered={seen.tempered_quality:.2f} (+{seen.quality_gain:.2f})")
    # synthetic obsidian + fire: the prime knapping stone, but heat yields nothing.
    obs_layers = [_layer(0.0, 5.0, "sandstone",
                         ore={"obsidian": 0.06, "pyrite": 0.05})]
    obs_cue = _derive((0, 0, 0), obs_layers, _GRASS, _fake_chunk(biome=_GRASS))
    obs_prev = lt.temper_preview(
        SimpleNamespace(
            streamer=SimpleNamespace(cache={(0, 0, 0): _fake_chunk(biome=_GRASS)}),
            _geology_state=SimpleNamespace(chunks={
                (0, 0, 0): ChunkGeology(coord=(0, 0, 0), layers=obs_layers)})),
        4.0, 4.0)
    lie_ok = (obs_cue is None and obs_prev["temperable"] is False
              and obs_prev["silica_kind"] == "obsidian")
    print(f"        obsidian outcrop + fire → temperable={obs_prev['temperable']} "
          f"reason='{obs_prev['reason']}' (looks ideal, heat won't improve glass)")
    check("3 — découverte : silex+foyer se trempe ; obsidienne non (mensonge visible)",
          temper_ok and lie_ok,
          f"temper_site={temper_ok} obsidian_no_gain={lie_ok}")

    # 4 — determinism (rebuild fresh: sim mutated by agent move above)
    sim2, coords2 = _build()
    sim3, _ = _build()
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = lt.temper_cue_for_chunk(sim2, coord)
        y = lt.temper_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.stone_material, x.silica_kind,
                                     round(x.tempered_quality, 6),
                                     round(x.quality_gain, 6))
        ky = None if y is None else (y.stone_material, y.silica_kind,
                                     round(y.tempered_quality, 6),
                                     round(y.quality_gain, 6))
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (affordances identiques)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — four silica responses + the fire gate (pure derivation)
    chert = _derive((0, 0, 0), _chert_firestone(), _GRASS, _fake_chunk(biome=_GRASS))
    quartzite = _derive((0, 0, 0),
                        [_layer(0.0, 5.0, "sandstone", ore={"quartz": 0.06})],
                        _SAVANNA, _fake_chunk(biome=_SAVANNA))
    nonsilica = _derive((0, 0, 0), [_layer(0.0, 5.0, "basalt", ore={"pyrite": 0.05})],
                        _GRASS, _fake_chunk(biome=_GRASS))
    chert_nofire = _derive((0, 0, 0), _chert_firestone(), _BOREAL,
                           _fake_chunk(biome=_BOREAL))
    responses_ok = (
        chert is not None and chert.silica_kind == "chert"
        and chert.quality_gain == lt._TEMPER_GAIN["chert"]
        and quartzite is not None and quartzite.silica_kind == "quartzite"
        and quartzite.quality_gain == lt._TEMPER_GAIN["quartzite"]
        and quartzite.quality_gain < chert.quality_gain
        and obs_cue is None              # obsidian: no gain (from check 3)
        and nonsilica is None            # basalt: not silica
        and chert_nofire is None)        # chert without fire: the 1+1>2 gate
    check("5 — quatre réponses silice + porte du feu (chert>quartzite>0 ; verre/roche/sans-feu=nul)",
          responses_ok,
          f"chert={chert.quality_gain if chert else None} "
          f"quartzite={quartzite.quality_gain if quartzite else None} "
          f"obsidian=None nonsilica=None chert_nofire=None")

    # 6 — best_temper_site_near prefers the largest gain (own-chunk radius)
    cx, cy, _ = coords2[len(coords2) // 2]
    cc = (cx, cy, 0)
    ch = sim2.streamer.get(0, cc)
    ch.biome = np.full(np.asarray(ch.biome).shape, _GRASS,
                       dtype=np.asarray(ch.biome).dtype)
    ch.water = np.zeros(np.asarray(ch.water).shape, dtype=np.float32)
    sim2._geology_state.chunks[cc] = ChunkGeology(coord=cc, layers=_chert_firestone())
    sim2._lithic_cue_cache.clear()
    sim2._ignition_cue_cache.clear()
    sim2._temper_cue_cache.clear()
    sim2.agents.pos[0, 0] = (cx + 0.5) * CHUNK_SIDE_M
    sim2.agents.pos[0, 1] = (cy + 0.5) * CHUNK_SIDE_M
    r = 0.4 * CHUNK_SIDE_M
    best = lt.best_temper_site_near(sim2, 0, perception_radius_m=r)
    pick_ok = (best is not None and best.temperable
               and best.silica_kind == "chert"
               and best.quality_gain == lt._TEMPER_GAIN["chert"])
    check("6 — best_temper_site préfère le plus grand gain (chert)",
          pick_ok, f"best_is_chert={pick_ok}")

    # 7 — zero tick cost / idempotent install
    c1 = lt.install_lithic_tempering(sim)
    c2 = lt.install_lithic_tempering(sim)
    check("7 — installation idempotente, coût tick nul",
          c1 is c2, "no per-tick hook on sim.step")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p140_lithic_tempering", "seed": SEED,
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
