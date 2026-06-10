# Wave 63 — Concavité de chenal / χ-steepness (loi de Flint + méthode χ)

**Date :** 2026-06-10 · **Module :** `engine.concavity_observer` · **Smoke :** `p132`

## Motivation

La veille du 2ᵉ cycle du jour
([`docs/veille/2026-06-10_VEILLE_Wave63_concavity.md`](../veille/2026-06-10_VEILLE_Wave63_concavity.md),
DÉCOUVERTE_1 **loi de Flint** + DÉCOUVERTE_2 **méthode χ intégrale**, Perron &
Royden 2013) cible le **3ᵉ descripteur fluvial canonique** encore non observé.
La Wave 49 (`watershed_observer`) quantifie la **topologie** du réseau (ordres de
Strahler, ratios de Horton, densité de drainage) ; la Wave 62
(`hypsometry_observer`) quantifie l'**aire–altitude** (courbe + intégrale
hypsométriques). Il manquait le **scaling pente–aire** du réseau de chenaux —
la signature directe de l'incision par stream-power.

Aucun nouveau substrat, aucun script : on lit les champs déjà émergents
`elevation_m`, `flow_dir` (D8) et `flow_acc` (aire drainée, en mailles) — comme
Waves 49/53/57 — et on **mesure** si le terrain produit par la chaîne tectonique
→ isostasie (Wave 59) → flexure (Wave 61) exhibe la loi. La loi est mesurée,
jamais imposée (conforme STONE-AGE).

## Modèles

### Loi de Flint (pente–aire)

Pour l'incision fluviale détachement-limitée, le modèle stream-power
`E = K·A^m·S^n` prédit, à l'état stationnaire sous soulèvement uniforme, une loi
de puissance pente–aire (Flint 1974 ; Hack 1957) :

```
S = k_s · A^(−θ)        θ = m/n  (indice de concavité)
log S = log k_s − θ · log A
```

