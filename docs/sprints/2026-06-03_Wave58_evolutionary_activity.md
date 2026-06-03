# Wave 58 — Open-endedness / activité évolutive (Bedau–Packard)

**Date :** 2026-06-03 · **Module :** `engine.evolutionary_activity` · **Smoke :** `p127`

## Motivation

La veille du jour ([`docs/veille/2026-06-03_VEILLE.md`](../veille/2026-06-03_VEILLE.md),
DÉCOUVERTE_2 — « A speciation simulation that partly passes open-endedness
tests », de Pinho & Sinapayen, arXiv 2603.01701, 2026) propose une **métrique
d'émergence vérifiable** alignée pile sur l'ADN du projet (**ZERO PRE-SCRIPT** +
[`FALSIFIABILITY.md`](../../FALSIFIABILITY.md)) : les **statistiques d'activité
évolutive de Bedau–Packard** (Bedau & Packard 1992 ; Bedau, Snyder & Packard
1998). Aujourd'hui `emergence_metrics.py` mesure des KPIs instantanés ; cette
Wave ajoute un **test objectif** de la question centrale du projet : *« la
civilisation produit-elle vraiment de la nouveauté soutenue, ou plafonne-t-
elle ? »*. Purement **observateur** (lit l'historique des innovations/gènes
émergents), donc **hors du chemin déterministe** de `Simulation.step()`.

## Modèle (Bedau–Packard)

À partir d'une *série d'usage* `u` — par tick, une application
`composant → incrément` (typiquement `1` quand le composant est présent/utilisé)
— on définit l'**activité cumulée** du composant `i` au tick `t` :

```
a_i(t) = Σ_{τ ≤ t} u_i(τ)
```

puis les courbes diagnostiques classiques :

- **Diversité** `D(t)` — nombre de composants déjà vus à `t` (monotone non
  décroissante ; sa croissance est le signal d'open-endedness) ;
- **Activité cumulée totale** `A(t) = Σ_i a_i(t)` ;
- **Activité moyenne** `Ā(t) = A(t) / D(t)` (shadow neutre analytique : valeur
  attendue si l'activité totale était répartie uniformément) ;
- **Taux d'innovation** `n_new(t) = D(t) − D(t−1)` — cœur du test OEE : une
  nouveauté **soutenue** ⇒ open-endedness.

Un **seuil shadow neutre** `= facteur · Ā` sépare les composants
*adaptativement significatifs* (qui persistent plus que la dérive neutre).

La **classification** est pilotée par la **nouveauté**, pas par l'activité
cumulée brute (qui croît trivialement dès qu'un composant persiste) : sur la
dernière fraction `tail_fraction` du run,

- run trop court (`< min_steps`) ⇒ **`insufficient`** ;
- aucune nouveauté en queue ⇒ **`none`** (système figé / scripté) ;
- taux de nouveauté soutenu `≥ unbounded_rate` ⇒ **`unbounded`** (open-ended) ;
- nouveauté présente mais décroissante ⇒ **`bounded`** (saturation).

Ce choix évite l'**artefact de persistance** qui ferait passer tout système
non vide pour « unbounded ».

## Composants émergents lus (read-only)

`component_usage(sim)` assemble, de façon défensive et **namespacée**, le jeu
de composants *présents* sans jamais muter le monde :

- `inv:<id>` — inventions de `sim.invention_registry.artifacts` ;
- `rec:<id>` — recettes de `sim._emergent_construction.discovered` ;
- `lex:<id>` — tokens de lexique émergent (memetic), si exposés.

Aucun composant n'est *imposé* : l'observateur lit ce que le run émergent a
produit et **score** sa dynamique de nouveauté.

## Invariants prouvés (smoke `p127` + tests)

- **Fermeture additive** : `A(T) == Σ_i a_i(T)` (résidu = 0.00e+00) ;
- **Diversité** monotone non décroissante et `Σ n_new == D_final` ;
- **Classification falsifiable** : série figée ⇒ `none` ; série saturante
  (nouveauté sur les carrés parfaits, taux → 0) ⇒ `bounded` ; série ouverte
  (un composant neuf par tick) ⇒ `unbounded` ; série trop courte ⇒
  `insufficient` ;
- **Seuil shadow** = facteur · activité moyenne ; comptage des significatifs
  cohérent ;
- **Read-only** sur monde Genesis : tick et lecture d'usage inchangés ;
- **Déterminisme** : signature `sha256` stable cross-sim (même seed) ;
- **Install idempotent / uninstall** restaure `sim.step` ; capture à la cadence.

`p127` — **10/10 PASS**. `tests/test_evolutionary_activity.py` — **11/11**
verts ; voisins observateurs (sediment / hydrograph / discharge / compaction)
verts ; `ruff` clean. Câblé dans `make validate-all` + CI (après `p126`).

## API publique

`EvoActivityConfig` / `EvoActivityStats` / `EvoActivitySnapshot` /
`EvoActivityHistory` / `EvoActivityState` ; fonctions pures world-free
(`diversity_curve`, `new_component_curve`, `component_activity`,
`total_activity_curve`, `mean_activity_curve`, `significance_threshold`,
`n_significant_components`, `classify_dynamics`, `evolutionary_activity_stats`) ;
`component_usage`, `observe_evolutionary_activity` (read-only) ;
`install_evolutionary_activity_observer` / `uninstall_...` (idempotents) ;
`evolutionary_activity_summary` (dashboard / `/api/emergence_metrics`).

## Lien falsifiabilité

Nouveau critère **falsifiable** pour [`FALSIFIABILITY.md`](../../FALSIFIABILITY.md) :
un run `terre`/`origins` *réellement* non scripté doit, sur un long horizon,
produire une dynamique `bounded` ou `unbounded` (nouveauté non nulle) ; une
classification `none` soutenue est une **réfutation** observable de la
prétention d'émergence ouverte.

## Gaps honnêtes

- **Shadow neutre analytique** simple (activité moyenne) au lieu d'un shadow
  Monte-Carlo (runs neutres randomisés) — délibéré pour rester **déterministe**
  et sans dépendance ; un calibrateur shadow hors-ligne reste backlog.
- **Composant = innovation présente** (présence ⇒ +1) ; une pondération par
  *usage réel* (fréquence d'emploi par les agents) affinerait l'activité.
- **Classification par taux de queue** (seuil `unbounded_rate`) plutôt que par
  ajustement statistique des classes de Bedau (Tokyo type-1) — suffisant pour
  un verdict falsifiable, raffinement statistique en backlog.
- Pas encore exposé dans `/api/emergence_metrics` ni l'Earth Console (la
  fonction `evolutionary_activity_summary` est prête pour le câblage).
