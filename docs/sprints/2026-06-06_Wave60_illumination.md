# Wave 60 — Behavioral illumination / Quality-Diversity observer

**Date :** 2026-06-06
**Type :** observateur read-only, additif, pur CPU déterministe (ZERO PRE-SCRIPT)
**Module :** `runtime/engine/illumination_observer.py`
**Smoke :** `runtime/scripts/p129_illumination_smoke.py` — **10/10 PASS**
**Tests :** `runtime/tests/test_illumination_observer.py` — **16/16** verts

---

## Motivation (veille 2026-06-06, piste #3 — ASAL)

La veille du jour ([`docs/veille/veille-2026-06-06.md`](../veille/veille-2026-06-06.md))
retient **ASAL** (*Automating the Search for Artificial Life*, Sakana AI 2024)
dans son top-3 des cibles de construction. ASAL formalise trois mesures de
recherche ALife, dont l'**illumination d'une diversité d'espace** : couvrir un
espace comportemental ouvert plutôt qu'optimiser une cible unique. C'est un
candidat idéal car c'est une **couche d'observation/évaluation read-only** (hors
hot path) qui quantifie la nouveauté émergente **sans scripter** — conforme à la
philosophie du projet.

La Wave 58 (Bedau–Packard) a couvert l'axe **temporel** de l'open-endedness
(la nouveauté continue-t-elle d'apparaître ?). La Wave 60 couvre l'axe
**spatial** orthogonal : *quelle fraction de l'espace comportemental émergent
est réellement remplie, et avec quelle qualité ?*

ASAL s'appuie sur un **VLM** (vision-language model) pour définir le descripteur
comportemental — dépendance externe non déterministe que Genesis évite dans son
tick déterministe. Wave 60 porte donc **la mesure, pas le VLM** : elle implémente
les primitives CPU déterministes sur lesquelles repose la mesure d'illumination —
**MAP-Elites** (Mouret & Clune 2015) et la distance comportementale de
**novelty search** (Lehman & Stanley 2011). Le « descripteur VLM » reste un gap
backlog honnête.

## Ce qui est mesuré

À partir d'une liste de couples *(descripteur comportemental, qualité)* — un par
agent émergent — l'observateur discrétise l'espace descripteur en une grille
régulière de niches et conserve, par niche, l'**élite** (meilleure qualité).
De cette archive MAP-Elites :

- **coverage** — niches occupées / niches totales ∈ [0, 1] (l'illumination).
- **qd_score** — Σ qualité élite sur niches occupées (quality-diversity).
- **niche_entropy** — entropie de Shannon normalisée ∈ [0, 1] de la distribution
  de qualité ; 1.0 ⇔ qualité répartie uniformément sur les niches remplies.
- **behavioral_novelty** — distance moyenne aux `k` plus proches voisins dans
  l'espace descripteur (sparsité du nuage comportemental).
- mean / max quality, nombre de niches occupées, meilleure niche.

## Descripteur & qualité (émergents, jamais scriptés)

L'adaptateur par défaut lit les **traits de personnalité émergents** par agent
(Big-Five + traits Genesis hérités à `spawn_offspring`) comme axes du
descripteur (défaut : `curiosity` × `aggression`) et le **succès reproductif**
(`offspring_count`) comme qualité. Les deux sont produits par la simulation
elle-même ; l'observateur ne déclare jamais quels comportements *devraient*
exister ni n'assigne de cible. Lecture strictement read-only sur les arrays
`sim.agents` (agents `alive` uniquement) ; dégradation gracieuse (`[]`) si aucun
agent / trait n'est exposé.

## Contrat observateur (aligné Waves 49 / 53 / 55 / 57 / 58)

`IlluminationConfig` / `IlluminationStats` / `IlluminationSnapshot` /
`IlluminationHistory` / `IlluminationState` ; fonctions d'archive/métriques pures
world-free ; `observe_illumination` (read-only) ; `install_illumination_observer`
/ `uninstall_…` idempotents (wrap unique de `sim.step`) ;
`illumination_summary` (dict diagnostic, prêt pour `/api/emergence_metrics`).

## Invariants prouvés

- discrétisation = arithmétique entière `floor` (clamp `[lo, hi]`, `hi` → dernier
  bin) ⇒ bit-déterministe ;
- MAP-Elites conserve le **meilleur strict** par niche (tie-break premier-vu :
  écrasement seulement sur qualité *strictement* supérieure) ;
- `coverage` grille pleine = 1.0, vide = 0.0 ; `qd_score` = somme des élites ;
- `niche_entropy` qualité uniforme → 1.0, spike → bas, ≤ 1 niche → 0, qualité
  toute nulle mais ≥ 2 niches → uniforme (présence pure ⇒ évenness maximale) ;
- `behavioral_novelty` nuage étalé > cluster serré, `k` clampé à `n−1`,
  `< 2` comportements → 0 ;
- read-only (tick + behaviors inchangés après observation) ;
- signature sha256 déterministe cross-sim.

## Run réel (smoke p129, 4 founders, 20 ticks, monde Genesis 64²)

```
n_behaviors        : 4
n_dims / bins      : 2 / 8        (curiosity × aggression, grille 8×8)
total_niches       : 64
occupied_niches    : 4
coverage           : 0.0625
qd_score           : 0.0000       (pas encore de reproduction ⇒ qualité 0)
niche_entropy      : 1.0000       (présence pure ⇒ évenness maximale)
behavioral_novelty : 0.6168
best_niche         : (7, 3)
```

## Impact

Nouvelle **métrique d'émergence falsifiable** côté *Observation IA* /
*Sociétés-agents* : un run réellement non scripté doit, sur long horizon, voir
sa **coverage** et sa **behavioral_novelty** croître (la population explore
l'espace comportemental) ; une coverage figée à quelques niches est une
réfutation observable de la diversité émergente. Complément spatial direct de la
Wave 58 (axe temporel).

## Gaps honnêtes

- **descripteur VLM ASAL non porté** (délibéré — dépendance externe non
  déterministe) ; le descripteur est ici 2 traits émergents configurables ;
- qualité = `offspring_count` (proxy de fitness reproductif) — d'autres proxies
  émergents (prestige, inventions créditées) restent backlog ;
- grille 2D fixe (`bins`²) — MAP-Elites N-D supporté par le cœur mais l'adaptateur
  par défaut reste 2D pour l'interprétabilité ;
- pas de couplage CVT-MAP-Elites (niches Voronoï) ni d'archive non régulière ;
- non encore exposé dans `/api/emergence_metrics` / Earth Console
  (`illumination_summary` prêt pour le câblage).
