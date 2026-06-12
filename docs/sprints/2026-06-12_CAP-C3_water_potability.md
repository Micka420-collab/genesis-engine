# Capacité Substrate C3 — Potabilité de l'eau (découverte fresh/saline émergente)

**Date :** 2026-06-12 · **Module :** `engine.water_potability` · **Smoke :** `p135` (7/7) · **Tests :** `tests/test_water_potability.py` (15) · **pytest global : 441/441**

> **Ce n'est PAS une Wave d'observateur.** C'est une **capacité** : un signal de
> monde interrogeable que les agents consomment pour **agir** (aller boire la
> bonne eau). Elle ne wrappe pas `sim.step` et n'ajoute **aucun coût au tick**
> (indices dérivés paresseusement par chunk, mémorisés). Elle respecte donc le
> **moratoire observateurs** (`CONTRIBUTING.md` §"Moratoire observateurs").

## Motivation — la ressource la plus fondamentale de toutes, muette d'une façon *fausse*

C1 (`surface_mineralization`) a livré la découverte du **minerai** (âge du
bronze), C2 (`lithic_outcrop`) celle de la **pierre taillée** (âge de pierre).
Mais la ressource **la plus fondamentale de toutes** — l'**eau potable**, sans
laquelle un agent meurt en ~3 jours, **avant** la faim, **avant** l'outil —
restait muette, et d'une façon **physiquement fausse** :

> `engine.physiology` (action `DRINK`) réduit la soif pour **n'importe quelle**
> cellule d'eau, **y compris l'eau de mer**. Le monde laissait un agent
> « boire l'océan » et être hydraté. Aucun signal ne distinguait l'eau douce
> qui sauve de la saumure qui tue.

Tout être vivant lit la salinité **par le goût**. C'est exactement ce que Cap.
C3 rend perceptible — sans rien scripter. Le prompt **World Realism v2.0**
appelle d'ailleurs ce signal explicitement (SYSTÈME A : « Nappe phréatique →
sources, oasis » ; SYSTÈME C/F : « source dont l'eau a un goût salé », « Agent :
lèche l'eau → mémoire "goût particulier" »).

**Règle d'émergence absolue respectée** : l'agent ne *sait* pas quelle eau le
sustente. Il PERÇOIT un goût (sucré/salé), une croûte de sel sur un rivage
stérile, un miroitement clair ; se souvient ; revient boire — ou crache. On
n'a jamais scripté « ne bois pas l'eau de mer » ; on a rendu **la salinité
détectable**.

## Modèle de salinité (véridique, calibré veille — non scripté)

Bandes calibrées sur la veille 2026-06-12 (WHO/EPA TDS + océanographie,
`docs/veille/2026-06-12_VEILLE_water_potability.md`) :

| Bande | ppt (g/L) | `WaterTaste` | Potable |
|-------|-----------|--------------|---------|
| Eau douce (douce) | ≤ 0.2 | `FRESH` | ✅ |
| Eau douce (dure / minéralisée) | 0.2 – 0.5 | `MINERAL` | ✅ |
| Saumâtre marginale | 0.5 – **3.0** (`POTABLE_MAX_PPT`) | `BRACKISH` | ✅ (limite) |
| Salée | 3.0 – 30 | `SALINE` | ❌ |
| Mer / saumure | ≥ 30 (mer **35**, saumure ≤ 300) | `BRINE` | ❌ |

`potable ⇔ salinity_ppt ≤ POTABLE_MAX_PPT (3.0)` — seuil physiologique de
déshydratation nette (> ~5 ppt = impropre à la consommation régulière).

## Le monde ne ment jamais — dérivation depuis des vérités *indépendantes*

La salinité n'est jamais un nombre arbitraire : elle est dérivée de truths déjà
présentes dans le substrat (toutes issues du seed) :

| Source (`cue.source`) | Vérité indépendante déclenchante | ppt |
|-----------------------|----------------------------------|-----|
| `sea` | biome dominant `OCEAN` | 35 (eau de mer) |
| `brine_spring` | **halite** peu profonde (≤ 8 m) dans `chunk_geology` — la *même* colonne que lit `mine_at` / la croûte de sel de **C1** | ∝ teneur (≤ 300) |
| `coastal` | eau posée au niveau / sous le niveau marin (`élévation moyenne ≤ COASTAL_MARGIN_M`) | mélange estuarien linéaire 35 → 0 |
| `fresh` | eau intérieure en altitude, sans halite | dureté carbonatée (0.05 soft / 0.40 hard) |

