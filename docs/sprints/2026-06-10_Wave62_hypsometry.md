# Wave 62 — Hypsométrie / maturité de paysage (Strahler)

**Date :** 2026-06-10 · **Module :** `engine.hypsometry_observer` · **Smoke :** `p131`

## Motivation

La veille du jour ([`docs/veille/2026-06-10_VEILLE.md`](../veille/2026-06-10_VEILLE.md),
DÉCOUVERTE_1 — **ARYA**, world model *physics-constrained, composable et
déterministe*, arXiv 2603.21340) fournit le cadre méthodologique exact de la
série d'observateurs Genesis : une loi de la nature à la fois, déterministe,
read-only, composable. Appliqué au **gap géologie « descripteurs de maturité du
paysage »**, cela donne la pièce manquante du couple altitude–surface.

La Wave 49 (`watershed_observer`) quantifie déjà le **réseau de drainage**
(ordres de Strahler, ratios de Horton, densité de drainage) et expose un
**HI scalaire *par bassin*** comme simple sous-produit `(mean−min)/(max−min)`,
côté dimension *hydrologie*. La Wave 62 le **généralise** côté *géologie* en
descripteur falsifiable complet : la **courbe** hypsométrique (fonction de
survie) *à l'échelle de la carte*, l'**identité de Pike-Wilson** comme invariant
prouvé (`trapz(courbe) == HI`), l'**invariance affine**, les **étages de
Strahler** (youthful/mature/monadnock) et la **skewness** signée. Aucun nouveau
substrat, aucun script : on lit le champ `elevation_m` déjà émergent (comme
Waves 53/57/59/61) et on *rapporte* la forme de sa distribution d'altitude.

## Modèle (hypsométrie de Strahler 1952)

Hauteur relative `h* = (h − h_min) / (h_max − h_min) ∈ [0, 1]`. La **courbe
hypsométrique** est la fonction de survie de la distribution de `h*` :

```
a*(h*) = fraction de mailles dont l'altitude relative ≥ h*
```

non croissante, de `a*(0) = 1` à `a*(1) ≈ 0`. L'**intégrale hypsométrique** est
l'aire sous cette courbe :

```
HI = ∫₀¹ a*(h*) dh*
```

Étages empiriques de Strahler : `HI > 0,60` *youthful* (déséquilibre, soulèvement
dominant) · `0,35 ≤ HI ≤ 0,60` *mature* (équilibre) · `HI < 0,35` *monadnock*
(pénéplaine, érosion dominante).

## Invariant pivot — identité de Pike-Wilson

L'intégrale de la fonction de survie d'une variable bornée non négative **égale
sa moyenne**. Donc l'aire sous la courbe échantillonnée vaut, à la tolérance de
discrétisation, le **ratio élévation-relief** en forme close :

```
HI = (mean(h) − h_min) / (h_max − h_min)            (Pike & Wilson 1971)
```

C'est l'invariant falsifiable central : `|trapz(courbe) − HI|` mesuré
**2,2e-07** (synthétique 512 bins) et **8,7e-05** (monde réel Genesis 64²).

## Invariants (prouvés par tests + smoke)

| Invariant | Vérification |
|-----------|--------------|
| **Identité Pike-Wilson** | `trapz(a*) == HI` (résidu < 1e-3 ; réel = 8,7e-05) |
| Bornes | `HI ∈ [0,1]`, courbe ∈ [0,1] |
| Survie monotone | `a*` non croissante, `a*(0) = 1` exact |
| **Invariance affine** | `HI(a·h + b) == HI(h)`, a > 0 (résidu = 0) |
| Datum rampe linéaire | altitude uniforme ⇒ `HI = 0,5` exact |
| Étages de Strahler | `x^0,25 → youthful` ; `x^1 → mature` ; `x^4 → monadnock` |
| Skewness signée | paysage vieux ⇒ skew > 0 ; jeune ⇒ skew < 0 |
| Relief plat | `HI = 0`, étage `degenerate`, skew = 0 (pas de NaN) |
| Lecture seule | `flow_dir`, `elevation_m`, `sim.tick` inchangés |
| Déterminisme | signature sha256 stable cross-sim |

## Surface

`HypsometryConfig` · `HypsometrySnapshot` · `HypsometryHistory` ·
`HypsometryState` · `relative_elevation` · `hypsometric_integral` ·
`hypsometric_curve` · `hypsometric_skewness` · `hypsometric_stage` ·
`observe_hypsometry` · `install_hypsometry_observer` /
`uninstall_hypsometry_observer` · `hypsometry_summary`.

Réutilise `engine.discharge_observer` (`_resolve_world`, `_field`) — **aucune
duplication** de l'accès monde.

## Résultats

- `runtime/tests/test_hypsometry_observer.py` — **15/15** verts.
- `runtime/scripts/p131_hypsometry_smoke.py` — **10/10 PASS**. Monde Genesis
  64² : `land_fraction ≈ 0,40`, `HI = 0,263` (étage *monadnock*), `skew = 1,05`
  — signature **bimodale continent/océan** réaliste (masse concentrée sur le
  plancher océanique profond), résidu Pike-Wilson 8,7e-05.
- `ruff check` clean ; voisins géologie/émergence `p128`–`p130` verts.
- `pytest runtime/tests` : **376/376** (361 + 15).
- Câblé dans `make validate-all` + CI (après `p130`).

## Impact réalisme

Premier **descripteur de maturité de paysage** émergent : complète la
quantification réseau (Wave 49) par l'axe aire–altitude, et offre un test
falsifiable de cohérence (Pike-Wilson) sur tout champ d'élévation produit par la
chaîne tectonique → isostasie (Wave 59) → flexure (Wave 61). Géologie/relief
**72 → 73 %** ; global ≈ **78,9 %** (moyenne 7 dimensions :
(80+73+73+76+82+86+82)/7 = 78,86 %).

## Gaps honnêtes / pistes

- Hypsométrie calculée sur **tout le champ** (continents + océans), d'où la
  forme bimodale terrestre ; une variante **par bassin versant** (sur le
  `watershed_id` émergent de la Wave 49) donnerait l'étage de maturité
  *par bassin*, plus proche de l'usage géomorphologique classique — backlog.
- Étages de Strahler = **seuils empiriques** (0,35 / 0,60) ; non recalibrés sur
  une base de référence terrestre (Earth global HI ≈ 0,40 sur terre émergée).
- Descripteur **statique** : l'évolution temporelle de `HI` (signature du
  passage soulèvement → équilibre → pénéplaine) émergerait d'un run long avec
  lit mobile rétro-injecté (couplage Exner ↔ DEM, encore backlog Wave 57).
- Skewness/kurtosis exposées comme moments standard ; la skewness *de la courbe*
  au sens strict de Strahler (densité hypsométrique) reste une extension
  possible.
