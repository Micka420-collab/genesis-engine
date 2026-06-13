# Capacité Substrate C4 — Affleurement de combustible (découverte d'énergie émergente)

**Date :** 2026-06-13 · **Module :** `engine.combustible_outcrop` · **Smoke :** `p136` (7/7) · **Tests :** `tests/test_combustible_outcrop.py` (18) + contrat cross-langage +1 · **pytest global : 467/467**

> **Ce n'est PAS une Wave d'observateur.** C'est une **capacité** : un signal de
> monde interrogeable que les agents consomment pour **agir** (couper, sécher,
> brûler, fondre). Elle ne wrappe pas `sim.step` et n'ajoute **aucun coût au
> tick** (indices dérivés paresseusement par chunk, mémorisés). Elle respecte
> donc le **moratoire observateurs** (`CONTRIBUTING.md` §"Moratoire observateurs").

## Motivation — la branche organique de la géologie, totalement muette

C1 (`surface_mineralization`) a livré la découverte du **minerai métallique**,
C2 (`lithic_outcrop`) celle de la **pierre taillée**, C3 (`water_potability`)
celle de l'**eau potable**. Mais toute la branche **ORGANIQUE** de la géologie —
`peat` / `coal` / `oil_shale` (catégorie `MineralCategory.ORGANIC`, **déjà semée
dans l'`ore_mix` des couches** par `engine.geology`) — restait **muette** :

> Aucun signal de surface ne disait à un agent *où trouver la roche/terre qui
> brûle*. Le combustible était dans le sol, mais le monde n'en montrait rien.

Or « la roche noire mate qui brûle longtemps » amorce la **révolution
énergétique** que le prompt **World Realism v2.0** décrit explicitement
(SYSTÈME F, chaîne « CHARBON → ÉNERGIE ») : feu durable → four en argile +
charbon → température de fusion → **métallurgie**. C4 rend ce premier maillon
perceptible — sans rien scripter.

**Règle d'émergence absolue respectée** : l'agent ne *sait* pas que ça brûle. Il
PERÇOIT une terre/roche **noire et mate**, sa spongiosité gorgée d'eau ; se
souvient ; coupe, sèche, allume — ou apprend qu'une veine sèche brûle là où elle
affleure. On n'a jamais scripté « ceci brûle » ; on a rendu **l'exposition
carbonée et son humidité détectables**.

## Combo veille (D1 × D2) — rang houiller × porte d'humidité

Veille 2026-06-13 (`docs/veille/2026-06-13_VEILLE_combustible_outcrop.md`) :

**D1 — Rang houiller / grade calorifique.** La série des combustibles fossiles
s'ordonne par rang croissant : **tourbe < schiste bitumineux < charbon**
(< lignite < bitumineux < anthracite dans la nature). On en tire un
`calorific_grade` intrinsèque et un seuil `SMELTING_GRADE` (seul le charbon
atteint la température de fusion d'un four).

| Matériau | `FuelClass` | grade | hygroscopie | `smelting_grade` | tell (rgb) |
|----------|-------------|-------|-------------|------------------|------------|
| `coal` | `COAL` | 0.85 | 0.25 | ✅ | **(20,20,20)** noir mat |
| `oil_shale` | `OIL_SHALE` | 0.55 | 0.40 | ❌ | (95,85,70) brun-gris |
| `peat` | `PEAT` | 0.35 | 1.00 | ❌ | (60,45,35) noir spongieux |

**D2 — Porte d'humidité (moisture-of-extinction).** Une tourbière est un milieu
**gorgé d'eau** : la tourbe qu'on y voit ne brûle pas tant qu'elle n'est pas
**coupée puis séchée** (seuil d'extinction de Rothermel, SYSTÈME E). On dérive
une **humidité ambiante** (biome + champ `chunk.water`), pondérée par
l'**hygroscopie** du matériau → `effective_moisture = ambient × hygroscopy`.

**Effet 1+1>2** : la géologie organique (SYSTÈME C) est reliée à l'hydrologie de
surface (SYSTÈME A). La même tourbière qu'on VOIT (`burnable_now = False`,
`dry_to_burn = True`) impose la boucle émergente **couper → sécher → brûler** ;
le charbon dense et peu hygroscopique brûle là où il affleure ; le grade pilote
ensuite `smelting_grade` → un **activateur de technologie** émergent.

## Le monde ne ment jamais — dérivation depuis le substrat

| Garantie | Vérité indépendante |
|----------|---------------------|
| cue émis | combustible réel dans une couche `≤ MAX_SEAM_DEPTH_M (6 m)` — `rock_type == material` (`lithology`) ou `ore_mix[material] ≥ MIN_VISIBLE_FRACTION` (`ore`), la **même colonne** que lit `mine_at` ; `collect_depth_m` y rend le matériau |
| `burnable_now` | `grade ≥ MIN_FUEL_GRADE` **ET** `effective_moisture ≤ MOISTURE_EXTINCTION` (biome + `chunk.water` + hygroscopie) |
| `smelting_grade` | `grade ≥ SMELTING_GRADE (0.70)` — seul le charbon |
| océan | masqué (combustible submergé) |

Réciproque volontairement *faible* (un filon sous 200 m de sédiment ne trahit
rien en surface) — l'agent prospecte. Honnête, et préserve l'émergence.

**Invariants prouvés** (smoke `p136` sur monde réel boréal seed `0xB0`, 66/144
chunks cués = 24 charbon + 42 tourbe, **0 violation** ; + 18 tests synthétiques) :
peat en bog gorgé d'eau → vu mais `dry_to_burn` ; charbon sec → `burnable_now` +
`smelting_grade`.

## Boucle de découverte (end-to-end, prouvée)

`prospect_fuel(x, y)` → l'agent **perçoit** l'exposition (couleur + label).
`ignite_preview(x, y)` → **aperçu non mutant** de ce que brûler donnerait
(`sustains_fire`, `smelting_grade`, `dry_to_burn`) sans démarrer aucun feu ni
muter la géologie. `best_fuel_near(row, …, require_burnable, require_smelting)` →
le pick actionnable (charbon préféré ; saute la tourbe trop humide ; ne garde que
le combustible de grade fusion quand on cherche la chaleur du métal).

* monde Genesis réel (boréal `0xB0`) : `prospect_fuel` sur un chunk charbon →
  `sustains_fire = True`, `smelting = True` ; sur un chunk tourbe gorgée d'eau →
  `sustains_fire = False`, `dry_to_burn = True` — **le mensonge du monde rendu
  visible** (ça *a l'air* brûlable, il faut couper & sécher), l'aperçu ne mute rien.

## Garde-fou cross-langage enrichi (ADR-0007)

Le moratoire exige que **toute capacité enrichisse `PY_TO_RUST`**. C4 le fait dans
`tests/test_geology_cross_language_contract.py` :
* **surface** enfin le `coal` (mappé spéculativement, jamais exposé jusqu'ici) ;
* **ajoute** `peat` et `oil_shale` (binnés au tell grossier Rust `Coal` — il n'y
  a pas de variante organique plus fine) ;
* **verrouille byte-exact** le tell charbon noir mat `(20,20,20)` ⇔
  `Mineral::Coal::surface_color()`, **miroir** du tell cuivre/malachite
  `(80,140,70)`. Toute dérive d'un côté casse le build.

## Émergence absolue, capacité (pas observateur), déterminisme

* **Perception-seule** : on n'altère NI le feu (`engine.wildfire`) NI une
  combustion : on expose le signal, l'agent agit. Apprendre noir-mat→feu et
  sec→durable reste à l'agent.
* **Capacité** : aucun hook `sim.step`, coût tick nul, cache paresseux par chunk.
* **Déterminisme** : pur (`chunk_geology` `prf_rng` + biome + `chunk.water`),
  aucun RNG nouveau, bit-identique même seed (check 4 du smoke).
* **ADR-0005** : `PIPELINE_LAYER = "Genesis-L1 Earth-Seed"`,
  `WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"` — module ajouté à
  `world_model_capabilities._REQUIRED_MODULES` (audité `ok`).

## Périmètre honnête (audit)

* La **diagenèse** tourbe→lignite→charbon (houillification par enfouissement/T°)
  n'est **pas** simulée : les rangs sont des matériaux distincts du catalogue,
  pas un continuum temporel. Piste future.
* Ne ferme **aucun** item Rust Phase A/B (A3/A4/A5/B1–B8 restent ouverts,
  `cargo` absent de l'env → CI = vérité). Capacité du **runtime Python live**.

## API publique

`install_combustible_outcrop(sim)` · `combustible_cue_for_chunk(sim, coord)` ·
`prospect_fuel(sim, x, y)` · `ignite_preview(sim, x, y)` (aperçu non mutant) ·
`discover_fuel_by_sight(sim, rows, r)` ·
`best_fuel_near(sim, row, r, require_burnable=…, require_smelting=…)` ·
`combustible_cue_summary(sim)`.

## Impact réalisme

Dimension **Géologie / relief 75 → 76** (branche organique du substrat rendue
perceptible : grade calorifique + porte d'humidité, découverte d'énergie
émergente, invariant « le monde ne ment jamais »). Global ~79,4 % → **~79,6 %**.