**Une seule couche de substrat, deux indices** : un banc de halite peu profond
fait *à la fois* affleurer la croûte de sel (C1) **et** saler la source (C3).
Cohérence physique garantie.

**Invariants prouvés** (smoke `p135` + `tests/test_water_potability`) :

1. tout indice ⇒ le chunk a de **vraies** cellules d'eau (`water ≥ WET_CELL_MIN
   = 5 L`, le même prédicat que `physiology`) — il y a de quoi boire là ;
2. indice **potable** ⇒ biome dominant ≠ `OCEAN` **ET** pas de saumure halite
   peu profonde **ET** `ppt ≤ POTABLE_MAX_PPT` — on ne qualifie JAMAIS l'eau de
   mer / la saumure de potable ;
3. indice **mer** ⇒ biome `OCEAN` ; indice **saumure** ⇒ halite peu profonde.

Réciproque volontairement *faible* (une eau peut être potable sans indice si
l'agent ne l'a pas goûtée) — on ne donne pas la carte des points d'eau ; l'agent
prospecte. Honnête, et préserve l'émergence.

## Boucle de découverte (end-to-end, prouvée)

`prospect_water(x, y)` → l'agent **perçoit** le goût + la couleur du plan d'eau.
`drink_at(x, y)` → **aperçu non mutant** de ce que boire donnerait : lit le
**vrai** champ `chunk.water` que consomme `physiology.DRINK`, plus la salinité,
sans toucher NI l'eau NI la soif. `hydrating = potable ∧ eau réellement présente`.

* monde Genesis réel (seed `0xFACE`, hautes terres ~577 m, 100 % chunks
  d'eau douce **dure** à 0.4 ppt) : `prospect_water` → `MINERAL`, potable ;
  `drink_at` → `hydrating = True`.
* océan injecté sur la tuile de l'agent : `prospect_water` → `sea`, 35 ppt, non
  potable ; `drink_at` → `hydrating = False` — **le mensonge du monde rendu
  visible**, l'aperçu ne mute rien.
* `nearest_potable_water(row)` saute l'eau salée pour l'eau douce voisine : un
  agent assoiffé au bord de mer doit marcher vers l'intérieur, exactement comme
  dans la réalité.

## Émergence absolue, capacité (pas observateur), déterminisme

* **Perception-seule** : on n'altère PAS `DRINK` pour pénaliser l'eau de mer
  (changement comportemental risqué, hors moratoire). C3 livre la *perception* ;
  apprendre goût↔hydratation reste à l'agent ; corriger la physiologie est un
  travail futur honnête.
* **Capacité** : aucun hook `sim.step`, coût tick nul, cache paresseux par chunk.
* **Déterminisme** : pur (`chunk.biome`/`height`/`water` + `chunk_geology`
  `prf_rng`), aucun RNG nouveau, bit-identique même seed (check 4 du smoke).
* **ADR-0005** : `PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`,
  `WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"` — audité `ok` par
  `world_model_capabilities.audit_modules()` (module ajouté à `_REQUIRED_MODULES`).

## Périmètre honnête (audit)

* La **nappe phréatique** (groundwater / loi de Darcy, SYSTÈME A du prompt)
  **n'est pas** modélisée : l'eau reste un champ de **surface** (`chunk.water`).
  La salinité d'une source intérieure dérive donc de la géologie peu profonde,
  pas d'un solveur d'écoulement souterrain. Piste future = hydrologie
  différentiable (veille D3, δHBV-globe ; NeuralGCM pour le forçage pluie).
* Ne ferme **aucun** item Rust Phase A/B (A3/A4/A5/B1–B8 restent ouverts,
  `cargo` absent de l'env → CI = vérité). Capacité du **runtime Python live**.

## API publique

`install_water_potability(sim)` · `water_cue_for_chunk(sim, coord)` ·
`prospect_water(sim, x, y)` · `drink_at(sim, x, y)` (aperçu non mutant) ·
`discover_water_by_sight(sim, rows, r)` · `nearest_potable_water(sim, row, r)` ·
`water_cue_summary(sim)`.

## Impact réalisme

Dimension **Écologie / hydrologie 73 → 74** (première *capacité* de découverte de
l'eau potable : la salinité devient perceptible et véridique, comblant une muette
physiquement fausse de `physiology.DRINK`). Global ~79,3 % → **~79,4 %**.
