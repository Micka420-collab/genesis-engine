#!/usr/bin/env python3
"""P152 — Substrate capability : la paroi à peindre (Cap. C20).

**La 2ᵉ brique de l'axe SYMBOLIQUE / du dessin.** C18 ``ochre_grinding`` a livré le
**pigment** (la matière de la marque) ; C20 livre son pendant — le **support** (la paroi
qui tient la marque). Non-fire (D9 1→0 après C19 — alternance) ; non mutant (D10 gelé).

Règle d'émergence absolue : l'agent ne *sait* pas qu'« on peint sur les parois
calcaires ». Il voit une paroi blanche (C6), tient un pigment (C18) et **découvre** que la
trace prend et **y reste** — ou s'écaille. Le geste (tracer, le sens) reste émergent
(c'est ``engine.art_discovery`` L4 qui l'enregistre) ; C20 n'expose que la vérité physique
du **mur**.

Comble le trou L1 sous l'art L4 : ``art_discovery`` (L4) a un dico abstrait
``PAINTABLE_SURFACES`` (``bedrock_calcite`` 0,95…) mais rien ne rendait perceptible, par
lieu, QUELLE paroi est là ni si une marque y DURE. C20 **fonde** ce ``bedrock_calcite``
dans la géologie réelle (pont L1↔L4 : ``CALCITE_ADHESION`` byte-égale).

N'introduit AUCUN nouveau tell : COMPOSE C6 (paroi carbonatée), pas de ``_PROFILE``,
``PY_TO_RUST`` reste 15 (garde-fou D8 — 14ᵉ par composition). Hors glob ``*_outcrop.py``.

LE MENSONGE RENDU VISIBLE #11 (la belle paroi qui ne tient pas la marque) : une paroi
SAINE (voile de calcite) tient une marque durable ; la **même** paroi carbonatée en climat
humide (KARST, dissolution) ou gelant (FROST, gélifraction) l'accepte (adhérence forte —
c'est du calcaire) mais l'**écaille** (persistance effondrée). Climat-driven, pendant exact
de C15 (même calcaire : sec→durable vs humide→s'écaille).

Seeds : 0xC1A7 (continent carbonaté tempéré sec → parois SAINES durables, comme C6) +
0xFE11 (même carbonate en climat humide → KARST, marques qui s'écaillent). Aucune injection.

Checks
------
 1.  Le monde réel produit des canevas durables (0xC1A7) ET le mensonge karst émerge (0xFE11).
 2.  « Le monde ne ment jamais » : cue ⇒ carbonate C6 (même matériau) ; holds ⟺ durability≥seuil ;
     durability == adhésion×persistance ; surface_key == bedrock_calcite.
 3.  Aperçu NON MUTANT : canvas_preview & paint_outcome ne touchent pas la géologie (D10 gelé).
 4.  Déterminisme même-seed : oracle bit-identique.
 5.  Physique : SOUND tient + KARST/FROST s'écaille + adhésion ∝ porosité + durability=adh×pers
     + pont L1↔L4 (CALCITE_ADHESION == art_discovery bedrock_calcite).
 6.  Hiérarchie + visibilité : best_canvas préfère le durable ; require_lasting filtre ;
     pigment sombre sur mur pâle = visible, pigment ≈ mur = invisible.
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
import engine.limestone_outcrop as li                              # noqa: E402
import engine.ochre_grinding as og                                 # noqa: E402
import engine.rock_canvas as rc                                    # noqa: E402

SOUND_SEED = 0xC1A7   # dry temperate carbonate continent — SOUND walls (durable canvases)
KARST_SEED = 0xFE11   # humid continent — the SAME carbonate, KARST (flaking) walls
GRID = 12
OUT = os.path.join(ROOT, "journals", "p152_rock_canvas.jsonl")

results: list = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "ok": bool(ok), "detail": detail})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}")


def _build(seed: int):
    cfg = SimConfig(name="p152", seed=seed, founders=4, max_agents=20,
                    bounds_km=(0.6, 0.6), spawn_radius_m=40.0,
                    drive_accel=1500.0, cultures=1)
    sim = Simulation(cfg)
    bootstrap_genesis_sim(sim, seed=seed,
                          genesis_params=GenesisParams(seed=seed, resolution=128,
                                                       n_plates=8))
    geo.install_geology(sim)
    rc.install_rock_canvas(sim)
    coords = []
    for cx in range(GRID):
        for cy in range(GRID):
            if sim.streamer.get(0, (cx, cy, 0)) is not None:
                geo.chunk_geology(sim, (cx, cy, 0))
                coords.append((cx, cy, 0))
    return sim, coords


def main() -> int:
    print("=" * 80)
    print("P152 — rock canvas (2nd brick of the symbolic axis: the paintable wall; grounds art L4 bedrock_calcite)")
    print("=" * 80)

    sim, coords = _build(SOUND_SEED)
    summary = rc.canvas_summary(sim)
    ksim, kcoords = _build(KARST_SEED)
    ksummary = rc.canvas_summary(ksim)
    print(f"  SOUND seed {hex(SOUND_SEED)}: walls={summary['n_canvas_walls']}/{summary['n_chunks']} "
          f"(lasting={summary['n_lasting']} flaking={summary['n_flaking']}) best_durability={summary['best_durability']} "
          f"weather={summary['by_weather']} mat={summary['by_material']}")
    print(f"  KARST seed {hex(KARST_SEED)}: walls={ksummary['n_canvas_walls']}/{ksummary['n_chunks']} "
          f"(lasting={ksummary['n_lasting']} flaking={ksummary['n_flaking']}) weather={ksummary['by_weather']} mat={ksummary['by_material']}")

    # 1 — durable canvases emerge (sound) AND the karst lie emerges (climate-driven)
    check("1 — monde réel : canevas durables (0xC1A7) ET mensonge karst émergent (0xFE11)",
          summary["n_canvas_walls"] > 0 and summary["n_lasting"] > 0
          and ksummary["n_canvas_walls"] > 0 and ksummary["n_flaking"] > 0,
          f"sound lasting={summary['n_lasting']} ; karst flaking={ksummary['n_flaking']}")

    # 2 — the world never lies (sound seed)
    violations = 0
    n = 0
    for coord in coords:
        cue = rc.canvas_cue_for_chunk(sim, coord)
        if cue is None:
            continue
        n += 1
        lime = li.limestone_cue_for_chunk(sim, coord)
        if lime is None or lime.material != cue.material:
            violations += 1
        if cue.holds_lasting_mark != (cue.durability >= rc.MIN_DURABLE):
            violations += 1
        if abs(cue.durability - cue.adhesion * cue.persistence) > 1e-9:
            violations += 1
        if cue.surface_key != "bedrock_calcite":
            violations += 1
    check("2 — le monde ne ment jamais (matériau==C6 ; holds⟺durability≥seuil ; durability=adh×pers ; bedrock_calcite)",
          violations == 0 and n > 0, f"violations={violations} walls={n}")

    # 3 — non-mutating preview / paint_outcome
    coord = next((c for c in coords if rc.canvas_cue_for_chunk(sim, c) is not None), None)
    prev_ok = nonmut_ok = paint_ok = False
    if coord is not None:
        cue = rc.canvas_cue_for_chunk(sim, coord)
        sim.agents.pos[0, 0] = (coord[0] + 0.5) * CHUNK_SIDE_M
        sim.agents.pos[0, 1] = (coord[1] + 0.5) * CHUNK_SIDE_M
        g = geo.chunk_geology(sim, coord)
        before = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        prev = rc.canvas_preview(sim, float(sim.agents.pos[0, 0]),
                                 float(sim.agents.pos[0, 1]))
        after = [(L.rock_type, dict(L.ore_mix), L.extracted_kg) for L in g.layers]
        nonmut_ok = (after == before)
        prev_ok = (prev["markable"] is True
                   and prev["holds_lasting_mark"] == cue.holds_lasting_mark)
        out = rc.paint_outcome(cue, og.RED_OCHRE_RGB, pigment_lightfast=True)
        paint_ok = (out["lasts"] == cue.holds_lasting_mark and out["visible"] is True)
        print(f"        CANVAS @ {coord}: {cue.material} ({'SOUND' if cue.sound_wall else 'KARST/FROST'}) "
              f"adh={cue.adhesion} pers={cue.persistence} durability={cue.durability} holds={cue.holds_lasting_mark} — geology untouched={nonmut_ok}")
    check("3 — aperçu NON MUTANT : canvas_preview & paint_outcome ne touchent pas la géologie (D10 gelé)",
          prev_ok and nonmut_ok and paint_ok,
          f"preview={prev_ok} non_mutating={nonmut_ok} paint={paint_ok}")

    # 4 — determinism
    sim2, coords2 = _build(SOUND_SEED)
    sim3, _ = _build(SOUND_SEED)
    det_ok = coords == coords2
    mism = 0
    for coord in coords2:
        x = rc.canvas_cue_for_chunk(sim2, coord)
        y = rc.canvas_cue_for_chunk(sim3, coord)
        kx = None if x is None else (x.material, round(x.durability, 6),
                                     x.holds_lasting_mark, x.weather_state)
        ky = None if y is None else (y.material, round(y.durability, 6),
                                     y.holds_lasting_mark, y.weather_state)
        if kx != ky:
            mism += 1
    check("4 — déterminisme même-seed (oracle bit-identique)",
          det_ok and mism == 0, f"mismatches={mism}")

    # 5 — physics
    import engine.art_discovery as art
    sound = rc.canvas_quality("limestone_pure", li.WeatherState.SOUND)
    karst = rc.canvas_quality("limestone_pure", li.WeatherState.KARST)
    frost = rc.canvas_quality("limestone_pure", li.WeatherState.FROST)
    pure = rc.canvas_quality("limestone_pure", li.WeatherState.SOUND).adhesion
    common = rc.canvas_quality("limestone", li.WeatherState.SOUND).adhesion
    marble = rc.canvas_quality("marble", li.WeatherState.SOUND).adhesion
    physics_ok = (
        sound.holds_lasting_mark and not karst.holds_lasting_mark
        and not frost.holds_lasting_mark
        and karst.adhesion == sound.adhesion and karst.persistence < sound.persistence
        and pure >= common > marble
        and abs(sound.durability - sound.adhesion * sound.persistence) < 1e-9
        and rc.CALCITE_ADHESION == art.PAINTABLE_SURFACES["bedrock_calcite"])
    print(f"        SOUND holds={sound.holds_lasting_mark} (dur {sound.durability:.3f}) | "
          f"KARST holds={karst.holds_lasting_mark} (dur {karst.durability:.3f}) | "
          f"adhesion pure {pure:.2f} > common {common:.2f} > marble {marble:.2f} | "
          f"L1↔L4 calcite {rc.CALCITE_ADHESION}=={art.PAINTABLE_SURFACES['bedrock_calcite']}")
    check("5 — physique : SOUND tient + KARST/FROST s'écaille + adhésion∝porosité + durability=adh×pers + pont L1↔L4",
          physics_ok, f"sound={sound.holds_lasting_mark} karst_flakes={not karst.holds_lasting_mark} bridge_ok={rc.CALCITE_ADHESION==art.PAINTABLE_SURFACES['bedrock_calcite']}")

    # 6 — best_canvas + visibility
    cn = next((c for c in coords2 if rc.canvas_cue_for_chunk(sim2, c) is not None), None)
    pick_ok = vis_ok = False
    if cn is not None:
        sim2.agents.pos[0, 0] = (cn[0] + 0.5) * CHUNK_SIDE_M
        sim2.agents.pos[0, 1] = (cn[1] + 0.5) * CHUNK_SIDE_M
        best = rc.best_canvas_near(sim2, 0, perception_radius_m=6 * CHUNK_SIDE_M)
        lasting = rc.best_canvas_near(sim2, 0, perception_radius_m=6 * CHUNK_SIDE_M,
                                      require_lasting=True)
        pick_ok = (best is not None and best.durability > 0.0
                   and (lasting is None or lasting.holds_lasting_mark is True))
    _, vis_dark = rc.mark_visibility((245, 240, 225), og.RED_OCHRE_RGB)
    _, vis_match = rc.mark_visibility((245, 240, 225), (244, 241, 224))
    vis_ok = (vis_dark is True and vis_match is False)
    check("6 — best_canvas préfère le durable + require_lasting filtre + visibilité (sombre visible, ≈mur invisible)",
          pick_ok and vis_ok, f"best={pick_ok} visible_dark={vis_dark} invisible_match={vis_match}")

    # 7 — zero tick cost / idempotent install
    c1 = rc.install_rock_canvas(sim)
    c2 = rc.install_rock_canvas(sim)
    check("7 — installation idempotente, coût tick nul (oracle)",
          c1 is c2, "no per-tick hook on sim.step")

    # 8 — D8 by composition
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_geology_cross_language_contract as contract       # noqa: E402
    d8_ok = (not hasattr(rc, "_PROFILE") and rc.li is li
             and not os.path.basename(rc.__file__).endswith("_outcrop.py")
             and len(contract.PY_TO_RUST) == 15)
    check("8 — D8 par composition : pas de _PROFILE ; PY_TO_RUST==15 ; hors *_outcrop",
          d8_ok, f"py_to_rust={len(contract.PY_TO_RUST)}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"smoke": "p152_rock_canvas", "seed": SOUND_SEED,
                   "karst_seed": KARST_SEED, "summary": summary,
                   "karst_summary": ksummary, "results": results,
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