Une régression OLS de `log S` sur `log A` sur les mailles de chenal récupère la
**concavité** `θ` (la pente, négativée) et la **raideur** `k_s` (l'ordonnée à
l'origine, exponentiée). Théorie et observation mondiale placent les chenaux
gradés dans une bande étroite **0,40 < θ < 0,60** (Wobus 2006 ; Kirby & Whipple
2012).

### Méthode χ (chi) intégrale — Perron & Royden 2013

La pente le long du chenal est une dérivée locale bruitée. La méthode intégrale
la remplace par une coordonnée transformée intégrée **vers l'amont** depuis le
niveau de base :

```
χ(x) = ∫_{x_base}^{x} (A0 / A(x'))^θ_ref  dx'
```

Avec `θ_ref = 0,45` et `A0 = 1 m²`, un chenal stationnaire est **linéaire en χ** :
`z = z_base + ksn·χ`, de pente = la **raideur normalisée ksn** (proxy de taux
d'érosion, faible bruit, comparable entre bassins — Mudd 2014). χ est intégrée
par un **balayage déterministe aval→amont** (par `flow_acc` décroissant : l'aval
porte toujours strictement plus d'accumulation que ses contributeurs amont).

## Invariant pivot — récupération exacte de la loi de puissance

Le test central : un couple synthétique `(A, S)` construit comme `S = k_s·A^(−θ)`
est **inversé exactement** par la régression log-log. Mesuré : `θ` et `k_s`
récupérés à **< 1e-9**, `R² = 1`. Falsifié si la régression n'inverse pas la
construction.

## Invariants (prouvés par tests + smoke)

| Invariant | Vérification |
|-----------|--------------|
| **Récupération loi de Flint** | `S = k_s·A^-θ ⇒ θ, k_s` exacts (< 1e-9), `R² = 1` |
| **Invariance d'échelle de θ** | `θ(c·A) == θ(A)` et `θ(c·S) == θ(S)` (résidu ≤ 1e-9) |
| **χ ≥ 0 + niveau de base** | `χ ≥ 0` partout, `χ = 0` à l'embouchure (exact) |
| **χ monotone amont** | `χ` strictement croissante en remontant le chenal |
| **Linéarité χ–z** | `z = a + ksn·χ ⇒ ksn, a` exacts, `R² = 1` |
| Bornes | `R² ∈ [0,1]` pour les deux régressions |
| Bandes de concavité | convex / low / **graded (0,40–0,60)** / high / degenerate |
| Réseau vide / dégénéré | pas de crash, χ = 0, fit `(0,0,0)` |
| Lecture seule | `elevation_m`, `flow_dir`, `flow_acc`, `sim.tick` inchangés |
| Déterminisme | balayage par `(-acc, index)`, signature sha256 stable cross-sim |

## Surface

`ConcavityConfig` · `ConcavitySnapshot` · `ConcavityHistory` · `ConcavityState` ·
`channel_slope_area` · `fit_flint_law` · `chi_transform` · `fit_chi_elevation` ·
`concavity_stage` · `observe_concavity` · `install_concavity_observer` /
`uninstall_concavity_observer` · `concavity_summary`.

Réutilise `engine.discharge_observer` (`_resolve_world`, `_field`) — **aucune
duplication** de l'accès monde. Constantes D8 alignées sur `world_genesis` /
`watershed_observer`.

## Résultats

- `runtime/tests/test_concavity_observer.py` — **13/13** verts (9,7 s).
- `runtime/scripts/p132_concavity_smoke.py` — **10/10 PASS**. Invariants
  synthétiques exacts (`θ=0,5`, `k_s=2,0`, `R²=1` ; `ksn=3,5`, `R²=1` ; χ
  monotone). Monde Genesis **res 192** (réseau émergent réel de **109 mailles**,
  52 dans le fit) : `θ = −0,23`, `R² ≈ 0` — voir « Gaps honnêtes ».
- `ruff check` clean sur les 3 fichiers.
- `pytest runtime/tests` : **389/389** (376 + 13).
- Câblé dans `make validate-all` + CI (après `p131`).

## Impact réalisme

Deuxième descripteur géomorphologique falsifiable de la série aire–altitude
(Wave 62) : complète la quantification réseau (Wave 49) et la maturité de paysage
(Wave 62) par l'axe **pente–aire / steepness**, et offre un **double test
croisé** (loi de Flint *et* χ mesurent le même rapport m/n). Géologie/relief
**73 → 74 %** ; global ≈ **79,0 %** (moyenne 7 dimensions :
(80+74+73+76+82+86+82)/7 = 79,0 %).

## Gaps honnêtes / pistes

- **Le monde Genesis coarse (~20 km/maille à res 192) n'est PAS un paysage
  fluvial gradé.** Le relief est dominé par la tectonique + l'isostasie sans
  incision fluviale fine ; l'observateur rapporte donc honnêtement `R² ≈ 0` et
  une concavité hors bande (convex). C'est le comportement *correct* : la
  machinerie est prouvée exacte (invariants synthétiques), et sur terrain réel
  elle dit la vérité plutôt que d'inventer un fit. Une bande graded `0,40–0,60`
  n'émergera qu'avec une **érosion fluviale transitoire active** (couplage Exner
  ↔ DEM rétro-injecté, backlog Wave 57) à résolution fine.
- **Cross-check `θ_χ == θ_pente-aire`** : on rapporte la concavité pente–aire et
  le ksn χ à `θ_ref` fixe ; chercher le `θ` qui *linéarise au mieux* le plot χ–z
  et vérifier l'égalité avec le m/n de la régression est une extension naturelle
  (Wave 64+, backlog veille).
- **Variante par bassin** : ksn / concavité par `watershed_id` émergent (Wave 49)
  donnerait la raideur *par bassin*, usage géomorphologique classique — backlog.
- Régression OLS simple (non pondérée) ; le cadre statistique de Mudd 2014
  (segmentation, incertitude bayésienne) reste une extension possible.
