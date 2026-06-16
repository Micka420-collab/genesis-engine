# Cap. C8 — `lithic_tempering` : trempe thermique de la pierre (transformation)

**Date :** 2026-06-16 (J+6) · **Seed :** `0xBEEF` (prairie) · **Smoke :** `p140` (7/7)
**Tests :** +16 (`test_lithic_tempering.py`) · **pytest : 552/552**
**Mode :** scheduled task (Morning Routine v3.0, user absent) · veille-first.

---

## 1. Pourquoi — la première capacité de TRANSFORMATION

L'audit J+5 (`native/world-engine/AUDIT-DELTA-2026-06-15.md` §7) recommandait, après
la voûte du feu (C7) : **(b)** écrire `crates/STATUS.md`, *puis* **(a)** livrer la
**première capacité de TRANSFORMATION** (et non de perception) — exemple cité :
*« tempering (chauffer pierre C2 pour la rendre taillable) »*, **par composition
pure, sans nouvelle entrée `PY_TO_RUST`**. Les deux sont livrés ce jour.

C1→C6 *montrent* une matière ; C7 *amorce* un feu. **C8 change une propriété** :
`base_quality` → `tempered_quality`. C'est la première fois qu'une capacité
**transforme** le monde au lieu de le *lire*.

**Veille du jour (PAPER_DU_JOUR) :** *ARYA — Physics-Constrained Composable &
Deterministic World Model* (arxiv 2603.21340). Sa thèse — déterminisme +
composition sous contrainte physique — est exactement la discipline C1→C7 ;
elle valide la règle « C8 = composition pure, 0 nouveau primitive ». Combo retenu :
**ARYA × C8**.

**Ancrage archéologique :** le traitement thermique de la silice cryptocristalline
(silex/chert/silcrète) est la **plus ancienne pyrotechnologie connue après le feu
lui-même**, **antérieure à la poterie et à la métallurgie** — attesté à **Pinnacle
Point (~72 ka)** sur le silcrète, puis tout au long du Méso/Néolithique européen.
Chauffé lentement à ~250–400 °C, le chert se déshydrate, le gel de silice se
réorganise : la fracture conchoïdale devient nettement plus régulière (débitage
plus facile, bords plus nets, matière plus cassante).

## 2. Ce qui est livré

`runtime/engine/lithic_tempering.py` — **lit** C2 `lithic_outcrop`
(`lithic_cue_for_chunk` : pierre, classe de fracture, `knap_quality` incl.
silex/chert) **×** C7 `fire_ignition` (`ignition_cue_for_chunk` : feu faisable).

- `tempered_quality(base, kind)` — **SSOT** déterministe et borné (`TEMPER_CEILING`
  = 0,95 ; même l'excellent chert chauffé reste sous l'obsidienne fraîche 1,0).
- `TemperCue` — affordance véridique : pierre, `silica_kind`, `base_quality`,
  `tempered_quality`, `quality_gain`, méthode de feu, `confidence`.
- `temper_cue_for_chunk` / `prospect_tempering` / `temper_preview` (non mutant) /
  `discover_temper_sites_by_sight` / `best_temper_site_near` / `tempering_summary`.

### Les quatre réponses de la silice (et le mensonge rendu visible)
| Pierre | `silica_kind` | Gain | Note |
|--------|---------------|------|------|
| Silex / chert (quartz + hôte carbonaté, C2 `CHERT_BONUS`) | `chert` | **+0,20** | la matière reine du traitement thermique |
| Quartz / quartzite (macrocristallin, hors carbonate) | `quartzite` | +0,12 | réponse modeste |
| **Obsidienne** (déjà du verre volcanique) | `obsidian` | **0** | **le mensonge** : la *meilleure* pierre (1,0), mais le feu ne l'améliore pas |
| Basalte / ardoise / calcaire (non conchoïdal) | `none` | 0 | pas de bord à gagner par la chaleur |

## 3. Invariants tenus

- **« Le monde ne ment jamais ».** Un cue ⇒ `temperable` : la pierre réactive
  existe réellement (C2, même colonne que `mine_at`) **ET** le feu est faisable
  (C7). Prouvé sur le monde Genesis réel (seed `0xBEEF`, **84/144 chunks
  temperables = 76 chert + 8 quartzite, 0 violation**) + boucle **silex+foyer se
  trempe / obsidienne+foyer vue comme idéale mais aucun gain** (`temper_preview`
  non mutant).
- **Effet 1+1>2.** Trempe possible QUE si silice réactive (C2) ET feu (C7)
  coexistent : un silex en forêt boréale détrempée (C7 muet) n'est pas trempable
  *ici*. Une seule vérité de substrat (pierre + feu), une lecture nouvelle.
- **Émergence absolue.** On rend détectable que *cette pierre-ci, chauffée,
  deviendrait taillable à tel point* — jamais « chauffe ton silex pour faire un
  meilleur outil ». Le four, l'enfouissement, la durée, le refroidissement lent
  restent émergents. L'agent découvre la corrélation feu+silex→meilleur outil en
  agissant.
- **Garde-fou D8 par COMPOSITION (2ᵉ démonstration après C7).** Pas de `_PROFILE`,
  **aucune** entrée `PY_TO_RUST`/`PY_CATALOGUE_ONLY` ; fichier **hors glob**
  `*_outcrop.py`. Asservi par `test_introduces_no_new_tell`. `PY_TO_RUST` reste à
  **15 entrées** (inchangé depuis C6).
- **Capacité, pas observateur.** 0 hook `sim.step`, dérivation paresseuse memoïsée,
  **coût tick nul** → conforme au moratoire (garde D1).
- **Déterminisme bit-à-bit** (composition de cues `prf_rng`, 0 RNG nouveau).

## 4. Gap honnête

- La **cinétique** du traitement (rampe de température, durée, refroidissement
  lent), le **risque de fracture par sur-chauffe** et la perte de matière ne sont
  pas simulés : C8 expose l'affordance et l'**outcome ground-truthé**, pas une
  thermodynamique de four.
- L'amélioration est un **Δ additif borné**, pas un continuum dépendant du
  protocole réel.
- **Ne ferme aucun item Rust Phase A/B** (perception/transformation Python ; le
  worldgen Rust reste gelé Wave 42, cf. ADR-0008 / R-J4-1).

## 5. Aussi livré ce jour — `crates/STATUS.md` (R1)

`native/world-engine/crates/STATUS.md` ferme **R1** du `BLIND-SPOTS-AUDIT-2026-06-13`
(dette de transparence J+30) : les **23 crates** classées (20 active / 2 entrypoints
/ 1 dormant `gpu` / 1 orpheline `geology`=ADR-0007), par inspection source (cargo
absent → CI = vérité), avec ⚠ explicite sur `scenario` (compile non vérifiable ici ;
un audit 2026-06-09 le notait cassé).

---

**Fichiers :** `runtime/engine/lithic_tempering.py`,
`runtime/tests/test_lithic_tempering.py`,
`runtime/scripts/p140_lithic_tempering_smoke.py`,
`native/world-engine/crates/STATUS.md`,
`docs/veille/2026-06-16_VEILLE_lithic_tempering.md`.
